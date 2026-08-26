from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import traceback
from typing import Any, Callable, Iterable, Mapping

import yaml

from smb3_agent.paths import repository_path


SCENARIO_SCHEMA_VERSION = "game-companion-scenario/v1"
PLAN_SCHEMA_VERSION = "game-companion-scenario-plan/v1"
ATTEMPT_SCHEMA_VERSION = "game-companion-scenario-attempt/v1"
DEFAULT_CATALOG = repository_path("data/scenarios/catalog.yaml")
DEFAULT_ATTEMPT_ROOT = Path("artifacts/scenarios")
READINESS_SCHEMA_VERSION = "game-companion-final-campaign-readiness/v2"
CAMPAIGN_ENTRY_MANIFEST_SCHEMA_VERSION = "game-companion-campaign-entry-manifest/v1"
CAMPAIGN_ENTRY_MANIFEST_MAX_BYTES = 256 * 1024
AUTHORITATIVE_CAMPAIGN_CONTRACTS = (
    "data/scenarios/catalog.yaml",
    "data/scenarios/final-campaign.yaml",
    "data/scenarios/campaign-entry-manifest-schema.json",
    "data/scenarios/event-schema.json",
    "data/scenarios/metrics-schema.json",
    "data/scenarios/fixtures.yaml",
    "data/scenarios/artifact-contract.yaml",
    "data/scenarios/unattended-artifact-contract.yaml",
    "data/scenarios/mario-owner-pilot.yaml",
    "data/scenarios/stardew-owner-pilot.yaml",
    "data/companion/catalog-contract.yaml",
    "data/experimental-adapters/artifact-contract.yaml",
    "data/stardew/evidence-contract.yaml",
)
KNOWN_CAPABILITY_STATUSES = frozenset(
    {
        "available",
        "missing_implementation",
        "implemented_campaign_validation_pending",
        "candidate_prerequisite_blocked",
        "live_validation_pending",
        "owner_action_pending",
        "completed_accepted",
    }
)
CAMPAIGN_ELIGIBLE_STATUSES = frozenset(
    {
        "available",
        "implemented_campaign_validation_pending",
        "live_validation_pending",
        "owner_action_pending",
    }
)
IMPLEMENTATION_BLOCKING_STATUSES = frozenset({"missing_implementation"})
CANDIDATE_BLOCKING_STATUSES = frozenset({"candidate_prerequisite_blocked"})
SCHEDULED_VALIDATION_STATUSES = frozenset(
    {"implemented_campaign_validation_pending", "live_validation_pending"}
)
PROOF_LIMITS = (
    "deterministic readiness is not live proof",
    "campaign entry is not campaign completion",
    "technical validation is not reliability, usefulness, or owner acceptance",
    "unattended regression cannot prove visible, authoritative, reliability, usefulness, or acceptance outcomes",
    "final owner acceptance remains pending until the owner explicitly decides for the exact candidate",
)


class ScenarioError(ValueError):
    pass


class ScenarioClassification(str, Enum):
    DETERMINISTIC_ONLY = "deterministic_only"
    VISIBLE_TECHNICAL = "visible_technical"
    OWNER_REQUIRED = "owner_required"
    RELIABILITY = "reliability"
    REVIEW_ONLY = "review_only"
    UNATTENDED_REGRESSION = "unattended_regression"
    FINAL_CAMPAIGN = "final_campaign_orchestration"


class EvidenceClassification(str, Enum):
    DETERMINISTIC_FIXTURE = "deterministic_fixture_result"
    UNIT_INTEGRATION = "unit_integration_result"
    TECHNICAL_SESSION = "technical_session_result"
    VISIBLE_LIVE = "visible_live_result"
    ROUTE_RELIABILITY = "route_reliability_result"
    REVIEW_ONLY_SHOW = "review_only_show_result"
    UNATTENDED_REGRESSION = "unattended_regression_result"
    OWNER_USEFULNESS = "owner_usefulness_feedback"
    OWNER_ACCEPTANCE = "owner_product_acceptance"
    AUTHORITATIVE_GAME = "authoritative_game_owned_outcome"


class ScenarioLifecycle(str, Enum):
    DEFINED = "defined"
    PREFLIGHT_PENDING = "preflight_pending"
    READY = "ready"
    BLOCKED = "blocked"
    RUNNING = "running"
    OWNER_ACTION_REQUIRED = "owner_action_required"
    CLEANUP_PENDING = "cleanup_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    PROCESS_LOST = "process_lost"
    RETAINED_FOR_REVIEW = "retained_for_review"


TERMINAL_STATES = frozenset(
    {
        ScenarioLifecycle.BLOCKED,
        ScenarioLifecycle.COMPLETED,
        ScenarioLifecycle.FAILED,
        ScenarioLifecycle.TIMED_OUT,
        ScenarioLifecycle.CANCELLED,
        ScenarioLifecycle.PROCESS_LOST,
        ScenarioLifecycle.RETAINED_FOR_REVIEW,
    }
)

