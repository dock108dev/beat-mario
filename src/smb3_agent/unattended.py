from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import time
import traceback
from typing import Any, Mapping, Protocol, Sequence

from smb3_agent.scenarios import (
    EvidenceClassification,
    ScenarioClassification,
    ScenarioDefinition,
)
from smb3_agent.fceux_harness import parse_fceux_log
from smb3_agent.goals import evaluate_success_metrics, load_goal_contract, resolve_goal_path
from smb3_agent.presets import environment_for_preset


RUNNER_VERSION = "game-companion-unattended-runner/v1"
MANIFEST_SCHEMA = "game-companion-unattended-attempt/v1"
REPORT_SCHEMA = "game-companion-unattended-repeatability/v1"
CLASSIFICATION = "unattended_regression"
EVIDENCE_CLASSIFICATION = "unattended_regression_result"
ACKNOWLEDGEMENT = "I_UNDERSTAND_UNATTENDED_REGRESSION_ONLY"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/unattended-regression")
SAFE_ENVIRONMENT_KEYS = frozenset(
    {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "DISPLAY"}
)
PROOF_LIMITS = (
    "technical regression behavior and repeatability only",
    "not visible player proof",
    "not review-only Show evidence",
    "not route reliability acceptance",
    "not authoritative game completion",
    "not owner usefulness or owner acceptance",
    "not a replacement for the consolidated campaign",
)


class UnattendedError(ValueError):
    pass


