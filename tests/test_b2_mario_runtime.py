from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
import time

import pytest

from smb3_agent.companion_session import Freshness
from smb3_agent.live_observation import (
    LiveObservationManager,
    LiveSessionAccumulator,
    LiveSample,
)
from smb3_agent.mario_plan_runtime import MarioPlanRuntime, runtime_fields
from smb3_agent.takeover import TakeoverController


def plan(
    session="session1", revision=1, parent=None, path="default", stop="full_route"
):
    return {
        "game_id": "mario",
        "session_id": session,
        "revision": revision,
        "parent_revision": parent,
        "base_route_id": "world_8_finish_game",
        "base_version": "1",
        "stop_point": stop,
        "requested_speed": 1.0,
        "actions": [
            {
                "kind": "mario_traverse",
                "parameters": {
                    "primitive_id": f"world_1_1_{'opening_hop' if path == 'opening_hop' else 'default'}_v1",
                    "path_choice": path,
                    "stop_point": stop,
                    "base_route_id": "world_8_finish_game",
                    "base_solution_id": "world_8_finish_game_v1",
                },
            }
        ],
    }


class FakeLive:
    def __init__(self, path):
        self.calls = []
        self.epoch = 0
        self.current = SimpleNamespace(
            session_id="session1",
            artifact_dir=path,
            emulator_pid=42,
            freshness=Freshness.FRESH,
            control_owner="player",
            takeover_terminal_reason=None,
            input_neutralized=True,
            samples=[SimpleNamespace(frame=0, world=0, object_set=0, x=0, y=0)],
        )

    def snapshot(self):
        return self.current

    def begin_session_plan(self, fields):
        self.calls.append(("start", fields))
        self.current.control_owner = "agent"
        self.epoch += 1
        return SimpleNamespace(control_epoch=self.epoch)

    def reclaim_takeover(self):
        self.calls.append(("reclaim",))

    def stop(self):
        self.calls.append(("stop",))


def setup_runtime(tmp_path):
    live = FakeLive(tmp_path)
    runtime = MarioPlanRuntime(live)
    runtime.start(plan())
    return live, runtime


def emit(runtime, event, **fields):
    row = {
        "event": event,
        "epoch": 1,
        "revision": 1,
        "frame": 10,
        "wall": time.time(),
        "x": 24,
        "y": 384,
        **fields,
    }
    with (runtime._directory / "events.log").open("a") as handle:
        handle.write(" ".join(f"{k}={v}" for k, v in row.items()) + "\n")


def test_plan_output_is_not_execution_authority_and_rate_normalized():
    p = plan()
    p["authorization_scope"] = {"granted": True}
    p["evidence_status"] = "accepted"
    assert runtime_fields(p)["speed"] == 1
    assert isinstance(runtime_fields(p)["speed"], int)
    assert "authorization_scope" not in runtime_fields(p)


@pytest.mark.parametrize(
    "change",
    [
        "game",
        "base",
        "version",
        "empty",
        "primitive",
        "contradictory",
        "stop",
        "solution",
        "speed",
        "hop_scope",
    ],
)
def test_adapter_rejects_unsupported_or_contradictory_plan(change):
    p = plan()
    a = p["actions"][0]["parameters"]
    if change == "game":
        p["game_id"] = "stardew"
    elif change == "base":
        p["base_route_id"] = "invented"
    elif change == "version":
        p["base_version"] = "999"
    elif change == "empty":
        p["actions"] = []
    elif change == "primitive":
        a["primitive_id"] = "captured_trace"
    elif change == "contradictory":
        a["path_choice"] = "opening_hop"
    elif change == "stop":
        a["stop_point"] = "world_1_1_exit"
    elif change == "solution":
        a["base_solution_id"] = "unvalidated"
    elif change == "speed":
        p["requested_speed"] = 4
    elif change == "hop_scope":
        p = plan(path="opening_hop")
    with pytest.raises(ValueError):
        runtime_fields(p)


def test_revision_order_duplicate_and_explicit_pending_replacement(tmp_path):
    _, r = setup_runtime(tmp_path)
    p = plan(revision=2, parent=1, path="opening_hop", stop="world_1_1_opening_end")
    r.queue_edit(p, command_id="a")
    with pytest.raises(ValueError, match="explicitly replace"):
        r.queue_edit(p, command_id="b")
    with pytest.raises(ValueError, match="Duplicate"):
        r.queue_edit(p, command_id="a", replace_pending=True)
    with pytest.raises(ValueError, match="Stale"):
        r.queue_edit(plan(revision=3, parent=2), replace_pending=True)
    r.queue_edit(p, command_id="b", replace_pending=True)
    assert r.snapshot()["pending"]["command_id"] == "b"
    assert len(list((tmp_path / "b2").glob("1-*.request"))) == 2


