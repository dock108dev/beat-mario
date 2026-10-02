"""Reviewed camera diagnostic; every pulse retained, never qualification."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
import subprocess
import threading
import time
from uuid import uuid4

from smb3_agent.camera_native_input import CameraMotionGuard, settings_digest
from smb3_agent.camera_practice import candidate_identity, environment, native_hid_receipt
from smb3_agent.feedback_contracts import RelativePointerAction, heading_delta
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver
from smb3_agent.screen_host import MacSelectedWindowHost


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--window', required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--dx', type=int, default=0)
    parser.add_argument('--dy', type=int, default=0)
    parser.add_argument('--wait-before', type=float, default=0)
    args = parser.parse_args()
    if args.pid == 74438 or bool(args.dx) == bool(args.dy) or max(abs(args.dx), abs(args.dy)) > 4 or not 0 <= args.wait_before <= 10:
        raise ValueError('Diagnostic permits one reviewed axis, <=4 units, <=10s wait')
    root = args.root / uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    canceled = threading.Event()
    guard = None
    def cancel(*_):
        canceled.set()
        if guard:
            guard.cancel()
    signal.signal(signal.SIGINT, cancel)
    signal.signal(signal.SIGTERM, cancel)
    record = {'class': 'diagnostic_only', 'candidate': candidate_identity(), 'wall_started_ns': time.time_ns(), 'observations': [], 'wait_before_seconds': args.wait_before}
    try:
        start = subprocess.check_output(['ps', '-p', str(args.pid), '-o', 'lstart='], text=True).strip()
        observer = MinecraftCameraObserver(MacSelectedWindowHost(args.pid, start, args.window), environment(), 'diagnostic-only/v1', root/'frames')
        first = observer.observe(execution=True)
        record['initial'] = asdict(first)
        first.require(first.grounded_at, .8, .1)
        guard = CameraMotionGuard(first.frame.binding, 1, settings_digest(), root)
        if canceled.wait(args.wait_before):
            raise ValueError('Canceled before diagnostic pulse')
        before = observer.observe(execution=True)
        record['before'] = asdict(before)
        record['before_timing'] = observer.last_timing
        before.require(before.grounded_at, .8, .1)
        now = time.monotonic()
        action = RelativePointerAction(args.dx, args.dy, 120, now, now+.12, 1, before.frame)
        record['action'] = asdict(action)
        if canceled.is_set():
            raise ValueError('Canceled before dispatch')
        record['delivery'] = guard.pulse(action)
        posted = record['delivery']['delivered_at']
        for delay in (.12, .6, 1.2, 2.5):
            if canceled.wait(max(0, posted+delay-time.monotonic())):
                raise ValueError('Canceled during observation')
            obs = observer.observe(execution=True)
            record['observations'].append({'view': asdict(obs), 'timing': observer.last_timing, 'seconds_after_post': obs.frame.captured_at-posted, 'visible': asdict(observer.last_visible) if observer.last_visible else None})
        record['response'] = [heading_delta(record['observations'][-1]['view']['heading'], before.heading), record['observations'][-1]['view']['pitch']-before.pitch]
    except Exception as exc:
        record['error'] = str(exc)
    finally:
        record['release'] = guard.cancel() if guard else {'method': 'no_worker'}
        record['canceled_at'] = time.monotonic()
        record['native_neutral'] = native_hid_receipt()
        try:
            first = observer.observe(execution=True)
            canceled.wait(.2)
            last = observer.observe(execution=True)
            record['settling'] = [asdict(first), asdict(last)]
        except Exception as exc:
            record['settling_error'] = str(exc)
        (root/'attempt.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({'attempt': str(root/'attempt.json'), 'error': record.get('error'), 'response': record.get('response'), 'release': record['release']}))


if __name__ == '__main__':
    main()
