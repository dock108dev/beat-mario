"""Frame synchronized player demonstrations; experimental and never accepted routes."""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import threading
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from smb3_agent.mario_coaching import CoachingStore

CONTRACT = 'smb3/world-1-1/player-sequence/v1'
COLUMNS = ('frame', 'x', 'y', 'vx', 'vy', 'form', 'air', 'world', 'object_set',
           'map_page', 'map_cursor_x', 'return_map', 'dying', 'lives', 'coins',
           'buttons', 'end_x', 'end_y')
MAX_FRAMES = 36000


def validate_rows(rows: list[dict]) -> None:
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FRAMES:
        raise ValueError('Record between one frame and ten minutes of World 1-1 gameplay')
    prior = None
    for row in rows:
        if set(row) != set(COLUMNS) or any(type(row[k]) is not int for k in COLUMNS):
            raise ValueError('Invalid demonstration frame')
        if not (0 <= row['buttons'] <= 255 and 0 < row['x'] < 8192 and 0 < row['y'] < 500
                and 0 < row['end_x'] < 8192 and 0 < row['end_y'] < 500
                and -128 <= row['vx'] <= 127 and -128 <= row['vy'] <= 127
                and 0 <= row['form'] <= 6 and 0 <= row['air'] <= 255
                and row['world'] == 0 and row['object_set'] == 1
                and row['map_page'] == 1 and row['map_cursor_x'] == 64
                and row['return_map'] == 0 and row['dying'] == 0):
            raise ValueError('Only alive World 1-1 route segments can be used; trim the recording before a transition/death')
        if prior and (row['frame'] != prior['frame'] + 1 or row['lives'] != prior['lives']
                      or row['x'] != prior['end_x'] or row['y'] != prior['end_y']):
            raise ValueError('Demonstration frames are discontinuous')
        prior = row


