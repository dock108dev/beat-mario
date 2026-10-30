import json
from types import SimpleNamespace

import pytest

from smb3_agent.minecraft_build import BuildProject, BuildConsole, validate_cells
from smb3_agent.directory_migration import activate

REGION = {
    "bounds": {"min": dict(x=0, y=0, z=0), "max": dict(x=63, y=63, z=63)},
    "protected": [{"min": dict(x=8, y=0, z=8), "max": dict(x=15, y=63, z=15)}],
}


class Bridge:
    session_id = "session"
    revision = 0

    def __init__(self):
        self.cells = {}

    def call(self, op, args, **kw):
        if op == "inspect_build":
            return [
                {"position": p, "state": self.cells.get(tuple(p.values()), "air")}
                for p in args["positions"]
            ]
        for c in args["cells"]:
            k = tuple(c["position"].values())
            if self.cells.get(k, "air") != c["before"]:
                raise ValueError("conflict")
            self.cells[k] = c["after"]
        return {"observed": "verified_build_batch"}


@pytest.mark.parametrize("point", ["intent", "write", "receipt"])
def test_restart_recovers_each_receipt_boundary(tmp_path, point):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])

    def fail(p, uid):
        if p == point:
            raise RuntimeError("power loss")

    project.run(fault=fail)
    project.close()
    restored = BuildProject(tmp_path, "world", REGION, bridge)
    assert restored.state == "idle"
    assert restored.run()["state"] == "complete"
    assert bridge.cells[(1, 1, 1)] == "stone"
    restored.close()


def test_player_edit_after_prepare_is_not_adopted(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])
    bridge.cells[(1, 1, 1)] = "glass"
    assert project.run()["state"] == "needs_review"
    assert bridge.cells[(1, 1, 1)] == "glass"
    project.close()


def test_first_design_refuses_unrecorded_occupied_cell(tmp_path):
    bridge = Bridge()
    bridge.cells[(1, 1, 1)] = "glass"
    project = BuildProject(tmp_path, "world", REGION, bridge)
    with pytest.raises(ValueError, match="Unrecorded"):
        project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])
    assert bridge.cells[(1, 1, 1)] == "glass"
    project.close()


def test_undo_refuses_changed_cells(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])
    assert project.run()["state"] == "complete"
    bridge.cells[(1, 1, 1)] = "glass"
    assert project.run(undo=True)["state"] == "needs_review"
    assert bridge.cells[(1, 1, 1)] == "glass"
    project.close()


def test_selective_undo_preserves_player_edit_and_undoes_other_cells(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare(
        [{"position": dict(x=x, y=1, z=1), "after": "stone"} for x in (1, 2)]
    )
    assert project.run()["state"] == "complete"
    bridge.cells[(1, 1, 1)] = "glass"
    result = project.run(undo=True, undo_unmodified=True)
    assert result["state"] == "partially_undone"
    assert result["undo_skipped"] == [dict(x=1, y=1, z=1)]
    assert bridge.cells[(1, 1, 1)] == "glass"
    assert bridge.cells[(2, 1, 1)] == "air"
    project.close()


def test_protection_and_console_authority(tmp_path):
    cell = {"position": dict(x=8, y=1, z=8), "before": "air", "after": "stone"}
    with pytest.raises(ValueError):
        validate_cells([cell], REGION)
    with pytest.raises(ValueError):
        BuildConsole(
            SimpleNamespace(home=tmp_path, survival=False, world_id="w"), REGION
        )
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
    cells = [
        {"position": dict(x=x, y=1, z=1), "before": "air", "after": "stone"}
        for x in range(4)
    ]
    console({"nonce": "a" * 32, "cells": cells, "mode": "bulk"})
    assert len(commands) == 2 and " run fill " in commands[0]
    assert commands[0].count("if block") == 4


POINTS = [
    "journal",
    "before:a",
    "activated:a",
    "recorded:a",
    "before:b",
    "activated:b",
    "recorded:b",
    "before:c",
    "activated:c",
    "recorded:c",
    "before_receipt",
    "receipt",
]


@pytest.mark.parametrize("point", POINTS)
def test_migration_restart_each_activation_and_receipt(tmp_path, point):
    source, dest, backup = [tmp_path / n for n in ("source", "dest", "backup")]
    dest.mkdir()
    for n in ("a", "b", "c"):
        (source / n).mkdir(parents=True)
        (source / n / "data").write_text(n)

    def fail(p):
        if p == point:
            raise RuntimeError("power loss")

    with pytest.raises(RuntimeError):
        activate(source, dest, backup, ("a", "b", "c"), fault=fail)
    activate(source, dest, backup, ("a", "b", "c"))
    assert (dest / "artifacts/a/data").read_text() == "a"
    assert (source / "a/data").read_text() == "a"
    assert (dest / "artifacts/c/data").read_text() == "c"


def test_migration_preserves_post_activation_player_edit(tmp_path):
    source, dest, backup = [tmp_path / n for n in ("source", "dest", "backup")]
    dest.mkdir()
    (source / "a").mkdir(parents=True)
    (source / "a/data").write_text("original")

    def fail(p):
        if p == "activated:a":
            raise RuntimeError("power loss")

    with pytest.raises(RuntimeError):
        activate(source, dest, backup, ("a",), fault=fail)
    (dest / "artifacts/a/data").write_text("player")
    with pytest.raises(ValueError, match="changed"):
        activate(source, dest, backup, ("a",))
    assert (dest / "artifacts/a/data").read_text() == "player"


def test_stop_invalidates_admitted_background_start(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])
    authority = (bridge.session_id, bridge.revision)
    project.stop()
    assert project.run(captured=authority)["state"] == "stopped"
    assert not bridge.cells
    project.close()


