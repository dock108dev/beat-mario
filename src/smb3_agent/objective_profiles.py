from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


PROFILE_PATH = Path("data/profiles/mario.yaml")
REFERENCE_PATH = Path("data/profiles/mario_references.yaml")


class ObjectiveProfileError(ValueError):
    pass


class ProfileClassification(str, Enum):
    ACCEPTED_AGENT_BEST = "accepted_agent_best"
    ACCEPTED_SAFE_REFERENCE = "accepted_safe_reference_run"
    PLAYER_PERSONAL_BEST = "player_personal_best"
    HISTORICAL_PLAYER_RUN = "historical_player_run"
    REVIEW_ONLY_DEMONSTRATION = "review_only_demonstration"
    UNREVIEWED_CANDIDATE = "unreviewed_candidate"


class RequirementState(str, Enum):
    COMPLETE = "complete"
    REMAINING = "remaining"
    STILL_RECOVERABLE = "still_recoverable"
    MISSED = "missed"
    UNVERIFIABLE = "unverifiable"


class ObjectiveOutcome(str, Enum):
    SUCCESS = "success"
    INCOMPLETE = "incomplete"
    MISSED = "missed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNVERIFIABLE = "unverifiable"


class ComparisonState(str, Enum):
    AHEAD = "ahead"
    BEHIND = "behind"
    TIED = "tied"
    NOT_COMPARABLE = "not_comparable"


class CoachingPolicy(str, Enum):
    QUIET = "quiet"
    ON_REQUEST = "on_request"
    PROACTIVE = "proactive"


@dataclass(frozen=True)
class Condition:
    fact: str
    operator: str
    value: str | int

    def validate(self) -> None:
        if not self.fact or self.operator not in {"equals", "at_least"}:
            raise ObjectiveProfileError("condition requires a fact and supported operator")


@dataclass(frozen=True)
class ObjectiveRequirement:
    requirement_id: str
    name: str
    condition: Condition
    optional: bool
    irreversible_after_x: int | None

    def validate(self) -> None:
        if not self.requirement_id or not self.name:
            raise ObjectiveProfileError("requirement id and name are required")
        self.condition.validate()


@dataclass(frozen=True)
class ObjectiveProfile:
    profile_id: str
    version: int
    game_id: str
    level_id: str
    segment_id: str
    name: str
    description: str
    classification: ProfileClassification
    start_condition: Condition
    terminal_condition: Condition
    timing_boundary: str
    timing_units: str
    pause_handling: str
    required: tuple[ObjectiveRequirement, ...]
    optional: tuple[ObjectiveRequirement, ...]
    allowed_techniques: tuple[str, ...]
    prohibited_techniques: tuple[str, ...]
    allowed_resources: tuple[str, ...]
    required_resources: tuple[str, ...]
    protected_resources: tuple[str, ...]
    supported_facts: tuple[str, ...]
    outcome_states: tuple[ObjectiveOutcome, ...]
    evidence_required: tuple[str, ...]
    comparison_supported: bool
    hints_supported: bool
    show_supported: bool
    future_takeover_supported: bool

    def validate(self) -> None:
        if not self.profile_id or self.version < 1 or not self.game_id or not self.level_id:
            raise ObjectiveProfileError("profile identity, version, game, and level are required")
        if not self.name or not self.description or not self.timing_boundary or not self.timing_units:
            raise ObjectiveProfileError("profile description and timing contract are required")
        self.start_condition.validate()
        self.terminal_condition.validate()
        if not self.required:
            raise ObjectiveProfileError("profile requires a finite required-event set")
        ids = [item.requirement_id for item in (*self.required, *self.optional)]
        if len(ids) != len(set(ids)):
            raise ObjectiveProfileError("profile requirement ids must be unique")
        for item in (*self.required, *self.optional):
            item.validate()
            if item.condition.fact not in self.supported_facts:
                raise ObjectiveProfileError(
                    f"requirement {item.requirement_id} uses unsupported observation fact"
                )
        if set(self.outcome_states) != set(ObjectiveOutcome):
            raise ObjectiveProfileError("profile must declare every objective outcome")
        claim = f"{self.name} {self.description}".lower()
        if any(word in claim for word in ("100%", "full completion")):
            raise ObjectiveProfileError("100% and full-completion claims require a complete object universe")
        if any(word in claim for word in ("fastest", "best")) and self.classification not in {
            ProfileClassification.ACCEPTED_AGENT_BEST,
            ProfileClassification.PLAYER_PERSONAL_BEST,
        }:
            raise ObjectiveProfileError("fastest/best claims require an accepted best classification")


