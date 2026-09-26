from dataclasses import replace
import json

import pytest

from smb3_agent.commands import parse_command
from smb3_agent.request_planning import ConversationPlan, Planner, PlanningContext


def context(**changes):
    values = dict(game_id="mario", conversation_id="conversation-a", session_id="session-a", observation_id="observation-a",
                  observation={"game_id": "mario", "session_id": "session-a", "observation_id": "observation-a", "fresh": True})
    values.update(changes)
    return PlanningContext(**values)


@pytest.mark.parametrize("wording", ["faster", "fastest", "quickest", "I want the shortest route", "Optimize the route", "Can you use the quickest route?"])
def test_optimization_intents_resolve_real_base_without_inventing_route(wording):
    result = Planner().plan(wording, context())
    assert result.plan.normalized_intent == "optimize_time"
    assert result.plan.base_route_id == "world_8_finish_game"
    assert result.plan.variant_id is None
    assert "No optimized variant" in result.message
    assert result.plan.execution_eligibility == "requires_runtime_validation"
    assert result.plan.authorization_scope["granted"] is False


def test_plan_contract_round_trip_and_no_authority_from_storage():
    result = Planner().plan("100% clear", context())
    payload = json.loads(json.dumps(result.plan.to_dict()))
    assert payload["completion_coverage"] == "unknown"
    assert "does not establish 100%" in payload["fallback_explanation"]
    payload["authorization_scope"]["granted"] = True
    payload["execution_eligibility"] = "authorized"
    restored = ConversationPlan.from_dict(payload)
    assert not restored.authorization_scope["granted"]
    assert restored.execution_eligibility == "requires_runtime_validation"
    assert restored.original_request == "100% clear"
    assert restored.observation_id == "observation-a"


def test_full_completion_measurement_needs_finite_inventory():
    result = Planner().plan("Measure 100% completion", context())
    assert result.kind == "clarification"
    assert result.plan.execution_eligibility == "blocked"
    assert "finite observable" in result.message


@pytest.mark.parametrize("text", [
    "Take the opening hop, then stop after the opening section",
    "Please jump along the opening path and stop after the opening",
    "Could you take the early jump and stop after the first hop?",
])
def test_natural_multi_action_path_and_stop(text):
    plan = Planner().plan(text, context()).plan
    assert plan.actions[0].parameters["path_choice"] == "opening_hop"
    assert plan.stop_point == "world_1_1_opening_end"
    assert plan.effective_boundary == "world_1_1_opening"


def test_followup_correction_preserves_intent_revision_and_existing_stop():
    planner = Planner()
    original = planner.plan("Quickest route; take the opening hop then stop after the opening", context()).plan
    ctx = context(current_plan=original, reviewed_edit_scope=("path", "stop_point", "speed"))
    result = planner.plan("Actually, don't take the opening hop; use the default path", ctx)
    assert result.kind == "edit" and result.apply_requested
    assert result.plan.actions[0].parameters["path_choice"] == "default"
    assert result.plan.normalized_intent == "optimize_time"  # path is not objective
    assert result.plan.stop_point == "world_1_1_opening_end"
    assert result.plan.revision == 2 and result.plan.parent_revision == 1
    assert result.plan.plan_id == original.plan_id
    assert result.plan.original_request.startswith("Actually")


@pytest.mark.parametrize("text", ["What if we take the opening hop?", "Would the opening hop be quicker?", "Maybe take the opening hop", "Should we stop after the opening?"])
def test_advisory_never_requests_application(text):
    planner = Planner()
    current = planner.plan("base route", context()).plan
    result = planner.plan(text, context(current_plan=current, reviewed_edit_scope=("path", "stop_point", "objective")))
    assert result.kind == "advisory"
    assert not result.apply_requested
    assert result.control is None


def test_conditional_edit_and_material_expansion_need_review():
    planner = Planner()
    current = planner.plan("stop after opening", context()).plan
    ctx = context(current_plan=current, reviewed_edit_scope=("path", "stop_point"))
    conditional = planner.plan("Take the opening hop if it is safe", ctx)
    assert conditional.kind == "clarification" and not conditional.apply_requested
    expanded = planner.plan("Continue to the ending", ctx)
    assert expanded.plan.stop_point == "full_route"
    assert not expanded.apply_requested


def test_advisory_question_does_not_become_a_pause():
    result = Planner().plan("Should we pause?", context())
    assert result.kind == "advisory" and result.control is None


@pytest.mark.parametrize("text,action", [("Stop", "stop"), ("hold on", "pause"), ("Could you pause?", "pause"), ("carry on", "resume"), ("Give me back control", "reclaim"), ("Cancel that", "cancel_pending"), ("Undo the last change", "revert")])
def test_controls_use_separate_typed_request(text, action):
    result = Planner().plan(text, context())
    assert result.control == {"action": action}
    assert result.plan is None


