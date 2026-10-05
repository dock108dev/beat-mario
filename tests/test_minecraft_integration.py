"""Affected lifecycle/native-port checks; simulated ports are not live evidence."""

from dataclasses import asdict
import threading

import pytest

from smb3_agent.player_store import PlayerStore
from smb3_agent.player_setup import PlayerSetupService
from smb3_agent.minecraft_session import MinecraftPlayerSession
from smb3_agent.minecraft_native import MinecraftNativeRuntime
from smb3_agent.minecraft_wall import CompositeBudget
from test_feedback_contracts import calibration
from test_player_beta import obs


def test_workspace_roundtrip_is_configuration_without_authority(tmp_path):
    store = PlayerStore(tmp_path)
    config = {
        "anchor": [3, -60, 10],
        "axis": "x",
        "material": "minecraft:stone",
        "protected": [[6, -60, 8]],
        "stop_point": [6.5, -59, 9.5],
    }
    p = store.save(game="minecraft", name="Flat practice", workspace=config)
    reopened = PlayerStore(tmp_path).load(p["id"])
    assert reopened["workspace"] == config and reopened["schema"] == "player-profile/v2"
    assert store.duplicate(p["id"])["workspace"] == config
    import json

    with pytest.raises(ValueError):
        store.import_profile(
            json.dumps({**p, "workspace": {**config, "creative": True}})
        )
    service = PlayerSetupService(store=store)
    state = service.dispatch("open", {"id": p["id"]})
    assert (
        state["selected"]["workspace"] == config
        and not state["plan"]
        and not state["reviewed"]
    )


class Camera:
    def __init__(self):
        self.selected = {"id": "session", "calibration": asdict(calibration())}
        self.client = None
        self.state = "connected"
        self.reason = "Ready"
        self.worker = None

    def snapshot(self):
        return {"busy": False, "sessions": [], "windows": []}

    def revoke(self, reason):
        return {"confirmed": True}

    def _require_calibration(self, cal):
        pass


def test_question_correction_stop_and_reopen_revoke_review_without_input(
    tmp_path, monkeypatch
):
    from smb3_agent.minecraft_session import CHECKED_FEATURES

    monkeypatch.setitem(CHECKED_FEATURES, "camera", True)
    store = PlayerStore(tmp_path)
    camera = Camera()
    native = MinecraftPlayerSession(camera, store)
    service = PlayerSetupService(store=store, minecraft=native)
    try:
        p = service.dispatch("save", {"game": "minecraft", "name": "Practice"})[
            "selected"
        ]
        camera.selected = {"id": "session", "calibration": asdict(calibration())}
        plan = service.dispatch("message", {"text": "Look slightly right, then stop"})[
            "plan"
        ]
        assert plan["executable"]
        service.dispatch("review", {"plan_id": plan["id"]})
        assert native.review is not None
        service.dispatch("message", {"text": "How does Stop work?"})
        assert native.review is None and service.plan is None
        with pytest.raises(ValueError):
            service.dispatch("start", {"client_id": "page"})
        service.dispatch("open", {"id": p["id"]})
        assert (
            camera.selected is None and native.scope is None and native.review is None
        )
    finally:
        native.close()


def test_priority_revoke_cancels_published_owner_before_camera_and_persistence(
    tmp_path,
):
    events = []
    camera = Camera()
    camera.revoke = lambda reason: events.append("camera") or {"confirmed": True}
    native = MinecraftPlayerSession(camera, PlayerStore(tmp_path))

    class Owner:
        def cancel(self):
            assert native.cancel.is_set()
            events.append("native")
            return {"confirmed": True}

    try:
        native.owner = Owner()
        native.review = {"old": "plan"}
        assert native.revoke("Take control")
        assert events == ["native", "camera"] and native.review is None
    finally:
        native.owner = None
        native.close()


