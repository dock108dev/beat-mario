"""Entrance-only reconnaissance. Route evidence is independent of watering coverage."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from PIL import Image

from smb3_agent.request_planning import ConversationPlan, PlannedAction
from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_inspection import InspectionNavigator
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator

DESTINATION = 'farm-cave'
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


class CaveRoute:
    """Trusted local calibration, never browser-supplied coordinates or qualification.

    Each cardinal edge requires its own retained approach AND return record. The
    runtime still re-observes the complete farm, resources and window every pulse.
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
        records = c.get('edge_records', [])
        for a, b in c['edges']:
            pair = next((r for r in records if set(r.get('edge', [])) == {a, b}), None)
            if pair is None or not pair.get('patches') or not pair.get('approach') or not pair.get('return'):
                raise StardewAdapterError('Cave route lacks independently checked approach/return boundaries.')
            referenced.update([pair['approach'], pair['return']])
            referenced.update(p['image'] for p in pair['patches'])
        if not referenced or None in referenced or not referenced <= evidence.keys():
            raise StardewAdapterError('Cave route evidence is missing.')
        if self.path.read_bytes() != self.raw or any(not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest() != h for p, h in evidence.items()):
            raise StardewAdapterError('Cave route evidence changed; qualify again.')

    def validate_view(self, screen):
        self.check()
        if screen.position.location != "Farm":
            raise StardewAdapterError("Cave reconnaissance supports the farm exterior only.")
        node = self.navigator._nearest(screen)
        self.navigator._path(node, {'entrance'})
        self.navigator._path('entrance', {self.navigator.return_pose})
        # Every nearby edge must remain visually clear; missing camera coverage
        # refuses movement rather than inventing a bypass or using old imagery.
        for record in self.config['edge_records']:
            if node in record['edge'] and not all(self.matches(p, screen) for p in record['patches']):
                raise StardewAdapterError('Cave approach boundary is hidden or changed. Take control and request a revised plan.')

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
            return image.crop(box).tobytes() == expected.tobytes()

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
        resource_limits={'maximum_seconds': 120, 'tool_uses': 0, 'purchases': 0},
        stop_point='farmhouse_entrance', effective_boundary='exterior_only',
        fallback_explanation='Follow the separately verified exterior approach; stop outside the doorway. '+LIMITS,
        change_summary=(LIMITS,))


class CaveNavigator(InspectionNavigator):
    destination = 'entrance'
