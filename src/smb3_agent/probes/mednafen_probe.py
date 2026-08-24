from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from smb3_agent.backends.mednafen import (
    MednafenProcess,
    capture_game_view,
    capture_window,
    find_mednafen_window,
    focus_mednafen,
    press,
)


def run_mednafen_probe(
    game_path: Path,
    artifacts_dir: Path,
    startup_seconds: float,
    after_start_seconds: float,
) -> None:
    if not game_path.exists():
        raise SystemExit("local game file not found")

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with MednafenProcess(game_path) as emulator:
        time.sleep(startup_seconds)
        focus_mednafen()
        bounds = find_mednafen_window()

        before_window = capture_window(bounds, artifacts_dir / f"{stamp}_before_start_window.png")
        before_game = capture_game_view(bounds, artifacts_dir / f"{stamp}_before_start_game.png")

        press("enter")
        time.sleep(after_start_seconds)

        bounds_after = find_mednafen_window()
        after_window = capture_window(bounds_after, artifacts_dir / f"{stamp}_after_start_window.png")
        after_game = capture_game_view(bounds_after, artifacts_dir / f"{stamp}_after_start_game.png")

    result = {
        "backend": "mednafen",
        "game_file": "<redacted-local-game-file>",
        "process_returncode": emulator.returncode,
        "window_bounds_before": asdict(bounds),
        "window_bounds_after": asdict(bounds_after),
        "captures": {
            "before_window": asdict(before_window),
            "before_game": asdict(before_game),
            "after_window": asdict(after_window),
            "after_game": asdict(after_game),
        },
        "mednafen_output_captured": bool(emulator.output),
    }
    metadata_path = artifacts_dir / f"{stamp}_probe.json"
    metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
