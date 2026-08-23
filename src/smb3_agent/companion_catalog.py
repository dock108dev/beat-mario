from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol, Sequence


CATALOG_SCHEMA_VERSION = "game-companion-catalog/v1"
PREFERENCES_SCHEMA_VERSION = "game-companion-catalog-preferences/v1"
SWITCH_EVIDENCE_CLASSIFICATION = "catalog_switch"
MAX_PREFERENCES_BYTES = 64 * 1024
MAX_SECTION_PREFERENCES = 32
KNOWN_CAPABILITY_STATUSES = frozenset(
    {"available", "setup_required", "implementation_validation_deferred", "unavailable"}
)
KNOWN_EVIDENCE_CLASSIFICATIONS = frozenset(
    {
        "review_only",
        "technical",
        "fixture",
        "owner_feedback",
        "reliability",
        "authoritative_gameplay",
        "unattended_regression",
        SWITCH_EVIDENCE_CLASSIFICATION,
    }
)


class CompanionCatalogError(ValueError):
    pass


class SwitchRefused(CompanionCatalogError):
    pass


@dataclass(frozen=True)
class CatalogCapability:
    capability_id: str
    label: str
    status: str
    summary: str
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class CatalogGoal:
    goal_id: str
    label: str
    summary: str
    profile_ids: tuple[str, ...]


@dataclass(frozen=True)
class CatalogProfile:
    profile_id: str
    label: str
    profile_type: str
    summary: str


@dataclass(frozen=True)
class CatalogScope:
    scope_id: str
    label: str
    stop_conditions: tuple[str, ...]


@dataclass(frozen=True)
class CatalogObservation:
    method_id: str
    label: str
    trust_boundary: str


@dataclass(frozen=True)
class CatalogSafety:
    summary: str
    protected_decisions: tuple[str, ...]
    stop_behavior: str
    reclaim_behavior: str
    handback_behavior: str


@dataclass(frozen=True)
class CatalogEvidence:
    namespace: str
    classifications: tuple[str, ...]
    trust_boundary: str


@dataclass(frozen=True)
class AdapterCatalogEntry:
    adapter_id: str
    game_id: str
    display_name: str
    description: str
    adapter_version: str
    implementation_status: str
    availability: str
    availability_reason: str
    setup_state: str
    observation: CatalogObservation
    capabilities: tuple[CatalogCapability, ...]
    goals: tuple[CatalogGoal, ...]
    profiles: tuple[CatalogProfile, ...]
    scopes: tuple[CatalogScope, ...]
    safety: CatalogSafety
    evidence: CatalogEvidence
    standalone_surface: str
    recovery_guidance: str


@dataclass(frozen=True)
class AdapterRuntimeState:
    adapter_id: str
    input_owner: str = "player"
    active_mode: str | None = None
    active_agent_input: bool = False
    active_show: bool = False
    active_do_authorization: bool = False
    pending_reclaim: bool = False
    pending_neutralization: bool = False
    handback_confirmed: bool = True
    ownership_ambiguous: bool = False
    incomplete_failure_retention: bool = False
    unsafe_save_transition: bool = False
    continuity_known: bool = True
    volatile_observation_present: bool = False
    volatile_authority_present: bool = False

    def refusal_reasons(self) -> tuple[str, ...]:
        checks = (
            (self.active_mode is not None, "the current adapter mode must be stopped"),
            (self.active_agent_input, "agent input is active"),
            (self.active_show, "Show is active"),
            (self.active_do_authorization, "Do authorization is active"),
            (self.pending_reclaim, "reclaim is pending"),
            (self.pending_neutralization, "input neutralization is pending"),
            (not self.handback_confirmed, "player handback is unconfirmed"),
            (
                self.ownership_ambiguous or self.input_owner != "player",
                "input ownership is not confirmed as player-owned",
            ),
            (self.incomplete_failure_retention, "failure retention is incomplete"),
            (self.unsafe_save_transition, "a save or reset transition is unsafe"),
            (not self.continuity_known, "process or window continuity is unknown"),
        )
        return tuple(reason for failed, reason in checks if failed)


