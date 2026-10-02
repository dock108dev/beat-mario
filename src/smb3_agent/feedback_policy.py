"""Game-neutral, synchronous correction policy; no OS input or model calls.

An engineering caller must supply its own independent native protection and
ordinary review/Start authority. This module is deliberately not registered as
an executable profile skill. Every pulse consumes budget before dispatch.
"""
from dataclasses import dataclass
from enum import Enum

from smb3_agent.feedback_contracts import (
    CalibrationSample, CameraEnvironment, CorrectionGoal, FeedbackError,
    NeutralHandback, RelativePointerAction, ViewObservation, WindowBinding,
    digest, finite, heading_delta, identity,
)


@dataclass(frozen=True)
class CameraCalibration:
    calibration_id: str
    environment: CameraEnvironment
    binding: WindowBinding
    samples: tuple[CalibrationSample, ...]
    # Signed degrees per input unit, separately measured in each direction.
    gains: tuple[float, float, float, float]  # +x, -x, +y, -y
    response_error: float
    recheck_reference: str
    version: str = "camera-calibration/v1"

    def __post_init__(self):
        if (self.version != "camera-calibration/v1" or not identity(self.calibration_id)
                or not isinstance(self.environment, CameraEnvironment)
                or not isinstance(self.binding, WindowBinding)
                or not identity(self.recheck_reference) or type(self.samples) is not tuple
                or not 8 <= len(self.samples) <= 128 or type(self.gains) is not tuple
                or len(self.gains) != 4 or not all(finite(v, -10, 10) and v != 0 for v in self.gains)
                or self.gains[0]*self.gains[1] <= 0 or self.gains[2]*self.gains[3] <= 0
                or not finite(self.response_error, 0, 5)):
            raise FeedbackError("Invalid evidence-bound calibration")
        directions = [0, 0, 0, 0]
        frames = set()
        for sample in self.samples:
            if not isinstance(sample, CalibrationSample):
                raise FeedbackError("Invalid calibration sample")
            action = sample.action
            if (action.frame.binding != self.binding
                    or action.frame.settings_sha256 != self.environment.sha256
                    or action.frame.calibration_id != self.calibration_id
                    or bool(action.dx) == bool(action.dy)):
                raise FeedbackError("Calibration binding or isolated axis mismatch")
            index = (0 if action.dx > 0 else 1) if action.dx else (2 if action.dy > 0 else 3)
            directions[index] += 1
            response = sample.response
            expected = (action.dx*self.gains[index], 0) if action.dx else (0, action.dy*self.gains[index])
            uncertainty = sample.before.uncertainty_degrees+sample.after.uncertainty_degrees
            if max(abs(a-b) for a, b in zip(response, expected)) > self.response_error+uncertainty:
                raise FeedbackError("Contradictory directional calibration")
            for obs in (sample.before, sample.after):
                if obs.frame.frame_id in frames:
                    raise FeedbackError("Calibration observations reused")
                frames.add(obs.frame.frame_id)
                obs.require(obs.grounded_at, 3, self.response_error)
                if not self.environment.pitch_range[0] <= obs.pitch <= self.environment.pitch_range[1]:
                    raise FeedbackError("Calibration pitch outside environment")
        if min(directions) < 2:
            raise FeedbackError("Both axes need repeated directional evidence")

    @property
    def sha256(self):
        return digest(self)


class CorrectionState(str, Enum):
    READY = "ready"
    AWAITING_OBSERVATION = "awaiting_observation"
    TARGET_OBSERVED = "target_observed"
    PARTIAL = "partial"
    CONTRADICTORY = "contradictory"


