"""Run the real Mario UI in disposable state; requires Node + Playwright Chromium.

Usage: .venv/bin/python scripts/check_learning_layout.py NEW_EVIDENCE_DIRECTORY
Set NODE_PATH if Playwright is installed outside the usual Node module path.
No gameplay actions or preference submissions are performed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

from smb3_agent.lab_ui import _new_lab_ui_server


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    evidence = Path(sys.argv[1]).resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    original = Path.cwd()
    result = 1
    with tempfile.TemporaryDirectory(prefix="mario-layout-") as isolated:
        # Only tracked contracts, never runtime evidence, ROMs or saves.
        tracked = subprocess.check_output(
            ["git", "ls-files", "data"], cwd=repo, text=True
        ).splitlines()
        for name in tracked:
            if Path(name).suffix not in {".yaml", ".json"}:
                continue
            destination = Path(isolated) / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / name, destination)
        os.chdir(isolated)
        server = _new_lab_ui_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_port
        try:
            result = subprocess.call([
                "node", str(repo / "scripts/check_learning_layout.cjs"),
                f"http://127.0.0.1:{port}", str(evidence),
            ])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            os.chdir(original)
    (evidence / "cleanup.json").write_text(json.dumps({
        "server_thread_stopped": not thread.is_alive(),
        "isolated_state_removed": not Path(isolated).exists(),
        "port": port, "browser_exit_code": result,
    }, indent=2))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
