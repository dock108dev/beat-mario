"""Disposable source viewer/UI pixel correlation; no model-answer qualification."""

import argparse
import json
import os
from pathlib import Path
import socket
import threading
import time
from qualify_minecraft_sustained import copy_trial_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ui-only", action="store_true")
    args = parser.parse_args()
    prior = json.loads((args.source / "report.json").read_text())
    assert prior["shutdown"]
    args.root.mkdir(parents=True, exist_ok=False)
    copy_trial_state(args.source, args.root)
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
        "scope": "Source measurement with controlled one-cell changes and synthetic UI messages; not model grounding or sustained acceptance",
        "pid": os.getpid(),
        "app_url": f"http://127.0.0.1:{server.server_port}/minecraft",
        "samples": [],
    }

    def save():
        tmp = args.root / "report.tmp"
        tmp.write_text(json.dumps(report, indent=2))
        tmp.replace(args.root / "report.json")

    def wait(predicate, seconds=120):
        end = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() > end:
                raise TimeoutError("Delivery qualification deadline")
            time.sleep(0.05)

    def events():
        p = service.root / "worker-events.jsonl"
        return (
            [json.loads(line) for line in p.read_text().splitlines()]
            if p.exists()
            else []
        )

    def capture(index, kind, **fields):
        pending = args.root / "pending-capture.json"
        temp = pending.with_suffix(".tmp")
        temp.write_text(json.dumps({"index": index, "kind": kind, **fields}))
        temp.replace(pending)
        wait(lambda: (args.root / f"capture-{index}.json").exists(), 120)
        return json.loads((args.root / f"capture-{index}.json").read_text())

    try:
        service.connect()
        wait(lambda: not service.connecting)
        assert not service.error, service.error
        save()
        if not args.ui_only:
            project = service.project
            terrain = project.terrain_manifest()
            service.bridge.call(
                "select_build_region",
                {"region": terrain["region"]},
                session_id=service.bridge.session_id,
                revision=service.bridge.revision,
            )
            service.bridge.build_console.region = project.region = terrain["region"]
            state = service.bridge.observe()
            pos = {k: int(state["position"][k]) for k in ("x", "y", "z")}
            pos["x"] += 3
            pos["y"] += 3
            pos["z"] += 1
            assert project.inspect([pos])[0]["state"] == "air"
            report["position"] = pos
            report["viewer_url"] = (
                state["viewer_url"]
                + "?measure="
                + ",".join(str(pos[k]) for k in ("x", "y", "z"))
            )
            project.prepare([{"position": pos, "after": "white_wool"}])
            assert project.run()["state"] == "complete", project.error
            report["phase"] = "awaiting visible viewer baseline"
            save()
            print(
                json.dumps({"viewer": report["viewer_url"], "app": report["app_url"]}),
                flush=True,
            )
            wait(
                lambda: any(e["type"] == "viewer_pixel_baseline" for e in events()), 180
            )
            for index in range(20):
                material = "dirt" if index % 2 == 0 else "white_wool"
                project.prepare([{"position": pos, "after": material}])
                row = {
                    "index": index,
                    "material": material,
                    "mutation_started_ms": time.time_ns() / 1e6,
                }
                assert project.run()["state"] == "complete", project.error
                wait(
                    lambda: any(
                        e["type"] == "viewer_pixel_observed"
                        and e["observed_server_ms"] >= row["mutation_started_ms"]
                        for e in events()
                    ),
                    12,
                )
                row["pixel_event"] = next(
                    e
                    for e in events()
                    if e["type"] == "viewer_pixel_observed"
                    and e["observed_server_ms"] >= row["mutation_started_ms"]
                )
                row["capture"] = capture(
                    index, "world", expected=material, pixel=row["pixel_event"]["pixel"]
                )
                report["samples"].append(row)
                save()
            project.prepare([{"position": pos, "after": "air"}])
            assert project.run()["state"] == "complete", project.error
            report["marker_restored"] = project.inspect([pos])[0]["state"] == "air"
        report["phase"] = "UI delivery"
        save()
        print(
            json.dumps(
                {"app": report["app_url"], "phase": "waiting for capture readiness"}
            ),
            flush=True,
        )
        setup_start = time.time_ns() / 1e6
        wait(lambda: (args.root / "capture-ready.json").exists(), 180)
        report["capture_setup_ms"] = time.time_ns() / 1e6 - setup_start
        words = "amber birch cedar delta ember forest garden harbor ivory jungle kettle lemon maple nectar ocean pebble quartz river spruce timber".split()
        for index in range(20, 40):
            text = f"Delivery sample {words[index - 20]} ready."
            service.message("assistant", text)
            message = service.messages[-1]
            row = {"index": index, "message": message}
            row["capture"] = capture(index, "ui", message=message)
            report["samples"].append(row)
            save()
        report["phase"] = "complete"
    except Exception as exc:
        report["failure"] = str(exc)
    finally:
        service.close()
        server.shutdown()
        server.server_close()
        report["shutdown"] = True
        save()
    if report.get("failure"):
        raise SystemExit(report["failure"])


if __name__ == "__main__":
    main()
