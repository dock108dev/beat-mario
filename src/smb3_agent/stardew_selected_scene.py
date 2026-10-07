"""Narrow visible spring-seed patch support, independent of save identity.

Shared calibration supplies house/avatar/tool/resource features. Current pixels
supply targets and clear terrain. Unknown terrain never supplies a route edge.
This does not recognize arbitrary farms, clothing, mature crops or upgraded cans.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator
from smb3_agent.stardew_perception import CameraAlignment, CalibratedBarRegion
from smb3_agent.stardew_farm_vision import FILLED, EMPTY, BAR_BOX


def scene_routes(clear, crops, *, edges=None):
    """Construct a cardinal graph from observed free cells, never fixture poses."""
    if (0, 0) not in clear:
        raise StardewAdapterError("The farmhouse return point is not visible")
    reachable, pending = {(0, 0)}, [(0, 0)]
    while pending:
        x, y = pending.pop()
        for tile in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
            if tile in clear and tile not in reachable and (edges is None or frozenset(((x, y), tile)) in edges):
                reachable.add(tile)
                pending.append(tile)
    def name(tile):
        return f"view-{tile[0]}-{tile[1]}"
    watering = {}
    for x, y in crops:
        # Cardinal neighbors keep the seed outside the avatar's foot mask.
        candidates = {(x-1, y), (x+1, y), (x, y-1), (x, y+1)} & reachable
        if not candidates:
            raise StardewAdapterError(f"Seed ({x}, {y}) has no observed clear approach and return")
        best = min(candidates, key=lambda t: (abs(t[0])+abs(t[1]), t))
        watering[f"farm-{x}-{y}"] = name(best)
    # Keep only observed paths needed for crop approaches and return. Changes
    # in unrelated visible terrain cannot invalidate this bounded activity.
    required = {(0, 0)}
    for target in watering.values():
        destination = next(t for t in reachable if name(t) == target)
        queue, parents = [(0, 0)], {(0, 0): None}
        for current in queue:
            if current == destination:
                break
            x, y = current
            for tile in sorted(((x-1, y), (x+1, y), (x, y-1), (x, y+1))):
                if (tile in reachable and tile not in parents
                        and (edges is None or frozenset((current, tile)) in edges)):
                    parents[tile] = current
                    queue.append(tile)
        while destination is not None:
            required.add(destination)
            destination = parents[destination]
    reachable = required
    return {"poses": {name(t): [t[0]*48, t[1]*48] for t in sorted(reachable)},
            "edges": [[name(t), name(n)] for t in sorted(reachable)
                      for n in ((t[0]+1, t[1]), (t[0], t[1]+1))
                      if n in reachable and (edges is None or frozenset((t, n)) in edges)],
            "watering": watering, "return_pose": name((0, 0))}


class SelectedSceneProfile(PreparedFarmPixelProfile):
    """Reuse qualified feature readers, discover a new bounded visible patch.

    Feature calibration is historical native evidence. Discovery/route execution
    on this new path needs its own packaged native qualification record.
    """
    tiles = tuple((x, y) for x in range(-2, 14) for y in range(1, 7))

    def __init__(self, manifest_path: Path):
        super().__init__(manifest_path)
        self.feature_config = self.config
        self.profile_id = "selected-visible-spring-patch-v1"
        self.expected = set()
        self.route_config = None
        self.route_cells = set()
        self.observed_edges = set()
        self.reviewed_edges = set()
        self.clear_templates = set()
        # The old record qualifies movement through these clear corridors. Only
        # their terrain pixels are shared; their coordinates are never a new
        # session's route. Match the entire foot collision footprint.
        points = set()
        for a, b in self.feature_config["edges"]:
            p, q = self.feature_config["poses"][a], self.feature_config["poses"][b]
            length = max(abs(p[j]-q[j]) for j in (0, 1))
            for i in range(length+1):
                points.add(tuple(round(p[j]+(q[j]-p[j])*i/max(1, length)) for j in (0, 1)))
        for x, y in points:
            # Do not label the calibration avatar or a seed as free terrain.
            if abs(x) <= 34 and -80 <= y <= 28:
                continue
            if any(abs(x-tx*48) <= 24 and abs(y-ty*48) <= 24
                   for tx, ty in self.feature_config["expected_tiles"]):
                continue
            self.clear_templates.add(self.reference.crop(self._foot_box(
                self.origin_reference[0]+x, self.origin_reference[1]+y)).tobytes())
        # Recombine only small exact motifs from independently qualified clear
        # terrain. Natural dirt/grass borders need not repeat an entire old
        # 37x21 footprint. Every current pixel remains covered by a recognized
        # 3x3 motif; unknown debris never supplies an edge.
        self._extend_native_terrain()
        self.clear_motifs = set()
        for value in self.clear_templates:
            self.clear_motifs.update(self._motifs(value))
        self._terrain_cache = {}
        self._renderer_motif_cache = {}
        # Fractional camera rendering can change a few edge channels in an
        # otherwise unchanged native wood motif. This optional, hash-bound
        # qualification supplies a bounded pattern comparison, never a palette
        # whitelist or a learned current-session route.
        from smb3_agent.stardew_view_settings import ViewSettingFeatures
        renderer = ViewSettingFeatures().config.get('terrain_renderer_variation')
        self._renderer_bank = None
        if renderer:
            features = ViewSettingFeatures()
            if renderer not in features.config['evidence_hashes']:
                raise StardewAdapterError('Terrain renderer variation lacks hashed evidence')
            receipt = json.loads(Path(renderer).read_text())
            if (receipt.get('status') != 'native_renderer_variation_observed'
                    or receipt.get('neutral_handback_confirmed') is not True
                    or receipt.get('maximum_channel_difference') != 9
                    or receipt.get('maximum_motif_channel_sum') != 81
                    or not receipt.get('frames')
                    or any(frame.get('sha256') not in features.config['evidence_hashes'].values()
                           for frame in receipt['frames'])):
                raise StardewAdapterError('Terrain renderer variation is incomplete')
            bank = np.frombuffer(b''.join(self.clear_motifs), dtype=np.uint8).reshape(-1,27)
            # Uniform patches require exact evidence. The fallback recognizes
            # spatially varied native texture, not a nearby solid color.
            varied = np.any(bank.reshape(-1,9,3) != bank[:,None,:3], axis=(1,2))
            self._renderer_bank = bank[varied].astype(np.int16)
        self.scene_receipt = None
        self.can_core = CameraAlignment.calibrate(self.reference.crop((510, 866, 550, 901))).template
        from smb3_agent.stardew_view_settings import ViewSettingFeatures
        features = ViewSettingFeatures()
        self.unselected_can_core = CameraAlignment.calibrate(
            features.images['can-unselected'].convert('RGB')).template
        self.selected_border = self.reference.crop((500, 875, 505, 909)).tobytes()
        self.tool_offset = 0
        self.toolbar_outline = {box: self.reference.crop(box).tobytes() for box in (
            (368, 850, 1148, 858), (368, 932, 1148, 938),
            (356, 862, 363, 932), (1150, 862, 1156, 932))}

    def _extend_native_terrain(self):
        """Shared textures from observed native movement, never a saved route."""
        from smb3_agent.stardew_view_settings import ViewSettingFeatures
        features = ViewSettingFeatures()
        for sweep in features.config.get('native_clear_sweeps', []):
            if any(sweep[name] not in features.config['evidence_hashes']
                   for name in ('receipt', 'reference')):
                raise StardewAdapterError('Native terrain qualification has unhashed evidence')
            receipt = json.loads(Path(sweep['receipt']).read_text())
            if (receipt.get('status') != 'native_passable_corridor_observed'
                    or receipt.get('owned_input_released') is not True
                    or not receipt.get('steps')):
                raise StardewAdapterError('Native terrain qualification is incomplete')
            image = Image.open(sweep['reference']).convert('RGB')
            _, origin, initial, uncertainty = self.geometry(image)
            if max(map(abs, initial))+uncertainty > 8:
                raise StardewAdapterError('Native terrain reference has no verified entrance pose')
            previous = receipt['initial']['position']
            if max(abs(previous[j]-initial[j]) for j in (0,1)) > uncertainty+1:
                raise StardewAdapterError('Native terrain reference and movement pose differ')
            points = set()
            for step in receipt['steps']:
                before, after = step['before']['position'], step['after']['position']
                timing = step['pulse_timing']
                delta = [abs(after[j]-before[j]) for j in (0,1)]
                axis = int(delta[1] > delta[0])
                if (max(abs(before[j]-previous[j]) for j in (0,1)) > 1
                        or delta[1-axis] > 5 or not .1 <= delta[axis] <= 60
                        or not 0 < timing['post_to_release_seconds'] <= .25
                        or any(abs(v[0]) > 192 or not -8 <= v[1] <= 175
                               for v in (before,after))):
                    raise StardewAdapterError('Native terrain movement evidence is inconsistent')
                length = round(delta[axis])
                for i in range(length+1):
                    points.add(tuple(round(before[j]+(after[j]-before[j])*i/length)
                                     for j in (0,1)))
                previous = after
            # Camera scrolling changes the pixel raster phase at fractional
            # zoom. Learn those phases from the independently observed native
            # movement frames, using their own camera/actor geometry. Resolve
            # receipt frames by approved content hash: receipt paths may refer
            # to the original source machine and cannot be runtime dependencies.
            approved = {digest: path for path, digest in features.config['evidence_hashes'].items()
                        if Path(path).suffix == '.png'}
            frames = {step[side]['sha256']: step[side]
                      for step in receipt['steps'] for side in ('before', 'after')}
            # A later neutral frame can expose floor previously covered by the
            # actor. It supplies textures only along the already verified path;
            # its unqualified surrounding terrain never creates more points.
            for frame in receipt.get('neutral_exposure_frames', []):
                if receipt.get('neutral_exposure_handback_confirmed') is not True:
                    raise StardewAdapterError('Native terrain exposure lacks neutral handback')
                frames[frame['sha256']] = frame
            for digest, frame in frames.items():
                if digest not in approved:
                    raise StardewAdapterError('Native terrain frame has unhashed evidence')
                frame_image = Image.open(approved[digest]).convert('RGB')
                _, frame_origin, actor, tolerance = self.geometry(frame_image)
                if max(abs(actor[j]-frame['position'][j]) for j in (0, 1)) > tolerance+1:
                    raise StardewAdapterError('Native terrain frame and movement pose differ')
                crops = self._reference_crops(frame_image, frame_origin)
                for x, y in points:
                    if abs(x-actor[0]) <= 34 and -80 <= y-actor[1] <= 28:
                        continue  # Never qualify a visible avatar or shadow.
                    if any(abs(x-tx*48) <= 24 and abs(y-ty*48) <= 24 for tx, ty in crops):
                        continue
                    self.clear_templates.add(frame_image.crop(self._foot_box(
                        frame_origin[0]+x, frame_origin[1]+y)).tobytes())

    def _reference_crops(self, image, origin):
        # Qualification excludes seed bodies independently of stored crop layout.
        pixels = np.asarray(image)
        crops = {}
        for tx, ty in self.tiles:
            x, y = (round(origin[j]+48*(tx,ty)[j]) for j in (0,1))
            patch = pixels[y-15:y+16,x-15:x+16]
            if any(np.count_nonzero(np.all(patch == tint,axis=2)) >= 25
                   for tint in ((86,54,52),(59,23,39))):
                crops[(tx,ty)] = False
        return crops

    def select_can(self, image):
        if image.size != self.viewport_size:
            raise StardewAdapterError("The complete toolbar requires the supported visible viewport")
        if any(image.crop(box).tobytes() != value for box, value in self.toolbar_outline.items()):
            raise StardewAdapterError("The complete toolbar outline is clipped, shifted or unknown")
        offsets = [64*(slot-2) for slot in range(12)]
        matches = [dx for dx in offsets if any(template.matches(image.crop((510+dx, 866, 550+dx, 901)))
                   for template in (self.can_core, self.unselected_can_core))]
        if len(matches) != 1:
            raise StardewAdapterError("A unique basic watering can is not visible in the complete toolbar")
        self.tool_offset = matches[0]
        self.tool_box = tuple(v+self.tool_offset if i % 2 == 0 else v
                              for i, v in enumerate((500, 858, 564, 909)))
        self.water = CalibratedBarRegion(tuple(v+self.tool_offset if i % 2 == 0 else v
                                              for i, v in enumerate(BAR_BOX)),
                                        FILLED, EMPTY, self.water.units_by_filled_pixels)
        return 531+self.tool_offset, 895

    @staticmethod
    def _foot_box(x, y):
        x, y = round(x), round(y)
        return x-18, y-10, x+19, y+11

    @staticmethod
    def _motifs(value):
        a = np.frombuffer(value, dtype=np.uint8).reshape(21,37,3)
        patches = np.lib.stride_tricks.sliding_window_view(a,(3,3),axis=(0,1))
        return (row.tobytes() for row in patches.transpose(0,1,3,4,2).reshape(-1,27))

    def _passable(self, value):
        if value in self.clear_templates:
            return True
        bank = getattr(self, 'clear_motifs', ())
        if not bank:
            return False
        cache = self._terrain_cache
        if value not in cache:
            if len(cache) >= 4096:
                cache.clear()
            cache[value] = all(self._terrain_motif(motif) for motif in self._motifs(value))
        return cache[value]

    def _terrain_motif(self, motif):
        if motif in self.clear_motifs:
            return True
        bank = getattr(self, '_renderer_bank', None)
        if bank is None:
            return False
        cache = self._renderer_motif_cache
        if motif not in cache:
            if len(cache) >= 8192:
                cache.clear()
            current = np.frombuffer(motif, dtype=np.uint8).astype(np.int16)
            if np.all(current.reshape(9,3) == current[:3]):
                cache[motif] = False
            else:
                candidates = bank[np.abs(bank[:,:3]-current[:3]).max(axis=1) <= 9]
                differences = np.abs(candidates-current)
                cache[motif] = bool(len(candidates) and np.any(
                    (differences.max(axis=1) <= 9) & (differences.sum(axis=1) <= 81)))
        return cache[motif]

    def _clear(self, image, x, y):
        box = self._foot_box(x, y)
        if not (0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height):
            return False
        # Camera alignment retains a one-pixel raster interval. Require an exact
        # retained terrain match within it; approximation cannot label debris.
        return any(self._passable(image.crop((box[0]+dx, box[1]+dy, box[2]+dx, box[3]+dy)).tobytes())
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    @staticmethod
    def _avatar_covers_footprint(point, player, uncertainty):
        # The tested swept footprint includes the localized sprite, shadow and
        # ground patch extent. Cell and edge checks must use the same boundary.
        return (abs(point[0]-player[0]) <= 34+uncertainty
                and -90-uncertainty <= point[1]-player[1] <= 38+uncertainty)

    def scan(self, image):
        origins, origin, player, uncertainty = self.geometry(image)
        pixels = np.asarray(image)
        crops, clear = {}, {(0, 0)}
        for tx, ty in self.tiles:
            values, free = set(), []
            for ox, oy in origins:
                x, y = round(ox+48*tx), round(oy+48*ty)
                if not (24 <= x < image.width-24 and 24 <= y < 824):
                    raise StardewAdapterError("The supported seed patch is outside the current screen")
                patch = pixels[y-15:y+16, x-15:x+16]
                dry = np.count_nonzero(np.all(patch == (86, 54, 52), axis=2))
                wet = np.count_nonzero(np.all(patch == (59, 23, 39), axis=2))
                if max(dry, wet) >= 25:
                    if min(dry, wet):
                        raise StardewAdapterError("Seed tint is ambiguous")
                    values.add(bool(wet))
                else:
                    values.add(None)
                # Crop discovery still covers the complete bounded patch. Once
                # reviewed, terrain decoding needs only its observed routes.
                free.append(self._clear(image, x, y) if self.route_config is None
                            or (tx, ty) in self.route_cells else False)
            if len(values) != 1:
                raise StardewAdapterError("Seed recognition differs across camera alignment")
            state = next(iter(values))
            if state is not None:
                crops[(tx, ty)] = state
            elif all(free):
                clear.add((tx, ty))
            elif ((tx, ty) in self.route_cells
                  and self._avatar_covers_footprint((tx*48, ty*48), player, uncertainty)):
                # Preserve only previously visible route identity beneath this
                # localized avatar. Other unknown terrain remains blocked.
                clear.add((tx, ty))
        # Stair corridor is observed at its actual location using shared clear
        # feature templates; it is never authorized just from a house label.
        if all(self._clear(image, ox, oy+48) for ox, oy in origins):
            clear.add((0, 1))
        self.observed_edges = set()
        edge_cells = clear & self.route_cells if self.route_config is not None else clear
        for a in edge_cells:
            for b in ((a[0]+1, a[1]), (a[0], a[1]+1)):
                if b not in edge_cells:
                    continue
                valid = True
                for step in range(49):
                    x, y = (a[j]*48+(b[j]-a[j])*step for j in (0, 1))
                    # The already localized avatar may cover terrain at its
                    # present footprint; every unobscured swept footprint must
                    # match. No edge is inferred merely from its endpoints.
                    if self._avatar_covers_footprint((x, y), player, uncertainty):
                        continue
                    if not all(self._clear(image, ox+x, oy+y) for ox, oy in origins):
                        valid = False
                        break
                if valid:
                    self.observed_edges.add(frozenset((a, b)))
        return crops, clear, origin, player, uncertainty

    def establish(self, image, *, screenshot: Path):
        crops, clear, _, player, uncertainty = self.scan(image)
        if max(map(abs, player))+uncertainty > 8:
            raise StardewAdapterError("Observed preparation has not reached the farmhouse return point")
        if not 1 <= len(crops) <= 15:
            raise StardewAdapterError("Support requires 1–15 visible spring seeds in the local farmhouse patch")
        route = scene_routes(clear, crops, edges=self.observed_edges)
        self.expected = set(crops)
        self.route_cells = {tuple(round(v/48) for v in pose) for pose in route['poses'].values()}
        self.route_config = route
        self.reviewed_edges = {frozenset(tuple(round(v/48) for v in route['poses'][name])
                               for name in edge) for edge in route['edges']}
        self.__dict__.pop('_activity_cells', None)
        self.__dict__.pop('_activity_edges', None)
        self.scene_receipt = {"schema": "stardew-selected-visible-scene/v1",
            "screenshot": str(screenshot), "sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
            "targets": [[*t, value] for t, value in sorted(crops.items())],
            "clear_cells": sorted(map(list, clear)), "route": route,
            "scope": "visible spring seed patch only", "execution_authority": False,
            "native_path_qualification": "pending"}
        return ViewpointNavigator(route)

    def review_targets(self, ids):
        """Bind terrain checks to approved approaches and their return paths."""
        route = self.route_config
        if not route or not ids or not set(ids) <= route['watering'].keys():
            raise StardewAdapterError('Reviewed targets have no observed approach')
        home = route['return_pose']
        queue, parents = [home], {home: None}
        adjacency = {name: set() for name in route['poses']}
        for a, b in route['edges']:
            adjacency[a].add(b)
            adjacency[b].add(a)
        for node in queue:
            for neighbor in sorted(adjacency[node]):
                if neighbor not in parents:
                    parents[neighbor] = node
                    queue.append(neighbor)
        cells, edges = {home}, set()
        def tile(name):
            return tuple(round(v/48) for v in route['poses'][name])
        for identity in ids:
            node = route['watering'][identity]
            while node != home:
                parent = parents[node]
                cells.add(node)
                edges.add(frozenset((tile(node), tile(parent))))
                node = parent
        self._activity_cells = {tile(name) for name in cells}
        self._activity_edges = edges

    def decode(self, image, *, resources=True, aiming_at=None):
        if self.route_config is None:
            raise StardewAdapterError("The selected scene has not passed observed support checks")
        crops, clear, origin, player, uncertainty = self.scan(image)
        # Occlusion may hide an already identified seed, never introduce a new
        # target. Existing history reconciliation remains in the shared reader.
        if not crops.keys() <= self.expected:
            raise StardewAdapterError("The selected scene acquired an unreviewed seed")
        for tile in self.expected-crops.keys():
            if abs(tile[0]*48-player[0]) <= 26 and -72 <= tile[1]*48-player[1] <= 20:
                crops[tile] = None
            else:
                raise StardewAdapterError("A selected seed disappeared; inspect before a fresh review")
        required_edges = getattr(self, '_activity_edges', self.reviewed_edges)
        required_cells = getattr(self, '_activity_cells', self.route_cells)
        if aiming_at is None and not required_edges <= self.observed_edges:
            raise StardewAdapterError("A swept approach corridor changed or became unknown")
        for tile in required_cells-clear:
            if tile == (0, 0):
                continue
            if self._avatar_covers_footprint((tile[0]*48, tile[1]*48), player, uncertainty):
                continue
            if aiming_at and abs(tile[0]-aiming_at[0]) <= 1 and abs(tile[1]-aiming_at[1]) <= 1:
                continue  # pointer-only supplementary frame; press rechecks unobscured terrain
            raise StardewAdapterError("Observed route terrain changed or became unknown")
        if (any(image.crop(box).tobytes() != value for box, value in self.toolbar_outline.items())
                or not self.can_core.matches(image.crop((510+self.tool_offset, 866, 550+self.tool_offset, 901)))
                or image.crop((500+self.tool_offset, 875, 505+self.tool_offset, 909)).tobytes() != self.selected_border):
            raise StardewAdapterError("The complete selected basic can is not visible in its supported toolbar slot")
        return {"origin": origin, "player": player, "uncertainty": uncertainty,
                "crops": crops, "obscured_obstacles": [],
                "energy": self.energy.recognize(image) if resources else None,
                "water": self.water.recognize(image) if resources else None}

    def retain(self, destination: Path):
        destination.write_text(json.dumps(self.scene_receipt, indent=2))
