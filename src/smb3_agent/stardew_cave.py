"""Entrance-only reconnaissance. Route evidence is independent of watering coverage."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from functools import lru_cache
import re
from uuid import uuid4

from PIL import Image

from smb3_agent.request_planning import ConversationPlan, PlannedAction
from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_inspection import InspectionNavigator
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator

@lru_cache(maxsize=512)
def _evidence_digest(path, identity):
    """Hash unchanged retained files once; every check re-reads file identity."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _current_digest(path):
    p = Path(path)
    stat = p.stat()
    return _evidence_digest(str(p), (stat.st_dev, stat.st_ino, stat.st_size,
                                   stat.st_mtime_ns, stat.st_ctime_ns))


DESTINATION = 'farm-cave'


def protected_crop_patch_visible(x, y, size):
    """Coverage excludes the calibrated toolbar, clock and energy overlays."""
    width, height = size
    if not 16 <= x < width-16 or not 16 <= y < 824:
        return False
    masks = ((1220, 0, width, 270), (1450, 690, width, height),
             (1235, 740, width, 824))
    return not any(x+15 >= left and x-15 < right and y+15 >= top and y-15 < bottom
                   for left, top, right, bottom in masks)

LABEL = 'Farm Cave entrance'
LIMITS = ('Observe the exterior only, then return to the farmhouse. No tools, combat, '
          'purchases or entry. Interior access, resources and hazards remain unknown; '
          'entering requires a further supported and approved plan.')
SETUP = ('Choose a fresh Day 2 disposable farm, Load the prepared farmer, use the visible '
         'preparation controls to reach the farmhouse porch, and connect screen recognition. '
         'The Farm Cave approach needs separate visible route qualification before Start is available.')


def cave_request(text):
    return bool(re.search(r'\b(cave|cavern|mines?|reconnaissance)\b', text.lower()))


def resolve_destination(text, previous=None):
    value = text.lower().strip(' ?.!')
    if re.search(r'\b(mine|mines|skull|desert|quarry|volcano)\b', value):
        return None, 'Only the Farm Cave entrance is in this activity. The Mines and other caves need their own supported approach. Choose Farm Cave to review that destination.'
    if 'farm' in value or value in {'the farm one', 'that one', 'the same one', 'continue', 'return', 'return home', 'continue return'} and previous == DESTINATION:
        return DESTINATION, None
    if previous == DESTINATION and ('that cave' in value or 'same cave' in value):
        return DESTINATION, None
    return None, 'Which cave do you mean: the Farm Cave on your farm, or the Mines? Initial coverage is the Farm Cave exterior only. Say “Farm Cave”.'


