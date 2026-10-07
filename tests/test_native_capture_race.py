"""A window geometry race rejects pixels and retains bounded diagnostic evidence."""
from dataclasses import replace
from types import SimpleNamespace
import json
import subprocess
import pytest
from PIL import Image
from smb3_agent.native_host import capture_selected
from smb3_agent.host_contracts import WindowObservation, HostError


def test_capture_bounds_change_is_retained_and_never_accepted(tmp_path, monkeypatch):
    window = WindowObservation(123, 'start', '7', 'game', (0, 0, 100, 100), True, True, True)
    windows = iter([window, replace(window, bounds=(0, 0, 80, 80))])
    def capture(args, **kwargs):
        Image.new('RGB', (100, 100)).save(args[-1], format='TIFF')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess, 'run', capture)
    target = tmp_path/'frame.png'
    with pytest.raises(HostError, match='process/window changed'):
        capture_selected(window, target, detect_window=lambda: next(windows))
    assert not target.exists()
    record = json.loads(target.with_suffix('.capture-refusal.json').read_text())
    assert record['frame_accepted'] is False
    assert record['before']['bounds'] != record['after']['bounds']
    assert target.with_name('frame-capture.tiff').exists()


def test_replaced_game_cannot_receive_fallback_focus(monkeypatch):
    from types import SimpleNamespace
    from smb3_agent import native_host
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(stdout='replacement-start'))
    monkeypatch.setattr(native_host, '_foreground_binding', lambda: pytest.fail('Replaced game must not receive a focus request'))
    with pytest.raises(Exception, match='changed before focus'):
        native_host.request_unbundled_activation(42, 'bound-start')


@pytest.mark.parametrize('cancelled_during', ['activation', 'detection'])
def test_cancelled_focus_wait_does_not_repeat_activation(monkeypatch, cancelled_during):
    import sys
    from types import SimpleNamespace
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend, StardewAdapterError
    events = []
    app = SimpleNamespace(unhide=lambda: events.append('unhide'),
                          activateWithOptions_=lambda _: events.append('activate'))
    monkeypatch.setitem(sys.modules, 'AppKit', SimpleNamespace(
        NSRunningApplication=SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda _: app),
        NSApplicationActivateIgnoringOtherApps=1, NSApplicationActivateAllWindows=2))
    native = MacVisibleStardewBackend(process_id=42, process_started_at='bound-start')
    def detect(**kwargs):
        assert cancelled_during == 'detection', 'Cancelled focus must not inspect windows'
        events.append('detect')
        raise StardewAdapterError('not visible')
    monkeypatch.setattr(native, 'detect_window', detect)
    monkeypatch.setattr(native, '_activation_window_exists', lambda **kwargs: pytest.fail('Cancelled focus must not inspect metadata'))
    monkeypatch.setattr('time.sleep', lambda _: None)
    with pytest.raises(StardewAdapterError, match='interrupted'):
        native.activate_window(cancelled=lambda: ('activate' if cancelled_during == 'activation' else 'detect') in events)
    assert events == ['unhide', 'activate'] + (['detect'] if cancelled_during == 'detection' else [])


def test_focus_is_requested_again_only_after_real_window_appears(monkeypatch):
    import sys
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend, StardewAdapterError
    from smb3_agent import native_host
    events = []
    app = SimpleNamespace(unhide=lambda: None, activateWithOptions_=lambda _: None,
                          bundleIdentifier=lambda: None)
    monkeypatch.setitem(sys.modules, 'AppKit', SimpleNamespace(
        NSRunningApplication=SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda _: app),
        NSApplicationActivateIgnoringOtherApps=1, NSApplicationActivateAllWindows=2))
    monkeypatch.setattr(native_host, 'request_unbundled_activation', lambda *a, **k: events.append('request'))
    window = WindowObservation(42, 'bound-start', '7', 'game', (0, 33, 1512, 949), True, True, True)
    calls = []
    def detect(*, require_foreground=True):
        calls.append(require_foreground)
        if len(events) == 2:
            return window
        if require_foreground or len(calls) < 4:
            raise StardewAdapterError('window not ready')
        return replace(window, foreground=False)
    native = MacVisibleStardewBackend(process_id=42, process_started_at='bound-start')
    monkeypatch.setattr(native, 'detect_window', detect)
    monkeypatch.setattr(native, '_activation_window_exists', lambda **kwargs: False)
    monkeypatch.setattr('time.sleep', lambda _: None)
    assert native.activate_window() is window
    assert events == ['request', 'request']
    assert calls == [True, False, True, False, True]


