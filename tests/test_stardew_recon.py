"""Simulated decision composition and guards; not native/model acceptance."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import threading

import pytest

from smb3_agent.stardew_recon import ReconAgent, fresh_finding, proposal
from smb3_agent.stardew_adapter import InputKind, OrdinaryInputDriver
from smb3_agent.conversation_service import StardewConversationService
from test_gc3_inspection import navigator, screen_at
from test_companion_ai import Provider, intent, decision, settled
from test_stardew_runtime import configured


def recon_intent(**changes):
    return intent((), canonical_command="reconnaissance", objective="Compare bare ground beside the mailbox and eastern crops",
                  constraints=["Inspect accessible ground first; leave all crops and vegetation alone"], **changes)


def prepared(tmp_path, replies):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime, _, state, commands = configured(tmp_path)
    state[0] = replace(state[0], position=screen_at(0, 0, True).position)
    runtime.navigator = navigator()
    def emit(command):
        commands.append(command)
        p = state[0].position
        dx, dy = {"s": (0,1), "w": (0,-1), "a": (-1,0), "d": (1,0)}[command.control]
        distance = min(12, command.duration_ms*.2)
        x, y = p.world_pixel_x+dx*distance, p.world_pixel_y+dy*distance
        state[0] = replace(state[0], position=screen_at(x,y,max(abs(x),abs(y)) <= 7).position)
    runtime.driver = OrdinaryInputDriver(keyboard=emit, neutralizer=lambda: None)
    runtime.driver.arm = lambda: None
    count = [0]
    def survey(**kw):
        count[0] += 1
        path = state[0].screenshot_references[0]
        return {"session_id": "session", "observation_id": "survey-"+str(count[0]),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "screenshot": path, "image_sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
                "image": "data:image/png;base64,AA", "targets": [
                    {"id": "survey-porch", "label": "Mailbox ground", "state": "empty_dirt", "access_observed": True},
                    {"id": "east-margin-a", "label": "Eastern ground", "state": "protected", "access_observed": False}]}
    runtime._planting_observer = survey
    runtime.observe()
    provider = Provider(replies)
    agent = runtime.gameplay_agent = ReconAgent(provider, recon_intent())
    plan = runtime.propose_recon("Compare bare ground", "chat", agent.intent)
    agent.plan_id = plan.plan_id
    runtime.review(plan)
    return runtime, plan, state, commands, provider


def finish(runtime):
    for _ in range(160):
        runtime.tick()
        if runtime.status != "running":
            break
    assert runtime.inspection_result["status"] == "completed", runtime.reason
    assert runtime.snapshot()["handback_confirmed"]


def test_fresh_findings_drive_changed_choices_and_independent_return(tmp_path):
    def adapt(role, supplied, cancel):
        assert supplied["findings"][0]["targets"][0]["state"] == "empty_dirt"
        assert supplied["prior_effects"][0]["effect"]["kind"] == "observation"
        return decision("move_viewpoint", "east-up", "Compare the new accessible porch ground with the eastern margin")
    runtime, plan, state, commands, provider = prepared(tmp_path, [
        decision("observe_current", "home"), adapt, decision("observe_current", "east-up"),
        decision("return_home", "farmhouse_entrance")])
    runtime.start(plan, background=False)
    finish(runtime)
    assert [f["viewpoint"] for f in runtime.inspection_result["observations"]] == ["home", "east-up"]
    assert provider.calls[-1][1]["findings"][-1]["targets"][0]["state"] == "protected"
    assert runtime.inspection_result["assessment_source"] == "model"
    assert commands and all(c.kind == InputKind.KEYBOARD and c.purpose == "navigate" for c in commands)
    assert state[0].energy == 20 and state[0].tool.watering_can_units == 5 and not state[0].crops[0].watered


def test_preference_variation_changes_observation_and_movement_composition(tmp_path):
    runtime, plan, state, commands, provider = prepared(tmp_path, [decision("observe_current", "home"),
        decision("return_home", "farmhouse_entrance", "Porch-only preference and observed access answer the question")])
    runtime.gameplay_agent.intent = recon_intent(target_ids=["home"], excluded_ids=["east-up"])
    plan = runtime.propose_recon("Only check the porch", "chat", runtime.gameplay_agent.intent)
    runtime.gameplay_agent.plan_id = plan.plan_id
    runtime.review(plan)
    runtime.start(plan, background=False)
    finish(runtime)
    assert not commands and len(runtime.inspection_result["observations"]) == 1
    assert provider.calls[0][1]["approved_scope"]["excluded_viewpoints"] == ["east-up"]


@pytest.mark.parametrize("reply", [decision("move_viewpoint", "unqualified"),
    decision("observe_current", "east-up"), decision("return_home", "cave")])
def test_stale_or_unapproved_targets_stop_without_movement(tmp_path, reply):
    runtime, plan, _, commands, _ = prepared(tmp_path, [reply])
    runtime.start(plan, background=False)
    runtime.tick()
    assert not commands and runtime.inspection_result["status"] == "stopped"
    assert runtime.snapshot()["handback_confirmed"]


@pytest.mark.parametrize("phase", ["pending", "movement"])
def test_stop_during_inference_or_movement_prevents_continuation(tmp_path, phase):
    entered, release = threading.Event(), threading.Event()
    def delayed(role, supplied, cancel):
        entered.set()
        release.wait(3)
        return decision("move_viewpoint", "east-up")
    runtime, plan, _, commands, _ = prepared(tmp_path, [delayed if phase == "pending" else decision("move_viewpoint", "east-up")])
    runtime.start(plan, background=False)
    if phase == "pending":
        worker = threading.Thread(target=runtime.tick)
        worker.start()
        assert entered.wait(2)
    else:
        runtime.tick()
        assert commands
    runtime.control("reclaim")
    count = len(commands)
    release.set()
    if phase == "pending":
        worker.join(3)
        assert not worker.is_alive()
    runtime.tick()
    assert len(commands) == count and runtime.snapshot()["handback_confirmed"]
    assert runtime.inspection_result.get("return_observation") is None


def test_review_tampering_and_return_reserve(tmp_path):
    runtime, plan, _, commands, provider = prepared(tmp_path, [])
    altered = replace(plan, resource_limits={**plan.resource_limits, "maximum_seconds": 900})
    runtime.review(altered)
    with pytest.raises(ValueError, match="scope"):
        runtime.start(altered, background=False)
    runtime.review(plan)
    runtime.start(plan, background=False)
    runtime.controller.authorization = replace(runtime.controller.authorization,
        expires_at=(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat())
    finish(runtime)
    assert not provider.calls and not commands
    assert runtime.inspection_result["question_status"] == "unanswered"


def test_observation_provenance_and_duplicate_rejection(tmp_path):
    runtime, _, state, _, _ = prepared(tmp_path, [])
    observed = runtime._planting_observer()
    fresh_finding(observed, state[0], "home", set())
    for changes in ({"session_id": "other"}, {"image_sha256": "wrong"},
                    {"observed_at": (datetime.now(timezone.utc)-timedelta(seconds=6)).isoformat()}):
        with pytest.raises(ValueError, match="fresh"):
            fresh_finding({**observed, **changes}, state[0], "home", set())
    with pytest.raises(ValueError, match="fresh"):
        fresh_finding(observed, state[0], "home", {observed["observation_id"]})


def test_ordinary_language_review_correction_and_historical_reopening(tmp_path):
    runtime, _, _, commands, _ = prepared(tmp_path, [])
    provider = Provider([recon_intent(), decision("observe_current", "home"),
                         decision("return_home", "farmhouse_entrance")])
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=provider)
    service.dispatch("message", {"text": "Investigate accessible ground and compare the eastern margin"})
    state = settled(service)
    plan = service._plan
    assert state["plan"]["normalized_intent"] == "inspect_recon" and not commands
    assert not state["reviewed"] and runtime.controller.authorization is None
    from smb3_agent.request_planning import ConversationPlan
    runtime.review(ConversationPlan.from_dict(plan))
    runtime.start(ConversationPlan.from_dict(plan), background=False)
    runtime.tick()
    service.snapshot()  # Findings persist while return is still pending.
    runtime.control("stop")
    service.snapshot()
    reopened_runtime, _, _, _, _ = prepared(tmp_path/"fresh", [])
    reopened = StardewConversationService(runtime=reopened_runtime, artifacts_root=tmp_path/"chat", provider=Provider([])).snapshot()
    assert reopened["inspection_result"]["historical"] and reopened["inspection_result"]["observations"]
    assert reopened["plan"] is None and not reopened["reviewed"]
    assert reopened_runtime.controller.authorization is None
    assert reopened_runtime.inspection_result is None
    history = StardewConversationService(runtime=reopened_runtime, artifacts_root=tmp_path/"chat", provider=Provider([]))._context()["reconnaissance_history"]
    assert history["historical"] and not history["input_authority"]
    assert history["findings"][0]["viewpoint"] == "home"


def test_correction_invalidates_review_and_rejects_prior_start(tmp_path):
    runtime, _, _, commands, _ = prepared(tmp_path, [])
    provider = Provider([recon_intent(), recon_intent(target_ids=["home"], excluded_ids=["east-up"], interaction="correction")])
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=provider)
    service.dispatch("message", {"text": "Compare the porch and eastern margin"})
    first = settled(service)["plan"]
    service.dispatch("apply", {"expected_plan_id": first["plan_id"], "expected_revision": first["revision"]})
    service.dispatch("message", {"text": "Actually only investigate the porch; avoid the eastern view"})
    state = settled(service)
    assert not state["reviewed"] and state["plan"]["actions"][0]["target_ids"] == ["home"]
    with pytest.raises(ValueError, match="plan changed"):
        service.dispatch("start", {"expected_plan_id": first["plan_id"], "expected_revision": first["revision"]})
    assert not commands and runtime.controller.authorization is None


def test_contextual_intent_uses_executable_capability_identifiers(tmp_path):
    runtime, _, _, commands, _ = prepared(tmp_path, [])
    class SchemaProvider(Provider):
        def infer(self, role, supplied, schema, cancel, **kwargs):
            assert schema["properties"]["canonical_command"]["enum"] == [
                "water", "reconnaissance", "inspect_eastern_margin", "inspect_farm_cave", "discuss_planting", ""]
            return recon_intent(canonical_command="inspect the eastern margin")
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path/"chat", provider=SchemaProvider([]))
    service.dispatch("message", {"text": "Investigate the eastern margin"})
    state = settled(service)
    assert state["ai"]["state"] == "failed" and state["plan"] is None and not commands


def test_deadline_late_reply_returns_instead_of_starting_movement(tmp_path, monkeypatch):
    import smb3_agent.stardew_recon as module
    class Deadline:
        def __init__(self, cancel):
            self.cancel, self.expired = cancel, False
        def is_set(self):
            return self.cancel.is_set() or self.expired
    def delayed(role, supplied, cancel):
        cancel.expired = True
        return decision("move_viewpoint", "east-up")
    monkeypatch.setattr(module, "DecisionCancellation", Deadline)
    runtime, plan, _, commands, _ = prepared(tmp_path, [delayed])
    runtime.start(plan, background=False)
    finish(runtime)
    assert not commands and runtime.inspection_result["question_status"] == "unanswered"
    assert "Inference time limit" in runtime.inspection_result["return_reason"]
    assert runtime.gameplay_agent.records[0]["role"] == "recon-controller"
    assert runtime.inspection_result["assessment_source"] == "controller"


def test_short_limits_refuse_and_excluded_porch_inspection_still_requires_return(tmp_path):
    runtime, _, _, _, _ = prepared(tmp_path, [])
    with pytest.raises(ValueError, match="time limit"):
        proposal(runtime.screen, runtime.navigator, "Check in 20 seconds", "chat", recon_intent())
    plan = proposal(runtime.screen, runtime.navigator, "Check east", "chat", recon_intent(excluded_ids=["home"]))
    assert plan.actions[0].target_ids == ("east-up",) and plan.stop_point == "farmhouse_entrance"
    assert "transit" in plan.fallback_explanation
    plan = proposal(runtime.screen, runtime.navigator, "Only observe porch within one minute", "chat", recon_intent(target_ids=["home"]))
    assert plan.resource_limits["maximum_seconds"] == 60
