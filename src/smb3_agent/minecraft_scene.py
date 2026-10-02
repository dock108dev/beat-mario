"""Visible Minecraft scene evidence and conservative line-of-sight cell inspection.

No world files, commands, process memory or model guesses supply gameplay facts.
A targeted full cube establishes its cell, and a ray ending at that cube can
establish empty cells strictly before it. Missing targets establish nothing.
"""

from dataclasses import dataclass
import math
import hashlib
from pathlib import Path
import re

import numpy as np
from PIL import Image

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.minecraft_camera_observation import FacingGlyphDetector
from smb3_agent.minecraft_skills import visible_spatial

FULL_CUBES = frozenset(
    {
        "minecraft:stone",
        "minecraft:bricks",
        "minecraft:oak_planks",
        "minecraft:cobblestone",
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:bedrock",
    }
)
SCENE_VERSION = "minecraft-visible-scene/v1"


class HudGlyphDetector(FacingGlyphDetector):
    """Decode exact static-font rows; ambiguity is refused, never corrected."""

    def row_text(self, row, x):
        # Different-width glyphs can share prefixes. Explore all exact matches
        # rather than taking the first one; accept only a unique complete row.
        stack, answers, visited = [(x, "")], set(), set()
        while stack:
            pos, text = stack.pop()
            if len(visited) > 4096:
                raise FeedbackError("HUD glyph decoding is ambiguous")
            if (pos, text) in visited:
                continue
            visited.add((pos, text))
            if not row[:, pos:].any():
                answers.add(text.rstrip())
                if len(answers) > 1:
                    raise FeedbackError("HUD row has ambiguous glyphs")
                continue
            if len(text) >= 160:
                continue
            for char, glyph in self.glyphs.items():
                end = pos + glyph.shape[1]
                if end <= row.shape[1] and np.array_equal(row[:, pos:end], glyph):
                    stack.append((end, text + char))
        if len(answers) != 1:
            raise FeedbackError("HUD row has unrecognized glyphs")
        return answers.pop()

    def spatial_rows(self, path):
        with Image.open(path) as image:
            if image.size != (1708, 1016):
                raise FeedbackError("Restore the supported window and capture scale")
            rgb = np.asarray(image.convert("RGB"))
        mask = (rgb.min(axis=2) > 200) & (rgb.max(axis=2) - rgb.min(axis=2) < 5)
        found = []
        for y in range(58, 750):
            row = mask[y : y + 16]
            for prefix in ("XYZ: ", "Targeted Block: ", "minecraft:"):
                glyph = self.render(prefix)
                # XYZ is always left-aligned. Target rows are right HUD aligned.
                candidates = np.flatnonzero(np.all(row.T == glyph[:, 0], axis=1))
                for x in candidates:
                    if x + glyph.shape[1] > row.shape[1]:
                        continue
                    if np.array_equal(row[:, x : x + glyph.shape[1]], glyph):
                        try:
                            text = self.row_text(
                                row[:, :854] if x < 854 else row, int(x)
                            )
                        except FeedbackError:
                            continue
                        if prefix != "minecraft:" or re.fullmatch(
                            r"minecraft:[a-z_]+", text
                        ):
                            found.append((y, int(x), text))
                        break
        # The left dimension row includes other suffixes and is not block identity.
        ordered = sorted(set(found))
        targets = [
            (y, x) for y, x, text in ordered if text.startswith("Targeted Block: ")
        ]
        return [
            text
            for y, x, text in ordered
            if not text.startswith("minecraft:")
            or any(x == tx and 0 < y - ty <= 20 for ty, tx in targets)
        ]


def ray_interval(position, heading, pitch, cell):
    h, p = math.radians(heading), math.radians(pitch)
    eye = (position[0], position[1] + 1.62, position[2])
    ray = (-math.sin(h) * math.cos(p), -math.sin(p), math.cos(h) * math.cos(p))
    near, far = -math.inf, math.inf
    for i in range(3):
        if abs(ray[i]) < 1e-9:
            # Boundary rays cannot establish a unique cell.
            if not cell[i] + 0.01 < eye[i] < cell[i] + 0.99:
                return None
            continue
        a, b = (cell[i] - eye[i]) / ray[i], (cell[i] + 1 - eye[i]) / ray[i]
        near, far = max(near, min(a, b)), min(far, max(a, b))
    return (max(0, near), far) if far - max(0, near) > 0.04 else None


@dataclass(frozen=True)
class CellEvidence:
    cell: tuple[int, int, int]
    material: str | None  # None = inspected air; absence from ledger = unknown
    captured_at: float
    source: str
    window_identity: tuple
    settings: str


