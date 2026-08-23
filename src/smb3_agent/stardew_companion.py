from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping

from smb3_agent.companion_session import (
    CompanionObservationEnvelope,
    Freshness,
    ModeCapability,
    Observation,
    ObservationSource,
)
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
from smb3_agent.stardew_adapter import (
    DisposableSaveManager,
    FailureCode,
    InputCommand,
    InputKind,
    InputOwner,
    OperatorLifecycle,
    OrdinaryInputDriver,
    SaveIdentity,
    ScreenObservation,
    StardewAdapterError,
    StardewOperator,
    OperatorView,
    WateringLedger,
    WindowObservation,
    load_stardew_contract,
)
from smb3_agent.tell import (
    GroundedText,
    ProvenanceReference,
    SpoilerLevel,
    TellCard,
    TellStep,
)


STARDEW_COMPANION_VERSION = "stardew-companion/v1"
STARDEW_ADAPTER_ID = "stardew"
STARDEW_GAME_ID = "stardew_valley"
STARDEW_TASK_ID = "water_initial_crops_and_return"
STARDEW_STOP_POINT = (
    "all initially observed planted crops are watered and the farmhouse entrance is visible"
)
STARDEW_STOP_CONDITIONS = (
    "completion",
    "reclaim",
    "timeout",
    "failure",
    "ambiguity",
    "process_or_window_loss",
    "save_mismatch",
    "protected_action_risk",
)


class StardewCatalogProvider:
    """Stardew-owned catalog declaration and switch hooks."""

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
                "Select an owner-provided primary save, create a verified disposable copy, and establish a visible window.",
                "unconfigured",
            )
        )
        self._runtime = runtime or (lambda: AdapterRuntimeState(adapter_id=STARDEW_ADAPTER_ID))
        self._retain = retain or (lambda: True)
        self._invalidate = invalidate or (lambda: True)

    def catalog_entry(self) -> AdapterCatalogEntry:
        contract = load_stardew_contract()
        if contract.get("adapter_id") != STARDEW_ADAPTER_ID or contract.get("game_id") != STARDEW_GAME_ID:
            raise CompanionCatalogError("Stardew catalog/provider identity disagreement")
        if contract.get("adapter_version") != STARDEW_COMPANION_VERSION:
            raise CompanionCatalogError("Stardew catalog/provider version disagreement")
        availability, reason, setup = self._availability()
        profile = CatalogProfile(
            "stardew.initial-crops.exact-watering",
            "Exact initial-crop watering",
            "bounded_task",
            "Water the frozen initial planted set and return to the visibly confirmed farmhouse entrance.",
        )
        return AdapterCatalogEntry(
            adapter_id=STARDEW_ADAPTER_ID,
            game_id=STARDEW_GAME_ID,
            display_name="Stardew Valley",
            description="Screen-only companion for one bounded crop-watering task on a verified disposable save copy.",
            adapter_version=STARDEW_COMPANION_VERSION,
            implementation_status="V2.11 implementation complete; final validation deferred",
            availability=availability,
            availability_reason=reason,
            setup_state=setup,
            observation=CatalogObservation(
                "visible_screen_only",
                "Visible screen observation",
                "No process memory, hidden game API, save parsing as live truth, or invisible automation; exact crop, resource, position, save, process, and window continuity are required.",
            ),
            capabilities=(
                CatalogCapability("tell", "Tell", "implementation_validation_deferred", "Provenance-grounded next action for the exact visible watering ledger.", "Fresh exact screen observation and final campaign validation are required."),
                CatalogCapability("show", "Show", "implementation_validation_deferred", "One fresh-copy watering demonstration; always review only.", "Fresh disposable copy, exact observation, and final campaign validation are required."),
                CatalogCapability("do", "Do", "implementation_validation_deferred", "One same-session watering authorization using ordinary visible input.", "Fresh exact observation, copied-save continuity, explicit owner authority, and final campaign validation are required."),
            ),
            goals=(
                CatalogGoal(STARDEW_TASK_ID, "Water initial crops and return", "Water every crop in the frozen initial set and visibly return to the farmhouse entrance.", (profile.profile_id,)),
            ),
            profiles=(profile,),
            scopes=(
                CatalogScope("bounded_watering_task", "One exact watering task", STARDEW_STOP_CONDITIONS),
            ),
            safety=CatalogSafety(
                "Disposable-copy only, visible screen truth, ordinary input, exact reconciliation, immediate reclaim, and neutral player handback.",
                ("No primary-save writes", "No purchases, sales, discards, gifts, or consequential dialogue", "No story choices or sleep", "No unknown refill location"),
                "Stop on completion, reclaim, timeout, ambiguity, protected action, continuity loss, save mismatch, or missing evidence.",
                "Reclaim neutralizes the configured driver first and invalidates volatile authority.",
                "Player ownership and neutral input must be visibly reported before another mode or adapter is enabled.",
            ),
            evidence=CatalogEvidence(
                "stardew",
                ("review_only", "technical", "owner_feedback", "authoritative_gameplay"),
                "Stardew screen, save-copy, watering-ledger, and outcome evidence remains Stardew-owned and cannot satisfy Mario contracts.",
            ),
            standalone_surface="/stardew",
            recovery_guidance="Preserve the prior attempt, reverify the primary, create a fresh destination when reset is needed, and establish a new observation and authorization.",
        )

    def runtime_state(self) -> AdapterRuntimeState:
        state = self._runtime()
        if state.adapter_id != STARDEW_ADAPTER_ID:
            raise CompanionCatalogError("Stardew runtime identity disagreement")
        return state

    def retain_for_switch(self) -> bool:
        return self._retain()

    def invalidate_volatile_state(self) -> bool:
        return self._invalidate()


