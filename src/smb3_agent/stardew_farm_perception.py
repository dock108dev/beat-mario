"""Bounded v2 farm recognition from independently retained pixel calibrations.

No v2 live calibration ships with this module. Every selected/protected tile,
inventory slot, selected item, calendar, clock, and resource must match current
pixels. Unsupported viewports and occlusion stop; no expected outcome is inferred.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image
from PIL import ImageFilter
import numpy as np

from smb3_agent.stardew_adapter import CropObservation, PositionObservation, ScreenObservation, ToolObservation
from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_farm_tasks import FarmObservation, FarmTarget, InventorySlot, require
from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
from smb3_agent.stardew_perception import PixelRegion


def region(value):
    return PixelRegion(tuple(value["box"]), value["values"])


def stable_patch(image):
    """One screen-pixel filter for the game's subpixel camera rasterization."""
    return np.asarray(image.filter(ImageFilter.GaussianBlur(1)), dtype=np.int16)


def patch_matches(actual, calibrated, *, mean_limit=2.0):
    # The two-pixel border includes adjacent-tile ink and filter boundary
    # effects. The calibrated object/soil core carries the classification.
    difference = np.abs(actual[2:-2, 2:-2]-calibrated[2:-2, 2:-2])
    # Both limits are required: a small localized changed object must not hide
    # behind a low average across its surrounding ground.
    return float(difference.mean()) <= mean_limit and int(difference.max()) <= 32


def read_inventory(image, specifications):
    """Read item identity and count separately from selected-slot decoration."""
    from smb3_agent.stardew_perception import _foreground_mask, pixel_digest
    slots = []
    for index, spec in enumerate(specifications):
        if "icon" not in spec:
            value = region(spec).recognize(image)
            item, count = value["item"], value["count"]
        else:
            item = region(spec["icon"]).recognize(image)
            numeric = spec["count"]
            patch = _foreground_mask(image.crop(tuple(numeric["box"])), ((255, 255, 255),)).convert("RGB")
            digest = pixel_digest(patch)
            require(digest in numeric["values"], "inventory count is unrecognized")
            count = numeric["values"][digest]
            if count is None:
                count = 1 if item else 0
            require(item is not None or count == 0, "count without a recognized inventory item")
        slots.append(InventorySlot(index, item, count, ""))
    return slots


def clock_reader(spec):
    """Build exact game-font glyphs from retained, reviewed clock screenshots."""
    from smb3_agent.stardew_perception import ExactGlyph, NumericHudRegion, _foreground_mask
    glyphs = []
    for sample in spec["glyph_samples"]:
        with Image.open(sample["image"]) as image:
            mask = _foreground_mask(image.crop(tuple(spec["box"])), ((32, 18, 33),))
        require(mask.getbbox() is not None, "clock sample has no text")
        mask = mask.crop(mask.getbbox())
        runs, start = [], None
        for x in range(mask.width+1):
            occupied = x < mask.width and mask.crop((x, 0, x+1, mask.height)).getbbox()
            if occupied and start is None:
                start = x
            elif not occupied and start is not None:
                runs.append((start, x))
                start = None
        require(len(runs) == len(sample["text"]), "clock sample annotation does not match its pixels")
        for char, (left, right) in zip(sample["text"], runs):
            part = mask.crop((left, 0, right, mask.height))
            part = part.crop(part.getbbox())
            glyphs.append(ExactGlyph(char, part.size, part.tobytes()))
    return NumericHudRegion(tuple(spec["box"]), ((32, 18, 33),), tuple(glyphs))


