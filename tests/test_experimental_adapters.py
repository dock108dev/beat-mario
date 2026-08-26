from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from smb3_agent.companion_catalog import build_default_catalog_registry
from smb3_agent.experimental_adapters import (
    ALLOWED_FILES,
    PROOF_LIMITS,
    ExperimentalAdapterError,
    ExperimentalCatalogProvider,
    InstallationRefused,
    RemovalRefused,
    install_adapter,
    installation_status,
    run_conformance,
    scaffold_adapter,
    scaffold_payload,
    uninstall_adapter,
    validate_contract,
)
from smb3_agent.lab_ui import render_experimental_onboarding
from smb3_agent.scenarios import load_scenario_catalog


def _scaffold(tmp_path: Path, adapter_id: str = "fixture-game") -> Path:
    return scaffold_adapter(tmp_path / "scaffolds", adapter_id, "Fixture Game")


def _write_contract(path: Path, payload: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_valid_contract_covers_every_versioned_adapter_boundary() -> None:
    contract = validate_contract(scaffold_payload("fixture-game", "Fixture Game"))
    assert contract["schema_version"] == "game-companion-experimental-adapter/v1"
    assert set(contract) == {
        "schema_version", "identity", "detection", "observation", "input", "ownership",
        "capabilities", "goals", "solution_profiles", "protected_actions", "takeover_scopes",
        "fixtures", "evidence", "proof_limits", "installation", "removal",
    }


@pytest.mark.parametrize("adapter_id", ["mario", "smb3", "stardew", "stardew-valley", "core", "lab"])
def test_reserved_and_builtin_ids_are_refused(adapter_id: str) -> None:
    with pytest.raises(ExperimentalAdapterError, match="reserved|built-in"):
        scaffold_payload(adapter_id, "Collision")


@pytest.mark.parametrize("bad_path", ["/tmp/fixture.json", "../fixture.json", "fixtures/../../escape.json"])
def test_absolute_and_traversal_paths_are_refused(bad_path: str) -> None:
    contract = scaffold_payload("fixture-game", "Fixture Game")
    contract["fixtures"]["observation-idle"] = bad_path
    with pytest.raises(ExperimentalAdapterError, match="bounded relative path"):
        validate_contract(contract)


@pytest.mark.parametrize("field", ["command", "shell", "script", "code", "url", "dependencies"])
def test_command_code_and_network_injection_fields_are_refused(field: str) -> None:
    contract = scaffold_payload("fixture-game", "Fixture Game")
    contract[field] = "unsafe"
    with pytest.raises(ExperimentalAdapterError, match="executable or network"):
        validate_contract(contract)


def test_capability_and_profile_conflicts_fail_closed() -> None:
    contract = scaffold_payload("fixture-game", "Fixture Game")
    contract["capabilities"][0]["state"] = "supported"
    with pytest.raises(ExperimentalAdapterError, match="declared or unsupported"):
        validate_contract(contract)
    contract = scaffold_payload("fixture-game", "Fixture Game")
    contract["solution_profiles"][0]["goal_id"] = "missing"
    with pytest.raises(ExperimentalAdapterError, match="unknown goal"):
        validate_contract(contract)


def test_scaffolds_are_deterministic_reviewable_and_non_executable(tmp_path: Path) -> None:
    left = scaffold_adapter(tmp_path / "left", "fixture-game", "Fixture Game")
    right = scaffold_adapter(tmp_path / "right", "fixture-game", "Fixture Game")
    left_files = {path.relative_to(left).as_posix(): path.read_bytes() for path in left.rglob("*") if path.is_file()}
    right_files = {path.relative_to(right).as_posix(): path.read_bytes() for path in right.rglob("*") if path.is_file()}
    assert left_files == right_files
    assert set(left_files) == ALLOWED_FILES
    assert not any(path.endswith((".py", ".sh", ".js", ".command")) for path in left_files)


def test_scaffold_overwrite_and_symlink_escape_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _scaffold(tmp_path)
    with pytest.raises(ExperimentalAdapterError, match="already exists"):
        scaffold_adapter(tmp_path / "scaffolds", "fixture-game", "Fixture Game")
    root.symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(ExperimentalAdapterError, match="symlink"):
        scaffold_adapter(root, "another-game", "Another Game")


def test_unknown_files_and_source_symlinks_are_refused(tmp_path: Path) -> None:
    source = _scaffold(tmp_path)
    (source / "plugin.py").write_text("print('unsafe')", encoding="utf-8")
    with pytest.raises(ExperimentalAdapterError, match="unknown adapter file"):
        run_conformance(source)
    (source / "plugin.py").unlink()
    fixture = source / "fixtures" / "input-neutral.json"
    fixture.unlink()
    fixture.symlink_to(source / "README.md")
    with pytest.raises(ExperimentalAdapterError, match="symlink"):
        run_conformance(source)


def test_oversized_contract_and_fixture_are_refused_before_parsing(tmp_path: Path) -> None:
    source = _scaffold(tmp_path)
    contract = source / "adapter.yaml"
    contract.write_text("#" * (256 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ExperimentalAdapterError, match="exceeds the .*byte limit"):
        run_conformance(source)

    source = scaffold_adapter(tmp_path / "second", "second-game", "Second Game")
    fixture = source / "fixtures" / "observation-idle.json"
    fixture.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ExperimentalAdapterError, match="exceeds the .*byte limit"):
        run_conformance(source)


def test_conformance_covers_provider_safety_integrity_removal_and_proof_limits(tmp_path: Path) -> None:
    report = run_conformance(_scaffold(tmp_path))
    assert report.overall_pass is True
    assert {item.check_id for item in report.checks} == {
        "schema", "provider_truth", "observation_envelopes", "capability_agreement",
        "ownership_reclaim", "protected_action_refusal", "measurable_goals",
        "evidence_isolation", "persistence_isolation", "installation_integrity",
        "removal", "catalog_labeling", "no_shared_core_edit",
    }
    assert report.proof_limits == PROOF_LIMITS


def test_atomic_install_manifest_inventory_hashes_and_collision_refusal(tmp_path: Path) -> None:
    source = _scaffold(tmp_path)
    installed = install_adapter(source, tmp_path / "installed")
    manifest = json.loads((installed / ".installation.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == ALLOWED_FILES
    assert installation_status(tmp_path / "installed")[0]["integrity"] == "clean"
    with pytest.raises(InstallationRefused, match="collision"):
        install_adapter(source, tmp_path / "installed")


def test_install_rolls_back_when_atomic_promotion_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _scaffold(tmp_path)
    import smb3_agent.experimental_adapters as adapters
    monkeypatch.setattr(adapters.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("fixture failure")))
    with pytest.raises(OSError, match="fixture failure"):
        install_adapter(source, tmp_path / "installed")
    assert not (tmp_path / "installed" / "fixture-game").exists()


def test_install_reports_staging_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _scaffold(tmp_path)
    import smb3_agent.experimental_adapters as adapters

    monkeypatch.setattr(
        adapters.os,
        "replace",
        lambda *_: (_ for _ in ()).throw(OSError("promotion failed")),
    )
    monkeypatch.setattr(
        adapters.shutil,
        "rmtree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup failed")),
    )

    with pytest.raises(ExperimentalAdapterError, match="staging cleanup also failed"):
        install_adapter(source, tmp_path / "installed")


