from copy import deepcopy
import pytest
from smb3_agent.minecraft_construction import ConstructionGoal, geometry
from test_minecraft_goals import setup
from test_minecraft_chat import plan


def spec(**kw):
    return {**plan()["structure"], "origin": {"x": 3, "y": 0, "z": 0}, **kw}


def test_geometry_varies_preserves_door_and_roof():
    a = geometry(spec())
    assert len(a) == 23
    assert not any(c["position"] == {"x": 4, "y": 0, "z": 0} for c in a)
    assert len(geometry(spec(width=4, material="birch_planks"))) > len(a)
    assert all(
        c["item"] == "birch_planks" for c in geometry(spec(material="birch_planks"))
    )
    with pytest.raises(ValueError):
        geometry(spec(width=100))
    with pytest.raises(ValueError):
        geometry(spec(doorway="me"))


def construction(tmp_path, **kw):
    chat, _ = setup(tmp_path)
    g = ConstructionGoal(
        chat,
        plan(action="build", structure=spec(**kw)),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = g
    g.publish()
    return chat, g


def test_revision_keeps_consumed_material_and_rejects_conflicting_completed_work(
    tmp_path,
):
    chat, g = construction(tmp_path)
    old = g.cells[0]
    g.placed.append({**old, "consumed": 1})
    revised = ConstructionGoal(
        chat,
        plan(
            action="build",
            structure=spec(revise=True, material="birch_planks", remaining_only=True),
        ),
        chat.bridge.observe(),
        chat.authority(),
    )
    assert revised.cells[0]["item"] == "oak_planks"
    assert revised.placed[0]["consumed"] == 1
    assert not revised.conflicts
    chat.construction = g.record
    changed = ConstructionGoal(
        chat,
        plan(action="build", structure=spec(revise=True, material="birch_planks")),
        chat.bridge.observe(),
        chat.authority(),
    )
    assert changed.conflicts
    chat.supervisor = changed
    changed.child = lambda action: {"cells": [{**old, "actual": old["item"]}]}
    changed.run()
    assert not chat.bridge.actions
    assert "not refunded" in chat.messages[-1]["text"]


@pytest.mark.parametrize("field", ["occupied", "protected", "unknown"])
def test_preflight_refuses_before_crafting_or_placement(tmp_path, field):
    chat, g = construction(tmp_path)
    calls = []

    def child(action):
        calls.append(action)
        r = {
            k: [] for k in ["occupied", "protected", "unknown", "unsupported", "cells"]
        }
        r[field] = [deepcopy(g.cells[0])]
        return r

    g.child = child
    g.run()
    assert [c["action"] for c in calls] == ["inspect_site", "inspect_site"]
    assert calls[1]["offer_only"] is True
    assert "incomplete" in chat.messages[-1]["text"]


def test_replaced_construction_cannot_start_child(tmp_path):
    chat, g = construction(tmp_path)
    chat.epoch += 1
    with pytest.raises(ValueError, match="canceled"):
        g.child({"action": "craft", "item": "oak_planks"})
    assert not chat.bridge.actions


def test_persisted_structure_reopens_without_authority_and_revalidates(tmp_path):
    from test_minecraft_chat import Provider, service

    chat, g = construction(tmp_path)
    g.placed.append({**g.cells[0], "consumed": 1})
    g.save_record()
    reopened = service(tmp_path, Provider([]))
    assert reopened.goal is reopened.supervisor is None
    assert reopened.construction["placed"][0]["consumed"] == 1
    reopened.bridge.state.update(chat.bridge.state)
    resumed = ConstructionGoal(
        reopened,
        plan(action="build", structure=spec(revise=True, remaining_only=True)),
        reopened.bridge.observe(),
        reopened.authority(),
    )
    reopened.supervisor = resumed
    calls = []

    def child(action):
        calls.append(action["action"])
        raise ValueError("changed terrain")

    resumed.child = child
    resumed.run()
    assert calls == ["inspect_site"]
    assert "changed terrain" in reopened.messages[-1]["text"]
    reopened.bridge.state["world_id"] = "other"
    with pytest.raises(ValueError, match="this world"):
        ConstructionGoal(
            reopened,
            plan(action="build", structure=spec(revise=True)),
            reopened.bridge.observe(),
            reopened.authority(),
        )


def test_stop_during_craft_result_rejects_next_placement(tmp_path):
    from concurrent.futures import Future

    chat, g = construction(tmp_path)
    f = Future()

    def submit(*args, **kw):
        chat.epoch += 1
        f.set_result({"observed": "inventory_delta"})
        return "craft", f

    chat.bridge.submit = submit
    with pytest.raises(ValueError, match="canceled"):
        g.child({"action": "craft", "item": "oak_planks", "recipe": 0, "times": 1})
    assert not g.placed


def test_revision_recovers_authoritative_block_from_late_old_result(tmp_path):
    chat, g = construction(tmp_path)
    # World placement committed, but the old result was canceled before ledger update.
    c = g.cells[0]
    revised = ConstructionGoal(
        chat,
        plan(
            action="build",
            structure=spec(revise=True, remaining_only=True, material="birch_planks"),
        ),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = revised
    calls = []

    def child(action):
        calls.append(action)
        if len(calls) == 1:
            return {"cells": [{**c, "actual": "oak_planks"}]}
        raise ValueError("end diagnostic")

    revised.child = child
    revised.run()
    assert revised.placed[0]["item"] == "oak_planks"
    assert revised.placed[0]["consumed"] is None
    assert revised.cells[0]["item"] == "oak_planks"


def test_protected_completed_blocks_cannot_be_removed_even_with_permission(tmp_path):
    chat, g = construction(tmp_path)
    c = g.cells[0]
    g.placed.append({**c, "consumed": 1})
    revised = ConstructionGoal(
        chat,
        plan(
            action="build",
            structure=spec(
                revise=True,
                remaining_only=False,
                material="birch_planks",
                allow_removal=True,
            ),
        ),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = revised
    revised.regions = [{"center": c["position"], "radius": 2}]
    calls = []

    def child(action):
        calls.append(action["action"])
        return {"cells": [{**c, "actual": c["item"]}]}

    revised.child = child
    revised.run()
    assert calls == ["inspect_site"]
    assert "Protected" in chat.messages[-1]["text"]


def test_revision_retains_surveyed_origin_even_with_saved_place(tmp_path):
    chat, g = construction(tmp_path)
    chat.places["camp"] = {"position": {"x": 0, "y": 0, "z": 0}, "world": g.world}
    g.spec["origin"] = {"x": 7, "y": 0, "z": 5}
    g.cells = geometry(g.spec)
    g.save_record()
    revised = ConstructionGoal(
        chat,
        plan(
            action="build",
            structure=spec(
                revise=True,
                site_place="camp",
                relocate=False,
                doorway="west",
                allow_removal=True,
            ),
        ),
        chat.bridge.observe(),
        chat.authority(),
    )
    assert revised.spec["origin"] == {"x": 7, "y": 0, "z": 5}


def test_revision_preflights_obstacles_before_authorized_removal(tmp_path):
    chat, g = construction(tmp_path)
    c = g.cells[0]
    g.placed.append({**c, "consumed": 1})
    revised = ConstructionGoal(
        chat,
        plan(
            action="build",
            structure=spec(revise=True, material="birch_planks", allow_removal=True),
        ),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = revised
    calls = []

    def child(action):
        calls.append(action["action"])
        if len(calls) == 1:
            return {"cells": [{**c, "actual": c["item"]}]}
        return {
            "occupied": [{"actual": "dirt"}],
            "unknown": [],
            "protected": [],
            "unsupported": [],
        }

    revised.child = child
    revised.run()
    assert calls == ["inspect_site", "inspect_site"]
    assert "occupied" in chat.messages[-1]["text"]


def test_rejected_new_site_keeps_last_accepted_record(tmp_path):
    chat, g = construction(tmp_path)
    g.placed.append({**g.cells[0], "consumed": 1})
    g.save_record()
    before = (chat.root / "construction.json").read_text()
    proposed = ConstructionGoal(
        chat,
        plan(action="build", structure=spec(material="birch_planks")),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = proposed
    proposed.child = lambda action: {
        "occupied": [{"actual": "dirt"}],
        "unknown": [],
        "protected": [],
        "unsupported": [],
    }
    proposed.run()
    assert chat.construction is g.record
    assert (chat.root / "construction.json").read_text() == before