class VisibleCellLedger:
    def __init__(self, binding, settings):
        self.binding, self.settings = binding, settings
        self.cells = {}

    def inspect(self, observation, requested, now):
        if (
            observation.window_identity != self.binding
            or observation.settings != self.settings
            or not 0 <= now - observation.captured_at <= 0.8
            or not observation.source
        ):
            raise FeedbackError("Cell inspection needs fresh selected-window evidence")
        if (
            observation.target is None
            or observation.block not in FULL_CUBES
            or observation.face is None
        ):
            return []  # No hidden inference from sky, distant ground or partial blocks.
        target = ray_interval(
            observation.position,
            observation.heading,
            observation.pitch,
            observation.target,
        )
        if target is None:
            return []
        accepted = []
        for raw in requested:
            cell = tuple(raw)
            material = observation.block if cell == observation.target else None
            if cell != observation.target:
                hit = ray_interval(
                    observation.position, observation.heading, observation.pitch, cell
                )
                if hit is None or not 0 < hit[0] < hit[1] <= target[0] + 1e-7:
                    continue
            evidence = CellEvidence(
                cell,
                material,
                observation.captured_at,
                observation.source,
                self.binding,
                self.settings,
            )
            previous = self.cells.get(cell)
            if previous and previous.captured_at >= evidence.captured_at:
                raise FeedbackError("Reused or out-of-order cell inspection")
            self.cells[cell] = evidence
            accepted.append(evidence)
        return accepted

    def invalidate(self, cells):
        for cell in cells:
            self.cells.pop(tuple(cell), None)

    def flat_path(self, start, finish, *, now, maximum_age=2):
        """Require inspected full-cube floor and inspected air across swept body.

        Includes width and both body cells; a single ground ray is insufficient.
        Evidence is invalidated by the executor for every affected addition.
        """
        if abs(start[1] - round(start[1])) > 0.02 or abs(finish[1] - start[1]) > 0.01:
            return False
        required_floor, required_air = set(), set()
        for t in np.linspace(0, 1, 11):
            x, z = (
                start[0] + t * (finish[0] - start[0]),
                start[2] + t * (finish[2] - start[2]),
            )
            for dx in (-0.3, 0.3):
                for dz in (-0.3, 0.3):
                    cell = (math.floor(x + dx), round(start[1]), math.floor(z + dz))
                    required_floor.add((cell[0], cell[1] - 1, cell[2]))
                    required_air.update((cell, (cell[0], cell[1] + 1, cell[2])))

        def fresh(cell):
            e = self.cells.get(cell)
            return e if e and 0 <= now - e.captured_at <= maximum_age else None

        return all(
            (e := fresh(c)) and e.material in FULL_CUBES for c in required_floor
        ) and all((e := fresh(c)) and e.material is None for c in required_air)


def observed_spatial(path, *, view, detector, now):
    """Bind decoded pixels to the current camera frame; missing facts stay unknown.

    Creative/material/path facts are deliberately not accepted as caller booleans
    or strings. Native scene integration must supply independently detected facts.
    """
    view.require(now, 0.8, 0.1)
    path = Path(path)
    if (
        str(path) != view.frame.evidence_reference
        or hashlib.sha256(path.read_bytes()).hexdigest() != view.frame.sha256
    ):
        raise FeedbackError("Spatial pixels do not match the retained camera frame")
    b = view.frame.binding
    return visible_spatial(
        detector.spatial_rows(path),
        captured_at=view.frame.captured_at,
        window_identity=(b.process_id, b.process_started_at, b.window_id, b.bounds),
        settings=view.frame.settings_sha256,
        orientation=view,
        source=f"{SCENE_VERSION}:{view.frame.frame_id}:{view.frame.sha256}",
    )


@dataclass(frozen=True)
class InventoryEvidence:
    """Current visible Creative inventory and material tooltip, never profile data."""

    material: str
    slot: int
    captured_at: float
    source: str
    window_identity: tuple
    settings: str


