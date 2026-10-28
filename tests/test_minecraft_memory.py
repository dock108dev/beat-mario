from copy import deepcopy
import json
import threading
import pytest
from smb3_agent.minecraft_memory import DurableJSON, MemoryUnavailable, library
from test_minecraft_construction import construction, spec
from test_minecraft_chat import service, Provider, plan, wait
from smb3_agent.minecraft_construction import ConstructionGoal


def test_invalid_write_retains_valid_and_interrupted_temp_is_never_promoted(tmp_path):
    store = DurableJSON(tmp_path / "memory.json", library)
    value = {"schema": 1, "structures": {}, "preferences": {}}
    store.save(value)
    store.save(
        {
            **value,
            "preferences": {
                json.dumps(["world", "overworld", "1.21.4"]): ["use birch"]
            },
        }
    )
    with pytest.raises(ValueError):
        store.save({**value, "schema": 2})
    (tmp_path / "memory.json.interrupted.tmp").write_text("{")
    assert store.load(None)["preferences"]
    assert (tmp_path / "memory.json.interrupted.tmp").exists()


def test_corrupt_primary_preserved_and_explicit_restore_grants_no_authority(tmp_path):
    chat, g = construction(tmp_path)
    g.save_record()
    path = tmp_path / "construction.json"
    path.write_text("{broken")
    opened = service(tmp_path, Provider([]))
    assert opened.construction is None
    assert opened.construction_store.problem
    assert path.read_text() == "{broken"
    with pytest.raises(MemoryUnavailable):
        opened.construction_store.save(g.record)
    opened.recover_memory("construction", opened.construction_store.candidates()[0])
    assert opened.construction["world"] == g.world
    assert opened.memory["structures"][g.id] == opened.construction
    assert opened.goal is opened.supervisor is None
    assert (
        list(tmp_path.glob("construction.json.incident-*"))[0].read_text() == "{broken"
    )
    assert not opened.bridge.actions


