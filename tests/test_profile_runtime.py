from dataclasses import asdict, replace
import threading
import time

import pytest
from PIL import Image

from smb3_agent.game_profiles import ClickSkill, ExecutableProfile, NumberSensor, ProfileError
from smb3_agent.model_gateway import LocalOllamaGateway, ModelGatewayError, ModelLimits
from smb3_agent.profile_runtime import ProfileRuntime, ProposalAdapter
from smb3_agent.request_planning import PlanningContext
from smb3_agent.screen_host import Frame, ScreenHostError, TextRegion
from smb3_agent.stardew_adapter import WindowObservation


BOX = (.2, .6, .2, .05)


def profile():
    return ExecutableProfile("test", "third", "1", "test-settings", "vision:local", (800, 600),
        (NumberSensor("cash", "Cash: £([0-9,]+)", (0, 0, 1, 1)),
         NumberSensor("loan", "Loan: £([0-9,]+)", (0, 0, 1, 1))),
        (ClickSkill("repay", "repay-button", "Repay £10,000", (0, 0, 1, 1),
                    (("cash", -10000), ("loan", -10000)),
                    (("cash", 100000), ("loan", 100000)), "Repay once", request_verbs=("repay", "pay back")),), ("build", "delete"))


def reply(**changes):
    return {"status": "propose", "skill_id": "repay", "target_id": "repay-button",
            "box": list(BOX), "confidence": 1, **changes}


class Host:
    def __init__(self, root):
        self.root = root
        self.window = WindowObservation(123, "started", "7", "test", (0, 0, 800, 600), True, True, True)
        self.value = 100000
        self.ambiguous = False
        self.stale = False
        self.calls = 0

    def detect_window(self):
        return self.window

    def observe(self, root):
        import hashlib
        self.calls += 1
        path = self.root / f"frame-{self.calls}.png"
        Image.new("RGB", (800, 600)).save(path)
        text = [TextRegion(f"Cash: £{self.value:,}", (.1, .1, .3, .03), 1),
                TextRegion(f"Loan: £{self.value:,}", (.1, .2, .3, .03), 1),
                TextRegion("Repay £10,000", BOX, 1)]
        if self.ambiguous:
            text.append(TextRegion("Repay £10,000", (.5, .6, .2, .05), 1))
        return Frame(str(self.calls), time.monotonic()-(10 if self.stale else 0), self.window,
                     path, hashlib.sha256(path.read_bytes()).hexdigest(), tuple(text))


class Driver:
    def __init__(self, runtime):
        self.runtime = runtime
        self.sent = []
        self.last_pulse_timing = {}
        self.receipt = True
        self.effect = True
        self.entered, self.unblock = threading.Event(), threading.Event()
        self.block = False

    def arm(self):
        self.runtime.require_authority()
        self.unblock.clear()

    def send(self, command):
        self.runtime.require_authority()
        self.sent.append(command)
        if command.action == "move":
            return
        self.entered.set()
        if self.block:
            self.unblock.wait(1)
            self.runtime.require_authority()
        if self.effect:
            self.runtime.host.value -= 10000

    def neutralize(self):
        self.unblock.set()

    def release_receipt(self):
        return {"confirmed": self.receipt}


class Gateway:
    model = "vision:local"
    limits = ModelLimits()

    def __init__(self):
        self.usage = []
        self.entered, self.unblock = threading.Event(), threading.Event()
        self.block = False
        self.response = reply()

    def propose(self, frame, context, cancel):
        self.entered.set()
        if self.block:
            self.unblock.wait(1)  # deliberately ignores cancel to exercise late reply
        return self.response


def runtime(tmp_path):
    return ProfileRuntime(profile=profile(), host=Host(tmp_path), gateway=Gateway(), driver_factory=Driver,
                          root=tmp_path / "attempt", isolation_receipt={"disposable": True,
                          "load_save_verified": True, "evidence_references": ["fixture-only"]})


def reviewed(rt):
    plan = rt.propose("please repay once").plan
    rt.review(plan)
    return plan


def test_useful_outcome_requires_fresh_integer_reconciliation_and_release(tmp_path):
    rt = runtime(tmp_path)
    result = rt.start(reviewed(rt))
    assert result["status"] == "completed"
    assert result["after_values"] == {"cash": 90000, "loan": 90000}
    assert len(rt.history.list()) == 1
    rt.session.validate()
    assert not rt._authority


@pytest.mark.parametrize("bad", [
    {"success": True}, {"confidence": float("nan")}, {"box": [True, 0, .1, .1]},
    {"skill_id": "delete"}, {"target_id": "other"}, {"status": "completed"},
])
def test_structured_rejection_cannot_grant_authority(bad):
    with pytest.raises(ProfileError):
        ProposalAdapter(profile(), reply(**bad)).propose("repay", PlanningContext())


