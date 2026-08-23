from __future__ import annotations

import json
import hashlib
import os
import secrets
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from smb3_agent.companion_session import Freshness, Observation, ObservationSource
from smb3_agent.fceux_images import convert_gd_directory, write_contact_sheet
from smb3_agent.learning import (
    AttemptContract,
    LocalLearningStore,
    ProgressAnchor,
    process_attempt,
)
from smb3_agent.run_library import (
    CompletionClassification,
    LocalRunLibrary,
    RunRecord,
    SolutionClassification,
)
from smb3_agent.takeover import (
    ControlOwner,
    ExecutableSolution,
    TakeoverAuthorization,
    TakeoverController,
    TakeoverError,
    TakeoverTerminal,
    state_fingerprint,
)
from smb3_agent.tell import ObservedFact


LIVE_OBSERVER_SCRIPT = Path("scripts/fceux_live_observer.lua")
LIVE_TAKEOVER_SCRIPT = Path("scripts/fceux_live_takeover.lua")
AGENT_SCRIPT = Path("scripts/fceux_1_1_agent.lua")
LIVE_ARTIFACTS_ROOT = Path("artifacts/live-observation")
BUTTONS = ("A", "B", "up", "down", "left", "right", "start", "select")
ITEM_CODES = {
    "super_mushroom_available": 1,
    "super_leaf_available": 3,
    "p_wing_available": 8,
}


class LiveObservationError(ValueError):
    pass


class ConnectionState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STALE = "stale"
    DISCONNECTED = "disconnected"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    TERMINAL = "terminal"


class EventKind(str, Enum):
    PROGRESS = "progress"
    TRANSITION = "transition"
    DEATH = "death"
    RECOVERY = "recovery"
    RESOURCE = "resource"
    COURSE_CLEAR = "course_clear"


@dataclass(frozen=True)
class EvidenceSource:
    source: str
    observed_at: datetime
    sequence: int
    frame: int
    confidence: float

    def validate(self) -> None:
        if not self.source:
            raise LiveObservationError("observation source is required")
        if self.sequence < 0 or self.frame < 0:
            raise LiveObservationError("observation sequence and frame must be non-negative")
        if not 0 <= self.confidence <= 1:
            raise LiveObservationError("observation confidence must be between 0 and 1")


@dataclass(frozen=True)
class LiveFact:
    fact_id: str
    value: str
    provenance: EvidenceSource


@dataclass(frozen=True)
class ControllerInput:
    actor: str
    buttons: tuple[str, ...]
    provenance: EvidenceSource

    def validate(self) -> None:
        self.provenance.validate()
        if self.actor not in {"player", "agent"}:
            raise LiveObservationError("input actor must be player or agent")
        if len(set(self.buttons)) != len(self.buttons) or any(
            button not in BUTTONS for button in self.buttons
        ):
            raise LiveObservationError("input contains duplicate or unsupported buttons")


@dataclass(frozen=True)
class LiveEvent:
    kind: EventKind
    detail: str
    provenance: EvidenceSource


@dataclass(frozen=True)
class LiveSample:
    session_id: str
    observer_token: str
    sequence: int
    frame: int
    observed_at: datetime
    world: int
    object_set: int
    map_page: int
    map_cursor_x: int
    map_cursor_y: int
    x: int
    y: int
    form: int
    lives: int
    player_is_dying: int
    return_map: int
    items: tuple[int, ...]
    buttons: tuple[str, ...]
    actor: str = "player"
    source: str = "fceux-memory-and-joypad-read"
    confidence: float = 1.0
    control_epoch: int = 0
    takeover_detail: str | None = None

    def provenance(self) -> EvidenceSource:
        return EvidenceSource(
            self.source, self.observed_at, self.sequence, self.frame, self.confidence
        )

    def validate(self) -> None:
        if not self.session_id or not self.observer_token:
            raise LiveObservationError("session and observer identity are required")
        ControllerInput(self.actor, self.buttons, self.provenance()).validate()
        if len(self.items) != 10:
            raise LiveObservationError("Mario resource samples require ten inventory slots")
        if self.player_is_dying not in {0, 1}:
            raise LiveObservationError("player death state must be zero or one")


@dataclass(frozen=True)
class LiveObservationSnapshot:
    session_id: str | None
    state: ConnectionState
    freshness: Freshness
    reason: str
    observed_at: datetime | None = None
    age_seconds: float | None = None
    checkpoint_id: str | None = None
    checkpoint: str | None = None
    mode: str = "unknown"
    progress: str = "Unknown"
    deaths: int = 0
    recoveries: int = 0
    facts: tuple[LiveFact, ...] = ()
    recent_inputs: tuple[ControllerInput, ...] = ()
    events: tuple[LiveEvent, ...] = ()
    agent_input_count: int = 0
    artifact_dir: Path | None = None
    confidence: float | None = None
    samples: tuple[LiveSample, ...] = ()
    player_input_count: int = 0
    takeover_capable: bool = False
    control_owner: str = "player"
    control_state: str = "player_control"
    control_epoch: int = 0
    takeover_terminal_reason: str | None = None
    input_neutralized: bool = True
    observation_resumed: bool = True
    handback_latency_ms: float | None = None
    process_alive: bool | None = None
    emulator_pid: int | None = None

    @property
    def observation_active(self) -> bool:
        return self.session_id is not None and self.state in {
            ConnectionState.CONNECTING,
            ConnectionState.CONNECTED,
            ConnectionState.STALE,
            ConnectionState.UNSUPPORTED,
            ConnectionState.UNKNOWN,
        }

    @property
    def tell_ready(self) -> bool:
        return (
            self.state is ConnectionState.CONNECTED
            and self.freshness is Freshness.FRESH
            and self.checkpoint_id is not None
            and self.confidence is not None
        )

    @property
    def tell_unavailable_reason(self) -> str:
        if self.tell_ready:
            return "Live Tell is ready from this fresh supported checkpoint."
        if self.state is not ConnectionState.CONNECTED or self.freshness is not Freshness.FRESH:
            return self.reason
        if self.checkpoint_id is None:
            return (
                "Live Tell needs a supported checkpoint; the current observed state is "
                f"{self.checkpoint or 'unknown'}."
            )
        if self.confidence is None:
            return "Live Tell needs a confidence-bearing observation."
        return "Live Tell is unavailable because the observed evidence is incomplete."

    def observation(self) -> Observation:
        return Observation(
            checkpoint=self.checkpoint,
            checkpoint_id=self.checkpoint_id,
            observed_at=self.observed_at,
            freshness=self.freshness,
            confidence=self.confidence,
            evidence_references=(
                f"live-observation:{self.artifact_dir / 'observations.jsonl'}",
            )
            if self.artifact_dir and self.observed_at
            else (),
            source=ObservationSource.ADAPTER if self.observed_at else None,
            game_id="smb3" if self.observed_at else None,
        )

    def tell_facts(self) -> tuple[ObservedFact, ...]:
        if not self.tell_ready:
            return ()
        selected = {
            fact.fact_id: fact.value
            for fact in self.facts
            if fact.fact_id
            in {
                "warp_whistle_count",
                "p_wing_available",
                "super_leaf_available",
                "super_mushroom_available",
            }
        }
        return (
            ObservedFact("checkpoint_confirmed", "true", ObservationSource.ADAPTER),
            *(
                ObservedFact(fact_id, value, ObservationSource.ADAPTER)
                for fact_id, value in sorted(selected.items())
            ),
        )


