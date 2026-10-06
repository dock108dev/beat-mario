"""Simulated providers/games prove mechanisms, never real model or gameplay quality."""
from dataclasses import replace
from pathlib import Path
import threading
import time

import pytest

from smb3_agent.codex_provider import CodexProvider, InferenceError, validate_object
from smb3_agent.companion_ai import DECISION_SCHEMA, INTENT_SCHEMA, WateringAgent
from smb3_agent.conversation_service import StardewConversationService
from smb3_agent.stardew_adapter import InputKind
from test_stardew_runtime import configured


def intent(ids=("crop",), **changes):
    return {"interaction": "activity", "objective": "Water selected crops", "message": "Water these dry crops and return",
            "canonical_command": "water", "target_ids": list(ids), "excluded_ids": [],
            "constraints": ["rightmost first"], "minimum_energy": 1, **changes}


class Provider:
    status = {"available": True, "message": "Simulated provider"}
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []
    def infer(self, role, context, schema, cancel, **kwargs):
        self.calls.append((role, context))
        reply = next(self.replies)
        return reply(role, context, cancel) if callable(reply) else reply


def settled(service):
    service.ai._worker.join(timeout=3)
    assert not service.ai._worker.is_alive()
    return service.snapshot()


def two_crops(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    state[0] = replace(state[0], crops=(*state[0].crops, replace(state[0].crops[0], crop_id="right", tile_x=0, tile_y=1)))
    runtime.navigator.centers[(0, 1)] = (5, 15)
    def emit(command):
        commands.append(command)
        if command.purpose == "water_crop":
            b = state[0]
            state[0] = replace(b, crops=tuple(replace(c, watered=True) if c.crop_id == command.reviewed_crop_id else c for c in b.crops),
                energy=b.energy-2, tool=replace(b.tool, watering_can_units=b.tool.watering_can_units-1, tool_uses=b.tool.tool_uses+1))
    runtime.driver._emitters[InputKind.MOUSE] = emit
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id,
                   actions=(replace(plan.actions[0], target_ids=("crop", "right")),), resource_limits={"maximum_seconds": 120})
    runtime.review(plan)
    return runtime, plan, state, commands


def decision(skill, target="", reason="Observed progress"):
    return {"skill": skill, "target_id": target, "reason": reason, "expected_effect": "Independent water/resource state or farmhouse arrival"}


def test_model_choices_change_execution_and_effects_feed_next_decision(tmp_path):
    runtime, plan, state, commands = two_crops(tmp_path)
    provider = Provider([decision("water_target", "right"), decision("water_target", "crop"), decision("return_home")])
    agent = runtime.gameplay_agent = WateringAgent(provider, intent(("crop", "right")))
    agent.plan_id = plan.plan_id
    runtime.start(plan, background=False)
    for _ in range(3):
        runtime.tick()
    assert [c.reviewed_crop_id for c in commands] == ["right", "crop"]
    supplied = provider.calls[1][1]
    assert supplied["remaining_ids"] == ["crop"]
    assert supplied["prior_effects"][0]["effect"]["target_id"] == "right"
    assert supplied["prior_effects"][0]["effect"]["water_after"] == 4
    assert runtime.status == "completed"
    assert runtime.snapshot()["handback_confirmed"]


@pytest.mark.parametrize("reply", [decision("water_target", "unknown"), decision("return_home"), decision("stop")])
def test_bad_or_early_decisions_release_without_input(tmp_path, reply):
    runtime, plan, state, commands = configured(tmp_path)
    agent = runtime.gameplay_agent = WateringAgent(Provider([reply]), intent())
    agent.plan_id = plan.plan_id
    runtime.start(plan, background=False)
    runtime.tick()
    assert not commands
    assert runtime.status == "stopped" and runtime.snapshot()["handback_confirmed"]