class StardewCompanionError(StardewAdapterError):
    """A Stardew companion-mode contract failed closed."""


class StardewMode(str, Enum):
    OBSERVE = "observe"
    TELL = "tell"
    SHOW = "show"
    DO = "do"


class StardewAttemptStatus(str, Enum):
    READY = "ready"
    ACTIVE = "active"
    STOPPED = "stopped"
    RECLAIMED = "reclaimed"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALIDATED_BY_RESET = "invalidated_by_reset"


@dataclass(frozen=True)
class StardewAuthorization:
    authorization_id: str
    epoch_id: str
    mode: StardewMode
    task_id: str
    copied_save_sha256: str
    copied_save_nonce: str
    process_id: int
    process_started_at: str
    window_id: str
    observation_id: str
    expires_at: str
    input_driver: InputKind
    stop_point: str
    stop_conditions: tuple[str, ...]


@dataclass(frozen=True)
class ActorInputRecord:
    actor: str
    epoch_id: str
    command: InputCommand
    before_observation_id: str
    after_observation_id: str
    recorded_at: str


@dataclass
class StardewModeAttempt:
    attempt_id: str
    mode: StardewMode
    save_identity: SaveIdentity
    review_only: bool
    player_completion: bool = False
    authoritative_evidence: bool = False
    owner_acceptance: bool = False
    status: StardewAttemptStatus = StardewAttemptStatus.READY
    before_observation: ScreenObservation | None = None
    after_observations: list[ScreenObservation] = field(default_factory=list)
    inputs: list[ActorInputRecord] = field(default_factory=list)
    stop_reason: str | None = None
    first_unmet_requirement: str | None = None
    input_neutralized: bool = True
    player_ownership_restored: bool = True
    primary_save_unchanged: bool | None = None
    evidence_hashes: dict[str, str] = field(default_factory=dict)
    reset_status: str = "not_requested"
    invalidated_by_reset: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _window_matches(left: WindowObservation, right: WindowObservation) -> bool:
    return (
        left.process_id == right.process_id
        and left.process_started_at == right.process_started_at
        and left.window_id == right.window_id
    )


