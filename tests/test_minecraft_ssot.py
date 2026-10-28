"""One delivery policy for setup, profile paths and retained-world reconnect."""

import json
from types import SimpleNamespace

import pytest
from smb3_agent import minecraft_delivery as delivery
from smb3_agent.minecraft_practice import PracticeServer, VERSION
from test_minecraft_chat import service, Provider, wait


@pytest.fixture(autouse=True)
def isolated_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_COMPANION_USER_DATA", str(tmp_path / "profile"))
    monkeypatch.setattr(delivery, "java_runtime", lambda: "/synthetic/java")
    monkeypatch.setattr(delivery, "node_runtime", lambda: "/synthetic/node")


def retained(home):
    (home / "practice-world").mkdir(parents=True)
    (home / "practice-world/level.dat").write_bytes(b"synthetic-world")
    (home / "eula.txt").write_text("eula=true\n")
    (home / "companion-practice.json").write_text(
        json.dumps({"schema": 1, "version": delivery.GAME_VERSION})
    )
    (home / "world-identity.json").write_text(
        json.dumps({"id": "kept", "survival": True})
    )


def test_practice_defaults_resolve_current_profile_not_import_time(
    tmp_path, monkeypatch
):
    assert VERSION == delivery.GAME_VERSION
    assert PracticeServer(survival=True).home == delivery.world_home(True).resolve()
    monkeypatch.setenv("GAME_COMPANION_USER_DATA", str(tmp_path / "second"))
    assert PracticeServer().home == delivery.world_home().resolve()
    assert PracticeServer(survival=True).home == delivery.world_home(True).resolve()
    # An explicit path is never silently redirected to a different world.
    assert (
        PracticeServer(delivery.world_home(), survival=True).home
        == delivery.world_home().resolve()
    )


@pytest.mark.parametrize("damage", ["version", "identity", "mode", "eula", "malformed"])
def test_setup_and_reconnect_refuse_same_damaged_retained_state(tmp_path, damage):
    home = delivery.world_home(True)
    retained(home)
    if damage == "version":
        (home / "companion-practice.json").write_text('{"schema":1,"version":"old"}')
    elif damage == "identity":
        (home / "world-identity.json").write_text('{"id":7,"survival":true}')
    elif damage == "mode":
        (home / "world-identity.json").write_text('{"id":"kept","survival":false}')
    elif damage == "eula":
        (home / "eula.txt").write_text("eula=false\n")
    else:
        (home / "world-identity.json").write_text("[]")
    before = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}
    assert not delivery.setup_status()["worlds"]["survival"]["ready"]
    chat = service(tmp_path / "chat", Provider([]))
    starts = []
    chat.practice = SimpleNamespace(
        home=home,
        world_id="kept",
        survival=True,
        process=SimpleNamespace(poll=lambda: 1),
        close=lambda: starts.append("close"),
        start=lambda: starts.append("start"),
    )
    chat.reconnect()
    wait(lambda: not chat.connecting)
    assert chat.connection_fault
    assert not starts
    assert not chat.bridge.actions
    assert before == {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}


def test_reconnect_requires_original_identity_even_for_other_valid_world(tmp_path):
    home = tmp_path / "world"
    retained(home)
    assert delivery.retained_world(home, survival=True)["id"] == "kept"
    with pytest.raises(ValueError, match="identity changed"):
        delivery.retained_world(home, expected_id="different", survival=True)
