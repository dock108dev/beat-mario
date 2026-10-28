"""Versioned stdio bridge; gameplay never depends on an AI call or UI thread."""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future, TimeoutError as FutureTimeout
import json
import subprocess
import threading
from uuid import uuid4

from smb3_agent.delivery import OwnedGameProcesses

from smb3_agent.paths import repository_path
from smb3_agent.minecraft_delivery import data_artifacts, node_runtime

WORKER = repository_path("minecraft-worker/worker.cjs")


class MinecraftBridge:
    def __init__(self, *, node=None, worker=WORKER):
        self.owned = OwnedGameProcesses()
        diagnostics = (
            data_artifacts() / "minecraft-chat/worker-stderr.log"
        )
        diagnostics.parent.mkdir(parents=True, exist_ok=True)
        self.stderr_log = diagnostics.open("a")
        self.process = self.owned.launch(
            [node or node_runtime(), str(worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr_log,
            text=True,
            bufsize=1,
        )
        self.session_id = None
        self.revision = 0
        self.events = deque(maxlen=2000)
        self.condition = threading.Condition()
        self.pending = {}
        self.write_lock = threading.Lock()
        self.lifecycle_lock = threading.RLock()
        self.reader = threading.Thread(
            target=self._read, daemon=True, name="minecraft-events"
        )
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                event = json.loads(line)
                if event.get("v") != 1:
                    raise ValueError("Worker protocol mismatch")
                with self.condition:
                    self.events.append(event)
                    pending = self.pending.get(event.get("request_id"))
                    if (
                        pending
                        and event.get("session_id") == pending[0]
                        and event["type"] in {"completed", "failed"}
                    ):
                        _, future = self.pending.pop(event["request_id"])
                        # Canceling a caller future is not gameplay Stop. Still
                        # consume its reply without killing the protocol reader.
                        if not future.set_running_or_notify_cancel():
                            self.condition.notify_all()
                            continue
                        if event["type"] == "failed":
                            future.set_exception(
                                RuntimeError(event.get("error", "worker_failed"))
                            )
                        else:
                            future.set_result(event.get("result"))
                    self.condition.notify_all()
        finally:
            if self.process.poll() is None:
                self.process.terminate()
            with self.condition:
                for _, future in self.pending.values():
                    if future.set_running_or_notify_cancel():
                        future.set_exception(RuntimeError("Minecraft worker exited"))
                self.pending.clear()
                self.condition.notify_all()

    def submit(
        self,
        op,
        args=None,
        *,
        timeout_ms=10000,
        revision=None,
        session_id=None,
        request_id=None,
    ):
        """Returns (request_id, Future). Only execute enters the worker action queue."""
        if op == "execute" and (session_id is None or revision is None):
            raise ValueError("execute requires captured session_id and revision")
        sid = session_id or self.session_id
        if not sid:
            raise RuntimeError("No Minecraft session")
        rid = request_id or uuid4().hex
        request = {
            "v": 1,
            "session_id": sid,
            "request_id": rid,
            "op": op,
            "revision": self.revision if revision is None else revision,
            "timeout_ms": timeout_ms,
            "args": args or {},
        }
        # Rejection history is an optimization; safety constraints must never be trimmed.
        frame = json.dumps(request, allow_nan=False, separators=(",", ":")) + "\n"
        if (
            len(frame.encode("utf-8")) > 65536
            and request["args"].get("action") == "inspect_site"
        ):
            request["args"] = dict(request["args"])
            hints = list(request["args"].get("rejections", []))
            while hints and len(frame.encode("utf-8")) > 65536:
                hints.pop(0)
                request["args"]["rejections"] = hints
                frame = (
                    json.dumps(request, allow_nan=False, separators=(",", ":")) + "\n"
                )
        if len(frame.encode("utf-8")) > 65536:
            raise ValueError("Worker request exceeds bounded frame; no action sent")
        future = Future()
        with self.write_lock, self.condition:
            if rid in self.pending:
                raise ValueError("Duplicate pending request")
            self.pending[rid] = (sid, future)
            try:
                self.process.stdin.write(frame)
                self.process.stdin.flush()
            except BaseException:
                self.pending.pop(rid, None)
                raise
        return rid, future

    def call(self, op, args=None, *, timeout_ms=10000, **kwargs):
        _, future = self.submit(op, args, timeout_ms=timeout_ms, **kwargs)
        try:
            return future.result(timeout_ms / 1000 + 4)
        except FutureTimeout:
            # A missing reply is not evidence of cessation. Tear down owned worker.
            self.close()
            raise TimeoutError(
                "Worker reply missing; connection closed, cessation unconfirmed"
            ) from None

    def connect(self, *, port=25575, viewer_port=0, world_id="unknown"):
        self.connection_options = dict(
            port=port, viewer_port=viewer_port, world_id=world_id
        )
        with self.lifecycle_lock:
            if self.session_id:
                raise RuntimeError("Disconnect before connecting")
            self.session_id = uuid4().hex
            self.revision = 0
            try:
                return self.call(
                    "connect",
                    {"port": port, "viewer_port": viewer_port, "world_id": world_id},
                    timeout_ms=30000,
                )
            except BaseException:
                self.session_id = None
                raise

    def observe(self):
        return self.call("observe")

    def stop(self, *, session_id=None):
        """Direct control path: request dispatch and observed cessation are distinct events."""
        sid = session_id or self.session_id
        result = self.call("cancel", timeout_ms=5000, session_id=sid)
        if self.session_id == sid:
            self.revision = result["revision"]
        return result

    def disconnect(self):
        with self.lifecycle_lock:
            if self.session_id:
                try:
                    return self.call("disconnect", timeout_ms=5000)
                finally:
                    self.session_id = None

    def reconnect(self, *, expected_session_id, port=25575):
        with self.lifecycle_lock:
            if expected_session_id != self.session_id:
                raise ValueError("stale_session")
            self.disconnect()
            return self.connect(**getattr(self, "connection_options", {"port": port}))

    def snapshot(self):
        with self.lifecycle_lock:
            return {"session_id": self.session_id, "state": self.observe()}

    def events_after(self, sequence=0):
        with self.condition:
            return [event for event in self.events if event["seq"] > sequence]

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.close()  # EOF requests bot/viewer cleanup.
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.owned.close()
        self.reader.join(timeout=2)
        self.process.stdout.close()
        self.stderr_log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
