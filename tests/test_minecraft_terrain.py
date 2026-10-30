"""Terrain geometry and authority tests use authored briefs and synthetic worlds."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from smb3_agent.minecraft_build import BuildProject, BuildConsole
from smb3_agent.minecraft_design import WorldDesign
from smb3_agent.minecraft_terrain import compile_terrain, tile_cells, FLOOR, SEA
from test_minecraft_build import Bridge, REGION
from test_minecraft_requirements import plan

BRIEFS = json.loads(
    (Path(__file__).parents[1] / "data/minecraft/design-briefs.json").read_text()
)
PALETTE = {
    k: k
    for k in (
        "air",
        "stone",
        "grass_block",
        "sand",
        "water",
        "glass",
        "oak_planks",
        "stone_bricks",
        "oak_log",
        "oak_leaves",
    )
}


@pytest.fixture
def project(tmp_path):
    p = BuildProject(tmp_path, "synthetic", REGION, Bridge())
    yield p
    p.close()


@pytest.mark.parametrize("scenario", ("island", "town"))
def test_requested_terrain_dimensions_heights_routes_and_cave(project, scenario):
    design = plan(WorldDesign(project), BRIEFS[scenario]["brief"])
    m = compile_terrain(design, [128, 0])
    assert m["extent"] == BRIEFS[scenario]["extent"] and m["buffer"] == 32
    assert max(p["height"] for p in m["peaks"]) == (32 if scenario == "island" else 28)
    for peak in m["peaks"]:
        x, z = peak["position"]
        assert m["field"]["height"][z][x] >= peak["height"]
    assert m["routes"] and all(r["width"] >= 2 for r in m["routes"])
    widths = {frozenset((r["from"], r["to"])): r["width"] for r in m["routes"]}
    assert (
        widths[
            frozenset(
                ("Dock", "Beach Camp") if scenario == "island" else ("Market", "Inn")
            )
        ]
        == 3
    )
    if scenario == "island":
        assert len(m["woodland_groups"]) == 3
        assert len(m["field"]["trees"]) == 9
    else:
        deck = {(x, z): y for x, z, y in m["field"]["paths"]}
        for c in design["components"]:
            if c["kind"] == "bridge":
                x0, z0, w, d, level, _ = c["box"]
                assert all(
                    deck[x, z] == max(1, level)
                    for z in range(z0, z0 + d)
                    for x in range(x0, x0 + w)
                )

    for route in m["routes"]:
        path_heights = {(x, z): y for x, z, y in m["field"]["paths"]}
        assert all(
            abs(path_heights[tuple(a)] - path_heights[tuple(b)]) <= 1
            for a, b in zip(route["points"], route["points"][1:])
        )
        assert all(
            abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
            for a, b in zip(route["points"], route["points"][1:])
        )
    if scenario == "island":
        cave = m["field"]["caves"][0]
        assert (
            cave["floor"] == 4
            and cave["passage"] == 24
            and cave["chamber"] == [10, 8]
            and cave["headroom"] == 2
        )
        assert all(
            m["field"]["water"][z][x]
            for x, z in ((1, 1), (15, 128), (240, 128), (128, 15), (128, 240))
        )
    assert m["source_digest"] and m["design_revision"] == design["revision"]
    cells = tile_cells(m, 0, 0, PALETTE)
    assert len(cells) < 100000
    assert all(FLOOR <= c["position"]["y"] <= SEA + 48 for c in cells)
    assert not any(c["after"] == "water" for c in cells)


def test_unresolved_requirement_cannot_expand_authority(project):
    with pytest.raises(ValueError, match="Resolve"):
        compile_terrain({"planning": {"state": "pending"}}, [128, 0])
    assert project.region == REGION and project.terrain_manifest() is None


def test_console_focus_is_bounded_and_not_an_arbitrary_command(tmp_path):
    (tmp_path / "build-permission.json").write_text(
        json.dumps({"world_id": "w", "region": REGION})
    )
    commands = []
    console = BuildConsole(
        SimpleNamespace(
            home=tmp_path, survival=False, world_id="w", command=commands.append
        ),
        REGION,
    )
    with pytest.raises(ValueError, match="focus"):
        console(
            {"mode": "focus", "nonce": "a" * 32, "position": dict(x=999, y=71, z=5)}
        )
    assert not commands
    console({"mode": "focus", "nonce": "a" * 32, "position": dict(x=32, y=71, z=32)})
    assert commands[0] == "tp CompanionBot 32 71 32"


def test_stale_terrain_start_refused_before_region_change(project):
    project.db.execute(
        "INSERT INTO terrain_manifests VALUES (1,?)",
        (json.dumps({"design_revision": 1, "stages": []}),),
    )
    project.db.commit()
    with pytest.raises(ValueError, match="Review"):
        project.run_terrain(2, captured=("stale", 0))
    assert not project.terrain_active and project.region == REGION


def test_stage_receipt_reuses_existing_transaction_on_resume(project, monkeypatch):
    # Exercise the real journal with a deliberately small synthetic terrain compiler.
    from smb3_agent import minecraft_terrain as terrain

    original_call = project.bridge.call
    project.bridge.build_console = SimpleNamespace(region=REGION)

    def call(op, args=None, **kw):
        if op == "build_palette":
            return PALETTE
        if op == "select_build_region":
            return {"observed": "build_region_selected"}
        if op == "execute" and args.get("action") == "build_focus":
            return {"observed": "terrain_chunks_ready"}
        return original_call(op, args, **kw)

    project.bridge.call = call
    base = {
        "design_revision": 1,
        "extent": 192,
        "origin": [0, 0],
        "buffer": 32,
        "region": REGION,
        "peaks": [],
        "reservations": {},
        "field": {
            "height": [[0] * 192 for _ in range(192)],
            "water": [[False] * 192 for _ in range(192)],
        },
        "max_seconds": 30,
        "max_cells": 1000,
    }
    monkeypatch.setattr(terrain, "compile_terrain", lambda design, origin: dict(base))
    monkeypatch.setattr(
        terrain,
        "tile_cells",
        lambda m, x, z, p, fluid=False, leaves=0: (
            []
            if fluid or leaves
            else [{"position": dict(x=x + 1, y=1, z=z + 1), "after": "stone"}]
        ),
    )
    # One tile keeps this test about authority and receipts, not full-scale generation.
    monkeypatch.setattr(terrain, "TILE", 192)
    project.review_terrain({"revision": 1})
    assert not project.bridge.cells and project.region == REGION
    storage_check = project.check_storage
    completing = []

    def observed_storage_check(*args):
        if project.state == "complete":
            completing.append(project.terrain_active)
        return storage_check(*args)

    project.check_storage = observed_storage_check
    saved_region = project.region
    result = project.run_terrain(1, captured=(project.bridge.session_id, 0))
    assert result["state"] == "complete", result
    count = project.db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
    assert (
        project.run_terrain(1, captured=(project.bridge.session_id, 0))["state"]
        == "complete"
    )
    assert project.db.execute("SELECT COUNT(*) FROM units").fetchone()[0] == count
    assert completing and all(completing)
    project.bridge.cells[(1, 1, 1)] = "glass"
    assert (
        project.run_terrain(1, captured=(project.bridge.session_id, 0))["state"]
        == "needs_review"
    )
    assert project.bridge.cells[(1, 1, 1)] == "glass" and project.region == saved_region


def test_native_foliage_layers_and_cleanup_preserve_unaffected_canopy():
    from smb3_agent.minecraft_terrain import foliage_cells, foliage_cleanup

    palette = {
        "oak_leaves": "oak_leaves[distance=7,persistent=false,waterlogged=false]"
    }
    old = {
        "origin": [64, 0],
        "field": {
            "trees": {
                "20,20": {"ground": 0, "height": 4},
                "40,40": {"ground": 0, "height": 4},
            }
        },
    }
    leaves = foliage_cells(old, palette)
    assert leaves and all("persistent=true" in c["after"] for c in leaves)
    assert [c["distance"] for c in leaves] == sorted(c["distance"] for c in leaves)
    new = {"field": {"trees": {"40,40": old["field"]["trees"]["40,40"]}}}
    cleanup = foliage_cleanup(old, new, palette)
    assert cleanup and all(
        c["after"] == "air" and c["position"]["x"] < 90 for c in cleanup
    )
    assert not foliage_cleanup(old, old, palette)


def test_rereview_cannot_reinterpret_existing_revision(project, monkeypatch):
    from smb3_agent import minecraft_terrain as terrain

    design = plan(WorldDesign(project), BRIEFS["town"]["brief"])
    original = project.bridge.call
    project.bridge.call = lambda op, *a, **kw: (
        PALETTE if op == "build_palette" else original(op, *a, **kw)
    )
    project.review_terrain(design)
    saved = project.terrain_manifest()
    monkeypatch.setattr(
        terrain,
        "compile_terrain",
        lambda *a: pytest.fail("Recompiled durable manifest"),
    )
    project.review_terrain(design)
    assert project.terrain_manifest() == saved
    changed = {**design, "requirements": []}
    with pytest.raises(ValueError, match="without a new revision"):
        project.review_terrain(changed)


@pytest.mark.parametrize("scenario", ("island", "town"))
def test_composed_routes_keep_solid_floors_and_two_clear_blocks(project, scenario):
    design = plan(WorldDesign(project), BRIEFS[scenario]["brief"])
    m = compile_terrain(design, [128, 0])
    heights = {(x, z): y for x, z, y in m["field"]["paths"]}
    points = {tuple(p) for r in m["routes"] for p in r["points"]}
    uphill = {
        tuple(a)
        for r in m["routes"]
        for a, b in zip(r["points"], r["points"][1:])
        if heights[tuple(b)] > heights[tuple(a)]
    }
    for tz in range(0, m["extent"], 64):
        for tx in range(0, m["extent"], 64):
            actual = {
                tuple(c["position"][k] for k in ("x", "y", "z")): c["after"]
                for c in tile_cells(m, tx, tz, PALETTE)
            }
            for x, z in points:
                if tx <= x < tx + 64 and tz <= z < tz + 64:
                    y = SEA + heights[x, z]
                    if (x, z) in uphill:
                        assert actual.get((128 + x, y + 3, z), "air") == "air", (
                            scenario,
                            "jump clearance",
                            x,
                            y,
                            z,
                        )
                    assert actual.get((128 + x, y, z)) in (
                        "stone_bricks",
                        "oak_planks",
                    ), (scenario, x, y, z)
                    assert all(
                        actual.get((128 + x, y + i, z), "air") == "air" for i in (1, 2)
                    ), (scenario, x, y, z)
    for cave in m["field"]["caves"]:
        x, z = cave["entrance"]
        outbound = [r for r in m["routes"] if r["from"] == cave["name"]]
        assert outbound and all(any(p[1] < z for p in r["points"]) for r in outbound)


def test_changed_manifest_is_refused_before_region_admission(project):
    design = plan(WorldDesign(project), BRIEFS["town"]["brief"])
    original = project.bridge.call
    project.bridge.call = lambda op, *a, **kw: (
        PALETTE if op == "build_palette" else original(op, *a, **kw)
    )
    project.review_terrain(design)
    manifest = project.terrain_manifest()
    manifest["max_seconds"] += 1
    project.db.execute("UPDATE terrain_manifests SET body=?", (json.dumps(manifest),))
    project.db.commit()
    before = dict(project.region)
    result = project.run_terrain(
        design["revision"],
        captured=(project.bridge.session_id, project.bridge.revision),
    )
    assert result["state"] == "needs_review" and "manifest changed" in result["error"]
    assert project.region == before and not project.bridge.cells


def test_routes_avoid_other_disjoint_architecture(project):
    designer = WorldDesign(project)
    initial = plan(designer, BRIEFS["island"]["brief"])
    design = designer.separate_architecture(initial["revision"])
    manifest = compile_terrain(design, [64, 0])
    route = next(
        r for r in manifest["routes"] if {r["from"], r["to"]} == {"Dock", "Beach Camp"}
    )
    pavilion = next(c for c in design["components"] if c["kind"] == "pavilion")
    x, z, w, d, *_ = pavilion["box"]
    assert all(not (x <= px < x + w and z <= pz < z + d) for px, pz in route["points"])
    refreshed = designer.refresh_paths(design["revision"])
    assert refreshed["components"] == design["components"]
    assert refreshed["requirements"] == design["requirements"]
    assert refreshed["revision"] == design["revision"] + 1


def test_reopened_status_reports_persisted_stage_counts(project):
    design = plan(WorldDesign(project), BRIEFS['town']['brief'])
    manifest = compile_terrain(design, [128, 0])
    manifest.update(cells=1, stages_count=1, max_seconds=7200, max_cells=2000000)
    project.db.execute('INSERT INTO terrain_manifests VALUES (?,?)', (design['revision'], json.dumps(manifest)))
    project.db.execute('INSERT INTO terrain_stages VALUES (?,?,?,?,?)', (design['revision'], 0, 'saved', 1, 1))
    assert project.terrain_progress == {}
    state = project.terrain_status()
    assert state['progress']['verified_stages'] == 1
    assert 'Saved checkpoint' in state['progress']['phase']
    assert project.state == 'idle' and not project.terrain_active
