"""Selected-window pixels and independent text sensors; no game-state access."""
from __future__ import annotations

import hashlib
import csv
import io
import math
import os
import sys
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from smb3_agent.host_contracts import WindowObservation
from smb3_agent.native_host import foreground_process_id, capture_selected


class ScreenHostError(ValueError):
    pass


@dataclass(frozen=True)
class TextRegion:
    text: str
    box: tuple[float, float, float, float]  # normalized left/top/width/height
    confidence: float


@dataclass(frozen=True)
class Frame:
    frame_id: str
    captured_at: float  # monotonic capture START, not completion
    window: WindowObservation
    path: Path
    sha256: str
    text: tuple[TextRegion, ...]

    def require_fresh(self, window: WindowObservation, max_age: float, *, require_foreground=True) -> None:
        if not (window.trusted if require_foreground else window.observable) or window != self.window:
            raise ScreenHostError("Selected window, geometry or focus changed")
        age = time.monotonic() - self.captured_at
        if not 0 <= age <= max_age:
            raise ScreenHostError("Stale or invalid capture timestamp")
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != self.sha256:
            raise ScreenHostError("Retained frame changed")


class MacSelectedWindowHost:
    """Reuse the qualified native capture and input window contract.

    Selection is an explicit PID/start/window triple, never a fuzzy title match.
    No existing Mario or Stardew backend changes behavior.
    """

    def __init__(self, process_id: int, process_started_at: str, window_id: str, *, background_observation=False, ocr_regions=()):
        self.expected_process_id, self.expected_process_started_at = process_id, process_started_at
        self.window_id = window_id
        self.background_observation = background_observation
        self.ocr_regions = tuple(ocr_regions)
        self.last_timing = {}

    def detect_window(self, *, require_foreground: bool = True) -> WindowObservation:
        import Quartz as q
        records = q.CGWindowListCopyWindowInfo(
            q.kCGWindowListOptionOnScreenOnly | q.kCGWindowListExcludeDesktopElements,
            q.kCGNullWindowID) or ()
        selected = [r for r in records if str(r.get(q.kCGWindowNumber)) == self.window_id
                    and r.get(q.kCGWindowOwnerPID) == self.expected_process_id
                    and r.get(q.kCGWindowLayer) == 0 and r.get(q.kCGWindowAlpha, 0) > 0]
        if len(selected) != 1:
            raise ScreenHostError("Selected process/window unavailable")
        r = selected[0]
        b = r[q.kCGWindowBounds]
        bounds = tuple(int(b[k]) for k in ("X", "Y", "Width", "Height"))
        started = subprocess.run(["ps", "-p", str(self.expected_process_id), "-o", "lstart="],
                                 capture_output=True, text=True, timeout=1, check=True).stdout.strip()
        if started != self.expected_process_started_at:
            raise ScreenHostError("Selected process restarted")
        # Refuse any overlapping foreground layer-zero window ahead of this one.
        occluded = False
        for other in records:
            if other.get(q.kCGWindowNumber) == r[q.kCGWindowNumber]:
                break
            if other.get(q.kCGWindowLayer) != 0 or other.get(q.kCGWindowAlpha, 0) <= 0:
                continue
            ob = other.get(q.kCGWindowBounds, {})
            x, y, w, h = bounds
            # macOS native traffic lights can be separate layer-zero windows.
            # Only the selected process's chrome wholly inside its title bar
            # is excluded. Other windows and all content overlap still refuse.
            if (other.get(q.kCGWindowOwnerPID) == self.expected_process_id
                    and ob.get("Width", 0) > 0 and ob.get("Height", 0) > 0
                    and x <= ob.get("X", 0) and y <= ob.get("Y", 0)
                    and ob.get("X", 0)+ob["Width"] <= x+w
                    and ob.get("Y", 0)+ob["Height"] <= y+32):
                continue
            if (ob.get("X", 0) < x+w and ob.get("Y", 0) < y+h
                    and ob.get("X", 0)+ob.get("Width", 0) > x
                    and ob.get("Y", 0)+ob.get("Height", 0) > y):
                occluded = True
        window = WindowObservation(self.expected_process_id, started, self.window_id,
                                   str(r.get(q.kCGWindowName, "selected game")), bounds,
                                   True, True, foreground_process_id() == self.expected_process_id,
                                   occluded)
        if occluded or (require_foreground and not window.trusted):
            raise ScreenHostError("Selected game must be foreground and unobscured")
        return window

    def capture(self, window, destination, *, require_foreground=True):
        return capture_selected(window, destination,
            detect_window=lambda: self.detect_window(require_foreground=require_foreground),
            require_foreground=require_foreground, error_type=ScreenHostError)

    def activate(self):
        # Called only after explicit Start, never by observation or chat.
        self.detect_window(require_foreground=False)
        import AppKit
        app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(self.expected_process_id)
        if app is None or not app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps):
            raise ScreenHostError("Selected game could not receive focus")
        deadline = time.monotonic()+1
        while foreground_process_id() != self.expected_process_id and time.monotonic() < deadline:
            time.sleep(.01)
        return self.detect_window()

    @staticmethod
    def permissions():
        import Quartz as q
        return {"capture": bool(q.CGPreflightScreenCaptureAccess()),
                "input": bool(q.CGPreflightPostEventAccess())}

    def observe(self, root: Path, *, execution=False) -> Frame:
        foreground = execution or not self.background_observation
        window = self.detect_window(require_foreground=foreground)
        at = time.monotonic()
        identity = uuid4().hex
        path = self.capture(window, root / (identity + ".png"), require_foreground=foreground)
        capture_seconds = time.monotonic()-at
        grounded_at = time.monotonic()
        text = recognize_text(path, regions=self.ocr_regions)
        self.last_timing = {"capture_seconds": capture_seconds, "grounding_seconds": time.monotonic()-grounded_at}
        return Frame(identity, at, window, path, hashlib.sha256(path.read_bytes()).hexdigest(),
                     text)