def test_unknown_addition_cell_refuses_before_driver_or_click():
    native = object.__new__(MinecraftNativeRuntime)
    native.approach = lambda cell: None
    native.inspect = lambda cell: None
    native._driver = lambda: pytest.fail("No driver may be created for unknown cell")
    with pytest.raises(ValueError, match="independently clear"):
        native.place((0, 1, 0), "minecraft:stone")


def test_missing_target_cannot_mean_air_before_positive_hud_check():
    native = object.__new__(MinecraftNativeRuntime)
    native.aim_point = lambda point: None
    native.target_hud_verified = False
    native.spatial = lambda: obs(target=None, block=None, face=None)
    assert native.inspect((0, 1, 0)) is None


def test_partial_block_or_occluder_cannot_establish_empty_cell():
    native = object.__new__(MinecraftNativeRuntime)
    native.aim_point = lambda point: None
    native.target_hud_verified = True
    native.spatial = lambda: obs(
        target=(0, 1, 1), block="minecraft:oak_slab", face=None
    )
    assert native.inspect((0, 1, 0)) is None


def test_unreachable_stop_point_refuses_without_travel():
    native = object.__new__(MinecraftNativeRuntime)
    native.spatial = lambda: obs()
    native.move = lambda p: pytest.fail("No long travel allowed")
    with pytest.raises(ValueError, match="unsupported travel"):
        native.approach((0.5, 0.0, 10.0))


def test_total_budget_cancellation_precedes_any_more_ports():
    cancel = threading.Event()
    budget = CompositeBudget(cancel.is_set)
    budget.consume(60)
    cancel.set()
    with pytest.raises(ValueError):
        budget.consume(120)
    assert budget.input_ms == 60


def test_capture_scale_conversion_preserves_exact_pixels_and_original(tmp_path):
    import hashlib
    import numpy as np
    from PIL import Image
    from smb3_agent.minecraft_capture import decode_pixels

    rgb = np.zeros((508, 854, 3), dtype=np.uint8)
    rgb[100:108, 10:16] = (221, 221, 221)
    raw = tmp_path / "native.png"
    decoded = tmp_path / "decoded.png"
    Image.fromarray(rgb).save(raw)
    before = hashlib.sha256(raw.read_bytes()).hexdigest()
    size, path, method = decode_pixels(raw, decoded)
    assert size == (854, 508) and "replication" in method
    actual = np.asarray(Image.open(path))
    assert np.array_equal(actual[::2, ::2], rgb)
    assert np.array_equal(actual[1::2, 1::2], rgb)
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == before
    Image.new("RGB", (900, 500)).save(raw)
    with pytest.raises(ValueError, match="Unsupported native"):
        decode_pixels(raw, decoded)


def test_visible_transition_observes_delayed_frame_without_repeating_toggle():
    from smb3_agent.minecraft_inventory import wait_visible
    from smb3_agent.feedback_contracts import FeedbackError

    rows = iter(["old world", "inventory"])
    observed = []

    def capture():
        value = next(rows)
        observed.append(value)
        return value

    def accept(value):
        if value != "inventory":
            raise FeedbackError("Not visibly open yet")

    assert wait_visible(capture, accept, threading.Event()) == "inventory"
    assert observed == ["old world", "inventory"]


def test_visible_transition_does_not_retry_lost_window_and_cancels_promptly():
    from smb3_agent.minecraft_inventory import wait_visible
    from smb3_agent.feedback_contracts import FeedbackError

    calls = []

    def lost():
        calls.append(1)
        raise FeedbackError("Exact window lost")

    with pytest.raises(FeedbackError, match="Exact window lost"):
        wait_visible(lost, lambda f: None, threading.Event())
    assert len(calls) == 1
    canceled = threading.Event()
    canceled.set()

    def absent(f):
        raise FeedbackError("Transition absent")

    with pytest.raises(FeedbackError, match="canceled"):
        wait_visible(lambda: "old", absent, canceled)


