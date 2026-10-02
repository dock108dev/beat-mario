"""App-owned supported settings, with backups; no save/world access."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.player_store import user_data_root

OPTIONS = {
    "mouseSensitivity": "0.5",
    "invertXMouse": "false",
    "invertYMouse": "false",
    "fov": "0.0",
    "fovEffectScale": "1.0",
    "guiScale": "0",
    "debugGuiScale": "0",
    "fullscreen": "false",
    "forceUnicodeFont": "false",
    "resourcePacks": "[]",
    "incompatibleResourcePacks": "[]",
    "advancedItemTooltips": "true",
    "reducedDebugInfo": "false",
    "lang": "en_us",
    "key_key.smoothCamera": "key.keyboard.unknown",
    "key_key.inventory": "key.keyboard.e",
    "key_key.debug.overlay": "key.keyboard.f3",
    "key_key.debug.modifier": "key.keyboard.f3",
}
DEBUG = {
    "DataVersion": 4649,
    "custom": {
        f"minecraft:{key}": "alwaysOn"
        for key in (
            "game_version",
            "fps",
            "tps",
            "memory",
            "system_specs",
            "player_position",
            "player_section_position",
            "simple_performance_impactors",
            "looking_at_block_state",
            "looking_at_fluid_state",
        )
    },
}


def minecraft_running():
    rows = subprocess.check_output(
        ["ps", "-axo", "comm"], text=True, timeout=2
    ).splitlines()
    return any(
        "Application Support/minecraft/runtime/" in p and p.endswith("/bin/java")
        for p in rows
    )


def read_options(root=None):
    root = Path(root) if root else Path.home() / "Library/Application Support/minecraft"
    path = root / "options.txt"
    if path.stat().st_size > 65536:
        raise FeedbackError("Minecraft settings are too large")
    result = {}
    for row in path.read_text().splitlines():
        key, sep, value = row.partition(":")
        if not sep or key in result:
            raise FeedbackError("Minecraft settings are malformed or ambiguous")
        result[key] = value
    return result


def require_supported_scene(root=None):
    root = Path(root) if root else Path.home() / "Library/Application Support/minecraft"
    values = read_options(root)
    if any(values.get(k) != v for k, v in OPTIONS.items()):
        raise FeedbackError(
            "Use Apply supported Minecraft settings, then restart the game"
        )
    path = root / "debug-profile.json"
    if (
        not path.exists()
        or path.stat().st_size > 65536
        or json.loads(path.read_text()) != DEBUG
    ):
        raise FeedbackError(
            "Targeted-block HUD is unavailable; apply supported settings and restart Minecraft"
        )
    return hashlib.sha256(
        json.dumps(
            {"options": {k: values[k] for k in OPTIONS}, "debug": DEBUG}, sort_keys=True
        ).encode()
    ).hexdigest()


def apply_supported_settings(*, root=None, backups=None, running=minecraft_running):
    """Explicit setup only. Back up both files before any atomic replacement."""
    root = Path(root) if root else Path.home() / "Library/Application Support/minecraft"
    backups = Path(backups) if backups else user_data_root() / "settings-backups"
    if running():
        raise FeedbackError(
            "Quit Minecraft first. This preserves your current settings safely."
        )
    values = read_options(root)
    paths = [root / "options.txt", root / "debug-profile.json"]
    original = {p: p.read_bytes() if p.exists() else None for p in paths}
    if original[paths[1]] is not None and len(original[paths[1]]) > 65536:
        raise FeedbackError("Debug settings are too large")
    folder = backups / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False, mode=0o700)
    for p, data in original.items():
        if data is not None:
            target = folder / p.name
            target.write_bytes(data)
            target.chmod(0o600)
    values.update(OPTIONS)
    replacement = {
        paths[0]: ("\n".join(f"{k}:{v}" for k, v in values.items()) + "\n").encode(),
        paths[1]: (json.dumps(DEBUG, indent=2) + "\n").encode(),
    }
    written = []
    try:
        if running() or any(
            (p.read_bytes() if p.exists() else None) != original[p] for p in paths
        ):
            raise FeedbackError(
                "Minecraft or settings changed; nothing applied. Retry after quitting."
            )
        for p, data in replacement.items():
            temporary = p.with_name("." + uuid4().hex + ".tmp")
            try:
                with temporary.open("xb") as stream:
                    os.chmod(temporary, 0o600)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(p)
                written.append(p)
            finally:
                temporary.unlink(missing_ok=True)
        require_supported_scene(root)
    except Exception:
        # Restore only this operation's unchanged replacements; never incoming edits.
        for p in written:
            if p.read_bytes() == replacement[p]:
                if original[p] is None:
                    p.unlink()
                else:
                    p.write_bytes(original[p])
        raise
    return {
        "backup": str(folder),
        "settings_sha256": require_supported_scene(root),
        "message": "Supported controls, English, default resources, advanced tooltips and targeted-block HUD applied. Restart Minecraft; the pose/target HUD stays visible. Choose a full block in your hotbar.",
    }
