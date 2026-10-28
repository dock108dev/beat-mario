"""Real stdio worker checks without a game server or OS input permissions."""

import json
import shutil
import time

import pytest

from smb3_agent.minecraft_bridge import MinecraftBridge, WORKER
from smb3_agent.minecraft_practice import PracticeServer

pytestmark = pytest.mark.skipif(
    not shutil.which("node") or not (WORKER.parent / "node_modules").exists(),
    reason="Run npm ci --prefix minecraft-worker first",
)


def test_protocol_rejects_duplicate_and_stale_commands_and_closes_child():
    bridge = MinecraftBridge()
    try:
        for rid, expected in [("once", "stale_session"), ("once", "duplicate_request")]:
            with pytest.raises(RuntimeError, match=expected):
                bridge.call(
                    "execute", session_id="never-connected", request_id=rid, revision=0
                )
        with pytest.raises(RuntimeError, match="invalid_timeout"):
            bridge.call("observe", session_id="never-connected", timeout_ms=0)
    finally:
        bridge.close()
    assert bridge.process.poll() == 0


def test_malformed_frame_does_not_kill_protocol():
    with MinecraftBridge() as bridge:
        bridge.process.stdin.write("{bad json}\n")
        bridge.process.stdin.flush()
        deadline = time.monotonic() + 3
        while not bridge.events_after() and time.monotonic() < deadline:
            time.sleep(0.01)
        with pytest.raises(RuntimeError, match="stale_session"):
            bridge.call("observe", session_id="none")
        assert any(e.get("error") == "invalid_json" for e in bridge.events_after())


def test_failed_connect_does_not_reuse_session():
    with MinecraftBridge() as bridge:
        # Invalid configuration never attempts a socket connection.
        with pytest.raises(RuntimeError, match="invalid_port"):
            bridge.connect(port=0)
        assert bridge.session_id is None
        with pytest.raises(RuntimeError, match="invalid_port"):
            bridge.connect(port=0)


def test_existing_unmarked_world_is_preserved(tmp_path):
    original = tmp_path / "level.dat"
    original.write_bytes(b"owner-save")
    with pytest.raises(ValueError, match="Refusing to adopt"):
        PracticeServer(tmp_path).prepare(accept_eula=True)
    assert original.read_bytes() == b"owner-save"
    assert not (tmp_path / "eula.txt").exists()


def test_new_world_requires_explicit_eula(tmp_path):
    with pytest.raises(ValueError, match="Owner must accept"):
        PracticeServer(tmp_path).prepare()
    assert not (tmp_path / "eula.txt").exists()


def test_world_version_mismatch_is_not_migrated(tmp_path):
    marker = tmp_path / "companion-practice.json"
    marker.write_text(json.dumps({"schema": 1, "version": "26.3"}))
    with pytest.raises(ValueError, match="version/ownership mismatch"):
        PracticeServer(tmp_path).prepare(accept_eula=True)
    assert json.loads(marker.read_text())["version"] == "26.3"


def test_execute_cannot_acquire_new_authority_implicitly():
    with MinecraftBridge() as bridge:
        with pytest.raises(ValueError, match="captured"):
            bridge.submit("execute", {"action": "move"})