def test_camera_refresh_uses_new_stable_frame_and_refuses_unexplained_change():
    from test_feedback_contracts import policy, observation, ENV
    from smb3_agent.feedback_contracts import FeedbackError
    from smb3_agent.feedback_policy import CorrectionState

    p = policy()
    fresh = observation("fresh", at=100.8)
    p.refresh(fresh, now=100.81, epoch=7, settings_sha256=ENV.sha256)
    action = p.propose(2, 0, 20, now=100.82, epoch=7, settings_sha256=ENV.sha256)
    assert action.frame == fresh.frame
    with pytest.raises(FeedbackError, match="pending or canceled"):
        p.refresh(
            observation("later", at=100.9),
            now=100.91,
            epoch=7,
            settings_sha256=ENV.sha256,
        )
    p = policy()
    with pytest.raises(FeedbackError, match="Unexplained"):
        p.refresh(
            observation("jump", at=100.1, heading=3),
            now=100.11,
            epoch=7,
            settings_sha256=ENV.sha256,
        )
    assert p.state is CorrectionState.CONTRADICTORY


def test_first_camera_pulse_refuses_changed_composition_baseline(tmp_path, monkeypatch):
    from test_feedback_contracts import observation
    from smb3_agent.feedback_contracts import FeedbackError
    import smb3_agent.minecraft_native as module

    pulses = []

    class Guard:
        def __init__(self, *args):
            pass

        def pulse(self, action):
            pulses.append(action)

    monkeypatch.setattr(module, "CameraMotionGuard", Guard)
    native = MinecraftNativeRuntime.__new__(MinecraftNativeRuntime)
    native.cal, native.epoch, native.root = calibration(), 1, tmp_path
    native.canceled, native.events = threading.Event(), []
    native.budget = CompositeBudget(lambda: False)
    native.detector = None
    from types import SimpleNamespace

    monkeypatch.setattr(
        module,
        "observed_spatial",
        lambda *args, **kwargs: SimpleNamespace(position=(0, 0, 0)),
    )
    frames = iter([observation(), observation("jump", at=100.1, heading=3)])
    native.view = lambda: next(frames)
    native._publish = lambda owner: None
    native.neutralize = lambda: {"confirmed": True}
    with pytest.raises(FeedbackError, match="View changed before"):
        native.aim(5, 0)
    assert not pulses


def test_air_cell_can_end_at_observed_full_cube_boundary_without_overlap():
    from smb3_agent.minecraft_scene import ray_interval
    import math

    position = (5.5, -60, 8.5)
    air = ray_interval(position, 0, 45, (5, -60, 10))
    floor = ray_interval(position, 0, 45, (5, -61, 10))
    assert air and floor and math.isclose(air[1], floor[0])
    assert air[1] <= floor[0] + 1e-7


def test_material_correction_is_saved_intent_and_never_a_live_material_fact(tmp_path):
    store = PlayerStore(tmp_path)
    service = PlayerSetupService(store=store)
    selected = service.dispatch("save", {"game": "minecraft", "name": "Practice"})[
        "selected"
    ]
    service.dispatch("message", {"text": "Finish a 7 by 3 wall"})
    service.dispatch("review", {"plan_id": service.plan["id"]})
    state = service.dispatch("message", {"text": "Actually use bricks instead"})
    assert not state["plan"] and not state["reviewed"]
    reopened = store.load(selected["id"])
    assert "Preferred building material: minecraft:bricks" in reopened["notes"]
    assert reopened.get("workspace") is None and reopened["executable"] is None
    service.dispatch("message", {"text": "Finish a 9 by 3 wall"})
    assert service.plan is None and "7 wide" in service.reason


