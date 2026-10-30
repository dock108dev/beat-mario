"""Explicit local-provider/design checks; uses a fresh disposable Minecraft world."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
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
        report["provider"] = service.provider.status
        save()
        if not service.provider.status["available"]:
            raise RuntimeError("Provider unavailable")
        print("READY " + address, flush=True)
        if args.requirements:
            fixture = json.loads(
                (
                    Path(__file__).resolve().parents[1]
                    / "data/minecraft/design-briefs.json"
                ).read_text()
            )[args.scenario]
            message(fixture["brief"], True)
            initial = service.designer.snapshot()["current"]
            assert initial["extent"] == fixture["extent"]
            assert initial["planning"]["state"] == "ready"
            assert len(initial["requirements"]) == (
                19 if args.scenario == "island" else 13
            )
            assert all(row["status"] == "matched" for row in initial["checklist"])
            by_name = {c["name"]: c for c in initial["components"]}
            for name, expected in fixture["expected"].items():
                for key, value in expected.items():
                    assert by_name[name][key] == value, (name, key)
            for r in initial["requirements"]:
                assert by_name[r["name"]]["connections"] == r["connections"]
                assert (
                    r["source"]["quote"]
                    == fixture["brief"][r["source"]["start"] : r["source"]["end"]]
                )
            report["initial_fidelity"] = {
                "extent": initial["extent"],
                "components": len(initial["components"]),
                "all_checklist_matched": True,
                "expected_dimensions_kinds_rooms": True,
                "connections_and_provenance": True,
            }
            if args.scenario == "island":
                message(
                    "Make Research Station larger inside, 28 by 20. Preserve the rooms and other places.",
                    True,
                )
                after = service.designer.snapshot()["current"]
                new = {c["name"]: c for c in after["components"]}
                assert new["Research Station"]["size"][:2] == [28, 20]
                assert (
                    new["Research Station"]["rooms"]
                    == by_name["Research Station"]["rooms"]
                )
                assert all(
                    new[n] == c for n, c in by_name.items() if n != "Research Station"
                )
                message("Move Dock nearer West Bay. Keep the rest unchanged.", True)
                moved = {
                    c["name"]: c
                    for c in service.designer.snapshot()["current"]["components"]
                }
                assert moved["Dock"]["link"] == "West Bay"
                assert all(moved[n] == c for n, c in new.items() if n != "Dock")
            else:
                message(
                    "Add a third pedestrian bridge 16 by 3, 2 blocks high and a rotated riverside Greenhouse 12 by 10, 6 blocks high; preserve all original buildings.",
                    True,
                )
                after = service.designer.snapshot()["current"]
                new = {c["name"]: c for c in after["components"]}
                assert all(new[n] == c for n, c in by_name.items())
                assert len([c for c in new.values() if c["kind"] == "bridge"]) == 3
                greenhouse = next(
                    c for c in new.values() if "greenhouse" in c["name"].lower()
                )
                assert greenhouse["turn"] == 1 and greenhouse["size"] == [12, 10, 6]
                assert greenhouse["connections"] == ["River"]
            report["targeted_changes_preserved_unaffected"] = True
            message(
                "Use a less industrial, natural palette. Preserve all places.", True
            )
            assert service.designer.current()["palette"] == "natural"
            message(
                "Welcome Pavilion: open pavilion 8 by 6, 4 blocks high, south.", True
            )
            current = service.designer.current()
            sample = next(
                c for c in current["components"] if c["name"] == "Welcome Pavilion"
            )
            assert sample["kind"] == "pavilion" and sample["size"] == [8, 6, 4]
            report["chat_origin_sample"] = sample
            save()
        else:
            if not args.mechanisms_from:
                if args.scenario == "island":
                    message(
                        "Plan Castaway Coast, a 256 by 256 island with a 16 block ocean border, two bays and forest ridge. Include Beach Camp open pavilion 6 by 5 height 4, Research Station 24 by 16 with workshop, bunkroom and records room, Cave, Rocky Lookout, Beacon, Dock 24 by 5 and Wreck 28 by 9. Connect them with walking paths. Warm timber and pale fabric. Include remaining places in subsequent batches.",
                        True,
                    )
                    message(
                        "Make Beach Camp an open pavilion (kind pavilion), 8 by 7 blocks and 4 blocks high. Preserve all other places.",
                        True,
                    )
                else:
                    message(
                        "Plan Highwater, a 192 by 192 alpine river town. Include an 8 to 12 block River across a valley, slopes, a 28 by 20 Market with four stalls, 20 by 16 two-storey Inn with kitchen and upstairs rooms, 16 by 12 Mill with decorative wheel, 18 by 14 Lodge with loft, Footbridge, Road Bridge, three Terraces, orchard and connecting paths. Stone and spruce timber. Include remaining places in subsequent batches.",
                        True,
                    )
                    message(
                        "Add a third pedestrian bridge and a rotated riverside Greenhouse; retain all original buildings.",
                        True,
                    )
                    message(
                        "Add a small open Visitor Pavilion, size 6 by 5 blocks and 4 high, for a bounded component preview.",
                        True,
                    )
        message(
            "What ingredients do I need for a crafting table? Does making one require stone or another crafting table? Only answer, do not craft."
        )
        current = service.designer.snapshot()["current"]
        if args.mechanisms_from:
            # Exercise the ordinary preview editor explicitly, not a hidden model repair.
            sample = current["components"][0]
            post(
                "design_edit",
                design_revision=current["revision"],
                component=sample["name"],
                size=json.dumps([8, 7, 4]),
                kind="pavilion",
                zone="south",
                level="shore",
                turn="1",
            )
            report["manual_preview_correction"] = {
                "component": sample["name"],
                "kind": "pavilion",
                "size": [8, 7, 4],
                "turn": 1,
            }
            current = service.designer.snapshot()["current"]
        sample = next(
            (
                c
                for c in current["components"]
                if c["kind"] == "pavilion" and max(c["size"][:2]) <= 12
            ),
            None,
        )
        if not sample:
            raise RuntimeError("Provider did not design a buildable bounded pavilion")
        post(
            "design_prepare",
            design_revision=current["revision"],
            component=sample["name"],
        )
        post(
            "design_run", design_revision=current["revision"], component=sample["name"]
        )
        wait(lambda: service.project.state in ("complete", "needs_review"), 120)
        report["build"] = service.project.status()
        save()
        if service.project.state != "complete":
            raise RuntimeError("Bounded design did not complete")
        post("stop")
        wait(lambda: not service.stopping)
        report["passed_bounded_build"] = True
        if args.requirements and args.scenario == "island":
            before = service.designer.snapshot()["current"]
            post(
                "message",
                text="Make Welcome Pavilion larger inside, 10 by 8. Preserve all other places.",
                request_id=str(time.time_ns()),
                design="true",
            )
            wait(lambda: bool(service.provider.lifecycle()), 20)
            post("stop")
            wait(lambda: not service.busy and not service.stopping, 15)
            canceled = service.designer.snapshot()["current"]
            unchanged = next(
                c for c in canceled["components"] if c["name"] == "Welcome Pavilion"
            )
            assert unchanged["size"] == [8, 6, 4]
            assert canceled["planning"]["state"] == "stopped"
            assert not service.provider.lifecycle()
            report["planning_stop"] = {
                "worker_reaped": True,
                "late_design_not_applied": True,
                "requirements_retained": True,
            }
            message("Continue planning", True)
            continued = service.designer.snapshot()["current"]
            assert continued["planning"]["state"] == "ready"
            assert next(
                c for c in continued["components"] if c["name"] == "Welcome Pavilion"
            )["size"] == [10, 8, 4]
            try:
                service.project_action(
                    "design_run",
                    design_revision=before["revision"],
                    component="Welcome Pavilion",
                    session_id=service.bridge.session_id,
                )
            except ValueError:
                report["stale_build_rejected"] = True
            else:
                raise AssertionError("Stale prepared design was admitted")
        from io import BytesIO
        import base64
        from PIL import Image

        image = BytesIO()
        Image.new("RGB", (24, 24), (150, 110, 80)).save(image, format="PNG")
        payload = urlencode(
            {
                "csrf_token": server.csrf_token,
                "session_id": service.bridge.session_id,
                "name": "synthetic-palette.png",
                "caption": "Synthetic warm palette example; no owner reference supplied.",
                "image": base64.b64encode(image.getvalue()).decode(),
            }
        ).encode()
        with urllib.request.urlopen(
            urllib.request.Request(address + "/api/minecraft/reference", data=payload)
        ) as response:
            assert response.status == 200
        before = service.designer.snapshot()
        root = service.root
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
        report["reopened"] = {
            "same_design": service.designer.snapshot() == before,
            "state": service.project.state,
            "active": service.bridge.observe().get("active"),
            "requests": service.provider.lifecycle(),
        }
        assert report["reopened"] == {
            "same_design": True,
            "state": "idle",
            "active": None,
            "requests": [],
        }
        save()
        print("MECHANISMS PASSED " + address, flush=True)
        if args.hold_seconds:
            time.sleep(min(args.hold_seconds, 60))
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