def test_stop_during_game_inference_rejects_late_success(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def delayed(role, context, cancel):
        entered.set()
        release.wait(3)
        return decision("water_target", "crop")  # intentionally ignores cancellation
    agent = runtime.gameplay_agent = WateringAgent(Provider([delayed]), intent())
    agent.plan_id = plan.plan_id
    runtime.start(plan, background=False)
    worker = threading.Thread(target=runtime.tick)
    worker.start()
    assert entered.wait(2)
    runtime.control("reclaim")
    assert runtime.snapshot()["handback_confirmed"]
    release.set()
    worker.join(3)
    assert not commands and runtime.status == "stopped"


def test_changed_resources_during_inference_cannot_execute(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    def change(role, context, cancel):
        state[0] = replace(state[0], tool=replace(state[0].tool, watering_can_units=0))
        return decision("water_target", "crop")
    agent = runtime.gameplay_agent = WateringAgent(Provider([change]), intent())
    agent.plan_id = plan.plan_id
    runtime.start(plan, background=False)
    runtime.tick()
    assert not commands and runtime.snapshot()["handback_confirmed"]
    assert "changed during inference" in runtime.reason


def test_language_correction_revises_scope_and_old_approval_fails(tmp_path):
    runtime, plan, state, commands = two_crops(tmp_path)
    provider = Provider([intent(("crop", "right")), intent(("right",), interaction="correction", excluded_ids=["crop"])])
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=provider)
    service.dispatch("message", {"text": "Look after these thirsty plants, rightmost first"})
    first = settled(service)
    service.dispatch("message", {"text": "Actually leave the other one alone"})
    corrected = settled(service)
    assert corrected["plan"]["actions"][0]["target_ids"] == ["right"]
    assert provider.calls[1][1]["current_goal"]["target_ids"] == ["crop", "right"]
    with pytest.raises(ValueError, match="plan changed"):
        service.dispatch("apply", {"expected_plan_id": first["plan"]["plan_id"], "expected_revision": 1})
    assert not commands
    reopened = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=provider)
    assert reopened.snapshot()["plan"] is None and reopened.ai.intent is None
    assert reopened.ai.snapshot()["historical"]


def test_stop_and_supersession_cancel_language_without_locking_controls(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def delayed(role, context, cancel):
        entered.set()
        release.wait(3)
        return intent()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=Provider([delayed]))
    service.dispatch("message", {"text": "Water these"})
    assert entered.wait(2)
    service.dispatch("stop")
    assert service.snapshot()["runtime"]["handback_confirmed"]
    release.set()
    assert settled(service)["plan"] is None
    assert not commands


@pytest.mark.parametrize("kind", ["question", "approval", "clarify", "unsupported"])
def test_discussion_never_grants_authority(tmp_path, kind):
    runtime, plan, state, commands = configured(tmp_path)
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=Provider([intent(interaction=kind)]))
    service.dispatch("message", {"text": "Could we discuss this?"})
    assert settled(service)["plan"] is None
    assert runtime.controller.authorization is None and not commands


def test_provider_failure_is_visible_without_grammar_fallback(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    def failed(*args):
        raise InferenceError("Account limit reached")
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=Provider([failed]))
    service.dispatch("message", {"text": "Water all observed crops"})
    result = settled(service)
    assert result["ai"]["state"] == "failed" and result["plan"] is None
    assert "Account limit" in result["messages"][-1]["text"] and not commands


def test_schema_rejects_extra_fields_and_bool_energy():
    with pytest.raises(ValueError):
        validate_object(intent(minimum_energy=True), INTENT_SCHEMA)
    with pytest.raises(ValueError):
        validate_object({**decision("stop"), "execute": "shell"}, DECISION_SCHEMA)


def test_codex_process_cancellation_reaps_owned_child(tmp_path):
    executable = tmp_path/"codex"
    executable.write_text('#!' + str(Path(__import__('sys').executable)) + '\nimport time,sys\nif sys.argv[1:]==["login","status"]: sys.exit(0)\ntime.sleep(30)\n')
    executable.chmod(0o700)
    provider = CodexProvider(executable=str(executable), timeout=2)
    cancel = threading.Event()
    errors = []
    def work():
        try:
            provider.infer("gameplay", {}, DECISION_SCHEMA, cancel)
        except InferenceError as exc:
            errors.append(str(exc))
    worker = threading.Thread(target=work)
    worker.start()
    deadline = time.monotonic()+2
    while not provider._children and time.monotonic() < deadline:
        time.sleep(.01)
    assert provider._children
    pending = provider.lifecycle()
    assert len(pending) == 1 and pending[0]["child_running"] is True
    assert pending[0]["role"] == "gameplay" and pending[0]["request_id"]
    cancel.set()
    worker.join(3)
    assert errors and not worker.is_alive() and not provider._children
    assert provider.lifecycle() == []
    assert provider.usage[-1]["request_id"] == pending[0]["request_id"]
    provider.close()


def test_invalid_provider_output_retries_once_then_fails_closed(tmp_path):
    executable = tmp_path/"codex"
    executable.write_text('#!' + str(Path(__import__('sys').executable)) + '\nimport sys,pathlib\nif sys.argv[1:]==["login","status"]: sys.exit(0)\nout=pathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1])\nout.write_text("{}")\n')
    executable.chmod(0o700)
    provider = CodexProvider(executable=str(executable), timeout=2, retries=1)
    with pytest.raises(InferenceError, match="invalid structured"):
        provider.infer("language", {}, INTENT_SCHEMA, threading.Event())
    assert not provider._children and provider.usage[-1]["status"] == "failed_or_canceled"
    provider.close()


