"""Synthetic watering behavior checks; no real-game evidence."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from smb3_agent.request_planning import Planner
from smb3_agent.stardew_adapter import InputKind
from smb3_agent.conversation_service import StardewConversationService
from test_stardew_conversation import FakeStardewRuntime, identity, live_context, request
from test_stardew_runtime import configured


def activity_context():
    context = live_context()
    targets = [dict(t, tile_x=i, tile_y=1, label=f"crop in row 1 column {i}")
               for i, t in enumerate(context.observation["targets"])]
    return replace(context, observation={**context.observation, "watering_activity": True,
        "targets": targets, "water": 5, "energy": 20, "energy_cost_upper_bound": 2,
        "selected_tool": "watering_can"})


def test_observed_patch_skips_wet_and_needs_no_ids():
    result = Planner().plan("Please water the crops", activity_context())
    assert not result.plan.ambiguities
    assert result.plan.actions[0].target_ids == ("c1",)
    assert result.plan.resource_limits["maximum_seconds"] == 120
    assert "two minutes" in result.message


@pytest.mark.parametrize("change,remedy", [({"water": 0}, "Refill"), ({"energy": 1}, "energy"),
    ({"energy_cost_upper_bound": None}, "energy"), ({"selected_tool": "axe"}, "Select the watering can")])
def test_resource_remedy_before_approval(change, remedy):
    ctx = activity_context()
    result = Planner().plan("Water crops", replace(ctx, observation={**ctx.observation, **change}))
    assert any(remedy in a for a in result.plan.ambiguities)


def test_ambiguous_patches_unknown_tiles_and_species():
    ctx = activity_context()
    targets = ctx.observation["targets"]
    other = {**targets[0], "id": "far", "tile_x": 9}
    result = Planner().plan("Water crops", replace(ctx, observation={**ctx.observation, "targets": [*targets, other]}))
    assert "Several dry patches" in result.message
    result = Planner().plan("Water all observed crops", replace(ctx, observation={**ctx.observation,
        "targets": [{**targets[0], "watered": None}]}))
    assert "uncertain water state" in result.message
    assert "identity is unconfirmed" in Planner().plan("Water the tomatoes", ctx).message


def test_yes_bound_to_display_and_question_releases_input(tmp_path):
    runtime = FakeStardewRuntime()
    runtime.context = activity_context()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    state = request(service, "Water crops")
    with pytest.raises(ValueError, match="displayed plan"):
        service.dispatch("message", {"text": "yes"})
    service.dispatch("message", {"text": "yes", **identity(state)})
    assert runtime.calls[-1][0] == "start"
    result = request(service, "what is left?")
    assert runtime.calls[-1][0] == "pause"
    assert not result["reviewed"]
    reopened = StardewConversationService(runtime=FakeStardewRuntime(), artifacts_root=tmp_path)
    assert reopened.snapshot()["plan"] is None
    assert reopened.snapshot()["history"][0]["reviewed_plan"]["resource_limits"]["maximum_seconds"] == 120


def test_subset_completes_without_claiming_other_dry_crops(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    state[0] = replace(state[0], crops=(*state[0].crops, replace(state[0].crops[0], crop_id="other", tile_x=-1)))
    runtime.navigator.centers[(-1, 0)] = (5, 5)
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id, resource_limits={"maximum_seconds": 120, "minimum_energy": 1})
    runtime.review(plan)
    # Preserve the untouched neighbor in the simulated game's post-frame.
    original = runtime.driver._emitters[InputKind.MOUSE]
    def emit(command):
        neighbor = state[0].crops[1]
        original(command)
        state[0] = replace(state[0], crops=(*state[0].crops, neighbor))
    runtime.driver._emitters[InputKind.MOUSE] = emit
    runtime.start(plan, background=False)
    assert datetime.fromisoformat(runtime.controller.authorization.expires_at) - datetime.now(timezone.utc) < timedelta(seconds=121)
    runtime.tick()
    runtime.tick()
    assert runtime.status == "completed"
    assert runtime.snapshot()["ledger"]["watered_count"] == 1
    assert not state[0].crops[1].watered
    assert len(commands) == 1


def test_two_minute_expiry_and_changed_resources_emit_nothing(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    plan = replace(plan, resource_limits={"maximum_seconds": 120})
    runtime.review(plan)
    state[0] = replace(state[0], tool=replace(state[0].tool, watering_can_units=0))
    with pytest.raises(ValueError, match="changed since review"):
        runtime.start(plan, background=False)
    assert not commands
    state[0] = replace(state[0], tool=replace(state[0].tool, watering_can_units=5))
    runtime.start(plan, background=False)
    runtime.controller.authorization = replace(runtime.controller.authorization,
        expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
    runtime.tick()
    assert not commands and runtime.controller.authorization is None
    assert runtime.snapshot()["handback_confirmed"]


def test_route_remedy_and_changed_plan_cannot_use_old_yes(tmp_path):
    ctx = activity_context()
    result = Planner().plan("Water crops", replace(ctx, observation={**ctx.observation,
        "watering_route_ready": False, "route_remedy": "no supported path"}))
    assert "Reposition" in result.message
    runtime = FakeStardewRuntime()
    runtime.context = ctx
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    old = request(service, "Water crops")
    new = request(service, "Keep at least 19 energy")
    with pytest.raises(ValueError, match="displayed plan"):
        service.dispatch("message", {"text": "yes", **identity(old)})
    with pytest.raises(ValueError, match="resource limits"):
        service.dispatch("message", {"text": "yes", **identity(new)})
    assert not any(call[0] == "start" for call in runtime.calls)


def test_last_observed_patch_labels_remain_stable_without_authority(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    original = state[0].crops[0]
    runtime.screen = replace(state[0], crops=(original,
        replace(original, crop_id="adjacent", tile_x=2, watered=True),
        replace(original, crop_id="far", tile_x=9)))
    context = runtime.planning_context()
    assert [t["patch"] for t in context.observation["targets"]] == ["left patch", "left patch", "right patch"]
    runtime.screen = replace(runtime.screen, observed_at=(datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat())
    stale = runtime.planning_context()
    assert stale.observation["targets"] == context.observation["targets"]
    assert not stale.observation["validated"] and stale.observation_id is None
    assert not commands


def test_natural_progress_question_does_not_reobserve_or_replan(tmp_path):
    runtime = FakeStardewRuntime()
    runtime.context = activity_context()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    before = request(service, "Water crops")
    calls = len(runtime.calls)
    answer = request(service, "How much is left?")
    assert answer["plan"] == before["plan"]
    assert len(runtime.calls) == calls
    assert answer["messages"][-1]["kind"] == "advisory"