class AttemptLifecycle(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CLEANUP_PENDING = "cleanup_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    RETAINED = "retained_for_review"


@dataclass(frozen=True)
class AssetIdentity:
    role: str
    path: str
    sha256: str
    byte_count: int
    sensitive: bool = True

    @classmethod
    def inspect(cls, role: str, path: Path, *, sensitive: bool = True) -> AssetIdentity:
        safe = require_existing_safe_path(path, kind=role)
        if not safe.is_file():
            raise UnattendedError(f"{role} must be a regular file")
        digest = hashlib.sha256()
        byte_count = 0
        with safe.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                byte_count += len(chunk)
        return cls(role, str(safe), digest.hexdigest(), byte_count, sensitive)


@dataclass(frozen=True)
class FixtureIdentity:
    fixture_id: str
    source_path: str
    source_sha256: str
    disposable_copy_required: bool
    owner_primary: bool = False


@dataclass(frozen=True)
class DisplayIdentity:
    provider_id: str
    backend: str
    identity: str
    available: bool
    renders_pixels: bool
    visible_to_player: bool
    diagnostic: str


class DisplayProvider(Protocol):
    def inspect(self) -> DisplayIdentity: ...

    def continuity_ok(self, frozen: DisplayIdentity) -> bool: ...


@dataclass(frozen=True)
class DeclaredDisplayProvider:
    provider_id: str
    backend: str
    identity: str
    available: bool
    renders_pixels: bool
    visible_to_player: bool = False
    diagnostic: str = "operator-declared local display"

    def inspect(self) -> DisplayIdentity:
        return DisplayIdentity(
            self.provider_id,
            self.backend,
            self.identity,
            self.available,
            self.renders_pixels,
            self.visible_to_player,
            self.diagnostic,
        )

    def continuity_ok(self, frozen: DisplayIdentity) -> bool:
        return self.inspect() == frozen and frozen.available and frozen.renders_pixels


@dataclass(frozen=True)
class NoDisplayProvider:
    reason: str = "no supported local display is configured"

    def inspect(self) -> DisplayIdentity:
        return DisplayIdentity("none", "none", "unavailable", False, False, False, self.reason)

    def continuity_ok(self, frozen: DisplayIdentity) -> bool:
        return False


@dataclass(frozen=True)
class ProbedDisplayProvider:
    provider_id: str
    backend: str
    identity: str
    probe_executable: str
    probe_arguments: tuple[str, ...] = ()
    visible_to_player: bool = False

    def inspect(self) -> DisplayIdentity:
        try:
            completed = subprocess.run(
                [self.probe_executable, *self.probe_arguments],
                check=False,
                capture_output=True,
                timeout=5,
                env=sanitize_environment({"PATH": os.environ.get("PATH", ""), "DISPLAY": os.environ.get("DISPLAY", "")}),
            )
            available = completed.returncode == 0
            diagnostic = f"probe_exit={completed.returncode};output_sha256={hashlib.sha256(completed.stdout).hexdigest()}"
        except (OSError, subprocess.SubprocessError) as exc:
            available = False
            diagnostic = f"probe_failed:{type(exc).__name__}"
        return DisplayIdentity(self.provider_id, self.backend, self.identity, available, available, self.visible_to_player, diagnostic)

    def continuity_ok(self, frozen: DisplayIdentity) -> bool:
        current = self.inspect()
        return (
            current.provider_id == frozen.provider_id
            and current.backend == frozen.backend
            and current.identity == frozen.identity
            and current.available
            and current.renders_pixels
        )


@dataclass(frozen=True)
class ProviderRunPlan:
    adapter_id: str
    adapter_version: str
    game_id: str
    executable: str
    arguments: tuple[str, ...]
    assets: tuple[AssetIdentity, ...]
    fixture: FixtureIdentity | None
    environment: Mapping[str, str]
    protected_data: tuple[str, ...]
    protected_actions: tuple[str, ...]
    expected_milestones: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    cleanup_policy: tuple[str, ...]
    evidence_contract_version: str
    observation_backend: str
    input_backend: str
    network_access_allowed: bool = False


@dataclass(frozen=True)
class RunResult:
    run_number: int
    lifecycle: str
    exit_status: int | None
    elapsed_seconds: float
    timed_out: bool
    cancelled: bool
    failure_classification: str | None
    last_good_milestone: str | None
    first_missing_requirement: str | None
    event_hash: str | None
    outcome_hash: str | None
    resource_deltas: Mapping[str, int | float | str]
    state_deltas: Mapping[str, int | float | str]
    artifact_complete: bool
    cleanup_complete: bool
    unknowns: tuple[str, ...]
    exception: Mapping[str, str] | None = None
    cleanup_exception: Mapping[str, str] | None = None


class UnattendedProvider(Protocol):
    @property
    def adapter_id(self) -> str: ...

    def capability(self) -> Mapping[str, Any]: ...

    def plan(self, *, run_root: Path | None = None) -> ProviderRunPlan: ...

    def prepare_run(self, run_root: Path, plan: ProviderRunPlan) -> ProviderRunPlan: ...

    def evaluate(self, run_root: Path, exit_status: int | None) -> RunResult: ...

    def cleanup(self, run_root: Path) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class AttemptManifest:
    schema_version: str
    attempt_id: str
    correlation_id: str
    causation_id: str
    created_at: str
    source_commit: str
    source_dirty: bool
    source_dirty_fingerprint: str
    adapter_id: str
    adapter_version: str
    game_id: str
    scenario_id: str
    scenario_version: str
    goal_version: str
    profile_version: str
    solution_version: str
    runner_version: str
    classification: str
    evidence_classification: str
    execution_classification: str
    may_count_toward_reliability: bool
    may_count_toward_owner_acceptance: bool
    visible_live_proof: bool
    authoritative_game_outcome: bool
    network_access_allowed: bool
    assets: tuple[AssetIdentity, ...]
    fixture: FixtureIdentity | None
    display: DisplayIdentity
    executable: str
    arguments: tuple[str, ...]
    sanitized_environment: Mapping[str, str]
    environment_allowlist: tuple[str, ...]
    run_count: int
    per_run_timeout_seconds: int
    aggregate_timeout_seconds: int
    concurrency: int
    cleanup_policy: tuple[str, ...]
    artifact_root: str
    workspace_root: str
    process_root: str
    protected_data: tuple[str, ...]
    protected_actions: tuple[str, ...]
    expected_milestones: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    observation_backend: str
    input_backend: str
    evidence_contract_version: str
    proof_limits: tuple[str, ...]
    correlation_reference: str | None = None
    manifest_sha256: str = field(default="")

    def __post_init__(self) -> None:
        immutable = {
            "classification": CLASSIFICATION,
            "evidence_classification": EVIDENCE_CLASSIFICATION,
            "execution_classification": CLASSIFICATION,
            "may_count_toward_reliability": False,
            "may_count_toward_owner_acceptance": False,
            "visible_live_proof": False,
            "authoritative_game_outcome": False,
            "network_access_allowed": False,
        }
        for name, expected in immutable.items():
            if getattr(self, name) != expected:
                raise UnattendedError(f"immutable unattended field {name} must be {expected!r}")
        if self.schema_version != MANIFEST_SCHEMA or self.runner_version != RUNNER_VERSION:
            raise UnattendedError("unsupported unattended manifest or runner version")
        if self.proof_limits != PROOF_LIMITS:
            raise UnattendedError("unattended proof limits are immutable")
        required_text = (
            self.attempt_id, self.correlation_id, self.causation_id,
            self.source_commit, self.source_dirty_fingerprint,
            self.adapter_id, self.adapter_version, self.game_id,
            self.scenario_id, self.scenario_version, self.goal_version,
            self.profile_version, self.solution_version, self.executable,
            self.artifact_root, self.workspace_root, self.process_root,
            self.evidence_contract_version, self.observation_backend, self.input_backend,
        )
        if any(not value for value in required_text):
            raise UnattendedError("unattended manifest is incomplete")
        if not self.cleanup_policy or not self.protected_data or not self.expected_outputs:
            raise UnattendedError("cleanup, protected-data, and expected-output declarations are required")
        if self.concurrency != 1:
            raise UnattendedError("V2.13 concurrency is bounded to sequential execution (1)")
        if self.run_count < 1 or self.run_count > 20:
            raise UnattendedError("run count must be between 1 and 20")
        if self.per_run_timeout_seconds < 1 or self.aggregate_timeout_seconds < self.per_run_timeout_seconds:
            raise UnattendedError("timeouts must be positive and aggregate must cover one run")
        expected_hash = hash_payload(self.to_dict(include_hash=False))
        if self.manifest_sha256 and self.manifest_sha256 != expected_hash:
            raise UnattendedError("attempt manifest integrity mismatch")

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_hash:
            payload.pop("manifest_sha256", None)
        return payload

    def with_hash(self) -> AttemptManifest:
        payload = self.to_dict(include_hash=False)
        return replace(self, manifest_sha256=hash_payload(payload))

    def compatibility_key(self) -> tuple[Any, ...]:
        return (
            self.adapter_id,
            self.adapter_version,
            self.scenario_id,
            self.scenario_version,
            self.goal_version,
            self.profile_version,
            self.solution_version,
            self.source_dirty_fingerprint,
            tuple((item.role, item.sha256) for item in self.assets),
            asdict(self.fixture) if self.fixture else None,
            asdict(self.display),
            tuple(sorted(self.sanitized_environment.items())),
            self.runner_version,
            self.evidence_contract_version,
        )


@dataclass(frozen=True)
class AttemptPlan:
    manifest: AttemptManifest
    blockers: tuple[str, ...]
    side_effect_free: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "game-companion-unattended-plan/v1",
            "eligible": not self.blockers,
            "blockers": list(self.blockers),
            "side_effect_free": self.side_effect_free,
            "manifest_preview": self.manifest.to_dict(),
        }


