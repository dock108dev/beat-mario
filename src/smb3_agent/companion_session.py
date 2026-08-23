from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol


class CompanionSessionError(ValueError):
    pass


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ObservationSource(str, Enum):
    ADAPTER = "adapter_observed"
    PLAYER = "player_reported"


class SessionLifecycle(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    CANCELLATION_REQUESTED = "cancellation_requested"
    INPUT_STOPPED = "input_stopped"
    CONTROL_RETURNED = "control_returned"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TAKEN_OVER = "taken_over"
    COMPLETED = "completed"


@dataclass(frozen=True)
class AdapterIdentity:
    adapter_id: str
    game_name: str
    adapter_name: str
    status: str


@dataclass(frozen=True)
class GoalIdentity:
    goal_id: str
    name: str
    objective: str


@dataclass(frozen=True)
class Observation:
    checkpoint: str | None
    observed_at: datetime | None
    freshness: Freshness
    confidence: float | None
    evidence_references: tuple[str, ...] = ()
    checkpoint_id: str | None = None
    source: ObservationSource | None = None
    game_id: str | None = None

    @property
    def trusted(self) -> bool:
        return (
            self.checkpoint is not None
            and self.freshness is Freshness.FRESH
            and self.confidence is not None
        )

    def validate(self) -> None:
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise CompanionSessionError("observation confidence must be between 0 and 1")
        if self.freshness is Freshness.FRESH and (
            self.checkpoint is None or self.observed_at is None or self.confidence is None
        ):
            raise CompanionSessionError(
                "fresh observations require a checkpoint, observation time, and confidence"
            )
        if self.checkpoint_id is not None and not self.checkpoint_id:
            raise CompanionSessionError("checkpoint id must be non-empty when supplied")


@dataclass(frozen=True)
class CompanionObservationEnvelope:
    """Adapter-neutral carrier for a shared observation plus adapter-owned facts.

    The shared record intentionally knows only identity, provenance, freshness,
    ownership, and opaque adapter facts. Adapters remain responsible for
    interpreting and validating those facts.
    """

    observation: Observation
    adapter_id: str
    session_identity: Mapping[str, str]
    facts: Mapping[str, Any]
    fact_provenance: Mapping[str, tuple[str, ...]]
    input_owner: str
    stale_reasons: tuple[str, ...] = ()

    def validate(self) -> None:
        self.observation.validate()
        if not self.adapter_id or not self.session_identity:
            raise CompanionSessionError("companion observations require adapter and session identity")
        if not self.input_owner:
            raise CompanionSessionError("companion observations require an input owner")
        if self.observation.freshness is Freshness.FRESH and self.stale_reasons:
            raise CompanionSessionError("fresh companion observations cannot carry stale reasons")
        if self.observation.freshness is not Freshness.FRESH and not self.stale_reasons:
            raise CompanionSessionError("non-fresh companion observations require a reason")
        for fact_id, references in self.fact_provenance.items():
            if fact_id not in self.facts or not references:
                raise CompanionSessionError("fact provenance must name a retained adapter fact")

    @property
    def trusted(self) -> bool:
        return self.observation.trusted and not self.stale_reasons


class CompanionCapabilityProvider(Protocol):
    """Adapter-owned mode truth consumed without shared game-id branching."""

    def mode_capabilities(
        self, observation: CompanionObservationEnvelope | None
    ) -> tuple[ModeCapability, ...]: ...


@dataclass(frozen=True)
class ModeCapability:
    mode: str
    available: bool
    explanation: str
    unavailable_reason: str | None = None

    def validate(self) -> None:
        if self.mode not in {"tell", "show", "do"}:
            raise CompanionSessionError(f"unsupported companion mode: {self.mode}")
        if not self.available and not self.unavailable_reason:
            raise CompanionSessionError(f"unavailable {self.mode} mode requires a reason")


@dataclass(frozen=True)
class SafetyBoundary:
    authorized: bool
    stop_point: str | None
    protected_decisions: tuple[str, ...]
    recovery_boundary: str

    def validate(self) -> None:
        if self.authorized and not self.stop_point:
            raise CompanionSessionError("authorization requires a declared stop point")


@dataclass(frozen=True)
class SessionOutcome:
    game_owned: bool
    attempted: str
    changed: str
    resources_consumed: str
    verified_outcome: str
    unresolved_uncertainty: str
    final_observation: Observation | None
    evidence_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompanionSession:
    adapter: AdapterIdentity
    goal: GoalIdentity
    observation: Observation
    modes: tuple[ModeCapability, ...]
    safety: SafetyBoundary
    lifecycle: SessionLifecycle
    activity: tuple[str, ...] = ()
    outcome: SessionOutcome | None = None
    input_stopped: bool = False
    control_returned: bool = False

    def validate(self) -> None:
        self.observation.validate()
        self.safety.validate()
        if {mode.mode for mode in self.modes} != {"tell", "show", "do"}:
            raise CompanionSessionError("session must declare Tell, Show, and Do exactly once")
        for mode in self.modes:
            mode.validate()
        if not self.observation.trusted and any(
            mode.available for mode in self.modes if mode.mode in {"show", "do"}
        ):
            raise CompanionSessionError(
                "Show and Do must be unavailable when observation is unknown or stale"
            )
        if self.lifecycle is SessionLifecycle.COMPLETED:
            if self.outcome is None or not self.outcome.game_owned:
                raise CompanionSessionError(
                    "completed sessions require a game-owned outcome"
                )
            if not self.input_stopped:
                raise CompanionSessionError("completed sessions require input to be stopped")
            if not self.control_returned:
                raise CompanionSessionError("completed sessions require control to be returned")
            final = self.outcome.final_observation
            if final is None or not final.trusted:
                raise CompanionSessionError(
                    "completed sessions require a known final observation"
                )

    @property
    def can_take_control(self) -> bool:
        return self.lifecycle in {
            SessionLifecycle.ACTIVE,
            SessionLifecycle.CANCELLATION_REQUESTED,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
