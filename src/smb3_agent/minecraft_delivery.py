"""Minecraft delivery paths and bounded runtime discovery, independent of shell cwd."""

from pathlib import Path
import os
import shutil
import subprocess

from smb3_agent.paths import is_packaged, repository_path


GAME_VERSION = "1.21.4"


def data_artifacts():
    if is_packaged() or os.environ.get("GAME_COMPANION_USER_DATA"):
        from smb3_agent.player_store import user_data_root

        return user_data_root() / "artifacts"
    return repository_path("artifacts")


def node_runtime():
    bundled = repository_path("runtime/node")
    if is_packaged():
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)
        raise ValueError(
            "The app’s Node runtime is missing. Reinstall this build; your worlds will be retained."
        )
    found = shutil.which("node")
    if not found:
        raise ValueError(
            "Node is unavailable. Open the installed Game Companion app, which includes Node."
        )
    return found


def java_runtime():
    # Explicit macOS homes avoid /usr/bin/java’s interactive installer stub.
    candidates = sorted(
        Path("/Library/Java/JavaVirtualMachines").glob("*/Contents/Home/bin/java")
    )
    candidates += sorted(
        (Path.home() / "Library/Java/JavaVirtualMachines").glob(
            "*/Contents/Home/bin/java"
        )
    )
    for candidate in candidates:
        try:
            result = subprocess.run(
                [str(candidate), "-version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and 'version "21.' in result.stderr:
                return str(candidate)
        except (OSError, subprocess.TimeoutExpired):
            pass
    raise ValueError(
        "Java 21 is required. Install a macOS Java 21 JDK, then choose Check setup again. Existing worlds are unchanged."
    )


def world_directory(survival=False):
    """Canonical directory name, independent of the active data profile."""
    return (
        f"minecraft-b1-survival-{GAME_VERSION}"
        if survival
        else f"minecraft-b1-practice-{GAME_VERSION}"
    )


def world_home(survival=False):
    return data_artifacts() / world_directory(survival)


def retained_world(home, *, expected_id=None, survival=None):
    import json

    home = Path(home)
    required = [
        "companion-practice.json",
        "world-identity.json",
        "practice-world/level.dat",
        "eula.txt",
    ]
    if any(not (home / name).is_file() for name in required):
        raise ValueError(
            "Retained world files are missing. Restore the saved world from your backup; this app will not recreate it. Choose another world meanwhile."
        )
    marker = json.loads((home / "companion-practice.json").read_text())
    identity = json.loads((home / "world-identity.json").read_text())
    if (
        marker != {"schema": 1, "version": GAME_VERSION}
        or not isinstance(identity, dict)
        or not isinstance(identity.get("id"), str)
        or not identity["id"].strip()
        or type(identity.get("survival")) is not bool
    ):
        raise ValueError(
            "Retained world identity or version is incompatible. Restore its matching backup; conversion is unavailable."
        )
    if expected_id is not None and identity["id"] != expected_id:
        raise ValueError("Retained world identity changed; reconnect refused.")
    if survival is not None and identity["survival"] != survival:
        raise ValueError("Refusing to change retained world mode")
    if "eula=true" not in (home / "eula.txt").read_text().splitlines():
        raise ValueError(
            "Retained world EULA acceptance is missing. Restore its accepted configuration before opening."
        )
    return identity


def setup_status():
    status = {"worlds": {}}
    for name, check in [("node", node_runtime), ("java", java_runtime)]:
        try:
            status[name] = {
                "ready": True,
                "path": check(),
                "message": name.title() + " ready",
            }
        except ValueError as exc:
            status[name] = {"ready": False, "message": str(exc)}
    for mode in ("creative", "survival"):
        home = world_home(mode == "survival")
        row = {"exists": home.exists() and any(home.iterdir()), "ready": False}
        if row["exists"]:
            try:
                row.update(
                    identity=retained_world(home, survival=mode == "survival"),
                    ready=True,
                    message="Retained world ready",
                )
            except (ValueError, OSError) as exc:
                row["message"] = str(exc)
        else:
            row["message"] = "No world yet. Choose Create new practice world."
        status["worlds"][mode] = row
    return status
