"""PB3 feedback evidence contracts. Validation does not grant input authority.

Detectors own interpretation; policy consumes bounded observations. Native
posting, model confidence and HID release cannot establish camera outcomes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
import re

from smb3_agent.coordinate_contracts import WindowCoordinates
from smb3_agent.host_contracts import HostError, WindowObservation
from smb3_agent.screen_host import Frame


class FeedbackError(HostError):
    pass


def finite(value, low, high):
    return type(value) in {int, float} and math.isfinite(value) and low <= value <= high


def identity(value):
    return isinstance(value, str) and 0 < len(value) <= 256


def digest(value):
    return hashlib.sha256(json.dumps(asdict(value), sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def heading_delta(target, current):
    """Signed shortest turn; a half-turn is ambiguous and must be refused."""
    if not all(finite(v, -180, 180) for v in (target, current)):
        raise FeedbackError("Invalid heading")
    delta = (target-current+180) % 360-180
    if abs(delta) == 180:
        raise FeedbackError("Ambiguous half-turn")
    return delta


@dataclass(frozen=True)
class WindowBinding:
    process_id: int
    process_started_at: str
    window_id: str
    bounds: tuple[int, int, int, int]
    pixel_size: tuple[int, int]

    def __post_init__(self):
        if (type(self.process_id) is not int or self.process_id <= 0
                or not all(identity(v) for v in (self.process_started_at, self.window_id))
                or type(self.bounds) is not tuple or type(self.pixel_size) is not tuple
                or len(self.pixel_size) != 2 or any(type(v) is not int for v in self.pixel_size)):
            raise FeedbackError("Invalid exact window binding")
        WindowCoordinates(self.bounds, self.pixel_size).validate()

    def require(self, window: WindowObservation, *, execution=False):
        if (not (window.trusted if execution else window.observable)
                or (window.process_id, window.process_started_at, window.window_id, window.bounds)
                != (self.process_id, self.process_started_at, self.window_id, self.bounds)):
            raise FeedbackError("Selected process/window/focus/geometry unavailable")


@dataclass(frozen=True)
class CameraEnvironment:
    game_build: str
    runtime: str
    mods: tuple[str, ...]
    profile_sha256: str
    controls_id: str
    display_mode: str
    sensitivity: float
    inverted: bool
    smoothing: str
    raw_input: str
    fov: float
    dynamic_fov: str
    fps_range: tuple[float, float]
    pitch_range: tuple[float, float]
    observation_method: str
    native_input_version: str
    confirmation_reference: str
    version: str = "camera-environment/v1"

    def __post_init__(self):
        strings = (self.game_build, self.runtime, self.controls_id, self.display_mode,
                   self.smoothing, self.raw_input, self.dynamic_fov,
                   self.observation_method, self.native_input_version, self.confirmation_reference)
        if (self.version != "camera-environment/v1" or not all(identity(v) for v in strings)
                or any(v.casefold() in {"unknown", "unavailable"} for v in strings)
                or not isinstance(self.profile_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", self.profile_sha256)
                or type(self.mods) is not tuple or len(self.mods) > 64
                or not all(identity(v) for v in self.mods)
                or type(self.inverted) is not bool or not finite(self.sensitivity, 0, 100)
                or not finite(self.fov, 1, 179)
                or type(self.fps_range) is not tuple or len(self.fps_range) != 2
                or not all(finite(v, 1, 1000) for v in self.fps_range)
                or self.fps_range[0] > self.fps_range[1]
                or type(self.pitch_range) is not tuple or len(self.pitch_range) != 2
                or not all(finite(v, -180, 180) for v in self.pitch_range)
                or self.pitch_range[0] >= self.pitch_range[1]):
            raise FeedbackError("Unknown or malformed camera compatibility")

    @property
    def sha256(self):
        return digest(self)


@dataclass(frozen=True)
class FeedbackFrame:
    frame_id: str
    captured_at: float
    sha256: str
    binding: WindowBinding
    settings_sha256: str
    calibration_id: str
    evidence_reference: str
    version: str = "feedback-frame/v1"

    def __post_init__(self):
        if (self.version != "feedback-frame/v1" or not isinstance(self.binding, WindowBinding)
                or not all(identity(v) for v in (self.frame_id, self.calibration_id, self.evidence_reference))
                or not all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                           for v in (self.sha256, self.settings_sha256))
                or not finite(self.captured_at, 0, 1e12)):
            raise FeedbackError("Invalid immutable feedback frame")

    @classmethod
    def from_frame(cls, frame: Frame, binding, settings_sha256, calibration_id):
        binding.require(frame.window)
        if hashlib.sha256(frame.path.read_bytes()).hexdigest() != frame.sha256:
            raise FeedbackError("Retained pixels changed")
        return cls(frame.frame_id, frame.captured_at, frame.sha256, binding,
                   settings_sha256, calibration_id, str(frame.path))

    def require_fresh(self, now, max_age):
        if not finite(max_age, .001, 3) or not finite(now-self.captured_at, 0, max_age):
            raise FeedbackError("Stale or future feedback frame")


class ReadingState(str, Enum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True)
class ViewObservation:
    frame: FeedbackFrame
    state: ReadingState
    heading: float | None
    pitch: float | None
    uncertainty_degrees: float
    detector_version: str
    provenance: tuple[str, ...]
    grounded_at: float
    gameplay_confirmed: bool
    capture_confirmed: bool
    reason: str = ""
    version: str = "view-observation/v1"

    def __post_init__(self):
        if (self.version != "view-observation/v1" or not isinstance(self.frame, FeedbackFrame)
                or not isinstance(self.state, ReadingState) or not identity(self.detector_version)
                or type(self.provenance) is not tuple or not 1 <= len(self.provenance) <= 16
                or not all(identity(v) for v in self.provenance)
                or self.frame.evidence_reference not in self.provenance
                or not finite(self.uncertainty_degrees, 0, 180)
                or not finite(self.grounded_at, self.frame.captured_at, 1e12)
                or type(self.gameplay_confirmed) is not bool or type(self.capture_confirmed) is not bool):
            raise FeedbackError("Invalid observation provenance or timing")
        if self.state is ReadingState.OBSERVED:
            if not finite(self.heading, -180, 180) or not finite(self.pitch, -180, 180):
                raise FeedbackError("Malformed visible orientation")
        elif self.heading is not None or self.pitch is not None or not identity(self.reason):
            raise FeedbackError("Unknown readings need a reason and no invented orientation")

    def require(self, now, max_age, max_uncertainty):
        self.frame.require_fresh(now, max_age)
        if (self.state is not ReadingState.OBSERVED or now < self.grounded_at
                or self.uncertainty_degrees > max_uncertainty
                or not self.gameplay_confirmed or not self.capture_confirmed):
            raise FeedbackError("Camera observation/capture is unavailable or uncertain")


@dataclass(frozen=True)
class RelativePointerAction:
    dx: int
    dy: int
    duration_ms: int
    issued_at: float
    deadline: float
    cancellation_epoch: int
    frame: FeedbackFrame
    version: str = "relative-pointer-action/v1"

    def __post_init__(self):
        if (self.version != "relative-pointer-action/v1" or not isinstance(self.frame, FeedbackFrame)
                or any(type(v) is not int or abs(v) > 100 for v in (self.dx, self.dy))
                or not (self.dx or self.dy) or type(self.duration_ms) is not int
                or not 1 <= self.duration_ms <= 250 or type(self.cancellation_epoch) is not int
                or self.cancellation_epoch < 0 or not finite(self.issued_at, self.frame.captured_at, 1e12)
                or not finite(self.deadline, self.issued_at+self.duration_ms/1000, self.issued_at+.25)):
            raise FeedbackError("Invalid finite relative motion")

    def require_dispatch(self, now, epoch, window):
        self.frame.binding.require(window, execution=True)
        if epoch != self.cancellation_epoch or not self.issued_at <= now < self.deadline:
            raise FeedbackError("Relative motion canceled or expired")


@dataclass(frozen=True)
class ObservedViewChange:
    before: ViewObservation
    after: ViewObservation
    version: str = "observed-view-change/v1"

    def __post_init__(self):
        if (self.version != "observed-view-change/v1"
                or not isinstance(self.before, ViewObservation) or not isinstance(self.after, ViewObservation)
                or self.before.state is not ReadingState.OBSERVED or self.after.state is not ReadingState.OBSERVED
                or self.before.frame.frame_id == self.after.frame.frame_id
                or self.after.frame.captured_at <= self.before.frame.captured_at
                or (self.before.frame.binding, self.before.frame.settings_sha256, self.before.frame.calibration_id)
                != (self.after.frame.binding, self.after.frame.settings_sha256, self.after.frame.calibration_id)):
            raise FeedbackError("Relative view change needs independent compatible frames")

    @property
    def degrees(self):
        return (heading_delta(self.after.heading, self.before.heading), self.after.pitch-self.before.pitch)

    @property
    def uncertainty_degrees(self):
        return self.before.uncertainty_degrees+self.after.uncertainty_degrees


@dataclass(frozen=True)
class CorrectionGoal:
    heading: float
    pitch: float
    tolerance: float
    max_uncertainty: float
    max_overshoot: float
    max_iterations: int
    total_displacement: int
    total_input_ms: int
    total_seconds: float
    frame_max_age: float
    settling_seconds: float
    version: str = "camera-correction-goal/v1"

    def __post_init__(self):
        if (self.version != "camera-correction-goal/v1"
                or not finite(self.heading, -180, 180) or not finite(self.pitch, -180, 180)
                or not finite(self.tolerance, .01, 5)
                or not finite(self.max_uncertainty, 0, self.tolerance)
                or not finite(self.max_overshoot, 0, 10)
                or type(self.max_iterations) is not int or not 1 <= self.max_iterations <= 32
                or type(self.total_displacement) is not int or not 1 <= self.total_displacement <= 3200
                or type(self.total_input_ms) is not int or not 1 <= self.total_input_ms <= 8000
                or not finite(self.total_seconds, .01, 60)
                or not finite(self.frame_max_age, .001, 3)
                or not finite(self.settling_seconds, .01, self.total_seconds)):
            raise FeedbackError("Invalid correction tolerances or finite budgets")


@dataclass(frozen=True)
class CalibrationSample:
    action: RelativePointerAction
    before: ViewObservation
    after: ViewObservation
    delivered_at: float
    delivery_reference: str
    version: str = "camera-calibration-sample/v1"

    def __post_init__(self):
        if (self.version != "camera-calibration-sample/v1" or not identity(self.delivery_reference)
                or not isinstance(self.action, RelativePointerAction)
                or not isinstance(self.before, ViewObservation) or not isinstance(self.after, ViewObservation)
                or self.action.frame != self.before.frame
                or not finite(self.delivered_at, self.action.issued_at, self.action.deadline)
                or self.after.frame.captured_at <= self.delivered_at+self.action.duration_ms/1000
                or self.before.frame.frame_id == self.after.frame.frame_id
                or (self.before.frame.binding, self.before.frame.settings_sha256, self.before.frame.calibration_id)
                != (self.after.frame.binding, self.after.frame.settings_sha256, self.after.frame.calibration_id)
                or self.before.state is not ReadingState.OBSERVED or self.after.state is not ReadingState.OBSERVED):
            raise FeedbackError("Calibration requires independently observed post-input response")

    @property
    def response(self):
        return ObservedViewChange(self.before, self.after).degrees


@dataclass(frozen=True)
class NeutralHandback:
    hid_released: bool
    epoch_revoked: bool
    pending_motion_revoked: bool
    canceled_at: float
    first: ViewObservation
    last: ViewObservation
    version: str = "camera-neutral-handback/v1"

    def settled(self, goal: CorrectionGoal):
        if (self.version != "camera-neutral-handback/v1"
                or not isinstance(self.first, ViewObservation) or not isinstance(self.last, ViewObservation)
                or any(v is not True for v in (self.hid_released, self.epoch_revoked, self.pending_motion_revoked))
                or not finite(self.canceled_at, 0, self.first.frame.captured_at)
                or self.first.frame.frame_id == self.last.frame.frame_id
                or self.last.frame.captured_at-self.first.frame.captured_at < goal.settling_seconds
                or (self.first.frame.binding, self.first.frame.settings_sha256, self.first.frame.calibration_id)
                != (self.last.frame.binding, self.last.frame.settings_sha256, self.last.frame.calibration_id)):
            return False
        try:
            for obs in (self.first, self.last):
                obs.require(obs.grounded_at, goal.frame_max_age, goal.max_uncertainty)
            uncertainty = self.first.uncertainty_degrees+self.last.uncertainty_degrees
            return max(abs(heading_delta(self.last.heading, self.first.heading)),
                       abs(self.last.pitch-self.first.pitch))+uncertainty <= goal.tolerance
        except FeedbackError:
            return False

    @property
    def residual_view_change(self):
        try:
            return ObservedViewChange(self.first, self.last).degrees
        except FeedbackError:
            return None