@dataclass
class LiveSessionAccumulator:
    session_id: str
    observer_token: str
    artifact_dir: Path
    stale_after_seconds: float = 2.0
    disconnect_after_seconds: float = 8.0
    samples: list[LiveSample] = field(default_factory=list)
    inputs: list[ControllerInput] = field(default_factory=list)
    events: list[LiveEvent] = field(default_factory=list)
    deaths: int = 0
    recoveries: int = 0
    agent_input_count: int = 0
    connection_state: ConnectionState = ConnectionState.CONNECTING
    reason: str = "Waiting for the first emulator observation."
    stopped: bool = False
    takeover_controller: TakeoverController | None = None

    def ingest(self, sample: LiveSample) -> None:
        sample.validate()
        if self.stopped:
            raise LiveObservationError("stopped observation sessions cannot accept samples")
        if sample.session_id != self.session_id or sample.observer_token != self.observer_token:
            self.connection_state = ConnectionState.DISCONNECTED
            self.reason = "Session identity changed unexpectedly; the prior session was closed."
            raise LiveObservationError("unexpected live-session replacement")
        if self.samples and sample.sequence <= self.samples[-1].sequence:
            raise LiveObservationError("observation sequence must increase")
        if self.samples and sample.frame < self.samples[-1].frame:
            raise LiveObservationError("observation frame must not move backward")
        if sample.actor == "agent":
            self.agent_input_count += 1
            if self.takeover_controller is None:
                self.connection_state = ConnectionState.DISCONNECTED
                self.reason = "Agent input appeared in observe-only mode; observation stopped."
                raise LiveObservationError("observe-only mode rejects agent input")
            try:
                self.takeover_controller.record_agent_input(sample.control_epoch, sample.buttons)
            except TakeoverError as exc:
                self.connection_state = ConnectionState.DISCONNECTED
                self.reason = str(exc)
                raise LiveObservationError(str(exc)) from exc
        if self.inputs and self.inputs[-1].provenance.frame == sample.frame:
            if self.inputs[-1].actor != sample.actor:
                raise LiveObservationError("simultaneous player and agent input is ambiguous")
        previous = self.samples[-1] if self.samples else None
        self.samples.append(sample)
        self.inputs.append(ControllerInput(sample.actor, sample.buttons, sample.provenance()))
        self._derive_events(previous, sample)
        self.connection_state = ConnectionState.CONNECTED
        self.reason = (
            "Companion is playing inside the active authorization."
            if sample.actor == "agent"
            else "You are playing. Companion is observing."
        )

    def mark_disconnect(self, reason: str) -> None:
        self.connection_state = ConnectionState.DISCONNECTED
        self.reason = reason

    def mark_unsupported(self, reason: str) -> None:
        self.connection_state = ConnectionState.UNSUPPORTED
        self.reason = reason

    def stop(self) -> None:
        self.stopped = True
        self.connection_state = ConnectionState.STOPPED
        self.reason = "Observation stopped. Your game was left running and unchanged."

    def snapshot(self, *, now: datetime | None = None) -> LiveObservationSnapshot:
        current = now or datetime.now(timezone.utc)
        if not self.samples:
            state = self.connection_state
            return LiveObservationSnapshot(
                self.session_id,
                state,
                Freshness.UNKNOWN,
                self.reason,
                agent_input_count=self.agent_input_count,
                artifact_dir=self.artifact_dir,
                takeover_capable=self.takeover_controller is not None,
                control_owner=(
                    self.takeover_controller.snapshot.owner.value
                    if self.takeover_controller
                    else "player"
                ),
                control_state=(
                    self.takeover_controller.snapshot.state.value
                    if self.takeover_controller
                    else "player_control"
                ),
                control_epoch=(
                    self.takeover_controller.snapshot.control_epoch
                    if self.takeover_controller
                    else 0
                ),
                takeover_terminal_reason=(
                    self.takeover_controller.snapshot.terminal_reason.value
                    if self.takeover_controller
                    and self.takeover_controller.snapshot.terminal_reason
                    else None
                ),
                input_neutralized=(
                    self.takeover_controller.snapshot.neutralized
                    if self.takeover_controller
                    else True
                ),
                observation_resumed=(
                    self.takeover_controller.snapshot.observation_resumed
                    if self.takeover_controller
                    else True
                ),
                handback_latency_ms=(
                    self.takeover_controller.snapshot.handback_latency_ms
                    if self.takeover_controller
                    else None
                ),
                process_alive=(
                    self.takeover_controller.snapshot.process_alive
                    if self.takeover_controller
                    else None
                ),
            )
        latest = self.samples[-1]
        age = max(0.0, (current - latest.observed_at).total_seconds())
        state = self.connection_state
        reason = self.reason
        freshness = Freshness.FRESH
        if state in {
            ConnectionState.DISCONNECTED,
            ConnectionState.UNSUPPORTED,
            ConnectionState.UNKNOWN,
            ConnectionState.STOPPED,
            ConnectionState.TERMINAL,
        }:
            freshness = Freshness.STALE
        elif age >= self.disconnect_after_seconds:
            state = ConnectionState.DISCONNECTED
            freshness = Freshness.STALE
            reason = "The emulator observation disconnected. Tell is unavailable."
        elif age >= self.stale_after_seconds:
            state = ConnectionState.STALE
            freshness = Freshness.STALE
            reason = "The last emulator observation is stale. Tell is unavailable."
        checkpoint_id, checkpoint = _checkpoint(latest)
        if state is ConnectionState.CONNECTED and not 0 <= latest.world <= 7:
            state = ConnectionState.UNKNOWN
            freshness = Freshness.UNKNOWN
            reason = "The observed game state is unknown. Tell is unavailable."
        elif (
            state is ConnectionState.CONNECTED
            and latest.object_set != 0
            and checkpoint_id is None
        ):
            state = ConnectionState.UNSUPPORTED
            freshness = Freshness.UNKNOWN
            reason = "This Mario checkpoint is not yet supported for live Tell."
        mode = "map or transition" if latest.object_set == 0 else "gameplay"
        progress = (
            f"Mario x={latest.x} in the current segment"
            if latest.object_set != 0
            else f"World {latest.world + 1} map page {latest.map_page + 1} at "
            f"({latest.map_cursor_x}, {latest.map_cursor_y})"
        )
        facts = _facts(latest)
        return LiveObservationSnapshot(
            self.session_id,
            state,
            freshness,
            reason,
            latest.observed_at,
            age,
            checkpoint_id,
            checkpoint,
            mode,
            progress,
            self.deaths,
            self.recoveries,
            facts,
            tuple(self.inputs[-12:]),
            tuple(self.events[-20:]),
            self.agent_input_count,
            self.artifact_dir,
            latest.confidence if state is ConnectionState.CONNECTED else None,
            tuple(self.samples),
            len(self.inputs),
            self.takeover_controller is not None,
            self.takeover_controller.snapshot.owner.value
            if self.takeover_controller
            else "player",
            self.takeover_controller.snapshot.state.value
            if self.takeover_controller
            else "player_control",
            self.takeover_controller.snapshot.control_epoch
            if self.takeover_controller
            else 0,
            self.takeover_controller.snapshot.terminal_reason.value
            if self.takeover_controller and self.takeover_controller.snapshot.terminal_reason
            else None,
            self.takeover_controller.snapshot.neutralized
            if self.takeover_controller
            else True,
            self.takeover_controller.snapshot.observation_resumed
            if self.takeover_controller
            else True,
            self.takeover_controller.snapshot.handback_latency_ms
            if self.takeover_controller
            else None,
            self.takeover_controller.snapshot.process_alive
            if self.takeover_controller
            else None,
        )

    def _derive_events(self, previous: LiveSample | None, sample: LiveSample) -> None:
        source = sample.provenance()
        if previous is None:
            self.events.append(LiveEvent(EventKind.TRANSITION, "Observation connected", source))
            return
        if (
            previous.lives != 255
            and sample.lives != 255
            and sample.lives < previous.lives
        ) or (
            sample.player_is_dying == 1 and previous.player_is_dying == 0
        ):
            self.deaths += 1
            self.events.append(LiveEvent(EventKind.DEATH, "Mario death observed", source))
        if previous.player_is_dying == 1 and sample.player_is_dying == 0:
            self.recoveries += 1
            self.events.append(LiveEvent(EventKind.RECOVERY, "Mario re-entry observed", source))
        if (sample.world, sample.object_set, sample.map_page) != (
            previous.world,
            previous.object_set,
            previous.map_page,
        ):
            detail = f"State changed to world={sample.world} object_set={sample.object_set}"
            kind = (
                EventKind.COURSE_CLEAR
                if previous.object_set != 0
                and sample.object_set == 0
                and (previous.return_map == 1 or sample.return_map == 1)
                else EventKind.TRANSITION
            )
            self.events.append(LiveEvent(kind, detail, source))
        if sample.x > previous.x and sample.object_set != 0:
            self.events.append(LiveEvent(EventKind.PROGRESS, f"Mario advanced to x={sample.x}", source))
        if sample.items != previous.items or sample.form != previous.form:
            self.events.append(LiveEvent(EventKind.RESOURCE, "Inventory or power-up changed", source))


