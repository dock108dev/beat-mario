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
    save_state,
    write_process_output_tail,
)
from smb3_agent.detection.state_detector import detect_state


CHECKPOINT_1_1_SEQUENCE = [
    ("boot", None, 0.0, None),
    ("title_menu", "enter", 2.0, "title_menu.png"),
    ("world_1_map", "enter", 5.0, "world_1_map.png"),
    ("map_move_right", "right", 0.8, None),
    ("map_move_up", "up", 0.8, None),
    ("level_1_1_start", "x", 1.0, "level_1_1_start.png"),
]


def run_checkpoint_1_1_task(
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
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    state_dir = Path.home() / ".mednafen" / "mcs"
    before_state_files = state_file_snapshot(state_dir)
    captures: list[dict[str, object]] = []

    with MednafenProcess(game_path) as emulator:
        time.sleep(startup_seconds)
        focus_mednafen()

        final_game_capture_path: Path | None = None
        for step_name, button, wait_seconds, fixture_name in CHECKPOINT_1_1_SEQUENCE:
            if button:
                press(button)
            if wait_seconds:
                time.sleep(wait_seconds)

            if step_name == "level_1_1_start":
                save_state(slot)
                time.sleep(0.4)

            focus_mednafen()
            bounds = find_mednafen_window()
            window_capture = capture_window(bounds, run_dir / f"{step_name}_window.png")
            game_capture_path = run_dir / f"{step_name}_game.png"
            game_capture = capture_game_view(bounds, game_capture_path)
            captures.append(
                {
                    "step": step_name,
                    "button": button,
                    "wait_seconds": wait_seconds,
                    "window_bounds": asdict(bounds),
                    "window_capture": asdict(window_capture),
                    "game_capture": asdict(game_capture),
                    "fixture": fixture_name,
                }
            )
            if fixture_name:
                shutil.copyfile(game_capture_path, fixtures_dir / fixture_name)
            final_game_capture_path = game_capture_path

        if final_game_capture_path is None:
            raise RuntimeError("No final capture was produced")

        detection = detect_state(final_game_capture_path, fixtures_dir)
        if detection.state != "LEVEL_1_1":
            raise RuntimeError(f"Expected LEVEL_1_1 before save-state, detected {detection.state}")

    after_state_files = state_file_snapshot(state_dir)
    write_process_output_tail(emulator.output, run_dir / "mednafen-output-tail.txt")

    result = {
        "task": "checkpoint-1-1",
        "backend": "mednafen",
        "game_file": "<redacted-local-game-file>",
        "process_returncode": emulator.returncode,
        "startup_seconds": startup_seconds,
        "slot": slot,
        "state_dir": str(state_dir),
        "state_files_before": before_state_files,
        "state_files_after": after_state_files,
        "new_or_updated_state_files": diff_state_files(before_state_files, after_state_files),
        "final_detection": asdict(detection),
        "sequence": CHECKPOINT_1_1_SEQUENCE,
        "fixtures_dir": str(fixtures_dir.resolve()),
        "captures": captures,
        "run_dir": str(run_dir.resolve()),
    }
    metadata_path = run_dir / "checkpoint-1-1.json"
    metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))


def state_file_snapshot(state_dir: Path) -> dict[str, dict[str, float | int]]:
    if not state_dir.exists():
        return {}
    snapshot: dict[str, dict[str, float | int]] = {}
    for path in sorted(state_dir.glob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        snapshot[str(path)] = {"size": stat.st_size, "mtime": stat.st_mtime}
    return snapshot


def diff_state_files(
    before: dict[str, dict[str, float | int]],
    after: dict[str, dict[str, float | int]],
) -> list[str]:
    changed: list[str] = []
    for path, after_stat in after.items():
        before_stat = before.get(path)
        if before_stat != after_stat:
            changed.append(path)
    return changed