def read_trace(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        values = line.split(',')
        if len(values) != len(COLUMNS):
            raise ValueError('Incomplete recording frame')
        rows.append(dict(zip(COLUMNS, map(int, values))))
    return rows


def compatible(record: dict, cartridge: str | None) -> None:
    if record.get('contract') != CONTRACT or not cartridge or record.get('cartridge_sha256') != cartridge:
        raise ValueError('Open the same cartridge used for this demonstration')
    validate_rows(record['frames'])
    if record.get('trace_sha256') != trace_hash(record['frames']):
        raise ValueError('Demonstration trace has changed')


def trace_hash(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def segment_range(payload: dict, count: int) -> tuple[int, int]:
    """Convert visible recording times to exact frame boundaries, retaining legacy callers."""
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    if 'start_seconds' in payload or 'end_seconds' in payload:
        try:
            start = Decimal(str(payload.get('start_seconds') or '0')) * 60
            end = Decimal(str(payload['end_seconds'])) * 60 if payload.get('end_seconds') else Decimal(count)
            if not start.is_finite() or not end.is_finite() or not 0 <= start < end or end > Decimal(count) + Decimal("0.000001"):
                raise ValueError
            first, last = (int(value.to_integral_value(rounding=ROUND_HALF_UP)) for value in (start, end))
        except (InvalidOperation, ValueError):
            raise ValueError('Choose a start and end within the recording, with the end after the start') from None
    else:
        first = int(payload.get('first') or 0)
        last = int(payload.get('last') or count)
    if not 0 <= first < last <= count:
        raise ValueError('Choose a segment containing at least one recorded moment')
    return first, last


def explanation(record: dict) -> str:
    start, end = record['frames'][0], record['frames'][-1]
    return (f"Follow '{record['name']}' ({len(record['frames'])} frames, x={start['x']} to {end['end_x']}). "
            f"Lesson: {record['lesson']}. Use the experimental balanced approach until the segment's "
            'position, velocity, form and level match, then follow its recorded buttons frame by frame. '
            'Stop at the segment end or on drift, death or interruption. This is sequence following; '
            'different enemies or timing may prevent success. Application and improvement are separate observations.')


class DemonstrationStore:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, identity: str) -> Path:
        if not re.fullmatch(r'[a-f0-9]{32}', identity):
            raise ValueError('Choose a saved demonstration')
        return self.root / (identity + '.json')

    def load(self, identity: str) -> dict:
        record = json.loads(self._path(identity).read_text())
        if record.get('id') != identity or record.get('contract') != CONTRACT:
            raise ValueError('Incompatible demonstration record')
        validate_rows(record['frames'])
        if record.get('trace_sha256') != trace_hash(record['frames']):
            raise ValueError('Demonstration trace has changed')
        return record

    def list(self) -> list[dict]:
        if not self.root.exists():
            return []
        return [{k: v for k, v in self.load(path.stem).items() if k != 'frames'}
                for path in sorted(self.root.glob('*.json'))]

    def save(self, frames: list[dict], *, name: str, lesson: str, cartridge: str, source: dict) -> dict:
        validate_rows(frames)
        if not name.strip() or not lesson.strip() or not cartridge:
            raise ValueError('Give the demonstration a name and intended lesson')
        record = dict(id=uuid4().hex, contract=CONTRACT, name=name.strip()[:120],
                      lesson=lesson.strip()[:4000], cartridge_sha256=cartridge,
                      frames=deepcopy(frames), frame_count=len(frames),
                      start=frames[0], end=frames[-1], trace_sha256=trace_hash(frames), source=source)
        import shutil
        record['images'] = []
        for image in source.get('images', []):
            if frames[0]['frame'] <= image['frame'] <= frames[-1]['frame'] + 1:
                target = self.root / (record['id'] + '-' + str(image['frame']) + '.png')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(image['path'], target)
                record['images'].append({'frame': image['frame'], 'path': str(target.resolve())})
        CoachingStore(self._path(record['id'])).write(record)
        return record

    def edit(self, identity: str, *, name: str, lesson: str) -> dict:
        record = self.load(identity)
        if not name.strip() or not lesson.strip():
            raise ValueError('Provide a name and intended lesson')
        record.update(name=name.strip()[:120], lesson=lesson.strip()[:4000])
        CoachingStore(self._path(identity)).write(record)
        return record

    def delete(self, identity: str) -> None:
        self._path(identity).unlink()
        for image in self.root.glob(identity + '-*.png'):
            image.unlink()


def write_replay(path: Path, record: dict) -> None:
    validate_rows(record['frames'])
    # Only validated numeric data reaches Lua. No user prose/code or external paths.
    content = '\n'.join(','.join(str(row[key]) for key in COLUMNS) for row in record['frames']) + '\n'
    path.write_text(content)


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class PlayerRecording:
    """Volatile recording session. Disk traces survive; reopening never records."""
    def __init__(self, live):
        self.live = live
        self._lock = threading.RLock()
        self.current: dict | None = None
        self.draft: dict | None = None

    @_serialized
    def start(self) -> None:
        if self.current:
            raise ValueError('Stop the current recording first')
        snapshot = self.live.snapshot()
        identity = uuid4().hex
        directory = self.live.demonstration_command(identity, 'start', snapshot.session_id)
        self.current = dict(id=identity, session_id=snapshot.session_id, emulator_pid=snapshot.emulator_pid,
                            directory=str(directory), cartridge_sha256=getattr(self.live, '_game_file_sha256', None),
                            status='starting')

    @_serialized
    def sync(self) -> dict | None:
        if not self.current:
            return None
        current = self.current
        snapshot = self.live.snapshot()
        ack = Path(current['directory']) / 'recording.ack'
        status = ack.read_text().split() if ack.exists() else []
        if len(status) == 2 and status[0] == current['id']:
            current['status'] = status[1]
            if status[1] != 'recording':
                self._freeze(status[1])
                return None
        if (snapshot.session_id != current['session_id'] or snapshot.emulator_pid != current['emulator_pid']
                or snapshot.process_alive is False or not snapshot.observation_active):
            self._freeze('disconnected')
            return None
        return deepcopy(current)

    @_serialized
    def stop(self) -> None:
        if not self.current:
            return
        current = self.current
        self.live.demonstration_command(current['id'], 'stop', current['session_id'])
        current['status'] = 'stopping'
        # A closed-file acknowledgment is required before a trace can be saved.
        import time
        deadline = time.monotonic() + 3
        while self.current and time.monotonic() < deadline:
            self.sync()
            if self.current:
                time.sleep(0.025)
        if self.current:
            raise ValueError('Recording stop is awaiting the emulator; no demonstration has been saved')

    def _freeze(self, reason: str) -> None:
        current = self.current
        path = Path(current['directory']) / ('recording-' + current['id'] + '.trace')
        frames = read_trace(path) if path.exists() else []
        images = []
        from smb3_agent.fceux_images import load_gd_screenshot
        candidates = sorted(Path(current['directory']).glob('recording-' + current['id'] + '-*.gd'),
                            key=lambda image: int(image.stem.rsplit('-', 1)[1]))
        for candidate in candidates[::max(1, (len(candidates)+59)//60)]:
            try:
                output = candidate.with_suffix('.png')
                load_gd_screenshot(candidate).save(output)
                images.append({'frame': int(candidate.stem.rsplit('-', 1)[1]), 'path': str(output.resolve())})
            except (ValueError, OSError):
                continue
        self.draft = dict(**current, images=images, reason=reason, frames=frames, source_path=str(path),
                          saveable=reason in {'stopped', 'segment_ended', 'timeout'})
        self.current = None

    @_serialized
    def review(self) -> dict:
        active = self.sync()
        draft = self.draft
        return {'active': active, 'draft': ({k: v for k, v in draft.items() if k != 'frames'} | {
            'frame_count': len(draft['frames']), 'preview': preview(draft['frames']),
            'image_urls': image_urls(draft.get('images', []))}) if draft else None}


def preview(frames: list[dict]) -> list[dict]:
    """Bounded inspectable action/context trace, with total frame count separately."""
    if not frames:
        return []
    indexes = sorted(set([0, len(frames)-1, *range(0, len(frames), max(1, len(frames)//40))]))
    keys = ('frame', 'x', 'y', 'vx', 'vy', 'form', 'air', 'coins', 'buttons', 'end_x', 'end_y')
    return [dict(index=i, **{k: frames[i][k] for k in keys}) for i in indexes]


def image_urls(images: list[dict]) -> list[dict]:
    from urllib.parse import quote
    result = []
    root = Path("artifacts").resolve()
    for image in images:
        try:
            relative = Path(image['path']).resolve().relative_to(root)
        except ValueError:
            continue
        result.append({'frame': image['frame'], 'url': '/artifacts/' + quote(str(relative))})
    return result
