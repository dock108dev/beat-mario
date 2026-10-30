"""Architecture must bind reviewed terrain and preserve explicit inventories."""

from copy import deepcopy
import pytest
from smb3_agent.minecraft_architecture import (
    compile_architecture,
    assembly,
    MATERIALS,
    expanded_rooms,
)
from smb3_agent.minecraft_terrain import digest

PALETTE = {
    name: name
    for name in "air stone stone_bricks dirt grass_block glass oak_planks spruce_planks white_wool glowstone oak_stairs oak_door white_bed chest crafting_table".split()
}


def fixture(kind="building", width=24, depth=16, height=6, turn=0):
    component = {
        "name": "Unseen place",
        "kind": kind,
        "box": [12, 12, width, depth, 0, height],
        "size": [width, depth, height],
        "turn": turn,
        "rooms": ["workshop", "bunkroom", "records room"] if kind == "building" else [],
        "objects": [],
        "native": [],
        "constraints": {},
    }
    design = {"revision": 3, "palette": "warm", "components": [component]}
    terrain = {
        "design_revision": 2,
        "origin": [64, 0],
        "sea_level": -47,
        "reservations": {"Unseen place": {"box": [12, 12, width, depth], "level": 0}},
        "field": {"height": [[0] * 64 for _ in range(64)]},
        "region": {
            "bounds": {
                "min": {"x": 64, "y": -60, "z": 0},
                "max": {"x": 127, "y": 1, "z": 63},
            },
            "protected": [],
        },
    }
    terrain["digest"] = digest(terrain)
    return design, terrain


def test_native_rooms_and_rotated_state_binding():
    design, terrain = fixture(turn=2)
    design["components"][0]["native"] = [
        "doors",
        "beds",
        "chests",
        "crafting table",
        "lamps",
    ]
    result = compile_architecture(design, terrain, PALETTE)
    c = result["components"][0]
    assert len(c["rooms"]) == 3 and len(c["objects"]) == 5
    assert not result["unsupported"] and not result["dependencies"]
    states = [cell["after"] for cell in c["cells"]]
    assert any("white_bed[facing=north" in s and "part=head" in s for s in states)
    assert any("oak_door[facing=north" in s and "half=upper" in s for s in states)
    assert all(64 <= cell["position"]["x"] <= 127 for cell in c["cells"])
    assert result["terrain_digest"] == terrain["digest"]


def test_unknown_objects_and_conflicting_terrain_remain_explicit():
    design, terrain = fixture()
    design["components"][0]["objects"] = ["working radio"]
    terrain["field"]["height"][12][12] = 3
    terrain["digest"] = digest({k: v for k, v in terrain.items() if k != "digest"})
    result = compile_architecture(design, terrain, PALETTE)
    assert "working radio" in result["unsupported"][0]
    assert any("intersects terrain" in issue for issue in result["dependencies"])


def test_changed_footprint_requires_terrain_review():
    design, terrain = fixture()
    design["components"][0]["box"][0] += 1
    result = compile_architecture(design, terrain, PALETTE)
    assert not result["components"]
    assert "footprint differs" in result["dependencies"][0]


def test_material_revision_is_pure_and_preserves_other_selected_places():
    design, terrain = fixture()
    original = deepcopy(design)
    a = compile_architecture(
        design, terrain, PALETTE, selected="Unseen place", material="warm"
    )
    b = compile_architecture(
        design, terrain, PALETTE, selected="Unseen place", material="industrial"
    )
    assert a["components"][0]["digest"] != b["components"][0]["digest"]
    assert a["terrain_digest"] == b["terrain_digest"] and design == original


def test_multipart_blocks_unavailable_fail_before_execution():
    design, terrain = fixture()
    design["components"][0]["native"] = ["beds"]
    with pytest.raises(ValueError, match="Native block unavailable"):
        compile_architecture(
            design, terrain, {k: v for k, v in PALETTE.items() if k != "white_bed"}
        )


