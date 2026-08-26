import json
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from smb3_agent.scenarios import (
    EvidenceClassification,
    PROOF_LIMITS,
    ScenarioError,
    ScenarioLifecycle,
    ScenarioRunner,
    ScenarioStep,
    build_campaign_entry_manifest,
    campaign_contract_hashes,
    final_campaign_readiness,
    load_scenario_catalog,
    scenario_classification_hash,
    scenario_plan,
)


CATALOG = Path("data/scenarios/catalog.yaml")


def test_catalog_retains_required_classification_boundaries() -> None:
    catalog = load_scenario_catalog(CATALOG)
    by_id = {item.scenario_id: item for item in catalog}
    assert by_id["regression.unattended"].evidence_classification is EvidenceClassification.UNATTENDED_REGRESSION
    assert not by_id["regression.unattended"].may_count_toward_owner_acceptance
    assert by_id["campaign.final_owner_acceptance"].owner_participation_required
    assert by_id["campaign.final_owner_acceptance"].capability_status != "available"


def test_owner_required_scenario_fails_closed_when_unattended(tmp_path: Path) -> None:
    scenario = next(item for item in load_scenario_catalog(CATALOG) if item.scenario_id == "takeover.current_session")
    blockers = ScenarioRunner(tmp_path).preflight(scenario, scenario.capability_requirements, unattended=True)
    assert "owner-required scenario cannot run unattended" in blockers


def test_dry_plan_identifies_owner_steps_and_proof_limits() -> None:
    scenario = next(item for item in load_scenario_catalog(CATALOG) if item.scenario_id == "takeover.immediate_reclaim")
    plan = scenario_plan(scenario).to_dict()
    assert any(step["automated"] is False for step in plan["steps"])
    assert "owner acceptance" in " ".join(plan["cannot_prove"])


def test_retry_creates_new_attempt_and_preserves_failure(tmp_path: Path) -> None:
    scenario = next(item for item in load_scenario_catalog(CATALOG) if item.scenario_id == "takeover.process_loss")
    runner = ScenarioRunner(tmp_path)
    first = runner.create_attempt(scenario, {"source": "fixture"})
    runner.transition(first, ScenarioLifecycle.PREFLIGHT_PENDING)
    runner.transition(first, ScenarioLifecycle.READY)
    runner.transition(first, ScenarioLifecycle.PROCESS_LOST, reason="fixture process loss")
    second = runner.retry(first, scenario)
    assert second.attempt_id != first.attempt_id
    assert second.source_identity["retry_of"] == first.attempt_id


def test_terminal_attempt_cannot_be_rewritten_as_success(tmp_path: Path) -> None:
    scenario = next(item for item in load_scenario_catalog(CATALOG) if item.scenario_id == "takeover.process_loss")
    runner = ScenarioRunner(tmp_path)
    attempt = runner.create_attempt(scenario, {"source": "fixture"})
    runner.transition(attempt, ScenarioLifecycle.PREFLIGHT_PENDING)
    runner.transition(attempt, ScenarioLifecycle.READY)
    runner.transition(attempt, ScenarioLifecycle.PROCESS_LOST, reason="lost")
    with pytest.raises(ScenarioError, match="terminal attempts are immutable"):
        runner.transition(attempt, ScenarioLifecycle.COMPLETED)


def test_execution_and_cleanup_failures_retain_traceback_records(tmp_path: Path) -> None:
    source = next(
        item for item in load_scenario_catalog(CATALOG)
        if item.scenario_id == "regression.unattended"
    )
    scenario = replace(
        source,
        capability_status="available",
        capability_requirements=(),
        required_fixtures=(),
        required_local_assets=(),
        automated_steps=(ScenarioStep("explode", "system", "fixture"),),
    )
    runner = ScenarioRunner(tmp_path)
    attempt = runner.create_attempt(scenario, {"source": "fixture"})

    result = runner.execute(
        scenario,
        attempt,
        capabilities=(),
        step_executors={"explode": lambda: (_ for _ in ()).throw(RuntimeError("step boom"))},
        cleanup_action=lambda: (_ for _ in ()).throw(OSError("cleanup boom")),
    )

    assert result.state is ScenarioLifecycle.RETAINED_FOR_REVIEW
    assert [item["phase"] for item in result.failure_details] == ["execution", "cleanup"]
    assert "RuntimeError: step boom" in result.failure_details[0]["traceback"]
    persisted = json.loads(
        (tmp_path / scenario.scenario_id / attempt.attempt_id / "attempt.json").read_text()
    )
    assert persisted["failure_details"][1]["type"] == "OSError"