def convert_stardew_observation(
    screen: ScreenObservation,
    save: SaveIdentity,
    *,
    input_owner: InputOwner,
    expected_window: WindowObservation | None = None,
    ledger: WateringLedger | None = None,
) -> CompanionObservationEnvelope:
    """Convert screen-only Stardew state without adding Stardew fields to Mario records."""
    stale: list[str] = []
    try:
        screen.validate(save.disposable_tree_sha256)
    except StardewAdapterError as exc:
        stale.append(str(exc))
    if not save.valid:
        stale.append(FailureCode.SAVE_MISMATCH.value)
    if expected_window is not None and not _window_matches(screen.window, expected_window):
        stale.append(FailureCode.PROCESS_LOSS.value)
    if input_owner in {InputOwner.AMBIGUOUS, InputOwner.NONE}:
        stale.append(FailureCode.AMBIGUOUS_OWNERSHIP.value)
    try:
        observed_at = datetime.fromisoformat(screen.observed_at)
        if observed_at.tzinfo is None:
            raise ValueError
    except ValueError:
        observed_at = None
        stale.append("invalid_observation_time")

    crop_confidence = min((crop.confidence for crop in screen.crops), default=1.0)
    confidence = min(crop_confidence, screen.position.confidence)
    if screen.energy is None or not screen.tool.exact:
        confidence = 0.0
    planted = tuple(crop for crop in screen.crops if crop.planted)
    if ledger is not None:
        current_ids = {crop.crop_id for crop in planted}
        watered_ids = {crop.crop_id for crop in planted if crop.watered}
        if current_ids != set(ledger.initial_crop_ids):
            stale.append(FailureCode.ACCOUNTING_MISMATCH.value)
        if not ledger.confirmed_watered_ids.issubset(watered_ids):
            stale.append(FailureCode.ACCOUNTING_MISMATCH.value)
        if screen.tool.tool_uses < ledger.tool_uses or screen.tool.refill_count < ledger.refills:
            stale.append(FailureCode.ACCOUNTING_MISMATCH.value)
        if ledger.energy_start is not None and screen.energy is not None and screen.energy > ledger.energy_start:
            stale.append(FailureCode.ACCOUNTING_MISMATCH.value)
    freshness = Freshness.STALE if stale else Freshness.FRESH
    active_ledger = ledger
    if active_ledger is None and not stale:
        active_ledger = WateringLedger.from_observation(screen)
    facts = {
        "save_copy_identity": save,
        "process_start_identity": screen.window.process_started_at,
        "window_identity": screen.window,
        "screenshot_evidence": screen.screenshot_references,
        "crop_observations": planted,
        "crop_ledger": active_ledger,
        "energy": screen.energy,
        "energy_maximum": screen.energy_maximum,
        "tool": screen.tool,
        "position": screen.position,
        "input_owner": input_owner.value,
        "scene_complete": screen.scene_complete,
        "unknown_regions": screen.unknown_regions,
    }
    crop_refs = tuple(crop.evidence_reference for crop in planted)
    screenshot_refs = tuple(screen.screenshot_references)
    retained_refs = screenshot_refs or ("missing_screen_evidence",)
    retained_crop_refs = crop_refs or retained_refs
    envelope = CompanionObservationEnvelope(
        observation=Observation(
            checkpoint="Stardew farm watering task",
            checkpoint_id=STARDEW_TASK_ID,
            observed_at=observed_at,
            freshness=freshness,
            confidence=confidence,
            evidence_references=screenshot_refs,
            source=ObservationSource.ADAPTER,
            game_id=STARDEW_GAME_ID,
        ),
        adapter_id=STARDEW_ADAPTER_ID,
        session_identity={
            "save_copy_sha256": save.disposable_tree_sha256,
            "save_copy_nonce": save.nonce,
            "process_id": str(screen.window.process_id or ""),
            "process_started_at": str(screen.window.process_started_at or ""),
            "window_id": str(screen.window.window_id or ""),
            "observation_id": screen.observation_id,
        },
        facts=facts,
        fact_provenance={
            "save_copy_identity": retained_refs,
            "process_start_identity": retained_refs,
            "window_identity": retained_refs,
            "screenshot_evidence": retained_refs,
            "crop_observations": retained_crop_refs,
            "crop_ledger": retained_crop_refs,
            "energy": retained_refs,
            "energy_maximum": retained_refs,
            "tool": retained_refs,
            "position": retained_refs,
            "input_owner": retained_refs,
            "scene_complete": retained_refs,
            "unknown_regions": retained_refs,
        },
        input_owner=input_owner.value,
        stale_reasons=tuple(dict.fromkeys(stale)),
    )
    envelope.validate()
    return envelope


class StardewSafetyPolicy:
    """Adapter-owned watering purposes and protected-action policy."""

    def __init__(self, contract: Mapping[str, object] | None = None) -> None:
        self.contract = contract or load_stardew_contract()
        self.allowed_purposes = {
            "navigate", "select_watering_can", "water_crop", "refill",
            "return_to_entrance", "neutralize",
        }
        self.protected_terms = tuple(
            str(item).lower() for item in self.contract.get("protected_action_terms", ())
        )
        self.refill_locations = tuple(
            str(item) for item in self.contract.get("refill_locations", ())
        )

    def first_refusal(
        self, command: InputCommand, observation: ScreenObservation
    ) -> str | None:
        normalized = f"{command.control} {command.action} {command.purpose}".lower()
        if command.purpose not in self.allowed_purposes:
            return f"input purpose is outside the watering task: {command.purpose}"
        matched = next((term for term in self.protected_terms if term in normalized), None)
        if matched:
            return f"protected action refused: {matched}"
        if command.purpose == "refill" and observation.position.location not in self.refill_locations:
            return "safe refill location is not visibly confirmed"
        return None


