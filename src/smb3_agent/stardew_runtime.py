"""Stardew-owned reviewed watering runtime. No Mario authority is reused.

A configured runtime receives an OS-verified isolated setup, a qualified visible
observer and ordinary input. The public default remains inspectable/unavailable.
Each tick is one bounded input followed by an exact visible postcondition; no
command queue survives pause, reclaim, focus loss, or session reset.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from smb3_agent.failure_diagnostics import log_failure
from smb3_agent.request_planning import ConversationPlan, PlanningContext
from smb3_agent.stardew_adapter import InputCommand, InputKind, InputOwner, OrdinaryInputDriver, ScreenObservation, StardewAdapterError
from smb3_agent.stardew_companion import StardewCompanionController, attempt_payload
from smb3_agent.stardew_farm_tasks import FARM_CONTRACT, FarmLedger, FarmObservation


LOGGER = logging.getLogger(__name__)


def plan_digest(plan: ConversationPlan) -> str:
    return hashlib.sha256(json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class WateringNavigator:
    """Single viewport, known walkable tiles, basic can, no refill or auto-tool change.

    Navigation emits a short pulse toward the next safe tile. Every pulse must
    visibly advance position. No open-loop path is queued and no crop can be
    treated as a walkable tile by accident.
    """
    def __init__(self, walkable: set[tuple[int, int]], centers: dict[tuple[int, int], tuple[int, int]],
                 return_tile: tuple[int, int], *, pulse_ms: int = 80, energy_cost_upper_bound: int | None = None) -> None:
        if not 1 <= pulse_ms <= 100:
            raise StardewAdapterError("navigation pulses must be bounded to 100 ms")
        self.walkable, self.centers, self.return_tile = set(walkable), dict(centers), return_tile
        if energy_cost_upper_bound is not None and (type(energy_cost_upper_bound) is not int or energy_cost_upper_bound < 0):
            raise StardewAdapterError("energy cost bound must be a known nonnegative integer")
        self.energy_cost_upper_bound = energy_cost_upper_bound
        self.pulse_ms = pulse_ms
        self._waypoint = None
        self._waypoint_pulses = 0

    def agent_context(self):
        return {"units": "tiles", "walkable": sorted(self.walkable), "return_tile": self.return_tile}

    def validate_scope(self, screen: ScreenObservation) -> None:
        """Reject an incomplete route before acquiring execution authority.

        This navigator supports cardinal watering from non-crop tiles only.
        A physically walkable crop tile is not implicitly a qualified viewing
        position: the player can hide its seed and invalidate complete coverage.
        """
        crops = [crop for crop in screen.crops if crop.planted]
        walkable = self.walkable - {(crop.tile_x, crop.tile_y) for crop in crops}
        start = screen.position.tile_x, screen.position.tile_y
        if start not in walkable or self.return_tile not in walkable:
            raise StardewAdapterError("player or reviewed return is outside the verified walkable corridor")
        reachable, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                tile = x + dx, y + dy
                if tile in walkable and tile not in reachable:
                    reachable.add(tile)
                    queue.append(tile)
        if self.return_tile not in reachable:
            raise StardewAdapterError("reviewed farmhouse return is unreachable")
        for crop in crops:
            if not crop.watered and not any((crop.tile_x + dx, crop.tile_y + dy) in reachable
                                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                raise StardewAdapterError(f"crop {crop.crop_id} has no reachable qualified watering position")

    def next_command(self, screen: ScreenObservation, remaining: set[str]) -> tuple[InputCommand | None, str | None]:
        if screen.position.world_pixel_x is not None:
            return self._pixel_next_command(screen, remaining)
        start = (screen.position.tile_x, screen.position.tile_y)
        crops = {c.crop_id: c for c in screen.crops if c.planted}
        if screen.tool.selected_tool != "watering_can":
            raise StardewAdapterError("select the watering can visibly before reviewing watering")
        if remaining and (screen.tool.watering_can_units is None or screen.tool.watering_can_units < 1):
            raise StardewAdapterError("can water exhausted; a visibly qualified refill route is unavailable")
        target = next((crops[key] for key in sorted(remaining) if key in crops), None)
        if remaining and target is None:
            raise StardewAdapterError("reviewed target disappeared")
        goal = (target.tile_x, target.tile_y) if target else self.return_tile
        if target and abs(start[0] - goal[0]) + abs(start[1] - goal[1]) == 1:
            if goal not in self.centers:
                raise StardewAdapterError("reviewed crop screen coordinate is unavailable")
            return InputCommand(InputKind.MOUSE, "left_button", "click", target=self.centers[goal], purpose="water_crop", reviewed_crop_id=target.crop_id), target.crop_id
        if not target and start == goal:
            return None, None
        destinations = {goal} if target is None else {(goal[0]+dx, goal[1]+dy) for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))}
        planted_tiles = {(c.tile_x, c.tile_y) for c in crops.values()}
        walkable = self.walkable - planted_tiles
        queue = deque([(start, [])])
        seen = {start}
        path = None
        while queue:
            tile, steps = queue.popleft()
            if tile in destinations and steps:
                path = steps
                break
            for dx, dy, key in ((1,0,"right"),(-1,0,"left"),(0,1,"down"),(0,-1,"up")):
                candidate = tile[0]+dx, tile[1]+dy
                if candidate in walkable and candidate not in seen:
                    seen.add(candidate)
                    queue.append((candidate, steps + [key]))
        if not path:
            raise StardewAdapterError("no reviewed unobstructed path to target or return point")
        # Multi-step return uses navigate; the final visible position decides completion.
        return InputCommand(InputKind.KEYBOARD, {"right": "d", "left": "a", "up": "w", "down": "s"}[path[0]], "press", self.pulse_ms, purpose="navigate"), None

    def _pixel_next_command(self, screen, remaining):
        """Reobserve sub-tile progress; never infer arrival from pulse duration."""
        p = screen.position
        values = (p.world_pixel_x, p.world_pixel_y, p.pixel_uncertainty, p.camera_origin_x, p.camera_origin_y)
        if any(v is None for v in values) or not 0 <= p.pixel_uncertainty <= 3:
            raise StardewAdapterError("bounded visible sub-tile position is required")
        if screen.tool.selected_tool != "watering_can":
            raise StardewAdapterError("select the watering can before review")
        start = p.tile_x, p.tile_y
        crops = {c.crop_id: c for c in screen.crops if c.planted}
        walkable = self.walkable - {(c.tile_x, c.tile_y) for c in crops.values()}
        if start not in walkable:
            raise StardewAdapterError("player is outside the verified walkable corridor")
        if self._waypoint is not None:
            if self._waypoint not in walkable:
                raise StardewAdapterError("navigation waypoint became obstructed")
            delta = self._waypoint[0]*48-p.world_pixel_x, self._waypoint[1]*48-p.world_pixel_y
            if max(map(abs, delta)) + p.pixel_uncertainty <= 8:
                self._waypoint = None
                self._waypoint_pulses = 0
            else:
                self._waypoint_pulses += 1
                if self._waypoint_pulses > 8:
                    raise StardewAdapterError("navigation failed to converge on the visible waypoint")
                axis = 0 if abs(delta[0]) > abs(delta[1]) else 1
                key = ('d' if delta[0] > 0 else 'a') if axis == 0 else ('s' if delta[1] > 0 else 'w')
                duration = min(self.pulse_ms, max(30, int(abs(delta[axis])*2)))
                return InputCommand(InputKind.KEYBOARD, key, 'press', duration, purpose='navigate'), None
        target = next((crops[key] for key in sorted(remaining) if key in crops), None)
        if remaining and target is None:
            raise StardewAdapterError("reviewed target disappeared")
        if remaining and (screen.tool.watering_can_units is None or screen.tool.watering_can_units < 1):
            raise StardewAdapterError("watering can is empty or unknown")
        goal = (target.tile_x, target.tile_y) if target else self.return_tile
        if target and abs(start[0]-goal[0]) + abs(start[1]-goal[1]) == 1:
            if max(abs(p.world_pixel_x-start[0]*48), abs(p.world_pixel_y-start[1]*48)) + p.pixel_uncertainty > 8:
                self._waypoint = start
                return self._pixel_next_command(screen, remaining)
            bx, by, _, _ = screen.window.bounds
            point = (round(bx+p.camera_origin_x+goal[0]*48), round(by+p.camera_origin_y+goal[1]*48))
            return InputCommand(InputKind.MOUSE, 'left_button', 'click', 80, target=point, purpose='water_crop', reviewed_crop_id=target.crop_id), target.crop_id
        if target is None and start == goal:
            if p.at_farmhouse_entrance:
                return None, None
            if max(abs(p.world_pixel_x-goal[0]*48), abs(p.world_pixel_y-goal[1]*48)) + p.pixel_uncertainty <= 8:
                raise StardewAdapterError("return marker disagrees with visible arrival geometry")
            self._waypoint = goal
            return self._pixel_next_command(screen, remaining)
        destinations = {goal} if target is None else {(goal[0]+dx, goal[1]+dy) for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))}
        queue, seen = deque([(start, [])]), {start}
        while queue:
            tile, path = queue.popleft()
            if tile in destinations and path:
                self._waypoint = path[0]
                return self._pixel_next_command(screen, remaining)
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nxt = tile[0]+dx, tile[1]+dy
                if nxt in walkable and nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, path+[nxt]))
        raise StardewAdapterError("no verified unobstructed path to target or return point")


class StardewRuntime:
    def __init__(self, *, setup=None, controller: StardewCompanionController | None = None,
                 observer: Callable[[], ScreenObservation] | None = None,
                 driver: OrdinaryInputDriver | None = None, navigator: WateringNavigator | None = None,
                 evidence_root: Path | None = None, maximum_observation_age: float = 2.0) -> None:
        if maximum_observation_age <= 0 or maximum_observation_age > 5:
            raise StardewAdapterError("observation freshness must be bounded to five seconds")
        self.setup_manager = setup
        self.controller, self.observer, self.driver, self.navigator = controller, observer, driver, navigator
        self.evidence_root = evidence_root
        self.maximum_observation_age = maximum_observation_age
        self.gameplay_agent = None
        self.screen: ScreenObservation | None = None
        self.current_plan: ConversationPlan | None = None
        self._review_digest: str | None = None
        self._review_screen: ScreenObservation | None = None
        self.status = "unconfigured"
        self.reason = "Select an authorized disposable session and verify actual isolated game loading, then qualify visible perception."
        self._cancel = threading.Event()
        self._lock = threading.RLock()
        self._authority_lock = threading.RLock()
        self._generation = 0
        self._pending_navigation_observation = None
        self._tick_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._evidence_files: list[str] = []
        self.evidence_error: str | None = None
        self._paused_scope: tuple[str, ...] | None = None
        self._planting_observer = None
        self._goal_preparation = None
        self.preparation_view = None
        self._survey_paused = False
        self._preparation_driver = None
        self._preparation_neutral_failure = None
        self.cave_result = None
        self._cave_navigation = None
        self._cave_route = None
        self._cave_observer = None
        self._cave_resume_clock = None
        self._inference_clock = None
        self._cave_baseline = None
        self.inspection_result = None
        self._inspection_navigation = None
        self._activate_game: Callable[[], None] | None = None
        self._engineering_launches: list[tuple[object, object]] = []
        self._retired_attempts: list[dict] = []
        self._qualified_profiles: dict[str, tuple[object, WateringNavigator, str, Path]] = {}

    def register_qualified_profile(self, profile, navigator: WateringNavigator, *, evidence_root: Path) -> None:
        """Internal calibration handoff; browser requests cannot supply profiles."""
        if self.status in {"running", "stopping"} or self._tick_lock.locked():
            raise StardewAdapterError("neutral handback is required before calibration changes")
        session = getattr(self.setup_manager, "session", None)
        if session is None or not session.input_ready or not profile.qualified():
            raise StardewAdapterError("verified farm and retained actual-live calibration are required")
        self._qualified_profiles[profile.profile_id] = (profile, navigator, session.session_id, Path(evidence_root))

    def _profile_options(self) -> list[dict]:
        session = getattr(self.setup_manager, "session", None)
        if session is None or not session.input_ready:
            return []
        return [{"profile_id": key, "label": key, "session_id": nonce}
                for key, (profile, _, nonce, _) in self._qualified_profiles.items()
                if nonce == session.session_id and profile.qualified()]

    def connect_profile(self, profile_id: str) -> dict:
        if self.status in {"running", "stopping"} or self._tick_lock.locked():
            raise StardewAdapterError("neutral handback is required before calibration connection")
        if profile_id not in {row["profile_id"] for row in self._profile_options()}:
            raise StardewAdapterError("no qualified calibration exists for this farm session")
        profile, navigator, _, root = self._qualified_profiles[profile_id]
        # Connecting is an explicit user action; background polling never focuses.
        loading = self.setup_manager.session.loading
        from smb3_agent.stardew_adapter import MacVisibleStardewBackend
        native = MacVisibleStardewBackend(process_id=loading.process_id, process_started_at=loading.process_started_at)
        # The browser may hide an isolated full-screen SDL window. Explicit
        # connection focuses the already verified process before enumeration.
        window = native.activate_window()
        if window.window_id != loading.window_id:
            raise StardewAdapterError("verified game window changed before calibration connection")
        return self.connect_live(profile=profile, navigator=navigator, evidence_root=root)

    def show_engineering_game(self) -> dict:
        """Focus only the identified disposable process; send no gameplay input."""
        if not self._engineering_launches:
            raise StardewAdapterError("Open a fresh disposable farm or reconnect its open game first.")
        self.control("pause", reason="Showing the disposable game; prior review is canceled.")
        launch, process = self._engineering_launches[-1]
        if process.poll() is not None:
            raise StardewAdapterError("The disposable game has exited. Open a fresh farm copy.")
        from smb3_agent.stardew_adapter import MacVisibleStardewBackend
        from smb3_agent.stardew_setup import _verify_engineering_launch_identity
        native = MacVisibleStardewBackend(process_id=launch.process_id, process_started_at=launch.process_started_at)
        window = native.activate_window()
        _verify_engineering_launch_identity(launch, window)
        self.reason = "Disposable game shown. Choose Load → Pilot/B3Test, walk out to the porch and select the watering can. Then Check isolated farm session and connect its qualified profile. No watering permission granted."
        return self.snapshot()

    def prepare_engineering(self, step, expected_view=None):
        """Player-directed setup pulses, always bound to a displayed disposable view."""
        import base64
        import time
        from smb3_agent.stardew_adapter import MacVisibleStardewBackend
        from smb3_agent.stardew_input import MacOrdinaryInputDriver
        from smb3_agent.stardew_setup import _verify_engineering_launch_identity
        if step not in {"view", "window", "load", "choose", "left", "right", "up", "down", "up_short", "left_short", "right_short", "down_short", "up_fine", "left_micro", "right_micro", "up_micro", "down_micro", "can", "menu", "survey_pause"}:
            raise StardewAdapterError("Unsupported preparation step.")
        if (self.controller and step not in {"view", "menu"}) or self.status in {"running", "stopping"} or self._tick_lock.locked():
            raise StardewAdapterError("Preparation controls are available only before screen connection.")
        if step != "view" and (not self.preparation_view or expected_view != self.preparation_view["id"]):
            raise StardewAdapterError("Refresh and inspect the preparation screen before each step.")
        self.show_engineering_game()
        launch, process = self._engineering_launches[-1]
        generation = self._generation
        native = MacVisibleStardewBackend(process_id=launch.process_id, process_started_at=launch.process_started_at)
        def guard(window):
            _verify_engineering_launch_identity(launch, window)
            if generation != self._generation or process.poll() is not None:
                raise StardewAdapterError("Preparation interrupted.")
        def authority():
            if generation != self._generation:
                raise StardewAdapterError("Preparation canceled.")
        driver = MacOrdinaryInputDriver(window_provider=native.detect_window,
            isolation_guard=guard, authority_guard=authority)
        self._preparation_driver = driver
        try:
            window = native.detect_window()
            guard(window)
            supported = window.bounds == (0, 33, 1512, 949)
            if step not in {"view", "window"} and not supported:
                raise StardewAdapterError(f"Current game window is {window.bounds}; preparation requires 1512×949 at (0,33). View preparation screen, restore the declared window/display settings in the game, then View again. No preparation input sent.")
            if step != "view" and self.preparation_view.get("window") != asdict(window):
                raise StardewAdapterError("The game window changed since the displayed preparation image. View preparation screen again before choosing a step.")
            driver.expected_pointer_window = window
            if step == "window" and window.bounds != (232, 132, 1280, 748):
                raise StardewAdapterError("Window recovery supports only the displayed centered 1280×748 title window on the qualified Mac display. Other display layouts require manual Windowed Borderless settings, then a fresh View.")
            survey = self._survey_paused or step == "survey_pause"
            def menu():
                authority()
                driver.arm()
                driver.send(InputCommand(InputKind.KEYBOARD, "escape", "press", 50, purpose="prepare_disposable"))
                driver.neutralize()
                time.sleep(0.2)  # Let the game finish its menu transition before observing or walking.
            if self._survey_paused:
                menu()
                self._survey_paused = False
            if step not in {"view", "survey_pause"}:
                if step in {"left", "right", "up", "down", "up_short", "left_short", "right_short", "down_short", "up_fine", "left_micro", "right_micro", "up_micro", "down_micro"}:
                    for _ in range(1 if step.endswith("_short") or step in {"up_fine", "left_micro", "right_micro", "up_micro", "down_micro"} else 8):
                        authority()
                        driver.arm()
                        driver.send(InputCommand(InputKind.KEYBOARD, ("a" if step.startswith("left") else "d" if step.startswith("right") else "w" if step.startswith("up") else "s"), "press", 15 if step.endswith("_micro") else 50 if step == "up_fine" else 100, purpose="prepare_disposable"))
                        driver.neutralize()
                elif step == "menu":
                    if not survey:
                        menu()
                    survey = False
                else:
                    points = {"load": (630, 835), "choose": (680, 270), "can": (531, 895), "window": (1478, 161)}
                    x,y = points[step]
                    target = (x, y+33)
                    if step == "window":
                        target = (1478, 194)
                    driver.arm()
                    # SDL menu hit-testing follows motion, not the coordinates
                    # carried by a button event. Bind both to the displayed frame.
                    driver.send(InputCommand(InputKind.MOUSE, "move", "move", 0,
                        target=target, purpose="prepare_disposable"))
                    time.sleep(0.08)
                    authority()
                    driver.send(InputCommand(InputKind.MOUSE, "left_button", "click", 50,
                        target=target, purpose="prepare_disposable"))
                driver.neutralize()
                time.sleep(0.3)
            current = native.detect_window()
            capture = native.capture(current, Path(launch.root) / f"preparation-{uuid4().hex}.png")
            authority()
            paused_capture = None
            if survey:
                menu()
                self._survey_paused = True
                paused_capture = native.capture(native.detect_window(), Path(launch.root) / f"survey-paused-{uuid4().hex}.png")
            self.preparation_view = {"id": uuid4().hex, "image": "data:image/png;base64,"+base64.b64encode(capture.read_bytes()).decode(),
                "screenshot": str(capture), "step": step, "window": asdict(current), "supported_geometry": current.bounds == (0, 33, 1512, 949), "input_released": True, "clock_paused_after_capture": self._survey_paused, "paused_screenshot": str(paused_capture) if paused_capture else None}
            self.reason = ("Survey clock paused after this capture. Walk/View briefly resumes, captures and pauses again; Menu ends survey pause. " if self._survey_paused else "") + "Check the displayed game screen before choosing the next preparation step. Steps release input; no farm-work authority."
            if current.bounds != (0, 33, 1512, 949):
                self.reason = f"Unsupported game window {current.bounds}. Farm preparation remains disabled. On the centered title screen, choose Restore supported window, then View again; this presses only the visible window-mode icon. Other layouts require manual Windowed Borderless settings. Use the qualified 3024×1964 display, 75% zoom and 100% UI."
        except StardewAdapterError as exc:
            if step != "window" or str(exc) not in {"window_loss"}:
                raise
            self.preparation_view = None
            self.reason = "Window-mode transition was attempted and input released. Choose View preparation screen to verify the current window before any further setup step. No farm-work authority granted."
            (Path(launch.root) / f"window-transition-{uuid4().hex}.json").write_text(json.dumps({
                "step": step, "outcome": "refresh_required", "reason": str(exc),
                "process_id": launch.process_id, "process_started_at": launch.process_started_at,
                "input_authority": False,
            }, indent=2))
        finally:
            driver.neutralize()
            self._preparation_driver = None
        return self.snapshot()

    def verify_engineering_session(self, *, preserve_preparation=False) -> dict:
        if self.status in {"running", "stopping"} or self._tick_lock.locked():
            raise StardewAdapterError("neutral handback is required before setup verification")
        if self._survey_paused:
            raise StardewAdapterError("End the survey pause with Toggle game menu before checking the farm. The paused screen and input ownership are retained.")
        if not self._engineering_launches or self.setup_manager is None:
            raise StardewAdapterError("open a dedicated engineering game before verifying its farm")
        launch, process = self._engineering_launches[-1]
        if process.poll() is not None:
            raise StardewAdapterError("the engineering game has exited")
        from smb3_agent.stardew_adapter import MacVisibleStardewBackend
        native = MacVisibleStardewBackend(process_id=launch.process_id, process_started_at=launch.process_started_at)
        window = native.detect_window(require_foreground=False)
        if not preserve_preparation:
            self.control("stop", reason="engineering session verification invalidates prior review")
        elif self.controller:
            raise StardewAdapterError("Preparation cannot preserve existing gameplay control.")
        if self.controller and not self.controller.operator.input_neutralized:
            raise StardewAdapterError("neutral handback is unconfirmed")
        if self.controller:
            self._retired_attempts.extend(attempt_payload(attempt) for attempt in self.controller.attempts)
        self.controller = self.observer = self.driver = self.navigator = None
        self.screen = self._review_screen = None
        self.current_plan = None
        self._review_digest = None
        self._activate_game = None
        self._planting_observer = None
        self.preparation_view = None
        self._survey_paused = False
        self._preparation_driver = None
        self.cave_result = None
        self._cave_navigation = None
        self._cave_route = None
        self._cave_observer = None
        self._cave_resume_clock = None
        self._inference_clock = None
        self._cave_baseline = None
        self.inspection_result = None
        self._inspection_navigation = None
        self._qualified_profiles.clear()
        self.status = "unconfigured"
        registry = Path("artifacts/stardew-qualified-profile.json")
        prepared = Path(launch.root) / "prepared-source.json"
        farm_registration = None
        farm_registry = Path("artifacts/stardew-qualified-farm-profiles.json")
        if prepared.is_file() and farm_registry.is_file():
            prepared_id = json.loads(prepared.read_text())["id"]
            entries = json.loads(farm_registry.read_text())
            matches = [entry for entry in entries if entry.get("prepared_id") == prepared_id]
            if len(matches) > 1:
                raise StardewAdapterError("ambiguous farm action profile registration")
            farm_registration = matches[0] if matches else None
        from smb3_agent.candidate_resources import calibration_registration
        if prepared.is_file() and (registry.is_file() or farm_registration or calibration_registration()):
            from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
            from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator
            from smb3_agent.stardew_input import MacOrdinaryInputDriver
            from smb3_agent.stardew_setup import _verify_engineering_launch_identity
            from smb3_agent.candidate_resources import calibration_registration
            registration = farm_registration or calibration_registration() or json.loads(registry.read_text())
            manifest = Path(registration["manifest"])
            evidence_base = Path("artifacts/b4-engineering" if farm_registration else "artifacts/b3-engineering").resolve()
            if (manifest.resolve() != manifest or (evidence_base not in manifest.parents and registration != calibration_registration())
                    or hashlib.sha256(manifest.read_bytes()).hexdigest() != registration["sha256"]):
                raise StardewAdapterError("local prepared-farm calibration registration changed")
            if farm_registration:
                from smb3_agent.stardew_farm_perception import FarmPixelProfile
                from smb3_agent.stardew_farm_navigation import FarmNavigator
                profile = FarmPixelProfile(manifest)
                navigator = FarmNavigator(profile.config)
            else:
                profile = PreparedFarmPixelProfile(manifest)
                navigator = ViewpointNavigator(profile.config)
            if not profile.qualified():
                raise StardewAdapterError("prepared-farm screen calibration is not qualified")
            # Explicit setup verification may focus only this fresh isolated game.
            import time
            window = native.activate_window()
            verification_generation = self._generation
            def verification_authority():
                if self._generation != verification_generation or (preserve_preparation and self._goal_preparation.cancel.is_set()):
                    raise StardewAdapterError("Preparation verification canceled.")
            pointer = MacOrdinaryInputDriver(window_provider=native.detect_window,
                isolation_guard=lambda current: _verify_engineering_launch_identity(launch, current),
                authority_guard=verification_authority)
            try:
                pointer.arm()
                if farm_registration:
                    profile.read_menu(native, pointer, Path(launch.root))
                window = native.detect_window()
                _verify_engineering_launch_identity(launch, window)
                if window.bounds[2:] != profile.viewport_size:
                    raise StardewAdapterError("viewport scale or dimensions changed before verification pointer")
                pointer.expected_pointer_window = window
                pointer.send(InputCommand(InputKind.MOUSE, "move", "move", 0,
                    target=(window.bounds[0]+profile.hud_hover[0], window.bounds[1]+profile.hud_hover[1]),
                    purpose="verify_prepared_energy"))
            finally:
                pointer.neutralize()
            time.sleep(0.15)
            screenshot = native.capture(native.detect_window(), Path(launch.root) / f"prepared-view-{uuid4().hex}.png")
            self.setup_manager.verify_prepared_view(launch, native.detect_window(), profile=profile, screenshot=screenshot)
            self.register_qualified_profile(profile, navigator,
                evidence_root=Path(launch.root) / ("farm-attempts" if farm_registration else "watering-attempts"))
        else:
            self.setup_manager.verify_engineering_launch(launch, window)
        self.reason = "Engineering farm loading verified; connect its qualified screen calibration next."
        return self.snapshot()

    def _require_configured(self) -> None:
        if not all((self.setup_manager, self.controller, self.observer, self.driver, self.navigator)):
            raise StardewAdapterError("live watering requires verified isolated loading, automatic visible perception, and ordinary input")

    def _validate(self, screen: ScreenObservation, *, allow_player_occlusion: bool = False) -> None:
        self._require_configured()
        screen.validate(self.controller.save.disposable_tree_sha256, allow_player_occlusion=allow_player_occlusion)
        if screen.session_nonce != self.controller.save.nonce:
            raise StardewAdapterError("observation belongs to a reset or different disposable session")
        if screen.perception_classification != "automatic_live":
            raise StardewAdapterError("fixture/manual/unqualified perception cannot authorize live input")
        observed = datetime.fromisoformat(screen.observed_at)
        age = (datetime.now(timezone.utc) - observed).total_seconds() if observed.tzinfo else -1
        maximum_age = self.maximum_observation_age
        if screen.navigation_coverage is not None and self._cave_route is not None and screen.navigation_coverage.route_digest == self._cave_route.digest:
            maximum_age = 5.0
        if not 0 <= age <= maximum_age:
            raise StardewAdapterError("stale or future visible observation")
        self.setup_manager.require_verified(screen.window)
        setup_session = getattr(self.setup_manager, "session", None)
        if setup_session is not None and setup_session.session_id != self.controller.save.nonce:
            raise StardewAdapterError("setup session changed; reconnect the reset disposable session")
        if self.controller.operator.window is not None:
            old = self.controller.operator.window
            if (old.process_id, old.process_started_at, old.window_id) != (screen.window.process_id, screen.window.process_started_at, screen.window.window_id):
                raise StardewAdapterError("process or window identity changed")
        for reference in screen.screenshot_references:
            if not Path(reference).is_file():
                raise StardewAdapterError("retained screenshot evidence is missing")

    def inspect_planting(self) -> dict:
        """Capture-only survey: no pointer, menu, tools or movement permission."""
        if not self.controller or not self.setup_manager or self._planting_observer is None:
            raise StardewAdapterError("Complete isolated farm setup and connect its matching screen profile, then show the farm from the porch and ask again.")
        if (self.status in {"running", "stopping"} or self._tick_lock.locked()
                or not self.controller.operator.input_neutralized):
            raise StardewAdapterError("Wait for confirmed handback before discussing a planting location.")
        if self._planting_observer is None:
            raise StardewAdapterError("Connect a supported farm profile before inspecting planting locations.")
        if self._activate_game is not None:
            self._activate_game()
        return self._planting_observer()

    def observe(self) -> dict:
        self.refresh_observation()
        return self.snapshot()

    def refresh_observation(self) -> None:
        import time
        started = time.monotonic()
        timings = {}
        try:
            self._require_configured()
            if self.status == "running":
                return
            if self._activate_game is not None:
                self._activate_game()
            screen = self.observer()
            timings['observer_seconds'] = time.monotonic() - started
            self._validate(screen)
            timings['validated_seconds'] = time.monotonic() - started
            envelope = self.controller.observe(screen)
            timings['converted_seconds'] = time.monotonic() - started
            if not envelope.trusted:
                raise StardewAdapterError(envelope.stale_reasons[0])
            self.screen = screen
            self.reason = "Fresh farm state observed; review the requested work before Start. Previous outcomes remain in history."
            if self.status in {"unconfigured", "ready"}:
                self.status = "ready"
        except Exception as exc:
            reason = self._failure_reason("stardew_observe", exc)
            self.screen = self._review_screen = None
            self._review_digest = None
            if self.status == "running":
                self.control("stop", reason=reason)
            self.reason = reason
        finally:
            timings['total_seconds'] = time.monotonic() - started
            self._observation_refresh_timing = timings

    def setup(self, payload: dict) -> dict:
        # JSON may select a source copy, never assert calibration/isolation verification.
        if self.status in {"running", "stopping"} or self._tick_lock.locked() or (self._worker and self._worker.is_alive()):
            raise StardewAdapterError("reclaim and wait for neutral handback before changing the disposable session")
        self.control("stop", reason="disposable setup changed; old review invalidated")
        self.screen = self._review_screen = None
        self.current_plan = None
        self._review_digest = None
        if not self.snapshot()['handback_confirmed']:
            raise StardewAdapterError("new setup refused because neutral handback is unconfirmed")
        if self.controller:
            self._retired_attempts.extend(attempt_payload(attempt) for attempt in self.controller.attempts)
        self.controller = self.observer = self.driver = self.navigator = None
        self._qualified_profiles.clear()
        self._activate_game = None
        self._planting_observer = None
        self.preparation_view = None
        self._survey_paused = False
        self._preparation_driver = None
        self.cave_result = None
        self._cave_navigation = None
        self._cave_route = None
        self._cave_observer = None
        self._cave_resume_clock = None
        self._inference_clock = None
        self._cave_baseline = None
        self.inspection_result = None
        self._inspection_navigation = None
        self.status = "unconfigured"
        if self.setup_manager is None:
            from smb3_agent.stardew_setup import DisposableSessionSetup
            self.setup_manager = DisposableSessionSetup()
        action = payload.get("action", "create_owner_copy")
        if action == "reconnect_engineering":
            from smb3_agent.stardew_setup import DisposableSessionSetup, reconnect_open_engineering
            launch, process = reconnect_open_engineering()
            self.setup_manager = DisposableSessionSetup()
            self._engineering_launches = [(launch, process)]
            self.reason = "Open disposable game reconnected. Show its window, load Pilot/B3Test if needed, exit to the porch and select the watering can. Check the farm session and connect screen recognition; no gameplay authority restored."
            return self.snapshot()
        if action in {"launch_engineering", "launch_selected_copy"}:
            from smb3_agent.stardew_setup import DisposableSessionSetup, discover_installations, launch_fresh_engineering
            self.setup_manager = DisposableSessionSetup()
            if any(process.poll() is None for _, process in self._engineering_launches):
                raise StardewAdapterError("an attempt-owned engineering process is already running")
            installation = payload.get("installation")
            if not installation:
                installed = discover_installations()["installations"]
                if len(installed) != 1:
                    raise StardewAdapterError("select the exact installed Stardew application; automatic selection is ambiguous or unavailable")
                installation = installed[0]
            app = Path(installation)
            if (app / "Stardew Valley.app").is_dir():
                app = app / "Stardew Valley.app"
            destination = Path(payload["destination"]) if payload.get("destination") else Path("artifacts/stardew-engineering") / uuid4().hex
            launch_options = ({"selected_source": Path(payload["source"]),
                               "copy_authorized": payload.get("copy_authorized") is True}
                              if action == "launch_selected_copy" else
                              {"prepared_id": payload["prepared_id"]} if payload.get("prepared_id") else {})
            launch, process = launch_fresh_engineering(app, destination, **launch_options)
            self._engineering_launches.append((launch, process))
            if process.poll() is not None:
                log_path = Path(launch.root) / "game.log"
                detail = log_path.read_text(errors="replace")[:400].strip() if log_path.is_file() else "launch log unavailable"
                self.reason = ("Stardew could not start because this Mac cannot currently run its Intel build. Complete Apple’s Rosetta setup, then open a fresh engineering session. No gameplay input was sent."
                               if "Bad CPU type" in detail else
                               f"The engineering game exited before setup completed (code {process.poll()}). Its launch log is retained in Session and evidence details.")
            else:
                self.reason = ("Selected save copied unchanged into an isolated game. Approve observed preparation; support and resources will be checked before watering review. The original is preserved."
                               if action == "launch_selected_copy" else
                               "Prepared farm copied into a fresh isolated session. Choose Load in the game; fresh loading verification and observation are required. No gameplay authority restored."
                               if payload.get("prepared_id") else "Fresh isolated title-screen launch requested. No prepared farm is loaded; input is disabled.")
            return self.snapshot()
        if action in {"create_owner_copy", "create_engineering_copy"}:
            create = (self.setup_manager.create_engineering_copy if action == "create_engineering_copy" or payload.get("source_kind", payload.get("setup_source_kind")) in {"engineering_save", "engineering_source"}
                      else self.setup_manager.create_owner_copy)
            create(Path(payload["source"]), Path(payload["destination"]),
                   copy_authorized=payload.get("copy_authorized") is True)
        elif action == "reset":
            self.control("stop", reason="disposable reset")
            self.setup_manager.reset(Path(payload["destination"]))
        else:
            raise StardewAdapterError("setup supports an explicitly authorized source copy or fresh reset; a browser assertion cannot verify loading")
        self.screen = self._review_screen = None
        self.current_plan = None
        self._review_digest = None
        self.controller = None
        self.status = "unconfigured"
        self.reason = "Disposable copy created; actual isolated loading and qualified visible perception are still required."
        return self.snapshot()

    def connect_selected_scene(self, launch, native, profile, navigator, screenshot, load_screenshot):
        """Internal observed handoff, never accepts browser-provided live facts."""
        from smb3_agent.stardew_setup import verify_selected_scene
        verify_selected_scene(self.setup_manager, launch, native.detect_window(), profile,
                              screenshot, load_screenshot)
        self.register_qualified_profile(profile, navigator, evidence_root=Path(launch.root)/"watering-attempts")
        self.connect_live(profile=profile, navigator=navigator,
                          evidence_root=Path(launch.root)/"watering-attempts")
        self.observe()

    def planning_context(self, conversation_id: str = "stardew-conversation", current_plan=None) -> PlanningContext:
        valid = False
        if self.screen:
            try:
                self._validate(self.screen)
                valid = True
            except (ValueError, OSError) as exc:
                observation_error = str(exc)
        targets = [{"id": c.crop_id, "kind": "crop", "planted": c.planted, "watered": None if c.occluded else c.watered,
                    "visible": not c.occluded, "confidence": c.confidence,
                    "label": f"crop at row {c.tile_y}, column {c.tile_x}",
                    "tile_x": c.tile_x, "tile_y": c.tile_y}
                   for c in self.screen.crops if c.planted] if self.screen else []
        observation = {"source": "automatic_visible" if valid else "unavailable", "validated": valid,
                       "complete_initial_set": valid and self.screen.scene_complete and not self.screen.unknown_regions,
                       "isolation_verified": valid,
                       "initial_target_ids": [t["id"] for t in targets], "return_point": "farmhouse_entrance",
                       "targets": targets}
        if self.screen and not valid:
            observation['validation_error'] = observation_error
        selected_copy = getattr(getattr(self.setup_manager, 'session', None), 'classification', None) == 'selected_owner_copy'
        observation['scene_scope'] = ('visible local farmhouse spring-seed patch; other terrain and crops are outside support'
                                      if selected_copy else 'frozen engineering farm calibration')
        if valid and isinstance(self.screen.farm, FarmObservation):
            farm = self.screen.farm
            targets = [{"id": t.target_id, "kind": "crop" if t.planted else "debris" if t.state == "debris" else "plot",
                        "planted": t.planted, "ready": t.state == "mature", "state": t.state,
                        "species": t.species, "watered": t.watered, "protected": t.protected,
                        "visible": True, "confidence": 1, "tile_x": t.tile_x, "tile_y": t.tile_y} for t in farm.targets]
            observation.update(targets=targets, farm_contract=FARM_CONTRACT,
                               inventory=farm.counts(), season=farm.season, day=farm.day,
                               supported_actions=getattr(self.navigator, "supported_actions", ()))
        if valid and not isinstance(self.screen.farm, FarmObservation):
            try:
                validator = getattr(self.navigator, "validate_scope", None)
                if validator is None:
                    raise StardewAdapterError("qualified route validation is unavailable")
                validator(self.screen)
                observation["watering_route_ready"] = True
            except StardewAdapterError as exc:
                observation.update(watering_route_ready=False, route_remedy=str(exc))
        # Last-observed location labels remain readable when pixels age out.
        # Only `valid` above can make these targets eligible for a new plan.
        pending = list(targets) if self.screen and not isinstance(self.screen.farm, FarmObservation) else []
        patches = []
        while pending:
            patch = [pending.pop(0)]
            for tile in patch:
                for other in list(pending):
                    if abs(tile["tile_x"]-other["tile_x"]) + abs(tile["tile_y"]-other["tile_y"]) == 1:
                        pending.remove(other)
                        patch.append(other)
            patches.append(patch)
        patches.sort(key=lambda patch: (min(t["tile_x"] for t in patch), min(t["tile_y"] for t in patch)))
        for index, patch in enumerate(patches):
            name = ("the crop patch" if len(patches) == 1 else "left patch" if index == 0
                    else "right patch" if index == len(patches)-1 else f"middle patch {index}")
            for target in patch:
                target["patch"] = name
                target["label"] = f"{name}, row {target['tile_y']}, column {target['tile_x']}"
        if valid:
            observation.update(player_location=asdict(self.screen.position), observed_at=self.screen.observed_at,
                               watering_activity=not isinstance(self.screen.farm, FarmObservation), energy=self.screen.energy,
                               water=self.screen.tool.watering_can_units,
                               selected_tool=self.screen.tool.selected_tool,
                               energy_cost_upper_bound=getattr(self.navigator, "energy_cost_upper_bound", None))
            if self._planting_observer and self.screen.farm is None:
                from smb3_agent.stardew_recon import catalog
                try:
                    observation["reconnaissance_viewpoints"] = catalog(self.navigator)
                except StardewAdapterError:
                    pass
        return PlanningContext(game_id="stardew", conversation_id=conversation_id,
                               session_id=self.controller.save.nonce if self.controller else None,
                               observation_id=self.screen.observation_id if valid else None,
                               observation=observation, current_plan=current_plan or self.current_plan,
                               selected_targets=tuple(targets), observation_fresh=valid)

    def review(self, plan: ConversationPlan) -> dict:
        if self.status in {"running", "stopping"} or self._tick_lock.locked() or (self._worker and self._worker.is_alive()):
            raise StardewAdapterError("pause and obtain fresh review after neutral handback before changing watering scope")
        for profile, _, nonce, _ in self._qualified_profiles.values():
            if self.controller and nonce == self.controller.save.nonce:
                restrict = getattr(profile, 'review_targets', None)
                if restrict and plan.actions and plan.actions[0].target_ids:
                    restrict(plan.actions[0].target_ids)
        self.current_plan = plan
        self._review_digest = plan_digest(plan)
        self._review_screen = self.screen
        self.reason = "Plan reviewed; Start still requires a fresh qualified visible session."
        return self.snapshot()

    @staticmethod
    def _task_state(screen: ScreenObservation) -> tuple:
        crop_state = tuple((c.crop_id, c.tile_x, c.tile_y, c.planted, c.watered, c.occluded, c.confidence) for c in screen.crops)
        return (screen.session_nonce, crop_state, screen.tool, screen.energy, screen.position,
                screen.window.process_id, screen.window.process_started_at, screen.window.window_id)

    def _task_unchanged(self, before, after):
        if (before.farm is None) != (after.farm is None):
            return False
        if before.farm is not None and before.farm.task_state() != after.farm.task_state():
            return False
        if before.position.world_pixel_x is None:
            return self._task_state(before) == self._task_state(after)
        from dataclasses import replace
        p, q = before.position, after.position
        if q.world_pixel_x is None or p.location != q.location:
            return False
        bound = p.pixel_uncertainty + q.pixel_uncertainty
        if max(abs(p.world_pixel_x-q.world_pixel_x), abs(p.world_pixel_y-q.world_pixel_y)) > bound:
            return False
        if before.crops != after.crops:
            left, right = {c.crop_id:c for c in before.crops}, {c.crop_id:c for c in after.crops}
            if left.keys() != right.keys():
                return False
            confirmed = self.controller.operator.ledger.confirmed_watered_ids if self.controller.operator.ledger else set()
            for key, crop in right.items():
                previous = left[key]
                if (crop.tile_x,crop.tile_y,crop.planted) != (previous.tile_x,previous.tile_y,previous.planted):
                    return False
                expected_watered = previous.watered if not previous.occluded else key in confirmed
                coverage = after.navigation_coverage or before.navigation_coverage
                if previous.occluded and coverage is not None:
                    expected_watered = next(c.watered for c in coverage.baseline.crops if c.crop_id == key)
                if not crop.occluded and crop.watered != expected_watered:
                    return False
        return self._task_state(replace(before, position=q, crops=after.crops)) == self._task_state(after)

    def start(self, plan: ConversationPlan, *, background: bool = True) -> dict:
        from smb3_agent.paths import is_packaged
        if is_packaged() and (plan.normalized_intent != "farm_routine" or any(action.kind != "water" for action in plan.actions)):
            raise StardewAdapterError("This candidate enables prepared Day 2 watering only; reconnaissance and wider farm work are unavailable.")
        with self._lock:
            self._require_configured()
            with self._authority_lock:
                generation = self._generation
            if self.status in {"running", "stopping"} or self._tick_lock.locked() or (self._worker and self._worker.is_alive()):
                raise StardewAdapterError("watering or handback is already running")
            if self._review_digest != plan_digest(plan) or self._review_screen is None:
                raise StardewAdapterError("Start requires the exact reviewed plan and observation")
            if plan.game_id != "stardew" or plan.session_id != self.controller.save.nonce or plan.observation_id != self._review_screen.observation_id:
                raise StardewAdapterError("reviewed plan session or observation mismatch")
            if plan.normalized_intent == "inspect_cave":
                return self._start_cave(plan, background=background)
            self._cave_navigation = None
            if self.screen and self.screen.navigation_coverage is not None:
                raise StardewAdapterError("Refresh complete farmhouse coverage before farm work or eastern inspection.")
            self._cave_baseline = None
            if plan.normalized_intent in {"inspect_planting", "inspect_recon"}:
                return self._start_inspection(plan, background=background)
            self._inspection_navigation = None
            farm_task = isinstance(self._review_screen.farm, FarmObservation)
            if plan.ambiguities or plan.unsupported_parts or not plan.actions or (not farm_task and any(a.kind != "water" for a in plan.actions)):
                raise StardewAdapterError("only unambiguous watering is executable without qualified farm-action recognition")
            if plan.stop_point != "farmhouse_entrance":
                raise StardewAdapterError("only the reviewed farmhouse entrance return point is supported")
            if self._activate_game is not None:
                self._activate_game()
            current = self.observer()
            self._validate(current)
            if not self._task_unchanged(self._review_screen, current):
                raise StardewAdapterError("visible task conditions changed since review; observe and review again")
            initial = {c.crop_id for c in current.crops if c.planted}
            requested = [target for action in plan.actions for target in action.target_ids]
            farm_ledger = FarmLedger.from_plan(plan, current) if farm_task else None
            seconds = plan.resource_limits.get("maximum_seconds")
            if seconds is not None and (type(seconds) is not int or not 1 <= seconds <= 180):
                raise StardewAdapterError("reviewed watering duration must be between 1 and 180 seconds")
            activity = type(seconds) is int and 1 <= seconds <= 180 and not farm_task
            if activity:
                if not requested or not set(requested) <= initial or len(set(requested)) != len(requested):
                    raise StardewAdapterError("reviewed watering targets must be unique observed planted crops")
                dry = {c.crop_id for c in current.crops if c.planted and c.watered is False and not c.occluded}
                if not set(requested) <= dry:
                    raise StardewAdapterError("reviewed patch is no longer visibly dry; request a revised plan")
                count = len(requested)
                cost = self.navigator.energy_cost_upper_bound
                reserve = plan.resource_limits.get("minimum_energy") or 1
                if current.tool.selected_tool != "watering_can":
                    raise StardewAdapterError("Select the watering can, then request and review again.")
                if current.tool.watering_can_units < count:
                    raise StardewAdapterError("Refill the watering can yourself, then request a fresh plan; automatic refill is unavailable.")
                water_reserve = plan.resource_limits.get("minimum_water", 0)
                water_uses = plan.resource_limits.get("maximum_water_uses", 32)
                if (type(water_reserve) is not int or not 0 <= water_reserve <= 40
                        or type(water_uses) is not int or not 0 <= water_uses <= 32):
                    raise StardewAdapterError("Invalid reviewed watering resource limits")
                if count > water_uses or current.tool.watering_can_units - count < water_reserve:
                    raise StardewAdapterError("Selected crops exceed the reviewed water reserve or use limit; request fewer targets and review again.")
                if cost is None or current.energy - count * cost < reserve:
                    raise StardewAdapterError("The patch exceeds the known energy budget; recover energy or choose a smaller patch and review again.")
            if not farm_task and not activity and (set(requested) != initial or len(requested) != len(initial)):
                raise StardewAdapterError("watering v1 requires every initially planted crop exactly once; narrower scope is unsupported")
            if farm_task:
                if not hasattr(self.navigator, "validate_farm_scope"):
                    raise StardewAdapterError("qualified action-specific farm routes are unavailable")
                self.navigator.validate_farm_scope(current, plan)
            else:
                self.navigator.validate_scope(current)
            # A new authorization never inherits a partial navigation waypoint.
            self.navigator._waypoint = None
            self.navigator._waypoint_pulses = 0
            if hasattr(self.navigator, "reset"):
                self.navigator.reset()
            if self.evidence_root is None:
                raise StardewAdapterError("watering requires a retained attempt evidence directory")
            self.evidence_root.mkdir(parents=True, exist_ok=True)
            self._evidence_files = []
            self.evidence_error = None
            self._retain("review", {"plan": plan.to_dict(), "before": asdict(current)})
            # Both mouse watering and keyboard navigation are required. Controller's
            # epoch uses a single kind; change it only within this reviewed runtime.
            if not self.driver.available(InputKind.MOUSE) or not self.driver.available(InputKind.KEYBOARD):
                raise StardewAdapterError("ordinary mouse and keyboard input are both required")
            with self._authority_lock:
                if generation != self._generation:
                    raise StardewAdapterError("Start was canceled during observation; review again")
                if self.controller.active_attempt is not None:
                    operator = self.controller.operator
                    if operator.owner is not InputOwner.PLAYER or not operator.input_neutralized:
                        raise StardewAdapterError("verified player handback is required for a new task baseline")
                    # A released action may finish visually after interruption.
                    # Preserve its old uncertain record. Explicit new review and
                    # Start establish current facts, not retrospective actor credit.
                    self._retain("reauthorization-baseline", {
                        "prior_attempt_id": self.controller.active_attempt.attempt_id,
                        "prior_ledger": asdict(operator.ledger) if operator.ledger else None,
                        "new_visible_baseline": asdict(current),
                        "attribution": "current visible state; previous uncertain actions remain unverified",
                    })
                    operator.attach_player_owned(current)
                    operator.establish_task(current)
                    operator.failure = None
                self.screen = current
                if farm_task:
                    self.controller.operator.ledger = farm_ledger
                if activity and not farm_task:
                    # A prior Stop without an attempt leaves the operator reclaimed.
                    # Fresh Start validates this player-owned baseline before reuse.
                    self.controller.operator.attach_player_owned(current)
                    self.controller.operator.establish_task(current)
                    self.controller.operator.ledger.requested_crop_ids = tuple(requested)
                self.controller.authorize_do(current, owner_confirmation=True, input_driver=InputKind.MOUSE,
                                             expires_at=(datetime.now(timezone.utc)+timedelta(seconds=seconds if activity else 600)).isoformat())
                self.current_plan = plan
                if self.gameplay_agent:
                    if self.gameplay_agent.plan_id != plan.plan_id:
                        self.gameplay_agent = None
                    else:
                        self.gameplay_agent.reset()
                self._cancel = threading.Event()
                self.status, self.reason = "running", ("Executing the reviewed farm routine. Keep the game foreground." if farm_task else "Watering the reviewed crop targets. Keep the game foreground.")
                if background:
                    self._worker = threading.Thread(target=self._run, args=(self._cancel,), daemon=True, name="stardew-watering")
                    self._worker.start()
        return self.snapshot()

    def propose_inspection(self, text, conversation_id):
        from smb3_agent.stardew_inspection import proposal
        self.observe()
        if self.screen is None:
            raise StardewAdapterError(self.reason)
        if self._planting_observer is None or self.screen.farm is not None:
            raise StardewAdapterError("Inspection coverage currently supports only the prepared Day 2 farm.")
        return proposal(self.screen, self.navigator, text, conversation_id)

    def propose_recon(self, text, conversation_id, intent):
        from smb3_agent.paths import is_packaged
        if is_packaged():
            raise StardewAdapterError("Reconnaissance is experimental and unavailable in this candidate; native qualification is pending.")
        from smb3_agent.stardew_recon import proposal
        self.observe()
        if self.screen is None or self._planting_observer is None or self.screen.farm is not None:
            raise StardewAdapterError("Reconnaissance requires the connected prepared Day 2 farm.")
        return proposal(self.screen, self.navigator, text, conversation_id, intent)

    def _start_inspection(self, plan, *, background):
        from smb3_agent.stardew_inspection import proposal, InspectionNavigator
        if self._activate_game:
            self._activate_game()
        current = self.observer()
        self._validate(current)
        recon = plan.normalized_intent == "inspect_recon"
        if recon:
            from smb3_agent.stardew_recon import ReconAgent, proposal as recon_proposal
            if not isinstance(self.gameplay_agent, ReconAgent) or self.gameplay_agent.plan_id != plan.plan_id:
                raise StardewAdapterError("Reconnaissance needs its current plan-bound gameplay agent.")
            expected = recon_proposal(current, self.navigator, plan.original_request, plan.conversation_id,
                                      self.gameplay_agent.intent)
        else:
            expected = proposal(current, self.navigator, plan.original_request, plan.conversation_id)
        if (plan.actions != expected.actions or plan.resource_limits != expected.resource_limits
                or plan.stop_point != expected.stop_point or current.farm is not None
                or not self._task_unchanged(self._review_screen, current)):
            raise StardewAdapterError("Inspection scope or current conditions changed; request a fresh plan.")
        if self.evidence_root is None:
            raise StardewAdapterError("Inspection requires retained evidence.")
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self._evidence_files = []
        self.evidence_error = None
        self._retain("inspection-review", {"plan": plan.to_dict(), "before": asdict(current)})
        with self._authority_lock:
            if self._review_digest != plan_digest(plan):
                raise StardewAdapterError("Inspection approval was canceled.")
            self.controller.operator.attach_player_owned(current)
            self.controller.operator.establish_task(current)
            self.controller.authorize_do(current, owner_confirmation=True, input_driver=InputKind.KEYBOARD,
                expires_at=(datetime.now(timezone.utc)+timedelta(seconds=plan.resource_limits['maximum_seconds'])).isoformat())
            self._inspection_navigation = InspectionNavigator(self.navigator)
            if recon:
                self.gameplay_agent.reset()
            self.inspection_result = {"plan": plan.to_dict(), "status": "running", "findings": None,
                                      "handback_confirmed": False, "observations": []}
            self.current_plan, self.screen = plan, current
            self._cancel = threading.Event()
            self.status, self.reason = "running", "Inspecting the eastern crop margin; 120 seconds including return."
            if recon:
                self.reason = "Investigating the reviewed question; model choices and observations stay within the return budget."
            if background:
                self._worker = threading.Thread(target=self._run, args=(self._cancel,), daemon=True, name="stardew-inspection")
                self._worker.start()
        return self.snapshot()

    def _tick_inspection(self):
        from smb3_agent.stardew_inspection import fresh_findings
        self.require_authority()
        pending = self._pending_navigation_observation
        self._pending_navigation_observation = None
        age = ((datetime.now(timezone.utc)-datetime.fromisoformat(pending.observed_at)).total_seconds()
               if pending is not None else float("inf"))
        current = pending if pending is self.screen and 0 <= age < 1 else self.observer()
        self._validate(current, allow_player_occlusion=True)
        if not self._task_unchanged(self.screen, current):
            raise StardewAdapterError("Farm changed outside the approved inspection movement.")
        self.require_authority()
        envelope = self.controller.observe(current, allow_player_occlusion=True)
        if not envelope.trusted:
            raise StardewAdapterError(envelope.stale_reasons[0])
        self.screen = current
        if self.current_plan.normalized_intent == "inspect_recon":
            return self.gameplay_agent.tick(self, current)
        command, event = self._inspection_navigation.next_inspection_command(current)
        if event == "observe":
            observation = self._planting_observer(inspection=True)
            self.require_authority()
            self.inspection_result["findings"] = fresh_findings(observation, self.controller.save.nonce,
                self.current_plan.observation_id)
            self._retain("inspection-findings", self.inspection_result)
            self._inspection_navigation.observed = True
        elif event == "returned":
            final = self.observer()
            self._validate(final)
            if not final.position.at_farmhouse_entrance or not self._task_unchanged(current, final):
                raise StardewAdapterError("Fresh inspection return could not be confirmed.")
            self.require_authority()
            self.screen = final
            self.control("stop", reason="Inspection finished; farmhouse return observed.")
            self.inspection_result.update(status="completed", return_observation=asdict(final),
                handback_confirmed=self.snapshot()["handback_confirmed"])
            if not self.inspection_result["handback_confirmed"]:
                self.inspection_result["status"] = "failed"
            self._retain("inspection-result", self.inspection_result)
        else:
            if command.kind != InputKind.KEYBOARD or command.purpose != "navigate":
                raise StardewAdapterError("Inspection permits navigation only.")
            self.require_authority()
            self.driver.arm()
            def after():
                result = self.observer()
                self._validate(result, allow_player_occlusion=True)
                self.require_authority()
                return result
            self.screen = self.controller.perform_input(command, current, self.driver, after)
            self._pending_navigation_observation = self.screen
            self._retain("inspection-step", {"command": asdict(command), "before": asdict(current), "after": asdict(self.screen)})
        return self.ui_snapshot()

    def _observe_cave(self):
        return self._cave_observer() if self._cave_observer else self.observer()

    def propose_cave(self, text, conversation_id, *, return_only=False):
        from smb3_agent.stardew_cave import proposal, SETUP
        if self._cave_route is None:
            raise StardewAdapterError(SETUP)
        if self._activate_game:
            self._activate_game()
        self.screen = self._observe_cave()
        self._validate(self.screen)
        if self.screen is None:
            raise StardewAdapterError(self.reason)
        if return_only and not (self.cave_result and self.cave_result.get("findings")
                                and self.cave_result["plan"]["session_id"] == self.screen.session_nonce):
            raise StardewAdapterError("No current-session cave findings to continue; request a new Farm Cave visit.")
        return proposal(self.screen, self._cave_route, text, conversation_id, return_only=return_only)

    def _start_cave(self, plan, *, background):
        from smb3_agent.stardew_cave import proposal, CaveNavigator
        if self._activate_game:
            self._activate_game()
        current = self._observe_cave()
        self._validate(current)
        return_only = bool(plan.actions and plan.actions[0].parameters.get("return_only"))
        expected = proposal(current, self._cave_route, plan.original_request, plan.conversation_id,
                            return_only=return_only)
        if (plan.actions != expected.actions or plan.resource_limits != expected.resource_limits
                or plan.stop_point != expected.stop_point or plan.effective_boundary != expected.effective_boundary
                or plan.requested_objective != expected.requested_objective
                or plan.fallback_explanation != expected.fallback_explanation
                or plan.ambiguities or plan.unsupported_parts
                or not self._task_unchanged(self._review_screen, current)):
            raise StardewAdapterError("Cave scope or conditions changed; request a fresh reviewed plan.")
        prior = self.cave_result
        if return_only and not (prior and prior.get("findings") and prior["plan"]["session_id"] == current.session_nonce):
            raise StardewAdapterError("A return continuation needs current-session retained findings.")
        if self.evidence_root is None:
            raise StardewAdapterError("Cave reconnaissance requires retained evidence.")
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        # Fine native corrections need deadline release outside this process's
        # GIL: observation/UI serialization must not extend a movement hold.
        from smb3_agent.stardew_input import MacOrdinaryInputDriver
        if isinstance(self.driver, MacOrdinaryInputDriver) and self.driver.external_guard is None:
            from smb3_agent.input_guardian import InputGuardian
            self.driver.external_guard = InputGuardian(self.evidence_root / "cave-input-guardian.jsonl")
        self._evidence_files = []
        self.evidence_error = None
        self._retain("cave-review", {"plan": plan.to_dict(), "before": asdict(current)})
        with self._authority_lock:
            if self._review_digest != plan_digest(plan):
                raise StardewAdapterError("Cave approval was canceled.")
            self.controller.operator.attach_player_owned(current)
            self.controller.operator.establish_task(self._cave_baseline or current)
            if self._cave_baseline:
                self.controller.operator.ledger.reconcile(current, allow_player_occlusion=True)
            self.controller.authorize_do(current, owner_confirmation=True, input_driver=InputKind.KEYBOARD,
                expires_at=(datetime.now(timezone.utc)+timedelta(seconds=plan.resource_limits["maximum_seconds"])).isoformat())
            self._cave_navigation = CaveNavigator(self._cave_route.navigator)
            self._cave_navigation.observed = return_only
            self._inspection_navigation = None
            self.cave_result = {"baseline_observation": asdict(self._cave_baseline or current), "plan": plan.to_dict(), "status": "running",
                "initial_request": prior.get("initial_request", prior["plan"]["original_request"]) if return_only else plan.original_request,
                "arrival_observation": prior.get("arrival_observation") if return_only else None,
                "findings": prior["findings"] if return_only else None, "return_observation": None,
                "handback_confirmed": False}
            self.current_plan, self.screen = plan, current
            self._cancel = threading.Event()
            self.status, self.reason = "running", "Farm Cave exterior reconnaissance; 10 minutes including farmhouse return."
            if background:
                self._worker = threading.Thread(target=self._run, args=(self._cancel,), daemon=True, name="stardew-cave")
                self._worker.start()
        return self.snapshot()

    def _tick_cave(self):
        self.require_authority()
        pending = self._pending_navigation_observation
        self._pending_navigation_observation = None
        age = ((datetime.now(timezone.utc)-datetime.fromisoformat(pending.observed_at)).total_seconds()
               if pending is not None else float('inf'))
        current = pending if pending is self.screen and 0 <= age < 5 else self._observe_cave()
        self._validate(current, allow_player_occlusion=True)
        if not self._task_unchanged(self.screen, current):
            raise StardewAdapterError("Farm or resources changed outside approved cave movement.")
        self._cave_route.validate_view(current)
        self.require_authority()
        envelope = self.controller.observe(current, allow_player_occlusion=True)
        if not envelope.trusted:
            raise StardewAdapterError(envelope.stale_reasons[0])
        self.screen = current
        command, event = self._cave_navigation.next_inspection_command(current)
        if event == "observe":
            self.cave_result["arrival_observation"] = asdict(current)
            self._retain("cave-arrival", self.cave_result)
            fresh = self._observe_cave()
            self._validate(fresh, allow_player_occlusion=True)
            if not self._task_unchanged(current, fresh):
                raise StardewAdapterError("Cave scene changed during entrance capture.")
            self._cave_route.validate_view(fresh)
            findings = self._cave_route.findings(fresh, session_id=self.controller.save.nonce,
                                               baseline_id=current.observation_id, baseline_time=current.observed_at)
            with self._authority_lock:
                self.require_authority()
                self.cave_result["findings"] = findings
                self._cave_navigation.observed = True
                self.screen = fresh
            self._retain("cave-findings", self.cave_result)
        elif event == "returned":
            final = self.observer()
            self._validate(final)
            self._cave_route.validate_view(final)
            from dataclasses import replace
            baseline = replace(self._cave_baseline or final, position=final.position)
            if not final.position.at_farmhouse_entrance or not self._task_unchanged(current, final) or not self._task_unchanged(baseline, final):
                raise StardewAdapterError("Fresh farmhouse return could not be confirmed.")
            self.require_authority()
            self.screen = final
            self.control("stop", reason="Cave visit finished; farmhouse return observed.")
            self.cave_result.update(status="completed", return_observation=asdict(final),
                handback_confirmed=self.snapshot()["handback_confirmed"])
            if not self.cave_result["handback_confirmed"]:
                self.cave_result["status"] = "failed"
            self._retain("cave-result", self.cave_result)
        else:
            if command.kind != InputKind.KEYBOARD or command.purpose != "navigate":
                raise StardewAdapterError("Cave reconnaissance permits navigation only.")
            self.require_authority()
            if self._cave_resume_clock:
                self._cave_resume_clock()
            self.driver.arm()
            def after():
                result = self._observe_cave()
                self._validate(result, allow_player_occlusion=True)
                self._cave_route.validate_view(result)
                self.require_authority()
                return result
            self.screen = self.controller.perform_input(command, current, self.driver, after)
            self._pending_navigation_observation = self.screen
            self._retain("cave-step", {"command": asdict(command), "before": asdict(current), "after": asdict(self.screen),
                                       "driver_timing": getattr(self.driver, "last_pulse_timing", None)})
        return self.ui_snapshot()

    def require_authority(self) -> None:
        if self._cancel.is_set() or self.status != "running" or self.controller is None or self.controller.authorization is None:
            raise StardewAdapterError("runtime authority has ended")
        if self.current_plan is None or plan_digest(self.current_plan) != self._review_digest:
            raise StardewAdapterError("reviewed plan identity changed")
        if datetime.fromisoformat(self.controller.authorization.expires_at) <= datetime.now(timezone.utc):
            raise StardewAdapterError("runtime authority expired")

    def _run(self, cancellation: threading.Event) -> None:
        while cancellation is self._cancel and not cancellation.is_set() and self.status == "running":
            self.tick()
            cancellation.wait(0.05)

    def tick(self) -> dict:
        if not self._tick_lock.acquire(blocking=False):
            return self.snapshot()
        try:
            return self._tick()
        finally:
            self._tick_lock.release()

    def _tick(self) -> dict:
        if self._cancel.is_set() or self.status != "running":
            return self.snapshot()
        try:
            if self._cave_navigation is not None:
                return self._tick_cave()
            if self._inspection_navigation is not None:
                return self._tick_inspection()
            pending = self._pending_navigation_observation
            self._pending_navigation_observation = None
            # A reconciled movement's post-frame is also the next movement's
            # before-frame while fresh. Preserve its original timestamp. Native
            # focus/session guards still run before every emitted input.
            age = ((datetime.now(timezone.utc) - datetime.fromisoformat(pending.observed_at)).total_seconds()
                   if pending is not None else float("inf"))
            current = (pending if pending is self.screen and 0 <= age < 1
                       else self.observer())
            self._validate(current, allow_player_occlusion=True)
            if self._cancel.is_set():
                return self.snapshot()
            ledger = self.controller.operator.ledger
            # All passive observations must equal the last actor-labeled state.
            if self.screen is None or not self._task_unchanged(self.screen, current):
                raise StardewAdapterError("task changed outside a reconciled input")
            self.controller.observe(current, allow_player_occlusion=True)
            self.screen = current
            minimum = self.current_plan.resource_limits.get("minimum_energy")
            remaining = set(ledger.task_crop_ids if not isinstance(ledger, FarmLedger) else ledger.initial_crop_ids) - ledger.confirmed_watered_ids
            farm_task = isinstance(ledger, FarmLedger)
            if farm_task:
                ledger.check_limits(current)
                ledger.skip_observed_water(current)
            if remaining and not farm_task:
                cost = self.navigator.energy_cost_upper_bound
                if cost is None:
                    raise StardewAdapterError("watering energy cost bound is unknown")
                reserve = minimum if minimum is not None else 1
                if current.energy - cost < reserve:
                    raise StardewAdapterError("reviewed energy reserve would be crossed")
            if self.gameplay_agent and not farm_task:
                remaining = self.gameplay_agent.choose(self, current, remaining)
                current = self.screen
                self.require_authority()
            command, _target = (self.navigator.next_farm_command(current, ledger.next_step) if farm_task
                                else self.navigator.next_command(current, remaining))
            if command is None:
                # Completion always has an independent, full current frame.
                current = self.observer()
                self._validate(current)
                if not self._task_unchanged(self.screen, current):
                    raise StardewAdapterError("task changed before final verification")
                # Accept the new evidence identity only after semantic equality
                # and full validation. Reconcile its actual return position too.
                self.controller.observe(current)
                ledger.reconcile(current)
                self.screen = current
                self._retain("final", asdict(current))
                with self._authority_lock:
                    self.require_authority()
                    self.controller.complete(current, self.driver, evidence_root=self.evidence_root,
                                             required_evidence=tuple(self._evidence_files), completion_guard=self.require_authority)
                self.status = self.controller.active_attempt.status.value
                self.reason = self.controller.active_attempt.stop_reason
                self._cancel.set()
                self._retain("outcome", attempt_payload(self.controller.active_attempt))
                return self.snapshot()
            if command.purpose == "water_crop" and not farm_task:
                limits = self.current_plan.resource_limits
                if current.tool.watering_can_units - 1 < limits.get("minimum_water", 0):
                    raise StardewAdapterError("reviewed water reserve would be crossed")
                used = len(ledger.confirmed_watered_ids & set(ledger.task_crop_ids))
                if used >= limits.get("maximum_water_uses", 32):
                    raise StardewAdapterError("reviewed watering-use limit reached")
            # Authorization remains exact plan/session; controller still validates kind
            # on every call. Only these two reviewed ordinary kinds are admitted.
            from dataclasses import replace
            self.controller.authorization = replace(self.controller.authorization, input_driver=command.kind)
            def after():
                if command.purpose in {"water_crop", "harvest_crop", "plant_seed", "clear_debris"} and getattr(self.navigator, "poses", None):
                    self._cancel.wait(0.7)
                    self.require_authority()
                value = self.observer()
                self._retain("post-observation", asdict(value))
                self.require_authority()
                self._validate(value, allow_player_occlusion=True)
                self.require_authority()
                return value
            if self._cancel.is_set():
                return self.snapshot()
            self.require_authority()
            if hasattr(self.driver, "arm"):
                self.driver.arm()
            result = self.controller.perform_input(command, current, self.driver, after)
            self.screen = result
            if self.gameplay_agent:
                self.gameplay_agent.effect(self, command, current, result)
            if command.purpose == "navigate" and getattr(self.navigator, "poses", None):
                self._pending_navigation_observation = result
            self._retain("step", {"before": asdict(current), "command": asdict(command), "after": asdict(result),
                                  "driver_timing":getattr(self.driver,"last_pulse_timing",None)})
        except Exception as exc:
            # A canceled native pulse can finish after Pause/reclaim has already
            # revoked authority. Preserve that control's terminal state/reason;
            # the draining worker must not overwrite it with an input error.
            if self._cancel.is_set() and self.status != "completed":
                return self.ui_snapshot()
            reason = self._failure_reason("stardew_tick", exc)
            active = self.controller.active_attempt if self.controller else None
            detail = active.first_unmet_requirement if active else None
            self.control("stop", reason=detail or reason)
        return self.ui_snapshot()

    def _retain(self, kind: str, value: dict) -> None:
        if self.evidence_root is None:
            return
        if kind == "outcome" and self.controller and isinstance(self.controller.operator.ledger, FarmLedger):
            value = {**value, "task_ledger": asdict(self.controller.operator.ledger)}
        name = f"{len(self._evidence_files):04d}-{kind}-{uuid4().hex}.json"
        pending = self.evidence_root / (name + ".pending")
        try:
            # Publish only a complete JSON record. A failed write may leave a
            # .pending file, which is never included in required evidence.
            payload = json.dumps(value, default=lambda obj: sorted(obj) if isinstance(obj, set) else str(obj), sort_keys=True, indent=2)
            with pending.open("x") as stream:
                stream.write(payload)
            os.replace(pending, self.evidence_root / name)
        except Exception as exc:
            self.evidence_error = f"{kind} evidence could not be saved ({type(exc).__name__})."
            log_failure(LOGGER, "stardew_evidence_" + kind, exc)
            raise StardewAdapterError(self.evidence_error) from exc
        self._evidence_files.append(name)

    @staticmethod
    def _failure_reason(phase: str, exc: Exception) -> str:
        if isinstance(exc, StardewAdapterError):
            if str(exc) == "camera anchor not recognized":
                return "Farm view not recognized. Close game menus and use the supported daylight farm with zoom 75% and UI 100%. If this disposable Day 2 copy has reached night, exit to title without sleeping or saving and reload it. Open the game menu during long breaks to pause the clock."
            return str(exc)
        log_failure(LOGGER, phase, exc)
        return f"Unexpected farm operation failure ({type(exc).__name__}); inspect the local diagnostics."

    def control(self, action: str, *, reason: str | None = None) -> dict:
        if action == "focus_lost":
            action, reason = "pause", "Game focus was lost; neutral input and fresh review are required."
        if action == "resume":
            # Resume is a fresh review/start operation, never restored authority.
            self.reason = "Observe the current complete set, review the remaining work, and press Start for fresh authority."
            return self.snapshot()
        if action not in {"pause", "stop", "reclaim", "take_control", "cancel"}:
            raise StardewAdapterError("unsupported Stardew control")
        if self._goal_preparation:
            self._goal_preparation.stop()
        self._cancel.set()  # revoke before native cleanup, including failures
        neutral_failure = None
        if self._preparation_driver:
            self._generation += 1
            try:
                self._preparation_driver.neutralize()
                self._preparation_neutral_failure = None
            except Exception as exc:
                log_failure(LOGGER, "stardew_preparation_neutralize", exc)
                neutral_failure = f"preparation input release failed ({type(exc).__name__})"
                self._preparation_neutral_failure = neutral_failure
        neutral_failure = neutral_failure or self._preparation_neutral_failure
        self._pending_navigation_observation = None
        if self.driver:
            try:
                self.driver.neutralize()
            except Exception as exc:
                log_failure(LOGGER, "stardew_neutralize", exc)
                neutral_failure = f"input release failed ({type(exc).__name__})"
        with self._authority_lock:
            self._generation += 1
            self.status = "stopping"
        if self.controller and self.driver:
            active = self.controller.active_attempt
            if active and active.status.value == "active":
                self.controller.stop_active(self.driver, reason=reason or action)
            else:
                self.controller.operator.reclaim(self.driver)
                self.controller.authorization = None
            if not self.controller.operator.input_neutralized:
                neutral_failure = neutral_failure or "input neutralization could not be verified"
            if active:
                try:
                    self._retain("outcome", attempt_payload(active))
                except Exception as exc:
                    # Also cover outcome construction before _retain is called.
                    # Reporting must not interrupt final authority revocation.
                    if self.evidence_error is None:
                        self.evidence_error = f"outcome evidence could not be saved ({type(exc).__name__})."
                        log_failure(LOGGER, "stardew_outcome", exc)
        self.status = "paused" if action == "pause" else "stopped"
        self.reason = reason or ("Paused with neutral input; fresh review and Start required." if action == "pause" else "Control returned to the player.")
        if neutral_failure:
            self.status, self.reason = "failed", f"Input authority ended; neutral handback unconfirmed: {neutral_failure}"
        if self.evidence_error:
            self.status = "failed"
            self.reason += " " + self.evidence_error + " The in-memory outcome remains available; saved history may be incomplete."
        self._review_digest = None
        if self.cave_result and self.cave_result.get("status") == "running":
            self.cave_result.update(status="stopped", reason=self.reason,
                handback_confirmed=neutral_failure is None and bool(self.controller and self.controller.authorization is None))
            self._retain("cave-result", self.cave_result)
        if self.inspection_result and self.inspection_result.get("status") == "running":
            self.inspection_result.update(status="stopped", reason=self.reason,
                handback_confirmed=neutral_failure is None and bool(self.controller and self.controller.authorization is None))
        return self.snapshot()

    def ui_snapshot(self) -> dict:
        return self.snapshot(compact=self.status == "running")

    def snapshot(self, *, compact: bool = False) -> dict:
        from smb3_agent.stardew_setup import prepared_engineering_farms
        ledger = self.controller.operator.ledger if self.controller else None
        outcome = attempt_payload(self.controller.active_attempt, compact=compact) if self.controller and self.controller.active_attempt else None
        return {"game_id": "stardew", "available": bool(self.setup_manager and self.controller and self.observer and self.driver and self.navigator) and self.status in {"ready", "running", "paused"},
                "qualified_profiles": self._profile_options(),
                "prepared_farms": [{"id": row["id"], "label": row["label"]} for row in prepared_engineering_farms()],
                "setup_steps": [
                    {"id": "farm", "label": "Verify saved test farm", "status": "complete" if getattr(getattr(self.setup_manager, "session", None), "input_ready", False) else "pending"},
                    {"id": "perception", "label": "Connect verified screen recognition", "status": "complete" if self.observer else "pending"}],
                "status": self.status, "reason": self.reason,
                "observation_refresh_timing": getattr(self, '_observation_refresh_timing', None),
                "evidence_error": self.evidence_error,
                "session_id": self.controller.save.nonce if self.controller else None,
                "observation_id": self.screen.observation_id if self.screen else None,
                "observation": asdict(self.screen) if self.screen else None,
                "ledger": ({**asdict(ledger), "confirmed_watered_ids": sorted(ledger.confirmed_watered_ids),
                            "remaining_count": ledger.remaining_count, "watered_count": ledger.watered_count} if ledger else None),
                "current_plan": self.current_plan.to_dict() if self.current_plan else None,
                "reviewed_observation": asdict(self._review_screen) if self._review_screen else None,
                "preparation_view": self.preparation_view,
                "goal_preparation": self._goal_preparation.result if self._goal_preparation else None,
                "cave_result": self.cave_result,
                "cave_available": self._cave_route is not None,
                "inspection_result": self.inspection_result,
                "outcome": outcome, "attempts": ([] if compact else self._retired_attempts) + ([attempt_payload(a, compact=compact) for a in self.controller.attempts] if self.controller else []),
                "owner": self.controller.operator.owner.value if self.controller else "player",
                "neutralized": not self._preparation_neutral_failure and (self.controller.operator.input_neutralized if self.controller else True),
                "handback_confirmed": not self._preparation_neutral_failure and
                    not (self._goal_preparation and self._goal_preparation.result.get('status') == 'preparing') and
                    (self.controller.operator.input_neutralized and self.controller.authorization is None if self.controller else True),
                "planning_observation": self.planning_context().observation,
                "setup": (self._engineering_launches[-1][0].status() if self._engineering_launches and not getattr(self.setup_manager, "session", None)
                          else self.setup_manager.status() if self.setup_manager and hasattr(self.setup_manager, "status") else None),
                "engineering_launches": [{**launch.status(), "returncode": process.poll()} for launch, process in self._engineering_launches]}

    def invalidate(self) -> dict:
        self.control("stop", reason="adapter switched; volatile observation and review invalidated")
        self.screen = self._review_screen = None
        self.current_plan = None
        self._review_digest = None
        return self.snapshot()

    def connect_live(self, *, profile, navigator: WateringNavigator, evidence_root: Path, backend=None) -> dict:
        """Wire the native backend only after independently verified loading/profile.

        This is an engineering API, deliberately unavailable to browser JSON. No
        profile, fixture or owner assertion is silently promoted to qualification.
        """
        from smb3_agent.stardew_adapter import MacVisibleStardewBackend
        from smb3_agent.stardew_input import MacOrdinaryInputDriver
        from smb3_agent.stardew_perception import VisibleWateringPerception
        from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
        if self.status in {"running", "stopping"} or self._tick_lock.locked():
            raise StardewAdapterError("neutral handback is required before live connection")
        if self.setup_manager is None or self.setup_manager.session is None:
            raise StardewAdapterError("select and verify an isolated disposable session first")
        if not profile.qualified():
            raise StardewAdapterError("a retained actual-live complete-farm calibration is required")
        if backend is None:
            loading = self.setup_manager.session.loading
            if loading is None:
                raise StardewAdapterError("verified loaded engineering process identity is required")
            native = MacVisibleStardewBackend(process_id=loading.process_id, process_started_at=loading.process_started_at)
        else:
            native = backend
        window = native.detect_window()
        self.setup_manager.require_verified(window)
        save = self.setup_manager.session.save
        perception = profile if isinstance(profile, PreparedFarmPixelProfile) else VisibleWateringPerception(profile)
        evidence_root = Path(evidence_root)
        evidence_root.mkdir(parents=True, exist_ok=True)
        expected = (window.process_id, window.process_started_at, window.window_id)
        cave_clock_paused = False
        def cave_clock(paused):
            nonlocal cave_clock_paused
            if cave_clock_paused == paused:
                return
            generation, running = self._generation, self.status == "running"
            def permission():
                if generation != self._generation:
                    raise StardewAdapterError("cave clock adjustment was canceled")
                if running:
                    self.require_authority()
            clock_driver = MacOrdinaryInputDriver(window_provider=native.detect_window,
                isolation_guard=self.setup_manager.require_verified, authority_guard=permission)
            try:
                permission()
                clock_driver.arm()
                clock_driver.send(InputCommand(InputKind.KEYBOARD, "escape", "press", 200,
                    purpose="pause_cave_clock" if paused else "resume_cave_clock"))
                cave_clock_paused = paused
                import time
                time.sleep(0.2)  # Capture the world after the menu transition, never its prior frame.
                permission()
                if backend is None and isinstance(profile, PreparedFarmPixelProfile):
                    from PIL import Image
                    from smb3_agent.stardew_view_settings import ViewSettingFeatures
                    current = native.detect_window()
                    self.setup_manager.require_verified(current)
                    path = native.capture(current, evidence_root / f"clock-effect-{uuid4().hex}.png")
                    permission()
                    menu_visible = ViewSettingFeatures().locate(
                        Image.open(path).convert('RGB'), 'options-icon', (350,130,1050,205)) is not None
                    cave_clock_paused = menu_visible
                    self._retain('clock-effect', {'requested_paused':paused,
                        'observed_menu_visible':menu_visible,'screenshot':str(path),
                        'observed_at':native.last_capture_started_at})
                    if menu_visible != paused:
                        raise StardewAdapterError('The expected game-owned menu transition was not observed; inspect before fresh review')
            finally:
                clock_driver.neutralize()
        self._cave_resume_clock = lambda: cave_clock(False)
        self._inference_clock = cave_clock
        tool_marker_enabled = False  # Ordinary preparation independently verifies Off.
        def set_tool_marker(enabled):
            nonlocal tool_marker_enabled, cave_clock_paused
            from smb3_agent.stardew_selected_scene import SelectedSceneProfile
            if backend is not None or not isinstance(profile, SelectedSceneProfile) or tool_marker_enabled == enabled:
                return
            from smb3_agent.stardew_view_settings import normalize_view
            generation, running = self._generation, self.status == 'running'
            def permission():
                if generation != self._generation:
                    raise StardewAdapterError('Tool marker transition canceled')
                if running:
                    self.require_authority()
            setting_driver = MacOrdinaryInputDriver(window_provider=native.detect_window,
                isolation_guard=self.setup_manager.require_verified,authority_guard=permission)
            result = {}
            self._preparation_driver = setting_driver
            try:
                if not enabled:
                    self._cancel.wait(.85)  # Let the reviewed can animation settle with neutral input.
                    permission()
                normalize_view(native,setting_driver,isolation=self.setup_manager.require_verified,
                    authority=permission,root=evidence_root,cancel=self._cancel,result=result,
                    tool_marker=enabled,marker_only=True)
                tool_marker_enabled = enabled
                cave_clock_paused = False
            finally:
                verified = [step for step in result.get('view_setting_steps',[])
                            if step['action'] == 'tool_hit_verified']
                if verified:
                    tool_marker_enabled = verified[-1]['enabled']
                if result.get('menu_open_observed') and not result.get('menu_closed_verified'):
                    cave_clock_paused = True
                setting_driver.neutralize()
                if self._preparation_driver is setting_driver:
                    self._preparation_driver = None
                self._retain('tool-marker-transition',result)
        def observe_native(*, refresh_menu=True, cave=False, marker_for_aim=False):
            if not cave:
                cave_clock(False)
                if not marker_for_aim:
                    set_tool_marker(False)
            current = native.detect_window()
            if (current.process_id, current.process_started_at, current.window_id) != expected:
                raise StardewAdapterError("configured process/window changed")
            self.setup_manager.require_verified(current)
            if isinstance(profile, PreparedFarmPixelProfile):
                # Pointer-only observation reveals the numerical energy tooltip.
                # It cannot click, select a tool, or restore gameplay authority.
                generation, running = self._generation, self.status == "running"
                def observation_permission():
                    if self._goal_preparation and self._goal_preparation.result.get("status") == "preparing" and self._goal_preparation.cancel.is_set():
                        raise StardewAdapterError("Preparation observation canceled.")
                    if generation != self._generation:
                        raise StardewAdapterError("observation pointer was canceled")
                    if running:
                        self.require_authority()
                pointer = MacOrdinaryInputDriver(window_provider=native.detect_window,
                    isolation_guard=self.setup_manager.require_verified, authority_guard=observation_permission)
                try:
                    pointer.arm()
                    from smb3_agent.stardew_farm_perception import FarmPixelProfile
                    if isinstance(profile, FarmPixelProfile) and refresh_menu:
                        profile.read_menu(native, pointer, evidence_root)
                    # Menu transitions may change SDL geometry. Bind the point to
                    # a fresh supported window, never to the pre-menu origin.
                    current = native.detect_window()
                    if (current.process_id, current.process_started_at, current.window_id) != expected:
                        raise StardewAdapterError("configured process/window changed after inventory")
                    self.setup_manager.require_verified(current)
                    bx, by, width, height = current.bounds
                    self._retain("pointer-geometry", {"window": asdict(current),
                        "profile_viewport": profile.viewport_size, "local_point": profile.hud_hover,
                        "screen_point": (bx+profile.hud_hover[0], by+profile.hud_hover[1]),
                        "coordinate_space": "normalized window points"})
                    if (width, height) != profile.viewport_size:
                        raise StardewAdapterError("viewport scale or dimensions changed before observation pointer")
                    pointer.expected_pointer_window = current
                    pointer.send(InputCommand(InputKind.MOUSE, "move", "move", 0,
                        target=(bx+profile.hud_hover[0], by+profile.hud_hover[1]), purpose="observe_energy_tooltip"))
                finally:
                    pointer.neutralize()
                if cave:
                    cave_clock(False)
                import time
                time.sleep(0.15)
                observation_permission()
            import time
            retry_deadline = time.monotonic() + 5
            for observation_attempt in range(8):
                cave_clock(False)
                capture = native.capture(current, evidence_root / f"screen-{uuid4().hex}.png")
                try:
                    if cave:
                        from smb3_agent.stardew_cave import CavePerception
                        if self._cave_baseline is None:
                            baseline = perception.recognize(capture, current, save)
                            from dataclasses import replace
                            baseline = replace(baseline, observed_at=getattr(native, 'last_capture_started_at', baseline.observed_at))
                            if baseline.unknown_regions:
                                raise StardewAdapterError("Cave baseline requires complete crop visibility.")
                            self._cave_baseline = baseline
                            # Baseline decoding and first sprite-bank calibration
                            # must not consume the movement view's freshness.
                            from smb3_agent.stardew_cave_avatar import _templates
                            refs = self._cave_route.config.get("avatar_references", [])
                            if refs:
                                _templates(tuple((p["image"], *p["foot_reference"]) for p in refs))
                            capture = native.capture(current, evidence_root / f"screen-{uuid4().hex}.png")
                        cave_clock(True)
                        value = CavePerception(profile, self._cave_route, self._cave_baseline).recognize(capture,current,save)
                    else:
                        value = perception.recognize(capture, current, save)
                    break
                except StardewAdapterError as exc:
                    # A visible ambient sprite may briefly cover an obstacle.
                    # No gameplay input or history update occurs while unknown;
                    # retain each failed frame and demand a new complete reading.
                    if (not isinstance(profile, PreparedFarmPixelProfile)
                            or not (str(exc).startswith("relevant obstacle ")
                                    or (isinstance(profile, FarmPixelProfile)
                                        and ((str(exc).startswith("farm target ")
                                              and str(exc).endswith(" is missing or occluded"))
                                             or str(exc) == "player moved during inventory observation; reacquire the farm"))
                                    or str(exc) in {"camera anchor not recognized",
                                        "player pants are ambiguous or absent", "player feet are unknown"})
                            or observation_attempt == 7 or time.monotonic() >= retry_deadline):
                        raise
                    self._retain("observation-retry", {"screenshot":str(capture),
                        "reason":str(exc), "attempt":observation_attempt+1})
                    import time
                    time.sleep(0.25)
                    observation_permission()
                    current = native.detect_window()
                    if (current.process_id, current.process_started_at, current.window_id) != expected:
                        raise StardewAdapterError("configured process/window changed during observation retry")
                    self.setup_manager.require_verified(current)
            from dataclasses import replace
            return replace(value, observed_at=getattr(native, "last_capture_started_at", value.observed_at))
        def acquire_target(command, current_window):
            if not isinstance(profile, PreparedFarmPixelProfile):
                return
            self.require_authority()
            before = self.screen
            from smb3_agent.stardew_farm_perception import FarmPixelProfile
            farm_profile = isinstance(profile, FarmPixelProfile)
            crop = next((c for c in before.crops if c.crop_id == command.reviewed_crop_id), None)
            if farm_profile:
                crop = next((t for t in before.farm.targets if t.target_id == command.reviewed_crop_id), None)
            if crop is None:
                raise StardewAdapterError("aim has no reviewed crop identity")
            from PIL import Image
            import time
            refreshed = None
            from smb3_agent.stardew_selected_scene import SelectedSceneProfile
            if backend is None and isinstance(profile,SelectedSceneProfile) and not tool_marker_enabled:
                set_tool_marker(True)
                refreshed = observe_native(marker_for_aim=True)
                self._validate(refreshed,allow_player_occlusion=True)
                if not self._task_unchanged(before,refreshed):
                    raise StardewAdapterError('Task changed during the observed tool marker transition')
                before = self.screen = refreshed
                pointer = MacOrdinaryInputDriver(window_provider=native.detect_window,
                    isolation_guard=self.setup_manager.require_verified,authority_guard=self.require_authority)
                try:
                    pointer.arm()
                    pointer.expected_pointer_window = native.detect_window()
                    pointer.send(InputCommand(InputKind.MOUSE,'move','move',0,
                        target=command.target,purpose='observe_farm_aim'))
                finally:
                    pointer.neutralize()
                current_window = native.detect_window()
            if farm_profile:
                # Full backpack observation temporarily opens a menu. Perform
                # it before the final aiming frame, then restore the requested
                # pointer and retain both original timestamps. This preserves
                # the existing resource and aiming freshness bounds.
                refreshed = observe_native()
                self._validate(refreshed, allow_player_occlusion=True)
                if not self._task_unchanged(before, refreshed):
                    raise StardewAdapterError("task changed while refreshing aimed resources")
                pointer = MacOrdinaryInputDriver(window_provider=native.detect_window,
                    isolation_guard=self.setup_manager.require_verified, authority_guard=self.require_authority)
                try:
                    pointer.arm()
                    pointer.send(InputCommand(InputKind.MOUSE, "move", "move", 0,
                        target=command.target, purpose="observe_farm_aim"))
                finally:
                    pointer.neutralize()
                current_window = native.detect_window()
            retry_deadline = time.monotonic() + 5
            for aiming_attempt in range(8):
                capture = native.capture(current_window, evidence_root / f"aim-{uuid4().hex}.png")
                try:
                    frame = (profile.verify_action_aim(command, Image.open(capture).convert("RGB"), before) if farm_profile else
                             profile.verify_aim(Image.open(capture).convert("RGB"), (crop.tile_x,crop.tile_y), before))
                    break
                except StardewAdapterError as exc:
                    if str(exc) not in {"camera anchor not recognized",
                            "player pants are ambiguous or absent", "player feet are unknown"} or aiming_attempt == 7 or time.monotonic() >= retry_deadline:
                        raise
                    self._retain("aim-observation-retry", {"screenshot":str(capture),
                        "reason":str(exc), "attempt":aiming_attempt+1})
                    import time
                    time.sleep(0.25)
                    self.require_authority()
                    current_window = native.detect_window()
                    if (current_window.process_id, current_window.process_started_at, current_window.window_id) != expected:
                        raise StardewAdapterError("configured process/window changed during aiming retry")
                    self.setup_manager.require_verified(current_window)
            aimed_at = native.last_capture_started_at
            # Aiming hides the numerical energy tooltip. Refresh it after the
            # marker check, requiring identical task state, rather than extending
            # the old resource timestamp to cover two captures.
            if farm_profile:
                # Reacquire the complete unobscured field and numerical resources
                # after aim, using the actual menu captured just above. Decode
                # still rejects that menu after five seconds or player movement.
                # This capture gets its own timestamp; no old fact is re-dated.
                refreshed = observe_native(refresh_menu=False)
            elif refreshed is None:
                refreshed = observe_native()
            self._validate(refreshed, allow_player_occlusion=True)
            if not self._task_unchanged(before, refreshed):
                raise StardewAdapterError("task changed while refreshing aimed resources")
            if max(abs(frame["origin"][i] - (refreshed.position.camera_origin_x,
                        refreshed.position.camera_origin_y)[i]) for i in (0, 1)) > 1:
                raise StardewAdapterError("camera moved after aiming; target must be reacquired")
            self._retain("aim", {"crop_id":command.reviewed_crop_id,"screenshot":str(capture),
                "observed_at":aimed_at,"player":frame["player"],
                "resource_observation_id":before.observation_id,
                "refreshed_resources":asdict(refreshed)})
            def ready_to_press():
                self.require_authority()
                now = datetime.now(timezone.utc)
                age = (now - datetime.fromisoformat(aimed_at)).total_seconds()
                resource_age = (now - datetime.fromisoformat(refreshed.observed_at)).total_seconds()
                self._retain("pre-click-freshness", {"crop_id":command.reviewed_crop_id,
                    "aim_age_seconds":age,"resource_age_seconds":resource_age,
                    "maximum_resource_age_seconds":self.maximum_observation_age,
                    "maximum_aim_age_seconds":3.0})
                self._validate(refreshed, allow_player_occlusion=True)
                # The newer complete state has already corroborated identical
                # player/camera/task geometry. Keep resources at the normal 2s
                # limit; the supplemental marker may span the two-frame capture
                # sequence, bounded separately at 3s. Neither timestamp changes.
                if not 0 <= age <= 3.0:
                    raise StardewAdapterError("visible aiming observation expired before click")
            return ready_to_press
        def confirm_target(command, current_window):
            from smb3_agent.stardew_farm_perception import FarmPixelProfile
            for attempt in range(2):
                try:
                    return acquire_target(command, current_window)
                except StardewAdapterError as exc:
                    # No mouse-down has occurred in this callback. Reacquire
                    # all menu/field/aim evidence once after transient occlusion
                    # or expiry; never reuse or re-date the failed observations.
                    transient = (str(exc) in {
                        "fresh visible inventory and calendar observation is required",
                        "stale or future visible observation",
                        "camera anchor not recognized", "player feet are unknown",
                        "player pants are ambiguous or absent"}
                        or (str(exc).startswith("farm target ")
                            and str(exc).endswith(" is missing or occluded")))
                    if not isinstance(profile, FarmPixelProfile) or attempt or not transient:
                        raise
                    self._retain("aim-reacquisition", {"reason": str(exc),
                        "attempt": attempt + 1, "mouse_press_emitted": False})
                    self.require_authority()
                    current_window = native.detect_window()
        def activate_native():
            # SDL can hide its window while Companion is foreground. Activate the
            # already verified process before looking for its on-screen window.
            # This explicit observation/Start hook never runs during agent input.
            if backend is None:
                current = native.activate_window()
            else:
                current = native.detect_window(require_foreground=False)
                if not current.foreground:
                    from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(current.process_id)
                    if app is None or not app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps):
                        raise StardewAdapterError("could not focus the reviewed game; focus it and retry Start")
            if (current.process_id, current.process_started_at, current.window_id) != expected:
                raise StardewAdapterError("cannot focus a changed game process/window")
            self.setup_manager.require_verified(current)
        self.controller = StardewCompanionController(save, manager=self.setup_manager.manager)
        self.observer, self.navigator, self.evidence_root = observe_native, navigator, evidence_root
        self.driver = MacOrdinaryInputDriver(window_provider=native.detect_window,
                    isolation_guard=self.setup_manager.require_verified, authority_guard=self.require_authority,
                    before_mouse_press=confirm_target if isinstance(profile, PreparedFarmPixelProfile) else None)
        def planting_native(*, inspection=False):
            from smb3_agent.stardew_planting import PlantingSurvey
            generation = self._generation
            current = native.detect_window()
            if (current.process_id, current.process_started_at, current.window_id) != expected:
                raise StardewAdapterError("configured process/window changed")
            self.setup_manager.require_verified(current)
            if not current.trusted:
                raise StardewAdapterError("Show the unobscured supported farm window before inspection.")
            capture = native.capture(current, evidence_root / f"planting-{uuid4().hex}.png")
            result = PlantingSurvey(profile).inspect(capture, session_id=save.nonce,
                observed_at=getattr(native, "last_capture_started_at", None), inspection=inspection)
            after = native.detect_window()
            self.setup_manager.require_verified(after)
            if (after.process_id, after.process_started_at, after.window_id) != expected or not after.trusted or generation != self._generation:
                raise StardewAdapterError("Planting inspection interrupted or game identity changed; inspect again.")
            return result
        self._cave_route = None
        self._cave_observer = None
        self._cave_baseline = None
        cave_manifest = Path("artifacts/stardew-cave-route.json")
        if isinstance(profile, PreparedFarmPixelProfile) and cave_manifest.is_file():
            from smb3_agent.stardew_cave import CaveRoute
            try:
                self._cave_route = CaveRoute(cave_manifest, profile_id=profile.profile_id)
            except (ValueError, OSError, KeyError):
                # An unavailable cave calibration cannot disable proven farm work.
                self._cave_route = None
        self._cave_observer = None
        self._cave_baseline = None
        if self._cave_route is not None:
            self._cave_observer = lambda: observe_native(cave=True)
        self._planting_observer = planting_native
        self._activate_game = activate_native
        self.status = "ready"
        return self.observe()

    def close(self) -> None:
        failures = []
        try:
            self.control("stop", reason="companion closed")
        except Exception:
            failures.append("Stardew stop or outcome retention unconfirmed")
        guardian = getattr(getattr(self, "driver", None), "external_guard", None)
        if guardian is not None:
            try:
                guardian.close()
            except Exception:
                failures.append("Stardew independent input release unconfirmed")
        # Continue every independent cleanup even when another owner fails.
        for launch, process in self._engineering_launches:
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            except Exception:
                failures.append("Isolated game closure unconfirmed; inspect retained process record")
            finally:
                watchdog = getattr(process, "_gc_watchdog", None)
                if watchdog is not None:
                    try:
                        watchdog.close()
                    except Exception:
                        failures.append("Isolated game watchdog closure unconfirmed")
        if failures:
            raise StardewAdapterError("; ".join(failures))