def parse_observer_line(line: str, *, observed_at: datetime | None = None) -> LiveSample:
    fields: dict[str, str] = {}
    for token in line.strip().split():
        key, separator, value = token.partition("=")
        if not key or separator != "=" or key in fields:
            raise LiveObservationError("malformed or duplicate observer field")
        fields[key] = value
    required = {
        "schema",
        "session",
        "token",
        "seq",
        "frame",
        "actor",
        "buttons",
        "world",
        "object_set",
        "map_page",
        "map_cursor_x",
        "map_cursor_y",
        "x",
        "y",
        "form",
        "lives",
        "dying",
        "return_map",
        *(f"item_{index}" for index in range(10)),
    }
    missing = required.difference(fields)
    if missing or fields.get("schema") != "game-companion-live-v1":
        raise LiveObservationError(
            "observer sample is incomplete or unsupported"
            + (f": {', '.join(sorted(missing))}" if missing else "")
        )
    try:
        buttons = tuple(button for button in fields["buttons"].split(",") if button)
        sample = LiveSample(
            fields["session"],
            fields["token"],
            int(fields["seq"]),
            int(fields["frame"]),
            observed_at or datetime.now(timezone.utc),
            int(fields["world"]),
            int(fields["object_set"]),
            int(fields["map_page"]),
            int(fields["map_cursor_x"]),
            int(fields["map_cursor_y"]),
            int(fields["x"]),
            int(fields["y"]),
            int(fields["form"]),
            int(fields["lives"]),
            int(fields["dying"]),
            int(fields["return_map"]),
            tuple(int(fields[f"item_{index}"]) for index in range(10)),
            buttons,
            fields["actor"],
            control_epoch=int(fields.get("control_epoch", "0")),
            takeover_detail=fields.get("takeover_detail"),
        )
    except ValueError as exc:
        raise LiveObservationError("observer numeric field is invalid") from exc
    sample.validate()
    return sample