@dataclass(frozen=True)
class ReferenceAnchor:
    anchor_id: str
    fact: str
    value: str | int
    elapsed: int


@dataclass(frozen=True)
class ReferenceRun:
    reference_id: str
    profile_id: str
    profile_version: int
    classification: ProfileClassification
    game_id: str
    level_id: str
    timing_boundary: str
    timing_units: str
    start_frame: int
    terminal_frame: int
    elapsed: int
    deaths: int
    complete_intervals: bool
    provenance: tuple[str, ...]
    evidence: tuple[str, ...]
    anchors: tuple[ReferenceAnchor, ...]

    def validate(self) -> None:
        if not self.reference_id or not self.provenance or not self.evidence:
            raise ObjectiveProfileError("reference identity, provenance, and evidence are required")
        if self.elapsed != self.terminal_frame - self.start_frame or self.elapsed < 0:
            raise ObjectiveProfileError("reference timing does not reconcile")
        if not self.complete_intervals:
            raise ObjectiveProfileError("reference contains an unexplained missing interval")
        if self.classification is ProfileClassification.REVIEW_ONLY_DEMONSTRATION:
            raise ObjectiveProfileError("review-only Show output cannot be authoritative reference evidence")


@dataclass(frozen=True)
class RequirementProgress:
    requirement_id: str
    name: str
    optional: bool
    state: RequirementState
    reason: str


@dataclass(frozen=True)
class ObjectiveProgress:
    profile: ObjectiveProfile
    requirements: tuple[RequirementProgress, ...]
    outcome: ObjectiveOutcome
    start_frame: int | None
    current_elapsed: int | None


@dataclass(frozen=True)
class ComparisonResult:
    state: ComparisonState
    reason: str
    player_elapsed: int | None = None
    reference_elapsed: int | None = None
    anchor_id: str | None = None
    death_delta: int | None = None


@dataclass(frozen=True)
class CoachingSuggestion:
    deduplication_key: str
    trigger: str
    profile_id: str
    provenance: tuple[str, ...]
    recoverable: bool
    action: str
    why: str
    confidence: float


@dataclass(frozen=True)
class ObjectiveTellAnswer:
    question: str
    spoiler_level: str
    answer: str
    current_facts: tuple[str, ...]
    profile_facts: tuple[str, ...]
    reference_facts: tuple[str, ...]
    inferences: tuple[str, ...]
    unknowns: tuple[str, ...]


@dataclass(frozen=True)
class ObjectiveView:
    profiles: tuple[ObjectiveProfile, ...]
    selected: ObjectiveProfile | None
    policy: CoachingPolicy
    progress: ObjectiveProgress | None
    reference: ReferenceRun | None
    comparison: ComparisonResult
    suggestion: CoachingSuggestion | None
    suppression_reason: str | None
    tell_answer: ObjectiveTellAnswer | None


