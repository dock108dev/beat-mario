from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from smb3_agent.companion_catalog import (
    AdapterRuntimeState,
    CatalogPreferenceStore,
    CatalogPreferences,
    CatalogRegistry,
    CatalogSession,
    CompanionCatalogError,
    SwitchRefused,
)
from smb3_agent.lab_ui import render_combined_catalog
from smb3_agent.mario_product import MarioCatalogProvider
from smb3_agent.stardew_companion import StardewCatalogProvider


def _registry(mario_state: AdapterRuntimeState | None = None) -> CatalogRegistry:
    return CatalogRegistry(
        (
            MarioCatalogProvider(runtime=lambda: mario_state or AdapterRuntimeState("smb3")),
            StardewCatalogProvider(),
        )
    )


def test_exact_two_adapter_catalog_is_stable_and_provider_owned() -> None:
    registry = _registry()
    assert tuple(item.adapter_id for item in registry.entries) == ("smb3", "stardew")
    assert tuple(item.game_id for item in registry.entries) == ("smb3", "stardew_valley")
    assert registry.entry("smb3").observation.method_id == "fceux_live_observer"
    assert registry.entry("stardew").observation.method_id == "visible_screen_only"
    assert registry.entry("smb3").goals != registry.entry("stardew").goals
    assert registry.entry("smb3").profiles != registry.entry("stardew").profiles
    assert registry.entry("smb3").safety != registry.entry("stardew").safety
    assert registry.entry("smb3").evidence.namespace == "mario"
    assert registry.entry("stardew").evidence.namespace == "stardew"


def test_duplicate_adapter_game_and_conflicting_provider_truth_fail_closed() -> None:
    mario = MarioCatalogProvider()

    class DuplicateProvider:
        def catalog_entry(self):
            return replace(mario.catalog_entry(), adapter_version="conflicting/v1")

        def runtime_state(self):
            return AdapterRuntimeState("smb3")

        def retain_for_switch(self):
            return True

        def invalidate_volatile_state(self):
            return True

    with pytest.raises(CompanionCatalogError, match="duplicate"):
        CatalogRegistry((mario, DuplicateProvider()))


def test_duplicate_evidence_namespace_fails_closed() -> None:
    mario = MarioCatalogProvider()
    stardew = StardewCatalogProvider()

    class ConflictingEvidenceProvider:
        def catalog_entry(self):
            entry = stardew.catalog_entry()
            return replace(entry, evidence=replace(entry.evidence, namespace="mario"))

        def runtime_state(self):
            return AdapterRuntimeState("stardew")

        def retain_for_switch(self):
            return True

        def invalidate_volatile_state(self):
            return True

    with pytest.raises(CompanionCatalogError, match="duplicate evidence namespace"):
        CatalogRegistry((mario, ConflictingEvidenceProvider()))


def test_provider_static_truth_cannot_drift_after_registration() -> None:
    class MutableProvider:
        def __init__(self):
            self.entry = MarioCatalogProvider().catalog_entry()

        def catalog_entry(self):
            return self.entry

        def runtime_state(self):
            return AdapterRuntimeState("smb3")

        def retain_for_switch(self):
            return True

        def invalidate_volatile_state(self):
            return True

    provider = MutableProvider()
    registry = CatalogRegistry((provider,))
    provider.entry = replace(provider.entry, description="drifted capability truth")
    with pytest.raises(CompanionCatalogError, match="catalog/provider disagreement"):
        registry.entry("smb3")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda entry: replace(entry, display_name=""), "missing provider field"),
        (
            lambda entry: replace(
                entry,
                capabilities=(replace(entry.capabilities[0], status="unknown"),) + entry.capabilities[1:],
            ),
            "unknown capability status",
        ),
        (
            lambda entry: replace(
                entry,
                goals=(replace(entry.goals[0], profile_ids=("stardew.profile",)),) + entry.goals[1:],
            ),
            "unsupported goal/profile reference",
        ),
        (lambda entry: replace(entry, safety=replace(entry.safety, protected_decisions=())), "missing safety"),
        (
            lambda entry: replace(
                entry,
                scopes=(replace(entry.scopes[0], stop_conditions=("",)),) + entry.scopes[1:],
            ),
            "unsupported scope/stop reference",
        ),
        (
            lambda entry: replace(
                entry,
                profiles=(replace(entry.profiles[0], summary=""),) + entry.profiles[1:],
            ),
            "missing provider field",
        ),
    ],
)
def test_missing_unknown_or_cross_adapter_provider_declarations_fail_closed(
    mutation, message: str
) -> None:
    base = MarioCatalogProvider().catalog_entry()

    class InvalidProvider:
        def catalog_entry(self):
            return mutation(base)

        def runtime_state(self):
            return AdapterRuntimeState("smb3")

        def retain_for_switch(self):
            return True

        def invalidate_volatile_state(self):
            return True

    with pytest.raises(CompanionCatalogError, match=message):
        CatalogRegistry((InvalidProvider(),))