class StardewCompanionProvider:
    """Standalone Stardew Observe/Tell/Show/Do provider above the V2.10 operator."""

    def __init__(self, contract: Mapping[str, object] | None = None) -> None:
        self.contract = contract or load_stardew_contract()
        self.safety = StardewSafetyPolicy(self.contract)

    def observe(
        self,
        screen: ScreenObservation,
        save: SaveIdentity,
        *,
        input_owner: InputOwner,
        expected_window: WindowObservation | None = None,
        ledger: WateringLedger | None = None,
    ) -> CompanionObservationEnvelope:
        return convert_stardew_observation(
            screen,
            save,
            input_owner=input_owner,
            expected_window=expected_window,
            ledger=ledger,
        )

    def mode_capabilities(
        self, observation: CompanionObservationEnvelope | None
    ) -> tuple[ModeCapability, ...]:
        available = bool(
            observation
            and observation.trusted
            and observation.observation.confidence == 1.0
        )
        reason = (
            "Fresh exact screen observation and retained evidence are available."
            if available
            else "Fresh exact screen observation, copied-save continuity, and retained evidence are required."
        )
        return tuple(
            ModeCapability(
                mode,
                available,
                reason,
                None if available else reason,
            )
            for mode in ("tell", "show", "do")
        )

    def tell(
        self,
        observation: CompanionObservationEnvelope,
        *,
        spoiler_level: SpoilerLevel = SpoilerLevel.GUIDED,
    ) -> TellCard:
        if not observation.trusted or observation.observation.confidence != 1.0:
            first = observation.stale_reasons[0] if observation.stale_reasons else "unknown state"
            raise StardewCompanionError(f"Tell disabled: {first}")
        screen = observation.facts.get("window_identity")
        ledger = observation.facts.get("crop_ledger")
        crops = observation.facts.get("crop_observations")
        tool = observation.facts.get("tool")
        position = observation.facts.get("position")
        if not isinstance(screen, WindowObservation) or not isinstance(ledger, WateringLedger):
            raise StardewCompanionError("Tell disabled: exact Stardew observation facts are missing")
        if not isinstance(crops, tuple) or tool is None or position is None:
            raise StardewCompanionError("Tell disabled: crop, resource, or position state is unknown")

        screen_ref = ProvenanceReference(
            "adapter_observation",
            observation.session_identity["observation_id"],
            "Retained Stardew screen observation",
        )
        ledger_ref = ProvenanceReference(
            "watering_ledger", ledger.task_id, "Exact initial-crop watering ledger"
        )
        safety_ref = ProvenanceReference(
            "adapter_safety_policy", STARDEW_COMPANION_VERSION, "Stardew watering safety policy"
        )
        screen_and_ledger = (screen_ref, ledger_ref)
        steps: list[TellStep] = []
        risks: list[GroundedText] = []
        remaining = tuple(
            crop for crop in crops
            if crop.crop_id in ledger.initial_crop_ids and crop.crop_id not in ledger.confirmed_watered_ids
        )
        if remaining:
            next_crop = sorted(remaining, key=lambda crop: (crop.tile_y, crop.tile_x, crop.crop_id))[0]
            if tool.selected_tool != "watering_can":
                steps.append(TellStep(
                    GroundedText("Select the watering can.", (screen_ref,)),
                    GroundedText("The watering can is visibly selected.", (screen_ref,)),
                ))
            elif tool.watering_can_units == 0:
                if position.location in self.safety.refill_locations:
                    steps.append(TellStep(
                        GroundedText("Refill only at the visibly confirmed safe farm water location.", (screen_ref, safety_ref)),
                        GroundedText("The can is visibly full and the refill ledger advances once.", screen_and_ledger),
                    ))
                else:
                    steps.append(TellStep(
                        GroundedText("Stop; a safe refill location is not visibly confirmed.", (screen_ref, safety_ref)),
                        GroundedText("No input is sent and player ownership remains active.", (safety_ref,)),
                    ))
            else:
                steps.append(TellStep(
                    GroundedText(
                        f"Water the next confirmed unwatered crop at tile ({next_crop.tile_x}, {next_crop.tile_y}).",
                        screen_and_ledger,
                    ),
                    GroundedText(
                        f"Crop {next_crop.crop_id} is visibly watered before the ledger advances.",
                        screen_and_ledger,
                    ),
                ))
        elif not ledger.complete:
            steps.append(TellStep(
                GroundedText("Return to the visibly confirmed farmhouse entrance.", screen_and_ledger),
                GroundedText("The exact position observation confirms the farmhouse entrance.", (screen_ref,)),
            ))
        else:
            steps.append(TellStep(
                GroundedText("Stop and keep input neutral; the exact bounded task is reconciled.", (ledger_ref, safety_ref)),
                GroundedText("Player ownership is visibly reported after neutral handback.", (safety_ref,)),
            ))
        risks.append(GroundedText(
            "Stop on uncertainty, protected-action risk, crop mismatch, resource ambiguity, or save/process/window/evidence loss.",
            (safety_ref,),
        ))
        if spoiler_level is SpoilerLevel.MINIMAL:
            risks = []
        card = TellCard(
            state_summary=GroundedText(
                f"{ledger.remaining_count} initially planted crop(s) remain; energy {observation.facts['energy']}; can {tool.watering_can_units}/{tool.watering_can_capacity}.",
                screen_and_ledger,
            ),
            observation_source=ObservationSource.ADAPTER,
            objective=GroundedText(
                "Water the exact initial crop set, then return to the farmhouse entrance.",
                (ledger_ref,),
            ),
            steps=tuple(steps[:1] if spoiler_level is SpoilerLevel.MINIMAL else steps),
            risks=tuple(risks),
            recovery=(GroundedText(
                "Neutralize input, restore player ownership, retain the attempt, and start fresh after re-observation.",
                (safety_ref,),
            ),) if spoiler_level is not SpoilerLevel.MINIMAL else (),
            spoiler_level=spoiler_level,
            protected_decisions_honored=tuple(self.safety.protected_terms),
            uncertainty=GroundedText(
                "No action or completion is inferred beyond the current visible reconciliation.",
                (screen_ref, ledger_ref),
            ),
            refresh_requirement=GroundedText(
                "Refresh after every input and whenever the save, process, window, crop coverage, resources, or evidence changes.",
                (screen_ref, safety_ref),
            ),
        )
        card.validate()
        return card


