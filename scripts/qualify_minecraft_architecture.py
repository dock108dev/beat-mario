"""Qualify reviewed architecture in a copy of a recorded disposable terrain world.

This focused trial is not full inventory, exploration or owner acceptance.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import threading
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--component", default="")
    parser.add_argument("--arrange", action="store_true")
    parser.add_argument("--material", default="warm")
    parser.add_argument("--functions", action="store_true")
    parser.add_argument("--walks", action="store_true")
    parser.add_argument("--routes", action="store_true")
    parser.add_argument("--expand", action="store_true")
    parser.add_argument("--question", action="store_true")
    parser.add_argument("--resume-expansion", action="store_true")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--crossings", action="store_true")
    parser.add_argument("--refresh-paths", action="store_true")
    parser.add_argument("--preservation", action="store_true")
    parser.add_argument("--hold-seconds", type=int, default=0)
    parser.add_argument("--stop-after-write", action="store_true")
    parser.add_argument("--interrupt-after-write", action="store_true")
    parser.add_argument("--archive-diagnostics", action="store_true")
    args = parser.parse_args()
    if args.stop_after_write and args.interrupt_after_write:
        raise ValueError("Choose one recovery trial per run")
    prior = json.loads((args.source / "report.json").read_text())
    if prior.get(
        "scope"
    ) != "Source app, actual provider, new disposable world" or not prior.get(
        "shutdown"
    ):
        raise ValueError("Source must be a shut-down recorded disposable world")
    args.root.mkdir(parents=True, exist_ok=False)
    for name in ("profile", "world"):
        shutil.copytree(args.source / name, args.root / name)
    if args.archive_diagnostics:
        archive = args.root / "retained-diagnostics"
        archive.mkdir()
        for name in ("events.jsonl", "worker-events.jsonl"):
            old = args.root / "profile" / "artifacts" / "minecraft-chat" / name
            if old.exists():
                old.rename(archive / name)
    os.environ["GAME_COMPANION_USER_DATA"] = str(args.root / "profile")
    from smb3_agent import lab_ui
    from smb3_agent.minecraft_practice import PracticeServer

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = lab_ui._new_lab_ui_server("127.0.0.1", 0)
    service = server.minecraft_chat
    service.practice_factory = lambda: PracticeServer(args.root / "world", port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {
        "scope": "Source app, actual provider, new disposable world",
        "qualification": "selected architecture only",
        "component": args.component,
        "source": str(args.source),
    }

    def save():
        (args.root / "report.json").write_text(json.dumps(report, indent=2))

    def post(action, **values):
        body = urlencode(
            {
                "csrf_token": server.csrf_token,
                "action": action,
                "session_id": service.bridge.session_id if service.bridge else "",
                **values,
            }
        ).encode()
        from urllib.error import HTTPError

        try:
            with urlopen(
                Request(
                    f"http://127.0.0.1:{server.server_port}/api/minecraft/chat",
                    data=body,
                ),
                timeout=60,
            ) as response:
                return json.load(response)
        except HTTPError as exc:
            report.setdefault("http_errors", []).append(
                {"action": action, "status": exc.code, "body": exc.read().decode()}
            )
            save()
            raise

    def wait(predicate, timeout=120):
        end = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > end:
                raise TimeoutError("Architecture qualification wait expired")
            time.sleep(0.1)

    try:
        post("connect")
        wait(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        report["idle_reopening"] = {
            "state": service.project.state,
            "active": service.project.staged_active,
            "automatic_resume": service.project.status()["automatic_resume"],
        }
        # A selected review is not the inventory of all built places. Recover
        # the latest completed binding for each place before preservation checks.
        retained_components = {}
        for (body,) in service.project.db.execute(
            "SELECT body FROM architecture_reviews ORDER BY id"
        ):
            for component in json.loads(body)["components"]:
                if service.project.db.execute(
                    "SELECT 1 FROM architecture_stages WHERE component=? AND digest=? AND completed=1",
                    (component["name"], component["digest"]),
                ).fetchone():
                    retained_components[component["name"]] = component
        original_manifest = (
            {"components": list(retained_components.values())}
            if retained_components
            else service.project.architecture_manifest()[1]
        )
        revision = service.designer.current()["revision"]
        if args.expand or args.question or args.native:
            report["startup_provider_status"] = dict(service.provider.status)
            post("check_setup")
            wait(lambda: service.provider.status.get("state") != "checking", 30)
            report["checked_provider_status"] = dict(service.provider.status)
            save()
            if not service.provider.status.get("available"):
                raise ValueError(service.provider.status["message"])
        if args.expand:
            original_design = service.designer.current()
            post(
                "message",
                request_id="architecture-expansion",
                design="true",
                text="Add a third pedestrian bridge 16 by 3, 2 blocks high and a rotated riverside Greenhouse 12 by 10, 6 blocks high; preserve all original buildings.",
            )
            wait(lambda: not service.busy, 650)
            expanded = service.designer.current()
            report["expansion_design"] = expanded
            report["expansion_messages"] = service.messages[-6:]
            save()
            if service.error:
                raise ValueError(service.error)
            originals = {c["name"]: c for c in original_design["components"]}
            added = {c["name"]: c for c in expanded["components"]}
            assert all(
                added[name] == component for name, component in originals.items()
            ), "Original design changed"
            bridges = [c for c in added.values() if c["kind"] == "bridge"]
            assert len(bridges) == 3
            bridge = next(c for c in bridges if c["name"] not in originals)
            greenhouse = next(
                c
                for c in added.values()
                if c["name"] not in originals and c["kind"] == "building"
            )
            assert greenhouse["turn"] == 1 and greenhouse["size"] == [12, 10, 6]
            river = added[bridge["link"]]
            rx, rz, rw, rd, *_ = river["box"]
            bx, bz, bw, bd, *_ = bridge["box"]
            assert bx < rx and bx + bw > rx + rw and rz <= bz and bz + bd <= rz + rd, (
                "Bridge does not span waterway"
            )
            gx, gz, gw, gd, *_ = greenhouse["box"]
            assert not (
                gx < rx + rw and gx + gw > rx and gz < rz + rd and gz + gd > rz
            ), "Riverside building is in water"
            report["expansion_geometry_and_original_design_preserved"] = True
            revision = expanded["revision"]
            post(
                "architecture_review",
                design_revision=revision,
                component=greenhouse["name"],
                material=args.material,
            )
            report["expansion_dependency_review"] = (
                service.project.architecture_status()
            )
            assert report["expansion_dependency_review"]["dependencies"], (
                "New footprint must require terrain"
            )
            save()
            post("terrain_review", design_revision=revision)
            report["expansion_terrain_review"] = service.project.terrain_status()
            save()
            post("terrain_run", design_revision=revision)
            wait(lambda: not service.project.terrain_active, 7300)
            report["expansion_terrain_result"] = service.project.status()
            save()
            if service.project.state != "complete":
                raise ValueError(service.project.error)
        if args.native:
            before = service.designer.current()
            chosen = next(
                c for c in before["components"] if c["name"] == args.component
            )
            post(
                "message",
                request_id="rotated-native-inventory",
                design="true",
                text=args.component
                + ": Native: doors, chests, crafting table, lamps. Keep its current dimensions, rotation and location.",
            )
            wait(lambda: not service.busy, 650)
            current = service.designer.current()
            report["native_chat_design"] = current
            report["native_chat_messages"] = service.messages[-4:]
            save()
            if service.error:
                raise ValueError(service.error)
            updated = next(
                c for c in current["components"] if c["name"] == args.component
            )
            assert (
                updated["box"] == chosen["box"] and updated["turn"] == chosen["turn"]
            ), "Native addition moved the place"
            assert all(
                c == next(n for n in current["components"] if n["name"] == c["name"])
                for c in before["components"]
                if c["name"] != args.component
            )
            revision = current["revision"]
            post("terrain_review", design_revision=revision)
            post("terrain_run", design_revision=revision)
            wait(lambda: not service.project.terrain_active, 7300)
            report["native_terrain_result"] = service.project.status()
            save()
            if service.project.state != "complete":
                raise ValueError(service.project.error)
        if args.resume_expansion:
            assert prior.get("expansion_geometry_and_original_design_preserved"), (
                "Resume only a validated ordinary-chat expansion"
            )
            assert service.designer.current() == prior["expansion_design"], (
                "Saved expansion changed"
            )
            terrain = service.project.terrain_manifest()
            pending = [
                c
                for c in service.designer.current()["components"]
                if c["kind"] == "building" and c["name"] not in terrain["reservations"]
            ]
            assert len(pending) == 1
            post(
                "architecture_review",
                design_revision=revision,
                component=pending[0]["name"],
                material=args.material,
            )
            report["expansion_dependency_review"] = (
                service.project.architecture_status()
            )
            assert report["expansion_dependency_review"]["dependencies"]
            save()
            post("terrain_review", design_revision=revision)
            report["expansion_terrain_review"] = service.project.terrain_status()
            save()
            post("terrain_run", design_revision=revision)
            wait(lambda: not service.project.terrain_active, 7300)
            report["expansion_terrain_result"] = service.project.status()
            save()
            if service.project.state != "complete":
                raise ValueError(service.project.error)
        if args.refresh_paths:
            post("terrain_refresh", design_revision=revision)
            revision = service.designer.current()["revision"]
            report["refreshed_paths_review"] = service.project.terrain_status()
            save()
            post("terrain_run", design_revision=revision)
            wait(lambda: not service.project.terrain_active, 7300)
            report["refreshed_paths_result"] = service.project.status()
            save()
            if service.project.state != "complete":
                raise ValueError(service.project.error)
        if args.arrange:
            post("architecture_arrange", design_revision=revision)
            revision = service.designer.current()["revision"]
            report["layout"] = service.designer.current()
            save()
            post("terrain_review", design_revision=revision)
            report["terrain_review"] = service.project.terrain_status()
            save()
            post("terrain_run", design_revision=revision)
            wait(lambda: not service.project.terrain_active, 7300)
            report["terrain_result"] = service.project.status()
            save()
            if service.project.state != "complete":
                raise ValueError(service.project.error)
        if args.preservation:
            from urllib.error import HTTPError

            try:
                post(
                    "architecture_review",
                    design_revision=revision - 1,
                    component=args.component,
                    material=args.material,
                )
                raise AssertionError("Stale review was admitted")
            except HTTPError as exc:
                assert exc.code == 409, exc.code
                report["stale_review_rejected"] = exc.code
            old_component = next(
                c
                for c in original_manifest["components"]
                if c["name"] == args.component
            )
            chest = next(
                o["position"] for o in old_component["objects"] if o["type"] == "chests"
            )
            terrain = service.project.terrain_manifest()
            service.bridge.call(
                "select_build_region",
                {"region": terrain["region"]},
                session_id=service.bridge.session_id,
                revision=service.bridge.revision,
            )
            service.bridge.build_console.region = service.project.region = terrain[
                "region"
            ]
            service.bridge.call(
                "execute",
                {
                    "action": "build_focus",
                    "position": {
                        **chest,
                        "y": terrain["region"]["bounds"]["max"]["y"] + 8,
                    },
                },
                session_id=service.bridge.session_id,
                revision=service.bridge.revision,
                timeout_ms=10000,
            )
            service.practice.command(
                f"tp CompanionBot {chest['x'] + 0.5} {chest['y']} {chest['z'] - 0.5}"
            )
            wait(
                lambda: (
                    abs(service.bridge.observe()["position"]["y"] - chest["y"]) < 0.75
                ),
                10,
            )
            service.practice.command(
                f"item replace block {chest['x']} {chest['y']} {chest['z']} container.0 with minecraft:diamond 3"
            )
            service.practice.command("give CompanionBot oak_planks 2")
            before = service.bridge.call(
                "execute",
                {"action": "build_probe", "target": chest},
                session_id=service.bridge.session_id,
                revision=service.bridge.revision,
                timeout_ms=10000,
            )
            assert any(
                i["name"] == "diamond" and i["count"] == 3
                for i in before["preserved_contents"]
            ), before
            report["container_before_revision"] = before
            report["seeded_container"] = chest
        start = time.monotonic()
        post(
            "architecture_review",
            design_revision=revision,
            component=args.component,
            material=args.material,
        )
        report["review_seconds"] = time.monotonic() - start
        report["review"] = service.project.architecture_status()
        save()
        print(json.dumps({"review": report["review"]}), flush=True)
        if report["review"]["unsupported"] or report["review"]["dependencies"]:
            raise ValueError("Architecture review has unresolved dependencies")
        initial_units = service.project.db.execute(
            "SELECT COUNT(*) FROM units"
        ).fetchone()[0]
        ordinary_run = service.project.run
        if args.interrupt_after_write:

            def interrupt(point, uid):
                if point == "write":
                    raise RuntimeError(
                        "Qualification interruption after server write before receipt"
                    )

            service.project.run = lambda **kw: ordinary_run(fault=interrupt, **kw)
        post(
            "architecture_run",
            design_revision=revision,
            architecture_review=report["review"]["review"],
        )
        if args.question:
            wait(
                lambda: (
                    service.project.db.execute("SELECT COUNT(*) FROM units").fetchone()[
                        0
                    ]
                    > initial_units
                ),
                30,
            )
            question_started = time.monotonic()
            authority = service.authority()
            count_before = service.project.db.execute(
                "SELECT COUNT(*) FROM units WHERE status='verified'"
            ).fetchone()[0]
            active_before = service.project.architecture_active
            post(
                "message",
                request_id="architecture-question-" + args.root.name,
                text="While you keep building, briefly explain: does Stop pause the Minecraft world?",
            )
            wait(lambda: not service.busy, 250)
            report["concurrent_question"] = {
                "seconds": time.monotonic() - question_started,
                "active_at_submission": active_before,
                "active_at_reply": service.project.architecture_active,
                "authority_before": authority,
                "authority_after": service.authority(),
                "verified_units_during_answer": service.project.db.execute(
                    "SELECT COUNT(*) FROM units WHERE status='verified'"
                ).fetchone()[0]
                - count_before,
                "messages": service.messages[-2:],
                "error": service.error,
                "usage": service.provider.usage[-1:],
            }
            save()
            question = report["concurrent_question"]
            assert not question["error"], question["error"]
            assert question["active_at_submission"], (
                "Question was not submitted during architecture"
            )
            assert question["authority_before"] == question["authority_after"], (
                "Question changed gameplay authority"
            )
            assert question["verified_units_during_answer"] > 0, (
                "No verified work overlapped the answer"
            )
            assert (
                question["messages"][-1]["role"] == "assistant"
                and question["messages"][-1]["text"].strip()
            ), "No actual answer received"
            report["concurrent_question_passed"] = True
            save()
        if args.stop_after_write:
            wait(
                lambda: (
                    service.project.db.execute("SELECT COUNT(*) FROM units").fetchone()[
                        0
                    ]
                    > initial_units
                ),
                30,
            )
            began = time.monotonic()
            post("stop")
            wait(
                lambda: (
                    not service.project.architecture_active and not service.stopping
                ),
                30,
            )
            report["stop"] = {
                "seconds": time.monotonic() - began,
                "state": service.project.state,
                "error": service.project.error,
            }
            save()
            post(
                "architecture_run",
                design_revision=revision,
                architecture_review=report["review"]["review"],
            )
        wait(lambda: not service.project.architecture_active, 7300)
        if args.interrupt_after_write:
            report["interruption"] = {
                "state": service.project.state,
                "error": service.project.error,
                "pending": service.project.db.execute(
                    "SELECT COUNT(*) FROM units WHERE status='pending'"
                ).fetchone()[0],
            }
            save()
            service.project.run = ordinary_run
            post(
                "architecture_run",
                design_revision=revision,
                architecture_review=report["review"]["review"],
            )
            wait(lambda: not service.project.architecture_active, 7300)
        report["result"] = service.project.status()
        report["passed_selected_build"] = service.project.state == "complete"
        save()
        print(
            json.dumps(
                {
                    "state": service.project.state,
                    "error": service.project.error,
                    "progress": service.project.architecture_progress,
                }
            ),
            flush=True,
        )
        if not report["passed_selected_build"]:
            raise ValueError(service.project.error)
        report["unaffected_components_verified"] = []
        if original_manifest and (
            args.component or args.expand or args.resume_expansion
        ):
            terrain = service.project.terrain_manifest()
            for other in original_manifest["components"]:
                if other["name"] == args.component:
                    continue
                x, z, w, d, _, _ = other["box"]
                service.bridge.call(
                    "execute",
                    {
                        "action": "build_focus",
                        "position": {
                            "x": terrain["origin"][0] + x + w // 2,
                            "y": terrain["region"]["bounds"]["max"]["y"] + 8,
                            "z": terrain["origin"][1] + z + d // 2,
                        },
                    },
                    session_id=service.bridge.session_id,
                    revision=service.bridge.revision,
                    timeout_ms=10000,
                )
                for offset in range(0, len(other["cells"]), 256):
                    cells = other["cells"][offset : offset + 256]
                    observed = service.project.inspect([c["position"] for c in cells])
                    if any(c["after"] != a["state"] for c, a in zip(cells, observed)):
                        raise ValueError(
                            "Unselected architecture changed: " + other["name"]
                        )
                report["unaffected_components_verified"].append(other["name"])
                save()
        components = service.project.architecture_status()["components"]

        def execute(action, **values):
            return service.bridge.call(
                "execute",
                {"action": action, **values},
                session_id=service.bridge.session_id,
                revision=service.bridge.revision,
                timeout_ms=30000,
            )

        def position(target):
            service.practice.command(
                f"tp CompanionBot {target['x'] + 0.5} {target['y']} {target['z'] + 0.5}"
            )
            wait(
                lambda: all(
                    abs(
                        service.bridge.observe()["position"][k]
                        - (v + (0.5 if k != "y" else 0))
                    )
                    < 0.75
                    for k, v in target.items()
                ),
                10,
            )

        for component in components:
            if component.get("retired"):
                continue
            terrain = service.project.terrain_manifest()
            x, z, w, d, _, _ = component["box"]
            execute(
                "build_focus",
                position={
                    "x": terrain["origin"][0] + x + w // 2,
                    "y": terrain["region"]["bounds"]["max"]["y"] + 8,
                    "z": terrain["origin"][1] + z + d // 2,
                },
            )
            if args.functions:
                report.setdefault("functions", [])
                service.practice.command("give CompanionBot oak_planks 32")
                service.practice.command("give CompanionBot potato 1")
                service.practice.command("time set midnight")
                service.practice.command("gamerule playersSleepingPercentage 101")
                native_items = []
                for item in component["objects"]:
                    if item["capability"].startswith("native"):
                        native_items.extend(item.get("parts", [item]))
                for item in native_items:
                    target = dict(item["position"])
                    if item["type"] == "lamppost":
                        target["y"] += 3
                    position({**target, "z": target["z"] - 1})
                    result = execute("build_probe", target=target)
                    report["functions"].append(
                        {
                            "place": component["name"],
                            "type": item["type"],
                            "result": result,
                        }
                    )
                    save()
                    print(json.dumps(report["functions"][-1]), flush=True)
            if args.walks:
                report.setdefault("walks", [])
                door = next(
                    (o for o in component["objects"] if o["type"] == "doors"), None
                )
                if door:
                    target = door["position"]
                    # Compiler records the actual rotated exterior approach.
                    position(component["walks"][0])
                    execute("build_probe", target=target, keep_open=True)
                elif component["walks"]:
                    position(component["walks"][0])
                for target in component["walks"]:
                    result = execute(
                        "move",
                        target={
                            k: v + (0.5 if k != "y" else 0) for k, v in target.items()
                        },
                    )
                    report["walks"].append(
                        {"place": component["name"], "target": target, "result": result}
                    )
                    save()
                    print(json.dumps(report["walks"][-1]), flush=True)
                if door:
                    execute("build_probe", target=door["position"], keep_closed=True)
        if args.preservation:
            chest = report["seeded_container"]
            position({**chest, "z": chest["z"] - 1})
            service.practice.command("give CompanionBot oak_planks 2")
            contents = execute("build_probe", target=chest)
            assert any(
                i["name"] == "diamond" and i["count"] == 3
                for i in contents["preserved_contents"]
            ), contents
            report["container_after_revision"] = contents
            _, manifest = service.project.architecture_manifest()
            component = next(
                c for c in manifest["components"] if c["name"] == args.component
            )
            marker = next(
                c["position"]
                for c in component["cells"]
                if c["after"] in ("oak_planks", "spruce_planks", "stone_bricks")
            )
            service.practice.command(
                f"setblock {marker['x']} {marker['y']} {marker['z']} glass"
            )
            wait(lambda: service.project.inspect([marker])[0]["state"] == "glass", 10)
            post(
                "architecture_review",
                design_revision=revision,
                component=args.component,
                material="warm" if args.material != "warm" else "industrial",
            )
            refused = service.project.architecture_status()
            post(
                "architecture_run",
                design_revision=revision,
                architecture_review=refused["review"],
            )
            wait(lambda: not service.project.architecture_active, 120)
            assert service.project.state == "needs_review", service.project.state
            assert service.project.inspect([marker])[0]["state"] == "glass"
            report["player_edit_preserved"] = {
                "position": marker,
                "error": service.project.error,
            }
            save()
        if args.routes:
            terrain = service.project.terrain_manifest()
            ox, oz = terrain["origin"]
            elevations = {(x, z): y for x, z, y in terrain["field"]["paths"]}
            buildings = [
                c["box"]
                for c in components
                if c["kind"] in ("building", "pavilion", "tower", "wreck")
            ]
            report["routes"] = []
            for route in terrain["routes"]:
                points = [
                    p
                    for p in route["points"]
                    if not any(
                        x <= p[0] < x + w and z <= p[1] < z + d
                        for x, z, w, d, *_ in buildings
                    )
                ]
                if len(points) < 2:
                    continue

                def target(p):
                    return {
                        "x": ox + p[0],
                        "y": terrain["sea_level"] + elevations[tuple(p)] + 1,
                        "z": oz + p[1],
                    }

                execute(
                    "build_focus",
                    position={
                        "x": ox + points[0][0],
                        "y": terrain["region"]["bounds"]["max"]["y"] + 8,
                        "z": oz + points[0][1],
                    },
                )
                position(target(points[0]))
                entry = {
                    "from": route["from"],
                    "to": route["to"],
                    "scope": "outdoor route between reserved footprints",
                    "segments": [],
                }
                report["routes"].append(entry)
                for point in points[12::12] + [points[-1]]:
                    t = target(point)
                    result = execute(
                        "move",
                        target={k: v + (0.5 if k != "y" else 0) for k, v in t.items()},
                    )
                    entry["segments"].append({"target": t, "result": result})
                    save()
                print("ROUTE", route["from"], route["to"], flush=True)
            for cave in terrain["field"]["caves"]:
                x, z = cave["entrance"]
                t = {
                    "x": ox + x,
                    "y": terrain["sea_level"] + cave["floor"] + 1,
                    "z": oz + z,
                }
                execute(
                    "build_focus",
                    position={**t, "y": terrain["region"]["bounds"]["max"]["y"] + 8},
                )
                position(t)
                t["z"] += min(20, cave["passage"])
                report["cave_walk"] = execute(
                    "move",
                    target={k: v + (0.5 if k != "y" else 0) for k, v in t.items()},
                )
                save()
        if args.crossings:
            terrain = service.project.terrain_manifest()
            ox, oz = terrain["origin"]
            elevations = {(x, z): y for x, z, y in terrain["field"]["paths"]}
            report["crossings"] = []
            for c in service.designer.current()["components"]:
                if c["kind"] != "bridge":
                    continue
                site = terrain["reservations"][c["name"]]
                x, z, w, d = site["box"]
                execute(
                    "build_focus",
                    position={
                        "x": ox + x + w // 2,
                        "y": terrain["region"]["bounds"]["max"]["y"] + 8,
                        "z": oz + z + d // 2,
                    },
                )
                deck = [
                    {
                        "x": ox + xx,
                        "y": terrain["sea_level"] + site["level"],
                        "z": oz + zz,
                    }
                    for xx in range(x, x + w)
                    for zz in range(z, z + d)
                ]
                actual = service.project.inspect(deck)
                assert all(
                    v["state"] in ("oak_planks", "stone_bricks") for v in actual
                ), "Incomplete bridge deck"
                a, b = (
                    ((x - 1, z + d // 2), (x + w, z + d // 2))
                    if w > d
                    else ((x + w // 2, z - 1), (x + w // 2, z + d))
                )

                def bank(p):
                    return {
                        "x": ox + p[0],
                        "y": terrain["sea_level"]
                        + elevations.get(p, terrain["field"]["height"][p[1]][p[0]])
                        + 1,
                        "z": oz + p[1],
                    }

                position(bank(a))
                result = execute(
                    "move",
                    target={
                        k: v + (0.5 if k != "y" else 0) for k, v in bank(b).items()
                    },
                )
                report["crossings"].append(
                    {
                        "name": c["name"],
                        "deck_cells": len(deck),
                        "width": min(w, d),
                        "result": result,
                    }
                )
                save()
        if args.hold_seconds:
            print("VIEW " + str(service.snapshot().get("viewer_url")), flush=True)
            end = time.monotonic() + args.hold_seconds
            while time.monotonic() < end:
                time.sleep(0.5)
    except KeyboardInterrupt:
        report["failure"] = "Qualification interrupted; not accepted"
    except Exception as exc:
        report["failure"] = str(exc)
        print(str(exc), flush=True)
    finally:
        service.close()
        server.ai_provider.close()
        server.shutdown()
        server.server_close()
        import resource

        report["max_child_rss_bytes"] = resource.getrusage(
            resource.RUSAGE_CHILDREN
        ).ru_maxrss
        report["shutdown"] = True
        save()
        print(str(args.root / "report.json"), flush=True)


if __name__ == "__main__":
    main()