class UnattendedRunner:
    def __init__(
        self,
        providers: Sequence[UnattendedProvider],
        displays: Sequence[DisplayProvider],
        *,
        artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
        repo_root: Path = Path("."),
    ) -> None:
        self.providers = {provider.adapter_id: provider for provider in providers}
        self.displays = {provider.inspect().provider_id: provider for provider in displays}
        if len(self.providers) != len(providers) or len(self.displays) != len(displays):
            raise UnattendedError("provider identities must be unique")
        self.artifact_root = require_safe_output_path(artifact_root, kind="artifact root")
        self.repo_root = require_existing_safe_path(repo_root, kind="source repository")

    def capability_status(self) -> dict[str, Any]:
        return {
            "schema_version": "game-companion-unattended-capabilities/v1",
            "classification": CLASSIFICATION,
            "proof_limits": list(PROOF_LIMITS),
            "adapters": [dict(provider.capability()) for provider in self.providers.values()],
            "displays": [asdict(provider.inspect()) for provider in self.displays.values()],
        }

    def plan(
        self,
        scenario: ScenarioDefinition,
        *,
        adapter_id: str,
        display_provider_id: str,
        source_identity: Mapping[str, Any],
        goal_version: str,
        profile_version: str,
        solution_version: str,
        run_count: int = 1,
        per_run_timeout_seconds: int = 300,
        aggregate_timeout_seconds: int = 600,
        concurrency: int = 1,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        correlation_reference: str | None = None,
        requested_promotion: str | None = None,
    ) -> AttemptPlan:
        provider = self.providers.get(adapter_id)
        display_provider = self.displays.get(display_provider_id)
        blockers = list(eligibility_blockers(scenario, requested_promotion=requested_promotion))
        if provider is None:
            raise UnattendedError(f"unknown or unavailable unattended adapter: {adapter_id}")
        if display_provider is None:
            raise UnattendedError(f"unsupported display provider: {display_provider_id}")
        provider_plan = provider.plan()
        display = display_provider.inspect()
        if not display.available or not display.renders_pixels:
            blockers.append("declared display does not provide continuously observable rendered pixels")
        if not source_identity.get("commit") or not source_identity.get("dirty_fingerprint"):
            blockers.append("missing or stale release/source identity")
        if not provider_plan.cleanup_policy or not provider_plan.protected_data:
            blockers.append("ambiguous cleanup or protected-data ownership")
        environment = sanitize_environment(provider_plan.environment)
        attempt_id = new_attempt_id(scenario.scenario_id)
        attempt_root = require_safe_output_path(self.artifact_root / attempt_id, kind="attempt root")
        manifest = AttemptManifest(
            schema_version=MANIFEST_SCHEMA,
            attempt_id=attempt_id,
            correlation_id=correlation_id or secrets.token_hex(16),
            causation_id=causation_id or secrets.token_hex(16),
            created_at=utc_now(),
            source_commit=str(source_identity.get("commit", "")),
            source_dirty=bool(source_identity.get("dirty", False)),
            source_dirty_fingerprint=str(source_identity.get("dirty_fingerprint", "")),
            adapter_id=provider_plan.adapter_id,
            adapter_version=provider_plan.adapter_version,
            game_id=provider_plan.game_id,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            goal_version=goal_version,
            profile_version=profile_version,
            solution_version=solution_version,
            runner_version=RUNNER_VERSION,
            classification=CLASSIFICATION,
            evidence_classification=EVIDENCE_CLASSIFICATION,
            execution_classification=CLASSIFICATION,
            may_count_toward_reliability=False,
            may_count_toward_owner_acceptance=False,
            visible_live_proof=False,
            authoritative_game_outcome=False,
            network_access_allowed=provider_plan.network_access_allowed,
            assets=provider_plan.assets,
            fixture=provider_plan.fixture,
            display=display,
            executable=provider_plan.executable,
            arguments=provider_plan.arguments,
            sanitized_environment=environment,
            environment_allowlist=tuple(sorted(environment)),
            run_count=run_count,
            per_run_timeout_seconds=per_run_timeout_seconds,
            aggregate_timeout_seconds=aggregate_timeout_seconds,
            concurrency=concurrency,
            cleanup_policy=provider_plan.cleanup_policy,
            artifact_root=str(attempt_root),
            workspace_root=str(attempt_root / "workspaces"),
            process_root=str(attempt_root / "processes"),
            protected_data=provider_plan.protected_data,
            protected_actions=provider_plan.protected_actions,
            expected_milestones=provider_plan.expected_milestones,
            expected_outputs=provider_plan.expected_outputs,
            observation_backend=provider_plan.observation_backend,
            input_backend=provider_plan.input_backend,
            evidence_contract_version=provider_plan.evidence_contract_version,
            proof_limits=PROOF_LIMITS,
            correlation_reference=correlation_reference,
        ).with_hash()
        return AttemptPlan(manifest, tuple(blockers))

    def create_attempt(self, plan: AttemptPlan) -> Path:
        if plan.blockers:
            raise UnattendedError("attempt is ineligible: " + "; ".join(plan.blockers))
        current_source = source_identity(self.repo_root)
        if (
            current_source["commit"] != plan.manifest.source_commit
            or current_source["dirty"] != plan.manifest.source_dirty
            or current_source["dirty_fingerprint"] != plan.manifest.source_dirty_fingerprint
        ):
            raise UnattendedError("release/source identity became stale; create a new plan and attempt")
        root = Path(plan.manifest.artifact_root)
        root.mkdir(parents=True, exist_ok=False)
        Path(plan.manifest.workspace_root).mkdir(parents=False, exist_ok=False)
        Path(plan.manifest.process_root).mkdir(parents=False, exist_ok=False)
        write_json_exclusive(root / "manifest.json", plan.manifest.to_dict())
        write_json_exclusive(root / "invocation.json", {
            "argument_vector": [plan.manifest.executable, *plan.manifest.arguments],
            "shell": False,
            "acknowledgement_required": ACKNOWLEDGEMENT,
            "classification": CLASSIFICATION,
        })
        write_json_exclusive(root / "environment.json", {
            "allowlist": list(plan.manifest.environment_allowlist),
            "environment": dict(plan.manifest.sanitized_environment),
        })
        write_json_exclusive(root / "display.json", asdict(plan.manifest.display))
        write_json_exclusive(root / "status.json", status_payload(plan.manifest, AttemptLifecycle.READY))
        append_classified_event(root / "events.jsonl", plan.manifest, "unattended_attempt_created", {"lifecycle": "ready"})
        return root

    def execute(self, plan: AttemptPlan, *, acknowledgement: str) -> dict[str, Any]:
        if acknowledgement != ACKNOWLEDGEMENT:
            raise UnattendedError("exact regression-only acknowledgement is required")
        if plan.manifest.concurrency != 1:
            raise UnattendedError("V2.13 execution supports only sequential concurrency=1")
        attempt_root = self.create_attempt(plan)
        provider = self.providers[plan.manifest.adapter_id]
        display = self.displays[plan.manifest.display.provider_id]
        results: list[RunResult] = []
        aggregate_started = time.monotonic()
        write_json_replace(attempt_root / "status.json", status_payload(plan.manifest, AttemptLifecycle.RUNNING))
        for number in range(1, plan.manifest.run_count + 1):
            if (attempt_root / "cancel.requested").exists():
                results.append(cancelled_result(number, "cancelled before launch"))
                break
            if time.monotonic() - aggregate_started >= plan.manifest.aggregate_timeout_seconds:
                results.append(timed_out_result(number, "aggregate timeout before launch"))
                break
            run_root = Path(plan.manifest.workspace_root) / f"run_{number:02d}"
            run_root.mkdir(parents=False, exist_ok=False)
            try:
                run_plan = provider.prepare_run(run_root, provider.plan(run_root=run_root))
                result = self._execute_one(plan.manifest, run_plan, display, provider, run_root, number)
            except Exception as exc:
                cleanup_complete = False
                cleanup_exception: dict[str, str] | None = None
                try:
                    cleanup = provider.cleanup(run_root)
                    cleanup_complete = bool(cleanup.get("complete", False))
                except Exception as cleanup_exc:
                    cleanup_exception = exception_record(cleanup_exc, phase="cleanup")
                    cleanup = {"complete": False, "failure": f"{type(cleanup_exc).__name__}: {cleanup_exc}"}
                write_json_exclusive(run_root / "cleanup.json", cleanup)
                result = RunResult(
                    number, "failed", None, 0, False, False,
                    f"prelaunch_or_fixture_failure:{type(exc).__name__}",
                    None, str(exc), None, None, {}, {}, False, cleanup_complete,
                    (str(exc),),
                    exception=exception_record(exc, phase="prelaunch_or_fixture"),
                    cleanup_exception=cleanup_exception,
                )
            results.append(result)
            write_json_exclusive(run_root / "run_report.json", asdict(result))
        report = repeatability_report(plan.manifest, results)
        write_json_exclusive(attempt_root / "repeatability.json", report)
        integrity = artifact_integrity(attempt_root, exclude={"integrity.json"})
        write_json_exclusive(attempt_root / "integrity.json", integrity)
        terminal = AttemptLifecycle.COMPLETED if results and all(item.lifecycle == "passed" for item in results) else AttemptLifecycle.RETAINED
        write_json_replace(attempt_root / "status.json", status_payload(plan.manifest, terminal, first_missing=report["first_missing_requirement"]))
        return report

    def _execute_one(
        self,
        manifest: AttemptManifest,
        run_plan: ProviderRunPlan,
        display: DisplayProvider,
        provider: UnattendedProvider,
        run_root: Path,
        number: int,
    ) -> RunResult:
        stdout_path = run_root / "stdout.log"
        stderr_path = run_root / "stderr.log"
        process: subprocess.Popen[bytes] | None = None
        started = time.monotonic()
        exit_status: int | None = None
        failure: str | None = None
        cancelled = False
        timed_out = False
        cleanup_complete = False
        process_exception: dict[str, str] | None = None
        cleanup_exception: dict[str, str] | None = None
        display_diagnostics: list[Mapping[str, Any]] = []
        try:
            display_diagnostics.append({"at": utc_now(), **asdict(display.inspect()), "phase": "prelaunch"})
            if not display.continuity_ok(manifest.display):
                raise UnattendedError("display unavailable or identity changed before launch")
            with stdout_path.open("xb") as stdout_file, stderr_path.open("xb") as stderr_file:
                process = subprocess.Popen(
                    [run_plan.executable, *run_plan.arguments],
                    cwd=run_root,
                    env=sanitize_environment(run_plan.environment),
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True,
                    shell=False,
                )
                write_json_exclusive(Path(manifest.process_root) / f"run_{number:02d}.json", {"pid": process.pid, "owned_process_group": process.pid, "workspace": str(run_root)})
                append_classified_event(run_root / "events.jsonl", manifest, "process_started", {"pid": process.pid, "run_number": number})
                next_display_sample = 0.0
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    if elapsed >= next_display_sample:
                        display_diagnostics.append({"at": utc_now(), **asdict(display.inspect()), "phase": "running"})
                        next_display_sample = elapsed + 1.0
                    if (Path(manifest.artifact_root) / "cancel.requested").exists():
                        cancelled = True
                        failure = "cancelled"
                        terminate_owned_process(process)
                        break
                    if elapsed >= manifest.per_run_timeout_seconds:
                        timed_out = True
                        failure = "per_run_timeout"
                        terminate_owned_process(process)
                        break
                    if not display.continuity_ok(manifest.display):
                        failure = "display_loss"
                        terminate_owned_process(process)
                        break
                    time.sleep(0.05)
                exit_status = process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError, UnattendedError, KeyboardInterrupt) as exc:
            failure = failure or f"process_or_environment_loss:{type(exc).__name__}"
            process_exception = exception_record(exc, phase="process_or_environment")
            if process is not None and process.poll() is None:
                terminate_owned_process(process)
        finally:
            try:
                cleanup = provider.cleanup(run_root)
                cleanup_complete = bool(cleanup.get("complete", False))
            except Exception as exc:
                cleanup_exception = exception_record(exc, phase="cleanup")
                cleanup = {"complete": False, "failure": f"{type(exc).__name__}: {exc}"}
                cleanup_complete = False
            write_json_exclusive(run_root / "cleanup.json", cleanup)
            write_json_exclusive(run_root / "display-diagnostics.json", {"samples": display_diagnostics})
        evaluated = provider.evaluate(run_root, exit_status)
        if failure or not cleanup_complete:
            return RunResult(
                number,
                "cancelled" if cancelled else "timed_out" if timed_out else "failed",
                exit_status,
                round(time.monotonic() - started, 6),
                timed_out,
                cancelled,
                failure or "incomplete_cleanup",
                evaluated.last_good_milestone,
                failure or (None if cleanup_complete else "cleanup completeness"),
                evaluated.event_hash,
                evaluated.outcome_hash,
                evaluated.resource_deltas,
                evaluated.state_deltas,
                evaluated.artifact_complete and stdout_path.is_file() and stderr_path.is_file(),
                cleanup_complete,
                evaluated.unknowns,
                exception=process_exception,
                cleanup_exception=cleanup_exception,
            )
        return RunResult(**{**asdict(evaluated), "run_number": number, "elapsed_seconds": round(time.monotonic() - started, 6), "artifact_complete": evaluated.artifact_complete and stdout_path.is_file() and stderr_path.is_file(), "cleanup_complete": cleanup_complete})

    def request_cancellation(self, attempt_id: str) -> Path:
        root = require_existing_safe_path(self.artifact_root / attempt_id, kind="attempt")
        manifest = load_manifest(root / "manifest.json")
        status = json.loads((root / "status.json").read_text(encoding="utf-8"))
        if status.get("lifecycle") not in {AttemptLifecycle.READY.value, AttemptLifecycle.RUNNING.value, AttemptLifecycle.CANCELLATION_REQUESTED.value}:
            raise UnattendedError("only an exact ready or running attempt may be cancelled")
        marker = root / "cancel.requested"
        with marker.open("x", encoding="utf-8") as target:
            target.write(json.dumps({"attempt_id": manifest.attempt_id, "requested_at": utc_now()}) + "\n")
        write_json_replace(root / "status.json", status_payload(manifest, AttemptLifecycle.CANCELLATION_REQUESTED))
        return marker

    def attempt_status(self, attempt_id: str) -> Mapping[str, Any]:
        root = require_existing_safe_path(self.artifact_root / attempt_id, kind="attempt")
        return json.loads((root / "status.json").read_text(encoding="utf-8"))


