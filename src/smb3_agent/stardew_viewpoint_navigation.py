"""Closed-loop navigation between visibly qualified watering viewpoints."""

from collections import deque
import heapq

from smb3_agent.stardew_adapter import InputCommand, InputKind, StardewAdapterError


class ViewpointNavigator:
    energy_cost_upper_bound = 2

    def __init__(self, config):
        self.poses = {key: tuple(value) for key, value in config["poses"].items()}
        self.edges = {key: set() for key in self.poses}
        for left, right in config["edges"]:
            if left not in self.poses or right not in self.poses:
                raise StardewAdapterError("unknown calibrated route endpoint")
            a, b = self.poses[left], self.poses[right]
            if a[0] != b[0] and a[1] != b[1]:
                raise StardewAdapterError(
                    "only cardinal approach corridors are qualified"
                )
            self.edges[left].add(right)
            self.edges[right].add(left)
        self.watering = dict(config["watering"])
        self.return_pose = config["return_pose"]
        self._waypoint = None
        self._waypoint_pulses = 0
        self._last_node = None
        self._progress = deque(maxlen=4)
        self._total_pulses = 0
        self._last_complete_node = None
        self._observation_return = None
        self._remaining_count = None

    def reset(self):
        self._waypoint = self._last_node = None
        self._waypoint_pulses = self._total_pulses = 0
        self._progress.clear()
        self._last_complete_node = self._observation_return = None
        self._remaining_count = None

    def _nearest(self, screen):
        p = screen.position
        if p.world_pixel_x is None or p.pixel_uncertainty is None:
            raise StardewAdapterError("current bounded pixel position is required")

        def distance(key):
            x, y = self.poses[key]
            return (
                max(abs(x - p.world_pixel_x), abs(y - p.world_pixel_y))
                + p.pixel_uncertainty
            )

        key = min(self.poses, key=distance)
        if distance(key) > 8:
            raise StardewAdapterError(
                "player is outside a qualified observation viewpoint; reposition before review"
            )
        return key

    def _path(self, start, goals):
        queue, best = [(0, start, [])], {start: 0}
        while queue:
            distance, node, path = heapq.heappop(queue)
            if distance != best[node]:
                continue
            if node in goals:
                return node, path
            for nxt in sorted(self.edges[node]):
                length = sum(abs(a-b) for a,b in zip(self.poses[node], self.poses[nxt], strict=True))
                candidate = distance + length
                if candidate < best.get(nxt, float('inf')):
                    best[nxt] = candidate
                    heapq.heappush(queue, (candidate, nxt, path + [nxt]))
        raise StardewAdapterError(
            "no qualified approach and return route for the complete task"
        )

    def validate_scope(self, screen):
        start = self._nearest(screen)
        for crop in screen.crops:
            if crop.planted:
                if crop.crop_id not in self.watering:
                    raise StardewAdapterError(
                        "initial crop lacks a qualified watering viewpoint"
                    )
                self._path(start, {self.watering[crop.crop_id]})
        self._path(start, {self.return_pose})

    def _clear_observation_pose(self, screen, node):
        # The calibrated avatar can cover seeds within x +/-26 and y -72..20
        # from its feet. Include the entire 8px arrival envelope: a lucky clear
        # frame near a pose's edge cannot qualify its center as a recovery view.
        # This only selects a candidate; arrival still requires visible crops.
        x, y = self.poses[node]
        return not any(c.planted and abs(c.tile_x * 48 - x) <= 34
                       and -80 <= c.tile_y * 48 - y <= 28
                       for c in screen.crops)

    def next_command(self, screen, remaining):
        p = screen.position
        if screen.tool.selected_tool != "watering_can":
            raise StardewAdapterError("equipped tool changed")
        if self._total_pulses > 240:
            raise StardewAdapterError("bounded route input budget exhausted")
        if self._last_node is None:
            self._last_node = self._nearest(screen)
        hidden = any(c.occluded for c in screen.crops)
        if (self._remaining_count is not None and len(remaining) < self._remaining_count
                and hidden):
            if self._last_complete_node is None:
                raise StardewAdapterError("no previously visible observation viewpoint")
            self._observation_return = self._last_complete_node
            self._waypoint = None
        self._remaining_count = len(remaining)
        if self._waypoint is None:
            if not hidden and self._clear_observation_pose(screen, self._last_node):
                self._last_complete_node = self._last_node
            goals = (
                {self._observation_return} if self._observation_return else
                {self.watering[key] for key in remaining}
                if remaining
                else {self.return_pose}
            )
            goal, path = self._path(self._last_node, goals)
            if path:
                self._waypoint = path[0]
                self._waypoint_pulses = 0
                self._progress.clear()
            else:
                x, y = self.poses[goal]
                if (
                    max(abs(x - p.world_pixel_x), abs(y - p.world_pixel_y))
                    + p.pixel_uncertainty
                    > 8
                ):
                    self._waypoint = goal
                elif self._observation_return:
                    if hidden:
                        raise StardewAdapterError("observation return did not restore complete crop visibility")
                    self._observation_return = None
                    return self.next_command(screen, remaining)
                elif remaining:
                    candidates = [
                        key for key in sorted(remaining) if self.watering[key] == goal
                    ]
                    visible = {c.crop_id for c in screen.crops if not c.occluded}
                    key = next(
                        (key for key in candidates if key in visible), candidates[0]
                    )
                    crop = next(c for c in screen.crops if c.crop_id == key)
                    if crop.occluded or crop.confidence != 1:
                        # Small observed alignment correction may restore a seed
                        # at the edge of the avatar. Never click an unseen target.
                        if max(abs(x - p.world_pixel_x), abs(y - p.world_pixel_y)) <= 2:
                            raise StardewAdapterError(
                                "reviewed target remains hidden at its qualified viewpoint"
                            )
                        self._waypoint = goal
                    else:
                        if (
                            screen.tool.watering_can_units is None
                            or screen.tool.watering_can_units < 1
                        ):
                            raise StardewAdapterError(
                                "watering can is empty or unknown"
                            )
                        bx, by, _, _ = screen.window.bounds
                        point = (
                            round(bx + p.camera_origin_x + crop.tile_x * 48 - 20),
                            round(by + p.camera_origin_y + crop.tile_y * 48 + 20),
                        )
                        return InputCommand(
                            InputKind.MOUSE,
                            "left_button",
                            "click",
                            80,
                            target=point,
                            purpose="water_crop",
                            reviewed_crop_id=key,
                        ), key
                elif p.at_farmhouse_entrance and not any(
                    c.occluded for c in screen.crops
                ):
                    return None, None
                else:
                    raise StardewAdapterError(
                        "reviewed return or complete final visibility is not confirmed"
                    )
        visible_here = any(
            c.crop_id in remaining
            and not c.occluded
            and self.watering[c.crop_id] == self._waypoint
            for c in screen.crops
        )
        return self.advance_to_waypoint(screen, visible_here, lambda: self.next_command(screen, remaining))

    def advance_to_waypoint(self, screen, visible_here, on_arrival):
        """Shared observed movement; callers own action-specific target eligibility."""
        p = screen.position
        goal = self.poses[self._waypoint]
        delta = (goal[0] - p.world_pixel_x, goal[1] - p.world_pixel_y)
        distance = max(map(abs, delta))
        fine_alignment = self._waypoint == self._last_node
        arrived = distance + p.pixel_uncertainty <= (8 if fine_alignment else 7)
        if fine_alignment and not visible_here:
            arrived = distance <= 2
        if arrived:
            self._last_node, self._waypoint = self._waypoint, None
            self._progress.clear()
            return on_arrival()
        # Remain inside the calibrated straight corridor; no obstacle bypass is
        # invented from a timer or a stalled movement event.
        origin = self.poses[self._last_node]
        if self._waypoint != self._last_node:
            perpendicular = 0 if origin[0] == goal[0] else 1
            if (
                abs(
                    (p.world_pixel_x, p.world_pixel_y)[perpendicular]
                    - origin[perpendicular]
                )
                + p.pixel_uncertainty
                > 8
            ):
                raise StardewAdapterError(
                    "player deviated outside the qualified approach corridor"
                )
        self._waypoint_pulses += 1
        self._total_pulses += 1
        if self._waypoint_pulses > 40:
            raise StardewAdapterError("viewpoint positioning failed to converge")
        self._progress.append((p.world_pixel_x, p.world_pixel_y))
        if (
            len(self._progress) == 4
            and max(
                max(v[j] for v in self._progress) - min(v[j] for v in self._progress)
                for j in (0, 1)
            )
            <= 2 * p.pixel_uncertainty
        ):
            raise StardewAdapterError(
                "no observed progress through the qualified corridor"
            )
        axis = 0 if abs(delta[0]) > abs(delta[1]) else 1
        key = (
            ("d" if delta[0] > 0 else "a")
            if axis == 0
            else ("s" if delta[1] > 0 else "w")
        )
        duration = min(40, max(15, int(abs(delta[axis]) * 2)))
        return InputCommand(
            InputKind.KEYBOARD, key, "press", duration, purpose="navigate"
        ), None