@dataclass(frozen=True)
class NavigationCoverage:
    """Current route view plus retained baseline identities, never fresh crop truth."""
    route_digest: str
    baseline: object
    hidden_ids: tuple[str, ...]

    def validate(self, screen):
        b = self.baseline
        if b.navigation_coverage is not None or not b.scene_complete or b.unknown_regions:
            raise StardewAdapterError("Navigation requires a complete protected-farm baseline.")
        if any(c.occluded or c.confidence != 1 for c in b.crops):
            raise StardewAdapterError("Navigation baseline has hidden protected crops.")
        if not re.fullmatch(r'[a-f0-9]{64}', self.route_digest):
            raise StardewAdapterError("Navigation coverage has no route identity.")
        if b.session_nonce != screen.session_nonce or b.save_tree_sha256 != screen.save_tree_sha256:
            raise StardewAdapterError("Navigation baseline belongs to another session.")
        if (b.window.process_id, b.window.process_started_at, b.window.window_id) != (
                screen.window.process_id, screen.window.process_started_at, screen.window.window_id):
            raise StardewAdapterError("Navigation baseline belongs to another game window.")
        if screen.observation_id == b.observation_id or datetime.fromisoformat(screen.observed_at) < datetime.fromisoformat(b.observed_at):
            raise StardewAdapterError("Navigation requires a new current observation.")
        if screen.energy != b.energy or screen.tool != b.tool:
            raise StardewAdapterError("Navigation changed protected resources.")
        initial = {c.crop_id: c for c in b.crops}
        if set(initial) != {c.crop_id for c in screen.crops}:
            raise StardewAdapterError("Navigation lost protected crop identities.")
        hidden = {c.crop_id for c in screen.crops if c.occluded}
        if screen.scene_complete != (not hidden):
            raise StardewAdapterError("Navigation scene completeness disagrees with coverage.")
        if hidden != set(self.hidden_ids) or set(screen.unknown_regions) != {f'navigation-hidden:{k}' for k in hidden}:
            raise StardewAdapterError("Navigation visibility labels do not reconcile.")
        for c in screen.crops:
            old = initial[c.crop_id]
            if (c.tile_x, c.tile_y, c.planted) != (old.tile_x, old.tile_y, old.planted):
                raise StardewAdapterError("Protected crop identity changed.")
            if c.occluded:
                if c.evidence_reference != old.evidence_reference or c.watered or c.confidence:
                    raise StardewAdapterError("Hidden crop must retain earlier evidence and unknown state.")
            elif c.watered != old.watered:
                raise StardewAdapterError("Protected crop changed during navigation.")
        p = screen.position
        if p.location != 'Farm' or any(v is None for v in (p.world_pixel_x, p.world_pixel_y, p.camera_origin_x, p.camera_origin_y)):
            raise StardewAdapterError("Navigation needs current exterior camera geometry.")


