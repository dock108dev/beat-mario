"""Simulated OS boundaries; these do not qualify actual OS permission denial."""
import json
import os
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from smb3_agent import input_guardian, screen_host
from smb3_agent.host_contracts import HostError, InputCommand, InputKind, WindowObservation
from smb3_agent.native_input import MacBoundedInputDriver


class NativeFixture:
    kCGHIDEventTap = 'hid'
    kCGEventSourceStateHIDSystemState = 'state'
    kCGMouseButtonLeft = 0
    kCGMouseButtonRight = 1
    kCGEventLeftMouseUp = 'left_up'
    kCGEventRightMouseUp = 'right_up'

    def __init__(self):
        self.events = []

    def CGPreflightPostEventAccess(self):
        return True

    def CGEventCreateKeyboardEvent(self, _, code, down):
        return (code, down)

    def CGEventPost(self, _, event):
        self.events.append(event)

    def CGEventSourceKeyState(self, *_):
        return False

    def CGEventSourceButtonState(self, *_):
        return False


def test_late_guardian_ack_cannot_emit_down():
    q = NativeFixture()
    guardian = SimpleNamespace(arm=lambda *_: time.sleep(.025))
    window = WindowObservation(123, 'start', '7', 'game', (0,0,100,100), True, True, True)
    driver = MacBoundedInputDriver(quartz=q, external_guard=guardian,
        window_provider=lambda: window, isolation_guard=lambda _: None, authority_guard=lambda: None)
    with pytest.raises(HostError, match='before guarded'):
        driver.send(InputCommand(InputKind.KEYBOARD, 'w', 'hold', 10))
    assert q.events and all(event[1] is False for event in q.events)


@pytest.mark.parametrize('reason', ['pulse_deadline', 'parent_transport_closed'])
def test_independent_guardian_releases_on_deadline_or_parent_eof(tmp_path, monkeypatch, reason):
    q = NativeFixture()
    monkeypatch.setitem(sys.modules, 'Quartz', q)
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, 'rb', buffering=0)
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(buffer=reader, fileno=reader.fileno))
    path = tmp_path/'guardian.jsonl'
    errors = []
    def run():
        try:
            input_guardian._worker(path)
        except Exception as exc:
            errors.append(exc)
    worker = threading.Thread(target=run)
    worker.start()
    os.write(write_fd, (json.dumps({'kind':'arm', 'token':'test', 'control':'w',
        'input_kind':'keyboard', 'target':None, 'deadline':time.monotonic()+.15})+'\n').encode())
    deadline = time.monotonic()+1
    while time.monotonic() < deadline:
        if path.exists() and 'armed' in path.read_text():
            break
        time.sleep(.002)
    assert 'armed' in path.read_text()
    if reason == 'parent_transport_closed':
        os.close(write_fd)
    else:
        while not q.events and time.monotonic() < deadline:
            time.sleep(.002)
        os.close(write_fd)
    worker.join(1)
    reader.close()
    assert not worker.is_alive() and not errors
    receipts = [json.loads(line) for line in path.read_text().splitlines()]
    releases = [r for r in receipts if r['kind']=='release']
    assert q.events == [(13, False)]
    assert len(releases)==1 and releases[0]['reason']==reason and releases[0]['confirmed']


@pytest.mark.parametrize('owner,top,height,refused', [(123,-1400,20,False), (999,-1400,20,True), (123,-1370,20,True)])
def test_only_exact_process_titlebar_chrome_is_excluded(monkeypatch, owner, top, height, refused):
    q = SimpleNamespace(kCGWindowNumber='number', kCGWindowOwnerPID='pid', kCGWindowLayer='layer',
        kCGWindowAlpha='alpha', kCGWindowBounds='bounds', kCGWindowName='name',
        kCGWindowListOptionOnScreenOnly=1, kCGWindowListExcludeDesktopElements=2, kCGNullWindowID=0)
    records = [{'number':8,'pid':owner,'layer':0,'alpha':1,
                'bounds':{'X':-985,'Y':top,'Width':66,'Height':height}},
               {'number':7,'pid':123,'layer':0,'alpha':1,'name':'game',
                'bounds':{'X':-991,'Y':-1400,'Width':1280,'Height':1056}}]
    q.CGWindowListCopyWindowInfo = lambda *_: records
    monkeypatch.setitem(sys.modules, 'Quartz', q)
    monkeypatch.setattr(screen_host.subprocess, 'run', lambda *_args, **_kw: SimpleNamespace(stdout='start'))
    monkeypatch.setattr(screen_host, 'foreground_process_id', lambda: 123)
    host = screen_host.MacSelectedWindowHost(123,'start','7')
    if refused:
        with pytest.raises(screen_host.ScreenHostError, match='unobscured'):
            host.detect_window()
    else:
        assert host.detect_window().trusted