def recognize_text(path: Path, *, regions=()) -> tuple[TextRegion, ...]:
    """Local OCR over declared rectangles, with original-window coordinates.

    Individual rectangles avoid joining unrelated HUD rows or button borders.
    All passes share a 1.5-second budget; freshness is checked after grounding.
    """
    from PIL import Image
    from smb3_agent.game_profiles import valid_box
    if len(regions) > 32 or not all(valid_box(box) for box in regions):
        raise ScreenHostError("Invalid declared OCR regions")
    binary = str(Path(sys._MEIPASS)/"ocr/tesseract") if getattr(sys, "frozen", False) else "tesseract"
    ocr_env = dict(os.environ)
    if getattr(sys, "frozen", False):
        ocr_env["TESSDATA_PREFIX"] = str(Path(sys._MEIPASS)/"ocr/tessdata")
    deadline = time.monotonic() + 1.5
    output_bytes = 0
    found = []
    with Image.open(path) as original, tempfile.TemporaryDirectory() as root:
        width, height = original.size
        for index, box in enumerate(regions or ((0, 0, 1, 1),)):
            ox, oy = math.floor(box[0]*width), math.floor(box[1]*height)
            right, bottom = math.ceil((box[0]+box[2])*width), math.ceil((box[1]+box[3])*height)
            image = original.crop((ox, oy, right, bottom))
            scaled = image.resize((image.width*2, image.height*2))
            bright = image.convert("L").point(lambda v: 0 if v > 210 else 255).resize(scaled.size)
            for pass_id, pixels in enumerate((scaled, bright)):
                image_path = Path(root) / f"{index}-{pass_id}.png"
                pixels.save(image_path)
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise ScreenHostError("Local OCR deadline exceeded")
                try:
                    result = subprocess.run([binary, str(image_path), "stdout", "--psm", "11",
                        "-c", "tessedit_create_tsv=1"], capture_output=True, text=True,
                        timeout=min(1, remaining), check=True, env=ocr_env)
                except (OSError, subprocess.SubprocessError) as exc:
                    raise ScreenHostError("Local OCR unavailable or deadline exceeded") from exc
                output_bytes += len(result.stdout)
                if output_bytes > 1_000_000:
                    raise ScreenHostError("OCR result budget exceeded")
                reader = csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
                columns = {"level", "text", "conf", "left", "top", "width", "height", "block_num", "par_num", "line_num"}
                if not columns <= set(reader.fieldnames or ()):
                    raise ScreenHostError("Local OCR returned an unsupported text format")
                groups = {}
                for row in reader:
                    if row["level"] == "5" and row["text"].strip():
                        groups.setdefault((row["block_num"], row["par_num"], row["line_num"]), []).append(row)
                for rows in groups.values():
                    left, top = min(int(r["left"]) for r in rows), min(int(r["top"]) for r in rows)
                    right = max(int(r["left"])+int(r["width"]) for r in rows)
                    bottom = max(int(r["top"])+int(r["height"]) for r in rows)
                    region = TextRegion(" ".join(r["text"] for r in rows),
                        ((left/2+ox)/width, (top/2+oy)/height, (right-left)/(width*2), (bottom-top)/(height*2)),
                        min(float(r["conf"]) for r in rows)/100)
                    duplicates = [r for r in found if r.text == region.text
                        and all(abs(a-b) <= .004 for a, b in zip(r.box, region.box))]
                    if duplicates:
                        previous = duplicates[0]
                        found[found.index(previous)] = max(previous, region, key=lambda r: r.confidence)
                    else:
                        found.append(region)
    return tuple(found)


def profile_ocr_regions(profile):
    """Read context around numbers; eligibility still uses their original bounds."""
    width, height = profile.viewport
    result = []
    for sensor in profile.sensors:
        x, y, w, h = sensor.region
        left, top = max(0, x-12/width), max(0, y-12/height)
        right, bottom = min(1, x+w+12/width), min(1, y+h)
        result.append((left, top, right-left, bottom-top))
    result.extend(skill.observation_region or skill.target_region for skill in profile.skills)
    return tuple(result)