class MarioUnattendedProvider:
    adapter_id = "smb3"

    def __init__(self, *, rom_path: Path | None, executable: Path = Path("/usr/local/bin/fceux"), goal_id: str = "world_8_double_whistle") -> None:
        self.rom_path = rom_path
        self.executable = executable
        self.goal_id = goal_id

    def capability(self) -> Mapping[str, Any]:
        configured = self.rom_path is not None and self.rom_path.exists() and self.executable.exists()
        return {"adapter_id": self.adapter_id, "supported": True, "configured": configured, "eligible": False if not configured else "pending_scenario_source_display_preflight", "status": "implemented_validation_deferred", "requires": ["owner-configured local ROM", "FCEUX", "rendered-pixel display"], "proof": "technical repeatability only"}

    def plan(self, *, run_root: Path | None = None) -> ProviderRunPlan:
        if self.rom_path is None:
            raise UnattendedError("Mario unattended provider requires an owner-configured ROM path")
        rom = AssetIdentity.inspect("owner_local_rom", self.rom_path, sensitive=True)
        executable = require_existing_safe_path(self.executable, kind="FCEUX executable")
        contract = load_goal_contract(resolve_goal_path(self.goal_id))
        if contract.goal_type != "product_goal" or not contract.executable or contract.bridged_segments:
            raise UnattendedError("Mario unattended regression requires an executable zero-bridge product goal")
        script = require_existing_safe_path(Path(str(contract.runner["script"])), kind="FCEUX route script")
        artifact = run_root or Path("__RUN_ROOT__")
        arguments = ("--no-config", "1", "--sound", "0", "--loadstate", "10", "--savestate", "10", "--loadlua", str(script), rom.path)
        preset_environment = dict(item.split("=", 1) for item in environment_for_preset(contract.preset))
        return ProviderRunPlan(
            self.adapter_id, "smb3-live-observer/v1", "smb3", str(executable), arguments,
            (rom, AssetIdentity.inspect("route_script", script, sensitive=False), AssetIdentity.inspect("fceux_executable", executable, sensitive=False)), None,
            {"PATH": os.environ.get("PATH", ""), "LANG": os.environ.get("LANG", "C"), **preset_environment, "SMB3_AGENT_LOG": str(artifact / "fceux_1_1.log"), "SMB3_AGENT_ATTEMPTS": "1", "SMB3_POST_1_1_PROBE": "run_1_castle_after_1_6"},
            (rom.path, "accepted Mario evidence namespaces", "route profiles", "fastest-run indexes", "learning state"),
            (), ("adapter-declared ordered route milestones",), ("fceux_1_1.log", "classified events", "adapter evidence"),
            ("neutralize controller input", "terminate only the owned FCEUX process group", "retain failed artifacts"),
            "game-companion-unattended-artifacts/v1", "existing FCEUX gameplay observers", "normal FCEUX controller input",
        )

    def prepare_run(self, run_root: Path, plan: ProviderRunPlan) -> ProviderRunPlan:
        env = {**plan.environment, "SMB3_AGENT_LOG": str(run_root / "fceux_1_1.log"), "SMB3_AGENT_ATTEMPTS": "1"}
        return ProviderRunPlan(**{**asdict(plan), "assets": plan.assets, "fixture": plan.fixture, "environment": env})

    def evaluate(self, run_root: Path, exit_status: int | None) -> RunResult:
        log = run_root / "fceux_1_1.log"
        digest = sha256_file(log) if log.is_file() else None
        summary = parse_fceux_log(log, expected_attempts=1, allow_bridges=False) if digest else None
        contract = load_goal_contract(resolve_goal_path(self.goal_id))
        passed = exit_status == 0 and summary is not None and evaluate_success_metrics(contract, summary)
        outcome_hash = hash_payload(asdict(summary)) if summary else None
        milestone = contract.id if passed else (summary.post_probe_last_event if summary else None)
        return RunResult(0, "passed" if passed else "failed", exit_status, 0, False, False, None if passed else "adapter_success_predicate_failed", milestone, None if passed else "exact goal success metrics", digest, outcome_hash, {}, {}, digest is not None, False, () if passed else ("game-owned outcome is not authoritative in unattended classification",))

    def cleanup(self, run_root: Path) -> Mapping[str, Any]:
        return {"complete": True, "neutral_input_requested": True, "broad_deletion": False, "retained": str(run_root), "primary_or_accepted_evidence_touched": False}


