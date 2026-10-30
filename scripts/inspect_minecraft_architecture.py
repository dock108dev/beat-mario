"""Read-only rendered inspection in a copy of a recorded disposable build.

Headless positioning is qualification setup, not a successful access walk.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--places", nargs="+", required=True)
    args = parser.parse_args()
    prior = json.loads((args.source / "report.json").read_text())
    if prior.get(
        "scope"
    ) != "Source app, actual provider, new disposable world" or not prior.get(
        "shutdown"
    ):
        raise ValueError("Only a closed recorded disposable world may be inspected")
    args.root.mkdir(parents=True, exist_ok=False)
    for name in ("profile", "world"):
        shutil.copytree(args.source / name, args.root / name)
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
        "scope": "Read-only architecture inspection; headless positioning is setup",
        "scenes": [],
        "address": f"http://127.0.0.1:{server.server_port}",
    }

    def save():
        (args.root / "report.json").write_text(json.dumps(report, indent=2))

    def wait(predicate, seconds=120):
        end = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() > end:
                raise TimeoutError("Inspection wait expired")
            time.sleep(0.1)

    try:
        service.connect()
        wait(lambda: not service.connecting)
        if service.error:
            raise RuntimeError(service.error)
        project = service.project
        terrain = project.terrain_manifest()
        service.bridge.call(
            "select_build_region",
            {"region": terrain["region"]},
            session_id=service.bridge.session_id,
            revision=service.bridge.revision,
        )
        service.bridge.build_console.region = project.region = terrain["region"]
        before = project.db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        components = {}
        for (body,) in project.db.execute(
            "SELECT body FROM architecture_reviews ORDER BY id"
        ):
            for c in json.loads(body)["components"]:
                components[c["name"]] = c
        service.practice.command("time set noon")
        for name in args.places:
            c = components[name]
            x, z, w, d, level, h = c["box"]
            ox, oz = terrain["origin"]
            scenes = [
                (
                    "exterior",
                    {
                        "x": ox + x + w // 2,
                        "y": terrain["sea_level"] + level + 1 + max(0, h - 8),
                        "z": oz + z + d // 2,
                    },
                    False,
                )
            ]
            if c["rooms"]:
                p = c["rooms"][0]["floor"]
                scenes.append(
                    (
                        "interior",
                        {**p, "x": p["x"] + 1, "y": p["y"] + 1, "z": p["z"] + 2},
                        True,
                    )
                )
            for label, pos, inside in scenes:
                service.bridge.call(
                    "execute",
                    {
                        "action": "build_focus",
                        "position": {
                            "x": ox + x + w // 2,
                            "y": terrain["region"]["bounds"]["max"]["y"] + 8,
                            "z": oz + z + d // 2,
                        },
                    },
                    session_id=service.bridge.session_id,
                    revision=service.bridge.revision,
                    timeout_ms=10000,
                )
                service.practice.command(
                    f"tp CompanionBot {pos['x'] + 0.5} {pos['y']} {pos['z'] + 0.5} 0 0"
                )
                wait(
                    lambda: all(
                        abs(
                            service.bridge.observe()["position"][k]
                            - (v + (0.5 if k != "y" else 0))
                        )
                        < 0.75
                        for k, v in pos.items()
                    ),
                    10,
                )
                view = service.bridge.observe()["viewer_url"] + (
                    "?view=inside" if inside else ""
                )
                index = len(report["scenes"])
                report["scenes"].append(
                    {
                        "index": index,
                        "place": name,
                        "view": label,
                        "position": pos,
                        "url": view,
                    }
                )
                report["current"] = index
                save()
                print(json.dumps(report["scenes"][-1]), flush=True)
                end = time.monotonic() + 120
                while (
                    time.monotonic() < end
                    and not (args.root / f"render-{index}.done").exists()
                ):
                    time.sleep(0.2)
        report["journal_unchanged"] = (
            before == project.db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        )
    except Exception as exc:
        report["failure"] = str(exc)
        print(str(exc), flush=True)
    finally:
        service.close()
        server.ai_provider.close()
        server.shutdown()
        server.server_close()
        report["shutdown"] = True
        save()


if __name__ == "__main__":
    main()
