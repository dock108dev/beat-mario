from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ApplicationServices import AXIsProcessTrusted
import mss
import pyautogui
import Quartz
from PIL import Image, ImageStat


@dataclass(frozen=True)
class WindowBounds:
    left: int
    top: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_mss_region(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class WindowInfo:
    number: int
    bounds: WindowBounds


@dataclass(frozen=True)
class CaptureResult:
    path: str
    width: int
    height: int
    mean_rgb: list[float]


class MednafenProcess:
    def __init__(self, game_path: Path) -> None:
        if not game_path.exists():
            raise FileNotFoundError("local game file not found")
        self.game_path = game_path
        self.process: subprocess.Popen[str] | None = None
        self.output = ""

    def __enter__(self) -> "MednafenProcess":
        self.process = subprocess.Popen(
            ["mednafen", str(self.game_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    @property
    def returncode(self) -> int | None:
        return self.process.returncode if self.process else None

    def close(self) -> None:
        if not self.process:
            return

        if self.process.poll() is None:
            self.process.terminate()
            try:
                output, _ = self.process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                output, _ = self.process.communicate(timeout=5)
        else:
            output, _ = self.process.communicate(timeout=5)
        self.output = (
            f"mednafen output captured ({len(output)} characters; content redacted)"
            if output
            else ""
        )


def focus_mednafen() -> None:
    _run_focus_command(
        ["osascript", "-e", 'tell application "mednafen" to activate']
    )
    _run_focus_command(
        [
            "osascript",
            "-e",
            'tell application "System Events" to set frontmost of process "mednafen" to true',
        ]
    )
    time.sleep(0.5)


def _run_focus_command(argv: list[str]) -> None:
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no command output"
        raise RuntimeError(
            f"Failed to focus Mednafen (exit {completed.returncode}): {detail}"
        )


def find_mednafen_window() -> WindowBounds:
    return find_mednafen_window_info().bounds


def find_mednafen_window_info() -> WindowInfo:
    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    windows = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    candidates: list[WindowInfo] = []

    for window in windows:
        owner = str(window.get("kCGWindowOwnerName", ""))
        name = str(window.get("kCGWindowName", ""))
        if "mednafen" not in owner.lower() and "smb3" not in name.lower():
            continue

        bounds = parse_quartz_bounds(window.get("kCGWindowBounds"))
        if bounds.width > 0 and bounds.height > 0:
            candidates.append(WindowInfo(number=int(window.get("kCGWindowNumber")), bounds=bounds))

    if not candidates:
        raise RuntimeError("No visible Mednafen window found")

    return max(candidates, key=lambda candidate: candidate.bounds.area)


def parse_quartz_bounds(raw_bounds: object) -> WindowBounds:
    values = {
        key: int(value)
        for key, value in re.findall(r"(X|Y|Width|Height) = (-?\d+)", str(raw_bounds))
    }
    return WindowBounds(
        left=values["X"],
        top=values["Y"],
        width=values["Width"],
        height=values["Height"],
    )


def capture_window(bounds: WindowBounds, path: Path) -> CaptureResult:
    image = capture_mednafen_window_image()
    image.save(path)
    return capture_result(path, image)


def capture_game_view(bounds: WindowBounds, path: Path) -> CaptureResult:
    image = capture_mednafen_window_image()
    game = crop_game_view(image)
    game.save(path)
    return capture_result(path, game)


def capture_screen_region(bounds: WindowBounds, path: Path) -> CaptureResult:
    with mss.MSS() as screen_capture:
        shot = screen_capture.grab(bounds.to_mss_region())
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        image.save(path)
        return capture_result(path, image)


def capture_mednafen_window_image() -> Image.Image:
    window = find_mednafen_window_info()
    image_ref = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        window.number,
        Quartz.kCGWindowImageBoundsIgnoreFraming,
    )
    if image_ref is None:
        raise RuntimeError("Unable to capture Mednafen window image")

    width = Quartz.CGImageGetWidth(image_ref)
    height = Quartz.CGImageGetHeight(image_ref)
    provider = Quartz.CGImageGetDataProvider(image_ref)
    data = Quartz.CGDataProviderCopyData(provider)
    bytes_per_row = Quartz.CGImageGetBytesPerRow(image_ref)
    return Image.frombuffer(
        "RGBA",
        (width, height),
        bytes(data),
        "raw",
        "BGRA",
        bytes_per_row,
        1,
    ).convert("RGB")


def crop_game_view(image: Image.Image) -> Image.Image:
    top_trim = detect_window_chrome_height(image)
    game = image.crop((0, top_trim, image.width, image.height))
    if game.size != (1024, 896):
        game = game.resize((1024, 896), Image.Resampling.NEAREST)
    return game


def detect_window_chrome_height(image: Image.Image) -> int:
    pixels = image.load()
    for y in range(10, min(120, image.height)):
        row_total = 0
        sample_count = 0
        for x in range(0, image.width, max(1, image.width // 128)):
            r, g, b = pixels[x, y]
            row_total += r + g + b
            sample_count += 3
        if sample_count and row_total / sample_count < 20:
            return y
    return 64 if image.height >= 1792 else 30


def capture_result(path: Path, image: Image.Image) -> CaptureResult:
    stat = ImageStat.Stat(image)
    return CaptureResult(
        path=str(path.resolve()),
        width=image.width,
        height=image.height,
        mean_rgb=[round(value, 2) for value in stat.mean],
    )


def press(button: str) -> None:
    pyautogui.press(button)


def key_down(button: str) -> None:
    pyautogui.keyDown(button)


def key_up(button: str) -> None:
    pyautogui.keyUp(button)


def tap(button: str, duration_seconds: float = 0.08) -> None:
    key_down(button)
    time.sleep(duration_seconds)
    key_up(button)


def hotkey(*buttons: str) -> None:
    pyautogui.hotkey(*buttons)


def select_state_slot(slot: int) -> None:
    if slot < 0 or slot > 9:
        raise ValueError(f"Mednafen state slot must be 0-9, got {slot}")
    press(str(slot))


def save_state(slot: int = 0) -> None:
    select_state_slot(slot)
    time.sleep(0.2)
    press("f5")


def load_state(slot: int = 0) -> None:
    select_state_slot(slot)
    time.sleep(0.2)
    press("f7")


def is_accessibility_trusted() -> bool:
    return bool(AXIsProcessTrusted())


def accessibility_help() -> str:
    return (
        "macOS Accessibility permission is not trusted for this Python process. "
        "Open System Settings -> Privacy & Security -> Accessibility, then enable "
        "the app that launches this command, usually Codex, Terminal, or your shell app. "
        "Quit and reopen that app after enabling it."
    )


def require_accessibility_trusted() -> None:
    if not is_accessibility_trusted():
        raise RuntimeError(accessibility_help())


def write_process_output_tail(output: str, path: Path, max_chars: int = 4000) -> None:
    path.write_text(output[-max_chars:], encoding="utf-8")
