"""Separate contextual language and gameplay roles atop existing authority owners."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
import re
import threading
import time
from uuid import uuid4

from smb3_agent.codex_provider import InferenceError, validate_object
from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.request_planning import ConversationPlan, PlanningContext
from smb3_agent.stardew_planning import StardewPlanningAdapter


def closed_schema(properties):
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


STRING = {"type": "string", "maxLength": 2000}
IDS = {"type": "array", "items": {"type": "string", "maxLength": 120}, "maxItems": 32}
INTENT_SCHEMA = closed_schema({
    "interaction": {"type": "string", "enum": ["activity", "correction", "question", "coaching", "approval", "clarify", "unsupported"]},
    "objective": STRING, "message": STRING, "canonical_command": STRING,
    "target_ids": IDS, "excluded_ids": IDS,
    "constraints": {"type": "array", "items": STRING, "maxItems": 12},
    "minimum_energy": {"type": "integer", "minimum": 1, "maximum": 270},
    "minimum_water": {"type": "integer", "minimum": 0, "maximum": 40},
    "maximum_water_uses": {"type": "integer", "minimum": 0, "maximum": 32},
    "maximum_seconds": {"type": "integer", "minimum": 0, "maximum": 600},
    "maximum_attempts": {"type": "integer", "minimum": 0, "maximum": 5},
})
DECISION_SCHEMA = closed_schema({
    "skill": {"type": "string", "enum": ["water_target", "return_home", "stop"]},
    "target_id": {"type": "string", "maxLength": 120},
    "reason": STRING, "expected_effect": STRING,
})
LANGUAGE_RULES = (
    "Interpret the original wording and relevant prior turns. Corrections replace the goal while retaining still applicable "
    "exclusions/preferences. Questions, suggestions and coaching grant no input. Approval only refers to a displayed scope; "
    "the app requires Review and Start. Preserve unsupported goals and explain the missing skill. "
    "Stardew first AI activity is watering an explicitly resolved subset of observed dry crops then returning home. "
    "Choose target_ids from supplied observations; ambiguous references or unknown species require clarification. "
    "Never identify unknown crop species from typical farm layouts. Account for water and known energy cost/reserve. "
    "Respect scene_scope: selected-session support covers the observed local seed patch only. Never claim whole-farm coverage or map an unobserved target into it. Explain wider-farm requests and offer the observed targets. "
    "Use the supplied energy_cost_upper_bound per crop when discussing resources; do not guess totals. "
    "Use minimum_energy=1 and minimum_water=0 unless the player specifies larger reserves. "
    "maximum_water_uses=32 means no smaller player limit; zero means no watering permitted. "
    "Resolve water reserves, maximum uses, duration in seconds and finite attempts into the numeric fields, "
    "not only constraints. maximum_seconds=0 and maximum_attempts=0 mean no explicit player limit. "
    "Corrections retain applicable numeric limits from current_goal unless explicitly replaced. "
    "If all requested targets cannot fit the limits, clarify a smaller selection; never silently drop crops. "
    "constraints describe priorities, exclusions and "
    "preferences for the gameplay agent. Stardew canonical_command water enables adaptive watering. Existing controller activities "
    "remain available: reconnaissance for model-directed spatial investigation using the supplied reconnaissance_viewpoints catalog. "
    "Resolve target_ids and excluded_ids as catalog viewpoint IDs (home is the porch, east-up the eastern margin); "
    "empty target_ids means both supported views. excluded_ids excludes investigation views, not required farmhouse return/transit. "
    "Clarify any physical-area avoidance that conflicts with the qualified transit/return. "
    "Put spatial preferences, desired findings, avoidance and explicit time limits in constraints; normalize time limits to numeric seconds. "
    "Reconnaissance investigates terrain/occupancy/access and compares supported areas; planting suitability needs separate crop/season rules. "
    "Never map an unsupported destination to a supported view; clarify ambiguous destinations. "
    "inspect_eastern_margin also enables model-directed reconnaissance; inspect_farm_cave for exterior cave "
    "reconnaissance if its route is available; discuss_planting for passive location guidance; or an explicit canonical farm "
    "routine describing harvest/plant/water/clear IDs and owned seed type on a qualified Day 5 profile. These other activities "
    "apart from reconnaissance have existing deterministic execution. Unsupported interior/arbitrary exploration "
    "or purchases must explain the missing capability. "
    "Mario supports the existing opening coaching, coin discovery/routes and flight proposal boundaries; canonical_command "
    "must use natural command wording understood by the existing controller planner, such as practice the opening jump, "
    "find a coin route, fly to the hidden 1UP, or base path to level exit; never invent snake_case command names. "
    "Opening practice uses an adaptive gameplay agent that composes bounded walks and hops with chosen jump delay and hold frames. Preserve height, timing and landing preferences in constraints. Broader strategy is unavailable. "
    "Never turn an unsupported intent into a different supported task."
)
GAME_RULES = (
    "Choose ONE available skill inside the approved goal. Target choice changes actual navigation and watering. "
    "Use spatial location, resources, player preferences and independently observed prior effects to select the next target. "
    "Only observed dry crops in remaining_ids may be watered. Water costs the supplied upper bound in energy and one can unit. "
    "No refill, purchase, harvest or new targets. water_target uses an exact crop ID; return_home uses target_id farmhouse_entrance or empty. Return_home only after all approved crops are confirmed watered; stop if blocked, "
    "insufficient resources or uncertain observations. Explain the expected observable effect; never claim success from a command."
)


class LanguageSession:
    """App-owned generations; no provider thread can grant or restore control."""
    def __init__(self, service, provider, game):
        self.service, self.provider, self.game = service, provider, game
        self._guard = threading.RLock()
        self._cancel = threading.Event()
        self.generation = 0
        self.state = "idle"
        self.intent = None
        self.records = []
        self._worker = None
        self._seen = set()
        self._history = []
        self._closed = False
        path = service.root/"ai-history.json"
        if path.is_file():
            try:
                self._history = json.loads(path.read_text())[-12:]
            except (ValueError, OSError, TypeError):
                pass

    def snapshot(self):
        return {"state": self.state, "provider": dict(self.provider.status), "intent": deepcopy(self.intent),
                "requests": self.provider.lifecycle() if hasattr(self.provider, "lifecycle") else [],
                "records": deepcopy(self.records[-20:]), "historical": deepcopy(self._history[-4:])}

    def cancel(self):
        with self._guard:
            lifecycle = self.provider.lifecycle() if hasattr(self.provider, "lifecycle") else []
            self._cancel.set()
            self.generation += 1
            self.state = "canceled"
            self.records.append({"role": "cancellation", "observed_monotonic": time.monotonic(),
                                 "requests_at_cancel": lifecycle})

    def close(self):
        self._closed = True
        self.cancel()
        if self._worker:
            self._worker.join(timeout=2)

    def invalidate_context(self):
        """A switched game cannot resolve references using its former live goal."""
        self.cancel()
        with self._guard:
            self.intent = None
            self.state = "idle"

    def submit(self, payload):
        s = self.service
        request_id = str(payload.get("request_id") or uuid4().hex)
        with self._guard:
            if self._closed or request_id in self._seen:
                return s.snapshot()
            self._seen.add(request_id)
        self.cancel()
        submission_generation = self.generation
        # Discussion ends any current authority before context capture.
        if self.game == "stardew":
            if s.runtime.snapshot().get("status") in {"running", "stopping"} or getattr(s.runtime, "_preparation_driver", None):
                s.runtime.control("pause")
        elif s._active() or s.live_manager.snapshot().control_owner == "agent":
            s.dispatch("stop")
        with s._lock:
            if hasattr(s, "_reviewed"):
                s._reviewed = None
            text = str(payload.get("text", "")).strip()
            if not text or len(text) > 4000:
                raise ValueError("Enter a request of up to 4000 characters")
            s._message("user", text, "request")
            prior = deepcopy(s._plan)
            s._plan = None
            messages = deepcopy(s._messages[-12:])
        with self._guard:
            if submission_generation != self.generation or self._closed:
                return s.snapshot()
            cancel = self._cancel = threading.Event()
            generation = self.generation
            self.state = "interpreting"
        def work():
            try:
                if cancel.is_set() or generation != self.generation or self._closed:
                    return
                if self.game == "stardew" and getattr(s.runtime, "observer", None):
                    # Capture and validate once, without assembling a UI snapshot
                    # before the language context consumes this fresh observation.
                    refresh = getattr(s.runtime, 'refresh_observation', s.runtime.observe)
                    refresh()
                if cancel.is_set() or generation != self.generation or self._closed:
                    return
                # Consume the fresh world frame before the guarded Escape/menu
                # transition pauses the disposable clock. That transition is
                # independently checked, but its work must not age this context.
                context = s._context()
                context["current_plan"] = prior
                # Slow discussion must not advance the disposable farm clock.
                # Explicit Observe/Review/Start reacquires pixels and resumes it;
                # cancellation leaves a neutral paused game, never restored work.
                if self.game == "stardew" and getattr(s.runtime, "_inference_clock", None):
                    s.runtime._inference_clock(True)
                if cancel.is_set() or generation != self.generation or self._closed:
                    return
                images = ()
                if self.game == "stardew" and getattr(s.runtime, "screen", None):
                    images = s.runtime.screen.screenshot_references[:1]
                language_rules = LANGUAGE_RULES
                from smb3_agent.paths import is_packaged
                if is_packaged():
                    language_rules += (
                        " This delivered candidate supports only Mario play the early segment and Stardew water. "
                        "Reconnaissance, coin routes, flight, recording, Day 5 and wider game actions are unavailable. "
                        "For those requests use interaction=unsupported, canonical_command empty, and explain the coverage limit."
                    )
                if self.game == 'mario':
                    from smb3_agent.mario_segment import LANGUAGE_RULES as SEGMENT_LANGUAGE
                    language_rules = language_rules.replace('Broader strategy is unavailable.', '') + SEGMENT_LANGUAGE
                    context['remembered_guidance'] = s._guidance_snapshot()
                supplied = {"rules": language_rules, "request": text, "conversation": messages,
                            "current_goal": self.intent, "context": context,
                            "historical_guidance": self._history[-4:]}
                intent_schema = deepcopy(INTENT_SCHEMA)
                if self.game == "stardew" and not context.get("observation", {}).get("farm_contract"):
                    # Capability identifiers are app contracts, not player wording.
                    # Free-form identifiers can describe the correct goal yet fail
                    # routing. Day 5 retains its existing parameterized translator.
                    intent_schema["properties"]["canonical_command"] = {"type": "string", "enum": [
                        "water", "reconnaissance", "inspect_eastern_margin", "inspect_farm_cave", "discuss_planting", ""]}
                result = self.provider.infer("language", supplied, intent_schema, cancel, images=images)
                validate_object(result, intent_schema)
                with self._guard:
                    if cancel.is_set() or generation != self.generation or self._closed:
                        return
                    # A reset/connection switch also invalidates replies independently.
                    if s._context().get("session_id") != context.get("session_id"):
                        raise ValueError("Game session changed during inference; request again")
                    with s._lock:
                        self.intent = result
                        self.state = "ready"
                        self.records.append({"role": "language", "request": text, "supplied": supplied, "result": result})
                        self._history.append({"game": self.game, "request": text, "intent": result,
                                              "historical": True, "input_authority": False})
                        self._history = self._history[-12:]
                        s.root.mkdir(parents=True, exist_ok=True)
                        (s.root/"ai-history.json").write_text(json.dumps(self._history, indent=2))
                        self._apply(result, context, text)
                        self._persist()
            except Exception as exc:
                with self._guard:
                    if cancel.is_set() or generation != self.generation or self._closed:
                        return
                    self.state = "failed"
                    with s._lock:
                        s._plan = None
                        # Provider raises sanitized errors; do not expose arbitrary logs.
                        s._message("assistant", str(exc) if isinstance(exc, ValueError) else "Inference failed; no input was authorized.", "error")
        self._worker = threading.Thread(target=work, daemon=True, name="companion-language")
        # Building the initial UI response can validate persistence and assemble
        # route/status data. Finish it before acquiring the inference frame so
        # that concurrent response work cannot consume that frame's freshness.
        response = s.snapshot()
        self._worker.start()
        return response

    def _persist(self):
        path = self.service.root/"ai-decisions.json"
        path.write_text(json.dumps(self.records[-40:], indent=2))

    def _apply(self, intent, context, original):
        s = self.service
        interaction = intent["interaction"]
        if interaction not in {"activity", "correction", "coaching"}:
            if interaction in {"question", "approval"}:
                s._plan = deepcopy(context.get("current_plan"))
            s._message("assistant", intent["message"] + (" Use Review and Start on the displayed scope." if interaction == "approval" else ""),
                       "clarification" if interaction == "clarify" else "advisory")
            return
        if self.game == "mario":
            # Existing planners validate the interpreted scope before gameplay.
            command = intent["canonical_command"]
            expanded = command.lower().strip() == 'play the early segment'
            if expanded:
                command = 'practice the opening jump'
            if not command:
                raise ValueError("No supported Mario command was resolved")
            s._operation_generation = s._control_generation
            message_index = len(s._messages)
            attempt_limit = re.search(r"\b(one|two|three|four|five|\d+)\s+(attempts?|tr(?:y|ies))\b",
                                      " ".join(intent["constraints"]), re.IGNORECASE)
            if attempt_limit and not intent["maximum_attempts"]:
                command += " for " + attempt_limit.group(0)
            if intent["maximum_attempts"]:
                command += " for " + str(intent["maximum_attempts"]) + " attempts"
            s._dispatch("message", {"text": command}, uuid4().hex)
            # Keep the player's original words in the conversation; the internal
            # planner command is a validated translation, not a second user turn.
            if len(s._messages) > message_index and s._messages[message_index]["role"] == "user":
                del s._messages[message_index]
            if s._plan:
                s._plan.update(original_request=original, requested_objective=intent["objective"],
                               model_intent=deepcopy(intent))
            if s._plan and s._plan.get("coaching_compatibility"):
                from smb3_agent.mario_strategy import CONTRACT
                s._plan["strategy_contract"] = CONTRACT
                del s._messages[message_index:]
                s._plan["fallback_explanation"] = "Experimental adaptive opening strategy; full-level play and generalized coverage remain unavailable."
                s._plan["change_summary"] = ["Adaptive opening strategy: model composes walks and hops (delay 0–12, hold 1–26 frames), stopping at x ≥ 160. Each attempt permits six decisions, 180 skill frames and 120 seconds, inside the displayed finite retry budget."]
            if expanded and s._plan:
                from smb3_agent import mario_segment
                mario_segment.expand_plan(s._plan)
                s._plan["resource_limits"]["maximum_seconds_per_attempt"] = min(
                    intent["maximum_seconds"] or mario_segment.MAX_SECONDS, mario_segment.MAX_SECONDS)
                if interaction in {'coaching', 'correction'}:
                    mario_segment.remember(s.coaching, intent, original, getattr(s.live_manager, '_game_file_sha256', None))
            s._message("assistant", intent["message"], "interpretation")
            return
        command = intent["canonical_command"]
        if command in {"inspect_eastern_margin", "reconnaissance"}:
            from smb3_agent.stardew_recon import ReconAgent
            plan = s.runtime.propose_recon(original, s.conversation_id, intent)
            s._plan = plan.to_dict()
            s.runtime.gameplay_agent = ReconAgent(self.provider, intent, self)
            s.runtime.gameplay_agent.plan_id = plan.plan_id
            s._message("assistant", intent["message"] + " " + plan.fallback_explanation + " Review and Start are required.", "proposal")
            return
        if command == "inspect_farm_cave":
            plan = s.runtime.propose_cave(original, s.conversation_id)
            s._plan = plan.to_dict()
            s._message("assistant", intent["message"] + " Exterior reconnaissance only; Review and Start are required.", "proposal")
            return
        if command == "discuss_planting":
            s._discuss_planting(original)
            return
        if command != "water":
            if context["observation"].get("farm_contract"):
                result = s.planner.plan(command, {**context, "current_plan": None})
                if result.plan and not result.control:
                    s._plan = result.plan.to_dict()
                    s._plan.update(original_request=original, requested_objective=intent["objective"])
                    s._message("assistant", intent["message"] + " " + result.message, result.kind)
                    return
            raise ValueError("The requested activity requires an unavailable game capability")
        current = context["observation"]
        ids, excluded = intent["target_ids"], set(intent["excluded_ids"])
        known = {t["id"]: t for t in current.get("targets", [])}
        if not ids or len(set(ids)) != len(ids) or not set(ids) <= known.keys() or set(ids) & excluded:
            raise ValueError("Resolve unique observed watering targets and exclusions before review")
        if any(known[key].get("watered") is not False or known[key].get("confidence") != 1 or known[key].get("visible") is False for key in ids):
            raise ValueError("Requested crops need a clear, independently confirmed dry observation")
        if not current.get("watering_activity"):
            raise ValueError("AI watering currently requires a qualified watering-only screen profile")
        # Reuse the adapter's resource/route/precondition validation, starting from
        # the model's target set rather than a text-selected scripted patch.
        ctx = PlanningContext.from_dict({**context, "current_plan": None, "selected_targets": [known[k] for k in ids]})
        proposal = StardewPlanningAdapter().propose("water selected crops; keep at least " + str(intent["minimum_energy"]) + " energy", ctx)
        limits = {**proposal.resource_limits,
                  "minimum_water": intent["minimum_water"],
                  "maximum_water_uses": intent["maximum_water_uses"],
                  "maximum_seconds": min(intent["maximum_seconds"] or 120, 180)}
        ambiguities = list(proposal.ambiguities)
        water = current.get("water")
        if len(ids) > limits["maximum_water_uses"]:
            ambiguities.append("The selected crops exceed your watering-use limit. Choose fewer targets or revise the limit, then review again.")
        if water is None or water - len(ids) < limits["minimum_water"]:
            ambiguities.append("The selected crops would cross your water reserve. Refill manually or choose fewer targets, then request again.")
        plan = ConversationPlan(plan_id="ai-"+uuid4().hex, request_id=uuid4().hex,
            original_request=original, conversation_id=s.conversation_id, game_id="stardew",
            session_id=ctx.session_id, observation_id=ctx.observation_id,
            requested_objective=intent["objective"], normalized_intent="farm_routine",
            actions=proposal.actions, base_task_id=proposal.base_task_id,
            ambiguities=tuple(ambiguities), unsupported_parts=proposal.unsupported_parts,
            protected_choices=proposal.protected_choices, resource_limits=limits,
            stop_point=proposal.stop_point, fallback_explanation=proposal.fallback_explanation,
            execution_eligibility=proposal.execution_eligibility)
        s._plan = plan.to_dict()
        s._plan["model_intent"] = deepcopy(intent)
        s.runtime.gameplay_agent = WateringAgent(self.provider, intent, self)
        s.runtime.gameplay_agent.plan_id = plan.plan_id
        s._message("assistant", intent["message"] + " " +
                   f"At most {limits['maximum_seconds']} seconds including return; keep {limits['minimum_water']} water units and use at most {limits['maximum_water_uses']}. " +
                   "Review and Start are required. " + " ".join(ambiguities), "proposal")


class WateringAgent:
    """Finite target-level choices; fast navigation remains controller-owned."""
    def __init__(self, provider, intent, session=None):
        self.provider, self.intent, self.session = provider, deepcopy(intent), session
        self.target = None
        self.returning = False
        self.calls = 0
        self.records = []
        self.pending = False
        self.plan_id = None

    def reset(self):
        self.target, self.returning, self.calls = None, False, 0
        self.records = []

    def choose(self, runtime, current, remaining):
        if self.target in remaining:
            return {self.target}
        if self.returning and not remaining:
            return set()
        if self.calls >= 20:
            raise StardewAdapterError("Gameplay decision budget exhausted")
        runtime.require_authority()
        runtime.driver.neutralize()
        context = runtime.planning_context()
        # During navigation the avatar can hide an unrelated tile. The runtime
        # validated this partial frame against the ledger; preserve its uncertainty
        # while supplying current resources and independently visible candidates.
        state = {**context.observation, "source": "automatic_visible", "validated": True,
                 "coverage": "partial" if any(c.occluded for c in current.crops) else "complete",
                 "energy": current.energy, "water": current.tool.watering_can_units,
                 "selected_tool": current.tool.selected_tool,
                 "energy_cost_upper_bound": runtime.navigator.energy_cost_upper_bound}
        supplied = {"rules": GAME_RULES, "goal": self.intent, "observation": asdict(current.position),
                    "observed_at": current.observed_at, "observation_id": current.observation_id,
                    "state": state, "remaining_ids": sorted(remaining),
                    "approved_ids": list(runtime.controller.operator.ledger.task_crop_ids),
                    "terrain": runtime.navigator.agent_context(),
                    "prior_effects": [{"decision": deepcopy(row["decision"]), "effect": deepcopy(row["effect"]),
                                      "observation_id": row["revalidated_observation_id"]} for row in self.records[-6:]]}
        self.calls += 1
        self.pending = True
        runtime.reason = "Considering the next crop from observed progress; input is released."
        try:
            clock = getattr(runtime, "_inference_clock", None)
            if clock:
                clock(True)
            result = self.provider.infer("gameplay", supplied, DECISION_SCHEMA, runtime._cancel,
                                         images=current.screenshot_references[:1])
            validate_object(result, DECISION_SCHEMA)
            runtime.require_authority()
            if clock:
                clock(False)
            # Inference can outlive frame freshness: acquire independent pixels and
            # reject changed task/resources/process/focus before executing a choice.
            fresh = runtime.observer()
            runtime._validate(fresh, allow_player_occlusion=True)
            if not runtime._task_unchanged(current, fresh):
                raise StardewAdapterError("Observed task changed during inference; fresh review is required")
            runtime.require_authority()
            runtime.controller.observe(fresh, allow_player_occlusion=True)
            runtime.screen = fresh
            skill, target = result["skill"], result["target_id"]
            if skill == "stop":
                raise StardewAdapterError("Agent stopped: " + result["reason"])
            if skill == "water_target":
                crop = next((c for c in fresh.crops if c.crop_id == target), None)
                if target not in remaining or target not in self.intent["target_ids"] or target in self.intent["excluded_ids"] or crop is None or crop.occluded or crop.watered is not False:
                    raise StardewAdapterError("Agent selected an unapproved or uncertain target")
                self.target, self.returning = target, False
            elif remaining or target not in {"", "farmhouse_entrance"}:
                raise StardewAdapterError("Agent cannot return before approved watering completes or name a return target")
            else:
                self.target, self.returning = None, True
            record = {"role": "gameplay", "supplied": supplied, "decision": result,
                      "effect": None, "revalidated_observation_id": fresh.observation_id}
            self.records.append(record)
            runtime._retain("model-decision", record)
            if self.session:
                self.session.records.append(record)
                self.session._persist()
            runtime.reason = result["reason"] + " Expected: " + result["expected_effect"]
            return {self.target} if self.target else set()
        except InferenceError as exc:
            raise StardewAdapterError(str(exc)) from exc
        finally:
            self.pending = False

    def effect(self, runtime, command, before, after):
        if not self.records:
            return
        if command.purpose == "water_crop":
            effect = {"target_id": command.reviewed_crop_id, "observation_id": after.observation_id,
                      "watered": next(c.watered for c in after.crops if c.crop_id == command.reviewed_crop_id),
                      "energy_before": before.energy, "energy_after": after.energy,
                      "water_before": before.tool.watering_can_units, "water_after": after.tool.watering_can_units}
            self.records[-1]["effect"] = effect
            runtime._retain("model-effect", effect)
            if self.session:
                self.session._persist()
