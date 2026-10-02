"""Deterministic simulated feedback, never Minecraft/native qualification."""
from dataclasses import replace
import hashlib

import pytest

from smb3_agent.coordinate_contracts import RelativePointerCalibration, relative_pointer_pulse
from smb3_agent.feedback_contracts import (
    CalibrationSample, CameraEnvironment, CorrectionGoal, FeedbackError, FeedbackFrame,
    NeutralHandback, ReadingState, RelativePointerAction, ViewObservation, WindowBinding,
    heading_delta,
)
from smb3_agent.feedback_policy import CameraCalibration, CorrectionPolicy, CorrectionState
from smb3_agent.game_profiles import ExecutableProfile, ProfileError
from smb3_agent.host_contracts import HostError, WindowObservation
from smb3_agent.screen_host import Frame


WINDOW = WindowObservation(123, "start", "7", "fixture", (0, 0, 800, 600), True, True, True)
BINDING = WindowBinding(123, "start", "7", (0, 0, 800, 600), (1600, 1200))
ENV = CameraEnvironment("fixture-build", "fixture-runtime", (), "a"*64, "controls/v1",
                        "windowed", .5, False, "off", "on", 70, "off", (30, 120),
                        (-90, 90), "visible-fixture/v1", "unimplemented", "fixture-confirmation")
GOAL = CorrectionGoal(10, 0, .5, .1, 1, 4, 40, 200, 10, .2, .1)


def observation(name="initial", at=100, heading=0, pitch=0, **changes):
    frame = FeedbackFrame(name, at, "b"*64, BINDING, ENV.sha256, "cal/v1", name+".png")
    return ViewObservation(frame, ReadingState.OBSERVED, heading, pitch, .05,
                           "detector-fixture/v1", (frame.evidence_reference,), at+.01,
                           True, True, **changes)


def calibration():
    samples = []
    for index, (dx, dy) in enumerate(((2, 0), (-2, 0), (0, 2), (0, -2))*2):
        before = observation(f"before-{index}", 10+index)
        action = RelativePointerAction(dx, dy, 20, 10+index+.02, 10+index+.04, 0, before.frame)
        after = observation(f"after-{index}", 10+index+.1, dx, dy)
        samples.append(CalibrationSample(action, before, after, 10+index+.021, "fixture-delivery"))
    return CameraCalibration("cal/v1", ENV, BINDING, tuple(samples), (1, 1, 1, 1), .1, "fixture-recheck")


def policy(initial=None, goal=GOAL):
    return CorrectionPolicy(calibration(), goal, initial or observation(), epoch=7, now=100.02)


def issue(p, dx=5, dy=0, now=100.02):
    action = p.propose(dx, dy, 20, now=now, epoch=7, settings_sha256=ENV.sha256)
    p.delivered(action, at=now+.001, epoch=7)
    return action


@pytest.mark.parametrize("target,current,expected", [(-179, 179, 2), (179, -179, -2), (180, -180, 0)])
def test_wraparound(target, current, expected):
    assert heading_delta(target, current) == expected


@pytest.mark.parametrize("target,current", [(180, 0), (float("nan"), 0), (True, 0), (181, 0)])
def test_invalid_or_ambiguous_heading(target, current):
    with pytest.raises(FeedbackError):
        heading_delta(target, current)


@pytest.mark.parametrize("changes", [{"sensitivity": float("nan")}, {"raw_input": "unknown"},
                                    {"inverted": 1}, {"fps_range": (120, 30)},
                                    {"pitch_range": (90, -90)}, {"version": "v2"}])
def test_environment_rejects_unknown_or_malformed(changes):
    with pytest.raises(FeedbackError):
        replace(ENV, **changes)


@pytest.mark.parametrize("changes", [{"sensitivity": .6}, {"inverted": True}, {"fov": 80},
                                    {"mods": ("mod",)}, {"runtime": "new"}, {"fps_range": (20, 30)},
                                    {"observation_method": "new"}, {"native_input_version": "new"}])
def test_settings_change_revokes_and_cannot_resume(changes):
    p = policy()
    with pytest.raises(FeedbackError, match="recalibration"):
        p.propose(5, 0, 20, now=100.02, epoch=7, settings_sha256=replace(ENV, **changes).sha256)
    assert p.state is CorrectionState.PARTIAL and p.epoch == 8
    with pytest.raises(FeedbackError):
        issue(p)


