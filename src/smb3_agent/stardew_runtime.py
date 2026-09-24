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
from smb3_agent.stardew_adapter import InputCommand, InputKind, OrdinaryInputDriver, ScreenObservation, StardewAdapterError
from smb3_agent.stardew_companion import StardewCompanionController, attempt_payload


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

    def next_command(self, screen: ScreenObservation, remaining: set[str]) -> tuple[InputCommand | None, str | None]:
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
        return InputCommand(InputKind.KEYBOARD, path[0], "press", self.pulse_ms, purpose="navigate"), None


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
        self.setup_manager.verify_engineering_launch(launch, window)
        self.reason = "Engineering farm loading verified; connect its qualified screen calibration next."
        return self.snapshot()

    def _require_configured(self) -> None:
        if not all((self.setup_manager, self.controller, self.observer, self.driver, self.navigator)):
            raise StardewAdapterError("live watering requires verified isolated loading, automatic visible perception, and ordinary input")

    def _validate(self, screen: ScreenObservation) -> None:
        self._require_configured()
        screen.validate(self.controller.save.disposable_tree_sha256)
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
            if self.status in {"unconfigured", "ready"}:
                self.status, self.reason = "ready", "Fresh complete planted set observed; review watering before Start."
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
            launch, process = launch_fresh_engineering(app, destination)
            self._engineering_launches.append((launch, process))
            if process.poll() is not None:
                log_path = Path(launch.root) / "game.log"
                detail = log_path.read_text(errors="replace")[:400].strip() if log_path.is_file() else "launch log unavailable"
                self.reason = ("Stardew could not start because this Mac cannot currently run its Intel build. Complete Apple’s Rosetta setup, then open a fresh engineering session. No gameplay input was sent."
                               if "Bad CPU type" in detail else
                               f"The engineering game exited before setup completed (code {process.poll()}). Its launch log is retained in Session and evidence details.")
            else:
                self.reason = "Fresh isolated title-screen launch requested. No prepared farm is loaded; input is disabled."
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
            if plan.ambiguities or plan.unsupported_parts or not plan.actions or any(a.kind != "water" for a in plan.actions):
                raise StardewAdapterError("only unambiguous watering is executable before B4")
            if plan.stop_point != "farmhouse_entrance":
                raise StardewAdapterError("only the reviewed farmhouse entrance return point is supported")
            if self._activate_game is not None:
                self._activate_game()
            current = self.observer()
            self._validate(current)
            if self._task_state(current) != self._task_state(self._review_screen):
                raise StardewAdapterError("visible task conditions changed since review; observe and review again")
            initial = {c.crop_id for c in current.crops if c.planted}
            requested = [target for action in plan.actions for target in action.target_ids]
            if set(requested) != initial or len(requested) != len(initial):
                raise StardewAdapterError("watering v1 requires every initially planted crop exactly once; narrower scope is unsupported")
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
                self.screen = current
                self.controller.authorize_do(current, owner_confirmation=True, input_driver=InputKind.MOUSE,
                                             expires_at=(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat())
                self.current_plan = plan
                self._cancel = threading.Event()
                self.status, self.reason = "running", "Watering the reviewed initial planted set. Keep the game foreground."
                if background:
                    self._worker = threading.Thread(target=self._run, args=(self._cancel,), daemon=True, name="stardew-watering")
                    self._worker.start()
        return self.snapshot()

    def require_authority(self) -> None:
        if self._cancel.is_set() or self.status != "running" or self.controller is None or self.controller.authorization is None:
            raise StardewAdapterError("runtime authority has ended")
        if self.current_plan is None or plan_digest(self.current_plan) != self._review_digest:
            raise StardewAdapterError("reviewed plan identity changed")

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
            current = self.observer()
            self._validate(current)
            if self._cancel.is_set():
                return self.snapshot()
            ledger = self.controller.operator.ledger
            # All passive observations must equal the last actor-labeled state.
            if self.screen is None or self._task_state(current) != self._task_state(self.screen):
                raise StardewAdapterError("task changed outside a reconciled input")
            self.controller.observe(current)
            self.screen = current
            minimum = self.current_plan.resource_limits.get("minimum_energy")
            remaining = set(ledger.initial_crop_ids) - ledger.confirmed_watered_ids
            if remaining:
                cost = self.navigator.energy_cost_upper_bound
                if cost is None:
                    raise StardewAdapterError("watering energy cost bound is unknown")
                reserve = minimum if minimum is not None else 1
                if current.energy - cost < reserve:
                    raise StardewAdapterError("reviewed energy reserve would be crossed")
            command, _target = self.navigator.next_command(current, remaining)
            if command is None:
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
                value = self.observer()
                self._retain("post-observation", asdict(value))
                self.require_authority()
                self._validate(value)
                self.require_authority()
                return value
            if self._cancel.is_set():
                return self.snapshot()
            self.require_authority()
            if hasattr(self.driver, "arm"):
                self.driver.arm()
            result = self.controller.perform_input(command, current, self.driver, after)
            self.screen = result
            self._retain("step", {"before": asdict(current), "command": asdict(command), "after": asdict(result)})
        except Exception as exc:
            self.control("stop", reason=str(exc))
        return self.snapshot()

    def _retain(self, kind: str, value: dict) -> None:
        if self.evidence_root is None:
            return
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

    def snapshot(self) -> dict:
        ledger = self.controller.operator.ledger if self.controller else None
        outcome = attempt_payload(self.controller.active_attempt) if self.controller and self.controller.active_attempt else None
        return {"game_id": "stardew", "available": bool(self.setup_manager and self.controller and self.observer and self.driver and self.navigator) and self.status in {"ready", "running", "paused"},
                "qualified_profiles": self._profile_options(),
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
                "outcome": outcome, "attempts": self._retired_attempts + ([attempt_payload(a) for a in self.controller.attempts] if self.controller else []),
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
        perception = VisibleWateringPerception(profile)
        evidence_root = Path(evidence_root)
        evidence_root.mkdir(parents=True, exist_ok=True)
        expected = (window.process_id, window.process_started_at, window.window_id)
        def observe_native():
            current = native.detect_window()
            if (current.process_id, current.process_started_at, current.window_id) != expected:
                raise StardewAdapterError("configured process/window changed")
            self.setup_manager.require_verified(current)
            capture = native.capture(current, evidence_root / f"screen-{uuid4().hex}.png")
            return perception.recognize(capture, current, save)
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
                    isolation_guard=self.setup_manager.require_verified, authority_guard=self.require_authority)
        self._activate_game = activate_native
        self.status = "ready"
        return self.observe()

    def close(self) -> None:
        self.control("stop", reason="companion closed")
