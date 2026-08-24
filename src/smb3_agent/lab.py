from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from smb3_agent.commands import AgentCommand, parse_command
from smb3_agent.fceux_harness import BatchSummary
from smb3_agent.goals import GoalRunResult, load_goal_contract, resolve_goal_path, run_goal_contract
from smb3_agent.review import LogEvent, parse_log_events, review_log


LATEST_SESSION_PATH = Path("artifacts/sessions/latest.txt")


class LabError(ValueError):
    pass


@dataclass(frozen=True)
class LabSessionResult:
    session_id: str
    session_dir: Path
    manifest_path: Path
    command: AgentCommand
    goal_result: GoalRunResult
    route_variant: str
    requested_speed: float
    attempts_requested: int
    run_settings: dict[str, Any]

    def to_text(self) -> str:
        lines = [
            f"session_id={self.session_id}",
            f"session_dir={self.session_dir}",
            f"manifest={self.manifest_path}",
            self.command.to_text(),
            f"route_variant={self.route_variant}",
            f"requested_speed={self.requested_speed:g}",
            f"attempts_requested={self.attempts_requested}",
            f"speed_mode={self.run_settings['speed_mode']}",
            f"frame_sleep_seconds={self.run_settings['frame_sleep_seconds']}",
            f"capture_images={str(self.run_settings['capture_images']).lower()}",
            f"capture_ticks={str(self.run_settings['capture_ticks']).lower()}",
            self.goal_result.summary.to_text(),
            f"metrics_passed={str(self.goal_result.metrics_passed).lower()}",
            f"notes_file={self.session_dir / 'notes.yaml'}",
            f"review_file={self.session_dir / 'review.md'}",
        ]
        return "\n".join(lines)


@dataclass(frozen=True)
class LabNoteResult:
    session_id: str
    notes_path: Path
    note: dict[str, Any]

    def to_text(self) -> str:
        anchor = self.note.get("anchor", {})
        lines = [
            f"session_id={self.session_id}",
            f"notes_file={self.notes_path}",
            f"note_id={self.note['id']}",
            f"segment_id={self.note['segment_id']}",
            f"anchor_type={anchor.get('type')}",
            f"anchor_value={anchor.get('value')}",
            f"severity={self.note['severity']}",
            f"text={self.note['text']}",
        ]
        return "\n".join(lines)


@dataclass(frozen=True)
class LabReviewResult:
    session_id: str
    review_path: Path
    review_yaml_path: Path
    review: dict[str, Any]

    def to_text(self) -> str:
        lines = [
            f"session_id={self.session_id}",
            f"review_file={self.review_path}",
            f"review_yaml={self.review_yaml_path}",
            f"result={self.review['result']}",
            f"primary_segment={self.review['primary_segment']}",
            f"classification={self.review['classification']}",
            f"hypothesis={self.review['hypothesis']}",
            f"recommended_experiment={self.review['recommended_experiment']}",
            f"confidence={self.review['confidence']}",
            f"notes={len(self.review['linked_notes'])}",
        ]
        return "\n".join(lines)


