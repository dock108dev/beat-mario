from __future__ import annotations

import json
from pathlib import Path

import pytest

from smb3_agent.metrics import EventEnvelope, MetricsError, integrity_hash
from smb3_agent.companion_catalog import CatalogRegistry
from smb3_agent.mario_product import MarioCatalogProvider
from smb3_agent.scenarios import load_scenario_catalog
from smb3_agent.stardew_companion import StardewCatalogProvider
from smb3_agent.unattended import (
    CLASSIFICATION,
    EVIDENCE_CLASSIFICATION,
    DeclaredDisplayProvider,
    NoDisplayProvider,
    UnattendedError,
    compare_attempts,
    eligibility_blockers,
    exception_record,
    load_manifest,
    reject_overlap,
    sanitize_environment,
    StardewUnattendedProvider,
    ProviderRunPlan,
)


def unattended_scenario():
    return next(item for item in load_scenario_catalog() if item.scenario_id == "regression.unattended")


def test_unattended_scenario_freezes_every_proof_boundary() -> None:
    scenario = unattended_scenario()
    assert scenario.classification.value == CLASSIFICATION
    assert scenario.evidence_classification.value == EVIDENCE_CLASSIFICATION
    assert scenario.execution_classification == CLASSIFICATION
    assert scenario.may_count_toward_reliability is False
    assert scenario.may_count_toward_owner_acceptance is False
    assert scenario.visible_live_proof is False
    assert scenario.authoritative_game_outcome is False
    assert eligibility_blockers(scenario) == ()


@pytest.mark.parametrize(
    "scenario_id",
    [
        "takeover.current_session",
        "show.separate_review_only",
        "mario.full_game_takeover",
        "campaign.final_owner_acceptance",
    ],
)
def test_owner_visible_show_reliability_and_campaign_scenarios_are_refused(scenario_id: str) -> None:
    scenario = next(item for item in load_scenario_catalog() if item.scenario_id == scenario_id)
    assert eligibility_blockers(scenario)


def test_requested_evidence_promotion_is_refused() -> None:
    assert "promotion" in " ".join(eligibility_blockers(unattended_scenario(), requested_promotion="reliability"))


def test_display_contract_distinguishes_unavailable_visible_and_virtual_pixels() -> None:
    assert NoDisplayProvider().inspect().available is False
    visible = DeclaredDisplayProvider("desktop", "normal_desktop", "window-server-1", True, True, True).inspect()
    virtual = DeclaredDisplayProvider("virtual", "local_virtual_display", "display-9", True, True, False).inspect()
    assert visible.visible_to_player is True
    assert virtual.visible_to_player is False
    assert virtual.renders_pixels is True


def test_environment_sanitization_rejects_credentials_and_preserves_only_allowlisted_values() -> None:
    with pytest.raises(UnattendedError, match="sensitive environment"):
        sanitize_environment({"GITHUB_TOKEN": "secret"})
    result = sanitize_environment({"PATH": "/bin", "SMB3_GOAL_ID": "fixture", "UNRELATED": "drop"})
    assert result == {"PATH": "/bin", "SMB3_GOAL_ID": "fixture", "LANG": "C"}


def test_stardew_preparation_fails_closed_without_bound_fixture(tmp_path: Path) -> None:
    provider = StardewUnattendedProvider(
        fixture_path=tmp_path / "fixture",
        owner_save_roots=(tmp_path / "owner",),
        executable=tmp_path / "game",
    )
    plan = ProviderRunPlan(
        "stardew", "v1", "stardew", "game", (), (), None, {}, (), (), (), (), (),
        "evidence/v1", "pixels", "ordinary", False,
    )
    with pytest.raises(UnattendedError, match="requires a bound regression fixture"):
        provider.prepare_run(tmp_path / "run", plan)


def test_unattended_exception_record_retains_phase_type_and_traceback() -> None:
    try:
        raise RuntimeError("runner boom")
    except RuntimeError as exc:
        record = exception_record(exc, phase="process_or_environment")

    assert record["phase"] == "process_or_environment"
    assert record["type"] == "RuntimeError"
    assert "RuntimeError: runner boom" in record["traceback"]


def test_owner_save_overlap_is_refused(tmp_path: Path) -> None:
    owner = tmp_path / "owner-save"
    owner.mkdir()
    with pytest.raises(UnattendedError, match="overlaps"):
        reject_overlap(owner / "regression-copy", [owner], label="fixture")


def test_symlink_fixture_overlap_cannot_hide_owner_data(tmp_path: Path) -> None:
    owner = tmp_path / "owner"
    owner.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(owner, target_is_directory=True)
    with pytest.raises(UnattendedError, match="overlaps"):
        reject_overlap(alias, [owner], label="fixture")


