"""Authorized live fluid Stop and server-loss probes in a new disposable app world."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import threading
import time
import urllib.request
from urllib.parse import urlencode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runtime-assets", type=Path, required=True)
    parser.add_argument(
        "--inference-only",
        action="store_true",
        help="Check Stop against one real inference request, then shut down",
    )
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=False)
    os.environ["GAME_COMPANION_USER_DATA"] = str(args.root / "profile")
    from smb3_agent import lab_ui
    from smb3_agent.minecraft_chat import MinecraftChat
    from smb3_agent.minecraft_practice import PracticeServer, VERSION

    home = args.root / "world"
    home.mkdir()
    (home / "companion-practice.json").write_text(
        json.dumps({"schema": 1, "version": VERSION})
    )
    for name in ("server.jar", "server-download.json", "eula.txt"):
        shutil.copy2(args.runtime_assets / name, home / name)
    assert "eula=true" in (home / "eula.txt").read_text().splitlines()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        gameport = sock.getsockname()[1]
    server = lab_ui._new_lab_ui_server("127.0.0.1", 0)
    service = server.minecraft_chat

    def factory():
        return PracticeServer(home, gameport)

    service.practice_factory = factory
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    report = {"scope": "live disposable world; explicit interruption tests"}
    original_helper = None

    def save():
        (args.root / "report.json").write_text(json.dumps(report, indent=2))

    def post(action, **fields):
        data = urlencode(
            {"csrf_token": server.csrf_token, "action": action, **fields}
        ).encode()
        with urllib.request.urlopen(
            urllib.request.Request(address + "/api/minecraft/chat", data=data),
            timeout=120,
        ) as reply:
            return json.load(reply)

    def wait(predicate, limit=120):
        until = time.monotonic() + limit
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(0.05)
        raise TimeoutError("Live recovery wait expired")

    try:
        post("connect", create="true", project="true")
        wait(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        if args.inference_only:
            service.check_setup()
            with service.provider._discovery_lock:
                pass
            report["provider"] = dict(service.provider.status)
            if not service.provider.status.get("available"):
                raise RuntimeError(
                    "Provider unavailable before live inference-cancellation check"
                )
            # Test-only observation around the unchanged production HTTP worker:
            # record successful POST transmission, never prompt/body/credentials.
            from smb3_agent import app_runtime

            marker = (args.root / "request-sent.json").resolve()
            wrapper = (args.root / "observe_request.py").resolve()
            wrapper.write_text(
                "import json, os, time\nfrom pathlib import Path\n"
                "from smb3_agent import http_inference as transport\n"
                "original = transport.connection\n"
                "def connection(*args, **kwargs):\n"
                "    conn, base = original(*args, **kwargs)\n"
                "    request = conn.request\n"
                "    def observed(method, url, *args, **kwargs):\n"
                "        result = request(method, url, *args, **kwargs)\n"
                "        if method == 'POST' and url.endswith('/chat/completions'):\n"
                f"            Path({str(marker)!r}).write_text(json.dumps({{'pid': os.getpid(), 'sent_at_ms': time.time()*1000, 'stage': 'completion_post_sent'}}))\n"
                "        return result\n"
                "    conn.request = observed\n"
                "    return conn, base\n"
                "transport.connection = connection\ntransport._worker()\n"
            )
            original_helper = app_runtime.helper_command

            def observed_helper(module, *arguments):
                if module == "smb3_agent.http_inference":
                    return [sys.executable, str(wrapper)]
                return original_helper(module, *arguments)

            app_runtime.helper_command = observed_helper
            post(
                "message",
                text="What game mode am I in? Only answer.",
                request_id="inference-stop-check",
                session_id=service.bridge.session_id,
            )
            wait(lambda: marker.exists(), 10)
            report["request_sent"] = json.loads(marker.read_text())
            report["requests_before_stop"] = service.provider.lifecycle()
            assert any(
                r["child_running"] and r["child_pid"] == report["request_sent"]["pid"]
                for r in report["requests_before_stop"]
            )
            started = time.monotonic()
            post("stop")
            report["ack_seconds"] = time.monotonic() - started
            wait(lambda: not service.stopping and not service.busy, 10)
            report["confirmed_seconds"] = time.monotonic() - started
            report["stop_failed"] = service.stop_failed
            report["requests_after_stop"] = service.provider.lifecycle()
            report["usage"] = service.provider.usage
            time.sleep(1)
            report["messages"] = service.messages
            report["build_commands"] = [
                e for e in service.bridge.events if e["type"] == "build_command"
            ]
            assert (
                not service.stop_failed
                and not report["requests_after_stop"]
                and not report["build_commands"]
            )
            report["accepted_game_actions"] = [
                e for e in service.bridge.events if e["type"] == "accepted"
            ]
            report["state_after_stop"] = {
                k: v
                for k, v in service.bridge.observe().items()
                if k in ("active", "queued")
            }
            assert not report["accepted_game_actions"]
            assert report["state_after_stop"] == {"active": None, "queued": 0}
            assert not any(m["role"] == "assistant" for m in service.messages)
            assert (
                report["usage"]
                and report["usage"][-1]["status"] == "failed_or_canceled"
            )
            if report["ack_seconds"] >= 1 or report["confirmed_seconds"] >= 2:
                raise RuntimeError(
                    "Live inference Stop exceeded its acknowledgement/confirmation budget"
                )
            app_runtime.helper_command = original_helper
            original_helper = None
            root = service.root
            messages = list(service.messages)
            service.close()
            service = server.minecraft_chat = MinecraftChat(
                root, provider=server.ai_provider, practice_factory=factory
            )
            post("connect")
            wait(lambda: not service.connecting)
            if service.error:
                raise RuntimeError(service.error)
            time.sleep(1)
            report["reopened"] = {
                "project_state": service.project.state,
                "messages_unchanged": service.messages == messages,
                "requests": service.provider.lifecycle(),
                "accepted_game_actions": [
                    e for e in service.bridge.events if e["type"] == "accepted"
                ],
                "state": {
                    k: v
                    for k, v in service.bridge.observe().items()
                    if k in ("active", "queued")
                },
            }
            assert (
                report["reopened"]["project_state"] == "idle"
                and report["reopened"]["messages_unchanged"]
            )
            assert (
                not report["reopened"]["requests"]
                and not report["reopened"]["accepted_game_actions"]
            )
            assert report["reopened"]["state"] == {"active": None, "queued": 0}
            save()
            print("INFERENCE STOP", report, flush=True)
            return
        service.practice.command("tp CompanionBot -4 -60 32")
        time.sleep(1)
        project = service.project
        palette = service.bridge.call("build_palette")
        basin = []
        for x in range(18):
            for z in range(30, 42):
                basin.append(
                    {"position": dict(x=x, y=-41, z=z), "after": palette["stone"]}
                )
                basin.append(
                    {
                        "position": dict(x=x, y=-40, z=z),
                        "after": palette[
                            "stone" if x in (0, 17) or z in (30, 41) else "water"
                        ],
                    }
                )
        project.prepare(basin)
        original = service.bridge.build_console
        stop_times = {}

        def stop_fluid(operation):
            original(operation)
            if (
                any(c["after"].startswith("water[") for c in operation["cells"])
                and not stop_times
            ):
                stop_times["request_ms"] = time.time() * 1000
                started = time.monotonic()

                def stop():
                    post("stop")
                    stop_times["ack_seconds"] = time.monotonic() - started

                threading.Thread(target=stop, daemon=True).start()

        # Preserve the underlying permission object for storage accounting.
        stop_fluid.practice = original.practice
        service.bridge.build_console = stop_fluid
        post("project_run")
        wait(lambda: bool(stop_times))
        wait(lambda: not service.stopping and project.state != "running", 10)
        confirmed = time.time() * 1000
        report["fluid_stop"] = {
            **stop_times,
            "confirmed_seconds": (confirmed - stop_times["request_ms"]) / 1000,
            "failed": service.stop_failed,
            "project": project.status(),
            "observation": {
                k: v
                for k, v in service.bridge.observe().items()
                if k in ("last_build_change_ms", "active", "queued")
            },
        }
        time.sleep(3)
        report["fluid_stop"]["after_wait_last_change_ms"] = service.bridge.observe()[
            "last_build_change_ms"
        ]
        service.bridge.build_console = original
        report["fluid_continue"] = project.run()
        print("FLUID", report["fluid_stop"], report["fluid_continue"], flush=True)
        save()
        # Kill the actual owned Java process after sending a journaled unit, before receipt.
        project.prepare(
            [
                {"position": dict(x=x, y=-24, z=z), "after": palette["stone"]}
                for x in range(32)
                for z in (44, 45, 46, 47)
            ]
        )
        killed = threading.Event()

        def lose_server(operation):
            original(operation)
            if not killed.is_set():
                killed.set()
                service.practice.process.kill()

        lose_server.practice = original.practice
        service.bridge.build_console = lose_server
        post("project_run")
        wait(lambda: killed.is_set())
        wait(lambda: project.state != "running", 12)
        report["server_loss"] = {"interrupted": project.status()}
        root = service.root
        service.close()
        service = server.minecraft_chat = MinecraftChat(
            root, provider=server.ai_provider, practice_factory=factory
        )
        post("connect")
        wait(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        project = service.project
        report["server_loss"]["reopened"] = project.status()
        time.sleep(0.5)
        report["server_loss"]["automatic_commands"] = sum(
            e["type"] == "build_command" for e in service.bridge.events
        )
        report["server_loss"]["continued"] = project.run()
        print("SERVER", report["server_loss"], flush=True)
        save()
        # A previously unknown occupied cell is not silently adopted as writable.
        service.practice.command("setblock 60 -24 60 glass")
        time.sleep(0.3)
        try:
            project.prepare(
                [{"position": dict(x=60, y=-24, z=60), "after": palette["stone"]}]
            )
            raise AssertionError("Unknown player edit was adopted")
        except ValueError as exc:
            report["unknown_player_edit"] = {
                "refusal": str(exc),
                "cells": project.inspect([dict(x=60, y=-24, z=60)]),
            }
        # Interrupt the final read before its completion can be published.
        target = dict(x=50, y=-24, z=50)
        project.prepare([{"position": target, "after": palette["stone"]}])
        inspect = project.inspect
        counts = [0]

        def stop_verification(positions):
            rows = inspect(positions)
            counts[0] += 1
            if counts[0] == 2:
                started = time.monotonic()
                post("stop")
                wait(lambda: not service.stopping, 5)
                report["verification_stop_seconds"] = time.monotonic() - started
            return rows

        project.inspect = stop_verification
        report["verification_interrupted"] = project.run()
        project.inspect = inspect
        report["verification_continued"] = project.run()
        save()
    except Exception as exc:
        report["failure"] = str(exc)
        save()
        raise
    finally:
        if original_helper is not None:
            app_runtime.helper_command = original_helper
        service.close()
        server.ai_provider.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
        save()


if __name__ == "__main__":
    main()
