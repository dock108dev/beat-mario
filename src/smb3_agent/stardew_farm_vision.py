"""Camera-aware recognition for one retained, isolated prepared-farm calibration.

Calibration labels describe pixels and supported geometry. Every runtime fact is
re-read from the current frame; missing targets are never silently dropped.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image

from smb3_agent.stardew_adapter import (
    CropObservation,
    PositionObservation,
    ScreenObservation,
    StardewAdapterError,
    ToolObservation,
)
from smb3_agent.stardew_perception import (
    CameraAlignment,
    CalibratedBarRegion,
    ExactGlyph,
    NumericHudRegion,
    _foreground_mask,
)

FILLED = (
    (105, 151, 206),
    (110, 156, 209),
    (111, 158, 211),
    (113, 161, 211),
    (114, 163, 214),
)
EMPTY = (
    (249, 217, 146),
    (247, 209, 138),
    (239, 201, 137),
    (238, 193, 129),
    (220, 176, 119),
)
BAR_BOX = (508, 912, 556, 918)
ENERGY_BOX = (1300, 780, 1445, 817)


def bar_pixels(image):
    return CalibratedBarRegion(
        BAR_BOX, FILLED, EMPTY, {n: (n,) for n in range(49)}
    ).recognize(image)


def glyphs_from_sample(image, text):
    mask = _foreground_mask(image.crop(ENERGY_BOX), ((255, 255, 255),))
    bounds = mask.getbbox()
    if bounds is None:
        raise StardewAdapterError("numeric HUD is not visible in calibration")
    mask = mask.crop(bounds)
    runs, start = [], None
    for x in range(mask.width + 1):
        occupied = (
            x < mask.width
            and mask.crop((x, 0, x + 1, mask.height)).getbbox() is not None
        )
        if occupied and start is None:
            start = x
        elif not occupied and start is not None:
            runs.append((start, x))
            start = None
    if len(runs) != len(text):
        raise StardewAdapterError(
            "resource sample does not match annotated glyph count"
        )
    result = []
    for char, (left, right) in zip(text, runs):
        glyph = mask.crop((left, 0, right, mask.height))
        glyph = glyph.crop(glyph.getbbox())
        result.append(ExactGlyph(char, glyph.size, glyph.tobytes()))
    return result


class PreparedFarmPixelProfile:
    """Explicit local profile; no fixture or browser payload can enable it."""

    viewport_size = (1512, 949)
    energy_maximum = 270
    can_capacity = 40
    complete_farm_coverage = True
    hud_hover = (1480, 792)  # window-local; exposes the actual numerical energy HUD

    def __init__(self, manifest_path: Path):
        self.manifest_path = Path(manifest_path)
        self.manifest_bytes = self.manifest_path.read_bytes()
        self.config = json.loads(self.manifest_bytes)
        if self.config.get("schema") != "prepared-farm-pixel-profile/v1":
            raise StardewAdapterError("unsupported prepared-farm calibration schema")
        self.profile_id = self.config["profile_id"]
        self.classification = self.config.get("classification", "unqualified")
        self.expected = {tuple(p) for p in self.config["expected_tiles"]}
        if len(self.expected) != 15:
            raise StardewAdapterError(
                "prepared farm calibration must retain all 15 targets"
            )
        self.reference = Image.open(self.config["reference"]).convert("RGB")
        self.anchor_box = tuple(self.config["anchor_box"])
        self.origin_reference = tuple(self.config["origin_reference"])
        self.anchor = CameraAlignment.calibrate(self.reference.crop(self.anchor_box))
        self.tool_box = (500, 858, 564, 909)
        self.tool_template = CameraAlignment.calibrate(
            self.reference.crop(self.tool_box)
        ).template
        glyphs, bar = [], {}
        for sample in self.config["resource_samples"]:
            image = Image.open(sample["image"]).convert("RGB")
            glyphs.extend(glyphs_from_sample(image, f"{sample['energy']}/270"))
            bar.setdefault(bar_pixels(image), set()).add(sample["water"])
        self.energy = NumericHudRegion(
            ENERGY_BOX, ((255, 255, 255),), tuple(glyphs), 270
        )
        self.water = CalibratedBarRegion(
            BAR_BOX, FILLED, EMPTY, {k: tuple(v) for k, v in bar.items()}
        )
        self.obstacles = []
        for item in self.config.get("obstacles", []):
            box = tuple(item["reference_box"])
            self.obstacles.append(
                (
                    item["id"],
                    box,
                    CameraAlignment.calibrate(self.reference.crop(box)).template,
                )
            )
        self.last_visible = {}
        self.previous = None
        self.tool_uses = 0

    def qualified(self):
        required = {
            "coverage",
            "positions",
            "resources",
            "tool",
            "obstacles",
            "occlusion",
        }
        if (
            self.classification != "actual_live"
            or set(self.config.get("qualified_roles", ())) != required
            or self.manifest_path.read_bytes() != self.manifest_bytes
        ):
            return False
        evidence = self.config.get("evidence_hashes", {})
        referenced = {self.config["reference"]} | {
            s["image"] for s in self.config["resource_samples"]
        }
        if not referenced <= evidence.keys() or not evidence or not self.obstacles:
            return False
        # Exact units require the observed full-to-empty calibration, not a
        # proportional guess or a counter advanced by emitted input events.
        mapping = self.water.units_by_filled_pixels
        if any(len(set(values)) != 1 for values in mapping.values()) or {
            value for values in mapping.values() for value in values
        } != set(range(41)):
            return False
        qualification = self.config.get("qualification_record")
        if not qualification or qualification not in evidence:
            return False
        return all(
            Path(p).is_file()
            and hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest
            for p, digest in evidence.items()
        )

    def geometry(self, image):
        """Read the camera and player independently of task-specific recognition."""
        if image.size != self.viewport_size:
            raise StardewAdapterError(
                "unsupported viewport; restore the calibrated 75% zoom / 100% UI configuration"
            )
        offsets = self.anchor.offsets(image)
        origins = [
            (
                x + self.origin_reference[0] - self.anchor_box[0],
                y + self.origin_reference[1] - self.anchor_box[1],
            )
            for x, y in offsets
        ]
        ox, oy = [
            (min(p[j] for p in origins) + max(p[j] for p in origins)) / 2
            for j in (0, 1)
        ]
        uncertainty = (
            max(max(p[j] for p in origins) - min(p[j] for p in origins) for j in (0, 1))
            / 2
            + 1.5
        )
        if uncertainty > 3:
            raise StardewAdapterError("camera offset interval is too wide")
        pixels = np.asarray(image)
        ys, xs = np.where(np.all(pixels[:840] == (43, 66, 146), axis=2))
        if not 16 <= len(xs) <= 200 or np.ptp(xs) > 35 or np.ptp(ys) > 25:
            raise StardewAdapterError("player pants are ambiguous or absent")
        by, bx = np.where(
            np.all(
                pixels[ys.max() : ys.max() + 22, xs.min() - 5 : xs.max() + 6]
                == (62, 25, 5),
                axis=2,
            )
        )
        if len(bx) < 20:
            raise StardewAdapterError("player feet are unknown")
        px = (int(bx.min()) + int(bx.max())) / 2 + int(xs.min()) - 5 - ox
        py = int(by.max()) + int(ys.max()) - 13 - oy
        return origins, (ox, oy), (px, py), uncertainty

    def decode(self, image, *, resources=True, aiming_at=None):
        origins, (ox, oy), (px, py), uncertainty = self.geometry(image)
        pixels = np.asarray(image)
        samples = []
        for cx, cy in origins:
            states = {}
            for tx in range(-2, 14):
                for ty in range(1, 7):
                    x, y = cx + 48 * tx, cy + 48 * ty
                    if not 16 <= x < image.width - 16 or not 16 <= y < 824:
                        raise StardewAdapterError(
                            "prepared planted area outside the viewport"
                        )
                    patch = pixels[y - 15 : y + 16, x - 15 : x + 16]
                    dry = int(np.count_nonzero(np.all(patch == (86, 54, 52), axis=2)))
                    wet = int(np.count_nonzero(np.all(patch == (59, 23, 39), axis=2)))
                    if max(dry, wet) >= 25:
                        if min(dry, wet) > 0:
                            raise StardewAdapterError("ambiguous seed tint")
                        states[(tx, ty)] = bool(wet)
            if not states.keys() <= self.expected:
                raise StardewAdapterError(
                    "unexpected planted target outside the calibrated initial set"
                )
            samples.append(states)
        crops = {}
        for tile in self.expected:
            values = {sample.get(tile) for sample in samples}
            if len(values) == 1 and None not in values:
                crops[tile] = next(iter(values))
            elif -26 <= tile[0] * 48 - px <= 26 and -72 <= tile[1] * 48 - py <= 20:
                crops[tile] = None
            elif (
                aiming_at is not None and tile != aiming_at
                and -35 <= (tile[0] - aiming_at[0]) * 48 <= 43
                and 5 <= (tile[1] - aiming_at[1]) * 48 <= 83
            ):
                # Supplemental aiming frames never establish crop coverage or
                # resource truth. The cursor can hide another seed; retain it
                # as unknown, then require the ordinary post-action observation
                # (with the cursor moved away) to reconcile every visible crop.
                crops[tile] = None
            else:
                raise StardewAdapterError(
                    f"crop {tile} missing or ambiguous outside the player footprint"
                )
        if not self.tool_template.matches(image.crop(self.tool_box)):
            raise StardewAdapterError("selected watering can is not visibly recognized")
        obscured_obstacles = []
        for name, box, template in self.obstacles:
            # Raster phase can differ by one pixel across independently drawn sprites.
            found = False
            for cx, cy in origins:
                dx, dy = cx - self.origin_reference[0], cy - self.origin_reference[1]
                moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
                if template.matches(image.crop(moved)):
                    found = True
                    break
            if not found:
                if aiming_at is not None:
                    # The ordinary cursor extends down/right from its hot spot
                    # (-20,+20 relative to the target). Only this supplemental
                    # marker frame may leave an intersecting obstacle unknown.
                    # The subsequent pointer-away full frame must recognize it
                    # before the driver is allowed to press the mouse button.
                    tx, ty = ox + aiming_at[0]*48, oy + aiming_at[1]*48
                    cursor = (tx-22, ty+18, tx+14, ty+57)
                    moved = (box[0]+ox-self.origin_reference[0],
                             box[1]+oy-self.origin_reference[1],
                             box[2]+ox-self.origin_reference[0],
                             box[3]+oy-self.origin_reference[1])
                    if (max(cursor[0], moved[0]) < min(cursor[2], moved[2])
                            and max(cursor[1], moved[1]) < min(cursor[3], moved[3])):
                        obscured_obstacles.append(name)
                        continue
                raise StardewAdapterError(f"relevant obstacle {name} is not recognized")
        return {
            "origin": (ox, oy),
            "player": (px, py),
            "uncertainty": uncertainty,
            "crops": crops,
            "obscured_obstacles": obscured_obstacles,
            "energy": self.energy.recognize(image) if resources else None,
            "water": self.water.recognize(image) if resources else None,
        }

    def verify_aim(self, image, tile, before):
        """Require the live red tool-hit rectangle on the reviewed dry seed.

        This second visible frame follows a pointer-only move. It cannot replace
        the fresh resource observation or confirm watering. Adjacent markers and
        partly unreadable rectangles are rejected before mouse-down.
        """
        frame = self.decode(image, resources=False, aiming_at=tile)
        if frame["crops"].get(tile) is not False:
            raise StardewAdapterError("aimed crop is not visibly dry")
        if (
            max(
                abs(
                    frame["player"][i]
                    - (before.position.world_pixel_x, before.position.world_pixel_y)[i]
                )
                for i in (0, 1)
            )
            > frame["uncertainty"] + before.position.pixel_uncertainty
        ):
            raise StardewAdapterError("player moved while confirming tool target")
        a = np.asarray(image).astype(int)
        red = (
            (a[:, :, 0] > 140)
            & (a[:, :, 0] > 1.8 * a[:, :, 1])
            & (a[:, :, 1] < 110)
            & (a[:, :, 2] < 80)
        )
        ox, oy = frame["origin"]

        def rectangle(tx, ty):
            cx, cy = round(ox + tx * 48), round(oy + ty * 48)
            best = 0
            for dx in range(-3, 5):
                for dy in range(-3, 5):
                    x, y = cx - 24 + dx, cy - 24 + dy
                    if x < 0 or y < 0 or x + 50 > image.width or y + 50 > image.height:
                        continue
                    top = int(red[y : y + 3, x : x + 48].any(axis=0).sum())
                    bottom = int(red[y + 45 : y + 48, x : x + 48].any(axis=0).sum())
                    left = int(red[y : y + 48, x : x + 3].any(axis=1).sum())
                    right = int(red[y : y + 48, x + 45 : x + 48].any(axis=1).sum())
                    # The avatar may cover part of the marker. Three separately
                    # visible edges locate the rectangle; a shared edge with an
                    # adjacent tile is insufficient.
                    three_edges = (
                        sum(edge >= 20 for edge in (top, bottom, left, right)) >= 3
                        and max(top, bottom, left, right) >= 35
                    )
                    # An occluded marker can still expose one long, connected
                    # right-angle corner. Two perpendicular edges locate both
                    # tile axes; adjacent-tile shared edges cannot satisfy it.
                    corners = (
                        (top, left, red[y:y+3, x:x+3]),
                        (top, right, red[y:y+3, x+45:x+48]),
                        (bottom, left, red[y+45:y+48, x:x+3]),
                        (bottom, right, red[y+45:y+48, x+45:x+48]),
                    )
                    connected_corner = any(min(a, b) >= 30 and max(a, b) >= 40 and corner.any()
                                           for a, b, corner in corners)
                    if three_edges or connected_corner:
                        best = max(best, top + bottom + left + right)
            return best

        matches = {
            (tile[0] + dx, tile[1] + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if rectangle(tile[0] + dx, tile[1] + dy) >= 95
        }
        if matches != {tile}:
            raise StardewAdapterError(
                f"visible tool target does not uniquely match reviewed crop: {sorted(matches)}"
            )
        return frame

    def recognize(self, screenshot, window, save):
        if self.previous and self.previous.session_nonce != save.nonce:
            raise StardewAdapterError("fresh session requires a new perception history")
        frame = self.decode(Image.open(screenshot).convert("RGB"))
        now = time.monotonic()
        next_history = dict(self.last_visible)
        crops = []
        for tile, watered in sorted(frame["crops"].items()):
            key = f"farm-{tile[0]}-{tile[1]}"
            if watered is None:
                if tile not in next_history or now - next_history[tile][1] > 30:
                    raise StardewAdapterError(
                        "occluded target lacks recent visible history"
                    )
            else:
                next_history[tile] = (watered, now, str(screenshot))
            crops.append(
                CropObservation(
                    key,
                    *tile,
                    True,
                    bool(watered),
                    watered is None,
                    0 if watered is None else 1,
                    str(screenshot),
                )
            )
        newly = [
            tile
            for tile, state in frame["crops"].items()
            if state is True
            and tile in self.last_visible
            and self.last_visible[tile][0] is False
        ]
        uses = self.tool_uses
        if self.previous:
            if newly:
                if (
                    len(newly) != 1
                    or frame["water"] != self.previous.tool.watering_can_units - 1
                    or frame["energy"] != self.previous.energy - 2
                ):
                    raise StardewAdapterError(
                        "visible crop, water and energy changes do not reconcile"
                    )
                uses += 1
            elif (
                frame["water"] != self.previous.tool.watering_can_units
                or frame["energy"] != self.previous.energy
            ):
                raise StardewAdapterError(
                    "resource use lacks a newly visible watered target"
                )
        x, y = frame["player"]
        ox, oy = frame["origin"]
        u = frame["uncertainty"]
        result = ScreenObservation(
            uuid4().hex,
            datetime.now(timezone.utc).isoformat(),
            save.disposable_tree_sha256,
            window,
            tuple(crops),
            frame["energy"],
            270,
            ToolObservation("watering_can", frame["water"], 40, 0, uses),
            PositionObservation(
                "Farm",
                round(x / 48),
                round(y / 48),
                max(abs(x), abs(y)) + u <= 8,
                1,
                x,
                y,
                u,
                ox,
                oy,
            ),
            (str(screenshot),),
            scene_complete=True,
            unknown_regions=tuple(
                f"player-occluded:{c.crop_id}" for c in crops if c.occluded
            ),
            session_nonce=save.nonce,
            perception_classification="automatic_live"
            if self.qualified()
            else "pixel_fixture_unqualified",
        )
        result.validate(
            save.disposable_tree_sha256,
            allow_player_occlusion=self.previous is not None,
        )
        self.last_visible, self.previous, self.tool_uses = next_history, result, uses
        return result
