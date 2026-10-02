import json
from pathlib import Path

import pytest

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.minecraft_settings import (
    apply_supported_settings,
    require_supported_scene,
    OPTIONS,
    DEBUG,
)


def test_supported_settings_preserve_previous_preferences_and_unrelated_values(
    tmp_path,
):
    root = tmp_path / "minecraft"
    root.mkdir()
    backups = tmp_path / "backups"
    original = b"mouseSensitivity:0.7\nlang:fr_fr\nunrelated:keep-me\n"
    (root / "options.txt").write_bytes(original)
    (root / "debug-profile.json").write_text('{"profile":"performance"}')
    result = apply_supported_settings(root=root, backups=backups, running=lambda: False)
    backup = Path(result["backup"])
    assert (backup / "options.txt").read_bytes() == original
    assert (backup / "debug-profile.json").read_text() == '{"profile":"performance"}'
    assert "unrelated:keep-me" in (root / "options.txt").read_text()
    assert require_supported_scene(root) == result["settings_sha256"]
    assert json.loads((root / "debug-profile.json").read_text()) == DEBUG
    values = dict(
        row.split(":", 1) for row in (root / "options.txt").read_text().splitlines()
    )
    assert all(values[k] == v for k, v in OPTIONS.items())


def test_running_game_and_concurrent_changes_refuse_without_overwriting(tmp_path):
    root = tmp_path / "minecraft"
    root.mkdir()
    path = root / "options.txt"
    path.write_text("lang:fr_fr\n")
    with pytest.raises(FeedbackError, match="Quit Minecraft"):
        apply_supported_settings(
            root=root, backups=tmp_path / "backups", running=lambda: True
        )
    assert path.read_text() == "lang:fr_fr\n"
    calls = [0]

    def running():
        calls[0] += 1
        if calls[0] == 2:
            path.write_text("lang:de_de\n")
        return False

    with pytest.raises(FeedbackError, match="changed"):
        apply_supported_settings(
            root=root, backups=tmp_path / "backups", running=running
        )
    assert (
        path.read_text() == "lang:de_de\n"
        and not (root / "debug-profile.json").exists()
    )


def test_missing_or_disabled_target_hud_cannot_imply_air(tmp_path):
    (tmp_path / "options.txt").write_text(
        "\n".join(f"{k}:{v}" for k, v in OPTIONS.items()) + "\n"
    )
    with pytest.raises(FeedbackError, match="Targeted-block"):
        require_supported_scene(tmp_path)
    (tmp_path / "debug-profile.json").write_text(
        json.dumps({"custom": {"minecraft:looking_at_block_state": "never"}})
    )
    with pytest.raises(FeedbackError, match="Targeted-block"):
        require_supported_scene(tmp_path)
