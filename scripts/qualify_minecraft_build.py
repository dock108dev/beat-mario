"""Explicit live qualification in a fresh isolated world; never adopts retained saves."""

import argparse
import hashlib
import subprocess
import json
import os
from pathlib import Path
import shutil
import socket
import threading
import time
import urllib.request
from urllib.parse import urlencode


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--runtime-assets", type=Path, required=True)
    a = p.parse_args()
    a.root.mkdir(parents=True, exist_ok=False)
    os.environ["GAME_COMPANION_USER_DATA"] = str(a.root / "profile")
    from smb3_agent import lab_ui
    from smb3_agent.minecraft_practice import PracticeServer, VERSION

    home = a.root / "world"
    home.mkdir()
    (home / "companion-practice.json").write_text(
        json.dumps({"schema": 1, "version": VERSION})
    )
    for name in ("server.jar", "server-download.json", "eula.txt"):
        shutil.copy2(a.runtime_assets / name, home / name)
    if "eula=true" not in (home / "eula.txt").read_text().splitlines():
        raise ValueError("An existing owner-accepted server EULA receipt is required")
    server = lab_ui._new_lab_ui_server("127.0.0.1", 0)
    service = server.minecraft_chat
    gameport = port()
    service.practice_factory = lambda: PracticeServer(home, gameport)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    (a.root / "connection.json").write_text(
        json.dumps({"url": address, "pid": os.getpid()})
    )
    code_paths = [
        *Path("src/smb3_agent").glob("*.py"),
        *Path("minecraft-worker").glob("*.cjs"),
        Path(__file__),
    ]

    def code_digest():
        return hashlib.sha256(
            b"".join(p.read_bytes() for p in sorted(code_paths))
        ).hexdigest()

    report = {
        "source_digest": code_digest(),
        "source": os.popen("git rev-parse HEAD").read().strip(),
        "trials": [],
        "scope": "disposable fixture, source app, not owner/full-project acceptance",
    }

    def post(action, **fields):
        data = urlencode(
            {"csrf_token": server.csrf_token, "action": action, **fields}
        ).encode()
        with urllib.request.urlopen(
            urllib.request.Request(address + "/api/minecraft/chat", data=data),
            timeout=120,
        ) as r:
            return json.load(r)

    def wait_for(f, seconds=120):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if f():
                return
            time.sleep(0.1)
        raise TimeoutError("qualification wait expired")

    def save():
        (a.root / "report.json").write_text(json.dumps(report, indent=2))

    try:
        post("connect", create="true", project="true")
        wait_for(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        service.practice.command("gamemode creative CompanionBot")
        service.practice.command("tp CompanionBot -4 -60 32")
        time.sleep(3)
        report["initial"] = service.bridge.observe()
        print("CONNECTED", address, report["initial"]["position"], flush=True)
        # Homogeneous equal-sized writes to empty cells, three trials per path.
        palette = service.bridge.call("build_palette")
        report["palette"] = palette
        for mode_index, mode in enumerate(
            ("ordinary", "ordinary_batch", "batch", "bulk")
        ):
            if mode_index:
                chat_root = service.root
                service.close()
                from smb3_agent.minecraft_chat import MinecraftChat

                service = server.minecraft_chat = MinecraftChat(
                    chat_root,
                    provider=server.ai_provider,
                    practice_factory=lambda: PracticeServer(home, gameport),
                )
                post("connect")
                wait_for(lambda: not service.connecting)
                if service.error:
                    raise RuntimeError(service.error)
            for trial in range(3):
                z = 2 + mode_index * 10 + trial * 2
                positions = [dict(x=x, y=-60, z=z) for x in range(3, 11)]
                service.practice.command(f"tp CompanionBot 6 -60 {z + 3}")
                service.practice.command("give CompanionBot oak_planks 64")
                time.sleep(0.7)
                project = service.project
                cells = [
                    {"position": p, "after": palette["oak_planks"]} for p in positions
                ]
                project.prepare(cells)
                started = time.monotonic()
                try:
                    if mode == "ordinary":
                        for position in positions:
                            service.bridge.call(
                                "execute",
                                {
                                    "action": "place",
                                    "target": position,
                                    "item": "oak_planks",
                                },
                                session_id=service.bridge.session_id,
                                revision=service.bridge.revision,
                                timeout_ms=10000,
                            )
                        result = {"state": "complete"}
                    elif mode == "ordinary_batch":
                        service.bridge.call(
                            "execute",
                            {
                                "action": "place_batch",
                                "cells": [
                                    {"position": p, "item": "oak_planks"}
                                    for p in positions
                                ],
                            },
                            session_id=service.bridge.session_id,
                            revision=service.bridge.revision,
                            timeout_ms=30000,
                        )
                        result = {"state": "complete"}
                    else:
                        result = project.run(mode)
                except Exception as exc:
                    result = {"state": "failed", "error": str(exc)}
                elapsed = time.monotonic() - started
                verified = sum(
                    c["state"] == palette["oak_planks"]
                    for c in project.inspect(positions)
                )
                report["trials"].append(
                    {
                        "mode": mode,
                        "trial": trial,
                        "warmth": "fresh_server_process_first_action"
                        if trial == 0
                        else "warm_server_process",
                        "cells": 8,
                        "verified": verified,
                        "seconds": elapsed,
                        "result": result,
                    }
                )
                save()
                print(
                    "TRIAL", mode, trial, result["state"], elapsed, verified, flush=True
                )
        service.practice.command("tp CompanionBot -4 -60 32")
        time.sleep(2)
        # Live Stop and explicit continuation using the same app endpoint.
        cells = [
            {"position": dict(x=x, y=-24, z=z), "after": palette["stone"]}
            for z in range(44, 48)
            for x in range(32)
        ]
        project.prepare(cells)
        post("project_run")
        wait_for(lambda: project.state == "running", 5)
        time.sleep(0.1)
        t = time.monotonic()
        stop_request_ms = time.time() * 1000
        post("stop")
        ack = time.monotonic() - t
        wait_for(lambda: not service.stopping and project.state != "running", 8)
        report["stop"] = {
            "ack_seconds": ack,
            "confirmed_seconds": time.monotonic() - t,
            "stop_failed": service.stop_failed,
            "request_ms": stop_request_ms,
            "last_change_ms": service.bridge.observe()["last_build_change_ms"],
            "project": project.status(),
        }
        time.sleep(0.2)
        report["stop"]["late_commands"] = len(
            [
                e
                for e in service.bridge.events
                if e["type"] == "build_command"
                and e["at_ms"] > time.time() * 1000 - 200
            ]
        )
        report["continued"] = project.run()
        # Durable store restart at every write-ahead boundary; no automatic mutation.
        from smb3_agent.minecraft_build import BuildProject

        report["faults"] = []
        for index, point in enumerate(("intent", "write", "receipt")):
            project.prepare(
                [
                    {
                        "position": dict(x=4 + index, y=-23, z=50),
                        "after": palette["stone"],
                    }
                ]
            )

            def fault(stage, uid):
                if stage == point:
                    raise RuntimeError("injected interruption")

            interrupted = project.run(fault=fault)
            project.close()
            project = service.project = BuildProject(
                service.root / "build-project",
                service.practice.world_id,
                service.bridge.build_console.region,
                service.bridge,
            )
            idle = project.state
            resumed = project.run()
            report["faults"].append(
                {
                    "point": point,
                    "interrupted": interrupted,
                    "reopened_state": idle,
                    "continued": resumed,
                }
            )
        project.prepare(
            [
                {"position": dict(x=x, y=-23, z=50), "after": palette["stone"]}
                for x in (8, 10)
            ]
        )
        project.run()
        service.practice.command("setblock 8 -23 50 glass")
        time.sleep(0.3)
        report["player_conflict"] = project.run(undo=True)
        report["player_preserved"] = (
            project.inspect([dict(x=8, y=-23, z=50)])[0]["state"] == "glass"
        )
        report["selective_undo"] = project.run(undo=True, undo_unmodified=True)
        report["selective_cells"] = project.inspect(
            [dict(x=x, y=-23, z=50) for x in (8, 10)]
        )
        project.prepare(
            [{"position": dict(x=9, y=-23, z=50), "after": palette["stone"]}]
        )
        project.run()
        report["undo"] = project.run(undo=True)
        report["undo_repeat"] = project.run(undo=True)
        # Close/reopen the actual application service and server, keeping their isolated data.
        chat_root = service.root
        service.close()
        from smb3_agent.minecraft_chat import MinecraftChat

        service = server.minecraft_chat = MinecraftChat(
            chat_root,
            provider=server.ai_provider,
            practice_factory=lambda: PracticeServer(home, gameport),
        )
        post("connect")
        wait_for(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        project = service.project
        report["reopen"] = {
            "state": project.state,
            "automatic_resume": False,
            "session": service.bridge.session_id,
        }
        service.practice.command("tp CompanionBot -4 -60 32")
        service.practice.command("setblock 50 -60 10 gold_block")
        for x, z in ((49, 10), (53, 13)):
            service.practice.command(f"fill {x} -60 {z} {x} -56 {z} oak_log")
            service.practice.command(
                f"fill {x - 1} -55 {z - 1} {x + 1} -53 {z + 1} oak_leaves[persistent=true]"
            )
        time.sleep(1)
        protected = [
            dict(x=x, y=y, z=z)
            for x in range(48, 56)
            for z in range(8, 16)
            for y in range(-60, -20)
        ]

        def scan(points):
            return [
                row
                for offset in range(0, len(points), 256)
                for row in project.inspect(points[offset : offset + 256])
            ]

        protected_before = scan(protected)
        started = time.monotonic()
        post("project_prepare")
        report["prepare_seconds"] = time.monotonic() - started
        prepared = json.loads(
            project.db.execute(
                "SELECT cells FROM designs WHERE revision=?", (project.revision,)
            ).fetchone()[0]
        )
        report["preflight"] = {
            "cells": len(prepared),
            "chunks": len(
                {(c["position"]["x"] // 16, c["position"]["z"] // 16) for c in prepared}
            ),
            "expected_states": sorted({c["after"] for c in prepared}),
            "block_entities": sum(c["after"].startswith("chest[") for c in prepared),
            "journal_estimate_bytes": len(prepared) * 1024,
        }
        save()
        post("project_run", mode="bulk")
        wait_for(lambda: service.project.state == "running", 5)
        chat_started = time.monotonic()
        try:
            post(
                "message",
                text="What game mode am I in? Only answer; do not change anything.",
                request_id="construction-question",
                session_id=service.bridge.session_id,
            )
        except urllib.error.HTTPError as exc:
            report["chat_unavailable"] = {
                "http_status": exc.code,
                "provider": dict(service.provider.status),
            }
        samples = []
        status_latencies = []
        while service.project.state == "running":
            time.sleep(2)
            status_started = time.monotonic()
            with urllib.request.urlopen(
                address + "/api/minecraft/chat", timeout=5
            ) as response:
                json.load(response)
            status_latencies.append(time.monotonic() - status_started)
            samples.append(
                subprocess.check_output(
                    [
                        "ps",
                        "-o",
                        "pid=,rss=,%cpu=",
                        "-p",
                        ",".join(
                            str(p)
                            for p in (
                                os.getpid(),
                                service.practice.process.pid,
                                service.bridge.process.pid,
                            )
                        ),
                    ],
                    text=True,
                )
            )
            print("PROGRESS", service.project.status()["units"], flush=True)
        report["resource_samples"] = samples
        report["status_seconds"] = status_latencies
        report["view_samples"] = [
            e for e in service.bridge.events if e["type"] == "viewer_sample"
        ]
        wait_for(lambda: not service.busy, 245)
        report["chat"] = {
            "reply_seconds": (
                service.messages[-1]["at_ms"] - service.messages[-2]["at_ms"]
            )
            / 1000
            if len(service.messages) >= 2
            else None,
            "elapsed_observed_seconds": time.monotonic() - chat_started,
            "messages": service.messages[-2:],
            "usage": service.provider.usage[-1:],
        }
        report["protected_unchanged"] = scan(protected) == protected_before
        report["outside_design_player_edit"] = project.inspect(
            [dict(x=8, y=-23, z=50)]
        )[0]["state"]
        report["slice_cells"] = json.loads(
            project.db.execute(
                "SELECT cells FROM designs WHERE revision=?", (project.revision,)
            ).fetchone()[0]
        )
        report["changed_cells"] = sum(
            c["before"] != c["after"] for c in report["slice_cells"]
        )
        report["design_cells"] = len(report.pop("slice_cells"))
        report["store_bytes"] = sum(
            p.stat().st_size for p in a.root.rglob("*") if p.is_file()
        )
        report["slice"] = {
            "seconds": service.project.elapsed,
            "result": service.project.status(),
        }
        save()
        print("SLICE", report["slice"], flush=True)
        # Traversal uses normal movement, not teleportation between destinations.
        report["traversal"] = []
        traversal_started = time.monotonic()
        for target in [
            dict(x=10, y=-54, z=31),
            dict(x=20, y=-54, z=27),
            dict(x=27, y=-51, z=21),
            dict(x=27, y=-51, z=24),
            dict(x=36, y=-51, z=27),
            dict(x=27, y=-51, z=24),
            dict(x=33, y=-51, z=41),
            dict(x=49, y=-51, z=41),
            dict(x=33, y=-51, z=41),
            dict(x=20, y=-54, z=27),
            dict(x=5, y=-53, z=24),
            dict(x=10, y=-53, z=24),
            dict(x=20, y=-54, z=17),
            dict(x=27, y=-53, z=10),
            dict(x=14, y=-53, z=6),
        ]:
            try:
                if target == dict(x=27, y=-51, z=24) and not any(
                    row.get("target") == target for row in report["traversal"]
                ):
                    service.bridge.call(
                        "execute",
                        {
                            "action": "build_probe",
                            "target": dict(x=27, y=-51, z=22),
                            "keep_open": True,
                        },
                        session_id=service.bridge.session_id,
                        revision=service.bridge.revision,
                        timeout_ms=10000,
                    )
                result = service.bridge.call(
                    "execute",
                    {"action": "move", "target": target},
                    session_id=service.bridge.session_id,
                    revision=service.bridge.revision,
                    timeout_ms=30000,
                )
                report["traversal"].append({"target": target, "result": result})
            except Exception as exc:
                report["traversal"].append({"target": target, "error": str(exc)})
                break
        report["traversal_seconds"] = time.monotonic() - traversal_started
        report["functional"] = []
        # Separate test positioning is disclosed; it does not count as traversal.
        service.practice.command("tp CompanionBot 27 -51 24")
        service.practice.command("give CompanionBot oak_planks 1")
        time.sleep(0.5)
        for target in [dict(x=26, y=-51, z=25), dict(x=27, y=-51, z=22)]:
            try:
                result = service.bridge.call(
                    "execute",
                    {"action": "build_probe", "target": target},
                    session_id=service.bridge.session_id,
                    revision=service.bridge.revision,
                    timeout_ms=10000,
                )
                report["functional"].append({"target": target, "result": result})
            except Exception as exc:
                report["functional"].append({"target": target, "error": str(exc)})
        report["source_unchanged_during_run"] = code_digest() == report["source_digest"]
        save()
        print(
            "FINAL",
            report["stop"],
            report["traversal"],
            report["functional"],
            flush=True,
        )
    except Exception as exc:
        report["failure"] = str(exc)
        save()
        raise
    finally:
        service.close()
        server.ai_provider.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
        save()


if __name__ == "__main__":
    main()
