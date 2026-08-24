from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="Mednafen desktop control is macOS-only"
)


def test_focus_mednafen_fails_closed_when_automation_command_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mednafen = importlib.import_module("smb3_agent.backends.mednafen")

    def failed_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="permission denied")

    monkeypatch.setattr(mednafen.subprocess, "run", failed_run)

    with pytest.raises(RuntimeError, match="permission denied"):
        mednafen.focus_mednafen()


def test_focus_mednafen_requires_both_automation_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mednafen = importlib.import_module("smb3_agent.backends.mednafen")
    calls: list[list[str]] = []

    def successful_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(mednafen.subprocess, "run", successful_run)
    monkeypatch.setattr(mednafen.time, "sleep", lambda _: None)

    mednafen.focus_mednafen()

    assert len(calls) == 2
    assert all(call[:2] == ["osascript", "-e"] for call in calls)


def test_process_output_does_not_retain_private_game_path(tmp_path: Path) -> None:
    mednafen = importlib.import_module("smb3_agent.backends.mednafen")
    game_path = tmp_path / "private-game-file.nes"
    game_path.write_bytes(b"fixture")
    emulator = mednafen.MednafenProcess(game_path)

    class FinishedProcess:
        returncode = 0

        @staticmethod
        def poll() -> int:
            return 0

        @staticmethod
        def communicate(timeout: int) -> tuple[str, None]:
            return f"opened {game_path} with private diagnostics", None

    emulator.process = FinishedProcess()
    emulator.close()

    assert str(game_path) not in emulator.output
    assert emulator.output == "mednafen output captured (" + str(
        len(f"opened {game_path} with private diagnostics")
    ) + " characters; content redacted)"