def _checkpoint(sample: LiveSample) -> tuple[str | None, str | None]:
    if (
        sample.frame <= 60
        and sample.world == 0
        and sample.object_set == 0
        and not sample.buttons
    ):
        return "fresh_power_on", "Fresh power-on"
    if sample.world == 0 and sample.object_set == 1:
        return "world_1_1_clear", "World 1-1"
    if sample.world == 0 and sample.object_set == 0:
        return None, "World 1 map"
    if 0 <= sample.world <= 7:
        return None, f"World {sample.world + 1} unsupported checkpoint"
    return None, "Unknown or unsupported game state"


def _facts(sample: LiveSample) -> tuple[LiveFact, ...]:
    source = sample.provenance()
    values = {
        "world_number": str(sample.world + 1),
        "map_page": str(sample.map_page + 1),
        "lives": str(sample.lives),
        "power_up_form": str(sample.form),
        "warp_whistle_count": str(sample.items.count(12)),
        **{
            fact_id: str(code in sample.items).lower()
            for fact_id, code in ITEM_CODES.items()
        },
    }
    return tuple(LiveFact(key, value, source) for key, value in values.items())


def observed_level_id(samples: tuple[LiveSample, ...] | list[LiveSample]) -> str | None:
    """Resolve the latest observed gameplay segment from adapter-owned state."""
    gameplay_index = next(
        (index for index in range(len(samples) - 1, -1, -1) if samples[index].object_set != 0),
        None,
    )
    if gameplay_index is None:
        return None
    gameplay = samples[gameplay_index]
    start_index = gameplay_index
    while (
        start_index > 0
        and samples[start_index - 1].world == gameplay.world
        and samples[start_index - 1].object_set == gameplay.object_set
    ):
        start_index -= 1
    entry_map = (
        samples[start_index - 1]
        if start_index > 0 and samples[start_index - 1].object_set == 0
        else None
    )
    return _level_identity(gameplay, entry_map)


def _level_identity(gameplay: LiveSample, entry_map: LiveSample | None) -> str:
    if gameplay.world == 0 and gameplay.object_set == 1 and entry_map is None:
        return "world_1_1"
    if entry_map is not None:
        return (
            f"world_{gameplay.world + 1}_page_{entry_map.map_page + 1}_"
            f"node_{entry_map.map_cursor_x}_{entry_map.map_cursor_y}_"
            f"object_{gameplay.object_set}"
        )
    return f"world_{gameplay.world + 1}_object_{gameplay.object_set}_unresolved_entry"


