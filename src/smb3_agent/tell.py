from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from smb3_agent.paths import repository_path

from smb3_agent.companion_session import Freshness, Observation, ObservationSource
from smb3_agent.goals import GoalContract, load_product_goal_contracts
from smb3_agent.segments import RouteSegment, load_segment_catalog, validate_goal_segments


TELL_KNOWLEDGE_PATH = repository_path("data/tell/mario.yaml")
SUPPORTED_PROVENANCE_CLASSES = {
    "adapter_observation",
    "player_reported_fact",
    "goal_contract",
    "segment_contract",
    "accepted_game_knowledge",
    "accepted_evidence",
    "watering_ledger",
    "adapter_safety_policy",
}


class TellValidationError(ValueError):
    pass


class SpoilerLevel(str, Enum):
    MINIMAL = "minimal"
    GUIDED = "guided"
    FULL = "full"


@dataclass(frozen=True)
class ObservedFact:
    fact_id: str
    value: str
    source: ObservationSource


@dataclass(frozen=True)
class ProvenanceReference:
    source_class: str
    record_id: str
    label: str

    def validate(self) -> None:
        if self.source_class not in SUPPORTED_PROVENANCE_CLASSES:
            raise TellValidationError(f"unsupported provenance class: {self.source_class}")
        if not self.record_id or not self.label:
            raise TellValidationError("provenance requires a record id and label")


@dataclass(frozen=True)
class GroundedText:
    text: str
    provenance: tuple[ProvenanceReference, ...]

    def validate(self) -> None:
        if not self.text or not self.provenance:
            raise TellValidationError("every factual Tell item requires text and provenance")
        for reference in self.provenance:
            reference.validate()


@dataclass(frozen=True)
class TellStep:
    action: GroundedText
    expected_cue: GroundedText

    def validate(self) -> None:
        self.action.validate()
        self.expected_cue.validate()


@dataclass(frozen=True)
class TellRequest:
    game_id: str
    goal: GoalContract
    observation: Observation
    facts: tuple[ObservedFact, ...]
    spoiler_level: SpoilerLevel
    protected_decisions: tuple[str, ...]


@dataclass(frozen=True)
class TellCard:
    state_summary: GroundedText
    observation_source: ObservationSource
    objective: GroundedText
    steps: tuple[TellStep, ...]
    risks: tuple[GroundedText, ...]
    recovery: tuple[GroundedText, ...]
    spoiler_level: SpoilerLevel
    protected_decisions_honored: tuple[str, ...]
    uncertainty: GroundedText
    refresh_requirement: GroundedText

    def validate(self) -> None:
        self.state_summary.validate()
        self.objective.validate()
        if not self.steps:
            raise TellValidationError("Tell card requires at least one instruction step")
        for step in self.steps:
            step.validate()
        for item in (*self.risks, *self.recovery):
            item.validate()
        self.uncertainty.validate()
        self.refresh_requirement.validate()


@dataclass(frozen=True)
class TellKnowledgeRecord:
    game_id: str
    segment_id: str
    required_facts: tuple[tuple[str, str], ...]
    actions: tuple[str, ...]
    cues: tuple[str, ...]
    risks: tuple[str, ...]
    recovery: tuple[str, ...]
    protected_actions: tuple[str, ...]
    evidence_references: tuple[str, ...]


