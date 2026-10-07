"""Identity for the in-place personal delivery; captured once at server startup."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from smb3_agent.beta_readiness import source_identity
from smb3_agent.paths import REPOSITORY_ROOT


def delivery_identity() -> dict:
    from smb3_agent.player_store import VERSION

    source = source_identity(REPOSITORY_ROOT)
    build = (
        json.loads((REPOSITORY_ROOT / "build-manifest.json").read_text()).get("build")
        if getattr(sys, "frozen", False)
        else None
    )
    return {
        "schema": "game-companion-delivery/v1",
        "version": VERSION,
        "build": build,
        "packaged": bool(getattr(sys, "frozen", False)),
        "root": str(REPOSITORY_ROOT),
        "source_sha256": source["source_sha256"],
        "head": source["head"],
        "python": str(Path(sys.executable).absolute()),
        "pid": os.getpid(),
        "instance": uuid.uuid4().hex,
    }


def activity_diagnostics(server):
    """Allowlisted activity metadata; no screenshots, credentials or provider logs."""
    activities = []
    for game, attribute in (
        ("mario", "conversation_service"),
        ("stardew", "stardew_conversation_service"),
    ):
        service = getattr(server, attribute, None)
        if service is None:
            continue
        state = service.snapshot()
        plan = state.get("current_plan") or state.get("plan") or {}
        runtime = state.get("runtime") or {}
        outcome = state.get("outcome") or {}
        preparation = runtime.get("goal_preparation") or {}
        activities.append(
            {
                "preparation_status": preparation.get("status"),
                "preparation_reason": str(preparation.get("reason") or "")[:1000],
                "preparation_step_count": len(preparation.get("steps") or []),
                "game": game,
                "plan_id": plan.get("plan_id"),
                "requested_objective": str(plan.get("requested_objective") or "")[
                    :2000
                ],
                "resource_limits": plan.get("resource_limits", {}),
                "status": runtime.get("status", runtime.get("state")),
                "handback_confirmed": runtime.get("handback_confirmed"),
                "outcome_status": outcome.get("status"),
                "inference_state": (state.get("ai") or {}).get("state"),
            }
        )
    return activities


class OwnedGameProcesses:
    """Retain child handles across observation detach; never discover processes."""

    def __init__(self):
        self.processes = []
        self.watchdogs = []

    def launch(self, *args, **kwargs):
        import subprocess

        from smb3_agent.process_watchdog import ChildWatchdog

        kwargs.setdefault("start_new_session", True)
        process = subprocess.Popen(*args, **kwargs)
        self.processes.append(process)
        try:
            self.watchdogs.append(ChildWatchdog(process))
        except Exception:
            process.terminate()
            process.wait(timeout=5)
            raise
        return process

    def close(self):
        import subprocess

        for process in self.processes:
            if process.poll() is not None:
                continue
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # A still-owned child handle cannot silently become an unrelated PID.
                # Neutralization precedes this cleanup; FCEUX may ignore SIGTERM.
                process.kill()
                process.wait(timeout=5)

        failures = []
        for guard in self.watchdogs:
            try:
                guard.close()
            except Exception:
                failures.append("Owned game watchdog closure unconfirmed")
        if failures:
            raise RuntimeError("; ".join(failures))
