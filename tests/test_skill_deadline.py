"""Slow fresh captures cannot complete a finite task after its deadline."""

from dataclasses import replace

import pytest

from smb3_agent.minecraft_skills import MinecraftSkills
from smb3_agent.minecraft_scene import CellEvidence
from smb3_agent.minecraft_wall import CompositeBudget, WallCoordinator, WallScope
from smb3_agent.skill_runtime import FiniteSkillRuntime
from test_player_beta import obs


def run_move_with_capture_delay(slow_capture, elapsed, parent_max_seconds=180):
    clock = [0.0]
    observations = [
        replace(obs(), captured_at=0),
        replace(obs(), captured_at=0.3, position=(0.5, 0, -1.95)),
    ]
    calls, released = [], []
    budget = CompositeBudget(
        lambda: False, clock=lambda: clock[0], max_seconds=parent_max_seconds
    )

    def observe():
        index = len(calls)
        captured = (
            elapsed
            if slow_capture == ("before" if index == 0 else "after")
            else observations[index].captured_at
        )
        clock[0] = captured
        return replace(observations[index], captured_at=captured)

    def emit(command):
        calls.append(command)
        clock[0] = 0.05

    def neutralize():
        released.append(True)
        return {"confirmed": True}

    provider = MinecraftSkills(obs().window_identity, obs().settings)
    result = FiniteSkillRuntime(
        observe=observe,
        emit=emit,
        neutralize=neutralize,
        canceled=lambda: False,
        clock=lambda: clock[0],
    ).run("move", provider, {"direction": "forward", "distance": 0.05}, budget=budget)
    return result, calls, released, budget


@pytest.mark.parametrize("slow_capture", ["before", "after"])
@pytest.mark.parametrize("elapsed", [8.0, 9.0])
def test_capture_crossing_move_deadline_is_partial_and_released(
    slow_capture, elapsed
):
    result, calls, released, budget = run_move_with_capture_delay(slow_capture, elapsed)

    assert result["status"] == "partial"
    assert "time budget exhausted" in result["reason"]
    assert result["completed"] == []
    assert result["release"] == {"confirmed": True} and released == [True]
    if slow_capture == "before":
        assert calls == [] and result["input_ms"] == budget.input_ms == 0
        assert budget.steps == 1
    else:
        assert len(calls) == 1 and result["input_ms"] == budget.input_ms == 50
        assert not result["steps"][0]["verified"]
        assert budget.steps == 3


@pytest.mark.parametrize("slow_capture", ["before", "after"])
def test_capture_crossing_parent_deadline_stops_valid_child(slow_capture):
    result, calls, released, budget = run_move_with_capture_delay(
        slow_capture, 0.3, parent_max_seconds=0.2
    )
    assert result["status"] == "partial" and result["completed"] == []
    assert "total work budget exhausted" in result["reason"]
    assert result["release"]["confirmed"] and released == [True]
    if slow_capture == "before":
        assert calls == [] and budget.steps == 1 and budget.input_ms == 0
    else:
        assert len(calls) == 1 and budget.steps == 3 and budget.input_ms == 50
        assert not result["steps"][0]["verified"]


def test_in_budget_independent_capture_can_complete_move():
    clock = [0.0]
    observations = [
        replace(obs(), captured_at=0),
        replace(obs(), captured_at=0.3, position=(0.5, 0, -1.95)),
    ]
    calls = []

    def observe():
        current = observations.pop(0)
        clock[0] = current.captured_at
        return current

    def emit(command):
        calls.append(command)
        clock[0] = 0.05

    result = FiniteSkillRuntime(
        observe=observe,
        emit=emit,
        neutralize=lambda: {"confirmed": True},
        canceled=lambda: False,
        clock=lambda: clock[0],
    ).run(
        "move",
        MinecraftSkills(obs().window_identity, obs().settings),
        {"direction": "forward", "distance": 0.05},
    )
    assert result["status"] == "completed" and len(calls) == 1
    assert result["steps"][0]["verified"] and result["release"]["confirmed"]


@pytest.mark.parametrize("final_delay", [0.5, 0.6])
def test_wall_final_position_capture_cannot_complete_after_parent_deadline(final_delay):
    clock = [0.0]
    budget = CompositeBudget(lambda: False, clock=lambda: clock[0], max_seconds=0.5)
    scope = WallScope(
        (0, 0, 0), "x", "minecraft:stone", (), (0.5, 0, -2), "fixture"
    )
    released = []

    def inspect(cell, parent_budget):
        parent_budget.consume()
        clock[0] += 0.001
        return CellEvidence(
            cell,
            None if cell in scope.doorway else scope.material,
            clock[0],
            "fixture",
            (),
            "settings",
        )

    def position():
        clock[0] = final_delay
        return scope.stop_point

    def neutralize():
        released.append(True)
        return {"confirmed": True}

    result = WallCoordinator(
        inspect=inspect,
        place=lambda *args: pytest.fail("Fixture wall already has all work cells"),
        approach=lambda cell, parent_budget: parent_budget.consume(),
        observe_position=position,
        neutralize=neutralize,
    ).run(scope, budget)

    assert result["status"] == "partial" and not result["stop_point_observed"]
    assert "total work budget exhausted" in result["reason"]
    assert len(result["existing"]) == len(result["final_verified"]) - 2 == 19
    assert result["steps"] == budget.steps == 63 and result["input_ms"] == 0
    assert result["release"]["confirmed"] and released == [True]
