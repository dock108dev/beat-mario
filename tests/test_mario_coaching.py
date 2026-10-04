"""Coached ordinary-interface behavior; fixtures do not establish real gameplay."""
from copy import deepcopy
import json
import threading

import pytest

from smb3_agent.conversation_service import ConversationService
from smb3_agent.mario_coaching import COMPATIBILITY, CoachingStore, urgent_control
from smb3_agent.mario_plan_runtime import runtime_fields
from test_conversation_service import FakeLiveManager, FakeRuntime, reviewed


@pytest.fixture
def service(tmp_path):
    live = FakeLiveManager(tmp_path / "evidence")
    return ConversationService(live, runtime=FakeRuntime(live), artifacts_root=tmp_path / "conversation")


def practice(service, attempts=3):
    return service.dispatch("message", {"text": f"Let's practice the opening jump for {attempts} attempts"})


def finish(service, *, delay=0, status="completed_stop", receipt=True):
    runtime = service.runtime
    runtime.state.update(state="finished", owner="player", outcome=status,
                         terminal_frame=40,
                         events=[{"event": "alternate_started", "jump_delay_frames": str(delay)}] if receipt else [])
    runtime.live.control_owner = "player"
    runtime.live.input_neutralized = True
    runtime.live.takeover_terminal_reason = status
    return service.snapshot()


def test_coaching_changes_wire_next_attempt_and_retains_unsuccessful_result(service):
    practice(service)
    service.dispatch("message", {"text": "yes"})
    original = deepcopy(service.runtime.calls[-1][1])
    coached = service.dispatch("message", {"text": "You're jumping too early, wait 4 more frames"})
    assert coached["guidance"]["jump_delay_frames"] == 4
    assert service.runtime.calls[-1][1] == original
    assert "next compatible attempt" in coached["message"]
    finish(service)
    service.dispatch("message", {"text": "try again"})
    actual = service.runtime.calls[-1][1]
    assert runtime_fields(actual)["jump_delay_frames"] == 4
    assert actual["coaching"][0]["original_words"].startswith("You're jumping")
    failed = finish(service, delay=4, status="death")
    evidence = failed["outcome"]["coaching_result"]
    assert evidence["controller_application_observed"] is True
    assert evidence["segment_completed"] is False
    assert evidence["improvement_observed"] is None
    assert len(failed["history"]) == 2


def test_budget_and_reclaim_require_renewed_approval(service):
    practice(service, attempts=2)
    service.dispatch("start", reviewed(service, "start"))
    finish(service)
    service.dispatch("retry")
    finish(service)
    with pytest.raises(ValueError, match="budget ended"):
        service.dispatch("retry")
    practice(service)
    service.dispatch("message", {"text": "yes"})
    state = service.dispatch("message", {"text": "STOP RIGHT NOW WAIT!!!"})
    assert state["runtime"]["owner"] == "player"
    assert state["outcome"]["neutralized"] is True
    assert state["retry_scope"] is None
    with pytest.raises(ValueError, match="budget ended"):
        service.dispatch("message", {"text": "try again"})


def test_reopening_guidance_compatibility_reset_preserve_history(service):
    practice(service)
    service.dispatch("message", {"text": "Delay the jump by a few frames"})
    service.dispatch("message", {"text": "yes"})
    finish(service, delay=3)
    reopened = ConversationService(service.live_manager, runtime=FakeRuntime(service.live_manager), artifacts_root=service.root)
    assert reopened.snapshot()["plan"] is None
    assert reopened.snapshot()["retry_scope"] is None
    practice(reopened)
    assert reopened.snapshot()["plan"]["jump_delay_frames"] == 3
    calls = deepcopy(reopened.runtime.calls)
    reopened.dispatch("message", {"text": "What coaching do you remember?"})
    assert reopened.runtime.calls == calls
    data = reopened.coaching.read()
    data["compatibility"] = "another-level/v9"
    reopened.coaching.write(data)
    with pytest.raises(ValueError, match="incompatible"):
        practice(reopened)
    reopened.dispatch("reset_guidance")
    assert reopened.snapshot()["guidance"]["jump_delay_frames"] == 0
    assert any(row.get("coaching_result") for row in reopened.snapshot()["history"])


