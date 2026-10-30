from concurrent.futures import Future
import threading
import time
from copy import deepcopy

import pytest

from smb3_agent.minecraft_chat import MinecraftChat


class Bridge:
    def __init__(self):
        self.session_id = "one"
        self.revision = 0
        self.stops = 0
        self.actions = []
        self.state = {
            "ready": True,
            "position": {"x": 0, "y": 0, "z": 0},
            "active": "old",
            "entities": [],
            "yaw": 0,
        }

    def observe(self):
        return deepcopy(self.state)

    def events_after(self):
        return []

    def stop(self, **kw):
        self.stops += 1
        self.revision += 1
        self.state["active"] = None
        return {
            "controls_cleared": True,
            "stopped_observed": True,
            "revision": self.revision,
        }

    def submit(self, op, action, **kw):
        self.actions.append((action, kw))
        self.state["active"] = "new"
        self.future = Future()
        return "new", self.future

    def reconnect(self, **kw):
        self.stop()
        self.session_id = "two"
        self.revision = 0
        return self.observe()

    def close(self):
        self.stop()


class Provider:
    status = {"available": True}
    usage = []

    def __init__(self, values, gate=None):
        self.values = list(values)
        self.calls = []
        self.entered = threading.Event()
        self.gate = gate

    def infer(self, role, context, schema, cancel):
        self.calls.append((role, context))
        self.entered.set()
        if self.gate:
            self.gate.wait(
                3
            )  # Deliberately ignore cancellation: stale results must still fail closed.
        if context.get('question_stage') == 'decompose':
            return {'cuts': []}
        if context.get('question_stage') == 'select_span':
            return self.values.pop(0) if self.values and ('fact_ids' in self.values[0] or self.values[0].get('kind') == 'stop') else {'fact_ids': ['stop_scope']}
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def wait(predicate):
    end = time.monotonic() + 4
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def service(tmp_path, provider):
    s = MinecraftChat(tmp_path, provider=provider)
    s.bridge = Bridge()
    s.state = s.bridge.state
    s.home = {"x": 0, "y": 0, "z": 0}
    return s


def plan(**kw):
    return {
        "structure_name": "",
        "preference": "",
        "hand_only": False,
        "craft_item": "none",
        "craft_quantity": 1,
        "structure": {
            "width": 3,
            "depth": 3,
            "height": 2,
            "material": "oak_planks",
            "doorway": "north",
            "windows": False,
            "site_place": "",
            "offset": {"x": 3, "y": 0, "z": 0},
            "revise": False,
            "relocate": False,
            "remaining_only": False,
            "allow_removal": False,
            "flexible_site": False,
        },
        "action": "move",
        "reply": "Walking north.",
        "direction": "north",
        "distance": 20,
        "player": "",
        "remember": "",
        "return_place": "",
        "resource": "none",
        "quantity": 0,
        "quantity_mode": "additional",
        "protect_place": "",
        "protect_radius": 0,
        **kw,
    }


def test_question_does_not_touch_goal_revision_or_action(tmp_path):
    s = service(tmp_path, Provider([{"kind": "question", "reply": "You are walking."}]))
    s.goal = "walk"
    s.submit("What are you doing?", "q", "one")
    wait(lambda: not s.busy)
    assert s.goal == "walk"
    assert s.bridge.revision == s.bridge.stops == 0
    assert s.bridge.state["active"] == "old"
    assert not s.bridge.actions
    assert s.messages[-1]["text"] == "You are walking."


def test_replacement_captures_authority_before_second_inference(tmp_path):
    p = Provider([{"kind": "replace", "reply": "Changing direction."}, plan()])
    s = service(tmp_path, p)
    s.submit("Go north instead", "r", "one")
    wait(lambda: not s.busy)
    assert s.bridge.stops == 1
    assert s.bridge.actions[0][1]["revision"] == 1
    started = [e for e in s.events if e["kind"] == "inference_started"]
    assert started[0]["authority"] == (0, "one", 0)
    assert started[1]["authority"] == (0, "one", 1)
    assert p.calls[1][1]["observations"]["active"] is None
    s.bridge.future.set_result({"observed": "position"})


