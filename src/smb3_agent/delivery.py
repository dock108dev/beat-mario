"""Identity for the in-place personal delivery; captured once at server startup."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import uuid

from smb3_agent.beta_readiness import source_identity
from smb3_agent.paths import REPOSITORY_ROOT


def delivery_identity() -> dict:
    source = source_identity(REPOSITORY_ROOT)
    return {"schema": "game-companion-delivery/v1", "root": str(REPOSITORY_ROOT),
            "source_sha256": source["source_sha256"], "head": source["head"],
            "python": str(Path(sys.executable).absolute()), "pid": os.getpid(),
            "instance": uuid.uuid4().hex}


class OwnedGameProcesses:
    """Retain child handles across observation detach; never discover processes."""

    def __init__(self):
        self.processes = []

    def launch(self, *args, **kwargs):
        import subprocess
        process = subprocess.Popen(*args, **kwargs)
        self.processes.append(process)
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