class FarmPixelProfile(PreparedFarmPixelProfile):
    def __init__(self, manifest_path):
        self.farm_manifest = Path(manifest_path)
        self.farm_manifest_bytes = self.farm_manifest.read_bytes()
        config = json.loads(self.farm_manifest_bytes)
        require(config.get("schema") == "farm-actions-pixel-profile/v2", "unsupported farm profile schema")
        # Reuse only qualified camera/player and numerical resource calibration.
        super().__init__(Path(config["geometry_manifest"]))
        self.geometry_config = self.config
        self.config = config
        self.profile_id = config["profile_id"]
        self.farm_previous = None
        self.menu_observation = None
        self.selection_samples = []
        for slot in config["inventory"]:
            if "icon" not in slot:
                continue
            for sample in slot["icon"]["samples"]:
                left, top, _, _ = sample["box"]
                with Image.open(sample["image"]) as image:
                    patch = image.convert("RGB").crop((left+2, top+2, left+18, top+18))
                from smb3_agent.stardew_perception import pixel_digest
                self.selection_samples.append((pixel_digest(patch), slot["icon"]["values"][sample["digest"]]))
        for spec in config.get("selection_icons", {}).values():
            self.selection_samples.extend(spec["values"].items())
        self.target_samples = {}
        if config.get("target_matcher") == "bounded_raster_v1":
            for target in config["targets"]:
                samples = []
                for sample in target["region"]["samples"]:
                    with Image.open(sample["image"]) as image:
                        patch = stable_patch(image.convert("RGB").crop(sample["box"]))
                    samples.append((patch, target["region"]["values"][sample["digest"]]))
                self.target_samples[target["id"]] = samples
        from smb3_agent.stardew_perception import _foreground_mask
        harvest_spec = config["aim_regions"]["harvest_crop"]
        colors = tuple(map(tuple, harvest_spec["foreground_colors"]))
        self.harvest_aim_samples = []
        for sample in harvest_spec["samples"]:
            with Image.open(sample["image"]) as image:
                self.harvest_aim_samples.append(np.asarray(_foreground_mask(
                    image.crop(sample["box"]), colors)).copy())
        self.clock_reader = clock_reader(config["clock"]) if "glyph_samples" in config["clock"] else None

    def read_menu(self, native, driver, destination):
        """Observe backpack capacity/calendar through the game's inventory UI.

        These are observations, not supplied setup labels. Only a recognized
        farm can open the menu, and only the recognized inventory menu can be
        closed. Every input uses the caller's identity/cancellation guard.
        """
        from smb3_agent.stardew_adapter import InputCommand, InputKind
        destination = Path(destination)
        self.menu_observation = None
        retry_deadline = time.monotonic() + 5
        for attempt in range(8):
            current = native.detect_window()
            before = native.capture(current, destination / f"menu-before-{uuid4().hex}.png")
            try:
                with Image.open(before) as source:
                    _, _, player, uncertainty = self.geometry(source.convert("RGB"))
                break
            except StardewAdapterError as exc:
                if (str(exc) not in {"camera anchor not recognized",
                        "player pants are ambiguous or absent", "player feet are unknown"}
                        or attempt == 7 or time.monotonic() >= retry_deadline):
                    raise
                (destination / f"menu-retry-{uuid4().hex}.json").write_text(json.dumps({
                    "screenshot": str(before), "reason": str(exc), "attempt": attempt + 1,
                    "input_emitted": False}))
                time.sleep(.25)
        driver.send(InputCommand(InputKind.KEYBOARD, "escape", "press", 60,
                                 purpose="observe_farm_inventory"))
        time.sleep(.12)
        capture = native.capture(native.detect_window(), destination / f"inventory-{uuid4().hex}.png")
        with Image.open(capture) as source:
            im = source.convert("RGB")
            values = {key: region(spec).recognize(im) for key, spec in self.config["menu_regions"].items()}
        require(values.get("capacity") == len(self.config["inventory"]), "visible backpack capacity differs")
        require(values.get("menu") is True, "inventory menu is not recognized")
        observed_at = time.monotonic()
        driver.send(InputCommand(InputKind.KEYBOARD, "escape", "press", 60,
                                 purpose="close_observed_farm_inventory"))
        time.sleep(.12)
        self.menu_observation = {"values": values, "image": str(capture), "time": observed_at,
                                 "player": player, "uncertainty": uncertainty}

    def qualified(self):
        if not hasattr(self, "geometry_config"):
            return False
        config = self.config
        from copy import copy
        geometry = copy(self)
        geometry.config = self.geometry_config
        geometry_ok = PreparedFarmPixelProfile.qualified(geometry)
        roles = {"coverage", "maturity", "empty_plots", "inventory", "seed_counts", "debris",
                 "protected_targets", "tools", "calendar", "clock", "approaches", "negative_frames"}
        evidence = config.get("evidence_hashes", {})
        bounds = config.get("coverage_bounds", ())
        if len(bounds) != 4 or any(type(v) is not int for v in bounds):
            return False
        left, top, right, bottom = bounds
        tiles = {tuple(t["tile"]) for t in config["targets"]}
        if not left <= right or not top <= bottom or not all(left <= x <= right and top <= y <= bottom for x,y in tiles):
            return False
        selected = {key for entries in config.get("farm_approaches", {}).values() for key in entries}
        by_id = {t["id"]: t for t in config["targets"]}
        if not selected or not selected <= by_id.keys():
            return False
        for key in selected:
            x, y = by_id[key]["tile"]
            neighbors = config.get("protected_neighbors", {}).get(key)
            if neighbors is None or any(n not in by_id or n == key for n in neighbors):
                return False
            actual_neighbors = {t["id"] for t in config["targets"] if t["id"] != key
                                and max(abs(t["tile"][0]-x),abs(t["tile"][1]-y)) <= 1}
            if set(neighbors) != actual_neighbors:
                return False
        # Only actual crop/debris/scenery objects become task facts. Traversed
        # bare ground is not falsely labeled as a visible protected object when
        # the avatar covers it. The retained scope review must bind this exact
        # prepared farm, its crop set, neighboring objects and approach corridors.
        if config.get("coverage_mode") != "selected_targets_and_observed_neighbors":
            return False
        if (not geometry_ok or config.get("classification") != "actual_live"
                or set(config.get("qualified_roles", ())) != roles
                or self.farm_manifest.read_bytes() != self.farm_manifest_bytes
                or config.get("qualification_record") not in evidence
                or config.get("geometry_manifest") not in evidence):
            return False
        if not all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in evidence.items()):
            return False
        # Every call still checks the immutable manifest and actual evidence
        # hashes. Re-decoding the same PNGs for every UI poll is redundant and
        # can starve fresh screen observations. Cache only that pure validation.
        sample_identity = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        if getattr(self, "_verified_sample_identity", None) == sample_identity:
            return True
        # Every lookup value must be reproducible from its retained calibration
        # frame; hand-entered hashes or runtime labels cannot add recognition.
        aim_regions = config.get("aim_regions", {})
        if set(aim_regions) != {"harvest_crop", "plant_seed", "clear_debris", "water_crop", "select_farm_item"}:
            return False
        if set(config.get("menu_regions", {})) != {"menu", "capacity", "calendar"}:
            return False
        inventory_regions = [r for spec in config["inventory"] for r in
                             ([spec["icon"], spec["count"]] if "icon" in spec else [spec])]
        regions = [t["region"] for t in config["targets"]] + inventory_regions + list(config["menu_regions"].values()) + [
            config[k] for k in ("selected_slot", "season", "day", "can_water")] + list(aim_regions.values())
        regions += list(config.get("selection_icons", {}).values())
        if self.clock_reader:
            if not all(s["image"] in evidence for s in config["clock"]["glyph_samples"]):
                return False
        else:
            regions.append(config["clock"])
        for spec in regions:
            samples = spec.get("samples", [])
            if not samples or set(spec["values"]) != {s["digest"] for s in samples}:
                return False
            from smb3_agent.stardew_perception import pixel_digest
            for sample in samples:
                path = sample["image"]
                if path not in evidence:
                    return False
                with Image.open(path) as image:
                    box = tuple(sample.get("box", spec["box"]))
                    if (box[2]-box[0], box[3]-box[1]) != (spec["box"][2]-spec["box"][0], spec["box"][3]-spec["box"][1]):
                        return False
                    if not 0 <= box[0] < box[2] <= image.width or not 0 <= box[1] < box[3] <= image.height:
                        return False
                    patch = image.crop(box)
                    if spec.get("foreground_white") or spec.get("foreground_colors"):
                        from smb3_agent.stardew_perception import _foreground_mask
                        colors = spec.get("foreground_colors", ((255, 255, 255),))
                        patch = _foreground_mask(patch, tuple(map(tuple, colors))).convert("RGB")
                    if pixel_digest(patch) != sample["digest"]:
                        return False
        self._verified_sample_identity = sample_identity
        return True

    def decode(self, image, *, resources=True, aiming_at=None):
        require(self.menu_observation is not None and 0 <= time.monotonic()-self.menu_observation["time"] <= 5,
                "fresh visible inventory and calendar observation is required")
        origins, origin, player, uncertainty = self.geometry(image)
        require(max(abs(a-b) for a, b in zip(player, self.menu_observation["player"]))
                <= uncertainty + self.menu_observation["uncertainty"],
                "player moved during inventory observation; reacquire the farm")
        targets = []
        for spec in self.config["targets"]:
            values = []
            for ox, oy in origins:
                dx, dy = ox-self.origin_reference[0], oy-self.origin_reference[1]
                calibrated = region(spec["region"])
                shifted = PixelRegion(tuple(round(v + (dx if i % 2 == 0 else dy)) for i, v in enumerate(calibrated.box)), calibrated.values)
                try:
                    values.append(shifted.recognize(image))
                except StardewAdapterError:
                    # Camera alignment is an interval, not twelve different
                    # simultaneously true raster locations. Require a retained
                    # pixel match inside it and reject conflicting matches.
                    if self.config.get("target_matcher") == "bounded_raster_v1":
                        patch = stable_patch(image.crop(shifted.box))
                        values.extend(value for sample, value in self.target_samples[spec["id"]]
                                      if patch_matches(patch, sample, mean_limit=3.0 if value["state"] == "immature" else 2.0))
                    continue
            require(values, f"farm target {spec['id']} is missing or occluded")
            require(all(v == values[0] for v in values), "farm target is ambiguous across camera alignment")
            value = values[0]
            require(isinstance(value, dict) and {"state", "species", "watered"} <= value.keys(), "unsupported farm target template")
            targets.append(FarmTarget(spec["id"], *spec["tile"], value["state"], value["species"],
                                      value["watered"], spec.get("protected", False)))
        slots = read_inventory(image, self.config["inventory"])
        selected = region(self.config["selected_slot"]).recognize(image)
        season = region(self.config["season"]).recognize(image)
        day = region(self.config["day"]).recognize(image)
        require(self.menu_observation["values"]["calendar"] == {"season": season, "day": day},
                "farm calendar changed between inventory and field observations")
        if self.clock_reader:
            import re
            text = self.clock_reader.recognize_text(image)
            clock = re.fullmatch(r"(\d{1,2}):(\d{2})(am|pm)", text)
            require(clock is not None, "visible farm clock format is unknown")
            hour, minute = int(clock[1]), int(clock[2])
            require(1 <= hour <= 12 and minute in range(0, 60, 10), "visible farm time is invalid")
            minutes = (hour % 12 + (12 if clock[3] == "pm" else 0))*60+minute
        else:
            minutes = region(self.config["clock"]).recognize(image)
        return {"origin": origin, "player": player, "uncertainty": uncertainty,
                "crops": {(t.tile_x, t.tile_y): t.watered for t in targets if t.planted},
                "targets": targets, "inventory": slots, "selected_slot": selected,
                "season": season,
                "day": day,
                "clock": minutes,
                "energy": self.energy.recognize(image) if resources else None,
                # Can content must remain observable even when another item is
                # selected; do not carry forward or subtract expected water use.
                "water": region(self.config["can_water"]).recognize(image)}

    def verify_action_aim(self, command, image, before):
        _, origin, player, uncertainty = self.geometry(image)
        frame = {"origin": origin, "player": player, "uncertainty": uncertainty}
        require(before.farm is not None, "farm aiming requires observed farm facts")
        p = before.position
        require(max(abs(player[0]-p.world_pixel_x), abs(player[1]-p.world_pixel_y))
                <= uncertainty+p.pixel_uncertainty, "player moved while aiming")
        if command.purpose == "select_farm_item":
            # Hover text hides other slots, while the cursor hides the lower
            # right of this icon. The shared runtime just observed the full
            # inventory; independently identify this icon's unobscured core.
            bx, by, _, _ = before.window.bounds
            x, y = command.target[0]-bx, command.target[1]-by
            slots = [int(k) for k, point in self.config["inventory_slot_points"].items()
                     if abs(x-point[0]) <= 1 and abs(y-point[1]) <= 1]
            require(len(slots) == 1, "item selection is outside a visible inventory slot")
            slot = slots[0]
            owned = next(s for s in before.farm.inventory if s.slot == slot)
            require(owned.count > 0 and owned.item in {"parsnip_seeds", "watering_can", "pickaxe", "axe", "scythe"},
                    "selection requires an observed owned farm item")
            left, top, _, _ = self.config["inventory"][slot]["icon"]["box"]
            from smb3_agent.stardew_perception import pixel_digest
            digest = pixel_digest(image.crop((left+2, top+2, left+18, top+18)))
            matches = {item for fingerprint, item in self.selection_samples if fingerprint == digest}
            require(matches == {owned.item}, "visible selection icon is unknown or ambiguous")
            return frame
        # The pointer/held-seed preview can obscure the target and its neighbor.
        # This supplementary frame establishes aim only. The shared runtime
        # refreshes the full unobscured task state before any mouse press.
        require([(s.slot, s.item, s.count) for s in read_inventory(image, self.config["inventory"])]
                == [(s.slot, s.item, s.count) for s in before.farm.inventory]
                and region(self.config["selected_slot"]).recognize(image) == before.farm.selected_slot
                and region(self.config["can_water"]).recognize(image) == before.tool.watering_can_units,
                "farm items changed while aiming")
        p = before.position
        require(max(abs(frame["player"][0]-p.world_pixel_x), abs(frame["player"][1]-p.world_pixel_y))
                <= frame["uncertainty"]+p.pixel_uncertainty, "player moved while aiming")
        spec = self.config["aim_regions"].get(command.purpose)
        require(spec is not None, "action has no calibrated visible aim")
        # Marker regions are relative to the requested current-window point.
        # Their calibrated pixels must identify the exact action/target marker.
        bx, by, _, _ = before.window.bounds
        x, y = command.target[0]-bx, command.target[1]-by
        if command.purpose == "select_farm_item":
            points = self.config["inventory_slot_points"]
            require(any(abs(x-p[0]) <= 1 and abs(y-p[1]) <= 1 for p in points.values()),
                    "item selection is outside a visible inventory slot")
        elif command.purpose == "harvest_crop":
            from smb3_agent.stardew_perception import _foreground_mask, pixel_digest
            marker = region(spec)
            found = False
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    box = tuple(round(v+(x+dx if i % 2 == 0 else y+dy)) for i,v in enumerate(marker.box))
                    patch = _foreground_mask(image.crop(box), tuple(map(tuple, spec["foreground_colors"]))).convert("RGB")
                    found = found or marker.values.get(pixel_digest(patch)) is True
                    if not found:
                        mask = np.asarray(patch)[:, :, 0]
                        found = any(np.count_nonzero(mask != sample) <= 12
                                    for sample in self.harvest_aim_samples)
            require(found, "visible harvest cursor is absent at the reviewed mature crop")
        else:
            from smb3_agent.stardew_farm_aim import verify_farm_marker
            target = next(t for t in before.farm.targets if t.target_id == command.reviewed_crop_id)
            verify_farm_marker(image, origin, (target.tile_x, target.tile_y),
                               planting=command.purpose == "plant_seed")
        return frame

    def verify_initial_view(self, frame):
        require(self.qualified(), "farm profile is not qualified")
        require(max(map(abs, frame["player"])) + frame["uncertainty"] <= 8,
                "show the reviewed farmhouse entrance for setup verification")
        require(frame["energy"] == self.config["initial_energy"]
                and frame["water"] == self.config["initial_water"], "prepared farm resources differ")
        observed = [{"id": t.target_id, "state": t.state, "species": t.species, "watered": t.watered}
                    for t in frame["targets"]]
        require(observed == self.config["initial_targets"], "prepared farm targets differ from retained seed proof")

    def recognize(self, screenshot, window, save):
        from dataclasses import replace
        require(window.trusted, "foreground game window is required")
        require(self.farm_previous is None or self.farm_previous.session_nonce == save.nonce,
                "fresh session requires a new farm recognizer")
        with Image.open(screenshot) as source:
            frame = self.decode(source.convert("RGB"))
        ref = str(screenshot)
        farm = FarmObservation(tuple(replace(t, evidence_reference=ref) for t in frame["targets"]),
                               tuple(replace(s, evidence_reference=ref) for s in frame["inventory"]),
                               len(frame["inventory"]), frame["selected_slot"], frame["season"], frame["day"],
                               frame["clock"], self.profile_id)
        crops = tuple(CropObservation(t.target_id, t.tile_x, t.tile_y, True, t.watered, False, 1, ref)
                      for t in farm.targets if t.planted)
        x, y = frame["player"]
        ox, oy = frame["origin"]
        u = frame["uncertainty"]
        result = ScreenObservation(uuid4().hex, datetime.now(timezone.utc).isoformat(), save.disposable_tree_sha256,
            window, crops, frame["energy"], 270, ToolObservation(farm.selected() or "empty", frame["water"], 40, 0, 0),
            PositionObservation("Farm", round(x/48), round(y/48), max(abs(x), abs(y))+u <= 8, 1, x, y, u, ox, oy),
            (ref, self.menu_observation["image"]), scene_complete=True, session_nonce=save.nonce,
            perception_classification="automatic_live" if self.qualified() else "pixel_fixture_unqualified", farm=farm)
        result.validate(save.disposable_tree_sha256)
        self.farm_previous = result
        return result
