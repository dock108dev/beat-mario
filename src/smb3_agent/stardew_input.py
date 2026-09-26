"""Bounded macOS foreground input with identity checks and cancellation."""
from __future__ import annotations

import threading
import time
from typing import Callable

from smb3_agent.stardew_adapter import InputCommand, InputKind, OrdinaryInputDriver, StardewAdapterError, WindowObservation

_KEY_CODES = {"a": 0, "s": 1, "d": 2, "w": 13, "x": 7, "c": 8,
              "escape": 53, "shift": 56, "left": 123, "right": 124, "down": 125, "up": 126}


class MacOrdinaryInputDriver(OrdinaryInputDriver):
    """One synchronous pulse at a time. Reclaim interrupts within the poll interval.

    Stardew polls system input state: process-posted events are not sufficient.
    Native events require foreground identity throughout each bounded pulse.
    Focus loss releases held input and revokes authority; typing during play is
    unsupported. There is an OS scheduling interval between checking and posting.
    """
    def __init__(self, *, window_provider: Callable[[], WindowObservation],
                 isolation_guard: Callable[[WindowObservation], None],
                 authority_guard: Callable[[], None], quartz=None, before_mouse_press=None, pulse_guard=None) -> None:
        native_input = quartz is None
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
        self.before_mouse_press = before_mouse_press
        if pulse_guard is None and native_input:
            from smb3_agent.stardew_adapter import _foreground_process_id
            def pulse_guard(expected):
                self.authority_guard()
                if _foreground_process_id() != expected.process_id:
                    raise StardewAdapterError("Foreground game changed during input")
        self.pulse_guard = pulse_guard
        self._cancel = threading.Event()
        self._revocation_count = 0
        self._lock = threading.RLock()
        self._dispatch = threading.Lock()
        self._held: list[tuple[int, object]] = []
        self.last_pulse_timing = None
        self.gameplay_emission_count = 0
        self._down_started = None
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
        if command.purpose in {"water_crop", "harvest_crop", "plant_seed", "clear_debris", "select_farm_item"} and self.before_mouse_press is not None:
            # SDL updates its targeting from mouse-motion events. A click's OS
            # coordinates alone need not update the game's current tool target.
            self._run_pulse(InputCommand(InputKind.MOUSE, "move", "move", 0,
                                        target=command.target, purpose="aim_reviewed_crop"))
            if self._cancel.wait(0.08):
                raise StardewAdapterError("Input canceled while aiming")
            ready_to_press = self.before_mouse_press(command, self._guard())
            if ready_to_press is not None:
                # Resource refresh may move the pointer to the HUD. Restore the
                # already visibly verified target; the callback checks both
                # retained timestamps immediately before mouse-down.
                self._run_pulse(InputCommand(InputKind.MOUSE, "move", "move", 0,
                                            target=command.target, purpose="restore_verified_aim"))
                if self._cancel.wait(0.08):
                    raise StardewAdapterError("Input canceled while restoring aim")
                ready_to_press()
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
                q.CGEventSetIntegerValueField(down, q.kCGMouseEventClickState, 1)
                q.CGEventSetIntegerValueField(up, q.kCGMouseEventClickState, 1)
            else:
                raise StardewAdapterError("Controller emission is not configured")
            self._held.append((pid, up))
            try:
                self._down_started = time.monotonic()
                q.CGEventPost(q.kCGHIDEventTap, down)
                if command.purpose in {"navigate", "water_crop", "harvest_crop", "plant_seed", "clear_debris", "select_farm_item"}:
                    self.gameplay_emission_count += 1
            except Exception:
                self._neutralize()
                raise
        # Identity checks can include slow OS/filesystem work. They must never
        # extend a held movement pulse beyond its requested duration.
        release_failures = []
        def expire():
            try:
                with self._lock:
                    self._release()
            except Exception as exc:
                release_failures.append(exc)
                self._cancel.set()
        # Posting may itself block. Count that time against the pulse instead
        # of adding the requested hold again after CGEventPost returns.
        deadline = self._down_started + command.duration_ms / 1000
        timer = threading.Timer(max(0, deadline-time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        try:
            while time.monotonic() < deadline:
                if self._cancel.wait(min(.02, max(0, deadline - time.monotonic()))):
                    raise StardewAdapterError("Input canceled")
                if time.monotonic() >= deadline:
                    # Do not begin an OS identity lookup at the release deadline.
                    # A native call holding the GIL could delay the release timer,
                    # turning a small positioning correction into an overshoot.
                    break
                if self.pulse_guard is not None:
                    # Full window enumeration and save hashing can hold the GIL
                    # long enough to delay key-up. Poll fresh OS focus/authority
                    # while held; full identity checks bracket every pulse.
                    self.pulse_guard(window)
                    continue
                current = self._guard()
                if (current.process_id, current.process_started_at, current.window_id) != (window.process_id, window.process_started_at, window.window_id):
                    raise StardewAdapterError("Process/window changed during input")
        finally:
            timer.cancel()
            timer.join()
            with self._lock:
                self._release()
        if release_failures:
            raise StardewAdapterError("Timed input release failed") from release_failures[0]
        if self.pulse_guard is not None:
            current = self._guard()
            if (current.process_id, current.process_started_at, current.window_id) != (window.process_id, window.process_started_at, window.window_id):
                raise StardewAdapterError("Process/window changed during input")

    def _release(self) -> None:
        # Retain failed releases for a subsequent neutralization attempt.
        while self._held:
            pid, event = self._held[-1]
            released_at = time.monotonic()
            self.q.CGEventPost(self.q.kCGHIDEventTap, event)
            if self._down_started is not None:
                self.last_pulse_timing = {"post_to_release_seconds": released_at - self._down_started,
                                          "release_call_seconds": time.monotonic() - released_at}
            self._held.pop()

    def _neutralize(self) -> None:
        self._revocation_count += 1
        self._cancel.set()
        with self._lock:
            self._release()
