"""Standalone app entry point and an explicit allowlist for frozen helper workers."""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser

HELPERS = frozenset(
    {
        "smb3_agent.model_gateway",
        "smb3_agent.input_guardian",
        "smb3_agent.camera_native_input",
    }
)


def helper_command(module, *arguments):
    if module not in HELPERS:
        raise ValueError("Unknown app helper")
    if getattr(sys, "frozen", False):
        return [sys.executable, "--gc-helper", module, *arguments]
    return [sys.executable, "-m", module, *arguments]


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--gc-helper":
        import importlib
        import io

        for name, fd, mode in (
            ("stdin", 0, "rb"),
            ("stdout", 1, "wb"),
            ("stderr", 2, "wb"),
        ):
            if getattr(sys, name) is None:
                setattr(
                    sys,
                    name,
                    io.TextIOWrapper(open(fd, mode, closefd=False), write_through=True),
                )
        if len(sys.argv) < 3 or sys.argv[2] not in HELPERS:
            raise SystemExit("Unknown helper")
        module = importlib.import_module(sys.argv[2])
        args = sys.argv[3:]
        if module.__name__.endswith("model_gateway") and args == ["--worker"]:
            module._worker()
        elif (
            module.__name__.endswith("input_guardian")
            and len(args) == 2
            and args[0] == "--worker"
        ):
            module._worker(args[1])
        elif module.__name__.endswith("camera_native_input") and len(args) == 1:
            module._worker(args[0])
        else:
            raise SystemExit("Invalid helper invocation")
        return
    from smb3_agent.player_store import user_data_root

    root = user_data_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)  # installation resources stay read-only; history is separate
    from smb3_agent.lab_ui import _new_lab_ui_server, _shutdown_session_managers

    smoke = "--smoke" in sys.argv
    if smoke:
        # HTTP/profile lifecycle smoke only. No capture, focus, game or native input.
        from urllib.request import urlopen, Request
        from urllib.parse import urlencode

        server = _new_lab_ui_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"

        def post(action, payload):
            body = urlencode(
                {
                    "csrf_token": server.csrf_token,
                    "action": action,
                    "payload": json.dumps(payload),
                }
            ).encode()
            with urlopen(Request(url + "/api/player", data=body), timeout=10) as r:
                return json.load(r)

        try:
            with urlopen(url + "/setup", timeout=10) as r:
                assert b"Save profile" in r.read()
            state = post(
                "save", {"game": "minecraft", "name": "Packaged smoke disposable setup"}
            )
            identity = state["selected"]["id"]
            post("chat", {})
            state = post(
                "message", {"text": "Finish a 7 by 3 wall with a centered doorway"}
            )
            assert state["plan"] is None and not state["reviewed"]
            state = post("message", {"text": "How does Stop work?"})
            assert state["plan"] is None and not state["reviewed"]
            state = post("stop", {})
            assert state["plan"] is None
            state = post("open", {"id": identity})
            assert state["selected"]["id"] == identity and not state["reviewed"]
            report = post(
                "report",
                {
                    "id": identity,
                    "text": "Packaged offline smoke; no native input used.",
                },
            )
            assert report["report"]["version"]
            print(
                json.dumps(
                    {
                        "smoke": "passed",
                        "native_input": False,
                        "version": state["version"],
                        "profile_reopened": True,
                        "report_exported": True,
                    }
                )
            )
        finally:
            failures = _shutdown_session_managers(server)
            server.shutdown()
            server.server_close()
            thread.join(3)
            if failures:
                raise RuntimeError(str(failures))
        return
    # Reuse an identified instance only; never stop an unknown port owner.
    from urllib.request import urlopen
    from urllib.error import URLError

    try:
        with urlopen("http://127.0.0.1:8765/api/delivery", timeout=2) as r:
            existing = json.load(r)
        from smb3_agent.delivery import delivery_identity

        own = delivery_identity()
        if (
            existing.get("schema") != "game-companion-delivery/v1"
            or existing.get("source_sha256") != own["source_sha256"]
        ):
            raise RuntimeError(
                "Another app/build uses port 8765. Stop it through its own app before opening this build."
            )
        if "--no-browser" not in sys.argv:
            webbrowser.open("http://127.0.0.1:8765/setup")
        return
    except URLError:
        pass
    server = _new_lab_ui_server("127.0.0.1", 8765)
    # A visible Quit action uses the existing verified shutdown endpoint.
    if "--no-browser" not in sys.argv:
        webbrowser.open("http://127.0.0.1:8765/setup")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