@pytest.mark.parametrize("helper_height", [44,64])
def test_sdl_startup_helper_is_not_a_second_game_viewport(monkeypatch, helper_height):
    import sys
    from smb3_agent import stardew_adapter
    constants = ['kCGWindowOwnerPID', 'kCGWindowOwnerName', 'kCGWindowName',
                 'kCGWindowLayer', 'kCGWindowAlpha', 'kCGWindowBounds', 'kCGWindowNumber']
    main = dict(zip(constants, [42, 'Stardew Valley', 'Stardew Valley', 0, 1,
                {'X': 0, 'Y': 33, 'Width': 1512, 'Height': 949}, 7]))
    helper = {**main, 'kCGWindowName': '', 'kCGWindowNumber': 8,
              'kCGWindowBounds': {**main['kCGWindowBounds'], 'Height': helper_height}}
    records = [helper, main]
    quartz = SimpleNamespace(**{k:k for k in constants}, kCGWindowListOptionOnScreenOnly=1,
        kCGWindowListExcludeDesktopElements=2, kCGNullWindowID=0,
        CGWindowListCopyWindowInfo=lambda *a: records, CGMainDisplayID=lambda: 1,
        CGDisplayBounds=lambda _: SimpleNamespace(origin=SimpleNamespace(x=0,y=0),
                                 size=SimpleNamespace(width=1512,height=982)))
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    monkeypatch.setattr(stardew_adapter, '_foreground_process_id', lambda: 42)
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(stdout='bound-start'))
    native = stardew_adapter.MacVisibleStardewBackend(process_id=42, process_started_at='bound-start')
    assert native.detect_window().window_id == '7'
    records.append({**main, 'kCGWindowNumber': 9})
    with pytest.raises(stardew_adapter.StardewAdapterError, match='observed 2'):
        native.detect_window()


def test_canceled_queued_focus_never_runs_late(monkeypatch):
    import sys
    import threading
    from smb3_agent import native_host
    queued, errors = [], []
    ready, cancel = threading.Event(), threading.Event()
    def enqueue(callback):
        queued.append(callback)
        ready.set()
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setitem(sys.modules, 'PyObjCTools', SimpleNamespace(AppHelper=SimpleNamespace(callAfter=enqueue)))
    monkeypatch.setattr(native_host, '_foreground_binding', lambda: pytest.fail('Canceled callback must not request native focus'))
    def request():
        try:
            native_host.request_unbundled_activation(42, 'bound-start', cancelled=cancel.is_set)
        except HostError as exc:
            errors.append(str(exc))
    worker = threading.Thread(target=request)
    worker.start()
    assert ready.wait(1)
    cancel.set()
    worker.join(1)
    assert not worker.is_alive()
    assert errors and 'interrupted' in errors[0]
    queued[0]()


def test_startup_waits_for_stable_supported_viewport_before_accepting_focus(monkeypatch):
    import sys
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend
    app = SimpleNamespace(unhide=lambda: None, activateWithOptions_=lambda _: True)
    monkeypatch.setitem(sys.modules, 'AppKit', SimpleNamespace(
        NSRunningApplication=SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda _: app),
        NSApplicationActivateIgnoringOtherApps=1, NSApplicationActivateAllWindows=2))
    supported = WindowObservation(42, 'start', '7', 'game', (0,33,1512,949), True, True, True)
    windows = iter([replace(supported, bounds=(0,33,640,480)), supported,
                    replace(supported, bounds=(0,33,1280,720)), supported, supported, supported])
    native = MacVisibleStardewBackend(process_id=42, process_started_at='start')
    reads = []
    def detect():
        result = next(windows)
        reads.append(result.bounds)
        return result
    monkeypatch.setattr(native, 'detect_window', detect)
    monkeypatch.setattr('time.sleep', lambda _: None)
    assert native.activate_window(expected_viewport=(1512,949)) is supported
    assert len(reads) == 6


