"""Stardew-owned reviewed watering runtime. No Mario authority is reused.

A configured runtime receives an OS-verified isolated setup, a qualified visible
observer and ordinary input. The public default remains inspectable/unavailable.
Each tick is one bounded input followed by an exact visible postcondition; no
command queue survives pause, reclaim, focus loss, or session reset.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from smb3_agent.request_planning import ConversationPlan, PlanningContext
from smb3_agent.stardew_adapter import InputCommand, InputKind, InputOwner, OrdinaryInputDriver, ScreenObservation, StardewAdapterError
from smb3_agent.stardew_companion import StardewCompanionController, attempt_payload
from smb3_agent.stardew_farm_tasks import FARM_CONTRACT, FarmLedger, FarmObservation


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
        self._paused_scope: tuple[str, ...] | None = None
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
        window = native.detect_window(require_foreground=False)
        if window.window_id != loading.window_id:
            raise StardewAdapterError("verified game window changed before calibration connection")
        if not window.foreground:
            from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(window.process_id)
            if app is None or not app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps):
                raise StardewAdapterError("focus the verified engineering game and retry connection")
        return self.connect_live(profile=profile, navigator=navigator, evidence_root=root)

    def verify_engineering_session(self) -> dict:
        if self.status in {"running", "stopping"} or self._tick_lock.locked():
            raise StardewAdapterError("neutral handback is required before setup verification")
        if not self._engineering_launches or self.setup_manager is None:
            raise StardewAdapterError("open a dedicated engineering game before verifying its farm")
        launch, process = self._engineering_launches[-1]
        if process.poll() is not None:
            raise StardewAdapterError("the engineering game has exited")
        from smb3_agent.stardew_adapter import MacVisibleStardewBackend
        native = MacVisibleStardewBackend(process_id=launch.process_id, process_started_at=launch.process_started_at)
        window = native.detect_window(require_foreground=False)
        self.control("stop", reason="engineering session verification invalidates prior review")
        if self.controller and not self.controller.operator.input_neutralized:
            raise StardewAdapterError("neutral handback is unconfirmed")
        if self.controller:
            self._retired_attempts.extend(attempt_payload(attempt) for attempt in self.controller.attempts)
        self.controller = self.observer = self.driver = self.navigator = None
        self.screen = self._review_screen = None
        self.current_plan = None
        self._review_digest = None
        self._activate_game = None
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
        if prepared.is_file() and (registry.is_file() or farm_registration):
            from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
            from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator
            from smb3_agent.stardew_input import MacOrdinaryInputDriver
            from smb3_agent.stardew_setup import _verify_engineering_launch_identity
            registration = farm_registration or json.loads(registry.read_text())
            manifest = Path(registration["manifest"])
            evidence_base = Path("artifacts/b4-engineering" if farm_registration else "artifacts/b3-engineering").resolve()
            if (manifest.resolve() != manifest or evidence_base not in manifest.parents
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
            from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(window.process_id)
            if app is None or not app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps):
                raise StardewAdapterError("focus the engineering game and retry verification")
            import time
            for _ in range(20):
                window = native.detect_window(require_foreground=False)
                if window.foreground:
                    break
                time.sleep(0.025)
            window = native.detect_window()
            pointer = MacOrdinaryInputDriver(window_provider=native.detect_window,
                isolation_guard=lambda current: _verify_engineering_launch_identity(launch, current),
                authority_guard=lambda: None)
            try:
                pointer.arm()
                if farm_registration:
                    profile.read_menu(native, pointer, Path(launch.root))
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
        if not 0 <= age <= self.maximum_observation_age:
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

    def observe(self) -> dict:
        try:
            self._require_configured()
            if self.status == "running":
                return self.snapshot()
            if self._activate_game is not None:
                self._activate_game()
            screen = self.observer()
            self._validate(screen)
            envelope = self.controller.observe(screen)
            if not envelope.trusted:
                raise StardewAdapterError(envelope.stale_reasons[0])
            self.screen = screen
            self.reason = "Fresh farm state observed; review the requested work before Start. Previous outcomes remain in history."
            if self.status in {"unconfigured", "ready"}:
                self.status = "ready"
        except Exception as exc:
            if self.status == "running":
                self.control("stop", reason=str(exc))
            self.reason = str(exc)
        return self.snapshot()

    def setup(self, payload: dict) -> dict:
        # JSON may select a source copy, never assert calibration/isolation verification.
        if self.status in {"running", "stopping"} or self._tick_lock.locked() or (self._worker and self._worker.is_alive()):
            raise StardewAdapterError("reclaim and wait for neutral handback before changing the disposable session")
        self.control("stop", reason="disposable setup changed; old review invalidated")
        self.screen = self._review_screen = None
        self.current_plan = None
        self._review_digest = None
        if self.controller and not self.controller.operator.input_neutralized:
            raise StardewAdapterError("new setup refused because neutral handback is unconfirmed")
        if self.controller:
            self._retired_attempts.extend(attempt_payload(attempt) for attempt in self.controller.attempts)
        self.controller = self.observer = self.driver = self.navigator = None
        self._qualified_profiles.clear()
        self._activate_game = None
        self.status = "unconfigured"
        if self.setup_manager is None:
            from smb3_agent.stardew_setup import DisposableSessionSetup
            self.setup_manager = DisposableSessionSetup()
        action = payload.get("action", "create_owner_copy")
        if action == "launch_engineering":
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
            launch, process = launch_fresh_engineering(app, destination, **(
                {"prepared_id": payload["prepared_id"]} if payload.get("prepared_id") else {}))
            self._engineering_launches.append((launch, process))
            if process.poll() is not None:
                log_path = Path(launch.root) / "game.log"
                detail = log_path.read_text(errors="replace")[:400].strip() if log_path.is_file() else "launch log unavailable"
                self.reason = ("Stardew could not start because this Mac cannot currently run its Intel build. Complete Apple’s Rosetta setup, then open a fresh engineering session. No gameplay input was sent."
                               if "Bad CPU type" in detail else
                               f"The engineering game exited before setup completed (code {process.poll()}). Its launch log is retained in Session and evidence details.")
            else:
                self.reason = ("Prepared farm copied into a fresh isolated session. Choose Load in the game; fresh loading verification and observation are required. No gameplay authority restored."
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

    def planning_context(self, conversation_id: str = "stardew-conversation", current_plan=None) -> PlanningContext:
        valid = False
        if self.screen:
            try:
                self._validate(self.screen)
                valid = True
            except (ValueError, OSError):
                pass
        targets = [{"id": c.crop_id, "kind": "crop", "planted": c.planted, "watered": c.watered,
                    "visible": not c.occluded, "confidence": c.confidence}
                   for c in self.screen.crops if c.planted] if valid else []
        observation = {"source": "automatic_visible" if valid else "unavailable", "validated": valid,
                       "complete_initial_set": valid, "isolation_verified": valid,
                       "initial_target_ids": [t["id"] for t in targets], "return_point": "farmhouse_entrance",
                       "targets": targets}
        if valid and isinstance(self.screen.farm, FarmObservation):
            farm = self.screen.farm
            targets = [{"id": t.target_id, "kind": "crop" if t.planted else "debris" if t.state == "debris" else "plot",
                        "planted": t.planted, "ready": t.state == "mature", "state": t.state,
                        "species": t.species, "watered": t.watered, "protected": t.protected,
                        "visible": True, "confidence": 1} for t in farm.targets]
            observation.update(targets=targets, farm_contract=FARM_CONTRACT,
                               inventory=farm.counts(), season=farm.season, day=farm.day,
                               supported_actions=getattr(self.navigator, "supported_actions", ()))
        return PlanningContext(game_id="stardew", conversation_id=conversation_id,
                               session_id=self.controller.save.nonce if self.controller else None,
                               observation_id=self.screen.observation_id if valid else None,
                               observation=observation, current_plan=current_plan or self.current_plan,
                               selected_targets=tuple(targets), observation_fresh=valid)

    def review(self, plan: ConversationPlan) -> dict:
        if self.status in {"running", "stopping"} or self._tick_lock.locked() or (self._worker and self._worker.is_alive()):
            raise StardewAdapterError("pause and obtain fresh review after neutral handback before changing watering scope")
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
                if not crop.occluded and crop.watered != (previous.watered if not previous.occluded else key in confirmed):
                    return False
        return self._task_state(replace(before, position=q, crops=after.crops)) == self._task_state(after)

    def start(self, plan: ConversationPlan, *, background: bool = True) -> dict:
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
            farm_task = isinstance(self._review_screen.farm, FarmObservation)
            if plan.ambiguities or plan.unsupported_parts or not plan.actions or (not farm_task and any(a.kind != "water" for a in plan.actions)):
                raise StardewAdapterError("only unambiguous watering is executable without qualified B4 recognition")
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
            if not farm_task and (set(requested) != initial or len(requested) != len(initial)):
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
                self.controller.authorize_do(current, owner_confirmation=True, input_driver=InputKind.MOUSE,
                                             expires_at=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
                self.current_plan = plan
                self._cancel = threading.Event()
                self.status, self.reason = "running", ("Executing the reviewed farm routine. Keep the game foreground." if farm_task else "Watering the reviewed initial planted set. Keep the game foreground.")
                if background:
                    self._worker = threading.Thread(target=self._run, args=(self._cancel,), daemon=True, name="stardew-watering")
                    self._worker.start()
        return self.snapshot()

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
            remaining = set(ledger.initial_crop_ids) - ledger.confirmed_watered_ids
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
            active = self.controller.active_attempt if self.controller else None
            detail = active.first_unmet_requirement if active else None
            self.control("stop", reason=detail or str(exc))
        return self.ui_snapshot()

    def _retain(self, kind: str, value: dict) -> None:
        if self.evidence_root is None:
            return
        if kind == "outcome" and self.controller and isinstance(self.controller.operator.ledger, FarmLedger):
            value = {**value, "task_ledger": asdict(self.controller.operator.ledger)}
        name = f"{len(self._evidence_files):04d}-{kind}-{uuid4().hex}.json"
        with (self.evidence_root / name).open("x") as stream:
            json.dump(value, stream, default=lambda obj: sorted(obj) if isinstance(obj, set) else str(obj), sort_keys=True, indent=2)
        self._evidence_files.append(name)

    def control(self, action: str, *, reason: str | None = None) -> dict:
        if action == "focus_lost":
            action, reason = "pause", "Game focus was lost; neutral input and fresh review are required."
        if action == "resume":
            # Resume is a fresh review/start operation, never restored authority.
            self.reason = "Observe the current complete set, review the remaining work, and press Start for fresh authority."
            return self.snapshot()
        if action not in {"pause", "stop", "reclaim", "take_control", "cancel"}:
            raise StardewAdapterError("unsupported Stardew control")
        self._cancel.set()  # revoke before waiting for terminal commit or any lock
        self._pending_navigation_observation = None
        neutral_failure = None
        if self.driver:
            try:
                self.driver.neutralize()
            except Exception as exc:
                neutral_failure = str(exc)
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
                self._retain("outcome", attempt_payload(active))
        self.status = "paused" if action == "pause" else "stopped"
        self.reason = reason or ("Paused with neutral input; fresh review and Start required." if action == "pause" else "Control returned to the player.")
        if neutral_failure:
            self.status, self.reason = "failed", f"Input authority ended; neutral handback unconfirmed: {neutral_failure}"
        self._review_digest = None
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
                "session_id": self.controller.save.nonce if self.controller else None,
                "observation_id": self.screen.observation_id if self.screen else None,
                "observation": asdict(self.screen) if self.screen else None,
                "ledger": ({**asdict(ledger), "confirmed_watered_ids": sorted(ledger.confirmed_watered_ids),
                            "remaining_count": ledger.remaining_count, "watered_count": ledger.watered_count} if ledger else None),
                "current_plan": self.current_plan.to_dict() if self.current_plan else None,
                "reviewed_observation": asdict(self._review_screen) if self._review_screen else None,
                "outcome": outcome, "attempts": ([] if compact else self._retired_attempts) + ([attempt_payload(a, compact=compact) for a in self.controller.attempts] if self.controller else []),
                "owner": self.controller.operator.owner.value if self.controller else "player",
                "neutralized": self.controller.operator.input_neutralized if self.controller else True,
                "handback_confirmed": self.controller.operator.input_neutralized and self.controller.authorization is None if self.controller else True,
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
        def observe_native(*, refresh_menu=True):
            current = native.detect_window()
            if (current.process_id, current.process_started_at, current.window_id) != expected:
                raise StardewAdapterError("configured process/window changed")
            self.setup_manager.require_verified(current)
            if isinstance(profile, PreparedFarmPixelProfile):
                # Pointer-only observation reveals the numerical energy tooltip.
                # It cannot click, select a tool, or restore gameplay authority.
                generation, running = self._generation, self.status == "running"
                def observation_permission():
                    if generation != self._generation:
                        raise StardewAdapterError("observation pointer was canceled")
                    if running:
                        self.require_authority()
                pointer = MacOrdinaryInputDriver(window_provider=native.detect_window,
                    isolation_guard=self.setup_manager.require_verified, authority_guard=observation_permission)
                bx, by, _, _ = current.bounds
                try:
                    pointer.arm()
                    from smb3_agent.stardew_farm_perception import FarmPixelProfile
                    if isinstance(profile, FarmPixelProfile) and refresh_menu:
                        profile.read_menu(native, pointer, evidence_root)
                    pointer.send(InputCommand(InputKind.MOUSE, "move", "move", 0,
                        target=(bx+profile.hud_hover[0], by+profile.hud_hover[1]), purpose="observe_energy_tooltip"))
                finally:
                    pointer.neutralize()
                import time
                time.sleep(0.15)
                observation_permission()
            import time
            retry_deadline = time.monotonic() + 5
            for observation_attempt in range(8):
                capture = native.capture(current, evidence_root / f"screen-{uuid4().hex}.png")
                try:
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
            current = native.detect_window(require_foreground=False)
            if (current.process_id, current.process_started_at, current.window_id) != expected:
                raise StardewAdapterError("cannot focus a changed game process/window")
            if not current.foreground:
                # Explicit Start transfers focus to the already verified process.
                # No gameplay event is emitted until a new trusted observation.
                from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(current.process_id)
                if app is None or not app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps):
                    raise StardewAdapterError("could not focus the reviewed game; focus it and retry Start")
        self.controller = StardewCompanionController(save, manager=self.setup_manager.manager)
        self.observer, self.navigator, self.evidence_root = observe_native, navigator, evidence_root
        self.driver = MacOrdinaryInputDriver(window_provider=native.detect_window,
                    isolation_guard=self.setup_manager.require_verified, authority_guard=self.require_authority,
                    before_mouse_press=confirm_target if isinstance(profile, PreparedFarmPixelProfile) else None)
        self._activate_game = activate_native
        self.status = "ready"
        return self.observe()

    def close(self) -> None:
        self.control("stop", reason="companion closed")
        import subprocess
        # Popen handles belong only to namespaces launched by this runtime.
        # Do not discover or terminate other game processes or personal sessions.
        for launch, process in self._engineering_launches:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    raise StardewAdapterError("Isolated game did not close; inspect its retained process record")