def test_named_library_preserves_multiple_and_filters_other_world(tmp_path):
    chat, g = construction(tmp_path)
    chat.remember_details(plan(structure_name="camp hut"), chat.bridge.observe())
    newer = ConstructionGoal(
        chat,
        plan(
            action="build",
            structure=spec(offset={"x": 12, "y": 0, "z": 0}),
            structure_name="workshop",
        ),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = newer
    newer.publish()
    assert len(chat.memory["structures"]) == 2
    assert len(chat.context("what", chat.bridge.observe())["saved_structures"]) == 2
    state = {**chat.bridge.observe(), "world_id": "other"}
    assert not chat.context("what", state)["saved_structures"]
    restored = service(tmp_path, Provider([]))
    restored.bridge.state.update(chat.bridge.state)
    revise = ConstructionGoal(
        restored,
        plan(action="build", structure=spec(revise=True), structure_name="camp hut"),
        restored.bridge.observe(),
        restored.authority(),
    )
    assert revise.spec["origin"] == g.spec["origin"]
    assert restored.goal is None


def test_missing_primary_with_generations_is_not_empty_new_state(tmp_path):
    store = DurableJSON(tmp_path / "memory.json", library)
    value = {"schema": 1, "structures": {}, "preferences": {}}
    store.save(value)
    store.save(value)
    store.path.unlink()
    assert store.load(None) is None
    assert store.problem


def test_disconnect_during_inference_rejects_late_reply(tmp_path):
    gate = threading.Event()
    provider = Provider([{"kind": "goal", "reply": "Starting"}], gate)
    chat = service(tmp_path, provider)
    chat.submit("walk north", "first", "one")
    assert provider.entered.wait(1)
    chat.connection_lost("worker exited")
    gate.set()
    wait(lambda: not chat.busy)
    assert not chat.bridge.actions
    assert chat.goal is None
    assert chat.connection_fault
    with pytest.raises(ValueError, match="reconnect"):
        chat.submit("go", "second", "one")
    chat.reconnect()
    wait(lambda: not chat.connecting)
    assert not chat.connection_fault
    assert not chat.bridge.actions


def test_canceled_construction_retains_partial_consumption(tmp_path):
    chat, g = construction(tmp_path)
    g.placed.append({**deepcopy(g.cells[0]), "consumed": 1})
    g.lost["oak_planks"] = 1
    chat.epoch += 1
    g.run()
    saved = json.loads((tmp_path / "construction.json").read_text())
    assert saved["inventory_losses"] == {"oak_planks": 1}
    assert not saved["outcome"]["complete"]
    assert saved["outcome"]["requires_inspection"]
    assert len(saved["placed"]) == 1


def test_resource_failures_skip_entire_tree_but_preserve_bounded_attempts(tmp_path):
    from test_minecraft_goals import setup

    chat, g = setup(tmp_path)
    chat.bridge.state["resources"] = [
        {"name": "oak_log", "position": {"x": x, "y": y, "z": 0}}
        for x in (2, 5, 8, 11)
        for y in (0, 1, 2)
    ]
    attempted = []

    def child(action):
        attempted.append(action["target"])
        raise ValueError("resource_approach_obstructed")

    g.child = child
    g.run()
    assert [p["x"] for p in attempted] == [2, 5, 8]
    assert g.failures == 3
    assert len(chat.memory["resource_constraints"][json.dumps(g.world)]) == 3


def test_new_proposal_never_mutates_accepted_geometry_in_memory(tmp_path):
    chat, g = construction(tmp_path)
    g.placed.append({**g.cells[0], "consumed": 1})
    g.save_record()
    before = deepcopy(chat.construction)
    ConstructionGoal(
        chat,
        plan(action="build", structure=spec()),
        chat.bridge.observe(),
        chat.authority(),
    )
    assert chat.construction == before


@pytest.mark.parametrize(
    "bad",
    [
        {"preferences": {"not a world": []}},
        {"outcomes": [{"world": ["w", "overworld", "1.21.4"], "reason": 7}]},
        {"resource_constraints": {"bad": [{"target": None}]}},
    ],
)
def test_malformed_nested_memory_is_preserved_and_blocked(tmp_path, bad):
    value = {"schema": 1, "structures": {}, "preferences": {}, **bad}
    path = tmp_path / "memory.json"
    path.write_text(json.dumps(value))
    store = DurableJSON(path, library)
    assert store.load(None) is None
    assert store.problem
    assert json.loads(path.read_text()) == value


def test_missing_retained_world_reconnect_never_recreates_it(tmp_path):
    from types import SimpleNamespace

    chat = service(tmp_path, Provider([]))
    chat.practice = SimpleNamespace(
        home=tmp_path / "missing-world",
        world_id="world",
        process=SimpleNamespace(poll=lambda: 1),
    )
    chat.reconnect()
    wait(lambda: not chat.connecting)
    assert "will not recreate" in chat.error
    assert chat.connection_fault
    assert not chat.snapshot()["state"]["ready"]
    assert not (tmp_path / "missing-world").exists()
    assert not chat.bridge.actions


def test_disconnect_snapshot_does_not_hide_reconnect_failure(tmp_path):
    chat = service(tmp_path, Provider([]))
    chat.error = "Reconnect failed: port occupied"
    chat.bridge.events_after = lambda: [{"type": "disconnected", "session_id": "one"}]
    assert chat.snapshot()["error"] == "Reconnect failed: port occupied"


def test_outcomes_survive_reopening_as_history_without_authority(tmp_path):
    from test_minecraft_goals import setup

    chat, goal = setup(tmp_path)
    goal.run()
    opened = service(tmp_path, Provider([]))
    assert opened.memory["outcomes"][-1]["shortfall"] == 2
    assert opened.memory["outcomes"][-1]["world"] == goal.world
    assert opened.goal is opened.supervisor is None


def test_interrupted_atomic_replace_preserves_committed_primary(tmp_path, monkeypatch):
    store = DurableJSON(tmp_path / "memory.json", library)
    value = {"schema": 1, "structures": {}, "preferences": {}}
    store.save(value)
    before = store.path.read_bytes()

    def interrupted(*args):
        raise OSError("injected interruption before rename")

    monkeypatch.setattr("smb3_agent.minecraft_memory.os.replace", interrupted)
    with pytest.raises(OSError, match="interruption"):
        store.save({**value, "outcomes": []})
    assert store.path.read_bytes() == before
    assert store.load(None) == value
    assert list(tmp_path.glob("memory.json.*.tmp"))
    assert store.candidates()


def test_interruption_before_compatibility_mirror_keeps_canonical_selection(
    tmp_path, monkeypatch
):
    chat, old = construction(tmp_path)
    newer = ConstructionGoal(
        chat,
        plan(
            action="build",
            structure=spec(offset={"x": 12, "y": 0, "z": 0}),
            structure_name="second",
        ),
        chat.bridge.observe(),
        chat.authority(),
    )
    chat.supervisor = newer

    def interrupted(*args):
        raise OSError("injected mirror interruption")

    monkeypatch.setattr(chat.construction_store, "save", interrupted)
    with pytest.raises(OSError):
        newer.publish()
    opened = service(tmp_path, Provider([]))
    assert opened.construction["structure_id"] == newer.id
    assert set(opened.memory["structures"]) == {old.id, newer.id}
    assert opened.goal is opened.supervisor is None
