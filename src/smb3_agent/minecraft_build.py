"""Explicit Creative region ownership, durable intent and verified execution.

No model commands enter this boundary. Every write uses the worker's one scheduler;
server preconditions protect intervening edits, including during undo/recovery.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import re
import sqlite3
import shutil
import threading
import time


def inside(p, bounds):
    return all(
        type(p.get(k)) is int and bounds["min"][k] <= p[k] <= bounds["max"][k]
        for k in ("x", "y", "z")
    )


def validate_cells(cells, region):
    if not isinstance(cells, list) or not 1 <= len(cells) <= 64:
        raise ValueError("Build unit must contain 1–64 cells")
    seen = set()
    for c in cells:
        p = c["position"]
        key = tuple(p[k] for k in ("x", "y", "z"))
        if (
            key in seen
            or not inside(p, region["bounds"])
            or any(inside(p, b) for b in region["protected"])
        ):
            raise ValueError("Duplicate, out-of-region or protected build cell")
        seen.add(key)
        for field in ("before", "after"):
            if (
                not re.fullmatch(
                    r"[a-z_]+(?:\[[a-z_]+=[a-z0-9_]+(?:,[a-z_]+=[a-z0-9_]+)*\])?",
                    c[field],
                )
                or len(c[field]) > 256
            ):
                raise ValueError("Invalid canonical block state")
        if (
            c["before"].split("[")[0] in {"chest", "oak_door", "white_bed", "furnace"}
            and c["before"] != c["after"]
        ):
            raise ValueError(
                "Interactive block removal requires a future content-aware operation"
            )


class BuildConsole:
    """Private worker callback; only enabled on a marked app-owned Creative world."""

    def __init__(self, practice, region):
        marker = practice.home / "build-permission.json"
        if practice.survival or not marker.is_file():
            raise ValueError("This world has no Creative build permission")
        if json.loads(marker.read_text()) != {
            "world_id": practice.world_id,
            "region": region,
        }:
            raise ValueError("Build permission does not match this world/region")
        self.practice, self.region = practice, region
        self.lock = threading.Lock()

    def __call__(self, operation):
        if operation.get("mode") == "light":
            p, nonce = operation["position"], operation["nonce"]
            if not re.fullmatch("[a-f0-9]{32}", nonce) or not inside(
                p, self.region["bounds"]
            ):
                raise ValueError("Invalid light inspection")
            # Fixed server-side read-only predicate; no supplied command text.
            predicate = '{"condition":"minecraft:location_check","predicate":{"light":{"light":{"min":14}}}}'
            with self.lock:
                self.practice.command(
                    f"execute positioned {p['x']} {p['y']} {p['z']} if predicate {predicate} run say GC_LIGHT_{nonce}"
                )
                self.practice.command(f"say GC_BUILD_{nonce}")
            return
        if operation.get("mode") == "focus":
            p = operation["position"]
            b = self.region["bounds"]
            nonce = operation["nonce"]
            if not (
                re.fullmatch("[a-f0-9]{32}", nonce)
                and all(type(p.get(k)) is int for k in ("x", "y", "z"))
                and b["min"]["x"] <= p["x"] <= b["max"]["x"]
                and b["min"]["z"] <= p["z"] <= b["max"]["z"]
                and p["y"] == b["max"]["y"] + 8
            ):
                raise ValueError("Invalid terrain loading focus")
            with self.lock:
                self.practice.command(f"tp CompanionBot {p['x']} {p['y']} {p['z']}")
                self.practice.command(f"say GC_BUILD_{nonce}")
            return
        cells = operation["cells"]
        validate_cells(cells, self.region)
        nonce = operation["nonce"]
        if not re.fullmatch("[a-f0-9]{32}", nonce):
            raise ValueError("Invalid build receipt")
        conditions = " ".join(
            "if block {x} {y} {z} minecraft:{state}".format(
                **c["position"], state=c["before"]
            )
            for c in cells
        )
        mode = operation["mode"]
        if mode not in {"batch", "bulk"}:
            raise ValueError("Unsupported build transport")
        # Bulk merges only a complete contiguous X row with identical before/after.
        ordered = sorted(cells, key=lambda c: c["position"]["x"])
        first, last = ordered[0], ordered[-1]
        row = all(
            c["position"]["y"] == first["position"]["y"]
            and c["position"]["z"] == first["position"]["z"]
            and c["before"] == first["before"]
            and c["after"] == first["after"]
            for c in cells
        )
        row = row and last["position"]["x"] - first["position"]["x"] + 1 == len(cells)
        with self.lock:
            if mode == "bulk" and row:
                a, b = first["position"], last["position"]
                self.practice.command(
                    f"execute {conditions} run fill {a['x']} {a['y']} {a['z']} {b['x']} {b['y']} {b['z']} minecraft:{first['after']}"
                )
            else:
                # Per-cell CAS still preserves concurrent changes when a unit partially succeeds.
                for c in cells:
                    p = c["position"]
                    xyz = f"{p['x']} {p['y']} {p['z']}"
                    self.practice.command(
                        f"execute if block {xyz} minecraft:{c['before']} run setblock {xyz} minecraft:{c['after']}"
                    )
            self.practice.command(f"say GC_BUILD_{nonce}")


class BuildProject:
    """One named region and durable write-ahead units; construction never auto-resumes."""

    def __init__(self, root, world_id, region, bridge):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.bridge, self.region, self.world_id = bridge, region, world_id
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.state, self.error = "idle", None
        self.terrain_active = False
        self.architecture_active = False
        self.architecture_progress = {}
        self.terrain_progress = {}
        self.undo_skipped = []
        self.metrics = {}
        self.db = sqlite3.connect(self.root / "project.sqlite", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY, value TEXT); CREATE TABLE IF NOT EXISTS units (id INTEGER PRIMARY KEY, revision INTEGER, cells TEXT, status TEXT, elapsed REAL); CREATE TABLE IF NOT EXISTS designs (revision INTEGER PRIMARY KEY, cells TEXT);"
        )
        identity = json.dumps({"world": world_id, "region": region}, sort_keys=True)
        row = self.db.execute("SELECT value FROM identity WHERE id=1").fetchone()
        if row and row[0] != identity:
            raise ValueError("Project world/region mismatch")
        self.db.execute("INSERT OR IGNORE INTO identity VALUES (1,?)", (identity,))
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS terrain_manifests (revision INTEGER PRIMARY KEY, body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS terrain_stages (manifest INTEGER, ordinal INTEGER, digest TEXT, design_revision INTEGER, PRIMARY KEY(manifest, ordinal));"
        )
        if "completed" not in {
            r[1] for r in self.db.execute("PRAGMA table_info(terrain_stages)")
        }:
            self.db.execute(
                "ALTER TABLE terrain_stages ADD COLUMN completed INTEGER NOT NULL DEFAULT 0"
            )
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS architecture_reviews (id INTEGER PRIMARY KEY, body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS architecture_stages (review INTEGER, component TEXT, digest TEXT, design_revision INTEGER, completed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(review,component));"
        )
        self.db.commit()
        self.revision = self.db.execute(
            "SELECT COALESCE(MAX(revision),0) FROM designs"
        ).fetchone()[0]

    def inspect(self, positions):
        started = time.monotonic()
        result = self.bridge.call("inspect_build", {"positions": positions})
        self.metrics["observation_seconds"] = (
            self.metrics.get("observation_seconds", 0) + time.monotonic() - started
        )
        # Callers pair observations with intent by position. Never let zip/all
        # turn a partial or reordered reply into a smaller design or a receipt.
        if not isinstance(result, list) or len(result) != len(positions):
            raise ValueError("Incomplete build inspection; fresh observation required")
        for position, row in zip(positions, result):
            if (
                not isinstance(row, dict)
                or row.get("position") != position
                or not isinstance(row.get("state"), str)
                or not row["state"]
            ):
                raise ValueError("Invalid build inspection; fresh observation required")
        return result

    def check_storage(self, cells=0):
        console = getattr(self.bridge, "build_console", None)
        world = getattr(getattr(console, "practice", None), "home", None)
        roots = [self.root] + ([world] if world else [])
        used = sum(
            p.stat().st_size for root in roots for p in root.rglob("*") if p.is_file()
        )
        growth = cells * 1024
        free = shutil.disk_usage(self.root).free
        if used + growth > 2 * 1024**3:
            raise ValueError(
                f"Project storage budget exhausted: {used} bytes used plus "
                f"{growth} bytes reserved exceeds {2 * 1024**3}; no automatic pruning"
            )
        if free < 1024**3 + growth:
            raise ValueError(
                f"Filesystem storage reserve exhausted: {free} bytes available; "
                f"{1024**3 + growth} required including growth; no automatic pruning"
            )
        return used

    def prepare(self, cells, *, terrain=False):
        with self.lock:
            if self.state == "running":
                raise ValueError("Stop before replacing a design")
            if not 1 <= len(cells) <= 100000:
                raise ValueError("Design bound exceeded")
            for c in cells:
                validate_cells([{**c, "before": "air"}], self.region)
            if len(
                {tuple(c["position"][k] for k in ("x", "y", "z")) for c in cells}
            ) != len(cells):
                raise ValueError("Duplicate design cells")
            self.check_storage(len(cells))
            wanted = {tuple(c["position"][k] for k in ("x", "y", "z")) for c in cells}
            history = {}
            for (blob,) in self.db.execute(
                "SELECT cells FROM designs ORDER BY revision"
            ):
                for old in json.loads(blob):
                    key = tuple(old["position"][k] for k in ("x", "y", "z"))
                    if key in wanted:
                        history[key] = old
            captured = []
            for offset in range(0, len(cells), 256):
                if terrain and self.cancel.is_set():
                    raise ValueError("Terrain preparation stopped")
                part = cells[offset : offset + 256]
                actual = self.inspect([c["position"] for c in part])
                captured.extend(
                    {**c, "before": a["state"]} for c, a in zip(part, actual)
                )
            cells = captured
            for cell in cells:
                old = history.get(tuple(cell["position"][k] for k in ("x", "y", "z")))
                if old is None and cell["before"] != "air":
                    raise ValueError(
                        "Unrecorded occupied cell requires protection or explicit design review"
                    )
                if old and cell["before"] not in (old["before"], old["after"]):
                    raise ValueError(
                        "Known player change cannot be adopted by a replacement design"
                    )
            projected = {
                tuple(c["position"][k] for k in ("x", "y", "z")): c["after"]
                for c in cells
            }
            solid = {
                "stone",
                "stone_bricks",
                "dirt",
                "grass_block",
                "sand",
                "oak_planks",
                "spruce_planks",
                "oak_log",
                "glass",
                "white_wool",
            }
            for cell in cells:
                if cell["after"].split("[")[0] != "water":
                    continue
                x, y, z = (cell["position"][k] for k in ("x", "y", "z"))
                for position in (
                    (x - 1, y, z),
                    (x + 1, y, z),
                    (x, y, z - 1),
                    (x, y, z + 1),
                    (x, y - 1, z),
                ):
                    neighbour = projected.get(position)
                    if neighbour is None:
                        neighbour = self.inspect(
                            [dict(zip(("x", "y", "z"), position))]
                        )[0]["state"]
                    if neighbour.split("[")[0] not in solid | {"water"}:
                        raise ValueError(
                            "Water requires a fully contained projected basin"
                        )
            # All containment is verified before any fluid is admitted.
            cells.sort(key=lambda c: c["after"].split("[")[0] == "water")
            with self.db:
                revision = self.db.execute(
                    "SELECT COALESCE(MAX(revision),0)+1 FROM designs"
                ).fetchone()[0]
                self.db.execute(
                    "INSERT INTO designs VALUES (?,?)", (revision, json.dumps(cells))
                )
            self.revision = revision
            self.state = "prepared"
        return self.status()

    def summary(self):
        """Small current progress for inference; no geometry decoding."""
        rows = self.db.execute(
            "SELECT status,COUNT(*),SUM(elapsed) FROM units WHERE ABS(revision)=? GROUP BY status",
            (self.revision,),
        ).fetchall()
        return {
            "state": "running" if self.staged_active else self.state,
            "error": self.error,
            "revision": self.revision,
            "units": rows,
            "world_id": self.world_id,
            "region": self.region,
            "automatic_resume": False,
            "undo_skipped": self.undo_skipped,
            "metrics": dict(self.metrics),
        }

    def question_state(self):
        """Explicitly scoped work facts; identifiers are not progress counters."""
        with self.lock:
            state = "running" if self.staged_active else self.state
            progress = self.architecture_progress if self.architecture_active else self.terrain_progress
            if not self.staged_active:
                progress = {}
            totals = dict(self.db.execute("SELECT status,COUNT(*) FROM units GROUP BY status"))
            saved = [row[0] for row in self.db.execute(
                "SELECT s.component FROM architecture_stages s JOIN "
                "(SELECT component,MAX(review) latest FROM architecture_stages GROUP BY component) v "
                "ON s.component=v.component AND s.review=v.latest WHERE s.completed=1 ORDER BY s.component"
            )]
            review = self.architecture_status()
            return {
                "state": state,
                "current_work": {
                    "state": state, "error": self.error,
                    "component": progress.get("component"),
                    "phase": progress.get("phase"),
                    "verified_units_in_current_run": progress.get("verified_units"),
                    "scope": "Current run only. Zero here does not describe older completed work.",
                },
                "receipt_history": {
                    "verified_receipts_across_all_revisions": totals.get("verified", 0),
                    "latest_saved_completed_components": saved,
                    "scope": "Historical receipts include revisions; they are not unique blocks or a current inspection. Current run counters do not reset these records.",
                },
                "review_dependencies": {
                    "reported_dependencies": review.get("dependencies", []) if review else None,
                    "reported_unsupported": review.get("unsupported", []) if review else None,
                    "scope": "Only the saved review. Editing the design requires a new review; future dependencies are unknown.",
                },
            }

    def status(self):
        return self.summary() | {
            "architecture": self.architecture_status(),
            "terrain": self.terrain_status(),
        }

    def _summary_manifest(self, kind, row):
        # Only two latest display summaries are cached. Compare the entire stored
        # body so same-length edits cannot leave stale UI facts. Execution always
        # reads and validates the original manifest independently.
        if not row:
            return None
        cache = getattr(self, "_display_cache", {})
        self._display_cache = cache
        body = row[0]
        previous = cache.get(kind)
        if previous is None or previous[0] != body:
            manifest = json.loads(body)
            if kind == "architecture":
                manifest["components"] = [
                    {k: v for k, v in c.items() if k != "cells"}
                    for c in manifest["components"]
                ]
            else:
                manifest["preview"] = [
                    [
                        x,
                        z,
                        manifest["field"]["height"][z][x],
                        manifest["field"]["water"][z][x],
                    ]
                    for z in range(0, manifest["extent"], 8)
                    for x in range(0, manifest["extent"], 8)
                ]
                manifest.pop("field", None)
                manifest.pop("stages", None)
            cache[kind] = (body, manifest)
        return deepcopy(cache[kind][1])

    def stop(self):
        self.cancel.set()

    def reconcile(self, *, allow_conflicts=False):
        # Only exact before/after states are recoverable; unknown changes never get overwritten.
        for uid, blob in self.db.execute(
            "SELECT id,cells FROM units WHERE status IN ('pending','partial')"
        ).fetchall():
            cells = json.loads(blob)
            actual = self.inspect([c["position"] for c in cells])
            if any(
                a["state"] not in (c["before"], c["after"])
                for a, c in zip(actual, cells)
            ):
                self.db.execute("UPDATE units SET status='conflict' WHERE id=?", (uid,))
            else:
                self.db.execute(
                    "UPDATE units SET status=? WHERE id=?",
                    (
                        "verified"
                        if all(a["state"] == c["after"] for a, c in zip(actual, cells))
                        else "partial",
                        uid,
                    ),
                )
            self.db.commit()
        if (
            not allow_conflicts
            and self.db.execute(
                "SELECT 1 FROM units WHERE status='conflict' LIMIT 1"
            ).fetchone()
        ):
            raise ValueError("Project conflicts require inspection; no overwrite")

    def run(
        self,
        mode="bulk",
        *,
        undo=False,
        undo_unmodified=False,
        fault=None,
        captured=None,
    ):
        if mode not in {"batch", "bulk"}:
            raise ValueError("Unsupported build mode")
        with self.lock:
            if self.state == "running":
                raise ValueError("Project already running")
            if captured is not None and (
                self.cancel.is_set()
                or captured != (self.bridge.session_id, self.bridge.revision)
            ):
                self.state, self.error = "stopped", "Stale project start discarded"
                return self.status()
            if captured is None:
                self.cancel.clear()
            self.state, self.error = "running", None
            self.undo_skipped = []
            self.metrics = {}
            revision = self.revision
        sid, epoch = self.bridge.session_id, self.bridge.revision
        started = time.monotonic()
        try:
            self.reconcile(allow_conflicts=undo and undo_unmodified)
            if undo:
                row = self.db.execute(
                    "SELECT cells FROM designs WHERE revision=?", (revision,)
                ).fetchone()
                if not row:
                    raise ValueError("No prepared design")
                design = json.loads(row[0])
                if any(
                    c[field].split("[")[0] == "water"
                    for c in design
                    for field in ("before", "after")
                ):
                    raise ValueError(
                        "Fluid design undo requires a containment-aware operation"
                    )
                plans = []
                for offset in range(0, len(design), 64):
                    part = design[offset : offset + 64]
                    actual = self.inspect([c["position"] for c in part])
                    cells = []
                    for c, a in zip(part, actual):
                        if undo_unmodified and (
                            a["state"] not in (c["before"], c["after"])
                            or (
                                a["state"] != c["before"]
                                and a["state"].split("[")[0]
                                in {
                                    "chest",
                                    "oak_door",
                                    "white_bed",
                                    "furnace",
                                    "water",
                                }
                            )
                        ):
                            self.undo_skipped.append(c["position"])
                            continue
                        if a["state"] not in (c["before"], c["after"]):
                            raise ValueError("Player change conflicts with undo")
                        if a["state"] != c["before"]:
                            cells.append(
                                {
                                    "position": c["position"],
                                    "before": c["after"],
                                    "after": c["before"],
                                }
                            )
                    if cells:
                        validate_cells(cells, self.region)
                        plans.append(cells)
                skipped = {
                    tuple(p[k] for k in ("x", "y", "z")) for p in self.undo_skipped
                }
                design = [
                    c
                    for c in design
                    if tuple(c["position"][k] for k in ("x", "y", "z")) not in skipped
                ]
            else:
                row = self.db.execute(
                    "SELECT cells FROM designs WHERE revision=?", (revision,)
                ).fetchone()
                if not row:
                    raise ValueError("No prepared design")
                design = json.loads(row[0])
                plans = []
                # Capture baseline once and persist it before any mutation. Reopening never adopts player edits.
                existing = {
                    tuple(c["position"][k] for k in ("x", "y", "z")): c
                    for (blob,) in self.db.execute(
                        "SELECT cells FROM units WHERE revision=?", (revision,)
                    ).fetchall()
                    for c in json.loads(blob)
                }
                staged = {
                    tuple(c["position"][k] for k in ("x", "y", "z"))
                    for (blob,) in self.db.execute(
                        "SELECT cells FROM units WHERE revision=?", (revision,)
                    ).fetchall()
                    for c in json.loads(blob)
                    if c["after"] == "glass"
                }
                water_plans = []
                staging_plans = []
                for offset in range(0, len(design), 64):
                    part = design[offset : offset + 64]
                    actual = self.inspect([c["position"] for c in part])
                    cells = []
                    staging = []
                    water = []
                    for c, a in zip(part, actual):
                        key = tuple(c["position"][k] for k in ("x", "y", "z"))
                        before = existing.get(key, {}).get("before", c["before"])
                        fluid = c["after"].split("[")[0] == "water"
                        if fluid and key in staged and a["state"] == "glass":
                            before = "glass"
                        if a["state"] not in (before, c["after"]):
                            raise ValueError(
                                "Player change conflicts with saved intent"
                            )
                        if a["state"] != c["after"]:
                            if fluid:
                                if before != "glass":
                                    staging.append(
                                        {
                                            "position": c["position"],
                                            "before": before,
                                            "after": "glass",
                                        }
                                    )
                                water.append({**c, "before": "glass"})
                            else:
                                cells.append({**c, "before": before})
                    if cells:
                        plans.append(cells)
                    if staging:
                        staging_plans.append(staging)
                    if water:
                        water_plans.append(water)
                # Journal a solid temporary volume before adding any water. Stopped
                # batches border source water or solids rather than unfilled air.
                plans.extend(staging_plans)
                plans.extend(water_plans)
            for index, cells in enumerate(plans):
                if index % 64 == 0:
                    self.check_storage()
                if (
                    self.cancel.is_set()
                    or sid != self.bridge.session_id
                    or epoch != self.bridge.revision
                ):
                    raise ValueError("Project stopped; explicit continuation required")
                validate_cells(cells, self.region)
                before = time.monotonic()
                uid = self.db.execute(
                    "INSERT INTO units(revision,cells,status,elapsed) VALUES (?,?,?,0)",
                    (-revision if undo else revision, json.dumps(cells), "pending"),
                ).lastrowid
                self.db.commit()
                if fault:
                    fault("intent", uid)
                result = self.bridge.call(
                    "execute",
                    {"action": "build_batch", "cells": cells, "mode": mode},
                    session_id=sid,
                    revision=epoch,
                    timeout_ms=5000,
                )
                if fault:
                    fault("write", uid)
                if result["observed"] != "verified_build_batch":
                    raise ValueError("Unverified build result")
                self.db.execute(
                    "UPDATE units SET status='verified',elapsed=? WHERE id=?",
                    (time.monotonic() - before, uid),
                )
                self.db.commit()
                self.metrics.setdefault(
                    "first_verified_seconds", time.monotonic() - started
                )
                if self.architecture_active:
                    self.architecture_progress.setdefault(
                        "first_verified_seconds",
                        time.monotonic() - self.architecture_began,
                    )
                    self.architecture_progress["verified_units"] += 1
                    self.architecture_progress["written_cells"] += len(cells)
                if self.terrain_active:
                    self.terrain_progress.setdefault(
                        "first_verified_seconds", time.monotonic() - self.terrain_began
                    )
                    self.terrain_progress["verified_units"] = (
                        self.terrain_progress.get("verified_units", 0) + 1
                    )
                    self.terrain_progress["written_cells"] = self.terrain_progress.get(
                        "written_cells", 0
                    ) + len(cells)
                    self.terrain_progress["elapsed_seconds"] = round(
                        time.monotonic() - self.terrain_began, 3
                    )
                if fault:
                    fault("receipt", uid)
            for offset in range(0, len(design), 256):
                if self.cancel.is_set():
                    raise ValueError("Stopped during final verification")
                part = design[offset : offset + 256]
                actual = self.inspect([c["position"] for c in part])
                if any(
                    a["state"] != c["before" if undo else "after"]
                    for c, a in zip(part, actual)
                ):
                    raise ValueError("Final world differs from approved design")
            if self.cancel.is_set() or (sid, epoch) != (
                self.bridge.session_id,
                self.bridge.revision,
            ):
                raise ValueError("Stopped before verification could commit")
            if not undo:
                self.db.execute(
                    "UPDATE units SET status='superseded' WHERE revision=? AND status='partial'",
                    (revision,),
                )
                self.db.commit()
            self.state = (
                ("partially_undone" if self.undo_skipped else "undone")
                if undo
                else "complete"
            )
        except Exception as exc:
            # Keep committed write-ahead intent, but discard failed/uncommitted
            # receipts before another operation can accidentally commit them.
            self.db.rollback()
            self.state, self.error = (
                "stopped" if self.cancel.is_set() else "needs_review",
                str(exc),
            )
        finally:
            self.elapsed = time.monotonic() - started
            self.metrics["total_seconds"] = self.elapsed
        return self.status()

    def terrain_manifest(self):
        row = self.db.execute(
            "SELECT body FROM terrain_manifests ORDER BY revision DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    def terrain_status(self):
        manifest = self._summary_manifest(
            "terrain",
            self.db.execute(
                "SELECT body FROM terrain_manifests ORDER BY revision DESC LIMIT 1"
            ).fetchone(),
        )
        if not manifest:
            return None
        return {
            k: manifest[k]
            for k in (
                "design_revision",
                "extent",
                "origin",
                "buffer",
                "digest",
                "cells",
                "stages_count",
                "max_seconds",
                "max_cells",
                "reservations",
            )
        } | {
            "progress": {**self.terrain_progress,
                "verified_stages": self.db.execute(
                    "SELECT COUNT(*) FROM terrain_stages WHERE manifest=? AND ordinal>=0 AND completed=1",
                    (manifest["design_revision"],),
                ).fetchone()[0],
                "phase": self.terrain_progress.get("phase", "Saved checkpoint; inspect before continuing"),
            },
            "peaks": manifest["peaks"],
            "preview": manifest["preview"],
            "state": "running" if self.terrain_active else self.state,
            "review": "Earth and containment first, then water. A one-block perimeter rim contains water inside the reviewed extent. Structure footprints are reserved; buildings are not generated.",
        }

    def review_terrain(self, design):
        from smb3_agent.minecraft_terrain import (
            compile_terrain,
            tile_cells,
            TILE,
            digest,
            MAX_CELLS,
            foliage_cleanup,
        )

        if self.state == "running" or self.staged_active:
            raise ValueError("Stop before reviewing terrain")
        old = self.terrain_manifest()
        origin = (
            old["origin"]
            if old
            else [
                ((self.region["bounds"]["max"]["x"] + 64) // 64) * 64,
                self.region["bounds"]["min"]["z"],
            ]
        )
        if old and old["extent"] != design["extent"]:
            raise ValueError("Terrain extent cannot change inside an existing project")
        if old and (old.get("tile_size", 32) != TILE or old.get("version") != 2):
            raise ValueError(
                "Earlier experimental terrain staging needs a fresh project"
            )
        if old and old["design_revision"] == design["revision"]:
            if old["source_digest"] != digest(design["requirements"]):
                raise ValueError(
                    "Saved terrain requirements changed without a new revision"
                )
            # Re-review cannot overwrite bindings or remove pending cleanup from
            # an already reviewed revision, even after a compiler update.
            return self.terrain_status()
        manifest = compile_terrain(design, origin)
        owned = self.architecture_ownership(require_complete=True)
        if owned and old:
            columns = {
                (p[0] - old["origin"][0], p[2] - old["origin"][1]) for p in owned
            }
            for x, z in columns:
                if any(
                    old["field"][key][z][x] != manifest["field"][key][z][x]
                    for key in ("height", "water")
                ):
                    # Path resurfacing is filtered at every architecture-owned
                    # coordinate during execution; foundations/water cannot move.
                    raise ValueError(
                        "Terrain revision changes a retained architecture foundation or approach; revise the dependency before building"
                    )
            manifest["preserved_architecture_cells"] = len(owned)
        palette = self.bridge.call("build_palette")
        specs = []
        total = 0
        for phase in (
            "earth",
            "leaves1",
            "leaves2",
            "leaves3",
            "leaves4",
            "leaves5",
            "leaves6",
            "water",
        ):
            for z in range(0, manifest["extent"], TILE):
                for x in range(0, manifest["extent"], TILE):
                    cells = tile_cells(
                        manifest,
                        x,
                        z,
                        palette,
                        fluid=phase == "water",
                        leaves=int(phase[-1]) if phase.startswith("leaves") else 0,
                    )
                    if len(cells) > 100000:
                        raise ValueError(
                            "Terrain stage exceeds 100,000 cells; revise its height/extent"
                        )
                    if not cells:
                        continue
                    total += len(cells)
                    specs.append(
                        {
                            "phase": phase,
                            "x": x,
                            "z": z,
                            "cells": len(cells),
                            "digest": digest(cells),
                        }
                    )
        if total > MAX_CELLS:
            raise ValueError(
                "Terrain exceeds two-million-cell operation budget; revise before starting"
            )
        manifest.update(
            stages=specs, cells=total, stages_count=len(specs), palette=palette
        )
        manifest["foliage_cleanup"] = (
            foliage_cleanup(old, manifest, palette) if old else []
        )

        manifest["digest"] = digest(
            {k: v for k, v in manifest.items() if k != "digest"}
        )
        # Review creates a durable manifest, but does not change region or write authority.
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO terrain_manifests VALUES (?,?)",
                (design["revision"], json.dumps(manifest)),
            )
            self.db.commit()
        if old:
            changed = {
                (s["x"], s["z"])
                for s in specs
                if s["phase"] == "earth"
                and not any(
                    p["phase"] == "earth"
                    and p["x"] == s["x"]
                    and p["z"] == s["z"]
                    and p["digest"] == s["digest"]
                    for p in old["stages"]
                )
            }
            for i, spec in enumerate(specs):
                if (spec["x"], spec["z"]) in changed or (
                    spec["phase"].startswith("leaves")
                    and any(
                        origin[0] + spec["x"]
                        <= c["position"]["x"]
                        < origin[0] + spec["x"] + TILE
                        and origin[1] + spec["z"]
                        <= c["position"]["z"]
                        < origin[1] + spec["z"] + TILE
                        for c in manifest["foliage_cleanup"]
                    )
                ):
                    continue
                previous = next(
                    (
                        j
                        for j, p in enumerate(old["stages"])
                        if p["digest"] == spec["digest"]
                        and p["phase"] == spec["phase"]
                        and p["x"] == spec["x"]
                        and p["z"] == spec["z"]
                    ),
                    None,
                )
                if previous is not None:
                    row = self.db.execute(
                        "SELECT design_revision,completed FROM terrain_stages WHERE manifest=? AND ordinal=?",
                        (old["design_revision"], previous),
                    ).fetchone()
                    if row and row[1]:
                        self.db.execute(
                            "INSERT OR IGNORE INTO terrain_stages VALUES (?,?,?,?,1)",
                            (design["revision"], i, spec["digest"], row[0]),
                        )
            self.db.commit()
        self.terrain_progress = {
            "phase": "reviewed",
            "verified_stages": 0,
            "total_stages": len(specs),
        }
        self.state, self.error = "prepared", None
        return self.terrain_status()

    def run_terrain(self, design_revision, *, captured):
        from smb3_agent.minecraft_terrain import tile_cells, TILE, digest

        started = time.monotonic()
        self.terrain_began = started
        manifest = self.terrain_manifest()
        if not manifest or manifest["design_revision"] != design_revision:
            self.terrain_active = False
            raise ValueError("Review the current design terrain before starting")
        self.terrain_active = True
        self.terrain_progress = {
            "phase": "starting",
            "verified_stages": 0,
            "total_stages": len(manifest["stages"]),
            "cells": 0,
        }
        try:
            if manifest.get("digest") != digest(
                {k: v for k, v in manifest.items() if k != "digest"}
            ):
                raise ValueError(
                    "Saved terrain manifest changed; review a new design revision"
                )
            if (
                captured != (self.bridge.session_id, self.bridge.revision)
                or self.cancel.is_set()
            ):
                raise ValueError("Stale terrain start")
            console = getattr(self.bridge, "build_console", None)
            if console is None:
                raise ValueError("Terrain requires an enabled Creative console")
            self.bridge.call(
                "select_build_region",
                {"region": manifest["region"]},
                session_id=captured[0],
                revision=captured[1],
            )
            console.region = self.region = manifest["region"]
            # All mutations still use existing designs/units. Stage rows only bind a
            # deterministic terrain portion to its existing transaction revision.
            prior_rows = self.db.execute(
                "SELECT revision,body FROM terrain_manifests WHERE revision<? ORDER BY revision DESC LIMIT 1",
                (design_revision,),
            ).fetchone()
            previous = json.loads(prior_rows[1]) if prior_rows else None

            def check():
                if self.cancel.is_set() or captured != (
                    self.bridge.session_id,
                    self.bridge.revision,
                ):
                    raise ValueError("Terrain stopped; explicit continuation required")
                if time.monotonic() - started > manifest["max_seconds"]:
                    raise ValueError("Terrain operation time budget exhausted")

            def focus(x, z):
                check()
                self.bridge.call(
                    "execute",
                    {
                        "action": "build_focus",
                        "position": {
                            "x": manifest["origin"][0] + x + TILE // 2,
                            "y": self.region["bounds"]["max"]["y"] + 8,
                            "z": manifest["origin"][1] + z + TILE // 2,
                        },
                    },
                    session_id=captured[0],
                    revision=captured[1],
                    timeout_ms=10000,
                )
                check()

            architecture_owned = self.architecture_ownership(require_complete=True)

            def transact(cells, ordinal, key):
                cells = [
                    c
                    for c in cells
                    if tuple(c["position"][k] for k in ("x", "y", "z"))
                    not in architecture_owned
                ]
                if not cells:
                    return
                row = self.db.execute(
                    "SELECT digest,design_revision,completed FROM terrain_stages WHERE manifest=? AND ordinal=?",
                    (design_revision, ordinal),
                ).fetchone()
                if row:
                    if row[2]:
                        return
                    if row[0] != key:
                        raise ValueError("Prepared terrain stage differs from manifest")
                    self.revision = row[1]
                else:
                    self.state = "preparing"
                    preparation_started = time.monotonic()
                    self.prepare(cells, terrain=True)
                    self.terrain_progress["preparation_seconds"] = round(
                        self.terrain_progress.get("preparation_seconds", 0)
                        + time.monotonic()
                        - preparation_started,
                        3,
                    )
                    self.db.execute(
                        "INSERT INTO terrain_stages VALUES (?,?,?,?,0)",
                        (design_revision, ordinal, key, self.revision),
                    )
                    self.db.commit()
                self.state = "prepared"
                outcome = self.run(captured=captured)
                if self.state != "complete":
                    raise ValueError(outcome["error"] or "Terrain stage incomplete")
                self.db.execute(
                    "UPDATE terrain_stages SET completed=1 WHERE manifest=? AND ordinal=?",
                    (design_revision, ordinal),
                )
                self.db.commit()
                self.terrain_progress.setdefault(
                    "first_verified_seconds", time.monotonic() - started
                )
                self.terrain_progress["cells"] += len(cells)

            # Remove affected native canopies before changing their supporting logs.
            cleanup = manifest.get("foliage_cleanup", [])
            for offset in range(0, len(cleanup), 64):
                part = cleanup[offset : offset + 64]
                # A connected canopy is small; focus its first cell before exact CAS.
                point = part[0]["position"]
                tx = max(
                    0,
                    min(
                        manifest["extent"] - TILE,
                        ((point["x"] - manifest["origin"][0]) // TILE) * TILE,
                    ),
                )
                tz = max(
                    0,
                    min(
                        manifest["extent"] - TILE,
                        ((point["z"] - manifest["origin"][1]) // TILE) * TILE,
                    ),
                )
                focus(tx, tz)
                transact(part, -10000 - offset, digest(part))
            # A revised wet landscape is sealed before any cuts. Sealing itself is
            # journaled, resumable and conditionally checked against the old water.
            if previous:
                for i, spec in enumerate(previous["stages"]):
                    if spec["phase"] != "water" or any(
                        s["phase"] == "earth"
                        and s["x"] == spec["x"]
                        and s["z"] == spec["z"]
                        and self.db.execute(
                            "SELECT completed FROM terrain_stages WHERE manifest=? AND ordinal=?",
                            (design_revision, j),
                        ).fetchone()
                        == (1,)
                        for j, s in enumerate(manifest["stages"])
                    ):
                        continue
                    old_stage = self.db.execute(
                        "SELECT design_revision FROM terrain_stages WHERE manifest=? AND ordinal=?",
                        (previous["design_revision"], i),
                    ).fetchone()
                    if not old_stage:
                        continue
                    cells = tile_cells(
                        previous, spec["x"], spec["z"], manifest["palette"], fluid=True
                    )
                    for c in cells:
                        c["after"] = manifest["palette"]["glass"]
                    self.terrain_progress["phase"] = "sealing previous water"
                    focus(spec["x"], spec["z"])
                    transact(cells, -i - 1, digest(cells))
            for ordinal, spec in enumerate(manifest["stages"]):
                check()
                self.terrain_progress.update(
                    phase=spec["phase"],
                    stage=ordinal + 1,
                    elapsed_seconds=round(time.monotonic() - started, 3),
                )
                completed = self.db.execute(
                    "SELECT completed FROM terrain_stages WHERE manifest=? AND ordinal=?",
                    (design_revision, ordinal),
                ).fetchone()
                if completed == (1,):
                    self.terrain_progress["verified_stages"] = ordinal + 1
                    continue
                focus(spec["x"], spec["z"])
                cells = tile_cells(
                    manifest,
                    spec["x"],
                    spec["z"],
                    manifest["palette"],
                    fluid=spec["phase"] == "water",
                    leaves=int(spec["phase"][-1])
                    if spec["phase"].startswith("leaves")
                    else 0,
                )
                if previous and spec["phase"] == "earth":
                    old = tile_cells(
                        previous, spec["x"], spec["z"], manifest["palette"]
                    )
                    keys = {
                        tuple(c["position"][k] for k in ("x", "y", "z")) for c in cells
                    }
                    cells += [
                        {"position": c["position"], "after": "air"}
                        for c in old
                        if tuple(c["position"][k] for k in ("x", "y", "z")) not in keys
                    ]
                transact(cells, ordinal, digest(cells))
                self.terrain_progress["verified_stages"] = ordinal + 1
            # Inspect final composed state, including stages retained from earlier revisions.
            for spec in manifest["stages"]:
                if spec["phase"] != "earth":
                    continue
                focus(spec["x"], spec["z"])
                solid = tile_cells(manifest, spec["x"], spec["z"], manifest["palette"])
                fluid = tile_cells(
                    manifest, spec["x"], spec["z"], manifest["palette"], fluid=True
                )
                foliage = [
                    c
                    for distance in range(1, 7)
                    for c in tile_cells(
                        manifest,
                        spec["x"],
                        spec["z"],
                        manifest["palette"],
                        leaves=distance,
                    )
                ]
                final = {
                    tuple(c["position"][k] for k in ("x", "y", "z")): c
                    for c in solid + foliage + fluid
                }
                cells = [
                    c
                    for c in final.values()
                    if tuple(c["position"][k] for k in ("x", "y", "z"))
                    not in architecture_owned
                ]
                for offset in range(0, len(cells), 256):
                    check()
                    part = cells[offset : offset + 256]
                    actual = self.inspect([c["position"] for c in part])
                    if any(c["after"] != a["state"] for c, a in zip(part, actual)):
                        raise ValueError(
                            "Terrain final survey found a conflict; existing changes preserved"
                        )
            check()
            self.state, self.error = "complete", None
        except Exception as exc:
            self.state = "stopped" if self.cancel.is_set() else "needs_review"
            self.error = str(exc)
        finally:
            self.terrain_progress["elapsed_seconds"] = round(
                time.monotonic() - started, 3
            )
            try:
                self.terrain_progress["storage_bytes"] = self.check_storage()
            except (OSError, ValueError) as exc:
                self.state, self.error = "needs_review", str(exc)
            finally:
                self.terrain_active = False
        return self.status()

    @property
    def staged_active(self):
        return self.terrain_active or self.architecture_active

    def architecture_ownership(self, *, require_complete=False):
        """Latest desired cells, indexed from the existing transaction journal."""
        owned = {}
        rows = self.db.execute(
            "SELECT s.component,s.design_revision,s.completed,s.review FROM architecture_stages s JOIN (SELECT component,MAX(review) AS latest FROM architecture_stages GROUP BY component) last ON last.component=s.component AND last.latest=s.review"
        ).fetchall()
        for name, revision, complete, review in rows:
            if require_complete and not complete:
                raise ValueError(
                    "Complete or resolve partial architecture before terrain changes"
                )
            body = json.loads(
                self.db.execute(
                    "SELECT body FROM architecture_reviews WHERE id=?", (review,)
                ).fetchone()[0]
            )
            component = next(c for c in body["components"] if c["name"] == name)
            if component.get("retired"):
                continue
            for cell in json.loads(
                self.db.execute(
                    "SELECT cells FROM designs WHERE revision=?", (revision,)
                ).fetchone()[0]
            ):
                owned[tuple(cell["position"][k] for k in ("x", "y", "z"))] = cell[
                    "after"
                ]
        return owned

    def architecture_manifest(self):
        row = self.db.execute(
            "SELECT id,body FROM architecture_reviews ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return (row[0], json.loads(row[1])) if row else (0, None)

    def architecture_status(self):
        row = self.db.execute(
            "SELECT id,body FROM architecture_reviews ORDER BY id DESC LIMIT 1"
        ).fetchone()
        review = row[0] if row else 0
        manifest = self._summary_manifest("architecture", (row[1],) if row else None)
        if manifest is None:
            return None
        return {
            "review": review,
            **{k: v for k, v in manifest.items() if k != "components"},
            "components": [
                {k: v for k, v in c.items() if k != "cells"}
                for c in manifest["components"]
            ],
            "progress": dict(self.architecture_progress),
            "completed": [
                r[0]
                for r in self.db.execute(
                    "SELECT component FROM architecture_stages WHERE review=? AND completed=1",
                    (review,),
                )
            ],
        }

    def review_architecture(self, design, *, selected=None, material=None):
        from smb3_agent.minecraft_architecture import compile_architecture
        from smb3_agent.minecraft_terrain import digest

        if self.state == "running" or self.staged_active:
            raise ValueError("Stop before reviewing architecture")
        terrain = self.terrain_manifest()
        if terrain is None:
            raise ValueError("Review and complete terrain before architecture")
        complete = self.db.execute(
            "SELECT COUNT(*) FROM terrain_stages WHERE manifest=? AND ordinal>=0 AND completed=1",
            (terrain["design_revision"],),
        ).fetchone()[0]
        if complete != len(terrain["stages"]):
            raise ValueError("Complete the reviewed terrain before architecture")
        retained = {}
        for (body,) in self.db.execute(
            "SELECT body FROM architecture_reviews ORDER BY id"
        ):
            for component in json.loads(body)["components"]:
                binding = self.db.execute(
                    "SELECT 1 FROM architecture_stages WHERE component=? AND digest=? AND completed=1",
                    (component["name"], component["digest"]),
                ).fetchone()
                if binding:
                    retained[component["name"]] = component
        manifest = compile_architecture(
            design,
            terrain,
            self.bridge.call("build_palette"),
            selected=selected,
            material=material,
            existing=retained,
        )
        # Migrate a former aggregate annotation only through an explicitly
        # reviewed cleanup stage, using its original captured baseline.
        groups = {
            c["source_component"]
            for c in manifest["components"]
            if c.get("source_component")
        }
        for group in groups:
            row = self.db.execute(
                "SELECT design_revision,review FROM architecture_stages WHERE component=? ORDER BY review LIMIT 1",
                (group,),
            ).fetchone()
            if not row:
                continue
            baseline = json.loads(
                self.db.execute(
                    "SELECT cells FROM designs WHERE revision=?", (row[0],)
                ).fetchone()[0]
            )
            previous_body = json.loads(
                self.db.execute(
                    "SELECT body FROM architecture_reviews WHERE id=?", (row[1],)
                ).fetchone()[0]
            )
            original = next(
                c for c in previous_body["components"] if c["name"] == group
            )
            cleanup = [
                {"position": c["position"], "after": c["before"]} for c in baseline
            ]
            manifest["components"].append(
                {
                    **original,
                    "retired": True,
                    "rooms": [],
                    "objects": [],
                    "walks": [],
                    "cells": cleanup,
                    "digest": digest(cleanup),
                }
            )
        manifest["cells"] = sum(len(c["cells"]) for c in manifest["components"])
        self.check_storage(manifest["cells"])
        previous_id, previous = self.architecture_manifest()
        if previous and previous["digest"] == manifest["digest"]:
            return self.architecture_status()
        # Bindings are an ownership index, not another mutation journal. A
        # selected review may not overwrite cells belonging to a different place.
        selected_names = {c["name"] for c in manifest["components"]}
        other_owned = {}
        for other, rev in self.db.execute(
            "SELECT component,MAX(review) FROM architecture_stages GROUP BY component"
        ):
            if other in selected_names:
                continue
            row = self.db.execute(
                "SELECT d.cells FROM architecture_stages s JOIN designs d ON d.revision=s.design_revision WHERE s.component=? AND s.review=?",
                (other, rev),
            ).fetchone()
            if row:
                for cell in json.loads(row[0]):
                    if cell["after"] != "air":
                        other_owned[
                            tuple(cell["position"][k] for k in ("x", "y", "z"))
                        ] = other
        for component in manifest["components"]:
            conflicts = {
                other_owned[tuple(c["position"][k] for k in ("x", "y", "z"))]
                for c in component["cells"]
                if tuple(c["position"][k] for k in ("x", "y", "z")) in other_owned
            }
            manifest["dependencies"].extend(
                f"{component['name']}: conflicts with retained architecture {other}"
                for other in sorted(conflicts)
            )
        # Only the selected components are revised. Other bindings stay unchanged.
        # Removed cells restore their prior baseline through the same journal;
        # interactive removal is still refused by validate_cells.
        for component in manifest["components"]:
            row = self.db.execute(
                "SELECT s.design_revision FROM architecture_stages s WHERE component=? ORDER BY review DESC LIMIT 1",
                (component["name"],),
            ).fetchone()
            if row:
                old = json.loads(
                    self.db.execute(
                        "SELECT cells FROM designs WHERE revision=?", row
                    ).fetchone()[0]
                )
                keys = {
                    tuple(c["position"][k] for k in ("x", "y", "z"))
                    for c in component["cells"]
                }
                # Each coordinate keeps the first captured baseline, including
                # cells first acquired by later expansions. A second revision's
                # before-state may itself be architecture, not original ground.
                baseline = {}
                for (body,) in self.db.execute(
                    "SELECT d.cells FROM architecture_stages s JOIN designs d ON d.revision=s.design_revision WHERE s.component=? ORDER BY s.review",
                    (component["name"],),
                ):
                    for cell in json.loads(body):
                        key = tuple(cell["position"][k] for k in ("x", "y", "z"))
                        baseline.setdefault(key, cell["before"])
                component["cells"] += [
                    {
                        "position": c["position"],
                        "after": baseline[
                            tuple(c["position"][k] for k in ("x", "y", "z"))
                        ],
                    }
                    for c in old
                    if tuple(c["position"][k] for k in ("x", "y", "z")) not in keys
                ]
                component["digest"] = digest(component["cells"])
        manifest["cells"] = sum(len(c["cells"]) for c in manifest["components"])
        manifest["digest"] = digest(
            {k: v for k, v in manifest.items() if k != "digest"}
        )
        if previous and previous["digest"] == manifest["digest"]:
            return self.architecture_status()
        with self.lock:
            self.db.execute(
                "INSERT INTO architecture_reviews(body) VALUES (?)",
                (json.dumps(manifest),),
            )
            self.db.commit()
        self.state, self.error = "prepared", None
        self.architecture_progress = {"phase": "reviewed"}
        return self.architecture_status()

    def run_architecture(self, review, *, captured):
        from smb3_agent.minecraft_terrain import digest

        started = time.monotonic()
        current_id, manifest = self.architecture_manifest()
        self.architecture_active = True
        self.architecture_began = started
        self.architecture_progress = {
            "phase": "starting",
            "verified_units": 0,
            "written_cells": 0,
        }
        try:
            if not manifest or review != current_id:
                raise ValueError("Review the latest architecture before starting")
            if manifest["digest"] != digest(
                {k: v for k, v in manifest.items() if k != "digest"}
            ):
                raise ValueError("Architecture manifest integrity changed")
            terrain = self.terrain_manifest()
            if not terrain or manifest["terrain_digest"] != terrain["digest"]:
                raise ValueError(
                    "Terrain changed; review architecture dependencies again"
                )
            if manifest["dependencies"] or manifest["unsupported"]:
                raise ValueError(
                    "Resolve architecture dependencies and unsupported inventory before building"
                )

            def check():
                if self.cancel.is_set() or captured != (
                    self.bridge.session_id,
                    self.bridge.revision,
                ):
                    raise ValueError(
                        "Architecture stopped; explicit continuation required"
                    )
                if time.monotonic() - started > manifest["max_seconds"]:
                    raise ValueError("Architecture operation time budget exhausted")

            check()
            console = getattr(self.bridge, "build_console", None)
            if console is None:
                raise ValueError("Architecture requires an enabled Creative console")
            self.bridge.call(
                "select_build_region",
                {"region": manifest["region"]},
                session_id=captured[0],
                revision=captured[1],
            )
            console.region = self.region = manifest["region"]
            for component in manifest["components"]:
                check()
                x, z, w, d, _, _ = component["box"]
                self.bridge.call(
                    "execute",
                    {
                        "action": "build_focus",
                        "position": {
                            "x": terrain["origin"][0] + x + w // 2,
                            "y": self.region["bounds"]["max"]["y"] + 8,
                            "z": terrain["origin"][1] + z + d // 2,
                        },
                    },
                    session_id=captured[0],
                    revision=captured[1],
                    timeout_ms=10000,
                )
                self.architecture_progress.update(
                    phase="preparing", component=component["name"]
                )
                row = self.db.execute(
                    "SELECT digest,design_revision,completed FROM architecture_stages WHERE review=? AND component=?",
                    (review, component["name"]),
                ).fetchone()
                if row:
                    if row[0] != component["digest"]:
                        raise ValueError(
                            "Architecture binding differs from reviewed cells"
                        )
                    self.revision = row[1]
                else:
                    before = time.monotonic()
                    self.prepare(component["cells"], terrain=True)
                    self.architecture_progress["preparation_seconds"] = (
                        time.monotonic() - before
                    )
                    check()
                    self.db.execute(
                        "INSERT INTO architecture_stages VALUES (?,?,?,?,0)",
                        (review, component["name"], component["digest"], self.revision),
                    )
                    self.db.commit()
                if not row or not row[2]:
                    self.state = "prepared"
                    outcome = self.run(captured=captured)
                    if self.state != "complete":
                        raise ValueError(
                            outcome["error"] or "Architecture stage incomplete"
                        )
                    self.db.execute(
                        "UPDATE architecture_stages SET completed=1 WHERE review=? AND component=?",
                        (review, component["name"]),
                    )
                    self.db.commit()
                # Reopening inspects saved intent; it never adopts changed blocks.
                for offset in range(0, len(component["cells"]), 256):
                    check()
                    cells = component["cells"][offset : offset + 256]
                    actual = self.inspect([c["position"] for c in cells])
                    if any(c["after"] != a["state"] for c, a in zip(cells, actual)):
                        raise ValueError(
                            "Architecture survey found a player or physics change"
                        )
            self.state, self.error = "complete", None
            self.architecture_progress["phase"] = "complete"
        except Exception as exc:
            self.state = "stopped" if self.cancel.is_set() else "needs_review"
            self.error = str(exc)
        finally:
            self.architecture_progress["elapsed_seconds"] = round(
                time.monotonic() - started, 3
            )
            try:
                self.architecture_progress["storage_bytes"] = self.check_storage()
            except (OSError, ValueError) as exc:
                self.state, self.error = "needs_review", str(exc)
            self.architecture_active = False
        return self.status()

    def close(self):
        self.stop()
        if self.state == "running" or self.staged_active:
            raise ValueError("Stop and join project work before closing storage")
        self.db.close()