def test_native_result_serializes_shared_commands_before_history_handoff(tmp_path):
    import json
    from smb3_agent.host_contracts import InputCommand, InputKind

    native = MinecraftNativeRuntime.__new__(MinecraftNativeRuntime)
    native.root, native.canceled, native.events = tmp_path, threading.Event(), []
    native.prepare = lambda **kwargs: None
    command = InputCommand(InputKind.KEYBOARD, "w", "press", 50)
    native.move = lambda parameters: {
        "status": "completed",
        "completed": ["nearby"],
        "steps": [{"command": command}],
    }
    native.neutralize = lambda: {"confirmed": True}
    result = native.run("move", {"distance": 0.1, "direction": "forward"})
    assert result["steps"][0]["command"]["control"] == "w"
    assert json.loads((tmp_path / "result.json").read_text()) == result
    store = PlayerStore(tmp_path / "player")
    profile = store.save(game="minecraft", name="Practice")
    store.record(profile["id"], result)
    assert store.history(profile["id"])[0]["status"] == "completed"


def test_wall_refuses_receipt_for_different_cell_before_any_addition():
    from smb3_agent.minecraft_scene import CellEvidence
    from smb3_agent.minecraft_wall import WallScope, WallCoordinator

    scope = WallScope(
        (0, 0, 0), "x", "minecraft:stone", (), (3.5, 0, 2.5), "fixture-scope"
    )
    placed = []
    coordinator = WallCoordinator(
        inspect=lambda cell, budget: CellEvidence(
            (99, 0, 99), None, 1, "fixture", (1, "fixture"), "fixture"
        ),
        place=lambda *args: placed.append(args),
        approach=lambda *args: None,
        observe_position=lambda: scope.stop_point,
        neutralize=lambda: {"confirmed": True},
    )
    result = coordinator.run(scope, CompositeBudget(lambda: False))
    assert result["status"] == "partial" and "different cell" in result["reason"]
    assert not placed


def test_swept_body_includes_diagonal_corners_and_overshoot_boundary():
    from smb3_agent.minecraft_native import movement_cells

    floor, body = movement_cells((0.5, 0, 0.5), (1.02, 0, 1.02))
    assert floor == {(x, -1, z) for x in (0, 1) for z in (0, 1)}
    assert body == {(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)}


def test_lintel_side_face_uses_one_addition_when_underneath_is_empty(
    tmp_path, monkeypatch
):
    import time
    from dataclasses import replace
    from types import SimpleNamespace
    import smb3_agent.minecraft_native as module
    from smb3_agent.minecraft_scene import CellEvidence

    cell = (3, 2, 0)
    native = MinecraftNativeRuntime.__new__(MinecraftNativeRuntime)
    native.approach = lambda cell: None
    native.latest_inspection = None
    native.inspect = lambda cell: CellEvidence(
        cell, None, time.monotonic(), "fixture", (), "settings"
    )
    native.events, native.canceled = [], threading.Event()
    native.scene_settings = "settings"
    native.budget = CompositeBudget(lambda: False)
    native.neutralize = lambda: {"confirmed": True}
    frames = iter(
        [
            replace(
                obs(),
                target=(3, 0, 0),
                block="minecraft:stone",
                face=(0, 1, 0),
                settings="settings",
                window_identity=(),
            ),
            replace(
                obs(),
                target=(2, 2, 0),
                block="minecraft:stone",
                face=(1, 0, 0),
                settings="settings",
                window_identity=(),
            ),
            replace(
                obs(),
                target=(2, 2, 0),
                block="minecraft:stone",
                face=(1, 0, 0),
                settings="settings",
                window_identity=(),
            ),
            replace(
                obs(),
                target=cell,
                block="minecraft:stone",
                face=(0, 0, 1),
                settings="settings",
                window_identity=(),
            ),
        ]
    )
    native.spatial = lambda: replace(next(frames), captured_at=time.monotonic())
    native.aim_point = lambda point: None
    emitted = []
    native._driver = lambda: SimpleNamespace(send=emitted.append)
    monkeypatch.setattr(module, "time", time)
    # Placement is simulated here; keep the pointer read off native OS APIs.
    import sys

    monkeypatch.setitem(
        sys.modules,
        "Quartz",
        SimpleNamespace(
            CGEventCreate=lambda source: object(),
            CGEventGetLocation=lambda event: SimpleNamespace(x=427, y=254),
        ),
    )
    result = native.place(cell, "minecraft:stone")
    assert result["status"] == "completed" and len(emitted) == 1
    assert emitted[0].control == "right_button" and emitted[0].duration_ms == 60