def load_tell_knowledge(
    path: Path = TELL_KNOWLEDGE_PATH,
    *,
    goals: tuple[GoalContract, ...] | None = None,
) -> dict[str, TellKnowledgeRecord]:
    if not path.is_file():
        raise TellValidationError(f"Tell knowledge catalog not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict) or raw.get("schema") != "game-companion-tell/v1":
        raise TellValidationError("Tell knowledge requires schema game-companion-tell/v1")
    records_raw = raw.get("records")
    if not isinstance(records_raw, list) or not records_raw:
        raise TellValidationError("Tell knowledge records must be a non-empty list")
    records: dict[str, TellKnowledgeRecord] = {}
    for index, item in enumerate(records_raw):
        record = _load_record(index, item)
        if record.segment_id in records:
            raise TellValidationError(f"duplicate Tell knowledge record: {record.segment_id}")
        records[record.segment_id] = record

    product_goals = goals or load_product_goal_contracts()
    expected: set[str] = set()
    catalogs: dict[Path, Any] = {}
    for goal in product_goals:
        catalog = catalogs.setdefault(goal.catalog_path, load_segment_catalog(goal.catalog_path))
        validate_goal_segments(goal, catalog)
        if goal.game != raw.get("game") or catalog.game != raw.get("game"):
            raise TellValidationError("Tell knowledge, goal, and segment game identities disagree")
        for step in goal.route_steps:
            segment = catalog.by_id[step.id]
            if step.execution_mode == "normal_gameplay" and segment.status == "solved":
                expected.add(step.id)
    actual = set(records)
    if actual != expected:
        missing = sorted(expected - actual)
        orphaned = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if orphaned:
            details.append(f"orphaned: {', '.join(orphaned)}")
        raise TellValidationError("Tell knowledge coverage mismatch (" + "; ".join(details) + ")")
    return records


def generate_tell_card(
    request: TellRequest,
    *,
    knowledge_path: Path = TELL_KNOWLEDGE_PATH,
) -> TellCard:
    observation = request.observation
    observation.validate()
    if request.game_id != request.goal.game:
        raise TellValidationError("goal and request game identities disagree")
    if observation.game_id != request.game_id:
        raise TellValidationError("observation and goal game identities disagree")
    if observation.source is None:
        raise TellValidationError("observation source is required")
    if observation.freshness is not Freshness.FRESH:
        raise TellValidationError("Tell requires a fresh current observation")
    if not observation.checkpoint_id:
        raise TellValidationError("Tell requires a stable checkpoint id")
    if observation.checkpoint_id not in request.goal.segments:
        raise TellValidationError("checkpoint is not part of the selected goal")
    if observation.confidence is None:
        raise TellValidationError("observation confidence is required")
    if observation.source is ObservationSource.ADAPTER and not observation.evidence_references:
        raise TellValidationError("adapter observations require an evidence reference")

    records = load_tell_knowledge(knowledge_path)
    record = records.get(observation.checkpoint_id)
    if record is None:
        raise TellValidationError("validated Tell knowledge is unavailable for this checkpoint")
    if record.game_id != request.game_id:
        raise TellValidationError("knowledge and observation game identities disagree")
    facts = {fact.fact_id: fact for fact in request.facts}
    if len(facts) != len(request.facts):
        raise TellValidationError("observed fact ids must be unique")
    for fact_id, expected in record.required_facts:
        fact = facts.get(fact_id)
        if fact is None:
            raise TellValidationError(f"missing required observed fact: {fact_id}")
        if fact.source is not observation.source:
            raise TellValidationError(f"fact source disagrees with observation: {fact_id}")
        if fact.value != expected:
            raise TellValidationError(f"observed fact contradicts checkpoint: {fact_id}")
    conflicts = sorted(set(record.protected_actions).intersection(request.protected_decisions))
    if conflicts:
        raise TellValidationError(
            "protected decision conflicts with every validated instruction path: "
            + ", ".join(conflicts)
        )

    catalog = load_segment_catalog(request.goal.catalog_path)
    validate_goal_segments(request.goal, catalog)
    segment = catalog.by_id[observation.checkpoint_id]
    refs = _references(request, segment, record)
    state_ref = refs[:1]
    goal_ref = tuple(reference for reference in refs if reference.source_class == "goal_contract")
    grounded_refs = tuple(reference for reference in refs if reference.source_class != "goal_contract")
    count = {SpoilerLevel.MINIMAL: 1, SpoilerLevel.GUIDED: 2, SpoilerLevel.FULL: len(record.actions)}[
        request.spoiler_level
    ]
    steps = tuple(
        TellStep(
            GroundedText(action, grounded_refs),
            GroundedText(record.cues[min(index, len(record.cues) - 1)], grounded_refs),
        )
        for index, action in enumerate(record.actions[:count])
    )
    include_support = request.spoiler_level is not SpoilerLevel.MINIMAL
    card = TellCard(
        state_summary=GroundedText(
            f"{observation.checkpoint} ({observation.source.value.replace('_', ' ')}; "
            f"confidence {observation.confidence:.0%}).",
            state_ref,
        ),
        observation_source=observation.source,
        objective=GroundedText(request.goal.user_directive, goal_ref),
        steps=steps,
        risks=tuple(GroundedText(item, grounded_refs) for item in record.risks)
        if include_support
        else (),
        recovery=tuple(GroundedText(item, grounded_refs) for item in record.recovery)
        if include_support
        else (),
        spoiler_level=request.spoiler_level,
        protected_decisions_honored=request.protected_decisions,
        uncertainty=GroundedText(
            "Companion has not verified any action after this starting observation.", state_ref
        ),
        refresh_requirement=GroundedText(
            "Refresh or reconfirm the checkpoint if the screen, inventory, or route state changes.",
            state_ref,
        ),
    )
    card.validate()
    return card


def _references(
    request: TellRequest,
    segment: RouteSegment,
    record: TellKnowledgeRecord,
) -> tuple[ProvenanceReference, ...]:
    observation_class = (
        "adapter_observation"
        if request.observation.source is ObservationSource.ADAPTER
        else "player_reported_fact"
    )
    references = [
        ProvenanceReference(observation_class, request.observation.checkpoint_id or "", "Current state"),
        ProvenanceReference("goal_contract", request.goal.id, request.goal.display_name),
        ProvenanceReference("segment_contract", segment.id, segment.name),
        ProvenanceReference("accepted_game_knowledge", record.segment_id, "Mario Tell catalog"),
    ]
    references.extend(
        ProvenanceReference("accepted_evidence", evidence, "Accepted segment evidence")
        for evidence in record.evidence_references
    )
    for reference in references:
        reference.validate()
    return tuple(references)


def _load_record(index: int, raw: Any) -> TellKnowledgeRecord:
    if not isinstance(raw, dict):
        raise TellValidationError(f"records[{index}] must be a mapping")
    required = {
        "game_id",
        "segment_id",
        "required_facts",
        "actions",
        "cues",
        "risks",
        "recovery",
        "protected_actions",
        "evidence_references",
    }
    missing = sorted(required.difference(raw))
    if missing:
        raise TellValidationError(f"records[{index}] missing: {', '.join(missing)}")
    required_facts = raw["required_facts"]
    if not isinstance(required_facts, dict) or not required_facts:
        raise TellValidationError(f"records[{index}].required_facts must be a mapping")
    list_fields = ("actions", "cues", "risks", "recovery", "protected_actions", "evidence_references")
    for field in list_fields:
        values = raw[field]
        if not isinstance(values, list) or (field in {"actions", "cues", "evidence_references"} and not values):
            raise TellValidationError(f"records[{index}].{field} must be a valid list")
        if not all(isinstance(value, str) and value for value in values):
            raise TellValidationError(f"records[{index}].{field} entries must be non-empty strings")
    if len(raw["cues"]) > len(raw["actions"]):
        raise TellValidationError(f"records[{index}] has more cues than actions")
    return TellKnowledgeRecord(
        game_id=str(raw["game_id"]),
        segment_id=str(raw["segment_id"]),
        required_facts=tuple((str(key), str(value)) for key, value in required_facts.items()),
        actions=tuple(raw["actions"]),
        cues=tuple(raw["cues"]),
        risks=tuple(raw["risks"]),
        recovery=tuple(raw["recovery"]),
        protected_actions=tuple(raw["protected_actions"]),
        evidence_references=tuple(raw["evidence_references"]),
    )
