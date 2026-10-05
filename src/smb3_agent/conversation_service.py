"""Connect typed proposals, volatile Mario authority and local plan history."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import threading
import time
from typing import Any
from uuid import uuid4

from smb3_agent.custom_variants import CustomVariantStore, PlanAttemptHistory
from smb3_agent.mario_coaching import CoachingStore, COMPATIBILITY, timing_adjustment, urgent_control
from smb3_agent import mario_coins, mario_demonstrations, mario_flight
from smb3_agent.outcome_review import outcome_review
from smb3_agent.request_planning import ConversationPlan, Planner, is_advisory, normalized_text
from smb3_agent.profile_conversation import ProfileConversationService as ProfileConversationService


def _retain_refusal(service: Any, action: str, payload: dict, reason: str, game: str) -> None:
    service.history.record("refused-" + uuid4().hex, {
        "game_id": game, "status": "refused", "reason": reason,
        "request": str(payload.get("text") or action),
        "reviewed_plan": deepcopy(service._plan),
        "input_authorized_by_request": False,
    })
    if hasattr(service, "_history_summary_cache"):
        service._history_summary_cache = None


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
        self.demonstrations = mario_demonstrations.DemonstrationStore(self.root / "demonstrations")
        self.recording = mario_demonstrations.PlayerRecording(live_manager)
        self._demo_review = None
        self.route_guidance_store = CoachingStore(self.root / "route-guidance.json")
        self.coaching = CoachingStore(self.root / "coaching.json")
        self._retry_scope: dict[str, Any] | None = None
        self._control_generation = 0
        self._interrupted = threading.Event()
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
        self._history_signature = None
        self._history_rows_cache = []
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
        from smb3_agent.live_observation import observed_level_id
        level_id = observed_level_id(live.samples) if sample and hasattr(sample, "object_set") else None
        return live, {
            "game_id": "mario", "session_id": live.session_id,
            "observation_id": observation_id, "fresh": fresh,
            "checkpoint_id": live.checkpoint_id,
            "level_id": level_id,
            **{key: getattr(sample, key, None) for key in ("form", "air", "p_meter", "flight_timer", "lives", "player_is_dying", "return_map")},
            "frame": sample.frame if sample else None,
            "x": sample.x if sample else None, "y": sample.y if sample else None,
        }

    def _context(self, *, current: dict[str, Any] | None = None) -> dict[str, Any]:
        live, observation = self._live()
        prior = deepcopy(current if current is not None else (self._pending or self._plan))
        # Flight scopes have their own immutable contract. Generic route
        # proposals start independently rather than inheriting that primitive.
        if prior and prior.get("flight_compatibility"):
            prior = None
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
        self.recording.sync()
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
                # The live watchdog can publish failure while the Lua terminal
                # receipt is arriving. Refresh before freezing the result.
                runtime = dict(self.runtime.snapshot())
                native_terminal = next((row for row in reversed(runtime.get("events", []))
                                        if row.get("event") == "terminal"), {})
                if native_terminal and runtime.get("native_neutral_ack") is False:
                    return runtime
                terminal = str(native_terminal.get("reason") or runtime.get("outcome") or reason or "partial")
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
        if record.get("initial_plan", {}).get("coaching_compatibility") == COMPATIBILITY:
            expected = record["initial_plan"].get("jump_delay_frames", 0)
            applied = any(event.get("event") == "alternate_started"
                          and str(event.get("jump_delay_frames")) == str(expected)
                          for event in runtime.get("events", []))
            record["coaching_result"] = {
                "compatibility": COMPATIBILITY, "requested_delay_frames": expected,
                "controller_application_observed": applied,
                "segment_completed": terminal == "completed_stop",
                "improvement_observed": None,
                "explanation": "Timing receipt confirms application only; improvement is unknown.",
            }
            # Compare only the same cartridge, fresh-power-on entry and opening
            # objective. We measure reaching the stop, never infer route quality.
            if applied and record.get("cartridge_sha256") and record["starting_observation"].get("checkpoint_id") == "fresh_power_on":
                for prior in self.history.list():
                    comparison = prior.get("coaching_result", {})
                    initial = prior.get("initial_plan", {})
                    if (comparison.get("compatibility") == COMPATIBILITY
                            and comparison.get("controller_application_observed")
                            and prior.get("cartridge_sha256") == record["cartridge_sha256"]
                            and prior.get("starting_observation", {}).get("checkpoint_id") == "fresh_power_on"
                            and initial.get("requested_speed") == record["initial_plan"].get("requested_speed")
                            and comparison.get("requested_delay_frames") != expected
                            and prior.get("status") in {"death", "completed_stop"}
                            and terminal in {"death", "completed_stop"}):
                        improved = terminal == "completed_stop" and prior["status"] == "death"
                        helped = improved if terminal == "death" or prior["status"] == "death" else None
                        record["coaching_result"].update(
                            comparison_attempt_id=prior.get("attempt_id"),
                            improvement_observed=helped,
                            explanation=("Observed improvement: opening stop reached after a prior death; causation and broader strategy remain unknown."
                                         if improved else "Timing was applied but did not improve observed stop completion."
                                         if helped is False else "Both reached the opening stop; no improvement established."))
                        break
            if terminal not in {"completed_stop", "death"} or not live.input_neutralized:
                self._retry_scope = None
        demo = record.get("initial_plan", {}).get("demonstration")
        if demo:
            events = runtime.get("events", [])
            record["demonstration_result"] = {
                "id": demo["id"], "name": demo["name"], "lesson": demo["lesson"],
                "trace_sha256": demo["trace_sha256"], "strategy": "recorded_sequence",
                "application_observed": any(row.get("event") == "demonstration_applied" for row in events),
                "frames_followed": sum(row.get("event") == "demonstration_frame" for row in events),
                "sequence_completed_observed": any(row.get("event") == "demonstration_sequence_completed" for row in events),
                "stopped_because": runtime.get("outcome"), "helped_overcome_failure": None,
                "improvement": "unknown; sequence application does not establish improvement",
                "terminal_observation": record.get("last_observation"),
            }
        if record.get("initial_plan", {}).get("coin_compatibility") == mario_coins.COMPATIBILITY:
            events = runtime.get("events", [])
            result = mario_coins.reconcile(events, finished=any(
                row.get("event") == "coin_level_finish_observed" for row in events))
            result["controller_application_observed"] = any(
                not demo and row.get("event") == "coin_route_applied" and row.get("route") == record["initial_plan"]["path_choice"]
                for row in events)
            prior_rows = mario_coins.compatible(self.history.list(limit=100000), record.get("cartridge_sha256"))
            bands = result["completed_landmarks"]
            prior_yield = max((sum(row["coin_result"]["segment_yields"].get(name, 0) for name in bands)
                               for row in prior_rows if row["coin_result"].get("collected") is not None), default=0)
            result["known_missed_lower_bound"] = (max(0, prior_yield - sum(
                result["segment_yields"][name] for name in bands))
                if result["collected"] is not None else None)
            result["unvisited_landmarks"] = [name for name in mario_coins.LANDMARKS
                                             if name not in result["completed_landmarks"]]
            guidance = record["initial_plan"].get("route_guidance")
            if guidance:
                result["route_guidance"] = deepcopy(guidance)
                result["guidance_application_observed"] = any(row.get("event") == "route_adjustment_applied" for row in events)
                result["stairs_landing_observed"] = any(row.get("event") == "route_progress_observed"
                                                        and row.get("landmark") == "stairs_landing" for row in events)
            record["coin_result"] = result
            if terminal not in {"completed_stop", "death"} or not live.input_neutralized:
                self._retry_scope = None
        if record.get("initial_plan", {}).get("flight_compatibility") == mario_flight.COMPATIBILITY:
            record["flight_result"] = mario_flight.reconcile(runtime.get("events", []), terminal=terminal)
            record["flight_result"]["controller_application_observed"] = any(
                row.get("event") == "flight_objective_applied" for row in runtime.get("events", []))
            record["flight_result"]["handback_confirmed"] = bool(live.input_neutralized)
            record["requested_objective_satisfied"] = record["flight_result"]["reward_collected"]
            self._retry_scope = None
        path = self.history.record(record["attempt_id"], record)
        record["evidence_path"] = str(path)
        self._outcome = record
        self._attempt = None
        self._pending = None
        if record.get("flight_result"):
            self._message("assistant", mario_flight.report(record["flight_result"]) +
                          (" Control returned." if live.input_neutralized else " Handback is unconfirmed; no further attempt can start."), "outcome")
            return
        if record.get("coin_result"):
            self._message("assistant", mario_coins.report(record["coin_result"]), "outcome")
            return
        self._message("assistant", f"Session {terminal.replace('_', ' ')}. Actual actions and timing are retained; full completion remains unknown.", "outcome")

    def _history_rows(self) -> list[dict[str, Any]]:
        # Terminal files are immutable, but another local session may append.
        # Stat the roster so polling avoids reparsing every native frame trace.
        signature = tuple(sorted((str(path), path.stat().st_mtime_ns, path.stat().st_size)
                                 for path in self.history.root.glob("*.json")))
        if signature != self._history_signature:
            self._history_rows_cache = self.history.list(limit=100000)
            self._history_signature = signature
        return self._history_rows_cache

    @staticmethod
    def _history_view(row: dict[str, Any]) -> dict[str, Any]:
        # The complete native trace remains at evidence_path. The ordinary
        # polling/history surface carries the reviewed plan and result once.
        view = deepcopy({key: value for key, value in row.items() if key != "runtime"})
        runtime = row.get("runtime")
        if isinstance(runtime, dict):
            view["runtime"] = {key: deepcopy(runtime[key]) for key in
                               ("state", "owner", "session_id", "revision", "outcome",
                                "terminal_frame", "native_neutral_ack", "input_neutralized")
                               if key in runtime}
            view["retained_event_count"] = len(runtime.get("events", []))
        return view

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
            history_rows = self._history_rows()
            coin_progress = None
            if self._attempt and self._attempt.get("initial_plan", {}).get("coin_compatibility"):
                coin_progress = mario_coins.reconcile(runtime.get("events", []), finished=False)
                guidance = self._attempt["initial_plan"].get("route_guidance")
                if guidance:
                    coin_progress["route_guidance"] = deepcopy(guidance)
                    coin_progress["guidance_application_observed"] = any(row.get("event") == "route_adjustment_applied" for row in runtime.get("events", []))
                    coin_progress["stairs_landing_observed"] = any(row.get("event") == "route_progress_observed" and row.get("landmark") == "stairs_landing" for row in runtime.get("events", []))
            return {
                "schema_version": "game-companion-conversation/v1",
                "conversation_id": self.conversation_id, "game_id": "mario",
                "plan": deepcopy(self._plan), "current_plan": deepcopy(self._current),
                "pending_plan": deepcopy(self._pending), "runtime": runtime,
                "messages": deepcopy(self._messages[-60:]), "message": self._last_message,
                "variants": self.variants.list(), "outcome": deepcopy(self._outcome),
                "flight_progress": mario_flight.reconcile(runtime.get("events", [])) if self._attempt and self._attempt["initial_plan"].get("flight_compatibility") else None,
                "flight_knowledge": mario_flight.knowledge(history_rows, getattr(self.live_manager, "_game_file_sha256", None)),
                "coin_progress": coin_progress,
                "coin_knowledge": mario_coins.knowledge(history_rows, getattr(self.live_manager, "_game_file_sha256", None)),
                "demonstrations": self.demonstrations.list(), "recording": self.recording.review(),
                "demonstration_review": deepcopy(self._demo_review),
                "guidance": self._guidance_snapshot(), "retry_scope": deepcopy(self._retry_scope),
                "history": [{**self._history_view(row), "review": outcome_review({"game_id": "mario", **row})} for row in history_rows[:20]], "revisions": deepcopy(list(self._revisions.values())),
                "live": {"session_id": live.session_id,
                         "observation_active": live.observation_active,
                         "process_alive": live.process_alive if live.process_alive is not None else bool(live.emulator_pid),
                         "takeover_capable": live.takeover_capable, "reason": live.reason},
            }

    def _guidance_snapshot(self) -> dict[str, Any]:
        try:
            return self.coaching.read()
        except (ValueError, OSError) as exc:
            return {"error": str(exc)}

    def _coached_plan(self, text: str, *, attempts: int = 3) -> dict[str, Any]:
        context = self._context()
        context["current_plan"] = None
        result = self.planner.plan("Take the opening hop, then stop after the opening section", context)
        if result.plan is None:
            raise ValueError("The opening hop proposal is unavailable")
        plan = result.plan.to_dict()
        guidance = self.coaching.read()
        plan.update(original_request=text, requested_objective="Practice the World 1-1 opening jump",
                    coaching_compatibility=COMPATIBILITY,
                    jump_delay_frames=guidance["jump_delay_frames"],
                    coaching=deepcopy(guidance["coaching"]),
                    resource_limits={"maximum_attempts": attempts, "jump_delay_range": [0, 12], "maximum_seconds": 600},
                    change_summary=[f"Experimental opening hop: delay {guidance['jump_delay_frames']} frames, hold jump 26 frames; stop at x ≥ 160. Up to {attempts} attempts within 10 minutes; each requires a compatible opening entry."],
                    fallback_explanation="Experimental coaching; gameplay improvement has not been established.")
        return plan

    def _flight_plan(self, text: str) -> dict[str, Any]:
        context = self._context()
        context["current_plan"] = None
        proposed = self.planner.plan("Use the base path and stop at the end of World 1-1", context)
        if proposed.plan is None:
            raise ValueError("Flight proposal unavailable")
        plan = proposed.plan.to_dict()
        requirements = mario_flight.prerequisites(self._live()[1])
        remembered = mario_flight.knowledge(self.history.list(limit=100000), getattr(self.live_manager, "_game_file_sha256", None))
        plan.update(original_request=text, requested_objective="Fly to the World 1-1 sky hidden 1UP brick",
                    normalized_intent="flight_reward", flight_compatibility=mario_flight.COMPATIBILITY,
                    path_choice=mario_flight.PATH, stop_point=mario_flight.STOP,
                    requested_speed=1, prerequisites=requirements, remembered_flight=remembered,
                    execution_eligibility="eligible" if requirements["ready"] else "blocked",
                    resource_limits={"maximum_attempts": 1, "maximum_seconds": 30, "maximum_frames": 900},
                    change_summary=[mario_flight.APPROACH], fallback_explanation=" ".join(requirements["missing"]) +
                    (" " + mario_flight.REMEDY if not requirements["ready"] else " Flight form and runway observed. Collection requires a game-owned mushroom hit receipt."))
        if remembered["last_result"]:
            previous = remembered["last_result"]
            plan["change_summary"].append("Last compatible attempt: " + mario_flight.report(previous) + " This review grants a fresh single attempt only.")
        parameters = plan["actions"][0]["parameters"]
        parameters.update(path_choice=mario_flight.PATH, primitive_id="world_1_1_sky_hidden_1up_v2", stop_point=mario_flight.STOP)
        plan["actions"][0]["target_ids"] = ["world_1_1_sky_hidden_1up_brick"]
        plan["actions"][0]["expected_outcomes"] = ["observe_mushroom_hit_receipt", "neutralize_and_return_control"]
        return plan

    def _coin_plan(self, text: str, *, attempts: int = 3) -> dict[str, Any]:
        context = self._context()
        context["current_plan"] = None
        proposed = self.planner.plan("Use the base path and stop at the end of World 1-1", context)
        if proposed.plan is None:
            raise ValueError("World 1-1 exploration proposal unavailable")
        plan = proposed.plan.to_dict()
        cartridge = getattr(self.live_manager, "_game_file_sha256", None)
        history = self.history.list(limit=100000)
        route, reason = mario_coins.choose_route(history, cartridge)
        guidance = mario_coins.route_guidance(history, cartridge)
        if self.route_guidance_store.path.exists():
            saved = json.loads(self.route_guidance_store.path.read_text())
            if saved.get("cartridge_sha256") == cartridge:
                guidance = {**(guidance or {}), **saved}
        if guidance:
            route = "coin_balanced"
            reason = "Next-attempt instruction: " + guidance["instruction"] + " " + guidance.get("pipe_instruction", "") + " Basis: " + guidance["basis"] + ". Controller application and progress will be reported separately."
        plan.update(original_request=text, requested_objective="Discover a World 1-1 coin route to the finish",
                    coin_compatibility=mario_coins.COMPATIBILITY, path_choice=route,
                    resource_limits={"maximum_attempts": attempts, "maximum_seconds": 600},
                    change_summary=[reason, f"Up to {attempts} explicitly requested attempts in ten minutes.", mario_coins.COVERAGE],
                    completion_coverage="unknown", fallback_explanation=reason)
        from smb3_agent.mario_route_contract import TRAVERSALS
        plan["actions"][0]["parameters"].update(path_choice=route, primitive_id=TRAVERSALS[route].primitive_id)
        if guidance:
            plan["route_guidance"] = deepcopy(guidance)
            plan["actions"][0]["parameters"]["stairs_tactic"] = guidance["stairs_tactic"]
            if guidance.get("pipe_tactic"):
                plan["actions"][0]["parameters"]["pipe_tactic"] = guidance["pipe_tactic"]
        return plan

    def _retry(self, request_id: str) -> None:
        scope = self._retry_scope
        live, observation = self._live()
        if self._active():
            raise ValueError("Wait for confirmed handback before retrying")
        if not scope or scope["remaining"] <= 0 or time.monotonic() >= scope["deadline"]:
            self._retry_scope = None
            raise ValueError("The attempt budget ended. Discuss and approve a new opening practice plan.")
        if (live.session_id != scope["session_id"] or not observation["fresh"]
                or live.control_owner != "player" or not live.input_neutralized):
            self._retry_scope = None
            raise ValueError("Session or control changed. Review and approve a fresh practice plan.")
        generation = self._control_generation
        restart = getattr(self.live_manager, "restart_coaching_session", None)
        if restart:
            try:
                live = restart(expected_session=scope["session_id"],
                               cancelled=lambda: self._interrupted.is_set() or generation != self._control_generation)
            except (ValueError, OSError):
                self._retry_scope = None
                raise
            scope["session_id"] = live.session_id
        if self._interrupted.is_set() or generation != self._control_generation:
            self._retry_scope = None
            raise ValueError("Retry was interrupted; fresh approval is required")
        # Runtime independently checks exact cartridge/process and opening entry.
        plan = (self._coin_plan("Retry using remembered coin discoveries", attempts=scope["maximum_attempts"])
                if scope.get("coin_discovery") else
                self._coached_plan("Retry with remembered opening-jump guidance", attempts=scope["maximum_attempts"]))
        plan = self._bound_plan(plan)
        if time.monotonic() >= scope["deadline"]:
            self._retry_scope = None
            raise ValueError("The attempt budget expired while preparing; fresh approval is required")
        plan["practice_expires_epoch"] = scope["expires_epoch"]
        started = self.runtime.start(plan)
        scope["remaining"] -= 1
        self._begin_attempt(plan, started)
        if generation != self._control_generation:
            self.runtime.control("stop", command_id=request_id)
            self._retry_scope = None
            raise ValueError("Retry interrupted during startup")
        self._message("assistant", f"Retry started: {plan['change_summary'][0]} {scope['remaining']} attempts remain. Controller application and outcome will be reported separately.", "started")

    def _begin_attempt(self, plan: dict, started_runtime: dict | None) -> None:
        self._plan = self._current = plan
        self._revisions = {plan["revision"]: deepcopy(plan)}
        live, observation = self._live()
        self._attempt = {"attempt_id": "plan-" + uuid4().hex,
                         "conversation_id": self.conversation_id, "session_id": live.session_id,
                         "requested_objective": plan["requested_objective"],
                         "initial_plan": deepcopy(plan),
                         "cartridge_sha256": getattr(self.live_manager, "_game_file_sha256", None),
                         "start_frame": (started_runtime or {}).get("start_frame", observation["frame"]),
                         "starting_observation": observation,
                         "started_at": datetime.now(timezone.utc).isoformat()}

    def _bound_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        live, observation = self._live()
        if not live.session_id or not observation["fresh"]:
            raise ValueError("Open a visible companion session and wait for a fresh observation")
        if plan.get("session_id") not in {None, live.session_id}:
            raise ValueError("This plan belongs to another session; select or reopen it for this session")
        result = deepcopy(plan)
        if result.get("flight_compatibility"):
            requirements = mario_flight.prerequisites(observation)
            if not requirements["ready"]:
                raise ValueError(" ".join(requirements["missing"]) + " " + mario_flight.REMEDY)
            result.update(prerequisites=requirements, execution_eligibility="eligible")
        if result.get("demonstration"):
            chosen = result["demonstration"]
            saved = self.demonstrations.load(chosen["id"])
            if saved != chosen:
                raise ValueError("Demonstration changed; choose Use again and review")
            mario_demonstrations.compatible(saved, getattr(self.live_manager, "_game_file_sha256", None))
        if result.get("coaching_compatibility") == COMPATIBILITY:
            guidance = self.coaching.read()
            result.update(jump_delay_frames=guidance["jump_delay_frames"], coaching=deepcopy(guidance["coaching"]))
        result.update({"session_id": live.session_id, "observation_id": observation["observation_id"],
                       "conversation_id": self.conversation_id})
        return result

    def _queue(self, plan: dict[str, Any], request_id: str) -> None:
        if (self._current or {}).get("coin_compatibility") or (self._current or {}).get("flight_compatibility"):
            raise ValueError("Coin route changes apply on fresh attempts; finish or Stop before reviewing another route")
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
        priority = urgent_control(str(payload.get("text", ""))) if action == "message" else None
        if priority:
            action = priority
        if action in {"stop", "reclaim", "demo_disable"}:
            # Revoke before waiting for conversation planning or its lock.
            self._interrupted.set()
            self._control_generation += 1
            self._retry_scope = None
            if self.recording.current:
                self.recording.stop()
            elif action != "demo_disable" or self._active() or self.live_manager.snapshot().control_owner == "agent":
                self.runtime.control("stop" if action == "demo_disable" else action, command_id=request_id)
            with self._lock:
                if action == "demo_disable":
                    self._plan = None
                self._pending = None
                self._pending_command_id = None
                if payload.get("text"):
                    self._message("user", str(payload["text"]), "request")
                self._message("assistant", "Handback requested. Pending work and retry permission canceled; status confirms input release.", "control")
                return self.snapshot()
        generation = self._control_generation
        with self._lock:
            if generation != self._control_generation:
                raise ValueError("Request interrupted; review a fresh plan")
            self._operation_generation = generation
            self._sync()
            if request_id in self._requests:
                return self.snapshot()
            self._requests.add(request_id)
            try:
                self._dispatch(action, payload, request_id)
            except (ValueError, OSError) as exc:
                self._message("assistant", str(exc), "error")
                if action in {"message", "apply", "start"}:
                    _retain_refusal(self, action, payload, str(exc), "mario")
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
        if self.recording.current and action not in {"record_stop", "record_save", "record_start"}:
            raise ValueError("Stop recording before asking the companion to play or changing its plan")
        if action == "preparation_press":
            if self._active():
                raise ValueError("Stop companion play before preparation")
            self._plan = None
            self._retry_scope = None
            choices = {"wait": (), "start": ("start",), "left": ("left",), "right": ("right",), "up": ("up",), "down": ("down",),
                       "jump": ("A",), "jump_right": ("A", "right"), "jump_left": ("A", "left"),
                       "run_right": ("B", "right"), "run_jump_right": ("A", "B", "right")}
            choice = payload.get("buttons")
            if choice not in choices:
                raise ValueError("Choose a preparation control")
            try:
                frames = int(payload.get("frames", ""))
            except (ValueError, TypeError) as exc:
                raise ValueError("Choose a short preparation duration") from exc
            self._message("assistant", self.live_manager.preparation_press(choices[choice], frames), "control")
        elif action == "player_play":
            if self._active():
                raise ValueError("Stop companion play before demonstrating")
            live = self.live_manager.snapshot()
            self.live_manager.demonstration_command(uuid4().hex, "play", live.session_id)
            self._plan = None
            self._retry_scope = None
            self._message("assistant", "You control Mario. Focus the emulator and prepare the entry for your next reviewed goal. Companion gameplay needs a fresh plan and Start.", "demonstration")
        elif action == "demo_fresh":
            if self._active():
                raise ValueError("Stop companion play before opening a fresh attempt")
            self._plan = None
            self._retry_scope = None
            live = self.live_manager.snapshot()
            generation = self._operation_generation
            self.live_manager.restart_coaching_session(expected_session=live.session_id,
                cancelled=lambda: generation != self._control_generation)
            if generation != self._control_generation:
                raise ValueError("Fresh attempt interrupted; review again")
            self._current = None
            self._message("assistant", "Fresh disposable attempt is paused. Prepare your entry, ask for a goal, review and Start. No recording is needed for flight.", "demonstration")
        elif action == "record_start":
            if self._active():
                raise ValueError("Stop companion play before demonstrating")
            self._plan = None
            self._retry_scope = None
            self.recording.start()
            self._message("assistant", "Recording requested. You own every input; check the recording status, focus Mario and show your route. Ten-minute maximum.", "demonstration")
        elif action == "record_stop":
            self.recording.stop()
            self._message("assistant", "Recording stopped. Review the gameplay, choose a segment if needed, name it and describe the intended lesson before saving.", "demonstration")
        elif action == "record_save":
            if self.recording.current:
                raise ValueError("Stop recording before saving")
            draft = self.recording.draft
            if not draft or not draft['saveable']:
                raise ValueError("Record and stop a player demonstration first")
            first, last = mario_demonstrations.segment_range(payload, len(draft['frames']))
            demo = self.demonstrations.save(draft['frames'][first:last], name=str(payload.get("name", "")),
                 lesson=str(payload.get("lesson", "")), cartridge=draft['cartridge_sha256'],
                 source={k: draft[k] for k in ('source_path', 'session_id', 'emulator_pid', 'reason', 'images')} | {'first': first, 'last': last})
            self._demo_review = {**{k: v for k, v in demo.items() if k != 'frames'},
                                 'preview': mario_demonstrations.preview(demo['frames']),
                                 'image_urls': mario_demonstrations.image_urls(demo.get('images', []))}
            self._message("assistant", "Saved demonstration. " + mario_demonstrations.explanation(demo), "saved")
        elif action in {"demo_review", "demo_edit", "demo_delete", "demo_use"}:
            identity = str(payload.get("demonstration_id", ""))
            demo = self.demonstrations.load(identity)
            if action == "demo_delete":
                if self._active():
                    raise ValueError("Stop the attempt before deleting a demonstration")
                self.demonstrations.delete(identity)
                self._demo_review = None
                self._plan = None
                self._message("assistant", "Demonstration deleted; prior applications remain in attempt history.", "deleted")
            else:
                if action == "demo_edit":
                    demo = self.demonstrations.edit(identity, name=str(payload.get("name", "")), lesson=str(payload.get("lesson", "")))
                    if not self._active():
                        self._plan = None
                self._demo_review = {**{k: v for k, v in demo.items() if k != 'frames'},
                                     'preview': mario_demonstrations.preview(demo['frames']),
                                 'image_urls': mario_demonstrations.image_urls(demo.get('images', []))}
                if action == "demo_use":
                    if self._active():
                        raise ValueError("Stop companion play before reviewing demonstration use")
                    mario_demonstrations.compatible(demo, getattr(self.live_manager, "_game_file_sha256", None))
                    plan = self._coin_plan("Use demonstrated route: " + demo['lesson'], attempts=1)
                    from smb3_agent.mario_route_contract import TRAVERSALS
                    plan.pop("route_guidance", None)
                    plan["actions"][0]["parameters"].pop("stairs_tactic", None)
                    plan["actions"][0]["parameters"].pop("pipe_tactic", None)
                    plan.update(demonstration=demo, path_choice="coin_balanced", requested_speed=1,
                                change_summary=[mario_demonstrations.explanation(demo)],
                                requested_objective="Follow demonstrated segment and stop")
                    plan['actions'][0]['parameters'].update(path_choice="coin_balanced", primitive_id=TRAVERSALS['coin_balanced'].primitive_id)
                    self._plan = plan
                    self._retry_scope = None
                self._message("assistant", mario_demonstrations.explanation(demo), "demonstration")
        elif action == "demo_disable":
            if self._active():
                self.runtime.control("stop", command_id=request_id)
            self._plan = None
            self._retry_scope = None
            self._message("assistant", "Stopped using demonstration guidance. Review a new ordinary plan to play again.", "control")
        elif action == "select_intent":
            self._retry_scope = None
            context = self._context()
            context["current_plan"] = None
            result = self.planner.plan("existing base route" if payload.get("intent") in {None, "base"} else str(payload["intent"]), context)
            if result.plan:
                self._plan = result.plan.to_dict()
            self._message("assistant", result.message, result.kind)
        elif action == "message":
            text = str(payload.get("text", "")).strip()
            self._message("user", text, "request")
            value = normalized_text(text)
            if value in {"reset guidance", "forget my coaching", "reset coaching"}:
                self._dispatch("reset_guidance", {}, request_id)
                return
            conversational = re.sub(r"^(?:please )?(?:can|could|would|will) you (?:please )?(?:help me )?", "", value).rstrip(".!?")
            practice_request = bool(re.search(r"\b(?:practice|learn|work on|try|coach|improve|get better at)\b", conversational)
                                    and re.search(r"\b(?:jump|jumping|hop|opening)\b", conversational))
            polite_action = conversational != value.rstrip(".!?") and (
                practice_request or timing_adjustment(conversational) is not None)
            if ("stairs" in value and not is_advisory(text)
                    and re.search(r"\b(?:land|landing)\b", value)
                    and "left" in value
                    and not re.search(r"\b(?:not|never|dont|don't)\b", value)
                    and re.search(r"\b(?:then|before)\b", value)
                    and re.search(r"\b(?:jump|jumping|cross|crossing)\b", value)):
                cartridge = getattr(self.live_manager, "_game_file_sha256", None)
                if not cartridge:
                    raise ValueError("Open the same Mario cartridge before teaching route guidance")
                guidance = {"contract": mario_coins.GUIDANCE_CONTRACT,
                            "stairs_tactic": mario_coins.STAIRS_TACTIC,
                            "instruction": "Land on the left stair top, release jump, then run and jump across the gap.",
                            "original_words": text, "basis": "player_instruction",
                            "cartridge_sha256": cartridge, "application": "next_compatible_attempt"}
                self.route_guidance_store.write(guidance)
                if not self._active() and self._plan and self._plan.get("coin_compatibility"):
                    revision = self._plan["revision"] + 1
                    self._plan = self._coin_plan(text, attempts=self._plan["resource_limits"]["maximum_attempts"])
                    self._plan["revision"] = revision
                self._message("assistant", "Remembered for the next compatible attempt: " + guidance["instruction"] +
                              " The current attempt is unchanged. Review a stairs or coin goal, or Try again after confirmed handback within the existing budget.", "coaching")
                return
            if mario_flight.request(conversational):
                if is_advisory(text) and re.search(r"\b(?:remember|history|outcome|result|learned)\b", value):
                    self._message("assistant", "Remembered flight results: " + json.dumps(mario_flight.knowledge(
                        self.history.list(limit=100000), getattr(self.live_manager, "_game_file_sha256", None))), "advisory")
                    return
                if self._active():
                    raise ValueError("Finish or Stop before reviewing a flight reward objective")
                self._retry_scope = None
                error = mario_flight.target_error(conversational)
                if error:
                    self._plan = None
                    self._message("assistant", error, "clarification")
                    return
                self._plan = self._flight_plan(text)
                self._message("assistant", " ".join(self._plan["change_summary"]) + " " + self._plan["fallback_explanation"] +
                              " Review and say yes or Start once prerequisites are observed.", "proposal")
                return
            coin_goal = mario_coins.coin_request(conversational)
            if "stairs" in value and is_advisory(text):
                cartridge = getattr(self.live_manager, "_game_file_sha256", None)
                guidance = mario_coins.route_guidance(self.history.list(limit=100000), cartridge)
                if self.route_guidance_store.path.exists():
                    saved = json.loads(self.route_guidance_store.path.read_text())
                    if saved.get("cartridge_sha256") == cartridge:
                        guidance = {**(guidance or {}), **saved}
                self._message("assistant", "Remembered next-attempt stairs instruction: " +
                              (json.dumps(guidance) if guidance else "none compatible; open the same cartridge to bind memory") +
                              ". This advice grants no gameplay permission.", "advisory")
                return
            coin_context = (self._current or self._plan or {}).get("coin_compatibility")
            if coin_context and is_advisory(text) and re.search(r"\b(?:why|route|learn|learned|discoveries|missed|unknown)\b", value):
                relevant = self._current or self._plan
                self._message("assistant", relevant["change_summary"][0] + " " +
                              json.dumps(mario_coins.knowledge(self.history.list(limit=100000), getattr(self.live_manager, "_game_file_sha256", None))), "advisory")
                return
            if "coin" in value and is_advisory(text) and not re.search(r"\b(?:can|could|would|will) (?:you|we)\b", value):
                summary = mario_coins.knowledge(self.history.list(limit=100000), getattr(self.live_manager, "_game_file_sha256", None))
                self._message("assistant", "Remembered coin discoveries: " + json.dumps(summary) +
                              ". Counts across attempts are knowledge, not coins collected in a single run.", "advisory")
                return
            if coin_goal:
                if re.search(r"world\s*(?!1[ -]1\b)\d+[ -]\d+", value):
                    raise ValueError("Coin discovery currently supports World 1-1 only")
                if self._active():
                    raise ValueError("Finish or Stop before reviewing a coin exploration scope")
                count = re.search(r"\b(\d+)\s*(?:attempts?|tries|lives?)\b", value)
                word_count = re.search(r"\b(one|two|three|four|five)\s*(?:attempts?|tries|lives?)\b", value)
                attempts = int(count[1]) if count else ({"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}[word_count[1]] if word_count else 3)
                if not 1 <= attempts <= 5:
                    raise ValueError("Choose between one and five attempts")
                self._retry_scope = None
                self._plan = self._coin_plan(text, attempts=attempts)
                self._message("assistant", " ".join(self._plan["change_summary"]) +
                              " Review and say yes or Start. After handback, Try again applies discoveries to a fresh disposable attempt.", "proposal")
                return
            if is_advisory(text) and not polite_action:
                if any(word in value for word in ("remember", "learn", "guidance", "coaching", "changed")):
                    self._message("assistant", "Remembered opening-jump guidance: " + json.dumps(self._guidance_snapshot()) + ". Applied timing and observed outcomes are in saved results; improvement remains unknown.", "advisory")
                    return
            else:
                if value in {"yes", "yes please", "go ahead", "approved", "start", "let's do it", "lets do it"}:
                    if self._plan is None:
                        raise ValueError("Discuss a goal before approving a plan")
                    self._dispatch("start", {"expected_plan_id": self._plan["plan_id"], "expected_revision": self._plan["revision"]}, request_id)
                    return
                if value in {"try again", "retry", "another attempt", "again", "let's try again", "lets try again"}:
                    self._retry(request_id)
                    return
                delta = timing_adjustment(conversational)
                if delta is not None:
                    relevant = self._current if self._active() else self._plan
                    if not relevant or relevant.get("coaching_compatibility") != COMPATIBILITY:
                        self._message("assistant", "Timing coaching supports experimental World 1-1 opening practice. Ask to practice the opening jump, then review that scope.", "clarification")
                        return
                    guidance = self.coaching.adjust(text, delta)
                    if not self._active():
                        self._plan = self._coached_plan(text, attempts=relevant["resource_limits"]["maximum_attempts"])
                    self._message("assistant", f"I interpreted that as {delta:+d} frames: delay is now {guidance['jump_delay_frames']} frames. This applies on the next compatible attempt; the current jump is unchanged. Improvement remains unknown.", "coaching")
                    return
                if practice_request:
                    if self._active():
                        raise ValueError("Stop or finish the current attempt before reviewing a new practice scope")
                    self._retry_scope = None
                    count = re.search(r"\b(\d+)\s*(?:attempts?|tr(?:y|ies)|lives?)\b", value)
                    word_count = re.search(r"\b(one|two|three|four|five)\s*(?:attempts?|tr(?:y|ies)|lives?)\b", value)
                    attempts = int(count[1]) if count else ({"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}[word_count[1]] if word_count else 3)
                    if not 1 <= attempts <= 5:
                        raise ValueError("Choose between one and five attempts")
                    self._plan = self._coached_plan(text, attempts=attempts)
                    self._message("assistant", "We can practice the World 1-1 opening jump, stop at x ≥ 160 and adjust its delay from 0–12 frames. " + self._plan["change_summary"][0] + " Review the plan and say yes or Start. Request Try again after confirmed handback to reopen a fresh disposable cartridge session inside the approved budget.", "proposal")
                    return
            if not is_advisory(text) and re.search(r"\b(?:jump|jumping|hop)\b", value) and re.search(r"\b(?:higher|lower|hold|longer|shorter|timing|too|bad|wrong)\b", value):
                self._message("assistant", "I can adjust the experimental opening jump earlier or later by 1–12 frames. Describe the direction and frame change; jump height and other level tactics are not supported yet.", "clarification")
                return
            generation = self._operation_generation
            result = self.planner.plan(text, self._context())
            if generation != self._control_generation:
                self._message("assistant", "Planning was interrupted. Review a fresh plan before playing.", "cancelled")
                return
            self._message("assistant", result.message, result.kind)
            if result.control:
                self._dispatch(result.control["action"], {"rate": result.control.get("speed")}, request_id)
            elif result.plan and result.kind != "advisory":
                self._retry_scope = None
                self._plan = result.plan.to_dict()
                if result.apply_requested and self._active():
                    self._queue(self._plan, request_id)
        elif action == "start":
            if self._active():
                raise ValueError("A bounded plan is already running")
            if self._plan is None:
                raise ValueError("Select and review a plan first")
            plan = self._bound_plan(self._plan)
            if (plan.get("coaching_compatibility") == COMPATIBILITY or plan.get("coin_compatibility") == mario_coins.COMPATIBILITY):
                maximum = plan.get("resource_limits", {}).get("maximum_attempts")
                if type(maximum) is not int or not 1 <= maximum <= 5:
                    raise ValueError("Invalid attempt budget")
            generation = self._operation_generation
            if generation != self._control_generation:
                raise ValueError("Startup interrupted; review a fresh plan")
            self._interrupted.clear()
            if (plan.get("coaching_compatibility") == COMPATIBILITY or plan.get("coin_compatibility") == mario_coins.COMPATIBILITY):
                plan["practice_expires_epoch"] = int(time.time()) + 600
            started_runtime = self.runtime.start(plan)
            self._begin_attempt(plan, started_runtime)
            if generation != self._control_generation:
                self.runtime.control("stop", command_id=request_id)
                raise ValueError("Startup interrupted; review a fresh plan")
            if (plan.get("coaching_compatibility") == COMPATIBILITY or plan.get("coin_compatibility") == mario_coins.COMPATIBILITY):
                maximum = plan["resource_limits"]["maximum_attempts"]
                if type(maximum) is not int or not 1 <= maximum <= 5:
                    raise ValueError("Invalid attempt budget")
                self._retry_scope = {"session_id": plan["session_id"], "maximum_attempts": maximum,
                                     "remaining": maximum - 1, "deadline": time.monotonic() + 600,
                                     "expires_epoch": plan["practice_expires_epoch"],
                                     "coin_discovery": bool(plan.get("coin_compatibility"))}
                self._message("assistant", f"Started bounded exploration: {plan['change_summary'][0]}" if plan.get("coin_compatibility") else f"Started opening practice: {plan['jump_delay_frames']} frames of jump delay; {maximum - 1} compatible retries remain. Timing application requires a controller receipt.", "started")
            else:
                self._retry_scope = None
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
            if action == "speed" and self._active() and (self._current or {}).get("demonstration") and payload.get("rate") != 1:
                raise ValueError("Demonstration playback uses normal speed")
            self.runtime.control(action, speed=payload.get("rate") if action == "speed" else None,
                                 command_id=request_id)
            if action == "speed":
                for plan in (self._plan, self._current, self._pending):
                    if plan is not None:
                        plan["requested_speed"] = payload.get("rate")
            self._message("assistant", f"{action.capitalize()} requested; controller acknowledgment is shown in status.", "control")
        elif action == "retry":
            self._retry(request_id)
        elif action == "reset_guidance":
            self.coaching.reset()
            self._retry_scope = None
            self._plan = None
            self._message("assistant", "Future opening guidance reset. Current play is unchanged; prior outcomes remain in history. Review a new plan before another attempt.", "reset")
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
            self._retry_scope = None
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

    def invalidate_for_switch(self) -> bool:
        """Retain the terminal result before forgetting session-bound proposals."""
        with self._lock:
            self._sync()
            live = self.live_manager.snapshot()
            if self.recording.current or self._active() or live.control_owner != "player" or not live.input_neutralized:
                return False
            self._retry_scope = None
            self._plan = self._current = self._pending = None
            self._pending_command_id = None
            self._cancel_requested = False
            self._revisions = {}
            self._message("assistant", "Switched games. Earlier conversation and results are reference only. Open a fresh session and review a new plan before Start.", "switched")
            return True

    def close(self) -> None:
        with self._lock:
            if self.recording.current:
                self.recording.stop()
            if self._active():
                self.runtime.control("stop", command_id=uuid4().hex)
                self._sync()


class StardewConversationService:
    """Shared typed proposals with exclusively Stardew-owned volatile authority.

    Saved events/outcomes are informational. Construction never reloads a plan,
    selected targets, reviewed scope, or input permission from disk.
    """

    def __init__(self, *, runtime: Any = None,
                 artifacts_root: Path = Path("artifacts/stardew-conversation")) -> None:
        if runtime is None:
            from smb3_agent.stardew_runtime import StardewRuntime
            runtime = StardewRuntime()
        self.runtime = runtime
        self.root = Path(artifacts_root)
        self.history = PlanAttemptHistory(self.root / "outcomes")
        self.planner = Planner()
        self.conversation_id = "stardew-conversation-" + uuid4().hex
        self._history_summary_cache = None
        self._lock = threading.RLock()
        self._plan: dict[str, Any] | None = None
        self._reviewed: dict[str, Any] | None = None
        self._messages: list[dict[str, Any]] = []
        self._requests: set[str] = set()
        self._retained: set[str] = set()
        self._selected: tuple[str, ...] = ()
        self._cave_destination = None
        self._cave_pending = False
        self._cave_saved = None
        cave_file = self.root / "cave-result.json"
        if cave_file.is_file():
            try:
                self._cave_saved = {**json.loads(cave_file.read_text()), "historical": True}
                if self._cave_saved.get("status") == "running":
                    self._cave_saved.update(status="interrupted", reason="Application reopened; return was not confirmed.", handback_confirmed=False)
            except (ValueError, OSError):
                pass
        self._inspection_saved = None
        inspection_file = self.root / "inspection-result.json"
        if inspection_file.is_file():
            try:
                self._inspection_saved = {**json.loads(inspection_file.read_text()), "historical": True}
            except (ValueError, TypeError):
                pass
        self._planting = None
        saved = self.root / "planting-discussion.json"
        if saved.is_file():
            try:
                retained = json.loads(saved.read_text())
                self._planting = {**retained["recommendation"], "historical": True}
                self._planting_messages = retained.get("messages", [])[-60:]
            except (ValueError, KeyError, TypeError):
                self._planting_messages = []
        else:
            self._planting_messages = []

    def _message(self, role: str, text: str, kind: str) -> None:
        event = {"role": role, "text": text, "kind": kind,
                 "at": datetime.now(timezone.utc).isoformat()}
        self._messages.append(event)
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / (self.conversation_id + ".jsonl")).open("a") as stream:
            stream.write(json.dumps(event) + "\n")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            runtime = deepcopy(getattr(self.runtime, "ui_snapshot", self.runtime.snapshot)())
            cave = runtime.get("cave_result")
            if cave and cave != self._cave_saved:
                self.root.mkdir(parents=True, exist_ok=True)
                # Persist findings even during return; reopening never resumes it.
                temporary = self.root / "cave-result.tmp"
                temporary.write_text(json.dumps(cave))
                temporary.replace(self.root / "cave-result.json")
                self._cave_saved = deepcopy(cave)
            inspection = runtime.get("inspection_result")
            if inspection and inspection.get("status") != "running" and inspection != self._inspection_saved:
                self.root.mkdir(parents=True, exist_ok=True)
                temporary = self.root / "inspection-result.tmp"
                temporary.write_text(json.dumps(inspection))
                temporary.replace(self.root / "inspection-result.json")
                self._inspection_saved = deepcopy(inspection)
            outcome = runtime.get("outcome")
            if (isinstance(outcome, dict) and outcome.get("attempt_id")
                    and outcome.get("status") not in {None, "active", "running"}
                    and runtime.get("status") != "running"):
                identity = str(outcome["attempt_id"])
                if identity not in self._retained:
                    self.history.record(identity, {**outcome, "game_id": "stardew",
                                                  "task_ledger": runtime.get("ledger"),
                                                  "reviewed_plan": deepcopy(runtime.get("current_plan") or self._plan),
                                                  "conversation_id": self.conversation_id})
                    self._retained.add(identity)
                    self._history_summary_cache = None
            if self._history_summary_cache is None:
                self._history_summary_cache = [
                    {key: value for key, value in row.items()
                     if key not in {"before_observation", "after_observations", "inputs", "evidence_hashes"}}
                    for row in self.history.list()]
            return {"schema_version": "game-companion-conversation/v1",
                    "game_id": "stardew", "conversation_id": self.conversation_id,
                    "plan": deepcopy(self._plan), "reviewed": self._reviewed == self._plan and self._plan is not None,
                    "current_plan": runtime.get("current_plan"), "pending_plan": None,
                    "messages": deepcopy(self._messages[-60:]), "runtime": runtime,
                    "planting_recommendation": deepcopy(self._planting),
                    "planting_messages": deepcopy(self._planting_messages),
                    "cave_result": deepcopy(cave or ({**self._cave_saved, "historical": True} if self._cave_saved else None)),
                    "inspection_result": deepcopy(inspection or self._inspection_saved),
                    "selected_target_ids": list(self._selected),
                    "outcome": outcome, "history": [{**row, "review": outcome_review(row)} for row in deepcopy(self._history_summary_cache)]}

    def _context(self) -> dict[str, Any]:
        context_value = self.runtime.planning_context(conversation_id=self.conversation_id,
                         current_plan=ConversationPlan.from_dict(self._plan) if self._plan else None)
        context = asdict(context_value) if hasattr(context_value, "__dataclass_fields__") else dict(context_value)
        # Selection carries only current observation-owned objects, never client facts.
        targets = context.get("observation", {}).get("targets", [])
        context["selected_targets"] = [item for item in targets if item.get("id") in self._selected]
        context["reviewed_edit_scope"] = []  # Every changed scope needs fresh explicit review/Start.
        return context

    def dispatch(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self._dispatch_request(action, payload)
        except ValueError as exc:
            if action in {"message", "apply", "start"}:
                with self._lock:
                    self._reviewed = None
                    _retain_refusal(self, action, payload or {}, str(exc), "stardew")
                    self._message("assistant", str(exc), "refused")
            raise

    def _dispatch_request(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        # Runtime neutralization has priority over setup, persistence and planning locks.
        if action in {"pause", "stop", "reclaim", "focus_lost"}:
            self.runtime.control(action)
            with self._lock:
                self._reviewed = None
                state = self.runtime.snapshot()
                handback = ("Input release and player handback confirmed." if state.get("handback_confirmed") is True
                            else str(state.get("reason") or "Input authority ended; check the handback status before continuing."))
                self._message("assistant", handback + " Review the remaining work before authorizing another attempt.", "control")
            return self.snapshot()
        # Discussion revokes input before acquiring planning/persistence locks,
        # including questions and check-ins that never activate observation.
        if action == "message" and (self.runtime.snapshot().get("status") == "running" or getattr(self.runtime, "_preparation_driver", None) is not None):
            self.runtime.control("pause")
            self._reviewed = None
        with self._lock:
            request_id = str(payload.get("request_id") or uuid4().hex)
            if request_id in self._requests:
                return self.snapshot()
            if action in {"apply", "start"}:
                if (not self._plan or payload.get("expected_plan_id") != self._plan["plan_id"]
                        or type(payload.get("expected_revision")) is not int
                        or payload["expected_revision"] != self._plan["revision"]):
                    raise ValueError("The plan changed. Review its current version before continuing.")
            if action == "prepare_engineering":
                self._plan = self._reviewed = None
                self.runtime.prepare_engineering(payload.get("step", "view"), payload.get("expected_view"))
            elif action in {"reconnect_engineering", "show_engineering_game"}:
                self._plan = self._reviewed = None
                self._selected = ()
                if self._planting:
                    self._planting["historical"] = True
                if action == "reconnect_engineering":
                    self.runtime.setup({"action": action})
                else:
                    self.runtime.show_engineering_game()
                self._message("assistant", str(self.runtime.snapshot().get("reason")), "setup")
            elif action == "launch_engineering":
                self._plan = self._reviewed = None
                self._selected = ()
                if self._planting:
                    self._planting["historical"] = True
                self.runtime.setup({"action": "launch_engineering", **(
                    {"prepared_id": payload["prepared_id"]} if payload.get("prepared_id") else {})})
                self._message("assistant", "Engineering launch attempted in a fresh isolated folder. Check the setup status; this does not establish a prepared farm or grant gameplay input.", "setup")
            elif action == "verify_engineering_session":
                self._plan = self._reviewed = None
                self._selected = ()
                if self._planting:
                    self._planting["historical"] = True
                verifier = getattr(self.runtime, "verify_engineering_session", None)
                if verifier is None:
                    raise ValueError("Game loading and persistence verification is unavailable for this session.")
                verifier()
                self._message("assistant", "Session verification checked. The setup checklist shows which evidence is still required; no gameplay permission was granted.", "setup")
            elif action == "connect_profile":
                profile_id = payload.get("profile_id")
                candidates = self.runtime.snapshot().get("qualified_profiles", [])
                if (not isinstance(profile_id, str) or not profile_id
                        or not any(item.get("profile_id") == profile_id for item in candidates)):
                    raise ValueError("Choose a qualified screen profile from this session's available profiles. Browser-provided calibration cannot qualify a profile.")
                connector = getattr(self.runtime, "connect_profile", None)
                if connector is None:
                    raise ValueError("Qualified screen connection is unavailable for this session.")
                self._plan = self._reviewed = None
                self._selected = ()
                if self._planting:
                    self._planting["historical"] = True
                connector(profile_id)
                self._message("assistant", "Screen connection checked. Request and review a task before explicitly authorizing farm work.", "setup")
            elif action == "setup":
                if (not isinstance(payload.get("source"), str) or not payload["source"].strip()
                        or not isinstance(payload.get("destination"), str) or not payload["destination"].strip()):
                    raise ValueError("Choose the exact source and a new disposable destination.")
                self.runtime.setup({key: payload[key] for key in
                                    ("source", "destination", "copy_authorized", "setup_source_kind") if key in payload})
                self._plan = self._reviewed = None
                self._selected = ()
                if self._planting:
                    self._planting["historical"] = True
                self._message("assistant", "Disposable setup recorded. Game loading, persistence and fresh screen perception must be verified before input.", "setup")
            elif action == "reset":
                if not isinstance(payload.get("destination"), str) or not payload["destination"].strip():
                    raise ValueError("Choose a new disposable destination for the fresh attempt.")
                self._plan = self._reviewed = None
                self._selected = ()
                if self._planting:
                    self._planting["historical"] = True
                self.runtime.setup({"action": "reset", "destination": payload.get("destination", "")})
                self._message("assistant", "Reset attempted with a fresh identity. All prior plans, observations and permission are invalidated.", "reset")
            elif action == "observe":
                self.runtime.observe()
                self._reviewed = None
                reason = self.runtime.snapshot().get("reason") or "Check readiness before reviewing the current targets and resources."
                self._message("assistant", "Observation checked. " + reason, "observed")
            elif action == "select_targets":
                ids = payload.get("target_ids", [])
                if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
                    raise ValueError("Select target identifiers from the current observation.")
                valid = {item.get("id") for item in self._context().get("observation", {}).get("targets", [])}
                if not set(ids) <= valid:
                    raise ValueError("A selected target is absent from the current observation.")
                self._selected = tuple(ids)
                self._reviewed = None
            elif action == "message":
                text = str(payload.get("text", "")).strip()
                if (self._plan and self._plan.get("normalized_intent") in {"inspect_planting", "inspect_cave"}
                        and text.lower().strip(" ?.! ") not in {"yes", "approve", "start", "go ahead"}):
                    self._plan = self._reviewed = None
                self._message("user", text, "request")
                from smb3_agent.stardew_planting import location_request
                from smb3_agent.stardew_inspection import inspection_request
                from smb3_agent.stardew_cave import cave_request, resolve_destination, DESTINATION, LIMITS
                cave_followup = (self._cave_pending and text.lower().strip(" ?.! ") in {"the farm one", "farm", "that one"}) or (self._cave_destination and text.lower().strip(" ?.! ") in
                    {"farm cave", "the farm one", "that one", "the same one", "continue", "return", "return home", "continue return"})
                control_preview = self.planner.plan(text, {"game_id": "stardew"})
                if control_preview.control:
                    self._plan = self._reviewed = None
                    self._cave_pending = False
                    self.runtime.control(control_preview.control["action"])
                    self._message("assistant", control_preview.message, "control")
                elif cave_request(text) or cave_followup:
                    self._plan = self._reviewed = None
                    destination, clarification = resolve_destination(text, self._cave_destination)
                    if clarification:
                        self._cave_destination = None
                        self._cave_pending = True
                        self._message("assistant", clarification, "clarification")
                    else:
                        self._cave_pending = False
                        self._cave_destination = DESTINATION
                        return_only = text.lower().strip(" ?.! ") in {"continue", "return", "return home", "continue return"}
                        try:
                            plan = self.runtime.propose_cave(text, self.conversation_id, return_only=return_only)
                        except ValueError as exc:
                            self._message("assistant", str(exc)+" "+LIMITS, "advisory")
                        else:
                            self._plan = plan.to_dict()
                            self._message("assistant", plan.requested_objective+" "+plan.fallback_explanation+
                                " Limit: 10 minutes including return. Review and Start or approve this displayed version.", "proposal")
                elif self.runtime.snapshot().get("cave_result") and text.lower().strip(" ?.! ") in {
                        "what did you find", "what did you see", "why", "what is left", "how is it going"}:
                    self._message("assistant", self.progress_summary(self.runtime.snapshot()), "advisory")
                elif inspection_request(text):
                    self._plan = self._reviewed = None
                    plan = self.runtime.propose_inspection(text, self.conversation_id)
                    self._plan = plan.to_dict()
                    self._message("assistant", plan.requested_objective + " " + plan.fallback_explanation + " Limit: 120 seconds including return. Review and Start or approve this displayed version.", "proposal")
                elif location_request(text, self._planting):
                    self._discuss_planting(text)
                elif self._planting and not self._plan and text.lower().strip(" ?.! ") in {"yes", "approve", "start", "go ahead", "plant it", "plant there"}:
                    self._message("assistant", "This is a location recommendation only. Planting, clearing, tilling and purchases need a separate supported activity and explicit review; no input was authorized.", "advisory")
                elif text.lower().strip(" ?.! ") in {"yes", "approve", "start", "go ahead"}:
                    if (not self._plan or payload.get("expected_plan_id") != self._plan["plan_id"]
                            or type(payload.get("expected_revision")) is not int
                            or payload.get("expected_revision") != self._plan["revision"]):
                        raise ValueError("Approval must name the displayed plan version; review the current plan again.")
                    if self._plan["ambiguities"] or self._plan["unsupported_parts"] or self._plan["execution_eligibility"] != "requires_runtime_validation":
                        raise ValueError("Resolve the plan's targets and resource limits before approval.")
                    plan = ConversationPlan.from_dict(self._plan)
                    self.runtime.review(plan)
                    self.runtime.start(plan)
                    self._reviewed = None
                    self._message("assistant", "Approved the displayed plan and started. Discussion stops input; continuation needs a fresh plan and approval.", "started")
                elif text.lower().strip(" ?.! ") in {"what is left", "what's left", "what remains", "remaining work", "how much is left", "how much remains", "how is it going", "what have you watered"}:
                    state = self.runtime.snapshot()
                    self._message("assistant", self.progress_summary(state), "advisory")
                else:
                    # Submission is an explicit observation request. Polling never
                    # activates the game; refresh here lets human composition take
                    # arbitrary time while keeping proposals bound to fresh pixels.
                    preview = self.planner.plan(text, {"game_id": "stardew"})
                    if not preview.control and not is_advisory(normalized_text(text)):
                        if self.runtime.snapshot().get("status") == "running":
                            self.runtime.control("pause")
                        self.runtime.observe()
                    result = self.planner.plan(text, self._context())
                    self._message("assistant", result.message, result.kind)
                    if result.control:
                        self.runtime.control(result.control["action"])
                        self._reviewed = None
                    elif result.plan and result.kind != "advisory":
                        self._plan = result.plan.to_dict()
                        self._reviewed = None
            elif action == "apply":
                assert self._plan is not None
                if self._plan["execution_eligibility"] != "requires_runtime_validation":
                    raise ValueError("This proposal is unavailable for live execution. Resolve the listed prerequisites first.")
                self.runtime.review(ConversationPlan.from_dict(self._plan))
                self._reviewed = deepcopy(self._plan)
                self._message("assistant", "Scope reviewed. Start is a separate explicit Do authorization for this exact plan and session.", "reviewed")
            elif action == "start":
                if self._reviewed is None or self._reviewed != self._plan:
                    raise ValueError("Review this exact scope before Start.")
                self.runtime.start(ConversationPlan.from_dict(self._plan))
                self._reviewed = None
                self._message("assistant", "Started the reviewed farm scope. Chat focus stops ordinary game input.", "started")
            elif action == "resume":
                raise ValueError("Refresh the observation, review the remaining work, then explicitly Start; saved permission never resumes.")
            elif action == "cancel_pending":
                self._reviewed = None
                self._message("assistant", "Review canceled. Confirmed actions and uncertain attempts remain in the outcome.", "cancelled")
            else:
                raise ValueError("Unsupported Stardew conversation action")
            self._requests.add(request_id)
            return self.snapshot()

    def _discuss_planting(self, text):
        from smb3_agent.stardew_planting import recommend
        # Every location discussion invalidates an earlier actionable farm plan.
        self._plan = self._reviewed = None
        self._selected = ()
        try:
            observation = self.runtime.inspect_planting()
        except (ValueError, OSError, AttributeError) as exc:
            observation = {"targets": [], "inspection_error": str(exc)}
        previous = self._planting  # Retain crop/preference as intent; never reuse its observation.
        result = recommend(text, observation, previous)
        if observation.get("inspection_error"):
            result["message"] = observation["inspection_error"] + " " + result["message"]
        self._planting = result
        self._message("assistant", result["message"], "planting_discussion")
        self._planting_messages.extend(deepcopy(self._messages[-2:]))
        self._planting_messages = self._planting_messages[-60:]
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / "planting-discussion.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps({"recommendation": result, "messages": self._planting_messages}))
        temporary.replace(destination)

    @staticmethod
    def progress_summary(state: dict[str, Any]) -> str:
        cave = state.get("cave_result")
        if cave and (state.get("current_plan") or {}).get("normalized_intent") == "inspect_cave":
            return (cave.get("findings", {}).get("message", "No fresh entrance findings yet.") if cave.get("findings")
                    else "No fresh entrance findings yet.") + " Arrival " + ("observed." if cave.get("arrival_observation") else "unknown.") + " Farmhouse return " + ("observed." if cave.get("return_observation") else "incomplete; request return home and approve a revised plan.")
        inspection = state.get("inspection_result")
        if inspection and (state.get("current_plan") or {}).get("normalized_intent") == "inspect_planting":
            return (inspection.get("findings", {}).get("message", "The second area has not yet been observed.")
                    if inspection.get("findings") else "The second area has not yet been observed.") + " Inspection " + inspection["status"] + ". Farmhouse return " + ("confirmed." if inspection.get("return_observation") else "not confirmed.")
        ledger = state.get("ledger")
        if not ledger:
            return "Remaining work is unknown until a fresh complete planted-set observation is available."
        if ledger.get("contract") == "selected-farm-actions/v2":
            steps = "; ".join(f"{s['kind']} {s['target_id']}: {s['status']}" for s in ledger["steps"])
            return (f"{steps}. Last reconciled energy: {ledger['energy_current']}; "
                    f"seeds consumed: {ledger['seed_consumed']}; water consumed: {ledger['can_water_consumed']}. "
                    + str(state.get("reason") or ""))
        observation = state.get("observation") or {}
        tool = observation.get("tool") or {}
        return (f"{ledger.get('watered_count', 'Unknown')} watered; {ledger.get('remaining_count', 'unknown')} remaining. "
                f"Energy: {ledger.get('energy_current') if ledger.get('energy_current') is not None else 'unknown'}. "
                f"Water in can: {tool.get('watering_can_units') if tool.get('watering_can_units') is not None else 'unknown'}. "
                f"Refills: {ledger.get('refills', 'unknown')}. " + str(state.get("reason") or ""))

    def invalidate_for_switch(self) -> bool:
        state = self.runtime.snapshot()
        if state.get("status") == "running" or state.get("owner") == "agent":
            return False
        self.runtime.invalidate()
        with self._lock:
            self._plan = self._reviewed = None
            self._selected = ()
        return True

    def close(self) -> None:
        self.runtime.close()
        self.snapshot()
