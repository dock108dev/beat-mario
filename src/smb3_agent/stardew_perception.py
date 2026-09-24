"""Bounded pixel recognition, with no hidden-state or save-reading fallback.

No qualified Stardew profile ships with B3. A profile needs retained real-screen
calibration and a complete farm coverage proof before it can emit live-qualified
observations. Synthetic templates exercise the algorithm only. Exact region
matches are deliberately brittle: scale, scroll, animation, occlusion, and
unknown HUD values fail closed instead of turning estimates into exact counts.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from smb3_agent.stardew_adapter import (
    CropObservation, PositionObservation, SaveIdentity, ScreenObservation,
    StardewAdapterError, ToolObservation, WindowObservation,
)


def pixel_digest(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    return hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()


@dataclass(frozen=True)
class PixelRegion:
    """An exact crop of retained pixels, mapped to an independently reviewed value."""
    box: tuple[int, int, int, int]
    values: dict[str, Any]

    def recognize(self, image: Image.Image) -> Any:
        x0, y0, x1, y1 = self.box
        if not 0 <= x0 < x1 <= image.width or not 0 <= y0 < y1 <= image.height:
            raise StardewAdapterError("recognition region outside the visible viewport")
        digest = pixel_digest(image.crop(self.box))
        if digest not in self.values:
            raise StardewAdapterError("unrecognized visible pixels; recalibration is required")
        return self.values[digest]


@dataclass(frozen=True)
class WateringPixelProfile:
    profile_id: str
    viewport_size: tuple[int, int]
    # Every tile in the supported complete planted area must match, including empty tiles.
    tiles: dict[tuple[int, int], PixelRegion]
    anchors: tuple[PixelRegion, ...]
    player: PixelRegion
    tool: PixelRegion
    energy: PixelRegion
    can_water: PixelRegion
    can_capacity: int
    energy_maximum: int
    return_tile: tuple[int, int]
    complete_farm_coverage: bool = False
    classification: str = "fixture"
    qualification_evidence: tuple[str, ...] = ()
    # Hashes bind calibration to retained evidence, not a user-entered live toggle.
    qualification_hashes: dict[str, str] = field(default_factory=dict)

    def qualified(self) -> bool:
        if self.classification != "actual_live" or not self.complete_farm_coverage or not self.qualification_evidence:
            return False
        for name in self.qualification_evidence:
            path = Path(name)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != self.qualification_hashes.get(name):
                return False
        return True


class VisibleWateringPerception:
    def __init__(self, profile: WateringPixelProfile | None = None) -> None:
        self.profile = profile
        self.tool_uses = 0
        self.refills = 0
        self._previous: ScreenObservation | None = None

    def recognize(self, screenshot: Path, window: WindowObservation, save: SaveIdentity) -> ScreenObservation:
        profile = self.profile
        if profile is None:
            raise StardewAdapterError("automatic visible perception requires a calibrated complete-farm pixel profile")
        if not window.trusted:
            raise StardewAdapterError("foreground unobscured game window is required")
        with Image.open(screenshot) as source:
            image = source.convert("RGB")
        if image.size != profile.viewport_size:
            raise StardewAdapterError("viewport scale or dimensions changed")
        if not profile.anchors or not profile.tiles:
            raise StardewAdapterError("complete viewport anchors and planted-area coverage are required")
        for anchor in profile.anchors:
            if anchor.recognize(image) is not True:
                raise StardewAdapterError("viewport moved, scrolled, or became occluded")
        crops = []
        for (x, y), region in profile.tiles.items():
            state = region.recognize(image)
            if state not in {"empty", "planted_dry", "planted_watered"}:
                raise StardewAdapterError("unknown planted tile state")
            if state != "empty":
                crops.append(CropObservation(f"farm-{x}-{y}", x, y, True,
                                             state == "planted_watered", False, 1.0, str(screenshot)))
        player = profile.player.recognize(image)
        if not isinstance(player, (tuple, list)) or len(player) != 2 or any(type(v) is not int for v in player):
            raise StardewAdapterError("player tile is unknown")
        energy = profile.energy.recognize(image)
        units = profile.can_water.recognize(image)
        selected = profile.tool.recognize(image)
        if type(energy) is not int or type(units) is not int:
            raise StardewAdapterError("exact visible resource numbers are unknown; a bar estimate is insufficient")
        if selected != "watering_can":
            raise StardewAdapterError("equipped watering can is not recognized")
        tool_uses, refills = self.tool_uses, self.refills
        previous = self._previous
        if previous:
            before = {c.crop_id for c in previous.crops if c.watered}
            after = {c.crop_id for c in crops if c.watered}
            newly = after - before
            if newly:
                if len(newly) != 1 or not before.issubset(after) or units != previous.tool.watering_can_units - 1:
                    raise StardewAdapterError("visible water use and target change do not reconcile")
                tool_uses += 1
            elif units != previous.tool.watering_can_units:
                # No refill is inferred merely from a moving water bar.
                raise StardewAdapterError("unreviewed water change; refill recognition is not qualified")
        result = ScreenObservation(
            uuid4().hex, datetime.now(timezone.utc).isoformat(), save.disposable_tree_sha256,
            window, tuple(crops), energy, profile.energy_maximum,
            ToolObservation(selected, units, profile.can_capacity, refills, tool_uses),
            PositionObservation("Farm", *player, tuple(player) == profile.return_tile, 1.0),
            (str(screenshot),), scene_complete=profile.complete_farm_coverage,
            unknown_regions=() if profile.complete_farm_coverage else ("farm extent outside viewport not qualified",),
            session_nonce=save.nonce,
            perception_classification="automatic_live" if profile.qualified() else "pixel_fixture_unqualified",
        )
        # Do not carry counters across sessions or failed observations.
        if previous and previous.session_nonce != save.nonce:
            raise StardewAdapterError("perception session changed; construct fresh perception after reset")
        result.validate(save.disposable_tree_sha256)
        self.tool_uses, self.refills, self._previous = tool_uses, refills, result
        return result


@dataclass(frozen=True)
class MaskedPixelTemplate:
    """Stable visible feature pixels; transparent pixels are explicitly unexamined.

    Masks help exclude unrelated animation/cursors, never turn unexamined crops
    into coverage. Template labels are calibration annotations, not live proof.
    """
    value: Any
    size: tuple[int, int]
    rgb: bytes
    mask: bytes

    @classmethod
    def from_image(cls, image: Image.Image, value: Any) -> MaskedPixelTemplate:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        if any(a not in {0, 255} for a in alpha.tobytes()):
            raise StardewAdapterError("template masks must be binary, not approximate transparency")
        if sum(a == 255 for a in alpha.tobytes()) < 16:
            raise StardewAdapterError("template requires at least 16 explicitly examined feature pixels")
        return cls(value, rgba.size, rgba.convert("RGB").tobytes(), alpha.tobytes())

    def matches(self, image: Image.Image) -> bool:
        if image.size != self.size:
            return False
        raw = image.convert("RGB").tobytes()
        return all(not included or raw[index*3:index*3+3] == self.rgb[index*3:index*3+3]
                   for index, included in enumerate(self.mask))


@dataclass(frozen=True)
class MaskedTemplateRegion:
    box: tuple[int, int, int, int]
    templates: tuple[MaskedPixelTemplate, ...]

    def recognize(self, image: Image.Image) -> Any:
        x0, y0, x1, y1 = self.box
        if not 0 <= x0 < x1 <= image.width or not 0 <= y0 < y1 <= image.height:
            raise StardewAdapterError("masked region outside the visible viewport")
        region = image.crop(self.box)
        matches = [template.value for template in self.templates if template.matches(region)]
        if not matches:
            raise StardewAdapterError("visible feature pixels are unrecognized or occluded")
        if any(value != matches[0] for value in matches):
            raise StardewAdapterError("visible feature match is ambiguous between calibrated states")
        return matches[0]


@dataclass(frozen=True)
class ExactGlyph:
    character: str
    size: tuple[int, int]
    mask: bytes

    @classmethod
    def calibrate(cls, character: str, image: Image.Image,
                  foreground_colors: tuple[tuple[int, int, int], ...]) -> ExactGlyph:
        if character not in "0123456789/-" or len(character) != 1:
            raise StardewAdapterError("numeric HUD calibration permits only digits, slash, and minus")
        binary = _foreground_mask(image, foreground_colors)
        box = binary.getbbox()
        if box is None:
            raise StardewAdapterError("numeric glyph calibration has no visible foreground")
        cropped = binary.crop(box)
        return cls(character, cropped.size, cropped.tobytes())


def _foreground_mask(image: Image.Image, colors: tuple[tuple[int, int, int], ...]) -> Image.Image:
    if not colors:
        raise StardewAdapterError("numeric HUD foreground palette is not calibrated")
    palette = set(colors)
    rgb = image.convert("RGB")
    # Exact game-font palette; no threshold, OCR-language guess, or interpolation.
    return Image.frombytes("L", rgb.size, bytes(255 if color in palette else 0 for color in zip(*(iter(rgb.tobytes()),) * 3)))


@dataclass(frozen=True)
class NumericHudRegion:
    """Exact calibrated glyph OCR for a visible integer or current/maximum tooltip.

    This reads displayed integers, not hidden fractional resource state. A live
    profile must independently establish that integer accounting is valid for its
    supported conditions; rounded numbers never prove an exact fractional value.
    """
    box: tuple[int, int, int, int]
    foreground_colors: tuple[tuple[int, int, int], ...]
    glyphs: tuple[ExactGlyph, ...]
    expected_maximum: int | None = None
    maximum_characters: int = 9

    def recognize_text(self, image: Image.Image) -> str:
        x0, y0, x1, y1 = self.box
        if not 0 <= x0 < x1 <= image.width or not 0 <= y0 < y1 <= image.height:
            raise StardewAdapterError("numeric HUD region outside the viewport")
        mask = _foreground_mask(image.crop(self.box), self.foreground_colors)
        bounds = mask.getbbox()
        if bounds is None:
            raise StardewAdapterError("numeric resource tooltip is not visibly present")
        mask = mask.crop(bounds)
        runs = []
        start = None
        for column in range(mask.width + 1):
            occupied = column < mask.width and mask.crop((column, 0, column+1, mask.height)).getbbox() is not None
            if occupied and start is None:
                start = column
            elif not occupied and start is not None:
                runs.append((start, column))
                start = None
        if not 1 <= len(runs) <= self.maximum_characters:
            raise StardewAdapterError("numeric resource text length is unsupported")
        result = []
        for left, right in runs:
            part = mask.crop((left, 0, right, mask.height))
            part = part.crop(part.getbbox())
            matches = {glyph.character for glyph in self.glyphs
                       if glyph.size == part.size and glyph.mask == part.tobytes()}
            if len(matches) != 1:
                raise StardewAdapterError("numeric resource glyph is unknown or ambiguous")
            result.append(next(iter(matches)))
        return "".join(result)

    def recognize(self, image: Image.Image) -> int:
        text = self.recognize_text(image)
        if self.expected_maximum is not None:
            pieces = text.split("/")
            if len(pieces) != 2 or not all(piece.isdecimal() for piece in pieces):
                raise StardewAdapterError("expected visible current/maximum numeric tooltip")
            value, maximum = map(int, pieces)
            if maximum != self.expected_maximum or not 0 <= value <= maximum:
                raise StardewAdapterError("numeric resource maximum changed or value is out of range")
            return value
        if not text.isdecimal():
            raise StardewAdapterError("resource must be a nonnegative displayed integer")
        return int(text)


@dataclass(frozen=True)
class CalibratedBarRegion:
    """Decode only uniquely calibrated fill lengths; preserve aliased counts.

    A proportional bar is not an exact counter by default. Two distinct unit
    counts that produce the same visible length stay ambiguous, even when a
    caller wants a particular answer. Every used length needs retained visual
    calibration in the surrounding profile qualification evidence.
    """
    box: tuple[int, int, int, int]
    filled_colors: tuple[tuple[int, int, int], ...]
    empty_colors: tuple[tuple[int, int, int], ...]
    units_by_filled_pixels: dict[int, tuple[int, ...]]
    orientation: str = "horizontal"

    def recognize(self, image: Image.Image) -> int:
        x0, y0, x1, y1 = self.box
        if not 0 <= x0 < x1 <= image.width or not 0 <= y0 < y1 <= image.height:
            raise StardewAdapterError("resource bar outside the visible viewport")
        if self.orientation not in {"horizontal", "vertical"}:
            raise StardewAdapterError("unsupported resource-bar orientation")
        filled, empty = set(self.filled_colors), set(self.empty_colors)
        if not filled or not empty or filled & empty:
            raise StardewAdapterError("resource-bar palettes must be known and disjoint")
        patch = image.crop(self.box).convert("RGB")
        states = []
        extent = patch.width if self.orientation == "horizontal" else patch.height
        for index in range(extent):
            line = (patch.crop((index, 0, index+1, patch.height)) if self.orientation == "horizontal"
                    else patch.crop((0, patch.height-index-1, patch.width, patch.height-index)))
            colors = set(zip(*(iter(line.tobytes()),) * 3))
            if colors <= filled:
                states.append(True)
            elif colors <= empty:
                states.append(False)
            else:
                raise StardewAdapterError("resource bar contains unknown, mixed, or occluded pixels")
        count = sum(states)
        if states != [True] * count + [False] * (extent-count):
            raise StardewAdapterError("resource bar fill is not contiguous")
        units = set(self.units_by_filled_pixels.get(count, ()))
        if len(units) != 1:
            raise StardewAdapterError("visible resource bar does not uniquely establish exact units")
        value = next(iter(units))
        if type(value) is not int or value < 0:
            raise StardewAdapterError("invalid calibrated resource units")
        return value


def retain_region_calibration(destination: Path, *, box: tuple[int, int, int, int],
                              samples: tuple[tuple[Path, Any], ...],
                              examined_boxes: tuple[tuple[int, int, int, int], ...] = ()) -> MaskedTemplateRegion:
    """Retain supplied screenshot crops and annotations; never issue qualification.

    Examined boxes are relative to the cropped region. Omitting them examines the
    entire region. Output is a reviewable calibration artifact, always explicitly
    unqualified; a source screenshot label alone never proves live recognition.
    """
    import json
    from PIL import ImageDraw
    if not samples:
        raise StardewAdapterError("calibration requires retained screenshot samples")
    if destination.exists():
        raise StardewAdapterError("calibration destination already exists; preserve previous attempts")
    destination.mkdir(parents=True)
    templates, records = [], []
    for index, (path, value) in enumerate(samples):
        with Image.open(path) as image:
            if not 0 <= box[0] < box[2] <= image.width or not 0 <= box[1] < box[3] <= image.height:
                raise StardewAdapterError("calibration region is outside retained screenshot")
            region = image.crop(box).convert("RGBA")
        if examined_boxes:
            alpha = Image.new("L", region.size, 0)
            draw = ImageDraw.Draw(alpha)
            for left, top, right, bottom in examined_boxes:
                if not 0 <= left < right <= region.width or not 0 <= top < bottom <= region.height:
                    raise StardewAdapterError("calibration mask outside region")
                draw.rectangle((left, top, right-1, bottom-1), fill=255)
            region.putalpha(alpha)
        template = MaskedPixelTemplate.from_image(region, value)
        target = destination / f"sample-{index:03d}.png"
        region.save(target)
        templates.append(template)
        records.append({"source": str(path.resolve()), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "template": target.name, "template_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        "annotated_value": value})
    manifest = {"schema": "stardew-visible-region-calibration/v1", "classification": "manual_calibration_unqualified",
                "box": box, "examined_boxes": examined_boxes, "samples": records,
                "automatic_live_qualified": False, "complete_farm_coverage": False}
    (destination / "calibration.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return MaskedTemplateRegion(box, tuple(templates))