def test_manifest_hash_and_evidence_classification_are_immutable(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": "bad"}), encoding="utf-8")
    with pytest.raises((TypeError, UnattendedError)):
        load_manifest(manifest_path)


@pytest.mark.parametrize(
    "field_name",
    [
        "attempt_id", "correlation_id", "causation_id", "source_commit",
        "source_dirty_fingerprint", "adapter_id", "adapter_version", "game_id",
        "scenario_id", "scenario_version", "goal_version", "profile_version",
        "solution_version", "runner_version", "assets", "fixture", "display",
        "executable", "arguments", "sanitized_environment", "run_count",
        "per_run_timeout_seconds", "aggregate_timeout_seconds", "concurrency",
        "cleanup_policy", "artifact_root", "workspace_root", "process_root",
        "protected_data", "protected_actions", "expected_milestones",
        "expected_outputs", "evidence_contract_version", "proof_limits",
    ],
)
def test_manifest_contract_prepares_every_required_identity(field_name: str) -> None:
    assert f"    {field_name}:" in Path("src/smb3_agent/unattended.py").read_text(encoding="utf-8")


def test_unattended_metrics_reject_owner_fastest_and_learning_mutations() -> None:
    base = {
        "event_id": "event-1", "schema_version": "game-companion-event/v1",
        "event_type": "fastest_observed_updated", "session_id": "session-1",
        "scenario_id": "regression.unattended", "scenario_version": "2",
        "attempt_id": "attempt-1", "correlation_id": "correlation-1", "causation_id": None,
        "game_id": "smb3", "adapter_id": "smb3", "adapter_version": "v1",
        "objective_version": "goal-v1", "profile_version": "profile-v1", "solution_version": "solution-v1",
        "actor": "system", "input_owner": "none", "control_epoch": 0,
        "lifecycle_state": "running", "source": "unattended_runner", "provenance": ("manifest",),
        "evidence_classification": EVIDENCE_CLASSIFICATION, "monotonic_sequence": 1,
        "emulator_frame": None, "wall_clock_time": "2026-08-23T00:00:00+00:00", "confidence": None,
        "payload": {
            "classification": CLASSIFICATION, "execution_classification": CLASSIFICATION,
            "may_count_toward_reliability": False, "may_count_toward_owner_acceptance": False,
            "visible_live_proof": False, "authoritative_game_outcome": False,
        },
        "artifact_references": (), "integrity_hash": "",
    }
    event = EventEnvelope(**{**base, "integrity_hash": integrity_hash({k: list(v) if isinstance(v, tuple) else v for k, v in base.items() if k != "integrity_hash"})})
    with pytest.raises(MetricsError, match="cannot mutate"):
        event.validate()


def test_repeatability_refuses_incompatible_manifests() -> None:
    assert compare_attempts


def test_cli_and_lab_contract_terms_are_present() -> None:
    cli = Path("src/smb3_agent/cli.py").read_text(encoding="utf-8")
    lab = Path("src/smb3_agent/lab_ui.py").read_text(encoding="utf-8")
    for command in ("capabilities", "plan", "manifest", "run", "cancel", "status", "compare"):
        assert f'"{command}"' in cli
    assert 'data-testid="lab-unattended-regression"' in lab
    assert "not visible player proof" in lab


def test_unattended_contract_preserves_v212_catalog_and_standalone_surfaces() -> None:
    source = Path("src/smb3_agent/unattended.py").read_text(encoding="utf-8")
    assert "companion_catalog" not in source
    entries = CatalogRegistry([MarioCatalogProvider(), StardewCatalogProvider()]).entries
    assert [(item.adapter_id, item.standalone_surface) for item in entries] == [
        ("smb3", "/mario"),
        ("stardew", "/stardew"),
    ]


def test_lab_prepares_desktop_and_narrow_truthful_unattended_presentation() -> None:
    lab = Path("src/smb3_agent/lab_ui.py").read_text(encoding="utf-8")
    assert 'data-testid="lab-unattended-regression"' in lab
    assert "@media (max-width:" in lab
    assert "Regression only" in lab
    assert "First unmet requirement" in lab
    assert "retained attempts" in lab.lower()


@pytest.mark.parametrize(
    "required_term",
    [
        "start_new_session=True",
        "shell=False",
        "cancel.requested",
        "per_run_timeout_seconds",
        "aggregate_timeout_seconds",
        "terminate_owned_process",
        "retain failed artifacts",
        "correlation_is_not_equivalence_or_causation",
    ],
)
def test_process_isolation_cancellation_failure_and_correlation_contracts_are_prepared(required_term: str) -> None:
    assert required_term in Path("src/smb3_agent/unattended.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "forbidden_target",
    [
        "route reliability",
        "visible player proof",
        "review-only Show evidence",
        "authoritative game completion",
        "owner usefulness",
        "owner acceptance",
        "consolidated campaign",
    ],
)
def test_exact_proof_limits_are_in_the_artifact_contract(forbidden_target: str) -> None:
    assert forbidden_target in Path("data/scenarios/unattended-artifact-contract.yaml").read_text(encoding="utf-8")