@pytest.mark.parametrize("failure", ["ambiguous", "stale", "wrong_window", "wrong_grounding"])
def test_bad_observation_never_dispatches(tmp_path, failure):
    rt = runtime(tmp_path)
    if failure == "wrong_window":
        rt.host.window = replace(rt.host.window, foreground=False)
    elif failure == "wrong_grounding":
        rt.gateway.response = reply(box=[.8, .8, .1, .1])
    else:
        setattr(rt.host, failure, True)
    with pytest.raises((ProfileError, ScreenHostError)):
        rt.propose("repay once")
    assert not rt.driver.sent and not rt._authority


def test_cancellation_does_not_wait_for_inference_and_late_reply_is_discarded(tmp_path):
    rt = runtime(tmp_path)
    rt.gateway.block = True
    errors = []
    def propose():
        try:
            rt.propose("repay")
        except ProfileError as exc:
            errors.append(str(exc))
    thread = threading.Thread(target=propose)
    thread.start()
    assert rt.gateway.entered.wait(1)
    start = time.monotonic()
    assert rt.control("reclaim")["confirmed"]
    assert time.monotonic()-start < .1
    rt.gateway.unblock.set()
    thread.join(2)
    assert errors and "Late reply" in errors[0]
    assert rt._current is None and not rt.driver.sent


def test_stop_during_active_dispatch_retains_partial(tmp_path):
    rt = runtime(tmp_path)
    plan = reviewed(rt)
    rt.driver.block = True
    results = []
    thread = threading.Thread(target=lambda: results.append(rt.start(plan)))
    thread.start()
    assert rt.driver.entered.wait(1)
    assert rt.control("stop")["confirmed"]
    thread.join(2)
    assert results[0]["status"] == "partial"
    assert rt.host.value == 100000 and not rt._authority


@pytest.mark.parametrize("failure", ["no_effect", "no_receipt", "state_changed", "focus_lost"])
def test_false_success_prevention(tmp_path, failure):
    rt = runtime(tmp_path)
    plan = reviewed(rt)
    if failure == "no_effect":
        rt.driver.effect = False
    elif failure == "no_receipt":
        rt.driver.receipt = False
    elif failure == "state_changed":
        rt.host.value = 80000
    else:
        rt.host.window = replace(rt.host.window, foreground=False)
    assert rt.start(plan)["status"] != "completed"
    assert not rt._authority


def test_correction_supersedes_review_and_old_revision(tmp_path):
    rt = runtime(tmp_path)
    first = reviewed(rt)
    rt.gateway.response = reply(status="refuse")
    correction = rt.propose("do not repay; leave the money alone")
    assert correction.kind == "clarification" and correction.plan.revision == 2
    assert rt.start(first)["status"] == "failed"
    assert not rt.driver.sent


def test_profile_rejects_invented_code_and_incompatible_backend(tmp_path):
    with pytest.raises(ProfileError):
        ExecutableProfile.from_dict({**asdict(profile()), "code": "print('invented')"})
    with pytest.raises(ProfileError):
        ProfileRuntime(
            profile=replace(profile(), backend_id="other"), host=Host(tmp_path), gateway=Gateway(),
            driver_factory=Driver, root=tmp_path / "bad", isolation_receipt={"disposable": True,
            "load_save_verified": True, "evidence_references": ["fixture"]})


def test_gateway_budget_prevents_backend_call(tmp_path):
    frame = Host(tmp_path).observe(tmp_path)
    gw = LocalOllamaGateway("vision:local", limits=ModelLimits(calls=1))
    gw.calls = 1
    with pytest.raises(ModelGatewayError, match="budget"):
        gw.propose(frame, {}, threading.Event())
    gw.calls = 0
    gw.started -= 1000
    with pytest.raises(ModelGatewayError, match="time budget"):
        gw.propose(frame, {}, threading.Event())


def test_gateway_rejects_cloud_and_invalid_budgets():
    with pytest.raises(ModelGatewayError):
        LocalOllamaGateway("vision:cloud")
    with pytest.raises(ModelGatewayError):
        LocalOllamaGateway("vision:local", limits=ModelLimits(output_tokens=100000))


def test_gateway_timeout_kills_worker_and_records_consumed_call(tmp_path, monkeypatch):
    import smb3_agent.model_gateway as module
    class Hung:
        returncode = None
        killed = False
        def __init__(self, *args, **kwargs):
            pass
        def poll(self):
            return -9 if self.killed else None
        def kill(self):
            self.killed = True
        def wait(self, timeout):
            return -9
    processes = []
    def worker(*args, **kwargs):
        child = Hung()
        processes.append(child)
        return child
    monkeypatch.setattr(module.subprocess, "Popen", worker)
    gateway = LocalOllamaGateway("vision:local", limits=ModelLimits(call_seconds=.03))
    monkeypatch.setattr(gateway, "describe", lambda: {})
    with pytest.raises(ModelGatewayError, match="deadline"):
        gateway.propose(Host(tmp_path).observe(tmp_path), {}, threading.Event())
    assert processes[0].killed and gateway.calls == 1
    assert gateway.usage[0]["usage_known"] is False


