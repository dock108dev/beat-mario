import json
import threading
import time

from test_minecraft_chat import Provider, plan, service, wait
from test_minecraft_goals import setup


def idle(tmp_path, provider):
    chat = service(tmp_path, provider)
    chat.bridge.state["active"] = None
    return chat


def test_idle_proposal_uses_one_call_and_original_authority(tmp_path):
    provider = Provider([plan()])
    chat = idle(tmp_path, provider)
    chat.submit("Walk north", "r", "one")
    wait(lambda: not chat.busy)
    assert len(provider.calls) == 1
    assert chat.bridge.stops == 0
    assert chat.bridge.actions[0][1]["revision"] == 0
    chat.bridge.future.set_result({"observed": "position"})


def test_idle_question_never_submits(tmp_path):
    chat = idle(tmp_path, Provider([plan(action="question", reply="At camp.")]))
    chat.submit("Where are we?", "q", "one")
    wait(lambda: not chat.busy)
    assert not chat.bridge.actions
    assert chat.messages[-1]["text"] == "At camp."


def test_stop_rejects_late_combined_proposal(tmp_path):
    gate = threading.Event()
    provider = Provider([plan()], gate)
    chat = idle(tmp_path, provider)
    chat.submit("Walk north", "r", "one")
    assert provider.entered.wait(1)
    chat.stop()
    gate.set()
    wait(lambda: not chat.busy)
    assert not chat.bridge.actions


def test_inventory_change_requires_fresh_plan(tmp_path):
    gate = threading.Event()
    provider = Provider(
        [plan(), plan(action="clarify", reply="Inventory changed.")], gate
    )
    chat = idle(tmp_path, provider)
    chat.submit("Walk north", "r", "one")
    assert provider.entered.wait(1)
    chat.bridge.state["inventory"] = [{"name": "oak_log", "count": 3}]
    gate.set()
    wait(lambda: not chat.busy)
    assert len(provider.calls) == 2
    assert not chat.bridge.actions


def test_recent_unchanged_column_is_skipped_but_changed_or_expired_retried(tmp_path):
    chat, goal = setup(tmp_path)
    target = {"x": 2, "y": 0, "z": 2}
    chat.bridge.state["resources"] = [
        {"name": "oak_log", "position": target, "signature": "new"}
    ]
    chat.remember_resource_constraint(goal.world, target, "obstructed", signature="new")
    calls = []

    def failed(action):
        calls.append(action)
        raise ValueError("obstructed")

    goal.child = failed
    goal.run()
    assert not calls
    for expired in (False, True):
        chat.supervisor = goal
        goal.skipped.clear()
        goal.failed_columns.clear()
        record = chat.memory["resource_constraints"][json.dumps(goal.world)][-1]
        record["signature"] = "new" if expired else "old"
        record["at_ms"] = (time.time() - (301 if expired else 0)) * 1000
        goal.run()
        assert calls[-1]["target"] == target
    assert len(calls) == 2


def test_scouting_has_distinct_sites_and_parent_bounds(tmp_path):
    chat, goal = setup(tmp_path)
    chat.bridge.state["scout_sites"] = [
        {"x": x, "y": 0, "z": 0} for x in (12, -12, 24, 40)
    ]
    calls = []
    goal.child = lambda action: calls.append(action)
    goal.run()
    assert len(calls) == 3
    assert all(abs(a["target"]["x"]) <= 24 for a in calls)
    assert len({a["target"]["x"] for a in calls}) == 3


def test_return_uses_original_position_when_destination_exceeds_one_leg(tmp_path):
    chat, goal = setup(tmp_path)
    goal.plan["action"] = "return"
    goal.plan["return_place"] = "camp"
    chat.places["camp"] = {"world": goal.world, "position": {"x": 20, "y": 0, "z": 0}}
    # Resolve destination before gathering, then simulate travel to the other edge.
    goal.plan["action"] = "gather"

    def gather():
        chat.bridge.state["position"] = {"x": -20, "y": 0, "z": 0}

    goal.gather = gather
    actions = []

    def child(action):
        actions.append(action)
        chat.bridge.state["position"] = action["target"]

    goal.child = child
    goal.run()
    assert [a["target"]["x"] for a in actions] == [0, 20]
    assert chat.events[-1]["returned"]


def test_only_relative_travel_selects_observed_surface(tmp_path):
    chat = idle(tmp_path, Provider([]))
    state = chat.bridge.observe()
    assert chat.resolve(plan(direction="east"), state)["surface_destination"]
    assert "surface_destination" not in chat.resolve(plan(direction="home"), state)


def test_gather_reserves_return_budget(tmp_path):
    chat, goal = setup(tmp_path)
    goal.destination = {"x": 0, "y": 0, "z": 0}
    goal.remaining = 4
    import pytest

    with pytest.raises(ValueError, match="reserved for return"):
        goal.gather()
    assert goal.remaining == 4
    assert not chat.bridge.actions


def test_long_session_context_preserves_authority_and_bounds_history(tmp_path):
    chat = idle(tmp_path, Provider([]))
    state = chat.bridge.observe()
    world = [state.get("world_id"), state.get("dimension"), state.get("game_version")]
    chat.memory["outcomes"] = [
        {
            "world": world,
            "at_ms": chat.opened_at_ms + n,
            "goal_id": str(n),
            "request": "request " * 200,
            "reason": "partial reason " * 200,
            "inventory_gains": {"oak_log": n},
            "complete": False,
        }
        for n in range(40)
    ]
    chat.messages = [{"role": "assistant", "text": "history " * 200} for _ in range(10)]
    context = chat.context("Summarize current work", state)
    assert len(json.dumps(context)) < 32000
    assert context["observations"]["position"] == state["position"]
    assert context["current_session_outcomes"][-1]["goal_id"] == "39"
    assert context["current_session_outcomes"][-1]["complete"] is False
    assert len(chat.memory["outcomes"][0]["reason"]) > 1000
    assert "different goal_id" in context["instructions"]
