import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.player_store import PlayerStore
from smb3_agent.player_setup import PlayerSetupService
from smb3_agent.minecraft_skills import (
    MinecraftSkills,
    SpatialObservation,
    wall_cells,
    reached_face,
    visible_spatial,
)
from smb3_agent.skill_runtime import FiniteSkillRuntime
from smb3_agent.host_contracts import InputCommand, InputKind


def test_profile_roundtrip_edit_import_duplicate_history_no_authority(tmp_path):
    store = PlayerStore(tmp_path)
    p = store.save(game="minecraft", name="Practice")
    store.record(
        p["id"],
        {
            "status": "partial",
            "reason": "Unknown target",
            "selection": {"pid": 1},
            "credentials": "secret",
        },
    )
    reopened = PlayerStore(tmp_path)
    assert reopened.load(p["id"]) == p
    edited = reopened.save(
        game="minecraft", name="Changed", notes="Leave the hut alone", identity=p["id"]
    )
    imported = reopened.import_profile(json.dumps(edited))
    assert imported["id"] != edited["id"]
    duplicate = reopened.duplicate(p["id"])
    assert duplicate["id"] != p["id"]
    history = reopened.history(p["id"])
    assert (
        history[0]["status"] == "partial"
        and "selection" not in history[0]
        and "credentials" not in history[0]
    )
    assert not reopened.history(imported["id"])
    report = reopened.report(text="Stop worked, placement unknown", profile_id=p["id"])
    assert "notes" not in report["report"]["profile"]
    assert set(report["report"]["profile"]) == {"id", "game", "settings"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(authority=True),
        lambda p: p.update(id="../escape"),
        lambda p: p.update(executable={"code": "run"}),
        lambda p: p["settings"].update(hud="off"),
        lambda p: p.update(game=["minecraft"]),
    ],
)
def test_unsafe_imports_rejected_without_overwrite(tmp_path, mutation):
    store = PlayerStore(tmp_path)
    p = store.save(game="minecraft", name="Safe")
    mutation(p)
    with pytest.raises((ValueError, TypeError)):
        store.import_profile(json.dumps(p))
    assert len(store.list()) == 1
    assert store.list()[0]["name"] == "Safe"


def test_setup_review_edits_questions_and_controls_never_enable_input(tmp_path):
    controls = []
    service = PlayerSetupService(
        store=PlayerStore(tmp_path),
        neutralize=lambda: controls.append("revoke") or True,
    )
    state = service.dispatch("save", {"game": "minecraft", "name": "Practice"})
    identity = state["selected"]["id"]
    state = service.dispatch(
        "message", {"text": "Finish a 7 by 3 wall with a centered doorway"}
    )
    assert len(state["plan"]["cells"]) == 19 and not state["plan"]["executable"]
    state = service.dispatch("review", {"plan_id": state["plan"]["id"]})
    assert state["reviewed"]
    with pytest.raises(ValueError, match="disabled"):
        service.dispatch("start")
    state = service.dispatch("edit")
    assert not state["plan"] and not state["reviewed"]
    state = service.dispatch("message", {"text": "What can you do?"})
    assert state["plan"] is None
    state = service.dispatch("message", {"text": "Do not move forward"})
    assert state["plan"] is None
    state = service.dispatch("open", {"id": identity})
    assert not state["reviewed"]
    assert len(controls) >= 6


def test_unconfirmed_release_blocks_profile_change(tmp_path):
    service = PlayerSetupService(store=PlayerStore(tmp_path), neutralize=lambda: False)
    with pytest.raises(ValueError, match="unconfirmed"):
        service.dispatch("save", {"game": "minecraft", "name": "Practice"})
    assert not service.store.list()


def test_wall_doorway_and_reachable_face_geometry():
    cells = wall_cells((10, 64, 20), "x")
    assert len(cells) == len(set(cells)) == 19
    assert (
        (13, 64, 20) not in cells
        and (13, 65, 20) not in cells
        and (13, 66, 20) in cells
    )
    assert reached_face((0.5, 0, -2), 0, 0, (0, 1, 0)) == (0, 0, -1)
    assert reached_face((0.01, 0, -2), 0, 0, (0, 1, 0)) is None
    assert reached_face((0.5, 0, -9), 0, 0, (0, 1, 0)) is None