ALLOWED_TRANSITIONS = {
    ScenarioLifecycle.DEFINED: frozenset({ScenarioLifecycle.PREFLIGHT_PENDING, ScenarioLifecycle.CANCELLED}),
    ScenarioLifecycle.PREFLIGHT_PENDING: frozenset({ScenarioLifecycle.READY, ScenarioLifecycle.BLOCKED, ScenarioLifecycle.FAILED}),
    ScenarioLifecycle.READY: frozenset({ScenarioLifecycle.RUNNING, ScenarioLifecycle.OWNER_ACTION_REQUIRED, ScenarioLifecycle.CANCELLED, ScenarioLifecycle.TIMED_OUT, ScenarioLifecycle.PROCESS_LOST}),
    ScenarioLifecycle.OWNER_ACTION_REQUIRED: frozenset({ScenarioLifecycle.READY, ScenarioLifecycle.CANCELLED, ScenarioLifecycle.TIMED_OUT, ScenarioLifecycle.PROCESS_LOST}),
    ScenarioLifecycle.RUNNING: frozenset({ScenarioLifecycle.OWNER_ACTION_REQUIRED, ScenarioLifecycle.CLEANUP_PENDING}),
    ScenarioLifecycle.CLEANUP_PENDING: TERMINAL_STATES,
}


@dataclass(frozen=True)
class ScenarioStep:
    step_id: str
    actor: str
    action: str
    owner_action_required: bool = False
    may_send_input: bool = False
    safe_to_resume: bool = False


@dataclass(frozen=True)
class RetryPolicy:
    maximum_new_attempts: int = 0
    retryable_terminal_states: tuple[str, ...] = ()
    destructive_retry: bool = False


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    version: str
    title: str
    game_id: str
    adapter_id: str
    adapter_version: str
    classification: ScenarioClassification
    evidence_classification: EvidenceClassification
    execution_classification: str
    capability_requirements: tuple[str, ...]
    preconditions: tuple[str, ...]
    required_fixtures: tuple[str, ...]
    required_local_assets: tuple[str, ...]
    owner_action_boundaries: tuple[str, ...]
    automated_steps: tuple[ScenarioStep, ...]
    expected_events: tuple[str, ...]
    expected_state_transitions: tuple[str, ...]
    negative_expectations: tuple[str, ...]
    timeout_seconds: int
    cleanup_requirements: tuple[str, ...]
    artifact_requirements: tuple[str, ...]
    expected_terminal_state: ScenarioLifecycle
    visible_execution_required: bool
    owner_participation_required: bool
    may_count_toward_reliability: bool
    may_count_toward_owner_acceptance: bool
    retry_policy: RetryPolicy
    failure_retention_policy: str
    affected_process_or_save: str
    allowed_inputs: tuple[str, ...]
    protected_decisions: tuple[str, ...]
    stop_and_reclaim_behavior: str
    expected_duration: str
    result_can_prove: tuple[str, ...]
    result_cannot_prove: tuple[str, ...]
    capability_status: str = "available"
    implementation_evidence: tuple[str, ...] = ()
    safety_requirements: tuple[str, ...] = ()
    visible_live_proof: bool = False
    authoritative_game_outcome: bool = False

    def validate(self) -> None:
        if not self.scenario_id or not self.version:
            raise ScenarioError("scenario id and version are required")
        if self.timeout_seconds <= 0:
            raise ScenarioError(f"{self.scenario_id}: timeout must be positive")
        if self.capability_status not in KNOWN_CAPABILITY_STATUSES:
            raise ScenarioError(
                f"{self.scenario_id}: unknown capability status: {self.capability_status}"
            )
        if self.capability_status in SCHEDULED_VALIDATION_STATUSES and (
            not self.implementation_evidence or not self.safety_requirements
        ):
            raise ScenarioError(
                f"{self.scenario_id}: campaign-eligible implementation requires evidence and safety requirements"
            )
        if self.capability_status == "owner_action_pending" and not self.owner_participation_required:
            raise ScenarioError(
                f"{self.scenario_id}: pending owner action requires owner participation"
            )
        if self.owner_participation_required and self.classification not in {
            ScenarioClassification.OWNER_REQUIRED,
            ScenarioClassification.FINAL_CAMPAIGN,
        }:
            raise ScenarioError(f"{self.scenario_id}: owner participation requires an owner classification")
        if self.may_count_toward_owner_acceptance and not self.owner_participation_required:
            raise ScenarioError(f"{self.scenario_id}: owner acceptance requires owner participation")
        if self.classification is ScenarioClassification.UNATTENDED_REGRESSION and (
            self.may_count_toward_reliability
            or self.may_count_toward_owner_acceptance
            or self.visible_live_proof
            or self.authoritative_game_outcome
            or self.evidence_classification is not EvidenceClassification.UNATTENDED_REGRESSION
            or self.execution_classification != ScenarioClassification.UNATTENDED_REGRESSION.value
        ):
            raise ScenarioError(f"{self.scenario_id}: unattended execution is regression-only")
        if any(step.owner_action_required for step in self.automated_steps):
            raise ScenarioError(f"{self.scenario_id}: owner steps cannot be listed as automated")

    @property
    def identity(self) -> str:
        return f"{self.scenario_id}@{self.version}"