def test_replacement_ack_is_bound_to_command_not_only_revision(tmp_path):
    _, r = setup_runtime(tmp_path)
    a = plan(revision=2, parent=1, path="opening_hop", stop="world_1_1_opening_end")
    b = plan(revision=2, parent=1, stop="world_1_1_exit")
    r.queue_edit(a, command_id="a")
    r.queue_edit(b, command_id="b", replace_pending=True)
    emit(
        r,
        "applied",
        revision=2,
        command_id="a",
        path_choice="opening_hop",
        stop_point="world_1_1_opening_end",
        boundary="world_1_1_opening",
    )
    emit(r, "rejected", revision=2, command_id="b", reason="stale_revision")
    state = r.snapshot()
    assert (
        state["plan"] == {**a, "effective_boundary": "world_1_1_opening"}
        and state["applied_command_id"] == "a"
    )
    assert state["last_rejection"] == "stale_revision"


def test_cancel_waits_for_runtime_receipt_and_completed_actions_remain(tmp_path):
    _, r = setup_runtime(tmp_path)
    r.queue_edit(plan(revision=2, parent=1, stop="world_1_1_exit"), command_id="change")
    r.cancel_pending(command_id="cancel")
    assert r.snapshot()["pending"] is not None
    emit(r, "cancelled", command_id="change")
    assert r.snapshot()["pending"] is None and r.snapshot()["revision"] == 1


def test_missed_opening_stops_and_reclaim_dominates_all_queued_commands(tmp_path):
    live, r = setup_runtime(tmp_path)
    live.current.samples = [
        SimpleNamespace(frame=1100, world=0, object_set=1, x=180, y=384)
    ]
    with pytest.raises(ValueError, match="missed"):
        r.queue_edit(
            plan(revision=2, parent=1, path="opening_hop", stop="world_1_1_opening_end")
        )
    assert live.calls[-1] == ("reclaim",)
    with pytest.raises(ValueError):
        r.control("resume")
    with pytest.raises(ValueError):
        r.control("speed", speed="turbo")
    assert r.snapshot()["outcome"] == "boundary_missed"


def test_expired_boundary_wait_stops_and_does_not_claim_neutral_early(tmp_path):
    live, r = setup_runtime(tmp_path)
    r.queue_edit(plan(revision=2, parent=1, stop="world_1_1_exit"))
    r._state["pending"]["deadline"] = time.time() - 1
    assert r.snapshot()["state"] == "stopping"
    assert live.calls[-1] == ("reclaim",)
    emit(r, "terminal", reason="reclaimed", speed_restored=1)
    state = r.snapshot()
    assert state["owner"] == "agent" and not state["input_neutralized"]
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = "reclaimed"
    assert r.snapshot()["state"] == "finished"
    assert r.snapshot()["outcome"] == "boundary_wait_expired"


def test_speed_intervals_report_real_frame_time_and_handback(tmp_path):
    live, r = setup_runtime(tmp_path)
    emit(r, "speed_ack", speed=1, frame=0, wall=100)
    r.control("speed", speed="turbo")
    emit(r, "speed_ack", speed="turbo", frame=120, wall=102)
    emit(r, "terminal", reason="completed_stop", frame=1320, wall=104, speed_restored=1)
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = "success"
    s = r.snapshot()
    assert s["speed_intervals"][0]["measured_multiplier"] == pytest.approx(0.998)
    assert s["speed_intervals"][1]["measured_multiplier"] > 9
    assert s["speed_restored"] and s["applied_speed"] == 1


def test_bad_wire_value_does_not_consume_command_sequence(tmp_path):
    _, r = setup_runtime(tmp_path)
    with pytest.raises(ValueError):
        r.control("pause", command_id="bad\naction=resume")
    r.control("pause", command_id="good")
    assert (tmp_path / "b2" / "1-000001.request").is_file()


