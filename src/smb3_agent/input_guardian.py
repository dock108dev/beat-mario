"""Independent deadline/parent-death release of explicitly registered native pulses."""
import json
import os
from pathlib import Path
import queue
import select
import subprocess
from smb3_agent.app_runtime import helper_command
import sys
import threading
import time
from uuid import uuid4

from smb3_agent.host_contracts import HostError
from smb3_agent.native_input import _KEY_CODES


class InputGuardian:
    def __init__(self, path):
        self.proc = subprocess.Popen(helper_command(__name__, "--worker", str(path)),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        os.set_blocking(self.proc.stdin.fileno(), False)
        self._responses = queue.Queue(maxsize=64)
        self._lock = threading.Lock()
        self._closed = False
        self.reader = threading.Thread(target=self._read, daemon=True, name="input-guardian-receipts")
        self.reader.start()
        try:
            response = self._responses.get(timeout=2)
        except queue.Empty as exc:
            self.close()
            raise HostError("Independent native release guardian did not become ready") from exc
        if response.get("kind") != "ready" or not response.get("input_permission"):
            self.close()
            raise HostError("Independent native release guardian is unavailable")

    def _read(self):
        for line in self.proc.stdout:
            try:
                self._responses.put_nowait(json.loads(line))
            except (ValueError, queue.Full):
                pass

    def _send(self, message):
        if self.proc.poll() is not None:
            raise HostError("Independent input guardian exited")
        payload = (json.dumps(message, allow_nan=False)+"\n").encode()
        try:
            written = os.write(self.proc.stdin.fileno(), payload)
        except (OSError, BlockingIOError) as exc:
            raise HostError("Input guardian transport unavailable") from exc
        if written != len(payload):
            raise HostError("Incomplete guardian registration; no input may start")

    def arm(self, command, started):
        if command.action == "move":
            return
        token = uuid4().hex
        with self._lock:
            self._send({"kind": "arm", "token": token, "control": command.control,
                "input_kind": command.kind.value, "target": command.target,
                "deadline": started+command.duration_ms/1000})
            deadline = min(started+command.duration_ms/1000, time.monotonic()+.1)
            while time.monotonic() < deadline:
                try:
                    reply = self._responses.get(timeout=max(.001, deadline-time.monotonic()))
                except queue.Empty:
                    break
                if reply.get("kind") == "armed" and reply.get("token") == token:
                    return
            raise HostError("Guardian did not acknowledge within the pulse budget")

    def close(self):
        if self._closed:
            return self.proc.poll() == 0
        self._closed = True
        try:
            self._send({"kind": "close"})
        except HostError:
            pass
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            return False
        self.reader.join(1)
        self.proc.stdout.close()
        return self.proc.returncode == 0 and not self.reader.is_alive()


def _worker(path):
    import Quartz as q
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    def record(message):
        with path.open("a") as stream:
            stream.write(json.dumps({"monotonic": time.monotonic(), **message})+"\n")
        print(json.dumps(message), flush=True)
    def release(reason):
        nonlocal pending
        if pending is None:
            return
        message = pending
        pending = None
        if message["input_kind"] == "keyboard":
            event = q.CGEventCreateKeyboardEvent(None, _KEY_CODES[message["control"]], False)
        else:
            button = q.kCGMouseButtonLeft if message["control"] == "left_button" else q.kCGMouseButtonRight
            kind = q.kCGEventLeftMouseUp if button == q.kCGMouseButtonLeft else q.kCGEventRightMouseUp
            event = q.CGEventCreateMouseEvent(None, kind, tuple(message["target"]), button)
        q.CGEventPost(q.kCGHIDEventTap, event)
        deadline = time.monotonic()+.05
        while time.monotonic() < deadline:
            keys = [code for code in _KEY_CODES.values() if q.CGEventSourceKeyState(q.kCGEventSourceStateHIDSystemState, code)]
            buttons = [b for b in (0,1) if q.CGEventSourceButtonState(q.kCGEventSourceStateHIDSystemState,b)]
            if not keys and not buttons:
                break
            time.sleep(.001)
        record({"kind": "release", "token": message["token"], "reason": reason,
                "confirmed": not keys and not buttons, "held_keys": keys, "held_buttons": buttons})
    permission = bool(q.CGPreflightPostEventAccess())
    record({"kind": "ready", "input_permission": permission, "pid": os.getpid()})
    if not permission:
        return
    buffer = b""
    try:
        while True:
            if pending and time.monotonic() >= pending["deadline"]:
                release("pulse_deadline")
            ready, _, _ = select.select([sys.stdin.buffer], [], [], .005)
            if not ready:
                continue
            data = os.read(sys.stdin.fileno(), 4096)
            if not data:
                release("parent_transport_closed")
                return
            buffer += data
            if len(buffer) > 8192:
                raise ValueError("Guardian input budget exceeded")
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                message = json.loads(line)
                if message.get("kind") == "close":
                    release("service_shutdown")
                    return
                if (message.get("kind") != "arm" or set(message) != {
                        "kind","token","control","input_kind","target","deadline"}
                        or type(message["deadline"]) not in {int,float}
                        or not 0 < message["deadline"]-time.monotonic() <= .25):
                    raise ValueError("Invalid guardian pulse")
                if message["input_kind"] == "keyboard":
                    if message["control"] not in _KEY_CODES:
                        raise ValueError("Unsupported key")
                elif message["input_kind"] == "mouse":
                    target = message["target"]
                    if (message["control"] not in {"left_button","right_button"}
                            or not isinstance(target,list) or len(target)!=2
                            or any(type(v) is not int or abs(v)>32768 for v in target)):
                        raise ValueError("Invalid mouse pulse")
                else:
                    raise ValueError("Unsupported input")
                release("superseded")
                pending = message
                record({"kind":"armed","token":message["token"],"deadline":message["deadline"]})
    finally:
        release("guardian_exit")


if __name__ == "__main__":
    _worker(sys.argv[2])
