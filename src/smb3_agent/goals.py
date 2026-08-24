from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from smb3_agent.fceux_harness import BatchSummary, run_fceux_1_1
from smb3_agent.presets import DIAGNOSTIC_PRESETS, EXECUTABLE_PRESETS, environment_for_preset
from smb3_agent.paths import repository_path


ACTIVE_PRODUCT_GOAL_ID = "world_8_double_whistle"
SUPPORTED_GOAL_TYPES = {"product_goal", "diagnostic_route"}
SUPPORTED_EXECUTION_STATUSES = {"executable", "planned"}
SUPPORTED_ROUTE_CLASSIFICATIONS = {
    "objective_milestone",
    "game_prerequisite",
    "optional",
    "recovery_only",
    "diagnostic_route",
}
SUPPORTED_EXECUTION_MODES = {"normal_gameplay", "bridge", "planned"}
SUPPORTED_PRESETS = EXECUTABLE_PRESETS | {"unavailable"}
SUPPORTED_METRIC_TYPES = {"summary_field", "final_event", "event_present", "event_absent"}
SUPPORTED_SUMMARY_FIELDS = {
    "success_count",
    "bad_state_count",
    "total",
    "post_probe_clear",
    "post_probe_last_event",
}
GOAL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{2,79}$")
SUPPORTED_RECOVERY_ACTIONS = {
    "capture_artifacts_and_stop",
    "correct_known_state_or_stop",
    "reclassify_state",
    "restart_goal",
    "stop_and_review",
}


class GoalValidationError(ValueError):
    pass


@dataclass(frozen=True)
class RouteStep:
    id: str
    classification: str
    execution_mode: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class GoalContract:
    id: str
    game: str
    user_directive: str
    goal_type: str
    execution_status: str
    objective: dict[str, Any]
    route: dict[str, Any]
    route_steps: tuple[RouteStep, ...]
    constraints: dict[str, Any]
    allowed_tactics: dict[str, Any]
    success_metrics: tuple[dict[str, Any], ...]
    recovery_policy: dict[str, Any]
    runner: dict[str, Any]
    prefix_goal: str | None
    bridged_segments: tuple[str, ...]
    display_name: str
    display_subtitle: str
    path: Path

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(step.id for step in self.route_steps)

    @property
    def catalog_path(self) -> Path:
        return Path(self.route["catalog"])

    @property
    def executable(self) -> bool:
        return bool(self.runner["executable"])

    @property
    def preset(self) -> str:
        return str(self.runner["preset"])


@dataclass(frozen=True)
class GoalRunResult:
    contract: GoalContract
    summary: BatchSummary
    artifacts_dir: Path
    metrics_passed: bool


def resolve_goal_path(goal: str, goals_dir: Path = Path("data/goals")) -> Path:
    root = os.path.realpath(os.fspath(repository_path(goals_dir)))
    if GOAL_ID_PATTERN.fullmatch(goal):
        candidate = os.path.realpath(os.path.join(root, f"{goal}.yaml"))
    else:
        candidate = os.path.realpath(os.fspath(repository_path(goal)))
    if (
        not candidate.startswith(root.rstrip(os.sep) + os.sep)
        or not candidate.endswith(".yaml")
    ):
        raise GoalValidationError(f"Invalid goal id or catalog path: {goal!r}")
    return Path(candidate)


