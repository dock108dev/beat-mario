"""Selected farm actions using the shared, observed viewpoint navigation."""
from smb3_agent.stardew_adapter import InputCommand, InputKind
from smb3_agent.stardew_farm_tasks import PURPOSES, TOOLS, require
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator


class FarmNavigator(ViewpointNavigator):
    def __init__(self, config):
        super().__init__(config)
        # Each supported action has its own retained approach/aim calibration.
        self.approaches = config["farm_approaches"]
        self.slot_points = {int(k): tuple(v) for k, v in config["inventory_slot_points"].items()}
        self.supported_actions = tuple(sorted(self.approaches))
        require(set(self.supported_actions) <= set(PURPOSES.values()), "unsupported farm route action")

    def validate_farm_scope(self, screen, plan):
        start = self._nearest(screen)
        for action in plan.actions:
            require(action.kind in self.approaches, "action lacks qualified live approach")
            for key in action.target_ids:
                route = self.approaches[action.kind].get(key)
                require(route is not None, "selected target lacks an action-specific approach")
                require(len(route["offset"]) == 2 and all(abs(v) <= 24 for v in route["offset"]), "invalid bounded target offset")
                self._path(start, {route["pose"]})
        self._path(start, {self.return_pose})

    def next_farm_command(self, screen, step):
        require(self._total_pulses <= 240, "bounded farm route input budget exhausted")
        # The runtime validates freshness before navigation and independently
        # verifies completion afterward. Completed farm work at the qualified
        # entrance needs no further waypoint alignment pulse.
        if step is None and screen.position.at_farmhouse_entrance is True:
            p = screen.position
            x, y = self.poses[self.return_pose]
            require(max(abs(x-p.world_pixel_x), abs(y-p.world_pixel_y))
                    + p.pixel_uncertainty <= 8, "reviewed return point is outside the qualified endpoint")
            return None, None
        if self._last_node is None:
            self._last_node = self._nearest(screen)
        route = self.approaches[step["kind"]][step["target_id"]] if step else None
        goal = route["pose"] if route else self.return_pose
        if self._waypoint is None:
            _, path = self._path(self._last_node, {goal})
            p = screen.position
            x, y = self.poses[goal]
            if path or max(abs(x-p.world_pixel_x), abs(y-p.world_pixel_y)) + p.pixel_uncertainty > 7:
                self._waypoint = path[0] if path else goal
                self._waypoint_pulses = 0
                self._progress.clear()
            elif step:
                target = next(t for t in screen.farm.targets if t.target_id == step["target_id"])
                # Geometry is checked on each actual frame, never inferred from
                # the requested movement or a pre-recorded route position.
                require(max(abs(target.tile_x*48-p.world_pixel_x), abs(target.tile_y*48-p.world_pixel_y))
                        + p.pixel_uncertainty <= 76, "selected target is outside bounded interaction reach")
                item = {"harvest": None, "plant": "parsnip_seeds", "water": "watering_can",
                        "clear": TOOLS.get(target.species)}[step["kind"]]
                bx, by, _, _ = screen.window.bounds
                if item and screen.farm.selected() != item:
                    slot = next((s.slot for s in screen.farm.inventory if s.item == item), None)
                    require(slot is not None and slot in self.slot_points, "owned item lacks visible selectable toolbar slot")
                    point = self.slot_points[slot]
                    return InputCommand(InputKind.MOUSE, "left_button", "click", 60,
                                        target=(bx+point[0], by+point[1]), purpose="select_farm_item",
                                        reviewed_crop_id=target.target_id), target.target_id
                point = (round(bx+p.camera_origin_x+target.tile_x*48+route["offset"][0]),
                         round(by+p.camera_origin_y+target.tile_y*48+route["offset"][1]))
                purpose = next(p for p, kind in PURPOSES.items() if kind == step["kind"])
                return InputCommand(InputKind.MOUSE, "right_button" if step["kind"] == "harvest" else "left_button",
                                    "click", 80, target=point, purpose=purpose,
                                    reviewed_crop_id=target.target_id), target.target_id
            else:
                require(screen.position.at_farmhouse_entrance is True, "reviewed return point is not visibly confirmed")
                return None, None
        return self.advance_to_waypoint(screen, True, lambda: self.next_farm_command(screen, step))
