"""Detector/policy/native faults are fixtures, never live qualification."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from zipfile import ZipFile
import io

import numpy as np
from PIL import Image
import pytest

from smb3_agent import camera_native_input as native, camera_practice as practice
from smb3_agent.feedback_contracts import FeedbackError, WindowBinding
from smb3_agent.host_contracts import WindowObservation
from smb3_agent.minecraft_camera_observation import FacingGlyphDetector


@pytest.fixture
def detector():
    jar = Path.home() / "Library/Application Support/minecraft/versions/26.3/26.3.jar"
    if not jar.exists():
        pytest.skip("Installed immutable vanilla font unavailable; no live claim")
    with ZipFile(jar) as z:
        return FacingGlyphDetector(z.read("assets/minecraft/textures/font/ascii.png"))


def pixels(detector, tmp_path, heading, pitch, cardinal="south", towards="positive Z"):
    array = np.zeros((1016, 1708, 3), dtype=np.uint8)
    text = f"Facing: {cardinal} (Towards {towards}) ({heading} / {pitch})"
    glyph = detector.render(text)
    array[240:256, 4 : 4 + glyph.shape[1]] = glyph[:, :, None] * 255
    fps = detector.render("10 fps")
    array[60:76, 4 : 4 + fps.shape[1]] = fps[:, :, None] * 255
    path = tmp_path / "frame.png"
    Image.fromarray(array).save(path)
    return path


@pytest.mark.parametrize(
    "heading,pitch,cardinal,towards",
    [
        ("0.0", "0.0", "south", "positive Z"),
        ("179.9", "-89.9", "north", "negative Z"),
        ("-179.9", "90.0", "north", "negative Z"),
        ("-90.0", "-0.1", "east", "positive X"),
        ("90.0", "0.6", "west", "negative X"),
    ],
)
def test_exact_visible_glyph_readings(
    detector, tmp_path, heading, pitch, cardinal, towards
):
    reading = detector.read(
        pixels(detector, tmp_path, heading, pitch, cardinal, towards)
    )
    assert (reading.heading, reading.pitch, reading.fps) == (
        float(heading),
        float(pitch),
        10,
    )


@pytest.mark.parametrize(
    "heading,pitch,cardinal,towards",
    [
        ("0.0", "0.0", "north", "negative Z"),
        ("181.0", "0.0", "south", "positive Z"),
        ("0.0", "91.0", "south", "positive Z"),
        ("0", "0.0", "south", "positive Z"),
        ("0.0", "0.0", "south", "negative Z"),
    ],
)
def test_contradictory_or_malformed_visible_values_refused(
    detector, tmp_path, heading, pitch, cardinal, towards
):
    with pytest.raises(FeedbackError):
        detector.read(pixels(detector, tmp_path, heading, pitch, cardinal, towards))


def test_occlusion_duplicate_wrong_scale_and_font_refused(detector, tmp_path):
    p = pixels(detector, tmp_path, "0.0", "0.0")
    a = np.array(Image.open(p))
    a[240:256, 4:30] = 0
    Image.fromarray(a).save(p)
    with pytest.raises(FeedbackError):
        detector.read(p)
    p = pixels(detector, tmp_path, "0.0", "0.0")
    a = np.array(Image.open(p))
    a[280:296] = a[240:256]
    Image.fromarray(a).save(p)
    with pytest.raises(FeedbackError):
        detector.read(p)
    Image.open(p).resize((854, 508)).save(p)
    with pytest.raises(FeedbackError):
        detector.read(p)
    with pytest.raises(FeedbackError):
        FacingGlyphDetector(b"wrong font")


class QuartzFixture:
    kCGWindowListOptionAll = 1
    kCGNullWindowID = 0
    kCGEventMouseMoved = 1
    kCGMouseButtonLeft = 0
    kCGMouseEventDeltaX = 4
    kCGMouseEventDeltaY = 5
    kCGSessionEventTap = 2

    def __init__(self):
        self.events = []
        self.visible = False
        self.permission = True

    def CGPreflightPostEventAccess(self):
        return self.permission

    def CGCursorIsVisible(self):
        return self.visible

    def CGEventCreate(self, _):
        return {}

    def CGEventGetLocation(self, _):
        return SimpleNamespace(x=10, y=20)

    def CGEventCreateMouseEvent(self, *_):
        return {}

    def CGEventSetIntegerValueField(self, event, field, value):
        event[field] = value

    def CGEventPost(self, kind, event):
        self.events.append((kind, event))


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "cursor",
        "permission",
        "settings",
        "focus",
        "stale",
        "deadline",
        "two_axes",
        "oversized",
        "duplicate",
    ],
)
def test_worker_guards_single_relative_event_and_transport_eof(
    tmp_path, monkeypatch, fault
):
    q = QuartzFixture()
    monkeypatch.setitem(sys.modules, "Quartz", q)
    binding = WindowBinding(123, "start", "7", (0, 0, 100, 100), (200, 200))
    w = WindowObservation(123, "start", "7", "game", (0, 0, 100, 100), True, True, True)
    monkeypatch.setattr(native, "settings_digest", lambda: "a" * 64)
    monkeypatch.setattr(
        native,
        "MacSelectedWindowHost",
        lambda *_: SimpleNamespace(detect_window=lambda: w),
    )
    from smb3_agent import native_host

    monkeypatch.setattr(
        native_host, "foreground_process_id", lambda: 999 if fault == "focus" else 123
    )
    rfd, wfd = os.pipe()
    r = os.fdopen(rfd, "rb", buffering=0)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=r, fileno=r.fileno))
    log = tmp_path / "native.jsonl"
    worker = threading.Thread(target=native._worker, args=(log,))
    worker.start()
    arm = {
        "kind": "arm",
        "binding": asdict(binding),
        "epoch": 1,
        "settings_sha256": "a" * 64,
    }
    os.write(wfd, (json.dumps(arm) + "\n").encode())
    deadline = time.monotonic() + 1
    while (
        not log.exists() or "armed" not in log.read_text()
    ) and time.monotonic() < deadline:
        time.sleep(0.002)
    assert "armed" in log.read_text()
    if fault == "cursor":
        q.visible = True
    if fault == "permission":
        q.permission = False
    if fault == "settings":
        monkeypatch.setattr(native, "settings_digest", lambda: "b" * 64)
    now = time.monotonic()
    packet = {
        "kind": "pulse",
        "token": "test",
        "dx": 4,
        "dy": 0,
        "duration_ms": 120,
        "issued_at": now,
        "deadline": now + 0.12,
        "frame_captured_at": now - 0.3,
        "epoch": 1,
    }
    if fault == "stale":
        packet["frame_captured_at"] = now - 1
    if fault == "deadline":
        packet["issued_at"] = now - 1
        packet["deadline"] = now - 0.88
    if fault == "two_axes":
        packet["dy"] = 1
    if fault == "oversized":
        packet["dx"] = 101
    os.write(wfd, (json.dumps(packet) + "\n").encode())
    if fault == "duplicate":
        os.write(wfd, (json.dumps(packet) + "\n").encode())
    os.close(wfd)
    worker.join(1)
    r.close()
    assert not worker.is_alive()
    assert len(q.events) == (1 if fault in {"none", "duplicate"} else 0)
    if q.events:
        assert q.events == [(q.kCGSessionEventTap, {4: 4, 5: 0})]
    receipts = [json.loads(line) for line in log.read_text().splitlines()]
    if fault != "none":
        assert any(r["kind"] == "refused" for r in receipts)


def test_service_stop_revokes_emitter_before_state_lock(tmp_path):
    service = practice.CameraPracticeService(tmp_path)
    killed = threading.Event()
    service.guard = SimpleNamespace(
        cancel=lambda: killed.set() or {"motion_worker_reaped": True}
    )
    service.lock.acquire()
    stop = threading.Thread(target=service.revoke, args=("Stop",))
    stop.start()
    assert killed.wait(0.1) and service.cancel.is_set()
    service.lock.release()
    stop.join(1)
    service.guard = None
    service.close()


def test_no_receipt_no_camera_authority_and_priority_page_binding(tmp_path):
    s = practice.CameraPracticeService(tmp_path)
    try:
        assert not s.snapshot()["available_outside_practice"]
        with pytest.raises(ValueError, match="sealed"):
            s.dispatch("connect", {"client_id": "a", "session_id": "personal"})
        with pytest.raises(ValueError, match="Review"):
            s.dispatch("start", {"client_id": "a"})
        with pytest.raises(ValueError, match="another page"):
            s.dispatch("stop", {"client_id": "b"})
        result = s.dispatch("stop", {"client_id": "a"})
        assert result["release"]["pending_motion_revoked"]
    finally:
        s.close()


def test_ui_direct_stop_chat_and_generation():
    from smb3_agent.camera_practice_ui import CAMERA_PRACTICE_JS, render_camera_practice

    page = render_camera_practice({}, csrf_token="<unsafe>")
    assert (
        "Take control" in page
        and "&lt;unsafe&gt;" in page
        and "disabled placeholder" in page
    )
    assert (
        "++generation" in CAMERA_PRACTICE_JS
        and "el('notes').focus()" in CAMERA_PRACTICE_JS
    )
    assert (
        "pagehide" in CAMERA_PRACTICE_JS
        and "motion_worker_reaped" in CAMERA_PRACTICE_JS
    )


def test_parent_trace_records_flushed_request_without_claiming_delivery(tmp_path):
    guard = native.CameraMotionGuard.__new__(native.CameraMotionGuard)
    guard.root = tmp_path
    guard.revoked = threading.Event()
    guard.proc = SimpleNamespace(stdin=io.StringIO(), poll=lambda: None, pid=987)
    request = {'kind': 'pulse', 'token': 'fixture-pending', 'dx': 4, 'dy': 0}
    before = time.monotonic()
    guard._send(request)
    trace = json.loads((tmp_path/'native-requests.jsonl').read_text())
    assert trace['request'] == json.loads(guard.proc.stdin.getvalue()) == request
    assert before <= trace['flushed_at'] <= time.monotonic()
    assert trace['worker_pid'] == 987 and trace['parent_pid'] == os.getpid()
    assert trace['wall_flushed_ns'] > 0 and 'delivered' not in trace


@pytest.mark.parametrize("normalize,size", [(True, (100, 100)), (False, (200, 200))])
def test_native_capture_default_contract_and_native_pixels(
    tmp_path, monkeypatch, normalize, size
):
    import subprocess
    from smb3_agent.native_host import capture_selected

    w = WindowObservation(123, "start", "7", "game", (0, 0, 100, 100), True, True, True)

    def capture(args, **kwargs):
        Image.new("RGB", (200, 200), (1, 2, 3)).save(args[-1], format="TIFF")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", capture)
    dest = tmp_path / "frame.png"
    kwargs = {} if normalize else {"normalize": False}
    capture_selected(w, dest, detect_window=lambda: w, **kwargs)
    with Image.open(dest) as pixels:
        assert pixels.size == size
    assert not dest.with_name("frame-capture.tiff").exists()


@pytest.mark.parametrize(
    "heading,cardinal,towards",
    [
        ("-45.0", "east", "positive X"),
        ("-45.0", "south", "positive Z"),
        ("45.0", "south", "positive Z"),
        ("45.0", "west", "negative X"),
        ("135.0", "west", "negative X"),
        ("135.0", "north", "negative Z"),
        ("-135.0", "north", "negative Z"),
        ("-135.0", "east", "positive X"),
    ],
)
def test_cardinal_boundary_respects_visible_rounding_uncertainty(
    detector, tmp_path, heading, cardinal, towards
):
    assert detector.read(
        pixels(detector, tmp_path, heading, "0.0", cardinal, towards)
    ).heading == float(heading)


@pytest.mark.parametrize(
    "heading,cardinal,towards",
    [
        ("-44.9", "east", "positive X"),
        ("45.1", "south", "positive Z"),
        ("134.9", "north", "negative Z"),
        ("-134.9", "north", "negative Z"),
    ],
)
def test_adjacent_cardinal_outside_rounding_interval_refused(
    detector, tmp_path, heading, cardinal, towards
):
    with pytest.raises(FeedbackError):
        detector.read(pixels(detector, tmp_path, heading, "0.0", cardinal, towards))


def test_settings_change_then_restore_still_requires_new_calibration(
    tmp_path, monkeypatch
):
    s = practice.CameraPracticeService(tmp_path)
    cal = SimpleNamespace(
        environment=SimpleNamespace(controls_id="original"), sha256="old-calibration"
    )
    try:
        monkeypatch.setattr(practice, "settings_digest", lambda: "changed")
        with pytest.raises(ValueError, match="invalidated"):
            s._require_calibration(cal)
        monkeypatch.setattr(practice, "settings_digest", lambda: "original")
        with pytest.raises(ValueError, match="invalidated"):
            s._require_calibration(cal)
    finally:
        s.close()


def test_page_lease_watchdog_cancels_without_operation_lock(tmp_path):
    now = [10]
    s = practice.CameraPracticeService(tmp_path, clock=lambda: now[0])
    s.state = "executing"
    s.lease = 0
    try:
        deadline = time.monotonic() + 0.6
        while not s.cancel.is_set() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert s.cancel.is_set() and s.snapshot()["review"] is None
        receipts = [
            json.loads(line)
            for line in (tmp_path / "control-receipts.jsonl").read_text().splitlines()
        ]
        assert any(
            "lease expired" in r["reason"] and r["release"]["epoch_revoked"]
            for r in receipts
        )
    finally:
        s.close()
