"""App-created, bounded calibration; called only by explicit practice Start."""

from dataclasses import asdict
import json
from pathlib import Path
import time
from uuid import uuid4

from smb3_agent.camera_native_input import CameraMotionGuard
from smb3_agent.camera_readiness import acquire_readiness
from smb3_agent.feedback_contracts import (
    CalibrationSample,
    RelativePointerAction,
    FeedbackError,
)
from smb3_agent.feedback_policy import CameraCalibration
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver


def measure_camera(
    *,
    binding,
    environment,
    epoch,
    canceled,
    root,
    publish_guard,
    activate,
    resume,
    neutral_receipt,
    clock=time.monotonic,
    verify_creative=None,
):
    """Eight finite directional measurements, separate preparation and settling.

    This is calibration, never campaign qualification or a gameplay success claim.
    Failure preserves the attempted measurements and emits no reusable calibration.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    record = {
        "schema": "player-camera-calibration/v1",
        "accepted": False,
        "samples": [],
        "environment": asdict(environment),
    }
    calibration_id = uuid4().hex
    guard = None
    deadline = clock() + 90
    try:
        host = activate(binding)
        resume(host, binding, root, canceled)
        if verify_creative is not None:
            record["creative_inspection"] = verify_creative(
                host, binding, root / "creative", canceled
            )
        observer = MinecraftCameraObserver(
            host, environment, calibration_id, root / "frames"
        )
        record["readiness"] = acquire_readiness(
            observer,
            binding,
            environment.controls_id,
            epoch,
            canceled,
            root / "readiness",
            publish_guard=publish_guard,
            neutral_receipt=neutral_receipt,
            feedback_identity=(environment.sha256, calibration_id),
        )
        samples = []
        for dx, dy in (
            (4, 0),
            (12, 0),
            (-4, 0),
            (-12, 0),
            (0, 4),
            (0, 12),
            (0, -4),
            (0, -12),
        ):
            if canceled.is_set() or clock() >= deadline:
                raise FeedbackError(
                    "Calibration canceled or 90-second budget exhausted"
                )
            folder = root / "samples" / uuid4().hex
            guard = CameraMotionGuard(binding, epoch, environment.controls_id, folder)
            publish_guard(guard)
            before = observer.observe(execution=True)
            before.require(clock(), 0.8, 0.1)
            now = clock()
            action = RelativePointerAction(
                dx, dy, 120, now, now + 0.12, epoch, before.frame
            )
            row = {"action": asdict(action), "before": asdict(before)}
            record["samples"].append(row)
            delivery = guard.pulse(action)
            row["delivery"] = delivery
            if canceled.wait(0.14):
                raise FeedbackError("Calibration canceled after pulse")
            after = observer.observe(execution=True)
            after.require(clock(), 0.8, 0.1)
            row["after"] = asdict(after)
            sample = CalibrationSample(
                action,
                before,
                after,
                delivery["delivered_at"],
                str(folder / "native-motion.jsonl"),
            )
            samples.append(sample)
            row["release"] = guard.cancel()
            first = observer.observe(execution=True)
            if canceled.wait(0.2):
                raise FeedbackError("Calibration canceled while checking settling")
            last = observer.observe(execution=True)
            row["settling"] = [asdict(first), asdict(last)]
            if (
                abs(last.heading - first.heading) > 0.1
                or abs(last.pitch - first.pitch) > 0.1
                or not neutral_receipt()["confirmed"]
            ):
                raise FeedbackError(
                    "Visible motion did not settle; calibration rejected"
                )
        groups = [[], [], [], []]
        for s in samples:
            a = s.action
            i = (0 if a.dx > 0 else 1) if a.dx else (2 if a.dy > 0 else 3)
            groups[i].append(s.response[0 if a.dx else 1] / (a.dx or a.dy))
        gains = tuple(sum(g) / len(g) for g in groups)
        calibration = CameraCalibration(
            calibration_id,
            environment,
            binding,
            tuple(samples),
            gains,
            0.2,
            str(root / "attempt.json"),
        )
        record.update(
            accepted=True,
            calibration=asdict(calibration),
            calibration_sha256=calibration.sha256,
        )
        return calibration
    except Exception as exc:
        record["reason"] = str(exc)
        raise
    finally:
        if guard:
            record["release"] = guard.cancel()
        (root / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