class LiveObservationManager:
    def __init__(
        self,
        *,
        artifacts_root: Path = LIVE_ARTIFACTS_ROOT,
        launcher: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        run_library: LocalRunLibrary | None = None,
        learning_store: LocalLearningStore | None = None,
    ) -> None:
        self._artifacts_root = artifacts_root
        self._launcher = launcher
        self._run_library = run_library or LocalRunLibrary()
        self._learning_store = learning_store or LocalLearningStore()
        self._lock = threading.Lock()
        self._accumulator: LiveSessionAccumulator | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._detach_path: Path | None = None
        self._takeover_controller: TakeoverController | None = None
        self._game_file_sha256: str | None = None
        self._allow_takeover = False

    def start(
        self, game_path: Path, *, allow_takeover: bool = False
    ) -> LiveObservationSnapshot:
        if not game_path.is_file():
            raise FileNotFoundError(f"Local game file not found: {game_path}")
        observer_script = LIVE_TAKEOVER_SCRIPT if allow_takeover else LIVE_OBSERVER_SCRIPT
        if not observer_script.is_file():
            raise LiveObservationError("Mario live-observer script is missing")
        if allow_takeover and not AGENT_SCRIPT.is_file():
            raise LiveObservationError("Mario accepted solution script is missing")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                assert self._accumulator is not None
                return self._accumulator.snapshot()
            session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            token = secrets.token_hex(16)
            artifact_dir = self._artifacts_root / session_id
            artifact_dir.mkdir(parents=True, exist_ok=False)
            log_path = artifact_dir / "observer.log"
            detach_path = artifact_dir / "detach.request"
            control_path = artifact_dir / "control.request"
            reclaim_path = artifact_dir / "reclaim.request"
            image_dir = artifact_dir / "state-samples"
            image_dir.mkdir()
            takeover_controller = (
                TakeoverController(artifact_dir, control_path, reclaim_path)
                if allow_takeover
                else None
            )
            accumulator = LiveSessionAccumulator(
                session_id,
                token,
                artifact_dir,
                takeover_controller=takeover_controller,
            )
            self._accumulator = accumulator
            self._detach_path = detach_path
            self._takeover_controller = takeover_controller
            self._allow_takeover = allow_takeover
            self._game_file_sha256 = hashlib.sha256(game_path.read_bytes()).hexdigest()
            self._write_manifest(game_path, allow_takeover=allow_takeover)
            env = {key: value for key, value in os.environ.items() if not key.startswith("SMB3_LIVE_")}
            env.update(
                {
                    "SMB3_LIVE_SESSION_ID": session_id,
                    "SMB3_LIVE_OBSERVER_TOKEN": token,
                    "SMB3_LIVE_OBSERVER_LOG": str(log_path.resolve()),
                    "SMB3_LIVE_DETACH_PATH": str(detach_path.resolve()),
                    "SMB3_LIVE_IMAGE_DIR": str(image_dir.resolve()),
                    "SMB3_TAKEOVER_CONTROL_PATH": str(control_path.resolve()),
                    "SMB3_TAKEOVER_RECLAIM_PATH": str(reclaim_path.resolve()),
                    "SMB3_TAKEOVER_AGENT_SCRIPT": str(AGENT_SCRIPT.resolve()),
                    "SMB3_AGENT_LOG": str((artifact_dir / "agent_solution.log").resolve()),
                    "SMB3_AGENT_IMAGE_DIR": str(image_dir.resolve()),
                    "SMB3_AGENT_ATTEMPTS": "1",
                    "SMB3_POST_1_1_PROBE": "run_1_castle_after_1_6",
                    "SMB3_WORLD_8_EXTENSION_MODE": "world_8_finish_game",
                }
            )
            stdout = (artifact_dir / "fceux_stdout.log").open("wb")
            stderr = (artifact_dir / "fceux_stderr.log").open("wb")
            command = [
                "fceux",
                "--loadlua",
                str(observer_script.resolve()),
                str(game_path.resolve()),
            ]
            try:
                process = self._launcher(
                    command,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=True,
                )
            except OSError as exc:
                stdout.close()
                stderr.close()
                accumulator.mark_disconnect(f"FCEUX could not start: {exc}")
                self._finalize("launch_failed")
                raise LiveObservationError(f"FCEUX could not start: {exc}") from exc
            self._process = process
            self._write_json(
                "connection.json",
                {
                    "session_id": session_id,
                    "observer_token": token,
                    "process_id": process.pid,
                    "adapter_id": "smb3",
                    "game_id": "smb3",
                    "continuity_rule": "same process id, observer token, increasing sequence, and non-decreasing frame",
                    "takeover_capable": allow_takeover,
                    "command": ["fceux", "--loadlua", str(observer_script), "<configured-game-file>"],
                },
            )
            self._thread = threading.Thread(
                target=self._follow,
                args=(log_path, process, stdout, stderr),
                name=f"live-observe-{session_id}",
                daemon=True,
            )
            self._thread.start()
            return accumulator.snapshot()

    @property
    def takeover_capable(self) -> bool:
        return self._allow_takeover and self._takeover_controller is not None

    def takeover_snapshot(self) -> Any:
        return self._takeover_controller.snapshot if self._takeover_controller else None

    def authorize_takeover(
        self,
        solution: ExecutableSolution,
        *,
        profile_id: str,
        profile_version: int,
        scope: str,
        stop_condition: str,
        timeout_seconds: int,
        protected_resources: tuple[str, ...] = (),
        protected_decisions: tuple[str, ...] = (),
    ) -> TakeoverAuthorization:
        with self._lock:
            if not self.takeover_capable or self._accumulator is None or self._process is None:
                raise LiveObservationError("This session was not launched with takeover capability")
            snapshot = self._accumulator.snapshot()
            if snapshot.freshness is not Freshness.FRESH or not self._accumulator.samples:
                raise LiveObservationError("Takeover requires a fresh current-state observation")
            if self._process.poll() is not None:
                raise LiveObservationError("The observed emulator process is no longer running")
            assert self._takeover_controller is not None
            assert self._game_file_sha256 is not None
            sample = self._accumulator.samples[-1]
            return self._takeover_controller.authorize(
                session_id=self._accumulator.session_id,
                emulator_pid=self._process.pid,
                game_file_sha256=self._game_file_sha256,
                current_fingerprint=state_fingerprint(
                    self._accumulator.session_id, self._process.pid, sample
                ),
                game_id="smb3",
                profile_id=profile_id,
                profile_version=profile_version,
                solution=solution,
                scope=scope,
                stop_condition=stop_condition,
                timeout_seconds=timeout_seconds,
                protected_resources=protected_resources,
                protected_decisions=protected_decisions,
            )

    def transfer_takeover(self, authorization: TakeoverAuthorization) -> None:
        with self._lock:
            if self._takeover_controller is None or self._accumulator is None or self._process is None:
                raise LiveObservationError("No takeover-capable live session is active")
            if not self._accumulator.samples or self._game_file_sha256 is None:
                raise LiveObservationError("Takeover requires a current observed state")
            sample = self._accumulator.samples[-1]
            self._takeover_controller.transfer(
                authorization,
                session_id=self._accumulator.session_id,
                emulator_pid=self._process.pid,
                game_file_sha256=self._game_file_sha256,
                current_fingerprint=state_fingerprint(
                    self._accumulator.session_id, self._process.pid, sample
                ),
            )

    def begin_takeover(
        self,
        solution: ExecutableSolution,
        *,
        profile_id: str,
        profile_version: int,
        scope: str,
        stop_condition: str,
        timeout_seconds: int,
        protected_resources: tuple[str, ...] = (),
        protected_decisions: tuple[str, ...] = (),
    ) -> TakeoverAuthorization:
        """Authorize and transfer against one locked observation sample."""
        with self._lock:
            if not self.takeover_capable or self._accumulator is None or self._process is None:
                raise LiveObservationError("This session was not launched with takeover capability")
            snapshot = self._accumulator.snapshot()
            if snapshot.freshness is not Freshness.FRESH or not self._accumulator.samples:
                raise LiveObservationError("Takeover requires a fresh current-state observation")
            if self._process.poll() is not None or self._game_file_sha256 is None:
                raise LiveObservationError("The observed emulator process is no longer running")
            assert self._takeover_controller is not None
            sample = self._accumulator.samples[-1]
            fingerprint = state_fingerprint(
                self._accumulator.session_id, self._process.pid, sample
            )
            authorization = self._takeover_controller.authorize(
                session_id=self._accumulator.session_id,
                emulator_pid=self._process.pid,
                game_file_sha256=self._game_file_sha256,
                current_fingerprint=fingerprint,
                game_id="smb3",
                profile_id=profile_id,
                profile_version=profile_version,
                solution=solution,
                scope=scope,
                stop_condition=stop_condition,
                timeout_seconds=timeout_seconds,
                protected_resources=protected_resources,
                protected_decisions=protected_decisions,
            )
            self._takeover_controller.transfer(
                authorization,
                session_id=self._accumulator.session_id,
                emulator_pid=self._process.pid,
                game_file_sha256=self._game_file_sha256,
                current_fingerprint=fingerprint,
            )
            return authorization

    def reclaim_takeover(self) -> Any:
        with self._lock:
            if self._takeover_controller is None or self._accumulator is None or self._process is None:
                raise LiveObservationError("No takeover-capable live session is active")
            if self._takeover_controller.snapshot.owner is not ControlOwner.AGENT:
                raise LiveObservationError("Companion does not own the active control epoch")
            fingerprint = (
                state_fingerprint(
                    self._accumulator.session_id,
                    self._process.pid,
                    self._accumulator.samples[-1],
                )
                if self._accumulator.samples
                else "unavailable"
            )
            return self._takeover_controller.reclaim(
                self._takeover_controller.snapshot.control_epoch,
                final_state_fingerprint=fingerprint,
                process_alive=self._process.poll() is None,
            )

    def snapshot(self) -> LiveObservationSnapshot:
        with self._lock:
            if self._accumulator is None:
                return LiveObservationSnapshot(
                    None,
                    ConnectionState.IDLE,
                    Freshness.UNKNOWN,
                    "Start live observation to open a visible player-controlled game.",
                )
            snapshot = self._accumulator.snapshot()
            controller = self._takeover_controller
            process = self._process
            if controller is not None and controller.snapshot.owner is ControlOwner.AGENT:
                authorization = controller.snapshot.authorization
                if process is None or process.poll() is not None:
                    controller.finish(
                        TakeoverTerminal.PROCESS_LOSS,
                        final_state_fingerprint="process_lost",
                        process_alive=False,
                    )
                elif (
                    authorization is not None
                    and datetime.now(timezone.utc)
                    >= datetime.fromisoformat(authorization.expires_at)
                    and controller.snapshot.state.value == "agent_control"
                ):
                    controller.request_terminal(TakeoverTerminal.TIMEOUT)
                elif (
                    snapshot.freshness is not Freshness.FRESH
                    and controller.snapshot.state.value == "agent_control"
                ):
                    controller.request_terminal(TakeoverTerminal.STALE_STATE)
                snapshot = self._accumulator.snapshot()
            return replace(
                snapshot,
                emulator_pid=process.pid if process is not None and process.poll() is None else None,
            )

    def stop(self) -> LiveObservationSnapshot:
        with self._lock:
            accumulator = self._accumulator
            detach_path = self._detach_path
            if accumulator is None:
                raise LiveObservationError("No live observation session is active")
            if accumulator.stopped or accumulator.connection_state in {
                ConnectionState.DISCONNECTED,
                ConnectionState.TERMINAL,
            }:
                return accumulator.snapshot()
            if (
                self._takeover_controller is not None
                and self._takeover_controller.snapshot.owner is ControlOwner.AGENT
            ):
                fingerprint = (
                    state_fingerprint(
                        accumulator.session_id,
                        self._process.pid,
                        accumulator.samples[-1],
                    )
                    if self._process is not None and accumulator.samples
                    else "unavailable"
                )
                self._takeover_controller.finish(
                    TakeoverTerminal.CANCELLED,
                    final_state_fingerprint=fingerprint,
                    process_alive=self._process is not None and self._process.poll() is None,
                )
            if detach_path is not None:
                detach_path.touch(exist_ok=True)
            accumulator.stop()
            self._append_lifecycle("clean_stop_requested", accumulator.reason)
            self._finalize("clean_stop")
            return accumulator.snapshot()

    def shutdown(self) -> None:
        with self._lock:
            if self._accumulator is not None and not self._accumulator.stopped:
                if self._detach_path is not None:
                    self._detach_path.touch(exist_ok=True)
                self._accumulator.stop()
                self._append_lifecycle("server_shutdown_detach", self._accumulator.reason)
                self._finalize("server_shutdown")

    def _follow(
        self,
        log_path: Path,
        process: subprocess.Popen[bytes],
        stdout: Any,
        stderr: Any,
    ) -> None:
        position = 0
        try:
            while process.poll() is None:
                position = self._consume(log_path, position)
                with self._lock:
                    if self._accumulator is None or self._accumulator.stopped:
                        break
                time.sleep(0.05)
            position = self._consume(log_path, position)
            with self._lock:
                if self._accumulator and not self._accumulator.stopped:
                    self._accumulator.mark_disconnect(
                        "The observation-enabled FCEUX process closed. Tell is unavailable."
                    )
                    if (
                        self._takeover_controller is not None
                        and self._takeover_controller.snapshot.owner is ControlOwner.AGENT
                    ):
                        self._takeover_controller.finish(
                            TakeoverTerminal.PROCESS_LOSS,
                            final_state_fingerprint="process_lost",
                            process_alive=False,
                        )
                    self._append_lifecycle("process_disconnected", self._accumulator.reason)
                    self._finalize("process_disconnected")
        finally:
            stdout.close()
            stderr.close()

    def _consume(self, log_path: Path, position: int) -> int:
        if not log_path.is_file():
            return position
        with log_path.open(encoding="utf-8") as handle:
            handle.seek(position)
            lines = handle.readlines()
            next_position = handle.tell()
        for line in lines:
            if not line.endswith("\n"):
                return position
            with self._lock:
                if self._accumulator is None or self._accumulator.stopped:
                    continue
                try:
                    sample = parse_observer_line(line)
                    previous = (
                        self._accumulator.samples[-1]
                        if self._accumulator.samples
                        else None
                    )
                    self._accumulator.ingest(sample)
                    self._append_jsonl("observations.jsonl", _sample_record(sample))
                    self._append_jsonl(
                        "controller_inputs.jsonl", asdict(self._accumulator.inputs[-1])
                    )
                    for event in self._accumulator.events[-4:]:
                        if event.provenance.sequence == sample.sequence:
                            self._append_jsonl("events.jsonl", asdict(event))
                    self._maybe_record_completion(previous, sample)
                    self._handle_takeover_detail(sample)
                except LiveObservationError as exc:
                    self._accumulator.mark_disconnect(str(exc))
                    self._append_lifecycle("sample_rejected", str(exc))
                    self._finalize("sample_rejected")
        return next_position

    def _handle_takeover_detail(self, sample: LiveSample) -> None:
        if (
            self._takeover_controller is None
            or self._accumulator is None
            or self._process is None
            or sample.takeover_detail is None
        ):
            return
        fingerprint = state_fingerprint(
            self._accumulator.session_id, self._process.pid, sample
        )
        if sample.takeover_detail == "reclaimed_neutral" or (
            sample.takeover_detail == "solution_failed_neutral"
            and self._takeover_controller.snapshot.state.value == "neutralizing"
        ):
            self._takeover_controller.confirm_handback(
                final_state_fingerprint=fingerprint,
                process_alive=self._process.poll() is None,
            )
        elif sample.takeover_detail == "solution_returned_neutral":
            self._takeover_controller.finish(
                TakeoverTerminal.SUCCESS,
                final_state_fingerprint=fingerprint,
                process_alive=self._process.poll() is None,
            )
        elif sample.takeover_detail == "solution_failed_neutral":
            self._takeover_controller.finish(
                TakeoverTerminal.FAILURE,
                final_state_fingerprint=fingerprint,
                process_alive=self._process.poll() is None,
            )

    def _maybe_record_completion(
        self, previous: LiveSample | None, sample: LiveSample
    ) -> None:
        if (
            self._accumulator is None
            or previous is None
            or previous.object_set == 0
            or sample.object_set != 0
            or (previous.return_map != 1 and sample.return_map != 1)
        ):
            return
        level_samples: list[LiveSample] = []
        for candidate in reversed(self._accumulator.samples[:-1]):
            if (
                candidate.world != previous.world
                or candidate.object_set != previous.object_set
            ):
                break
            level_samples.append(candidate)
        level_samples.reverse()
        if not level_samples:
            return
        actors = {item.actor for item in level_samples}
        actors.add(sample.actor)
        actor = next(iter(actors)) if len(actors) == 1 else "mixed"
        start = level_samples[0]
        start_index = len(self._accumulator.samples) - 1 - len(level_samples)
        entry_map = (
            self._accumulator.samples[start_index - 1]
            if start_index > 0
            and self._accumulator.samples[start_index - 1].object_set == 0
            else None
        )
        level_id = _level_identity(previous, entry_map)
        profile_id = LocalRunLibrary.normal_clear_profile_id("smb3", level_id)
        evidence_reference = (
            f"{self._accumulator.artifact_dir / 'observations.jsonl'}"
            f"#terminal_sequence={sample.sequence}"
        )
        evidence_key = LocalRunLibrary.evidence_key(evidence_reference, profile_id, 1)
        record = RunRecord(
            run_id=f"run-{evidence_key[:20]}",
            evidence_key=evidence_key,
            game_id="smb3",
            level_id=level_id,
            segment_id=f"{level_id}_clear",
            profile_id=profile_id,
            profile_version=1,
            actor=actor,
            session_actor=actor,
            start_state={
                "boundary": "stable_observed_level_gameplay",
                "world": start.world,
                "object_set": start.object_set,
                "x": start.x,
                "lives": start.lives,
            },
            terminal_state={
                "boundary": "game_owned_clear_return_map",
                "world": sample.world,
                "object_set": sample.object_set,
                "return_map": sample.return_map,
                "clear_signal_return_map": previous.return_map,
                "lives": sample.lives,
            },
            start_frame=start.frame,
            terminal_frame=sample.frame,
            elapsed_compatible_frames=sample.frame - start.frame,
            timing_units="fceux_emulated_frames",
            emulator_assumptions=("same_process", "same_game_file", "fceux_movie_framecount"),
            deaths=sum(
                1
                for left, right in zip(level_samples, level_samples[1:])
                if right.lives < left.lives
                or (left.player_is_dying == 0 and right.player_is_dying == 1)
            ),
            recoveries=sum(
                1
                for left, right in zip(level_samples, level_samples[1:])
                if left.player_is_dying == 1 and right.player_is_dying == 0
            ),
            resources={
                "start_items": start.items,
                "terminal_items": sample.items,
                "start_form": start.form,
                "terminal_form": sample.form,
            },
            required_events=("stable_level_identity", "observed_start_boundary", "game_owned_course_clear", "normal_map_return"),
            optional_events=(),
            input_trace_reference=str(
                self._accumulator.artifact_dir / "controller_inputs.jsonl"
            ),
            observation_evidence_reference=evidence_reference,
            completion=CompletionClassification.COMPLETED,
            comparison_compatible=True,
            compatibility_reason="level, profile, boundaries, timing units, process assumptions, and evidence agree",
            solution_classification=SolutionClassification.CANDIDATE,
            provenance=(
                f"live-session:{self._accumulator.session_id}",
                "fceux-memory-and-joypad-read",
            ),
            created_at=sample.observed_at.isoformat(),
        )
        decision = self._run_library.record(record)
        anchor_samples: dict[str, list[LiveSample]] = {}
        for level_sample in level_samples:
            anchor_samples.setdefault(f"x-{level_sample.x // 32}", []).append(level_sample)
        anchors = tuple(
            ProgressAnchor(
                anchor_id,
                f"{level_id}:x-bucket:{anchor_id.removeprefix('x-')}",
                samples_at_anchor[0].frame - start.frame,
                {
                    "death": any(item.player_is_dying == 1 for item in samples_at_anchor),
                    "failed_recovery": False,
                    "x_min": min(item.x for item in samples_at_anchor),
                    "x_max": max(item.x for item in samples_at_anchor),
                },
                (evidence_reference,),
            )
            for anchor_id, samples_at_anchor in sorted(anchor_samples.items())
        )
        directional_corrections = sum(
            1
            for left, right in zip(level_samples, level_samples[1:])
            if ({"left", "right"}.intersection(left.buttons))
            and ({"left", "right"}.intersection(right.buttons))
            and ({"left", "right"}.intersection(left.buttons)
                != {"left", "right"}.intersection(right.buttons))
        )
        hesitation_intervals = sum(
            1
            for left, right in zip(level_samples, level_samples[1:])
            if left.x == right.x and right.frame - left.frame >= 15
        )
        tactic_tags = tuple(
            tag
            for tag, present in (
                ("deathless_clear", record.deaths == 0),
                ("successful_recovery", record.recoveries > 0),
                ("low_directional_correction", directional_corrections <= 2),
            )
            if present
        )
        learning_session = process_attempt(
            self._learning_store,
            AttemptContract(
                run_id=record.run_id,
                game_id=record.game_id,
                adapter_id="smb3",
                adapter_version="smb3-live-observer/v1",
                level_id=record.level_id,
                segment_id=record.segment_id,
                objective_id=record.profile_id,
                objective_version=record.profile_version,
                actor=record.actor,
                start_boundary=str(record.start_state["boundary"]),
                terminal_boundary=str(record.terminal_state["boundary"]),
                timing_units=record.timing_units,
                start_time=record.start_frame,
                terminal_time=record.terminal_frame,
                complete_timing_interval=True,
                emulator_assumptions=record.emulator_assumptions,
                allowed_techniques=("normal_gameplay",),
                resource_policy=("no_automatic_inventory_use",),
                required_observation_facts=record.required_events,
                observed_facts=record.required_events,
                evidence_integrity=True,
                completion=record.completion.value,
                deaths=record.deaths,
                recoveries=record.recoveries,
                directional_corrections=directional_corrections,
                hesitation_intervals=hesitation_intervals,
                missed_requirements=(),
                lost_resources=tuple(
                    f"inventory_slot_{index}"
                    for index, (before, after) in enumerate(zip(start.items, sample.items))
                    if before and not after
                ),
                anchors=anchors,
                tactic_tags=tactic_tags,
                input_trace_reference=record.input_trace_reference,
                observation_evidence_reference=record.observation_evidence_reference,
                created_at=record.created_at,
            ),
        )
        self._write_json(
            "run_library_decision.json",
            {
                "run_id": decision.run.run_id,
                "created": decision.created,
                "profile_created": decision.profile_created,
                "previous_fastest_observed": decision.previous_fastest_overall,
                "resulting_fastest_observed": decision.resulting_fastest_overall,
                "actor": actor,
                "captured_trace_classification": "candidate_non_executable",
                "learning_session_id": learning_session.session_id,
                "derived_pattern_ids": learning_session.derived_pattern_ids,
                "candidate_ids": learning_session.candidate_ids,
                "automatic_promotion": False,
            },
        )

    def _write_manifest(self, game_path: Path, *, allow_takeover: bool) -> None:
        assert self._accumulator is not None
        self._write_json(
            "session_manifest.json",
            {
                "schema": "game-companion-live-observation/v1",
                "session_id": self._accumulator.session_id,
                "adapter_id": "smb3",
                "game_id": "smb3",
                "connection_mechanism": (
                    "Game Companion launches one visible FCEUX process with opt-in takeover capability; player owns control until a fresh bound authorization transfers it."
                    if allow_takeover
                    else "Game Companion launches one visible FCEUX process with a read-only Lua observer; player controller configuration remains owned by FCEUX."
                ),
                "game_file": game_path.name,
                "game_file_sha256": hashlib.sha256(game_path.read_bytes()).hexdigest(),
                "observe_only": not allow_takeover,
                "observer_source": "FCEUX memory.readbyte and joypad.get",
                "controller_write_path": allow_takeover,
                "savestate": False,
                "reset": False,
                "agent_input_expected": 0 if not allow_takeover else "only inside active authorization",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._append_lifecycle("connecting", "Visible observation-enabled FCEUX launch requested.")

    def _finalize(self, outcome: str) -> None:
        if self._accumulator is None:
            return
        snapshot = self._accumulator.snapshot()
        converted: list[Path] = []
        image_dir = self._accumulator.artifact_dir / "state-samples"
        try:
            converted = convert_gd_directory(
                image_dir,
                self._accumulator.artifact_dir / "state-samples-png",
            )
            if converted:
                write_contact_sheet(
                    converted,
                    self._accumulator.artifact_dir / "state-samples-contact-sheet.png",
                    columns=4,
                )
        except (OSError, ValueError):
            converted = []
        self._write_json(
            "reconciliation.json",
            {
                "outcome": outcome,
                "samples": len(self._accumulator.samples),
                "player_input_records": len(self._accumulator.inputs),
                "agent_input_count": self._accumulator.agent_input_count,
                "agent_input_zero": self._accumulator.agent_input_count == 0,
                "deaths": self._accumulator.deaths,
                "recoveries": self._accumulator.recoveries,
                "events": len(self._accumulator.events),
                "independently_readable_state_samples": [str(path) for path in converted],
                "last_sequence": self._accumulator.samples[-1].sequence
                if self._accumulator.samples
                else None,
                "last_frame": self._accumulator.samples[-1].frame
                if self._accumulator.samples
                else None,
                "final_connection_state": snapshot.state.value,
                "observation_stopped_without_game_process_termination": outcome
                in {"clean_stop", "server_shutdown"},
                "classification": (
                    "takeover-capable mixed-ownership session evidence"
                    if self._allow_takeover
                    else "owner-play observation evidence"
                ),
                "not_route_reliability": True,
                "not_show": True,
                "not_agent_gameplay": not self._allow_takeover,
                "not_takeover": not self._allow_takeover,
                "not_player_completion": not (
                    self._accumulator.artifact_dir / "run_library_decision.json"
                ).is_file(),
                "takeover_capable": self._allow_takeover,
                "control_owner_final": (
                    self._takeover_controller.snapshot.owner.value
                    if self._takeover_controller
                    else "player"
                ),
                "control_epoch_final": (
                    self._takeover_controller.snapshot.control_epoch
                    if self._takeover_controller
                    else 0
                ),
                "input_neutralized": (
                    self._takeover_controller.snapshot.neutralized
                    if self._takeover_controller
                    else True
                ),
            },
        )

    def _append_lifecycle(self, state: str, detail: str) -> None:
        self._append_jsonl(
            "lifecycle.jsonl",
            {
                "state": state,
                "detail": detail,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        assert self._accumulator is not None
        path = self._accumulator.artifact_dir / name
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=_json_default) + "\n")

    def _write_json(self, name: str, payload: dict[str, Any]) -> None:
        assert self._accumulator is not None
        path = self._accumulator.artifact_dir / name
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
            encoding="utf-8",
        )


def _sample_record(sample: LiveSample) -> dict[str, Any]:
    return {
        **asdict(sample),
        "facts": [asdict(fact) for fact in _facts(sample)],
        "mode": "map_or_transition" if sample.object_set == 0 else "gameplay",
        "checkpoint_id": _checkpoint(sample)[0],
        "checkpoint": _checkpoint(sample)[1],
    }


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, Path, Enum)):
        return value.value if isinstance(value, Enum) else str(value)
    raise TypeError(f"unsupported JSON evidence value: {type(value).__name__}")
