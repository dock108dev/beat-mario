"""Bounded local player data; saved configuration never contains live authority."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import threading
from uuid import uuid4
from datetime import datetime, timezone

from smb3_agent.game_profiles import ExecutableProfile

VERSION = "0.2.0-private.2"
TEMPLATES = {
    "openttd": {
        "label": "OpenTTD · one repayment",
        "surface": "/openttd",
        "supported": [
            "Repay £10,000 once in a paused disposable company; verify cash and loan."
        ],
        "unavailable": [
            "General company management",
            "Building, borrowing, demolition and network play",
        ],
        "settings": {
            "game_build": "15.3",
            "model": "gemma3:4b",
            "viewport": "1280 × 1024",
        },
    },
    "minecraft": {
        "label": "Minecraft Java · Creative practice",
        "surface": "/minecraft",
        "supported": [
            "Local setup and saved requests",
            "App-created calibration and checked camera tasks through Review/Start",
            "Review world scope, short movement, aiming and the 19-cell wall; checked availability appears in the workspace",
        ],
        "unavailable": [
            "Unchecked gameplay families shown unavailable in the workspace",
            "Survival, flying, breaking blocks, inventory changes and unrestricted exploration",
        ],
        "settings": {
            "game_build": "26.3 vanilla",
            "model": "gemma3:4b",
            "viewport": "854 × 508 points / 1708 × 1016 pixels",
            "sensitivity": "50%",
            "fov": "70",
            "hud": "F3 visible",
            "font": "default / Retina 2×",
        },
    },
}


def user_data_root():
    return (
        Path(
            os.environ.get(
                "GAME_COMPANION_USER_DATA",
                str(Path.home() / "Library/Application Support/Game Companion"),
            )
        )
        .expanduser()
        .resolve()
    )


def bounded_json(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(raw.encode()) > 65536:
        raise ValueError("Profile or report is too large (64 KB maximum)")
    return raw


def validate_profile(value):
    if not isinstance(value, dict):
        raise ValueError("Profile must be an object")
    expected = {
        "schema",
        "id",
        "name",
        "game",
        "settings",
        "notes",
        "executable",
    }
    if value.get("schema") == "player-profile/v2":
        expected.add("workspace")
    if set(value) != expected:
        raise ValueError(
            "Unknown profile fields; live authority and executable content are refused"
        )
    if value["schema"] not in {
        "player-profile/v1",
        "player-profile/v2",
    } or not re.fullmatch(r"[a-f0-9]{32}", str(value["id"])):
        raise ValueError("Unsupported profile identity")
    if not isinstance(value["game"], str) or value["game"] not in TEMPLATES:
        raise ValueError("Choose an implemented game template")
    for field, limit in [("name", 80), ("notes", 2000)]:
        if (
            not isinstance(value[field], str)
            or len(value[field]) > limit
            or (field == "name" and not value[field].strip())
        ):
            raise ValueError("Invalid profile " + field)
    if value["settings"] != TEMPLATES[value["game"]]["settings"]:
        raise ValueError(
            "These settings are not supported yet. Use the displayed template settings."
        )
    if value["executable"] is not None:
        profile = ExecutableProfile.from_dict(value["executable"])
        if value["game"] != profile.game_id or profile.game_id != "openttd":
            raise ValueError(
                "Profile capability family is not implemented for this template"
            )
    if "workspace" in value and value["workspace"] is not None:
        workspace = value["workspace"]
        if (
            value["game"] != "minecraft"
            or not isinstance(workspace, dict)
            or set(workspace)
            != {"anchor", "axis", "material", "protected", "stop_point"}
        ):
            raise ValueError(
                "Workspace contains unsupported fields; observations and authority cannot be imported"
            )
        from smb3_agent.minecraft_wall import WallScope

        WallScope(
            tuple(workspace["anchor"]),
            workspace["axis"],
            workspace["material"],
            tuple(tuple(v) for v in workspace["protected"]),
            tuple(workspace["stop_point"]),
            "saved configuration; fresh inspection required",
        )
    bounded_json(value)
    return value


class PlayerStore:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else user_data_root()
        self.lock = threading.RLock()
        for name in ("profiles", "history", "reports", "sessions"):
            (self.root / name).mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise ValueError("Invalid local profile identity")
        return self.root / "profiles" / (identity + ".json")

    def _write(self, path, value):
        raw = bounded_json(value)
        with self.lock:
            temp = path.with_name("." + uuid4().hex + ".tmp")
            try:
                with temp.open("x") as stream:
                    os.chmod(temp, 0o600)
                    stream.write(raw + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)

    def list(self):
        result = []
        for path in sorted((self.root / "profiles").glob("*.json")):
            try:
                result.append(validate_profile(json.loads(path.read_text())))
            except (ValueError, OSError):
                continue  # preserve malformed incoming files for inspection
        return result

    def load(self, identity):
        path = self._path(identity)
        if path.stat().st_size > 65536:
            raise ValueError("Profile is too large")
        return validate_profile(json.loads(path.read_text()))

    def save(
        self, *, game, name, notes="", identity=None, executable=None, workspace=None
    ):
        if game not in TEMPLATES:
            raise ValueError("Unknown game template")
        if identity:
            previous = self.load(identity)
            if previous["game"] != game:
                raise ValueError("Create a new profile to change the game")
            if executable is None:
                executable = previous["executable"]
            if workspace is None:
                workspace = previous.get("workspace")
        value = validate_profile(
            {
                "schema": "player-profile/v2"
                if workspace is not None
                else "player-profile/v1",
                "id": identity or uuid4().hex,
                "game": game,
                "name": name,
                "notes": notes,
                "settings": dict(TEMPLATES[game]["settings"]),
                "executable": executable,
                **({"workspace": workspace} if workspace is not None else {}),
            }
        )
        self._write(self._path(value["id"]), value)
        return value

    def import_profile(self, raw):
        if not isinstance(raw, str) or len(raw.encode()) > 65536:
            raise ValueError("Import a profile smaller than 64 KB")
        value = validate_profile(json.loads(raw))
        value = {**value, "id": uuid4().hex}  # never overwrite local work
        self._write(self._path(value["id"]), value)
        return value

    def duplicate(self, identity):
        value = self.load(identity)
        return self.save(
            game=value["game"],
            name=(value["name"][:70] + " copy"),
            notes=value["notes"],
            executable=value["executable"],
            workspace=value.get("workspace"),
        )

    def record(self, identity, outcome):
        self.load(identity)
        # Deliberate allowlist: no screenshots, paths, live selection or credentials.
        row = {
            key: outcome[key]
            for key in (
                "status",
                "reason",
                "request",
                "completed",
                "unknown",
                "version",
                "existing",
                "placed",
                "doorway_empty",
                "protected_verified",
                "final_verified",
                "stop_point_observed",
                "input_ms",
                "steps_used",
            )
            if key in outcome
        }
        row["id"] = uuid4().hex
        row["at"] = datetime.now(timezone.utc).isoformat()
        self._write(self.root / "history" / (identity + "-" + row["id"] + ".json"), row)
        return row

    def history(self, identity):
        self.load(identity)
        rows = [
            json.loads(p.read_text())
            for p in (self.root / "history").glob(identity + "-*.json")
        ]
        return sorted(rows, key=lambda row: row.get("at", ""))[-50:]

    def report(self, *, text, profile_id=None, checks=None):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
            raise ValueError(
                "Describe what happened, what you expected, and how to reproduce it (up to 4000 characters)."
            )
        row = {
            "schema": "player-issue/v1",
            "version": VERSION,
            "id": uuid4().hex,
            "feedback": text,
            "checks": checks or {},
            "profile": None,
            "recent_outcomes": [],
        }
        if profile_id:
            value = self.load(profile_id)
            row["profile"] = {k: value[k] for k in ("id", "game", "settings")}
            row["recent_outcomes"] = self.history(profile_id)[-5:]
        path = self.root / "reports" / (row["id"] + ".json")
        self._write(path, row)
        return {"report": row, "path": str(path)}