def test_advisory_and_old_review_after_stop_cannot_execute(tmp_path):
    rt = runtime(tmp_path)
    advisory = rt.propose("What would repaying do?")
    assert advisory.kind == "advisory"
    with pytest.raises(ProfileError):
        rt.review(advisory.plan)
    plan = reviewed(rt)
    rt.control("reclaim")
    assert rt.start(plan)["status"] == "failed"
    assert not rt.driver.sent


def test_number_detector_rejects_ambiguous_contradictory_and_executable_patterns(tmp_path):
    host = Host(tmp_path)
    frame = host.observe(tmp_path)
    bad = replace(frame, text=(*frame.text, TextRegion("Cash: £90,000", (.5, .1, .3, .03), 1)))
    with pytest.raises(ProfileError, match="ambiguous"):
        profile().values(bad)
    for pattern in ("(a+)+", "£([0-9,]+).*", "£([0-9,]+)([0-9,]+)"):
        with pytest.raises(ProfileError):
            replace(profile(), sensors=(replace(profile().sensors[0], pattern=pattern), profile().sensors[1])).validate()


def test_click_gutter_stays_in_reviewed_region(tmp_path):
    rt = runtime(tmp_path)
    rt.profile = replace(rt.profile, skills=(replace(rt.profile.skills[0], click_anchor="label_left_gutter",
                                                   target_region=BOX),))
    result = rt.start(reviewed(rt))
    assert result["status"] == "failed" and "hit region" in result["reason"]
    assert not rt.driver.sent


def test_unconfirmed_release_blocks_chat_and_fresh_authority(tmp_path):
    rt = runtime(tmp_path)
    rt.driver.receipt = False
    with pytest.raises(ProfileError, match="Neutral receipt"):
        rt.begin_chat()
    with pytest.raises(ProfileError, match="Neutral receipt"):
        rt.propose("repay once")
    assert not rt.driver.sent and not rt._authority


def test_named_action_and_negation_guard_is_independent_of_model():
    adapter = ProposalAdapter(profile(), reply())  # deliberately confident/wrong backend
    assert adapter.propose("use the loan button", PlanningContext()).ambiguities
    assert adapter.propose("do not repay", PlanningContext()).ambiguities
    assert adapter.propose("pay back the loan once", PlanningContext()).actions


def test_json_profile_parameters_are_frozen():
    data = asdict(profile())
    loaded = ExecutableProfile.from_dict(data)
    assert isinstance(loaded.skills[0].required_before, tuple)
    assert isinstance(loaded.sensors[0].region, tuple)


def test_isolation_receipt_required(tmp_path):
    with pytest.raises(ProfileError, match="disposable"):
        ProfileRuntime(profile=profile(), host=Host(tmp_path), gateway=Gateway(), driver_factory=Driver,
                       root=tmp_path / "bad", isolation_receipt={})


def test_retained_frame_mutation_and_geometry_change_are_rejected(tmp_path):
    host = Host(tmp_path)
    frame = host.observe(tmp_path)
    with pytest.raises(ScreenHostError):
        frame.require_fresh(replace(host.window, bounds=(10, 0, 800, 600)), 2)
    frame.path.write_bytes(b"changed")
    with pytest.raises(ScreenHostError):
        frame.require_fresh(host.window, 2)


def test_profile_catalog_uses_shared_registry_and_safe_switch_contract(tmp_path):
    from smb3_agent.companion_catalog import CatalogRegistry
    from smb3_agent.profile_catalog import ProfileCatalogProvider
    rt = runtime(tmp_path)
    provider = ProfileCatalogProvider(rt.profile, rt)
    registry = CatalogRegistry((provider,))
    assert registry.entry("third").availability == "setup_required"
    rt.propose("repay once")
    assert provider.retain_for_switch()
    assert provider.invalidate_volatile_state()
    assert rt.frame is None and rt._current is None


@pytest.mark.parametrize("acknowledged", [True, False])
def test_native_release_waits_for_os_acknowledgment_with_bounded_deadline(monkeypatch, acknowledged):
    from types import SimpleNamespace
    from smb3_agent import ordinary_input
    from smb3_agent.ordinary_input import MacProfileInput
    elapsed = [0.]
    monkeypatch.setattr(ordinary_input.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(ordinary_input.time, "sleep", lambda seconds: elapsed.__setitem__(0, elapsed[0]+seconds))
    native = SimpleNamespace(kCGEventSourceStateHIDSystemState=0, kCGMouseButtonLeft=0, kCGMouseButtonRight=1,
        CGEventSourceKeyState=lambda source, code: False,
        CGEventSourceButtonState=lambda source, button: button == 0 and (not acknowledged or elapsed[0] < .003))
    driver = MacProfileInput.__new__(MacProfileInput)
    driver.q, driver._lock, driver._held = native, threading.RLock(), []
    receipt = driver.release_receipt()
    assert receipt["confirmed"] is acknowledged
    assert receipt["ledger_empty"]
    assert .003 <= elapsed[0] <= .051
    if not acknowledged:
        assert receipt["held_mouse_buttons"] == [0]