class CorrectionPolicy:
    """One reviewed goal, no blind queue, no restored authority after a fault."""

    def __init__(self, calibration: CameraCalibration, goal: CorrectionGoal,
                 initial: ViewObservation, *, epoch: int, now: float):
        if (not isinstance(calibration, CameraCalibration) or not isinstance(goal, CorrectionGoal)
                or type(epoch) is not int or epoch < 0 or not finite(now, 0, 1e12)
                or not calibration.environment.pitch_range[0] <= goal.pitch <= calibration.environment.pitch_range[1]):
            raise FeedbackError("Invalid correction boundary")
        self.calibration, self.goal, self.epoch = calibration, goal, epoch
        self.started_at, self.last = now, initial
        self.state, self.reason = CorrectionState.READY, ""
        self.iterations = self.displacement = self.input_ms = 0
        self.pending = self.delivered_at = None
        self.seen_frames = {initial.frame.frame_id}
        self._require(initial, now, calibration.environment.sha256)
        if self.at_target(initial):
            self.state = CorrectionState.TARGET_OBSERVED

    def at_target(self, observation):
        error = max(abs(heading_delta(self.goal.heading, observation.heading)),
                    abs(self.goal.pitch-observation.pitch))
        return error+observation.uncertainty_degrees <= self.goal.tolerance

    def _require(self, observation, now, settings_sha256):
        calibration = self.calibration
        if (settings_sha256 != calibration.environment.sha256
                or observation.frame.settings_sha256 != settings_sha256
                or observation.frame.binding != calibration.binding
                or observation.frame.calibration_id != calibration.calibration_id):
            raise FeedbackError("Settings/window/calibration changed; recalibration required")
        if not finite(now-self.started_at, 0, self.goal.total_seconds):
            raise FeedbackError("Total correction time exhausted")
        observation.require(now, self.goal.frame_max_age, self.goal.max_uncertainty)
        if not calibration.environment.pitch_range[0] <= observation.pitch <= calibration.environment.pitch_range[1]:
            raise FeedbackError("Observed pitch outside environment")

    def cancel(self, reason="canceled", *, contradictory=False):
        self.epoch += 1
        self.pending = self.delivered_at = None
        self.state = CorrectionState.CONTRADICTORY if contradictory else CorrectionState.PARTIAL
        self.reason = reason
        # Native callers must separately revoke queued emission and measure
        # settling. Clearing this policy's request cannot retract OS events.

    def propose(self, dx, dy, duration_ms, *, now, epoch, settings_sha256):
        if self.state is not CorrectionState.READY or epoch != self.epoch:
            raise FeedbackError("No current correction authority or observation pending")
        try:
            self._require(self.last, now, settings_sha256)
            if bool(dx) == bool(dy):
                raise FeedbackError("Correct one independently calibrated axis per pulse")
            action = RelativePointerAction(dx, dy, duration_ms, now,
                                           now+duration_ms/1000, epoch, self.last.frame)
            gain = self.calibration.gains[(0 if dx > 0 else 1) if dx else (2 if dy > 0 else 3)]
            predicted = (dx or dy)*gain
            error = heading_delta(self.goal.heading, self.last.heading) if dx else self.goal.pitch-self.last.pitch
            if error*predicted <= 0 or abs(predicted) > abs(error)+self.goal.max_overshoot:
                raise FeedbackError("Pulse moves away from goal or risks excess overshoot")
            if (self.iterations+1 > self.goal.max_iterations
                    or self.displacement+abs(dx)+abs(dy) > self.goal.total_displacement
                    or self.input_ms+duration_ms > self.goal.total_input_ms
                    or now+duration_ms/1000 > self.started_at+self.goal.total_seconds):
                raise FeedbackError("Finite correction budget exhausted")
        except FeedbackError as exc:
            self.cancel(str(exc))
            raise
        self.iterations += 1
        self.displacement += abs(dx)+abs(dy)
        self.input_ms += duration_ms
        self.pending, self.state = action, CorrectionState.AWAITING_OBSERVATION
        return action

    def refresh(self, observation, *, now, epoch, settings_sha256):
        """Re-ground a settled view before the next pulse; never reuse old pixels."""
        if self.state not in {CorrectionState.READY, CorrectionState.TARGET_OBSERVED} or epoch != self.epoch:
            raise FeedbackError("Fresh view cannot restore pending or canceled authority")
        self._require(observation, now, settings_sha256)
        if observation.frame.frame_id in self.seen_frames or observation.frame.captured_at <= self.last.frame.captured_at:
            raise FeedbackError("A new pre-pulse frame is required")
        residual = max(abs(heading_delta(observation.heading, self.last.heading)), abs(observation.pitch-self.last.pitch))
        if residual > self.last.uncertainty_degrees + observation.uncertainty_degrees:
            self.cancel("Unexplained view change between pulses", contradictory=True)
            raise FeedbackError(self.reason)
        self.last = observation
        self.seen_frames.add(observation.frame.frame_id)
        self.state = CorrectionState.TARGET_OBSERVED if self.at_target(observation) else CorrectionState.READY

    def delivered(self, action, *, at, epoch):
        if (self.state is not CorrectionState.AWAITING_OBSERVATION or self.pending != action
                or self.delivered_at is not None or epoch != self.epoch
                or not finite(at, action.issued_at, action.deadline)):
            raise FeedbackError("Late, duplicate or canceled delivery receipt")
        self.delivered_at = at

    def observe(self, observation, *, now, epoch, settings_sha256):
        if self.state is not CorrectionState.AWAITING_OBSERVATION or epoch != self.epoch:
            raise FeedbackError("Observation cannot restore old correction authority")
        try:
            self._require(observation, now, settings_sha256)
            action = self.pending
            if (self.delivered_at is None or observation.frame.frame_id in self.seen_frames
                    or observation.frame.captured_at <= max(action.deadline,
                        self.delivered_at+action.duration_ms/1000)):
                raise FeedbackError("Fresh post-pulse observation required")
            measured = (heading_delta(observation.heading, self.last.heading), observation.pitch-self.last.pitch)
            index = (0 if action.dx > 0 else 1) if action.dx else (2 if action.dy > 0 else 3)
            gain = self.calibration.gains[index]
            predicted = (action.dx*gain, 0) if action.dx else (0, action.dy*gain)
            uncertainty = self.last.uncertainty_degrees+observation.uncertainty_degrees
            if max(abs(a-b) for a, b in zip(measured, predicted)) > self.calibration.response_error+uncertainty:
                self.cancel("Contradictory camera response", contradictory=True)
                raise FeedbackError(self.reason)
            before = (heading_delta(self.goal.heading, self.last.heading), self.goal.pitch-self.last.pitch)
            after = (heading_delta(self.goal.heading, observation.heading), self.goal.pitch-observation.pitch)
            if any(a*b < 0 and abs(b)+uncertainty > self.goal.max_overshoot for a, b in zip(before, after)):
                self.cancel("Observed excess overshoot", contradictory=True)
                raise FeedbackError(self.reason)
        except FeedbackError as exc:
            if self.state is not CorrectionState.CONTRADICTORY:
                self.cancel(str(exc))
            raise
        self.last = observation
        self.seen_frames.add(observation.frame.frame_id)
        self.pending = self.delivered_at = None
        self.state = CorrectionState.TARGET_OBSERVED if self.at_target(observation) else CorrectionState.READY

    def result(self, handback: NeutralHandback, *, now):
        """Only independent stable final evidence permits verified completion."""
        confirmed = (isinstance(handback, NeutralHandback) and handback.settled(self.goal)
                     and handback.first.frame.binding == self.calibration.binding
                     and handback.first.frame.settings_sha256 == self.calibration.environment.sha256
                     and handback.first.frame.calibration_id == self.calibration.calibration_id
                     and handback.canceled_at >= self.last.frame.captured_at
                     and handback.first.frame.captured_at > self.last.frame.captured_at)
        if confirmed:
            try:
                self._require(handback.last, now, self.calibration.environment.sha256)
            except FeedbackError:
                confirmed = False
        completed = (confirmed and self.state is CorrectionState.TARGET_OBSERVED
                     and self.at_target(handback.last))
        return {"version": "camera-correction-result/v1",
                "status": "verified_completion" if completed else self.state.value,
                "neutral_handback_confirmed": confirmed,
                "last_observed_heading": self.last.heading, "last_observed_pitch": self.last.pitch,
                "iterations": self.iterations, "reserved_displacement": self.displacement,
                "reserved_input_ms": self.input_ms, "reason": self.reason,
                "sampled_residual_view_change": handback.residual_view_change
                    if isinstance(handback, NeutralHandback) else None,
                "final_frame_id": handback.last.frame.frame_id
                    if isinstance(handback, NeutralHandback) and isinstance(handback.last, ViewObservation) else None,
                "calibration_sha256": self.calibration.sha256,
                "evidence_class": "caller_supplied_observations"}