@pytest.mark.parametrize("operation", ["stop", "reconnect"])
def test_pending_old_reply_cannot_act(tmp_path, operation):
    gate = threading.Event()
    p = Provider([{"kind": "goal", "reply": "Go"}], gate)
    s = service(tmp_path, p)
    s.submit("Go north", "r", "one")
    assert p.entered.wait(1)
    getattr(s, operation)()
    wait(lambda: s.bridge.stops == 1)
    gate.set()
    wait(lambda: not s.busy)
    assert not s.bridge.actions
    assert len(p.calls) == 1


def test_stop_during_plan_and_active_movement(tmp_path):
    s = service(tmp_path, Provider([{"kind": "goal", "reply": "Go"}, plan()]))
    s.submit("Go north", "r", "one")
    wait(lambda: not s.busy)
    s.stop()
    wait(lambda: s.bridge.stops == 2)
    s.bridge.future.set_exception(RuntimeError("canceled"))
    wait(lambda: any(e["kind"] == "action_result" for e in s.events))
    assert s.goal is None
    assert "Stopped" in s.activity


@pytest.mark.parametrize("kind", ["clarify", "unavailable"])
def test_non_actions_preserve_play(tmp_path, kind):
    s = service(tmp_path, Provider([{"kind": kind, "reply": "Please clarify."}]))
    s.submit("Build a castle", "r", "one")
    wait(lambda: not s.busy)
    assert s.bridge.stops == 0
    assert s.bridge.state["active"] == "old"


def test_error_duplicate_and_session_validation(tmp_path):
    s = service(tmp_path, Provider([ValueError("AI unavailable")]))
    s.submit("Go", "r", "one")
    wait(lambda: not s.busy)
    assert s.error == "AI unavailable"
    assert s.bridge.stops == 0
    with pytest.raises(ValueError, match="Duplicate"):
        s.submit("Go", "r", "one")
    with pytest.raises(ValueError, match="Connection changed"):
        s.submit("Go", "new", "old-session")


def test_reopen_restores_only_conversation(tmp_path):
    s = service(tmp_path, Provider([{"kind": "question", "reply": "Hello"}]))
    s.submit("Hello", "r", "one")
    wait(lambda: not s.busy)
    restored = MinecraftChat(tmp_path, provider=Provider([]))
    assert restored.messages == s.messages
    assert restored.bridge is restored.goal is None
    assert not restored.busy
    assert restored.epoch == 0
    assert "r" in restored.seen


def test_follow_only_observed_entity_and_movement_limits(tmp_path):
    s = service(tmp_path, Provider([]))
    with pytest.raises(ValueError, match="not observed"):
        s.resolve(plan(action="follow", player="Ghost"), s.bridge.observe())
    state = s.bridge.observe()
    state["entities"] = [
        {"name": "Probe", "id": 5, "position": {"x": 4, "y": 0, "z": 2}}
    ]
    action = s.resolve(plan(action="follow", player="Probe"), state)
    assert action == {
        "action": "follow",
        "player": "Probe",
        "entity_id": 5,
        "duration_ms": 25000,
    }
    s.home["x"] = 50
    with pytest.raises(ValueError, match="32-block"):
        s.resolve(plan(direction="home"), state)


def test_busy_keeps_new_message_unaccepted_and_stop_bypasses_model(tmp_path):
    gate = threading.Event()
    s = service(tmp_path, Provider([{"kind": "question", "reply": "Hello"}], gate))
    s.submit("Hello", "r", "one")
    with pytest.raises(ValueError, match="draft is retained"):
        s.submit("Go north", "two", "one")
    s.submit("Stop now", "stop", "one")
    wait(lambda: s.bridge.stops == 1)
    gate.set()
    wait(lambda: not s.busy)
    assert len(s.provider.calls) == 1
    assert "two" not in s.seen