def test_offscreen_window_metadata_can_request_focus_but_is_not_observation(monkeypatch):
    import sys
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend
    keys = ['kCGWindowOwnerPID', 'kCGWindowLayer', 'kCGWindowName',
            'kCGWindowAlpha', 'kCGWindowBounds']
    records = [dict(zip(keys, [42, 0, 'Stardew Valley', 1, {'Height': 949}]))]
    q = SimpleNamespace(**{key: key for key in keys}, kCGWindowListOptionAll=0,
        kCGWindowListExcludeDesktopElements=2, kCGNullWindowID=0,
        CGWindowListCopyWindowInfo=lambda *args: records)
    monkeypatch.setitem(sys.modules, 'Quartz', q)
    native = MacVisibleStardewBackend(process_id=42, process_started_at='bound-start')
    assert native._activation_window_exists()
    records[0]['kCGWindowBounds'] = {'Height': 44}
    assert not native._activation_window_exists()
    records[0]['kCGWindowBounds'] = {'Height': 949}
    records.append(dict(records[0]))
    assert not native._activation_window_exists()


def test_sdl_shielding_layer_requires_bound_named_supported_game():
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend
    keys = ['kCGWindowLayer', 'kCGWindowOwnerPID', 'kCGWindowOwnerName',
            'kCGWindowName', 'kCGWindowBounds']
    q = SimpleNamespace(**{key:key for key in keys}, CGShieldingWindowLevel=lambda:2147483628)
    native = MacVisibleStardewBackend(process_id=42,process_started_at='bound-start')
    row = dict(zip(keys,[2147483628,42,'Stardew Valley','Stardew Valley',
        {'X':0,'Y':33,'Width':1512,'Height':949}]))
    assert native._supported_game_layer(row,q)
    for key, value in [('kCGWindowOwnerPID',43),('kCGWindowName',''),
                       ('kCGWindowLayer',1000),('kCGWindowBounds',{'Height':44})]:
        assert not native._supported_game_layer({**row,key:value},q)
    assert not MacVisibleStardewBackend()._supported_game_layer(row,q)


def test_focus_retry_waits_for_declared_viewport_metadata(monkeypatch):
    import sys
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend
    keys = ['kCGWindowOwnerPID','kCGWindowLayer','kCGWindowName','kCGWindowAlpha','kCGWindowBounds']
    records = [dict(zip(keys,[42,0,'Stardew Valley',1,{'Width':1280,'Height':748}]))]
    q = SimpleNamespace(**{key:key for key in keys}, kCGWindowListOptionAll=0,
        kCGWindowListExcludeDesktopElements=2,kCGNullWindowID=0,
        CGWindowListCopyWindowInfo=lambda *args:records)
    monkeypatch.setitem(sys.modules,'Quartz',q)
    native = MacVisibleStardewBackend(process_id=42,process_started_at='bound-start')
    assert not native._activation_window_exists(expected_viewport=(1512,949))
    records[0]['kCGWindowBounds']={'Width':1512,'Height':949}
    assert native._activation_window_exists(expected_viewport=(1512,949))


def test_startup_ambiguity_gets_one_retry_only_after_the_sole_view_settles(monkeypatch):
    import sys
    from dataclasses import replace
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend, StardewAdapterError
    from smb3_agent.host_contracts import WindowObservation
    window = WindowObservation(42,'start','game','Stardew',(0,33,1512,949),True,True,True)
    app = SimpleNamespace(unhide=lambda:None, activateWithOptions_=lambda _:None,
                          bundleIdentifier=lambda:'game.bundle')
    monkeypatch.setitem(sys.modules,'AppKit',SimpleNamespace(
        NSRunningApplication=SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda _:app),
        NSApplicationActivateIgnoringOtherApps=1,NSApplicationActivateAllWindows=2))
    requests=[]
    monkeypatch.setattr('smb3_agent.native_host.request_unbundled_activation',
                        lambda *a,**k:requests.append('focus') or {})
    monkeypatch.setattr('time.sleep',lambda _:None)
    native=MacVisibleStardewBackend(process_id=42,process_started_at='start')
    reads=[0]
    def detect(*,require_foreground=True):
        if not require_foreground:
            if reads[0] <= 3:
                raise StardewAdapterError('expected exactly one visible Stardew window; observed 2')
            return replace(window,foreground=False)
        reads[0]+=1
        if len(requests)>=2:
            return window
        raise StardewAdapterError('expected exactly one visible Stardew window; observed 2' if reads[0]<=3 else 'window_loss')
    monkeypatch.setattr(native,'detect_window',detect)
    monkeypatch.setattr(native,'_activation_window_exists',lambda **k:True)
    assert native.activate_window(expected_viewport=(1512,949))==window
    assert requests==['focus','focus']