def test_unseen_names_use_same_room_and_object_composition():
    design, terrain = fixture(height=10)
    c = design["components"][0]
    c["constraints"]["storeys"] = 2
    c["rooms"] = ["common room", "kitchen", "four upstairs rooms"]
    result = compile_architecture(design, terrain, PALETTE)
    assert len(result["components"][0]["rooms"]) == 6
    assert expanded_rooms(["four upstairs rooms"]) == [
        f"upstairs rooms {i}" for i in range(1, 5)
    ]
    assert assembly("stall", MATERIALS["warm"]) != assembly("awning", MATERIALS["warm"])


def test_terrain_integrity_required():
    design, terrain = fixture()
    terrain["origin"][0] += 1
    with pytest.raises(ValueError, match="integrity"):
        compile_architecture(design, terrain, PALETTE)


def project_fixture(tmp_path):
    import json
    from types import SimpleNamespace
    from smb3_agent.minecraft_build import BuildProject
    from test_minecraft_build import Bridge

    design, terrain = fixture(kind="pavilion", width=8, depth=6, height=4)
    terrain.update(
        stages=[],
        extent=64,
        buffer=32,
        cells=0,
        stages_count=0,
        max_seconds=30,
        max_cells=10000,
        peaks=[],
    )
    terrain["field"]["water"] = [[False] * 64 for _ in range(64)]
    terrain["digest"] = digest({k: v for k, v in terrain.items() if k != "digest"})
    bridge = Bridge()
    original = bridge.call
    bridge.build_console = SimpleNamespace(region=terrain["region"])
    bridge.admissions = []

    def call(op, args=None, **kw):
        if op == "build_palette":
            return PALETTE
        if (
            op == "select_build_region"
            or op == "execute"
            and args.get("action") == "build_focus"
        ):
            bridge.admissions.append(op)
            return {}
        return original(op, args, **kw)

    bridge.call = call
    project = BuildProject(tmp_path, "synthetic", terrain["region"], bridge)
    project.db.execute(
        "INSERT INTO terrain_manifests VALUES (?,?)",
        (terrain["design_revision"], json.dumps(terrain)),
    )
    project.db.commit()
    return project, design, terrain


def test_architecture_reopens_idle_and_reuses_existing_journal(tmp_path):
    from smb3_agent.minecraft_build import BuildProject

    project, design, terrain = project_fixture(tmp_path)
    review = project.review_architecture(design)
    assert not project.bridge.cells
    captured = (project.bridge.session_id, project.bridge.revision)
    assert (
        project.run_architecture(review["review"], captured=captured)["state"]
        == "complete"
    )
    units = project.db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
    bridge = project.bridge
    project.close()
    restored = BuildProject(tmp_path, "synthetic", terrain["region"], bridge)
    try:
        assert restored.state == "idle" and not restored.staged_active
        assert (
            restored.run_architecture(review["review"], captured=captured)["state"]
            == "complete"
        )
        assert restored.db.execute("SELECT COUNT(*) FROM units").fetchone()[0] == units
    finally:
        restored.close()


def test_stale_architecture_cannot_admit_region_or_write(tmp_path):
    project, design, _ = project_fixture(tmp_path)
    try:
        review = project.review_architecture(design)
        outcome = project.run_architecture(
            review["review"], captured=("old-session", 0)
        )
        assert outcome["state"] == "needs_review"
        assert not project.bridge.admissions and not project.bridge.cells
    finally:
        project.close()


def test_material_revision_preserves_changed_player_block(tmp_path):
    project, design, _ = project_fixture(tmp_path)
    try:
        review = project.review_architecture(design)
        captured = (project.bridge.session_id, project.bridge.revision)
        project.run_architecture(review["review"], captured=captured)
        point = next(p for p, s in project.bridge.cells.items() if s == "oak_planks")
        project.bridge.cells[point] = "glass"
        review = project.review_architecture(design, material="industrial")
        assert (
            project.run_architecture(review["review"], captured=captured)["state"]
            == "needs_review"
        )
        assert project.bridge.cells[point] == "glass"
    finally:
        project.close()