def load_goal_contract(path: Path, *, _seen: frozenset[Path] = frozenset()) -> GoalContract:
    source_path = path if path.is_file() else repository_path(path)
    if not source_path.is_file():
        raise GoalValidationError(f"Goal contract not found: {path}")
    resolved_path = source_path.resolve()
    if resolved_path in _seen:
        raise GoalValidationError(f"Goal prefix cycle detected at: {path}")

    raw = yaml.safe_load(source_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise GoalValidationError("Goal contract must be a YAML mapping")

    _require_fields(
        raw,
        (
            "id",
            "game",
            "user_directive",
            "goal_type",
            "execution_status",
            "objective",
            "route",
            "constraints",
            "allowed_tactics",
            "success_metrics",
            "recovery_policy",
            "runner",
        ),
    )

    _require_type(raw, "id", str)
    _require_type(raw, "game", str)
    _require_type(raw, "user_directive", str)
    _require_type(raw, "goal_type", str)
    _require_type(raw, "execution_status", str)
    _require_type(raw, "objective", dict)
    _require_type(raw, "route", dict)
    _require_type(raw, "constraints", dict)
    _require_type(raw, "allowed_tactics", dict)
    _require_type(raw, "success_metrics", list)
    _require_type(raw, "recovery_policy", dict)
    _require_type(raw, "runner", dict)

    display = raw.get("display")
    if not isinstance(display, dict):
        raise GoalValidationError("display must be a mapping")
    _require_fields(display, ("name", "subtitle"))
    if not all(isinstance(display[field], str) and display[field] for field in ("name", "subtitle")):
        raise GoalValidationError("display.name and display.subtitle must be non-empty strings")

    goal_type = raw["goal_type"]
    if goal_type not in SUPPORTED_GOAL_TYPES:
        raise GoalValidationError(f"Unsupported goal_type: {goal_type}")
    execution_status = raw["execution_status"]
    if execution_status not in SUPPORTED_EXECUTION_STATUSES:
        raise GoalValidationError(f"Unsupported execution_status: {execution_status}")

    route = raw["route"]
    _require_fields(route, ("catalog", "segments"))
    if not isinstance(route["catalog"], str) or not route["catalog"]:
        raise GoalValidationError("route.catalog must be a non-empty string")
    segments = route["segments"]
    if not isinstance(segments, list) or not segments:
        raise GoalValidationError("route.segments must be a non-empty list")
    local_route_steps = tuple(
        _load_route_step(index, item) for index, item in enumerate(segments)
    )
    prefix_goal = route.get("prefix_goal")
    prefix_route_steps: tuple[RouteStep, ...] = ()
    if prefix_goal is not None:
        if not isinstance(prefix_goal, str) or not prefix_goal:
            raise GoalValidationError("route.prefix_goal must be a non-empty string")
        prefix = load_goal_contract(
            resolve_goal_path(prefix_goal), _seen=_seen | {resolved_path}
        )
        if prefix.catalog_path != Path(route["catalog"]):
            raise GoalValidationError(
                "prefixed goals must use the same route catalog as their prefix"
            )
        prefix_route_steps = prefix.route_steps
    route_steps = prefix_route_steps + local_route_steps
    route_ids = [step.id for step in route_steps]
    duplicates = sorted({segment_id for segment_id in route_ids if route_ids.count(segment_id) > 1})
    if duplicates:
        raise GoalValidationError(f"Duplicate route segment id(s): {', '.join(duplicates)}")

    runner = raw["runner"]
    _require_fields(
        runner,
        ("backend", "preset", "script", "artifacts_root", "require_perfect", "executable"),
    )
    if runner["preset"] not in SUPPORTED_PRESETS:
        raise GoalValidationError(f"Unsupported runner preset: {runner['preset']}")
    if "env" in runner:
        raise GoalValidationError(
            "runner.env is unsupported; define fixed execution policy in presets.py"
        )
    if not isinstance(runner["executable"], bool):
        raise GoalValidationError("runner.executable must be bool")
    if execution_status == "planned" and runner["executable"]:
        raise GoalValidationError("planned goals cannot declare runner.executable=true")
    if execution_status == "executable" and not runner["executable"]:
        raise GoalValidationError("executable goals must declare runner.executable=true")

    bridged_segments = raw.get("bridged_segments", ())
    if not isinstance(bridged_segments, list) or not all(isinstance(item, str) for item in bridged_segments):
        raise GoalValidationError("bridged_segments must be a list of strings")
    unknown_bridges = sorted(set(bridged_segments).difference(route_ids))
    if unknown_bridges:
        raise GoalValidationError(f"bridged_segments not present in route.segments: {', '.join(unknown_bridges)}")
    declared_bridge_steps = {step.id for step in route_steps if step.execution_mode == "bridge"}
    missing_bridge_declarations = sorted(declared_bridge_steps.difference(bridged_segments))
    if missing_bridge_declarations:
        raise GoalValidationError(
            "bridge route step(s) missing from bridged_segments: "
            + ", ".join(missing_bridge_declarations)
        )
    non_bridge_declarations = sorted(set(bridged_segments).difference(declared_bridge_steps))
    if non_bridge_declarations:
        raise GoalValidationError(
            "bridged_segments must use execution_mode=bridge: " + ", ".join(non_bridge_declarations)
        )

    metrics = tuple(raw["success_metrics"])
    if not metrics:
        raise GoalValidationError("success_metrics must be non-empty")
    for index, metric in enumerate(metrics):
        _validate_metric(index, metric)

    for state, policy in raw["recovery_policy"].items():
        if not isinstance(policy, dict):
            raise GoalValidationError(f"recovery_policy.{state} must be a mapping")
        action = policy.get("action")
        if action not in SUPPORTED_RECOVERY_ACTIONS:
            raise GoalValidationError(f"Unsupported recovery action for {state}: {action}")

    return GoalContract(
        id=raw["id"],
        game=raw["game"],
        user_directive=raw["user_directive"],
        goal_type=goal_type,
        execution_status=execution_status,
        objective=raw["objective"],
        route=route,
        route_steps=route_steps,
        constraints=raw["constraints"],
        allowed_tactics=raw["allowed_tactics"],
        success_metrics=metrics,
        recovery_policy=raw["recovery_policy"],
        runner=runner,
        prefix_goal=prefix_goal,
        bridged_segments=tuple(bridged_segments),
        display_name=display["name"],
        display_subtitle=display["subtitle"],
        path=path,
    )


def load_product_goal_contracts(goals_dir: Path = Path("data/goals")) -> tuple[GoalContract, ...]:
    if not goals_dir.is_dir():
        goals_dir = repository_path(goals_dir)
    contracts = tuple(
        load_goal_contract(path)
        for path in sorted(goals_dir.glob("*.yaml"))
    )
    product_contracts = tuple(
        sorted(
            (
                contract
                for contract in contracts
                if contract.goal_type == "product_goal" and contract.executable
            ),
            key=lambda contract: len(contract.route_steps),
        )
    )
    ids = [contract.id for contract in product_contracts]
    if len(ids) != len(set(ids)):
        raise GoalValidationError("Product goal ids must be unique")
    if not product_contracts or product_contracts[0].id != ACTIVE_PRODUCT_GOAL_ID:
        raise GoalValidationError(
            f"Product goal catalog must begin with {ACTIVE_PRODUCT_GOAL_ID}"
        )
    return product_contracts


def run_goal_contract(
    contract: GoalContract,
    *,
    game_path: Path,
    attempts: int,
    artifacts_dir: Path | None = None,
    capture_images: bool = False,
    capture_ticks: bool = False,
    env_overrides: tuple[str, ...] = (),
    clean_product_env: bool = False,
    frame_sleep_seconds: float = 0.0,
    timeout_seconds: int | None = None,
) -> GoalRunResult:
    if not contract.executable:
        raise GoalValidationError(
            f"Goal {contract.id} is planned and not yet executable; "
            "no diagnostic runner fallback is permitted"
        )
    if contract.preset not in EXECUTABLE_PRESETS:
        raise GoalValidationError(f"Unsupported runner preset: {contract.preset}")

    preset_env = environment_for_preset(contract.preset)

    run_dir = artifacts_dir or _default_artifacts_dir(contract)
    summary = run_fceux_1_1(
        game_path=game_path,
        script_path=repository_path(contract.runner["script"]),
        artifacts_dir=run_dir,
        attempts=attempts,
        capture_images=capture_images,
        capture_ticks=capture_ticks,
        post_1_1_probe="run_1_castle_after_1_6",
        env_overrides=preset_env + env_overrides,
        allow_bridges=contract.preset in DIAGNOSTIC_PRESETS,
        clean_product_env=clean_product_env,
        frame_sleep_seconds=frame_sleep_seconds,
        timeout_seconds=timeout_seconds,
    )
    return GoalRunResult(
        contract=contract,
        summary=summary,
        artifacts_dir=run_dir,
        metrics_passed=evaluate_success_metrics(contract, summary),
    )


def evaluate_success_metrics(contract: GoalContract, summary: BatchSummary) -> bool:
    return all(_metric_passes(metric, summary) for metric in contract.success_metrics)


def _default_artifacts_dir(contract: GoalContract) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(contract.runner["artifacts_root"]) / timestamp


def _metric_passes(metric: dict[str, Any], summary: BatchSummary) -> bool:
    metric_type = metric["type"]
    if metric_type == "final_event":
        return summary.post_probe_last_event == metric["value"]
    if metric_type == "event_present":
        return metric["value"] in summary.post_probe_events
    if metric_type == "event_absent":
        return metric["value"] not in summary.post_probe_events
    if metric_type == "summary_field":
        actual = getattr(summary, metric["field"])
        expected = metric["equals"]
        if expected == "total":
            expected = summary.total
        return actual == expected
    raise GoalValidationError(f"Unsupported success metric type: {metric_type}")


def _validate_metric(index: int, metric: Any) -> None:
    if not isinstance(metric, dict):
        raise GoalValidationError(f"success_metrics[{index}] must be a mapping")
    _require_fields(metric, ("id", "type"))
    if metric["type"] not in SUPPORTED_METRIC_TYPES:
        raise GoalValidationError(f"Unsupported success metric type: {metric['type']}")
    if metric["type"] == "summary_field":
        _require_fields(metric, ("field", "equals"))
        if metric["field"] not in SUPPORTED_SUMMARY_FIELDS:
            raise GoalValidationError(f"Unsupported summary field: {metric['field']}")
    if metric["type"] in {"final_event", "event_present", "event_absent"}:
        _require_fields(metric, ("value",))


def _load_route_step(index: int, raw: Any) -> RouteStep:
    if not isinstance(raw, dict):
        raise GoalValidationError(f"route.segments[{index}] must be a mapping")
    _require_fields(raw, ("id", "classification", "execution_mode", "evidence"))
    segment_id = raw["id"]
    if not isinstance(segment_id, str) or not segment_id:
        raise GoalValidationError(f"route.segments[{index}].id must be a non-empty string")
    classification = raw["classification"]
    if classification not in SUPPORTED_ROUTE_CLASSIFICATIONS:
        raise GoalValidationError(f"Unsupported route classification for {segment_id}: {classification}")
    execution_mode = raw["execution_mode"]
    if execution_mode not in SUPPORTED_EXECUTION_MODES:
        raise GoalValidationError(f"Unsupported execution mode for {segment_id}: {execution_mode}")
    evidence = raw["evidence"]
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item for item in evidence):
        raise GoalValidationError(f"{segment_id}.evidence must be a non-empty list of strings")
    return RouteStep(
        id=segment_id,
        classification=classification,
        execution_mode=execution_mode,
        evidence=tuple(evidence),
    )


def _require_fields(data: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        raise GoalValidationError(f"Missing required field(s): {', '.join(missing)}")


def _require_type(data: dict[str, Any], field: str, expected_type: type) -> None:
    if not isinstance(data[field], expected_type):
        raise GoalValidationError(f"{field} must be {expected_type.__name__}")