@pytest.mark.parametrize("changes", [{"process_id": 124}, {"process_started_at": "new"},
                                    {"window_id": "8"}, {"bounds": (1, 0, 800, 600)},
                                    {"foreground": False}, {"visible": False}, {"occluded": True}])
def test_exact_dispatch_identity(changes):
    action = issue(policy())
    with pytest.raises(FeedbackError):
        action.require_dispatch(100.025, 7, replace(WINDOW, **changes))


def test_frame_pixels_and_capture_start_are_bound(tmp_path):
    path = tmp_path/"frame.png"
    path.write_bytes(b"fixture pixels")
    frame = Frame("id", 100, WINDOW, path, hashlib.sha256(path.read_bytes()).hexdigest(), ())
    bound = FeedbackFrame.from_frame(frame, BINDING, ENV.sha256, "cal/v1")
    assert bound.captured_at == 100
    path.write_bytes(b"altered")
    with pytest.raises(FeedbackError, match="pixels"):
        FeedbackFrame.from_frame(frame, BINDING, ENV.sha256, "cal/v1")


@pytest.mark.parametrize("now", [99.9, 100.21, float("nan")])
def test_stale_future_or_invalid_frames(now):
    with pytest.raises(FeedbackError):
        observation().require(now, .2, .1)


@pytest.mark.parametrize("state", [ReadingState.UNAVAILABLE, ReadingState.UNSUPPORTED, ReadingState.CONTRADICTORY])
def test_unavailable_reading_never_invents_orientation(state):
    obs = replace(observation(), state=state, heading=None, pitch=None, reason="occluded")
    with pytest.raises(FeedbackError):
        policy(obs)
    with pytest.raises(FeedbackError):
        replace(obs, heading=0)


@pytest.mark.parametrize("changes", [{"gameplay_confirmed": False}, {"capture_confirmed": False},
                                    {"uncertainty_degrees": 1}])
def test_menu_capture_loss_or_uncertainty_refuses(changes):
    p = policy()
    issue(p)
    with pytest.raises(FeedbackError):
        p.observe(replace(observation("after", 100.1, 5), **changes), now=100.12,
                  epoch=7, settings_sha256=ENV.sha256)
    assert p.state is CorrectionState.PARTIAL


def test_no_blind_queue_or_completion_from_delivery():
    p = policy()
    action = issue(p)
    with pytest.raises(FeedbackError):
        issue(p)
    assert p.state is CorrectionState.AWAITING_OBSERVATION
    with pytest.raises(FeedbackError):
        p.delivered(action, at=100.025, epoch=7)
    p.observe(observation("after", 100.1, 5), now=100.12, epoch=7, settings_sha256=ENV.sha256)
    assert p.state is CorrectionState.READY
    issue(p, now=100.12)
    p.observe(observation("final", 100.2, 10), now=100.22, epoch=7, settings_sha256=ENV.sha256)
    assert p.state is CorrectionState.TARGET_OBSERVED


def test_cancel_pending_receipt_and_late_observation():
    p = policy()
    action = p.propose(5, 0, 20, now=100.02, epoch=7, settings_sha256=ENV.sha256)
    p.cancel("Take control")
    with pytest.raises(FeedbackError):
        p.delivered(action, at=100.025, epoch=7)
    with pytest.raises(FeedbackError):
        action.require_dispatch(100.025, p.epoch, WINDOW)
    with pytest.raises(FeedbackError):
        p.observe(observation("late", 100.1, 5), now=100.12, epoch=7, settings_sha256=ENV.sha256)
    assert p.last.heading == 0 and p.state is CorrectionState.PARTIAL


@pytest.mark.parametrize("heading,pitch", [(-5, 0), (5, 2), (0, 0)])
def test_wrong_direction_cross_axis_or_no_response_stops(heading, pitch):
    p = policy()
    issue(p)
    with pytest.raises(FeedbackError, match="Contradictory"):
        p.observe(observation("bad", 100.1, heading, pitch), now=100.12,
                  epoch=7, settings_sha256=ENV.sha256)
    assert p.state is CorrectionState.CONTRADICTORY


@pytest.mark.parametrize("changes", [{"max_iterations": 1}, {"total_displacement": 5}, {"total_input_ms": 20}])
def test_budget_reserved_before_dispatch(changes):
    p = policy(goal=replace(GOAL, **changes))
    issue(p)
    p.observe(observation("after", 100.1, 5), now=100.12, epoch=7, settings_sha256=ENV.sha256)
    with pytest.raises(FeedbackError, match="budget"):
        issue(p, now=100.12)
    assert p.iterations == 1 and p.state is CorrectionState.PARTIAL