def test_interrupted_architecture_intent_recovers_without_second_journal(tmp_path):
    project, design, _ = project_fixture(tmp_path)
    try:
        review = project.review_architecture(design)
        captured = (project.bridge.session_id, project.bridge.revision)
        ordinary = project.run

        def fail(point, uid):
            if point == "write":
                raise RuntimeError("injected interrupted receipt")

        project.run = lambda **kw: ordinary(fault=fail, **kw)
        assert (
            project.run_architecture(review["review"], captured=captured)["state"]
            == "needs_review"
        )
        assert (
            project.db.execute(
                "SELECT COUNT(*) FROM units WHERE status='pending'"
            ).fetchone()[0]
            == 1
        )
        project.run = ordinary
        assert (
            project.run_architecture(review["review"], captured=captured)["state"]
            == "complete"
        )
        assert (
            project.db.execute(
                "SELECT COUNT(*) FROM units WHERE status='pending'"
            ).fetchone()[0]
            == 0
        )
    finally:
        project.close()


def test_terrain_stage_preserves_architecture_cells_and_room_air(tmp_path, monkeypatch):
    import json
    from smb3_agent import minecraft_terrain

    project, design, terrain = project_fixture(tmp_path)
    try:
        review = project.review_architecture(design)
        captured = (project.bridge.session_id, project.bridge.revision)
        assert (
            project.run_architecture(review["review"], captured=captured)["state"]
            == "complete"
        )
        owned = project.architecture_ownership(require_complete=True)
        point = next(p for p, s in owned.items() if s == "oak_planks")
        cells = [
            {"position": dict(zip(("x", "y", "z"), point)), "after": "stone"},
            {"position": {"x": 65, "y": -47, "z": 1}, "after": "stone"},
        ]
        manifest = deepcopy(terrain)
        manifest.update(
            design_revision=4,
            stages=[
                {"phase": "earth", "x": 0, "z": 0, "digest": digest(cells), "cells": 2}
            ],
            stages_count=1,
            palette=PALETTE,
            foliage_cleanup=[],
        )
        manifest["digest"] = digest(
            {k: v for k, v in manifest.items() if k != "digest"}
        )
        project.db.execute(
            "INSERT INTO terrain_manifests VALUES (?,?)", (4, json.dumps(manifest))
        )
        project.db.commit()
        monkeypatch.setattr(
            minecraft_terrain,
            "tile_cells",
            lambda m, x, z, p, fluid=False, leaves=0: [] if fluid or leaves else cells,
        )
        result = project.run_terrain(4, captured=captured)
        assert result["state"] == "complete", result["error"]
        assert project.bridge.cells[point] == "oak_planks"
        assert project.bridge.cells[(65, -47, 1)] == "stone"
    finally:
        project.close()


def test_beds_and_furnaces_cannot_be_removed_by_generic_state_undo():
    from smb3_agent.minecraft_build import validate_cells

    for block in (
        "white_bed[facing=north,occupied=false,part=foot]",
        "furnace[facing=north,lit=false]",
    ):
        with pytest.raises(ValueError, match="content-aware"):
            validate_cells(
                [
                    {
                        "position": {"x": 70, "y": -47, "z": 1},
                        "before": block,
                        "after": "air",
                    }
                ],
                fixture()[1]["region"],
            )


def test_repeated_roof_revision_restores_original_baseline(tmp_path):
    project, design, _ = project_fixture(tmp_path)
    try:
        captured = (project.bridge.session_id, project.bridge.revision)
        for material in ("warm", "industrial"):
            review = project.review_architecture(design, material=material)
            assert (
                project.run_architecture(review["review"], captured=captured)["state"]
                == "complete"
            )
        old_roof = (78, -44, 14)
        assert project.bridge.cells[old_roof] != "air"
        design["components"][0]["box"][5] = 3
        design["components"][0]["size"][2] = 3
        for material in ("coastal", "natural"):
            review = project.review_architecture(design, material=material)
            result = project.run_architecture(review["review"], captured=captured)
            assert result["state"] == "complete", result["error"]
            assert project.bridge.cells[old_roof] == "air"
    finally:
        project.close()


