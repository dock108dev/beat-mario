from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import yaml

from smb3_agent.companion_session import Freshness
from smb3_agent.companion_catalog import (
    AdapterCatalogEntry,
    AdapterRuntimeState,
    CatalogCapability,
    CatalogEvidence,
    CatalogGoal,
    CatalogObservation,
    CatalogProfile,
    CatalogSafety,
    CatalogScope,
    CompanionCatalogError,
)
from smb3_agent.live_observation import ConnectionState, LiveObservationSnapshot
from smb3_agent.takeover import supported_solutions


PRODUCT_SCHEMA_VERSION = "game-companion-mario-product/v1"
PILOT_MANIFEST_PATH = Path("data/scenarios/mario-owner-pilot.yaml")
ADAPTER_PRODUCT_PATH = Path("data/mario/product.yaml")
DEFAULT_PRODUCT_ROOT = Path("artifacts/product-session")


class MarioCatalogProvider:
    """Mario-owned catalog declaration and switch hooks."""

    def __init__(
        self,
        *,
        availability: Callable[[], tuple[str, str, str]] | None = None,
        runtime: Callable[[], AdapterRuntimeState] | None = None,
        retain: Callable[[], bool] | None = None,
        invalidate: Callable[[], bool] | None = None,
    ) -> None:
        self._availability = availability or (
            lambda: (
                "setup_required",
                "Choose a supported local game file, confirm FCEUX, and start a new observation.",
                "unconfigured",
            )
        )
        self._runtime = runtime or (lambda: AdapterRuntimeState(adapter_id="smb3"))
        self._retain = retain or (lambda: True)
        self._invalidate = invalidate or (lambda: True)

    def catalog_entry(self) -> AdapterCatalogEntry:
        contract = _load_adapter_product()
        if contract.get("adapter_id") != "smb3" or contract.get("game_id") != "smb3":
            raise CompanionCatalogError("Mario catalog/provider identity disagreement")
        if contract.get("adapter_version") != "smb3-live-observer/v1":
            raise CompanionCatalogError("Mario catalog/provider version disagreement")
        availability, reason, setup = self._availability()
        capabilities = (
            CatalogCapability("tell", "Tell", "available", "Grounded advice from fresh observed state."),
            CatalogCapability("show", "Show", "available", "Separate fresh-process World 1-1 demonstration; review only."),
            CatalogCapability("do", "Do", "available", "Explicit same-process takeover with an accepted replay-safe solution."),
        )
        profiles = (
            CatalogProfile("smb3.world-1-1.fastest-accepted-clear", "Fastest accepted World 1-1 clear", "speed", "Like-for-like emulator-frame comparison."),
            CatalogProfile("smb3.world-1-1.observable-progress-checklist", "World 1-1 observable progress", "completion", "Finite milestones visible to the passive observer."),
            CatalogProfile("smb3.route.world-8-double-whistle", "Accepted World 8 arrival route", "accepted_solution", "Replay-safe route through genuine World 8 map arrival."),
            CatalogProfile("smb3.route.world-8-big-tanks", "Accepted Big Tanks route", "accepted_solution", "Accepted cumulative route through Big Tanks."),
            CatalogProfile("smb3.route.world-8-battleships", "Accepted Battleships route", "accepted_solution", "Accepted cumulative route through Battleships."),
            CatalogProfile("smb3.route.world-8-hand-traps-jet", "Accepted Hand Traps and Jet route", "accepted_solution", "Accepted cumulative route through all Hand Traps and the Jet."),
            CatalogProfile("smb3.route.world-8-8-2", "Accepted World 8-2 route", "accepted_solution", "Accepted cumulative route through World 8-2."),
            CatalogProfile("smb3.route.world-8-super-tanks", "Accepted Super Tanks route", "accepted_solution", "Accepted cumulative route through Super Tanks and Bowser's Castle access."),
            CatalogProfile("smb3.full-game.accepted-route", "Accepted full-game route", "accepted_solution", "Replay-safe fresh-power-on route through the stable ending."),
        )
        return AdapterCatalogEntry(
            adapter_id="smb3",
            game_id="smb3",
            display_name="Super Mario Bros. 3",
            description="Live coaching, separate demonstration, and bounded takeover through the accepted FCEUX adapter.",
            adapter_version="smb3-live-observer/v1",
            implementation_status="V2.9 implementation complete; final validation deferred",
            availability=availability,
            availability_reason=reason,
            setup_state=setup,
            observation=CatalogObservation(
                "fceux_live_observer",
                "Read-only FCEUX observation",
                "The observer reads the visible session and controller stream; only the separately authorized takeover path can send input.",
            ),
            capabilities=capabilities,
            goals=(
                CatalogGoal("world_1_king", "World 1 King", "Observe, Tell, compare, or Show the supported World 1-1 boundary within the accepted World 1 route.", (profiles[0].profile_id, profiles[1].profile_id)),
                CatalogGoal("world_8_double_whistle", "World 8 arrival", "Reach the genuine World 8 map through the accepted double-whistle route.", (profiles[2].profile_id,)),
                CatalogGoal("world_8_big_tanks", "Big Tanks", "Run the accepted cumulative route through Big Tanks.", (profiles[3].profile_id,)),
                CatalogGoal("world_8_battleships", "Battleships", "Run the accepted cumulative route through Battleships.", (profiles[4].profile_id,)),
                CatalogGoal("world_8_hand_traps_jet", "Hand Traps and Jet", "Run all accepted Hand Traps and the Jet section.", (profiles[5].profile_id,)),
                CatalogGoal("world_8_8_2", "World 8-2", "Run the accepted cumulative route through World 8-2.", (profiles[6].profile_id,)),
                CatalogGoal("world_8_super_tanks", "Super Tanks", "Run the accepted cumulative route through Super Tanks and stop with Bowser's Castle accessible.", (profiles[7].profile_id,)),
                CatalogGoal("world_8_finish_game", "Finish Super Mario Bros. 3", "Execute the accepted fresh-power-on route through the stable game-owned ending.", (profiles[8].profile_id,)),
            ),
            profiles=profiles,
            scopes=(
                CatalogScope("obstacle", "One obstacle", ("declared checkpoint", "reclaim", "timeout", "failure", "continuity loss")),
                CatalogScope("level", "One level", ("game-owned level clear", "reclaim", "timeout", "failure", "continuity loss")),
                CatalogScope("full_game", "Accepted full game", ("stable game-owned ending", "reclaim", "timeout", "failure", "continuity loss")),
            ),
            safety=CatalogSafety(
                "Fresh same-process authority, actor-labeled input, immediate reclaim, neutral input, and verified player handback.",
                ("No savestates or memory mutation", "No route bypass", "No protected inventory use", "No acceptance claim from review-only evidence"),
                "Stop on the declared boundary, reclaim, timeout, mismatch, protected-resource conflict, or unknown state.",
                "Take Control Now invalidates the control epoch and neutralizes before ownership changes.",
                "Player ownership is confirmed before another active mode can begin.",
            ),
            evidence=CatalogEvidence(
                "mario",
                ("review_only", "technical", "owner_feedback", "reliability", "authoritative_gameplay"),
                "Mario evidence remains Mario-owned; classifications never promote one another implicitly.",
            ),
            standalone_surface="/mario",
            recovery_guidance="Return to Mario setup or a fresh observation; never restore a prior process identity, observation, or authorization.",
        )

    def runtime_state(self) -> AdapterRuntimeState:
        state = self._runtime()
        if state.adapter_id != "smb3":
            raise CompanionCatalogError("Mario runtime identity disagreement")
        return state

    def retain_for_switch(self) -> bool:
        return self._retain()

    def invalidate_volatile_state(self) -> bool:
        return self._invalidate()


