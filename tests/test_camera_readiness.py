"""Simulated capture suppression and cancellation; no live qualification."""
from dataclasses import replace
import json
from types import SimpleNamespace
import threading
import time

import pytest

from smb3_agent import camera_readiness as ready, camera_practice as practice
from smb3_agent.feedback_contracts import FeedbackError
from test_feedback_contracts import BINDING, ENV, observation


class CaptureFixture:
    def __init__(self, responses, cancellation):
        self.responses = iter(responses)
        self.heading = 0
        self.count = 0
        self.posted = 0
        self.cancellation = cancellation
        self.revoked = False

    def observe(self, **_):
        self.count += 1
        at = time.monotonic()
        return replace(observation(str(self.count), at, self.heading), grounded_at=at)

    def pulse(self, action):
        if self.revoked:
            raise FeedbackError('revoked')
        self.posted += 1
        response = next(self.responses)
        if response == 'cancel':
            self.heading += .6  # posted rotation survives cancellation
            self.cancellation.set()
        else:
            self.heading += response
        return {'delivered_at': time.monotonic()}

    def cancel(self):
        self.revoked = True
        return {'motion_worker_reaped': True, 'pending_motion_revoked': True,
                'epoch_revoked': True, 'seconds': .001}


def run(tmp_path, fixture, cancellation, **kwargs):
    return ready.acquire_readiness(fixture, BINDING, 'controls', 7, cancellation,
        tmp_path/'prep', publish_guard=lambda _: None,
        neutral_receipt=lambda: {'confirmed': True},
        guard_factory=lambda *_: fixture, feedback_identity=(ENV.sha256, 'cal/v1'), **kwargs)


def test_first_callback_suppression_is_retained_before_usable_response(tmp_path):
    cancel = threading.Event()
    f = CaptureFixture([0, .6], cancel)
    result = run(tmp_path, f, cancel)
    assert result['ready'] and f.posted == 2 and f.revoked
    assert [s['outcome'] for s in result['steps']] == [
        'no_usable_response_observed', 'usable_response_observed']
    assert result['steps'][0]['response_degrees'] == (0, 0)
    assert result['settling'][-1]['heading'] == .6
    assert result['class'] == 'readiness_preparation_only'
    assert result['contract']['reusable'] is False


@pytest.mark.parametrize('responses,posts', [([0, 0], 2), ([-.6], 1), ([1.8], 1)])
def test_no_readiness_on_unresponsive_or_contradictory_capture(tmp_path, responses, posts):
    cancel = threading.Event()
    f = CaptureFixture(responses, cancel)
    with pytest.raises(FeedbackError):
        run(tmp_path, f, cancel)
    result = json.loads((tmp_path/'prep/attempt.json').read_text())
    assert not result['ready'] and f.posted == posts and f.revoked
    assert len(result['steps']) == posts and result['settling']


def test_cancel_after_post_retains_partial_rotation_and_forbids_next_probe(tmp_path):
    cancel = threading.Event()
    f = CaptureFixture(['cancel'], cancel)
    with pytest.raises(FeedbackError, match='canceled'):
        run(tmp_path, f, cancel)
    result = json.loads((tmp_path/'prep/attempt.json').read_text())
    assert f.posted == 1 and f.revoked and not result['ready']
    assert result['settling'][-1]['heading'] == .6


def test_cancellation_before_arm_posts_nothing(tmp_path):
    cancel = threading.Event()
    cancel.set()
    f = CaptureFixture([], cancel)
    with pytest.raises(FeedbackError, match='canceled'):
        run(tmp_path, f, cancel)
    assert f.posted == 0


def test_readiness_time_budget_prevents_late_second_probe(tmp_path):
    cancel = threading.Event()
    f = CaptureFixture([0, .6], cancel)
    ticks = iter([0, 0, 0, 0, 0, 0, 9] + [9]*20)
    with pytest.raises(FeedbackError):
        run(tmp_path, f, cancel, clock=lambda: next(ticks))
    assert f.posted <= 1


def test_settings_restore_and_service_reconnect_cannot_restore_old_calibration(tmp_path, monkeypatch):
    cal = SimpleNamespace(environment=SimpleNamespace(controls_id='original'), sha256='old')
    s = practice.CameraPracticeService(tmp_path)
    monkeypatch.setattr(practice, 'settings_digest', lambda: 'changed')
    try:
        with pytest.raises(ValueError, match='invalidated'):
            s._require_calibration(cal)
    finally:
        s.close()
    monkeypatch.setattr(practice, 'settings_digest', lambda: 'original')
    s = practice.CameraPracticeService(tmp_path)
    try:
        with pytest.raises(ValueError, match='invalidated'):
            s._require_calibration(cal)
        assert s.readiness is None
    finally:
        s.close()


def test_old_review_cannot_start_unreviewed_preparation(tmp_path):
    s = practice.CameraPracticeService(tmp_path)
    s.review = {'epoch': 0, 'created_at': time.monotonic()}
    try:
        with pytest.raises(ValueError, match='Review'):
            s.dispatch('start', {'client_id':'fixture'})
        assert not s.worker
    finally:
        s.close()
