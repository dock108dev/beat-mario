from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smb3_agent.takeover import (
    ControlOwner,
    ExecutableSolution,
    TakeoverController,
    TakeoverError,
    TakeoverState,
    TakeoverTerminal,
    supported_solutions,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _controller(tmp_path: Path) -> TakeoverController:
    return TakeoverController(tmp_path, tmp_path / "control.request")


def _authorize(controller: TakeoverController, **changes: object):
    values = {
        "session_id": "session-1",
        "emulator_pid": 123,
        "game_file_sha256": "game-sha",
        "current_fingerprint": "state-sha",
        "game_id": "smb3",
        "profile_id": "smb3.world_1_1.normal_clear",
        "profile_version": 1,
        "solution": supported_solutions()[0],
        "scope": "level_remainder",
        "stop_condition": "game_owned_level_clear",
        "timeout_seconds": 60,
        "protected_resources": ("p_wing",),
        "now": NOW,
    }
    values.update(changes)
    return controller.authorize(**values)


def _transfer(controller: TakeoverController, authorization, **changes: object) -> None:
    values = {
        "session_id": "session-1",
        "emulator_pid": 123,
        "game_file_sha256": "game-sha",
        "current_fingerprint": "state-sha",
        "now": NOW + timedelta(milliseconds=10),
    }
    values.update(changes)
    controller.transfer(authorization, **values)


def test_atomic_authorization_transfer_and_actor_labeled_input(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    authorization = _authorize(controller)
    assert controller.snapshot.owner is ControlOwner.PLAYER
    assert controller.snapshot.state is TakeoverState.AUTHORIZED
    assert controller.snapshot.agent_inputs_before == 0

    _transfer(controller, authorization)
    controller.record_agent_input(authorization.control_epoch, ("B", "right"))

    assert controller.snapshot.owner is ControlOwner.AGENT
    assert controller.snapshot.agent_inputs_during == 1
    assert "action=start" in (tmp_path / "control.request").read_text()


@pytest.mark.parametrize("mutation", ["session", "pid", "game", "state", "epoch"])
def test_mismatched_authorization_fails_closed(tmp_path: Path, mutation: str) -> None:
    controller = _controller(tmp_path)
    authorization = _authorize(controller)
    changes = {
        "session": {"session_id": "other"},
        "pid": {"emulator_pid": 999},
        "game": {"game_file_sha256": "other"},
        "state": {"current_fingerprint": "other"},
        "epoch": {},
    }[mutation]
    if mutation == "epoch":
        authorization = replace(authorization, control_epoch=99)
    with pytest.raises(TakeoverError, match="stale|matches"):
        _transfer(controller, authorization, **changes)
    assert controller.snapshot.owner is ControlOwner.PLAYER


def test_expired_and_replayed_authorization_cannot_send_input(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    authorization = _authorize(controller, timeout_seconds=1)
    with pytest.raises(TakeoverError, match="expired"):
        _transfer(controller, authorization, now=NOW + timedelta(seconds=2))

    controller = _controller(tmp_path / "second")
    authorization = _authorize(controller)
    _transfer(controller, authorization)
    controller.finish(
        TakeoverTerminal.SUCCESS,
        final_state_fingerprint="final",
        process_alive=True,
    )
    controller.snapshot = replace(controller.snapshot, state=TakeoverState.AUTHORIZED, authorization=authorization)
    with pytest.raises(TakeoverError, match="already been used"):
        _transfer(controller, authorization)


def test_candidate_or_unreviewed_solution_cannot_drive_takeover(tmp_path: Path) -> None:
    solution = replace(supported_solutions()[0], replay_safe=False, accepted=False)
    with pytest.raises(TakeoverError, match="replay-safe accepted"):
        _authorize(_controller(tmp_path), solution=solution)


def test_immediate_reclaim_neutralizes_and_resumes_same_process_observation(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    authorization = _authorize(controller)
    _transfer(controller, authorization)
    controller.record_agent_input(authorization.control_epoch, ("right",))
    result = controller.reclaim(
        authorization.control_epoch,
        final_state_fingerprint="final-state",
        process_alive=True,
        requested_at=NOW + timedelta(seconds=1),
        completed_at=NOW + timedelta(seconds=1, milliseconds=18),
    )

    assert result.owner is ControlOwner.PLAYER
    assert result.terminal_reason is TakeoverTerminal.RECLAIMED
    assert result.neutralized and result.observation_resumed
    assert result.handback_latency_ms == pytest.approx(18)
    assert "action=neutralize" in (tmp_path / "control.request").read_text()

    with pytest.raises(TakeoverError, match="outside active authorization"):
        controller.record_agent_input(authorization.control_epoch, ("right",))
    assert controller.snapshot.agent_inputs_after == 1


@pytest.mark.parametrize("reason", list(TakeoverTerminal))
def test_every_terminal_path_neutralizes_and_returns_or_fails_closed(
    tmp_path: Path, reason: TakeoverTerminal
) -> None:
    controller = _controller(tmp_path)
    authorization = _authorize(controller)
    _transfer(controller, authorization)
    result = controller.finish(
        reason,
        final_state_fingerprint="final",
        process_alive=reason is not TakeoverTerminal.PROCESS_LOSS,
    )
    assert result.owner is ControlOwner.PLAYER
    assert result.neutralized
    assert result.state is (
        TakeoverState.FAILED if reason is TakeoverTerminal.PROCESS_LOSS else TakeoverState.RETURNED
    )


def test_solution_scopes_are_capability_data_not_level_name_branches() -> None:
    solutions = supported_solutions()
    assert {scope for solution in solutions for scope in solution.scopes} >= {
        "level_remainder",
        "complete_level",
        "world_or_route_goal",
        "full_game",
        "until_reclaim",
    }
    assert all(isinstance(solution, ExecutableSolution) for solution in solutions)