def _candidate_manifest(catalog) -> dict[str, object]:
    return {
        "schema_version": "game-companion-campaign-entry-manifest/v1",
        "source_commit": "a" * 40,
        "source_tree": "b" * 40,
        "repository_clean": True,
        "created_at": "2026-08-25T00:00:00+00:00",
        "classification_hash": scenario_classification_hash(catalog),
        "contract_hashes": campaign_contract_hashes(),
        "deterministic_evidence": {
            "focused_readiness": {"status": "passed", "test_total": 10},
            "focused_v2": {"status": "passed", "test_total": 366},
            "canonical_non_live": {"status": "passed", "test_total": 666},
        },
        "owner_fields_blank": True,
        "owner_fields_source": [
            "data/scenarios/mario-owner-pilot.yaml",
            "data/scenarios/stardew-owner-pilot.yaml",
        ],
        "campaign_completion": "pending",
        "proof_limits": list(PROOF_LIMITS),
    }


def test_v2_14_implementation_can_be_ready_while_campaign_completion_remains_pending() -> None:
    catalog = load_scenario_catalog(CATALOG)
    readiness = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    assert readiness["implementation_readiness"]["ready"] is True
    assert readiness["campaign_entry_ready"] is True
    assert readiness["campaign_complete"] is False
    assert readiness["campaign_completion"]["complete"] is False
    assert readiness["implementation_blockers"] == []
    assert readiness["candidate_blockers"] == []
    assert {
        "visible_technical",
        "route_reliability",
        "owner_sessions",
        "unattended_regression",
        "experimental_onboarding_removal",
        "final_owner_decision",
    }.issubset(
        {item["phase"] for item in readiness["completion_blockers"] if "phase" in item}
    )


def test_missing_technical_implementation_blocks_campaign_entry() -> None:
    catalog = list(load_scenario_catalog(CATALOG))
    index = next(
        index for index, item in enumerate(catalog)
        if item.scenario_id == "adapters.mario_stardew_switching"
    )
    catalog[index] = replace(catalog[index], capability_status="missing_implementation")
    readiness = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    assert readiness["implementation_readiness"]["ready"] is False
    assert readiness["campaign_entry_ready"] is False
    assert readiness["implementation_blockers"][0]["scenario"] == catalog[index].identity


def test_campaign_validation_pending_is_scheduled_not_falsely_completed() -> None:
    catalog = load_scenario_catalog(CATALOG)
    readiness = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    scheduled = {item["scenario"]: item for item in readiness["scheduled_technical_validations"]}
    assert scheduled["adapters.mario_stardew_switching@1"]["proof_status"] == "pending"
    assert scheduled["regression.unattended@2"]["proof_status"] == "pending"
    assert scheduled["adapters.experimental_onboarding_removal@1"]["proof_status"] == "pending"
    assert all(
        scheduled[identity]["status"] == "implemented_campaign_validation_pending"
        for identity in (
            "adapters.mario_stardew_switching@1",
            "regression.unattended@2",
            "adapters.experimental_onboarding_removal@1",
        )
    )


def test_candidate_prerequisite_live_pending_and_completed_statuses_remain_distinct() -> None:
    catalog = list(load_scenario_catalog(CATALOG))
    switching_index = next(
        index for index, item in enumerate(catalog)
        if item.scenario_id == "adapters.mario_stardew_switching"
    )
    catalog[switching_index] = replace(
        catalog[switching_index],
        capability_status="candidate_prerequisite_blocked",
    )
    blocked = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    assert blocked["implementation_readiness"]["ready"] is True
    assert blocked["campaign_entry_ready"] is False
    assert blocked["candidate_blockers"][0]["reason"] == "candidate_prerequisite_blocked"

    catalog[switching_index] = replace(
        catalog[switching_index],
        capability_status="live_validation_pending",
    )
    pending = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    assert pending["campaign_entry_ready"] is True
    assert any(
        item["scenario"] == catalog[switching_index].identity
        and item["proof_status"] == "pending"
        for item in pending["scheduled_technical_validations"]
    )

    catalog[switching_index] = replace(
        catalog[switching_index],
        capability_status="completed_accepted",
    )
    completed = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    assert not any(
        item["scenario"] == catalog[switching_index].identity
        for item in completed["scheduled_technical_validations"]
    )


