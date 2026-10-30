"""Authorized multi-process source-use trial; only copied disposable worlds.

Each invocation is one process session. No owner root or provider overrides.
Polling waits observe work; elapsed idle waiting never pads the activity interval.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def copy_state_file(source, destination):
    if sys.platform == "darwin":
        # Independent copy-on-write files; changes never mutate the source.
        # Fail visibly if unavailable rather than unexpectedly consuming disk.
        subprocess.run(["cp", "-c", "-p", str(source), str(destination)], check=True)
        return destination
    return shutil.copy2(source, destination)


def copy_trial_state(source, destination):
    """Copy runnable state; reference prior diagnostics at their retained source.

    Historical logs are not execution inputs. Repeatedly copying them consumed
    disk needed for actual checkpoint and restore qualification.
    """
    log_root = source / "profile" / "artifacts" / "minecraft-chat"
    names = {"events.jsonl", "worker-events.jsonl"}
    retained = [str((log_root / name).resolve()) for name in sorted(names)
                if (log_root / name).is_file()]

    def ignore(directory, entries):
        return names.intersection(entries) if Path(directory) == log_root else set()

    for name in ("profile", "world"):
        shutil.copytree(source / name, destination / name, ignore=ignore, copy_function=copy_state_file)
    return retained


def checkpoint_material(project, component):
    """Choose a real change from the selected component's latest binding."""
    row = project.db.execute(
        "SELECT r.body FROM architecture_stages s JOIN architecture_reviews r "
        "ON r.id=s.review WHERE s.component=? ORDER BY s.review DESC LIMIT 1",
        (component,),
    ).fetchone()
    if not row:
        raise ValueError("Restart checkpoint requires an existing component binding")
    current = next(c for c in json.loads(row[0])["components"] if c["name"] == component)
    return "natural" if current["material"] == "glass" else "glass"



