from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from smb3_agent.run_library import LocalRunLibrary, RunRecord


LEARNING_SCHEMA_VERSION = "game-companion-learning/v1"
DERIVATION_VERSION = "game-companion-learning-derivation/v1"


class LearningError(ValueError):
    pass


class EvidenceClassification(str, Enum):
    RAW_OBSERVED_RUN = "raw_observed_run"
    FASTEST_LOCALLY_OBSERVED = "fastest_locally_observed_run"
    PLAYER_BEST = "player_best"
    AGENT_BEST = "agent_best"
    MIXED_COMPLETION = "mixed_actor_completion"
    DERIVED_PATTERN = "derived_pattern"
    CANDIDATE_TACTIC = "candidate_tactic"
    CANDIDATE_SOLUTION = "candidate_solution"
    OWNER_PREFERENCE = "owner_preference"
    APPROVED_FOR_VALIDATION = "approved_for_validation_candidate"
    REPLAY_VERIFIED = "replay_verified_candidate"
    ACCEPTED_EXECUTABLE = "accepted_executable_solution"
    REJECTED = "rejected_candidate"
    ROLLED_BACK = "rolled_back_solution"
    UNKNOWN = "unknown_or_insufficient_evidence"


class CandidateLifecycle(str, Enum):
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"
    APPROVED_FOR_VALIDATION = "approved_for_validation"
    VALIDATION_FAILED = "validation_failed"
    REPLAY_VERIFIED = "replay_verified"
    PROMOTION_READY = "promotion_ready"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    SUPERSEDED = "superseded"


LIFECYCLE_TRANSITIONS: dict[CandidateLifecycle, frozenset[CandidateLifecycle]] = {
    CandidateLifecycle.OBSERVED: frozenset({CandidateLifecycle.CANDIDATE}),
    CandidateLifecycle.CANDIDATE: frozenset({CandidateLifecycle.REVIEW_REQUIRED}),
    CandidateLifecycle.REVIEW_REQUIRED: frozenset(
        {
            CandidateLifecycle.REJECTED,
            CandidateLifecycle.APPROVED_FOR_VALIDATION,
            CandidateLifecycle.SUPERSEDED,
        }
    ),
    CandidateLifecycle.REJECTED: frozenset({CandidateLifecycle.SUPERSEDED}),
    CandidateLifecycle.APPROVED_FOR_VALIDATION: frozenset(
        {
            CandidateLifecycle.VALIDATION_FAILED,
            CandidateLifecycle.REPLAY_VERIFIED,
            CandidateLifecycle.SUPERSEDED,
        }
    ),
    CandidateLifecycle.VALIDATION_FAILED: frozenset(
        {CandidateLifecycle.APPROVED_FOR_VALIDATION, CandidateLifecycle.SUPERSEDED}
    ),
    CandidateLifecycle.REPLAY_VERIFIED: frozenset(
        {CandidateLifecycle.PROMOTION_READY, CandidateLifecycle.VALIDATION_FAILED}
    ),
    CandidateLifecycle.PROMOTION_READY: frozenset(
        {CandidateLifecycle.PROMOTED, CandidateLifecycle.VALIDATION_FAILED}
    ),
    CandidateLifecycle.PROMOTED: frozenset(
        {CandidateLifecycle.ROLLED_BACK, CandidateLifecycle.SUPERSEDED}
    ),
    CandidateLifecycle.ROLLED_BACK: frozenset({CandidateLifecycle.SUPERSEDED}),
    CandidateLifecycle.SUPERSEDED: frozenset(),
}


class HelpPolicy(str, Enum):
    QUIET = "quiet"
    ON_REQUEST = "on_request"
    PROACTIVE = "proactive"


@dataclass(frozen=True)
class ProgressAnchor:
    anchor_id: str
    state_boundary: str
    elapsed: int | None
    facts: dict[str, Any]
    observation_references: tuple[str, ...]


@dataclass(frozen=True)
class AttemptContract:
    run_id: str
    game_id: str
    adapter_id: str
    adapter_version: str
    level_id: str
    segment_id: str
    objective_id: str
    objective_version: int
    actor: str
    start_boundary: str
    terminal_boundary: str
    timing_units: str
    start_time: int
    terminal_time: int
    complete_timing_interval: bool
    emulator_assumptions: tuple[str, ...]
    allowed_techniques: tuple[str, ...]
    resource_policy: tuple[str, ...]
    required_observation_facts: tuple[str, ...]
    observed_facts: tuple[str, ...]
    evidence_integrity: bool
    completion: str
    deaths: int
    recoveries: int
    directional_corrections: int
    hesitation_intervals: int
    missed_requirements: tuple[str, ...]
    lost_resources: tuple[str, ...]
    anchors: tuple[ProgressAnchor, ...]
    tactic_tags: tuple[str, ...]
    input_trace_reference: str
    observation_evidence_reference: str
    created_at: str

    @property
    def elapsed(self) -> int:
        return self.terminal_time - self.start_time

    def validate(self) -> None:
        identity = (
            self.run_id,
            self.game_id,
            self.adapter_id,
            self.adapter_version,
            self.level_id,
            self.segment_id,
            self.objective_id,
            self.start_boundary,
            self.terminal_boundary,
            self.timing_units,
            self.input_trace_reference,
            self.observation_evidence_reference,
        )
        if not all(identity) or self.objective_version < 1:
            raise LearningError("attempt identity, contract, and evidence are required")
        if self.actor not in {"player", "agent", "mixed"}:
            raise LearningError("attempt actor must be player, agent, or mixed")
        if self.start_time < 0 or self.terminal_time < self.start_time:
            raise LearningError("attempt timing boundaries are invalid")
        if min(
            self.deaths,
            self.recoveries,
            self.directional_corrections,
            self.hesitation_intervals,
        ) < 0:
            raise LearningError("attempt counters cannot be negative")


@dataclass(frozen=True)
class CompatibilityDecision:
    left_run_id: str
    right_run_id: str
    compatible: bool
    matched_fields: tuple[str, ...]
    mismatches: tuple[str, ...]
    decided_at: str
    method_version: str = DERIVATION_VERSION


@dataclass(frozen=True)
class CompatibleAttemptSet:
    set_id: str
    game_id: str
    adapter_id: str
    level_id: str
    segment_id: str
    objective_id: str
    objective_version: int
    run_ids: tuple[str, ...]
    excluded_run_ids: tuple[str, ...]
    compatibility_decisions: tuple[CompatibilityDecision, ...]
    created_at: str


@dataclass(frozen=True)
class AttemptComparison:
    comparison_id: str
    left_run_id: str
    right_run_id: str
    compatible: bool
    timing_delta: int | None
    death_delta: int | None
    recovery_delta: int | None
    objective_deltas: tuple[str, ...]
    classification: EvidenceClassification
    evidence_references: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class DerivedEvidenceContext:
    game_id: str
    adapter_id: str
    adapter_version: str
    level_id: str
    segment_id: str
    objective_id: str
    objective_version: int
    source_run_ids: tuple[str, ...]
    source_actors: tuple[str, ...]
    state_boundaries: tuple[str, ...]
    timing_boundaries: tuple[str, ...]
    input_trace_references: tuple[str, ...]
    observation_evidence_references: tuple[str, ...]
    compatibility_set_id: str
    compatibility_decision: str
    derivation_method: str
    derivation_version: str
    confidence: float
    created_at: str
    review_state: str = "not_applicable"
    promotion_state: str = "not_applicable"
    supersession_history: tuple[str, ...] = ()
    rollback_history: tuple[str, ...] = ()


