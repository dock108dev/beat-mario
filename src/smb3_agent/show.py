from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import traceback
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml

from smb3_agent.companion_session import Observation, ObservationSource
from smb3_agent.fceux_images import convert_gd_directory, write_contact_sheet
from smb3_agent.goals import load_goal_contract, resolve_goal_path
from smb3_agent.observe import build_state_trace, write_state_trace
from smb3_agent.review import LogEvent, parse_log_events
from smb3_agent.segments import load_segment_catalog, validate_goal_segments
from smb3_agent.tell import ProvenanceReference, load_tell_knowledge


SHOW_DEFINITIONS_PATH = Path("data/show/mario.yaml")
SHOW_ARTIFACTS_ROOT = Path("artifacts/show/world_1_1_clear")
SHOW_SCRIPT_PATH = Path("scripts/fceux_1_1_agent.lua")
SUPPORTED_SHOW_SEGMENT = "world_1_1_clear"
SHOW_EVENT_IDS = {
    "attempt_1_fresh_start",
    "attempt_1_reached_end_x",
    "attempt_1_success_course_clear",
    "attempt_1_bad_state",
    "show_input_stopped",
}


class ShowError(ValueError):
    pass


class ShowLifecycle(str, Enum):
    READY = "ready"
    STARTING = "starting"
    ACTIVE = "active"
    STOP_REQUESTED = "stop_requested"
    INPUT_STOPPED = "input_stopped"
    CANCELLED = "cancelled"
    TAKEN_OVER = "taken_over"
    FAILED = "failed"
    DEMONSTRATED = "demonstrated"