class CaveRoute:
    """Trusted local calibration, never browser-supplied coordinates or qualification.

    Each cardinal edge requires its own retained approach AND return record. The
    runtime observes current route geometry, resources and window every pulse;
    complete protected-farm coverage is required at baseline and final return.
    Patches are world-relative exterior/corridor pixels, not inferred walkability.
    """
    def __init__(self, manifest, *, profile_id):
        self.path = Path(manifest)
        self.raw = self.path.read_bytes()
        self.config = json.loads(self.raw)
        c = self.config
        if c.get('schema') != 'stardew-cave-route/v1' or c.get('profile_id') != profile_id:
            raise StardewAdapterError('Cave route does not match the connected farm profile.')
        if c.get('destination') != DESTINATION or c.get('classification') != 'actual_live':
            raise StardewAdapterError('Cave approach has no actual-live qualification.')
        self.navigator = ViewpointNavigator({**c, 'watering': {}})
        if c['return_pose'] != 'home' or 'entrance' not in self.navigator.poses:
            raise StardewAdapterError('Cave route must stop outside the entrance and return to the farmhouse.')
        required = {'approach', 'return', 'exterior', 'corridor', 'resources', 'handback'}
        if set(c.get('qualified_roles', [])) != required:
            raise StardewAdapterError('Cave route qualification is incomplete.')
        self.check()

    @property
    def digest(self):
        return hashlib.sha256(self.raw).hexdigest()

    def check(self):
        c = self.config
        if c != json.loads(self.raw):
            raise StardewAdapterError("Cave route configuration changed.")
        evidence = c.get('evidence_hashes', {})
        referenced = {c.get('qualification_record'), c.get('exterior', {}).get('image')}
        referenced.update(p["image"] for p in c.get("camera_anchors", []))
        referenced.update(p["image"] for p in c.get("avatar_references", []))
        records = c.get('edge_records', [])
        for a, b in c['edges']:
            pair = next((r for r in records if set(r.get('edge', [])) == {a, b}), None)
            if pair is None or not pair.get('patches') or not pair.get('approach') or not pair.get('return'):
                raise StardewAdapterError('Cave route lacks independently checked approach/return boundaries.')
            referenced.update([pair['approach'], pair['return']])
            referenced.update(p['image'] for p in pair['patches'])
        if not referenced or None in referenced or not referenced <= evidence.keys():
            raise StardewAdapterError('Cave route evidence is missing.')
        if self.path.read_bytes() != self.raw or any(not Path(p).is_file() or _current_digest(p) != h for p, h in evidence.items()):
            raise StardewAdapterError('Cave route evidence changed; qualify again.')

    def validate_view(self, screen):
        self.check()
        if screen.navigation_coverage is not None and screen.navigation_coverage.route_digest != self.digest:
            raise StardewAdapterError("Navigation observation belongs to another route.")
        if screen.position.location != "Farm":
            raise StardewAdapterError("Cave reconnaissance supports the farm exterior only.")
        node = self.navigator._nearest(screen)
        self.navigator._path(node, {'entrance'})
        self.navigator._path('entrance', {self.navigator.return_pose})
        # Every nearby edge must remain visually clear; missing camera coverage
        # refuses movement rather than inventing a bypass or using old imagery.
        for record in self.config['edge_records']:
            if node in record['edge']:
                visible = [p for p in record['patches'] if self.patch_visible(p, screen)]
                if not visible or not all(self.matches(p, screen) for p in visible):
                    raise StardewAdapterError('Cave approach boundary is hidden or changed. Take control and request a revised plan.')

    @staticmethod
    def patch_visible(patch, screen):
        p = screen.position
        if p.camera_origin_x is None or p.camera_origin_y is None:
            return False
        with Image.open(screen.screenshot_references[-1]) as image:
            width, height = image.size
        left = round(p.camera_origin_x + patch['world_origin'][0])
        top = round(p.camera_origin_y + patch['world_origin'][1])
        box = patch['reference_box']
        right, bottom = left+box[2]-box[0], top+box[3]-box[1]
        if left < 0 or top < 0 or right > width or bottom > min(height,824):
            return False
        masks = ((1220,0,width,270),(1450,690,width,height),(1235,740,width,824))
        return not any(right > x and left < r and bottom > y and top < b for x,y,r,b in masks)

    @staticmethod
    def matches(patch, screen):
        p = screen.position
        if p.camera_origin_x is None or p.camera_origin_y is None:
            return False
        with Image.open(screen.screenshot_references[-1]) as source, Image.open(patch['image']) as reference:
            image = source.convert('RGB')
            expected = reference.convert('RGB').crop(tuple(patch['reference_box']))
            x, y = patch['world_origin']
            left, top = round(p.camera_origin_x+x), round(p.camera_origin_y+y)
            box = (left, top, left+expected.width, top+expected.height)
            if left < 0 or top < 0 or box[2] > image.width or box[3] > image.height:
                return False
            if not patch.get('raster_phase_tolerance'):
                return image.crop(box).tobytes() == expected.tobytes()
            if patch['raster_phase_tolerance'] != 3:
                raise StardewAdapterError('Unsupported corridor raster tolerance.')
            from smb3_agent.stardew_perception import CameraAlignment
            template = CameraAlignment.calibrate(expected).template
            # Only boundary pixels affected by raster phase are excluded. The
            # independently bounded camera supplies placement, never a search
            # for an unrelated piece of terrain elsewhere on the screen.
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    shifted = (box[0]+dx, box[1]+dy, box[2]+dx, box[3]+dy)
                    if shifted[0] >= 0 and shifted[1] >= 0 and shifted[2] <= image.width and shifted[3] <= image.height and template.matches(image.crop(shifted)):
                        return True
            return False

    def findings(self, screen, *, session_id, baseline_id, baseline_time=None):
        self.check()
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(screen.observed_at)).total_seconds()
        if not 0 <= age <= 5 or screen.session_nonce != session_id or screen.observation_id == baseline_id:
            raise StardewAdapterError('Cave findings require a fresh independent view from this session.')
        if baseline_time is not None and datetime.fromisoformat(screen.observed_at) < datetime.fromisoformat(baseline_time):
            raise StardewAdapterError("Entrance capture predates observed arrival.")
        x, y = self.navigator.poses['entrance']
        p = screen.position
        if max(abs(x-p.world_pixel_x), abs(y-p.world_pixel_y))+p.pixel_uncertainty > 8:
            raise StardewAdapterError('Entrance observation requires independently observed arrival.')
        recognized = self.matches(self.config['exterior'], screen)
        image = Path(screen.screenshot_references[-1])
        import base64
        return {'observation': {'observation_id': screen.observation_id, 'observed_at': screen.observed_at,
                    'session_id': session_id, 'destination': DESTINATION,
                    'image': 'data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode(),
                    'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest()},
                'entrance': 'recognized exterior' if recognized else 'unknown',
                'interior_access': 'unknown', 'resources': 'unknown', 'hazards': 'unknown',
                'message': ('The Farm Cave exterior matches the supported entrance view. ' if recognized else
                            'The exterior appearance is changed or hidden; entrance recognition is unknown. ')+LIMITS}


def proposal(screen, route, text, conversation_id, *, return_only=False):
    if route is None:
        raise StardewAdapterError(SETUP)
    route.validate_view(screen)
    nav = route.navigator
    start = nav._nearest(screen)
    _, approach = nav._path(start, {nav.return_pose if return_only else 'entrance'})
    _, home = nav._path(nav.return_pose if return_only else 'entrance', {nav.return_pose})
    return ConversationPlan(plan_id='cave-'+uuid4().hex, request_id=uuid4().hex,
        original_request=text, conversation_id=conversation_id, game_id='stardew',
        session_id=screen.session_nonce, observation_id=screen.observation_id,
        requested_objective=('Return from the Farm Cave approach to the farmhouse; retain earlier findings.' if return_only else
                             'Visit the Farm Cave entrance, capture the exterior and return to the farmhouse.'),
        normalized_intent='inspect_cave', actions=(PlannedAction('cave', 'inspect', (),
            {'destination': DESTINATION, 'route_digest': route.digest, 'approach': [start, *approach],
             'return': [nav.return_pose if return_only else 'entrance', *home], 'return_only': return_only}),),
        resource_limits={'maximum_seconds': 600, 'tool_uses': 0, 'purchases': 0},
        stop_point='farmhouse_entrance', effective_boundary='exterior_only',
        fallback_explanation='Follow the separately verified exterior approach; stop outside the doorway. '+LIMITS,
        change_summary=(LIMITS, 'Pause the game clock between movement observations; discussion releases control with the game paused.'))


class CaveNavigator(InspectionNavigator):
    destination = 'entrance'
    maximum_total_pulses = 600
    maximum_pulse_ms = 250
    maximum_waypoint_pulses = 100


class CavePerception:
    """Route-only camera coverage; baseline crop pixels are explicitly historical."""
    def __init__(self, profile, route, baseline):
        baseline.validate(baseline.save_tree_sha256)
        if baseline.unknown_regions or baseline.navigation_coverage is not None:
            raise StardewAdapterError('Cave travel requires a complete fresh farm baseline.')
        self.profile, self.route, self.baseline = profile, route, baseline

    def recognize(self, screenshot, window, save):
        from dataclasses import replace
        import numpy as np
        from smb3_agent.stardew_perception import CameraAlignment
        self.route.check()
        image = Image.open(screenshot).convert('RGB')
        # Each additional anchor is a retained world-relative static feature.
        # At camera transitions, independently recognized anchors must agree.
        candidates = []
        anchors = [(self.profile.anchor, self.profile.anchor_box, self.profile.origin_reference)]
        for patch in self.route.config.get('camera_anchors', []):
            with Image.open(patch['image']) as reference:
                anchors.append((CameraAlignment.calibrate(reference.convert('RGB').crop(tuple(patch['reference_box']))),
                                patch['reference_box'], patch['origin_reference']))
        for anchor, box, origin in anchors:
            try:
                offsets = anchor.offsets(image)
            except StardewAdapterError:
                continue
            candidates.extend((x+origin[0]-box[0], y+origin[1]-box[1]) for x,y in offsets)
        if not candidates or any(max(p[j] for p in candidates)-min(p[j] for p in candidates)>3 for j in (0,1)):
            raise StardewAdapterError('Cave camera anchors are missing or disagree.')
        # Reuse the independent avatar detector and bounded raster geometry.
        class CurrentAnchor:
            def offsets(self, _):
                return tuple((x-self.profile.origin_reference[0]+self.profile.anchor_box[0],
                              y-self.profile.origin_reference[1]+self.profile.anchor_box[1]) for x,y in candidates)
        current_anchor = CurrentAnchor()
        current_anchor.profile = self.profile
        import copy
        geometry_profile = copy.copy(self.profile)
        geometry_profile.anchor = current_anchor
        clear_geometry = None
        try:
            clear_geometry = geometry_profile.geometry(image)
        except StardewAdapterError:
            pass
        if clear_geometry is not None:
            origins, (ox,oy), (px,py), uncertainty = clear_geometry
        elif self.route.config.get('avatar_references'):
            from smb3_agent.stardew_cave_avatar import locate_avatar
            (sx, sy), player_uncertainty = locate_avatar(image, self.route.config['avatar_references'])
            origins = candidates
            ox, oy = [(min(p[j] for p in candidates)+max(p[j] for p in candidates))/2 for j in (0, 1)]
            camera_interval = max(max(p[j] for p in candidates)-min(p[j] for p in candidates) for j in (0, 1))/2
            uncertainty = camera_interval+player_uncertainty
            if uncertainty > 3:
                raise StardewAdapterError('Cave camera/player interval is too wide.')
            px, py = sx-ox, sy-oy
        else:
            origins, (ox,oy), (px,py), uncertainty = geometry_profile.geometry(image)
        if not self.profile.tool_template.matches(image.crop(self.profile.tool_box)):
            raise StardewAdapterError('Selected tool changed during cave movement.')
        pixels = np.asarray(image)
        crops, hidden = [], []
        for old in self.baseline.crops:
            readings = []
            for cx,cy in origins:
                x,y = round(cx+48*old.tile_x), round(cy+48*old.tile_y)
                if not protected_crop_patch_visible(x, y, image.size):
                    readings.append(None)
                    continue
                patch = pixels[y-15:y+16,x-15:x+16]
                dry = int(np.count_nonzero(np.all(patch == (86,54,52),axis=2)))
                wet = int(np.count_nonzero(np.all(patch == (59,23,39),axis=2)))
                if max(dry,wet)>=25 and min(dry,wet)==0:
                    readings.append(bool(wet))
                elif -26<=old.tile_x*48-px<=26 and -72<=old.tile_y*48-py<=20:
                    readings.append(None)
                else:
                    raise StardewAdapterError('Visible protected crop changed or is unreadable.')
            visible = len(set(readings))==1 and readings[0] is not None
            if not visible:
                hidden.append(old.crop_id)
            crops.append(replace(old, watered=readings[0] if visible else False, occluded=not visible,
                                 confidence=1 if visible else 0,
                                 evidence_reference=str(screenshot) if visible else old.evidence_reference))
        from smb3_agent.stardew_adapter import PositionObservation
        screen = replace(self.baseline, observation_id=uuid4().hex,
                         observed_at=datetime.now(timezone.utc).isoformat(), window=window,
                         crops=tuple(crops), energy=self.profile.energy.recognize(image),
                         tool=replace(self.baseline.tool,watering_can_units=self.profile.water.recognize(image)),
                         position=PositionObservation('Farm',round(px/48),round(py/48),max(abs(px),abs(py))+uncertainty<=8,
                                                      1,px,py,uncertainty,ox,oy),
                         screenshot_references=(str(screenshot),), scene_complete=not hidden,
                         unknown_regions=tuple(f'navigation-hidden:{k}' for k in hidden),
                         navigation_coverage=NavigationCoverage(self.route.digest,self.baseline,tuple(hidden)))
        screen.validate(save.disposable_tree_sha256)
        self.route.validate_view(screen)
        return screen
