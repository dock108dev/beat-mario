"""Simulated conversation routing; none of these tests establishes live evidence."""
from dataclasses import replace
from copy import deepcopy

import pytest

from smb3_agent.conversation_service import StardewConversationService
from smb3_agent.conversation_ui import render_stardew_conversation_workspace, STARDEW_CONVERSATION_JS
from smb3_agent.request_planning import Planner, PlanningContext


def live_context():
    targets = [{"id": "c1", "kind": "crop", "planted": True, "watered": False, "visible": True, "confidence": 1},
               {"id": "c2", "kind": "crop", "planted": True, "watered": True, "visible": True, "confidence": 1}]
    return PlanningContext(game_id="stardew", conversation_id="conversation", session_id="session", observation_id="screen",
        observation_fresh=True, observation={"source": "automatic_visible", "validated": True,
        "complete_initial_set": True, "isolation_verified": True, "initial_target_ids": ["c1", "c2"],
        "return_point": "farmhouse_entrance", "targets": targets})


class FakeStardewRuntime:
    def __init__(self):
        self.context = live_context()
        self.calls = []
        self.state = {"status": "ready", "owner": "player", "observation": self.context.observation, "outcome": None}

    def snapshot(self):
        return deepcopy(self.state)

    def planning_context(self, conversation_id, current_plan):
        return replace(self.context, conversation_id=conversation_id, current_plan=current_plan)

    def review(self, plan):
        self.calls.append(("review", plan))

    def start(self, plan):
        self.calls.append(("start", plan))
        self.state.update(status="running", owner="agent", outcome={"attempt_id": "fixture-attempt", "status": "active"})

    def control(self, action):
        self.calls.append((action,))
        self.state.update(status="stopped", owner="player", outcome={"attempt_id": "fixture-attempt", "status": "reclaimed", "neutralized": True})

    def observe(self):
        return self.snapshot()

    def setup(self, payload):
        self.calls.append(("setup", payload))
        self.context = replace(self.context, session_id="reset-session")

    def close(self):
        self.control("stop")


def request(service, text="Water all initially planted crops"):
    return service.dispatch("message", {"text": text})


def identity(state):
    return {"expected_plan_id": state["plan"]["plan_id"], "expected_revision": state["plan"]["revision"]}


def test_complete_set_live_eligibility_is_not_authority():
    result = Planner().plan("Water all initially planted crops", live_context())
    assert result.plan.execution_eligibility == "requires_runtime_validation"
    assert result.plan.actions[0].target_ids == ("c1", "c2")
    assert result.plan.authorization_scope["granted"] is False
    assert result.plan.stop_point == "farmhouse_entrance"


def test_live_narrowing_is_blocked_and_b4_stays_unavailable():
    context = live_context()
    narrow = Planner().plan("Water c1", context)
    assert narrow.kind == "clarification"
    assert "all initially" in narrow.message
    harvest = Planner().plan("Harvest all observed crops", context)
    assert harvest.plan.execution_eligibility == "unavailable_live"
    assert "B4" in harvest.message


@pytest.mark.parametrize("field,value", [("source", "fixture"), ("validated", False),
                                             ("complete_initial_set", False), ("isolation_verified", False)])
def test_missing_live_preconditions_never_enable_planner(field, value):
    context = live_context()
    result = Planner().plan("Water all initially planted crops", replace(context, observation={**context.observation, field:value}))
    assert result.plan.execution_eligibility == "unavailable_live"


def test_service_review_start_and_changed_revision_are_exact(tmp_path):
    runtime = FakeStardewRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    proposed = request(service)
    assert not runtime.calls
    with pytest.raises(ValueError, match="Review this exact"):
        service.dispatch("start", identity(proposed))
    reviewed = service.dispatch("apply", identity(proposed))
    assert reviewed["reviewed"]
    changed = request(service, "Leave at least 20 energy")
    with pytest.raises(ValueError, match="plan changed"):
        service.dispatch("start", identity(proposed))
    with pytest.raises(ValueError, match="Review this exact"):
        service.dispatch("start", identity(changed))
    service.dispatch("apply", identity(changed))
    service.dispatch("start", identity(changed))
    assert [call[0] for call in runtime.calls] == ["review", "review", "start"]


