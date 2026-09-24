"""Typed, local conversation planning. No input, save or runtime authority lives here.

The bounded grammar recognizes action families and their modifiers, resolves references
against adapter observations, and retains uncertainty instead of guessing targets.
Adapters own capability checks; the runtime must independently authorize every plan.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping, Protocol
from uuid import uuid4

PLAN_SCHEMA_VERSION = "game-companion-plan/v1"
PlanKind = Literal["proposal", "edit", "control", "advisory", "clarification"]


@dataclass(frozen=True)
class PlannedAction:
    action_id: str
    kind: str
    target_ids: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)
    preconditions: tuple[str, ...] = ()
    expected_outcomes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PlannedAction:
        return cls(
            action_id=str(value["action_id"]), kind=str(value["kind"]),
            target_ids=tuple(value.get("target_ids", ())),
            parameters=dict(value.get("parameters", {})),
            preconditions=tuple(value.get("preconditions", ())),
            expected_outcomes=tuple(value.get("expected_outcomes", ())),
        )


@dataclass(frozen=True)
class ConversationPlan:
    plan_id: str
    request_id: str
    original_request: str
    conversation_id: str
    game_id: str
    session_id: str | None
    observation_id: str | None
    requested_objective: str
    normalized_intent: str
    actions: tuple[PlannedAction, ...]
    base_route_id: str | None = None
    base_task_id: str | None = None
    base_version: str = "1"
    variant_id: str | None = None
    revision: int = 1
    parent_revision: int | None = None
    ambiguities: tuple[str, ...] = ()
    unsupported_parts: tuple[str, ...] = ()
    protected_choices: tuple[str, ...] = ()
    resource_limits: dict[str, Any] = field(default_factory=dict)
    stop_point: str | None = None
    effective_boundary: str | None = None
    requested_speed: float | str | None = None
    applied_speed: float | str | None = None
    execution_eligibility: str = "requires_runtime_validation"
    evidence_status: str = "proposal_only"
    authorization_scope: dict[str, Any] = field(default_factory=lambda: {"granted": False})
    fallback_explanation: str = ""
    change_summary: tuple[str, ...] = ()
    completion_coverage: str = "unknown"
    schema_version: str = PLAN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        # Lists make the public contract JSON-shaped even before JSON encoding.
        import json
        return json.loads(json.dumps(asdict(self)))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ConversationPlan:
        """Read plans as data only; stored authority is deliberately discarded."""
        if value.get("schema_version", PLAN_SCHEMA_VERSION) != PLAN_SCHEMA_VERSION:
            raise ValueError("Unsupported conversation plan schema")
        names = cls.__dataclass_fields__
        data = {key: item for key, item in value.items() if key in names}
        data["actions"] = tuple(PlannedAction.from_dict(item) for item in value.get("actions", ()))
        for key in ("ambiguities", "unsupported_parts", "protected_choices", "change_summary"):
            data[key] = tuple(value.get(key, ()))
        data["authorization_scope"] = {**dict(value.get("authorization_scope", {})), "granted": False}
        # Compatibility is a new runtime decision, never a deserialized assertion.
        if data.get("execution_eligibility") in {"authorized", "executable", "running"}:
            data["execution_eligibility"] = "requires_runtime_validation"
        return cls(**data)


@dataclass(frozen=True)
class PlanningContext:
    game_id: str = "mario"
    conversation_id: str = "local-conversation"
    session_id: str | None = None
    observation_id: str | None = None
    observation: dict[str, Any] = field(default_factory=dict)
    current_plan: ConversationPlan | None = None
    selected_targets: tuple[dict[str, Any], ...] = ()
    reviewed_edit_scope: tuple[str, ...] = ()
    requested_speed: float | str | None = None
    applied_speed: float | str | None = None
    observation_fresh: bool | None = None
    supported_speeds: tuple[float | str, ...] = (1.0, "turbo")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PlanningContext:
        data = {key: item for key, item in value.items() if key in cls.__dataclass_fields__}
        if isinstance(data.get("current_plan"), Mapping):
            data["current_plan"] = ConversationPlan.from_dict(data["current_plan"])
        for key in ("selected_targets", "reviewed_edit_scope", "supported_speeds"):
            if key in data:
                data[key] = tuple(data[key])
        return cls(**data)


@dataclass(frozen=True)
class PlanResult:
    kind: PlanKind
    message: str
    plan: ConversationPlan | None = None
    control: dict[str, Any] | None = None
    apply_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "message": self.message,
                "plan": self.plan.to_dict() if self.plan else None,
                "control": self.control, "apply_requested": self.apply_requested}


@dataclass(frozen=True)
class AdapterProposal:
    """Adapter-authored proposal; eligibility is never execution permission."""
    normalized_intent: str
    requested_objective: str
    actions: tuple[PlannedAction, ...]
    base_route_id: str | None = None
    base_task_id: str | None = None
    ambiguities: tuple[str, ...] = ()
    unsupported_parts: tuple[str, ...] = ()
    protected_choices: tuple[str, ...] = ()
    resource_limits: dict[str, Any] = field(default_factory=dict)
    stop_point: str | None = None
    effective_boundary: str | None = None
    requested_speed: float | str | None = None
    execution_eligibility: str = "requires_runtime_validation"
    evidence_status: str = "proposal_only"
    fallback_explanation: str = ""
    change_summary: tuple[str, ...] = ()
    changed_scopes: tuple[str, ...] = ()
    recognized: bool = True


class PlanningAdapter(Protocol):
    """Adapters own their vocabulary, target resolution and capability limits."""
    help_text: str

    def propose(self, text: str, context: PlanningContext) -> AdapterProposal: ...


def normalized_text(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").replace("×", "x").split())


def is_advisory(text: str) -> bool:
    """Polite action requests remain commands; hypothetical/capability talk does not."""
    text = normalized_text(text)
    if re.match(r"^(?:please\s+)?(?:can|could|would|will) you\s+(?:please\s+)?(?:take|use|go|stop|pause|resume|water|harvest|plant|clear|remove|leave|switch|change|set|play|run|do|keep)\b", text):
        return False
    return bool(re.match(r"^(?:what|why|how|when|where|which|is|are|does|do you|can|could|would|should|will|explain|tell me|show me)\b", text)
                or re.search(r"\b(?:what if|maybe|perhaps|i wonder|i suggest|consider|might we)\b", text)
                or text.endswith("?"))


def is_negated(text: str, start: int) -> bool:
    """Negation applies within a clause, including 'leave ... alone' exclusions."""
    prefix = text[:start]
    prefix = re.split(r"[,;]|\b(?:but|then|and)\b", prefix)[-1]
    return bool(re.search(r"\b(?:not|never|don't|dont|do not|no|without|avoid|skip|instead of|rather than)\b", prefix))


def _identity_problem(context: PlanningContext) -> str | None:
    canonical = "mario" if context.game_id == "smb3" else context.game_id
    current = context.current_plan
    if current and (canonical != current.game_id or context.session_id != current.session_id
                    or context.conversation_id != current.conversation_id):
        return "The prior plan belongs to a different game, conversation or session; select a plan for this session."
    observation = context.observation
    for key, expected in (("game_id", canonical), ("session_id", context.session_id),
                          ("observation_id", context.observation_id)):
        actual = observation.get(key)
        if key == "game_id" and actual == "smb3":
            actual = "mario"
        if actual is not None and actual != expected:
            return "The observation belongs to a different game, session or observation; refresh it before planning."
    if context.observation_fresh is False or observation.get("stale") is True or observation.get("fresh") is False:
        return "The observation is stale; refresh it before planning changes."
    for target in context.selected_targets:
        for key, expected in (("game_id", canonical), ("session_id", context.session_id),
                              ("observation_id", context.observation_id)):
            actual = target.get(key)
            if key == "game_id" and actual == "smb3":
                actual = "mario"
            if actual is not None and actual != expected:
                return "A selected target belongs to a different game, session or observation; select it again."
    return None


def speed_label(speed: float | str) -> str:
    return "turbo (uncapped)" if speed == "turbo" else f"{float(speed):g}x"


def speed_from_text(text: str) -> float | str | None:
    if re.search(r"\b(?:turbo|uncapped|faster playback|fast playback)\b", text):
        return "turbo"
    match = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:x\b|times (?:the )?(?:normal )?speed)", text)
    if match:
        return float(match.group(1))
    if re.search(r"\b(?:normal|regular|original) speed\b|\b(?:single|one) speed\b", text):
        return 1.0
    if re.search(r"\b(?:twice as fast|double (?:the )?speed|double time)\b", text):
        return 2.0
    if re.search(r"\b(?:four times as fast|quadruple (?:the )?speed)\b", text):
        return 4.0
    return None


def _control_request(text: str, context: PlanningContext) -> PlanResult | None:
    value = re.sub(r"^(?:(?:please|okay|ok)\s+|(?:can|could|would|will) you\s+(?:please\s+)?)+", "", text)
    value = value.rstrip(".!?")
    if re.search(r"\b(?:don't|do not|never|not)\b", value):
        return None
    controls = {
        "stop": r"(?:stop|stop (?:playing|the agent|now)|end (?:the )?(?:run|session))",
        "pause": r"(?:pause|pause (?:playing|the game|the agent)|hold on|wait a (?:second|moment))",
        "resume": r"(?:resume|resume (?:playing|the game)|continue|keep (?:playing|going)|carry on|unpause)",
        "reclaim": r"(?:take control|give me (?:back )?control|let me (?:play|take over)|i(?:'ll| will) take (?:over|control)|hand (?:it |control )?back)",
        "cancel_pending": r"(?:cancel (?:the )?(?:pending )?(?:edit|change)|cancel that|never ?mind|forget (?:that|the change))",
        "revert": r"(?:revert(?: (?:the )?(?:future|remaining) (?:steps|plan))?|undo (?:the )?(?:last )?(?:edit|change)|go back to (?:the )?(?:previous|original) (?:plan|route))",
    }
    for action, pattern in controls.items():
        if re.fullmatch(pattern, value):
            return PlanResult("control", f"Requested {action.replace('_', ' ')}.", control={"action": action})
    speed = speed_from_text(value)
    speed_only = (speed is not None and not re.search(r"\b(?:route|path|level|world|clear|water|plant|harvest|debris)\b", value))
    if speed_only and re.search(r"\b(?:speed|play|run|make it|set|switch|go|change|normal|double|twice|turbo|uncapped|playback)\b|^\d", value):
        if context.game_id not in {"mario", "smb3"}:
            return PlanResult("clarification", "Playback speed is available only in the Mario adapter.")
        if speed not in context.supported_speeds:
            options = ", ".join(speed_label(item) for item in context.supported_speeds)
            return PlanResult("clarification", f"{speed_label(speed)} is unsupported; choose {options}.")
        return PlanResult("control", f"Requested {speed_label(speed)} playback; applied speed awaits runtime acknowledgment.", control={"action": "speed", "speed": speed})
    if re.fullmatch(r"(?:speed up|slow down|play faster|play slower|increase (?:the )?speed|decrease (?:the )?speed)", value):
        return PlanResult("clarification", "Choose an explicit playback rate: " + ", ".join(speed_label(item) for item in context.supported_speeds) + ". Playback speed does not optimize the route.")
    return None


class Planner:
    """A deterministic backend behind a shared typed contract.

    Recognized requests can be proposed without a current observation, but never
    become executable here. Material unknowns require clarification. There is no
    provider, filesystem write, controller call, or implicit game launch.
    """

    def __init__(self, adapters: Mapping[str, PlanningAdapter] | None = None):
        if adapters is None:
            from smb3_agent.mario_route_plan import MarioPlanningAdapter
            from smb3_agent.stardew_planning import StardewPlanningAdapter
            adapters = {"mario": MarioPlanningAdapter(), "stardew": StardewPlanningAdapter()}
        self.adapters = dict(adapters)

    def plan(self, text: str, context: PlanningContext | Mapping[str, Any] | None = None) -> PlanResult:
        if not isinstance(text, str) or not text.strip():
            return PlanResult("clarification", "Describe the route or farm task you want.")
        if len(text) > 8000:
            return PlanResult("clarification", "Please split this into shorter route or farm requests.")
        ctx = context if isinstance(context, PlanningContext) else PlanningContext.from_dict(context or {})
        value = normalized_text(text)
        advisory = is_advisory(value)
        # Reclaim/stop/pause are always expressible; authority and epochs stay runtime-owned.
        control = None if advisory else _control_request(value, ctx)
        if control and control.control and control.control["action"] in {"stop", "pause", "reclaim", "cancel_pending"}:
            return control
        problem = _identity_problem(ctx)
        if problem:
            return PlanResult("clarification", problem)
        if control:
            return control
        game = "mario" if ctx.game_id == "smb3" else ctx.game_id
        adapter = self.adapters.get(game)
        if adapter is None:
            return PlanResult("clarification", "Choose Mario or Stardew; this game has no planning adapter.")
        proposal = adapter.propose(value, ctx)
        if not proposal.recognized:
            return PlanResult("advisory" if advisory else "clarification", adapter.help_text)
        current = ctx.current_plan
        revision = current.revision + 1 if current else 1
        fields = asdict(proposal)
        for name in ("recognized", "changed_scopes"):
            fields.pop(name)
        fields["actions"] = proposal.actions
        requested_speed = proposal.requested_speed
        if requested_speed is None:
            requested_speed = current.requested_speed if current else (ctx.requested_speed or (1.0 if game == "mario" else None))
        fields["requested_speed"] = requested_speed
        if re.search(r"\b(?:if|unless|until you|when you think|whenever)\b", value) and not advisory:
            fields["ambiguities"] = (*proposal.ambiguities, "Conditional actions need an explicit observable condition and supported boundary before application.")
        if requested_speed is not None and game == "mario" and requested_speed not in ctx.supported_speeds:
            fields["unsupported_parts"] = (*proposal.unsupported_parts, f"Playback rate {speed_label(requested_speed)} is unsupported.")
        ambiguities = tuple(fields["ambiguities"])
        unsupported = tuple(fields["unsupported_parts"])
        eligibility = fields["execution_eligibility"]
        if ambiguities or unsupported:
            eligibility = "blocked"
        elif advisory:
            eligibility = "advisory"
        fields["execution_eligibility"] = eligibility
        plan = ConversationPlan(
            plan_id=current.plan_id if current else "plan-" + uuid4().hex,
            request_id="request-" + uuid4().hex, original_request=text,
            conversation_id=ctx.conversation_id, game_id=game, session_id=ctx.session_id,
            observation_id=ctx.observation_id,
            variant_id=current.variant_id if current else None, revision=revision,
            parent_revision=current.revision if current else None,
            applied_speed=ctx.applied_speed,
            authorization_scope={"granted": False, "scope": "bounded_session_plan", "requires_fresh_runtime_authority": True},
            **fields,
        )
        if ambiguities:
            return PlanResult("advisory" if advisory else "clarification", " ".join((*ambiguities, *unsupported)), plan)
        if unsupported:
            return PlanResult("advisory" if advisory else "clarification", " ".join(unsupported), plan)
        if advisory:
            message = "Preview only. " + " ".join(proposal.change_summary)
            return PlanResult("advisory", message, plan)
        kind: PlanKind = "edit" if current else "proposal"
        scopes = set(proposal.changed_scopes)
        reviewed = set(ctx.reviewed_edit_scope)
        # Unambiguous edits inside an explicitly reviewed scope request application;
        # the service/runtime still check revision, freshness and capability.
        apply_requested = bool(current and scopes and scopes <= reviewed and eligibility == "requires_runtime_validation")
        message = " ".join(proposal.change_summary) or "Plan prepared for review."
        if proposal.fallback_explanation:
            message += " " + proposal.fallback_explanation
        if current and not apply_requested:
            message += " Review this change and choose Apply before it can take effect."
        return PlanResult(kind, message, plan, apply_requested=apply_requested)
