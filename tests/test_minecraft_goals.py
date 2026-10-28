from copy import deepcopy
from concurrent.futures import Future
import time

import pytest

from smb3_agent.minecraft_goals import Goal, inventory, protected
from test_minecraft_chat import Provider, plan, service, wait


def setup(tmp_path, **changes):
    chat = service(tmp_path, Provider([]))
    chat.bridge.state.update(
        world_id="world",
        dimension="overworld",
        game_version="1.21.4",
        inventory=[],
        resources=[],
    )
    goal = Goal(
        chat,
        plan(action="gather", resource="oak_log", quantity=2, **changes),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = goal
    chat.goal = "gather"
    return chat, goal


@pytest.mark.parametrize("change", ["stop", "revision", "world", "deadline", "budget"])
def test_goal_authority_and_budgets(tmp_path, change):
    chat, goal = setup(tmp_path)
    if change == "stop":
        chat.supervisor = None
    elif change == "revision":
        chat.bridge.revision += 1
    elif change == "world":
        chat.bridge.state["world_id"] = "other"
    elif change == "deadline":
        goal.deadline = time.monotonic() - 1
    else:
        goal.remaining = 0
    with pytest.raises(ValueError):
        goal.observe()
    assert not chat.bridge.actions


def test_inventory_variants_losses_and_unrelated_pickups(tmp_path):
    chat, goal = setup(tmp_path)
    chat.bridge.state["inventory"] = [
        {"name": "oak_log", "count": 2},
        {"name": "birch_log", "count": 8},
    ]
    goal.observe()
    chat.bridge.state["inventory"][0]["count"] = 1
    goal.observe()
    assert goal.count(goal.gained) == 2
    assert goal.count(goal.last) == 1
    assert goal.lost["oak_log"] == 1
    assert goal.gained["birch_log"] == 8
    assert (
        inventory(
            {
                "inventory": [
                    {"name": "oak_log", "count": 2},
                    {"name": "oak_log", "count": 3},
                ]
            }
        )["oak_log"]
        == 5
    )


def test_place_reopen_and_wrong_world(tmp_path):
    chat, goal = setup(tmp_path, remember="home")
    goal.plan["action"] = "remember"
    goal.run()
    restored = service(tmp_path, Provider([]))
    assert restored.places["home"]["world"][0] == "world"
    assert restored.goal is restored.supervisor is None
    chat.supervisor = goal
    assert goal.place("home", chat.bridge.observe()) == chat.home
    goal.world = ["other", "overworld", "1.21.4"]
    with pytest.raises(ValueError, match="another world"):
        goal.place("home", chat.bridge.observe())


def test_missing_resource_is_honest_partial(tmp_path):
    chat, goal = setup(tmp_path)
    goal.run()
    outcome = chat.events[-1]
    assert outcome["kind"] == "goal_outcome"
    assert outcome["broken"] == outcome["net_matching"] == 0
    assert "No matching" in chat.messages[-1]["text"]


def test_protection_blocks_candidate(tmp_path):
    chat, goal = setup(tmp_path)
    pos = {"x": 1, "y": 0, "z": 1}
    goal.regions = [{"center": pos, "radius": 2}]
    assert protected(pos, goal.regions)
    chat.bridge.state["resources"] = [{"name": "oak_log", "position": pos}]
    goal.run()
    assert not chat.bridge.actions


def test_recovery_never_repeats_failed_target(tmp_path):
    chat, goal = setup(tmp_path)
    chat.bridge.state["resources"] = [
        {"name": "oak_log", "position": {"x": x, "y": 0, "z": 1}} for x in range(1, 6)
    ]
    targets = []

    def failed(action):
        targets.append(deepcopy(action["target"]))
        raise ValueError("obstructed")

    goal.child = failed
    goal.run()
    assert goal.failures == 3
    assert len(targets) == len({tuple(t.values()) for t in targets}) == 3


def test_question_keeps_supervisor_and_child_authority(tmp_path):
    chat, goal = setup(tmp_path)
    chat.provider = Provider([{"kind": "question", "reply": "Gathering."}])
    chat.submit("How is gathering going?", "q", "one")
    wait(lambda: not chat.busy)
    assert chat.supervisor is goal
    goal.check()
    assert chat.bridge.stops == 0


def test_stop_at_child_completion_cannot_start_another(tmp_path):
    chat, goal = setup(tmp_path)
    future = Future()

    def submit(*args, **kwargs):
        chat.supervisor = None
        future.set_result({"observed": "position"})
        return "child", future

    chat.bridge.submit = submit
    with pytest.raises(ValueError, match="canceled"):
        goal.child({"action": "move", "target": chat.home})
    assert goal.remaining == 79


def test_total_quantity_uses_existing_inventory(tmp_path):
    chat, goal = setup(tmp_path, quantity_mode="total")
    state = chat.bridge.observe()
    state["inventory"] = [{"name": "oak_log", "count": 5}]
    goal = Goal(chat, goal.plan, state, chat.authority())
    assert goal.needed == 0


def test_total_deadline_includes_reasoning_time(tmp_path):
    chat, existing = setup(tmp_path)
    goal = Goal(
        chat,
        existing.plan,
        chat.bridge.observe(),
        chat.authority(),
        started_at=time.monotonic() - 241,
    )
    chat.supervisor = goal
    with pytest.raises(ValueError, match="deadline"):
        goal.observe()


def test_stop_between_observation_and_memory_write(tmp_path):
    chat, goal = setup(tmp_path, remember="late")
    goal.plan["action"] = "remember"
    original = goal.observe

    def observed_then_stop():
        result = original()
        chat.epoch += 1
        return result

    goal.observe = observed_then_stop
    goal.run()
    assert "late" not in chat.places
