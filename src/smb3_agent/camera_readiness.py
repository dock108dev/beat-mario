"""Explicit, observed preparation; never correction or calibration work.

Every invocation has new authority. No readiness is restored from a file or
reused after launch, focus, capture, identity or settings transitions. A posted
probe may rotate the view even when cancellation wins; retain that partial view.
"""
from dataclasses import asdict
import json
from pathlib import Path
import threading
import time

from smb3_agent.camera_native_input import CameraMotionGuard
from smb3_agent.feedback_contracts import FeedbackError, RelativePointerAction, heading_delta

READINESS_VERSION = 'minecraft-capture-response/v1'
READINESS_CONTRACT = {
    'version': READINESS_VERSION,
    'max_pulses': 2,
    'units_per_pulse': 4,
    'pulse_ms': 120,
    'max_total_units': 8,
    'max_input_ms': 240,
    'max_seconds': 8,
    'axis': 'positive yaw',
    'max_predicted_rotation_degrees': 1.2,
    'expected_response_degrees': .6,
    'response_error_degrees': .2,
    'max_frame_age_seconds': .8,
    'settling_seconds': .2,
    'max_residual_degrees': .1,
    'reusable': False,
}


def acquire_readiness(observer, binding, controls_id, epoch, cancellation, root,
                      *, publish_guard, neutral_receipt, clock=time.monotonic,
                      guard_factory=CameraMotionGuard, feedback_identity):
    """Caller explicitly reviews this operation, separately from its absolute goal."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    started = clock()
    record = {'class': 'readiness_preparation_only', 'contract': READINESS_CONTRACT,
              'epoch': epoch, 'binding': asdict(binding), 'started_at': started,
              'steps': [], 'ready': False}
    guard = None
    failure = None
    def check():
        if cancellation.is_set() or clock()-started >= READINESS_CONTRACT['max_seconds']:
            raise FeedbackError('Readiness canceled or finite time budget exhausted')
    def bound(obs):
        if (obs.frame.binding != binding or
                (obs.frame.settings_sha256, obs.frame.calibration_id) != feedback_identity):
            raise FeedbackError('Readiness feedback identity changed')
    try:
        check()
        guard = guard_factory(binding, epoch, controls_id, root)
        publish_guard(guard)
        for _ in range(READINESS_CONTRACT['max_pulses']):
            check()
            before = observer.observe(execution=True)
            before.require(clock(), .8, .1)
            bound(before)
            now = clock()
            check()
            action = RelativePointerAction(4, 0, 120, now, now+.12, epoch, before.frame)
            step = {'before': asdict(before), 'action': asdict(action)}
            record['steps'].append(step)
            step['delivery'] = guard.pulse(action)
            if cancellation.wait(max(0, step['delivery']['delivered_at']+.14-clock())):
                raise FeedbackError('Readiness canceled after posting; partial motion retained')
            check()
            after = observer.observe(execution=True)
            step['after'] = asdict(after)
            after.require(clock(), .8, .1)
            bound(after)
            if (after.frame.binding != binding or after.frame.settings_sha256 != before.frame.settings_sha256
                    or after.frame.calibration_id != before.frame.calibration_id
                    or after.frame.captured_at <= step['delivery']['delivered_at']):
                raise FeedbackError('Readiness observation binding changed or predates dispatch')
            response = (heading_delta(after.heading, before.heading), after.pitch-before.pitch)
            step['response_degrees'] = response
            uncertainty = before.uncertainty_degrees+after.uncertainty_degrees
            if abs(response[1]) > uncertainty:
                raise FeedbackError('Readiness cross-axis rotation contradicts reviewed probe')
            if abs(response[0]-.6) <= .2+uncertainty:
                step['outcome'] = 'usable_response_observed'
                record['response_observed'] = True
                break
            if abs(response[0]) <= uncertainty:
                step['outcome'] = 'no_usable_response_observed'
            else:
                raise FeedbackError('Readiness response contradicts reviewed four-unit probe')
        if not record.get('response_observed'):
            raise FeedbackError('Readiness not established within two probes')
    except Exception as exc:
        failure = str(exc)
    finally:
        record['release'] = guard.cancel() if guard else {'motion_worker_reaped': True, 'pending_motion_revoked': True, 'epoch_revoked': True, 'seconds': 0}
        record['canceled_at'] = clock()
        try:
            record['native_neutral'] = neutral_receipt()
            first = observer.observe(execution=True)
            # Settling observation is required even after direct cancellation.
            threading.Event().wait(.2)
            last = observer.observe(execution=True)
            record['settling'] = [asdict(first), asdict(last)]
            if record['steps']:
                baseline = record['steps'][0]['before']
                record['observed_preparation_rotation'] = [heading_delta(last.heading, baseline['heading']), last.pitch-baseline['pitch']]
            for obs in (first, last):
                obs.require(clock() if obs is last else obs.grounded_at, .8, .1)
                bound(obs)
                if obs.frame.binding != binding or obs.frame.settings_sha256 != first.frame.settings_sha256:
                    raise FeedbackError('Readiness settling identity changed')
            if (first.frame.captured_at < record['canceled_at']
                    or last.frame.captured_at-first.frame.captured_at < .2
                    or max(abs(heading_delta(last.heading, first.heading)), abs(last.pitch-first.pitch)) > .1
                    or not record['native_neutral']['confirmed']
                    or not all(record['release'][k] for k in ('motion_worker_reaped', 'pending_motion_revoked', 'epoch_revoked'))
                    or record['release']['seconds'] > .3):
                raise FeedbackError('Readiness neutral settling unconfirmed')
            check()
            if not failure:
                record['ready'] = True
        except Exception as exc:
            failure = failure or str(exc)
        record['elapsed_seconds'] = clock()-started
        if failure:
            record['error'] = failure
        (root/'attempt.json').write_text(json.dumps(record, indent=2)+'\n')
    if not record['ready']:
        raise FeedbackError(failure or 'Readiness eligibility closed')
    return record
