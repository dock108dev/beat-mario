"""Versioned world briefs in the construction project's existing database.

Designs describe intent, never execution authority. Terrain and architecture
require separate reviews through the existing region transaction boundary.
"""

from copy import deepcopy
import base64
import hashlib
import json
import math
import re
from io import BytesIO
from PIL import Image

from smb3_agent.inference_contract import validate_object
from smb3_agent.minecraft_planning import schema

KINDS = [
    "terrain",
    "water",
    "grove",
    "cave",
    "building",
    "tower",
    "bridge",
    "dock",
    "wreck",
    "path",
    "decoration",
    "pavilion",
    "platform",
]
PALETTES = {
    "warm": ["oak_planks", "white_wool", "stone"],
    "coastal": ["oak_planks", "glass", "white_wool"],
    "natural": ["spruce_planks", "stone", "glass"],
    "industrial": ["stone_bricks", "glass", "spruce_planks"],
}


def string(n):
    return {"type": "string", "maxLength": n}


COMPONENT = schema(
    {
        "name": string(48),
        "kind": {"type": "string", "enum": KINDS},
        "size": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "integer", "minimum": 1, "maximum": 256},
        },
        "zone": {
            "type": "string",
            "enum": ["north", "south", "east", "west", "center"],
        },
        "level": {"type": "string", "enum": ["shore", "raised", "ridge"]},
        "turn": {"type": "integer", "minimum": 0, "maximum": 3},
        "link": string(48),
        "detail": string(80),
    }
)
DELTA = schema(
    {
        "title": string(60),
        "extent": {"type": "integer", "enum": [192, 256]},
        "palette": {"type": "string", "enum": list(PALETTES)},
        "reply": string(240),
        "remove": string(48),
        "components": {
            "type": "array",
            "minItems": 0,
            "maxItems": 3,
            "items": COMPONENT,
        },
    }
)


def requested_extent(text):
    match = re.search(r"\b(192|256)\s*(?:by|x|×)\s*\1\b", text, re.I)
    return int(match[1]) if match else None


def preview_problem(component):
    """Sample-site geometry eligibility; live admission still belongs to chat/build."""
    if not component or component["kind"] not in {"platform", "pavilion"}:
        return (
            "Only a small platform or open pavilion can be built here; "
            "other components are planning previews"
        )
    _, _, width, depth, _, height = component["box"]
    if not 3 <= width <= 12 or not 3 <= depth <= 12 or not 3 <= height <= 8:
        return (
            "The bounded preview supports 3–12 block footprints "
            "and 3–8 block heights"
        )
    return None


