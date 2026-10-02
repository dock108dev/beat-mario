"""Experimental camera-only practice, sharing the ordinary Companion server.

Only locally sealed disposable-world receipts are selectable. No executable
profile, generic skill, natural-language plan, or normal catalog capability is
created here. Stop revokes the independent emitter before operation locks.
"""

from dataclasses import asdict
import hashlib
import json
import os
import subprocess
from pathlib import Path
import threading
import time
from uuid import uuid4

from smb3_agent.camera_native_input import (
    CameraMotionGuard,
    NATIVE_VERSION,
    settings_digest,
    settings_snapshot,
)
from smb3_agent.companion_session import SessionOutcome
from smb3_agent.custom_variants import PlanAttemptHistory
from smb3_agent.feedback_contracts import (
    CalibrationSample,
    CameraEnvironment,
    CorrectionGoal,
    FeedbackError,
    FeedbackFrame,
    NeutralHandback,
    ReadingState,
    RelativePointerAction,
    ViewObservation,
    WindowBinding,
    heading_delta,
)
from smb3_agent.feedback_policy import (
    CameraCalibration,
    CorrectionPolicy,
    CorrectionState,
)
from smb3_agent.minecraft_camera_observation import (
    DETECTOR_VERSION,
    MinecraftCameraObserver,
)
from smb3_agent.ordinary_input import MacProfileInput
from smb3_agent.screen_host import MacSelectedWindowHost, recognize_text
from smb3_agent.host_contracts import InputCommand, InputKind
from smb3_agent.camera_readiness import READINESS_CONTRACT, acquire_readiness

from smb3_agent.paths import REPOSITORY_ROOT
ROOT = REPOSITORY_ROOT
PROFILE = ROOT / "data/private-beta/minecraft-camera-practice.json"
EVIDENCE = Path(os.environ.get('GAME_COMPANION_CAMERA_EVIDENCE',
                              str(ROOT / "artifacts/private-beta/pb7m-camera/r1")))


def profile():
    return json.loads(PROFILE.read_text())


def candidate_identity():
    files = sorted((ROOT / "src").rglob("*.py")) + sorted(
        (ROOT / "data/private-beta").glob("*.json")
    )
    hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }
    return hashlib.sha256(
        json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def environment():
    settings = settings_snapshot()
    config = profile()
    for key, expected in {
        "mouseSensitivity": "0.5",
        "invertXMouse": "false",
        "invertYMouse": "false",
        "fov": "0.0",
        "fovEffectScale": "1.0",
        "guiScale": "0",
        "fullscreen": "false",
        "forceUnicodeFont": "false",
        "key_key.smoothCamera": "key.keyboard.unknown",
    }.items():
        if settings[key] != expected:
            raise FeedbackError("Unqualified camera setting: " + key)
    return CameraEnvironment(
        config["game"],
        "Microsoft OpenJDK 25.0.1+8 LTS arm64",
        (),
        hashlib.sha256(PROFILE.read_bytes()).hexdigest(),
        settings_digest(),
        "windowed 854x508 points; native 1x/2x capture retained; exact scale2 glyph decoding",
        float(settings["mouseSensitivity"]),
        settings["invertYMouse"] == "true",
        "fresh session; smooth-camera binding unassigned",
        "raw option not exposed; explicit Cocoa event deltas tested",
        70,
        settings["fovEffectScale"],
        tuple(config["fps_range"]),
        tuple(config["pitch_range"]),
        DETECTOR_VERSION,
        NATIVE_VERSION,
        "artifacts/private-beta/pb7m-camera/r1/preparation",
    )


def binding_from(value):
    value = dict(value)
    value["bounds"], value["pixel_size"] = (
        tuple(value["bounds"]),
        tuple(value["pixel_size"]),
    )
    return WindowBinding(**value)


def require_calibration_lifetime(binding):
    """Read only identity/geometry; focus or occlusion is a readiness boundary."""
    import Quartz as q
    rows = [r for r in q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionAll, q.kCGNullWindowID) or ()
            if r.get(q.kCGWindowOwnerPID) == binding.process_id
            and str(r.get(q.kCGWindowNumber)) == binding.window_id
            and r.get(q.kCGWindowLayer) == 0]
    if len(rows) != 1:
        raise FeedbackError('Calibration process/window identity lost')
    bounds = tuple(int(rows[0][q.kCGWindowBounds][k]) for k in ('X', 'Y', 'Width', 'Height'))
    started = subprocess.run(['ps', '-p', str(binding.process_id), '-o', 'lstart='],
                             capture_output=True, text=True, timeout=1, check=True).stdout.strip()
    if bounds != binding.bounds or started != binding.process_started_at:
        raise FeedbackError('Calibration process/window geometry changed')


