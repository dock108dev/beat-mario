"""PB1 finite profile execution using shared plans, sessions and attempt history.

The reusable family is one grounded text-button action with independently read
integer entry conditions and reconciled deltas. This is not generic navigation.
"""
from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from smb3_agent.companion_session import (
    AdapterIdentity, CompanionObservationEnvelope, CompanionSession, Freshness,
    GoalIdentity, ModeCapability, Observation, ObservationSource, SafetyBoundary,
    SessionLifecycle, SessionOutcome,
)
from smb3_agent.custom_variants import PlanAttemptHistory
from smb3_agent.game_profiles import ProfileError, valid_box
from smb3_agent.request_planning import AdapterProposal, PlannedAction, Planner, PlanningContext, is_negated
from smb3_agent.host_contracts import InputCommand, InputKind
from smb3_agent.coordinate_contracts import WindowCoordinates
from smb3_agent.skill_registry import exact_delta_verification
from smb3_agent.runtime_events import RuntimeEvents


class ProposalAdapter:
    help_text = "Describe one available bounded skill."

    def __init__(self, profile, reply):
        self.profile, self.reply = profile, reply

    def propose(self, text, context):
        reply = self.reply
        if not isinstance(reply, dict) or set(reply) != {"status", "skill_id", "target_id", "box", "confidence"}:
            raise ProfileError("Structured result rejected: unexpected fields")
        if reply["status"] not in {"propose", "clarify", "refuse"}:
            raise ProfileError("Structured result rejected: status")
        if (not valid_box(reply["box"]) or type(reply["confidence"]) not in {int, float}
                or not math.isfinite(reply["confidence"]) or not 0 <= reply["confidence"] <= 1
                or not isinstance(reply["skill_id"], str) or not isinstance(reply["target_id"], str)):
            raise ProfileError("Structured result rejected: grounding")
        if reply["status"] != "propose" or reply["confidence"] < .9:
            return AdapterProposal("uncertain", text, (), ambiguities=("Target or task requires clarification.",))
        skill = self.profile.skill(reply["skill_id"])
        if reply["target_id"] != skill.target_id:
            raise ProfileError("Model target is outside skill scope")
        # This implemented lexical guard resolves only the finite profile family,
        # not general natural-language semantics. Inference cannot turn an
        # unnamed or explicitly negated action into executable eligibility.
        mentions = [m for verb in skill.request_verbs for m in re.finditer(r"\b"+re.escape(verb)+r"\b", text)]
        if not any(not is_negated(text, m.start()) for m in mentions):
            return AdapterProposal("ambiguous_action", text, (), ambiguities=(
                "Name one supported action explicitly; an unnamed or negated action cannot run.",))
        return AdapterProposal("profile_skill", text,
            (PlannedAction("action-"+uuid4().hex, skill.skill_id, (skill.target_id,),
                           {"box": reply["box"], "profile_sha256": self.profile.digest},
                           tuple(dict(skill.required_before)), tuple(dict(skill.deltas))),),
            base_task_id=skill.skill_id,
            stop_point="one verified action then neutral handback",
            effective_boundary="neutral_before_action", protected_choices=self.profile.protected_actions,
            change_summary=(skill.description,))