@pytest.mark.parametrize(
    "state",
    [
        AdapterRuntimeState("smb3", active_mode="observe"),
        AdapterRuntimeState("smb3", active_mode="tell"),
        AdapterRuntimeState("smb3", active_mode="show"),
        AdapterRuntimeState("smb3", active_mode="do"),
        AdapterRuntimeState("smb3", active_agent_input=True),
        AdapterRuntimeState("smb3", active_show=True),
        AdapterRuntimeState("smb3", active_do_authorization=True),
        AdapterRuntimeState("smb3", pending_reclaim=True),
        AdapterRuntimeState("smb3", pending_neutralization=True),
        AdapterRuntimeState("smb3", handback_confirmed=False),
        AdapterRuntimeState("smb3", input_owner="ambiguous", ownership_ambiguous=True),
        AdapterRuntimeState("smb3", input_owner="none"),
        AdapterRuntimeState("smb3", incomplete_failure_retention=True),
        AdapterRuntimeState("smb3", unsafe_save_transition=True),
        AdapterRuntimeState("smb3", continuity_known=False),
    ],
)
def test_switch_refuses_every_active_or_ambiguous_state(
    tmp_path: Path, state: AdapterRuntimeState
) -> None:
    session = CatalogSession(_registry(state), CatalogPreferenceStore(tmp_path / "preferences.json"))
    session.select_initial("smb3")
    with pytest.raises(SwitchRefused, match="Switch refused"):
        session.switch("stardew")
    assert session.selected_adapter_id == "smb3"


def test_successful_switch_retains_evidence_invalidates_volatile_state_and_records_event(
    tmp_path: Path,
) -> None:
    retained: list[bool] = []
    invalidated: list[bool] = []
    registry = CatalogRegistry(
        (
            MarioCatalogProvider(
                runtime=lambda: AdapterRuntimeState(
                    "smb3", volatile_observation_present=True
                ),
                retain=lambda: retained.append(True) is None,
                invalidate=lambda: invalidated.append(True) is None,
            ),
            StardewCatalogProvider(),
        )
    )
    session = CatalogSession(registry, CatalogPreferenceStore(tmp_path / "preferences.json"))
    session.select_initial("smb3")
    event = session.switch("stardew")
    assert retained == [True]
    assert invalidated == [True]
    assert event.classification == "catalog_switch"
    assert event.volatile_state_invalidated is True
    assert event.active_modes_disabled is True
    assert event.input_neutralized is True
    assert event.handback_status == "player_owned_neutral"
    assert event.new_observation_required is True
    assert session.selected_adapter_id == "stardew"


def test_unknown_or_unavailable_target_is_refused_before_current_state_mutation(
    tmp_path: Path,
) -> None:
    retained: list[bool] = []
    invalidated: list[bool] = []
    registry = CatalogRegistry(
        (
            MarioCatalogProvider(
                retain=lambda: retained.append(True) is None,
                invalidate=lambda: invalidated.append(True) is None,
            ),
            StardewCatalogProvider(
                availability=lambda: ("unavailable", "Stardew is unavailable.", "blocked")
            ),
        )
    )
    session = CatalogSession(registry, CatalogPreferenceStore(tmp_path / "preferences.json"))
    session.select_initial("smb3")
    with pytest.raises(CompanionCatalogError, match="unknown adapter"):
        session.switch("unknown")
    with pytest.raises(SwitchRefused, match="unavailable"):
        session.switch("stardew")
    assert retained == []
    assert invalidated == []
    assert session.selected_adapter_id == "smb3"


