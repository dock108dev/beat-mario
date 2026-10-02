"""Experimental captured-relative motion; never registered in playable profiles.

An independent process emits at most one finite mouse-motion event per request.
It never emits a key, mouse button, scroll, movement command or capture click.
Cancel kills/reaps the emitter, revoking pending requests. Already posted native
motion cannot be undone; the caller must independently observe settling.
"""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import queue
import select
import os
import subprocess
from smb3_agent.app_runtime import helper_command
import sys
import threading
import time
from uuid import uuid4

from smb3_agent.feedback_contracts import (
    FeedbackError,
    RelativePointerAction,
    WindowBinding,
)
from smb3_agent.screen_host import MacSelectedWindowHost

NATIVE_VERSION = "mac-captured-delta-session-event/v4-request-trace"
SETTING_KEYS = frozenset(
    {
        "mouseSensitivity",
        "invertXMouse",
        "invertYMouse",
        "fov",
        "fovEffectScale",
        "guiScale",
        "fullscreen",
        "maxFps",
        "enableVsync",
        "renderDistance",
        "simulationDistance",
        "preferredGraphicsBackend",
        "graphicsPreset",
        "key_key.smoothCamera",
        "forceUnicodeFont",
        "inactivityFpsLimit",
        "pauseOnLostFocus",
    }
)


def settings_snapshot():
    path = Path.home() / "Library/Application Support/minecraft/options.txt"
    values = {}
    for line in path.read_text().splitlines():
        key, _, value = line.partition(":")
        if key in SETTING_KEYS:
            if key in values:
                raise FeedbackError("Ambiguous controls/settings file")
            values[key] = value
    if set(values) != SETTING_KEYS:
        raise FeedbackError(
            "Unknown relevant settings; explicit environment recheck required"
        )
    return values