class MarioProductError(ValueError):
    pass


class ProductStage(str, Enum):
    FIRST_USE = "first_use"
    IDLE = "idle"
    STARTING = "starting"
    PLAYER_OBSERVING = "player_observing"
    TELL_COACHING = "tell_coaching"
    SHOW_ACTIVE_SEPARATELY = "show_active_separately"
    DO_PREFLIGHT = "do_preflight"
    DO_AUTHORIZED = "do_authorized"
    AGENT_CONTROLLING = "agent_controlling"
    RECLAIM = "reclaim"
    HANDBACK = "handback"
    FAILURE = "failure"
    RECOVERY = "recovery"
    STOPPED = "stopped"
    HISTORICAL_REVIEW = "historical_review"


class SetupStatus(str, Enum):
    READY = "ready"
    NEEDS_GAME_FILE = "needs_game_file"
    INVALID_GAME_FILE = "invalid_game_file"
    NEEDS_EMULATOR = "needs_emulator"
    NEEDS_INPUT_CONFIRMATION = "needs_input_confirmation"
    CONFIGURATION_ERROR = "configuration_error"


@dataclass(frozen=True)
class GameFileIdentity:
    path: Path | None
    detected_from: str
    present: bool
    valid_container: bool
    supported_identity: bool
    sha256: str | None
    display: str
    reason: str