def test_stop_during_second_inference_rejects_plan(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class DelayedPlan(Provider):
        def infer(self, role, context, schema, cancel):
            if role == "gameplay":
                entered.set()
                release.wait(2)
                return plan()
            return {"kind": "goal", "reply": "Go"}

    s = service(tmp_path, DelayedPlan([]))
    s.submit("Go north", "r", "one")
    assert entered.wait(1)
    s.stop()
    wait(lambda: s.bridge.stops == 2)
    release.set()
    wait(lambda: not s.busy)
    assert not s.bridge.actions
    assert any(e["kind"] == "stale_plan_discarded" for e in s.events)


def test_changed_position_reobserves_and_replans(tmp_path):
    class Drift(Provider):
        def infer(self, role, context, schema, cancel):
            value = super().infer(role, context, schema, cancel)
            if role == "gameplay" and len(self.calls) == 2:
                s.bridge.state["position"]["x"] = 5
            return value

    p = Drift([{"kind": "goal", "reply": "Go"}, plan(), plan()])
    s = service(tmp_path, p)
    s.submit("Go north", "r", "one")
    wait(lambda: not s.busy)
    assert len(p.calls) == 3
    assert s.bridge.actions[0][0]["target"]["x"] == 5
    s.bridge.future.set_result({"observed": "position"})


def test_invalid_plan_never_executes(tmp_path):
    s = service(
        tmp_path, Provider([{"kind": "goal", "reply": "Go"}, plan(distance=300)])
    )
    s.submit("Go north", "r", "one")
    wait(lambda: not s.busy)
    assert not s.bridge.actions
    assert s.error == "Invalid integer"


def test_setup_refresh_rejects_message_without_consuming_draft_or_stop(tmp_path):
    provider = Provider([])
    provider.status = {'available': False, 'state': 'checking', 'message': 'Checking AI setup'}
    s = service(tmp_path, provider)
    with pytest.raises(ValueError, match='Checking AI setup'):
        s.submit('Hello', 'draft', 'one')
    assert 'draft' not in s.seen and not s.messages and not provider.calls
    assert s.snapshot()['ai'] == provider.status
    s.submit('Stop', 'stop', 'one')
    wait(lambda: not s.stopping)
    assert s.bridge.stops == 1


def test_snapshot_during_shutdown_does_not_read_closed_project(tmp_path):
    from smb3_agent.minecraft_build import BuildProject
    from smb3_agent.minecraft_design import WorldDesign
    from test_minecraft_build import Bridge as BuildBridge, REGION

    s = MinecraftChat(tmp_path / 'chat', provider=Provider([]))
    s.project = BuildProject(tmp_path / 'project', 'synthetic', REGION, BuildBridge())
    s.designer = WorldDesign(s.project)
    s.close()
    snapshot = s.snapshot()
    assert snapshot['project'] is None and snapshot['design'] is None


def test_question_between_architecture_units_uses_language_without_new_plan(tmp_path):
    from smb3_agent.minecraft_build import BuildProject
    from test_minecraft_build import Bridge as BuildBridge, REGION
    provider = Provider([{'kind': 'question', 'reply': 'The building is underway.'}])
    s = service(tmp_path / 'chat', provider)
    s.bridge.state['active'] = None
    s.project = BuildProject(tmp_path / 'project', 'synthetic', REGION, BuildBridge())
    s.project.architecture_active = True
    try:
        s.submit('What is happening?', 'architecture-question', 'one')
        wait(lambda: not s.busy)
        assert provider.calls[0][0] == 'language'
        assert not s.bridge.actions and s.bridge.revision == 0
        assert s.messages[-1]['text'] == 'The building is underway.'
    finally:
        s.project.architecture_active = False
        s.close()


def test_project_gap_during_answer_does_not_claim_build_ended(tmp_path):
    from smb3_agent.minecraft_build import BuildProject
    from test_minecraft_build import Bridge as BuildBridge, REGION
    gate = threading.Event()
    provider = Provider([{'kind': 'question', 'reply': 'The building is underway.'}], gate)
    s = service(tmp_path / 'chat', provider)
    s.project = BuildProject(tmp_path / 'project', 'synthetic', REGION, BuildBridge())
    s.project.architecture_active = True
    try:
        s.submit('What is happening?', 'gap-question', 'one')
        assert provider.entered.wait(2)
        context = provider.calls[0][1]
        assert context['question_stage'] == 'conversation'
        s.bridge.state['active'] = None
        gate.set()
        wait(lambda: not s.busy)
        assert s.messages[-1]['text'] == 'The building is underway.'
    finally:
        gate.set()
        s.project.architecture_active = False
        s.close()


def test_oversized_diagnostic_batch_stops_work_without_deleting_retained_log(tmp_path):
    s = service(tmp_path, Provider([]))
    retained = tmp_path / 'events.jsonl'
    retained.write_text('retained history\n')
    s.log_limit = retained.stat().st_size
    try:
        assert not s.append_log('events.jsonl', [{'kind': 'oversized diagnostic batch'}])
        wait(lambda: s.bridge.stops > 0 and not s.stopping)
        assert retained.read_text() == 'retained history\n'
        assert s.snapshot()['error'] == s.storage_error
        with pytest.raises(ValueError, match='Diagnostic history'):
            s.submit('Hello', 'full-log', 'one')
        assert 'full-log' not in s.seen
    finally:
        s.close()


def test_diagnostics_rotate_without_changing_saved_conversation(tmp_path):
    s = service(tmp_path, Provider([]))
    path = tmp_path / 'events.jsonl'
    history = tmp_path / 'conversation.json'
    history.write_text('retained conversation')
    s.log_limit = 32
    try:
        path.write_text('old diagnostics' * 2)
        assert s.append_log('events.jsonl', [{'kind': 'first'}])
        assert path.with_name('events.jsonl.1').read_text() == 'old diagnostics' * 2
        assert s.append_log('events.jsonl', [{'kind': 'second'}])
        assert 'first' in path.with_name('events.jsonl.1').read_text()
        assert 'second' in path.read_text()
        assert history.read_text() == 'retained conversation'
        assert s.storage_error is None
        assert not s.cancel.is_set()
    finally:
        s.close()


def test_diagnostic_compaction_does_not_modify_actual_observations(tmp_path):
    import json
    s = service(tmp_path, Provider([]))
    row = {'type': 'completed', 'result': [{'position': {'x':1,'y':2,'z':3}, 'state':'stone'}]}
    original = deepcopy(row)
    try:
        assert s.append_log('worker-events.jsonl', [row])
        assert row == original
        stored = json.loads((tmp_path/'worker-events.jsonl').read_text())
        assert stored['result']['observation_count'] == 1
        assert len(stored['result']['sha256']) == 64
    finally:
        s.close()


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("question", ["Does stopping this construction also stop other players?", "If I close and reopen, will construction resume by itself?"])
def test_informational_project_question_cannot_become_model_stop(tmp_path, active, question):
    from smb3_agent.minecraft_build import BuildProject
    from test_minecraft_build import Bridge as BuildBridge, REGION
    provider = Provider([{'kind': 'stop', 'reply': 'No, other players continue.'}])
    s = service(tmp_path / 'chat', provider)
    s.project = BuildProject(tmp_path / 'project', 'synthetic', REGION, BuildBridge())
    s.project.architecture_active = active
    s.bridge.state["active"] = None
    try:
        before = s.authority()
        s.submit(question, 'stop-question', 'one')
        wait(lambda: not s.busy)
        assert s.error
        assert s.authority() == before and s.bridge.stops == 0
        assert s.project.architecture_active == active
    finally:
        s.project.architecture_active = False
        s.close()


def test_question_context_excludes_model_prose_and_preserves_factual_scope():
    from smb3_agent.minecraft_planning import question_context
    context = {'request': 'What is underway?', 'instructions': 'Plan destructive work',
               'project': {'state': 'running'}, 'historical_outcomes': [{'complete': True}],
               'construction': None, 'goal_progress': None, 'active_goal_id': None,
               'observations': {'active': None, 'queued': 0, 'health': 20},
               'recent_conversation': [{'role': 'assistant', 'text': 'World resets'},
                                       {'role': 'user', 'text': 'Inspect the Inn'},
                                       {'role': 'user', 'text': 'What is underway?'}]}
    original = deepcopy(context)
    result = question_context(context)
    assert context == original
    assert result['project'] == {'state': 'running'}
    assert result['question_stage'] == 'select'
    assert 'observations' not in result
    assert 'recent_conversation' not in result
    assert 'World resets' not in str(result)
    assert 'not supplied' in result['evidence']['current_work']['text']



@pytest.mark.parametrize('reply', [
    'Stop pauses the world.', 'Stop halts the simulation loop.',
    'Reopening resets the world.', 'Reopening automatically resumes construction.',
    'There are no active goals at this moment.',
    'This activity will not stop when you use Stop.',
])
def test_known_control_contradictions_are_withheld(reply):
    from smb3_agent.minecraft_planning import reject_known_question_contradictions
    with pytest.raises(ValueError, match='reply withheld'):
        reject_known_question_contradictions(reply, {'project': {'state': 'running'}})


@pytest.mark.parametrize('reply', [
    'Stop does not pause the world.', 'Stop never freezes other players.',
    'Reopening does not automatically resume construction.',
    'The Inn is underway. Stop halts companion work only.',
])
def test_accurate_control_explanations_remain_model_replies(reply):
    from smb3_agent.minecraft_planning import reject_known_question_contradictions
    reject_known_question_contradictions(reply, {'project': {'state': 'running'}})


def test_grounded_project_question_reaches_provider_without_raw_worker_fields(tmp_path):
    from smb3_agent.minecraft_build import BuildProject
    from test_minecraft_build import Bridge as BuildBridge, REGION
    provider = Provider([{'kind': 'question', 'reply': 'Stop cancels companion work; the world keeps running.'}])
    s = service(tmp_path / 'chat', provider)
    s.project = BuildProject(tmp_path / 'project', 'synthetic', REGION, BuildBridge())
    s.project.architecture_active = True
    s.project.state = 'running'
    s.bridge.state['active'] = None
    try:
        before = s.authority()
        s.submit('Does Stop pause the world?', 'grounded-question', 'one')
        wait(lambda: not s.busy)
        assert not s.error
        assert s.messages[-1]['text'] == 'Stop cancels companion work; the world keeps running.'
        assert len(provider.calls) == 1
        assert s.authority() == before and s.bridge.stops == 0
        assert 'observations' not in provider.calls[-1][1]
    finally:
        s.project.architecture_active = False
        s.close()


@pytest.mark.parametrize('stage', ['conversation'])
def test_question_expiry_at_any_stage_never_publishes_late_reply(tmp_path, stage):
    from smb3_agent.minecraft_build import BuildProject
    from test_minecraft_build import Bridge as BuildBridge, REGION

    class ExpiringProvider(Provider):
        def infer(self, role, context, schema, cancel):
            value = super().infer(role, context, schema, cancel)
            if context.get('question_stage') == stage:
                cancel.until = 0
            return value

    provider = ExpiringProvider([{'kind': 'question', 'reply': 'LATE ANSWER'}])
    s = service(tmp_path / 'chat', provider)
    s.project = BuildProject(tmp_path / 'project', 'synthetic', REGION, BuildBridge())
    s.project.architecture_active = True
    s.project.state = 'running'
    try:
        authority = s.authority()
        s.submit('Does Stop pause the world?', 'expiry', 'one')
        wait(lambda: not s.busy)
        assert all(m['text'] != 'LATE ANSWER' for m in s.messages)
        assert len(provider.calls) == ['conversation'].index(stage) + 1
        assert s.authority() == authority
        assert not s.bridge.actions and s.bridge.stops == 0
    finally:
        s.project.architecture_active = False
        s.close()


def test_log_rotation_rejects_non_diagnostic_paths(tmp_path):
    s = service(tmp_path, Provider([]))
    try:
        for name in ('conversation.json', '../world/level.dat', 'build-project'):
            with pytest.raises(ValueError, match='Unknown diagnostic log'):
                s.append_log(name, [])
    finally:
        s.close()