@dataclass(frozen=True)
class TroublePattern:
    pattern_id: str
    kind: str
    anchor_id: str | None
    summary: str
    supporting_run_ids: tuple[str, ...]
    counterexample_run_ids: tuple[str, ...]
    minimum_attempts: int
    confidence: float
    derivation_method: str
    created_at: str
    context: DerivedEvidenceContext


@dataclass(frozen=True)
class SuccessfulTactic:
    tactic_id: str
    tactic_tag: str
    state_boundary: str
    supporting_run_ids: tuple[str, ...]
    comparison_run_ids: tuple[str, ...]
    avoided_pattern_ids: tuple[str, ...]
    confidence: float
    derivation_method: str
    created_at: str
    context: DerivedEvidenceContext


@dataclass(frozen=True)
class ObjectiveDelta:
    delta_id: str
    objective_id: str
    left_run_id: str
    right_run_id: str
    requirement: str
    left_value: str
    right_value: str
    evidence_references: tuple[str, ...]
    context: DerivedEvidenceContext


@dataclass(frozen=True)
class CandidateTactic:
    tactic_id: str
    objective_id: str
    state_boundary: str
    preconditions: tuple[str, ...]
    action_sequence: tuple[str, ...]
    source_run_ids: tuple[str, ...]
    expected_benefit: str
    risks: tuple[str, ...]
    recovery_boundary: str
    confidence: float
    context: DerivedEvidenceContext


@dataclass(frozen=True)
class CandidateProvenance:
    source_run_ids: tuple[str, ...]
    source_actors: tuple[str, ...]
    input_trace_references: tuple[str, ...]
    observation_evidence_references: tuple[str, ...]
    derivation_method: str
    derivation_version: str
    compatibility_set_id: str
    created_at: str


@dataclass(frozen=True)
class ReplayValidationRequirement:
    requirement_id: str
    description: str
    compatible_start_boundary: str
    required_replays: int
    exact_diff_required: bool
    affected_reliability_profiles: tuple[str, ...]
    status: str = "pending"
    evidence_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateSolution:
    candidate_id: str
    content_hash: str
    game_id: str
    adapter_id: str
    level_id: str
    segment_id: str
    objective_id: str
    objective_version: int
    state_boundary: str
    preconditions: tuple[str, ...]
    action_sequence: tuple[str, ...]
    why_improvement: str
    expected_benefit: str
    risks: tuple[str, ...]
    protected_resources: tuple[str, ...]
    protected_decisions: tuple[str, ...]
    recovery_boundary: str
    unsupported_assumptions: tuple[str, ...]
    validation_requirements: tuple[ReplayValidationRequirement, ...]
    classification: str
    advisory_only: bool
    potentially_executable: bool
    provenance: CandidateProvenance
    context: DerivedEvidenceContext
    lifecycle: CandidateLifecycle
    created_at: str


@dataclass(frozen=True)
class ReviewDecision:
    candidate_id: str
    decision: str
    reason: str
    reviewer: str
    candidate_hash: str
    decided_at: str


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    candidate_hash: str
    exact_diff_reference: str
    route_patch_id: str
    replay_evidence_references: tuple[str, ...]
    affected_reliability_evidence: tuple[str, ...]
    previous_solution_id: str | None
    promoted_solution_id: str
    decided_at: str


@dataclass(frozen=True)
class Rejection:
    candidate_id: str
    candidate_hash: str
    reason: str
    rejected_by: str
    rejected_at: str


@dataclass(frozen=True)
class Rollback:
    candidate_id: str
    promoted_solution_id: str
    restored_solution_id: str | None
    reason: str
    rolled_back_by: str
    rolled_back_at: str


@dataclass(frozen=True)
class OwnerLocalPreference:
    game_id: str
    objective_id: str
    help_policy: HelpPolicy = HelpPolicy.ON_REQUEST
    preferred_solution_style: str = "balanced"
    risk_tolerance: str = "moderate"
    resource_preservation: tuple[str, ...] = ()
    spoiler_level: str = "guided"
    repeated_trouble_anchors: tuple[str, ...] = ()
    dismissed_suggestion_types: tuple[str, ...] = ()
    confirmed_helpful_suggestion_types: tuple[str, ...] = ()
    preferred_comparison_target: str = "player_best"
    explicit_current_session_choices: tuple[str, ...] = ()
    updated_at: str = ""

    def validate(self) -> None:
        if not self.game_id or not self.objective_id:
            raise LearningError("preference game and objective scope are required")
        if self.risk_tolerance not in {"cautious", "moderate", "aggressive"}:
            raise LearningError("unsupported risk tolerance")
        if self.spoiler_level not in {"minimal", "guided", "full"}:
            raise LearningError("unsupported spoiler level")


@dataclass(frozen=True)
class PersonalizedAssistanceRule:
    rule_id: str
    game_id: str
    objective_id: str
    trigger: str
    action: str
    preference_fields: tuple[str, ...]
    evidence_references: tuple[str, ...]
    classification: EvidenceClassification
    confidence: float
    enabled: bool


@dataclass(frozen=True)
class LearningArtifactManifest:
    manifest_id: str
    schema_version: str
    game_id: str
    adapter_id: str
    level_id: str
    segment_id: str
    objective_id: str
    objective_version: int
    source_run_ids: tuple[str, ...]
    artifact_references: tuple[str, ...]
    content_hashes: dict[str, str]
    created_at: str


@dataclass(frozen=True)
class LearningSession:
    session_id: str
    game_id: str
    adapter_id: str
    objective_id: str
    objective_version: int
    source_run_ids: tuple[str, ...]
    compatible_set_ids: tuple[str, ...]
    derived_pattern_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class LearningAdvice:
    text: str
    classification: EvidenceClassification
    evidence_references: tuple[str, ...]
    confidence: float
    candidate_id: str | None = None


@dataclass(frozen=True)
class LearningSnapshot:
    attempts: tuple[AttemptContract, ...]
    patterns: tuple[TroublePattern, ...]
    tactics: tuple[SuccessfulTactic, ...]
    candidates: tuple[CandidateSolution, ...]
    reviews: tuple[ReviewDecision, ...]
    rejections: tuple[Rejection, ...]
    promotions: tuple[PromotionDecision, ...]
    rollbacks: tuple[Rollback, ...]
    preferences: tuple[OwnerLocalPreference, ...]