def inspect_inventory(frame, *, detector, now, settings, pointer, selected_slot):
    """Only the default Creative Items tab and advanced hotbar tooltip qualify.

    The owner opens inventory and hovers the selected hotbar slot during setup.
    Compare the Creative-specific frame against the installed static asset and
    read the rendered tooltip ID. This is read-only; it cannot select an item.
    Other tabs, scales, absent/ambiguous IDs and slot mismatch are unavailable.
    """
    import io
    from zipfile import ZipFile

    if not frame.window.trusted or not 0 <= now - frame.captured_at <= 0.8:
        raise FeedbackError("Inventory inspection needs fresh selected-window pixels")
    path = frame.path
    if hashlib.sha256(path.read_bytes()).hexdigest() != frame.sha256:
        raise FeedbackError("Inventory evidence pixels changed")
    window = frame.window
    window_identity = (
        window.process_id,
        window.process_started_at,
        window.window_id,
        window.bounds,
    )
    if type(selected_slot) is not int or not 0 <= selected_slot < 9:
        raise FeedbackError("Select one hotbar slot in the game")
    with Image.open(path) as image:
        if image.size != (1708, 1016):
            raise FeedbackError("Restore the supported window and capture scale")
        rgb = np.asarray(image.convert("RGB"))
    jar = Path.home() / "Library/Application Support/minecraft/versions/26.3/26.3.jar"
    with ZipFile(jar) as archive:
        asset = np.asarray(
            Image.open(
                io.BytesIO(
                    archive.read(
                        "assets/minecraft/textures/gui/container/creative_inventory/tab_items.png"
                    )
                )
            ).convert("RGBA")
        )
    scale, x, y = creative_inventory_bounds(rgb, asset)
    sx, sy = x + (9 + 18 * selected_slot) * scale, y + 112 * scale
    if not sx <= pointer[0] < sx + 16 * scale or not sy <= pointer[1] < sy + 16 * scale:
        raise FeedbackError("Hover the selected hotbar slot to inspect its material")
    # Inventory labels use GUI scale 2 / Retina 2x, unlike the debug HUD.
    mask = (rgb.min(2) > 60) & (rgb.max(2) - rgb.min(2) < 5)
    ids = set()
    for material in FULL_CUBES:
        glyph = np.repeat(np.repeat(detector.render(material), 2, 0), 2, 1)
        for ty in range(max(56, pointer[1] - 180), min(984, pointer[1] + 100)):
            row = mask[ty : ty + 32]
            left = max(0, pointer[0] - 500)
            right = min(1708 - glyph.shape[1], pointer[0] + 100)
            if row.shape[0] != glyph.shape[0]:
                continue
            candidates = (
                np.flatnonzero(np.all(row[:, left:right].T == glyph[:, 0], axis=1))
                + left
            )
            for tx in candidates:
                end = tx + glyph.shape[1]
                if (
                    np.array_equal(row[:, tx:end], glyph)
                    and not row[:, end : end + 4].any()
                ):
                    ids.add(material)
    if len(ids) != 1:
        raise FeedbackError(
            "Material tooltip is missing or ambiguous; enable advanced tooltips (F3+H)"
        )
    return InventoryEvidence(
        ids.pop(),
        selected_slot,
        frame.captured_at,
        "creative-inventory-pixels:"
        + hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        window_identity,
        settings,
    )


def creative_inventory_bounds(rgb, asset):
    """Default layout, verified against retained native Creative inventory pixels.

    F3 overlaps the top/upper-left edges. Only unobscured opaque frame/separator
    patches are used; tooltip and item contents do not establish mode by themselves.
    """
    scale, x, y = 4, 464, 264
    for left, top, width, height in (
        (0, 42, 1, 92),
        (194, 112, 1, 22),
        (8, 107, 16, 2),
        (2, 134, 20, 1),
    ):
        reference = np.repeat(
            np.repeat(asset[top : top + height, left : left + width], scale, 0),
            scale,
            1,
        )
        actual = rgb[
            y + top * scale : y + (top + height) * scale,
            x + left * scale : x + (left + width) * scale,
        ]
        opaque = reference[:, :, 3] == 255
        if (
            actual.shape != reference[:, :, :3].shape
            or not opaque.any()
            or not np.array_equal(actual[opaque], reference[:, :, :3][opaque])
        ):
            raise FeedbackError(
                "Creative inventory is not visibly verified; open the Building Blocks tab"
            )
    return scale, x, y


def creative_inventory(path):
    import io
    from zipfile import ZipFile

    with Image.open(path) as image:
        if image.size != (1708, 1016):
            raise FeedbackError("Restore the supported window and capture scale")
        rgb = np.asarray(image.convert("RGB"))
    jar = Path.home() / "Library/Application Support/minecraft/versions/26.3/26.3.jar"
    with ZipFile(jar) as archive:
        asset = np.asarray(
            Image.open(
                io.BytesIO(
                    archive.read(
                        "assets/minecraft/textures/gui/container/creative_inventory/tab_items.png"
                    )
                )
            ).convert("RGBA")
        )
    return creative_inventory_bounds(rgb, asset)