@pytest.mark.parametrize("text,speed", [("play at normal speed", 1), ("Use turbo", "turbo"), ("faster playback", "turbo"), ("switch to uncapped speed", "turbo")])
def test_supported_speed_request_is_not_route_optimization(text, speed):
    result = Planner().plan(text, context())
    assert result.control == {"action": "speed", "speed": speed}
    assert "awaits runtime acknowledgment" in result.message


@pytest.mark.parametrize("text", ["play at 2x", "set speed to 4x", "double the speed"])
def test_numeric_unverified_speed_rejected_visibly(text):
    result = Planner().plan(text, context())
    assert result.kind == "clarification" and result.control is None
    assert "unsupported" in result.message


def test_negated_speed_does_not_emit_control():
    result = Planner().plan("Don't play at turbo", context())
    assert result.control is None and not result.apply_requested


@pytest.mark.parametrize("changes", [
    {"observation_fresh": False},
    {"observation": {"game_id": "stardew"}},
    {"observation": {"session_id": "another"}},
    {"selected_targets": ({"id": "world_1_1_exit", "game_id": "stardew"},)},
    {"selected_targets": ({"id": "world_1_1_exit", "observation_id": "old"},)},
])
def test_stale_and_wrong_game_references_are_blocked(changes):
    result = Planner().plan("Take the selected path", context(**changes))
    assert result.kind == "clarification" and not result.apply_requested and result.plan is None


def test_prior_session_and_conversation_are_not_inherited():
    planner = Planner()
    original = planner.plan("base route", context()).plan
    for field in ("session_id", "conversation_id", "game_id"):
        ctx = replace(context(current_plan=original), **{field: "another"})
        result = planner.plan("Take the other path", ctx)
        assert result.kind == "clarification" and result.plan is None


def test_selected_observable_target_resolves_to_adapter_capability():
    result = Planner().plan("Stop there", context(selected_targets=({"id": "world_1_1_exit", "visible": True},)))
    assert result.plan.stop_point == "world_1_1_exit"
    unknown = Planner().plan("Take that one", context(selected_targets=({"id": "unknown-tunnel", "visible": True},)))
    assert unknown.kind == "clarification" and unknown.plan.execution_eligibility == "blocked"


def test_unknown_extra_action_is_not_silently_dropped():
    result = Planner().plan("Take the opening hop and swim across the ocean", context())
    assert result.kind == "clarification"
    assert result.plan.unsupported_parts
    assert not result.apply_requested


def test_legacy_command_parser_is_preserved():
    assert parse_command("show me the route at 2x").speed == 2
    assert parse_command("run world 1 king 3 times").attempts == 3


@pytest.mark.parametrize("wording", ["base", "normal clear", "default route"])
def test_plain_base_selection(wording):
    result = Planner().plan(wording, context())
    assert result.kind == "proposal"
    assert result.plan.normalized_intent == "base_route"
    assert result.plan.stop_point == "full_route"


def test_opening_hop_is_only_authorizable_with_opening_stop():
    result = Planner().plan("Take the opening hop", context())
    assert result.plan.stop_point == "world_1_1_opening_end"
    assert "unvalidated" in result.message
    longer = Planner().plan("Take the opening hop then stop after World 1-1", context())
    assert longer.kind == "clarification"
    assert not longer.apply_requested


def test_planner_adapter_registry_is_injectable_without_game_specific_branch():
    from smb3_agent.request_planning import AdapterProposal
    class Adapter:
        help_text = "Example adapter"
        def propose(self, text, context):
            return AdapterProposal("example_task", text, (), base_task_id="example", execution_eligibility="unavailable_live")
    result = Planner(adapters={"example": Adapter()}).plan("Do the task", PlanningContext(game_id="example"))
    assert result.plan.game_id == "example"
    assert result.plan.base_task_id == "example"
    assert result.plan.authorization_scope["granted"] is False


@pytest.mark.parametrize("text,choice", [
    ("Take the opening hop instead of the default path", "opening_hop"),
    ("Use the default path rather than the opening hop", "default"),
    ("Don't use the default path; take the opening hop instead", "opening_hop"),
])
def test_contrasted_corrections_do_not_invert_the_requested_choice(text, choice):
    result = Planner().plan(text, context())
    assert result.kind == "proposal"
    assert result.plan.actions[0].parameters["path_choice"] == choice


@pytest.mark.parametrize("wording,path,stop", [
    ("Default route; stop after the opening", "default", "world_1_1_opening_end"),
    ("Default route; stop after World 1-1", "default", "world_1_1_exit"),
    ("Default route", "default", "full_route"),
    ("Opening hop; stop after the opening", "opening_hop", "world_1_1_opening_end"),
])
def test_planner_output_passes_authoritative_runtime_contract(wording, path, stop):
    from smb3_agent.mario_plan_runtime import runtime_fields

    plan = Planner().plan(wording, context()).plan
    fields = runtime_fields(plan)
    assert fields["path_choice"] == path
    assert fields["stop_point"] == stop
