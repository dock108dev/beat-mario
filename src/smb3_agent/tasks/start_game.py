from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from smb3_agent.backends.mednafen import (
    MednafenProcess,
    accessibility_help,
    capture_game_view,
    capture_window,
    find_mednafen_window,
    focus_mednafen,
    is_accessibility_trusted,
    press,
    write_process_output_tail,
)


START_SEQUENCE = [
    ("boot", None, 0.0),
    ("title_menu", "enter", 2.0),
    ("world_1_map", "enter", 5.0),
]


def run_start_game_task(
    game_path: Path,
    artifacts_dir: Path,
    fixtures_dir: Path,
    startup_seconds: float,
) -> None:
    if not game_path.exists():
        raise SystemExit("local game file not found")
    if not is_accessibility_trusted():
        raise SystemExit(accessibility_help())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = artifacts_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    captures: list[dict[str, object]] = []

    with MednafenProcess(game_path) as emulator:
        time.sleep(startup_seconds)
        focus_mednafen()

        for step_name, button, wait_seconds in START_SEQUENCE:
            if button:
                press(button)
            if wait_seconds:
                time.sleep(wait_seconds)

            focus_mednafen()
            bounds = find_mednafen_window()
            window_capture = capture_window(bounds, run_dir / f"{step_name}_window.png")
            game_capture = capture_game_view(bounds, run_dir / f"{step_name}_game.png")
            captures.append(
                {
                    "step": step_name,
                    "button": button,
                    "wait_seconds": wait_seconds,
                    "window_bounds": asdict(bounds),
                    "window_capture": asdict(window_capture),
                    "game_capture": asdict(game_capture),
                }
            )
            if step_name in {"title_menu", "world_1_map"}:
                shutil.copyfile(run_dir / f"{step_name}_game.png", fixtures_dir / f"{step_name}.png")

    write_process_output_tail(emulator.output, run_dir / "mednafen-output-tail.txt")

    result = {
        "task": "start-game",
        "backend": "mednafen",
        "game_file": "<redacted-local-game-file>",
        "accessibility_trusted": is_accessibility_trusted(),
        "process_returncode": emulator.returncode,
        "startup_seconds": startup_seconds,
        "sequence": START_SEQUENCE,
        "fixtures_dir": str(fixtures_dir.resolve()),
        "captures": captures,
        "run_dir": str(run_dir.resolve()),
    }
    metadata_path = run_dir / "start-game.json"
    metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