def test_session_replacement_and_process_loss_revoke_volatile_authority(tmp_path):
    live, r = setup_runtime(tmp_path)
    live.current.emulator_pid = 43
    assert r.snapshot()["outcome"] == "process_loss"
    with pytest.raises(ValueError):
        r.control("resume")
    assert not r.snapshot()["speed_restored"]


def sample(seq=1, **changes):
    base = LiveSample(
        "session1",
        "token",
        seq,
        0,
        datetime.now(timezone.utc),
        0,
        0,
        0,
        64,
        32,
        8192,
        32,
        0,
        5,
        0,
        0,
        (0,) * 10,
        (),
    )
    return replace(base, **changes)


def test_start_rejects_same_tileset_other_level_and_requires_observed_lineage(tmp_path):
    manager = LiveObservationManager(artifacts_root=tmp_path)
    controller = TakeoverController(tmp_path, tmp_path / "control.request")
    manager._takeover_controller = controller
    manager._allow_takeover = True
    manager._process = SimpleNamespace(pid=42, poll=lambda: None)
    manager._game_file_sha256 = "hash"
    accumulator = LiveSessionAccumulator(
        "session1", "token", tmp_path, takeover_controller=controller
    )
    accumulator.ingest(sample(frame=600, map_cursor_x=96, map_cursor_y=32))
    accumulator.ingest(sample(2, frame=820, object_set=1, x=24, y=384))
    manager._accumulator = accumulator
    with pytest.raises(ValueError, match="arbitrary resume"):
        manager.begin_session_plan(runtime_fields(plan(stop="world_1_1_exit")))
    assert not (tmp_path / "control.request").exists()


def test_supported_opening_resume_is_same_process_and_never_accepted_route(tmp_path):
    manager = LiveObservationManager(artifacts_root=tmp_path)
    controller = TakeoverController(tmp_path, tmp_path / "control.request")
    manager._takeover_controller = controller
    manager._allow_takeover = True
    manager._process = SimpleNamespace(pid=42, poll=lambda: None)
    manager._game_file_sha256 = "hash"
    accumulator = LiveSessionAccumulator(
        "session1", "token", tmp_path, takeover_controller=controller
    )
    accumulator.ingest(sample(frame=600))
    accumulator.ingest(sample(2, frame=820, object_set=1, x=24, y=384))
    manager._accumulator = accumulator
    auth = manager.begin_session_plan(runtime_fields(plan(stop="world_1_1_exit")))
    assert auth.emulator_pid == 42 and auth.authority_kind == "bounded_session_plan"
    assert "policy=b2_world_1_1_plan_v1" in (tmp_path / "control.request").read_text()


def test_terminal_timing_stays_at_acknowledged_boundary_after_player_progress(tmp_path):
    live, runtime = setup_runtime(tmp_path)
    assert runtime.snapshot()["start_frame"] == 0
    assert runtime.snapshot()["terminal_frame"] is None
    emit(
        runtime,
        "terminal",
        reason="completed_stop",
        frame=1004,
        wall=1234.5,
        speed_restored=1,
    )
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = "success"
    live.current.samples[-1].frame = 1026
    state = runtime.snapshot()
    assert state["terminal_frame"] == 1004
    assert state["terminal_wall"] == 1234.5
    assert state["observation"]["frame"] == 1026
    live.current.samples[-1].frame = 1090
    assert runtime.snapshot()["terminal_frame"] == 1004


def test_start_captures_frame_before_authority_transfer(tmp_path):
    live = FakeLive(tmp_path)
    live.current.samples[-1].frame = 24
    begin = live.begin_session_plan

    def transfer_then_advance(fields):
        authorization = begin(fields)
        live.current.samples[-1].frame = 30
        return authorization

    live.begin_session_plan = transfer_then_advance
    runtime = MarioPlanRuntime(live)
    state = runtime.start(plan())
    assert state["start_frame"] == 24
    assert state["observation"]["frame"] == 30