def frame_from(value):
    return FeedbackFrame(**{**value, "binding": binding_from(value["binding"])})


def observation_from(value):
    return ViewObservation(
        **{
            **value,
            "frame": frame_from(value["frame"]),
            "state": ReadingState(value["state"]),
            "provenance": tuple(value["provenance"]),
        }
    )


def calibration_from(value):
    env = dict(value["environment"])
    for key in ("mods", "fps_range", "pitch_range"):
        env[key] = tuple(env[key])
    samples = []
    for s in value["samples"]:
        action = RelativePointerAction(
            **{**s["action"], "frame": frame_from(s["action"]["frame"])}
        )
        samples.append(
            CalibrationSample(
                action,
                observation_from(s["before"]),
                observation_from(s["after"]),
                s["delivered_at"],
                s["delivery_reference"],
            )
        )
    return CameraCalibration(
        value["calibration_id"],
        CameraEnvironment(**env),
        binding_from(value["binding"]),
        tuple(samples),
        tuple(value["gains"]),
        value["response_error"],
        value["recheck_reference"],
    )


def activate_practice(binding):
    """Raise only the receipt's exact window; input still needs full guards."""
    import AppKit
    import ApplicationServices as ax
    import Quartz as q

    host = MacSelectedWindowHost(
        binding.process_id,
        binding.process_started_at,
        binding.window_id,
        background_observation=True,
    )
    rows = (
        q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionAll, q.kCGNullWindowID) or ()
    )
    rows = [
        r
        for r in rows
        if r.get(q.kCGWindowOwnerPID) == binding.process_id
        and str(r.get(q.kCGWindowNumber)) == binding.window_id
        and r.get(q.kCGWindowLayer) == 0
    ]
    if len(rows) != 1:
        raise FeedbackError("Approved practice window unavailable")
    app = ax.AXUIElementCreateApplication(binding.process_id)
    error, windows = ax.AXUIElementCopyAttributeValue(app, ax.kAXWindowsAttribute, None)
    if error:
        raise FeedbackError("Practice window cannot be raised safely")
    matches = []
    for w in windows or ():
        error, title = ax.AXUIElementCopyAttributeValue(w, ax.kAXTitleAttribute, None)
        if not error and title == rows[0].get(q.kCGWindowName):
            matches.append(w)
    if len(matches) != 1:
        raise FeedbackError("Ambiguous practice accessibility window")
    ax.AXUIElementSetAttributeValue(app, ax.kAXFrontmostAttribute, True)
    ax.AXUIElementPerformAction(matches[0], ax.kAXRaiseAction)
    AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(
        binding.process_id
    ).activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    # AX raising and Cocoa activation complete asynchronously. Wait once for
    # this requested activation; never reactivate against an owner/focus change.
    until = time.monotonic() + 1
    while True:
        try:
            binding.require(host.detect_window(), execution=True)
            return host
        except ValueError:
            if time.monotonic() >= until:
                raise
            time.sleep(.02)


def resume_practice(host, binding, root, cancellation):
    """Explicit Review/Start may resume a visibly paused approved practice world."""
    import Quartz as q

    if not q.CGCursorIsVisible():
        return
    w = host.detect_window()
    path = Path(root) / (uuid4().hex + "-menu.png")
    started = time.monotonic()
    host.capture(w, path)
    labels = [t.text.casefold() for t in recognize_text(path)]
    if "game menu" not in labels or not any("back to game" in t for t in labels):
        raise FeedbackError(
            "Gameplay capture unavailable; explicit menu/settings recheck required"
        )

    def authority():
        if cancellation.is_set() or time.monotonic() - started > 3:
            raise FeedbackError("Menu resume authority revoked or expired")

    def isolation(current):
        binding.require(current, execution=True)

    driver = MacProfileInput(
        window_provider=host.detect_window,
        authority_guard=authority,
        isolation_guard=isolation,
    )
    try:
        driver.arm()
        driver.send(
            InputCommand(
                InputKind.KEYBOARD,
                "escape",
                "press",
                30,
                purpose="explicit_practice_resume",
            )
        )
    finally:
        driver.neutralize()
        receipt = driver.release_receipt()
        (Path(root) / (uuid4().hex + "-menu-release.json")).write_text(
            json.dumps(receipt, indent=2) + "\n"
        )
    time.sleep(0.12)


