"""Shared product behavior; simulated contracts, not live qualification."""
from copy import deepcopy

import pytest

from smb3_agent.conversation_service import ConversationService, StardewConversationService
from smb3_agent.outcome_review import outcome_review
from test_conversation_service import FakeLiveManager, FakeRuntime, start
from test_stardew_conversation import FakeStardewRuntime, request, identity


def test_mario_switch_retains_outcome_but_drops_pending_and_revisions(tmp_path):
    manager = FakeLiveManager(tmp_path)
    runtime = FakeRuntime(manager)
    service = ConversationService(manager, runtime=runtime, artifacts_root=tmp_path)
    start(service)
    service.dispatch('message', {'text': 'Take the opening hop'})
    assert not service.invalidate_for_switch()
    service.dispatch('reclaim')
    assert service.invalidate_for_switch()
    state = service.snapshot()
    assert state['plan'] is state['current_plan'] is state['pending_plan'] is None
    assert state['revisions'] == []
    assert state['history'] and state['messages']
    assert 'read-only' in state['history'][0]['review']['recovery']
    with pytest.raises(ValueError, match='reviewed plan'):
        service.dispatch('start', {'expected_revision': 1})


def test_stardew_cancel_and_refusal_history_survive_new_service_without_review(tmp_path):
    runtime = FakeStardewRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    proposed = request(service)
    service.dispatch('apply', identity(proposed))
    service.dispatch('cancel_pending')
    with pytest.raises(ValueError, match='Review this exact'):
        service.dispatch('start', identity(proposed))
    assert not any(call[0] == 'start' for call in runtime.calls)
    state = StardewConversationService(runtime=FakeStardewRuntime(), artifacts_root=tmp_path).snapshot()
    assert state['plan'] is None and not state['reviewed'] and not state['selected_target_ids']
    assert state['history'][0]['status'] == 'refused'
    assert state['history'][0]['review']['request']


@pytest.mark.parametrize('status', ['completed', 'partial', 'interrupted_by_owner_input', 'refused', 'failed'])
def test_read_only_outcome_preserves_exact_status_and_partial_ledger(status):
    row = {'game_id': 'stardew', 'status': status, 'task_ledger': {
        'steps': [{'kind': 'harvest', 'target_id': 'left', 'status': 'confirmed'},
                  {'kind': 'plant', 'target_id': 'left', 'status': 'pending'}]}}
    original = deepcopy(row)
    view = outcome_review(row)
    assert row == original
    assert view['confirmed'] == ['harvest left']
    assert 'plant left: pending' in view['remaining']
    assert 'Farmhouse return not confirmed' in view['remaining']
    assert 'no control permission' in view['recovery']


def test_occlusion_stop_cannot_be_presented_as_success():
    view = outcome_review({'game_id': 'stardew', 'status': 'failed', 'stop_reason': 'occlusion history guard'})
    assert view['label'] == 'Guarded stop — not complete'
    assert 'Never automatically resume' in view['recovery']


def test_recovery_does_not_claim_satisfied_work_was_executed_again():
    view = outcome_review({'game_id': 'stardew', 'status': 'completed', 'task_ledger': {
        'steps': [{'kind': 'water', 'target_id': 'left', 'status': 'already_satisfied'}],
        'final_position': {'at_farmhouse_entrance': True}}})
    assert view['confirmed'] == ['water left (already satisfied before this run)']
    assert view['remaining'] == ['Reviewed scope complete; no automatic continuation']


def test_failed_observation_does_not_claim_a_fresh_view(tmp_path):
    class FailedObserver(FakeStardewRuntime):
        def snapshot(self):
            return {**super().snapshot(), 'reason': 'camera anchor not recognized'}
    service = StardewConversationService(runtime=FailedObserver(), artifacts_root=tmp_path)
    state = service.dispatch('observe')
    assert state['messages'][-1]['text'] == 'Observation checked. camera anchor not recognized'
    assert not state['reviewed']


def test_switch_lock_blocks_new_authority_but_not_reclaim(tmp_path, monkeypatch):
    import http.client
    import json
    import re
    import threading
    from urllib.parse import urlencode
    from smb3_agent.lab_ui import _new_lab_ui_server

    monkeypatch.chdir(tmp_path)
    # Catalog contracts use repository-relative paths.
    from pathlib import Path
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    server = _new_lab_ui_server('127.0.0.1', 0)
    calls = []
    class Service:
        def dispatch(self, action, payload):
            calls.append(action)
            return {'owner': 'player'}
    server.stardew_conversation_service = Service()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def post(action, token):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
        connection.request('POST', '/api/stardew/conversation',
                           urlencode({'csrf_token': token, 'action': action, 'payload': '{}'}),
                           {'Content-Type': 'application/x-www-form-urlencoded'})
        response = connection.getresponse()
        value = (response.status, json.loads(response.read()))
        connection.close()
        return value
    try:
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
        # The Mario surface includes the ordinary request token.
        connection.request('GET', '/mario')
        page = connection.getresponse().read().decode()
        connection.close()
        token = re.search(r'data-csrf="([^"]+)"', page)[1]
        server.action_lock.acquire()
        try:
            status, result = post('start', token)
            assert status == 400 and 'transition' in result['error']
            assert post('reclaim', token)[0] == 200
            assert calls == ['reclaim']
        finally:
            server.action_lock.release()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_negation_stops_at_sentence_boundary_for_remaining_work():
    from smb3_agent.request_planning import is_negated
    text = "do not harvest. do not plant. do not water. clear farm-0-5"
    assert is_negated(text, text.index("harvest"))
    assert is_negated(text, text.index("plant"))
    assert is_negated(text, text.index("water"))
    assert not is_negated(text, text.index("clear"))