@dataclass(frozen=True)
class SwitchEvent:
    event_id: str
    occurred_at: str
    from_adapter_id: str
    to_adapter_id: str
    classification: str
    input_owner: str
    input_neutralized: bool
    active_modes_disabled: bool
    volatile_state_invalidated: bool
    attempt_and_evidence_retained: bool
    handback_status: str
    new_observation_required: bool


class CatalogProvider(Protocol):
    def catalog_entry(self) -> AdapterCatalogEntry: ...

    def runtime_state(self) -> AdapterRuntimeState: ...

    def retain_for_switch(self) -> bool: ...

    def invalidate_volatile_state(self) -> bool: ...


class CatalogRegistry:
    def __init__(self, providers: Sequence[CatalogProvider]) -> None:
        self._providers = tuple(providers)
        self._entries = tuple(provider.catalog_entry() for provider in self._providers)
        self._validate()
        self._by_adapter = dict(zip((item.adapter_id for item in self._entries), self._providers))

    @property
    def entries(self) -> tuple[AdapterCatalogEntry, ...]:
        return tuple(self.entry(item.adapter_id) for item in self._entries)

    def entry(self, adapter_id: str) -> AdapterCatalogEntry:
        provider = self._by_adapter.get(adapter_id)
        if provider is None:
            raise CompanionCatalogError(f"unknown adapter id: {adapter_id}")
        entry = provider.catalog_entry()
        baseline = next(item for item in self._entries if item.adapter_id == adapter_id)
        if _static_provider_payload(entry) != _static_provider_payload(baseline):
            raise CompanionCatalogError(f"catalog/provider disagreement: {adapter_id}")
        self._validate_entry(entry)
        return entry

    def provider(self, adapter_id: str) -> CatalogProvider:
        try:
            return self._by_adapter[adapter_id]
        except KeyError as exc:
            raise CompanionCatalogError(f"unknown adapter id: {adapter_id}") from exc

    def _validate(self) -> None:
        if not self._entries:
            raise CompanionCatalogError("catalog requires at least one explicit provider")
        adapter_ids = [item.adapter_id for item in self._entries]
        game_ids = [item.game_id for item in self._entries]
        evidence_namespaces = [item.evidence.namespace for item in self._entries]
        if len(adapter_ids) != len(set(adapter_ids)):
            raise CompanionCatalogError("duplicate adapter id")
        if len(game_ids) != len(set(game_ids)):
            raise CompanionCatalogError("duplicate game id")
        if len(evidence_namespaces) != len(set(evidence_namespaces)):
            raise CompanionCatalogError("duplicate evidence namespace")
        for provider, entry in zip(self._providers, self._entries):
            repeated = provider.catalog_entry()
            if repeated != entry:
                raise CompanionCatalogError(f"catalog/provider disagreement: {entry.adapter_id}")
            self._validate_entry(entry)

    @staticmethod
    def _validate_entry(entry: AdapterCatalogEntry) -> None:
        required_text = (
            entry.adapter_id,
            entry.game_id,
            entry.display_name,
            entry.description,
            entry.adapter_version,
            entry.implementation_status,
            entry.availability,
            entry.availability_reason,
            entry.setup_state,
            entry.observation.method_id,
            entry.observation.label,
            entry.observation.trust_boundary,
            entry.safety.summary,
            entry.safety.stop_behavior,
            entry.safety.reclaim_behavior,
            entry.safety.handback_behavior,
            entry.evidence.namespace,
            entry.evidence.trust_boundary,
            entry.standalone_surface,
            entry.recovery_guidance,
        )
        if any(not value.strip() for value in required_text):
            raise CompanionCatalogError(f"missing provider field: {entry.adapter_id}")
        if entry.availability not in {"available", "setup_required", "unavailable"}:
            raise CompanionCatalogError(f"unknown availability state: {entry.adapter_id}")
        if not entry.capabilities or not entry.goals or not entry.profiles or not entry.scopes:
            raise CompanionCatalogError(f"missing capability, goal, profile, or scope declaration: {entry.adapter_id}")
        if not entry.safety.protected_decisions or not entry.evidence.classifications:
            raise CompanionCatalogError(f"missing safety or evidence declaration: {entry.adapter_id}")
        capability_ids = [item.capability_id for item in entry.capabilities]
        goal_ids = [item.goal_id for item in entry.goals]
        profile_ids = {item.profile_id for item in entry.profiles}
        scope_ids = [item.scope_id for item in entry.scopes]
        if len(capability_ids) != len(set(capability_ids)):
            raise CompanionCatalogError(f"duplicate capability id: {entry.adapter_id}")
        if len(goal_ids) != len(set(goal_ids)):
            raise CompanionCatalogError(f"duplicate goal id: {entry.adapter_id}")
        if len(profile_ids) != len(entry.profiles):
            raise CompanionCatalogError(f"duplicate profile id: {entry.adapter_id}")
        if len(scope_ids) != len(set(scope_ids)):
            raise CompanionCatalogError(f"duplicate scope id: {entry.adapter_id}")
        if {"tell", "show", "do"} - set(capability_ids):
            raise CompanionCatalogError(f"Tell, Show, and Do declarations are required: {entry.adapter_id}")
        for capability in entry.capabilities:
            if any(
                not value.strip()
                for value in (capability.capability_id, capability.label, capability.summary)
            ):
                raise CompanionCatalogError(f"missing provider field: {entry.adapter_id}")
            if capability.status not in KNOWN_CAPABILITY_STATUSES:
                raise CompanionCatalogError(
                    f"unknown capability status: {entry.adapter_id}/{capability.capability_id}"
                )
            if capability.status != "available" and not capability.unavailable_reason:
                raise CompanionCatalogError(
                    f"unavailable capability requires a reason: {entry.adapter_id}/{capability.capability_id}"
                )
        for goal in entry.goals:
            if any(not value.strip() for value in (goal.goal_id, goal.label, goal.summary)):
                raise CompanionCatalogError(f"missing provider field: {entry.adapter_id}")
            if not goal.profile_ids or not set(goal.profile_ids).issubset(profile_ids):
                raise CompanionCatalogError(f"unsupported goal/profile reference: {entry.adapter_id}/{goal.goal_id}")
        if any(
            any(not value.strip() for value in (profile.profile_id, profile.label, profile.profile_type, profile.summary))
            for profile in entry.profiles
        ):
            raise CompanionCatalogError(f"missing provider field: {entry.adapter_id}")
        if any(
            not scope.scope_id.strip()
            or not scope.label.strip()
            or not scope.stop_conditions
            or any(not condition.strip() for condition in scope.stop_conditions)
            for scope in entry.scopes
        ):
            raise CompanionCatalogError(f"unsupported scope/stop reference: {entry.adapter_id}")
        if any(not decision.strip() for decision in entry.safety.protected_decisions):
            raise CompanionCatalogError(f"missing safety or evidence declaration: {entry.adapter_id}")
        if len(entry.evidence.classifications) != len(set(entry.evidence.classifications)):
            raise CompanionCatalogError(f"duplicate evidence classification: {entry.adapter_id}")
        unknown_evidence = set(entry.evidence.classifications) - KNOWN_EVIDENCE_CLASSIFICATIONS
        if unknown_evidence:
            raise CompanionCatalogError(f"unknown evidence classification: {entry.adapter_id}")