def test_active_poll_does_not_freeze_terminal_history(tmp_path):
    runtime = FakeStardewRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    state = request(service)
    service.dispatch("apply", identity(state))
    service.dispatch("start", identity(state))
    assert service.snapshot()["history"] == []
    ended = service.dispatch("reclaim")
    assert ended["history"][0]["status"] == "reclaimed"
    assert ended["history"][0]["neutralized"] is True
    reopened = StardewConversationService(runtime=FakeStardewRuntime(), artifacts_root=tmp_path)
    assert reopened.snapshot()["plan"] is None
    assert not reopened.snapshot()["reviewed"]
    assert reopened.snapshot()["history"][0]["status"] == "reclaimed"


def test_reset_and_focus_loss_invalidate_review(tmp_path):
    runtime = FakeStardewRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    state = request(service)
    service.dispatch("apply", identity(state))
    assert not service.dispatch("focus_lost")["reviewed"]
    state = service.dispatch("reset", {"destination": "/explicit/new-copy"})
    assert state["plan"] is None and state["selected_target_ids"] == []
    assert runtime.calls[-1] == ("setup", {"action": "reset", "destination": "/explicit/new-copy"})


def test_contextual_remaining_unknown_does_not_invent_resources(tmp_path):
    service = StardewConversationService(runtime=FakeStardewRuntime(), artifacts_root=tmp_path)
    state = request(service, "what is left?")
    assert state["plan"] is None
    assert "unknown" in state["messages"][-1]["text"]


def test_workspace_controls_setup_consent_and_stable_editable_nodes():
    rendered = render_stardew_conversation_workspace(csrf_token="token")
    for marker in ("stardew-draft", 'data-action="reclaim"', 'name="copy_authorized"',
                   'name="setup_source_kind"', 'data-action="reset"', 'id="stardew-review"', 'id="stardew-start"'):
        assert marker in rendered
    assert "innerHTML" not in STARDEW_CONVERSATION_JS
    assert 'draft.value === submitted' in STARDEW_CONVERSATION_JS
    assert "focus_lost" in STARDEW_CONVERSATION_JS
    assert "/api/stardew/conversation" in STARDEW_CONVERSATION_JS


