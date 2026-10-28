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