def test_undo_is_repeatable_and_targets_latest_design(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])
    assert project.run()["state"] == "complete"
    project.prepare([{"position": dict(x=2, y=1, z=1), "after": "stone"}])
    assert project.run()["state"] == "complete"
    assert project.run(undo=True)["state"] == "undone"
    assert project.run(undo=True)["state"] == "undone"
    assert bridge.cells[(1, 1, 1)] == "stone"
    assert bridge.cells[(2, 1, 1)] == "air"
    project.close()


def test_final_verification_detects_late_player_edit(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])

    def edit(point, uid):
        if point == "receipt":
            bridge.cells[(1, 1, 1)] = "glass"

    assert project.run(fault=edit)["state"] == "needs_review"
    assert bridge.cells[(1, 1, 1)] == "glass"
    project.close()


def test_stop_during_last_verification_cannot_publish_complete(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])
    inspect = project.inspect

    def interrupted(positions):
        result = inspect(positions)
        if bridge.cells.get((1, 1, 1)) == "stone":
            project.stop()
        return result

    project.inspect = interrupted
    assert project.run()["state"] == "stopped"
    project.close()


def test_replacement_design_cannot_adopt_known_player_change(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    cells = [{"position": dict(x=1, y=1, z=1), "after": "stone"}]
    project.prepare(cells)
    project.run()
    bridge.cells[(1, 1, 1)] = "glass"
    with pytest.raises(ValueError, match="player change"):
        project.prepare(cells)
    assert bridge.cells[(1, 1, 1)] == "glass"
    project.close()


def test_uncontained_water_refuses_before_mutation(tmp_path):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    with pytest.raises(ValueError, match="contained"):
        project.prepare([{"position": dict(x=2, y=2, z=2), "after": "water[level=0]"}])
    assert not bridge.cells
    project.close()


@pytest.mark.parametrize("point", ["intent", "write", "receipt"])
def test_water_staging_survives_interruption_without_adopting_unknown_edits(
    tmp_path, point
):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    cells = [
        {"position": dict(x=x, y=0, z=z), "after": "stone"}
        for x in range(3)
        for z in range(3)
    ]
    cells += [
        {
            "position": dict(x=x, y=1, z=z),
            "after": "water[level=0]" if x == z == 1 else "stone",
        }
        for x in range(3)
        for z in range(3)
    ]
    project.prepare(cells)

    def interrupt(stage, uid):
        row = json.loads(
            project.db.execute("SELECT cells FROM units WHERE id=?", (uid,)).fetchone()[
                0
            ]
        )
        if stage == point and any(c["after"] == "glass" for c in row):
            raise RuntimeError("interrupted staging")

    assert project.run(fault=interrupt)["state"] == "needs_review"
    project.close()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    assert project.run()["state"] == "complete"
    assert bridge.cells[(1, 1, 1)] == "water[level=0]"
    assert project.run(undo=True)["state"] == "needs_review"
    project.close()


def test_storage_reserve_blocks_new_work_without_pruning(tmp_path, monkeypatch):
    bridge = Bridge()
    project = BuildProject(tmp_path, "world", REGION, bridge)
    monkeypatch.setattr(
        "smb3_agent.minecraft_build.shutil.disk_usage",
        lambda p: SimpleNamespace(free=0),
    )
    with pytest.raises(ValueError, match="storage"):
        project.prepare([{"position": dict(x=1, y=1, z=1), "after": "stone"}])
    assert not bridge.cells and (tmp_path / "project.sqlite").is_file()
    project.close()


def test_display_cache_observes_same_length_database_edits_and_is_detached(tmp_path):
    project = BuildProject(tmp_path, "world", REGION, Bridge())
    body = {"components": [{"name": "A", "cells": [{"after": "stone"}]}]}
    project.db.execute("INSERT INTO architecture_reviews VALUES (1,?)", (json.dumps(body),))
    first = project.architecture_status()
    assert "cells" not in first["components"][0]
    first["components"][0]["name"] = "client edit"
    assert project.architecture_status()["components"][0]["name"] == "A"
    body["components"][0]["name"] = "B"
    project.db.execute("UPDATE architecture_reviews SET body=?", (json.dumps(body),))
    assert project.architecture_status()["components"][0]["name"] == "B"
    project.close()


def test_inference_summary_never_decodes_manifest_geometry(tmp_path, monkeypatch):
    project = BuildProject(tmp_path, "world", REGION, Bridge())
    monkeypatch.setattr(project, "architecture_status", lambda: pytest.fail("geometry read"))
    monkeypatch.setattr(project, "terrain_status", lambda: pytest.fail("terrain read"))
    assert project.summary()["automatic_resume"] is False
    project.close()


def test_storage_error_distinguishes_available_space_and_preserves_reserve(tmp_path, monkeypatch):
    import smb3_agent.minecraft_build as module
    project = BuildProject(tmp_path, 'world', REGION, Bridge())
    try:
        monkeypatch.setattr(module.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1024**3))
        project.check_storage()
        with pytest.raises(ValueError, match='Filesystem storage reserve exhausted: 1073741824 bytes available; 1073742848 required'):
            project.check_storage(1)
    finally:
        project.close()
