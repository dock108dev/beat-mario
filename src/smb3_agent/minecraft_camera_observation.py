"""Declared vanilla 26.3 debug-HUD detector; camera facts come only from pixels.

The installed static font atlas supplies glyph shapes, never gameplay state.
Exact glyph/grammar/cardinal checks reject ambiguity instead of correcting OCR.
"""

from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import time
from zipfile import ZipFile

import numpy as np
from PIL import Image

from smb3_agent.feedback_contracts import (
    FeedbackError,
    FeedbackFrame,
    ReadingState,
    ViewObservation,
    WindowBinding,
)

FONT_SHA256 = "e8646f1ed1f4bfd597d262cca3d8fac88ceaaa62807bbd5e607b2e3fe41c928a"
DETECTOR_VERSION = "minecraft-26.3-visible-facing-glyphs/v2"


@dataclass(frozen=True)
class VisibleOrientation:
    heading: float
    pitch: float
    cardinal: str
    text: str
    fps: int | None


class FacingGlyphDetector:
    def __init__(self, atlas: bytes):
        if hashlib.sha256(atlas).hexdigest() != FONT_SHA256:
            raise FeedbackError("Declared vanilla font atlas changed")
        with Image.open(io.BytesIO(atlas)) as image:
            self.font = np.asarray(image.convert("RGBA"))[:, :, 3] > 0
        self.scale = 2  # declared native Retina debug-font scale; other scales refuse
        self.glyphs = {}
        for code in range(33, 127):
            glyph = self.font[
                code // 16 * 8 : (code // 16 + 1) * 8,
                code % 16 * 8 : (code % 16 + 1) * 8,
            ]
            columns = np.flatnonzero(glyph.any(axis=0))
            if not len(columns):
                continue
            width = columns[-1] + 1
            padded = np.pad(glyph[:, :width], ((0, 0), (0, 1)))
            self.glyphs[chr(code)] = np.repeat(np.repeat(padded, 2, axis=0), 2, axis=1)
        self.glyphs[" "] = np.zeros((16, 8), dtype=bool)

    @classmethod
    def installed(cls):
        jar = (
            Path.home() / "Library/Application Support/minecraft/versions/26.3/26.3.jar"
        )
        with ZipFile(jar) as archive:
            return cls(archive.read("assets/minecraft/textures/font/ascii.png"))

    def render(self, text):
        return np.concatenate([self.glyphs[c] for c in text], axis=1)

    def literal(self, row, x, text):
        template = self.render(text)
        if x + template.shape[1] > row.shape[1] or not np.array_equal(
            row[:, x : x + template.shape[1]], template
        ):
            raise FeedbackError("Visible HUD glyph/grammar mismatch")
        return x + template.shape[1]

    def number(self, row, x, *, integer=False):
        value = ""
        for _ in range(7):
            matches = []
            for char in "0123456789" if integer else "-0123456789.":
                g = self.glyphs[char]
                if x + g.shape[1] <= row.shape[1] and np.array_equal(
                    row[:, x : x + g.shape[1]], g
                ):
                    matches.append(char)
            if not matches:
                break
            if len(matches) != 1:
                raise FeedbackError("Ambiguous visible numeric glyph")
            char = matches[0]
            value += char
            x += self.glyphs[char].shape[1]
        import re

        pattern = r"[0-9]{1,3}" if integer else r"-?[0-9]{1,3}\.[0-9]"
        if not re.fullmatch(pattern, value):
            raise FeedbackError("Malformed visible numeric HUD reading")
        return (int(value) if integer else float(value)), x, value

    def read(self, path):
        with Image.open(path) as image:
            if image.size != (1708, 1016):
                raise FeedbackError("Unqualified native viewport/debug-font scale")
            rgb = np.asarray(image.convert("RGB"))
        mask = (rgb.min(axis=2) > 200) & (rgb.max(axis=2) - rgb.min(axis=2) < 5)
        prefix = self.render("Facing: ")
        matches = []
        # Only the declared left HUD region; no other window or hidden state.
        for y in range(90, 420):
            row = mask[y : y + 16]
            for x in np.flatnonzero(np.all(row.T == prefix[:, 0], axis=1)):
                if np.array_equal(row[:, x : x + prefix.shape[1]], prefix):
                    matches.append((row, int(x)))
        if len(matches) != 1:
            raise FeedbackError("Facing HUD unavailable, occluded or ambiguous")
        row, left = matches[0]
        x = left + prefix.shape[1]
        cardinals = {
            "south": "positive Z",
            "west": "negative X",
            "north": "negative Z",
            "east": "positive X",
        }
        cards = [
            c
            for c in cardinals
            if np.array_equal(row[:, x : x + self.render(c).shape[1]], self.render(c))
        ]
        if len(cards) != 1:
            raise FeedbackError("Cardinal HUD unavailable")
        cardinal = cards[0]
        lead = cardinal + " (Towards " + cardinals[cardinal] + ") ("
        x = self.literal(row, x, lead)
        heading, x, htext = self.number(row, x)
        x = self.literal(row, x, " / ")
        pitch, x, ptext = self.number(row, x)
        self.literal(row, x, ")")
        if not -180 <= heading <= 180 or not -90 <= pitch <= 90:
            raise FeedbackError("Visible camera angle outside declared bounds")
        # The displayed one-decimal heading loses up to .05 degrees. At a
        # cardinal boundary, either adjacent direction can therefore agree
        # with the pixels. Other directions remain contradictory.
        possible = {
            ("south", "west", "north", "east")[
                int(((heading + offset + 45) % 360) // 90)
            ]
            for offset in (-0.05, 0, 0.05)
        }
        if cardinal not in possible:
            raise FeedbackError("Contradictory heading/cardinal HUD evidence")
        fps = None
        # FPS is visible performance evidence, separately from capture cadence.
        row = mask[60:76, :600]
        try:
            fps, x, _ = self.number(row, 4, integer=True)
            self.literal(row, x, " fps")
        except FeedbackError:
            fps = None
        return VisibleOrientation(
            heading,
            pitch,
            cardinal,
            "Facing: " + lead + htext + " / " + ptext + ")",
            fps,
        )


class MinecraftCameraObserver:
    def __init__(self, host, environment, calibration_id, root):
        self.host, self.environment, self.calibration_id = (
            host,
            environment,
            calibration_id,
        )
        self.root = Path(root)
        self.detector = FacingGlyphDetector.installed()
        self.last_timing = {}
        self.last_visible = None

    def observe(self, *, execution=False):
        import Quartz as q

        from smb3_agent.minecraft_capture import capture_frame

        started = time.monotonic()
        frame, native_size, native_provenance = capture_frame(
            self.host, self.root, execution=execution
        )
        window, path = frame.window, frame.path
        captured = time.monotonic()
        binding = WindowBinding(
            window.process_id,
            window.process_started_at,
            window.window_id,
            window.bounds,
            native_size,
        )
        feedback = FeedbackFrame.from_frame(
            frame, binding, self.environment.sha256, self.calibration_id
        )
        state, heading, pitch, reason = ReadingState.UNAVAILABLE, None, None, ""
        captured_mouse = bool(window.foreground and not q.CGCursorIsVisible())
        try:
            visible = self.detector.read(path)
            if (
                visible.fps is None
                or not self.environment.fps_range[0]
                <= visible.fps
                <= self.environment.fps_range[1]
            ):
                raise FeedbackError(
                    "Visible frame rate outside declared performance envelope"
                )
            if not captured_mouse:
                raise FeedbackError(
                    "Native cursor is visible or selected game lacks focus"
                )
            self.last_visible = visible
            heading, pitch, state = (
                visible.heading,
                visible.pitch,
                ReadingState.OBSERVED,
            )
        except FeedbackError as exc:
            self.last_visible = None
            reason = str(exc)
        grounded = time.monotonic()
        self.last_timing = {
            "capture_seconds": captured - started,
            "grounding_seconds": grounded - captured,
            "frame_age_seconds": grounded - started,
        }
        return ViewObservation(
            feedback,
            state,
            heading,
            pitch,
            0.05,
            DETECTOR_VERSION,
            (str(path), "installed-static-font:" + FONT_SHA256) + native_provenance,
            grounded,
            state is ReadingState.OBSERVED,
            captured_mouse,
            reason,
        )
