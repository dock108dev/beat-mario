from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from smb3_agent.companion_session import Freshness
from smb3_agent.live_observation import ConnectionState, LiveObservationSnapshot
from smb3_agent.mario_product import (
    MarioProductSessionManager,
    ProductStage,
    SetupStatus,
    load_owner_pilot_manifest,
    mario_capabilities,
    recovery_for,
)
from smb3_agent.scenarios import load_scenario_catalog


def _product_contract(path: Path, game_hash: str) -> Path:
    source = yaml.safe_load(Path("data/mario/product.yaml").read_text(encoding="utf-8"))
    source["automatic_game_file_locations"] = []
    source["supported_game_sha256"] = [game_hash]
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    return path


def test_first_use_manual_identity_session_choice_and_safe_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = tmp_path / "mario.nes"
    game.write_bytes(b"NES\x1a" + bytes(12) + b"local-test-fixture")
    game_hash = hashlib.sha256(game.read_bytes()).hexdigest()
    contract = _product_contract(tmp_path / "product.yaml", game_hash)
    monkeypatch.setattr("smb3_agent.mario_product.shutil.which", lambda _: "/opt/local/bin/fceux")
    manager = MarioProductSessionManager(tmp_path / "product-state", contract)

    identity = manager.select_game_file(game)
    assert identity.supported_identity is True
    manager.confirm_input_ready(ready=True, session_kind="takeover_capable")
    state = manager.first_use_state()
    assert state.status is SetupStatus.READY
    assert state.launch_ready is True

    persisted = json.loads(manager.preferences_path.read_text(encoding="utf-8"))
    assert persisted["session_kind"] == "takeover_capable"
    assert not {
        "authorization",
        "control_epoch",
        "process_owner",
        "reclaim_state",
        "write_capability",
    }.intersection(persisted)


def test_observe_only_capability_truth_fails_closed_without_live_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = tmp_path / "mario.nes"
    game.write_bytes(b"NES\x1a" + bytes(12) + b"local-test-fixture")
    contract = _product_contract(
        tmp_path / "product.yaml", hashlib.sha256(game.read_bytes()).hexdigest()
    )
    monkeypatch.setattr("smb3_agent.mario_product.shutil.which", lambda _: "/opt/local/bin/fceux")
    manager = MarioProductSessionManager(tmp_path / "product-state", contract)
    manager.select_game_file(game)
    manager.confirm_input_ready(ready=True, session_kind="observe_only")
    setup = manager.first_use_state()
    snapshot = LiveObservationSnapshot(
        None, ConnectionState.IDLE, Freshness.UNKNOWN, "No live observation."
    )
    capabilities = {item.capability_id: item for item in mario_capabilities(
        setup,
        snapshot,
        show_active=False,
        has_compatible_profile=False,
        has_accepted_reference=False,
        candidate_review_available=False,
    )}
    assert capabilities["observation"].available is True
    assert capabilities["tell"].available is False
    assert capabilities["takeover"].available is False
    assert capabilities["history_evidence"].available is True


@pytest.mark.parametrize(
    "failure_id",
    [
        "missing_game_file",
        "invalid_game_file",
        "emulator_unavailable",
        "launch_failure",
        "duplicate_session",
        "observer_not_ready",
        "stale_observation",
        "unsupported_state",
        "unknown_checkpoint",
        "disconnection",
        "process_lost",
        "controller_conflict",
        "authorization_mismatch",
        "protected_resource_conflict",
        "reclaim_in_progress",
        "neutralization_failure",
        "handback_failure",
        "incompatible_reference",
        "candidate_not_executable",
        "corrupt_local_data",
        "scenario_evidence_mismatch",
    ],
)
def test_every_recovery_contract_has_player_safe_fields(failure_id: str) -> None:
    recovery = recovery_for(failure_id)
    assert recovery.what_happened
    assert recovery.input_owner in {"player", "agent", "ambiguous", "unknown"}
    assert recovery.safe_next_action
    assert isinstance(recovery.game_may_be_running, bool)
    assert isinstance(recovery.agent_input_stopped, bool)
    assert isinstance(recovery.evidence_retained, bool)
    assert isinstance(recovery.retry_creates_fresh_attempt, bool)


def test_runtime_control_state_is_presented_but_never_restored(tmp_path: Path) -> None:
    manager = MarioProductSessionManager(tmp_path / "product-state")
    snapshot = LiveObservationSnapshot(
        "session-1",
        ConnectionState.CONNECTED,
        Freshness.FRESH,
        "Companion is playing.",
        takeover_capable=True,
        control_owner="agent",
        control_state="agent_control",
        control_epoch=4,
    )
    view = manager.view(snapshot)
    assert view.stage is ProductStage.AGENT_CONTROLLING
    assert view.unsafe_state_restored is False
    assert manager.preferences().schema_version == "game-companion-mario-product/v1"


def test_owner_pilot_starts_disabled_with_blank_owner_fields() -> None:
    pilot = load_owner_pilot_manifest()
    assert pilot["execution_enabled"] is False
    assert pilot["status"] == "prepared_not_run"
    assert all(value == "OWNER_TO_COMPLETE" for value in pilot["owner_feedback"].values())
    assert all(value == "OWNER_TO_COMPLETE" for value in pilot["owner_acceptance"].values())
    assert pilot["attempt_rules"]["patching_during_attempt"] == "forbidden"
    assert pilot["failure_retention_rules"]["report_first_unmet_requirement"] is True


def test_v29_deferred_scenario_hooks_are_cataloged() -> None:
    ids = {item.scenario_id for item in load_scenario_catalog()}
    assert {
        "mario.product_first_use",
        "mario.product_workspace",
        "mario.product_observe_tell_coaching",
        "mario.product_show_separation",
        "mario.product_do_reclaim_handback",
        "mario.product_history_learning_recovery",
        "mario.product_persistence_security",
        "mario.owner_pilot_manifest",
    }.issubset(ids)