class StardewUnattendedProvider:
    adapter_id = "stardew"

    def __init__(self, *, fixture_path: Path | None, owner_save_roots: Sequence[Path], executable: Path | None = None) -> None:
        self.fixture_path = fixture_path
        self.owner_save_roots = tuple(owner_save_roots)
        self.executable = executable

    def capability(self) -> Mapping[str, Any]:
        configured = self.fixture_path is not None and self.fixture_path.exists() and self.executable is not None and self.executable.exists() and bool(self.owner_save_roots)
        return {"adapter_id": self.adapter_id, "supported": True, "configured": configured, "eligible": False if not configured else "pending_scenario_source_display_path_preflight", "status": "implemented_validation_deferred", "requires": ["designated regression fixture", "visible-window pixel backend", "ordinary input", "all owner-save roots"], "primary_save_allowed": False, "proof": "technical regression behavior only"}

    def plan(self, *, run_root: Path | None = None) -> ProviderRunPlan:
        if self.fixture_path is None or self.executable is None:
            raise UnattendedError("Stardew unattended provider requires a dedicated fixture and executable")
        if not self.owner_save_roots:
            raise UnattendedError("Stardew unattended provider requires every owner-save root to be declared")
        fixture = require_existing_safe_path(self.fixture_path, kind="Stardew regression fixture")
        if not fixture.is_dir():
            raise UnattendedError("Stardew regression fixture must be a directory")
        reject_overlap(fixture, self.owner_save_roots, label="Stardew regression fixture")
        fixture_hash = tree_hash(fixture)
        executable = require_existing_safe_path(self.executable, kind="Stardew executable")
        disposable = (run_root / "disposable-save") if run_root else Path("__RUN_ROOT__/disposable-save")
        return ProviderRunPlan(
            self.adapter_id, "stardew-companion/v1", "stardew_valley", str(executable), tuple(), (AssetIdentity.inspect("stardew_regression_executable", executable, sensitive=False),),
            FixtureIdentity("stardew-regression-fixture", str(fixture), fixture_hash, True, False),
            {"PATH": os.environ.get("PATH", ""), "LANG": os.environ.get("LANG", "C"), "STARDEW_REGRESSION_SAVE": str(disposable)},
            tuple(str(path.resolve(strict=False)) for path in self.owner_save_roots) + (str(fixture),),
            ("purchase", "sale", "discard", "gift", "consequential dialogue", "story choice", "sleep", "save operation"),
            ("exact crop sweep", "exact watering reconciliation", "exact farmhouse entrance position", "neutral handback"),
            ("screen observations", "actor-labeled ordinary inputs", "resource and position ledger"),
            ("neutralize ordinary input", "verify handback", "retain failures and disposable copy", "never delete owner data"),
            "game-companion-unattended-artifacts/v1", "visible-window pixel observation", "existing ordinary-input protected-action driver",
        )

    def prepare_run(self, run_root: Path, plan: ProviderRunPlan) -> ProviderRunPlan:
        if plan.fixture is None:
            raise UnattendedError(
                "Stardew unattended preparation requires a bound regression fixture"
            )
        source = require_existing_safe_path(Path(plan.fixture.source_path), kind="Stardew regression fixture")
        target = require_safe_output_path(run_root / "disposable-save", kind="disposable regression save")
        reject_overlap(target, self.owner_save_roots, label="disposable regression save")
        shutil.copytree(source, target, symlinks=False)
        if tree_hash(target) != plan.fixture.source_sha256:
            raise UnattendedError("fresh disposable regression copy did not reconcile")
        env = {**plan.environment, "STARDEW_REGRESSION_SAVE": str(target)}
        return ProviderRunPlan(**{**asdict(plan), "assets": plan.assets, "fixture": plan.fixture, "environment": env})

    def evaluate(self, run_root: Path, exit_status: int | None) -> RunResult:
        evidence = run_root / "adapter-evidence.json"
        digest = sha256_file(evidence) if evidence.is_file() else None
        payload: Mapping[str, Any] = {}
        if digest:
            try:
                payload = json.loads(evidence.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                payload = {}
        exact = all(payload.get(key) is True for key in ("screen_only", "crop_reconciled", "resources_reconciled", "position_reconciled", "protected_actions_refused"))
        owner_fields_absent = not any(key in payload for key in ("owner_feedback", "owner_acceptance", "owner_usefulness"))
        passed = exit_status == 0 and digest is not None and payload.get("success") is True and exact and owner_fields_absent
        unknowns = tuple(str(item) for item in payload.get("unknowns", ())) if payload else ("screen/resource/position reconciliation unknown",)
        return RunResult(0, "passed" if passed else "failed", exit_status, 0, False, False, None if passed else "missing_or_failed_adapter_evidence", str(payload.get("last_good_milestone")) if payload.get("last_good_milestone") else None, None if passed else "exact Stardew regression evidence", str(payload.get("event_hash")) if payload.get("event_hash") else digest, str(payload.get("outcome_hash")) if payload.get("outcome_hash") else None, dict(payload.get("resource_deltas") or {}), dict(payload.get("state_deltas") or {}), digest is not None and exact and owner_fields_absent, False, unknowns)

    def cleanup(self, run_root: Path) -> Mapping[str, Any]:
        evidence_path = run_root / "cleanup-evidence.json"
        evidence: Mapping[str, Any] = {}
        if evidence_path.is_file():
            try:
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                evidence = {}
        complete = all(
            evidence.get(key) is True
            for key in ("input_neutralized", "handback_verified", "primary_save_untouched")
        )
        return {"complete": complete, "neutral_input_verified": bool(evidence.get("input_neutralized")), "handback_verified": bool(evidence.get("handback_verified")), "broad_deletion": False, "failed_copy_retained": True, "owner_save_touched": evidence.get("primary_save_untouched") is not True}


def eligibility_blockers(definition: ScenarioDefinition, *, requested_promotion: str | None = None) -> tuple[str, ...]:
    blockers: list[str] = []
    if definition.classification is not ScenarioClassification.UNATTENDED_REGRESSION:
        blockers.append("only explicitly unattended_regression scenarios are eligible")
    if definition.evidence_classification is not EvidenceClassification.UNATTENDED_REGRESSION:
        blockers.append("scenario evidence classification is not unattended_regression_result")
    if definition.execution_classification != CLASSIFICATION:
        blockers.append("scenario execution classification is not unattended_regression")
    if definition.owner_participation_required or definition.owner_action_boundaries:
        blockers.append("owner-required scenarios cannot execute unattended")
    if definition.visible_execution_required:
        blockers.append("visible-live or owner-visible proof scenarios cannot execute unattended")
    if definition.may_count_toward_reliability or definition.may_count_toward_owner_acceptance:
        blockers.append("scenario requests prohibited evidence promotion")
    if requested_promotion:
        blockers.append("unattended evidence promotion to another class is forbidden")
    if "final" in definition.execution_classification or definition.classification is ScenarioClassification.FINAL_CAMPAIGN:
        blockers.append("final-campaign orchestration cannot execute unattended")
    return tuple(blockers)


def sanitize_environment(requested: Mapping[str, str]) -> dict[str, str]:
    forbidden_markers = ("TOKEN", "SECRET", "PASSWORD", "KEY", "CREDENTIAL", "COOKIE", "AUTH")
    result: dict[str, str] = {}
    for key, value in requested.items():
        if key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}:
            raise UnattendedError(f"network environment variable is forbidden: {key}")
        if any(marker in key.upper() for marker in forbidden_markers):
            raise UnattendedError(f"sensitive environment variable is forbidden: {key}")
        if key in SAFE_ENVIRONMENT_KEYS or key.startswith(("SMB3_", "STARDEW_REGRESSION_")):
            result[str(key)] = str(value)
    result.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    result.setdefault("LANG", "C")
    return result


