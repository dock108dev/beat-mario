"""Calibrated camera/aim provider for the shared finite skill executor."""

import time

from smb3_agent.feedback_contracts import CorrectionGoal, FeedbackError, heading_delta
from smb3_agent.feedback_policy import CorrectionPolicy, CorrectionState


class MinecraftCameraSkill:
    def __init__(self, calibration, epoch, *, clock=time.monotonic):
        self.calibration, self.epoch, self.clock = calibration, epoch, clock
        self.policy = None

    def validate(self, skill, parameters):
        if skill not in {"camera", "aim"} or set(parameters) != {"heading", "pitch"}:
            raise FeedbackError("Review one heading and pitch goal")
        goal = CorrectionGoal(
            parameters["heading"],
            parameters["pitch"],
            0.35,
            0.1,
            0.5,
            12,
            192,
            1440,
            12,
            0.8,
            0.2,
        )
        if not -90 <= goal.pitch <= 90:
            raise FeedbackError("Pitch must be between -90 and 90")
        self.goal = goal
        self.policy = None

    def require_fresh(self, observation, now):
        cal = self.calibration
        if (
            observation.frame.binding != cal.binding
            or observation.frame.settings_sha256 != cal.environment.sha256
            or observation.frame.calibration_id != cal.calibration_id
        ):
            raise FeedbackError("Camera settings/window/calibration changed")
        observation.require(now, 0.8, 0.1)

    def next(self, skill, parameters, observation, result):
        if self.policy is None:
            self.policy = CorrectionPolicy(
                self.calibration,
                self.goal,
                observation,
                epoch=self.epoch,
                now=self.clock(),
            )
        else:
            self.policy.refresh(
                observation,
                now=self.clock(),
                epoch=self.epoch,
                settings_sha256=self.calibration.environment.sha256,
            )
        if self.policy.state is CorrectionState.TARGET_OBSERVED:
            result["completed"] = [
                {"heading": observation.heading, "pitch": observation.pitch}
            ]
            return None
        errors = (
            heading_delta(self.goal.heading, observation.heading),
            self.goal.pitch - observation.pitch,
        )
        axis = 0 if abs(errors[0]) >= abs(errors[1]) else 1
        error = errors[axis]
        candidates = []
        for index in (0, 1) if axis == 0 else (2, 3):
            gain = self.calibration.gains[index]
            units = max(-64, min(64, round(error / gain)))
            if (units > 0) != (index in (0, 2)) or not units:
                continue
            predicted = units * gain
            if (
                error * predicted > 0
                and abs(predicted) <= abs(error) + self.goal.max_overshoot
            ):
                candidates.append((abs(error - predicted), units))
        if not candidates:
            raise FeedbackError("Goal cannot be resolved within calibrated precision")
        units = min(candidates)[1]
        return self.policy.propose(
            units if axis == 0 else 0,
            units if axis == 1 else 0,
            120,
            now=self.clock(),
            epoch=self.epoch,
            settings_sha256=self.calibration.environment.sha256,
        )

    def reconcile(self, skill, parameters, before, after, result):
        delivery = result["steps"][-1].get("delivery")
        if not isinstance(delivery, dict) or "delivered_at" not in delivery:
            raise FeedbackError("Native motion receipt missing; outcome unverified")
        self.policy.delivered(
            result["steps"][-1]["command"],
            at=delivery["delivered_at"],
            epoch=self.epoch,
        )
        self.policy.observe(
            after,
            now=self.clock(),
            epoch=self.epoch,
            settings_sha256=self.calibration.environment.sha256,
        )
        if self.complete(skill, parameters, result):
            result["completed"] = [{"heading": after.heading, "pitch": after.pitch}]

    def complete(self, skill, parameters, result):
        return (
            self.policy is not None
            and self.policy.state is CorrectionState.TARGET_OBSERVED
        )