class ShowCueStatus(str, Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    OBSERVED = "observed"
    MISSED = "missed"
    CANCELLED = "cancelled"


_TRANSITIONS = {
    ShowLifecycle.READY: {ShowLifecycle.STARTING},
    ShowLifecycle.STARTING: {ShowLifecycle.ACTIVE, ShowLifecycle.FAILED, ShowLifecycle.STOP_REQUESTED},
    ShowLifecycle.ACTIVE: {ShowLifecycle.STOP_REQUESTED, ShowLifecycle.INPUT_STOPPED, ShowLifecycle.FAILED},
    ShowLifecycle.STOP_REQUESTED: {ShowLifecycle.INPUT_STOPPED, ShowLifecycle.FAILED},
    ShowLifecycle.INPUT_STOPPED: {
        ShowLifecycle.CANCELLED,
        ShowLifecycle.TAKEN_OVER,
        ShowLifecycle.DEMONSTRATED,
        ShowLifecycle.FAILED,
    },
    ShowLifecycle.CANCELLED: set(),
    ShowLifecycle.TAKEN_OVER: set(),
    ShowLifecycle.FAILED: set(),
    ShowLifecycle.DEMONSTRATED: set(),
}


@dataclass(frozen=True)
class ShowArtifactReference:
    role: str
    path: str
    cue_id: str | None = None
    event_id: str | None = None
    frame: int | None = None


@dataclass(frozen=True)
class ShowCue:
    cue_id: str
    instruction: str
    expected_visual_cue: str
    trigger_event: str
    status: ShowCueStatus = ShowCueStatus.WAITING
    provenance: tuple[ProvenanceReference, ...] = ()
    frame: int | None = None
    event_position: int | None = None


@dataclass(frozen=True)
class ShowDefinition:
    game_id: str
    goal_id: str
    segment_id: str
    tell_segment_id: str
    starting_state_event: str
    success_event: str
    failure_events: tuple[str, ...]
    stop_event: str
    replay_roles: tuple[str, ...]
    cues: tuple[ShowCue, ...]


@dataclass(frozen=True)
class ShowRequest:
    adapter_id: str
    game_id: str
    goal_id: str
    segment_id: str
    observation: Observation
    game_path: Path
    trusted_starting_state: str
    demonstration_stop_event: str
    recovery_boundary: str
    protected_decisions: tuple[str, ...]
    review_only: bool = True
    promotable: bool = False
    counts_toward_reliability: bool = False

    def validate(self) -> None:
        self.observation.validate()
        if self.observation.source is not ObservationSource.ADAPTER:
            raise ShowError("Show requires an adapter-observed starting state")
        if not self.observation.trusted or not self.observation.evidence_references:
            raise ShowError("Show requires a fresh adapter-verifiable starting state")
        if self.observation.game_id != self.game_id:
            raise ShowError("observation and Show game identities disagree")
        if self.segment_id != SUPPORTED_SHOW_SEGMENT:
            raise ShowError(f"Show is unavailable for {self.segment_id}; V2.3 supports only {SUPPORTED_SHOW_SEGMENT}")
        if not self.game_path.is_file():
            raise ShowError(f"configured game file was not found: {self.game_path}")
        if not self.review_only or self.promotable or self.counts_toward_reliability:
            raise ShowError("Show must remain review-only and non-promotable")


@dataclass(frozen=True)
class ShowCapability:
    available: bool
    reason: str
    definition: ShowDefinition | None = None


@dataclass(frozen=True)
class ShowOutcome:
    demonstration_game_owned_success: bool
    player_completion: bool = False
    authoritative_acceptance: bool = False
    review_only: bool = True
    promotable: bool = False
    counts_toward_reliability: bool = False
    input_stopped: bool = False
    process_relinquished: bool = False
    cue_reconciled: bool = False
    explanation: str = ""
    artifacts: tuple[ShowArtifactReference, ...] = ()

    def validate(self) -> None:
        if self.player_completion or self.authoritative_acceptance:
            raise ShowError("Show cannot claim player completion or authoritative acceptance")
        if not self.review_only or self.promotable or self.counts_toward_reliability:
            raise ShowError("Show outcome policy is invalid")
        if self.demonstration_game_owned_success and not (
            self.input_stopped and self.process_relinquished and self.cue_reconciled and self.artifacts
        ):
            raise ShowError("demonstrated outcome lacks stopped input, relinquishment, artifacts, or cue reconciliation")


@dataclass(frozen=True)
class ShowSession:
    session_id: str
    request: ShowRequest
    definition: ShowDefinition
    lifecycle: ShowLifecycle = ShowLifecycle.READY
    cues: tuple[ShowCue, ...] = ()
    current_cue_id: str | None = None
    activity: tuple[str, ...] = ()
    artifacts_dir: Path | None = None
    outcome: ShowOutcome | None = None
    error: str | None = None
    control_returned: bool = False

    def transition(self, target: ShowLifecycle, *, activity: str | None = None, **changes: Any) -> ShowSession:
        if target not in _TRANSITIONS[self.lifecycle]:
            raise ShowError(f"invalid Show lifecycle transition: {self.lifecycle.value} -> {target.value}")
        items = self.activity + ((activity,) if activity else ())
        return replace(self, lifecycle=target, activity=items, **changes)


@dataclass(frozen=True)
class CueReconciliation:
    passed: bool
    cues: tuple[ShowCue, ...]
    first_problem: str | None
    success_event_observed: bool
    manifest: tuple[ShowArtifactReference, ...]


def load_show_definition(path: Path = SHOW_DEFINITIONS_PATH) -> ShowDefinition:
    raw = yaml.safe_load(path.read_text()) if path.is_file() else None
    if not isinstance(raw, dict) or raw.get("schema") != "game-companion-show/v1":
        raise ShowError("Show definition requires schema game-companion-show/v1")
    definitions = raw.get("definitions")
    if not isinstance(definitions, list) or len(definitions) != 1:
        raise ShowError("V2.3 requires exactly one Show definition")
    item = definitions[0]
    if not isinstance(item, dict):
        raise ShowError("Show definition must be a mapping")
    cues_raw = item.get("cues")
    if not isinstance(cues_raw, list) or not cues_raw:
        raise ShowError("Show definition requires ordered cues")
    goal_id = str(item["goal_id"])
    segment_id = str(item["segment_id"])
    provenance = (
        ProvenanceReference("goal_contract", goal_id, "Selected Mario goal"),
        ProvenanceReference("segment_contract", segment_id, "Accepted Mario segment"),
        ProvenanceReference("accepted_game_knowledge", segment_id, "Validated Show cue catalog"),
        ProvenanceReference("accepted_evidence", "fceux_1_1_reliability_gate", "Accepted 1-1 evidence"),
    )
    cues = tuple(
        ShowCue(
            cue_id=str(cue["cue_id"]),
            instruction=str(cue["instruction"]),
            expected_visual_cue=str(cue["expected_visual_cue"]),
            trigger_event=str(cue["trigger_event"]),
            provenance=provenance,
        )
        for cue in cues_raw
    )
    definition = ShowDefinition(
        game_id=str(item["game_id"]), goal_id=goal_id,
        segment_id=segment_id, tell_segment_id=str(item["tell_segment_id"]),
        starting_state_event=str(item["starting_state_event"]), success_event=str(item["success_event"]),
        failure_events=tuple(str(value) for value in item["failure_events"]),
        stop_event=str(item["stop_event"]), replay_roles=tuple(str(value) for value in item["replay_roles"]),
        cues=cues,
    )
    validate_show_definition(definition, declared_game=str(raw.get("game", "")))
    return definition


def validate_show_definition(definition: ShowDefinition, *, declared_game: str | None = None) -> None:
    if declared_game is not None and definition.game_id != declared_game:
        raise ShowError("Show catalog and definition game identities disagree")
    if definition.segment_id != SUPPORTED_SHOW_SEGMENT or definition.tell_segment_id != definition.segment_id:
        raise ShowError("Show segment must be the supported Tell segment")
    contract = load_goal_contract(resolve_goal_path(definition.goal_id))
    catalog = load_segment_catalog(contract.catalog_path)
    validate_goal_segments(contract, catalog)
    segment = catalog.by_id.get(definition.segment_id)
    step = next((step for step in contract.route_steps if step.id == definition.segment_id), None)
    if definition.game_id != contract.game or segment is None or segment.status != "solved":
        raise ShowError("Show game, goal membership, or accepted segment status is invalid")
    if step is None or step.execution_mode != "normal_gameplay":
        raise ShowError("Show requires normal-gameplay goal membership")
    if definition.tell_segment_id not in load_tell_knowledge():
        raise ShowError("Show definition has no validated Tell relationship")
    event_ids = [definition.starting_state_event, *(cue.trigger_event for cue in definition.cues), definition.success_event, *definition.failure_events, definition.stop_event]
    if any(event_id not in SHOW_EVENT_IDS for event_id in event_ids):
        raise ShowError("Show definition references an unknown event id")
    cue_ids = [cue.cue_id for cue in definition.cues]
    cue_events = [cue.trigger_event for cue in definition.cues]
    if len(set(cue_ids)) != len(cue_ids) or len(set(cue_events)) != len(cue_events):
        raise ShowError("Show cue ids and trigger events must be unique")
    if cue_events[0] != definition.starting_state_event or cue_events[-1] != definition.success_event:
        raise ShowError("Show cues must begin at the start event and end at exact terminal success")
    for cue in definition.cues:
        if not cue.instruction or not cue.expected_visual_cue or not cue.provenance:
            raise ShowError("every Show cue requires instruction, visual cue, and typed provenance")
        for reference in cue.provenance:
            reference.validate()


def show_capability(request: ShowRequest | None, *, definition_path: Path = SHOW_DEFINITIONS_PATH) -> ShowCapability:
    if request is None:
        return ShowCapability(False, "Show needs a fresh adapter observation and configured game file.")
    try:
        request.validate()
        definition = load_show_definition(definition_path)
        if (request.game_id, request.goal_id, request.segment_id) != (
            definition.game_id, definition.goal_id, definition.segment_id
        ):
            raise ShowError("validated Show knowledge is unavailable for this game, goal, and segment")
    except (OSError, KeyError, ShowError, ValueError) as exc:
        return ShowCapability(False, str(exc))
    return ShowCapability(True, "A separate review-only 1-1 demonstration is ready.", definition)


def reconcile_show_cues(
    definition: ShowDefinition,
    events: tuple[LogEvent, ...],
    image_paths: tuple[Path, ...] = (),
) -> CueReconciliation:
    positions: dict[str, tuple[int, LogEvent]] = {}
    for position, event in enumerate(events):
        positions.setdefault(event.event, (position, event))
    reconciled: list[ShowCue] = []
    last_position = -1
    first_problem: str | None = None
    manifest: list[ShowArtifactReference] = []
    for cue in definition.cues:
        match = positions.get(cue.trigger_event)
        if match is None:
            label = "missing terminal success" if cue.trigger_event == definition.success_event else "missing cue event"
            first_problem = first_problem or f"{label}: {cue.trigger_event}"
            reconciled.append(replace(cue, status=ShowCueStatus.MISSED))
            continue
        position, event = match
        if position <= last_position:
            first_problem = first_problem or f"out-of-order cue event: {cue.trigger_event}"
            reconciled.append(replace(cue, status=ShowCueStatus.MISSED, frame=event.frame, event_position=position))
            continue
        last_position = position
        observed = replace(cue, status=ShowCueStatus.OBSERVED, frame=event.frame, event_position=position)
        reconciled.append(observed)
        image = _nearest_image(image_paths, event.frame)
        manifest.append(ShowArtifactReference("cue_evidence", str(image) if image else "", cue.cue_id, event.event, event.frame))
    success = definition.success_event in positions
    if not success:
        first_problem = first_problem or f"missing terminal success: {definition.success_event}"
    return CueReconciliation(first_problem is None and success, tuple(reconciled), first_problem, success, tuple(manifest))


class ShowProcessController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self.stop_requested = threading.Event()
        self.takeover_requested = threading.Event()
        self.input_stopped = threading.Event()

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            if self._process is not None:
                raise ShowError("Show controller already owns a process")
            self._process = process
            if self.stop_requested.is_set():
                self._terminate_locked()

    def request_stop(self, *, takeover: bool = False) -> None:
        if takeover:
            self.takeover_requested.set()
        self.stop_requested.set()
        with self._lock:
            self._terminate_locked()

    def mark_natural_stop(self) -> None:
        self.input_stopped.set()

    def _terminate_locked(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            self.input_stopped.set()
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        finally:
            self.input_stopped.set()


Runner = Callable[[ShowRequest, ShowDefinition, Path, ShowProcessController, Callable[[str], None]], ShowOutcome]


def run_show_demonstration(
    request: ShowRequest,
    definition: ShowDefinition,
    artifacts_dir: Path,
    controller: ShowProcessController,
    progress: Callable[[str], None] = lambda _message: None,
    *,
    frame_sleep_seconds: float = 0.0035,
    timeout_seconds: int = 180,
) -> ShowOutcome:
    request.validate()
    validate_show_definition(definition)
    if frame_sleep_seconds <= 0:
        raise ShowError("Show frame delay must be positive")
    artifacts_dir.mkdir(parents=True, exist_ok=False)
    log_path = artifacts_dir / "fceux_1_1.log"
    image_dir = artifacts_dir / "images"
    image_dir.mkdir()
    stdout_path, stderr_path = artifacts_dir / "fceux_stdout.log", artifacts_dir / "fceux_stderr.log"
    invocation = {
        "adapter_id": request.adapter_id, "game_id": request.game_id, "goal_id": request.goal_id,
        "segment_id": request.segment_id, "fresh_process": True, "attempts": 1, "savestate": False,
        "selected_segment_only": True, "capture_images": True, "capture_ticks": True,
        "frame_sleep_seconds": frame_sleep_seconds, "review_only": True, "promotable": False,
        "counts_toward_reliability": False, "player_completion": False,
    }
    _write_json(artifacts_dir / "invocation.json", invocation)
    env = {key: value for key, value in os.environ.items() if not key.startswith("SMB3_")}
    env.update({
        "SMB3_AGENT_LOG": str(log_path.resolve()), "SMB3_AGENT_ATTEMPTS": "1",
        "SMB3_AGENT_FRAME_SLEEP_SECONDS": str(frame_sleep_seconds), "SMB3_CAPTURE_TICKS": "1",
        "SMB3_AGENT_IMAGE_DIR": str(image_dir.resolve()), "SMB3_POST_1_1_PROBE": "",
    })
    command = ["fceux", "--no-config", "1", "--sound", "0", "--loadlua", str(SHOW_SCRIPT_PATH.resolve()), str(request.game_path.resolve())]
    execution: dict[str, Any] = {"command": command[:-1] + ["<configured-game-file>"], "started_at": _now(), "returncode": None, "timed_out": False, "input_stopped": False}
    progress("Starting a separate visible 1-1 demonstration process.")
    with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
        process = subprocess.Popen(command, env=env, stdout=stdout_file, stderr=stderr_file, start_new_session=True)
        controller.attach(process)
        deadline = time.monotonic() + timeout_seconds
        announced: set[str] = set()
        while process.poll() is None and time.monotonic() < deadline:
            if log_path.is_file():
                observed_ids = {event.event for event in parse_log_events(log_path)}
                for cue in definition.cues:
                    if cue.trigger_event in observed_ids and cue.cue_id not in announced:
                        announced.add(cue.cue_id)
                        progress(f"cue:{cue.cue_id}:{cue.instruction}")
            if controller.stop_requested.wait(0.05):
                controller.request_stop(takeover=controller.takeover_requested.is_set())
                break
        if process.poll() is None:
            execution["timed_out"] = True
            controller.request_stop()
        execution["returncode"] = process.wait(timeout=5)
    controller.mark_natural_stop()
    execution.update({"finished_at": _now(), "input_stopped": controller.input_stopped.is_set(), "takeover_requested": controller.takeover_requested.is_set(), "stop_requested": controller.stop_requested.is_set()})
    _write_json(artifacts_dir / "fceux_execution.json", execution)
    events = parse_log_events(log_path) if log_path.is_file() else ()
    snapshots = build_state_trace(events, segment=request.segment_id, sample_frames=60)
    write_state_trace(artifacts_dir / "state_tick_trace.jsonl", snapshots)
    converted: list[Path] = []
    try:
        converted = convert_gd_directory(image_dir, artifacts_dir / "review" / "png")
        if converted:
            write_contact_sheet(converted, artifacts_dir / "review" / "contact_sheet.png", columns=4)
    except Exception:
        (artifacts_dir / "review").mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "review" / "conversion_error.txt").write_text(traceback.format_exc())
    reconciliation = reconcile_show_cues(definition, events, tuple(converted))
    _write_json(artifacts_dir / "cue_reconciliation.json", {"passed": reconciliation.passed, "first_problem": reconciliation.first_problem, "success_event_observed": reconciliation.success_event_observed, "cues": [asdict(cue) for cue in reconciliation.cues]})
    _write_json(artifacts_dir / "replay_manifest.json", {"ordered_cues": [asdict(item) for item in reconciliation.manifest]})
    cancelled = controller.stop_requested.is_set()
    passed = reconciliation.passed and execution["returncode"] == 0 and not cancelled and bool(converted)
    explanation = (
        "The separate demonstration produced the game-owned 1-1 course-clear event. Your game was not advanced."
        if passed else "The separate demonstration stopped without a completion claim. Your game was not advanced."
    )
    artifacts = tuple(reconciliation.manifest) + tuple(
        ShowArtifactReference(role, str(path))
        for role, path in (
            ("invocation", artifacts_dir / "invocation.json"), ("execution", artifacts_dir / "fceux_execution.json"),
            ("structured_game_log", log_path), ("state_trace", artifacts_dir / "state_tick_trace.jsonl"),
            ("cue_reconciliation", artifacts_dir / "cue_reconciliation.json"), ("replay_manifest", artifacts_dir / "replay_manifest.json"),
            ("contact_sheet", artifacts_dir / "review" / "contact_sheet.png"),
        ) if path.is_file()
    )
    outcome = ShowOutcome(passed, input_stopped=controller.input_stopped.is_set(), process_relinquished=process.poll() is not None, cue_reconciled=reconciliation.passed, explanation=explanation, artifacts=artifacts)
    outcome.validate()
    failure_classification = (
        None if passed else "timeout" if execution["timed_out"] else "cancelled" if cancelled
        else "cue-reconciliation" if not reconciliation.passed else "artifact-integrity" if not converted
        else "process-exit"
    )
    _write_json(
        artifacts_dir / "show_report.json",
        {
            **asdict(outcome),
            "failure_classification": failure_classification,
            "first_unmet_requirement": reconciliation.first_problem,
            "displayed_cues": [
                {
                    "cue_id": cue.cue_id,
                    "instruction": cue.instruction,
                    "expected_visual_cue": cue.expected_visual_cue,
                    "trigger_event": cue.trigger_event,
                }
                for cue in definition.cues
            ],
            "displayed_card_agrees_with_reconciliation": reconciliation.passed,
        },
    )
    if cancelled:
        _write_json(artifacts_dir / "cancellation.json", {"takeover": controller.takeover_requested.is_set(), "input_stopped": controller.input_stopped.is_set(), "last_event": events[-1].event if events else None})
    return outcome


class ShowSessionManager:
    def __init__(self, *, runner: Runner = run_show_demonstration, artifacts_root: Path = SHOW_ARTIFACTS_ROOT) -> None:
        self._runner, self._artifacts_root = runner, artifacts_root
        self._lock = threading.Lock()
        self._session: ShowSession | None = None
        self._controller: ShowProcessController | None = None
        self._thread: threading.Thread | None = None

    def snapshot(self) -> ShowSession | None:
        with self._lock:
            return self._session

    def start(self, request: ShowRequest, definition: ShowDefinition | None = None) -> ShowSession:
        request.validate()
        selected = definition or load_show_definition()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ShowError("Another Show session is already active")
            session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            artifacts_dir = self._artifacts_root / session_id
            self._controller = ShowProcessController()
            self._session = ShowSession(session_id, request, selected, cues=selected.cues, artifacts_dir=artifacts_dir).transition(ShowLifecycle.STARTING, activity="Show start accepted; preparing the owned process.")
            self._thread = threading.Thread(target=self._run, name=f"show-{session_id}", daemon=True)
            self._thread.start()
            return self._session

    def stop(self, *, takeover: bool = False) -> ShowSession:
        with self._lock:
            if self._session is None or self._controller is None or self._session.lifecycle not in {ShowLifecycle.STARTING, ShowLifecycle.ACTIVE}:
                raise ShowError("No active Show session can be stopped")
            self._session = self._session.transition(ShowLifecycle.STOP_REQUESTED, activity="Take Control requested." if takeover else "Stop demonstration requested.")
            controller = self._controller
        controller.request_stop(takeover=takeover)
        return self.snapshot()  # type: ignore[return-value]

    def shutdown(self) -> None:
        with self._lock:
            controller, thread = self._controller, self._thread
        if controller is not None and thread is not None and thread.is_alive():
            controller.request_stop()
            thread.join(timeout=10)

    def _progress(self, message: str) -> None:
        with self._lock:
            if self._session is not None:
                target = ShowLifecycle.ACTIVE if self._session.lifecycle is ShowLifecycle.STARTING else self._session.lifecycle
                cue_id = None
                display = message
                if message.startswith("cue:"):
                    _, cue_id, display = message.split(":", 2)
                cues = self._session.cues
                if cue_id is not None:
                    cues = tuple(
                        replace(cue, status=ShowCueStatus.ACTIVE if cue.cue_id == cue_id else ShowCueStatus.OBSERVED if cue.status is ShowCueStatus.ACTIVE else cue.status)
                        for cue in cues
                    )
                if target is not self._session.lifecycle:
                    self._session = self._session.transition(
                        target,
                        activity=display,
                        cues=cues,
                        current_cue_id=cue_id or self._session.current_cue_id,
                    )
                else:
                    self._session = replace(
                        self._session,
                        activity=self._session.activity + (display,),
                        cues=cues,
                        current_cue_id=cue_id or self._session.current_cue_id,
                    )

    def _run(self) -> None:
        with self._lock:
            session, controller = self._session, self._controller
        assert session is not None and controller is not None and session.artifacts_dir is not None
        try:
            outcome = self._runner(session.request, session.definition, session.artifacts_dir, controller, self._progress)
            with self._lock:
                assert self._session is not None
                current = self._session
                if current.lifecycle is ShowLifecycle.STOP_REQUESTED:
                    current = current.transition(ShowLifecycle.INPUT_STOPPED, activity="Automation input stopped.")
                    terminal = ShowLifecycle.TAKEN_OVER if controller.takeover_requested.is_set() else ShowLifecycle.CANCELLED
                    self._session = current.transition(terminal, activity="Control returned outside the demonstration.", outcome=outcome, control_returned=True)
                else:
                    current = current.transition(ShowLifecycle.INPUT_STOPPED, activity="Automation input stopped.")
                    terminal = ShowLifecycle.DEMONSTRATED if outcome.demonstration_game_owned_success else ShowLifecycle.FAILED
                    self._session = current.transition(terminal, activity=outcome.explanation, outcome=outcome, control_returned=True)
        except Exception as exc:
            if session.artifacts_dir:
                session.artifacts_dir.mkdir(parents=True, exist_ok=True)
                (session.artifacts_dir / "failure_traceback.txt").write_text(traceback.format_exc())
                _write_json(session.artifacts_dir / "show_report.json", {"review_only": True, "promotable": False, "counts_toward_reliability": False, "player_completion": False, "authoritative_acceptance": False, "demonstration_game_owned_success": False, "failure_classification": "unexpected-exception", "error": f"{type(exc).__name__}: {exc}"})
            with self._lock:
                if self._session is not None:
                    current = self._session
                    if current.lifecycle in {ShowLifecycle.STARTING, ShowLifecycle.ACTIVE, ShowLifecycle.STOP_REQUESTED}:
                        if controller.input_stopped.is_set() and current.lifecycle in {ShowLifecycle.ACTIVE, ShowLifecycle.STOP_REQUESTED}:
                            current = current.transition(ShowLifecycle.INPUT_STOPPED, activity="Automation input stopped after failure.")
                        self._session = current.transition(ShowLifecycle.FAILED, activity="Show failed closed.", error=f"{type(exc).__name__}: {exc}", control_returned=controller.input_stopped.is_set())


def _nearest_image(paths: tuple[Path, ...], frame: int | None) -> Path | None:
    if not paths or frame is None:
        return paths[0] if paths else None
    def image_frame(path: Path) -> int:
        prefix = path.stem.split("_", 1)[0]
        return int(prefix) if prefix.isdigit() else 0
    return min(paths, key=lambda path: abs(image_frame(path) - frame))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