class ObjectiveSessionManager:
    def __init__(self) -> None:
        self.profile_id: str | None = None
        self.policy = CoachingPolicy.QUIET
        self.reference_id: str | None = None
        self.emitted_keys: set[str] = set()
        self.suggestion: CoachingSuggestion | None = None
        self.suppression_reason: str | None = None
        self.tell_answer: ObjectiveTellAnswer | None = None
        self._last_progress_signature: tuple[str, ...] | None = None
        self._last_fresh_progress: ObjectiveProgress | None = None
        self._last_fresh_comparison: ComparisonResult | None = None

    def configure(self, snapshot: Any, profile_id: str, policy: str, reference_id: str | None) -> ObjectiveView:
        available = self._profiles(snapshot)
        selected = next((item for item in available if item.profile_id == profile_id), None)
        if selected is None:
            raise ObjectiveProfileError("profile is not supported for the currently observed level")
        try:
            selected_policy = CoachingPolicy(policy)
        except ValueError as exc:
            raise ObjectiveProfileError("unsupported coaching policy") from exc
        reference = compatible_reference(selected, reference_id) if reference_id else compatible_reference(selected)
        if reference_id and reference is None:
            raise ObjectiveProfileError("comparison target is incompatible with the selected profile")
        self.profile_id = selected.profile_id
        self.policy = selected_policy
        self.reference_id = reference.reference_id if reference else None
        self.suggestion = None
        self.tell_answer = None
        self._record(snapshot, "configuration", {"profile_id": self.profile_id, "profile_version": selected.version, "coaching_policy": self.policy.value, "reference_id": self.reference_id})
        self.view(snapshot)
        if self.policy is CoachingPolicy.QUIET:
            self.suppression_reason = "quiet_policy"
            self._record(snapshot, "advice_decision", {"decision": "quiet_policy", "suggestion": None})
        elif self.policy is CoachingPolicy.ON_REQUEST:
            self.suppression_reason = "not_requested"
            self._record(snapshot, "advice_decision", {"decision": "not_requested", "suggestion": None})
        return self.view(snapshot)

    def view(self, snapshot: Any) -> ObjectiveView:
        available = self._profiles(snapshot)
        selected = next((item for item in available if item.profile_id == self.profile_id), None)
        if selected is None and available:
            selected = available[0]
            self.profile_id = selected.profile_id
        if selected is None:
            return ObjectiveView((), None, self.policy, None, None, ComparisonResult(ComparisonState.NOT_COMPARABLE, "No supported profile is available for the currently observed level."), None, "unsupported_level", self.tell_answer)
        fresh = _snapshot_fresh(snapshot)
        progress = evaluate_progress(selected, tuple(snapshot.samples), fresh=fresh)
        reference = compatible_reference(selected, self.reference_id) if self.reference_id else compatible_reference(selected)
        comparison = compare_progress(progress, reference, tuple(snapshot.samples), fresh=fresh)
        if fresh:
            self._last_fresh_progress = progress
            self._last_fresh_comparison = comparison
        elif self.suggestion is not None:
            self.suggestion = None
            self.suppression_reason = "stale_observation"
            self._record(snapshot, "advice_decision", {"decision": "stale_observation", "suggestion": None})
        signature = tuple(f"{item.requirement_id}:{item.state.value}" for item in progress.requirements) + (comparison.anchor_id or "none",)
        if signature != self._last_progress_signature:
            self._last_progress_signature = signature
            self._record(snapshot, "objective_progress", {"profile_id": selected.profile_id, "profile_version": selected.version, "requirements": [asdict(item) for item in progress.requirements], "outcome": progress.outcome.value})
            self._record(snapshot, "comparison", asdict(comparison))
        if self.policy is CoachingPolicy.PROACTIVE and self.suggestion is None:
            suggestion, reason = choose_suggestion(progress, comparison, self.policy, requested=False, fresh=fresh, emitted_keys=self.emitted_keys)
            self.suppression_reason = reason
            if suggestion:
                self.suggestion = suggestion
                self.emitted_keys.add(suggestion.deduplication_key)
            self._record(snapshot, "advice_decision", {"decision": reason, "suggestion": asdict(suggestion) if suggestion else None})
        return ObjectiveView(available, selected, self.policy, progress, reference, comparison, self.suggestion, self.suppression_reason, self.tell_answer)

    def request_advice(self, snapshot: Any) -> ObjectiveView:
        view = self.view(snapshot)
        if view.progress is None:
            raise ObjectiveProfileError("objective advice requires a supported live profile")
        suggestion, reason = choose_suggestion(view.progress, view.comparison, self.policy, requested=True, fresh=_snapshot_fresh(snapshot), emitted_keys=self.emitted_keys)
        self.suppression_reason = reason
        self.suggestion = suggestion
        if suggestion:
            self.emitted_keys.add(suggestion.deduplication_key)
        self._record(snapshot, "requested_advice", {"decision": reason, "suggestion": asdict(suggestion) if suggestion else None})
        return self.view(snapshot)

    def dismiss(self, snapshot: Any) -> ObjectiveView:
        key = self.suggestion.deduplication_key if self.suggestion else None
        self.suggestion = None
        self._record(snapshot, "dismissed_advice", {"deduplication_key": key})
        return self.view(snapshot)

    def ask(self, snapshot: Any, question: str, spoiler_level: str = "guided") -> ObjectiveView:
        view = self.view(snapshot)
        if view.progress is None or view.selected is None:
            raise ObjectiveProfileError("objective-aware Tell requires a supported selected profile")
        self.tell_answer = objective_tell_answer(
            view,
            question,
            fresh=_snapshot_fresh(snapshot),
            spoiler_level=spoiler_level,
        )
        self._record(snapshot, "objective_tell", asdict(self.tell_answer))
        return self.view(snapshot)

    def finalize(self, snapshot: Any) -> None:
        view = self.view(snapshot)
        if snapshot.artifact_dir is None:
            return
        payload = {
            "schema": "game-companion-objective-session/v1",
            "profile": {"profile_id": view.selected.profile_id, "version": view.selected.version, "classification": view.selected.classification.value} if view.selected else None,
            "profile_definition": asdict(view.selected) if view.selected else None,
            "reference": asdict(view.reference) if view.reference else None,
            "coaching_policy": self.policy.value,
            "final_objective_classification": self._last_fresh_progress.outcome.value if self._last_fresh_progress else ObjectiveOutcome.UNVERIFIABLE.value,
            "post_stop_objective_availability": view.progress.outcome.value if view.progress else ObjectiveOutcome.UNVERIFIABLE.value,
            "comparison_compatibility": asdict(self._last_fresh_comparison or view.comparison),
            "player_input_count": snapshot.player_input_count,
            "agent_input_count": snapshot.agent_input_count,
            "observation_state": snapshot.state.value,
            "independently_readable_samples": sorted(
                str(path)
                for path in (snapshot.artifact_dir / "state-samples-png").glob("*.png")
            ),
            "reconciliation": {"profile_selected": view.selected is not None, "requirements_finite": bool(view.selected and view.selected.required), "agent_input_zero": snapshot.agent_input_count == 0, "not_route_reliability": True, "not_show": True, "not_takeover": True, "not_v2_9_acceptance": True, "not_automatically_promoted": True},
        }
        (snapshot.artifact_dir / "objective_reconciliation.json").write_text(json.dumps(payload, indent=2, default=_json_default) + "\n")

    def invalidate_volatile_state(self) -> None:
        """Clear live objective, coaching, comparison, and Tell presentation state."""
        self.profile_id = None
        self.policy = CoachingPolicy.QUIET
        self.reference_id = None
        self.emitted_keys.clear()
        self.suggestion = None
        self.suppression_reason = None
        self.tell_answer = None
        self._last_progress_signature = None
        self._last_fresh_progress = None
        self._last_fresh_comparison = None

    def _profiles(self, snapshot: Any) -> tuple[ObjectiveProfile, ...]:
        level = "world_1_1" if snapshot.checkpoint_id == "world_1_1_clear" or any(sample.world == 0 and sample.object_set == 1 for sample in snapshot.samples) else ""
        return profiles_for_level("smb3", level) if level else ()

    def _record(self, snapshot: Any, event: str, payload: dict[str, Any]) -> None:
        if snapshot.artifact_dir is None:
            return
        record = {"event": event, "observed_at": datetime.now(timezone.utc).isoformat(), **payload}
        with (snapshot.artifact_dir / "objective_events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=_json_default, sort_keys=True) + "\n")


def load_profile_catalog(path: Path = PROFILE_PATH) -> tuple[ObjectiveProfile, ...]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or raw.get("schema") != "game-companion-objective-profiles/v1":
        raise ObjectiveProfileError("objective catalog schema is unsupported")
    game_id = str(raw.get("game_id", ""))
    profiles = tuple(_load_profile(game_id, item) for item in raw.get("profiles", ()))
    if not profiles:
        raise ObjectiveProfileError("objective catalog must contain profiles")
    keys = [(profile.profile_id, profile.version) for profile in profiles]
    if len(keys) != len(set(keys)):
        raise ObjectiveProfileError("profile id and version pairs must be unique")
    for profile in profiles:
        profile.validate()
    return profiles


def load_reference_catalog(path: Path = REFERENCE_PATH) -> tuple[ReferenceRun, ...]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or raw.get("schema") != "game-companion-reference-runs/v1":
        raise ObjectiveProfileError("reference catalog schema is unsupported")
    references = tuple(_load_reference(item) for item in raw.get("references", ()))
    ids = [item.reference_id for item in references]
    if len(ids) != len(set(ids)):
        raise ObjectiveProfileError("reference ids must be unique")
    for reference in references:
        reference.validate()
    return references


def profiles_for_level(game_id: str, level_id: str) -> tuple[ObjectiveProfile, ...]:
    return tuple(
        profile for profile in load_profile_catalog()
        if profile.game_id == game_id and profile.level_id == level_id
    )


def compatible_reference(profile: ObjectiveProfile, reference_id: str | None = None) -> ReferenceRun | None:
    matches = [
        reference for reference in load_reference_catalog()
        if reference.profile_id == profile.profile_id
        and reference.profile_version == profile.version
        and reference.game_id == profile.game_id
        and reference.level_id == profile.level_id
        and reference.timing_boundary == profile.timing_boundary
        and reference.timing_units == profile.timing_units
    ]
    if reference_id is not None:
        matches = [item for item in matches if item.reference_id == reference_id]
    return matches[0] if matches else None


def evaluate_progress(profile: ObjectiveProfile, samples: tuple[Any, ...], *, fresh: bool) -> ObjectiveProgress:
    if not samples:
        return ObjectiveProgress(profile, tuple(_unverifiable(profile)), ObjectiveOutcome.UNVERIFIABLE, None, None)
    level_samples = tuple(sample for sample in samples if sample.world == 0 and sample.object_set == 1)
    start_frame = level_samples[0].frame if level_samples else None
    latest = samples[-1]
    course_clear = any(
        previous.object_set == 1
        and current.object_set == 0
        and (previous.return_map == 1 or current.return_map == 1)
        for previous, current in zip(samples, samples[1:])
    )
    facts: dict[str, str | int] = {
        "level_identity": "world_1_1" if level_samples else "unknown",
        "mario_x": max((sample.x for sample in level_samples), default=0),
        "course_clear": str(course_clear).lower(),
        "deaths": sum(
            1 for previous, current in zip(samples, samples[1:])
            if current.lives < previous.lives
            or (previous.player_is_dying == 0 and current.player_is_dying == 1)
        ),
    }
    progress: list[RequirementProgress] = []
    for requirement in (*profile.required, *profile.optional):
        if requirement.condition.fact not in facts or not fresh:
            state = RequirementState.UNVERIFIABLE
            reason = "Fresh supported observation is unavailable."
        elif _matches(requirement.condition, facts[requirement.condition.fact]):
            state = RequirementState.COMPLETE
            reason = f"Observed {requirement.condition.fact}={facts[requirement.condition.fact]}."
        elif requirement.irreversible_after_x is not None and int(facts["mario_x"]) > requirement.irreversible_after_x:
            state = RequirementState.MISSED
            reason = "The observed scroll boundary passed; this requirement is no longer recoverable."
        else:
            state = RequirementState.STILL_RECOVERABLE if level_samples and not course_clear else RequirementState.REMAINING
            reason = "Not complete; it remains available in this active attempt." if state is RequirementState.STILL_RECOVERABLE else "Not observed complete."
        progress.append(RequirementProgress(requirement.requirement_id, requirement.name, requirement.optional, state, reason))
    required = progress[: len(profile.required)]
    if not fresh:
        outcome = ObjectiveOutcome.UNVERIFIABLE
    elif all(item.state is RequirementState.COMPLETE for item in required):
        outcome = ObjectiveOutcome.SUCCESS
    elif any(item.state is RequirementState.MISSED for item in required):
        outcome = ObjectiveOutcome.MISSED
    else:
        outcome = ObjectiveOutcome.INCOMPLETE
    elapsed = latest.frame - start_frame if start_frame is not None else None
    return ObjectiveProgress(profile, tuple(progress), outcome, start_frame, elapsed)


def compare_progress(progress: ObjectiveProgress, reference: ReferenceRun | None, samples: tuple[Any, ...], *, fresh: bool) -> ComparisonResult:
    profile = progress.profile
    if not profile.comparison_supported:
        return ComparisonResult(ComparisonState.NOT_COMPARABLE, "This profile does not define a timing comparison.")
    if reference is None:
        return ComparisonResult(ComparisonState.NOT_COMPARABLE, "No compatible accepted reference exists for this profile and version.")
    if not fresh or not samples:
        return ComparisonResult(ComparisonState.NOT_COMPARABLE, "Fresh live state is unavailable.")
    if progress.start_frame is None or progress.current_elapsed is None:
        return ComparisonResult(ComparisonState.NOT_COMPARABLE, "The measurable profile start was not observed.")
    x = max((sample.x for sample in samples if sample.world == 0 and sample.object_set == 1), default=0)
    completed = progress.outcome is ObjectiveOutcome.SUCCESS
    candidates = [anchor for anchor in reference.anchors if (anchor.fact == "mario_x" and int(anchor.value) <= x) or (anchor.fact == "course_clear" and completed)]
    if not candidates:
        return ComparisonResult(ComparisonState.NOT_COMPARABLE, "No comparable progress anchor has been observed yet.")
    anchor = max(candidates, key=lambda item: item.elapsed)
    delta = progress.current_elapsed - anchor.elapsed
    state = ComparisonState.TIED if delta == 0 else ComparisonState.AHEAD if delta < 0 else ComparisonState.BEHIND
    deaths = sum(1 for previous, current in zip(samples, samples[1:]) if current.lives < previous.lives or (previous.player_is_dying == 0 and current.player_is_dying == 1))
    return ComparisonResult(state, f"Compared at {anchor.anchor_id} using {profile.timing_units} from the same start boundary.", progress.current_elapsed, anchor.elapsed, anchor.anchor_id, deaths - reference.deaths)


def choose_suggestion(progress: ObjectiveProgress, comparison: ComparisonResult, policy: CoachingPolicy, *, requested: bool, fresh: bool, emitted_keys: set[str]) -> tuple[CoachingSuggestion | None, str]:
    if policy is CoachingPolicy.QUIET:
        return None, "quiet_policy"
    if policy is CoachingPolicy.ON_REQUEST and not requested:
        return None, "not_requested"
    if not fresh:
        return None, "stale_observation"
    missed = next((item for item in progress.requirements if item.state is RequirementState.MISSED), None)
    remaining = next((item for item in progress.requirements if item.state is RequirementState.STILL_RECOVERABLE), None)
    if missed is not None:
        return None, "requirement_already_impossible"
    if remaining is None:
        return None, "no_actionable_requirement"
    key = f"{progress.profile.profile_id}:{remaining.requirement_id}:{comparison.anchor_id or 'none'}"
    if key in emitted_keys:
        return None, "duplicate_without_meaningful_change"
    suggestion = CoachingSuggestion(
        key,
        f"{remaining.name} is still recoverable in the fresh observed attempt.",
        progress.profile.profile_id,
        ("adapter_observation:live-sample", f"objective_profile:{progress.profile.profile_id}@{progress.profile.version}"),
        True,
        "Keep moving right toward the next observable milestone while protecting your current life.",
        f"It advances the selected objective: {progress.profile.name}.",
        0.9,
    )
    return suggestion, "emitted"


def objective_tell_answer(
    view: ObjectiveView,
    question: str,
    *,
    fresh: bool,
    spoiler_level: str = "guided",
) -> ObjectiveTellAnswer:
    if view.selected is None or view.progress is None:
        raise ObjectiveProfileError("objective-aware Tell requires a selected profile")
    if spoiler_level not in {"minimal", "guided", "full"}:
        raise ObjectiveProfileError("unsupported objective Tell spoiler level")
    normalized = question.strip().lower()
    current = tuple(
        f"{item.name}: {item.state.value.replace('_', ' ')}"
        for item in view.progress.requirements
    )
    profile_facts = (
        f"Selected profile: {view.selected.name} ({view.selected.profile_id}@{view.selected.version}).",
        f"Timing boundary: {view.selected.timing_boundary} in {view.selected.timing_units}.",
    )
    reference_facts = (
        (f"Reference {view.reference.reference_id}: {view.reference.elapsed} {view.reference.timing_units}; classification {view.reference.classification.value}.",)
        if view.reference
        else ()
    )
    unknowns: list[str] = []
    inferences: list[str] = []
    if not fresh:
        answer = "Live state is stale or disconnected, so objective progress, comparison, and coaching are unavailable."
        unknowns.append("Current objective state cannot be verified until a fresh observation arrives.")
    elif "against" in normalized or "behind" in normalized or "reference" in normalized:
        answer = f"Comparison: {view.comparison.state.value.replace('_', ' ')}. {view.comparison.reason}"
        if view.comparison.state is not ComparisonState.NOT_COMPARABLE:
            inferences.append("Ahead/behind is inferred only at the latest compatible progress anchor.")
        else:
            unknowns.append(view.comparison.reason)
    elif "miss" in normalized:
        missed = [item.name for item in view.progress.requirements if item.state is RequirementState.MISSED]
        unverifiable = [item.name for item in view.progress.requirements if item.state is RequirementState.UNVERIFIABLE]
        answer = "Missed: " + (", ".join(missed) if missed else "none observed") + "."
        if unverifiable:
            unknowns.append("Unverifiable: " + ", ".join(unverifiable) + ".")
    elif "still" in normalized or "need" in normalized or "complete" in normalized:
        remaining = [item.name for item in view.progress.requirements if item.state in {RequirementState.REMAINING, RequirementState.STILL_RECOVERABLE}]
        answer = "Remaining: " + (", ".join(remaining) if remaining else "none") + "."
    elif "full plan" in normalized or "plan" in normalized:
        answer = "Profile plan: " + "; then ".join(item.name for item in view.progress.requirements if not item.optional) + "."
    elif "speed" in normalized or "next" in normalized:
        if view.comparison.state is ComparisonState.NOT_COMPARABLE:
            answer = "Speed advice is unavailable because " + view.comparison.reason.lower()
            unknowns.append("No speed claim is made without a compatible reference.")
        else:
            remaining = next((item.name for item in view.progress.requirements if item.state is RequirementState.STILL_RECOVERABLE), "the course clear")
            answer = f"Next objective action: continue toward {remaining}; comparison is {view.comparison.state.value} at {view.comparison.anchor_id}."
    else:
        answer = f"Objective outcome is {view.progress.outcome.value}; {view.comparison.reason}"
    if spoiler_level == "minimal":
        current = current[:1]
        profile_facts = profile_facts[:1]
        reference_facts = ()
        inferences = []
    elif spoiler_level == "full" and "plan" not in normalized:
        answer += " Full profile plan: " + "; then ".join(
            item.name for item in view.progress.requirements if not item.optional
        ) + "."
    return ObjectiveTellAnswer(
        question,
        spoiler_level,
        answer,
        current,
        profile_facts,
        reference_facts,
        tuple(inferences),
        tuple(unknowns),
    )


def _unverifiable(profile: ObjectiveProfile) -> list[RequirementProgress]:
    return [RequirementProgress(item.requirement_id, item.name, item.optional, RequirementState.UNVERIFIABLE, "No live attempt has been observed.") for item in (*profile.required, *profile.optional)]


def _matches(condition: Condition, actual: str | int) -> bool:
    if condition.operator == "equals":
        return str(actual).lower() == str(condition.value).lower()
    return int(actual) >= int(condition.value)


def _snapshot_fresh(snapshot: Any) -> bool:
    return (
        getattr(getattr(snapshot, "state", None), "value", None) == "connected"
        and getattr(getattr(snapshot, "freshness", None), "value", None) == "fresh"
        and bool(getattr(snapshot, "samples", ()))
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _load_profile(game_id: str, raw: dict[str, Any]) -> ObjectiveProfile:
    timing = raw["timing"]
    capabilities = raw["capabilities"]
    return ObjectiveProfile(
        str(raw["profile_id"]), int(raw["version"]), game_id, str(raw["level_id"]), str(raw["segment_id"]), str(raw["name"]), str(raw["description"]), ProfileClassification(raw["classification"]),
        Condition(**raw["start_condition"]), Condition(**raw["terminal_condition"]), str(timing["boundary"]), str(timing["units"]), str(timing["pauses"]),
        tuple(_load_requirement(item, False) for item in raw["required_events"]), tuple(_load_requirement(item, True) for item in raw["optional_events"]),
        tuple(raw["allowed_techniques"]), tuple(raw["prohibited_techniques"]), tuple(raw["allowed_resources"]), tuple(raw["required_resources"]), tuple(raw["protected_resources"]), tuple(raw["supported_observation_facts"]), tuple(ObjectiveOutcome(item) for item in raw["outcome_states"]), tuple(raw["evidence_required"]),
        bool(capabilities["comparison"]), bool(capabilities["hints"]), bool(capabilities["show"]), bool(capabilities["future_takeover"]),
    )


def _load_requirement(raw: dict[str, Any], optional: bool) -> ObjectiveRequirement:
    return ObjectiveRequirement(str(raw["requirement_id"]), str(raw["name"]), Condition(str(raw["fact"]), str(raw["operator"]), raw["value"]), optional, raw.get("irreversible_after_x"))


def _load_reference(raw: dict[str, Any]) -> ReferenceRun:
    return ReferenceRun(
        str(raw["reference_id"]), str(raw["profile_id"]), int(raw["profile_version"]), ProfileClassification(raw["classification"]), str(raw["game_id"]), str(raw["level_id"]), str(raw["timing_boundary"]), str(raw["timing_units"]), int(raw["start_frame"]), int(raw["terminal_frame"]), int(raw["elapsed"]), int(raw["deaths"]), bool(raw["complete_intervals"]), tuple(raw["provenance"]), tuple(raw["evidence"]), tuple(ReferenceAnchor(str(item["anchor_id"]), str(item["fact"]), item["value"], int(item["elapsed"])) for item in raw["anchors"]),
    )