def test_urgent_release_precedes_blocked_planning_and_discards_late_proposal(service):
    practice(service)
    service.dispatch("message", {"text": "yes"})
    entered, released = threading.Event(), threading.Event()
    original = service.planner.plan

    def blocked(*args, **kwargs):
        entered.set()
        assert released.wait(3)
        return original(*args, **kwargs)

    service.planner.plan = blocked
    worker = threading.Thread(target=lambda: service.dispatch("message", {"text": "Use the base path"}))
    worker.start()
    assert entered.wait(2)
    stopper = threading.Thread(target=lambda: service.dispatch("message", {"text": "stop right now wait"}))
    stopper.start()
    # Fake runtime control executes before acquiring the conversation lock.
    for _ in range(10000):
        if service.runtime.live.control_owner == "player":
            break
        threading.Event().wait(0.001)
    assert service.runtime.live.control_owner == "player"
    released.set()
    worker.join(3)
    stopper.join(3)
    assert not worker.is_alive() and not stopper.is_alive()
    assert not any(call[0] == "queue" for call in service.runtime.calls)
    assert service.snapshot()["retry_scope"] is None


@pytest.mark.parametrize("text", ["STOP RIGHT NOW WAIT", "Please stop, now!!!", "give me control immediately", "Could you stop right now?"])
def test_urgent_variants(text):
    assert urgent_control(text) in {"stop", "reclaim"}


@pytest.mark.parametrize("text", ["Why stop now?", "don't stop", "What if we stop right now?", "stop jumping early"])
def test_questions_negations_and_coaching_are_not_emergencies(text):
    assert urgent_control(text) is None


def test_timing_range_and_other_routes_reject_unreviewed_parameters(service):
    state = practice(service)
    plan = state["plan"]
    assert runtime_fields({**plan, "session_id": "fixture"})["jump_delay_frames"] == 0
    for delay in (13, -1, True, 2.5):
        with pytest.raises(ValueError):
            runtime_fields({**plan, "jump_delay_frames": delay, "session_id": "fixture"})
    with pytest.raises(ValueError, match="between 0 and 12"):
        service.dispatch("message", {"text": "Jump 20 frames later"})
    assert service.snapshot()["guidance"]["jump_delay_frames"] == 0
    if service.coaching.path.exists():
        assert json.loads(service.coaching.path.read_text())["jump_delay_frames"] == 0


def test_retry_session_change_and_deadline_invalidate_budget(service):
    practice(service)
    service.dispatch("message", {"text": "yes"})
    finish(service)
    service.live_manager.live.session_id = "unrelated-session"
    with pytest.raises(ValueError, match="Session or control changed"):
        service.dispatch("retry")
    assert service.snapshot()["retry_scope"] is None
    practice(service)
    service.dispatch("message", {"text": "yes"})
    finish(service)
    service._retry_scope["deadline"] = 0
    with pytest.raises(ValueError, match="budget ended"):
        service.dispatch("retry")


def test_memory_invalid_type_is_not_controller_data(tmp_path):
    store = CoachingStore(tmp_path / "coaching.json")
    store.write({"schema_version": 1, "compatibility": COMPATIBILITY, "jump_delay_frames": "3", "coaching": []})
    with pytest.raises(ValueError, match="invalid"):
        store.read()


@pytest.mark.parametrize("goal_text", ["Can you help me practice the opening jump for two tries?", "I want to get better at jumping in the opening", "Please work on the opening hop"])
def test_natural_goals_propose_without_input(service, goal_text):
    state = service.dispatch("message", {"text": goal_text})
    assert state["plan"]["coaching_compatibility"] == COMPATIBILITY
    assert service.runtime.calls == []


def test_unsupported_coaching_clarifies_without_unchanged_route_execution(service):
    practice(service)
    before = deepcopy(service.snapshot()["plan"])
    state = service.dispatch("message", {"text": "Hold the jump longer"})
    assert state["messages"][-1]["kind"] == "clarification"
    assert state["plan"] == before
    assert service.runtime.calls == []