def test_provider_deadline_kills_worker_and_never_returns_output(tmp_path):
    executable = tmp_path/"codex"
    executable.write_text('#!' + str(Path(__import__('sys').executable)) + '\nimport time,sys\nif sys.argv[1:]==["login","status"]: sys.exit(0)\ntime.sleep(30)\n')
    executable.chmod(0o700)
    provider = CodexProvider(executable=str(executable), timeout=1)
    with pytest.raises(InferenceError, match="deadline"):
        provider.infer("gameplay", {}, DECISION_SCHEMA, threading.Event())
    assert not provider._children
    provider.close()


def test_mario_model_translation_preserves_words_and_existing_plan_boundary(tmp_path):
    from smb3_agent.conversation_service import ConversationService
    from test_conversation_service import FakeLiveManager, FakeRuntime
    manager = FakeLiveManager(tmp_path/'evidence')
    runtime = FakeRuntime(manager)
    provider = Provider([intent((), canonical_command='practice the opening jump', objective='Practice first jump', constraints=['Allow exactly one attempt.', 'Use the same timing: delay 5 frames and hold jump 26 frames.'])])
    service = ConversationService(manager, runtime=runtime, artifacts_root=tmp_path/'conversation', provider=provider)
    original = 'Could we practice the first jump, keeping the later route as it is?'
    service.dispatch('message', {'text': original})
    result = settled(service)
    assert result['ai']['state'] == 'ready'
    assert result['plan']['original_request'] == original
    assert result['plan']['coaching_compatibility']
    assert result['plan']['strategy_contract'] == 'smb3/world-1-1/opening-strategy/v1'
    assert not any('hold jump 26 frames' in m['text'] for m in service._messages if m['role'] == 'assistant')
    assert result['plan']['resource_limits']['maximum_attempts'] == 1
    assert not runtime.calls
    assert [m['text'] for m in service._messages if m['role'] == 'user'] == [original]
    service.close()


def test_game_clock_pauses_only_pending_decision_and_resumes_before_reobservation(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    events = []
    runtime._inference_clock = lambda paused: events.append(('clock', paused))
    observer = runtime.observer
    def fresh():
        events.append(('observe', None))
        return observer()
    runtime.observer = fresh
    def infer(role, context, cancel):
        assert events[-1] == ('clock', True)
        return decision('water_target', 'crop')
    agent = runtime.gameplay_agent = WateringAgent(Provider([infer]), intent())
    agent.plan_id = plan.plan_id
    runtime.start(plan, background=False)
    runtime.tick()
    pause = events.index(('clock', True))
    assert events[pause+1:pause+3] == [('clock', False), ('observe', None)]
    runtime.control('stop')


def test_canceled_game_decision_never_resumes_clock(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    events = []
    runtime._inference_clock = events.append
    def canceled(role, context, cancel):
        runtime.control('stop')
        return decision('water_target', 'crop')
    agent = runtime.gameplay_agent = WateringAgent(Provider([canceled]), intent())
    agent.plan_id = plan.plan_id
    runtime.start(plan, background=False)
    runtime.tick()
    assert events == [True] and not commands
    assert runtime.snapshot()['handback_confirmed']


def test_language_holds_game_clock_without_granting_work(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    clocks = []
    runtime._inference_clock = clocks.append
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/'language-clock', provider=Provider([intent()]))
    service.dispatch('message', {'text': 'Water this plant then return'})
    settled(service)
    assert clocks == [True]
    assert not commands and runtime.status != 'running'
    assert runtime.controller.authorization is None


def test_codex_readiness_refresh_after_sign_in_does_not_read_or_expose_auth(monkeypatch):
    from types import SimpleNamespace
    calls = []
    signed_in = [False]
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0 if signed_in[0] else 1, stdout=b'private output must not enter status')
    monkeypatch.setattr('subprocess.run', run)
    provider = CodexProvider(executable='/fixture/codex')
    with provider._discovery_lock:
        assert provider.status['state'] == 'sign_in_required'
    signed_in[0] = True
    provider.refresh()
    with provider._discovery_lock:
        assert provider.status['available'] is True
        assert provider.status['state'] == 'ready'
    assert calls == [['/fixture/codex', 'login', 'status']] * 2
    assert 'private' not in str(provider.status)
    provider.close()
    provider.refresh()
    assert len(calls) == 2


def test_switch_invalidates_late_language_reply_and_old_farm_targets(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def delayed(role, context, cancel):
        entered.set()
        assert release.wait(3)
        return intent()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/'chat', provider=Provider([delayed]))
    service.dispatch('message', {'text': 'Please water the crops'})
    assert entered.wait(2)
    runtime.control('stop')
    assert service.invalidate_for_switch()
    release.set()
    service.ai._worker.join(3)
    assert not service.ai._worker.is_alive()
    after = service.snapshot()
    assert after['plan'] is None and after['selected_target_ids'] == []
    assert runtime.current_plan is None and runtime.screen is None
    assert not commands