def test_ordinary_http_routes_stardew_without_mario_runtime(tmp_path):
    import http.client
    import json
    import threading
    from urllib.parse import urlencode
    from smb3_agent.lab_ui import _new_lab_ui_server
    from smb3_agent.companion_catalog import CatalogPreferenceStore, CatalogSession

    server = _new_lab_ui_server("127.0.0.1", 0)
    runtime = FakeStardewRuntime()
    server.stardew_conversation_service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path / "stardew")
    # Avoid relying on the user's selected catalog adapter.
    server.catalog_session = CatalogSession(server.catalog_session.registry, CatalogPreferenceStore(tmp_path / "catalog.json"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def call(method, path, fields=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(method, path, body=urlencode(fields) if fields else None,
                           headers={"Content-Type": "application/x-www-form-urlencoded"} if fields else {})
        response = connection.getresponse()
        data = response.read().decode()
        connection.close()
        return response.status, data
    try:
        status, page = call("GET", "/stardew")
        assert status == 200 and "stardew-draft" in page and "mario-conversation" not in page
        status, body = call("POST", "/api/stardew/conversation", {
            "csrf_token": server.csrf_token, "action": "message", "payload": json.dumps({"text": "Water all initially planted crops"})})
        assert status == 200
        assert json.loads(body)["game_id"] == "stardew"
        assert runtime.calls == []
        status, _ = call("POST", "/api/stardew/conversation", {"action": "start", "payload": "{}"})
        assert status == 403
        assert runtime.calls == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_questions_and_controls_never_activate_observation(tmp_path):
    class ObservationSpy(FakeStardewRuntime):
        def observe(self):
            self.calls.append(("observe",))
            return super().observe()
    runtime = ObservationSpy()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    request(service, "Could we water all observed crops?")
    request(service, "what is left?")
    request(service, "pause")
    assert not any(call[0] == "observe" for call in runtime.calls)
    request(service, "Water all initially planted crops")
    assert runtime.calls[-1] == ("observe",)


def test_engineering_launch_requires_explicit_action_and_invalidates_plan(tmp_path):
    runtime = FakeStardewRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    request(service)
    service.snapshot()
    render_stardew_conversation_workspace(service.snapshot())
    assert runtime.calls == []
    result = service.dispatch("launch_engineering")
    assert runtime.calls == [("setup", {"action": "launch_engineering"})]
    assert result["plan"] is None and not result["reviewed"]


def test_loading_check_never_accepts_browser_evidence_or_permission(tmp_path):
    class SetupRuntime(FakeStardewRuntime):
        def verify_engineering_session(self):
            self.calls.append(("verify_engineering_session",))
    runtime = SetupRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    planned = request(service)
    service.dispatch("apply", identity(planned))
    checked = service.dispatch("verify_engineering_session", {
        "input_ready": True, "classification": "actual_live", "loading": {"verified": True}})
    assert runtime.calls[-1] == ("verify_engineering_session",)
    assert checked["plan"] is None and not checked["reviewed"]
    assert not any(call[0] == "start" for call in runtime.calls)


def test_profile_connection_accepts_only_server_registered_identity(tmp_path):
    class SetupRuntime(FakeStardewRuntime):
        def connect_profile(self, profile_id):
            self.calls.append(("connect_profile", profile_id))
    runtime = SetupRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    with pytest.raises(ValueError, match="Choose a qualified"):
        service.dispatch("connect_profile", {"profile_id": "invented", "qualified": True,
                                             "profile": {"classification": "actual_live"}})
    assert runtime.calls == []
    runtime.state["qualified_profiles"] = [{"profile_id": "retained-profile", "label": "Retained test profile"}]
    result = service.dispatch("connect_profile", {"profile_id": "retained-profile", "input_ready": True,
                                                 "profile": {"classification": "actual_live"}})
    assert runtime.calls == [("connect_profile", "retained-profile")]
    assert result["plan"] is None and not result["reviewed"]


def test_source_setup_cannot_smuggle_runtime_actions_or_verified_flags(tmp_path):
    runtime = FakeStardewRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    service.dispatch("setup", {"source": "/selected/source", "destination": "/new/copy", "copy_authorized": True,
                               "action": "launch_engineering", "input_ready": True, "profile": {"qualified": True}})
    assert runtime.calls == [("setup", {"source": "/selected/source", "destination": "/new/copy", "copy_authorized": True})]


def test_setup_checklist_and_profiles_are_readonly_server_state():
    rendered = render_stardew_conversation_workspace()
    assert 'data-action="verify_engineering_session"' in rendered
    assert 'data-action="connect_profile"' in rendered
    assert 'id="stardew-setup-steps"' in rendered
    assert "No qualified profile available" in rendered
    assert 'id="stardew-connect" type="submit" disabled' in rendered
    assert "run.qualified_profiles || []" in STARDEW_CONVERSATION_JS
    assert "run.setup_steps || []" in STARDEW_CONVERSATION_JS


def test_status_poll_caches_history_summaries_preserving_full_evidence(tmp_path, monkeypatch):
    import json
    service = StardewConversationService(runtime=FakeStardewRuntime(), artifacts_root=tmp_path)
    evidence = {'status': 'reclaimed', 'inputs': [{'actual': 'retained'}],
                'after_observations': [{'crop': 'visible'}]}
    path = service.history.record('retained-proof', evidence)
    state = service.snapshot()
    assert 'inputs' not in state['history'][0]
    assert state['history'][0]['evidence_path'] == str(path)
    assert json.loads(path.read_text())['inputs'] == evidence['inputs']
    monkeypatch.setattr(service.history, 'list', lambda: (_ for _ in ()).throw(AssertionError('history reread during poll')))
    assert service.snapshot()['history'] == state['history']
