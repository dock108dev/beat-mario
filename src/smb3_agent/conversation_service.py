"""Connect typed proposals, volatile Mario authority and local plan history."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from smb3_agent.custom_variants import CustomVariantStore, PlanAttemptHistory
from smb3_agent.request_planning import ConversationPlan, Planner


class ConversationService:
    def __init__(self, live_manager: Any, *, artifacts_root: Path = Path("artifacts/conversation"),
                 runtime: Any = None) -> None:
        if runtime is None:
            from smb3_agent.mario_plan_runtime import MarioPlanRuntime
            runtime = MarioPlanRuntime(live_manager)
        self.live_manager = live_manager
        self.runtime = runtime
        self.root = Path(artifacts_root)
        self.variants = CustomVariantStore(self.root / "variants")
        self.history = PlanAttemptHistory(self.root / "outcomes")
        self.planner = Planner()
        self.conversation_id = "conversation-" + uuid4().hex
        self._lock = threading.RLock()
        self._plan: dict[str, Any] | None = None
        self._current: dict[str, Any] | None = None
        self._pending: dict[str, Any] | None = None
        self._cancel_requested = False
        self._pending_command_id: str | None = None
        self._revisions: dict[int, dict[str, Any]] = {}
        self._messages: list[dict[str, Any]] = []
        self._requests: set[str] = set()
        self._attempt: dict[str, Any] | None = None
        self._outcome: dict[str, Any] | None = None
        self._last_message = "Select a route intent, then review the actual base and supported edit scope."

    def _message(self, role: str, text: str, kind: str) -> None:
        value = {"role": role, "text": text, "kind": kind,
                 "at": datetime.now(timezone.utc).isoformat()}
        self._messages.append(value)
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / f"{self.conversation_id}.jsonl").open("a") as stream:
            stream.write(json.dumps(value) + "\n")
        self._last_message = text

    def _live(self) -> tuple[Any, dict[str, Any]]:
        live = self.live_manager.snapshot()
        sample = live.samples[-1] if live.samples else None
        fresh = getattr(live.freshness, "value", live.freshness) == "fresh"
        observation_id = f"{live.session_id}:{sample.sequence}" if sample else None
        return live, {
            "game_id": "mario", "session_id": live.session_id,
            "observation_id": observation_id, "fresh": fresh,
            "checkpoint_id": live.checkpoint_id,
            "frame": sample.frame if sample else None,
            "x": sample.x if sample else None, "y": sample.y if sample else None,
        }

    def _context(self, *, current: dict[str, Any] | None = None) -> dict[str, Any]:
        live, observation = self._live()
        prior = deepcopy(current if current is not None else (self._pending or self._plan))
        # A plan prepared before explicit launch is a proposal; bind it to the new
        # observation without acquiring permission. Already-bound plans stay bound.
        if prior and prior.get("session_id") is None:
            prior["session_id"] = live.session_id
            prior["observation_id"] = observation["observation_id"]
        return {
            "game_id": "mario", "conversation_id": self.conversation_id,
            "session_id": live.session_id, "observation_id": observation["observation_id"],
            "observation": observation if live.session_id else {},
            "observation_fresh": observation["fresh"] if live.session_id else None,
            "current_plan": prior,
            "requested_speed": self.runtime.snapshot().get("requested_speed"),
            "applied_speed": self.runtime.snapshot().get("applied_speed"),
            "reviewed_edit_scope": ["path", "stop_point", "speed"] if self._active() else [],
            "supported_speeds": [1, "turbo"],
        }

    def _active(self) -> bool:
        return self._attempt is not None

    @staticmethod
    def _revision(runtime: dict[str, Any]) -> int | None:
        value = runtime.get("revision", runtime.get("current_revision"))
        return value if isinstance(value, int) else None

    def _sync(self) -> dict[str, Any]:
        runtime = self.runtime.snapshot()
        if hasattr(runtime, "to_dict"):
            runtime = runtime.to_dict()
        runtime = dict(runtime)
        if self._current is not None:
            self._current["applied_speed"] = runtime.get("applied_speed")
        revision = self._revision(runtime)
        actual_plan = runtime.get("plan")
        ack_id = runtime.get("applied_command_id") or (actual_plan or {}).get("application_command_id")
        if self._pending and revision == self._pending["revision"] and ack_id == self._pending_command_id:
            self._current = deepcopy(actual_plan or self._pending)
            self._plan = deepcopy(self._current)
            self._pending = None
            self._pending_command_id = None
            self._cancel_requested = False
            self._revisions[revision] = deepcopy(self._current)
            self._message("assistant", f"Revision {revision} applied at the supported boundary.", "applied")
        elif actual_plan and revision is not None and self._current and revision != self._current.get("revision"):
            # A superseded command may win the boundary race. Only the plan the
            # controller actually acknowledged enters history, never its replacement.
            self._current = deepcopy(actual_plan)
            self._revisions[revision] = deepcopy(actual_plan)
            self._message("assistant", f"Controller applied revision {revision}; a later replacement has not been acknowledged.", "applied")
        if self._pending and runtime.get("pending") is None and ack_id != self._pending_command_id:
            self._pending = None
            self._pending_command_id = None
            self._plan = deepcopy(self._current)
            detail = "Pending change canceled by the controller." if self._cancel_requested else (
                "Pending change was not applied: " + str(runtime.get("last_rejection") or runtime.get("outcome") or "execution ended"))
            self._cancel_requested = False
            self._message("assistant", detail, "cancelled")
        live, observation = self._live()
        if self._attempt:
            self._attempt["last_observation"] = observation
            self._attempt["runtime"] = deepcopy(runtime)
            self._attempt["actual_plan"] = deepcopy(self._current)
            self._attempt["revisions"] = deepcopy(list(self._revisions.values()))
            reason = live.takeover_terminal_reason
            if live.control_owner == "player" and (reason or runtime.get("state") == "finished"):
                terminal = str(runtime.get("outcome") or reason or "partial")
                self._finish(terminal, live, runtime)
        return runtime

    def _finish(self, terminal: str, live: Any, runtime: dict[str, Any]) -> None:
        if self._attempt is None:
            return
        record = deepcopy(self._attempt)
        frame = runtime.get("terminal_frame")
        if frame is None:
            # Failed/disconnected attempts without a terminal receipt keep the
            # last observation explicitly, rather than inventing a clear boundary.
            frame = live.samples[-1].frame if live.samples else None
        start_frame = runtime.get("start_frame", record.get("start_frame"))
        actors = {sample.actor for sample in live.samples
                  if getattr(sample, "buttons", ()) and getattr(sample, "actor", None) in {"player", "agent"}
                  and start_frame is not None and frame is not None
                  and start_frame <= sample.frame <= frame}
        actor = "mixed" if len(actors) > 1 else next(iter(actors), "agent")
        record.update({
            "status": terminal, "start_frame": start_frame, "terminal_frame": frame,
            "terminal_boundary_observed": runtime.get("terminal_frame") is not None,
            "elapsed_game_frames": frame - start_frame if frame is not None and start_frame is not None else None,
            "timing_units": "emulator_frames",
            "actor": actor,
            "actor_basis": "nonempty observed controller inputs within the attempt frame boundary",
            "speed_intervals": runtime.get("speed_intervals", []),
            "neutralized": live.input_neutralized,
            "controller_owner": live.control_owner,
            "runtime_evidence_path": str(live.artifact_dir) if live.artifact_dir else None,
            "pending_plan_at_stop": deepcopy(self._pending),
            "requested_objective_satisfied": None,
            "comparison_compatible": False,
            "comparison_reason": "Session-plan timing includes its actual entry/stop; compare only matching boundaries and actor classes.",
        })
        path = self.history.record(record["attempt_id"], record)
        record["evidence_path"] = str(path)
        self._outcome = record
        self._attempt = None
        self._pending = None
        self._message("assistant", f"Session {terminal.replace('_', ' ')}. Actual actions and timing are retained; full completion remains unknown.", "outcome")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            runtime = self._sync()
            live, observation = self._live()
            runtime.setdefault("owner", live.control_owner)
            runtime.setdefault("session_id", live.session_id)
            runtime.setdefault("neutralized", live.input_neutralized)
            runtime.setdefault("frame", observation["frame"])
            runtime.setdefault("status", runtime.get("state", "idle"))
            runtime.setdefault("performance_limitation", runtime.get("speed_limitation"))
            runtime.setdefault("pending_revision", (runtime.get("pending") or {}).get("revision"))
            return {
                "schema_version": "game-companion-conversation/v1",
                "conversation_id": self.conversation_id, "game_id": "mario",
                "plan": deepcopy(self._plan), "current_plan": deepcopy(self._current),
                "pending_plan": deepcopy(self._pending), "runtime": runtime,
                "messages": deepcopy(self._messages[-60:]), "message": self._last_message,
                "variants": self.variants.list(), "outcome": deepcopy(self._outcome),
                "history": self.history.list(), "revisions": deepcopy(list(self._revisions.values())),
                "live": {"session_id": live.session_id,
                         "observation_active": live.observation_active,
                         "process_alive": live.process_alive if live.process_alive is not None else bool(live.emulator_pid),
                         "takeover_capable": live.takeover_capable, "reason": live.reason},
            }

    def _bound_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        live, observation = self._live()
        if not live.session_id or not observation["fresh"]:
            raise ValueError("Open a visible companion session and wait for a fresh observation")
        if plan.get("session_id") not in {None, live.session_id}:
            raise ValueError("This plan belongs to another session; select or reopen it for this session")
        result = deepcopy(plan)
        result.update({"session_id": live.session_id, "observation_id": observation["observation_id"],
                       "conversation_id": self.conversation_id})
        return result

    def _queue(self, plan: dict[str, Any], request_id: str) -> None:
        if plan.get("ambiguities") or plan.get("execution_eligibility") in {"blocked", "unsupported", "planning_only", "clarification_required"}:
            raise ValueError("Resolve the plan's unsupported actions or material clarification before applying")
        plan = self._bound_plan(plan)
        state = self.runtime.snapshot()
        current_revision = self._revision(state)
        if current_revision is None:
            raise ValueError("The controller has no current revision to edit")
        plan["parent_revision"] = current_revision
        plan["revision"] = current_revision + 1
        plan["application_command_id"] = request_id
        queued = self.runtime.queue_edit(plan, expected_revision=current_revision, command_id=request_id,
                                         replace_pending=self._pending is not None)
        boundary = ((queued or {}).get("pending") or {}).get("effective_boundary")
        if boundary:
            plan["effective_boundary"] = boundary
        self._pending = plan
        self._cancel_requested = False
        self._pending_command_id = request_id
        self._plan = plan
        self._message("assistant", f"Revision {plan['revision']} pending at {plan.get('effective_boundary')}; the current plan continues until acknowledgment.", "pending")

    def dispatch(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        request_id = str(payload.get("request_id") or uuid4().hex)
        with self._lock:
            self._sync()
            if request_id in self._requests:
                return self.snapshot()
            self._requests.add(request_id)
            try:
                self._dispatch(action, payload, request_id)
            except (ValueError, OSError) as exc:
                self._message("assistant", str(exc), "error")
                raise
            return self.snapshot()

    def _dispatch(self, action: str, payload: dict[str, Any], request_id: str) -> None:
        if action in {"start", "apply"} and (
            self._plan is None
            or payload.get("expected_plan_id") != self._plan.get("plan_id")
            or type(payload.get("expected_revision")) is not int
            or payload["expected_revision"] != self._plan.get("revision")
        ):
            raise ValueError("The reviewed plan has changed. Review the current plan before Start or Apply.")
        if action == "select_intent":
            context = self._context()
            context["current_plan"] = None
            result = self.planner.plan("existing base route" if payload.get("intent") in {None, "base"} else str(payload["intent"]), context)
            if result.plan:
                self._plan = result.plan.to_dict()
            self._message("assistant", result.message, result.kind)
        elif action == "message":
            text = str(payload.get("text", "")).strip()
            self._message("user", text, "request")
            result = self.planner.plan(text, self._context())
            self._message("assistant", result.message, result.kind)
            if result.control:
                self._dispatch(result.control["action"], {"rate": result.control.get("speed")}, request_id)
            elif result.plan and result.kind != "advisory":
                self._plan = result.plan.to_dict()
                if result.apply_requested and self._active():
                    self._queue(self._plan, request_id)
        elif action == "start":
            if self._active():
                raise ValueError("A bounded plan is already running")
            if self._plan is None:
                raise ValueError("Select and review a plan first")
            plan = self._bound_plan(self._plan)
            started_runtime = self.runtime.start(plan)
            self._plan = self._current = plan
            self._revisions = {plan["revision"]: deepcopy(plan)}
            live, observation = self._live()
            self._attempt = {"attempt_id": "plan-" + uuid4().hex,
                             "conversation_id": self.conversation_id, "session_id": live.session_id,
                             "requested_objective": plan["requested_objective"],
                             "initial_plan": deepcopy(plan), "start_frame": (started_runtime or {}).get("start_frame", observation["frame"]),
                             "starting_observation": observation,
                             "started_at": datetime.now(timezone.utc).isoformat()}
            self._message("assistant", "Started the reviewed bounded plan. Opening path and supported stop edits are included; other changes need review.", "started")
        elif action == "apply":
            if self._plan is None:
                raise ValueError("There is no proposed change")
            if self._active():
                self._queue(self._plan, request_id)
            else:
                self._message("assistant", "Plan reviewed. Start authorizes it in a compatible visible session.", "reviewed")
        elif action == "cancel_pending":
            if self._pending:
                self.runtime.cancel_pending(command_id=request_id)
                self._cancel_requested = True
            else:
                self._plan = deepcopy(self._current or self._plan)
            self._message("assistant", "Cancellation requested. Controller acknowledgment determines whether the edit was still pending; completed actions remain in history.", "cancelled")
        elif action == "revert":
            if not self._revisions:
                raise ValueError("No earlier session revision is available")
            revision = int(payload.get("revision") or min(self._revisions))
            if revision not in self._revisions:
                raise ValueError("That revision is not part of this session")
            plan = deepcopy(self._revisions[revision])
            if self._pending and self._current and revision == self._current["revision"]:
                self._dispatch("cancel_pending", {}, request_id)
            elif self._active():
                self._queue(plan, request_id)
            else:
                self._plan = plan
            self._message("assistant", "Future steps reverted for review/application. This does not undo completed game actions.", "revert")
        elif action in {"pause", "resume", "stop", "reclaim", "speed"}:
            self.runtime.control(action, speed=payload.get("rate") if action == "speed" else None,
                                 command_id=request_id)
            if action == "speed":
                for plan in (self._plan, self._current, self._pending):
                    if plan is not None:
                        plan["requested_speed"] = payload.get("rate")
            self._message("assistant", f"{action.capitalize()} requested; controller acknowledgment is shown in status.", "control")
        elif action == "save_variant":
            if self._plan is None:
                raise ValueError("Prepare a custom plan before saving")
            outcome_plan = (self._outcome or {}).get("actual_plan") or {}
            matching_outcome = bool(self._outcome) and all(
                outcome_plan.get(key) == self._plan.get(key)
                for key in ("request_id", "revision", "session_id")
            )
            record = self.variants.save(str(payload.get("name", "")), self._plan,
                                        variant_id=self._plan.get("variant_id"),
                                        source_outcome_reference=self._outcome.get("evidence_path") if matching_outcome else None,
                                        runtime_evidence_reference=str(self.live_manager.snapshot().artifact_dir or ""))
            self._plan["variant_id"] = record["variant_id"]
            self._message("assistant", f"Saved {record['name']} revision {record['saved_revision']}. Execution requires fresh validation; this is not an accepted or fastest route.", "saved")
        elif action == "load_variant":
            if self._active():
                raise ValueError("Reclaim before reopening a saved variant")
            record = self.variants.load(str(payload.get("variant_id", "")), game_id="mario")
            plan = ConversationPlan.from_dict(record["plan"]).to_dict()
            from smb3_agent.mario_plan_runtime import runtime_fields
            from smb3_agent.mario_route_plan import resolve_base_route
            base = resolve_base_route()
            if plan.get("base_route_id") != base["goal_id"] or str(plan.get("base_version")) != str(base["solution_version"]):
                raise ValueError("The saved base route or version is no longer compatible")
            runtime_fields({**plan, "session_id": "compatibility-check"})
            live, observation = self._live()
            plan.update({"session_id": live.session_id, "observation_id": observation["observation_id"],
                         "conversation_id": self.conversation_id})
            self._plan = plan
            self._message("assistant", f"Reopened {record['name']}. Review and Start in a compatible state; no control permission was restored.", "loaded")
        else:
            raise ValueError("Unsupported conversation action")

    def close(self) -> None:
        with self._lock:
            if self._active():
                self.runtime.control("stop", command_id=uuid4().hex)
                self._sync()
