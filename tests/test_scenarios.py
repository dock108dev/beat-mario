from pathlib import Path

import pytest

from smb3_agent.scenarios import (
    EvidenceClassification,
    ScenarioError,
    ScenarioLifecycle,
    ScenarioRunner,
    final_campaign_readiness,
    load_scenario_catalog,
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


def test_final_campaign_readiness_marks_v2_12_ready_and_preserves_later_slice_blockers() -> None:
    readiness = final_campaign_readiness(load_scenario_catalog(CATALOG))
    assert readiness["ready_to_execute"] is False
    assert "stardew.visible_observation@1" not in readiness["capability_blockers"]
    assert "stardew.takeover_reclaim@1" not in readiness["capability_blockers"]
    assert "stardew.show_review_only@1" not in readiness["capability_blockers"]
    assert "stardew.disposable_reset@1" not in readiness["capability_blockers"]
    assert "adapters.mario_stardew_switching@1" not in readiness["capability_blockers"]
    assert "regression.unattended@1" in readiness["capability_blockers"]
