from __future__ import annotations

from smb3_agent.glass_ui import GLASS_CSS, STARDEW_GLASS_CSS

import hashlib
import html
import json
import os
import secrets
import stat
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import yaml

from smb3_agent.paths import repository_path


STARDEW_SCHEMA_VERSION = "game-companion-stardew-operator/v1"
ADAPTER_CONTRACT_PATH = repository_path("data/stardew/operator.yaml")
DEFAULT_ARTIFACT_ROOT = Path("artifacts/stardew-operator")


class StardewAdapterError(ValueError):
    """A fail-closed Stardew adapter boundary was not satisfied."""


class InputOwner(str, Enum):
    PLAYER = "player"
    AGENT = "agent"
    AMBIGUOUS = "ambiguous"
    NONE = "none"


class OperatorLifecycle(str, Enum):
    UNCONFIGURED = "unconfigured"
    COPY_READY = "copy_ready"
    PLAYER_OWNED = "player_owned"
    AGENT_AUTHORIZED = "agent_authorized"
    RUNNING = "running"
    RECLAIMING = "reclaiming"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureCode(str, Enum):
    UNKNOWN_STATE = "unknown_state"
    SAVE_MISMATCH = "save_mismatch"
    PRIMARY_SAVE_RISK = "primary_save_risk"
    AMBIGUOUS_OWNERSHIP = "ambiguous_ownership"
    PROTECTED_ACTION_RISK = "protected_action_risk"
    MISSING_EVIDENCE = "missing_evidence"
    PROCESS_LOSS = "process_loss"
    WINDOW_LOSS = "window_loss"
    OCCLUDED_CROPS = "occluded_crops"
    ACCOUNTING_MISMATCH = "accounting_mismatch"
    RESOURCE_UNKNOWN = "resource_unknown"
    INPUT_REJECTED = "input_rejected"