@dataclass(frozen=True)
class ScenarioPlan:
    schema_version: str
    scenario: ScenarioDefinition
    generated_at: str
    steps: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario.scenario_id,
            "scenario_version": self.scenario.version,
            "generated_at": self.generated_at,
            "classification": self.scenario.classification.value,
            "evidence_classification": self.scenario.evidence_classification.value,
            "execution_classification": self.scenario.execution_classification,
            "steps": list(self.steps),
            "game_and_adapter": {
                "game_id": self.scenario.game_id,
                "adapter_id": self.scenario.adapter_id,
                "adapter_version": self.scenario.adapter_version,
            },
            "affected_process_or_save": self.scenario.affected_process_or_save,
            "allowed_inputs": list(self.scenario.allowed_inputs),
            "protected_decisions": list(self.scenario.protected_decisions),
            "stop_and_reclaim_behavior": self.scenario.stop_and_reclaim_behavior,
            "expected_duration": self.scenario.expected_duration,
            "cleanup_requirements": list(self.scenario.cleanup_requirements),
            "retained_evidence": list(self.scenario.artifact_requirements),
            "can_prove": list(self.scenario.result_can_prove),
            "cannot_prove": list(self.scenario.result_cannot_prove),
            "visible_execution_required": self.scenario.visible_execution_required,
            "owner_participation_required": self.scenario.owner_participation_required,
        }


@dataclass
class ScenarioAttempt:
    attempt_id: str
    scenario_id: str
    scenario_version: str
    evidence_classification: str
    source_identity: Mapping[str, str]
    state: ScenarioLifecycle = ScenarioLifecycle.DEFINED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    history: list[Mapping[str, Any]] = field(default_factory=list)
    failure: str | None = None
    failure_details: list[Mapping[str, str]] = field(default_factory=list)
    cleanup_complete: bool = False


def _tuples(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in (value or ()))


def _load_definition(raw: Mapping[str, Any], defaults: Mapping[str, Any]) -> ScenarioDefinition:
    item = {**defaults, **raw}
    retry = item.get("retry_policy") or {}
    steps = tuple(
        ScenarioStep(
            step_id=str(step["step_id"]),
            actor=str(step.get("actor", "system")),
            action=str(step["action"]),
            owner_action_required=bool(step.get("owner_action_required", False)),
            may_send_input=bool(step.get("may_send_input", False)),
            safe_to_resume=bool(step.get("safe_to_resume", False)),
        )
        for step in item.get("automated_steps", ())
    )
    definition = ScenarioDefinition(
        scenario_id=str(item["scenario_id"]),
        version=str(item["version"]),
        title=str(item["title"]),
        game_id=str(item["game_id"]),
        adapter_id=str(item["adapter_id"]),
        adapter_version=str(item["adapter_version"]),
        classification=ScenarioClassification(str(item["classification"])),
        evidence_classification=EvidenceClassification(str(item["evidence_classification"])),
        execution_classification=str(item["execution_classification"]),
        capability_requirements=_tuples(item.get("capability_requirements")),
        preconditions=_tuples(item.get("preconditions")),
        required_fixtures=_tuples(item.get("required_fixtures")),
        required_local_assets=_tuples(item.get("required_local_assets")),
        owner_action_boundaries=_tuples(item.get("owner_action_boundaries")),
        automated_steps=steps,
        expected_events=_tuples(item.get("expected_events")),
        expected_state_transitions=_tuples(item.get("expected_state_transitions")),
        negative_expectations=_tuples(item.get("negative_expectations")),
        timeout_seconds=int(item["timeout_seconds"]),
        cleanup_requirements=_tuples(item.get("cleanup_requirements")),
        artifact_requirements=_tuples(item.get("artifact_requirements")),
        expected_terminal_state=ScenarioLifecycle(str(item["expected_terminal_state"])),
        visible_execution_required=bool(item.get("visible_execution_required", False)),
        owner_participation_required=bool(item.get("owner_participation_required", False)),
        may_count_toward_reliability=bool(item.get("may_count_toward_reliability", False)),
        may_count_toward_owner_acceptance=bool(item.get("may_count_toward_owner_acceptance", False)),
        visible_live_proof=bool(item.get("visible_live_proof", False)),
        authoritative_game_outcome=bool(item.get("authoritative_game_outcome", False)),
        retry_policy=RetryPolicy(
            maximum_new_attempts=int(retry.get("maximum_new_attempts", 0)),
            retryable_terminal_states=_tuples(retry.get("retryable_terminal_states")),
            destructive_retry=bool(retry.get("destructive_retry", False)),
        ),
        failure_retention_policy=str(item.get("failure_retention_policy", "retain_complete_attempt")),
        affected_process_or_save=str(item.get("affected_process_or_save", "none")),
        allowed_inputs=_tuples(item.get("allowed_inputs")),
        protected_decisions=_tuples(item.get("protected_decisions")),
        stop_and_reclaim_behavior=str(item.get("stop_and_reclaim_behavior", "stop without input")),
        expected_duration=str(item.get("expected_duration", "unknown")),
        result_can_prove=_tuples(item.get("result_can_prove")),
        result_cannot_prove=_tuples(item.get("result_cannot_prove")),
        capability_status=str(item.get("capability_status", "available")),
        implementation_evidence=_tuples(item.get("implementation_evidence")),
        safety_requirements=_tuples(item.get("safety_requirements")),
    )
    definition.validate()
    return definition