def test_key_up_recovery_never_presses_or_releases_into_changed_window():
    from dataclasses import replace
    from types import SimpleNamespace
    from test_feedback_contracts import WINDOW, BINDING
    from smb3_agent.minecraft_recovery import release_movement_keys, MOVEMENT_KEYS

    events = []
    q = SimpleNamespace(
        CGPreflightPostEventAccess=lambda: True,
        CGEventCreateKeyboardEvent=lambda source, code, down: (code, down),
        CGEventPost=lambda tap, event: events.append(event),
        kCGHIDEventTap=0,
    )
    h = SimpleNamespace(detect_window=lambda: replace(WINDOW, process_id=999))
    with pytest.raises(ValueError):
        release_movement_keys(h, BINDING, quartz=q)
    assert not events
    h.detect_window = lambda: WINDOW
    release_movement_keys(h, BINDING, quartz=q)
    assert events == [(code, False) for code in MOVEMENT_KEYS]


def test_local_diagnostic_save_failure_keeps_observed_outcome_and_release(
    tmp_path, monkeypatch
):
    from pathlib import Path

    native = MinecraftNativeRuntime.__new__(MinecraftNativeRuntime)
    native.root, native.canceled, native.events = tmp_path, threading.Event(), []
    native.prepare = lambda **kwargs: None
    calls = []
    native.move = lambda p: (
        calls.append(p) or {"status": "completed", "completed": [0.1]}
    )
    native.neutralize = lambda: {"confirmed": True}
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    result = native.run("move", {"distance": 0.1, "direction": "forward"})
    assert result["status"] == "completed" and result["release"]["confirmed"]
    assert result["diagnostics_saved"] is False and len(calls) == 1


def test_pointed_protection_is_reachable_from_ordinary_setup(tmp_path):
    from types import SimpleNamespace

    events = []
    session = SimpleNamespace(
        snapshot=lambda: {"features": {"camera": True}},
        reason="fixture",
        revoke=lambda *args, **kwargs: events.append("release") or True,
        dispatch=lambda action, payload: events.append(action),
    )
    service = PlayerSetupService(store=PlayerStore(tmp_path), minecraft=session)
    service.selected = service.store.save(game="minecraft", name="Practice")
    state = service.dispatch("protect", {"disposable_confirmation": True, "axis": "x"})
    assert events == ["release", "protect"] and not state["reviewed"]


def test_floor_viewpoints_cover_every_swept_cell_without_opposite_corner_turns():
    from smb3_agent.minecraft_native import floor_inspection_points, movement_cells
    from smb3_agent.minecraft_scene import ray_interval
    import math

    start = (5.5, -61, 8.5)
    floor, body = movement_cells(start, (5.4, -61, 8.5))
    points = floor_inspection_points(start, 5.2, floor)
    assert {cell for cell, point in points} == floor == {(5, -62, 8)}
    cell, point = points[0]
    assert point[0] == start[0] and point[2] == start[2]
    # A downward first-hit ground ray crosses both required body cells.
    ground = ray_interval(start, 5.2, 90, cell)
    assert ground
    for air in body:
        segment = ray_interval(start, 5.2, 90, air)
        assert segment and segment[1] <= ground[0] + 1e-7
    # Adjacent floors remain included, and every sample stays off face edges.
    wider, _ = movement_cells((.7, 0, .7), (1.12, 0, 1.12))
    ordered = floor_inspection_points((.7, 0, .7), -45, wider)
    assert len(ordered) == len(wider) == 4
    assert ordered[0][0] == (0, -1, 0)
    for cell, point in ordered:
        assert .19 < point[0] - cell[0] < .81
        assert .19 < point[2] - cell[2] < .81
        assert math.isclose(point[1], cell[1] + .999)