@pytest.mark.parametrize("hook", ["retain", "invalidate"])
def test_failed_retention_or_invalidation_keeps_current_selection(
    tmp_path: Path, hook: str
) -> None:
    registry = CatalogRegistry(
        (
            MarioCatalogProvider(
                retain=(lambda: False) if hook == "retain" else None,
                invalidate=(lambda: False) if hook == "invalidate" else None,
            ),
            StardewCatalogProvider(),
        )
    )
    session = CatalogSession(registry, CatalogPreferenceStore(tmp_path / "preferences.json"))
    session.select_initial("smb3")
    with pytest.raises(SwitchRefused):
        session.switch("stardew")
    assert session.selected_adapter_id == "smb3"


def test_safe_preferences_are_namespaced_and_corrupt_state_recovers(tmp_path: Path) -> None:
    registry = _registry()
    store = CatalogPreferenceStore(tmp_path / "preferences.json")
    preferences = CatalogPreferences(
        selected_adapter_id="smb3",
        display={"compact_catalog": True},
        adapters={
            "smb3": {
                "last_goal_id": "world_1_king",
                "last_profile_id": "smb3.world-1-1.fastest-accepted-clear",
                "sections": {"safety": True},
            }
        },
    )
    store.write(preferences, registry)
    assert store.load(registry) == preferences
    store.path.write_text(
        '{"schema_version":"stale","selected_adapter_id":"stardew"}',
        encoding="utf-8",
    )
    recovered = store.load(registry)
    assert recovered.selected_adapter_id is None
    assert store.recovery_reason


@pytest.mark.parametrize(
    "payload",
    [
        '{"schema_version":"game-companion-catalog-preferences/v1",'
        '"selected_adapter_id":"smb3","display":{"compact_catalog":"false"},'
        '"adapters":{}}',
        '{"schema_version":"game-companion-catalog-preferences/v1",'
        '"selected_adapter_id":"smb3","display":{"compact_catalog":false},'
        '"adapters":{"smb3":{"last_goal_id":"water_initial_crops_and_return"}}}',
    ],
)
def test_cross_adapter_and_unsafe_presentation_persistence_recovers_to_catalog(
    tmp_path: Path, payload: str
) -> None:
    registry = _registry()
    store = CatalogPreferenceStore(tmp_path / "preferences.json")
    store.path.write_text(payload, encoding="utf-8")
    recovered = store.load(registry)
    assert recovered.selected_adapter_id is None
    assert recovered.adapters == {}
    assert store.recovery_reason


def test_root_surface_contains_both_cards_explicit_switch_and_narrow_contract(
    tmp_path: Path,
) -> None:
    session = CatalogSession(_registry(), CatalogPreferenceStore(tmp_path / "preferences.json"))
    html = render_combined_catalog(session, csrf_token="fixture")
    assert 'data-adapter-id="smb3"' in html
    assert 'data-adapter-id="stardew"' in html
    assert 'action="/catalog-switch"' in html
    assert '@media(max-width:390px)' in html
    assert 'href="/lab"' in html
    assert 'data-testid="safe-catalog-only"' in html


def test_selected_workspace_preserves_standalone_surface_and_switch_is_explicit(
    tmp_path: Path,
) -> None:
    session = CatalogSession(_registry(), CatalogPreferenceStore(tmp_path / "preferences.json"))
    session.select_initial("stardew")
    html = render_combined_catalog(session, csrf_token="fixture")
    assert 'data-testid="selected-game-workspace"' in html
    assert 'data-adapter-id="stardew"' in html
    assert 'href="/stardew"' in html
    assert 'action="/catalog-switch"' in html
    assert "The new adapter requires a fresh observation" in html
    assert "Recovery guidance:" in html


def test_shared_catalog_and_session_module_contains_no_game_id_branching() -> None:
    source = Path("src/smb3_agent/companion_catalog.py").read_text(encoding="utf-8")
    assert 'if game_id == "mario"' not in source
    assert 'if game_id == "stardew"' not in source
    assert 'if adapter_id == "smb3"' not in source
    assert 'if adapter_id == "stardew"' not in source