def source_identity(repo: Path = Path(".")) -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo, check=True, text=True, capture_output=True).stdout
    diff = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=repo, check=True, capture_output=True).stdout
    untracked = []
    for line in status.splitlines():
        if line.startswith("?? "):
            path = require_existing_safe_path(repo / line[3:], kind="untracked source")
            untracked.append((line[3:], sha256_file(path) if path.is_file() else tree_hash(path)))
    fingerprint = hash_payload({"commit": commit, "status": status, "diff_sha256": hashlib.sha256(diff).hexdigest(), "untracked": untracked})
    return {"commit": commit, "dirty": bool(status), "dirty_fingerprint": fingerprint}


def compare_attempts(manifests: Sequence[AttemptManifest], reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(manifests) < 2 or len(manifests) != len(reports):
        raise UnattendedError("repeatability comparison requires two or more manifest/report pairs")
    compatible = all(item.compatibility_key() == manifests[0].compatibility_key() for item in manifests[1:])
    if not compatible:
        return {"schema_version": "game-companion-unattended-comparison/v1", "compatible": False, "result": "not_comparable", "correlation": None, "equivalence": False, "causation": False}
    hashes = [report.get("deterministic_hashes") for report in reports]
    milestones = [report.get("milestone_agreement") for report in reports]
    outcomes = [report.get("outcome_agreement") for report in reports]
    return {"schema_version": "game-companion-unattended-comparison/v1", "compatible": True, "technical_repeatability": len({json.dumps(item, sort_keys=True) for item in hashes}) == 1 and all(milestones) and all(outcomes), "correlation": "reference_only_if_explicitly_supplied", "equivalence": False, "causation": False, "proof_limits": list(PROOF_LIMITS)}


def repeatability_report(manifest: AttemptManifest, results: Sequence[RunResult]) -> dict[str, Any]:
    counts = {name: 0 for name in ("completed", "passed", "failed", "cancelled", "timed_out")}
    for result in results:
        counts["completed"] += 1
        if result.lifecycle == "passed":
            counts["passed"] += 1
        elif result.cancelled:
            counts["cancelled"] += 1
        elif result.timed_out:
            counts["timed_out"] += 1
        else:
            counts["failed"] += 1
    event_hashes = [item.event_hash for item in results]
    outcome_hashes = [item.outcome_hash for item in results]
    first_missing = next((item.first_missing_requirement for item in results if item.first_missing_requirement), None)
    return {
        "schema_version": REPORT_SCHEMA,
        "attempt_id": manifest.attempt_id,
        "classification": CLASSIFICATION,
        "evidence_classification": EVIDENCE_CLASSIFICATION,
        "runs_requested": manifest.run_count,
        **counts,
        "deterministic_hashes": {"events": event_hashes, "outcomes": outcome_hashes},
        "milestone_agreement": bool(results) and all(item.last_good_milestone == results[0].last_good_milestone for item in results),
        "outcome_agreement": bool(results) and len(set(outcome_hashes)) == 1 and None not in outcome_hashes,
        "resource_deltas": [dict(item.resource_deltas) for item in results],
        "state_deltas": [dict(item.state_deltas) for item in results],
        "failure_classifications": [item.failure_classification for item in results if item.failure_classification],
        "artifact_completeness": [item.artifact_complete for item in results],
        "cleanup_completeness": [item.cleanup_complete for item in results],
        "unknowns": [unknown for item in results for unknown in item.unknowns],
        "exceptions": [dict(item.exception) for item in results if item.exception],
        "cleanup_exceptions": [
            dict(item.cleanup_exception) for item in results if item.cleanup_exception
        ],
        "first_missing_requirement": first_missing,
        "correlation_reference": manifest.correlation_reference,
        "correlation_is_not_equivalence_or_causation": True,
        "blended_success_score": None,
        "proof_limits": list(PROOF_LIMITS),
    }


def require_existing_safe_path(path: Path, *, kind: str) -> Path:
    supplied = path.expanduser().absolute()
    current = Path(supplied.anchor)
    for component in supplied.parts[1:]:
        current = current / component
        if current.is_symlink():
            raise UnattendedError(f"{kind} contains a symlink")
    resolved = supplied.resolve(strict=True)
    return resolved


def require_safe_output_path(path: Path, *, kind: str) -> Path:
    supplied = path.expanduser().absolute()
    if str(supplied) in {"/", str(Path.home()), str(Path.cwd().anchor)}:
        raise UnattendedError(f"unsafe broad {kind}")
    if supplied.exists() and (supplied / ".git").exists():
        raise UnattendedError(f"repository root is an unsafe {kind}")
    existing = supplied
    while not existing.exists():
        if existing == existing.parent:
            raise UnattendedError(f"cannot establish safe parent for {kind}")
        existing = existing.parent
    require_existing_safe_path(existing, kind=f"{kind} parent")
    return supplied


def reject_overlap(path: Path, protected_roots: Sequence[Path], *, label: str) -> None:
    candidate = path.resolve(strict=False)
    for root in protected_roots:
        protected = root.expanduser().resolve(strict=False)
        if candidate == protected or candidate in protected.parents or protected in candidate.parents:
            raise UnattendedError(f"{label} overlaps a protected owner-data location")


def terminate_owned_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
    except ProcessLookupError:
        return


def load_manifest(path: Path) -> AttemptManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != MANIFEST_SCHEMA:
            raise UnattendedError("unsupported unattended manifest schema")
        raw["assets"] = tuple(AssetIdentity(**item) for item in raw.get("assets", ()))
        raw["fixture"] = FixtureIdentity(**raw["fixture"]) if raw.get("fixture") else None
        raw["display"] = DisplayIdentity(**raw["display"])
        for key in ("environment_allowlist", "arguments", "cleanup_policy", "protected_data", "protected_actions", "expected_milestones", "expected_outputs", "proof_limits"):
            raw[key] = tuple(raw.get(key, ()))
        return AttemptManifest(**raw)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, UnattendedError):
            raise
        raise UnattendedError(f"invalid unattended manifest: {exc}") from exc