def test_comparison_reports_only_observed_stop_completion(service):
    service.live_manager._game_file_sha256 = "fixture-cartridge"
    practice(service)
    service.dispatch("message", {"text": "yes"})
    finish(service, status="death")
    service.dispatch("message", {"text": "Jump 3 frames later"})
    service.dispatch("retry")
    state = finish(service, delay=3)
    assert state["outcome"]["coaching_result"]["improvement_observed"] is True
    assert "causation" in state["outcome"]["coaching_result"]["explanation"]


def test_restart_cancel_prevents_new_runtime_start(service):
    practice(service)
    service.dispatch("message", {"text": "yes"})
    finish(service)
    calls = len(service.runtime.calls)

    def restart(**kwargs):
        service._interrupted.set()
        assert kwargs["cancelled"]()
        return service.live_manager.live

    service.live_manager.restart_coaching_session = restart
    with pytest.raises(ValueError, match="interrupted"):
        service.dispatch("retry")
    assert len(service.runtime.calls) == calls
    assert service.snapshot()["retry_scope"] is None


@pytest.mark.parametrize('goal_text', ['Practice the opening jump for one attempt', 'Can you help me try the opening hop for 1 try?'])
def test_singular_budget_is_one_attempt(service, goal_text):
    state = service.dispatch('message', {'text': goal_text})
    assert state['plan']['resource_limits']['maximum_attempts'] == 1


def test_owned_retry_process_closure_checks_cartridge_and_neutrality(tmp_path, monkeypatch):
    from hashlib import sha256
    from types import SimpleNamespace
    import subprocess
    from smb3_agent.live_observation import LiveObservationManager
    from smb3_agent.companion_session import Freshness

    cartridge = tmp_path / 'fixture-game.bin'
    cartridge.write_bytes(b'fixture only')
    manager = LiveObservationManager(artifacts_root=tmp_path)
    current = SimpleNamespace(session_id='old', control_owner='player', input_neutralized=True,
                              freshness=Freshness.FRESH, checkpoint_id='fresh_power_on', process_alive=True)
    holder = [current]
    manager._accumulator = SimpleNamespace(snapshot=lambda: holder[0])
    manager._coaching_game_path = cartridge
    manager._game_file_sha256 = sha256(cartridge.read_bytes()).hexdigest()
    manager._allow_takeover = True
    calls = []

    class Process:
        closed = False
        def poll(self):
            return 0 if self.closed else None
        def terminate(self):
            calls.append('terminate')
        def kill(self):
            calls.append('kill')
            self.closed = True
        def wait(self, timeout):
            if not self.closed:
                raise subprocess.TimeoutExpired('fixture', timeout)

    manager._process = Process()
    monkeypatch.setattr(manager, 'stop', lambda: calls.append('stop'))
    monkeypatch.setattr(manager, 'invalidate_volatile_state', lambda: True)

    def launch(path, **kwargs):
        assert path == cartridge
        assert kwargs == {'allow_takeover': True, 'pause_for_plan': True}
        manager._game_file_sha256 = sha256(path.read_bytes()).hexdigest()
        calls.append('fresh_paused_launch')
        holder[0] = SimpleNamespace(**{**vars(current), 'session_id': 'new'})
    monkeypatch.setattr(manager, 'start', launch)
    monkeypatch.setattr(manager, 'snapshot', lambda: holder[0])
    current.input_neutralized = False
    with pytest.raises(ValueError, match='released disposable'):
        manager.restart_coaching_session(expected_session='old', cancelled=lambda: False)
    assert not calls
    current.input_neutralized = True
    cartridge.write_bytes(b'changed fixture')
    with pytest.raises(ValueError, match='cartridge changed'):
        manager.restart_coaching_session(expected_session='old', cancelled=lambda: False)
    assert not calls
    cartridge.write_bytes(b'fixture only')
    result = manager.restart_coaching_session(expected_session='old', cancelled=lambda: False)
    assert result.session_id == 'new'
    assert calls == ['stop', 'terminate', 'kill', 'fresh_paused_launch']