class WorldDesign:
    def __init__(self, project):
        self.project = project
        with project.lock:
            project.db.executescript("""
                CREATE TABLE IF NOT EXISTS world_designs
                  (revision INTEGER PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS design_references
                  (id TEXT PRIMARY KEY, name TEXT, caption TEXT, mime TEXT, image BLOB);
                CREATE TABLE IF NOT EXISTS design_bindings
                  (revision INTEGER, component TEXT, build_revision INTEGER);
            """)
            project.db.commit()

    def current(self):
        row = self.project.db.execute(
            "SELECT body FROM world_designs ORDER BY revision DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    def references(self):
        return [
            dict(zip(("id", "name", "caption", "mime"), row))
            for row in self.project.db.execute(
                "SELECT id,name,caption,mime FROM design_references ORDER BY rowid"
            )
        ]

    def snapshot(self):
        with self.project.lock:
            current = self.current()
            return {
                "current": current,
                "preview_components": (
                    [c["name"] for c in current["components"] if preview_problem(c) is None]
                    if current else []
                ),
                "references": self.references(),
                "versions": [
                    r[0]
                    for r in self.project.db.execute(
                        "SELECT revision FROM world_designs ORDER BY revision DESC"
                    )
                ],
                "bound": [
                    dict(zip(("revision", "component", "build_revision"), r))
                    for r in self.project.db.execute(
                        "SELECT * FROM design_bindings ORDER BY rowid DESC LIMIT 1"
                    )
                ],
            }

    def add_reference(self, name, caption, encoded):
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 120
            or not isinstance(caption, str)
            or not 1 <= len(caption) <= 500
        ):
            raise ValueError(
                "Give the image a short name and a description of how to use it."
            )
        if len(encoded) > 5_333_336:
            raise ValueError("Reference exceeds 4 MB")
        try:
            image = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ValueError("Invalid reference image") from exc
        mime = (
            "image/png"
            if image.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/jpeg"
            if image.startswith(b"\xff\xd8")
            else None
        )
        if not mime or not 1 <= len(image) <= 4_000_000:
            raise ValueError("Select a PNG or JPEG no larger than 4 MB")
        try:
            with Image.open(BytesIO(image)) as decoded:
                if (
                    decoded.format not in {"PNG", "JPEG"}
                    or decoded.width * decoded.height > 16_000_000
                ):
                    raise ValueError("Reference dimensions exceed the preview limit")
                decoded.verify()
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError("Reference image cannot be decoded safely") from exc
        key = hashlib.sha256(image).hexdigest()
        with self.project.lock:
            if len(self.references()) >= 6:
                raise ValueError("At most six references per project")
            if self.project.db.execute(
                "SELECT 1 FROM design_references WHERE id=?", (key,)
            ).fetchone():
                raise ValueError("That image is already selected")
            self.project.check_storage()
            self.project.db.execute(
                "INSERT INTO design_references VALUES (?,?,?,?,?)",
                (key, name, caption, mime, image),
            )
            self.project.db.commit()
        return key

    def reference(self, key):
        with self.project.lock:
            row = self.project.db.execute(
                "SELECT mime,image FROM design_references WHERE id=?", (key,)
            ).fetchone()
            if not row:
                raise ValueError("Reference not found")
            return row

    def begin_requirements(self, parsed, expected):
        from smb3_agent.minecraft_requirements import MAX_CALLS, MAX_SECONDS

        with self.project.lock:
            old = self.current()
            if (old["revision"] if old else 0) != expected:
                raise ValueError("Design changed before requirements could be saved")
            if len(parsed["requirements"]) > 40:
                raise ValueError(
                    "At most 40 named components; no inventory was dropped"
                )
            value = (
                deepcopy(old)
                if old
                else {
                    "components": [],
                    "brief": parsed["source"]["text"],
                    "protected_buffer": 32,
                    "estimated_volume": 0,
                    "estimate_note": "Bounding volume, not a block count or time promise.",
                    "uncertainty": "Unspecified placement is an interpretation. Image analysis unavailable.",
                    "references": self.references(),
                    "sources": [],
                }
            )
            value.update(
                revision=expected + 1,
                title=parsed["title"],
                extent=parsed["extent"],
                palette=parsed["palette"],
                requirements=parsed["requirements"],
                request=parsed["source"]["text"],
                changed=parsed["changed"],
                previous_components=deepcopy(value["components"]),
                planning={
                    "state": "pending",
                    "issues": parsed["issues"],
                    "calls": 0,
                    "seconds": 0,
                    "max_calls": MAX_CALLS,
                    "max_seconds": MAX_SECONDS,
                    "repairs": [],
                },
            )
            value.setdefault("sources", []).append(parsed["source"])
            self._save_version(value)
            return value

    def _save_version(self, value):
        if value["revision"] > 400:
            raise ValueError("Design version budget exhausted; no history deleted")
        self.project.check_storage()
        self.project.db.execute(
            "INSERT INTO world_designs VALUES (?,?)",
            (value["revision"], json.dumps(value)),
        )
        self.project.db.commit()

    def planning_progress(self, calls, seconds, *, state=None, repair=None):
        from smb3_agent.minecraft_requirements import checklist

        with self.project.lock:
            value = self.current()
            if not value or "planning" not in value:
                return
            value["planning"].update(calls=calls, seconds=round(seconds, 3))
            if repair:
                value["planning"]["repairs"].append(repair)
            rows = checklist(value)
            value["checklist"] = rows
            if state:
                value["planning"]["state"] = state
            elif not value["planning"]["issues"] and all(
                row["status"] == "matched" for row in rows
            ):
                value["planning"]["state"] = "ready"
            else:
                value["planning"]["state"] = "pending"
            self.project.db.execute(
                "UPDATE world_designs SET body=? WHERE revision=?",
                (json.dumps(value), value["revision"]),
            )
            self.project.db.commit()

    def apply(self, delta, brief, expected):
        validate_object(delta, DELTA)
        with self.project.lock:
            old = self.current()
            revision = old["revision"] if old else 0
            if revision != expected:
                raise ValueError(
                    "Design changed; review the current version before editing"
                )
            if revision >= 400:
                raise ValueError(
                    "Design history limit reached; no versions were deleted"
                )
            specified = requested_extent(brief) if not old else old["extent"]
            if specified and delta["extent"] != specified:
                raise ValueError(
                    "The design must preserve the requested project extent"
                )
            if old and delta["extent"] != old["extent"]:
                raise ValueError("Changing the project boundary needs a new project")
            components = (
                {c["name"]: deepcopy(c) for c in old["components"]} if old else {}
            )
            changed = (
                list(components) if old and old["palette"] != delta["palette"] else []
            )
            if delta["remove"]:
                if delta["remove"] not in components:
                    raise ValueError("The component to remove does not exist")
                del components[delta["remove"]]
                changed.append(delta["remove"])
            seen = set()
            for component in delta["components"]:
                name = component["name"].strip()
                if not name or name in seen or name != component["name"]:
                    raise ValueError("Component names must be unique and nonempty")
                seen.add(name)
                requirement = next(
                    (
                        r
                        for r in (old or {}).get("requirements", [])
                        if r["name"] == name
                    ),
                    None,
                )
                if requirement:
                    from smb3_agent.minecraft_requirements import reconcile

                    # Re-validate explicit facts at the persistence boundary, not only at inference.
                    candidate = {
                        "0": dict(zip(("width", "depth", "height"), component["size"]))
                        | {"zone": component["zone"]}
                    }
                    checked = reconcile([requirement], candidate)[0]
                    if any(
                        component[k] != checked[k] for k in ("kind", "turn", "link")
                    ):
                        raise ValueError(
                            "Component contradicts authoritative requirements"
                        )
                w, d, h = component["size"]
                if component["turn"] % 2:
                    w, d = d, w
                y = {"shore": 0, "raised": 4, "ridge": 24}[component["level"]]
                if h > 48:
                    raise ValueError("Component height exceeds design limits")
                if requirement and "elevation" in requirement["constraints"]:
                    y = requirement["constraints"]["elevation"]
                if not -12 <= y <= 36:
                    raise ValueError("Elevation outside project design limits")
                previous = components.get(name)
                if (
                    previous
                    and not (requirement and requirement.get("relocate"))
                    and previous["zone"] == component["zone"]
                    and previous["link"] == component["link"]
                ):
                    x, z = previous["box"][:2]
                else:
                    centers = {
                        "north": (0.5, 0.2),
                        "south": (0.5, 0.8),
                        "east": (0.8, 0.5),
                        "west": (0.2, 0.5),
                        "center": (0.5, 0.5),
                    }
                    cx, cz = centers[component["zone"]]
                    extent = delta["extent"]
                    if component["link"] in components and (
                        not previous
                        or previous["link"] != component["link"]
                        or (requirement and requirement.get("relocate"))
                    ):
                        anchor = components[component["link"]]["box"]
                        cx, cz = (
                            (anchor[0] + anchor[2] / 2) / extent,
                            (anchor[1] + anchor[3] / 2) / extent,
                        )
                    # Use a stable search around the requested zone; never move other places.
                    candidates = [
                        (px, pz)
                        for px in range(16, extent - w - 15, 4)
                        for pz in range(16, extent - d - 15, 4)
                    ]
                    if component["kind"] in {"terrain", "water", "path", "grove"} and (
                        w > extent - 32 or d > extent - 32
                    ):
                        candidates = [
                            (max(0, (extent - w) // 2), max(0, (extent - d) // 2))
                        ]
                    candidates.sort(
                        key=lambda p: (
                            (p[0] + w / 2 - cx * extent) ** 2
                            + (p[1] + d / 2 - cz * extent) ** 2
                        )
                    )

                    def clear(position):
                        px, pz = position
                        linked = components.get(component["link"])
                        if linked and linked["kind"] == "water":
                            ax, az, aw, ad, *_ = linked["box"]
                            if component["kind"] == "bridge":
                                # Cross the narrow axis with a dry landing on both banks.
                                if aw < ad:
                                    if not (px < ax and px + w > ax + aw and az <= pz and pz + d <= az + ad):
                                        return False
                                elif not (pz < az and pz + d > az + ad and ax <= px and px + w <= ax + aw):
                                    return False
                            elif component["kind"] in {"building", "tower", "pavilion"}:
                                # Near water means beside it, never submerged in its footprint.
                                if px < ax + aw + 2 and px + w + 2 > ax and pz < az + ad + 2 and pz + d + 2 > az:
                                    return False
                        for water in components.values():
                            if water["kind"] != "water" or component["kind"] not in {"building", "tower", "pavilion"}:
                                continue
                            ax, az, aw, ad, *_ = water["box"]
                            # An enclosing ocean is a boundary, not an all-water rectangle.
                            if water.get("constraints", {}).get("border"):
                                continue
                            if px < ax+aw and px+w > ax and pz < az+ad and pz+d > az:
                                return False
                        for other in components.values():
                            if (
                                other["name"] == name
                                or other["kind"]
                                in {"terrain", "water", "path", "grove"}
                                or component["kind"]
                                in {"terrain", "water", "path", "grove"}
                            ):
                                continue
                            ox, oz, ow, od, *_ = other["box"]
                            if (
                                px < ox + ow + 2
                                and px + w + 2 > ox
                                and pz < oz + od + 2
                                and pz + d + 2 > oz
                            ):
                                return False
                        return True

                    selected = next(
                        (position for position in candidates if clear(position)), None
                    )
                    if selected is None:
                        raise ValueError(
                            "No clear footprint in the requested layout; choose a smaller component"
                        )
                    x, z = selected
                if x + w > delta["extent"] or z + d > delta["extent"]:
                    raise ValueError("Revised footprint exceeds the project boundary")
                if component["kind"] not in {"terrain", "water", "grove", "path"}:
                    for other in components.values():
                        if other["name"] == name or other["kind"] in {
                            "terrain",
                            "water",
                            "grove",
                            "path",
                        }:
                            continue
                        ox, oz, ow, od, *_ = other["box"]
                        if x < ox + ow and x + w > ox and z < oz + od and z + d > oz:
                            raise ValueError(
                                "This revision overlaps another named place; choose a different location or smaller footprint"
                            )
                component = {**component, "box": [x, z, w, d, y, h]}
                if requirement:
                    component.update(
                        requirement_source=deepcopy(requirement["source"]),
                        rooms=list(requirement["rooms"]),
                        connections=list(requirement["connections"]),
                        objects=list(requirement["objects"]),
                        native=list(requirement["native"]),
                        constraints=deepcopy(requirement["constraints"]),
                        measurements=deepcopy(requirement.get("measurements", [])),
                    )
                if component["link"] == name:
                    raise ValueError("A component cannot connect to itself")
                components[name] = deepcopy(component)
                changed.append(name)
            if len(components) > 40:
                raise ValueError("Design component budget reached")
            if not components:
                raise ValueError(delta["reply"] or "Describe the places to include")
            value = {
                "revision": revision + 1,
                "title": delta["title"],
                "extent": delta["extent"],
                "palette": delta["palette"],
                "components": list(components.values()),
                "brief": old["brief"] if old else brief,
                "request": brief,
                "references": self.references(),
                "changed": changed,
                "previous_components": old["components"] if old else [],
                "uncertainty": "Interpretation from your text and captions; image analysis unavailable. Review dimensions and relationships.",
                "protected_buffer": 32,
                "estimated_volume": sum(
                    math.prod(c["box"][2:4]) * c["box"][5] for c in components.values()
                ),
                "estimate_note": "Bounding volume, not a block count or completion-time promise.",
            }
            if old and "requirements" in old:
                from smb3_agent.minecraft_requirements import checklist

                for key in ("requirements", "sources", "planning"):
                    value[key] = deepcopy(old[key])
                value["checklist"] = checklist(value)
            self._save_version(value)
            return value

    def refresh_paths(self, revision):
        """Explicitly version a path review without moving existing places."""
        with self.project.lock:
            old = self.current()
            if not old or old["revision"] != revision:
                raise ValueError("Design changed; review the latest places")
            value = deepcopy(old)
            value.update(revision=revision + 1, changed=[],
                         previous_components=deepcopy(old["components"]),
                         request="Review updated paths around retained buildings.")
            self._save_version(value)
            return value

    def separate_architecture(self, revision):
        """Propose disjoint sites as a new design version; terrain still needs review."""
        with self.project.lock:
            old = self.current()
            if not old or old["revision"] != revision:
                raise ValueError("Design changed; review the latest places")
            if self.project.db.execute(
                "SELECT 1 FROM architecture_stages LIMIT 1"
            ).fetchone():
                raise ValueError(
                    "Built architecture must not be relocated by layout arrangement"
                )
            value = deepcopy(old)
            sites = [
                c
                for c in value["components"]
                if c["kind"]
                in {
                    "building",
                    "pavilion",
                    "tower",
                    "dock",
                    "bridge",
                    "wreck",
                    "cave",
                    "decoration",
                    "platform",
                }
                or (c["kind"] == "terrain" and c.get("objects"))
            ]
            # Keep outdoor inventories first; then reserve real room footprints.
            sites.sort(key=lambda c: c["kind"] != "terrain")
            placed, changed = [], []
            extent = value["extent"]
            for c in sites:
                x, z, w, d, y, h = c["box"]

                def clear(a, b):
                    return all(
                        not (
                            a < px + pw + 3
                            and a + w + 3 > px
                            and b < pz + pd + 3
                            and b + d + 3 > pz
                        )
                        for px, pz, pw, pd in placed
                    )

                if not clear(x, z):
                    candidates = sorted(
                        (
                            (a, b)
                            for a in range(16, extent - w - 15, 2)
                            for b in range(16, extent - d - 15, 2)
                        ),
                        key=lambda p: (abs(p[0] - x) + abs(p[1] - z), p),
                    )
                    found = next((p for p in candidates if clear(*p)), None)
                    if found is None:
                        raise ValueError(
                            "No disjoint layout fits; review dimensions before building"
                        )
                    x, z = found
                    c["box"] = [x, z, w, d, y, h]
                    changed.append(c["name"])
                placed.append((x, z, w, d))
            if not changed:
                return old
            value.update(
                revision=revision + 1,
                changed=changed,
                previous_components=deepcopy(old["components"]),
                request="Separate overlapping architecture sites; dimensions and source requirements retained.",
            )
            value["layout_dependency"] = (
                "Moved sites require explicit terrain review and construction before architecture."
            )
            self._save_version(value)
            return value

    def compile_component(self, revision, name):
        with self.project.lock:
            design = self.current()
            if not design or design["revision"] != revision:
                raise ValueError(
                    "Review the latest design before preparing construction"
                )
            if design.get("planning", {}).get("state", "ready") != "ready":
                raise ValueError(
                    "Resolve the requirement checklist before preparing construction"
                )
            component = next(
                (c for c in design["components"] if c["name"] == name), None
            )
            problem = preview_problem(component)
            if problem:
                raise ValueError(problem)
            x, z, w, d, y, h = component["box"]
            # The UI explicitly labels this as a component sample at the preview site,
            # not construction at its full-plan destination.
            x = self.project.region["bounds"]["min"]["x"] + 16
            z = self.project.region["bounds"]["min"]["z"] + 32
            y = self.project.region["bounds"]["min"]["y"] + y
            material = PALETTES[design["palette"]][0]
            cells = {}
            for dx in range(w):
                for dz in range(d):
                    cells[x + dx, y, z + dz] = material
                    if component["kind"] == "pavilion":
                        cells[x + dx, y + h - 1, z + dz] = material
            if component["kind"] == "pavilion":
                for dx, dz in ((0, 0), (w - 1, 0), (0, d - 1), (w - 1, d - 1)):
                    for dy in range(1, h - 1):
                        cells[x + dx, y + dy, z + dz] = material
            base = self.project.region["bounds"]["min"]["y"]
            for dx, dz in ((0, 0), (w - 1, 0), (0, d - 1), (w - 1, d - 1)):
                for support_y in range(base, y):
                    cells[x + dx, support_y, z + dz] = material
            result = [
                {"position": dict(zip(("x", "y", "z"), p)), "after": v}
                for p, v in cells.items()
            ]
        self.project.prepare(result)
        with self.project.lock:
            self.project.db.execute(
                "INSERT INTO design_bindings VALUES (?,?,?)",
                (revision, name, self.project.revision),
            )
            self.project.db.commit()
        return len(result)
