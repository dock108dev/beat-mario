from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from smb3_agent.backends.mednafen import (
    MednafenProcess,
    accessibility_help,
    capture_game_view,
    capture_window,
    find_mednafen_window,
    focus_mednafen,
    is_accessibility_trusted,
    load_state,
    save_state,
    write_process_output_tail,
)
from smb3_agent.control.input_script import execute_input_script
from smb3_agent.detection.hud_detector import detect_hud
from smb3_agent.detection.state_detector import detect_state


def run_1_1_script_task(
    game_path: Path,
    script_path: Path,
    artifacts_dir: Path,
    fixtures_dir: Path,
    startup_seconds: float,
    slot: int,
    save_final_slot: int | None = None,
    sample_interval_seconds: float = 0.1,
) -> None:
    if not game_path.exists():
        raise SystemExit("local game file not found")
    if not script_path.exists():
        raise SystemExit(f"Input script not found: {script_path}")
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
        before_path = run_dir / "before_script_game.png"
        before_capture = capture_game_view(bounds, before_path)
        before_detection = detect_state(before_path, fixtures_dir)
        lives_dir = run_dir / "lives"
        before_hud = detect_hud(before_path, output_crop_path=lives_dir / "before_lives_digit.png")
        if before_detection.state != "LEVEL_1_1":
            raise RuntimeError(f"Expected LEVEL_1_1 before script, detected {before_detection.state}")

        trace_path = run_dir / "input_trace.jsonl"
        frames_dir = run_dir / "frames"
        stop_sampling = threading.Event()
        frame_records: list[dict[str, object]] = []
        script_start = time.monotonic()
        sampler = None
        if sample_interval_seconds > 0:
            sampler = threading.Thread(
                target=sample_frames,
                args=(
                    stop_sampling,
                    frames_dir,
                    frame_records,
                    script_start,
                    lives_dir / "before_lives_digit.png",
                    sample_interval_seconds,
                ),
                daemon=True,
            )
            sampler.start()
        try:
            input_events = execute_input_script(script_path, trace_path)
            time.sleep(1.0)
        finally:
            stop_sampling.set()
            if sampler is not None:
                sampler.join(timeout=2.0)
        time.sleep(0.1)

        focus_mednafen()
        bounds_after = find_mednafen_window()
        after_window = capture_window(bounds_after, run_dir / "after_script_window.png")
        after_path = run_dir / "after_script_game.png"
        after_capture = capture_game_view(bounds_after, after_path)
        after_detection = detect_state(after_path, fixtures_dir)
        after_hud = detect_hud(
            after_path,
            output_crop_path=lives_dir / "after_lives_digit.png",
            reference_lives_crop_path=lives_dir / "before_lives_digit.png",
        )
        saved_final_slot = None
        if (
            save_final_slot is not None
            and after_detection.state == "LEVEL_1_1"
            and not after_hud.lives_changed_from_reference
        ):
            save_state(save_final_slot)
            time.sleep(0.4)
            saved_final_slot = save_final_slot

    write_process_output_tail(emulator.output, run_dir / "mednafen-output-tail.txt")
    outcome = classify_outcome(
        after_detection.state,
        after_detection.confidence,
        after_hud.lives_changed_from_reference,
        after_hud.darkened_frame,
        frame_records,
    )

    result = {
        "task": "run-1-1-script",
        "backend": "mednafen",
        "game_file": "<redacted-local-game-file>",
        "script": str(script_path),
        "accessibility_trusted": is_accessibility_trusted(),
        "process_returncode": emulator.returncode,
        "startup_seconds": startup_seconds,
        "sample_interval_seconds": sample_interval_seconds,
        "slot": slot,
        "save_final_slot": save_final_slot,
        "saved_final_slot": saved_final_slot,
        "before_capture": asdict(before_capture),
        "before_detection": asdict(before_detection),
        "before_hud": asdict(before_hud),
        "after_window": asdict(after_window),
        "after_capture": asdict(after_capture),
        "after_detection": asdict(after_detection),
        "after_hud": asdict(after_hud),
        "outcome": outcome,
        "input_trace": str(trace_path.resolve()),
        "input_events": input_events,
        "frames": frame_records,
        "run_dir": str(run_dir.resolve()),
    }
    metadata_path = run_dir / "run-1-1-script.json"
    metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def sample_frames(
    stop_event: threading.Event,
    frames_dir: Path,
    frame_records: list[dict[str, object]],
    script_start: float,
    reference_lives_crop_path: Path,
    interval_seconds: float = 0.1,
) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    while not stop_event.is_set():
        try:
            bounds = find_mednafen_window()
            frame_path = frames_dir / f"frame_{index:03d}.png"
            capture = capture_game_view(bounds, frame_path)
            hud = detect_hud(frame_path, reference_lives_crop_path=reference_lives_crop_path)
            frame_records.append(
                {
                    "index": index,
                    "ts": round(time.monotonic() - script_start, 4),
                    "capture": asdict(capture),
                    "hud": asdict(hud),
                }
            )
            index += 1
        except Exception as error:
            frame_records.append(
                {
                    "index": index,
                    "ts": round(time.monotonic() - script_start, 4),
                    "error": repr(error),
                }
            )
            index += 1
        stop_event.wait(interval_seconds)


