"""Bounded macOS ordinary input with process-targeted events and cancellation."""
from __future__ import annotations

import threading
import time
from typing import Callable

from smb3_agent.stardew_adapter import InputCommand, InputKind, OrdinaryInputDriver, StardewAdapterError, WindowObservation

_KEY_CODES = {"a": 0, "s": 1, "d": 2, "w": 13, "x": 7, "c": 8,
              "escape": 53, "shift": 56, "left": 123, "right": 124, "down": 125, "up": 126}


class MacOrdinaryInputDriver(OrdinaryInputDriver):
    """One synchronous pulse at a time. Reclaim interrupts within the poll interval.

    Events target the reviewed process, so focus loss cannot type in companion
    chat even in the interval between a foreground check and native dispatch.
    """
    def __init__(self, *, window_provider: Callable[[], WindowObservation],
                 isolation_guard: Callable[[WindowObservation], None],
                 authority_guard: Callable[[], None], quartz=None) -> None:
        if quartz is None:
            try:
                import Quartz as quartz
            except ImportError as exc:
                raise StardewAdapterError("macOS ordinary-input dependency unavailable") from exc
            preflight = getattr(quartz, "CGPreflightPostEventAccess", None)
            if preflight is None or not preflight():
                raise StardewAdapterError("macOS input-post permission is unavailable; no permission prompt was opened")
        self.q = quartz
        self.window_provider = window_provider
        self.isolation_guard = isolation_guard
        self.authority_guard = authority_guard
        self._cancel = threading.Event()
        self._revocation_count = 0
        self._lock = threading.RLock()
        self._dispatch = threading.Lock()
        self._held: list[tuple[int, object]] = []
        super().__init__(keyboard=self._pulse, mouse=self._pulse, neutralizer=self._neutralize)

    def arm(self) -> None:
        """Runtime calls only with new explicit authorization, never on resume from disk."""
        with self._lock:
            revocation = self._revocation_count
            self._guard()
            if self._revocation_count != revocation:
                raise StardewAdapterError("Input authorization was canceled while arming")
            self._cancel.clear()

    def _guard(self) -> WindowObservation:
        self.authority_guard()
        window = self.window_provider()
        if not window.trusted:
            raise StardewAdapterError("Foreground game window is required")
        self.isolation_guard(window)
        return window

    def _pulse(self, command: InputCommand) -> None:
        if not self._dispatch.acquire(blocking=False):
            raise StardewAdapterError("An ordinary input pulse is already active")
        try:
            self._run_pulse(command)
        except Exception:
            self._neutralize()
            raise
        finally:
            self._dispatch.release()

    def _run_pulse(self, command: InputCommand) -> None:
        if command.action not in {"press", "tap", "hold", "click", "move"} or not 0 <= command.duration_ms <= 250:
            raise StardewAdapterError("Input must be one bounded pulse of at most 250 ms")
        with self._lock:
            if self._cancel.is_set():
                raise StardewAdapterError("Input authority was canceled; fresh authorization required")
            window = self._guard()
            if self._cancel.is_set():
                raise StardewAdapterError("Input canceled during guard validation")
            pid = window.process_id
            q = self.q
            if command.kind is InputKind.KEYBOARD:
                if command.control not in _KEY_CODES:
                    raise StardewAdapterError("Unsupported keyboard control")
                code = _KEY_CODES[command.control]
                down = q.CGEventCreateKeyboardEvent(None, code, True)
                up = q.CGEventCreateKeyboardEvent(None, code, False)
            elif command.kind is InputKind.MOUSE:
                if command.target is None or window.bounds is None:
                    raise StardewAdapterError("Mouse input requires a reviewed screen point")
                x, y = command.target
                bx, by, width, height = window.bounds
                if not (bx <= x < bx + width and by <= y < by + height):
                    raise StardewAdapterError("Mouse target is outside the game window")
                mapping = {"left_button": (q.kCGEventLeftMouseDown, q.kCGEventLeftMouseUp, q.kCGMouseButtonLeft),
                           "right_button": (q.kCGEventRightMouseDown, q.kCGEventRightMouseUp, q.kCGMouseButtonRight),
                           "move": (q.kCGEventMouseMoved, q.kCGEventMouseMoved, q.kCGMouseButtonLeft)}
                if command.control not in mapping:
                    raise StardewAdapterError("Unsupported mouse control")
                start, stop, button = mapping[command.control]
                down = q.CGEventCreateMouseEvent(None, start, (x, y), button)
                up = q.CGEventCreateMouseEvent(None, stop, (x, y), button)
            else:
                raise StardewAdapterError("Controller emission is not configured")
            self._held.append((pid, up))
            try:
                q.CGEventPostToPid(pid, down)
            except Exception:
                self._neutralize()
                raise
        try:
            deadline = time.monotonic() + command.duration_ms / 1000
            while time.monotonic() < deadline:
                if self._cancel.wait(min(.02, max(0, deadline - time.monotonic()))):
                    raise StardewAdapterError("Input canceled")
                current = self._guard()
                if (current.process_id, current.process_started_at, current.window_id) != (window.process_id, window.process_started_at, window.window_id):
                    raise StardewAdapterError("Process/window changed during input")
        finally:
            with self._lock:
                self._release()

    def _release(self) -> None:
        # Retain failed releases for a subsequent neutralization attempt.
        while self._held:
            pid, event = self._held[-1]
            self.q.CGEventPostToPid(pid, event)
            self._held.pop()

    def _neutralize(self) -> None:
        self._revocation_count += 1
        self._cancel.set()
        with self._lock:
            self._release()