def test_time_budget_and_expired_action():
    p = policy()
    with pytest.raises(FeedbackError):
        issue(p, now=111)
    action = issue(policy())
    with pytest.raises(FeedbackError):
        action.require_dispatch(action.deadline, 7, WINDOW)


def test_calibration_requires_independent_directional_samples():
    cal = calibration()
    with pytest.raises(FeedbackError):
        replace(cal, samples=(cal.samples[0],)*8)
    with pytest.raises(FeedbackError):
        replace(cal.samples[0], after=cal.samples[0].before)
    with pytest.raises(FeedbackError):
        replace(cal, gains=(-1, -1, 1, 1))


@pytest.mark.parametrize("changes", [{"dx": True}, {"dx": 101}, {"dy": float("nan")},
                                    {"duration_ms": 0}, {"duration_ms": 251},
                                    {"deadline": 101}, {"cancellation_epoch": -1},
                                    {"version": "relative-pointer-action/v2"}])
def test_malformed_pulse_cannot_dispatch(changes):
    with pytest.raises(FeedbackError):
        replace(issue(policy()), **changes)


def test_post_pulse_frame_cannot_reuse_or_precede_motion():
    p = policy()
    issue(p)
    with pytest.raises(FeedbackError, match="post-pulse"):
        p.observe(observation("old", 100.03, 5), now=100.06, epoch=7, settings_sha256=ENV.sha256)
    assert p.state is CorrectionState.PARTIAL


def test_no_input_away_from_target_or_excess_overshoot():
    for dx in (-2, 12):
        p = policy()
        with pytest.raises(FeedbackError, match="overshoot"):
            issue(p, dx=dx)
        assert p.iterations == 0


def test_partial_rotation_and_residual_remain_in_result():
    p = policy()
    issue(p)
    p.observe(observation("partial", 100.1, 5), now=100.12, epoch=7, settings_sha256=ENV.sha256)
    p.cancel("Stop after partial turn")
    receipt = replace(handback(5), last=observation("residual", 100.5, 6))
    result = p.result(receipt, now=100.52)
    assert result["last_observed_heading"] == 5
    assert result["sampled_residual_view_change"] == (1, 0)
    assert not result["neutral_handback_confirmed"]
    assert result["status"] == "partial"


def test_pitch_limits_and_wraparound_corrections():
    p = policy(observation(heading=179), replace(GOAL, heading=-179))
    issue(p, dx=2)
    p.observe(observation("wrapped", 100.1, -179), now=100.12, epoch=7, settings_sha256=ENV.sha256)
    assert p.state is CorrectionState.TARGET_OBSERVED
    p = policy(observation(pitch=89), replace(GOAL, heading=0, pitch=90))
    issue(p, dx=0, dy=1)
    p.observe(observation("limit", 100.1, 0, 90), now=100.12, epoch=7, settings_sha256=ENV.sha256)
    assert p.state is CorrectionState.TARGET_OBSERVED
    with pytest.raises(FeedbackError):
        policy(goal=replace(GOAL, pitch=91))


def handback(heading=10):
    return NeutralHandback(True, True, True, 100.23, observation("settle-1", 100.3, heading),
                          observation("settle-2", 100.5, heading))


def completed_policy():
    p = policy()
    issue(p, dx=10)
    p.observe(observation("final", 100.2, 10), now=100.22, epoch=7, settings_sha256=ENV.sha256)
    return p


def test_completion_requires_fresh_settled_handback():
    p = completed_policy()
    assert p.result(handback(), now=100.52)["status"] == "verified_completion"
    for receipt in (replace(handback(), pending_motion_revoked=False),
                    replace(handback(), hid_released=False),
                    replace(handback(), last=observation("residual", 100.5, 12))):
        assert p.result(receipt, now=100.52)["status"] != "verified_completion"
    assert p.result(handback(), now=101)["status"] != "verified_completion"
    p.cancel("Stop")
    assert p.result(handback(), now=100.52)["status"] == "partial"


def test_experimental_contracts_never_enable_profiles():
    import json
    from pathlib import Path
    data = json.loads(Path("data/private-beta/openttd-pb2.json").read_text())
    data["capabilities"].append("relative-pointer-action/v1")
    with pytest.raises(ProfileError):
        ExecutableProfile.from_dict(data)
    with pytest.raises(HostError, match="not qualified"):
        relative_pointer_pulse(2, 0, 20, RelativePointerCalibration("p", "w", "s", True))