@dataclass
class CatalogPreferences:
    schema_version: str = PREFERENCES_SCHEMA_VERSION
    selected_adapter_id: str | None = None
    display: dict[str, object] = field(default_factory=dict)
    adapters: dict[str, dict[str, object]] = field(default_factory=dict)


class CatalogPreferenceStore:
    def __init__(self, path: Path = Path("artifacts/companion/catalog-preferences.json")) -> None:
        self.path = path
        self.recovery_reason: str | None = None

    def load(self, registry: CatalogRegistry) -> CatalogPreferences:
        self.recovery_reason = None
        if not self.path.exists():
            return CatalogPreferences()
        try:
            if self.path.stat().st_size > MAX_PREFERENCES_BYTES:
                raise CompanionCatalogError("catalog preferences exceed the bounded local size")
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, Mapping) or raw.get("schema_version") != PREFERENCES_SCHEMA_VERSION:
                raise CompanionCatalogError("catalog preferences are stale or use an unknown schema")
            selected = raw.get("selected_adapter_id")
            known = {entry.adapter_id for entry in registry.entries}
            if selected is not None and selected not in known:
                raise CompanionCatalogError("persisted adapter selection is unknown or stale")
            display = raw.get("display", {})
            adapters = raw.get("adapters", {})
            if not isinstance(display, dict) or not isinstance(adapters, dict):
                raise CompanionCatalogError("catalog preferences have an invalid shape")
            if set(adapters) - known:
                raise CompanionCatalogError("catalog preferences contain an unknown adapter namespace")
            allowed_display = {"compact_catalog", "catalog_expanded"}
            allowed_adapter = {"last_goal_id", "last_profile_id", "sections"}
            if set(display) - allowed_display:
                raise CompanionCatalogError("catalog preferences contain unsupported display state")
            if any(not isinstance(value, bool) for value in display.values()):
                raise CompanionCatalogError("catalog preferences contain unsafe display state")
            for adapter_id, values in adapters.items():
                if not isinstance(values, dict) or set(values) - allowed_adapter:
                    raise CompanionCatalogError(f"unsafe persisted state in adapter namespace: {adapter_id}")
                entry = registry.entry(adapter_id)
                goal_id = values.get("last_goal_id")
                profile_id = values.get("last_profile_id")
                if goal_id is not None and goal_id not in {item.goal_id for item in entry.goals}:
                    raise CompanionCatalogError("persisted goal is stale or cross-adapter")
                if profile_id is not None and profile_id not in {item.profile_id for item in entry.profiles}:
                    raise CompanionCatalogError("persisted profile is stale or cross-adapter")
                sections = values.get("sections", {})
                if (
                    not isinstance(sections, dict)
                    or len(sections) > MAX_SECTION_PREFERENCES
                    or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in sections.items())
                ):
                    raise CompanionCatalogError("persisted section state is unsafe or unbounded")
            return CatalogPreferences(
                selected_adapter_id=selected,
                display=dict(display),
                adapters={str(key): dict(value) for key, value in adapters.items()},
            )
        except (OSError, json.JSONDecodeError, TypeError, CompanionCatalogError) as exc:
            self.recovery_reason = str(exc)
            return CatalogPreferences()

    def write(self, preferences: CatalogPreferences, registry: CatalogRegistry) -> None:
        if preferences.schema_version != PREFERENCES_SCHEMA_VERSION:
            raise CompanionCatalogError("refusing to persist unknown catalog preference schema")
        known = {entry.adapter_id for entry in registry.entries}
        if preferences.selected_adapter_id not in known:
            raise CompanionCatalogError("refusing to persist an unknown adapter selection")
        if set(preferences.adapters) - known:
            raise CompanionCatalogError("refusing to persist an unknown adapter namespace")
        if set(preferences.display) - {"compact_catalog", "catalog_expanded"} or any(
            not isinstance(value, bool) for value in preferences.display.values()
        ):
            raise CompanionCatalogError("refusing to persist unsafe display preferences")
        for adapter_id, values in preferences.adapters.items():
            if set(values) - {"last_goal_id", "last_profile_id", "sections"}:
                raise CompanionCatalogError("refusing to persist unsafe adapter preferences")
            entry = registry.entry(adapter_id)
            if values.get("last_goal_id") is not None and values["last_goal_id"] not in {
                item.goal_id for item in entry.goals
            }:
                raise CompanionCatalogError("refusing to persist a cross-adapter goal")
            if values.get("last_profile_id") is not None and values["last_profile_id"] not in {
                item.profile_id for item in entry.profiles
            }:
                raise CompanionCatalogError("refusing to persist a cross-adapter profile")
            sections = values.get("sections", {})
            if (
                not isinstance(sections, dict)
                or len(sections) > MAX_SECTION_PREFERENCES
                or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in sections.items())
            ):
                raise CompanionCatalogError("refusing to persist unsafe section preferences")
        encoded = (json.dumps(asdict(preferences), indent=2, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > MAX_PREFERENCES_BYTES:
            raise CompanionCatalogError("refusing to persist unbounded catalog preferences")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".{secrets.token_hex(6)}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(encoded.decode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


class CatalogSession:
    def __init__(self, registry: CatalogRegistry, store: CatalogPreferenceStore) -> None:
        self.registry = registry
        self.store = store
        self.preferences = store.load(registry)
        self.switch_events: list[SwitchEvent] = []
        self.switch_event_path = store.path.parent / "catalog-switch-events.jsonl"

    @property
    def selected_adapter_id(self) -> str | None:
        return self.preferences.selected_adapter_id

    @property
    def safe_catalog_only(self) -> bool:
        return self.store.recovery_reason is not None or self.selected_adapter_id is None

    def select_initial(self, adapter_id: str) -> SwitchEvent:
        if self.selected_adapter_id is not None:
            raise SwitchRefused("an adapter is already selected; use explicit switching")
        return self._complete_switch("catalog", adapter_id)

    def switch(self, adapter_id: str) -> SwitchEvent:
        current_id = self.selected_adapter_id
        if current_id is None:
            return self.select_initial(adapter_id)
        if current_id == adapter_id:
            raise SwitchRefused("the requested adapter is already selected")
        target = self.registry.entry(adapter_id)
        if target.availability == "unavailable":
            raise SwitchRefused(f"Switch refused: {target.availability_reason}")
        current = self.registry.provider(current_id)
        state = current.runtime_state()
        if state.adapter_id != current_id:
            raise SwitchRefused("cross-adapter runtime identity was refused")
        reasons = state.refusal_reasons()
        if reasons:
            raise SwitchRefused("Switch refused: " + "; ".join(reasons))
        if not current.retain_for_switch():
            raise SwitchRefused("Switch refused: current attempt and evidence were not retained")
        if not current.invalidate_volatile_state():
            raise SwitchRefused("Switch refused: volatile authority or observation could not be invalidated")
        return self._complete_switch(current_id, adapter_id, target=target)

    def update_display_preferences(
        self,
        *,
        compact_catalog: bool,
        catalog_expanded: bool,
    ) -> None:
        if self.preferences.selected_adapter_id is None:
            raise CompanionCatalogError("select an adapter before persisting presentation preferences")
        self.preferences.display = {
            "compact_catalog": compact_catalog,
            "catalog_expanded": catalog_expanded,
        }
        self.store.write(self.preferences, self.registry)

    def _complete_switch(
        self,
        from_adapter_id: str,
        adapter_id: str,
        *,
        target: AdapterCatalogEntry | None = None,
    ) -> SwitchEvent:
        target = target or self.registry.entry(adapter_id)
        if target.availability == "unavailable":
            raise SwitchRefused(f"Switch refused: {target.availability_reason}")
        self.preferences.selected_adapter_id = adapter_id
        self.store.write(self.preferences, self.registry)
        event = SwitchEvent(
            event_id=secrets.token_hex(12),
            occurred_at=datetime.now(timezone.utc).isoformat(),
            from_adapter_id=from_adapter_id,
            to_adapter_id=adapter_id,
            classification=SWITCH_EVIDENCE_CLASSIFICATION,
            input_owner="player",
            input_neutralized=True,
            active_modes_disabled=True,
            volatile_state_invalidated=True,
            attempt_and_evidence_retained=True,
            handback_status="player_owned_neutral",
            new_observation_required=True,
        )
        self.switch_events.append(event)
        self._append_switch_event(event)
        return event

    def _append_switch_event(self, event: SwitchEvent) -> None:
        self.switch_event_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            self.switch_event_path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(event), sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def inspection_payload(self) -> dict[str, object]:
        return {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "selected_adapter_id": self.selected_adapter_id,
            "safe_catalog_only": self.safe_catalog_only,
            "preference_recovery_reason": self.store.recovery_reason,
            "switch_evidence_classification": SWITCH_EVIDENCE_CLASSIFICATION,
            "adapters": [asdict(entry) for entry in self.registry.entries],
            "live_activity_run": False,
        }


def _static_provider_payload(entry: AdapterCatalogEntry) -> dict[str, object]:
    """Compare provider-owned truth while permitting live setup availability to refresh."""
    payload = asdict(entry)
    for field_name in ("availability", "availability_reason", "setup_state"):
        payload.pop(field_name)
    return payload