def obs(**changes):
    return replace(
        SpatialObservation(
            10,
            (1, "start", "window"),
            "settings",
            (0.5, 0, -2),
            0,
            0,
            (0, 1, 0),
            "minecraft:stone",
            (0, 0, -1),
            "minecraft:stone",
            True,
            True,
            "pixels",
        ),
        **changes,
    )


def test_spatial_hud_never_infers_creative_or_material():
    value = visible_spatial(
        ["XYZ: 0.500 / 0.000 / -2.000", "Targeted Block: 0, 1, 0", "minecraft:stone"],
        captured_at=10,
        window_identity=(1, "start", "window"),
        settings="settings",
        orientation=SimpleNamespace(heading=0, pitch=0),
    )
    assert not value.creative and value.material is None
    with pytest.raises(FeedbackError):
        MinecraftSkills(value.window_identity, "settings").require_fresh(value, 10)
    with pytest.raises(FeedbackError):
        visible_spatial(
            ["XYZ: 0.500 / 0.000 / -2.000"] * 2,
            captured_at=10,
            window_identity=(),
            settings="s",
            orientation=SimpleNamespace(heading=0, pitch=0),
        )


def test_placement_reconciles_only_expected_cell_not_delivery_or_wrong_block():
    provider = MinecraftSkills(
        (1, "start", "window"), "settings", screen_center=(100, 100)
    )
    p = {"anchor": (0, 1, -1), "axis": "x", "material": "minecraft:stone"}
    result = {"completed": [], "unknown": []}
    provider.validate("place", p)
    command = provider.next("place", p, obs(), result)
    assert command.control == "right_button" and command.duration_ms == 60
    with pytest.raises(FeedbackError, match="independently"):
        provider.reconcile("place", p, obs(), obs(), result)
    assert not result["completed"]
    provider.reconcile("place", p, obs(), obs(target=(0, 1, -1)), result)
    assert provider.complete("place", p, result)
    with pytest.raises(FeedbackError, match="protected"):
        MinecraftSkills(
            (1, "start", "window"), "settings", protected=[(0, 1, -1)]
        ).validate("place", p)


@pytest.mark.parametrize(
    "bad",
    [
        obs(captured_at=8),
        obs(window_identity=(2, "start", "window")),
        obs(settings="changed"),
        obs(creative=False),
    ],
)
def test_freshness_identity_settings_and_mode_refused(bad):
    with pytest.raises(FeedbackError):
        MinecraftSkills((1, "start", "window"), "settings").require_fresh(bad, 10)


def test_shared_runtime_consumes_budget_and_retains_partial_on_cancel():
    canceled = [False]
    emissions = []

    class Provider:
        def validate(self, *a):
            pass

        def require_fresh(self, *a):
            pass

        def next(self, *a):
            return InputCommand(InputKind.KEYBOARD, "w", "hold", 100)

        def reconcile(self, *a):
            raise AssertionError("Canceled action cannot be verified")

        def complete(self, *a):
            return False

    def emit(c):
        emissions.append(c)
        canceled[0] = True

    rt = FiniteSkillRuntime(
        observe=lambda: obs(),
        emit=emit,
        neutralize=lambda: {"confirmed": True},
        canceled=lambda: canceled[0],
        clock=lambda: 10,
    )
    result = rt.run("move", Provider(), {})
    assert (
        result["status"] == "partial"
        and result["input_ms"] == 100
        and len(emissions) == 1
    )
    assert not result["steps"][0]["verified"] and not result["completed"]


def test_shared_runtime_neutral_failure_never_reports_completion():
    provider = SimpleNamespace(
        validate=lambda *a: None,
        require_fresh=lambda *a: None,
        next=lambda *a: None,
        complete=lambda *a: True,
    )
    rt = FiniteSkillRuntime(
        observe=lambda: obs(),
        emit=lambda c: pytest.fail("No input expected"),
        neutralize=lambda: {"confirmed": False},
        canceled=lambda: False,
        clock=lambda: 10,
    )
    assert rt.run("move", provider, {})["status"] == "partial"