class InputKind(str, Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    CONTROLLER = "controller"


@dataclass(frozen=True)
class SaveIdentity:
    primary_path: str
    primary_real_path: str
    disposable_path: str
    disposable_real_path: str
    source_tree_sha256: str
    disposable_tree_sha256: str
    file_count: int
    byte_count: int
    created_at: str
    nonce: str
    primary_unchanged: bool
    disposable_only: bool

    @property
    def valid(self) -> bool:
        return (
            self.primary_unchanged
            and self.disposable_only
            and bool(self.nonce)
            and bool(self.source_tree_sha256)
            and self.file_count > 0
            and self.byte_count >= 0
            and self.source_tree_sha256 == self.disposable_tree_sha256
            and self.primary_real_path != self.disposable_real_path
        )


@dataclass(frozen=True)
class WindowObservation:
    process_id: int | None
    process_started_at: str | None
    window_id: str | None
    title: str | None
    bounds: tuple[int, int, int, int] | None
    visible: bool
    windowed: bool
    foreground: bool
    occluded: bool = False

    @property
    def trusted(self) -> bool:
        return (
            self.process_id is not None
            and self.process_started_at is not None
            and bool(self.window_id)
            and self.bounds is not None
            and self.visible
            and self.windowed
            and self.foreground
            and not self.occluded
        )


@dataclass(frozen=True)
class CropObservation:
    crop_id: str
    tile_x: int
    tile_y: int
    planted: bool
    watered: bool
    occluded: bool
    confidence: float
    evidence_reference: str

    def validate(self) -> None:
        if not self.crop_id:
            raise StardewAdapterError("crop observations require a stable crop id")
        if not 0 <= self.confidence <= 1:
            raise StardewAdapterError(f"{self.crop_id}: confidence must be between zero and one")
        if not self.evidence_reference:
            raise StardewAdapterError(f"{self.crop_id}: screen evidence is required")
        if self.occluded and self.watered:
            raise StardewAdapterError(f"{self.crop_id}: an occluded crop cannot be called watered")


@dataclass(frozen=True)
class ToolObservation:
    selected_tool: str | None
    watering_can_units: int | None
    watering_can_capacity: int | None
    refill_count: int
    tool_uses: int

    @property
    def exact(self) -> bool:
        return (
            self.selected_tool is not None
            and self.watering_can_units is not None
            and self.watering_can_capacity is not None
            and 0 <= self.watering_can_units <= self.watering_can_capacity
            and self.refill_count >= 0
            and self.tool_uses >= 0
        )


@dataclass(frozen=True)
class PositionObservation:
    location: str | None
    tile_x: int | None
    tile_y: int | None
    at_farmhouse_entrance: bool | None
    confidence: float

    @property
    def exact(self) -> bool:
        return (
            self.location is not None
            and self.tile_x is not None
            and self.tile_y is not None
            and self.at_farmhouse_entrance is not None
            and self.confidence == 1.0
        )


@dataclass(frozen=True)
class ScreenObservation:
    observation_id: str
    observed_at: str
    save_tree_sha256: str
    window: WindowObservation
    crops: tuple[CropObservation, ...]
    energy: int | None
    energy_maximum: int | None
    tool: ToolObservation
    position: PositionObservation
    screenshot_references: tuple[str, ...]
    source: str = "screen"
    scene_complete: bool = False
    unknown_regions: tuple[str, ...] = ()
    session_nonce: str | None = None
    perception_classification: str = "unqualified"

    def validate(self, expected_save_sha256: str) -> None:
        if not self.observation_id or not self.observed_at:
            raise StardewAdapterError(FailureCode.UNKNOWN_STATE.value)
        if self.source != "screen":
            raise StardewAdapterError("Stardew state must come from visible screen observation")
        if self.save_tree_sha256 != expected_save_sha256:
            raise StardewAdapterError(FailureCode.SAVE_MISMATCH.value)
        if not self.window.trusted:
            raise StardewAdapterError(FailureCode.WINDOW_LOSS.value)
        if not self.screenshot_references:
            raise StardewAdapterError(FailureCode.MISSING_EVIDENCE.value)
        if self.energy is None or self.energy_maximum is None:
            raise StardewAdapterError(FailureCode.RESOURCE_UNKNOWN.value)
        if not 0 <= self.energy <= self.energy_maximum:
            raise StardewAdapterError("energy observation is outside its visible range")
        if not self.tool.exact or not self.position.exact:
            raise StardewAdapterError(FailureCode.RESOURCE_UNKNOWN.value)
        if not self.scene_complete or self.unknown_regions:
            raise StardewAdapterError(FailureCode.UNKNOWN_STATE.value)
        seen: set[str] = set()
        coordinates: set[tuple[int, int]] = set()
        for crop in self.crops:
            crop.validate()
            if crop.crop_id in seen or (crop.tile_x, crop.tile_y) in coordinates:
                raise StardewAdapterError(FailureCode.ACCOUNTING_MISMATCH.value)
            seen.add(crop.crop_id)
            coordinates.add((crop.tile_x, crop.tile_y))
            if crop.occluded:
                raise StardewAdapterError(FailureCode.OCCLUDED_CROPS.value)
            if crop.confidence != 1.0:
                raise StardewAdapterError(FailureCode.UNKNOWN_STATE.value)


@dataclass(frozen=True)
class InputCommand:
    kind: InputKind
    control: str
    action: str
    duration_ms: int = 0
    target: tuple[int, int] | None = None
    purpose: str = ""
    reviewed_crop_id: str | None = None


@dataclass(frozen=True)
class OwnershipEpoch:
    epoch_id: str
    owner: InputOwner
    process_id: int
    process_started_at: str
    window_id: str
    save_tree_sha256: str
    observation_id: str
    input_driver: str
    authorized_at: str
    expires_at: str
    task_id: str
    stop_point: str
    stop_conditions: tuple[str, ...]
    neutralized: bool = False


@dataclass
class WateringLedger:
    task_id: str
    initial_crop_ids: tuple[str, ...]
    initially_watered_ids: tuple[str, ...]
    confirmed_watered_ids: set[str] = field(default_factory=set)
    tool_uses: int = 0
    refills: int = 0
    energy_start: int | None = None
    energy_current: int | None = None
    energy_spent: int = 0
    can_water_start: int | None = None
    can_water_current: int | None = None
    can_water_consumed: int = 0
    can_water_added: int = 0
    final_position: PositionObservation | None = None
    evidence_references: list[str] = field(default_factory=list)

    @classmethod
    def from_observation(cls, observation: ScreenObservation) -> WateringLedger:
        planted = tuple(sorted(crop.crop_id for crop in observation.crops if crop.planted))
        watered = tuple(sorted(crop.crop_id for crop in observation.crops if crop.planted and crop.watered))
        return cls(
            task_id=f"water-planted-{secrets.token_hex(6)}",
            initial_crop_ids=planted,
            initially_watered_ids=watered,
            confirmed_watered_ids=set(watered),
            tool_uses=observation.tool.tool_uses,
            refills=observation.tool.refill_count,
            energy_start=observation.energy,
            energy_current=observation.energy,
            can_water_start=observation.tool.watering_can_units,
            can_water_current=observation.tool.watering_can_units,
            final_position=observation.position,
            evidence_references=list(observation.screenshot_references),
        )

    def reconcile(self, observation: ScreenObservation) -> None:
        current = {crop.crop_id: crop for crop in observation.crops if crop.planted}
        if set(current) != set(self.initial_crop_ids):
            raise StardewAdapterError(FailureCode.ACCOUNTING_MISMATCH.value)
        newly_confirmed = {crop_id for crop_id, crop in current.items() if crop.watered}
        if not self.confirmed_watered_ids.issubset(newly_confirmed):
            raise StardewAdapterError("a previously confirmed watered crop became unverified")
        if observation.tool.tool_uses < self.tool_uses or observation.tool.refill_count < self.refills:
            raise StardewAdapterError(FailureCode.ACCOUNTING_MISMATCH.value)
        if self.energy_start is None or observation.energy is None:
            raise StardewAdapterError(FailureCode.RESOURCE_UNKNOWN.value)
        if self.energy_current is not None and observation.energy > self.energy_current:
            raise StardewAdapterError(FailureCode.ACCOUNTING_MISMATCH.value)
        current_water = observation.tool.watering_can_units
        if self.can_water_current is None or current_water is None:
            raise StardewAdapterError(FailureCode.RESOURCE_UNKNOWN.value)
        consumed = observation.tool.tool_uses - self.tool_uses
        added = current_water - self.can_water_current + consumed
        if added < 0 or (added > 0 and observation.tool.refill_count <= self.refills):
            raise StardewAdapterError(FailureCode.ACCOUNTING_MISMATCH.value)
        self.can_water_consumed += consumed
        self.can_water_added += added
        self.can_water_current = current_water
        self.confirmed_watered_ids = newly_confirmed
        self.tool_uses = observation.tool.tool_uses
        self.refills = observation.tool.refill_count
        self.energy_current = observation.energy
        self.energy_spent = self.energy_start - observation.energy
        if self.energy_spent < 0:
            raise StardewAdapterError(FailureCode.ACCOUNTING_MISMATCH.value)
        self.final_position = observation.position
        self.evidence_references.extend(observation.screenshot_references)

    @property
    def planted_count(self) -> int:
        return len(self.initial_crop_ids)

    @property
    def watered_count(self) -> int:
        return len(self.confirmed_watered_ids)

    @property
    def remaining_count(self) -> int:
        return self.planted_count - self.watered_count

    @property
    def complete(self) -> bool:
        return (
            self.remaining_count == 0
            and self.final_position is not None
            and self.final_position.exact
            and self.final_position.at_farmhouse_entrance is True
        )


@dataclass(frozen=True)
class OperatorFailure:
    code: FailureCode
    detail: str
    observed_at: str
    input_neutralized: bool
    evidence_retained: bool
    safe_recovery: str
    first_unmet_requirement: str


@dataclass(frozen=True)
class OperatorView:
    lifecycle: OperatorLifecycle
    save: SaveIdentity | None
    window: WindowObservation | None
    input_owner: InputOwner
    ledger: WateringLedger | None
    energy: int | None
    can_units: int | None
    failure: OperatorFailure | None
    evidence_status: str
    capability_status: Mapping[str, str]
    current_mode: str = "Observe"
    availability_reason: str = "A fresh exact screen observation is required."
    observation_freshness: str = "unknown"
    observation_evidence: tuple[str, ...] = ()
    tell_card: Any | None = None
    show_status: str = "not_started"
    do_authorization_scope: str | None = None
    do_authorization_expiry: str | None = None
    neutralization_status: str = "neutral"
    handback_status: str = "player control not established"
    reset_status: str = "not_started"
    protected_action_refusal: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tree_identity(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    count = 0
    byte_count = 0
    if not root.is_dir() or root.is_symlink():
        raise StardewAdapterError("save identity requires a real local directory")
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise StardewAdapterError("save directories containing symlinks are refused")
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode) or path.stat().st_nlink != 1:
            raise StardewAdapterError("save content must contain only unaliased regular files")
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        size = path.stat().st_size
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        count += 1
        byte_count += size
    if count == 0:
        raise StardewAdapterError("owner-provided save directory is empty")
    return digest.hexdigest(), count, byte_count


class DisposableSaveManager:
    """Creates one verified copy without modifying or following links from the primary save."""

    def create(self, primary_save: Path, destination: Path) -> SaveIdentity:
        primary_supplied = primary_save.expanduser().absolute()
        primary = primary_supplied.resolve(strict=True)
        if primary_supplied.is_symlink() or primary_supplied != primary:
            raise StardewAdapterError("aliased or symlinked primary save paths are refused")
        target = destination.expanduser().absolute()
        if primary == target or primary in target.parents or target in primary.parents:
            raise StardewAdapterError(FailureCode.PRIMARY_SAVE_RISK.value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target_parent = target.parent.resolve(strict=True)
        target_resolved = target_parent / target.name
        if target.parent.is_symlink() or target_resolved != target:
            raise StardewAdapterError("aliased or symlinked disposable destinations are refused")
        if target.exists() or target.is_symlink():
            raise StardewAdapterError("disposable save destination must not already exist")
        if primary == target_resolved or primary in target_resolved.parents or target_resolved in primary.parents:
            raise StardewAdapterError(FailureCode.PRIMARY_SAVE_RISK.value)
        before_hash, count, byte_count = _tree_identity(primary)
        try:
            shutil.copytree(primary, target_resolved, symlinks=True)
        except OSError as exc:
            raise StardewAdapterError(f"disposable save copy failed: {exc}") from exc
        after_primary_hash, _, _ = _tree_identity(primary)
        copy_hash, copy_count, copy_bytes = _tree_identity(target_resolved)
        identity = SaveIdentity(
            primary_path=str(primary_save),
            primary_real_path=str(primary),
            disposable_path=str(target_resolved),
            disposable_real_path=str(target_resolved.resolve(strict=True)),
            source_tree_sha256=before_hash,
            disposable_tree_sha256=copy_hash,
            file_count=copy_count,
            byte_count=copy_bytes,
            created_at=_utc_now(),
            nonce=secrets.token_hex(16),
            primary_unchanged=before_hash == after_primary_hash,
            disposable_only=(count == copy_count and byte_count == copy_bytes),
        )
        if (not identity.valid or primary != primary.resolve(strict=True) or
                target_resolved != target_resolved.resolve(strict=True)):
            raise StardewAdapterError(FailureCode.SAVE_MISMATCH.value)
        return identity

    def verify_primary_unchanged(self, identity: SaveIdentity) -> bool:
        primary = Path(identity.primary_real_path)
        try:
            if primary != primary.resolve(strict=True):
                return False
            current_hash, count, byte_count = _tree_identity(primary)
        except (OSError, StardewAdapterError):
            return False
        return (current_hash == identity.source_tree_sha256 and
                count == identity.file_count and byte_count == identity.byte_count)

    def reset(self, previous: SaveIdentity, fresh_destination: Path) -> SaveIdentity:
        """Create a new attempt-owned copy while preserving the previous attempt."""
        if not previous.valid or not self.verify_primary_unchanged(previous):
            raise StardewAdapterError(FailureCode.PRIMARY_SAVE_RISK.value)
        destination = fresh_destination.expanduser().absolute()
        previous_copy = Path(previous.disposable_real_path)
        if (
            destination == previous_copy
            or destination in previous_copy.parents
            or previous_copy in destination.parents
        ):
            raise StardewAdapterError("reset requires a fresh, non-nested attempt destination")
        reset_identity = self.create(Path(previous.primary_real_path), destination)
        if reset_identity.nonce == previous.nonce or not self.verify_primary_unchanged(reset_identity):
            raise StardewAdapterError(FailureCode.SAVE_MISMATCH.value)
        return reset_identity


class StardewEvidenceStore:
    def __init__(self, root: Path = DEFAULT_ARTIFACT_ROOT) -> None:
        self.root = root

    def begin(self, save: SaveIdentity) -> Path:
        attempt = self.root / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{secrets.token_hex(4)}"
        attempt.mkdir(parents=True, exist_ok=False)
        self._write_once(attempt / "attempt.json", {"schema_version": STARDEW_SCHEMA_VERSION, "save": asdict(save)})
        return attempt

    def append(self, attempt: Path, event_type: str, payload: Mapping[str, Any]) -> None:
        attempt = attempt.resolve(strict=True)
        if self.root.resolve() not in attempt.parents:
            raise StardewAdapterError("evidence attempt is outside the adapter artifact root")
        record = {"event_id": secrets.token_hex(12), "event_type": event_type, "occurred_at": _utc_now(), **payload}
        with (attempt / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def finalize(self, attempt: Path, report: Mapping[str, Any]) -> None:
        self._write_once(attempt / "report.json", dict(report))

    @staticmethod
    def _write_once(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


class MacVisibleStardewBackend:
    """Reads only normal macOS process/window metadata and visible window pixels."""

    def __init__(self, *, process_id: int | None = None, process_started_at: str | None = None) -> None:
        if (process_id is None) != (process_started_at is None):
            raise StardewAdapterError("Expected process id and start identity must be supplied together")
        self.expected_process_id = process_id
        self.expected_process_started_at = process_started_at

    def detect_window(self, *, require_foreground: bool = True) -> WindowObservation:
        try:
            import Quartz
            from AppKit import NSWorkspace
        except ImportError as exc:
            raise StardewAdapterError("macOS visible-window dependencies are unavailable") from exc
        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        records = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or ()
        candidates: list[Mapping[str, Any]] = []
        for record in records:
            if (self.expected_process_id is not None and
                    int(record.get(Quartz.kCGWindowOwnerPID, -1)) != self.expected_process_id):
                continue
            owner = str(record.get(Quartz.kCGWindowOwnerName, ""))
            title = str(record.get(Quartz.kCGWindowName, ""))
            layer = int(record.get(Quartz.kCGWindowLayer, -1))
            alpha = float(record.get(Quartz.kCGWindowAlpha, 0.0))
            if "stardew valley" in f"{owner} {title}".lower() and layer == 0 and alpha > 0:
                candidates.append(record)
        if len(candidates) != 1:
            raise StardewAdapterError(
                f"expected exactly one visible Stardew window; observed {len(candidates)}"
            )
        record = candidates[0]
        bounds = record.get(Quartz.kCGWindowBounds) or {}
        geometry = (
            int(bounds.get("X", 0)),
            int(bounds.get("Y", 0)),
            int(bounds.get("Width", 0)),
            int(bounds.get("Height", 0)),
        )
        process_id = int(record[Quartz.kCGWindowOwnerPID])
        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        foreground = bool(frontmost and frontmost.processIdentifier() == process_id)
        started = subprocess.run(
            ["ps", "-p", str(process_id), "-o", "lstart="],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not started or geometry[2] <= 0 or geometry[3] <= 0:
            raise StardewAdapterError(FailureCode.WINDOW_LOSS.value)
        if self.expected_process_started_at is not None and started != self.expected_process_started_at:
            raise StardewAdapterError(FailureCode.PROCESS_LOSS.value)
        display_bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        fullscreen = (
            geometry[0] == int(display_bounds.origin.x)
            and geometry[1] == int(display_bounds.origin.y)
            and geometry[2] == int(display_bounds.size.width)
            and geometry[3] == int(display_bounds.size.height)
        )
        window = WindowObservation(
            process_id=process_id,
            process_started_at=started,
            window_id=str(record[Quartz.kCGWindowNumber]),
            title=str(record.get(Quartz.kCGWindowName) or record.get(Quartz.kCGWindowOwnerName) or "Stardew Valley"),
            bounds=geometry,
            visible=True,
            windowed=not fullscreen,
            foreground=foreground,
        )
        if (not window.windowed or window.occluded or
                (require_foreground and not window.trusted)):
            raise StardewAdapterError(FailureCode.WINDOW_LOSS.value)
        return window

    def capture(self, window: WindowObservation, destination: Path) -> Path:
        if not window.trusted or window.bounds is None:
            raise StardewAdapterError(FailureCode.WINDOW_LOSS.value)
        current = self.detect_window()
        if (
            current.process_id != window.process_id
            or current.process_started_at != window.process_started_at
            or current.window_id != window.window_id
        ):
            raise StardewAdapterError(FailureCode.PROCESS_LOSS.value)
        if destination.exists():
            raise StardewAdapterError("screen evidence destination already exists")
        try:
            import mss
            from PIL import Image
        except ImportError as exc:
            raise StardewAdapterError("visible screen-capture dependencies are unavailable") from exc
        x, y, width, height = window.bounds
        with mss.mss() as capture:
            frame = capture.grab({"left": x, "top": y, "width": width, "height": height})
        destination.parent.mkdir(parents=True, exist_ok=True)
        Image.frombytes("RGB", frame.size, frame.rgb).save(destination, format="PNG")
        return destination

def load_stardew_contract(path: Path = ADAPTER_CONTRACT_PATH) -> Mapping[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise StardewAdapterError(f"Stardew adapter contract is unavailable: {exc}") from exc
    if not isinstance(raw, Mapping) or raw.get("schema_version") != STARDEW_SCHEMA_VERSION:
        raise StardewAdapterError("Stardew adapter contract has an unsupported schema")
    return raw


class StardewOperator:
    """Visible-screen operator for one copied-save watering task; no companion modes."""

    def __init__(self, save: SaveIdentity, *, contract_path: Path = ADAPTER_CONTRACT_PATH) -> None:
        if not save.valid:
            raise StardewAdapterError(FailureCode.SAVE_MISMATCH.value)
        self.save = save
        self.contract = load_stardew_contract(contract_path)
        self.lifecycle = OperatorLifecycle.COPY_READY
        self.owner = InputOwner.PLAYER
        self.window: WindowObservation | None = None
        self.observation: ScreenObservation | None = None
        self.ledger: WateringLedger | None = None
        self.epoch: OwnershipEpoch | None = None
        self.failure: OperatorFailure | None = None
        self.input_neutralized = True

    def attach_player_owned(self, observation: ScreenObservation) -> None:
        observation.validate(self.save.disposable_tree_sha256)
        self._bind_window(observation.window)
        self.observation = observation
        self.owner = InputOwner.PLAYER
        self.lifecycle = OperatorLifecycle.PLAYER_OWNED

    def establish_task(self, observation: ScreenObservation) -> WateringLedger:
        if self.lifecycle is not OperatorLifecycle.PLAYER_OWNED or self.owner is not InputOwner.PLAYER:
            raise StardewAdapterError(FailureCode.AMBIGUOUS_OWNERSHIP.value)
        self._validate_same_process(observation)
        observation.validate(self.save.disposable_tree_sha256)
        self.ledger = WateringLedger.from_observation(observation)
        self.observation = observation
        return self.ledger

    def authorize_agent(
        self,
        *,
        expires_at: str,
        owner_confirmation: bool,
        input_driver: str = "unconfigured",
        stop_conditions: tuple[str, ...] = (
            "completion", "reclaim", "timeout", "failure", "ambiguity",
            "process_or_window_loss", "save_mismatch", "protected_action_risk",
        ),
    ) -> OwnershipEpoch:
        if not owner_confirmation or self.owner is not InputOwner.PLAYER or self.ledger is None or self.window is None:
            raise StardewAdapterError(FailureCode.AMBIGUOUS_OWNERSHIP.value)
        if not self.window.trusted or self.window.process_id is None or self.window.process_started_at is None:
            raise StardewAdapterError(FailureCode.PROCESS_LOSS.value)
        try:
            expiry = datetime.fromisoformat(expires_at)
        except ValueError as exc:
            raise StardewAdapterError("authorization expiry must be an ISO-8601 timestamp") from exc
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise StardewAdapterError("authorization must expire in the future")
        self.epoch = OwnershipEpoch(
            epoch_id=secrets.token_hex(16),
            owner=InputOwner.AGENT,
            process_id=self.window.process_id,
            process_started_at=self.window.process_started_at,
            window_id=str(self.window.window_id),
            save_tree_sha256=self.save.disposable_tree_sha256,
            observation_id=str(self.observation.observation_id if self.observation else ""),
            input_driver=input_driver,
            authorized_at=_utc_now(),
            expires_at=expires_at,
            task_id=self.ledger.task_id,
            stop_point="all initially observed planted crops watered and player at farmhouse entrance",
            stop_conditions=stop_conditions,
        )
        self.owner = InputOwner.AGENT
        self.lifecycle = OperatorLifecycle.AGENT_AUTHORIZED
        self.input_neutralized = True
        return self.epoch

    def validate_input(self, command: InputCommand, observation: ScreenObservation) -> None:
        if self.owner is not InputOwner.AGENT or self.epoch is None:
            raise StardewAdapterError(FailureCode.AMBIGUOUS_OWNERSHIP.value)
        if datetime.fromisoformat(self.epoch.expires_at) <= datetime.now(timezone.utc):
            raise StardewAdapterError(FailureCode.AMBIGUOUS_OWNERSHIP.value)
        self._validate_same_process(observation)
        observation.validate(self.save.disposable_tree_sha256)
        allowed = self.contract.get("ordinary_input", {})
        if command.kind.value not in allowed:
            raise StardewAdapterError(FailureCode.INPUT_REJECTED.value)
        permitted = {str(item) for item in allowed[command.kind.value]}
        if command.control not in permitted or command.duration_ms < 0:
            raise StardewAdapterError(FailureCode.INPUT_REJECTED.value)
        normalized = f"{command.control} {command.action} {command.purpose}".lower()
        if any(term.lower() in normalized for term in self.contract.get("protected_action_terms", ())):
            raise StardewAdapterError(FailureCode.PROTECTED_ACTION_RISK.value)
        if command.purpose not in {"navigate", "select_watering_can", "water_crop", "refill", "return_to_entrance", "neutralize"}:
            raise StardewAdapterError(FailureCode.PROTECTED_ACTION_RISK.value)
        if command.purpose == "water_crop" and (
            observation.tool.selected_tool != "watering_can"
            or observation.tool.watering_can_units is None
            or observation.tool.watering_can_units <= 0
        ):
            raise StardewAdapterError(FailureCode.RESOURCE_UNKNOWN.value)
        if command.purpose == "refill" and observation.position.location not in {
            str(item) for item in self.contract.get("refill_locations", ())
        }:
            raise StardewAdapterError(FailureCode.PROTECTED_ACTION_RISK.value)

    def send_input(
        self,
        command: InputCommand,
        observation: ScreenObservation,
        driver: OrdinaryInputDriver,
    ) -> None:
        self.validate_input(command, observation)
        self.input_neutralized = False
        try:
            driver.send(command)
        except Exception as exc:
            self.fail(
                FailureCode.INPUT_REJECTED,
                f"ordinary input failed: {type(exc).__name__}: {exc}",
                driver=driver,
            )
            raise StardewAdapterError(FailureCode.INPUT_REJECTED.value) from exc

    def record_post_input(self, observation: ScreenObservation) -> WateringLedger:
        if self.owner is not InputOwner.AGENT or self.ledger is None:
            raise StardewAdapterError(FailureCode.AMBIGUOUS_OWNERSHIP.value)
        self._validate_same_process(observation)
        observation.validate(self.save.disposable_tree_sha256)
        self.ledger.reconcile(observation)
        self.observation = observation
        self.lifecycle = OperatorLifecycle.RUNNING
        self.input_neutralized = True
        return self.ledger

    def reclaim(self, driver: OrdinaryInputDriver | None = None) -> bool:
        self.lifecycle = OperatorLifecycle.RECLAIMING
        neutralized = True
        if driver is not None:
            try:
                driver.neutralize()
            except Exception:
                neutralized = False
        self.input_neutralized = neutralized
        self.epoch = None
        self.owner = InputOwner.PLAYER if neutralized else InputOwner.NONE
        self.lifecycle = OperatorLifecycle.STOPPED if neutralized else OperatorLifecycle.FAILED
        return neutralized

    def complete(self, final_observation: ScreenObservation) -> None:
        self.record_post_input(final_observation)
        if self.ledger is None or not self.ledger.complete:
            raise StardewAdapterError(FailureCode.ACCOUNTING_MISMATCH.value)
        if not self.reclaim():
            raise StardewAdapterError(FailureCode.INPUT_REJECTED.value)
        self.lifecycle = OperatorLifecycle.COMPLETED

    def fail(
        self,
        code: FailureCode,
        detail: str,
        *,
        driver: OrdinaryInputDriver | None = None,
    ) -> OperatorFailure:
        neutralized = True
        neutralization_error: str | None = None
        if driver is not None:
            try:
                driver.neutralize()
            except Exception as exc:
                neutralized = False
                neutralization_error = f"{type(exc).__name__}: {exc}"
        recorded_detail = (
            detail
            if neutralization_error is None
            else f"{detail}; neutralization failed: {neutralization_error}"
        )
        self.input_neutralized = neutralized
        self.epoch = None
        self.owner = (
            InputOwner.PLAYER
            if neutralized and self.window and self.window.trusted
            else InputOwner.NONE
        )
        self.lifecycle = OperatorLifecycle.FAILED
        self.failure = OperatorFailure(
            code=code,
            detail=recorded_detail,
            observed_at=_utc_now(),
            input_neutralized=neutralized,
            evidence_retained=True,
            safe_recovery="Stop. Keep the copied save and evidence. Re-detect the process, window, save identity, and player ownership before a fresh attempt.",
            first_unmet_requirement=(
                detail
                if neutralized
                else f"input neutralization could not be verified; {recorded_detail}"
            ),
        )
        return self.failure

    def view(self) -> OperatorView:
        capabilities = {
            str(item["id"]): str(item["status"])
            for item in self.contract.get("capabilities", ())
        }
        return OperatorView(
            lifecycle=self.lifecycle,
            save=self.save,
            window=self.window,
            input_owner=self.owner,
            ledger=self.ledger,
            energy=self.observation.energy if self.observation else None,
            can_units=self.observation.tool.watering_can_units if self.observation else None,
            failure=self.failure,
            evidence_status="retained" if self.failure else "pending",
            capability_status=capabilities,
            current_mode="Do" if self.owner is InputOwner.AGENT else "Observe",
            availability_reason=(
                "Fresh exact copied-save observation is available."
                if self.observation is not None
                else "A fresh exact screen observation is required."
            ),
            observation_freshness="fresh" if self.observation is not None else "unknown",
            observation_evidence=(self.observation.screenshot_references if self.observation else ()),
            do_authorization_scope=(self.epoch.task_id if self.epoch else None),
            do_authorization_expiry=(self.epoch.expires_at if self.epoch else None),
            neutralization_status="neutral" if self.input_neutralized else "input active",
            handback_status=(
                "player ownership restored"
                if self.owner is InputOwner.PLAYER and self.input_neutralized
                else "handback pending"
            ),
            protected_action_refusal=(
                self.failure.detail
                if self.failure and self.failure.code is FailureCode.PROTECTED_ACTION_RISK
                else None
            ),
        )

    def _bind_window(self, window: WindowObservation) -> None:
        if not window.trusted:
            raise StardewAdapterError(FailureCode.WINDOW_LOSS.value)
        self.window = window

    def _validate_same_process(self, observation: ScreenObservation) -> None:
        if self.window is None or not observation.window.trusted:
            raise StardewAdapterError(FailureCode.PROCESS_LOSS.value)
        if (
            observation.window.process_id != self.window.process_id
            or observation.window.process_started_at != self.window.process_started_at
            or observation.window.window_id != self.window.window_id
        ):
            raise StardewAdapterError(FailureCode.PROCESS_LOSS.value)


class OrdinaryInputDriver:
    """Uses only configured OS-visible keyboard, mouse, or controller emitters."""

    def __init__(
        self,
        *,
        keyboard: Callable[[InputCommand], None] | None = None,
        mouse: Callable[[InputCommand], None] | None = None,
        controller: Callable[[InputCommand], None] | None = None,
        neutralizer: Callable[[], None] | None = None,
    ) -> None:
        self._emitters = {
            InputKind.KEYBOARD: keyboard,
            InputKind.MOUSE: mouse,
            InputKind.CONTROLLER: controller,
        }
        self._neutralizer = neutralizer

    def available(self, kind: InputKind) -> bool:
        return self._emitters[kind] is not None

    def send(self, command: InputCommand) -> None:
        emitter = self._emitters.get(command.kind)
        if emitter is None:
            raise StardewAdapterError(f"no ordinary {command.kind.value} emitter is configured")
        emitter(command)

    def neutralize(self) -> None:
        if self._neutralizer is not None:
            self._neutralizer()


def render_stardew_operator(view: OperatorView) -> str:
    ledger = view.ledger
    crop_text = "Unknown" if ledger is None else f"{ledger.watered_count} / {ledger.planted_count}"
    remaining = "Unknown" if ledger is None else str(ledger.remaining_count)
    position = "Unknown"
    if ledger and ledger.final_position:
        position = "Farmhouse entrance" if ledger.final_position.at_farmhouse_entrance else (
            f"{ledger.final_position.location} ({ledger.final_position.tile_x}, {ledger.final_position.tile_y})"
        )
    failure = ""
    if view.failure:
        failure = f'<section class="failure" role="alert" data-testid="failure"><h2>Stopped safely</h2><p>Cannot continue: {html.escape(view.failure.first_unmet_requirement)}</p><p>{html.escape(view.failure.safe_recovery)}</p></section>'
    save_label = "No copied save"
    if view.save:
        save_label = f"Disposable copy · {view.save.disposable_tree_sha256[:12]}"
    tell_text = "Advice needs a fresh view of the game."
    if view.tell_card is not None:
        summary = getattr(getattr(view.tell_card, "state_summary", None), "text", None)
        steps = getattr(view.tell_card, "steps", ())
        first_step = getattr(getattr(steps[0], "action", None), "text", None) if steps else None
        tell_text = " ".join(item for item in (summary, first_step) if item)
    evidence_text = ", ".join(view.observation_evidence) or "No current screenshot"
    do_scope = view.do_authorization_scope or "Not authorized"
    do_expiry = view.do_authorization_expiry or "No expiry"
    protected = view.protected_action_refusal or "Purchases, sales, discards, gifts, dialogue/story choices, sleep, saves, and unknown refills are refused."
    modes_ready = view.observation_freshness == "fresh" and view.input_owner is InputOwner.PLAYER
    tell_disabled = "" if modes_ready else " disabled"
    show_start_disabled = "" if modes_ready and view.show_status != "active" else " disabled"
    show_stop_disabled = "" if view.show_status == "active" else " disabled"
    do_disabled = "" if modes_ready else " disabled"
    reclaim_disabled = "" if view.input_owner is InputOwner.AGENT else " disabled"
    refills = "Unknown" if ledger is None else str(ledger.refills)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stardew Valley · Game Companion</title><style>
:root{{--bg:#121611;--panel:#1d241b;--ink:#f4f0df;--muted:#b8c1aa;--accent:#e7bc52;--safe:#86c879;--danger:#e38475}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,sans-serif}}
main{{max-width:1040px;margin:auto;padding:24px}}header,.grid,section{{border:1px solid #3b4636;border-radius:14px;background:var(--panel)}}
header,section{{padding:18px}}h1,h2,h3,p{{margin-top:0}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;overflow:hidden;margin:16px 0;background:#3b4636}}
.metric{{background:var(--panel);padding:16px}}.metric strong{{display:block;font-size:1.45rem;color:var(--accent)}}.muted{{color:var(--muted)}}
.owner{{color:var(--safe)}}.failure{{border-color:var(--danger)}}.mode-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}}.mode-card{{min-width:0}}.actions{{display:flex;gap:10px;flex-wrap:wrap}}button{{min-height:44px;border-radius:9px;border:0;padding:0 16px;font-weight:700}}
button[disabled]{{opacity:.5}}@media(max-width:620px){{main{{padding:12px}}.grid{{grid-template-columns:repeat(2,1fr)}}header,section{{padding:14px}}}}
@media(max-width:390px){{.mode-grid{{grid-template-columns:1fr}}.actions button{{width:100%}}}}
</style><style>{GLASS_CSS}{STARDEW_GLASS_CSS}</style></head><body><main data-testid="stardew-operator">
<header><nav><a href="/">Choose a game</a></nav><h1>Stardew Valley</h1><p><strong>Water every planted crop</strong> · copied save only · <span data-testid="save-identity">{html.escape(save_label)}</span></p><p>{html.escape(view.availability_reason)}</p><p class="muted">Mode: <strong data-testid="current-mode">{html.escape(view.current_mode)}</strong> · <strong data-testid="input-owner">{html.escape({"none": "No companion input", "player": "You control the game", "agent": "Companion is playing"}.get(view.input_owner.value, view.input_owner.value))}</strong> · {html.escape(view.lifecycle.value.replace('_', ' '))}</p></header>
{failure}<details class="stardew-progress" {'open' if ledger else ''}><summary>Watering progress{' — not observed yet' if ledger is None else ''}</summary><div class="grid" aria-label="Task accounting"><div class="metric"><span>Watered</span><strong data-testid="crop-progress">{crop_text}</strong></div><div class="metric"><span>Remaining</span><strong>{remaining}</strong></div><div class="metric"><span>Energy</span><strong>{view.energy if view.energy is not None else 'Unknown'}</strong></div><div class="metric"><span>Water in can</span><strong>{view.can_units if view.can_units is not None else 'Unknown'}</strong></div><div class="metric"><span>Refills</span><strong data-testid="refill-count">{refills}</strong></div></div></details>
<div class="mode-grid"><section class="mode-card"><h2>Game observation</h2><p>Freshness: <strong data-testid="observation-freshness">{html.escape(view.observation_freshness)}</strong></p><details><summary>Screenshot evidence</summary><p>{html.escape(evidence_text)}</p></details></section><section class="mode-card"><h2>Advice</h2><p data-testid="tell-card">{html.escape(tell_text)}</p><button{tell_disabled}>Refresh advice</button></section><section class="mode-card"><h2>Demonstration</h2><p>Review only; does not complete your game.</p><p>Status: <span data-testid="show-status">{html.escape(view.show_status.replace('_', ' '))}</span></p><div class="actions"><button{show_start_disabled}>Start demonstration</button><button{show_stop_disabled}>Stop demonstration</button></div></section></div>
<section class="stardew-control"><h2>Companion play</h2><p>Scope: <strong data-testid="do-scope">{html.escape(do_scope)}</strong> · Expiry: {html.escape(do_expiry)}</p><p>Input stopped: <strong data-testid="neutralization-status">{html.escape({"neutral": "Yes", "input active": "No — input is active"}.get(view.neutralization_status, view.neutralization_status))}</strong> · Control returned: <strong data-testid="handback-status">{html.escape({"player ownership required before active modes": "Confirm player control before starting", "player ownership restored": "Yes", "handback pending": "Not yet confirmed"}.get(view.handback_status, view.handback_status))}</strong></p><div class="actions"><button{do_disabled}>Authorize one watering task</button><button{reclaim_disabled}>Take control now</button></div><p class="muted">Controls remain disabled until there is a verified save copy, a fresh game observation and your permission for this task.</p></section>
<section><h2>Where this task stops</h2><p>Water the exact crops observed at task start, then return to the farmhouse entrance. Stop on any unknown, occlusion, save/process mismatch, ownership ambiguity, or protected action.</p><p>Final position: <strong data-testid="final-position">{html.escape(position)}</strong></p><details><summary>Attempt details and reset</summary><p>Evidence: {html.escape(view.evidence_status)}</p><p>Reset: <strong data-testid="reset-status">{html.escape(view.reset_status.replace('_', ' '))}</strong>. Reset creates a fresh attempt-owned copy and preserves the prior attempt.</p><button disabled>Reset disposable copy</button></details></section>
<section><h2>Protected actions</h2><p data-testid="protected-action-refusal">{html.escape(protected)}</p></section>
</main></body></html>"""


def fixture_observation(raw: Mapping[str, Any]) -> ScreenObservation:
    window = WindowObservation(**raw["window"])
    crops = tuple(CropObservation(**item) for item in raw.get("crops", ()))
    tool = ToolObservation(**raw["tool"])
    position = PositionObservation(**raw["position"])
    return ScreenObservation(
        observation_id=str(raw["observation_id"]),
        observed_at=str(raw["observed_at"]),
        save_tree_sha256=str(raw["save_tree_sha256"]),
        window=window,
        crops=crops,
        energy=raw.get("energy"),
        energy_maximum=raw.get("energy_maximum"),
        tool=tool,
        position=position,
        screenshot_references=tuple(str(item) for item in raw.get("screenshot_references", ())),
        source=str(raw.get("source", "screen")),
        scene_complete=bool(raw.get("scene_complete", False)),
        unknown_regions=tuple(str(item) for item in raw.get("unknown_regions", ())),
    )


def reconcile_evidence_files(attempt: Path, required: Iterable[str]) -> tuple[str, ...]:
    missing = tuple(item for item in required if not (attempt / item).is_file())
    if missing:
        raise StardewAdapterError(f"{FailureCode.MISSING_EVIDENCE.value}: {', '.join(missing)}")
    return tuple(sorted(required))
