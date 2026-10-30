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
    parser.add_argument("--refresh-terrain", action="store_true")
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

    if not args.mechanisms_from:
        raise ValueError(
            "Follow-up requires an explicitly recorded disposable terrain world"
        )
    try:
        post("connect")
        wait(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        if args.refresh_terrain:
            brief = json.loads(Path("data/minecraft/design-briefs.json").read_text())[
                args.scenario
            ]["brief"]
            message(brief, True)
            revision = service.designer.current()["revision"]
            post("terrain_review", design_revision=revision)
            post("terrain_run", design_revision=revision)
            wait(lambda: not service.project.terrain_active, 7500)
            report["refreshed_terrain"] = service.project.status()
            save()
            assert service.project.state == "complete", service.project.error
        manifest = service.project.terrain_manifest()
        if not manifest:
            raise ValueError("No reviewed terrain")
        from smb3_agent.minecraft_terrain import SEA, FLOOR

        service.bridge.call(
            "select_build_region",
            {"region": manifest["region"]},
            session_id=service.bridge.session_id,
            revision=service.bridge.revision,
        )
        service.bridge.build_console.region = service.project.region = manifest[
            "region"
        ]
        ox, oz = manifest["origin"]
        n = manifest["extent"]
        report["surveys"] = []
        report["walks"] = []

        def focus(x, z):
            tile = manifest["tile_size"]
            x = min(n - tile // 2, max(tile // 2, (x // tile) * tile + tile // 2))
            z = min(n - tile // 2, max(tile // 2, (z // tile) * tile + tile // 2))
            service.bridge.call(
                "execute",
                {
                    "action": "build_focus",
                    "position": dict(
                        x=ox + x,
                        y=manifest["region"]["bounds"]["max"]["y"] + 8,
                        z=oz + z,
                    ),
                },
                session_id=service.bridge.session_id,
                revision=service.bridge.revision,
                timeout_ms=10000,
            )

        def survey(label, points, expected):
            focus(points[0]["x"] - ox, points[0]["z"] - oz)
            actual = service.project.inspect(points)
            assert [a["state"].split("[")[0] for a in actual] == expected, (
                label,
                actual,
                expected,
            )
            report["surveys"].append({"label": label, "actual": actual})
            save()

        path_elevations = {(x, z): y for x, z, y in manifest["field"]["paths"]}
        for peak in manifest["peaks"]:
            x, z = peak["position"]
            survey(
                peak["name"] + " elevation",
                [dict(x=ox + x, y=SEA + peak["height"], z=oz + z)],
                [
                    "stone_bricks"
                    if path_elevations.get((x, z)) == peak["height"]
                    else "grass_block"
                ],
            )
        for cave in manifest["field"]["caves"]:
            x, z = cave["entrance"]
            y = SEA + cave["floor"]
            survey(
                "Cave entrance clearance",
                [dict(x=ox + x, y=y + i, z=oz + z) for i in (0, 1, 2)],
                ["stone_bricks", "air", "air"],
            )
            endz = z + cave["passage"] + cave["chamber"][1] - 1
            survey(
                "Cave chamber clearance",
                [dict(x=ox + x, y=y + i, z=oz + endz) for i in (0, 1, 2)],
                ["stone_bricks", "air", "air"],
            )
        for group in manifest["woodland_groups"]:
            x, z = group["center"]
            y = SEA + manifest["field"]["height"][z][x] + 1
            survey(
                "Woodland " + str(group["group"]),
                [dict(x=ox + x, y=y, z=oz + z)],
                ["oak_log"],
            )
        design_components = service.designer.current()["components"]
        if args.scenario == "island":
            cove = next(
                c
                for c in design_components
                if c["kind"] == "water"
                and "depth"
                in next(
                    r["details"].lower()
                    for r in service.designer.current()["requirements"]
                    if r["name"] == c["name"]
                )
            )
            x, z, w, d, level, _ = cove["box"]
            x += w // 2
            z += d // 2
            assert -8 <= level <= -4
            survey(
                "Cove measured depth",
                [dict(x=ox + x, y=SEA + dy, z=oz + z) for dy in range(level, 1)],
                ["stone"] + ["water"] * (-level),
            )
            report["cove_depth_blocks"] = -level
            candidates = []
            path_set = {(x, z) for x, z, _ in manifest["field"]["paths"]}
            for x in range(16, n - 16):
                for z in range(n // 2, n - 8):
                    run = [(x, z - i) for i in range(6)]
                    if (
                        manifest["field"]["water"][z + 1][x]
                        and all(
                            manifest["field"]["sand"][zz][xx]
                            and (xx, zz) not in path_set
                            for xx, zz in run
                        )
                        and not manifest["field"]["sand"][z - 6][x]
                    ):
                        candidates.append(run)
            assert candidates, "No six-block southern beach section"
            beach = candidates[len(candidates) // 2]
            grouped = [
                dict(x=ox + x, y=SEA + manifest["field"]["height"][z][x], z=oz + z)
                for x, z in beach
            ]
            survey("Six-block beach surface", grouped, ["sand"] * 6)
            report["beach_depth_blocks"] = 6
            for name, site in manifest["reservations"].items():
                if site["level"] == 28:
                    x, z, w, d = site["box"]
                    survey(
                        "Raised lookout elevation",
                        [dict(x=ox + x + w // 2, y=SEA + 28, z=oz + z + d // 2)],
                        [
                            "stone_bricks"
                            if (x + w // 2, z + d // 2) in path_set
                            else "grass_block"
                        ],
                    )
        else:
            terrace = next(
                c
                for c in design_components
                if c.get("constraints", {}).get("count") == 3 and c["kind"] == "terrain"
            )
            x0, z0, w, d, _, height = terrace["box"]
            path_set = {(x, z) for x, z, _ in manifest["field"]["paths"]}
            report["terrace_levels"] = []
            for step in range(1, 4):
                level = height * step // 3
                spots = [
                    (x, z)
                    for z in range(z0, z0 + d)
                    for x in range(x0, x0 + w)
                    if manifest["field"]["height"][z][x] == level
                    and not manifest["field"]["water"][z][x]
                    and (x, z) not in path_set
                ]
                assert spots
                x, z = spots[len(spots) // 2]
                survey(
                    "Terrace elevation " + str(level),
                    [dict(x=ox + x, y=SEA + level, z=oz + z)],
                    ["grass_block"],
                )
                report["terrace_levels"].append(level)

        # Boundary and former preview protection columns are outside terrain write authority.
        for x, z in ((0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1)):
            survey("Boundary containment", [dict(x=ox + x, y=SEA, z=oz + z)], ["stone"])

        # Independent physical checks at seams, every route centreline, and the no-write ring.
        def grouped_survey(label, pairs):
            groups = {}
            for point, expected in pairs:
                key = ((point["x"] - ox) // 64, (point["z"] - oz) // 64)
                groups.setdefault(key, []).append((point, expected))
            for group in groups.values():
                for offset in range(0, len(group), 256):
                    part = group[offset : offset + 256]
                    survey(label, [p for p, _ in part], [e for _, e in part])

        paths = {(x, z): y for x, z, y in manifest["field"]["paths"]}
        route_points = {tuple(p) for r in manifest["routes"] for p in r["points"]}
        grouped_survey(
            "Connected route clearance",
            [
                (dict(x=ox + x, y=SEA + paths[x, z] + dy, z=oz + z), "air")
                for x, z in route_points
                for dy in (1, 2)
            ],
        )
        grouped_survey(
            "No-write buffer",
            [
                (dict(x=ox + x, y=y, z=oz + z), "air")
                for i in range(0, n, 8)
                for x, z in ((-1, i), (n, i), (i, -1), (i, n))
                for y in (FLOOR, SEA)
            ],
        )
        grouped_survey(
            "Adjacent stage floor seams",
            [
                (dict(x=ox + x, y=FLOOR, z=oz + z), "stone")
                for seam in range(64, n, 64)
                for i in range(0, n, 8)
                for x, z in ((seam - 1, i), (seam, i), (i, seam - 1), (i, seam))
            ],
        )
        if args.scenario == "town":
            component = next(
                c
                for c in service.designer.current()["components"]
                if c["kind"] == "water"
            )
            rx, rz, rw, rd, _, _ = component["box"]
            assert 8 <= rw <= 12
            line = rz + rd // 3
            grouped_survey(
                "River actual width and banks",
                [
                    (dict(x=ox + x, y=SEA, z=oz + line), "water")
                    for x in range(rx, rx + rw)
                ],
            )
            report["river_width_blocks"] = rw
            for c in design_components:
                if c["kind"] == "bridge":
                    x0, z0, w, d, level, _ = c["box"]
                    grouped_survey(
                        c["name"] + " full deck width",
                        [
                            (
                                dict(x=ox + x, y=SEA + max(1, level), z=oz + z),
                                "oak_planks"
                                if manifest["field"]["water"][z][x]
                                else "stone_bricks",
                            )
                            for z in range(z0, z0 + d)
                            for x in range(x0, x0 + w)
                        ],
                    )

        else:
            grouped_survey(
                "Sixteen-block ocean border",
                [
                    (dict(x=ox + x, y=SEA, z=oz + z), "water")
                    for i in range(1, n - 1, 8)
                    for j in (1, 8, 15)
                    for x, z in ((j, i), (n - 1 - j, i), (i, j), (i, n - 1 - j))
                ],
            )
            for cave in manifest["field"]["caves"]:
                grouped_survey(
                    "Full cave floor and headroom",
                    [
                        (
                            dict(x=ox + x, y=SEA + cave["floor"] + dy, z=oz + z),
                            "stone_bricks" if dy == 0 else "air",
                        )
                        for x, z in cave["cells"]
                        for dy in (0, 1, 2)
                    ],
                )

        routes = manifest["routes"][:4]
        walks = []
        for route in routes:
            points = route["points"]
            start = points[0]
            end = points[min(12, len(points) - 1)]
            walks.append(
                (
                    route["from"] + " to " + route["to"],
                    start,
                    end,
                    paths[tuple(start)],
                    paths[tuple(end)],
                )
            )
        for cave in manifest["field"]["caves"]:
            x, z = cave["entrance"]
            walks.append(
                (
                    "Cave passage",
                    [x, z],
                    [x, z + min(20, cave["passage"])],
                    cave["floor"],
                    cave["floor"],
                )
            )
        for label, start, end, sy, ey in walks:
            focus(*start)
            service.practice.command(
                f"tp CompanionBot {ox + start[0] + 0.5} {SEA + sy + 1} {oz + start[1] + 0.5}"
            )
            expected_start = dict(
                x=ox + start[0] + 0.5, y=SEA + sy + 1, z=oz + start[1] + 0.5
            )
            wait(
                lambda: all(
                    abs(service.bridge.observe()["position"][k] - v) < 0.75
                    for k, v in expected_start.items()
                ),
                10,
            )
            target = dict(x=ox + end[0] + 0.5, y=SEA + ey + 1, z=oz + end[1] + 0.5)
            result = service.bridge.call(
                "execute",
                {"action": "move", "target": target},
                session_id=service.bridge.session_id,
                revision=service.bridge.revision,
                timeout_ms=30000,
            )
            assert result["observed"] == "position", result
            report["walks"].append({"label": label, "target": target, "result": result})
            save()
            print("WALK", label, flush=True)
        report["survey_passed"] = True
        save()
        # Read-only browser inspection checkpoints; placement remains headless.
        if args.hold_seconds:
            scenes = [(peak["name"], peak["position"]) for peak in manifest["peaks"]]
            scenes += [
                (c["name"] + " entrance", c["entrance"])
                for c in manifest["field"]["caves"]
            ]
            scenes += [("Water and route connections", [n // 2, n // 2])]
            for index, (label, point) in enumerate(scenes):
                focus(*point)
                report["render_checkpoint"] = {
                    "index": index,
                    "label": label,
                    "position": point,
                    "address": address,
                }
                save()
                print("RENDER CHECKPOINT", report["render_checkpoint"], flush=True)
                end = time.monotonic() + min(args.hold_seconds, 60)
                advance = args.root / f"render-{index}.done"
                while time.monotonic() < end and not advance.exists():
                    time.sleep(0.2)
        marker = dict(x=ox - 12, y=FLOOR, z=12)
        focus(0, 0)
        service.practice.command(
            f"setblock {marker['x']} {marker['y']} {marker['z']} gold_block"
        )
        wait(lambda: service.project.inspect([marker])[0]["state"] == "gold_block", 5)
        report["protected_marker_before"] = service.project.inspect([marker])

        message(
            "What ingredients do I need for a crafting table? Only answer, do not craft."
        )
        old_revision = service.designer.current()["revision"]
        change = (
            "Ridge: terrain 64 by 48, 34 blocks high, north.\nWest Bay: water 36 by 24, 4 blocks high, elevation -4, west."
            if args.scenario == "island"
            else "West Slope: terrain 64 by 48, 26 blocks high, west."
        )
        message(change, True)
        revision = service.designer.current()["revision"]
        try:
            service.project_action(
                "terrain_run",
                design_revision=old_revision,
                session_id=service.bridge.session_id,
            )
        except ValueError:
            report["stale_revision_rejected"] = True
        else:
            raise AssertionError("Stale terrain run admitted")
        post("terrain_review", design_revision=revision)
        rows = service.project.db.execute(
            "SELECT COUNT(*) FROM terrain_stages WHERE manifest=? AND completed=1",
            (revision,),
        ).fetchone()[0]
        report["retained_stages"] = rows
        assert rows > 0
        post("terrain_run", design_revision=revision)
        last = 0
        while service.project.terrain_active:
            if time.monotonic() - last > 20:
                print(
                    "REVISION", service.project.terrain_status()["progress"], flush=True
                )
                last = time.monotonic()
                save()
            time.sleep(0.2)
        report["revision_result"] = service.project.status()
        save()
        assert service.project.state == "complete", service.project.error
        focus(0, 0)
        assert service.project.inspect([marker]) == report["protected_marker_before"]
        report["protected_marker_preserved"] = True
        manifest = service.project.terrain_manifest()
        # Inject a player edit into a known, already verified cell; replay must refuse it.
        focus(2, 2)
        pos = dict(x=ox + 2, y=FLOOR, z=oz + 2)
        service.practice.command(f"setblock {pos['x']} {pos['y']} {pos['z']} glass")
        wait(lambda: service.project.inspect([pos])[0]["state"] == "glass", 5)
        before = service.project.db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        post("terrain_run", design_revision=revision)
        wait(lambda: not service.project.terrain_active, 120)
        assert service.project.state == "needs_review"
        assert service.project.inspect([pos])[0]["state"] == "glass"
        assert (
            service.project.db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
            == before
        )
        report["player_edit_preserved"] = True
        try:
            service.project.prepare(
                [{"position": dict(x=ox - 1, y=FLOOR, z=oz), "after": "stone"}]
            )
        except ValueError:
            report["outside_write_refused"] = True
        else:
            raise AssertionError("Outside write admitted")
        report["passed_followup"] = True
        save()
        print("FOLLOWUP PASSED", address, flush=True)
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
