"""First-use guidance cannot turn saved configuration into playable building."""

from smb3_agent.player_onboarding import minecraft_onboarding
from smb3_agent.player_setup import PlayerSetupService
from smb3_agent.player_store import PlayerStore


def test_profile_and_saved_coordinates_do_not_restore_connection(tmp_path):
    store = PlayerStore(tmp_path)
    profile = store.save(
        game="minecraft", name="First use", workspace={
            "anchor": [0, 0, 0], "axis": "x", "material": "minecraft:stone",
            "protected": [], "stop_point": [3, 0, -2],
        },
    )
    setup = PlayerSetupService(store=store)
    first = setup.snapshot()["minecraft_onboarding"]
    assert first["status"] == "profile"
    state = setup.dispatch("open", {"id": profile["id"]})
    guidance = state["minecraft_onboarding"]
    assert guidance["status"] == "connection"
    assert guidance["steps"][0]["status"] == "done"
    assert guidance["steps"][2]["status"] == "pending"
    assert guidance["steps"][3]["status"] == "unavailable"
    assert not state["reviewed"] and state["plan"] is None


def test_camera_connection_exposes_build_limitation_instead_of_false_readiness():
    guidance = minecraft_onboarding({"game": "minecraft"}, {
        "connected": True, "features": {"camera": True}, "scope": {"anchor": [0, 0, 0]},
    })
    assert guidance["status"] == "setup_only"
    assert guidance["steps"][1]["status"] == "done"
    assert guidance["steps"][3]["status"] == "unavailable"
    assert guidance["available_tasks"] == ["Small camera adjustments"]
    assert "Finish the wall with its doorway" in guidance["blocked_tasks"]
    assert "update" in guidance["next_action"]


def test_enabled_wall_requires_current_region_and_still_needs_review():
    native = {"connected": True, "features": {"wall": True}}
    guidance = minecraft_onboarding({"game": "minecraft"}, native)
    assert guidance["status"] == "region"
    assert guidance["steps"][3]["status"] == "pending"
    native["scope"] = {"anchor": [0, 0, 0]}
    guidance = minecraft_onboarding({"game": "minecraft"}, native)
    assert guidance["status"] == "task_review"
    assert guidance["steps"][3]["status"] == "next"
    assert "Review" in guidance["next_action"]


def test_unconfirmed_release_and_running_work_take_priority():
    native = {"connected": True, "features": {"wall": True}, "busy": True, "release_blocked": True}
    assert minecraft_onboarding({"game": "minecraft"}, native)["status"] == "release_blocked"
    native["release_blocked"] = False
    assert minecraft_onboarding({"game": "minecraft"}, native)["status"] == "working"


def test_other_game_uses_its_own_onboarding():
    assert minecraft_onboarding({"game": "openttd"}, {}) is None