def classify_outcome(
    after_state: str,
    after_confidence: float,
    lives_changed: bool | None,
    after_darkened: bool,
    frame_records: list[dict[str, object]],
) -> dict[str, object]:
    darkened_frames = [
        frame
        for frame in frame_records
        if isinstance(frame.get("hud"), dict) and frame["hud"].get("darkened_frame")
    ]
    course_clear_detected = has_course_clear_frame(frame_records)
    if course_clear_detected and after_state == "WORLD_1_MAP":
        return {
            "result": "SUCCESS_MAP_RETURN",
            "reason": "Course-clear text screen was observed before the final World 1 map return.",
            "darkened_frame_count": len(darkened_frames),
            "first_darkened_frame": darkened_frames[0] if darkened_frames else None,
            "course_clear_detected": True,
        }
    if after_state == "WORLD_1_MAP":
        return {
            "result": "FAILED_MAP_RETURN_WITHOUT_CLEAR",
            "reason": "World map returned, but no course-clear text screen was observed.",
            "darkened_frame_count": len(darkened_frames),
            "first_darkened_frame": darkened_frames[0] if darkened_frames else None,
            "course_clear_detected": False,
        }
    if lives_changed:
        return {
            "result": "FAILED_DEATH",
            "reason": "Lives digit changed from the checkpoint value; map return is a death return, not level clear.",
            "darkened_frame_count": len(darkened_frames),
            "first_darkened_frame": darkened_frames[0] if darkened_frames else None,
            "course_clear_detected": course_clear_detected,
        }
    if after_darkened and after_confidence < 0.6:
        return {
            "result": "INCOMPLETE_DARK_LEVEL",
            "reason": "Final frame is darkened and state confidence is low; do not treat this as a map return.",
            "darkened_frame_count": len(darkened_frames),
            "first_darkened_frame": darkened_frames[0] if darkened_frames else None,
            "course_clear_detected": course_clear_detected,
        }
    return {
        "result": "INCOMPLETE",
        "reason": f"Script ended in {after_state}.",
        "darkened_frame_count": len(darkened_frames),
        "first_darkened_frame": darkened_frames[0] if darkened_frames else None,
        "course_clear_detected": course_clear_detected,
    }


def has_course_clear_frame(frame_records: list[dict[str, object]]) -> bool:
    for frame in frame_records:
        capture = frame.get("capture")
        if not isinstance(capture, dict):
            continue
        path = capture.get("path")
        if not isinstance(path, str):
            continue
        try:
            image = Image.open(path).convert("RGB")
        except OSError:
            continue

        luma = np.asarray(image.convert("L"), dtype=np.float32)
        if float(np.mean(luma)) > 80.0:
            continue

        crop = image.crop((510, 90, 930, 300))
        pixels = np.asarray(crop)
        white_pixels = (
            (pixels[:, :, 0] > 205)
            & (pixels[:, :, 1] > 205)
            & (pixels[:, :, 2] > 205)
        ).sum()
        if int(white_pixels) > 650:
            return True
    return False