def test_pending_final_owner_acceptance_does_not_block_entry_but_blocks_completion() -> None:
    catalog = load_scenario_catalog(CATALOG)
    readiness = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    owner = next(
        item for item in readiness["required_owner_actions"]
        if item["scenario"] == "campaign.final_owner_acceptance@1"
    )
    assert owner["entry_blocker"] is False
    assert owner["completion_required"] is True
    assert readiness["campaign_entry_ready"] is True
    assert any(
        item.get("scenario") == "campaign.final_owner_acceptance@1"
        for item in readiness["completion_blockers"]
    )


@pytest.mark.parametrize(
    ("mutation", "blocker_id"),
    [
        (lambda manifest: manifest.pop("source_commit"), "candidate_identity.commit"),
        (lambda manifest: manifest.update(owner_fields_blank=False), "owner_fields"),
        (lambda manifest: manifest.update(contract_hashes={}), "campaign_contracts"),
        (lambda manifest: manifest.update(repository_clean=False), "candidate_identity.clean"),
    ],
)
def test_missing_candidate_identity_contract_or_blank_owner_guarantee_blocks_entry(
    mutation, blocker_id: str
) -> None:
    catalog = load_scenario_catalog(CATALOG)
    manifest = _candidate_manifest(catalog)
    mutation(manifest)
    readiness = final_campaign_readiness(catalog, manifest)
    assert readiness["campaign_entry_ready"] is False
    assert blocker_id in {item["id"] for item in readiness["candidate_blockers"]}


def test_missing_manifest_fixture_asset_or_safety_requirement_blocks_entry() -> None:
    catalog = list(load_scenario_catalog(CATALOG))
    assert final_campaign_readiness(catalog)["campaign_entry_ready"] is False
    source = catalog[0]
    catalog[0] = replace(
        source,
        required_fixtures=source.required_fixtures + ("data/scenarios/missing-fixture.yaml",),
        required_local_assets=source.required_local_assets + ("artifacts/missing-local-asset",),
    )
    readiness = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    reasons = " ".join(item["reason"] for item in readiness["candidate_blockers"])
    assert "missing fixture" in reasons
    assert "missing local asset" in reasons
    switching_index = next(
        index for index, item in enumerate(catalog)
        if item.scenario_id == "adapters.mario_stardew_switching"
    )
    catalog[switching_index] = replace(catalog[switching_index], safety_requirements=())
    readiness = final_campaign_readiness(catalog, _candidate_manifest(catalog))
    assert any(
        item["reason"] == "missing campaign safety requirements"
        for item in readiness["implementation_blockers"]
    )


def test_readiness_hash_and_output_are_deterministic_and_states_do_not_collapse() -> None:
    catalog = load_scenario_catalog(CATALOG)
    manifest = _candidate_manifest(catalog)
    first = final_campaign_readiness(catalog, manifest)
    second = final_campaign_readiness(reversed(catalog), manifest)
    assert first == second
    assert first["classification_hash"] == scenario_classification_hash(catalog)
    assert first["implementation_readiness"]["ready"] is True
    assert first["campaign_entry_readiness"]["ready"] is True
    assert first["campaign_completion"]["complete"] is False
    assert first["proof_limits"]


def test_candidate_manifest_builder_binds_clean_exact_identity_hashes_and_blank_owner_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import smb3_agent.scenarios as scenarios_module

    catalog = load_scenario_catalog(CATALOG)
    values = {
        ("status", "--porcelain", "--untracked-files=all"): "",
        ("rev-parse", "HEAD"): "c" * 40,
        ("rev-parse", "HEAD^{tree}"): "d" * 40,
    }
    monkeypatch.setattr(scenarios_module, "_git_value", lambda *args: values[args])
    payload = build_campaign_entry_manifest(
        catalog,
        focused_readiness_total=25,
        focused_v2_total=400,
        canonical_total=700,
    )
    assert payload["source_commit"] == "c" * 40
    assert payload["source_tree"] == "d" * 40
    assert payload["repository_clean"] is True
    assert payload["owner_fields_blank"] is True
    assert payload["campaign_completion"] == "pending"
    assert payload["deterministic_evidence"]["canonical_non_live"]["test_total"] == 700


def test_readiness_gate_exits_nonzero_and_emits_structured_blocker_without_manifest() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "smb3_agent",
            "scenario",
            "final-campaign-readiness",
            "--gate",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["campaign_entry_ready"] is False
    assert payload["candidate_blockers"][0]["id"] == "candidate_manifest"
