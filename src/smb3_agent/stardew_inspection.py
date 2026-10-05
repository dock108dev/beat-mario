"""Reviewed Day 2 east-patch inspection on existing cardinal corridors."""
from datetime import datetime, timezone
from uuid import uuid4

from smb3_agent.request_planning import ConversationPlan, PlannedAction
from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator


DESTINATION = 'east-up'
SCOPE = 'Inspect the bare margin west of the eastern crop patch, including terrain, occupancy and access; return to the farmhouse entrance.'


def inspection_request(text):
    return any(word in text.lower() for word in ('inspect', 'inspection', 'take a walk', 'second viewpoint'))


def proposal(screen, navigator, text, conversation_id):
    if any(word in text.lower() for word in ('cave', 'pond', 'west of the house', 'south of')):
        raise StardewAdapterError('That area has no qualified inspection corridor. Ask to inspect the eastern crop margin.')
    if not isinstance(navigator, ViewpointNavigator) or DESTINATION not in navigator.poses:
        raise StardewAdapterError('Inspection walks currently require the supported Day 2 watering corridors.')
    start = navigator._nearest(screen)
    _, route = navigator._path(start, {DESTINATION})
    if not route:
        raise StardewAdapterError('Already at the inspection viewpoint; return to the porch for a new walk.')
    navigator._path(DESTINATION, {navigator.return_pose})
    return ConversationPlan(plan_id='inspection-'+uuid4().hex, request_id=uuid4().hex,
        original_request=text, conversation_id=conversation_id, game_id='stardew',
        session_id=screen.session_nonce, observation_id=screen.observation_id,
        requested_objective=SCOPE, normalized_intent='inspect_planting',
        actions=(PlannedAction(action_id='inspect', kind='inspect', target_ids=(),
            parameters={'destination': DESTINATION, 'route': [start, *route], 'scope': SCOPE}),),
        resource_limits={'maximum_seconds': 120}, stop_point='farmhouse_entrance',
        fallback_explanation='Walk past the mailbox along the known crop corridor, then north to the eastern patch. Observe two margin tiles; unrecognized terrain and access remain unknown. No tools, planting, clearing or purchases.',
        change_summary=(SCOPE,))


class InspectionNavigator(ViewpointNavigator):
    destination = DESTINATION
    maximum_total_pulses = 160

    def __init__(self, source):
        super().__init__({'poses': source.poses, 'edges': [(a,b) for a,ns in source.edges.items() for b in ns],
                          'watering': {}, 'return_pose': source.return_pose})
        self.observed = False

    def next_inspection_command(self, screen):
        if self.observed and screen.position.at_farmhouse_entrance:
            return None, "returned"
        if self._total_pulses > self.maximum_total_pulses:
            raise StardewAdapterError('Inspection movement budget exhausted.')
        if self._last_node is None:
            self._last_node = self._nearest(screen)
            p = screen.position
            x,y = self.poses[self._last_node]
            if max(abs(x-p.world_pixel_x), abs(y-p.world_pixel_y))+p.pixel_uncertainty > 8:
                self._waypoint = self._last_node
        if self._waypoint is None:
            goal, route = self._path(self._last_node, {self.return_pose if self.observed else self.destination})
            if not route:
                if self.observed and not screen.position.at_farmhouse_entrance:
                    raise StardewAdapterError('Inspection return is not independently confirmed.')
                return None, 'returned' if self.observed else 'observe'
            self._waypoint = route[0]
            self._waypoint_pulses = 0
            self._progress.clear()
        # Use the qualified eight-pixel arrival envelope at turns. A narrower
        # seven-pixel goal can demand an unnecessary minimum pulse and push an
        # otherwise qualified native position across the corridor boundary.
        p = screen.position
        x, y = self.poses[self._waypoint]
        if max(abs(x-p.world_pixel_x), abs(y-p.world_pixel_y)) + p.pixel_uncertainty <= 8:
            self._last_node, self._waypoint = self._waypoint, None
            self._progress.clear()
            return self.next_inspection_command(screen)
        return self.advance_to_waypoint(screen, True, lambda: self.next_inspection_command(screen))


def fresh_findings(observation, session_id, baseline_id):
    age = (datetime.now(timezone.utc)-datetime.fromisoformat(observation['observed_at'])).total_seconds()
    if not 0 <= age <= 5 or observation['session_id'] != session_id or observation['observation_id'] == baseline_id:
        raise StardewAdapterError('Inspection needs a fresh observation from this disposable session.')
    targets = [t for t in observation['targets'] if t['id'].startswith('east-margin-')]
    if len(targets) != 2:
        raise StardewAdapterError('The second viewpoint has no qualified margin coverage.')
    message = ' '.join(f"{t['label']}: {t['state'].replace('_', ' ')}." for t in targets)
    return {'observation': observation, 'message': message + ' Access to these tiles remains unknown; no planting location or farm-work authority is granted.'}
