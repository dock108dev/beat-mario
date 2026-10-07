from types import SimpleNamespace
import threading

import pytest
from PIL import Image

from smb3_agent.stardew_adapter import StardewAdapterError, WindowObservation
from smb3_agent.stardew_preparation import GoalPreparation, porch_action
from smb3_agent.stardew_runtime import StardewRuntime


@pytest.mark.parametrize("position, action", [((0, -60), "s"), ((10, -30), "a"), ((-10, -30), "d"), ((0, 0), None)])
def test_observed_entrance_position_changes_preparation(position, action):
    profile = SimpleNamespace(geometry=lambda _: ([], (0, 0), position, 2))
    assert porch_action(profile, None) == (action, position)


def test_preparation_refuses_unrecognized_corridor():
    profile = SimpleNamespace(geometry=lambda _: ([], (0, 0), (80, -30), 2))
    with pytest.raises(StardewAdapterError, match="outside the supported entrance corridor"):
        porch_action(profile, None)


def test_stop_during_preparation_inference_prevents_late_native_action(tmp_path, monkeypatch):
    import smb3_agent.candidate_resources as resources
    import smb3_agent.stardew_adapter as adapter
    import smb3_agent.stardew_farm_vision as vision
    import smb3_agent.stardew_input as inputs
    import smb3_agent.stardew_setup as setup
    (tmp_path / "prepared-source.json").write_text("{}")
    entered, release = threading.Event(), threading.Event()
    commands = []
    class Provider:
        status = {"available": True}
        def infer(self, *args, **kwargs):
            entered.set()
            assert release.wait(3)
            return {"screen": "bedroom", "action": "left", "reason": "Visible exit is left"}
    class Profile:
        viewport_size = (1512, 949)
        def __init__(self, *_):
            pass
        def qualified(self):
            return True
        def geometry(self, image):
            raise StardewAdapterError("not farm")
    window = WindowObservation(42, "start", "window", "Stardew", (0, 33, 1512, 949), True, True, True)
    class Native:
        def __init__(self, **kwargs):
            pass
        def activate_window(self, **kwargs):
            return window
        def detect_window(self):
            return window
        def capture(self, window, path):
            Image.new("RGB", (1512, 949)).save(path)
            return path
    class Driver:
        def __init__(self, **kwargs):
            pass
        def arm(self):
            commands.append("arm")
        def send(self, command):
            commands.append(command)
        def neutralize(self):
            pass
    monkeypatch.setattr(resources, "calibration_registration", lambda: {"manifest": "fixture"})
    monkeypatch.setattr(vision, "PreparedFarmPixelProfile", Profile)
    monkeypatch.setattr(adapter, "MacVisibleStardewBackend", Native)
    monkeypatch.setattr(inputs, "MacOrdinaryInputDriver", Driver)
    monkeypatch.setattr(setup, "_verify_engineering_launch_identity", lambda *_: None)
    runtime = StardewRuntime()
    launch = SimpleNamespace(process_id=42, process_started_at="start", root=str(tmp_path), status=lambda: {})
    runtime._engineering_launches = [(launch, SimpleNamespace(poll=lambda: None))]
    preparation = runtime._goal_preparation = GoalPreparation(runtime, Provider())
    preparation.start()
    assert entered.wait(3)
    runtime.control("reclaim")
    release.set()
    preparation.worker.join(3)
    assert not preparation.worker.is_alive()
    assert commands == []
    assert preparation.result["status"] == "stopped"
    assert runtime.snapshot()["handback_confirmed"] is True