class ProfileRuntime:
    def __init__(self, *, profile, host, gateway, driver_factory, root: Path,
                 isolation_receipt: dict, observe_background=False, state_callback=None):
        profile.validate()
        if (isolation_receipt.get("disposable") is not True
                or isolation_receipt.get("load_save_verified") is not True
                or not isolation_receipt.get("evidence_references")):
            raise ProfileError("Verified disposable load/save receipt required")
        self.profile, self.host, self.gateway = profile, host, gateway
        self.observe_background, self.state_callback = observe_background, state_callback
        self._review_frame = None
        if profile.backend_id != gateway.model:
            raise ProfileError("Profile/backend incompatibility")
        self.session_id, self.conversation_id = uuid4().hex, uuid4().hex
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.history = PlanAttemptHistory(self.root / "outcomes")
        self.control_epoch = 0
        self._lock = threading.RLock()
        self._operation = threading.Lock()
        self.cancel = threading.Event()
        self._authority = False
        self._started = time.monotonic()
        self._current = self._reviewed = None
        self.frame = None
        self.release = {"confirmed": False, "method": "not_checked"}
        self.driver = driver_factory(self)
        unknown = Observation(None, None, Freshness.UNKNOWN, None)
        self.session = CompanionSession(
            AdapterIdentity(profile.game_id, profile.game_id, "executable-profile", "experimental"),
            GoalIdentity(profile.profile_id, profile.profile_id, "bounded profile task"), unknown,
            (ModeCapability("tell", True, "Inspect declared skills"),
             ModeCapability("show", False, "No fresh observation", "observe first"),
             ModeCapability("do", False, "No fresh observation", "observe first")),
            SafetyBoundary(False, None, profile.protected_actions, "fresh observation and review"),
            SessionLifecycle.IDLE)
        self._events = RuntimeEvents(self.root / "events.jsonl")
        self.event("session", {"session_id": self.session_id, "profile": asdict(profile),
                              "profile_sha256": profile.digest, "isolation": isolation_receipt})

    def event(self, kind, payload):
        self._events.put({"kind": kind, "at": datetime.now(timezone.utc).isoformat(),
            "monotonic": time.monotonic(), "control_epoch": self.control_epoch, **payload})

    def _stage(self, name):
        if self.state_callback and not self.cancel.is_set():
            self.state_callback(name)
        self.event("phase", {"phase": name})

    def _detect(self, execution=False):
        return self.host.detect_window(require_foreground=execution) if self.observe_background else self.host.detect_window()

    def close_events(self):
        if getattr(self, "resources", None) and not self.resources.close():
            return False
        return self._events.close()

    def require_authority(self):
        if (self._events.failed or not self._authority or self.cancel.is_set()
                or time.monotonic()-self._started > self.gateway.limits.task_seconds):
            raise ProfileError("No current input authority or task deadline expired")

    def begin_chat(self):
        """UI callers invoke BEFORE transferring focus to typed conversation."""
        receipt = self.control("chat_focus")
        if not receipt["confirmed"]:
            raise ProfileError("Neutral receipt unavailable; fresh authority remains blocked")
        return receipt

    def _observe(self, *, execution=False):
        start = time.monotonic()
        frame = (self.host.observe(self.root / "frames", execution=execution) if self.observe_background
                 else self.host.observe(self.root / "frames"))
        if frame.window.bounds[2:] != self.profile.viewport:
            raise ProfileError("Profile viewport incompatibility")
        frame.require_fresh(self._detect(execution), self.profile.frame_max_age,
                            require_foreground=execution or not self.observe_background)
        values = self.profile.values(frame)
        self.event("observation", {"frame_id": frame.frame_id, "capture_monotonic": frame.captured_at,
                   "window": asdict(frame.window), "path": str(frame.path), "sha256": frame.sha256,
                   "text": [asdict(t) for t in frame.text], "values": values,
                   "capture_grounding_seconds": time.monotonic()-start,
                   "frame_age_seconds": time.monotonic()-frame.captured_at,
                   "timing": getattr(self.host, "last_timing", {})})
        return frame, values

    def _observation(self, frame):
        obs = Observation(self.profile.settings_id, datetime.now(timezone.utc), Freshness.FRESH, 1,
                          (str(frame.path),), frame.frame_id, ObservationSource.ADAPTER, self.profile.game_id)
        envelope = CompanionObservationEnvelope(obs, self.profile.game_id,
            {"session_id": self.session_id, "window_id": frame.window.window_id,
             "process_started_at": frame.window.process_started_at},
            self.profile.values(frame), {s.sensor_id: (str(frame.path),) for s in self.profile.sensors},
            "agent" if self._authority else "player")
        envelope.validate()
        return obs

    def propose(self, text):
        # Direct controls bypass inference, even when the backend is unavailable.
        direct = Planner({}).plan(text)
        if direct.control and direct.control["action"] in {"stop", "reclaim", "pause", "cancel_pending"}:
            self.control(direct.control["action"])
            return direct
        self.begin_chat()
        if not self._operation.acquire(blocking=False):
            raise ProfileError("Another operation is ending; retry after neutral handback")
        try:
            with self._lock:
                self.cancel = threading.Event()
                cancel, epoch = self.cancel, self.control_epoch
                current = self._current
                self._reviewed = None
            self._stage("Observing")
            before, values = self._observe()
            signatures = [{"skill_id": s.skill_id, "target_id": s.target_id,
                           "target_text": s.target_text, "description": s.description,
                           "required_before": s.required_before, "deltas": s.deltas}
                          for s in self.profile.skills]
            grounded = []
            for skill in self.profile.skills:
                target = self.profile.target(before, skill)
                grounded.append({"target_id": skill.target_id, "label": target.text,
                                 "box": target.box, "confidence": target.confidence,
                                 "frame_id": before.frame_id})
            context = {"request": text, "skills": signatures, "grounded_targets": grounded,
                       "protected_actions": self.profile.protected_actions,
                       "values": values, "frame_id": before.frame_id}
            self._stage("Planning")
            reply = self.gateway.propose(before, context, cancel)
            if cancel.is_set() or epoch != self.control_epoch:
                raise ProfileError("Late reply belongs to canceled control epoch")
            adapter = ProposalAdapter(self.profile, reply)
            self._stage("Rechecking")
            fresh, fresh_values = self._observe()
            if values != fresh_values:
                raise ProfileError("State changed while inference was pending")
            ctx = PlanningContext(game_id=self.profile.game_id, session_id=self.session_id,
                                  conversation_id=self.conversation_id, observation_id=fresh.frame_id,
                                  observation_fresh=True, current_plan=current)
            result = Planner({self.profile.game_id: adapter}).plan(text, ctx)
            if result.plan and result.plan.actions:
                skill = self.profile.skill(result.plan.actions[0].kind)
                old_target, new_target = self.profile.target(before, skill), self.profile.target(fresh, skill)
                if any(abs(a-b) > .01 for a, b in zip(old_target.box, new_target.box)):
                    raise ProfileError("Target moved during inference; re-ground required")
                # Independent OCR constrains the model box to the same visible label.
                box = reply["box"]
                cx, cy = box[0]+box[2]/2, box[1]+box[3]/2
                x, y, w, h = new_target.box
                if not (x <= cx <= x+w and y <= cy <= y+h):
                    raise ProfileError("Model grounding contradicts independent text target")
            with self._lock:
                if cancel.is_set() or epoch != self.control_epoch:
                    raise ProfileError("Proposal canceled before publication")
                self.frame = fresh
                self._current = result.plan
                self.session = replace(self.session, observation=self._observation(fresh),
                    modes=(ModeCapability("tell", True, "Fresh profile state"),
                           ModeCapability("show", True, "Fresh target grounding"),
                           ModeCapability("do", True, "Review then authorize bounded task")))
            self.event("proposal", {"request": text, "result": result.to_dict(),
                                   "model_reply": reply, "usage": self.gateway.usage,
                                   "backend_identity": getattr(self.gateway, "backend_identity", None)})
            return result
        except Exception as exc:
            self.control("proposal_failed")
            self.event("refusal", {"phase": "proposal", "reason": str(exc)})
            raise
        finally:
            self._operation.release()

    def review(self, plan):
        if not self._operation.acquire(blocking=False):
            raise ProfileError("Another operation is ending")
        try:
            with self._lock:
                if (plan != self._current or not plan or plan.execution_eligibility != "requires_runtime_validation"
                        or len(plan.actions) != 1 or plan.session_id != self.session_id
                        or plan.observation_id != self.frame.frame_id or self.cancel.is_set()):
                    raise ProfileError("Review requires the exact current finite proposal")
                epoch = self.control_epoch
            self._stage("Rechecking")
            fresh, values = self._observe()
            self._validate_review_state(fresh, values, self.frame, plan)
            with self._lock:
                if epoch != self.control_epoch or self.cancel.is_set():
                    raise ProfileError("Review canceled")
                self._review_frame = fresh
                self._reviewed = plan.to_dict()
            self.event("review", {"plan": self._reviewed, "fresh_frame_id": fresh.frame_id})
        finally:
            self._operation.release()

    def _validate_review_state(self, fresh, values, previous, plan):
        import hashlib
        if hashlib.sha256(previous.path.read_bytes()).hexdigest() != previous.sha256:
            raise ProfileError("Reviewed frame bytes changed")
        if (fresh.window.bounds != previous.window.bounds
                or fresh.window.window_id != previous.window.window_id
                or values != self.profile.values(previous)):
            raise ProfileError("Reviewed geometry or state changed")
        skill = self.profile.skill(plan.actions[0].kind)
        old, new = self.profile.target(previous, skill), self.profile.target(fresh, skill)
        if any(abs(a-b) > .01 for a, b in zip(old.box, new.box)):
            raise ProfileError("Reviewed target moved")

    def start(self, plan):
        if not self._operation.acquire(blocking=False):
            raise ProfileError("An operation is already active")
        attempt_id = "profile-"+uuid4().hex
        attempted, changed, final, status, reason = False, None, None, "failed", ""
        before_values = after_values = None
        try:
            with self._lock:
                if not plan or self._reviewed != plan.to_dict() or self._current != plan:
                    raise ProfileError("Start requires exact reviewed plan and revision")
                if not self.release["confirmed"]:
                    raise ProfileError("Previous neutral handback is unconfirmed")
                self._reviewed = None
                if self.cancel.is_set():
                    raise ProfileError("Review authority invalidated")
                self.control_epoch += 1
                epoch, cancel = self.control_epoch, self.cancel
                self._authority = True
                self.session = replace(self.session, lifecycle=SessionLifecycle.ACTIVE,
                                       safety=SafetyBoundary(True, plan.stop_point, self.profile.protected_actions,
                                                             "neutral_before_action"))
            self._stage("Rechecking")
            self.driver.arm()
            before, before_values = self._observe(execution=True)
            self._validate_review_state(before, before_values, self._review_frame or self.frame, plan)
            skill = self.profile.skill(plan.actions[0].kind)
            if (plan.actions[0].parameters.get("profile_sha256") != self.profile.digest
                    or plan.actions[0].target_ids != (skill.target_id,)
                    or before_values != dict(skill.required_before)):
                raise ProfileError("Skill entry, profile or target incompatibility")
            if before_values != self.profile.values(self.frame):
                raise ProfileError("Reviewed state changed")
            target = self.profile.target(before, skill)
            reviewed_target = self.profile.target(self.frame, skill)
            if any(abs(a-b) > .01 for a, b in zip(target.box, reviewed_target.box)):
                raise ProfileError("Reviewed target moved")
            before.require_fresh(self.host.detect_window(), self.profile.frame_max_age)
            x, y, w, h = target.box
            click_x = x+w/2 if skill.click_anchor == "label_center" else x-.03
            click_y = y+h/2
            rx, ry, rw, rh = skill.target_region
            if not (rx < click_x < rx+rw and ry < click_y < ry+rh):
                raise ProfileError("Grounded click anchor is outside reviewed hit region")
            command = InputCommand(InputKind.MOUSE, "left_button", "click", skill.pulse_ms,
                WindowCoordinates(before.window.bounds, before.window.bounds[2:]).native_point(click_x, click_y),
                skill.skill_id)
            # The native driver rechecks authority/focus inside its dispatch lock.
            if epoch != self.control_epoch:
                raise ProfileError("Queued action epoch invalidated")
            self.require_authority()
            self.driver.send(InputCommand(InputKind.MOUSE, "move", "move", 0,
                                          command.target, "grounded_aim"))
            if cancel.wait(.08):
                raise ProfileError("Canceled while aiming")
            aimed, aimed_values = self._observe(execution=True)
            aimed_target = self.profile.target(aimed, skill)
            if aimed_values != before_values or any(abs(a-b) > .01 for a, b in zip(target.box, aimed_target.box)):
                raise ProfileError("Target/state changed while aiming")
            aimed.require_fresh(self.host.detect_window(), self.profile.frame_max_age)
            attempted = True
            self.event("input_proposed", {"command": asdict(command), "frame_id": before.frame_id})
            self._stage("Acting")
            self.driver.send(command)
            self.event("input_acknowledged", {"timing": self.driver.last_pulse_timing})
            if cancel.wait(.15):
                raise ProfileError("Canceled before postcondition verification")
            self._stage("Verifying")
            final, after_values = self._observe(execution=True)
            changed = before_values != after_values
            if not exact_delta_verification(before_values, after_values, skill.deltas) or final.frame_id == before.frame_id or final.captured_at <= before.captured_at:
                raise ProfileError("Observed postcondition not verified")
            with self._lock:
                if epoch != self.control_epoch or cancel.is_set():
                    raise ProfileError("Verification canceled")
                status = "completed"
        except Exception as exc:
            reason = str(exc)
            status = "partial" if attempted else "failed"
        finally:
            self.control("task_finished")
            # Read-only reconciliation happens in the task worker after release.
            # Immediate reclaim never waits for capture, OCR or this record.
            if attempted and final is None:
                try:
                    final, after_values = self._observe()
                    changed = before_values != after_values
                except Exception as exc:
                    self.event("post_stop_observation_unavailable", {"reason": str(exc)})
            if not self.release["confirmed"]:
                status, reason = "partial" if attempted else "failed", "Neutral handback receipt unavailable"
            record = {"status": status, "reason": reason, "game_id": self.profile.game_id,
                      "session_id": self.session_id, "plan": plan.to_dict() if plan else None,
                      "profile_sha256": self.profile.digest, "attempted_input": attempted,
                      "observed_change": changed, "before_values": before_values, "after_values": after_values,
                      "release": self.release, "model_usage": self.gateway.usage,
                      "final_frame": str(final.path) if final else None}
            self.history.record(attempt_id, record)
            self.event("outcome", {"attempt_id": attempt_id, **record})
            final_obs = self._observation(final) if final and status == "completed" else None
            outcome = SessionOutcome(status == "completed", plan.requested_objective if plan else "unknown",
                str(after_values), str({k: after_values[k]-before_values[k] for k in before_values})
                if before_values is not None and after_values is not None else "unknown",
                status, reason, final_obs,
                (str(final.path),) if final else ())
            self.session = replace(self.session,
                lifecycle=SessionLifecycle.COMPLETED if status == "completed" else SessionLifecycle.FAILED,
                safety=SafetyBoundary(False, None, self.profile.protected_actions, "fresh review"),
                outcome=outcome, input_stopped=self.release["confirmed"], control_returned=self.release["confirmed"])
            self.session.validate()
            self._operation.release()
        return record

    def control(self, action="stop"):
        # Never acquire the planner/operation/persistence lock before revocation.
        self._authority = False
        self.control_epoch += 1
        self.cancel.set()
        self._reviewed = self._review_frame = None
        start = time.monotonic()
        try:
            self.driver.neutralize()
            self.release = self.driver.release_receipt()
        except Exception:
            self.release = {"confirmed": False, "method": "neutralization_unavailable"}
        receipt = {"action": action, "seconds": time.monotonic()-start, **self.release}
        self.event("control", receipt)
        if self.state_callback:
            self.state_callback("Stopped")
        return receipt

    def invalidate_volatile_state(self):
        self.control("switch")
        self._current = self._reviewed = self.frame = None
        return self.release["confirmed"]
