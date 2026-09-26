"""Synthetic contract checks, explicitly not Stardew live qualification."""
from dataclasses import replace

import pytest

from smb3_agent.request_planning import PlannedAction, Planner
from smb3_agent.stardew_adapter import CropObservation, StardewAdapterError
from smb3_agent.stardew_farm_navigation import FarmNavigator
from smb3_agent.stardew_farm_tasks import FarmLedger, FarmObservation, FarmTarget, InventorySlot
from test_stardew_runtime import configured


def routine(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    ref = state[0].screenshot_references[0]
    slots = tuple(InventorySlot(i, item, count, ref) for i, (item, count) in enumerate(
        [("axe", 1), ("parsnip_seeds", 2), ("watering_can", 1)] + [(None, 0)]*9))
    farm = FarmObservation((FarmTarget("crop", 1, 0, "mature", "parsnip", evidence_reference=ref),
                            FarmTarget("twig", 0, 1, "debris", "twig", evidence_reference=ref)),
                           slots, 12, 2, "spring", 5, 360, "synthetic-contract-test")
    state[0] = replace(state[0], farm=farm, position=replace(state[0].position, world_pixel_x=0,
        world_pixel_y=0, camera_origin_x=0, camera_origin_y=0, pixel_uncertainty=1))
    runtime.navigator = FarmNavigator({"poses": {"home": [0, 0]}, "edges": [], "watering": {},
        "return_pose": "home", "farm_approaches": {k: {target: {"pose": "home", "offset": [0, 0]}}
        for k, target in [("harvest", "crop"), ("plant", "crop"), ("water", "crop"), ("clear", "twig")]},
        "inventory_slot_points": {0: [5, 90], 1: [15, 90], 2: [25, 90]}})
    def emit(command):
        commands.append(command)
        before = state[0]
        f = before.farm
        targets, inventory = list(f.targets), list(f.inventory)
        energy, tool = before.energy, before.tool
        if command.purpose == "select_farm_item":
            slot = {5: 0, 15: 1, 25: 2}[command.target[0]]
            state[0] = replace(before, farm=replace(f, selected_slot=slot),
                               tool=replace(tool, selected_tool=inventory[slot].item))
            return
        index = next(i for i, t in enumerate(targets) if t.target_id == command.reviewed_crop_id)
        target = targets[index]
        if command.purpose == "harvest_crop":
            targets[index] = replace(target, state="empty_tilled", species=None)
            inventory[3] = replace(inventory[3], item="parsnip", count=1)
        elif command.purpose == "plant_seed":
            targets[index] = replace(target, state="immature", species="parsnip")
            inventory[1] = replace(inventory[1], count=inventory[1].count-1)
        elif command.purpose == "water_crop":
            targets[index] = replace(target, watered=True)
            energy -= 2
            tool = replace(tool, watering_can_units=tool.watering_can_units-1, tool_uses=tool.tool_uses+1)
        elif command.purpose == "clear_debris":
            targets[index] = replace(target, state="cleared", species=None)
            inventory[4] = replace(inventory[4], item="wood", count=1)
            energy -= 2
        crops = tuple(CropObservation(t.target_id, t.tile_x, t.tile_y, True, t.watered, False, 1, ref)
                      for t in targets if t.planted)
        state[0] = replace(before, crops=crops, energy=energy, tool=tool,
                           farm=replace(f, targets=tuple(targets), inventory=tuple(inventory)))
    # The public driver's configured callbacks, not an alternative executor.
    runtime.driver = type(runtime.driver)(keyboard=emit, mouse=emit, neutralizer=lambda: None)
    runtime.observe()
    actions = (PlannedAction("harvest", "harvest", ("crop",)),
               PlannedAction("plant", "plant", ("crop",), {"seed_type": "parsnip", "seed_count": 1}),
               PlannedAction("water", "water", ("crop",)), PlannedAction("clear", "clear", ("twig",)))
    plan = replace(plan, observation_id=runtime.screen.observation_id, actions=actions)
    runtime.review(plan)
    return runtime, plan, state, commands


def test_shared_runtime_combined_crop_set_inventory_and_handback(tmp_path):
    runtime, plan, state, commands = routine(tmp_path)
    runtime.start(plan, background=False)
    for _ in range(12):
        if runtime.status != "running":
            break
        runtime.tick()
    result = runtime.snapshot()
    assert result["status"] == "completed", result["reason"]
    ledger = result["ledger"]
    assert len(ledger["confirmed_steps"]) == 4
    assert ledger["harvested_ids"] == ledger["newly_planted_ids"] == ["crop"]
    assert ledger["cleared_ids"] == ["twig"]
    assert ledger["seed_consumed"] == ledger["can_water_consumed"] == 1
    assert ledger["energy_spent"] == 4
    assert ledger["current_inventory"]["parsnip"] == ledger["current_inventory"]["wood"] == 1
    assert result["owner"] == "player" and result["handback_confirmed"]
    assert not result["outcome"]["owner_acceptance"]


def test_typed_combined_plan_uses_same_runtime_and_records_dependencies(tmp_path):
    runtime, _, state, commands = routine(tmp_path)
    result = Planner().plan("Harvest crop, then plant parsnip seeds on crop, then water them and clear twig and return to the farmhouse entrance.",
                            replace(runtime.planning_context(conversation_id="conversation"), current_plan=None))
    assert result.kind == "proposal", result.message
    plan = result.plan
    assert not plan.ambiguities and not plan.unsupported_parts
    assert plan.execution_eligibility == "requires_runtime_validation"
    assert "harvested_plot_observed_empty_not_regrowing" in plan.actions[1].preconditions
    runtime.review(plan)
    runtime.start(plan, background=False)
    for _ in range(12):
        if runtime.status == "running":
            runtime.tick()
    assert runtime.status == "completed", runtime.reason


def test_b3_observation_cannot_enable_b4_actions(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    result = Planner().plan("Harvest crop and return to the farmhouse entrance.", runtime.planning_context(conversation_id="conversation"))
    assert result.plan.execution_eligibility == "unavailable_live"
    runtime.review(result.plan)
    with pytest.raises(StardewAdapterError, match="qualified B4"):
        runtime.start(result.plan, background=False)
    assert not commands


@pytest.mark.parametrize("issue,match", [("immature", "mature"), ("full", "capacity"),
    ("no_seeds", "seed shortage"), ("no_tool", "tool"), ("protected", "protected"),
    ("season", "spring"), ("unknown_inventory", "inventory"), ("energy", "reserve")])
def test_ineligible_routines_emit_nothing(tmp_path, issue, match):
    runtime, plan, state, commands = routine(tmp_path)
    f = state[0].farm
    if issue == "immature":
        f = replace(f, targets=(replace(f.targets[0], state="immature"), f.targets[1]))
    elif issue == "full":
        f = replace(f, inventory=tuple(replace(s, item="stone", count=999) if s.item is None else s for s in f.inventory))
    elif issue in {"no_seeds", "no_tool"}:
        item = "parsnip_seeds" if issue == "no_seeds" else "axe"
        f = replace(f, inventory=tuple(replace(s, item=None, count=0) if s.item == item else s for s in f.inventory))
    elif issue == "protected":
        f = replace(f, targets=(f.targets[0], replace(f.targets[1], protected=True)))
    elif issue == "season":
        f = replace(f, season="fall")
    elif issue == "unknown_inventory":
        f = replace(f, inventory=f.inventory[:-1])
    elif issue == "energy":
        state[0] = replace(state[0], energy=0)
    state[0] = replace(state[0], farm=f)
    with pytest.raises(StardewAdapterError, match=match):
        FarmLedger.from_plan(plan, state[0])
    assert not commands


def test_harvest_without_inventory_gain_remains_unconfirmed(tmp_path):
    runtime, plan, state, commands = routine(tmp_path)
    runtime.start(plan, background=False)
    original = runtime.observer
    def unknown_gain():
        value = original()
        f = value.farm
        if f.targets[0].state == "empty_tilled":
            f = replace(f, inventory=tuple(replace(s, item=None, count=0) if s.item == "parsnip" else s for s in f.inventory))
        return replace(value, farm=f)
    runtime.observer = unknown_gain
    runtime.tick()
    assert runtime.status == "stopped"
    assert runtime.snapshot()["ledger"]["remaining_count"] == 4
    assert runtime.snapshot()["handback_confirmed"]
    assert len(commands) == 1


def test_partial_harvest_pause_preserves_ledger_and_no_authority(tmp_path):
    runtime, plan, state, commands = routine(tmp_path)
    runtime.start(plan, background=False)
    runtime.tick()
    runtime.control("pause")
    assert runtime.snapshot()["ledger"]["harvested_ids"] == ["crop"]
    assert runtime.snapshot()["ledger"]["remaining_count"] == 3
    assert runtime.controller.authorization is None
    runtime.tick()
    assert len(commands) == 1


def test_already_wet_replanted_plot_needs_no_extra_water(tmp_path):
    runtime, plan, state, commands = routine(tmp_path)
    state[0] = replace(state[0], farm=replace(state[0].farm, targets=(
        replace(state[0].farm.targets[0], watered=True), state[0].farm.targets[1])),
        crops=(replace(state[0].crops[0], watered=True),))
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id)
    runtime.review(plan)
    runtime.start(plan, background=False)
    for _ in range(12):
        if runtime.status == "running":
            runtime.tick()
    assert runtime.status == "completed", runtime.reason
    assert runtime.snapshot()["ledger"]["steps"][2]["status"] == "already_satisfied"
    assert not any(c.purpose == "water_crop" for c in commands)


def completed_at_return(tmp_path):
    runtime, plan, state, commands = routine(tmp_path)
    runtime.start(plan, background=False)
    for _ in range(12):
        if runtime.controller.operator.ledger.remaining_count == 0:
            break
        runtime.tick()
    assert runtime.status == "running"
    assert runtime.controller.operator.ledger.remaining_count == 0
    nav = runtime.navigator
    nav.poses["approach"] = (0, 48)
    nav._last_node, nav._waypoint = "approach", "home"
    state[0] = replace(state[0], position=replace(state[0].position,
        world_pixel_x=-5, world_pixel_y=-2, pixel_uncertainty=2.5,
        at_farmhouse_entrance=True))
    # Retained post-navigation state, already reconciled before this tick.
    runtime.screen = state[0]
    return runtime, state, commands


def test_qualified_75px_final_return_has_no_alignment_and_independent_verification(tmp_path):
    runtime, state, commands = completed_at_return(tmp_path)
    before = len(commands)
    frames = []
    observer = runtime.observer
    def observed():
        frame = observer()
        frames.append(frame.observation_id)
        return frame
    runtime.observer = observed
    runtime.tick()
    assert runtime.status == "completed", runtime.reason
    assert len(commands) == before
    assert len(set(frames)) >= 2
    assert runtime.snapshot()["neutralized"] and runtime.snapshot()["handback_confirmed"]


@pytest.mark.parametrize("entrance", [False, True])
def test_retained_overshoot_refuses_without_input(tmp_path, entrance):
    runtime, state, commands = completed_at_return(tmp_path)
    state[0] = replace(state[0], position=replace(state[0].position,
        world_pixel_x=14.5, at_farmhouse_entrance=entrance))
    runtime.screen = state[0]
    before = len(commands)
    runtime.tick()
    assert runtime.status == "stopped"
    assert "outside the qualified" in runtime.reason
    assert len(commands) == before


@pytest.mark.parametrize("stale_frame", [1, 2])
def test_stale_arrival_or_independent_final_frame_cannot_complete(tmp_path, stale_frame):
    from datetime import datetime, timedelta, timezone
    runtime, state, commands = completed_at_return(tmp_path)
    observer = runtime.observer
    calls = [0]
    def observed():
        calls[0] += 1
        frame = observer()
        if calls[0] == stale_frame:
            frame = replace(frame, observed_at=(datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat())
        return frame
    runtime.observer = observed
    before = len(commands)
    runtime.tick()
    assert runtime.status == "stopped" and "stale" in runtime.reason
    assert len(commands) == before


def test_incomplete_actions_at_entrance_do_not_complete(tmp_path):
    runtime, plan, state, commands = routine(tmp_path)
    runtime.start(plan, background=False)
    runtime.tick()
    assert runtime.status == "running"
    assert runtime.controller.operator.ledger.remaining_count == 3
    assert commands[0].purpose == "harvest_crop"


def test_independent_final_frame_outside_entrance_cannot_complete(tmp_path):
    runtime, state, commands = completed_at_return(tmp_path)
    observer = runtime.observer
    calls = [0]
    def observed():
        calls[0] += 1
        frame = observer()
        if calls[0] >= 2:
            frame = replace(frame, position=replace(frame.position,
                world_pixel_x=14.5, at_farmhouse_entrance=False))
        return frame
    runtime.observer = observed
    before = len(commands)
    runtime.tick()
    assert runtime.status == "stopped"
    assert len(commands) == before
