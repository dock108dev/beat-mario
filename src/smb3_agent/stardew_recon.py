"""Model-composed reconnaissance on qualified Day 2 viewpoints only.

The model selects capabilities; existing deterministic controllers own every
movement pulse, localization, task reconciliation and release.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import time
from uuid import uuid4

from smb3_agent.codex_provider import InferenceError, validate_object
from smb3_agent.request_planning import ConversationPlan, PlannedAction
from smb3_agent.stardew_adapter import InputKind, StardewAdapterError
from smb3_agent.stardew_inspection import InspectionNavigator
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator


CONTRACT = "stardew/day2/recon/v1"
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["skill", "target_id", "reason", "expected_effect"],
          "properties": {
              "skill": {"type": "string", "enum": ["observe_current", "move_viewpoint", "return_home", "stop"]},
              "target_id": {"type": "string", "maxLength": 120},
              "reason": {"type": "string", "maxLength": 2000},
              "expected_effect": {"type": "string", "maxLength": 2000}}}
RULES = (
    "Investigate the approved spatial question using ONE capability per decision. "
    "observe_current captures terrain/occupancy/access at the current supported viewpoint; "
    "move_viewpoint navigates to another approved viewpoint but does not inspect terrain. "
    "Use target_id from approved_viewpoints for these two skills. First consider a current view; "
    "use its new findings and player preferences to decide whether another view will answer "
    "the question. Compare bare ground, protected vegetation and observed access as appropriate. "
    "Returning early is allowed when answered or another view is not useful. return_home uses "
    "farmhouse_entrance; stop releases input without claiming return. Every activity owes a return. "
    "Only catalog corridors are executable. Never target a terrain tile or infer a new walkable route. "
    "Off-screen findings are historical until reacquired. Empty dirt is visible terrain, not "
    "planting suitability or cleared planting access. Unknown states/access remain unknown. "
    "No tools, watering, planting, clearing, purchases, interior entry or overnight save. "
    "Explain why the next action is useful and what it could establish; never claim an effect "
    "from a prediction. Use prior_effects and findings to change subsequent choices."
)


def catalog(navigator):
    if not isinstance(navigator, ViewpointNavigator) or "east-up" not in navigator.poses:
        raise StardewAdapterError("Reconnaissance needs the qualified Day 2 corridors.")
    return {navigator.return_pose: {"label": "farmhouse porch / mailbox and starter crops",
                                   "coverage": "sampled porch ground, crop occupancy and access strip"},
            "east-up": {"label": "eastern crop margin",
                        "coverage": "two sampled margin tiles; planting access remains unknown"}}


def return_seconds(navigator, start):
    _, path = navigator._path(start, {navigator.return_pose})
    points = [start, *path]
    distance = sum(sum(abs(a-b) for a, b in zip(navigator.poses[left], navigator.poses[right], strict=True))
                   for left, right in zip(points, points[1:]))
    # Conservative operational reserve, not a promise about native latency.
    return 15 + distance / 4


class DecisionCancellation:
    """A local inference deadline shares cancellation with the control owner."""
    def __init__(self, cancel, seconds=45):
        self.cancel, self.deadline = cancel, time.monotonic()+seconds

    def is_set(self):
        return self.cancel.is_set() or time.monotonic() >= self.deadline

    def wait(self, seconds):
        self.cancel.wait(max(0, min(seconds, self.deadline-time.monotonic())))
        return self.is_set()


def proposal(screen, navigator, text, conversation_id, intent):
    available = catalog(navigator)
    ids = intent.get("target_ids") or list(available)
    excluded = intent.get("excluded_ids", [])
    if (len(ids) != len(set(ids)) or not set(ids) <= available.keys()
            or not set(excluded) <= available.keys()):
        raise StardewAdapterError("Resolve the supported viewpoints and exclusions before review.")
    allowed = sorted(set(ids)-set(excluded))
    if not allowed:
        raise StardewAdapterError("No investigation viewpoint remains in the requested scope.")
    start = navigator._nearest(screen)
    maximum = 300
    limit_text = text + " " + " ".join(intent.get("constraints", []))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
             "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45,
             "sixty": 60, "ninety": 90}
    for word in sorted(words, key=len, reverse=True):
        limit_text = re.sub(r"\b"+word+r"(?=\s+(?:seconds?|secs?|minutes?|mins?)\b)",
                            str(words[word]), limit_text, flags=re.I)
    limits = re.findall(r"\b(\d+)\s*(seconds?|secs?|minutes?|mins?)\b",
                        limit_text, re.I)
    if limits:
        maximum = min(maximum, *(int(n)*(60 if unit.lower().startswith("m") else 1) for n, unit in limits))
    for node in allowed:
        navigator._path(start, {node})
        if maximum <= return_seconds(navigator, node) + 30:
            raise StardewAdapterError("That time limit cannot reserve a supported investigation and return; revise it.")
    scope = {"contract": CONTRACT, "viewpoints": allowed,
             "objective": intent["objective"], "preferences": list(intent.get("constraints", [])),
             "excluded_viewpoints": list(excluded)}
    return ConversationPlan(plan_id="recon-"+uuid4().hex, request_id=uuid4().hex,
        original_request=text, conversation_id=conversation_id, game_id="stardew",
        session_id=screen.session_nonce, observation_id=screen.observation_id,
        requested_objective=intent["objective"], normalized_intent="inspect_recon",
        actions=(PlannedAction(action_id="recon", kind="inspect", target_ids=tuple(allowed), parameters=scope),),
        resource_limits={"maximum_seconds": maximum, "maximum_decisions": 6},
        stop_point="farmhouse_entrance",
        fallback_explanation=("Investigate: " + intent["objective"] + ". Allowed views: "
            + "; ".join(available[node]["label"] for node in allowed)
            + ". The model chooses fresh observations and subsequent visits along qualified corridors. "
            + "Preferences: " + "; ".join(scope["preferences"])
            + f". At most six decisions and {maximum} seconds including farmhouse return. "
            + "Excluded views are excluded from investigation; qualified transit and farmhouse return remain required. "
            + "Navigation and observation only; unknown terrain/access stay unknown. No farm work or interior entry."),
        change_summary=(intent["objective"],))


def fresh_finding(observation, current, viewpoint, seen):
    age = (datetime.now(timezone.utc)-datetime.fromisoformat(observation["observed_at"])).total_seconds()
    path = Path(observation["screenshot"])
    if (not 0 <= age <= 5 or observation["session_id"] != current.session_nonce
            or observation["observation_id"] in seen or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != observation["image_sha256"]):
        raise StardewAdapterError("Reconnaissance needs fresh session-bound, hash-bound independent pixels.")
    targets = [deepcopy(t) for t in observation["targets"]
               if t["id"].startswith("east-margin-") == (viewpoint == "east-up")]
    if not targets:
        raise StardewAdapterError("No supported terrain coverage in this view.")
    message = " ".join(f"{t['label']}: {t['state'].replace('_', ' ')}; "
                        + ("adjacent access observed." if t.get("access_observed") else "access unknown.")
                        for t in targets)
    return {"viewpoint": viewpoint, "position": asdict(current.position),
            "observation": {**observation, "targets": targets},
            "message": message + " Terrain alone does not establish planting suitability or planting access."}


class ReconAgent:
    contract = CONTRACT

    def __init__(self, provider, intent, session=None):
        self.provider, self.intent, self.session = provider, deepcopy(intent), session
        self.plan_id = None
        self.reset()

    def reset(self):
        self.records, self.findings = [], []
        self.calls, self.pending = 0, False
        self.active = None
        self.return_reason = None

    def _record(self, runtime, row):
        self.records.append(row)
        runtime._retain("recon-decision", row)
        if self.session:
            self.session.records.append(row)
            self.session._persist()

    def _effect(self, runtime, effect):
        if self.records:
            self.records[-1]["effect"] = effect
        runtime._retain("recon-effect", effect)
        if self.session:
            self.session._persist()

    def decide(self, runtime, current):
        runtime.require_authority()
        nav = runtime._inspection_navigation
        remaining = (datetime.fromisoformat(runtime.controller.authorization.expires_at)
                     - datetime.now(timezone.utc)).total_seconds()
        # Worst-case provider retries share the activity deadline. Reserve return
        # before starting another inference; the model cannot consume this reserve.
        inference_bound = 45
        if self.calls >= 6 or remaining <= return_seconds(nav, nav._nearest(current)) + inference_bound + 5:
            self.return_reason = "Returning within the finite budget; unanswered details remain unknown."
            decision = {"skill": "return_home", "target_id": "farmhouse_entrance",
                        "reason": self.return_reason, "expected_effect": "Independent farmhouse arrival"}
            self._record(runtime, {"role": "recon-controller", "decision": decision, "effect": None})
            return decision
        runtime.driver.neutralize()
        scope = runtime.current_plan.actions[0].parameters
        supplied = {"rules": RULES, "approved_scope": scope,
                    "approved_viewpoints": {k: catalog(nav)[k] for k in scope["viewpoints"]},
                    "current_viewpoint": nav._nearest(current), "position": asdict(current.position),
                    "observation_id": current.observation_id, "observed_at": current.observed_at,
                    "seconds_remaining": remaining, "return_reserve_seconds": return_seconds(nav, nav._nearest(current)),
                    "findings": [{"viewpoint": f["viewpoint"], "observation_id": f["observation"]["observation_id"],
                                  "observed_at": f["observation"]["observed_at"],
                                  "targets": f["observation"]["targets"],
                                  "historical_until_reacquired": True} for f in self.findings[-3:]],
                    "prior_effects": []}
        # Omit old prompts/images from subsequent calls; effects retain provenance.
        supplied["prior_effects"] = [{"decision": r["decision"], "effect": r.get("effect")} for r in self.records[-4:]]
        self.calls += 1
        self.pending = True
        runtime.reason = "Considering the next investigation step; input is released."
        clock = getattr(runtime, "_inference_clock", None)
        decision_source = "model"
        try:
            if clock:
                clock(True)
            cancellation = DecisionCancellation(runtime._cancel)
            try:
                decision = self.provider.infer("gameplay", supplied, SCHEMA, cancellation,
                                               images=current.screenshot_references[:1])
                if cancellation.is_set():
                    raise InferenceError("Reconnaissance decision deadline ended.")
            except InferenceError:
                runtime.require_authority()
                if not cancellation.is_set():
                    raise
                self.return_reason = "Inference time limit reached; returning with partial findings."
                decision_source = "controller_inference_deadline"
                decision = {"skill": "return_home", "target_id": "farmhouse_entrance",
                            "reason": self.return_reason, "expected_effect": "Independent farmhouse arrival"}
            validate_object(decision, SCHEMA)
            runtime.require_authority()
            if clock:
                clock(False)
            fresh = runtime.observer()
            runtime._validate(fresh, allow_player_occlusion=True)
            if not runtime._task_unchanged(current, fresh):
                raise StardewAdapterError("Reconnaissance state or localization changed during inference; review again.")
            runtime.require_authority()
            envelope = runtime.controller.observe(fresh, allow_player_occlusion=True)
            if not envelope.trusted:
                raise StardewAdapterError("Reconnaissance inference revalidation failed.")
            runtime.screen = fresh
            skill, target = decision["skill"], decision["target_id"]
            if skill in {"observe_current", "move_viewpoint"}:
                if target not in scope["viewpoints"]:
                    raise StardewAdapterError("Model selected an unapproved investigation viewpoint.")
                if skill == "observe_current" and not at_view(nav, fresh, target):
                    raise StardewAdapterError("Inspection target is stale or outside the current supported view.")
                if skill == "move_viewpoint" and at_view(nav, fresh, target):
                    raise StardewAdapterError("Movement must establish a different supported view.")
                # Re-check ability to return after the provider delay.
                remaining = (datetime.fromisoformat(runtime.controller.authorization.expires_at)
                             - datetime.now(timezone.utc)).total_seconds()
                _, outward = nav._path(nav._nearest(fresh), {target})
                points = [nav._nearest(fresh), *outward]
                outward_reserve = sum(sum(abs(a-b) for a,b in zip(nav.poses[left], nav.poses[right], strict=True))
                                      for left,right in zip(points, points[1:])) / 4
                if remaining <= outward_reserve + return_seconds(nav, target) + 30:
                    decision_source = "controller_return_reserve"
                    self.return_reason = "Return reserve reached after inference; findings remain partial."
                    decision = {"skill": "return_home", "target_id": "farmhouse_entrance",
                                "reason": self.return_reason,
                                "expected_effect": "Independent farmhouse arrival"}
            elif skill == "return_home" and target != "farmhouse_entrance":
                raise StardewAdapterError("Unknown return target.")
            self._record(runtime, {"role": "recon-gameplay" if decision_source == "model" else "recon-controller",
                                   "decision_source": decision_source, "supplied": supplied, "decision": decision,
                                   "revalidated_observation_id": fresh.observation_id, "effect": None})
            return decision
        finally:
            self.pending = False

    def tick(self, runtime, current):
        nav = runtime._inspection_navigation
        if self.active is None:
            self.active = self.decide(runtime, current)
            current = runtime.screen
            runtime.reason = self.active["reason"] + " Expected: " + self.active["expected_effect"]
            skill = self.active["skill"]
            if skill == "stop":
                runtime.control("stop", reason=self.active["reason"])
                return runtime.ui_snapshot()
            if skill in {"move_viewpoint", "return_home"}:
                nav.destination = self.active["target_id"] if skill == "move_viewpoint" else nav.return_pose
                nav.observed = skill == "return_home"
                nav._waypoint = None
        if self.active["skill"] == "observe_current":
            observation = runtime._planting_observer(inspection=self.active["target_id"] == "east-up")
            runtime.require_authority()
            finding = fresh_finding(observation, current, self.active["target_id"],
                                    {f["observation"]["observation_id"] for f in self.findings})
            after = runtime.observer()
            runtime._validate(after, allow_player_occlusion=True)
            runtime.require_authority()
            if not runtime._task_unchanged(current, after) or not at_view(nav, after, self.active["target_id"]):
                raise StardewAdapterError("Farm or viewpoint changed during reconnaissance observation.")
            runtime.screen = after
            self.findings.append(finding)
            runtime.inspection_result.update(findings=finding, observations=deepcopy(self.findings))
            self._effect(runtime, {"kind": "observation", "viewpoint": finding["viewpoint"],
                                   "observation_id": observation["observation_id"],
                                   "observed_at": observation["observed_at"], "targets": finding["observation"]["targets"]})
            runtime._retain("recon-findings", runtime.inspection_result)
            self.active = None
        else:
            command, event = nav.next_inspection_command(current)
            if event == "returned":
                final = runtime.observer()
                runtime._validate(final)
                runtime.require_authority()
                if not final.position.at_farmhouse_entrance or not runtime._task_unchanged(current, final):
                    raise StardewAdapterError("Reconnaissance farmhouse return is unconfirmed.")
                runtime.screen = final
                self._effect(runtime, {"kind": "return", "observation_id": final.observation_id,
                                       "position": asdict(final.position)})
                runtime.control("stop", reason="Reconnaissance ended; farmhouse return independently observed.")
                handback = runtime.snapshot()["handback_confirmed"]
                runtime.inspection_result.update(status="completed" if handback else "failed",
                    return_observation=asdict(final), handback_confirmed=handback,
                    observations=deepcopy(self.findings), return_reason=self.return_reason,
                    assessment=self.active["reason"],
                    assessment_source="controller" if self.return_reason else "model",
                    question_status="findings retained; review observed facts and unknowns" if self.findings else "unanswered")
                runtime._retain("recon-result", runtime.inspection_result)
            elif event == "observe":
                self._effect(runtime, {"kind": "arrival", "viewpoint": nav.destination,
                                       "observation_id": current.observation_id, "position": asdict(current.position)})
                self.active = None
            else:
                if command.kind != InputKind.KEYBOARD or command.purpose != "navigate":
                    raise StardewAdapterError("Reconnaissance permits guarded navigation only.")
                runtime.require_authority()
                runtime.driver.arm()
                def after():
                    observed = runtime.observer()
                    runtime._validate(observed, allow_player_occlusion=True)
                    runtime.require_authority()
                    return observed
                runtime.screen = runtime.controller.perform_input(command, current, runtime.driver, after)
                runtime._pending_navigation_observation = runtime.screen
                runtime._retain("recon-step", {"command": asdict(command), "before": asdict(current), "after": asdict(runtime.screen)})
        return runtime.ui_snapshot()


def at_view(navigator, screen, target):
    p = screen.position
    x, y = navigator.poses[target]
    return max(abs(x-p.world_pixel_x), abs(y-p.world_pixel_y)) + p.pixel_uncertainty <= 8


def navigation(source):
    return InspectionNavigator(source)