def test_provider_discovery_extends_catalog_without_game_id_branches_or_support_promotion(tmp_path: Path) -> None:
    install_adapter(_scaffold(tmp_path), tmp_path / "installed")
    registry = build_default_catalog_registry(
        experimental_install_root=tmp_path / "installed"
    )
    entry = registry.entry("fixture-game")
    assert isinstance(registry.provider("fixture-game"), ExperimentalCatalogProvider)
    assert entry.implementation_status == "experimental_installed_live_unproven"
    assert entry.availability == "setup_required"
    assert "Experimental" in entry.description
    assert registry.entry("smb3").implementation_status != entry.implementation_status
    assert registry.entry("stardew").implementation_status != entry.implementation_status


def test_modified_unknown_or_ambiguous_installation_refuses_uninstall(tmp_path: Path) -> None:
    installed_root = tmp_path / "installed"
    target = install_adapter(_scaffold(tmp_path), installed_root)
    (target / "README.md").write_text("modified", encoding="utf-8")
    with pytest.raises(RemovalRefused, match="modified"):
        uninstall_adapter(installed_root, "fixture-game")
    assert target.exists()


@pytest.mark.parametrize("active_file", ["active-process.json", "active-authority.json", "active-input.json", "active-session.json"])
def test_active_process_authority_input_or_session_refuses_removal(tmp_path: Path, active_file: str) -> None:
    installed_root = tmp_path / "installed"
    target = install_adapter(_scaffold(tmp_path), installed_root)
    (target / active_file).write_text("{}", encoding="utf-8")
    with pytest.raises(RemovalRefused, match="active process"):
        uninstall_adapter(installed_root, "fixture-game")


def test_clean_removal_has_zero_residual_state_and_preserves_external_evidence_history(tmp_path: Path) -> None:
    source = _scaffold(tmp_path)
    installed_root = tmp_path / "installed"
    target = install_adapter(source, installed_root)
    evidence = tmp_path / "evidence" / "experimental.fixture-game"
    history = tmp_path / "history" / "experimental.fixture-game"
    evidence.mkdir(parents=True)
    history.mkdir(parents=True)
    result = uninstall_adapter(installed_root, "fixture-game")
    assert result["zero_residual"] == {"process": True, "authority": True, "input": True, "session": True}
    assert not target.exists()
    assert evidence.exists() and history.exists() and source.exists()


def test_onboarding_ui_names_all_states_steps_proof_limits_and_narrow_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GAME_COMPANION_EXPERIMENTAL_ROOT", str(tmp_path / "installed"))
    html = render_experimental_onboarding(csrf_token="fixture-token")
    for text in ("Declared", "Conformant", "Live-unproven", "Unsupported", "Scaffolded", "Installed", "Metadata", "Detection", "Observation", "Input", "Safety", "Goals", "Capabilities", "Fixtures", "Scaffold review", "Conformance", "Installation", "Removal"):
        assert text in html
    for limit in PROOF_LIMITS:
        assert limit in html
    assert "@media(max-width:390px)" in html
    assert "<main>" in html
    assert "</main>" in html
    assert 'action="/adapter-remove"' not in html


def test_scenario_contract_agrees_with_conformance_and_proof_limits() -> None:
    scenario = next(item for item in load_scenario_catalog() if item.scenario_id == "adapters.experimental_onboarding_removal")
    assert scenario.capability_status == "implemented_campaign_validation_pending"
    assert scenario.may_count_toward_owner_acceptance is False
    assert set(PROOF_LIMITS).issubset(set(scenario.result_cannot_prove))
