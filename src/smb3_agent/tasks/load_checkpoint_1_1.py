from __future__ import annotations

import json
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
    load_state,
    write_process_output_tail,
)
from smb3_agent.detection.state_detector import detect_state


def run_load_checkpoint_1_1_task(
    game_path: Path,
    artifacts_dir: Path,
    fixtures_dir: Path,
    startup_seconds: float,
    slot: int,
) -> None:
    if not game_path.exists():
        raise SystemExit("local game file not found")
    if not is_accessibility_trusted():
        raise SystemExit(accessibility_help())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = artifacts_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    with MednafenProcess(game_path) as emulator:
        time.sleep(startup_seconds)
        focus_mednafen()
        load_state(slot)
        time.sleep(1.5)
        focus_mednafen()
        bounds = find_mednafen_window()
        window_capture = capture_window(bounds, run_dir / "loaded_window.png")
        game_capture_path = run_dir / "loaded_game.png"
        game_capture = capture_game_view(bounds, game_capture_path)
        detection = detect_state(game_capture_path, fixtures_dir)
        if detection.state != "LEVEL_1_1":
            raise RuntimeError(f"Expected LEVEL_1_1 after loading checkpoint, detected {detection.state}")

    write_process_output_tail(emulator.output, run_dir / "mednafen-output-tail.txt")

    result = {
        "task": "load-checkpoint-1-1",
        "backend": "mednafen",
        "game_file": "<redacted-local-game-file>",
        "accessibility_trusted": is_accessibility_trusted(),
        "process_returncode": emulator.returncode,
        "startup_seconds": startup_seconds,
        "slot": slot,
        "window_bounds": asdict(bounds),
        "window_capture": asdict(window_capture),
        "game_capture": asdict(game_capture),
        "detection": asdict(detection),
        "run_dir": str(run_dir.resolve()),
    }
    metadata_path = run_dir / "load-checkpoint-1-1.json"
    metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
