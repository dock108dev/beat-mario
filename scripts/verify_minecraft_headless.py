"""Live qualification against the retained isolated practice world (requires EULA)."""

import json
import math
from pathlib import Path
import subprocess
import time
import urllib.request

from smb3_agent.minecraft_bridge import MinecraftBridge
from smb3_agent.minecraft_practice import PracticeServer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "mc-b1-01-live"
OUT.mkdir(parents=True, exist_ok=True)
report = {"minecraft": "1.21.4", "checks": {}}
server = PracticeServer()
bridge = None
sentinel = subprocess.Popen(["sleep", "300"])


def rejected(fn, text):
    try:
        fn()
    except RuntimeError as error:
        assert text in str(error), str(error)
        return str(error)
    raise AssertionError("Expected rejection: " + text)


try:
    server.start()
    bridge = MinecraftBridge()
    report["pids"] = {
        "server": server.process.pid,
        "worker": bridge.process.pid,
        "unrelated_sentinel": sentinel.pid,
    }
    state = bridge.connect()
    time.sleep(1)
    state = bridge.observe()
    sid = bridge.session_id
    authority = {"session_id": sid, "revision": 0}
    report["initial"] = state
    viewer_identity = json.load(
        urllib.request.urlopen(state["viewer_url"] + "/session")
    )
    assert viewer_identity["session_id"] == sid
    report["checks"]["viewer_session_identity"] = viewer_identity
    start = state["position"]
    target = {**start, "x": start["x"] + 5}
    report["checks"]["movement"] = bridge.call(
        "execute",
        {"action": "move", "target": target},
        request_id="live-move",
        **authority,
        timeout_ms=10000,
    )
    assert math.dist(start.values(), bridge.observe()["position"].values()) > 2
    report["checks"]["duplicate"] = rejected(
        lambda: bridge.call(
            "execute",
            {"action": "move", "target": target},
            request_id="live-move",
            **authority,
        ),
        "duplicate_request",
    )
    state = bridge.observe()
    block = state["nearby_blocks"][1]
    result = bridge.call(
        "execute", {"action": "dig", "target": block["position"]}, **authority
    )
    assert result["observed"] == "server_block_change" and result["after"] == "air"
    report["checks"]["dig"] = result
    state = bridge.observe()
    target = {**state["position"], "z": state["position"]["z"] + 25}
    active_id, active = bridge.submit(
        "execute", {"action": "move", "target": target}, timeout_ms=15000, **authority
    )
    queued_id, queued = bridge.submit(
        "execute", {"action": "move", "target": target}, timeout_ms=15000, **authority
    )
    time.sleep(0.3)
    assert bridge.observe()["active"] == active_id
    started = time.monotonic()
    dispatched_epoch_ms = time.time() * 1000
    stop = bridge.stop()
    report["checks"]["stop"] = {
        "result": stop,
        "dispatch_ms": max(
            0,
            next(
                e["at_ms"]
                for e in reversed(bridge.events_after())
                if e["type"] == "cancel_dispatched"
            )
            - dispatched_epoch_ms,
        ),
        "dispatch_clock_resolution_ms": 1,
        "roundtrip_ms": (time.monotonic() - started) * 1000,
        "active": rejected(lambda: active.result(3), "canceled"),
        "queued": rejected(lambda: queued.result(3), "canceled_queued"),
    }
    assert stop["stopped_observed"]
    report["checks"]["stale_revision"] = rejected(
        lambda: bridge.call(
            "execute", {"action": "move", "target": target}, revision=0, session_id=sid
        ),
        "stale_revision",
    )
    stopped_position = bridge.observe()["position"]
    time.sleep(1)
    assert (
        math.dist(stopped_position.values(), bridge.observe()["position"].values())
        < 0.03
    )
    old_viewer = state["viewer_url"]
    bridge.disconnect()
    try:
        urllib.request.urlopen(old_viewer, timeout=1)
        raise AssertionError("Viewer listener survived disconnect")
    except OSError:
        pass
    reconnected = bridge.connect()
    assert bridge.session_id != sid
    assert reconnected["active"] is None and reconnected["queued"] == 0
    report["checks"]["reconnect"] = {
        "old_session": sid,
        "new_session": bridge.session_id,
        "state": reconnected,
    }
    report["checks"]["stale_session"] = rejected(
        lambda: bridge.call(
            "execute", {"action": "move", "target": target}, session_id=sid, revision=0
        ),
        "stale_session",
    )
    # Actual second protocol connection, explicitly NOT a human-client acceptance claim.
    probe = subprocess.run(
        [
            "node",
            "-e",
            """
const mineflayer = require('mineflayer');
const bot = mineflayer.createBot({host:'127.0.0.1',port:25575,username:'JoinProbe',version:'1.21.4',auth:'offline'});
const timer=setTimeout(()=>{bot.end();process.exit(1)},15000);
bot.once('spawn',()=>setTimeout(()=>{console.log(JSON.stringify({players:Object.keys(bot.players),uuid:bot.player.uuid}));bot.quit();clearTimeout(timer)},500));
""",
        ],
        cwd=ROOT / "minecraft-worker",
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    report["checks"]["second_identity_protocol_only"] = json.loads(probe.stdout)
    assert (
        "CompanionBot" in report["checks"]["second_identity_protocol_only"]["players"]
    )
    assert "JoinProbe" in report["checks"]["second_identity_protocol_only"]["players"]
    report["status"] = "live_protocol_checks_passed"
finally:
    if bridge:
        (OUT / "events.json").write_text(json.dumps(bridge.events_after(), indent=2))
        bridge.close()
    server.close()
    report["cleanup"] = {
        "worker_exited": bridge is None or bridge.process.poll() is not None,
        "server_exited": server.process is None or server.process.poll() is not None,
        "unrelated_process_untouched": sentinel.poll() is None,
        "world_retained": (server.home / "practice-world" / "level.dat").exists(),
    }
    sentinel.terminate()
    sentinel.wait(timeout=3)
    (OUT / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