@dataclass(frozen=True)
class EmulatorIdentity:
    path: Path | None
    available: bool
    reason: str


@dataclass(frozen=True)
class FirstUseState:
    status: SetupStatus
    game_file: GameFileIdentity
    emulator: EmulatorIdentity
    input_ready: bool
    input_reason: str
    selected_session_kind: str | None
    error: str | None
    error_retained: bool

    @property
    def launch_ready(self) -> bool:
        return (
            self.game_file.supported_identity
            and self.emulator.available
            and self.input_ready
        )


@dataclass(frozen=True)
class CapabilityPresentation:
    capability_id: str
    label: str
    available: bool
    summary: str
    unavailable_reason: str | None
    supported_scope: tuple[str, ...] = ()
    contract_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryPresentation:
    failure_id: str
    title: str
    what_happened: str
    game_may_be_running: bool
    input_owner: str
    agent_input_stopped: bool
    safe_next_action: str
    evidence_retained: bool
    retry_creates_fresh_attempt: bool


@dataclass(frozen=True)
class ProductSessionView:
    schema_version: str
    stage: ProductStage
    first_use: FirstUseState
    capabilities: tuple[CapabilityPresentation, ...]
    current_failure: RecoveryPresentation | None
    resumable_session_id: str | None
    history_count: int
    unsafe_state_restored: bool = False


@dataclass
class ProductPreferences:
    schema_version: str = PRODUCT_SCHEMA_VERSION
    game_file_path: str | None = None
    game_file_sha256: str | None = None
    input_ready_confirmed: bool = False
    session_kind: str | None = None
    detail_level: str = "guided"
    coaching_policy: str = "on_request"
    updated_at: str | None = None


@dataclass
class ProductHistoryEntry:
    event_id: str
    event_type: str
    stage: str
    occurred_at: str
    session_id: str | None
    input_owner: str
    evidence_status: str
    detail: str
    recovery: Mapping[str, Any] | None = None