@dataclass(frozen=True)
class IssueLedgerResult:
    session_id: str
    issues_path: Path
    issues: tuple[dict[str, Any], ...]

    @property
    def actionable_count(self) -> int:
        return sum(1 for issue in self.issues if issue.get("actionable"))

    def to_text(self) -> str:
        lines = [
            f"session_id={self.session_id}",
            f"issues_file={self.issues_path}",
            f"issues={len(self.issues)}",
            f"actionable_issues={self.actionable_count}",
        ]
        primary = _highest_priority_issue(list(self.issues))
        if primary is not None:
            lines.append(f"highest_priority_issue={primary['id']}")
            lines.append(f"highest_priority_segment={primary['segment_id']}")
        for issue in self.issues:
            lines.append(
                "issue={id} segment={segment_id} type={type} priority={priority} "
                "actionable={actionable} notes={notes}".format(
                    id=issue["id"],
                    segment_id=issue["segment_id"],
                    type=issue["type"],
                    priority=issue["priority"],
                    actionable=str(issue["actionable"]).lower(),
                    notes=",".join(issue["source_notes"]),
                )
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class MultiVariantProposalResult:
    session_id: str
    proposals_path: Path
    proposals: tuple[dict[str, Any], ...]

    def to_text(self) -> str:
        lines = [
            f"session_id={self.session_id}",
            f"proposals_file={self.proposals_path}",
            f"proposals={len(self.proposals)}",
        ]
        for proposal in self.proposals:
            lines.append(
                "variant_id={variant_id} source_issue={source_issue} priority={priority} "
                "status={status}".format(
                    variant_id=proposal["variant_id"],
                    source_issue=proposal["source_issue"],
                    priority=proposal["priority"],
                    status=proposal["status"],
                )
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class UiSummaryResult:
    session_id: str
    summary_path: Path
    summary: dict[str, Any]

    def to_text(self) -> str:
        return "\n".join(
            [
                f"session_id={self.session_id}",
                f"ui_summary={self.summary_path}",
                f"segments={len(self.summary['segments'])}",
                f"notes={self.summary['totals']['notes']}",
                f"issues={self.summary['totals']['issues']}",
                f"proposals={self.summary['totals']['proposals']}",
                f"highest_priority_issue={self.summary.get('highest_priority_issue')}",
            ]
        )


@dataclass(frozen=True)
class CodexTaskResult:
    session_id: str
    issue_id: str
    task_path: Path
    excerpt_path: Path

    def to_text(self) -> str:
        return "\n".join(
            [
                f"session_id={self.session_id}",
                f"issue_id={self.issue_id}",
                f"codex_task={self.task_path}",
                f"route_log_excerpt={self.excerpt_path}",
            ]
        )


def start_session(
    raw_command: str,
    *,
    game_path: Path,
    attempts: int,
    artifacts_root: Path = Path("artifacts/sessions"),
    route_variant: str = "world_1_baseline",
    capture_images: bool = False,
    capture_ticks: bool = True,
) -> LabSessionResult:
    command = parse_command(raw_command)
    if command.action not in {"run_goal", "show_route"}:
        raise LabError(f"Lab cannot start command action yet: {command.action}")
    if command.goal is None:
        raise LabError("Lab command did not resolve to a goal")

    requested_speed = _requested_speed(command)
    run_mode = command.run_mode or "gate"
    contract = load_goal_contract(resolve_goal_path(command.goal))
    session_id = _new_session_id(contract.id)
    session_dir = artifacts_root / session_id
    goal_dir = session_dir / "goal"
    started_at = _now()
    run_settings = _run_settings_for_speed(requested_speed, run_mode, capture_images, capture_ticks)

    attempts_requested = attempts if attempts > 0 else command.attempts or 1
    goal_result = run_goal_contract(
        contract,
        game_path=game_path,
        attempts=attempts_requested,
        artifacts_dir=goal_dir,
        capture_images=run_settings["capture_images"],
        capture_ticks=run_settings["capture_ticks"],
        env_overrides=tuple(run_settings["env_overrides"]),
    )
    ended_at = _now()

    manifest = _session_manifest(
        session_id=session_id,
        command=command,
        route_variant=route_variant,
        requested_speed=requested_speed,
        attempts=attempts_requested,
        session_dir=session_dir,
        goal_result=goal_result,
        run_settings=run_settings,
        started_at=started_at,
        ended_at=ended_at,
    )
    manifest_path = session_dir / "session.yaml"
    _write_yaml(manifest_path, manifest)
    _write_yaml(session_dir / "notes.yaml", {"notes": []})
    _write_latest_session(session_dir)

    return LabSessionResult(
        session_id=session_id,
        session_dir=session_dir,
        manifest_path=manifest_path,
        command=command,
        goal_result=goal_result,
        route_variant=route_variant,
        requested_speed=requested_speed,
        attempts_requested=attempts_requested,
        run_settings=run_settings,
    )


def add_note_to_latest(
    text: str,
    *,
    segment_id: str | None = None,
    attempt_number: int | None = None,
    anchor_type: str | None = None,
    anchor_value: str | int | float | None = None,
    severity: str = "note",
) -> LabNoteResult:
    return add_note(
        _latest_session_dir(),
        text,
        segment_id=segment_id,
        attempt_number=attempt_number,
        anchor_type=anchor_type,
        anchor_value=anchor_value,
        severity=severity,
    )


def add_batch_notes_to_latest(notes: list[dict[str, Any]]) -> list[LabNoteResult]:
    return add_batch_notes(_latest_session_dir(), notes)


def add_batch_notes(session_dir: Path, notes: list[dict[str, Any]]) -> list[LabNoteResult]:
    results: list[LabNoteResult] = []
    for note in notes:
        text = str(note.get("text", "")).strip()
        if not text:
            continue
        results.append(
            add_note(
                session_dir,
                text,
                segment_id=note.get("segment_id"),
                attempt_number=note.get("attempt_number"),
                anchor_type=note.get("anchor_type"),
                anchor_value=note.get("anchor_value"),
                severity=str(note.get("severity") or "note"),
            )
        )
    return results


def add_note(
    session_dir: Path,
    text: str,
    *,
    segment_id: str | None = None,
    attempt_number: int | None = None,
    anchor_type: str | None = None,
    anchor_value: str | int | float | None = None,
    severity: str = "note",
) -> LabNoteResult:
    if not text:
        raise LabError("Note text is required")
    manifest = _load_session_manifest(session_dir)
    notes_path = session_dir / "notes.yaml"
    notes_doc = _load_yaml(notes_path, default={"notes": []})
    notes = notes_doc.setdefault("notes", [])
    if not isinstance(notes, list):
        raise LabError(f"Invalid notes file: {notes_path}")

    note = {
        "id": _next_note_id(notes),
        "created_at": _now(),
        "author": "user",
        "segment_id": _canonical_segment_id(segment_id or _infer_segment_id(text)),
        "attempt_number": attempt_number,
        "anchor": _note_anchor(text, anchor_type, anchor_value),
        "severity": severity,
        "text": text,
        "evidence_paths": _artifact_paths(text),
        "expected_change": _expected_change(text),
        "interpretation": {
            "status": "pending_review",
            "classification": None,
            "linked_events": [],
        },
    }
    notes.append(note)
    _write_yaml(notes_path, notes_doc)
    return LabNoteResult(session_id=str(manifest["session_id"]), notes_path=notes_path, note=note)


def review_latest_session() -> LabReviewResult:
    return review_session(_latest_session_dir())


def review_session(session_dir: Path) -> LabReviewResult:
    manifest = _load_session_manifest(session_dir)
    notes = _load_notes(session_dir)
    route_log = _route_log_path(session_dir, manifest)
    report = review_log(route_log, expected_attempts=int(manifest["attempts_requested"]))
    events = parse_log_events(route_log)
    linked_notes = [_interpret_note(note, events) for note in notes]
    primary_segment = _primary_segment(report.failed_segment, linked_notes)
    classification = _classification(report.failure_class, linked_notes)
    recommended = _recommendation(report.next_experiment, linked_notes)
    result = "passing_evidence" if classification == "none" else "needs_route_hardening"
    review = {
        "review_id": "review_001",
        "session_id": manifest["session_id"],
        "result": result,
        "primary_segment": primary_segment,
        "linked_notes": linked_notes,
        "evidence": _review_evidence(report, linked_notes),
        "classification": classification,
        "hypothesis": _hypothesis(classification, primary_segment, linked_notes),
        "recommended_experiment": recommended,
        "confidence": _confidence(classification, linked_notes),
        "route_review": {
            "failure_class": report.failure_class,
            "failed_segment": report.failed_segment,
            "last_event": report.last_event,
            "max_x": report.max_x,
            "post_probe_clear": report.summary.post_probe_clear,
            "successes": f"{report.summary.success_count}/{report.summary.total}",
        },
    }
    review_yaml_path = session_dir / "review.yaml"
    review_path = session_dir / "review.md"
    _write_yaml(review_yaml_path, review)
    review_path.write_text(_review_markdown(review), encoding="utf-8")
    return LabReviewResult(
        session_id=str(manifest["session_id"]),
        review_path=review_path,
        review_yaml_path=review_yaml_path,
        review=review,
    )


def build_issue_ledger_latest() -> IssueLedgerResult:
    return build_issue_ledger(_latest_session_dir())


def build_issue_ledger(session_dir: Path) -> IssueLedgerResult:
    manifest = _load_session_manifest(session_dir)
    notes = _load_notes(session_dir)
    issues = _issues_from_notes(str(manifest["session_id"]), notes)
    contract = load_goal_contract(resolve_goal_path(str(manifest["goal_id"])))
    for issue in issues:
        issue["relevant_files"] = _relevant_files_for_issue(issue, contract.catalog_path)
    issues_path = session_dir / "issues.yaml"
    _write_yaml(
        issues_path,
        {
            "session_id": manifest["session_id"],
            "issues": issues,
        },
    )
    return IssueLedgerResult(
        session_id=str(manifest["session_id"]),
        issues_path=issues_path,
        issues=tuple(issues),
    )


def propose_variants_from_latest() -> MultiVariantProposalResult:
    return propose_variants(_latest_session_dir())


def propose_variants(session_dir: Path) -> MultiVariantProposalResult:
    manifest = _load_session_manifest(session_dir)
    issues_path = session_dir / "issues.yaml"
    if not issues_path.is_file():
        build_issue_ledger(session_dir)
    issues_doc = _load_yaml(issues_path)
    issues = [issue for issue in issues_doc.get("issues", []) if isinstance(issue, dict)]
    proposals: list[dict[str, Any]] = []
    for issue in sorted((issue for issue in issues if issue.get("actionable")), key=_issue_sort_key):
        proposals.append(_proposal_from_issue(manifest, issue))

    proposals_path = session_dir / "variant_proposals.yaml"
    _write_yaml(
        proposals_path,
        {
            "session_id": manifest["session_id"],
            "proposals": proposals,
        },
    )
    for proposal in proposals:
        _write_yaml(_variant_path(str(proposal["variant_id"])), proposal)
    return MultiVariantProposalResult(
        session_id=str(manifest["session_id"]),
        proposals_path=proposals_path,
        proposals=tuple(proposals),
    )


def write_ui_summary_latest() -> UiSummaryResult:
    return write_ui_summary(_latest_session_dir())


def write_ui_summary(
    session_dir: Path,
    *,
    segment_catalog_path: Path | None = None,
) -> UiSummaryResult:
    manifest = _load_session_manifest(session_dir)
    if segment_catalog_path is None:
        contract = load_goal_contract(resolve_goal_path(str(manifest["goal_id"])))
        segment_catalog_path = contract.catalog_path
    notes = _load_notes(session_dir)
    if not (session_dir / "issues.yaml").is_file():
        build_issue_ledger(session_dir)
    issues = _load_yaml(session_dir / "issues.yaml").get("issues", [])
    if not (session_dir / "variant_proposals.yaml").is_file():
        propose_variants(session_dir)
    proposals = _load_yaml(session_dir / "variant_proposals.yaml").get("proposals", [])
    segments = _load_segment_summaries(segment_catalog_path)
    highest = _highest_priority_issue([issue for issue in issues if isinstance(issue, dict)])
    segment_rows = []
    for segment in segments:
        segment_id = segment["id"]
        segment_notes = [note for note in notes if _canonical_segment_id(str(note.get("segment_id"))) == segment_id]
        segment_issues = [issue for issue in issues if isinstance(issue, dict) and issue.get("segment_id") == segment_id]
        issue_ids = {issue["id"] for issue in segment_issues}
        segment_proposals = [
            proposal
            for proposal in proposals
            if isinstance(proposal, dict) and proposal.get("source_issue") in issue_ids
        ]
        segment_rows.append(
            {
                "id": segment_id,
                "name": segment.get("name", segment_id),
                "status": segment.get("status", "unknown"),
                "notes": len(segment_notes),
                "issues": len(segment_issues),
                "open_issues": sum(1 for issue in segment_issues if issue.get("status") == "open"),
                "highest_priority_issue": _issue_id(_highest_priority_issue(segment_issues)),
                "proposals": len(segment_proposals),
                "validation_status": _segment_validation_status(segment_proposals),
            }
        )

    summary = {
        "session_id": manifest["session_id"],
        "session_dir": str(session_dir),
        "goal_id": manifest.get("goal_id"),
        "route_variant": manifest.get("route_variant"),
        "highest_priority_issue": _issue_id(highest),
        "segments": segment_rows,
        "totals": {
            "notes": len(notes),
            "issues": len(issues),
            "actionable_issues": sum(1 for issue in issues if isinstance(issue, dict) and issue.get("actionable")),
            "proposals": len(proposals),
        },
    }
    summary_path = session_dir / "ui_summary.yaml"
    _write_yaml(summary_path, summary)
    return UiSummaryResult(session_id=str(manifest["session_id"]), summary_path=summary_path, summary=summary)


def write_codex_task_latest(issue_id: str) -> CodexTaskResult:
    return write_codex_task(_latest_session_dir(), issue_id)


def write_codex_task(session_dir: Path, issue_id: str) -> CodexTaskResult:
    manifest = _load_session_manifest(session_dir)
    contract = load_goal_contract(resolve_goal_path(str(manifest["goal_id"])))
    if not (session_dir / "issues.yaml").is_file():
        build_issue_ledger(session_dir)
    issues = _load_yaml(session_dir / "issues.yaml").get("issues", [])
    issue = next((item for item in issues if isinstance(item, dict) and item.get("id") == issue_id), None)
    if issue is None:
        raise LabError(f"Issue not found in latest session: {issue_id}")
    if not re.fullmatch(r"[a-z0-9_]{3,160}", issue_id):
        raise LabError(f"Invalid issue id: {issue_id!r}")
    notes = [note for note in _load_notes(session_dir) if note.get("id") in set(issue.get("source_notes", []))]
    route_log = _route_log_path(session_dir, manifest)
    session_root = os.path.realpath(os.fspath(session_dir))
    excerpt_real = os.path.realpath(
        os.path.join(session_root, "excerpts", f"{issue_id}.log")
    )
    task_real = os.path.realpath(
        os.path.join(session_root, "codex_tasks", f"{issue_id}.yaml")
    )
    safe_prefix = session_root.rstrip(os.sep) + os.sep
    if not excerpt_real.startswith(safe_prefix) or not task_real.startswith(safe_prefix):
        raise LabError("Codex task paths escape the selected lab session")
    excerpt_path = Path(excerpt_real)
    excerpt_path.parent.mkdir(parents=True, exist_ok=True)
    excerpt_path.write_text(_route_log_excerpt(route_log, issue), encoding="utf-8")
    task_path = Path(task_real)
    task = {
        "task_id": f"codex_{issue_id}",
        "created_at": _now(),
        "session_id": manifest["session_id"],
        "issue_id": issue_id,
        "objective": (
            "Return one concrete Beat Mario route-patch/v1 artifact for the selected "
            "bounded issue. Do not declare review, approval, or validation results."
        ),
        "selected_issue": issue,
        "relevant_notes": notes,
        "inputs": {
            "session_manifest": str(session_dir / "session.yaml"),
            "notes": str(session_dir / "notes.yaml"),
            "issue_ledger": str(session_dir / "issues.yaml"),
            "review": str(session_dir / "review.yaml"),
            "route_log_excerpt": str(excerpt_path),
            "segment_catalog": str(contract.catalog_path),
            "relevant_files": _relevant_files_for_issue(issue, contract.catalog_path),
        },
        "expected_output": {
            "artifact": "One YAML document using schema_version beat-mario.route-patch/v1.",
            "source": {
                "kind": "codex_task",
                "session_id": manifest["session_id"],
                "issue_id": issue_id,
                "note_ids": [str(note["id"]) for note in notes],
                "task_id": f"codex_{issue_id}",
                "task_packet": str(task_path),
            },
            "required_fields": [
                "patch_id",
                "variant_id",
                "parent_variant",
                "repository_base_commit",
                "allowed_files",
                "preimage_sha256",
                "operations",
                "expected_postimage_sha256",
                "summary",
                "rollback_description",
                "timestamps",
                "provenance",
            ],
            "operation_contract": (
                "Use replace_text operations containing path, complete UTF-8 content, "
                "preimage_sha256, and expected_postimage_sha256."
            ),
            "validation": (
                "Do not supply a command or result. Route Lab selects and runs an "
                "internal validation profile after review and isolated application."
            ),
        },
    }
    _write_yaml(task_path, task)
    return CodexTaskResult(
        session_id=str(manifest["session_id"]),
        issue_id=issue_id,
        task_path=task_path,
        excerpt_path=excerpt_path,
    )


def _session_manifest(
    *,
    session_id: str,
    command: AgentCommand,
    route_variant: str,
    requested_speed: float,
    attempts: int,
    session_dir: Path,
    goal_result: GoalRunResult,
    run_settings: dict[str, Any],
    started_at: str,
    ended_at: str,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "goal_id": command.goal,
        "route_variant": route_variant,
        "run_mode": command.run_mode,
        "requested_speed": requested_speed,
        "attempts_requested": attempts,
        "started_at": started_at,
        "ended_at": ended_at,
        "artifacts_dir": str(session_dir),
        "inputs": {
            "command": command.raw,
            "game_file_env": "SMB3_GAME_FILE",
        },
        "run_settings": {
            key: value for key, value in run_settings.items() if key != "env_overrides"
        },
        "outputs": {
            "route_log": "goal/fceux_1_1.log",
            "state_trace": "state_trace.jsonl",
            "screenshots_dir": "goal/images",
            "notes_file": "notes.yaml",
            "review_file": "review.md",
            "variant_proposal": "variant_proposal.yaml",
        },
        "result": {
            "status": "passed" if goal_result.metrics_passed else "failed",
            "metrics_passed": goal_result.metrics_passed,
            "successes": f"{goal_result.summary.success_count}/{goal_result.summary.total}",
            "bad_states": f"{goal_result.summary.bad_state_count}/{goal_result.summary.total}",
            "post_probe_last_event": goal_result.summary.post_probe_last_event,
            "post_probe_clear": goal_result.summary.post_probe_clear,
        },
    }


def _run_settings_for_speed(
    speed: float,
    run_mode: str,
    capture_images: bool,
    capture_ticks: bool,
) -> dict[str, Any]:
    if speed < 1 or speed > 100:
        raise LabError("Speed must be between 1 and 100")
    if speed >= 100:
        frame_sleep = 0
        speed_mode = "maximum"
    elif run_mode == "watch" or speed < 100:
        frame_sleep = round(1 / (60 * speed), 6)
        speed_mode = "normal"
    else:
        frame_sleep = 0
        speed_mode = "maximum"
    env_overrides = [
        f"SMB3_AGENT_SPEED_MODE={speed_mode}",
        f"SMB3_AGENT_FRAME_SLEEP_SECONDS={frame_sleep}",
    ]
    return {
        "emulator": "fceux",
        "speed_mode": speed_mode,
        "frame_sleep_seconds": frame_sleep,
        "capture_images": capture_images,
        "capture_ticks": capture_ticks,
        "env_overrides": env_overrides,
    }


def _requested_speed(command: AgentCommand) -> float:
    if command.speed is not None:
        return float(command.speed or 1)
    return 100


def _new_session_id(goal_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{goal_id}"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        if default is not None:
            return default
        raise LabError(f"File not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise LabError(f"Expected YAML mapping: {path}")
    return data


def _write_latest_session(session_dir: Path) -> None:
    LATEST_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_SESSION_PATH.write_text(str(session_dir) + "\n", encoding="utf-8")


def _latest_session_dir() -> Path:
    if not LATEST_SESSION_PATH.is_file():
        raise LabError("No latest lab session exists")
    sessions_root = os.path.realpath("artifacts/sessions")
    session_real = os.path.realpath(
        LATEST_SESSION_PATH.read_text(encoding="utf-8").strip()
    )
    if not session_real.startswith(sessions_root.rstrip(os.sep) + os.sep):
        raise LabError("Latest session path escapes the lab artifact root")
    session_dir = Path(session_real)
    if not session_dir.is_dir():
        raise LabError(f"Latest session directory does not exist: {session_dir}")
    return session_dir


def _load_session_manifest(session_dir: Path) -> dict[str, Any]:
    return _load_yaml(session_dir / "session.yaml")


def _load_notes(session_dir: Path) -> list[dict[str, Any]]:
    notes_doc = _load_yaml(session_dir / "notes.yaml", default={"notes": []})
    notes = notes_doc.get("notes", [])
    if not isinstance(notes, list):
        raise LabError("notes.yaml must contain a notes list")
    return [note for note in notes if isinstance(note, dict)]


def _route_log_path(session_dir: Path, manifest: dict[str, Any]) -> Path:
    route_log = manifest.get("outputs", {}).get("route_log", "goal/fceux_1_1.log")
    session_root = os.path.realpath(os.fspath(session_dir))
    route_log_real = os.path.realpath(os.path.join(session_root, str(route_log)))
    if not route_log_real.startswith(session_root.rstrip(os.sep) + os.sep):
        raise LabError("Route log path escapes the selected lab session")
    return Path(route_log_real)


def _next_note_id(notes: list[Any]) -> str:
    return f"note_{len(notes) + 1:03d}"


def _infer_segment_id(text: str) -> str:
    lowered = text.lower()
    if "1-1" in lowered or "1 1" in lowered:
        return "world_1_1_clear"
    if "1-2" in lowered or "1 2" in lowered:
        return "world_1_2_clear"
    if "1-3" in lowered or "1 3" in lowered:
        return "world_1_3_whistle"
    if "fortress" in lowered or "castle" in lowered:
        return "world_1_fortress_whistle"
    return "unknown"


def _canonical_segment_id(segment_id: str | None) -> str:
    aliases = {
        "world_1_1": "world_1_1_clear",
        "1-1": "world_1_1_clear",
        "world_1_2": "world_1_2_clear",
        "1-2": "world_1_2_clear",
        "world_1_4": "world_1_4_clear",
        "1-4": "world_1_4_clear",
        "fortress": "world_1_fortress_whistle",
        "castle": "world_1_fortress_whistle",
    }
    if segment_id is None:
        return "unknown"
    return aliases.get(segment_id, segment_id)


def _note_anchor(text: str, anchor_type: str | None, anchor_value: str | int | float | None) -> dict[str, Any]:
    if anchor_type is not None:
        return {"type": anchor_type, "value": _coerce_anchor_value(anchor_value)}
    timer_match = re.search(r"\b(?P<timer>\d{2,3})\s*(?:timer|seconds?\s+remaining|remaining)\b", text, re.I)
    if timer_match is None:
        timer_match = re.search(r"\baround\s+(?P<timer>\d{2,3})\b", text, re.I)
    if timer_match is not None:
        return {"type": "in_game_timer", "value": int(timer_match.group("timer"))}
    return {"type": "free_text", "value": None}


def _coerce_anchor_value(value: str | int | float | None) -> str | int | float | None:
    if isinstance(value, str) and value.removeprefix("-").isdigit():
        return int(value)
    return value


def _artifact_paths(text: str) -> list[str]:
    suffixes = (".png", ".jpg", ".jpeg", ".gif", ".gd", ".log", ".jsonl", ".yaml")
    matches: list[str] = []
    for token in text.split():
        starts = [index for marker in ("artifacts/", "/") if (index := token.find(marker)) >= 0]
        if not starts:
            continue
        candidate = token[min(starts) :].rstrip(".,;:)")
        if candidate.lower().endswith(suffixes):
            matches.append(candidate)
    return list(dict.fromkeys(matches))


def _expected_change(text: str) -> str:
    lowered = text.lower()
    if "fall" in lowered or "hole" in lowered:
        return "Add a safer jump, slowdown, or verification marker around the noted hazard."
    if "too slow" in lowered:
        return "Adjust playback or input timing earlier while preserving the parent route gate."
    if "too fast" in lowered:
        return "Add a delay or guard before the noted action."
    return "Review trace evidence and propose one controlled route experiment."


def _interpret_note(note: dict[str, Any], events: tuple[LogEvent, ...]) -> dict[str, Any]:
    linked = _nearest_events(note, events)
    classification = _note_classification(note)
    interpreted = dict(note)
    interpreted["interpretation"] = {
        "status": "reviewed",
        "classification": classification,
        "linked_events": linked,
    }
    return interpreted


def _nearest_events(note: dict[str, Any], events: tuple[LogEvent, ...]) -> list[dict[str, Any]]:
    anchor = note.get("anchor", {})
    if anchor.get("type") == "frame" and isinstance(anchor.get("value"), int):
        target = int(anchor["value"])
        ordered = sorted(
            (event for event in events if event.frame is not None),
            key=lambda event: abs(int(event.frame or 0) - target),
        )
        return [_event_ref(event) for event in ordered[:3]]
    segment = note.get("segment_id")
    if _canonical_segment_id(str(segment)) == "world_1_1_clear":
        segment_events = [event for event in events if event.event.startswith("attempt_")]
        return [_event_ref(event) for event in segment_events[-3:]]
    if events:
        return [_event_ref(events[-1])]
    return []


def _event_ref(event: LogEvent) -> dict[str, Any]:
    return {
        "frame": event.frame,
        "event": event.event,
        "x": event.fields.get("x"),
        "y": event.fields.get("y"),
    }


def _note_classification(note: dict[str, Any]) -> str:
    text = str(note.get("text", "")).lower()
    if "fall" in text or "hole" in text or "jump" in text:
        return "input_timing"
    if "wrong" in text or "map" in text:
        return "wrong_route_state"
    if "died" in text or "life" in text:
        return "life_lost"
    return "needs_review"


def _primary_segment(failed_segment: str, linked_notes: list[dict[str, Any]]) -> str:
    for note in linked_notes:
        segment = note.get("segment_id")
        if segment and segment != "unknown":
            return str(segment)
    return failed_segment


def _classification(failure_class: str, linked_notes: list[dict[str, Any]]) -> str:
    if linked_notes:
        note_class = linked_notes[0].get("interpretation", {}).get("classification")
        if note_class and note_class != "needs_review":
            return str(note_class)
    return failure_class


def _recommendation(route_experiment: str, linked_notes: list[dict[str, Any]]) -> str:
    for note in linked_notes:
        expected = note.get("expected_change")
        if expected:
            return str(expected)
    return route_experiment


def _review_evidence(report: Any, linked_notes: list[dict[str, Any]]) -> list[Any]:
    evidence: list[Any] = [note["id"] for note in linked_notes]
    evidence.append(
        {
            "event": report.last_event,
            "max_x": report.max_x,
            "successes": f"{report.summary.success_count}/{report.summary.total}",
        }
    )
    return evidence


def _hypothesis(classification: str, primary_segment: str, linked_notes: list[dict[str, Any]]) -> str:
    if linked_notes:
        return f"{primary_segment} needs a controlled route variant for the user-noted {classification} risk."
    if classification == "none":
        return "No route issue found in this session."
    return f"{primary_segment} needs review for {classification}."


def _confidence(classification: str, linked_notes: list[dict[str, Any]]) -> str:
    if classification == "none":
        return "high"
    if linked_notes:
        return "medium"
    return "low"


def _review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Lab Review",
        "",
        f"- session: {review['session_id']}",
        f"- result: {review['result']}",
        f"- primary_segment: {review['primary_segment']}",
        f"- classification: {review['classification']}",
        f"- confidence: {review['confidence']}",
        "",
        "## Hypothesis",
        "",
        review["hypothesis"],
        "",
        "## Recommended Experiment",
        "",
        review["recommended_experiment"],
        "",
        "## Linked Notes",
        "",
    ]
    if review["linked_notes"]:
        for note in review["linked_notes"]:
            lines.append(f"- {note['id']}: {note['text']}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _suggested_change_file(segment: str) -> str:
    if _canonical_segment_id(segment) == "world_1_1_clear":
        return "data/routes/scripts/world_1_1_clear_v0.yaml"
    return "scripts/fceux_1_1_agent.lua"


def batch_summary_to_json(summary: BatchSummary) -> str:
    return json.dumps(asdict(summary), sort_keys=True)


def _issues_from_notes(session_id: str, notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for note in notes:
        issue_type = _issue_type_for_note(note)
        segment_id = _canonical_segment_id(str(note.get("segment_id") or "unknown"))
        grouped.setdefault((segment_id, issue_type), []).append(note)

    issue_counters: dict[str, int] = {}
    issues: list[dict[str, Any]] = []
    for (segment_id, issue_type), source_notes in sorted(grouped.items(), key=lambda item: _group_sort_key(item[0])):
        issue_counters[segment_id] = issue_counters.get(segment_id, 0) + 1
        priority = _issue_priority(issue_type, source_notes)
        issue_id = f"issue_{segment_id}_{issue_counters[segment_id]:03d}"
        actionable = issue_type not in {
            "positive_evidence",
            "evidence_attachment",
            "expected_behavior",
            "objective_update",
            "guide_detail",
        }
        issues.append(
            {
                "id": issue_id,
                "session_id": session_id,
                "segment_id": segment_id,
                "type": issue_type,
                "priority": priority,
                "status": "open" if actionable else "accepted",
                "actionable": actionable,
                "source_notes": [str(note["id"]) for note in source_notes],
                "evidence_paths": list(
                    dict.fromkeys(
                        str(path)
                        for note in source_notes
                        for path in (note.get("evidence_paths") or _artifact_paths(str(note.get("text", ""))))
                    )
                ),
                "summary": _issue_summary(segment_id, issue_type, source_notes),
                "proposed_next_step": _issue_next_step(segment_id, issue_type),
            }
        )
    return sorted(issues, key=_issue_sort_key)


def _group_sort_key(key: tuple[str, str]) -> tuple[int, str, str]:
    segment_id, issue_type = key
    return (_priority_rank(_issue_priority(issue_type, [])), segment_id, issue_type)


def _issue_type_for_note(note: dict[str, Any]) -> str:
    text = str(note.get("text", "")).lower()
    severity = str(note.get("severity", "")).lower()
    if severity in {"positive", "success", "passing"}:
        return "positive_evidence"
    if severity == "note" and (note.get("evidence_paths") or _artifact_paths(text)):
        return "evidence_attachment"
    if severity == "objective":
        return "objective_update"
    if severity == "map_action":
        return "map_action"
    if severity == "guide_detail":
        return "guide_detail"
    if "carry" in text or "leak" in text or "dies first" in text or "die first" in text:
        return "recovery_bug"
    if severity in {"failure", "error"} and ("fire" in text or "death" in text or "dies" in text):
        return "recovery_bug"
    if "wrong" in text or "1-4" in text or "map" in text:
        return "wrong_route_state"
    if "fall" in text or "hole" in text or "jump" in text or "clock" in text:
        return "route_hardening" if severity == "harden" else "input_timing"
    if severity == "harden":
        return "route_hardening"
    if "expected" in text or "not complete" in text or "not a complete" in text:
        return "expected_behavior"
    if "perfect" in text or "good" in text:
        return "positive_evidence"
    return "unknown"


def _issue_priority(issue_type: str, source_notes: list[dict[str, Any]]) -> str:
    if issue_type == "recovery_bug":
        return "high"
    if issue_type in {"wrong_route_state", "route_hardening", "input_timing"}:
        return "medium"
    if issue_type in {"expected_behavior", "positive_evidence", "evidence_attachment", "objective_update", "guide_detail"}:
        return "none"
    if issue_type == "map_action":
        return "medium"
    if any(str(note.get("severity", "")).lower() == "harden" for note in source_notes):
        return "medium"
    return "low"


def _priority_rank(priority: str) -> int:
    return {
        "high": 0,
        "medium": 1,
        "low": 2,
        "none": 3,
    }.get(priority, 4)


def _issue_sort_key(issue: dict[str, Any]) -> tuple[int, str]:
    return (_priority_rank(str(issue.get("priority", "low"))), str(issue.get("id", "")))


def _issue_summary(segment_id: str, issue_type: str, source_notes: list[dict[str, Any]]) -> str:
    raw_text = " ".join(str(note.get("text", "")) for note in source_notes).strip()
    if raw_text:
        return raw_text
    return f"{segment_id} has {issue_type.replace('_', ' ')} evidence."


def _issue_next_step(segment_id: str, issue_type: str) -> str:
    if issue_type == "recovery_bug":
        return "Add input cleanup and state reclassification after the failed/death path."
    if issue_type == "wrong_route_state":
        return "Add a map-state guard and recovery before continuing route input."
    if issue_type == "route_hardening":
        return "Add a safer input window or progress guard around the noted hazard."
    if issue_type == "input_timing":
        return "Tune one input timing window and validate without broad route changes."
    if issue_type == "expected_behavior":
        return "Record as expected route behavior and exclude from failure classification."
    if issue_type == "positive_evidence":
        return "Record as passing evidence for this segment."
    if issue_type == "objective_update":
        return "Record the objective update for this location."
    if issue_type == "guide_detail":
        return "Record the guide detail as route context."
    if issue_type == "map_action":
        return "Add or verify the map movement/action before continuing route input."
    return "Review trace evidence and decide whether this should become actionable."


def _highest_priority_issue(issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    actionable = [issue for issue in issues if issue.get("actionable")]
    ranked = sorted(actionable or issues, key=_issue_sort_key)
    return ranked[0] if ranked else None


def _issue_id(issue: dict[str, Any] | None) -> str | None:
    if issue is None:
        return None
    return str(issue["id"])


def _proposal_from_issue(manifest: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any]:
    variant_id = _variant_id_from_issue(issue)
    return {
        "variant_id": variant_id,
        "parent_variant": manifest.get("route_variant", "world_1_baseline"),
        "status": "proposed",
        "created_at": _now(),
        "reason": issue["proposed_next_step"],
        "source_session": manifest["session_id"],
        "source_issue": issue["id"],
        "source_notes": issue["source_notes"],
        "priority": issue["priority"],
        "changes": [
            {
                "file": _suggested_change_file(str(issue["segment_id"])),
                "summary": issue["proposed_next_step"],
            }
        ],
        "route_patch": {
            "required": True,
            "schema_version": "beat-mario.route-patch/v1",
            "patch_id": None,
            "execution_status": "awaiting_normalized_patch",
        },
        "validation": {
            "profile": "internally_selected_after_patch_import",
            "workflow": f"python -m smb3_agent lab patch validate PATCH_ID  # variant {variant_id}",
            "promotion_gate": "10/10 for targeted segment or configured goal gate, with no parent-route regression",
        },
        "outcome": {
            "status": "untested",
            "artifacts_dir": None,
        },
    }


def _variant_id_from_issue(issue: dict[str, Any]) -> str:
    segment = re.sub(r"[^a-z0-9_]+", "_", str(issue["segment_id"]).lower()).strip("_") or "route"
    issue_type = str(issue["type"])
    suffix = "recovery" if issue_type == "recovery_bug" else "harden"
    anchor = _first_numeric_anchor(issue)
    anchor_part = f"_{anchor}" if anchor is not None else ""
    base = f"{segment}_{suffix}{anchor_part}_a"
    candidate = base
    index = 1
    while _variant_path(candidate).exists():
        index += 1
        candidate = f"{base[:-1]}{chr(96 + min(index, 26))}"
    return candidate


def _variant_path(variant_id: str) -> Path:
    variants_root = os.path.realpath("data/variants")
    variant_real = os.path.realpath(
        os.path.join(variants_root, f"{variant_id}.yaml")
    )
    if not variant_real.startswith(variants_root.rstrip(os.sep) + os.sep):
        raise LabError("Variant path escapes the variant artifact root")
    return Path(variant_real)


def _first_numeric_anchor(issue: dict[str, Any]) -> int | None:
    match = re.search(r"\b(\d{2,3})\b", str(issue.get("summary", "")))
    return int(match.group(1)) if match else None


def _load_segment_summaries(segment_catalog_path: Path) -> list[dict[str, Any]]:
    data = _load_yaml(segment_catalog_path)
    segments = data.get("segments", [])
    if not isinstance(segments, list):
        raise LabError(f"Segment catalog has no segment list: {segment_catalog_path}")
    return [
        {
            "id": segment.get("id"),
            "name": segment.get("name"),
            "status": segment.get("status"),
        }
        for segment in segments
        if isinstance(segment, dict) and segment.get("id")
    ]


def _segment_validation_status(proposals: list[dict[str, Any]]) -> str:
    if not proposals:
        return "none"
    if any(proposal.get("outcome", {}).get("metrics_passed") for proposal in proposals):
        return "passed"
    if any(proposal.get("outcome", {}).get("status") not in {None, "untested"} for proposal in proposals):
        return "failed"
    return "untested"


def _relevant_files_for_issue(issue: dict[str, Any], catalog_path: Path) -> list[str]:
    segment_id = str(issue.get("segment_id", ""))
    files = [_suggested_change_file(segment_id), str(catalog_path)]
    return list(dict.fromkeys(files))


def _route_log_excerpt(route_log: Path, issue: dict[str, Any], max_lines: int = 80) -> str:
    if not route_log.is_file():
        return ""
    lines = route_log.read_text(errors="replace").splitlines()
    segment_id = str(issue.get("segment_id", ""))
    keywords = _excerpt_keywords(segment_id)
    selected = [line for line in lines if any(keyword in line for keyword in keywords)]
    if not selected:
        selected = lines[-max_lines:]
    return "\n".join(selected[-max_lines:]) + ("\n" if selected else "")


def _excerpt_keywords(segment_id: str) -> tuple[str, ...]:
    if _canonical_segment_id(segment_id) == "world_1_1_clear":
        return ("attempt_",)
    if _canonical_segment_id(segment_id) == "world_1_2_clear":
        return ("post_probe_1_2",)
    if segment_id == "world_1_3_whistle":
        return ("post_probe_1_3",)
    if segment_id == "world_1_fortress_whistle":
        return ("post_probe_1_fortress",)
    if segment_id == "world_1_4_clear":
        return ("post_probe_1_4",)
    return ("post_probe_", "attempt_")
