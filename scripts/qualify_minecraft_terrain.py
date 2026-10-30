"""Explicit local-provider/design checks; uses a fresh disposable Minecraft world."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import resource
import threading
import time
from urllib.parse import urlencode
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runtime-assets", type=Path, required=True)
    parser.add_argument("--scenario", choices=("island", "town"), default="island")
    parser.add_argument("--mechanisms-from", type=Path)
    parser.add_argument("--hold-seconds", type=int, default=0)
    parser.add_argument("--requirements", action="store_true")
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=False)
    if args.mechanisms_from:
        prior = json.loads((args.mechanisms_from / "report.json").read_text())
        if prior.get("scope") != "Source app, actual provider, new disposable world":
            raise ValueError("Only a recorded disposable design trial may be copied")
        shutil.copytree(args.mechanisms_from / "profile", args.root / "profile")
        shutil.copytree(args.mechanisms_from / "world", args.root / "world")
    os.environ["GAME_COMPANION_USER_DATA"] = str(args.root / "profile")
    from smb3_agent import lab_ui
    from smb3_agent.minecraft_practice import PracticeServer, VERSION

    home = args.root / "world"
    if not args.mechanisms_from:
        home.mkdir()
        (home / "companion-practice.json").write_text(
            json.dumps({"schema": 1, "version": VERSION})
        )
        for name in ("server.jar", "server-download.json", "eula.txt"):
            shutil.copy2(args.runtime_assets / name, home / name)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = lab_ui._new_lab_ui_server("127.0.0.1", 0)
    service = server.minecraft_chat
    service.practice_factory = lambda: PracticeServer(home, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    report = {
        "continued_from": str(args.mechanisms_from) if args.mechanisms_from else None,
        "address": address,
        "scope": "Source app, actual provider, new disposable world",
        "steps": [],
    }

    def save():
        (args.root / "report.json").write_text(json.dumps(report, indent=2))

    def post(action, **fields):
        data = urlencode(
            {
                "csrf_token": server.csrf_token,
                "action": action,
                "session_id": service.bridge.session_id if service.bridge else "",
                **fields,
            }
        ).encode()
        with urllib.request.urlopen(
            urllib.request.Request(address + "/api/minecraft/chat", data=data),
            timeout=120,
        ) as response:
            return json.load(response)

    def wait(predicate, seconds=120):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(0.1)
        raise TimeoutError("Qualification wait expired")

    def message(text, design=False):
        start = time.monotonic()
        before = len(service.provider.usage)
        post(
            "message",
            text=text,
            request_id=str(time.time_ns()),
            design=str(design).lower(),
        )
        wait(lambda: not service.busy, 1240)
        step = {
            "request": text,
            "design": design,
            "seconds": time.monotonic() - start,
            "error": service.error,
            "messages": service.messages[-6:],
            "usage": service.provider.usage[before:],
            "plan": service.designer.snapshot() if service.designer else None,
            "proposals": [
                e for e in service.events if e.get("kind") == "design_proposal"
            ],
        }
        report["steps"].append(step)
        save()
        print(
            json.dumps(
                {
                    "request": text[:120],
                    "seconds": step["seconds"],
                    "error": step["error"],
                    "planning": step["plan"]["current"].get("planning")
                    if step["plan"] and step["plan"]["current"]
                    else None,
                    "calls": len(step["usage"]),
                }
            ),
            flush=True,
        )
        if service.error:
            raise RuntimeError(service.error)
        return step

    try:
        post(
            "connect",
            **({} if args.mechanisms_from else {"create": "true", "project": "true"}),
        )
        wait(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        service.check_setup()
        with service.provider._discovery_lock:
            pass
        if not service.provider.status["available"]:
            raise RuntimeError("Provider unavailable")
        fixture = json.loads(Path("data/minecraft/design-briefs.json").read_text())[
            args.scenario
        ]
        message(fixture["brief"], True)
        revision = service.designer.current()["revision"]
        start = time.monotonic()
        post("terrain_review", design_revision=revision)
        report["review_seconds"] = time.monotonic() - start
        report["terrain_review"] = service.project.terrain_status()
        print(
            "REVIEWED",
            {
                k: v
                for k, v in report["terrain_review"].items()
                if k not in ("preview", "reservations")
            },
            flush=True,
        )
        save()
        construction_began = time.monotonic()
        report["phase_observations"] = []
        post("terrain_run", design_revision=revision)
        wait(lambda: service.project.terrain_active, 10)
        wait(
            lambda: (
                bool(
                    service.project.db.execute(
                        "SELECT 1 FROM units WHERE status='verified' LIMIT 1"
                    ).fetchone()
                )
                or not service.project.terrain_active
            ),
            120,
        )
        if not service.project.terrain_active:
            raise RuntimeError(
                service.project.error or "Terrain ended before Stop check"
            )
        report["first_verified_seconds"] = time.monotonic() - construction_began
        started = time.monotonic()
        post("stop")
        wait(lambda: not service.stopping and not service.project.terrain_active, 30)
        report["solid_stop"] = {
            "seconds": time.monotonic() - started,
            "state": service.project.state,
            "confirmed": not service.stop_failed,
        }
        save()
        print("STOP", report["solid_stop"], flush=True)
        post("terrain_run", design_revision=revision)
        start = time.monotonic()
        last = 0
        fluid_stopped = False
        while service.project.terrain_active:
            if time.monotonic() - start > 7500:
                raise TimeoutError("Terrain harness deadline")
            if (
                not fluid_stopped
                and service.project.terrain_progress.get("phase") == "water"
            ):
                latest = service.project.db.execute(
                    "SELECT cells,status FROM units ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if (
                    latest
                    and latest[1] == "verified"
                    and any(
                        c["after"].split("[")[0] == "water"
                        for c in json.loads(latest[0])
                    )
                ):
                    began = time.monotonic()
                    post("stop")
                    wait(
                        lambda: (
                            not service.stopping and not service.project.terrain_active
                        ),
                        30,
                    )
                    report["fluid_stop"] = {
                        "seconds": time.monotonic() - began,
                        "confirmed": not service.stop_failed,
                        "state": service.project.state,
                    }
                    root = service.root
                    before = service.designer.snapshot()
                    service.close()
                    from smb3_agent.minecraft_chat import MinecraftChat

                    service = server.minecraft_chat = MinecraftChat(
                        root,
                        provider=server.ai_provider,
                        practice_factory=lambda: PracticeServer(home, port),
                    )
                    post("connect")
                    wait(lambda: not service.connecting)
                    if service.error:
                        raise RuntimeError(service.error)
                    assert (
                        service.project.state == "idle"
                        and not service.project.terrain_active
                        and service.designer.snapshot() == before
                    )
                    report["fluid_reopen_idle"] = True
                    save()
                    print("FLUID STOP AND REOPEN", report["fluid_stop"], flush=True)
                    post("terrain_run", design_revision=revision)
                    fluid_stopped = True
            if time.monotonic() - last > 20:
                report["progress"] = service.project.terrain_status()
                report["phase_observations"].append(
                    {
                        "seconds": time.monotonic() - construction_began,
                        **service.project.terrain_progress,
                    }
                )
                report["source_peak_rss_bytes"] = resource.getrusage(
                    resource.RUSAGE_SELF
                ).ru_maxrss
                save()
                print("PROGRESS", report["progress"]["progress"], flush=True)
                last = time.monotonic()
            time.sleep(0.2)
        report["construction_wall_seconds"] = time.monotonic() - construction_began
        report["terrain_result"] = service.project.status()
        save()
        if service.project.state != "complete":
            raise RuntimeError(service.project.error or "Terrain incomplete")
        print(
            "TERRAIN COMPLETE",
            report["terrain_result"]["terrain"]["progress"],
            flush=True,
        )
        root = service.root
        before = service.designer.snapshot()
        manifest = service.project.terrain_manifest()
        service.close()
        from smb3_agent.minecraft_chat import MinecraftChat

        service = server.minecraft_chat = MinecraftChat(
            root,
            provider=server.ai_provider,
            practice_factory=lambda: PracticeServer(home, port),
        )
        post("connect")
        wait(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        assert service.project.state == "idle" and not service.project.terrain_active
        assert (
            service.designer.snapshot() == before
            and service.project.terrain_manifest() == manifest
        )
        report["reopened_idle"] = True
        save()
        print("TERRAIN MECHANISMS PASSED", address, flush=True)
        time.sleep(min(60, args.hold_seconds))
    except Exception as exc:
        report["failure"] = str(exc)
        save()
        raise
    finally:
        service.close()
        server.ai_provider.close()
        server.shutdown()
        server.server_close()
        thread.join(3)
        report["shutdown"] = True
        save()


if __name__ == "__main__":
    main()