def native_hid_receipt():
    import Quartz as q

    keys = [
        c
        for c in range(128)
        if q.CGEventSourceKeyState(q.kCGEventSourceStateHIDSystemState, c)
    ]
    buttons = [
        c
        for c in range(3)
        if q.CGEventSourceButtonState(q.kCGEventSourceStateHIDSystemState, c)
    ]
    return {
        "confirmed": not keys and not buttons,
        "held_keys": keys,
        "held_buttons": buttons,
        "method": "independent native HID state; camera emitter owns no key/button ledger",
    }


class CameraPracticeService:
    PRIORITY = frozenset({"stop", "reclaim", "edit", "chat", "disconnect", "heartbeat"})

    def __init__(self, root=EVIDENCE, *, clock=time.monotonic, native_enabled=False, engineering_sessions=False):
        self.native_enabled = native_enabled
        self.engineering_sessions = engineering_sessions
        self.window_rows = []
        self.root = Path(root)
        self.clock = clock
        self.history = PlanAttemptHistory(self.root / "history")
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.guard = None
        self.worker = None
        self.epoch = 0
        self.review = None
        self.selected = None
        self.client = None
        self.lease = 0
        self.state = "unavailable"
        self.reason = (
            "Choose the current Minecraft window and confirm a disposable Creative world. Native practice is disabled pending a short focused smoke and unresolved motion review."
        )
        self.release = None
        self.last_result = None
        self.invalid_calibrations = set()
        journal = self.root / 'invalid-calibrations.jsonl'
        if journal.exists():
            self.invalid_calibrations.update(json.loads(line)['sha256'] for line in journal.read_text().splitlines())
        self.readiness = None
        self.stage = 'idle'
        self.closed = threading.Event()
        self.watchdog = threading.Thread(target=self._watch, daemon=True)
        self.watchdog.start()

    def _receipts(self):
        path = self.root / ("approved-sessions.json" if self.engineering_sessions else "player-calibrations.json")
        return json.loads(path.read_text()) if path.exists() else []

    def _require_calibration(self, cal):
        if settings_digest() != cal.environment.controls_id:
            self._invalidate_calibration(cal, 'settings changed')
            raise ValueError(
                "Settings changed; calibration invalidated. Repeat directional measurement"
            )
        if cal.sha256 in self.invalid_calibrations:
            raise ValueError("Calibration invalidated; repeat directional measurement")
        if cal.environment != environment():
            self._invalidate_calibration(cal, 'profile/environment changed')
            raise ValueError("Profile/environment changed; recalibration required")

    def _invalidate_calibration(self, cal, reason):
        self.readiness = None
        if cal.sha256 not in self.invalid_calibrations:
            self.invalid_calibrations.add(cal.sha256)
            self.root.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.root / 'invalid-calibrations.jsonl', os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, (json.dumps({'sha256': cal.sha256, 'reason': reason, 'at': self.clock()})+'\n').encode())
            finally:
                os.close(fd)

    def snapshot(self):
        with self.lock:
            return {
                "native_enabled": self.native_enabled,
                "windows": self.window_rows,
                "experimental": True,
                "available_outside_practice": False,
                "state": self.state,
                "reason": self.reason,
                "epoch": self.epoch,
                "busy": bool(self.worker and self.worker.is_alive()),
                "stage": self.stage,
                "readiness": self.readiness,
                "sessions": [
                    {
                        "id": r["id"],
                        "world": r["world"],
                        "window_id": r["calibration"]["binding"]["window_id"],
                        "process_id": r["calibration"]["binding"]["process_id"],
                    }
                    for r in self._receipts()
                ],
                "selected": self.selected["id"] if self.selected else None,
                "review": self.review,
                "release": self.release,
                "result": self.last_result,
                "history": self.history.list(12),
            }

    def revoke(self, reason):
        # Cancellation is published before any operation/state lock.
        self.cancel.set()
        self.readiness = None
        guard = self.guard
        receipt = (
            guard.cancel()
            if guard
            else {
                "epoch_revoked": True,
                "pending_motion_revoked": True,
                "motion_worker_reaped": True,
                "seconds": 0,
                "method": "no_emitter_active",
            }
        )
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "at": self.clock(),
            "epoch": self.epoch,
            "reason": reason,
            "release": receipt,
        }
        fd = os.open(
            self.root / "control-receipts.jsonl",
            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
            0o600,
        )
        try:
            os.write(fd, (json.dumps(event) + "\n").encode())
        finally:
            os.close(fd)
        with self.lock:
            self.epoch += 1
            self.review = None
            self.release = receipt
            self.reason = reason
            if not (self.worker and self.worker.is_alive()):
                self.state = "stopped"
        return receipt

    def dispatch(self, action, payload=None):
        payload = payload or {}
        client = payload.get("client_id")
        if not isinstance(client, str) or not 1 <= len(client) <= 100:
            raise ValueError("Practice page identity is required")
        if action in self.PRIORITY:
            if self.client and client != self.client:
                raise ValueError("This practice session belongs to another page")
            if action == "heartbeat":
                self.lease = self.clock()
            else:
                self.revoke(
                    {
                        "stop": "Stopped",
                        "reclaim": "Control returned",
                        "edit": "Goal edit: review again",
                        "chat": "Chat: input stopped",
                        "disconnect": "Practice page disconnected",
                    }[action]
                )
            return self.snapshot()
        with self.lock:
            if self.closed.is_set() or (self.worker and self.worker.is_alive()):
                raise ValueError("Wait for neutral handback before new authority")
            if (
                self.client
                and self.client != client
                and self.state not in {"stopped", "unavailable"}
            ):
                raise ValueError("Take control on the owning page first")
            self.client, self.lease = client, self.clock()
            if action == "windows":
                import Quartz as q
                from smb3_agent.prepared_game import start_identity
                self.window_rows = []
                for r in q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly, 0) or ():
                    title = str(r.get(q.kCGWindowName) or "")
                    if r.get(q.kCGWindowLayer) != 0 or title != "Minecraft 26.3 - Singleplayer":
                        continue
                    pid = int(r[q.kCGWindowOwnerPID])
                    bounds = tuple(int(r[q.kCGWindowBounds][k]) for k in ('X','Y','Width','Height'))
                    self.window_rows.append({"pid":pid,"started":start_identity(pid),
                        "window_id":str(r[q.kCGWindowNumber]),"bounds":bounds,"label":title})
            elif action == "calibrate":
                if not self.native_enabled:
                    raise ValueError("Native calibration unavailable pending focused smoke and unexplained motion review")
                if payload.get("disposable_confirmation") is not True:
                    raise ValueError("Confirm a disposable Creative world before practice")
                selection = payload.get("selection")
                matches = [w for w in self.window_rows if selection and {**w, "bounds": list(w["bounds"])} == {**selection, "bounds": list(selection.get("bounds", ())) }]
                if len(matches) != 1 or tuple(selection["bounds"])[2:] != (854,508):
                    raise ValueError("Refresh and select one supported Minecraft window")
                from smb3_agent.minecraft_capture import capture_frame
                host = MacSelectedWindowHost(selection["pid"],selection["started"],selection["window_id"],background_observation=True)
                _, native_size, _ = capture_frame(host,self.root/"window-checks",execution=False)
                binding = WindowBinding(selection["pid"],selection["started"],selection["window_id"],tuple(selection["bounds"]),native_size)
                self.cancel = threading.Event()
                self.epoch += 1
                self.state = "executing"
                self.worker = threading.Thread(target=self._calibrate, args=(binding,self.epoch,self.cancel),daemon=True)
                self.worker.start()
            elif action == "connect":
                self.revoke("New practice connection; review required")
                matches = [
                    r for r in self._receipts() if r["id"] == payload.get("session_id")
                ]
                if len(matches) != 1:
                    raise ValueError(
                        "No sealed disposable-world receipt for this selection"
                    )
                selected = matches[0]
                if selected.get("source") != "player_setup" and selected["candidate"] != candidate_identity():
                    raise ValueError(
                        "Candidate changed; session seal must be rebuilt before practice"
                    )
                cal = calibration_from(selected["calibration"])
                if cal.sha256 in self.invalid_calibrations:
                    raise ValueError(
                        "Calibration invalidated; repeat directional measurement"
                    )
                self._require_calibration(cal)
                # Validate process identity without taking focus or entering a world.
                cal.binding.require(
                    MacSelectedWindowHost(
                        cal.binding.process_id,
                        cal.binding.process_started_at,
                        cal.binding.window_id,
                        background_observation=True,
                    ).detect_window(require_foreground=False)
                )
                self.selected, self.state = selected, "connected"
                self.reason = "Disposable Creative practice selected. Review the typed camera goal."
            elif action == "review":
                if not self.engineering_sessions:
                    raise ValueError("Use the integrated Minecraft workspace for ordinary Review/Start")
                from smb3_agent.minecraft_session import CHECKED_FEATURES
                if not CHECKED_FEATURES["camera"]:
                    raise ValueError("Use the integrated workspace; camera gameplay check is pending")
                if not self.native_enabled:
                    raise ValueError("Native camera practice unavailable pending focused smoke and unexplained motion review")
                if not self.selected:
                    raise ValueError("Connect a prepared practice session first")
                cal = calibration_from(self.selected["calibration"])
                if cal.sha256 in self.invalid_calibrations:
                    raise ValueError(
                        "Calibration invalidated; repeat directional measurement"
                    )
                self._require_calibration(cal)
                goal = CorrectionGoal(
                    float(payload["heading"]),
                    float(payload["pitch"]),
                    **profile()["goal"],
                )
                self.cancel = threading.Event()
                self.epoch += 1
                root = self.root / "reviews" / uuid4().hex
                root.mkdir(parents=True)
                host = activate_practice(cal.binding)
                resume_practice(host, cal.binding, root, self.cancel)
                obs = MinecraftCameraObserver(
                    host, cal.environment, cal.calibration_id, root
                ).observe(execution=True)
                CorrectionPolicy(cal, goal, obs, epoch=self.epoch, now=self.clock())
                self.review = {
                    "goal": asdict(goal),
                    "epoch": self.epoch,
                    "created_at": self.clock(),
                    "initial": asdict(obs),
                    "calibration_sha256": cal.sha256,
                    "readiness_preparation": dict(READINESS_CONTRACT),
                }
                self.state, self.reason = (
                    "reviewed",
                    "Reviewed: Start first prepares capture with up to two four-unit yaw probes (up to 1.2°); then corrects the absolute goal. Preparation rotation is retained separately.",
                )
            elif action == "start":
                if (
                    not self.review
                    or self.review["epoch"] != self.epoch
                    or self.clock() - self.review["created_at"] > 30
                    or self.review.get('readiness_preparation') != READINESS_CONTRACT
                ):
                    raise ValueError("Review again before Start")
                if not self.native_enabled:
                    raise ValueError("Native camera Start unavailable pending focused smoke and unexplained motion review")
                self.cancel = threading.Event()
                reviewed = self.review
                self.review = None
                self.state, self.reason = (
                    "executing",
                    "Preparing reviewed camera capture; Stop and Take control remain direct.",
                )
                self.worker = threading.Thread(
                    target=self._run,
                    args=(reviewed, self.epoch, self.cancel),
                    daemon=True,
                )
                self.worker.start()
            else:
                raise ValueError("Unknown camera practice action")
        return self.snapshot()

    def _calibrate(self, binding, epoch, cancel):
        from smb3_agent.player_calibration import measure_camera
        try:
            env = environment()
            def verify_creative(host, binding, folder, cancellation):
                from smb3_agent.minecraft_inventory import inspect_creative
                from smb3_agent.minecraft_native import InventoryInputOwner
                return inspect_creative(host, binding, folder, cancellation,
                    publish_driver=lambda driver: publish(InventoryInputOwner(driver)))[1]
            def publish(guard):
                self.guard = guard
                if cancel.is_set() or epoch != self.epoch:
                    guard.cancel()
                    raise FeedbackError("Calibration canceled while arming")
            cal = measure_camera(binding=binding, environment=env, epoch=epoch,
                canceled=cancel, root=self.root/"calibrations"/uuid4().hex,
                publish_guard=publish, activate=activate_practice, resume=resume_practice,
                neutral_receipt=native_hid_receipt, clock=self.clock, verify_creative=verify_creative)
            if cancel.is_set() or epoch != self.epoch:
                raise FeedbackError("Calibration canceled before saving")
            # Calibration data is session evidence, never restored Start authority.
            value = {"id":uuid4().hex,"world":"Disposable practice; visible Creative inventory verified",
                     "candidate":candidate_identity(),"source":"player_setup","calibration":asdict(cal)}
            path = self.root/"player-calibrations.json"
            rows = self._receipts()
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(rows+[value],indent=2)+'\n')
            temp.replace(path)
            self.reason = "Directional calibration saved. Connect and review a fresh camera goal."
            self.state = "stopped"
        except Exception as exc:
            self.reason, self.state = str(exc), "partial"
        finally:
            if self.guard:
                self.release = self.guard.cancel()
            self.guard = None

    def _run(self, reviewed, epoch, cancel):
        attempt = uuid4().hex
        root = self.root / "runs" / attempt
        root.mkdir(parents=True)
        cal = calibration_from(self.selected["calibration"])
        goal = CorrectionGoal(**reviewed["goal"])
        record = {
            "evidence_class": "live_selected_window_camera",
            "session_id": self.selected["id"],
            "review": reviewed,
            "epoch": epoch,
            "steps": [],
            "candidate": self.selected["candidate"],
        }
        policy = observer = guard = None
        status = "partial"
        try:
            self._require_calibration(cal)
            if cancel.is_set() or (self.selected.get("source") != "player_setup" and self.selected["candidate"] != candidate_identity()):
                raise FeedbackError("Start authority canceled or settings changed")
            host = activate_practice(cal.binding)
            resume_practice(host, cal.binding, root, cancel)
            observer = MinecraftCameraObserver(
                host, cal.environment, cal.calibration_id, root / "frames"
            )
            self.stage = 'readiness_preparation'
            def publish_guard(preparation_guard):
                with self.lock:
                    if cancel.is_set() or epoch != self.epoch:
                        preparation_guard.cancel()
                        raise FeedbackError('Readiness authority revoked while arming')
                    self.guard = preparation_guard
            record['readiness_preparation'] = acquire_readiness(
                observer, cal.binding, cal.environment.controls_id, epoch, cancel,
                root/'readiness', publish_guard=publish_guard,
                neutral_receipt=native_hid_receipt,
                feedback_identity=(cal.environment.sha256, cal.calibration_id),
            )
            with self.lock:
                if cancel.is_set() or epoch != self.epoch:
                    raise FeedbackError('Canceled after readiness preparation')
                self.readiness = {'epoch': epoch, 'candidate': self.selected['candidate'],
                                  'evidence': str(root/'readiness/attempt.json'),
                                  'reusable': False}
                self.guard = None
                self.stage = 'correction'
            guard = CameraMotionGuard(
                cal.binding, epoch, cal.environment.controls_id, root
            )
            with self.lock:
                if cancel.is_set() or epoch != self.epoch:
                    guard.cancel()
                    raise FeedbackError("Canceled while guardian was arming")
                self.guard = guard
            initial = observer.observe(execution=True)
            policy = CorrectionPolicy(cal, goal, initial, epoch=epoch, now=self.clock())
            record["initial"] = asdict(initial)
            while policy.state is CorrectionState.READY:
                if cancel.is_set() or epoch != self.epoch:
                    raise FeedbackError("Direct control revoked correction")
                error = (
                    heading_delta(goal.heading, policy.last.heading),
                    goal.pitch - policy.last.pitch,
                )
                axis = 0 if abs(error[0]) >= abs(error[1]) else 1
                units = max(
                    1, min(profile()["max_pulse_units"], round(abs(error[axis]) / 0.15))
                )
                units *= 1 if error[axis] > 0 else -1
                now = self.clock()
                action = policy.propose(
                    units if axis == 0 else 0,
                    units if axis == 1 else 0,
                    profile()["pulse_ms"],
                    now=now,
                    epoch=epoch,
                    settings_sha256=environment().sha256,
                )
                step = {"action": asdict(action)}
                record["steps"].append(step)
                receipt = guard.pulse(action)
                step["delivery"] = receipt
                policy.delivered(action, at=receipt["delivered_at"], epoch=epoch)
                if cancel.wait(
                    max(
                        0,
                        receipt["delivered_at"]
                        + action.duration_ms / 1000
                        - self.clock(),
                    )
                    + 0.02
                ):
                    raise FeedbackError("Canceled while waiting for visible response")
                after = observer.observe(execution=True)
                step["after"], step["timing"] = asdict(after), observer.last_timing
                policy.observe(
                    after,
                    now=self.clock(),
                    epoch=epoch,
                    settings_sha256=environment().sha256,
                )
        except Exception as exc:
            record["error"] = str(exc)
            if policy:
                policy.cancel(str(exc))
        finally:
            release = (
                guard.cancel()
                if guard
                else {
                    "motion_worker_reaped": True,
                    "pending_motion_revoked": True,
                    "epoch_revoked": True,
                    "seconds": 0,
                }
            )
            canceled_at = self.clock()
            record["release"] = release
            # Independently check native HID neutrality, without sending any world input.
            try:
                neutral = native_hid_receipt()
                record["hid_release"] = neutral
                hid = neutral["confirmed"]
            except Exception as exc:
                record["hid_error"], hid = str(exc), False
            handback = None
            if observer:
                try:
                    first = observer.observe(execution=True)
                    time.sleep(goal.settling_seconds)
                    last = observer.observe(execution=True)
                    handback = NeutralHandback(
                        hid,
                        release["epoch_revoked"],
                        release["pending_motion_revoked"],
                        canceled_at,
                        first,
                        last,
                    )
                    record["handback"] = asdict(handback)
                except Exception as exc:
                    record["settling_error"] = str(exc)
            result = (
                policy.result(handback, now=self.clock())
                if policy
                else {"status": "partial", "neutral_handback_confirmed": False}
            )
            result["evidence_class"] = "live_selected_window_camera"
            preparation_path = root/'readiness/attempt.json'
            if preparation_path.exists():
                preparation = json.loads(preparation_path.read_text())
                result['readiness_preparation'] = {
                    'ready': preparation['ready'],
                    'pulses': len(preparation['steps']),
                    'observed_rotation': preparation.get('observed_preparation_rotation'),
                    'evidence_path': str(preparation_path),
                    'class': 'readiness_preparation_only',
                }
            if record.get("error"):
                result["reason"] = record["error"]
            status = result["status"]
            record["result"] = result
            (root / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
            outcome = SessionOutcome(
                True,
                "Reviewed camera heading/pitch",
                f"{len(record['steps'])} relative camera pulses",
                "No world resources consumed",
                status,
                ""
                if result["neutral_handback_confirmed"]
                else "Visible settling or HID release unconfirmed",
                None,
                (str(root / "attempt.json"),),
            )
            saved = self.history.record(
                attempt, {**record, "outcome": asdict(outcome), "status": status}
            )
            with self.lock:
                self.guard = None
                self.readiness = None
                self.stage = 'idle'
                self.release = release
                self.last_result = {**result, "evidence_path": str(saved)}
                self.state = status
                self.reason = (
                    result.get("reason")
                    or "Camera outcome retained; Review again for another goal."
                )

    def _watch(self):
        while not self.closed.wait(0.15):
            if self.state == 'executing' and not self.cancel.is_set() and self.clock() - self.lease > 3:
                self.revoke('Practice page lease expired')
            if not self.selected:
                continue
            try:
                cal = calibration_from(self.selected['calibration'])
                self._require_calibration(cal)
                try:
                    require_calibration_lifetime(cal.binding)
                except Exception:
                    self._invalidate_calibration(cal, 'process/window/geometry transition')
                    raise
                if self.state != 'executing' or self.cancel.is_set():
                    continue
                if self.clock() - self.lease > 3:
                    raise FeedbackError("Practice page lease expired")
                if self.guard:
                    self.guard.binding.require(
                        MacSelectedWindowHost(
                            self.guard.binding.process_id,
                            self.guard.binding.process_started_at,
                            self.guard.binding.window_id,
                        ).detect_window(),
                        execution=True,
                    )
                    if (
                        settings_digest()
                        != self.selected["calibration"]["environment"]["controls_id"]
                    ):
                        self._invalidate_calibration(cal, 'settings changed during operation')
                        raise FeedbackError("Settings changed; recalibration required")
                    import Quartz as q
                    if q.CGCursorIsVisible():
                        raise FeedbackError('Menu/capture transition revoked readiness; review preparation again')
            except Exception as exc:
                if not self.cancel.is_set():
                    self.revoke(str(exc))

    def close(self):
        self.closed.set()
        self.revoke("Companion shutdown")
        if self.worker:
            self.worker.join(3)
        self.watchdog.join(0.3)