def reserve_question_calls(root, current_report, used):
    """Reserve the complete four-call question before admission across restarts."""
    prior_calls = sum(json.loads(p.read_text()).get('provider_calls', 0)
                      for p in root.glob('session-*.json') if p != current_report)
    if prior_calls + used + 4 > 80:
        raise ValueError('Sustained qualification aggregate 80-call budget would be exceeded')
    return 80 - prior_calls - used


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--session", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--questions", type=int, default=7)
    parser.add_argument("--faults", action="store_true")
    parser.add_argument("--finish", action="store_true")
    args = parser.parse_args()
    assert 0 <= args.questions <= 20
    if args.source:
        prior = json.loads((args.source / "report.json").read_text())
        assert (
            prior.get("shutdown")
            and prior.get("scope")
            == "Source app, actual provider, new disposable world"
        )
        args.root.mkdir(parents=True, exist_ok=False)
        retained_diagnostics = copy_trial_state(args.source, args.root)
    else:
        prior = json.loads((args.root / f"session-{args.session - 1}.json").read_text())
        assert prior.get("shutdown") and not prior.get("failure")
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
        "session": args.session,
        "pid": os.getpid(),
        "address": f"http://127.0.0.1:{server.server_port}",
        "started_at": time.time(),
        "operations": [],
        "prior_diagnostics_retained_at_source": retained_diagnostics if args.source else [],
    }
    path = args.root / f"session-{args.session}.json"

    def save():
        report["provider_calls"] = len(service.provider.usage)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(report, indent=2))
        temp.replace(path)

    def post(action, **values):
        start = time.monotonic()
        data = urlencode(
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
                    data=data,
                ),
                timeout=60,
            ) as reply:
                result = json.load(reply)
        except HTTPError as exc:
            report.setdefault("http_errors", []).append(
                {"action": action, "status": exc.code, "body": exc.read().decode()}
            )
            save()
            raise
        report.setdefault("admission_seconds", []).append(
            {"action": action, "seconds": time.monotonic() - start}
        )
        return result

    def wait(predicate, seconds=120):
        until = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() > until:
                raise TimeoutError("Bounded sustained qualification wait expired")
            time.sleep(0.1)

    def counts():
        return [
            list(r)
            for r in service.project.db.execute(
                "SELECT status, COUNT(*) FROM units GROUP BY status"
            )
        ]

    def start_review(component, material):
        revision = service.designer.current()["revision"]
        post(
            "architecture_review",
            design_revision=revision,
            component=component,
            material=material,
        )
        review = service.project.architecture_status()
        assert not review["unsupported"] and not review["dependencies"], review
        post(
            "architecture_run",
            design_revision=revision,
            architecture_review=review["review"],
        )
        return review

    def continue_review():
        review = service.project.architecture_status()
        post(
            "architecture_run",
            design_revision=service.designer.current()["revision"],
            architecture_review=review["review"],
        )
        wait(lambda: not service.project.architecture_active, 180)
        assert service.project.state == "complete", service.project.error

    questions = [
        "While you keep building, briefly explain: does Stop pause the Minecraft world?",
        "What work is currently underway? Distinguish it from older saved work.",
        "If I close and reopen the companion, will construction resume by itself?",
        "Can a saved completed building record prove nobody changed its blocks?",
        "What should I do before changing the dimensions of a reviewed building?",
        "Does stopping this construction also stop other players in the world?",
        "Can you restore items inside a chest just from its recorded block state?",
        "How is a decorative object different from a functional workstation?",
        "Why does a building need a separate review when its footprint changes?",
        "What remains unverified about this project? Be brief and do not invent results.",
    ]
    try:
        post("connect")
        wait(lambda: not service.connecting)
        assert not service.error, service.error
        p = service.project
        assert p.state == "idle" and not p.staged_active
        report["reopened"] = {
            "state": p.state,
            "counts": counts(),
            "authority": service.authority(),
            "automatic_resume": p.status()["automatic_resume"],
        }
        report["fresh_observation"] = {
            k: v
            for k, v in service.bridge.observe().items()
            if k in ("world_id", "dimension", "game_version", "active", "queued")
        }
        assert report["fresh_observation"].get("active") is None
        if args.session:
            assert report["reopened"]["counts"] == prior["closed_counts"], (
                "Receipt counts changed before explicit continuation"
            )
        post("check_setup")
        wait(lambda: service.provider.status["state"] != "checking", 30)
        assert service.provider.status.get("available"), service.provider.status.get(
            "message"
        )
        if args.faults:
            component = next(
                c["name"]
                for c in service.designer.current()["components"]
                if c["kind"] == "building"
            )
            ordinary_run = p.run

            def interrupt(point, uid):
                if point == "write":
                    raise RuntimeError("Qualification interruption before receipt")

            p.run = lambda **kw: ordinary_run(fault=interrupt, **kw)
            start_review(component, "industrial")
            wait(lambda: not p.architecture_active)
            report["interrupted_receipt"] = p.status()
            assert (
                p.db.execute(
                    "SELECT COUNT(*) FROM units WHERE status='pending'"
                ).fetchone()[0]
                > 0
            )
            p.run = ordinary_run
            post("reconnect")
            wait(lambda: not service.connecting)
            assert not service.error and not p.staged_active
            continue_review()
            report["receipt_continued"] = p.status()

            log = service.practice.home / "server.log"
            log_offset = log.stat().st_size
            service.practice.command("save-all flush")
            wait(lambda: "Saved the game" in log.read_text()[log_offset:], 30)
            report["pre_crash_save_confirmed"] = True

            # A real owned-server loss at a known receipt boundary, in this copy.
            def lose_server(point, uid):
                if point == "write":
                    service.practice.process.kill()
                    service.practice.process.wait(timeout=10)
                    raise RuntimeError("Qualification owned server loss")

            p.run = lambda **kw: ordinary_run(fault=lose_server, **kw)
            start_review(component, "coastal")
            wait(lambda: not p.architecture_active)
            report["server_loss"] = p.status()
            save()
            p.run = ordinary_run
            post("reconnect")
            wait(lambda: not service.connecting)
            assert not service.error, service.error
            assert not p.staged_active
            report["server_reconnected_idle"] = service.authority()
            continue_review()
            report["server_continued"] = p.status()
            save()
            # Observe an actual inference child before direct Stop.
            post(
                "message",
                text="Briefly explain what this companion can inspect in the current world.",
                request_id="fault-cancel",
            )
            wait(lambda: bool(service.provider.lifecycle()), 10)
            report["cancel_child"] = service.provider.lifecycle()
            t = time.monotonic()
            post("stop")
            wait(lambda: not service.stopping and not service.busy, 10)
            report["cancel_seconds"] = time.monotonic() - t
            assert not service.provider.lifecycle() and not service.stop_failed
            report["cancel_usage"] = service.provider.usage[-1:]
            # Inject disk accounting only; do not consume disk or weaken the reserve.
            import smb3_agent.minecraft_build as build

            disk_usage = build.shutil.disk_usage
            from collections import namedtuple

            try:
                build.shutil.disk_usage = lambda path: namedtuple(
                    "Usage", "total used free"
                )(100, 100, 0)
                try:
                    p.check_storage()
                    raise AssertionError("Low disk admitted")
                except ValueError as exc:
                    report["low_disk_refusal"] = str(exc)
            finally:
                build.shutil.disk_usage = disk_usage
            # Known player edit after completed work must survive a fresh survey.
            manifest = p.architecture_manifest()[1]
            cell = next(
                c
                for c in manifest["components"][0]["cells"]
                if c["after"] == "white_wool"
            )
            pos = cell["position"]
            service.practice.command(
                "setblock {x} {y} {z} minecraft:diamond_block".format(**pos)
            )
            wait(lambda: p.inspect([pos])[0]["state"] == "diamond_block", 10)
            post(
                "architecture_run",
                design_revision=service.designer.current()["revision"],
                architecture_review=p.architecture_status()["review"],
            )
            wait(lambda: not p.architecture_active)
            assert (
                p.state == "needs_review"
                and p.inspect([pos])[0]["state"] == "diamond_block"
            )
            report["player_conflict"] = {
                "position": pos,
                "error": p.error,
                "preserved": True,
            }
            save()
            return
        started = time.monotonic()
        report["activity_started_at"] = time.time()
        save()
        if args.session:
            continue_review()
            report["continued_saved_review"] = p.architecture_status()
        if args.finish:
            assert args.session > 0
            report["restore_verified_complete"] = service.project.state == "complete"
            report["closed_counts"] = counts()
            report["activity_seconds"] = time.monotonic() - started
            save()
            return
        components = [
            c["name"]
            for c in service.designer.current()["components"]
            if c["kind"] == "building"
        ]
        assert components
        round_no = 0
        # Material studies at independently selected places; each is an explicit
        # normal review/start, not an inferred edit or scripted raw world command.
        materials = ("warm", "coastal", "industrial", "natural")
        while time.monotonic() - started < args.seconds:
            component = components[(round_no + args.session) % len(components)]
            material = materials[
                (round_no // len(components) + args.session) % len(materials)
            ]
            op = {
                "component": component,
                "material": material,
                "started_at": time.time(),
            }
            report["operations"].append(op)
            review = start_review(component, material)
            op["review"] = review["review"]
            authority = service.authority()
            op["counts_before"] = counts()
            if round_no < args.questions:
                reserve_question_calls(args.root, path, len(service.provider.usage))
                usage_start = len(service.provider.usage)
                question = questions[(round_no + args.session * 3) % len(questions)]
                t = time.monotonic()
                post(
                    "message",
                    text=question,
                    request_id=f"sustained-{args.session}-{round_no}",
                )
                wait(lambda: not service.busy, 245)
                op.update(
                    question=question,
                    question_seconds=time.monotonic() - t,
                    messages=service.messages[-2:],
                    usage=service.provider.usage[usage_start:],
                    authority_unchanged=authority == service.authority(),
                    error=service.error,
                )
                report["provider_calls"] = len(service.provider.usage)
                save()
                assert not service.error and op["authority_unchanged"], op
                assert (
                    op["messages"][-1]["role"] == "assistant"
                    and op["usage"][-1]["status"] == "returned"
                )
            wait(lambda: not p.architecture_active, 180)
            assert p.state == "complete", p.error
            op["progress"] = dict(p.architecture_progress)
            op["counts_after"] = counts()
            t = time.monotonic()
            snapshot = service.snapshot()
            op["status_seconds"] = time.monotonic() - t
            op["status_bytes"] = len(json.dumps(snapshot).encode())
            op["storage_bytes"] = p.check_storage()
            op["finished_at"] = time.time()
            round_no += 1
            report["activity_seconds"] = time.monotonic() - started
            save()
            print(
                json.dumps(
                    {
                        "session": args.session,
                        "round": round_no,
                        "elapsed": report["activity_seconds"],
                        "reply": op.get("question_seconds"),
                    }
                ),
                flush=True,
            )
        # Leave genuinely incomplete work for the next process to reconcile.
        count = p.db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        final = start_review(
            components[0], checkpoint_material(p, components[0])
        )
        wait(
            lambda: (
                p.db.execute("SELECT COUNT(*) FROM units").fetchone()[0] > count
                or not p.architecture_active
            ),
            60,
        )
        t = time.monotonic()
        post("stop")
        wait(lambda: not p.staged_active and not service.stopping, 30)
        report["stop_seconds"] = time.monotonic() - t
        assert not service.stop_failed
        report["remaining_review"] = p.architecture_status()
        assert len(report["remaining_review"]["completed"]) < len(
            final["components"]
        ), "Work completed before restart checkpoint"
        report["closed_counts"] = counts()
        report["activity_seconds"] = time.monotonic() - started
        report["activity_finished_at"] = time.time()
        save()
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
        save()
    finally:
        service.close()
        server.shutdown()
        server.server_close()
        report["shutdown"] = True
        report["finished_at"] = time.time()
        save()
    if report.get("failure"):
        raise SystemExit(report["failure"])


if __name__ == "__main__":
    main()