def test_new_start_does_not_restore_prior_epoch_receipts_or_terminal_timing(tmp_path):
    live, runtime = setup_runtime(tmp_path)
    change = plan(revision=2, parent=1, stop="world_1_1_exit")
    runtime.queue_edit(change, command_id="first-epoch-edit")
    emit(
        runtime,
        "applied",
        revision=2,
        command_id="first-epoch-edit",
        path_choice="default",
        stop_point="world_1_1_exit",
        boundary="world_1_1_exit",
    )
    emit(runtime, "rejected", revision=2, command_id="old", reason="stale_revision")
    emit(
        runtime,
        "terminal",
        revision=2,
        frame=3156,
        wall=1000.5,
        reason="completed_stop",
        speed_restored=1,
    )
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = "success"
    previous = runtime.snapshot()
    assert previous["applied_command_id"] == "first-epoch-edit"
    assert previous["last_rejection"] == "stale_revision"
    live.current.takeover_terminal_reason = None
    live.current.samples[-1].frame = 820
    current = runtime.start(plan(stop="world_1_1_exit"))
    assert current["start_frame"] == 820
    assert current["terminal_frame"] is None and current["terminal_wall"] is None
    assert current["applied_command_id"] is None and current["last_rejection"] is None
    assert current["outcome"] is None
    assert [row["event"] for row in current["events"]] == ["start_authorized"]
    # The append-only disk history remains intact even though volatile receipts reset.
    history = (tmp_path / "b2" / "runtime_history.jsonl").read_text()
    assert "first-epoch-edit" in history and "stale_revision" in history


def test_boolean_is_not_a_plan_revision():
    with pytest.raises(ValueError, match="positive plan revision"):
        runtime_fields(plan(revision=True))


def test_neutral_input_needs_native_completed_frame_and_ownership_ack(tmp_path):
    live, runtime = setup_runtime(tmp_path)
    emit(
        runtime,
        "terminal",
        reason="completed_stop",
        frame=1004,
        wall=1234.5,
        speed_restored=1,
    )
    state = runtime.snapshot()
    assert state["terminal_frame"] == 1004
    assert state["handback_frame"] is None
    assert not state["input_neutralized"] and state["owner"] == "agent"
    emit(runtime, "neutral_ack", frame=1005, wall=1234.52, actual_buttons="none")
    state = runtime.snapshot()
    assert state["handback_frame"] == 1005 and state["terminal_frame"] == 1004
    assert not state[
        "input_neutralized"
    ]  # Native receipt alone cannot transfer authority.
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = "success"
    state = runtime.snapshot()
    assert state["input_neutralized"] and state["state"] == "finished"
    assert state["handback_frame"] == state["terminal_frame"] + 1


def test_legacy_owner_neutral_claim_cannot_substitute_for_native_b2_receipt(tmp_path):
    live, runtime = setup_runtime(tmp_path)
    emit(runtime, "terminal", reason="completed_stop", frame=1004, speed_restored=1)
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = "success"
    live.current.input_neutralized = True
    state = runtime.snapshot()
    assert not state["input_neutralized"] and state["handback_frame"] is None


def test_failed_effective_neutral_frame_cannot_claim_safe_handback(tmp_path):
    live, runtime = setup_runtime(tmp_path)
    emit(runtime, "terminal", reason="completed_stop", frame=1004, speed_restored=1)
    emit(runtime, "neutralization_failed", frame=1005, actual_button="right")
    state = runtime.snapshot()
    assert state["outcome"] == "neutralization_failed"
    assert not state["input_neutralized"] and not state["native_neutral_ack"]
    assert state["owner"] == "agent" and state["handback_frame"] is None


def test_applied_plan_uses_adapter_selected_exit_boundary(tmp_path):
    _, runtime = setup_runtime(tmp_path)
    change = plan(revision=2, parent=1, stop="world_1_1_exit")
    change["effective_boundary"] = "world_1_1_opening"
    pending = runtime.queue_edit(change, command_id="stop-at-exit")
    assert pending["pending"]["effective_boundary"] == "world_1_1_exit"
    emit(
        runtime,
        "applied",
        revision=2,
        command_id="stop-at-exit",
        path_choice="default",
        stop_point="world_1_1_exit",
        boundary="world_1_1_exit",
    )
    actual = runtime.snapshot()
    assert actual["plan"]["effective_boundary"] == "world_1_1_exit"
    assert actual["effective_boundary"] == "world_1_1_exit"
    assert change["effective_boundary"] == "world_1_1_opening"