def load_scenario_catalog(path: Path = DEFAULT_CATALOG) -> tuple[ScenarioDefinition, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != SCENARIO_SCHEMA_VERSION:
        raise ScenarioError("unsupported scenario catalog schema")
    defaults = raw.get("defaults") or {}
    definitions = tuple(_load_definition(item, defaults) for item in raw.get("scenarios", ()))
    identities = [item.identity for item in definitions]
    if len(identities) != len(set(identities)):
        raise ScenarioError("duplicate scenario identity")
    return definitions


def scenario_plan(definition: ScenarioDefinition) -> ScenarioPlan:
    steps: list[Mapping[str, Any]] = [
        {"step_id": "preflight", "actor": "system", "action": "Fail-closed capability, fixture, asset, and process checks", "automated": True, "may_send_input": False}
    ]
    steps.extend(
        {
            "step_id": step.step_id,
            "actor": step.actor,
            "action": step.action,
            "automated": True,
            "may_send_input": step.may_send_input,
            "safe_to_resume": step.safe_to_resume,
        }
        for step in definition.automated_steps
    )
    steps.extend(
        {"step_id": f"owner-{index}", "actor": "owner", "action": boundary, "automated": False, "may_send_input": False}
        for index, boundary in enumerate(definition.owner_action_boundaries, 1)
    )
    steps.append({"step_id": "cleanup", "actor": "system", "action": "; ".join(definition.cleanup_requirements), "automated": True, "may_send_input": False})
    return ScenarioPlan(PLAN_SCHEMA_VERSION, definition, datetime.now(timezone.utc).isoformat(), tuple(steps))


class ScenarioRunner:
    """Local orchestration contract. Construction and planning never execute a scenario."""

    def __init__(self, root: Path = DEFAULT_ATTEMPT_ROOT):
        self.root = root

    def preflight(self, definition: ScenarioDefinition, capabilities: Iterable[str], *, unattended: bool = False) -> tuple[str, ...]:
        available = set(capabilities)
        blockers = [f"missing capability: {item}" for item in definition.capability_requirements if item not in available]
        blockers.extend(f"missing fixture: {item}" for item in definition.required_fixtures if not Path(item).exists())
        blockers.extend(f"missing local asset: {item}" for item in definition.required_local_assets if not Path(item).exists())
        if definition.capability_status not in CAMPAIGN_ELIGIBLE_STATUSES:
            blockers.append(f"capability status: {definition.capability_status}")
        if unattended and definition.owner_participation_required:
            blockers.append("owner-required scenario cannot run unattended")
        if unattended and definition.classification is not ScenarioClassification.UNATTENDED_REGRESSION:
            blockers.append("scenario is not classified for unattended regression")
        return tuple(blockers)

    @staticmethod
    def list(definitions: Iterable[ScenarioDefinition]) -> tuple[ScenarioDefinition, ...]:
        return tuple(definitions)

    def execute(
        self,
        definition: ScenarioDefinition,
        attempt: ScenarioAttempt,
        *,
        capabilities: Iterable[str],
        step_executors: Mapping[str, Callable[[], None]],
        cleanup_action: Callable[[], None],
        owner_action_acknowledged: bool = False,
        unattended: bool = False,
        authorization_check: Callable[[ScenarioStep], bool] | None = None,
    ) -> ScenarioAttempt:
        """Execute only supplied local step adapters; no game adapter is implicit."""
        blockers = self.preflight(definition, capabilities, unattended=unattended)
        self.transition(attempt, ScenarioLifecycle.PREFLIGHT_PENDING)
        if blockers:
            return self.transition(attempt, ScenarioLifecycle.BLOCKED, reason="; ".join(blockers))
        self.transition(attempt, ScenarioLifecycle.READY)
        if definition.owner_participation_required and not owner_action_acknowledged:
            return self.transition(
                attempt,
                ScenarioLifecycle.OWNER_ACTION_REQUIRED,
                reason="explicit owner action is required; no step was simulated",
            )
        self.transition(attempt, ScenarioLifecycle.RUNNING)
        try:
            for step in definition.automated_steps:
                executor = step_executors.get(step.step_id)
                if executor is None:
                    raise ScenarioError(f"no executor supplied for step: {step.step_id}")
                if step.may_send_input and (
                    authorization_check is None or not authorization_check(step)
                ):
                    raise ScenarioError(f"input step is not authorized: {step.step_id}")
                executor()
                attempt.history.append(
                    {"at": datetime.now(timezone.utc).isoformat(), "step_id": step.step_id, "state": "step_completed"}
                )
                self._persist(attempt)
            self.transition(attempt, ScenarioLifecycle.CLEANUP_PENDING)
            self.cleanup(attempt, cleanup_action)
            if attempt.state is ScenarioLifecycle.RETAINED_FOR_REVIEW:
                return attempt
            return self.transition(attempt, definition.expected_terminal_state)
        except Exception as exc:
            attempt.failure = str(exc)
            attempt.failure_details.append(_exception_record(exc, phase="execution"))
            self.transition(attempt, ScenarioLifecycle.CLEANUP_PENDING, reason=attempt.failure)
            self.cleanup(attempt, cleanup_action)
            if attempt.state is not ScenarioLifecycle.RETAINED_FOR_REVIEW:
                self.transition(attempt, ScenarioLifecycle.FAILED, reason=attempt.failure)
            return attempt

    def resume(self, attempt: ScenarioAttempt, *, explicitly_safe: bool) -> ScenarioAttempt:
        if attempt.state is not ScenarioLifecycle.OWNER_ACTION_REQUIRED:
            raise ScenarioError("only an owner-action pause can be considered for resume")
        if not explicitly_safe:
            raise ScenarioError("resume was not explicitly proven safe")
        return self.transition(attempt, ScenarioLifecycle.READY, reason="explicit safe resume requested")

    def create_attempt(self, definition: ScenarioDefinition, source_identity: Mapping[str, str]) -> ScenarioAttempt:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        attempt_id = f"{definition.scenario_id}-{stamp}-{secrets.token_hex(4)}"
        attempt = ScenarioAttempt(
            attempt_id=attempt_id,
            scenario_id=definition.scenario_id,
            scenario_version=definition.version,
            evidence_classification=definition.evidence_classification.value,
            source_identity=dict(source_identity),
        )
        self._persist(attempt, exclusive=True)
        return attempt

    def retry(self, failed: ScenarioAttempt, definition: ScenarioDefinition) -> ScenarioAttempt:
        if failed.state.value not in definition.retry_policy.retryable_terminal_states:
            raise ScenarioError(f"attempt state {failed.state.value} is not retryable")
        source = {**failed.source_identity, "retry_of": failed.attempt_id}
        return self.create_attempt(definition, source)

    def transition(self, attempt: ScenarioAttempt, target: ScenarioLifecycle, *, reason: str | None = None) -> ScenarioAttempt:
        if attempt.state is target:
            return attempt
        if attempt.state in TERMINAL_STATES:
            raise ScenarioError("terminal attempts are immutable; create a retry attempt")
        if target not in ALLOWED_TRANSITIONS.get(attempt.state, frozenset()):
            raise ScenarioError(f"invalid scenario transition: {attempt.state.value} -> {target.value}")
        if target is ScenarioLifecycle.COMPLETED and attempt.failure:
            raise ScenarioError("a failed step prevents a completion claim")
        attempt.state = target
        attempt.history.append({"at": datetime.now(timezone.utc).isoformat(), "state": target.value, "reason": reason})
        if target in TERMINAL_STATES:
            attempt.failure = reason if target is not ScenarioLifecycle.COMPLETED else None
        self._persist(attempt)
        return attempt

    def cleanup(self, attempt: ScenarioAttempt, cleanup: Callable[[], None]) -> ScenarioAttempt:
        if attempt.cleanup_complete:
            return attempt
        try:
            cleanup()
            attempt.cleanup_complete = True
            attempt.history.append({"at": datetime.now(timezone.utc).isoformat(), "state": "cleanup_complete"})
        except Exception as exc:
            attempt.failure = f"cleanup failure: {exc}"
            attempt.failure_details.append(_exception_record(exc, phase="cleanup"))
            attempt.state = ScenarioLifecycle.RETAINED_FOR_REVIEW
            attempt.history.append({"at": datetime.now(timezone.utc).isoformat(), "state": attempt.state.value, "reason": attempt.failure})
        self._persist(attempt)
        return attempt

    def cancel(self, attempt: ScenarioAttempt, neutralize: Callable[[], None]) -> ScenarioAttempt:
        neutralize()
        if attempt.state is ScenarioLifecycle.RUNNING:
            self.transition(attempt, ScenarioLifecycle.CLEANUP_PENDING, reason="cancellation requested")
            attempt.cleanup_complete = True
            self._persist(attempt)
        return self.transition(attempt, ScenarioLifecycle.CANCELLED, reason="local cancellation after neutralization")

    def reconcile_artifacts(
        self, definition: ScenarioDefinition, artifacts: Mapping[str, Path]
    ) -> dict[str, Any]:
        records: dict[str, Any] = {}
        missing: list[str] = []
        for requirement in definition.artifact_requirements:
            path = artifacts.get(requirement)
            if path is None or not path.is_file():
                missing.append(requirement)
                continue
            records[requirement] = {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        return {
            "schema_version": "game-companion-artifact-reconciliation/v1",
            "scenario_id": definition.scenario_id,
            "scenario_version": definition.version,
            "complete": not missing,
            "missing": missing,
            "artifacts": records,
        }

    @staticmethod
    def classified_report(
        definition: ScenarioDefinition,
        attempt: ScenarioAttempt,
        reconciliation: Mapping[str, Any],
    ) -> dict[str, Any]:
        completed = attempt.state is ScenarioLifecycle.COMPLETED and bool(reconciliation.get("complete"))
        return {
            "schema_version": "game-companion-scenario-report/v1",
            "scenario_id": definition.scenario_id,
            "scenario_version": definition.version,
            "attempt_id": attempt.attempt_id,
            "terminal_state": attempt.state.value,
            "technical_scenario_completed": completed,
            "evidence_classification": attempt.evidence_classification,
            "may_count_toward_reliability": completed and definition.may_count_toward_reliability,
            "may_count_toward_owner_acceptance": completed and definition.may_count_toward_owner_acceptance,
            "owner_usefulness": "unknown unless explicit owner feedback event exists",
            "authoritative_game_outcome": "unknown unless separately reconciled game-owned evidence exists",
            "reconciliation": dict(reconciliation),
        }

    def _persist(self, attempt: ScenarioAttempt, *, exclusive: bool = False) -> None:
        directory = self.root / attempt.scenario_id / attempt.attempt_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "attempt.json"
        payload = {
            "schema_version": ATTEMPT_SCHEMA_VERSION,
            "attempt_id": attempt.attempt_id,
            "scenario_id": attempt.scenario_id,
            "scenario_version": attempt.scenario_version,
            "evidence_classification": attempt.evidence_classification,
            "source_identity": dict(attempt.source_identity),
            "state": attempt.state.value,
            "created_at": attempt.created_at,
            "history": attempt.history,
            "failure": attempt.failure,
            "failure_details": attempt.failure_details,
            "cleanup_complete": attempt.cleanup_complete,
        }
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        if exclusive:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            return
        temporary = target.with_suffix(f".{secrets.token_hex(4)}.tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, target)


def _exception_record(exc: Exception, *, phase: str) -> dict[str, str]:
    return {
        "phase": phase,
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scenario_classification_hash(scenarios: Iterable[ScenarioDefinition]) -> str:
    payload = [
        {
            "identity": item.identity,
            "classification": item.classification.value,
            "evidence_classification": item.evidence_classification.value,
            "execution_classification": item.execution_classification,
            "capability_status": item.capability_status,
            "capability_requirements": item.capability_requirements,
            "required_fixtures": item.required_fixtures,
            "required_local_assets": item.required_local_assets,
            "implementation_evidence": item.implementation_evidence,
            "safety_requirements": item.safety_requirements,
            "owner_participation_required": item.owner_participation_required,
            "may_count_toward_reliability": item.may_count_toward_reliability,
            "may_count_toward_owner_acceptance": item.may_count_toward_owner_acceptance,
            "visible_live_proof": item.visible_live_proof,
            "authoritative_game_outcome": item.authoritative_game_outcome,
        }
        for item in sorted(scenarios, key=lambda scenario: scenario.identity)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def campaign_contract_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in AUTHORITATIVE_CAMPAIGN_CONTRACTS:
        path = repository_path(relative)
        if not path.is_file() or path.is_symlink():
            raise ScenarioError(f"campaign contract must be a regular non-symlinked file: {relative}")
        hashes[relative] = _sha256_file(path)
    return hashes


def _campaign_completion_phase_blockers() -> list[dict[str, str]]:
    contract = yaml.safe_load(
        repository_path("data/scenarios/final-campaign.yaml").read_text(encoding="utf-8")
    )
    phases = contract.get("phases") if isinstance(contract, Mapping) else None
    if not isinstance(phases, list):
        raise ScenarioError("final campaign phases are missing")
    blockers: list[dict[str, str]] = []
    for phase in phases:
        if not isinstance(phase, Mapping) or not isinstance(phase.get("id"), str):
            raise ScenarioError("final campaign phase identity is invalid")
        if phase["id"] == "deterministic_contracts":
            continue
        blockers.append(
            {
                "phase": str(phase["id"]),
                "reason": "required campaign phase has not run",
            }
        )
    return blockers


def _owner_fields_blank() -> bool:
    mario = yaml.safe_load(repository_path("data/scenarios/mario-owner-pilot.yaml").read_text(encoding="utf-8"))
    stardew = yaml.safe_load(repository_path("data/scenarios/stardew-owner-pilot.yaml").read_text(encoding="utf-8"))
    mario_values = tuple((mario.get("owner_feedback") or {}).values()) + tuple(
        (mario.get("owner_acceptance") or {}).values()
    )
    stardew_values = tuple((stardew.get("owner_feedback") or {}).values()) + tuple(
        (stardew.get("owner_acceptance") or {}).values()
    )
    return bool(mario_values) and all(value == "OWNER_TO_COMPLETE" for value in mario_values) and bool(
        stardew_values
    ) and all(value is None for value in stardew_values)


def _git_value(*args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=repository_path("."),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ScenarioError(f"cannot resolve candidate Git identity: {exc.stderr.strip()}") from exc
    return completed.stdout.strip()


def build_campaign_entry_manifest(
    catalog: Iterable[ScenarioDefinition],
    *,
    focused_readiness_total: int,
    focused_v2_total: int,
    canonical_total: int,
) -> dict[str, Any]:
    scenarios = tuple(sorted(catalog, key=lambda scenario: scenario.identity))
    if min(focused_readiness_total, focused_v2_total, canonical_total) <= 0:
        raise ScenarioError("candidate manifest requires positive deterministic test totals")
    dirty = _git_value("status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise ScenarioError("candidate manifest requires a clean repository")
    if not _owner_fields_blank():
        raise ScenarioError("candidate manifest requires every owner response and acceptance field to be blank")
    return {
        "schema_version": CAMPAIGN_ENTRY_MANIFEST_SCHEMA_VERSION,
        "source_commit": _git_value("rev-parse", "HEAD"),
        "source_tree": _git_value("rev-parse", "HEAD^{tree}"),
        "repository_clean": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classification_hash": scenario_classification_hash(scenarios),
        "contract_hashes": campaign_contract_hashes(),
        "deterministic_evidence": {
            "focused_readiness": {"status": "passed", "test_total": focused_readiness_total},
            "focused_v2": {"status": "passed", "test_total": focused_v2_total},
            "canonical_non_live": {"status": "passed", "test_total": canonical_total},
        },
        "owner_fields_blank": True,
        "owner_fields_source": [
            "data/scenarios/mario-owner-pilot.yaml",
            "data/scenarios/stardew-owner-pilot.yaml",
        ],
        "campaign_completion": "pending",
        "proof_limits": list(PROOF_LIMITS),
    }


def write_campaign_entry_manifest(payload: Mapping[str, Any], path: Path) -> Path:
    root = repository_path("artifacts/campaigns").resolve()
    target = repository_path(path).resolve()
    if target.parent != root and root not in target.parents:
        raise ScenarioError("candidate manifest must remain under artifacts/campaigns")
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(payload), indent=2, sort_keys=True).encode("utf-8") + b"\n"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return target


def load_campaign_entry_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ScenarioError("candidate manifest must be a regular non-symlinked file")
    if path.stat().st_size > CAMPAIGN_ENTRY_MANIFEST_MAX_BYTES:
        raise ScenarioError("candidate manifest exceeds the 262144-byte limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read candidate manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != CAMPAIGN_ENTRY_MANIFEST_SCHEMA_VERSION:
        raise ScenarioError("unsupported candidate manifest schema")
    return payload


def _candidate_manifest_blockers(
    manifest: Mapping[str, Any] | None,
    scenarios: tuple[ScenarioDefinition, ...],
    *,
    verify_candidate_identity: bool,
) -> list[dict[str, str]]:
    if manifest is None:
        return [{"id": "candidate_manifest", "reason": "missing candidate-bound campaign-entry manifest"}]
    blockers: list[dict[str, str]] = []
    required_fields = {
        "schema_version",
        "source_commit",
        "source_tree",
        "repository_clean",
        "created_at",
        "classification_hash",
        "contract_hashes",
        "deterministic_evidence",
        "owner_fields_blank",
        "owner_fields_source",
        "campaign_completion",
        "proof_limits",
    }
    if set(manifest) != required_fields:
        blockers.append({"id": "candidate_manifest.fields", "reason": "manifest fields do not match the v1 schema"})
    if manifest.get("schema_version") != CAMPAIGN_ENTRY_MANIFEST_SCHEMA_VERSION:
        blockers.append({"id": "candidate_manifest.schema", "reason": "unsupported manifest schema"})
    commit = str(manifest.get("source_commit", ""))
    tree = str(manifest.get("source_tree", ""))
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        blockers.append({"id": "candidate_identity.commit", "reason": "missing exact 40-character commit"})
    if len(tree) != 40 or any(character not in "0123456789abcdef" for character in tree):
        blockers.append({"id": "candidate_identity.tree", "reason": "missing exact 40-character Git tree"})
    if manifest.get("repository_clean") is not True:
        blockers.append({"id": "candidate_identity.clean", "reason": "candidate was not frozen clean"})
    if manifest.get("owner_fields_blank") is not True or not _owner_fields_blank():
        blockers.append({"id": "owner_fields", "reason": "owner response or acceptance fields are not guaranteed blank"})
    if manifest.get("owner_fields_source") != [
        "data/scenarios/mario-owner-pilot.yaml",
        "data/scenarios/stardew-owner-pilot.yaml",
    ]:
        blockers.append({"id": "owner_fields.source", "reason": "owner field sources are incomplete"})
    if manifest.get("campaign_completion") != "pending":
        blockers.append({"id": "campaign_completion", "reason": "campaign completion must begin pending"})
    if manifest.get("proof_limits") != list(PROOF_LIMITS):
        blockers.append({"id": "proof_limits", "reason": "candidate proof limits do not match"})
    if manifest.get("classification_hash") != scenario_classification_hash(scenarios):
        blockers.append({"id": "classification_hash", "reason": "scenario classification hash mismatch"})
    try:
        expected_hashes = campaign_contract_hashes()
    except ScenarioError as exc:
        blockers.append({"id": "campaign_contracts", "reason": str(exc)})
    else:
        if manifest.get("contract_hashes") != expected_hashes:
            blockers.append({"id": "campaign_contracts", "reason": "candidate contract hashes do not match"})
    evidence = manifest.get("deterministic_evidence")
    if not isinstance(evidence, Mapping):
        blockers.append({"id": "deterministic_evidence", "reason": "deterministic gate evidence is missing"})
    else:
        for gate in ("focused_readiness", "focused_v2", "canonical_non_live"):
            record = evidence.get(gate)
            if not isinstance(record, Mapping) or record.get("status") != "passed" or not isinstance(
                record.get("test_total"), int
            ) or int(record["test_total"]) <= 0:
                blockers.append({"id": f"deterministic_evidence.{gate}", "reason": "passed status and positive total required"})
    if verify_candidate_identity and not blockers:
        if _git_value("rev-parse", "HEAD") != commit:
            blockers.append({"id": "candidate_identity.commit", "reason": "manifest does not match HEAD"})
        if _git_value("rev-parse", "HEAD^{tree}") != tree:
            blockers.append({"id": "candidate_identity.tree", "reason": "manifest does not match the current Git tree"})
        if _git_value("status", "--porcelain", "--untracked-files=all"):
            blockers.append({"id": "candidate_identity.clean", "reason": "repository is not clean"})
    return blockers


def final_campaign_readiness(
    catalog: Iterable[ScenarioDefinition],
    candidate_manifest: Mapping[str, Any] | None = None,
    *,
    verify_candidate_identity: bool = False,
) -> dict[str, Any]:
    scenarios = tuple(sorted(catalog, key=lambda scenario: scenario.identity))
    implementation_blockers: list[dict[str, str]] = []
    candidate_blockers: list[dict[str, str]] = []
    for scenario in scenarios:
        if scenario.capability_status in IMPLEMENTATION_BLOCKING_STATUSES:
            implementation_blockers.append(
                {"scenario": scenario.identity, "reason": scenario.capability_status}
            )
        if scenario.capability_status in SCHEDULED_VALIDATION_STATUSES and not scenario.safety_requirements:
            implementation_blockers.append(
                {"scenario": scenario.identity, "reason": "missing campaign safety requirements"}
            )
        if scenario.capability_status in SCHEDULED_VALIDATION_STATUSES and not scenario.implementation_evidence:
            implementation_blockers.append(
                {"scenario": scenario.identity, "reason": "missing implementation evidence"}
            )
        for evidence_path in scenario.implementation_evidence:
            evidence = repository_path(evidence_path)
            if not evidence.is_file() or evidence.is_symlink():
                implementation_blockers.append(
                    {"scenario": scenario.identity, "reason": f"missing implementation evidence: {evidence_path}"}
                )
        if scenario.capability_status in CANDIDATE_BLOCKING_STATUSES:
            candidate_blockers.append(
                {"scenario": scenario.identity, "reason": scenario.capability_status}
            )
        for fixture_path in scenario.required_fixtures:
            fixture = repository_path(fixture_path)
            if not fixture.is_file() or fixture.is_symlink():
                candidate_blockers.append(
                    {"scenario": scenario.identity, "reason": f"missing fixture: {fixture_path}"}
                )
        for asset_path in scenario.required_local_assets:
            asset = repository_path(asset_path)
            if not asset.exists():
                candidate_blockers.append(
                    {"scenario": scenario.identity, "reason": f"missing local asset: {asset_path}"}
                )
    candidate_blockers.extend(
        _candidate_manifest_blockers(
            candidate_manifest,
            scenarios,
            verify_candidate_identity=verify_candidate_identity,
        )
    )
    scheduled = [
        {
            "scenario": item.identity,
            "status": item.capability_status,
            "classification": item.classification.value,
            "proof_status": "pending",
        }
        for item in scenarios
        if item.capability_status != "completed_accepted"
        and item.classification
        in {
            ScenarioClassification.VISIBLE_TECHNICAL,
            ScenarioClassification.RELIABILITY,
            ScenarioClassification.REVIEW_ONLY,
            ScenarioClassification.UNATTENDED_REGRESSION,
        }
    ]
    owner_actions = [
        {
            "scenario": item.identity,
            "status": item.capability_status,
            "entry_blocker": False,
            "completion_required": True,
        }
        for item in scenarios
        if item.owner_participation_required
    ]
    implementation_ready = not implementation_blockers
    campaign_entry_ready = implementation_ready and not candidate_blockers
    completion_blockers = _campaign_completion_phase_blockers() + [
        {"scenario": item["scenario"], "reason": "scheduled technical validation has not run"}
        for item in scheduled
    ] + [
        {"scenario": item["scenario"], "reason": "required owner action has not occurred"}
        for item in owner_actions
    ]
    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "scenario_count": len(scenarios),
        "implementation_readiness": {
            "ready": implementation_ready,
            "blockers": implementation_blockers,
        },
        "campaign_entry_readiness": {
            "ready": campaign_entry_ready,
            "blockers": candidate_blockers,
        },
        "campaign_completion": {
            "complete": False,
            "blockers": completion_blockers,
        },
        "implementation_blockers": implementation_blockers,
        "candidate_blockers": candidate_blockers,
        "scheduled_technical_validations": scheduled,
        "required_owner_actions": owner_actions,
        "completion_blockers": completion_blockers,
        "proof_limits": list(PROOF_LIMITS),
        "campaign_entry_ready": campaign_entry_ready,
        "campaign_complete": False,
        "classification_hash": scenario_classification_hash(scenarios),
        "candidate_commit": candidate_manifest.get("source_commit") if candidate_manifest else None,
    }