def test_static_wheel_contrasts_with_every_facade_palette():
    for material in MATERIALS.values():
        blocks = assembly("static wheel", material)
        assert blocks and all(value != material["wall"] for value in blocks.values())


def test_path_review_keeps_retained_cooking_corner_position():
    design, terrain = fixture(kind="terrain", width=12, depth=10, height=3)
    design["components"][0]["objects"] = ["cooking corner"]
    terrain["field"]["paths"] = [[12, 12, 0]]
    terrain["digest"] = digest({k: v for k, v in terrain.items() if k != "digest"})
    palette = {**PALETTE, "furnace": "furnace"}
    old = compile_architecture(design, terrain, palette)["components"][0]
    terrain["field"]["paths"] = []
    terrain["digest"] = digest({k: v for k, v in terrain.items() if k != "digest"})
    new = compile_architecture(design, terrain, palette, existing={old["name"]: old})[
        "components"
    ][0]
    assert new["objects"][0]["position"] == old["objects"][0]["position"]
    assert new["objects"][0]["parts"] == old["objects"][0]["parts"]


def test_new_selected_place_shows_terrain_dependency_before_building():
    design, terrain = fixture()
    terrain["reservations"] = {}
    terrain["digest"] = digest({k: v for k, v in terrain.items() if k != "digest"})
    review = compile_architecture(design, terrain, PALETTE, selected="Unseen place")
    assert not review["components"]
    assert review["dependencies"] == [
        "Unseen place: requires a reviewed terrain reservation"
    ]


def test_small_rotated_building_fits_native_inventory_without_fixed_empty_slots():
    design, terrain = fixture(width=10, depth=12, height=6, turn=1)
    component = design["components"][0]
    component["rooms"] = []
    component["native"] = ["doors", "chests", "crafting table", "lamps"]
    result = compile_architecture(design, terrain, PALETTE)
    assert not result["unsupported"]
    objects = result["components"][0]["objects"]
    assert {o["type"] for o in objects} == set(component["native"])
    assert len({tuple(o["position"].values()) for o in objects}) == 4


def test_glass_material_keeps_geometry_and_glazes_roof():
    design, terrain = fixture(width=10, depth=12, height=6, turn=1)
    design["components"][0]["rooms"] = []
    original = deepcopy(design)
    result = compile_architecture(design, terrain, PALETTE, material="glass")
    component = result["components"][0]
    assert not result["unsupported"]
    assert design == original
    cells = component["cells"]
    highest = max(c["position"]["y"] for c in cells)
    assert {c["after"] for c in cells if c["position"]["y"] == highest} == {"glass"}
    assert any(c["after"] == "stone_bricks" for c in cells)


@pytest.mark.parametrize('turn', [0, 1, 2, 3])
def test_small_single_room_cabin_keeps_usable_interior_and_entrance(turn):
    design, terrain = fixture(width=8, depth=8, height=5, turn=turn)
    design['components'][0]['rooms'] = []
    result = compile_architecture(design, terrain, PALETTE)
    assert not result['dependencies'] and not result['unsupported']
    room = result['components'][0]['rooms'][0]
    cells = {tuple(c['position'][k] for k in ('x','y','z')):c['after'] for c in result['components'][0]['cells']}
    floor = room['floor']
    assert cells[tuple(floor[k] for k in ('x','y','z'))] != 'air'
    assert cells[floor['x'],floor['y']+1,floor['z']] == 'air'
    assert cells[tuple(room['entrance'][k] for k in ('x','y','z'))] == 'air'
    assert all(76 <= x < 84 and 12 <= z < 20 for x,y,z in cells)


def test_small_cabin_does_not_drop_requested_extra_rooms():
    design, terrain = fixture(width=8, depth=8, height=5)
    with pytest.raises(ValueError, match='rooms need more width'):
        compile_architecture(design, terrain, PALETTE)