class StardewCompanionController:
    """Fail-closed lifecycle for one standalone Stardew companion session."""

    def __init__(
        self,
        save: SaveIdentity,
        *,
        manager: DisposableSaveManager | None = None,
        provider: StardewCompanionProvider | None = None,
    ) -> None:
        self.manager = manager or DisposableSaveManager()
        self.provider = provider or StardewCompanionProvider()
        self.operator = StardewOperator(save)
        self.authorization: StardewAuthorization | None = None
        self.active_attempt: StardewModeAttempt | None = None
        self.attempts: list[StardewModeAttempt] = []
        self.last_tell_card: TellCard | None = None
        self.reset_status = "not_requested"
        self._used_copy_nonces: set[str] = set()

    @property
    def save(self) -> SaveIdentity:
        return self.operator.save

    def observe(self, screen: ScreenObservation) -> CompanionObservationEnvelope:
        envelope = self.provider.observe(
            screen,
            self.save,
            input_owner=self.operator.owner,
            expected_window=self.operator.window,
            ledger=self.operator.ledger,
        )
        if envelope.trusted:
            if self.operator.window is None:
                self.operator.attach_player_owned(screen)
            else:
                self.operator.observation = screen
        return envelope

    def tell(self, screen: ScreenObservation) -> TellCard:
        envelope = self.observe(screen)
        if self.operator.ledger is None:
            self.operator.establish_task(screen)
            envelope = self.provider.observe(
                screen,
                self.save,
                input_owner=self.operator.owner,
                expected_window=self.operator.window,
                ledger=self.operator.ledger,
            )
        self.last_tell_card = self.provider.tell(envelope)
        return self.last_tell_card

    def view(self) -> OperatorView:
        base = self.operator.view()
        mode = self.active_attempt.mode.value.title() if self.active_attempt else "Observe"
        show_status = (
            self.active_attempt.status.value
            if self.active_attempt and self.active_attempt.mode is StardewMode.SHOW
            else "not_started"
        )
        return replace(
            base,
            current_mode=mode,
            tell_card=self.last_tell_card,
            show_status=show_status,
            do_authorization_scope=(self.authorization.task_id if self.authorization else None),
            do_authorization_expiry=(self.authorization.expires_at if self.authorization else None),
            reset_status=self.reset_status,
        )

    def start_show(
        self,
        screen: ScreenObservation,
        *,
        input_driver: InputKind,
        expires_at: str,
    ) -> StardewModeAttempt:
        if self.save.nonce in self._used_copy_nonces:
            raise StardewCompanionError("Show requires a fresh disposable copy and attempt identity")
        attempt = self._start(StardewMode.SHOW, screen, input_driver, expires_at)
        attempt.review_only = True
        self._used_copy_nonces.add(self.save.nonce)
        return attempt

    def authorize_do(
        self,
        screen: ScreenObservation,
        *,
        owner_confirmation: bool,
        input_driver: InputKind,
        expires_at: str,
    ) -> StardewAuthorization:
        if not owner_confirmation:
            raise StardewCompanionError("Do requires explicit owner authorization")
        self._start(StardewMode.DO, screen, input_driver, expires_at)
        assert self.authorization is not None
        return self.authorization

    def _start(
        self,
        mode: StardewMode,
        screen: ScreenObservation,
        input_driver: InputKind,
        expires_at: str,
    ) -> StardewModeAttempt:
        if self.active_attempt and self.active_attempt.status is StardewAttemptStatus.ACTIVE:
            raise StardewCompanionError("another Stardew companion mode is already active")
        envelope = self.observe(screen)
        if not envelope.trusted:
            raise StardewCompanionError(
                f"{mode.value} requires a fresh exact observation: {envelope.stale_reasons[0]}"
            )
        if self.operator.owner is not InputOwner.PLAYER:
            raise StardewCompanionError(FailureCode.AMBIGUOUS_OWNERSHIP.value)
        if self.operator.ledger is None:
            self.operator.establish_task(screen)
        epoch = self.operator.authorize_agent(
            expires_at=expires_at,
            owner_confirmation=True,
            input_driver=input_driver.value,
            stop_conditions=STARDEW_STOP_CONDITIONS,
        )
        assert screen.window.process_id is not None
        assert screen.window.process_started_at is not None
        assert screen.window.window_id is not None
        self.authorization = StardewAuthorization(
            authorization_id=secrets.token_hex(16),
            epoch_id=epoch.epoch_id,
            mode=mode,
            task_id=epoch.task_id,
            copied_save_sha256=self.save.disposable_tree_sha256,
            copied_save_nonce=self.save.nonce,
            process_id=screen.window.process_id,
            process_started_at=screen.window.process_started_at,
            window_id=screen.window.window_id,
            observation_id=screen.observation_id,
            expires_at=expires_at,
            input_driver=input_driver,
            stop_point=STARDEW_STOP_POINT,
            stop_conditions=STARDEW_STOP_CONDITIONS,
        )
        attempt = StardewModeAttempt(
            attempt_id=f"stardew-{mode.value}-{secrets.token_hex(8)}",
            mode=mode,
            save_identity=self.save,
            review_only=mode is StardewMode.SHOW,
            status=StardewAttemptStatus.ACTIVE,
            before_observation=screen,
            input_neutralized=True,
            player_ownership_restored=False,
        )
        self.active_attempt = attempt
        self.attempts.append(attempt)
        return attempt

    def perform_input(
        self,
        command: InputCommand,
        current: ScreenObservation,
        driver: OrdinaryInputDriver,
        observe_after: Callable[[], ScreenObservation],
    ) -> ScreenObservation:
        attempt = self._require_active()
        authorization: StardewAuthorization | None = None
        input_sent = False
        input_recorded = False
        try:
            authorization = self._require_authorization(current, command.kind, driver)
            refusal = self.provider.safety.first_refusal(command, current)
            if refusal:
                raise StardewCompanionError(refusal)
            self.operator.send_input(command, current, driver)
            input_sent = True
            driver.neutralize()
            self.operator.input_neutralized = True
            after = observe_after()
            if after.observation_id == current.observation_id:
                raise StardewCompanionError("fresh post-input screen observation is required")
            attempt.inputs.append(ActorInputRecord(
                actor="agent",
                epoch_id=authorization.epoch_id,
                command=command,
                before_observation_id=current.observation_id,
                after_observation_id=after.observation_id,
                recorded_at=_now(),
            ))
            input_recorded = True
            attempt.after_observations.append(after)
            envelope = self.provider.observe(
                after,
                self.save,
                input_owner=InputOwner.AGENT,
                expected_window=current.window,
                ledger=self.operator.ledger,
            )
            if not envelope.trusted:
                raise StardewCompanionError(envelope.stale_reasons[0])
            self._verify_postcondition(command, current, after)
            self.operator.record_post_input(after)
            attempt.input_neutralized = True
            return after
        except Exception as exc:
            if input_sent and not input_recorded:
                attempt.inputs.append(ActorInputRecord(
                    actor="agent",
                    epoch_id=authorization.epoch_id if authorization else "invalidated",
                    command=command,
                    before_observation_id=current.observation_id,
                    after_observation_id="missing_or_unverified",
                    recorded_at=_now(),
                ))
            if attempt.status is StardewAttemptStatus.ACTIVE:
                code = (
                    FailureCode.PROTECTED_ACTION_RISK
                    if "protected action" in str(exc) or "watering task" in str(exc)
                    else self._failure_code(exc)
                )
                self._fail(code, str(exc), driver)
            raise

    def reclaim(self, driver: OrdinaryInputDriver, *, reason: str = "player reclaim") -> StardewModeAttempt:
        attempt = self._require_active()
        neutralized = self.operator.reclaim(driver)
        self.authorization = None
        attempt.status = StardewAttemptStatus.RECLAIMED if neutralized else StardewAttemptStatus.FAILED
        attempt.stop_reason = reason if neutralized else "input neutralization could not be verified"
        attempt.first_unmet_requirement = None if neutralized else attempt.stop_reason
        attempt.input_neutralized = neutralized
        attempt.player_ownership_restored = neutralized
        return attempt

    def stop_active(
        self,
        driver: OrdinaryInputDriver,
        *,
        reason: str,
        failure_code: FailureCode | None = None,
    ) -> StardewModeAttempt:
        """Neutral terminal path for cancellation, timeout, loss, or ambiguity."""
        if failure_code is not None:
            return self._fail(failure_code, reason, driver)
        attempt = self._require_active()
        neutralized = self.operator.reclaim(driver)
        self.authorization = None
        attempt.status = StardewAttemptStatus.STOPPED if neutralized else StardewAttemptStatus.FAILED
        attempt.stop_reason = reason if neutralized else "input neutralization could not be verified"
        attempt.first_unmet_requirement = None if neutralized else attempt.stop_reason
        attempt.input_neutralized = neutralized
        attempt.player_ownership_restored = neutralized
        return attempt

    def complete(
        self,
        final_observation: ScreenObservation,
        driver: OrdinaryInputDriver,
        *,
        evidence_root: Path,
        required_evidence: tuple[str, ...],
    ) -> StardewModeAttempt:
        attempt = self._require_active()
        envelope = self.provider.observe(
            final_observation,
            self.save,
            input_owner=InputOwner.AGENT,
            expected_window=self.operator.window,
            ledger=self.operator.ledger,
        )
        if not envelope.trusted:
            return self._fail(self._failure_code_from_reason(envelope.stale_reasons[0]), envelope.stale_reasons[0], driver)
        if self.operator.ledger is None:
            return self._fail(FailureCode.ACCOUNTING_MISMATCH, "watering ledger is missing", driver)
        try:
            if self.operator.observation is None or self.operator.observation.observation_id != final_observation.observation_id:
                if self.operator.observation is None or not self._same_task_state(
                    self.operator.observation, final_observation
                ):
                    return self._fail(
                        FailureCode.ACCOUNTING_MISMATCH,
                        "final state changed without an actor-labeled input and fresh postcondition",
                        driver,
                    )
                self.operator.record_post_input(final_observation)
        except StardewAdapterError as exc:
            return self._fail(self._failure_code(exc), str(exc), driver)
        if not self.operator.ledger.complete:
            return self._fail(FailureCode.ACCOUNTING_MISMATCH, "initial crop set, resources, or farmhouse entrance is not exactly reconciled", driver)
        try:
            primary_unchanged = self.manager.verify_primary_unchanged(self.save)
        except StardewAdapterError:
            primary_unchanged = False
        if not primary_unchanged:
            return self._fail(FailureCode.PRIMARY_SAVE_RISK, "primary save changed", driver)
        try:
            attempt.evidence_hashes = _hash_required_evidence(evidence_root, required_evidence)
        except StardewCompanionError as exc:
            return self._fail(FailureCode.MISSING_EVIDENCE, str(exc), driver)
        if not self.operator.reclaim(driver):
            attempt.status = StardewAttemptStatus.FAILED
            attempt.stop_reason = "input neutralization could not be verified"
            attempt.first_unmet_requirement = attempt.stop_reason
            attempt.input_neutralized = False
            attempt.player_ownership_restored = False
            self.authorization = None
            return attempt
        self.operator.lifecycle = OperatorLifecycle.COMPLETED
        self.authorization = None
        if (
            not attempt.after_observations
            or attempt.after_observations[-1].observation_id != final_observation.observation_id
        ):
            attempt.after_observations.append(final_observation)
        attempt.status = StardewAttemptStatus.COMPLETED
        attempt.stop_reason = "exact bounded task completed"
        attempt.input_neutralized = True
        attempt.player_ownership_restored = True
        attempt.primary_save_unchanged = True
        attempt.player_completion = False
        attempt.authoritative_evidence = False
        attempt.owner_acceptance = False
        return attempt

    def reset_disposable(
        self,
        fresh_destination: Path,
        *,
        driver: OrdinaryInputDriver | None = None,
    ) -> SaveIdentity:
        previous = self.save
        if self.active_attempt and self.active_attempt.status is StardewAttemptStatus.ACTIVE:
            if driver is None:
                raise StardewCompanionError("active reset requires input neutralization")
            if not self.operator.reclaim(driver):
                self.active_attempt.status = StardewAttemptStatus.FAILED
                self.active_attempt.stop_reason = "input neutralization could not be verified"
                self.active_attempt.first_unmet_requirement = self.active_attempt.stop_reason
                self.active_attempt.input_neutralized = False
                self.active_attempt.player_ownership_restored = False
                self.authorization = None
                raise StardewCompanionError(self.active_attempt.stop_reason)
            self.active_attempt.status = StardewAttemptStatus.INVALIDATED_BY_RESET
            self.active_attempt.stop_reason = "disposable copy reset"
            self.active_attempt.input_neutralized = True
            self.active_attempt.player_ownership_restored = True
            self.active_attempt.reset_status = "invalidated_preserved"
        for attempt in self.attempts:
            attempt.invalidated_by_reset = True
            if attempt.reset_status == "not_requested":
                attempt.reset_status = "invalidated_preserved"
        self.authorization = None
        self.last_tell_card = None
        self.operator.epoch = None
        self.operator.observation = None
        self.operator.ledger = None
        self.operator.window = None
        self.operator.owner = InputOwner.PLAYER
        self.operator.lifecycle = OperatorLifecycle.COPY_READY
        try:
            replacement = self.manager.reset(previous, fresh_destination)
        except StardewAdapterError:
            self.reset_status = "failed_prior_attempt_preserved_all_mode_state_invalidated"
            raise
        self.operator = StardewOperator(replacement)
        self.active_attempt = None
        self.reset_status = "fresh_attempt_ready_previous_attempt_preserved"
        return replacement

    def _require_active(self) -> StardewModeAttempt:
        if self.active_attempt is None or self.active_attempt.status is not StardewAttemptStatus.ACTIVE:
            raise StardewCompanionError("no active Stardew Show or Do attempt")
        return self.active_attempt

    def _require_authorization(
        self,
        current: ScreenObservation,
        input_kind: InputKind,
        driver: OrdinaryInputDriver,
    ) -> StardewAuthorization:
        authorization = self.authorization
        if authorization is None or self.operator.epoch is None:
            raise StardewCompanionError("authority is missing or invalidated")
        try:
            expiry = datetime.fromisoformat(authorization.expires_at)
        except ValueError as exc:
            raise StardewCompanionError("authorization expiry is invalid") from exc
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise StardewCompanionError("authorization expired")
        if not driver.available(input_kind) or input_kind is not authorization.input_driver:
            raise StardewCompanionError("authorized ordinary input driver is unavailable or changed")
        if (
            authorization.task_id != (self.operator.ledger.task_id if self.operator.ledger else None)
            or authorization.copied_save_sha256 != self.save.disposable_tree_sha256
            or authorization.copied_save_nonce != self.save.nonce
            or authorization.process_id != current.window.process_id
            or authorization.process_started_at != current.window.process_started_at
            or authorization.window_id != current.window.window_id
            or self.operator.observation is None
            or self.operator.observation.observation_id != current.observation_id
        ):
            raise StardewCompanionError("authorization no longer matches the live observation")
        current.validate(self.save.disposable_tree_sha256)
        return authorization

    @staticmethod
    def _verify_postcondition(
        command: InputCommand,
        before: ScreenObservation,
        after: ScreenObservation,
    ) -> None:
        before_watered = {crop.crop_id for crop in before.crops if crop.planted and crop.watered}
        after_watered = {crop.crop_id for crop in after.crops if crop.planted and crop.watered}
        crop_state_unchanged = before_watered == after_watered
        resources_unchanged = (
            after.tool.tool_uses == before.tool.tool_uses
            and after.tool.refill_count == before.tool.refill_count
            and after.tool.watering_can_units == before.tool.watering_can_units
            and after.energy == before.energy
        )
        if command.purpose == "water_crop" and not (
            len(after_watered - before_watered) == 1
            and after.tool.tool_uses == before.tool.tool_uses + 1
            and after.tool.watering_can_units == before.tool.watering_can_units - 1
            and after.energy is not None
            and before.energy is not None
            and after.energy <= before.energy
        ):
            raise StardewCompanionError("watering postcondition is not exactly visible")
        if command.purpose == "select_watering_can" and after.tool.selected_tool != "watering_can":
            raise StardewCompanionError("watering-can selection is not visibly confirmed")
        if command.purpose == "select_watering_can" and not (
            crop_state_unchanged and resources_unchanged
        ):
            raise StardewCompanionError("watering-can selection changed task resources")
        if command.purpose == "refill" and not (
            after.tool.refill_count == before.tool.refill_count + 1
            and after.tool.watering_can_units == after.tool.watering_can_capacity
            and after.tool.tool_uses == before.tool.tool_uses
            and after.energy == before.energy
            and crop_state_unchanged
        ):
            raise StardewCompanionError("safe refill postcondition is not exactly visible")
        if command.purpose == "return_to_entrance" and after.position.at_farmhouse_entrance is not True:
            raise StardewCompanionError("farmhouse entrance is not visibly confirmed")
        if command.purpose in {"navigate", "return_to_entrance", "neutralize"} and not (
            crop_state_unchanged and resources_unchanged
        ):
            raise StardewCompanionError("navigation or neutralization changed task resources")
        if command.purpose == "navigate" and after.position == before.position:
            raise StardewCompanionError("navigation postcondition is not visibly confirmed")

    @staticmethod
    def _same_task_state(before: ScreenObservation, after: ScreenObservation) -> bool:
        return (
            before.save_tree_sha256 == after.save_tree_sha256
            and before.window == after.window
            and before.crops == after.crops
            and before.energy == after.energy
            and before.energy_maximum == after.energy_maximum
            and before.tool == after.tool
            and before.position == after.position
        )

    def _fail(
        self,
        code: FailureCode,
        detail: str,
        driver: OrdinaryInputDriver,
    ) -> StardewModeAttempt:
        attempt = self._require_active()
        self.operator.fail(code, detail, driver=driver)
        self.authorization = None
        attempt.status = StardewAttemptStatus.FAILED
        attempt.stop_reason = code.value
        attempt.first_unmet_requirement = detail
        attempt.input_neutralized = self.operator.input_neutralized
        attempt.player_ownership_restored = self.operator.owner is InputOwner.PLAYER
        try:
            attempt.primary_save_unchanged = self.manager.verify_primary_unchanged(self.save)
        except StardewAdapterError:
            attempt.primary_save_unchanged = False
        return attempt

    @staticmethod
    def _failure_code(exc: Exception) -> FailureCode:
        return StardewCompanionController._failure_code_from_reason(str(exc))

    @staticmethod
    def _failure_code_from_reason(reason: str) -> FailureCode:
        for code in FailureCode:
            if code.value in reason:
                return code
        return FailureCode.UNKNOWN_STATE


def _hash_required_evidence(root: Path, required: tuple[str, ...]) -> dict[str, str]:
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise StardewCompanionError("missing required evidence root") from exc
    hashes: dict[str, str] = {}
    for relative in required:
        try:
            candidate = (root / relative).resolve(strict=True)
        except OSError as exc:
            raise StardewCompanionError(f"missing required evidence: {relative}") from exc
        if root not in candidate.parents or not candidate.is_file():
            raise StardewCompanionError(f"missing required evidence: {relative}")
        hashes[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if not hashes:
        raise StardewCompanionError("missing required evidence manifest")
    return hashes


def attempt_payload(attempt: StardewModeAttempt) -> dict[str, object]:
    """Serializable evidence payload; Show classifications remain explicit."""
    payload = asdict(attempt)
    payload["mode"] = attempt.mode.value
    payload["status"] = attempt.status.value
    return payload