def boot_manager(tmp_path):
    manager = LiveObservationManager(artifacts_root=tmp_path)
    controller = TakeoverController(tmp_path, tmp_path / "control.request")
    manager._takeover_controller = controller
    manager._allow_takeover = True
    manager._process = SimpleNamespace(pid=42, poll=lambda: None)
    manager._game_file_sha256 = "hash"
    manager._accumulator = LiveSessionAccumulator(
        "session1", "token", tmp_path, takeover_controller=controller
    )
    initial = sample(
        world=255,
        object_set=0,
        map_page=255,
        map_cursor_x=0,
        map_cursor_y=255,
        x=65280,
        y=65280,
        form=255,
        lives=255,
        return_map=255,
        takeover_detail="plan_review_paused",
    )
    manager._accumulator.ingest(initial)
    auth = manager.begin_session_plan(runtime_fields(plan()))
    manager._accumulator.ingest(
        replace(
            initial,
            sequence=2,
            actor="agent",
            control_epoch=auth.control_epoch,
            takeover_detail="ownership_transferred",
        )
    )
    return manager, controller, initial, auth


@pytest.mark.parametrize(
    "detail", ["ownership_transferred", "authorized_solution_input"]
)
def test_polling_exact_authenticated_boot_sample_does_not_trigger_stale_stop(
    tmp_path, detail
):
    manager, controller, initial, auth = boot_manager(tmp_path)
    manager._accumulator.ingest(
        replace(
            initial,
            sequence=3,
            actor="agent",
            control_epoch=auth.control_epoch,
            takeover_detail=detail,
        )
    )
    snapshot = manager.snapshot()
    assert snapshot.control_state == "agent_control"
    assert controller.snapshot.terminal_reason is None
    assert not controller.reclaim_path.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"frame": 1},
        {"world": 254},
        {"x": 24},
        {"return_map": 0},
        {"buttons": ("right",)},
        {"takeover_detail": "arbitrary"},
        {"stale": True},
    ],
)
def test_boot_grace_never_accepts_later_invalid_changed_or_stale_state(
    tmp_path, changes
):
    from datetime import timedelta

    manager, controller, initial, auth = boot_manager(tmp_path)
    changes = dict(changes)
    if changes.pop("stale", False):
        changes["observed_at"] = datetime.now(timezone.utc) - timedelta(seconds=3)
    incoming = replace(
        initial,
        sequence=3,
        actor="agent",
        control_epoch=auth.control_epoch,
        takeover_detail="authorized_solution_input",
    )
    manager._accumulator.ingest(replace(incoming, **changes))
    assert manager.snapshot().control_state == "neutralizing"
    assert controller.reclaim_path.exists()


def test_bounded_inflight_input_is_observed_during_neutralization_not_authorized_after_handback(
    tmp_path,
):
    from smb3_agent.takeover import TakeoverError, TakeoverTerminal

    manager, controller, initial, auth = boot_manager(tmp_path)
    controller.request_terminal(TakeoverTerminal.STALE_STATE)
    count = controller.snapshot.agent_inputs_during
    for sequence, buttons in ((3, ()), (4, ("B", "right"))):
        manager._accumulator.ingest(
            replace(
                initial,
                sequence=sequence,
                frame=sequence,
                world=0,
                actor="agent",
                buttons=buttons,
                control_epoch=auth.control_epoch,
                takeover_detail="authorized_solution_input",
            )
        )
    assert controller.snapshot.agent_inputs_during == count + 2
    assert controller.snapshot.state.value == "neutralizing"
    controller.confirm_handback(final_state_fingerprint="neutral", process_alive=True)
    with pytest.raises(TakeoverError):
        controller.record_agent_input(auth.control_epoch, ("right",))
    assert controller.snapshot.terminal_reason is TakeoverTerminal.STALE_STATE


@pytest.mark.parametrize(
    "reason", ["stale_state", "timeout", "process_loss", "reclaimed"]
)
def test_generic_native_reclaim_keeps_authoritative_manager_terminal_reason(
    tmp_path, reason
):
    live, runtime = setup_runtime(tmp_path)
    emit(runtime, "terminal", reason="reclaimed", frame=5, speed_restored=1)
    emit(runtime, "neutral_ack", frame=6, actual_buttons="none")
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = reason
    assert runtime.snapshot()["outcome"] == reason


def test_specific_boundary_failure_survives_generic_native_and_manager_reclaim(
    tmp_path,
):
    live, runtime = setup_runtime(tmp_path)
    runtime._state["outcome"] = "boundary_missed"
    emit(runtime, "terminal", reason="reclaimed", frame=5, speed_restored=1)
    emit(runtime, "neutral_ack", frame=6, actual_buttons="none")
    live.current.control_owner = "player"
    live.current.takeover_terminal_reason = "reclaimed"
    assert runtime.snapshot()["outcome"] == "boundary_missed"