class LocalLearningStore:
    """Append-safe local learning history with rebuildable atomic indexes."""

    def __init__(self, root: Path = Path("artifacts/learning")) -> None:
        self.root = root
        self.events_path = root / "events.jsonl"
        self.index_path = root / "index.json"
        self.accepted_solutions_path = root / "accepted-solutions.json"
        self.review_packets_path = root / "review-packets"
        self.manifests_path = root / "manifests"

    def snapshot(self) -> LearningSnapshot:
        state: dict[str, dict[str, Any]] = {
            name: {}
            for name in (
                "attempts",
                "patterns",
                "tactics",
                "candidates",
                "reviews",
                "rejections",
                "promotions",
                "rollbacks",
                "preferences",
            )
        }
        for event in self._events():
            kind = event["kind"]
            payload = event["payload"]
            if kind == "candidate_transition":
                candidate = state["candidates"].get(payload["candidate_id"])
                if candidate is None:
                    raise LearningError("candidate transition precedes candidate creation")
                candidate["lifecycle"] = payload["to"]
                continue
            collection = {
                "attempt": "attempts",
                "pattern": "patterns",
                "tactic": "tactics",
                "candidate": "candidates",
                "review": "reviews",
                "rejection": "rejections",
                "promotion": "promotions",
                "rollback": "rollbacks",
                "preference": "preferences",
            }.get(kind)
            if collection is not None:
                state[collection][event["record_id"]] = payload
        return LearningSnapshot(
            attempts=tuple(self._attempt(item) for item in state["attempts"].values()),
            patterns=tuple(self._pattern(item) for item in state["patterns"].values()),
            tactics=tuple(self._tactic(item) for item in state["tactics"].values()),
            candidates=tuple(self._candidate(item) for item in state["candidates"].values()),
            reviews=tuple(ReviewDecision(**item) for item in state["reviews"].values()),
            rejections=tuple(Rejection(**item) for item in state["rejections"].values()),
            promotions=tuple(self._promotion(item) for item in state["promotions"].values()),
            rollbacks=tuple(Rollback(**item) for item in state["rollbacks"].values()),
            preferences=tuple(self._preference(item) for item in state["preferences"].values()),
        )

    def record_attempt(self, attempt: AttemptContract) -> bool:
        attempt.validate()
        snapshot = self.snapshot()
        if any(item.run_id == attempt.run_id for item in snapshot.attempts):
            return False
        self._append("attempt", attempt.run_id, asdict(attempt))
        return True

    def save_pattern(self, pattern: TroublePattern) -> bool:
        if len(pattern.supporting_run_ids) < pattern.minimum_attempts or pattern.minimum_attempts < 2:
            raise LearningError("a repeated pattern requires its configured compatible-attempt threshold")
        if pattern.context.compatibility_decision != "compatible":
            raise LearningError("patterns require a compatible evidence context")
        return self._append_unique("pattern", pattern.pattern_id, asdict(pattern))

    def save_tactic(self, tactic: SuccessfulTactic) -> bool:
        if not tactic.supporting_run_ids:
            raise LearningError("successful tactics require supporting attempts")
        if tactic.context.compatibility_decision != "compatible":
            raise LearningError("tactics require a compatible evidence context")
        return self._append_unique("tactic", tactic.tactic_id, asdict(tactic))

    def create_candidate(self, candidate: CandidateSolution) -> bool:
        if candidate.lifecycle is not CandidateLifecycle.OBSERVED:
            raise LearningError("new candidates begin as observed")
        if candidate.content_hash != candidate_content_hash(candidate):
            raise LearningError("candidate content hash does not match its reviewable content")
        if not candidate.provenance.source_run_ids or not candidate.validation_requirements:
            raise LearningError("candidate provenance and replay requirements are required")
        if candidate.advisory_only and candidate.potentially_executable:
            raise LearningError("advisory-only candidates cannot claim executable potential")
        created = self._append_unique("candidate", candidate.candidate_id, self._candidate_payload(candidate))
        if created:
            self.transition(candidate.candidate_id, CandidateLifecycle.CANDIDATE, "derivation")
            self.transition(candidate.candidate_id, CandidateLifecycle.REVIEW_REQUIRED, "derivation")
        return created

    def review(self, candidate_id: str, *, approve: bool, reason: str, reviewer: str) -> ReviewDecision:
        candidate = self._candidate_by_id(candidate_id)
        if candidate.lifecycle is not CandidateLifecycle.REVIEW_REQUIRED:
            raise LearningError("only review-required candidates can receive an owner decision")
        if not reason.strip() or not reviewer.strip():
            raise LearningError("review reason and reviewer are required")
        decision = ReviewDecision(
            candidate_id,
            "approve_for_validation" if approve else "reject",
            reason.strip(),
            reviewer.strip(),
            candidate.content_hash,
            utc_now(),
        )
        self._append("review", stable_id("review", asdict(decision)), asdict(decision))
        if approve:
            self.transition(candidate_id, CandidateLifecycle.APPROVED_FOR_VALIDATION, reviewer)
        else:
            rejection = Rejection(
                candidate_id,
                candidate.content_hash,
                reason.strip(),
                reviewer.strip(),
                decision.decided_at,
            )
            self._append("rejection", stable_id("rejection", asdict(rejection)), asdict(rejection))
            self.transition(candidate_id, CandidateLifecycle.REJECTED, reviewer)
        return decision

    def record_replay_validation(
        self,
        candidate_id: str,
        *,
        passed: bool,
        evidence_references: tuple[str, ...],
        actor: str,
    ) -> None:
        candidate = self._candidate_by_id(candidate_id)
        if candidate.lifecycle is not CandidateLifecycle.APPROVED_FOR_VALIDATION:
            raise LearningError("replay validation requires prior review approval")
        if passed and not evidence_references:
            raise LearningError("replay verification requires compatible replay evidence")
        target = CandidateLifecycle.REPLAY_VERIFIED if passed else CandidateLifecycle.VALIDATION_FAILED
        self.transition(candidate_id, target, actor, evidence_references=evidence_references)

    def mark_promotion_ready(
        self,
        candidate_id: str,
        *,
        route_patch_id: str,
        exact_diff_reference: str,
        reliability_evidence: tuple[str, ...],
        actor: str,
    ) -> None:
        candidate = self._candidate_by_id(candidate_id)
        if candidate.lifecycle is not CandidateLifecycle.REPLAY_VERIFIED:
            raise LearningError("promotion readiness requires replay verification")
        if not route_patch_id or not exact_diff_reference or not reliability_evidence:
            raise LearningError("route-patch exact diff and affected reliability evidence are required")
        self.transition(
            candidate_id,
            CandidateLifecycle.PROMOTION_READY,
            actor,
            evidence_references=(route_patch_id, exact_diff_reference, *reliability_evidence),
        )

    def promote(self, decision: PromotionDecision, *, actor: str) -> None:
        candidate = self._candidate_by_id(decision.candidate_id)
        if candidate.lifecycle is not CandidateLifecycle.PROMOTION_READY:
            raise LearningError("candidate is not promotion-ready")
        if candidate.content_hash != decision.candidate_hash:
            raise LearningError("promotion candidate hash is stale")
        if not (
            decision.exact_diff_reference
            and decision.route_patch_id
            and decision.replay_evidence_references
            and decision.affected_reliability_evidence
            and decision.promoted_solution_id
        ):
            raise LearningError("promotion requires exact diff, replay, reliability, and solution evidence")
        self._append("promotion", decision.promoted_solution_id, asdict(decision))
        registry = self._accepted_solutions()
        objective_key = f"{candidate.game_id}:{candidate.objective_id}@{candidate.objective_version}"
        registry[objective_key] = {
            "solution_id": decision.promoted_solution_id,
            "candidate_id": decision.candidate_id,
            "candidate_hash": decision.candidate_hash,
            "route_patch_id": decision.route_patch_id,
            "previous_solution_id": decision.previous_solution_id,
        }
        self._atomic_json(self.accepted_solutions_path, {
            "schema_version": "game-companion-accepted-solutions/v1",
            "solutions": registry,
        })
        self.transition(decision.candidate_id, CandidateLifecycle.PROMOTED, actor)

    def rollback(self, candidate_id: str, *, reason: str, actor: str) -> Rollback:
        candidate = self._candidate_by_id(candidate_id)
        if candidate.lifecycle is not CandidateLifecycle.PROMOTED:
            raise LearningError("only promoted candidates can be rolled back")
        promotion = next(
            (item for item in reversed(self.snapshot().promotions) if item.candidate_id == candidate_id),
            None,
        )
        if promotion is None or not reason.strip():
            raise LearningError("rollback requires promotion history and a reason")
        rollback = Rollback(
            candidate_id,
            promotion.promoted_solution_id,
            promotion.previous_solution_id,
            reason.strip(),
            actor,
            utc_now(),
        )
        registry = self._accepted_solutions()
        objective_key = f"{candidate.game_id}:{candidate.objective_id}@{candidate.objective_version}"
        if promotion.previous_solution_id is None:
            registry.pop(objective_key, None)
        else:
            registry[objective_key] = {
                "solution_id": promotion.previous_solution_id,
                "restored_from": promotion.promoted_solution_id,
                "route_patch_id": promotion.route_patch_id,
            }
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_json(self.accepted_solutions_path, {
            "schema_version": "game-companion-accepted-solutions/v1",
            "solutions": registry,
        })
        self._append("rollback", stable_id("rollback", asdict(rollback)), asdict(rollback))
        self.transition(candidate_id, CandidateLifecycle.ROLLED_BACK, actor)
        return rollback

    def supersede(self, candidate_id: str, *, replacement_id: str, actor: str) -> None:
        if not replacement_id or replacement_id == candidate_id:
            raise LearningError("supersession requires a distinct replacement candidate")
        self._candidate_by_id(replacement_id)
        self.transition(candidate_id, CandidateLifecycle.SUPERSEDED, actor, superseded_by=replacement_id)

    def revise_candidate(
        self,
        candidate_id: str,
        revision: CandidateSolution,
        *,
        reason: str,
        actor: str,
    ) -> None:
        original = self._candidate_by_id(candidate_id)
        if original.lifecycle not in {
            CandidateLifecycle.REVIEW_REQUIRED,
            CandidateLifecycle.APPROVED_FOR_VALIDATION,
            CandidateLifecycle.VALIDATION_FAILED,
        }:
            raise LearningError("candidate cannot be revised from its current lifecycle state")
        if not reason.strip() or revision.candidate_id == candidate_id:
            raise LearningError("revision requires a reason and a new stable candidate id")
        if revision.provenance.source_run_ids != original.provenance.source_run_ids:
            raise LearningError("revision cannot silently replace source evidence")
        self.create_candidate(revision)
        self.transition(
            candidate_id,
            CandidateLifecycle.SUPERSEDED,
            actor,
            superseded_by=revision.candidate_id,
            revision_reason=reason.strip(),
        )

    def set_preference(self, preference: OwnerLocalPreference) -> None:
        preference.validate()
        key = f"{preference.game_id}:{preference.objective_id}"
        payload = asdict(preference)
        payload["help_policy"] = preference.help_policy.value
        self._append("preference", key, payload)

    def reset_preference(self, game_id: str, objective_id: str) -> OwnerLocalPreference:
        preference = OwnerLocalPreference(game_id, objective_id, updated_at=utc_now())
        self.set_preference(preference)
        return preference

    def export_review_packet(self, candidate_id: str) -> Path:
        candidate = self._candidate_by_id(candidate_id)
        payload = {
            "schema_version": "game-companion-learning-review-packet/v1",
            "candidate": self._candidate_payload(candidate),
            "candidate_content_hash": candidate.content_hash,
            "route_patch_workflow": {
                "mechanism": "beat-mario.route-patch/v1",
                "automatic_import": False,
                "requirements": [
                    "review decision",
                    "compatible replay validation",
                    "exact proposed diff",
                    "affected reliability gates",
                    "explicit promotion decision",
                ],
            },
            "exported_at": utc_now(),
        }
        self.review_packets_path.mkdir(parents=True, exist_ok=True)
        path = self.review_packets_path / f"{candidate.candidate_id}.json"
        self._atomic_json(path, payload)
        return path

    def write_manifest(
        self,
        session: LearningSession,
        attempt: AttemptContract,
        *,
        artifact_references: tuple[str, ...],
    ) -> LearningArtifactManifest:
        hashes = {
            reference: stable_hash(reference)
            for reference in artifact_references
        }
        payload = {
            "session_id": session.session_id,
            "runs": session.source_run_ids,
            "artifacts": artifact_references,
            "hashes": hashes,
        }
        manifest = LearningArtifactManifest(
            stable_id("learning-manifest", payload),
            "game-companion-learning-manifest/v1",
            attempt.game_id,
            attempt.adapter_id,
            attempt.level_id,
            attempt.segment_id,
            attempt.objective_id,
            attempt.objective_version,
            session.source_run_ids,
            artifact_references,
            hashes,
            utc_now(),
        )
        self.manifests_path.mkdir(parents=True, exist_ok=True)
        self._atomic_json(
            self.manifests_path / f"{manifest.manifest_id}.json",
            asdict(manifest),
        )
        return manifest

    def recover_index(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        index = {
            "schema_version": "game-companion-learning-index/v1",
            "run_ids": [item.run_id for item in snapshot.attempts],
            "candidate_states": {item.candidate_id: item.lifecycle.value for item in snapshot.candidates},
            "preference_scopes": [f"{item.game_id}:{item.objective_id}" for item in snapshot.preferences],
            "event_log_sha256": sha256_file(self.events_path) if self.events_path.is_file() else None,
            "rebuilt_at": utc_now(),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_json(self.index_path, index)
        return index

    def transition(
        self,
        candidate_id: str,
        target: CandidateLifecycle,
        actor: str,
        **details: Any,
    ) -> None:
        current = self._candidate_by_id(candidate_id).lifecycle
        if target not in LIFECYCLE_TRANSITIONS[current]:
            raise LearningError(f"invalid candidate transition: {current.value} -> {target.value}")
        payload = {
            "candidate_id": candidate_id,
            "from": current.value,
            "to": target.value,
            "actor": actor,
            "at": utc_now(),
            **details,
        }
        self._append("candidate_transition", stable_id("transition", payload), payload)

    def _candidate_by_id(self, candidate_id: str) -> CandidateSolution:
        candidate = next(
            (item for item in self.snapshot().candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise LearningError(f"unknown learning candidate: {candidate_id}")
        return candidate

    def _accepted_solutions(self) -> dict[str, Any]:
        if not self.accepted_solutions_path.is_file():
            return {}
        payload = json.loads(self.accepted_solutions_path.read_text(encoding="utf-8"))
        schema = payload.get("schema_version")
        if schema != "game-companion-accepted-solutions/v1":
            raise LearningError(f"unsupported accepted-solution schema: {schema}")
        solutions = payload.get("solutions")
        if not isinstance(solutions, dict):
            raise LearningError("accepted-solution registry is corrupt")
        return solutions

    def _append_unique(self, kind: str, record_id: str, payload: dict[str, Any]) -> bool:
        if any(event["kind"] == kind and event["record_id"] == record_id for event in self._events()):
            return False
        self._append(kind, record_id, payload)
        return True

    def _append(self, kind: str, record_id: str, payload: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "schema_version": LEARNING_SCHEMA_VERSION,
            "kind": kind,
            "record_id": record_id,
            "payload": payload,
        }
        event["content_sha256"] = stable_hash(event)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=_json_default) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.recover_index()

    def _events(self) -> list[dict[str, Any]]:
        if not self.events_path.is_file():
            return []
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.events_path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LearningError(f"corrupt learning event at line {line_number}") from exc
            schema = event.get("schema_version")
            if schema != LEARNING_SCHEMA_VERSION:
                raise LearningError(f"unsupported learning event schema: {schema}")
            expected = event.get("content_sha256")
            unsigned = {key: value for key, value in event.items() if key != "content_sha256"}
            if expected != stable_hash(unsigned):
                raise LearningError(f"learning event checksum mismatch at line {line_number}")
            events.append(event)
        return events

    @staticmethod
    def _attempt(payload: dict[str, Any]) -> AttemptContract:
        item = dict(payload)
        item["anchors"] = tuple(ProgressAnchor(**anchor) for anchor in item["anchors"])
        for key in (
            "emulator_assumptions",
            "allowed_techniques",
            "resource_policy",
            "required_observation_facts",
            "observed_facts",
            "missed_requirements",
            "lost_resources",
            "tactic_tags",
        ):
            item[key] = tuple(item[key])
        return AttemptContract(**item)

    @staticmethod
    def _candidate(payload: dict[str, Any]) -> CandidateSolution:
        item = dict(payload)
        item["lifecycle"] = CandidateLifecycle(item["lifecycle"])
        item["provenance"] = CandidateProvenance(**item["provenance"])
        item["context"] = DerivedEvidenceContext(**item["context"])
        item["validation_requirements"] = tuple(
            ReplayValidationRequirement(**requirement)
            for requirement in item["validation_requirements"]
        )
        for key in (
            "preconditions",
            "action_sequence",
            "risks",
            "protected_resources",
            "protected_decisions",
            "unsupported_assumptions",
        ):
            item[key] = tuple(item[key])
        return CandidateSolution(**item)

    @staticmethod
    def _pattern(payload: dict[str, Any]) -> TroublePattern:
        item = dict(payload)
        item["context"] = DerivedEvidenceContext(**item["context"])
        for key in ("supporting_run_ids", "counterexample_run_ids"):
            item[key] = tuple(item[key])
        return TroublePattern(**item)

    @staticmethod
    def _tactic(payload: dict[str, Any]) -> SuccessfulTactic:
        item = dict(payload)
        item["context"] = DerivedEvidenceContext(**item["context"])
        for key in (
            "supporting_run_ids",
            "comparison_run_ids",
            "avoided_pattern_ids",
        ):
            item[key] = tuple(item[key])
        return SuccessfulTactic(**item)

    @staticmethod
    def _candidate_payload(candidate: CandidateSolution) -> dict[str, Any]:
        payload = asdict(candidate)
        payload["lifecycle"] = candidate.lifecycle.value
        return payload

    @staticmethod
    def _promotion(payload: dict[str, Any]) -> PromotionDecision:
        item = dict(payload)
        item["replay_evidence_references"] = tuple(item["replay_evidence_references"])
        item["affected_reliability_evidence"] = tuple(item["affected_reliability_evidence"])
        return PromotionDecision(**item)

    @staticmethod
    def _preference(payload: dict[str, Any]) -> OwnerLocalPreference:
        item = dict(payload)
        item["help_policy"] = HelpPolicy(item["help_policy"])
        for key in (
            "resource_preservation",
            "repeated_trouble_anchors",
            "dismissed_suggestion_types",
            "confirmed_helpful_suggestion_types",
            "explicit_current_session_choices",
        ):
            item[key] = tuple(item[key])
        return OwnerLocalPreference(**item)

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True, default=_json_default)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def compatibility(left: AttemptContract, right: AttemptContract) -> CompatibilityDecision:
    fields = {
        "game_id": (left.game_id, right.game_id),
        "adapter_id": (left.adapter_id, right.adapter_id),
        "adapter_version": (left.adapter_version, right.adapter_version),
        "level_id": (left.level_id, right.level_id),
        "segment_id": (left.segment_id, right.segment_id),
        "objective_id": (left.objective_id, right.objective_id),
        "objective_version": (left.objective_version, right.objective_version),
        "start_boundary": (left.start_boundary, right.start_boundary),
        "terminal_boundary": (left.terminal_boundary, right.terminal_boundary),
        "timing_units": (left.timing_units, right.timing_units),
        "emulator_assumptions": (left.emulator_assumptions, right.emulator_assumptions),
        "allowed_techniques": (left.allowed_techniques, right.allowed_techniques),
        "resource_policy": (left.resource_policy, right.resource_policy),
        "required_observation_facts": (
            left.required_observation_facts,
            right.required_observation_facts,
        ),
    }
    matched = tuple(name for name, values in fields.items() if values[0] == values[1])
    mismatches = [name for name, values in fields.items() if values[0] != values[1]]
    if not left.complete_timing_interval or not right.complete_timing_interval:
        mismatches.append("complete_timing_interval")
    if not left.evidence_integrity or not right.evidence_integrity:
        mismatches.append("evidence_integrity")
    if not set(left.required_observation_facts).issubset(left.observed_facts) or not set(
        right.required_observation_facts
    ).issubset(right.observed_facts):
        mismatches.append("required_observation_coverage")
    return CompatibilityDecision(
        left.run_id,
        right.run_id,
        not mismatches,
        matched,
        tuple(dict.fromkeys(mismatches)),
        utc_now(),
    )


def build_compatible_set(attempts: Iterable[AttemptContract]) -> CompatibleAttemptSet:
    selected = tuple(attempts)
    if not selected:
        raise LearningError("compatible attempt set requires at least one attempt")
    reference = selected[0]
    decisions = tuple(compatibility(reference, attempt) for attempt in selected[1:])
    included = (reference.run_id,) + tuple(
        decision.right_run_id for decision in decisions if decision.compatible
    )
    excluded = tuple(decision.right_run_id for decision in decisions if not decision.compatible)
    set_payload = {
        "reference": reference.run_id,
        "included": included,
        "objective": f"{reference.objective_id}@{reference.objective_version}",
    }
    return CompatibleAttemptSet(
        stable_id("compatible-set", set_payload),
        reference.game_id,
        reference.adapter_id,
        reference.level_id,
        reference.segment_id,
        reference.objective_id,
        reference.objective_version,
        included,
        excluded,
        decisions,
        utc_now(),
    )


def compare_attempts(left: AttemptContract, right: AttemptContract) -> AttemptComparison:
    decision = compatibility(left, right)
    objective_deltas = tuple(
        f"{requirement}: {requirement in left.missed_requirements} -> {requirement in right.missed_requirements}"
        for requirement in sorted(set(left.missed_requirements) | set(right.missed_requirements))
    )
    return AttemptComparison(
        stable_id("comparison", {"left": left.run_id, "right": right.run_id}),
        left.run_id,
        right.run_id,
        decision.compatible,
        right.elapsed - left.elapsed if decision.compatible else None,
        right.deaths - left.deaths if decision.compatible else None,
        right.recoveries - left.recoveries if decision.compatible else None,
        objective_deltas if decision.compatible else (),
        EvidenceClassification.RAW_OBSERVED_RUN,
        (left.observation_evidence_reference, right.observation_evidence_reference),
        utc_now(),
    )


def derive_trouble_patterns(
    attempt_set: CompatibleAttemptSet,
    attempts: Iterable[AttemptContract],
    *,
    minimum_attempts: int = 3,
) -> tuple[TroublePattern, ...]:
    if minimum_attempts < 2:
        raise LearningError("repeated-pattern threshold must be at least two")
    by_id = {attempt.run_id: attempt for attempt in attempts}
    compatible_attempts = [by_id[run_id] for run_id in attempt_set.run_ids if run_id in by_id]
    context = derived_evidence_context(attempt_set, compatible_attempts, confidence=0.0)
    failures: dict[tuple[str, str], list[str]] = {}
    counterexamples: dict[tuple[str, str], list[str]] = {}
    completed = [item for item in compatible_attempts if item.completion == "completed"]
    fastest_elapsed = min((item.elapsed for item in completed), default=None)
    for attempt in compatible_attempts:
        failed_anchor_ids = {
            anchor.anchor_id
            for anchor in attempt.anchors
            if anchor.facts.get("death") or anchor.facts.get("failed_recovery")
        }
        for anchor in attempt.anchors:
            key = ("repeated_death_or_failed_recovery", anchor.anchor_id)
            target = failures if anchor.anchor_id in failed_anchor_ids else counterexamples
            target.setdefault(key, []).append(attempt.run_id)
        for resource in attempt.lost_resources:
            failures.setdefault(("repeated_resource_loss", resource), []).append(attempt.run_id)
        for requirement in attempt.missed_requirements:
            failures.setdefault(("repeated_missed_requirement", requirement), []).append(attempt.run_id)
        if attempt.directional_corrections >= 6:
            failures.setdefault(("excessive_directional_correction", "whole_attempt"), []).append(attempt.run_id)
        if attempt.hesitation_intervals >= 3:
            failures.setdefault(("repeated_hesitation", "whole_attempt"), []).append(attempt.run_id)
        if fastest_elapsed is not None and attempt.elapsed > fastest_elapsed * 1.2:
            failures.setdefault(("consistent_slowdown", "terminal_boundary"), []).append(attempt.run_id)
    for key, run_ids in failures.items():
        supporting = set(run_ids)
        counterexamples[key] = [
            item.run_id for item in compatible_attempts if item.run_id not in supporting
        ]
    patterns: list[TroublePattern] = []
    for (kind, anchor), run_ids in sorted(failures.items()):
        unique = tuple(dict.fromkeys(run_ids))
        if len(unique) < minimum_attempts:
            continue
        counter = tuple(dict.fromkeys(counterexamples.get((kind, anchor), [])))
        confidence = min(0.99, len(unique) / max(len(compatible_attempts), 1))
        payload = {"kind": kind, "anchor": anchor, "runs": unique, "set": attempt_set.set_id}
        patterns.append(
            TroublePattern(
                stable_id("pattern", payload),
                kind,
                anchor,
                f"{kind.replace('_', ' ').title()} at {anchor}",
                unique,
                counter,
                minimum_attempts,
                confidence,
                DERIVATION_VERSION,
                utc_now(),
                DerivedEvidenceContext(
                    **{
                        **asdict(context),
                        "confidence": confidence,
                    }
                ),
            )
        )
    return tuple(patterns)


def derive_successful_tactics(
    attempt_set: CompatibleAttemptSet,
    attempts: Iterable[AttemptContract],
    patterns: Iterable[TroublePattern],
) -> tuple[SuccessfulTactic, ...]:
    by_id = {attempt.run_id: attempt for attempt in attempts}
    compatible_attempts = [by_id[run_id] for run_id in attempt_set.run_ids if run_id in by_id]
    tags: dict[str, list[AttemptContract]] = {}
    for attempt in compatible_attempts:
        if attempt.completion != "completed":
            continue
        for tag in attempt.tactic_tags:
            tags.setdefault(tag, []).append(attempt)
    results: list[SuccessfulTactic] = []
    pattern_list = tuple(patterns)
    for tag, supporting in sorted(tags.items()):
        comparison = [item for item in compatible_attempts if tag not in item.tactic_tags]
        if not comparison:
            continue
        supporting_score = min(
            (item.deaths, item.elapsed, item.directional_corrections)
            for item in supporting
        )
        comparison_score = min(
            (item.deaths, item.elapsed, item.directional_corrections)
            for item in comparison
        )
        if supporting_score >= comparison_score:
            continue
        supporting_ids = tuple(item.run_id for item in supporting)
        avoided = tuple(
            pattern.pattern_id
            for pattern in pattern_list
            if not set(pattern.supporting_run_ids).intersection(supporting_ids)
        )
        payload = {"tag": tag, "support": supporting_ids, "set": attempt_set.set_id}
        results.append(
            SuccessfulTactic(
                stable_id("tactic", payload),
                tag,
                supporting[0].start_boundary,
                supporting_ids,
                tuple(item.run_id for item in comparison),
                avoided,
                min(0.95, 0.5 + 0.1 * len(supporting)),
                DERIVATION_VERSION,
                utc_now(),
                derived_evidence_context(
                    attempt_set,
                    compatible_attempts,
                    confidence=min(0.95, 0.5 + 0.1 * len(supporting)),
                ),
            )
        )
    return tuple(results)


def derived_evidence_context(
    attempt_set: CompatibleAttemptSet,
    attempts: Iterable[AttemptContract],
    *,
    confidence: float,
) -> DerivedEvidenceContext:
    sources = tuple(attempts)
    if not sources:
        raise LearningError("derived evidence context requires source attempts")
    first = sources[0]
    return DerivedEvidenceContext(
        first.game_id,
        first.adapter_id,
        first.adapter_version,
        first.level_id,
        first.segment_id,
        first.objective_id,
        first.objective_version,
        tuple(item.run_id for item in sources),
        tuple(item.actor for item in sources),
        tuple(f"{item.start_boundary}->{item.terminal_boundary}" for item in sources),
        tuple(f"{item.start_time}->{item.terminal_time} {item.timing_units}" for item in sources),
        tuple(item.input_trace_reference for item in sources),
        tuple(item.observation_evidence_reference for item in sources),
        attempt_set.set_id,
        "compatible",
        "compatible_attempt_derivation",
        DERIVATION_VERSION,
        confidence,
        utc_now(),
    )


def derive_objective_deltas(
    left: AttemptContract,
    right: AttemptContract,
) -> tuple[ObjectiveDelta, ...]:
    decision = compatibility(left, right)
    if not decision.compatible:
        return ()
    attempt_set = build_compatible_set((left, right))
    context = derived_evidence_context(attempt_set, (left, right), confidence=1.0)
    deltas: list[ObjectiveDelta] = []
    values = {
        "elapsed": (left.elapsed, right.elapsed),
        "deaths": (left.deaths, right.deaths),
        "recoveries": (left.recoveries, right.recoveries),
        "directional_corrections": (
            left.directional_corrections,
            right.directional_corrections,
        ),
        "hesitation_intervals": (left.hesitation_intervals, right.hesitation_intervals),
    }
    for requirement, (left_value, right_value) in values.items():
        if left_value == right_value:
            continue
        payload = {
            "left": left.run_id,
            "right": right.run_id,
            "requirement": requirement,
        }
        deltas.append(
            ObjectiveDelta(
                stable_id("objective-delta", payload),
                left.objective_id,
                left.run_id,
                right.run_id,
                requirement,
                str(left_value),
                str(right_value),
                (left.observation_evidence_reference, right.observation_evidence_reference),
                context,
            )
        )
    return tuple(deltas)


def derive_candidate(
    attempt_set: CompatibleAttemptSet,
    tactic: SuccessfulTactic,
    attempts: Iterable[AttemptContract],
    *,
    action_sequence: tuple[str, ...],
    protected_resources: tuple[str, ...] = (),
    protected_decisions: tuple[str, ...] = (),
) -> CandidateSolution:
    by_id = {attempt.run_id: attempt for attempt in attempts}
    sources = tuple(by_id[run_id] for run_id in tactic.supporting_run_ids if run_id in by_id)
    if not sources or not action_sequence:
        raise LearningError("candidate derivation requires compatible sources and an action sequence")
    source = sources[0]
    provenance = CandidateProvenance(
        tuple(item.run_id for item in sources),
        tuple(item.actor for item in sources),
        tuple(item.input_trace_reference for item in sources),
        tuple(item.observation_evidence_reference for item in sources),
        "successful_compatible_tactic",
        DERIVATION_VERSION,
        attempt_set.set_id,
        utc_now(),
    )
    requirements = (
        ReplayValidationRequirement(
            stable_id("validation", {"set": attempt_set.set_id, "tactic": tactic.tactic_id}),
            "Replay from the exact compatible start and satisfy the objective contract.",
            tactic.state_boundary,
            3,
            True,
            (source.objective_id,),
        ),
    )
    draft = CandidateSolution(
        candidate_id=stable_id("candidate", {"set": attempt_set.set_id, "tactic": tactic.tactic_id}),
        content_hash="",
        game_id=source.game_id,
        adapter_id=source.adapter_id,
        level_id=source.level_id,
        segment_id=source.segment_id,
        objective_id=source.objective_id,
        objective_version=source.objective_version,
        state_boundary=tactic.state_boundary,
        preconditions=("exact compatible start boundary", "required observation facts present"),
        action_sequence=action_sequence,
        why_improvement=f"The {tactic.tactic_tag} tactic succeeded in compatible observed attempts.",
        expected_benefit="Candidate improvement; fastest observed is not treated as best strategy.",
        risks=("Observed input may not be replay-safe.",),
        protected_resources=protected_resources,
        protected_decisions=protected_decisions,
        recovery_boundary=source.terminal_boundary,
        unsupported_assumptions=("Replay stability is not yet proven.",),
        validation_requirements=requirements,
        classification="candidate_solution",
        advisory_only=False,
        potentially_executable=True,
        provenance=provenance,
        context=derived_evidence_context(
            attempt_set,
            sources,
            confidence=tactic.confidence,
        ),
        lifecycle=CandidateLifecycle.OBSERVED,
        created_at=utc_now(),
    )
    return CandidateSolution(**{**asdict(draft), "content_hash": candidate_content_hash(draft), "provenance": provenance, "context": draft.context, "validation_requirements": requirements, "lifecycle": CandidateLifecycle.OBSERVED})


def process_attempt(
    store: LocalLearningStore,
    attempt: AttemptContract,
    *,
    minimum_repeated_attempts: int = 3,
) -> LearningSession:
    """Idempotently retain raw evidence and rebuild only compatible derived learning."""
    store.record_attempt(attempt)
    snapshot = store.snapshot()
    same_contract = tuple(
        item
        for item in snapshot.attempts
        if item.game_id == attempt.game_id
        and item.adapter_id == attempt.adapter_id
        and item.level_id == attempt.level_id
        and item.segment_id == attempt.segment_id
        and item.objective_id == attempt.objective_id
        and item.objective_version == attempt.objective_version
    )
    eligible = tuple(
        item
        for item in same_contract
        if item.complete_timing_interval
        and item.evidence_integrity
        and set(item.required_observation_facts).issubset(item.observed_facts)
    )
    if not eligible:
        session = LearningSession(
            stable_id("learning-session", {"run": attempt.run_id, "eligible": ()}),
            attempt.game_id,
            attempt.adapter_id,
            attempt.objective_id,
            attempt.objective_version,
            tuple(item.run_id for item in same_contract),
            (),
            (),
            (),
            utc_now(),
        )
        store.write_manifest(
            session,
            attempt,
            artifact_references=(attempt.observation_evidence_reference,),
        )
        return session
    attempt_set = build_compatible_set(eligible)
    patterns = derive_trouble_patterns(
        attempt_set,
        eligible,
        minimum_attempts=minimum_repeated_attempts,
    )
    for pattern in patterns:
        store.save_pattern(pattern)
    tactics = derive_successful_tactics(attempt_set, eligible, patterns)
    for tactic in tactics:
        store.save_tactic(tactic)
    candidate_ids: list[str] = []
    for tactic in tactics:
        tactic_sources = tuple(
            item for item in eligible if item.run_id in tactic.supporting_run_ids
        )
        candidate = derive_candidate(
            attempt_set,
            tactic,
            eligible,
            action_sequence=(
                f"At {tactic.state_boundary}, apply reviewed tactic: {tactic.tactic_tag}.",
                *tuple(
                    f"Use hash-bound source input trace {item.input_trace_reference}."
                    for item in tactic_sources
                ),
            ),
        )
        store.create_candidate(candidate)
        candidate_ids.append(candidate.candidate_id)
    session = LearningSession(
        stable_id(
            "learning-session",
            {"runs": attempt_set.run_ids, "derivation": DERIVATION_VERSION},
        ),
        attempt.game_id,
        attempt.adapter_id,
        attempt.objective_id,
        attempt.objective_version,
        tuple(item.run_id for item in same_contract),
        (attempt_set.set_id,),
        tuple(pattern.pattern_id for pattern in patterns),
        tuple(candidate_ids),
        utc_now(),
    )
    store.write_manifest(
        session,
        attempt,
        artifact_references=(
            attempt.input_trace_reference,
            attempt.observation_evidence_reference,
            *tuple(f"candidate:{candidate_id}" for candidate_id in candidate_ids),
        ),
    )
    return session


def attempt_from_run_record(
    run: RunRecord,
    *,
    adapter_id: str,
    adapter_version: str,
) -> AttemptContract:
    """Backfill an existing V2.6 record without inventing unavailable anchors."""
    return AttemptContract(
        run_id=run.run_id,
        game_id=run.game_id,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        level_id=run.level_id,
        segment_id=run.segment_id,
        objective_id=run.profile_id,
        objective_version=run.profile_version,
        actor=run.actor,
        start_boundary=str(run.start_state.get("boundary", "unknown")),
        terminal_boundary=str(run.terminal_state.get("boundary", "unknown")),
        timing_units=run.timing_units,
        start_time=run.start_frame,
        terminal_time=run.terminal_frame,
        complete_timing_interval=run.elapsed_compatible_frames
        == run.terminal_frame - run.start_frame,
        emulator_assumptions=run.emulator_assumptions,
        allowed_techniques=("normal_gameplay",),
        resource_policy=("no_automatic_inventory_use",),
        required_observation_facts=run.required_events,
        observed_facts=run.required_events if run.comparison_compatible else (),
        evidence_integrity=run.comparison_compatible,
        completion=run.completion.value,
        deaths=run.deaths,
        recoveries=run.recoveries,
        directional_corrections=0,
        hesitation_intervals=0,
        missed_requirements=(),
        lost_resources=(),
        anchors=(),
        tactic_tags=tuple(
            tag
            for tag, present in (
                ("deathless_clear", run.deaths == 0),
                ("successful_recovery", run.recoveries > 0),
            )
            if present
        ),
        input_trace_reference=run.input_trace_reference,
        observation_evidence_reference=run.observation_evidence_reference,
        created_at=run.created_at,
    )


def backfill_run_library(
    store: LocalLearningStore,
    run_library: LocalRunLibrary,
    *,
    adapter_id: str,
    adapter_version: str,
) -> tuple[LearningSession, ...]:
    sessions = []
    for run in run_library.runs():
        sessions.append(
            process_attempt(
                store,
                attempt_from_run_record(
                    run,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                ),
            )
        )
    return tuple(sessions)


def learning_advice(
    snapshot: LearningSnapshot,
    game_id: str,
    objective_id: str,
    preference: OwnerLocalPreference | None = None,
) -> tuple[LearningAdvice, ...]:
    attempts = tuple(
        attempt
        for attempt in snapshot.attempts
        if attempt.game_id == game_id and attempt.objective_id == objective_id
    )
    patterns = tuple(
        pattern
        for pattern in snapshot.patterns
        if set(pattern.supporting_run_ids).intersection({attempt.run_id for attempt in attempts})
    )
    candidates = tuple(
        candidate
        for candidate in snapshot.candidates
        if candidate.game_id == game_id and candidate.objective_id == objective_id
    )
    if preference is None:
        preference = next(
            (
                item
                for item in reversed(snapshot.preferences)
                if item.game_id == game_id and item.objective_id == objective_id
            ),
            OwnerLocalPreference(game_id, objective_id),
        )
    advice: list[LearningAdvice] = []
    if len(attempts) < 2:
        advice.append(
            LearningAdvice(
                "There is not enough compatible evidence yet.",
                EvidenceClassification.UNKNOWN,
                tuple(attempt.observation_evidence_reference for attempt in attempts),
                1.0,
            )
        )
    completed = [item for item in attempts if item.completion == "completed" and item.evidence_integrity]
    if completed:
        fastest = min(completed, key=lambda item: item.elapsed)
        advice.append(
            LearningAdvice(
                f"Your current fastest observed run used this route in {fastest.elapsed} {fastest.timing_units}.",
                EvidenceClassification.FASTEST_LOCALLY_OBSERVED,
                (fastest.run_id, fastest.observation_evidence_reference),
                1.0,
            )
        )
    player_runs = [item for item in completed if item.actor == "player"]
    agent_runs = [item for item in completed if item.actor == "agent"]
    if player_runs and agent_runs:
        player_best = min(player_runs, key=lambda item: item.elapsed)
        agent_best = min(agent_runs, key=lambda item: item.elapsed)
        faster = agent_best if agent_best.elapsed < player_best.elapsed else player_best
        label = "agent reference" if faster.actor == "agent" else "player reference"
        advice.append(
            LearningAdvice(
                f"The {label} is faster for this compatible objective boundary.",
                EvidenceClassification.AGENT_BEST
                if faster.actor == "agent"
                else EvidenceClassification.PLAYER_BEST,
                (player_best.run_id, agent_best.run_id),
                1.0,
            )
        )
    for pattern in patterns:
        advice.append(
            LearningAdvice(
                f"You have had repeated trouble here in {len(pattern.supporting_run_ids)} compatible attempts.",
                EvidenceClassification.DERIVED_PATTERN,
                pattern.supporting_run_ids,
                pattern.confidence,
            )
        )
    for tactic in snapshot.tactics:
        if not set(tactic.supporting_run_ids).intersection({item.run_id for item in attempts}):
            continue
        advice.append(
            LearningAdvice(
                f"This approach worked better in {len(tactic.supporting_run_ids)} compatible attempt(s), but it has not been replay-validated.",
                EvidenceClassification.CANDIDATE_TACTIC,
                (*tactic.supporting_run_ids, *tactic.comparison_run_ids),
                tactic.confidence,
            )
        )
    for candidate in candidates:
        status_text = {
            CandidateLifecycle.REJECTED: "This candidate was rejected.",
            CandidateLifecycle.ROLLED_BACK: "This candidate was rolled back.",
        }.get(candidate.lifecycle, "A candidate improvement is available for review.")
        advice.append(
            LearningAdvice(
                status_text,
                EvidenceClassification.REJECTED
                if candidate.lifecycle is CandidateLifecycle.REJECTED
                else EvidenceClassification.ROLLED_BACK
                if candidate.lifecycle is CandidateLifecycle.ROLLED_BACK
                else EvidenceClassification.CANDIDATE_SOLUTION,
                candidate.provenance.source_run_ids,
                0.75,
                candidate.candidate_id,
            )
        )
    filtered: list[LearningAdvice] = []
    for item in advice:
        if (
            "speed" in preference.dismissed_suggestion_types
            and item.classification
            in {
                EvidenceClassification.FASTEST_LOCALLY_OBSERVED,
                EvidenceClassification.PLAYER_BEST,
                EvidenceClassification.AGENT_BEST,
            }
        ):
            continue
        if (
            "high_risk" in preference.dismissed_suggestion_types
            and item.candidate_id is not None
            and any(
                "risk" in risk.lower()
                for candidate in candidates
                if candidate.candidate_id == item.candidate_id
                for risk in candidate.risks
            )
        ):
            continue
        filtered.append(item)
    return tuple(filtered)


def personalized_assistance_rules(
    snapshot: LearningSnapshot,
    preference: OwnerLocalPreference,
) -> tuple[PersonalizedAssistanceRule, ...]:
    preference.validate()
    rules: list[PersonalizedAssistanceRule] = []
    for pattern in snapshot.patterns:
        if pattern.context.game_id != preference.game_id or pattern.context.objective_id != preference.objective_id:
            continue
        payload = {
            "scope": f"{preference.game_id}:{preference.objective_id}",
            "pattern": pattern.pattern_id,
            "policy": preference.help_policy.value,
        }
        rules.append(
            PersonalizedAssistanceRule(
                stable_id("assistance-rule", payload),
                preference.game_id,
                preference.objective_id,
                f"repeat at {pattern.anchor_id or 'objective boundary'}",
                "Offer evidence-linked help under the selected local help policy.",
                (
                    "help_policy",
                    "preferred_solution_style",
                    "risk_tolerance",
                    "resource_preservation",
                    "spoiler_level",
                ),
                (pattern.pattern_id, *pattern.supporting_run_ids),
                EvidenceClassification.OWNER_PREFERENCE,
                pattern.confidence,
                preference.help_policy is not HelpPolicy.QUIET,
            )
        )
    return tuple(rules)


def candidate_content_hash(candidate: CandidateSolution) -> str:
    payload = asdict(candidate)
    payload.pop("content_hash", None)
    payload.pop("lifecycle", None)
    payload.pop("created_at", None)
    return stable_hash(payload)


def stable_id(prefix: str, payload: Any) -> str:
    return f"{prefix}-{stable_hash(payload)[:16]}"


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default).encode()
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")