def settings_digest():
    return hashlib.sha256(
        json.dumps(settings_snapshot(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class CameraMotionGuard:
    def __init__(self, binding: WindowBinding, epoch, settings_sha256, root):
        self.binding, self.epoch = binding, epoch
        self.revoked = threading.Event()
        self._dispatch = threading.Lock()
        self.responses = queue.Queue(maxsize=64)
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(
            helper_command(__name__, str(self.root / "native-motion.jsonl")),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def read():
            for line in self.proc.stdout:
                try:
                    self.responses.put_nowait(json.loads(line))
                except (ValueError, queue.Full):
                    self.revoked.set()
                    self.proc.kill()
                    break

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            ready = self.responses.get(timeout=2)
            if ready.get("kind") != "ready" or not ready.get("input_permission"):
                raise FeedbackError("Native motion guardian is unavailable")
            self._send(
                {
                    "kind": "arm",
                    "binding": asdict(binding),
                    "epoch": epoch,
                    "settings_sha256": settings_sha256,
                }
            )
            reply = self.responses.get(timeout=1)
            if reply.get("kind") != "armed":
                raise FeedbackError("Native motion guardian refused environment")
        except Exception:
            self.cancel()
            raise

    def _send(self, data):
        if self.revoked.is_set() or self.proc.poll() is not None:
            raise FeedbackError("Motion authority revoked")
        self.proc.stdin.write(json.dumps(data, allow_nan=False) + "\n")
        self.proc.stdin.flush()
        # A flushed request can still be pending or refused; it is never proof
        # of event consumption. Retain this boundary for native cancellation
        # trials instead of inferring a pending packet from an armed worker.
        with (self.root / 'native-requests.jsonl').open('a') as stream:
            stream.write(json.dumps({'flushed_at': time.monotonic(),
                                     'wall_flushed_ns': time.time_ns(),
                                     'parent_pid': os.getpid(),
                                     'worker_pid': self.proc.pid,
                                     'request': data})+'\n')

    def pulse(self, action: RelativePointerAction):
        if (
            not isinstance(action, RelativePointerAction)
            or action.frame.binding != self.binding
        ):
            raise FeedbackError("Motion action has wrong exact window binding")
        if not self._dispatch.acquire(blocking=False):
            raise FeedbackError("No blind or concurrent relative-motion queue")
        try:
            if self.revoked.is_set() or action.cancellation_epoch != self.epoch:
                raise FeedbackError("Relative motion belongs to revoked epoch")
            token = uuid4().hex
            self._send(
                {
                    "kind": "pulse",
                    "token": token,
                    "dx": action.dx,
                    "dy": action.dy,
                    "duration_ms": action.duration_ms,
                    "issued_at": action.issued_at,
                    "deadline": action.deadline,
                    "frame_captured_at": action.frame.captured_at,
                    "epoch": action.cancellation_epoch,
                }
            )
            while time.monotonic() < action.deadline + 0.05:
                if self.revoked.is_set():
                    raise FeedbackError("Motion canceled while receipt pending")
                try:
                    receipt = self.responses.get(timeout=0.005)
                except queue.Empty:
                    continue
                if receipt.get("token") == token:
                    if receipt.get("kind") != "delivered":
                        raise FeedbackError(
                            receipt.get("reason", "Native motion refused")
                        )
                    return receipt
            raise FeedbackError("Native motion acknowledgment deadline expired")
        except Exception:
            self.cancel()
            raise
        finally:
            self._dispatch.release()

    def cancel(self):
        started = time.monotonic()
        self.revoked.set()  # independent of the dispatch/operation lock
        if self.proc.poll() is None:
            self.proc.kill()
        try:
            self.proc.wait(timeout=0.2)
            reaped = self.proc.poll() is not None
        except subprocess.TimeoutExpired:
            reaped = False
        self.reader.join(0.05)
        if reaped:
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                if not stream.closed:
                    stream.close()
        return {
            "motion_worker_reaped": reaped,
            "pending_motion_revoked": reaped,
            "epoch_revoked": True,
            "seconds": time.monotonic() - started,
            "method": "independent_single_event_worker_killed_and_reaped",
            "already_posted_motion": "requires_visible_settling_check",
        }


def _worker(path):
    import Quartz as q

    path = Path(path)
    state = None
    seen = set()
    buffer = b""

    def record(data):
        data = {"monotonic": time.monotonic(), **data}
        with path.open("a") as stream:
            stream.write(json.dumps(data) + "\n")
        print(json.dumps(data), flush=True)

    record(
        {
            "kind": "ready",
            "input_permission": bool(q.CGPreflightPostEventAccess()),
            "pid": os.getpid(),
            "implementation": NATIVE_VERSION,
        }
    )
    while True:
        ready, _, _ = select.select([sys.stdin.buffer], [], [], 0.005)
        if not ready:
            continue
        data = os.read(sys.stdin.fileno(), 8192)
        if not data:
            return  # transport death never grants input
        buffer += data
        if len(buffer) > 16384:
            return
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            message = json.loads(line)
            if message.get("kind") == "arm":
                if state is not None or set(message) != {
                    "kind",
                    "binding",
                    "epoch",
                    "settings_sha256",
                }:
                    return
                binding = dict(message["binding"])
                binding["bounds"], binding["pixel_size"] = (
                    tuple(binding["bounds"]),
                    tuple(binding["pixel_size"]),
                )
                selected = WindowBinding(**binding)
                if (
                    type(message["epoch"]) is not int
                    or message["epoch"] < 0
                    or settings_digest() != message["settings_sha256"]
                ):
                    return
                state = (selected, message["epoch"], message["settings_sha256"])
                record(
                    {
                        "kind": "armed",
                        "epoch": message["epoch"],
                        "binding": asdict(selected),
                    }
                )
                continue
            token = message.get("token")
            try:
                if (
                    state is None
                    or set(message)
                    != {
                        "kind",
                        "token",
                        "dx",
                        "dy",
                        "duration_ms",
                        "issued_at",
                        "deadline",
                        "frame_captured_at",
                        "epoch",
                    }
                    or message["kind"] != "pulse"
                ):
                    raise FeedbackError("Invalid finite motion packet")
                binding, epoch, settings = state
                if token in seen or len(seen) >= 32:
                    raise FeedbackError(
                        "Duplicate pulse or finite session motion budget exhausted"
                    )
                seen.add(token)
                from smb3_agent.feedback_contracts import finite

                if (
                    any(
                        type(message[k]) is not int or abs(message[k]) > 100
                        for k in ("dx", "dy")
                    )
                    or bool(message["dx"]) == bool(message["dy"])
                    or type(message["duration_ms"]) is not int
                    or not 1 <= message["duration_ms"] <= 250
                    or message["epoch"] != epoch
                    or not finite(
                        message["deadline"],
                        message["issued_at"] + message["duration_ms"] / 1000,
                        message["issued_at"] + 0.25,
                    )
                ):
                    raise FeedbackError("Unbounded or invalid relative motion packet")
                host = MacSelectedWindowHost(
                    binding.process_id, binding.process_started_at, binding.window_id
                )
                binding.require(host.detect_window(), execution=True)
                if (
                    settings_digest() != settings
                    or q.CGCursorIsVisible()
                    or not q.CGPreflightPostEventAccess()
                ):
                    raise FeedbackError("Settings, permission or capture changed")
                # One mouseMoved event carries explicit Cocoa relative deltas.
                # Keep the desktop cursor at its current location; never warp,
                # press a button, acquire capture, or queue a motion sequence.
                point = q.CGEventGetLocation(q.CGEventCreate(None))
                event_created_at = time.monotonic()
                event = q.CGEventCreateMouseEvent(
                    None, q.kCGEventMouseMoved, point, q.kCGMouseButtonLeft
                )
                q.CGEventSetIntegerValueField(
                    event, q.kCGMouseEventDeltaX, message["dx"]
                )
                q.CGEventSetIntegerValueField(
                    event, q.kCGMouseEventDeltaY, message["dy"]
                )
                now = time.monotonic()
                if (
                    not message["issued_at"] <= now < message["deadline"]
                    or not 0 <= now - message["frame_captured_at"] <= 0.8
                ):
                    raise FeedbackError("Expired pulse or stale native feedback frame")
                # Exact focus/authority guards bracket the single native post.
                from smb3_agent.native_host import foreground_process_id

                if foreground_process_id() != binding.process_id:
                    raise FeedbackError(
                        "Foreground changed immediately before relative input"
                    )
                post_started_at = time.monotonic()
                q.CGEventPost(q.kCGSessionEventTap, event)
                post_returned_at = time.monotonic()
                record(
                    {
                        "kind": "delivered",
                        "token": token,
                        "issued_at": message["issued_at"],
                        "delivered_at": now,
                        "event_created_at": event_created_at,
                        "post_started_at": post_started_at,
                        "post_returned_at": post_returned_at,
                        "post_call_seconds": post_returned_at - post_started_at,
                        "binding": asdict(binding),
                        "epoch": epoch,
                        "settings_sha256": settings,
                        "foreground_checked": binding.process_id,
                        "cursor_hidden_checked": True,
                        "consumption_proven": False,
                        "dx": message["dx"],
                        "dy": message["dy"],
                        "deadline": message["deadline"],
                        "buttons_or_keys_emitted": False,
                        "cursor_location": [point.x, point.y],
                    }
                )
            except Exception as exc:
                record({"kind": "refused", "token": token, "reason": str(exc)})


if __name__ == "__main__":
    _worker(sys.argv[1])
