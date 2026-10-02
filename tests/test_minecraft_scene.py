"""Pixel/geometry/composition regressions; no live gameplay claim."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.minecraft_scene import HudGlyphDetector, VisibleCellLedger, CellEvidence
from smb3_agent.minecraft_wall import CompositeBudget, WallScope, WallCoordinator
from smb3_agent.minecraft_skills import visible_spatial, MinecraftSkills, wall_cells
from smb3_agent.minecraft_camera_skill import MinecraftCameraSkill
from smb3_agent.skill_runtime import FiniteSkillRuntime
from test_feedback_contracts import calibration, observation
from test_player_beta import obs


@pytest.fixture
def glyphs():
    if not (
        Path.home() / "Library/Application Support/minecraft/versions/26.3/26.3.jar"
    ).exists():
        pytest.skip("Installed static font absent")
    return HudGlyphDetector.installed()


def test_pixels_read_five_decimal_height_and_target_without_dimension_as_material(
    glyphs, tmp_path
):
    array = np.zeros((1016, 1708, 3), dtype=np.uint8)
    for y, x, text in [
        (222, 4, "XYZ: 6.182 / -60.00000 / 8.187"),
        (276, 4, "minecraft:overworld FC: 0"),
        (460, 1050, "Targeted Block: 6, -61, 8"),
        (478, 1050, "minecraft:grass_block"),
    ]:
        g = glyphs.render(text)
        array[y : y + 16, x : x + g.shape[1]] = g[:, :, None] * 221
    path = tmp_path / "frame.png"
    Image.fromarray(array).save(path)
    rows = glyphs.spatial_rows(path)
    assert rows == [
        "XYZ: 6.182 / -60.00000 / 8.187",
        "Targeted Block: 6, -61, 8",
        "minecraft:grass_block",
    ]
    state = visible_spatial(
        rows,
        captured_at=10,
        window_identity=(),
        settings="s",
        orientation=SimpleNamespace(heading=0, pitch=0),
    )
    assert state.position == (6.182, -60, 8.187)
    assert (
        state.block == "minecraft:grass_block"
        and not state.creative
        and state.material is None
    )
    array[222:238, 4:30] = 0
    Image.fromarray(array).save(path)
    with pytest.raises(FeedbackError):
        visible_spatial(
            glyphs.spatial_rows(path),
            captured_at=10,
            window_identity=(),
            settings="s",
            orientation=SimpleNamespace(heading=0, pitch=0),
        )


def test_ray_inspection_air_only_before_a_visible_reachable_full_cube():
    state = obs(target=(0, 1, 1))
    ledger = VisibleCellLedger(state.window_identity, state.settings)
    evidence = ledger.inspect(
        state, [(0, 1, -1), (0, 1, 0), (0, 1, 1), (0, 1, 2), (1, 1, 0)], 10
    )
    assert {e.cell: e.material for e in evidence} == {
        (0, 1, -1): None,
        (0, 1, 0): None,
        (0, 1, 1): "minecraft:stone",
    }
    assert not ledger.inspect(replace(state, target=None), [(0, 1, 2)], 10)
    assert not ledger.inspect(
        replace(state, block="minecraft:oak_fence"), [(0, 1, 1)], 10
    )
    with pytest.raises(FeedbackError):
        ledger.inspect(state, [(0, 1, 1)], 10)
    with pytest.raises(FeedbackError):
        ledger.inspect(replace(state, window_identity=(99,)), [(0, 1, 1)], 10)
    assert not ledger.flat_path(state.position, (0.5, 0, -1.75), now=10)


def coordinator_fixture(
    *, wrong_door=False, unknown_after=False, canceled=lambda: False, limit=512
):
    scope = WallScope(
        (0, 0, 0), "x", "minecraft:stone", ((10, 0, 0),), (0.5, 0, -2), "visible-frame"
    )
    material = {c: scope.material for c in wall_cells(scope.anchor)}
    missing = (2, 0, 0)
    material[missing] = None
    material[scope.protected[0]] = "minecraft:bricks"
    if wrong_door:
        material[scope.doorway[0]] = "minecraft:dirt"
    input_calls = []
    at = [10]
    budget = CompositeBudget(canceled, clock=lambda: at[0], max_steps=limit)

    def inspect(cell, b):
        b.consume()
        at[0] += 0.01
        if unknown_after and cell == missing and input_calls:
            return None
        return CellEvidence(cell, material.get(cell), at[0], "pixels", (), "s")

    def place(cell, m, b):
        b.consume(60)
        input_calls.append(cell)
        material[cell] = m

    def approach(cell, b):
        b.consume(100)

    coordinator = WallCoordinator(
        inspect=inspect,
        place=place,
        approach=approach,
        observe_position=lambda: scope.stop_point,
        neutralize=lambda: {"confirmed": True},
    )
    return coordinator, scope, budget, input_calls


def test_wall_existing_cells_advance_one_new_addition_doorway_and_protection_verified():
    c, s, b, calls = coordinator_fixture()
    result = c.run(s, b)
    assert (
        result["status"] == "completed"
        and len(result["existing"]) == 18
        and len(result["placed"]) == 1
    )
    assert len(calls) == 1 and result["doorway_empty"] == list(s.doorway)
    assert (
        result["protected_verified"] == list(s.protected)
        and result["stop_point_observed"]
    )
    assert result["input_ms"] == 2060 and result["steps"] > 19


def test_wall_unknown_placement_is_partial_no_retry_and_wrong_door_stops_before_input():
    c, s, b, calls = coordinator_fixture(unknown_after=True)
    r = c.run(s, b)
    assert (
        r["status"] == "partial" and calls == [(2, 0, 0)] and (2, 0, 0) in r["unknown"]
    )
    assert not r["placed"] and "no blind retry" in r["reason"]
    c, s, b, calls = coordinator_fixture(wrong_door=True)
    r = c.run(s, b)
    assert r["status"] == "partial" and not calls and "Doorway" in r["reason"]


def test_composite_exhaustion_and_cancellation_include_inspection_and_child_work():
    c, s, b, calls = coordinator_fixture(limit=4)
    r = c.run(s, b)
    assert r["status"] == "partial" and b.steps == 4 and not calls
    c, s, b, calls = coordinator_fixture(canceled=lambda: True)
    r = c.run(s, b)
    assert r["status"] == "partial" and b.steps == 0 and not calls
    with pytest.raises(FeedbackError):
        MinecraftSkills((), "s").validate("wall", {})


def test_camera_provider_runs_shared_executor_with_actual_receipt_then_independent_feedback():
    clock = [100.02]
    views = [observation("pre", 100, 0), observation("post", 100.2, 2)]
    provider = MinecraftCameraSkill(calibration(), 7, clock=lambda: clock[0])

    def observe():
        view = views.pop(0)
        clock[0] = max(clock[0], view.grounded_at)
        return view

    def emit(action):
        clock[0] = 100.16
        assert action.dx == 2 and action.dy == 0
        return {"delivered_at": action.issued_at + 0.001}

    runtime = FiniteSkillRuntime(
        observe=observe,
        emit=emit,
        neutralize=lambda: {"confirmed": True},
        canceled=lambda: False,
        clock=lambda: clock[0],
    )
    result = runtime.run("camera", provider, {"heading": 2, "pitch": 0})
    assert result["status"] == "completed" and result["input_ms"] == 120
    assert result["steps"][0]["verified"] and result["completed"] == [
        {"heading": 2, "pitch": 0}
    ]


def test_camera_delivery_without_matching_response_cannot_complete():
    clock = [100.02]
    views = [observation("pre", 100, 0), observation("post", 100.2, 40)]
    provider = MinecraftCameraSkill(calibration(), 7, clock=lambda: clock[0])

    def observe():
        view = views.pop(0)
        clock[0] = max(clock[0], view.grounded_at)
        return view

    def emit(action):
        clock[0] = 100.16
        return {"delivered_at": action.issued_at + 0.001}

    r = FiniteSkillRuntime(
        observe=observe,
        emit=emit,
        neutralize=lambda: {"confirmed": True},
        canceled=lambda: False,
        clock=lambda: clock[0],
    ).run("aim", provider, {"heading": 2, "pitch": 0})
    assert (
        r["status"] == "partial"
        and not r["completed"]
        and "Contradictory" in r["reason"]
    )


def test_spatial_wrapper_rejects_stale_or_replaced_pixels_and_never_accepts_asserted_mode(
    tmp_path,
):
    import hashlib
    from smb3_agent.minecraft_scene import observed_spatial

    path = tmp_path / "frame.png"
    path.write_bytes(b"fixture pixel binding")
    view = observation("spatial", 10, 0)
    view = replace(
        view,
        provenance=(str(path),),
        frame=replace(
            view.frame,
            evidence_reference=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        ),
    )
    detector = SimpleNamespace(spatial_rows=lambda _: ["XYZ: 0.500 / 0.00000 / -2.000"])
    state = observed_spatial(path, view=view, detector=detector, now=10.02)
    assert (
        state.position == (0.5, 0, -2) and not state.creative and state.material is None
    )
    with pytest.raises(FeedbackError):
        observed_spatial(path, view=view, detector=detector, now=11)
    with pytest.raises(TypeError):
        observed_spatial(path, view=view, detector=detector, now=10.02, creative=True)
    path.write_bytes(b"replaced pixels")
    with pytest.raises(FeedbackError, match="pixels"):
        observed_spatial(path, view=view, detector=detector, now=10.02)