def _load_adapter_product(path: Path = ADAPTER_PRODUCT_PATH) -> Mapping[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise MarioProductError(f"Mario product contract is unavailable: {exc}") from exc
    if not isinstance(raw, Mapping) or raw.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise MarioProductError("Mario product contract has an unsupported schema")
    return raw


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class MarioProductSessionManager:
    """Owns the player product state without restoring live control authority."""

    def __init__(
        self,
        root: Path = DEFAULT_PRODUCT_ROOT,
        adapter_product_path: Path = ADAPTER_PRODUCT_PATH,
    ) -> None:
        self.root = root
        self.preferences_path = root / "preferences.json"
        self.history_path = root / "history.jsonl"
        self.adapter_product_path = adapter_product_path
        self._error: RecoveryPresentation | None = None
        self._starting = False
        self._stage_override: ProductStage | None = None

    def preferences(self) -> ProductPreferences:
        if not self.preferences_path.exists():
            return ProductPreferences()
        try:
            raw = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            if raw.get("schema_version") != PRODUCT_SCHEMA_VERSION:
                raise MarioProductError("Saved Mario preferences use an unsupported schema")
            allowed = {item.name for item in ProductPreferences.__dataclass_fields__.values()}
            return ProductPreferences(**{key: value for key, value in raw.items() if key in allowed})
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            self._error = recovery_for("corrupt_local_data", detail=str(exc))
            return ProductPreferences()

    def detect_game_file(self) -> GameFileIdentity:
        contract = _load_adapter_product(self.adapter_product_path)
        preferences = self.preferences()
        candidates: list[tuple[Path, str]] = []
        configured = os.environ.get("SMB3_GAME_FILE", "").strip()
        if configured:
            candidates.append((Path(configured), "SMB3_GAME_FILE"))
        if preferences.game_file_path:
            candidates.append((Path(preferences.game_file_path), "saved local selection"))
        for value in contract.get("automatic_game_file_locations", ()):
            candidates.append((Path(str(value)), "supported local location"))
        seen: set[Path] = set()
        for candidate, source in candidates:
            expanded = candidate.expanduser()
            try:
                resolved = expanded.resolve()
            except OSError:
                resolved = expanded.absolute()
            if resolved in seen:
                continue
            seen.add(resolved)
            if not resolved.is_file():
                continue
            return self.inspect_game_file(resolved, detected_from=source)
        return GameFileIdentity(
            None,
            "automatic detection",
            False,
            False,
            False,
            None,
            "No game file selected",
            "Game Companion does not provide the game file. Choose your local Mario game file.",
        )

    def inspect_game_file(self, path: Path, *, detected_from: str) -> GameFileIdentity:
        contract = _load_adapter_product(self.adapter_product_path)
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            return GameFileIdentity(
                resolved, detected_from, False, False, False, None, resolved.name,
                "The selected game file does not exist or is not a regular file.",
            )
        try:
            with resolved.open("rb") as stream:
                header = stream.read(16)
            digest = _sha256(resolved)
        except OSError as exc:
            return GameFileIdentity(
                resolved, detected_from, True, False, False, None, resolved.name,
                f"The selected file could not be read: {exc}",
            )
        valid_container = len(header) == 16 and header[:4] == b"NES\x1a"
        supported_hashes = {str(item).lower() for item in contract.get("supported_game_sha256", ())}
        supported = valid_container and digest.lower() in supported_hashes
        reason = (
            "Mario identity verified from the local file fingerprint. The file contents were not copied."
            if supported
            else "The file has an NES container but its fingerprint is not supported by this Mario adapter."
            if valid_container
            else "The selected file is not a supported NES game container."
        )
        return GameFileIdentity(
            resolved,
            detected_from,
            True,
            valid_container,
            supported,
            digest,
            resolved.name,
            reason,
        )

    def select_game_file(self, path: Path) -> GameFileIdentity:
        identity = self.inspect_game_file(path, detected_from="manual local selection")
        if not identity.supported_identity:
            self._error = recovery_for("invalid_game_file", detail=identity.reason)
            self.record("configuration_failed", ProductStage.FIRST_USE, identity.reason)
            return identity
        preferences = self.preferences()
        preferences.game_file_path = str(identity.path)
        preferences.game_file_sha256 = identity.sha256
        preferences.updated_at = _utc_now()
        self._write_preferences(preferences)
        self._error = None
        self.record("game_identity_verified", ProductStage.FIRST_USE, identity.reason)
        return identity

    def confirm_input_ready(self, *, ready: bool, session_kind: str) -> None:
        if session_kind not in {"observe_only", "takeover_capable"}:
            raise MarioProductError("Choose Observe only or Observe with the option to allow Do later")
        if not ready:
            raise MarioProductError("Confirm the FCEUX keyboard or controller is ready before launch")
        preferences = self.preferences()
        preferences.input_ready_confirmed = True
        preferences.session_kind = session_kind
        preferences.updated_at = _utc_now()
        self._write_preferences(preferences)
        self._error = None
        self.record(
            "session_choice_selected",
            ProductStage.FIRST_USE,
            "Observe only selected."
            if session_kind == "observe_only"
            else "Observe with the option to allow Do later selected.",
        )
        self.record(
            "input_readiness_confirmed",
            ProductStage.FIRST_USE,
            "Owner confirmed the local keyboard or controller mapping is ready.",
        )
        self.record(
            "first_use_completed",
            ProductStage.IDLE,
            "Mario setup completed; no session or input authorization was restored.",
        )

    def mark_starting(self) -> None:
        self._starting = True
        self._stage_override = ProductStage.STARTING

    def mark_started(self, session_id: str | None) -> None:
        self._starting = False
        self._error = None
        self._stage_override = ProductStage.PLAYER_OBSERVING
        self.record(
            "session_started",
            ProductStage.PLAYER_OBSERVING,
            "Visible Mario session started with player input ownership.",
            session_id=session_id,
        )

    def mark_failure(self, failure_id: str, *, detail: str = "") -> RecoveryPresentation:
        self._starting = False
        self._error = recovery_for(failure_id, detail=detail)
        self.record(
            "recovery",
            ProductStage.FAILURE,
            self._error.what_happened,
            evidence_status="retained" if self._error.evidence_retained else "not_created",
            recovery=asdict(self._error),
        )
        return self._error

    def clear_error(self) -> None:
        self._error = None
        self._stage_override = ProductStage.RECOVERY

    def mark_stage(self, stage: ProductStage) -> None:
        """Track current product presentation only; never persists runtime authority."""
        self._stage_override = stage

    def first_use_state(self) -> FirstUseState:
        game = self.detect_game_file()
        emulator_path = shutil.which("fceux")
        emulator = EmulatorIdentity(
            Path(emulator_path).resolve() if emulator_path else None,
            bool(emulator_path),
            "FCEUX is available for a visible local session."
            if emulator_path
            else "FCEUX was not found. Install it locally and retry setup.",
        )
        preferences = self.preferences()
        if self._error is not None:
            status = SetupStatus.CONFIGURATION_ERROR
        elif not game.present:
            status = SetupStatus.NEEDS_GAME_FILE
        elif not game.supported_identity:
            status = SetupStatus.INVALID_GAME_FILE
        elif not emulator.available:
            status = SetupStatus.NEEDS_EMULATOR
        elif not preferences.input_ready_confirmed:
            status = SetupStatus.NEEDS_INPUT_CONFIRMATION
        else:
            status = SetupStatus.READY
        return FirstUseState(
            status,
            game,
            emulator,
            preferences.input_ready_confirmed,
            "Keyboard/controller readiness was explicitly confirmed."
            if preferences.input_ready_confirmed
            else "FCEUX accepts ordinary keyboard or controller input; confirm your local mapping is ready.",
            preferences.session_kind,
            self._error.what_happened if self._error else None,
            self._error is not None,
        )

    def view(
        self,
        snapshot: LiveObservationSnapshot,
        *,
        show_active: bool = False,
        has_compatible_profile: bool = False,
        has_accepted_reference: bool = False,
        candidate_review_available: bool = False,
    ) -> ProductSessionView:
        setup = self.first_use_state()
        derived_failure = self._error or recovery_from_snapshot(snapshot)
        capabilities = mario_capabilities(
            setup,
            snapshot,
            show_active=show_active,
            has_compatible_profile=has_compatible_profile,
            has_accepted_reference=has_accepted_reference,
            candidate_review_available=candidate_review_available,
        )
        stage = product_stage(
            setup,
            snapshot,
            show_active=show_active,
            starting=self._starting,
            failure=derived_failure,
        )
        if (
            self._stage_override is not None
            and stage in {ProductStage.IDLE, ProductStage.PLAYER_OBSERVING, ProductStage.STOPPED}
        ):
            stage = self._stage_override
        history = self.history()
        return ProductSessionView(
            PRODUCT_SCHEMA_VERSION,
            stage,
            setup,
            capabilities,
            derived_failure,
            resumable_session_id(snapshot, history),
            len(history),
            unsafe_state_restored=False,
        )

    def history(self) -> tuple[ProductHistoryEntry, ...]:
        if not self.history_path.exists():
            return ()
        entries: list[ProductHistoryEntry] = []
        try:
            for line in self.history_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entries.append(ProductHistoryEntry(**json.loads(line)))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            self._error = recovery_for("corrupt_local_data", detail=str(exc))
            return tuple(entries)
        return tuple(entries)

    def record(
        self,
        event_type: str,
        stage: ProductStage,
        detail: str,
        *,
        session_id: str | None = None,
        input_owner: str = "player",
        evidence_status: str = "implementation_event",
        recovery: Mapping[str, Any] | None = None,
    ) -> None:
        entry = ProductHistoryEntry(
            secrets.token_hex(12),
            event_type,
            stage.value,
            _utc_now(),
            session_id,
            input_owner,
            evidence_status,
            detail,
            recovery,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.history_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(entry), sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _write_preferences(self, preferences: ProductPreferences) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.preferences_path.with_suffix(f".{secrets.token_hex(4)}.tmp")
        temporary.write_text(json.dumps(asdict(preferences), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.preferences_path)


def product_stage(
    setup: FirstUseState,
    snapshot: LiveObservationSnapshot,
    *,
    show_active: bool,
    starting: bool,
    failure: RecoveryPresentation | None,
) -> ProductStage:
    if failure is not None:
        return ProductStage.FAILURE
    if not setup.launch_ready:
        return ProductStage.FIRST_USE
    if starting:
        return ProductStage.STARTING
    if snapshot.control_state == "neutralizing":
        return ProductStage.RECLAIM
    if snapshot.control_owner == "agent":
        return ProductStage.AGENT_CONTROLLING
    if snapshot.control_state == "returned":
        return ProductStage.HANDBACK
    if show_active:
        return ProductStage.SHOW_ACTIVE_SEPARATELY
    if snapshot.observation_active:
        return ProductStage.PLAYER_OBSERVING
    if snapshot.state is ConnectionState.STOPPED:
        return ProductStage.STOPPED
    return ProductStage.IDLE


def mario_capabilities(
    setup: FirstUseState,
    snapshot: LiveObservationSnapshot,
    *,
    show_active: bool,
    has_compatible_profile: bool,
    has_accepted_reference: bool,
    candidate_review_available: bool,
) -> tuple[CapabilityPresentation, ...]:
    contract = _load_adapter_product()
    declared = {str(item["id"]): item for item in contract.get("capabilities", ())}
    solutions = tuple(item for item in supported_solutions() if item.game_id == "smb3")
    scopes = tuple(sorted({scope for item in solutions if item.executable for scope in item.scopes}))
    executable_here = any(item.executable for item in solutions)
    game_ready = setup.game_file.supported_identity
    emulator_ready = setup.emulator.available
    observation_ready = snapshot.observation_active
    fresh = snapshot.freshness is Freshness.FRESH and snapshot.state is ConnectionState.CONNECTED
    takeover_path = snapshot.takeover_capable

    def capability(
        capability_id: str,
        available: bool,
        unavailable_reason: str | None,
        *,
        supported_scope: tuple[str, ...] = (),
    ) -> CapabilityPresentation:
        item = declared[capability_id]
        return CapabilityPresentation(
            capability_id,
            str(item["label"]),
            available,
            str(item["summary"]),
            None if available else unavailable_reason,
            supported_scope,
            tuple(str(value) for value in item.get("contract_references", ())),
        )

    launch_reason = (
        "Game file missing" if not game_ready else "Emulator missing" if not emulator_ready else None
    )
    observation_reason = launch_reason or "Start a visible session"
    fresh_reason = observation_reason if not observation_ready else "Observation stale or checkpoint unknown"
    takeover_reason = (
        launch_reason
        or ("Read-only session" if observation_ready and not takeover_path else None)
        or ("Observation stale or unsupported current level" if not fresh else None)
        or ("No replay-safe executable solution" if not executable_here else None)
        or ("Active Show" if show_active else None)
        or ("Active takeover" if snapshot.control_owner == "agent" else None)
    )
    return (
        capability("observation", game_ready and emulator_ready, launch_reason),
        capability("tell", fresh, fresh_reason),
        capability("coaching", fresh and has_compatible_profile, fresh_reason if not fresh else "No compatible profile"),
        capability("show", game_ready and emulator_ready and not show_active, launch_reason or "Active Show"),
        capability("dynamic_profiles", observation_ready, observation_reason),
        capability("comparison", has_compatible_profile and has_accepted_reference, "No compatible profile" if not has_compatible_profile else "No accepted reference"),
        capability("learning", observation_ready, observation_reason),
        capability("candidate_review", candidate_review_available, "Candidate not validated or no candidate needs review"),
        capability("takeover", takeover_reason is None, takeover_reason, supported_scope=scopes),
        capability("reclaim", snapshot.control_owner == "agent", "No active takeover"),
        capability("full_game_route", any(item.executable and "full_game" in item.scopes for item in solutions), "No replay-safe executable full-game solution"),
        capability("history_evidence", True, None),
    )


def recovery_for(failure_id: str, *, detail: str = "") -> RecoveryPresentation:
    definitions: dict[str, tuple[str, str, bool, str, bool, str, bool, bool]] = {
        "missing_game_file": ("Game file missing", "No supported local Mario game file was found.", False, "player", True, "Choose your local game file, then retry setup.", False, True),
        "invalid_game_file": ("Game file not supported", "The selected file did not match the supported Mario identity.", False, "player", True, "Choose the supported local game file.", False, True),
        "emulator_unavailable": ("FCEUX unavailable", "The local FCEUX executable could not be found.", False, "player", True, "Install or expose FCEUX locally, then retry setup.", False, True),
        "configuration_error": ("Setup could not continue", "A required first-use choice was missing, cancelled, or invalid.", False, "player", True, "Keep the error context visible, correct the setup choice, and retry.", True, True),
        "launch_failure": ("Mario did not start", "The visible emulator process did not reach a connected observation.", True, "player", True, "Check the retained launch error, close any orphaned duplicate only if identified, then retry.", True, True),
        "duplicate_session": ("A Mario session is already active", "Game Companion refused to start a second product session.", True, "player", True, "Return to the active session or stop its observation before retrying.", True, False),
        "observer_not_ready": ("Observer not ready", "The session started but current Mario state is not readable yet.", True, "player", True, "Keep control and wait for a fresh supported observation, or stop observation.", True, False),
        "stale_observation": ("Observation is stale", "Game Companion can no longer confirm the current state.", True, "player", True, "Keep playing or reconnect observation; Do remains unavailable.", True, True),
        "unsupported_state": ("Current state is unsupported", "The adapter cannot safely interpret this level or checkpoint.", True, "player", True, "Continue under your control until a supported checkpoint or stop observation.", True, True),
        "unknown_checkpoint": ("Checkpoint unknown", "The current checkpoint could not be verified.", True, "player", True, "Keep control and wait for a supported checkpoint.", True, True),
        "disconnection": ("Observation disconnected", "The observer connection ended unexpectedly.", True, "player", True, "Reconnect only if process identity and continuity still match; otherwise start a fresh attempt.", True, True),
        "process_lost": ("Mario process lost", "The exact observed emulator process is no longer available.", False, "player", True, "Start a fresh visible session. Prior authorization cannot be reused.", True, True),
        "controller_conflict": ("Controller ownership conflict", "Input ownership could not be proven exclusive.", True, "ambiguous", True, "Stop agent input, neutralize, and explicitly confirm player control before continuing.", True, True),
        "authorization_mismatch": ("Authorization expired or mismatched", "The authorization no longer matches the exact session, process, state, or control epoch.", True, "player", True, "Review a fresh preflight and authorize again only if desired.", True, True),
        "protected_resource_conflict": ("Protected choice would be crossed", "The selected solution conflicts with a protected resource or decision.", True, "player", True, "Change the goal or protections; Companion will not cross them.", True, True),
        "reclaim_in_progress": ("Returning control", "Companion is neutralizing input before handback.", True, "agent", False, "Wait for neutral input and confirmed player ownership; do not authorize another action.", True, False),
        "neutralization_failure": ("Input could not be confirmed neutral", "Game Companion could not prove that agent input stopped cleanly.", True, "ambiguous", False, "Stop the session and regain control directly in FCEUX before any retry.", True, True),
        "handback_failure": ("Handback not confirmed", "Agent input stopped but returned player control could not be verified.", True, "ambiguous", True, "Confirm control directly in FCEUX and start a fresh observation if needed.", True, True),
        "incompatible_reference": ("Comparison unavailable", "No accepted compatible reference matches the current profile and timing boundary.", True, "player", True, "Continue without comparison or choose a compatible profile.", True, False),
        "candidate_not_executable": ("Candidate cannot play", "The reviewed candidate has not passed replay-safe promotion.", True, "player", True, "Review or validate it later; choose an accepted executable solution for Do.", True, False),
        "corrupt_local_data": ("Local history needs recovery", "A local event or derived index could not be read safely.", False, "player", True, "Retain raw data and explicitly rebuild only the affected derived index.", True, True),
        "scenario_evidence_mismatch": ("Evidence did not reconcile", "Scenario identity, artifacts, or classifications did not match the manifest.", False, "player", True, "Retain the failed attempt and report the first unmet requirement before a fresh retry.", True, True),
    }
    selected = definitions.get(failure_id, ("Mario session needs attention", "The product state could not be verified.", True, "unknown", True, "Stop unsafe actions and return to a known player-owned state.", True, True))
    happened = selected[1] + (f" {detail}" if detail else "")
    return RecoveryPresentation(failure_id, selected[0], happened, *selected[2:])


def recovery_from_snapshot(
    snapshot: LiveObservationSnapshot,
) -> RecoveryPresentation | None:
    if snapshot.control_state == "neutralizing":
        return recovery_for("reclaim_in_progress", detail=snapshot.reason)
    if snapshot.state is ConnectionState.DISCONNECTED:
        return recovery_for(
            "process_lost" if snapshot.process_alive is False else "disconnection",
            detail=snapshot.reason,
        )
    if snapshot.state is ConnectionState.STALE:
        return recovery_for("stale_observation", detail=snapshot.reason)
    if snapshot.state is ConnectionState.UNSUPPORTED:
        return recovery_for("unsupported_state", detail=snapshot.reason)
    if snapshot.state is ConnectionState.UNKNOWN and snapshot.session_id is not None:
        return recovery_for("unknown_checkpoint", detail=snapshot.reason)
    if snapshot.takeover_terminal_reason == "ownership_conflict":
        return recovery_for("controller_conflict", detail=snapshot.reason)
    if snapshot.takeover_terminal_reason == "process_loss":
        return recovery_for("process_lost", detail=snapshot.reason)
    return None


def resumable_session_id(
    snapshot: LiveObservationSnapshot,
    history: Iterable[ProductHistoryEntry],
) -> str | None:
    if not snapshot.observation_active or snapshot.session_id is None:
        return None
    if snapshot.state not in {ConnectionState.CONNECTED, ConnectionState.STALE}:
        return None
    if snapshot.control_owner != "player":
        return None
    if any(item.session_id == snapshot.session_id for item in history):
        return snapshot.session_id
    return None


def load_owner_pilot_manifest(path: Path = PILOT_MANIFEST_PATH) -> Mapping[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise MarioProductError(f"Mario owner-pilot manifest is unavailable: {exc}") from exc
    if not isinstance(payload, Mapping) or payload.get("schema_version") != "game-companion-mario-owner-pilot/v1":
        raise MarioProductError("Mario owner-pilot manifest has an unsupported schema")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
