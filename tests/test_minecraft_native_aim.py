"""Native composition boundaries with simulated ports; no gameplay input."""

from dataclasses import replace
import threading
import time
from types import SimpleNamespace

import pytest

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.minecraft_camera_skill import MinecraftCameraSkill
from smb3_agent.minecraft_native import MinecraftNativeRuntime
from smb3_agent.minecraft_scene import CellEvidence
from smb3_agent.minecraft_wall import CompositeBudget
from test_feedback_contracts import calibration, observation
from test_player_beta import obs


@pytest.mark.parametrize("axis", ["heading", "pitch"])
@pytest.mark.parametrize("error,accepted", [(0.29, True), (0.34, False)])
def test_aim_completion_matches_provider_uncertainty_boundary(
    tmp_path, monkeypatch, axis, error, accepted
):
    import smb3_agent.minecraft_native as module

    native = object.__new__(MinecraftNativeRuntime)
    native.cal, native.epoch, native.root = calibration(), 1, tmp_path
    native.canceled, native.events = threading.Event(), []
    native.budget = CompositeBudget(native.canceled.is_set)
    native.detector = None
    native.view = lambda: observation(at=time.monotonic() - 0.02)
    native._publish = lambda owner: None
    native.neutralize = lambda: {"confirmed": True}
    monkeypatch.setattr(
        module,
        "observed_spatial",
        lambda *args, **kwargs: SimpleNamespace(position=(0, 0, 0)),
    )
    monkeypatch.setattr(module, "native_hid_receipt", lambda: {"confirmed": True})

    class Guard:
        def __init__(self, *args):
            pass

        def pulse(self, action):
            pytest.fail("An unresolvable sub-unit goal must never emit native input")

    monkeypatch.setattr(module, "CameraMotionGuard", Guard)
    goal = {"heading": 0, "pitch": 0, axis: error}
    provider = MinecraftCameraSkill(native.cal, native.epoch)
    provider.validate("aim", goal)
    if accepted:
        assert provider.next("aim", goal, native.view(), {}) is None
        final = native.aim(**goal)
        assert final.heading == final.pitch == 0
        assert not native.events
    else:
        with pytest.raises(FeedbackError, match="calibrated precision"):
            provider.next("aim", goal, native.view(), {})
        with pytest.raises(FeedbackError, match="calibrated precision"):
            native.aim(**goal)
        assert native.events[-1]["result"]["status"] == "partial"


@pytest.mark.parametrize(
    "change",
    [
        {"position": (0.53, 0, -2)},
        {"window_identity": (999, "different-window")},
        {"settings": "different-settings"},
        {"captured_at": -0.2},
        {"captured_at": -1},
        {"captured_at": 1},
        None,
    ],
)
def test_place_reinspects_cached_air_after_pose_or_evidence_change(change):
    now = time.monotonic()
    current = replace(obs(), captured_at=now - 0.05)
    cell = (0, 0, 0)
    evidence = CellEvidence(
        cell, None, now - 0.1, "pixels", current.window_identity, current.settings
    )
    native = object.__new__(MinecraftNativeRuntime)
    native.latest_inspection = (evidence, current.position)
    native.last_spatial = current

    def approach(_):
        if change is None:
            native.last_spatial = None
        else:
            update = dict(change)
            if "captured_at" in update:
                update["captured_at"] += now
            native.last_spatial = replace(current, **update)

    inspected = []
    native.approach = approach
    native.inspect = lambda cell: inspected.append(cell) or None
    native._driver = lambda: pytest.fail("Unknown cell must stop before input")
    with pytest.raises(FeedbackError, match="independently clear"):
        native.place(cell, "minecraft:stone")
    assert inspected == [cell]


def test_place_can_reuse_current_same_pose_inspection_for_existing_block():
    now = time.monotonic()
    current = replace(obs(), captured_at=now - 0.05)
    cell = (0, 0, 0)
    evidence = CellEvidence(
        cell,
        "minecraft:stone",
        now - 0.1,
        "pixels",
        current.window_identity,
        current.settings,
    )
    native = object.__new__(MinecraftNativeRuntime)
    native.latest_inspection = (evidence, current.position)
    native.last_spatial, native.events = current, []
    native.approach = lambda _: None
    native.inspect = lambda _: pytest.fail("Fresh compatible inspection is reusable")
    native._driver = lambda: pytest.fail("Existing block must not emit input")
    result = native.place(cell, "minecraft:stone")
    assert result["status"] == "completed" and result["placed"] == []
