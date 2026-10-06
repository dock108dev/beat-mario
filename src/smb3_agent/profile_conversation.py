"""Ordinary conversation service over the shared plan/session/history runtime."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import math
import threading
import time
import sys

from smb3_agent.game_profiles import ExecutableProfile, ProfileError
from smb3_agent.host_contracts import HostError
from smb3_agent.model_gateway import LocalOllamaGateway, ModelLimits
from smb3_agent.native_host import foreground_process_id
from smb3_agent.ordinary_input import MacProfileInput
from smb3_agent.paths import repository_path
from smb3_agent.prepared_game import PreparedGame
from smb3_agent.profile_runtime import ProfileRuntime
from smb3_agent.screen_host import MacSelectedWindowHost, profile_ocr_regions


def supported_profile():
    return ExecutableProfile.from_dict(json.loads(repository_path("data/private-beta/openttd-pb2.json").read_text()))


class ProfileConversationService:
    """Small state locks; model/capture/history run in task-owned workers.

    Heartbeats are a volatile client lease. Reopening never restores authority.
    Read-only observation can use an unobscured background game; input cannot.
    """
    PRIORITY = {"stop", "reclaim", "pause", "chat", "edit", "ui_disconnect", "cancel_pending"}

    def __init__(self, *, artifacts_root=Path("artifacts/private-beta/pb2/sessions"),
                 profile=None, launcher=None, runtime_factory=None, watchdog=True):
        self.player_store = None
        self.saved_profile_id = None
        self.profile = profile or supported_profile()
        self.profile.validate()
        self.root = Path(artifacts_root)
        self.launcher = launcher or PreparedGame(self.root / "games")
        self.runtime_factory = runtime_factory
        self.runtime = None
        self._lock = threading.RLock()
        self._worker = None
        self._generation = 0
        self._closed = False
        self._cleanup_confirmed = False
        self._watch_stop = threading.Event()
        self._heartbeat = 0
        self._client = None
        self._state = "Needs attention"
        self._reason = "Open a paused test game, open its Finances panel, then connect its window."
        self._plan = None
        self._outcome = None
        self._messages = []
        self._history = []
        self._controls = []
        self._selection = None
        self._bound_bounds = None
        self._window_rows = []
        self._display_rows = []
        self._request_changed = False
        self._operation_name = None
        self._watch = threading.Thread(target=self._watchdog, daemon=True, name="profile-watchdog")
        if watchdog:
            self._watch.start()

    def _phase(self, runtime, name):
        with self._lock:
            if runtime is self.runtime and (not runtime.cancel.is_set() or name == "Stopped"):
                self._state = name

    def _factory(self, selection, owned, folder):
        host = MacSelectedWindowHost(selection["pid"], selection["started"], selection["window_id"],
                                    background_observation=True,
                                    ocr_regions=profile_ocr_regions(self.profile))
        if not host.permissions()["capture"]:
            raise HostError("Screen capture permission is unavailable. Observation remains disabled.")
        frame = host.observe(folder / "connection-frames")
        frame.require_fresh(host.detect_window(require_foreground=False), self.profile.frame_max_age,
                            require_foreground=False)
        values = self.profile.values(frame)
        if frame.window.bounds[2:] != self.profile.viewport or values != dict(self.profile.skills[0].required_before):
            raise ProfileError("The selected window does not show the prepared £100,000 loan and cash")
        self.profile.target(frame, self.profile.skills[0])
        receipt = {"disposable": True, "load_save_verified": True, "selection": selection,
                   "isolation_basis": "user_confirmed_disposable_and_visible_entry_checks" if owned.get("user_confirmed_disposable") else "owned_checkpoint",
                   "game_build": owned["game_build"], "profile_sha256": self.profile.digest,
                   "save_sha256": owned["checkpoint_sha256"], "settings_sha256": owned["settings_sha256"],
                   "evidence_references": [str(frame.path)], "before_values": values}
        gateway = LocalOllamaGateway(self.profile.backend_id, limits=ModelLimits(calls=3, call_seconds=60, task_seconds=180))
        identity = gateway.describe()
        def driver(rt):
            import Quartz as q
            from smb3_agent.input_guardian import InputGuardian
            guardian = InputGuardian(folder/"input-guardian.jsonl") if host.permissions()["input"] else None
            def isolation(window):
                if (window.process_id, window.process_started_at, window.window_id) != (
                        selection["pid"], selection["started"], selection["window_id"]):
                    raise HostError("Exact selected process/window changed")
                if not host.permissions()["input"]:
                    raise HostError("Native input permission is unavailable")
            def fast_guard(window):
                rt.require_authority()
                if foreground_process_id() != window.process_id:
                    raise HostError("Foreground game changed during input")
            return MacProfileInput(window_provider=host.detect_window, isolation_guard=isolation,
                authority_guard=rt.require_authority, quartz=q, pulse_guard=fast_guard, external_guard=guardian)
        rt = ProfileRuntime(profile=self.profile, host=host, gateway=gateway, driver_factory=driver,
            root=folder/"runtime", isolation_receipt=receipt, observe_background=True)
        rt.state_callback = lambda phase: self._phase(rt, phase)
        try:
            source_paths = [*repository_path("src").rglob("*.py"), repository_path("data/private-beta/openttd-pb2.json")]
            manifest = {"schema": "game-companion-pb2-candidate/v1", "selection": selection,
                    "profile": asdict(self.profile), "profile_sha256": self.profile.digest,
                    "backend": identity, "limits": asdict(gateway.limits), "isolation": receipt,
                    "source_files": {str(p.relative_to(repository_path(""))): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(source_paths)}, "evidence_class": "ordinary_app_engineering_session"}
            (folder/"manifest.json").write_text(json.dumps(manifest, indent=2))
        except Exception:
            rt.control("connection_retention_failed")
            rt.driver.close()
            rt.close_events()
            raise
        self._bound_bounds = frame.window.bounds
        from smb3_agent.resource_samples import ResourceSamples
        rt.resources = ResourceSamples(rt)
        return rt

    def snapshot(self):
        with self._lock:
            rt = self.runtime
            busy = bool(self._worker and self._worker.is_alive())
            return {"schema_version": "game-companion-conversation/v1", "game_id": self.profile.game_id,
                "conversation_id": rt.conversation_id if rt else None,
                "engineering_launcher_available": not getattr(sys, "frozen", False),
                "state": self._state, "reason": self._reason, "busy": busy,
                "connected": rt is not None, "client_matches": self._client,
                "plan": self._plan.to_dict() if self._plan else None,
                "reviewed": bool(rt and rt._reviewed and not self._request_changed),
                "proposal_current": bool(rt and self._plan and not self._request_changed and not rt.cancel.is_set()),
                "outcome": deepcopy(self._outcome), "history": (self.player_store.history(self.saved_profile_id) if self.player_store and self.saved_profile_id else deepcopy(self._history[-20:])),
                "messages": deepcopy(self._messages[-16:]), "selection": deepcopy(self._selection),
                "profiles": [{"id": self.profile.profile_id, "label": "Paused company · repay £10,000 once"}],
                "windows": deepcopy(self._window_rows),
                "displays": deepcopy(self._display_rows),
                "runtime": {"owner": "agent" if rt and rt._authority else "player",
                    "status": rt.session.lifecycle.value if rt else "unconfigured",
                    "session_id": rt.session_id if rt else None,
                    "neutralized": bool(rt and rt.release["confirmed"]),
                    "release": dict(rt.release) if rt else {"confirmed": False, "method": "not_connected"},
                    "frame_id": rt.frame.frame_id if rt and rt.frame else None,
                    "values": rt.profile.values(rt.frame) if rt and rt.frame else None,
                    "permissions": rt.host.permissions() if rt else None,
                    "control_epoch": rt.control_epoch if rt else None,
                    "inference_pending": bool(rt and rt.gateway.inference_pending.is_set()),
                    "worker_pid": rt.gateway.worker_pid if rt else None,
                    "model_usage": deepcopy(rt.gateway.usage) if rt else [],
                    "backend": deepcopy(rt.gateway.backend_identity) if rt else None,
                    "evidence_root": str(rt.root) if rt else None,
                    "capabilities": self.profile.capabilities,
                    "controls": deepcopy(self._controls[-20:])}}

    def _control(self, action):
        # Revoke first. No service state/history lock is acquired before this.
        self._generation += 1
        rt = self.runtime
        receipt = rt.control(action) if rt else {"confirmed": True, "seconds": 0, "method": "no_agent_session"}
        receipt = {**receipt, "control_id": uuid4().hex}
        with self._lock:
            self._controls.append({"action": action, "at": time.monotonic(), **receipt})
            self._state = "Stopped" if receipt["confirmed"] else "Needs attention"
            self._reason = "Control returned. Review fresh state before starting again." if receipt["confirmed"] else "Input release is unconfirmed. New play and switching are blocked."
        return receipt

    def _submit(self, name, fn):
        with self._lock:
            if self._closed:
                raise ProfileError("The service is shutting down")
            if self._worker and self._worker.is_alive():
                raise ProfileError("Previous work is ending. Wait for neutral handback.")
            self._generation += 1
            generation = self._generation
            self._operation_name = name
            self._state = "Observing" if name in {"message", "observe", "connect"} else "Rechecking"
            self._reason = ""
            def work():
                started = time.monotonic()
                try:
                    result = fn(generation)
                    with self._lock:
                        if generation != self._generation:
                            return
                        if name == "message":
                            self._plan = result.plan
                            self._request_changed = False
                            self._state = "Ready to review" if result.plan and result.plan.actions else "Needs attention"
                            self._reason = "Review the single proposed repayment." if self._state == "Ready to review" else "Name a supported action explicitly; nothing will run."
                            self._messages.append({"role": "assistant", "text": self._reason})
                        elif name == "start":
                            self._outcome = result
                            self._history.append(result)
                            self._persist_outcome(result)
                            self._state = "Completed" if result["status"] == "completed" else "Needs attention"
                            self._reason = result["reason"] or "Both balances verified. Control returned to you."
                        else:
                            self._state = "Ready to start" if name == "review" else "Connected"
                            self._reason = "Start will focus and recheck the selected game." if name == "review" else "You control the game. Enter chat to describe one task."
                except Exception as exc:
                    if self.runtime:
                        self.runtime.control("operation_failed")
                    with self._lock:
                        if generation == self._generation:
                            self._state, self._reason = "Needs attention", str(exc)
                finally:
                    rt = self.runtime
                    if rt:
                        rt.event("operation_timing", {"operation": name, "seconds": time.monotonic()-started})
                    # Interrupted outcomes still enter history, never completion.
                    if name == "start" and 'result' in locals() and generation != self._generation:
                        with self._lock:
                            self._outcome = result
                            self._history.append(result)
                            self._persist_outcome(result)
            self._worker = threading.Thread(target=work, daemon=True, name="profile-"+name)
            self._worker.start()

    def _persist_outcome(self, result):
        if self.player_store and self.saved_profile_id:
            from smb3_agent.player_store import VERSION
            self.player_store.record(self.saved_profile_id, {
                "status": result["status"], "reason": result.get("reason", ""),
                "request": self._plan.request if self._plan and hasattr(self._plan, "request") else "Repay £10,000 once",
                "version": VERSION})

    def dispatch(self, action, payload=None):
        payload = payload or {}
        client = payload.get("client_id")
        if action == "heartbeat":
            if client == self._client:
                self._heartbeat = time.monotonic()
            return self.snapshot()
        if action in self.PRIORITY:
            receipt = self._control(action)
            if action in {"edit", "chat"} and self._plan:
                self._request_changed = True
            return {**self.snapshot(), "control_receipt": receipt}
        if self._closed:
            raise ProfileError("Service stopped; reconnect in a fresh session")
        if action == "windows":
            self._window_rows = self.launcher.windows()
            if self.runtime_factory is None:
                from smb3_agent.window_setup import available_displays
                self._display_rows = available_displays()
        elif action == "arrange":
            receipt = self._control("window_setup")
            if not receipt["confirmed"] or (self._worker and self._worker.is_alive()):
                raise ProfileError("Wait for confirmed handback before changing window setup")
            selection = payload.get("selection")
            if not isinstance(selection, dict) or set(selection) != {"pid", "started", "window_id"}:
                raise ProfileError("Select the exact current game window")
            eligible = self.launcher.windows()
            if not any(all(row.get(k) == v for k, v in selection.items()) for row in eligible):
                raise HostError("Selected window is not an eligible current OpenTTD window")
            from smb3_agent.window_setup import arrange_selected
            arrange_selected(selection, display_id=payload.get("display_id"), viewport=self.profile.viewport)
            self._window_rows = self.launcher.windows()
            self._request_changed = True
            self._state, self._reason = "Needs attention", "Supported window size arranged. Reconnect and review fresh game state."
        elif action == "launch":
            if getattr(sys, "frozen", False):
                raise ProfileError("Open a disposable company in OpenTTD itself, then connect its exact window")
            self._control("new_test_session")
            if self._worker and self._worker.is_alive():
                raise ProfileError("Previous work is ending")
            if self.runtime and not self.runtime.release["confirmed"]:
                raise ProfileError("Unconfirmed input release blocks a new game")
            self.launcher.close()
            self.launcher.launch()
            self._window_rows = self.launcher.windows()
            self._state, self._reason = "Needs attention", "Open Finances in the paused game, return here, and connect its exact window."
        elif action == "connect":
            if payload.get("profile_id") != self.profile.profile_id:
                raise ProfileError("Unknown supported profile")
            selection = payload.get("selection")
            if not isinstance(selection, dict) or set(selection) != {"pid", "started", "window_id"}:
                raise ProfileError("Exact process/start/window selection required")
            try:
                owned = self.launcher.binding(selection)
            except HostError:
                if payload.get("disposable_confirmation") is not True:
                    raise
                eligible = self.launcher.windows()
                if not any(all(row.get(key) == value for key, value in selection.items()) for row in eligible):
                    raise HostError("Selected window is not an eligible current OpenTTD window")
                owned = {"game_build": self.profile.game_build, "checkpoint_sha256": None,
                         "settings_sha256": None, "user_confirmed_disposable": True}
            receipt = self._control("connection_change")
            if not receipt["confirmed"]:
                raise ProfileError("Unconfirmed release blocks changing the connection")
            if self._worker and self._worker.is_alive():
                raise ProfileError("Previous work is ending")
            if self.runtime:
                if not self.runtime.driver.close() or not self.runtime.close_events():
                    raise ProfileError("Previous input/evidence worker cleanup is unconfirmed")
            self.runtime = None
            self._plan = self._outcome = None
            self._selection = selection
            self._client, self._heartbeat = client, time.monotonic()
            folder = self.root/"connections"/uuid4().hex
            folder.mkdir(parents=True, exist_ok=False)
            def connect(generation):
                rt = (self.runtime_factory or self._factory)(selection, owned, folder)
                with self._lock:
                    if generation != self._generation or self._closed:
                        rt.control("connection_canceled")
                        rt.driver.close()
                        rt.close_events()
                        raise ProfileError("Connection canceled")
                    self.runtime = rt
                rt.begin_chat()
            self._submit(action, connect)
        else:
            rt = self.runtime
            if not rt or client != self._client:
                raise ProfileError("Connect this page to the exact test window first")
            if action == "ui_timing":
                milliseconds = payload.get("milliseconds")
                matching = next((c for c in self._controls if c["control_id"] == payload.get("control_id")), None)
                if (not matching or type(milliseconds) not in {int, float}
                        or not math.isfinite(milliseconds) or not 0 <= milliseconds <= 10000):
                    raise ProfileError("Invalid UI acknowledgment timing")
                rt.event("ui_control_timing", {"control_id": matching["control_id"],
                    "action": matching["action"], "milliseconds": milliseconds,
                    "native_confirmed": matching["confirmed"], "handler_seconds": matching["seconds"]})
            elif action == "message":
                text = payload.get("text")
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                    raise ProfileError("Enter a bounded task request")
                from smb3_agent.request_planning import Planner
                direct = Planner({}).plan(text)
                if direct.control and direct.control["action"] in self.PRIORITY:
                    return self.dispatch(direct.control["action"], payload)
                self._control("new_request")
                self._messages.append({"role": "user", "text": text})
                self._plan = None
                self._submit(action, lambda generation: rt.propose(text))
            elif action == "observe":
                rt.begin_chat()
                self._submit(action, lambda generation: rt._observe())
            elif action in {"review", "start"}:
                plan = self._plan
                if (not plan or self._request_changed or payload.get("expected_plan_id") != plan.plan_id
                        or payload.get("expected_revision") != plan.revision):
                    raise ProfileError("The request or proposal changed; send and review fresh work")
                if action == "review":
                    self._submit(action, lambda generation: rt.review(plan))
                else:
                    if not rt._reviewed or not rt.release["confirmed"] or not rt.host.permissions()["input"]:
                        raise ProfileError("Fresh review and confirmed native input readiness required")
                    def start(generation):
                        rt.host.activate()
                        if generation != self._generation or rt.cancel.is_set():
                            raise ProfileError("Start canceled during focus transition")
                        return rt.start(plan)
                    self._submit(action, start)
            else:
                raise ProfileError("Unknown conversation action")
        return self.snapshot()

    def _watchdog(self):
        while not self._watch_stop.wait(.2):
            rt = self.runtime
            if not rt:
                continue
            # Quiescent stopped sessions need no repeated control receipts.
            if self._state in {"Stopped", "Needs attention", "Completed"} and not rt._authority:
                continue
            try:
                if time.monotonic()-self._heartbeat > 3:
                    raise HostError("App connection lost; pending work was canceled")
                if time.monotonic()-rt._started > rt.gateway.limits.task_seconds:
                    raise HostError("Session deadline expired; reconnect before new work")
                window = rt.host.detect_window(require_foreground=rt._authority)
                if self._bound_bounds is not None and window.bounds != self._bound_bounds:
                    raise HostError("Selected window moved or resized; reconnect and review")
                permissions = rt.host.permissions()
                if not permissions["capture"] or (rt._authority and not permissions["input"]):
                    raise HostError("Required native permission is unavailable")
                if rt._events.failed:
                    raise HostError("Evidence retention failed; execution stopped")
            except Exception as exc:
                self._control("watchdog")
                with self._lock:
                    self._state, self._reason = "Needs attention", str(exc)

    def invalidate_for_switch(self):
        receipt = self._control("switch")
        if self._worker and self._worker.is_alive():
            return False
        if self.runtime:
            self.runtime.invalidate_volatile_state()
        return receipt["confirmed"]

    def close(self):
        if self._cleanup_confirmed:
            return True
        self._closed = True
        receipt = self._control("service_shutdown")
        self._watch_stop.set()
        if self._watch.is_alive():
            self._watch.join(1.5)
        if self._worker:
            self._worker.join(4)
        if not receipt["confirmed"] or (self._worker and self._worker.is_alive()):
            raise HostError("Native release or task worker shutdown is unconfirmed")
        errors = []
        if self.runtime:
            for operation, label in ((self.runtime.close_events, "Evidence worker"),
                                     (self.runtime.driver.close, "Native guardian")):
                try:
                    if not operation():
                        errors.append(label+" shutdown is unconfirmed")
                except Exception as exc:
                    errors.append(label+" shutdown failed: "+str(exc))
        try:
            self.launcher.close()
        except Exception as exc:
            errors.append("Test game shutdown failed: "+str(exc))
        if errors:
            raise HostError("; ".join(errors))
        self._cleanup_confirmed = True
        return True