def artifact_integrity(root: Path, *, exclude: set[str]) -> dict[str, Any]:
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name not in exclude):
        entries.append({"path": str(path.relative_to(root)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return {"schema_version": "game-companion-unattended-integrity/v1", "files": entries, "root_hash": hash_payload(entries)}


def tree_hash(root: Path) -> str:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise UnattendedError("symlinked fixture content is refused")
        if path.is_file():
            entries.append((str(path.relative_to(root)), sha256_file(path)))
    return hash_payload(entries)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_payload(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def new_attempt_id(scenario_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{scenario_id.replace('.', '-')}-{stamp}-{secrets.token_hex(4)}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as target:
        json.dump(payload, target, indent=2, sort_keys=True)
        target.write("\n")


def write_json_replace(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def append_classified_event(path: Path, manifest: AttemptManifest, event_type: str, payload: Mapping[str, Any]) -> None:
    event = {
        "event_type": event_type,
        "at": utc_now(),
        "attempt_id": manifest.attempt_id,
        "correlation_id": manifest.correlation_id,
        "causation_id": manifest.causation_id,
        "adapter_id": manifest.adapter_id,
        "scenario_id": manifest.scenario_id,
        "classification": CLASSIFICATION,
        "evidence_classification": EVIDENCE_CLASSIFICATION,
        "execution_classification": CLASSIFICATION,
        "may_count_toward_reliability": False,
        "may_count_toward_owner_acceptance": False,
        "visible_live_proof": False,
        "authoritative_game_outcome": False,
        "network_access_allowed": False,
        "payload": dict(payload),
    }
    event["integrity_sha256"] = hash_payload(event)
    with path.open("a", encoding="utf-8") as target:
        target.write(json.dumps(event, sort_keys=True) + "\n")


def status_payload(manifest: AttemptManifest, lifecycle: AttemptLifecycle, *, first_missing: str | None = None) -> dict[str, Any]:
    return {"attempt_id": manifest.attempt_id, "lifecycle": lifecycle.value, "classification": CLASSIFICATION, "evidence_classification": EVIDENCE_CLASSIFICATION, "first_missing_requirement": first_missing, "proof_limits": list(PROOF_LIMITS), "updated_at": utc_now()}


def cancelled_result(number: int, reason: str) -> RunResult:
    return RunResult(number, "cancelled", None, 0, False, True, "cancelled", None, reason, None, None, {}, {}, False, True, (reason,))


def timed_out_result(number: int, reason: str) -> RunResult:
    return RunResult(number, "timed_out", None, 0, True, False, "aggregate_timeout", None, reason, None, None, {}, {}, False, True, (reason,))


def exception_record(exc: BaseException, *, phase: str) -> dict[str, str]:
    return {
        "phase": phase,
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
