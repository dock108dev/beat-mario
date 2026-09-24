from dataclasses import replace

from smb3_agent.request_planning import Planner, PlanningContext


def target(identity, kind, **kwargs):
    return {"id": identity, "kind": kind, "visible": True, "confidence": 1, **kwargs}


def farm_context(selected=None, targets=None, **kwargs):
    observed = targets or [target("crop-north", "crop", patch="north", ready=True, planted=True),
                           target("crop-south", "crop", patch="south", ready=False, planted=True),
                           target("plot-a", "plot", patch="east", planted=False),
                           target("debris-a", "debris", patch="west")]
    return PlanningContext(game_id="stardew", conversation_id="farm-conversation", session_id="fixture-session",
                           observation_id="fixture-observation", observation={"source": "fixture", "targets": observed},
                           selected_targets=tuple(selected if selected is not None else observed), **kwargs)


def test_ordered_farm_routine_and_water_recomputation_stay_fixture_only():
    result = Planner().plan("Harvest ready crops, then plant parsnip seeds in selected plots, then water them and clear selected debris", farm_context())
    assert result.kind == "proposal", result.message
    assert [action.kind for action in result.plan.actions] == ["harvest", "plant", "water", "clear"]
    assert result.plan.actions[0].target_ids == ("crop-north",)
    plant = result.plan.actions[1]
    assert plant.parameters["seed_type"] == "parsnip"
    assert plant.parameters["owned_seeds_only"]
    water = result.plan.actions[2]
    assert water.parameters["recompute_after_planting"]
    assert water.target_ids == plant.target_ids
    assert result.plan.execution_eligibility == "unavailable_live"
    assert result.plan.evidence_status == "fixture_only"
    assert result.plan.authorization_scope["granted"] is False


def test_other_patch_and_seed_corrections_use_context():
    planner = Planner()
    ctx = farm_context()
    first = planner.plan("Water the north patch", ctx).plan
    corrected = planner.plan("Actually the other patch", replace(ctx, current_plan=first))
    assert corrected.plan.actions[0].target_ids == ("crop-south",)
    assert corrected.plan.parent_revision == first.revision
    plant = planner.plan("Plant parsnip seeds in selected plots", ctx).plan
    corrected_seed = planner.plan("Use potato seeds instead", replace(ctx, current_plan=plant))
    assert corrected_seed.plan.actions[0].parameters["seed_type"] == "potato"
    assert corrected_seed.plan.actions[0].target_ids == plant.actions[0].target_ids


def test_negated_actions_remove_future_step_without_undoing_history():
    planner = Planner()
    ctx = farm_context()
    first = planner.plan("Water selected crops and harvest ready crops", ctx).plan
    result = planner.plan("Actually don't harvest; just water the north patch", replace(ctx, current_plan=first))
    assert [action.kind for action in result.plan.actions] == ["water"]
    assert "do_not:harvest" in result.plan.protected_choices
    assert result.plan.actions[0].target_ids == ("crop-north",)


def test_leave_selected_crops_protects_subset_and_preserves_others():
    planner = Planner()
    ctx = farm_context()
    first = planner.plan("Water selected crops", ctx).plan
    chosen = [ctx.observation["targets"][0]]
    result = planner.plan("Leave those crops alone", replace(ctx, current_plan=first, selected_targets=tuple(chosen)))
    assert result.plan.actions[0].target_ids == ("crop-south",)
    assert "leave_untouched:crop-north" in result.plan.protected_choices


def test_ambiguous_other_patch_requires_selection():
    ctx = farm_context(targets=[target("c1", "crop", patch="north"), target("c2", "crop", patch="south"), target("c3", "crop", patch="west")])
    first = Planner().plan("Water the north patch", ctx).plan
    result = Planner().plan("The other patch instead", replace(ctx, current_plan=first))
    assert result.kind == "clarification"
    assert "Select the other patch" in result.message


def test_unknown_seed_and_missing_targets_need_material_clarification():
    result = Planner().plan("Plant those", farm_context(selected=[]))
    assert result.kind == "clarification"
    assert "seed type" in result.message
    assert "No matching" in result.message


def test_obscured_and_foreign_targets_fail_closed():
    for selected in [target("c1", "crop", visible=False), target("c1", "crop", observation_id="old")]:
        result = Planner().plan("Water these crops", farm_context(selected=[selected], targets=[selected]))
        assert result.kind == "clarification"
        assert not result.apply_requested


def test_farm_question_retains_preview_without_live_authority():
    result = Planner().plan("Could we harvest the ready crops?", farm_context())
    assert result.kind == "advisory"
    assert not result.apply_requested and result.control is None
    assert result.plan.authorization_scope["granted"] is False


def test_limit_correction_does_not_protect_every_selected_target():
    planner = Planner()
    ctx = farm_context()
    first = planner.plan("Water the north patch", ctx).plan
    result = planner.plan("Leave at least 20 energy", replace(ctx, current_plan=first))
    assert result.plan.actions == first.actions
    assert result.plan.resource_limits["minimum_energy"] == 20


def test_unimplemented_actions_and_cross_game_reference_stay_visible():
    result = Planner().plan("Water selected crops and buy more seeds", farm_context())
    assert result.kind == "clarification" and result.plan.unsupported_parts
    other = Planner().plan("Use Mario's opening hop", farm_context())
    assert other.kind == "clarification" and "Mario" in other.message


def test_no_observations_remains_proposal_without_accessing_saves():
    result = Planner().plan("Water the crops", PlanningContext(game_id="stardew"))
    assert result.kind == "clarification"
    assert result.plan.evidence_status == "proposal_only"
    assert result.plan.execution_eligibility == "blocked"


def test_extra_unknown_farm_task_is_not_silently_discarded():
    result = Planner().plan("Water selected crops then pet the animals", farm_context())
    assert result.kind == "clarification"
    assert any("pet the animals" in part for part in result.plan.unsupported_parts)
