"""Typed planner/service integration with an explicitly simulated Mario runtime."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from smb3_agent.conversation_service import ConversationService
from smb3_agent.mario_plan_runtime import runtime_fields


class FakeLiveManager:
    def __init__(self, artifacts: Path) -> None:
        self.live = SimpleNamespace(
            session_id="fixture-session", samples=[SimpleNamespace(
                sequence=1, frame=0, x=0, y=0, actor="player", buttons=(),
            )],
            freshness="fresh", checkpoint_id="fresh_power_on", control_owner="player",
            takeover_terminal_reason=None, player_input_count=0, agent_input_count=0,
            input_neutralized=True, artifact_dir=artifacts, process_alive=True,
            emulator_pid=424242, observation_active=True, takeover_capable=True,
            reason="Fixture observation only",
        )

    def snapshot(self):
        return self.live


class FakeRuntime:
    def __init__(self, manager: FakeLiveManager) -> None:
        self.live = manager.live
        self.calls: list[tuple] = []
        self.state = {"state": "idle", "owner": "player", "revision": None,
                      "pending": None, "requested_speed": 1, "applied_speed": None,
                      "speed_intervals": [], "events": [], "outcome": None}

    def snapshot(self):
        return deepcopy(self.state)

    def start(self, plan):
        runtime_fields(plan)
        self.calls.append(("start", deepcopy(plan)))
        self.state.update(state="playing", owner="agent", revision=plan["revision"],
                          plan=deepcopy(plan), session_id=self.live.session_id, applied_speed=1,
                          start_frame=self.live.samples[-1].frame)
        self.live.samples.append(SimpleNamespace(
            sequence=self.live.samples[-1].sequence + 1,
            frame=self.live.samples[-1].frame + 1, x=1, y=0, actor="agent", buttons=("right",),
        ))
        self.live.control_owner = "agent"
        self.live.input_neutralized = False
        self.live.agent_input_count = 1

    def queue_edit(self, plan, *, expected_revision, command_id, replace_pending):
        runtime_fields(plan)
        assert self.state["revision"] == expected_revision
        self.calls.append(("queue", deepcopy(plan), expected_revision, command_id, replace_pending))
        self.state["pending"] = deepcopy(plan)

    def cancel_pending(self, *, command_id):
        self.calls.append(("cancel", command_id))
        self.state["pending"] = None

    def acknowledge(self) -> None:
        assert self.state["pending"]
        plan = self.state["pending"]
        self.state.update(plan=deepcopy(plan), revision=plan["revision"], pending=None,
                          applied_command_id=plan.get("application_command_id"),
                          effective_boundary=plan["effective_boundary"])
        self.live.samples[-1].frame += 20

    def control(self, action, *, speed=None, command_id):
        self.calls.append((action, speed, command_id))
        if action in {"reclaim", "stop"}:
            self.state.update(state="finished", owner="player", pending=None,
                              outcome="reclaimed" if action == "reclaim" else "stopped",
                              input_neutralized=True, speed_restored=True,
                              terminal_frame=self.live.samples[-1].frame)
            self.live.control_owner = "player"
            self.live.input_neutralized = True
            self.live.takeover_terminal_reason = self.state["outcome"]
        elif action == "speed":
            self.state.update(requested_speed=speed, applied_speed=speed)
        elif action in {"pause", "resume"}:
            self.state["state"] = "paused" if action == "pause" else "playing"


@pytest.fixture
def service(tmp_path):
    manager = FakeLiveManager(tmp_path / "fixture-evidence")
    runtime = FakeRuntime(manager)
    return ConversationService(manager, runtime=runtime, artifacts_root=tmp_path / "conversation")


def reviewed(service, request_id):
    plan = service.snapshot()["plan"]
    return {"request_id": request_id, "expected_plan_id": plan["plan_id"],
            "expected_revision": plan["revision"]}


def start(service):
    service.dispatch("select_intent", {"intent": "existing base route", "request_id": "select"})
    return service.dispatch("start", reviewed(service, "start"))


@pytest.mark.parametrize("intent", ["existing base route", "faster", "fastest", "quickest", "100% clear"])
def test_actual_planner_intents_keep_registry_base_and_no_control(service, intent):
    state = service.dispatch("select_intent", {"intent": intent, "request_id": "select"})
    assert state["plan"]["base_route_id"] == "world_8_finish_game"
    assert state["plan"]["requested_objective"] == intent
    assert state["plan"]["completion_coverage"] == "unknown"
    if intent != "existing base route":
        assert state["plan"]["fallback_explanation"]
    assert state["plan"]["authorization_scope"]["granted"] is False
    assert service.runtime.calls == []


def test_question_keeps_current_execution_and_duplicate_message_is_idempotent(service):
    before = start(service)
    calls = deepcopy(service.runtime.calls)
    state = service.dispatch("message", {"text": "Why are we using the base route?", "request_id": "question"})
    assert state["current_plan"] == before["current_plan"]
    assert service.runtime.calls == calls
    assert state["messages"][-1]["kind"] == "advisory"
    repeated = service.dispatch("message", {"text": "Why are we using the base route?", "request_id": "question"})
    assert repeated["messages"] == state["messages"]
    assert service.runtime.calls == calls


def test_in_scope_edit_pending_replacement_cancel_and_ack(service):
    state = start(service)
    initial = deepcopy(state["current_plan"])
    state = service.dispatch("message", {"text": "Take the opening hop, then stop after the opening section", "request_id": "hop"})
    assert state["pending_plan"]["revision"] == 2
    assert state["pending_plan"]["stop_point"] == "world_1_1_opening_end"
    assert runtime_fields(state["pending_plan"])["path_choice"] == "opening_hop"
    assert state["current_plan"] == initial
    state = service.dispatch("message", {"text": "Actually use the base path and stop after the opening", "request_id": "replace"})
    assert state["pending_plan"]["revision"] == 2
    assert runtime_fields(state["pending_plan"])["path_choice"] == "default"
    assert service.runtime.calls[-1][-1] is True
    state = service.dispatch("cancel_pending", {"request_id": "cancel"})
    assert state["pending_plan"] is None
    assert state["plan"] == state["current_plan"] == initial
    state = service.dispatch("message", {"text": "Take the opening hop, then stop after the opening section", "request_id": "again"})
    assert state["pending_plan"]
    service.runtime.acknowledge()
    state = service.snapshot()
    assert state["pending_plan"] is None
    assert state["current_plan"]["revision"] == 2
    assert runtime_fields(state["current_plan"])["path_choice"] == "opening_hop"
    assert state["messages"][-1]["kind"] == "applied"


def test_stop_retains_partial_history_neutralization_and_unknown_objective(service):
    start(service)
    service.live_manager.live.samples.extend([
        SimpleNamespace(sequence=3, frame=40, x=40, y=0, actor="player", buttons=("A",)),
        SimpleNamespace(sequence=4, frame=55, x=55, y=0, actor="player", buttons=()),
    ])
    service.live_manager.live.player_input_count = 1
    state = service.dispatch("stop", {"request_id": "stop"})
    assert state["outcome"]["status"] == "stopped"
    assert state["outcome"]["actor"] == "mixed"
    assert state["outcome"]["elapsed_game_frames"] == 55
    assert state["outcome"]["neutralized"] is True
    assert state["outcome"]["requested_objective_satisfied"] is None
    assert state["history"][0]["owner_acceptance"] is None
    assert state["history"][0]["reliability_accepted"] is False
    assert state["history"][0]["fastest"] is False
    assert state["history"][0]["completion_coverage"] == "unknown"
    first = Path(state["outcome"]["evidence_path"]).read_bytes()
    service.snapshot()
    assert Path(state["outcome"]["evidence_path"]).read_bytes() == first
    assert len(service.history.list()) == 1


def test_saved_variant_reopens_steps_without_restoring_authority(service):
    start(service)
    service.dispatch("message", {"text": "Take the opening hop, then stop after the opening section", "request_id": "hop"})
    service.runtime.acknowledge()
    service.snapshot()
    state = service.dispatch("save_variant", {"name": "Fixture hop", "request_id": "save"})
    identity = state["variants"][0]["variant_id"]
    service.dispatch("reclaim", {"request_id": "reclaim"})
    calls = deepcopy(service.runtime.calls)
    state = service.dispatch("load_variant", {"variant_id": identity, "request_id": "load"})
    assert service.runtime.calls == calls
    assert state["runtime"]["owner"] == "player"
    assert state["plan"]["authorization_scope"]["granted"] is False
    assert state["plan"]["execution_eligibility"] != "authorized"
    assert runtime_fields(state["plan"])["path_choice"] == "opening_hop"
    assert state["plan"]["stop_point"] == "world_1_1_opening_end"
    assert state["plan"]["variant_id"] == identity
    record = service.variants.load(identity)
    assert record["status"] != "accepted"
    assert len(service.history.list()) == 1


def test_stale_observation_and_other_session_plan_cannot_start(service):
    service.dispatch("select_intent", {"intent": "quickest", "request_id": "select"})
    service.live_manager.live.freshness = "stale"
    with pytest.raises(ValueError, match="fresh observation"):
        service.dispatch("start", reviewed(service, "stale"))
    service.live_manager.live.freshness = "fresh"
    service.live_manager.live.session_id = "other-session"
    with pytest.raises(ValueError, match="another session"):
        service.dispatch("start", reviewed(service, "wrong-session"))
    assert service.runtime.calls == []


def test_superseded_edit_wins_boundary_race_without_relabeling_rejected_replacement(service):
    start(service)
    first = service.dispatch("message", {
        "text": "Take the opening hop, then stop after the opening section", "request_id": "first",
    })["pending_plan"]
    second = service.dispatch("message", {
        "text": "Actually use the base path and stop after the opening", "request_id": "second",
    })["pending_plan"]
    assert first["revision"] == second["revision"] == 2
    assert first["application_command_id"] != second["application_command_id"]
    # The first request reaches the real boundary before its replacement can be
    # processed. The controller applies first and rejects second's stale parent.
    service.runtime.state.update(
        revision=first["revision"], plan=deepcopy(first), pending=None,
        applied_command_id=first["application_command_id"], last_rejection="stale_revision",
    )
    state = service.snapshot()
    assert state["current_plan"] == first
    assert state["plan"] == first
    assert state["pending_plan"] is None
    assert state["revisions"][-1] == first
    assert "not applied" in state["message"]
    outcome = service.dispatch("reclaim", {"request_id": "reclaim-race"})["outcome"]
    assert outcome["actual_plan"] == first
    assert all(revision.get("application_command_id") != "second" for revision in outcome["revisions"])


def test_cancel_that_loses_boundary_race_reports_actual_applied_plan(service):
    start(service)
    pending = service.dispatch("message", {
        "text": "Take the opening hop, then stop after the opening section", "request_id": "hop",
    })["pending_plan"]

    def cancel_at_boundary(*, command_id):
        service.runtime.calls.append(("cancel", command_id))
        service.runtime.acknowledge()

    service.runtime.cancel_pending = cancel_at_boundary
    state = service.dispatch("cancel_pending", {"request_id": "late-cancel"})
    assert state["pending_plan"] is None
    assert state["current_plan"] == pending
    assert state["message"] == "Revision 2 applied at the supported boundary."


@pytest.mark.parametrize("field,value", [("base_route_id", "missing-route"),
                                         ("base_version", "incompatible-v999")])
def test_reopen_rejects_incompatible_saved_base_or_version_without_control(service, field, value):
    proposed = service.dispatch("select_intent", {
        "intent": "existing base route", "request_id": "select",
    })["plan"]
    incompatible = deepcopy(proposed)
    incompatible[field] = value
    saved = service.variants.save("Incompatible fixture", incompatible)
    with pytest.raises(ValueError, match="base route or version.*compatible"):
        service.dispatch("load_variant", {"variant_id": saved["variant_id"], "request_id": "load"})
    assert service.runtime.calls == []
    assert service.snapshot()["plan"] == proposed


def test_revert_replaces_pending_with_selected_older_steps_instead_of_only_canceling(service):
    first = service.dispatch("message", {
        "text": "Use the base path and stop after the opening", "request_id": "first",
    })["plan"]
    assert first["stop_point"] == "world_1_1_opening_end"
    service.dispatch("start", reviewed(service, "start"))
    service.dispatch("message", {
        "text": "Take the opening hop", "request_id": "hop",
    })
    service.runtime.acknowledge()
    assert service.snapshot()["current_plan"]["revision"] == 2
    service.dispatch("message", {
        "text": "Use the base path and stop after clearing World 1-1", "request_id": "extend",
    })
    state = service.dispatch("apply", reviewed(service, "review-expanded-stop"))
    assert state["pending_plan"]["stop_point"] == "world_1_1_exit"
    state = service.dispatch("revert", {"revision": first["revision"], "request_id": "revert-first"})
    assert state["current_plan"]["revision"] == 2
    assert runtime_fields(state["current_plan"])["path_choice"] == "opening_hop"
    assert state["pending_plan"]["revision"] == 3
    assert state["pending_plan"]["parent_revision"] == 2
    assert state["pending_plan"]["stop_point"] == first["stop_point"]
    assert runtime_fields(state["pending_plan"])["path_choice"] == "default"
    assert service.runtime.calls[-1][0] == "queue"
    assert service.runtime.calls[-1][-1] is True
    service.runtime.acknowledge()
    state = service.snapshot()
    assert state["current_plan"]["revision"] == 3
    assert state["current_plan"]["stop_point"] == first["stop_point"]
    assert state["revisions"][0]["actions"] == first["actions"]


@pytest.mark.parametrize("genuine_player_input,expected_actor", [(False, "agent"), (True, "mixed")])
def test_terminal_timing_and_actor_use_actual_input_inside_controller_frame_window(
    service, genuine_player_input, expected_actor,
):
    start(service)
    samples = service.live_manager.live.samples
    if genuine_player_input:
        samples.append(SimpleNamespace(sequence=3, frame=500, x=120, y=300,
                                       actor="player", buttons=("A",)))
    samples.extend([
        SimpleNamespace(sequence=4, frame=900, x=140, y=310, actor="agent", buttons=("right",)),
        SimpleNamespace(sequence=5, frame=1004, x=160, y=315, actor="player", buttons=()),
        # This genuine player button is after controller handback, outside this
        # attempt's measured game-frame interval. It belongs to later play.
        SimpleNamespace(sequence=6, frame=1026, x=180, y=330, actor="player", buttons=("right",)),
    ])
    service.live_manager.live.player_input_count = 25
    service.live_manager.live.agent_input_count = 900
    service.live_manager.live.control_owner = "player"
    service.live_manager.live.input_neutralized = True
    service.live_manager.live.takeover_terminal_reason = "completed_stop"
    service.runtime.state.update(state="finished", owner="player", outcome="completed_stop",
                                 start_frame=0, terminal_frame=1004,
                                 input_neutralized=True, speed_restored=True)
    outcome = service.snapshot()["outcome"]
    assert outcome["start_frame"] == 0
    assert outcome["terminal_frame"] == 1004
    assert outcome["elapsed_game_frames"] == 1004
    assert outcome["actor"] == expected_actor
    assert outcome["last_observation"]["frame"] == 1026
    saved = service.history.list()[0]
    assert saved["terminal_frame"] == 1004
    assert saved["elapsed_game_frames"] == 1004
    assert saved["actor"] == expected_actor


def test_saving_completed_variant_retains_only_its_matching_outcome_reference(service):
    start(service)
    service.dispatch("message", {
        "text": "Take the opening hop, then stop after the opening section", "request_id": "hop",
    })
    service.runtime.acknowledge()
    service.snapshot()
    service.runtime.state.update(state="finished", owner="player", outcome="completed_stop",
                                 terminal_frame=1004, input_neutralized=True, speed_restored=True)
    service.live_manager.live.control_owner = "player"
    service.live_manager.live.input_neutralized = True
    service.live_manager.live.takeover_terminal_reason = "completed_stop"
    outcome = service.snapshot()["outcome"]
    state = service.dispatch("save_variant", {"name": "Completed opening hop", "request_id": "save-completed"})
    identity = state["plan"]["variant_id"]
    record = service.variants.load(identity)
    assert record["source_outcome_reference"] == outcome["evidence_path"]
    assert Path(record["source_outcome_reference"]).is_file()
    assert record["runtime_evidence_reference"] == str(service.live_manager.live.artifact_dir)
    assert record["plan"]["authorization_scope"]["granted"] is False
    assert record["plan"]["session_id"] is None
    assert record["accepted"] is False
    assert record["fastest"] is False
    service.dispatch("message", {
        "text": "Use the base path and stop after the opening", "request_id": "new-unplayed-edit",
    })
    service.dispatch("save_variant", {"name": "Unplayed base revision", "request_id": "save-unplayed"})
    latest = service.variants.load(identity)
    assert latest["saved_revision"] == 2
    assert latest["source_outcome_reference"] is None
    assert service.variants.load(identity, revision=1)["source_outcome_reference"] == outcome["evidence_path"]


@pytest.mark.parametrize("action", ["start", "apply"])
def test_stale_browser_review_cannot_authorize_another_tabs_plan(service, action):
    service.dispatch("message", {"text": "Take the opening hop, then stop after the opening section", "request_id": "tab-a"})
    old_review = reviewed(service, "tab-a-start")
    service.dispatch("select_intent", {"intent": "existing base route", "request_id": "tab-b"})
    with pytest.raises(ValueError, match="reviewed plan has changed"):
        service.dispatch(action, old_review)
    assert service.runtime.calls == []
    with pytest.raises(ValueError, match="reviewed plan has changed"):
        service.dispatch(action, {"request_id": "missing-review"})
    assert service.runtime.calls == []


def test_pending_notice_uses_runtime_selected_stop_boundary(service):
    start(service)
    original_queue = service.runtime.queue_edit
    def queue(plan, **kwargs):
        original_queue(plan, **kwargs)
        service.runtime.state["pending"]["effective_boundary"] = "world_1_1_exit"
        return service.runtime.snapshot()
    service.runtime.queue_edit = queue
    state = service.dispatch("message", {"text": "Stop after clearing World 1-1", "request_id": "exit-edit"})
    assert state["pending_plan"]["effective_boundary"] == "world_1_1_exit"
    assert "pending at world_1_1_exit" in state["message"]
