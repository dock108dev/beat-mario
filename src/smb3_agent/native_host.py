"""Native focus and selected-window pixels shared across adapters."""
from pathlib import Path
from smb3_agent.host_contracts import HostError, WindowObservation

from functools import lru_cache


@lru_cache(maxsize=1)
def _foreground_binding():
    # Cache the library binding, never the OS focus answer. Repeated dynamic
    # library discovery can delay small key-up deadlines during held input.
    import ctypes
    import ctypes.util

    class ProcessSerialNumber(ctypes.Structure):
        _fields_ = [("high", ctypes.c_uint32), ("low", ctypes.c_uint32)]

    location = ctypes.util.find_library("ApplicationServices")
    if location is None:
        raise OSError("ApplicationServices unavailable")
    native = ctypes.CDLL(location)
    native.GetFrontProcess.argtypes = [ctypes.POINTER(ProcessSerialNumber)]
    native.GetFrontProcess.restype = ctypes.c_int32
    native.GetProcessPID.argtypes = [ctypes.POINTER(ProcessSerialNumber), ctypes.POINTER(ctypes.c_int32)]
    native.GetProcessPID.restype = ctypes.c_int32
    return native, ProcessSerialNumber


def foreground_process_id(*, error_type=HostError) -> int:
    """Read current OS focus on every call, without NSWorkspace's cached answer."""
    import ctypes
    try:
        native, serial_type = _foreground_binding()
        serial, pid = serial_type(), ctypes.c_int32()
        if native.GetFrontProcess(ctypes.byref(serial)) != 0 or native.GetProcessPID(ctypes.byref(serial), ctypes.byref(pid)) != 0 or pid.value <= 0:
            raise OSError("foreground process query failed")
        return pid.value
    except (OSError, AttributeError) as exc:
        raise error_type("Fresh macOS foreground identity is unavailable") from exc


def request_unbundled_activation(pid: int, started_at: str, *, error_type=HostError, cancelled=None) -> dict:
    """Request focus for an owned direct game launch without a bundle identity.

    The request is never focus proof. Callers must observe current OS foreground,
    window visibility and exact identity before accepting pixels or sending input.
    """
    import ctypes
    import subprocess
    import sys
    import threading
    import time
    if cancelled is not None and cancelled():
        raise error_type('Game focus preparation interrupted')
    if getattr(sys, 'frozen', False) and threading.current_thread() is not threading.main_thread():
        from PyObjCTools import AppHelper
        finished, abandoned, result = threading.Event(), threading.Event(), {}
        def on_main():
            try:
                if not abandoned.is_set():
                    result['value'] = request_unbundled_activation(pid, started_at,
                        error_type=error_type, cancelled=cancelled)
            except Exception as exc:
                result['error'] = exc
            finally:
                finished.set()
        AppHelper.callAfter(on_main)
        deadline = time.monotonic() + 2
        while not finished.wait(.05):
            if (cancelled is not None and cancelled()) or time.monotonic() >= deadline:
                abandoned.set()
                raise error_type('Game focus preparation interrupted or main event loop unavailable')
        if 'error' in result:
            raise result['error']
        return result.get('value', {})
    actual = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='],
                            capture_output=True, text=True, timeout=2).stdout.strip()
    if not started_at or actual != started_at:
        raise error_type('Owned game process changed before focus request')
    native, serial_type = _foreground_binding()
    serial = serial_type()
    native.GetProcessForPID.argtypes = [ctypes.c_int32, ctypes.POINTER(serial_type)]
    native.GetProcessForPID.restype = ctypes.c_int32
    native.SetFrontProcessWithOptions.argtypes = [ctypes.POINTER(serial_type), ctypes.c_uint32]
    native.SetFrontProcessWithOptions.restype = ctypes.c_int32
    lookup = native.GetProcessForPID(pid, ctypes.byref(serial))
    requested = native.SetFrontProcessWithOptions(ctypes.byref(serial), 0) if lookup == 0 else None
    return {"owned_pid": pid, "process_start_verified": True,
            "serial_lookup_status": lookup, "focus_request_status": requested,
            "foreground_after_request": foreground_process_id(error_type=error_type),
            "request_thread_main": threading.current_thread() is threading.main_thread()}


def capture_selected(window: WindowObservation, destination: Path, *, detect_window,
                     require_foreground=True, error_type=HostError, started=None,
                     normalize=True, screen_region=False) -> Path:
    if not (window.trusted if require_foreground else window.observable) or window.bounds is None:
        raise error_type("window_loss")
    current = detect_window()
    if (
        current.process_id != window.process_id
        or current.process_started_at != window.process_started_at
        or current.window_id != window.window_id
        or current.bounds != window.bounds
    ):
        raise error_type("process_loss")
    if destination.exists():
        raise error_type("screen evidence destination already exists")
    if screen_region and (not require_foreground or not window.trusted):
        raise error_type("screen-region capture requires the identified foreground window")
    import subprocess
    from PIL import Image
    from datetime import datetime, timezone
    _, _, width, height = window.bounds
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Native PNG compression of the retina frame is avoidable latency.
    # TIFF is a lossless capture intermediate; the normalized PNG remains
    # the retained visible evidence. Failed intermediates remain available.
    raw = destination.with_name(destination.stem + "-capture.tiff")
    if raw.exists():
        raise error_type("native screen evidence destination already exists")
    if started is not None:
        started(datetime.now(timezone.utc).isoformat())
    try:
        selector = (["-R", ','.join(map(str, window.bounds))] if screen_region
                    else ["-l", window.window_id])
        result = subprocess.run(["/usr/sbin/screencapture", "-x", "-o", "-t", "tiff", *selector, str(raw)],
                                capture_output=True, timeout=1.5, check=False)
    except subprocess.TimeoutExpired as exc:
        raise error_type("visible capture exceeded freshness bound; no frame accepted") from exc
    if result.returncode or not raw.is_file():
        raise error_type("native visible capture failed; check screen-recording permission")
    after = detect_window()
    if (after.process_id, after.process_started_at, after.window_id, after.bounds) != (window.process_id, window.process_started_at, window.window_id, window.bounds):
        import json
        from dataclasses import asdict
        destination.with_suffix(".capture-refusal.json").write_text(json.dumps({
            "reason": "process/window changed during visible capture",
            "before": asdict(window), "after": asdict(after), "frame_accepted": False,
        }, indent=2))
        raise error_type("process/window changed during visible capture")
    with Image.open(raw) as image:
        if image.size not in {(width, height), (width*2, height*2)}:
            raise error_type("native capture has unexpected viewport dimensions")
        pixels = image.convert("RGB")
        if normalize:
            pixels = pixels.resize((width, height), Image.Resampling.NEAREST)
        pixels.save(destination, format="PNG", compress_level=1)
    raw.unlink()  # newly created lossless intermediate, never retained evidence
    return destination
