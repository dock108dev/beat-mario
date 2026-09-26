from dataclasses import replace
import threading
import time

import pytest

from smb3_agent.stardew_adapter import InputCommand, InputKind, StardewAdapterError, WindowObservation
from smb3_agent.stardew_input import MacOrdinaryInputDriver
from smb3_agent.stardew_setup import DisposableSessionSetup, LoadingEvidence, discover_installations


def window():
    return WindowObservation(123, "start", "window", "Stardew Valley", (0, 0, 100, 100), True, True, True)


def test_explicit_copy_never_enables_input_and_reset_invalidates(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "farm").write_text("synthetic test only")
    setup = DisposableSessionSetup()
    with pytest.raises(StardewAdapterError, match="authorization"):
        setup.create_owner_copy(source, tmp_path / "copy", copy_authorized=False)
    first = setup.create_owner_copy(source, tmp_path / "copy", copy_authorized=True)
    assert not first.input_ready
    with pytest.raises(StardewAdapterError, match="not been verified"):
        setup.require_verified(window())
    second = setup.reset(tmp_path / "copy2")
    assert second.session_id != first.session_id
    assert (tmp_path / "copy/farm").is_file()
    assert not second.input_ready


def test_fixture_loading_does_not_grant_live_isolation(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "farm").write_text("synthetic")
    setup = DisposableSessionSetup()
    session = setup.create_owner_copy(source, tmp_path / "copy", copy_authorized=True)
    trace = tmp_path / "trace"
    trace.write_text("fixture OS accesses")
    evidence = LoadingEvidence(session.session_id, 123, "start", "window", (str(tmp_path / "copy/farm"),), (str(tmp_path / "copy/farm"),), (str(trace),))
    setup.verify_loading(window(), probe=lambda *_: evidence)
    assert not setup.session.input_ready
    with pytest.raises(StardewAdapterError, match="outside"):
        setup.verify_loading(window(), probe=lambda *_: replace(evidence, loaded_paths=(str(source / "farm"),)))


def test_discovery_only_inspects_explicit_metadata(tmp_path):
    steam = tmp_path / "steam"
    (steam / "steamapps").mkdir(parents=True)
    result = discover_installations(steam, ())
    assert result["installations"] == [] and result["save_directories_inspected"] is False
    (steam / "steamapps/appmanifest_413150.acf").write_text('"installdir" "Stardew Valley"')
    binary_root = steam / "steamapps/common/Stardew Valley/Contents/MacOS"
    binary_root.mkdir(parents=True)
    (binary_root / "Stardew Valley.dll").write_bytes(b"fixture")
    (binary_root / "Stardew Valley").write_bytes(b"fixture")
    apps = tmp_path / "Applications"
    (apps / "Stardew Valley.app").mkdir(parents=True)
    result = discover_installations(steam, (apps,))
    assert len(result["installations"]) == 1
    assert result["launcher_shortcuts"] == [str(apps / "Stardew Valley.app")]


class QuartzFixture:
    kCGHIDEventTap = "hid"
    def __init__(self):
        self.events = []
    def CGEventCreateKeyboardEvent(self, _, code, down):
        return code, down
    def CGEventPost(self, pid, event):
        self.events.append((pid, event))


def driver(q, provider=window, isolation=lambda _: None, authority=lambda: None):
    return MacOrdinaryInputDriver(window_provider=provider, isolation_guard=isolation, authority_guard=authority, quartz=q)


def test_guard_failure_emits_nothing():
    q = QuartzFixture()
    d = driver(q, provider=lambda: replace(window(), foreground=False))
    with pytest.raises(StardewAdapterError, match="Foreground"):
        d.send(InputCommand(InputKind.KEYBOARD, "w", "press", 0))
    assert q.events == []


def test_neutral_reclaim_interrupts_held_key_and_no_queued_actions():
    q = QuartzFixture()
    d = driver(q)
    errors = []
    def run():
        try:
            d.send(InputCommand(InputKind.KEYBOARD, "w", "hold", 250))
        except StardewAdapterError as exc:
            errors.append(str(exc))
    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.monotonic() + 1
    while not q.events and time.monotonic() < deadline:
        time.sleep(.001)
    d.neutralize()
    thread.join(1)
    assert not thread.is_alive() and errors == ["Input canceled"]
    assert q.events == [("hid", (13, True)), ("hid", (13, False))]
    with pytest.raises(StardewAdapterError, match="canceled"):
        d.send(InputCommand(InputKind.KEYBOARD, "w", "press", 0))
    assert len(q.events) == 2


def test_focus_loss_releases_held_system_input():
    q = QuartzFixture()
    calls = []
    def provider():
        calls.append(1)
        return window() if len(calls) == 1 else replace(window(), foreground=False)
    d = driver(q, provider=provider)
    with pytest.raises(StardewAdapterError, match="Foreground"):
        d.send(InputCommand(InputKind.KEYBOARD, "w", "hold", 60))
    assert q.events == [("hid", (13, True)), ("hid", (13, False))]


def test_engineering_source_classification_is_preserved_on_reset(tmp_path):
    source = tmp_path / "engineering"
    source.mkdir()
    (source / "farm").write_text("synthetic")
    setup = DisposableSessionSetup()
    first = setup.create_engineering_copy(source, tmp_path / "attempt1", copy_authorized=True)
    second = setup.reset(tmp_path / "attempt2")
    assert first.classification == second.classification == "engineering_source"
    assert first.session_id != second.session_id


def test_source_special_files_and_hardlink_aliases_are_rejected(tmp_path):
    import os
    source = tmp_path / "source"
    source.mkdir()
    os.mkfifo(source / "pipe")
    setup = DisposableSessionSetup()
    with pytest.raises(StardewAdapterError, match="regular files"):
        setup.create_owner_copy(source, tmp_path / "copy", copy_authorized=True)
    (source / "pipe").unlink()
    outside = tmp_path / "outside"
    outside.write_text("source")
    os.link(outside, source / "farm")
    with pytest.raises(StardewAdapterError, match="regular files"):
        setup.create_owner_copy(source, tmp_path / "copy", copy_authorized=True)


def test_reclaim_during_slow_guard_never_posts_new_input():
    q = QuartzFixture()
    entered = threading.Event()
    release = threading.Event()
    def isolation(_):
        entered.set()
        assert release.wait(1)
    d = driver(q, isolation=isolation)
    errors = []
    def run():
        try:
            d.send(InputCommand(InputKind.KEYBOARD, "w", "press", 0))
        except StardewAdapterError as exc:
            errors.append(str(exc))
    input_thread = threading.Thread(target=run)
    input_thread.start()
    assert entered.wait(1)
    reclaim_thread = threading.Thread(target=d.neutralize)
    reclaim_thread.start()
    assert d._cancel.wait(1)
    release.set()
    input_thread.join(1)
    reclaim_thread.join(1)
    assert not input_thread.is_alive() and not reclaim_thread.is_alive()
    assert errors == ["Input canceled during guard validation"]
    assert q.events == []


def test_reclaim_during_arm_cannot_clear_cancellation():
    q = QuartzFixture()
    entered, release = threading.Event(), threading.Event()
    def isolation(_):
        entered.set()
        assert release.wait(1)
    d = driver(q, isolation=isolation)
    errors = []
    def arm():
        try:
            d.arm()
        except StardewAdapterError as exc:
            errors.append(str(exc))
    armer = threading.Thread(target=arm)
    armer.start()
    assert entered.wait(1)
    reclaim = threading.Thread(target=d.neutralize)
    reclaim.start()
    assert d._cancel.wait(1)
    release.set()
    armer.join(1)
    reclaim.join(1)
    assert errors == ["Input authorization was canceled while arming"]
    assert d._cancel.is_set() and not q.events


def test_real_driver_refuses_missing_event_post_permission(monkeypatch):
    import sys
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules, "Quartz", SimpleNamespace(CGPreflightPostEventAccess=lambda: False))
    with pytest.raises(StardewAdapterError, match="permission is unavailable"):
        MacOrdinaryInputDriver(window_provider=window, isolation_guard=lambda _: None, authority_guard=lambda: None)


def test_engineering_launch_rejects_uninspected_runtime_before_process_creation(tmp_path):
    import json
    from smb3_agent.stardew_setup import launch_fresh_engineering
    installation = tmp_path / "game"
    macos = installation / "Contents/MacOS"
    macos.mkdir(parents=True)
    (macos / "Stardew Valley.runtimeconfig.json").write_text(json.dumps({"runtimeOptions": {"includedFrameworks": [{"name": "Microsoft.NETCore.App", "version": "9.0.0"}]}}))
    with pytest.raises(StardewAdapterError, match="runtime differs"):
        launch_fresh_engineering(installation, tmp_path / "session")
    assert not (tmp_path / "session").exists()


def test_visible_backend_requires_full_expected_process_identity():
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend
    with pytest.raises(StardewAdapterError, match="supplied together"):
        MacVisibleStardewBackend(process_id=123)
    backend = MacVisibleStardewBackend(process_id=123, process_started_at="start")
    assert backend.expected_process_id == 123


def test_engineering_verification_never_accepts_absent_review(tmp_path):
    from smb3_agent.stardew_setup import EngineeringLaunch
    launch = EngineeringLaunch('nonce', str(tmp_path), '/game', '/game/bin', str(tmp_path / 'config'), str(tmp_path / 'data'), str(tmp_path / 'isolation.sb'), {}, 123, 'start')
    with pytest.raises(StardewAdapterError, match="review is missing"):
        DisposableSessionSetup().verify_engineering_launch(launch, window())


def test_engineering_review_adopts_actual_path_and_preserves_seed(tmp_path, monkeypatch):
    import os
    from PIL import Image
    import smb3_agent.stardew_setup as module
    launch = module.EngineeringLaunch('launch-nonce', str(tmp_path), '/fixture', '/fixture/bin', str(tmp_path / 'config'), str(tmp_path / 'data'), str(tmp_path / 'isolation.sb'), {}, 123, 'start')
    # All native/visual values here are a deterministic fixture, not live evidence.
    monkeypatch.setattr(module, '_verify_engineering_launch_identity', lambda *_: None)
    (tmp_path / 'launch.json').write_text('{}')
    start = (tmp_path / 'launch.json').stat().st_mtime_ns
    farm = tmp_path / 'config/StardewValley/Saves/Engineering_123'
    farm.mkdir(parents=True)
    for name in (farm.name, 'SaveGameInfo'):
        (farm / name).write_bytes(b'synthetic test save identity only')
        os.utime(farm / name, ns=(start+100, start+100))
    menu, loaded = tmp_path / 'menu.png', tmp_path / 'loaded.png'
    Image.new('RGB', (100, 100), 'red').save(menu)
    Image.new('RGB', (100, 100), 'green').save(loaded)
    os.utime(menu, ns=(start+200, start+200))
    os.utime(loaded, ns=(start+300, start+300))
    module.retain_engineering_load_review(launch, window(), save_name=farm.name,
                                        load_menu_screenshot=menu, loaded_screenshot=loaded)
    setup = module.DisposableSessionSetup()
    session = setup.verify_engineering_launch(launch, window())
    assert session.input_ready and session.classification == 'engineering_source'
    assert session.save.disposable_real_path == str(farm)
    assert setup.manager.verify_primary_unchanged(session.save)
    setup.require_verified(window())
    assert session.save.primary_real_path != str(farm)
    # A changed receipt-bound file or screenshot can never be re-certified.
    (farm / farm.name).write_bytes(b'mutated')
    with pytest.raises(StardewAdapterError, match='persistence changed'):
        module.DisposableSessionSetup().verify_engineering_launch(launch, window())
    assert setup.manager.verify_primary_unchanged(session.save)
    with pytest.raises(StardewAdapterError, match='Disposable persistence identity changed'):
        setup.require_verified(window())


def test_mouse_uses_system_events_and_releases_at_reviewed_point():
    class MouseQuartz(QuartzFixture):
        kCGEventLeftMouseDown, kCGEventLeftMouseUp = 1, 2
        kCGEventRightMouseDown, kCGEventRightMouseUp = 3, 4
        kCGEventMouseMoved, kCGMouseButtonLeft, kCGMouseButtonRight = 5, 0, 1
        kCGMouseEventClickState = 1

        def CGEventCreateMouseEvent(self, _, kind, point, button):
            return (kind, point, button)

        def CGEventSetIntegerValueField(self, event, field, value):
            assert value == 1

    q = MouseQuartz()
    d = driver(q)
    d.send(InputCommand(InputKind.MOUSE, 'left_button', 'click', 0, target=(40, 50)))
    assert q.events == [('hid', (1, (40, 50), 0)), ('hid', (2, (40, 50), 0))]
    with pytest.raises(StardewAdapterError, match='outside'):
        d.send(InputCommand(InputKind.MOUSE, 'left_button', 'click', 0, target=(140, 50)))
    assert len(q.events) == 2


def test_prepared_farm_registry_never_discovers_external_sources(tmp_path, monkeypatch):
    import json
    from smb3_agent.stardew_setup import prepared_engineering_farms
    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'artifacts/stardew-engineering/session/prepared-sources/seed/Farm'
    root.mkdir(parents=True)
    external = tmp_path / 'external'
    external.mkdir()
    registry = tmp_path / 'artifacts/stardew-prepared-farms.json'
    registry.write_text(json.dumps([
        {'id': 'allowed', 'source': str(root), 'label': 'Test', 'tree_sha256': 'x'},
        {'id': 'external', 'source': str(external), 'label': 'No', 'tree_sha256': 'x'},
    ]))
    assert [r['id'] for r in prepared_engineering_farms()] == ['allowed']


def test_changed_prepared_seed_refuses_before_launch(tmp_path, monkeypatch):
    import json
    from smb3_agent.stardew_setup import launch_fresh_engineering
    monkeypatch.chdir(tmp_path)
    source = tmp_path / 'artifacts/stardew-engineering/session/prepared-sources/seed/Farm'
    source.mkdir(parents=True)
    (source / 'Farm').write_bytes(b'changed')
    (tmp_path / 'artifacts/stardew-prepared-farms.json').write_text(json.dumps([
        {'id': 'farm', 'source': str(source), 'label': 'Test', 'tree_sha256': 'bad'},
    ]))
    with pytest.raises(Exception, match='seed is missing or changed'):
        launch_fresh_engineering(tmp_path / 'absent-installation', tmp_path / 'new', prepared_id='farm')
    assert not (tmp_path / 'new').exists()


@pytest.mark.parametrize('contents', ['broken json', '{}', '[null, {}, 12]'])
def test_malformed_prepared_registry_does_not_break_ordinary_setup(tmp_path, monkeypatch, contents):
    from smb3_agent.stardew_setup import prepared_engineering_farms
    monkeypatch.chdir(tmp_path)
    registry = tmp_path / 'artifacts/stardew-prepared-farms.json'
    registry.parent.mkdir()
    registry.write_text(contents)
    assert prepared_engineering_farms() == []


def test_foreground_identity_is_fresh_and_native_failure_is_unknown(monkeypatch):
    import ctypes
    import ctypes.util
    from types import SimpleNamespace
    from smb3_agent.stardew_adapter import _foreground_process_id
    active = [123]
    status = [0]
    def front(serial):
        return status[0]
    def pid(serial, output):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_int32))[0] = active[0]
        return status[0]
    monkeypatch.setattr(ctypes.util, 'find_library', lambda name: 'fixture')
    monkeypatch.setattr(ctypes, 'CDLL', lambda name: SimpleNamespace(GetFrontProcess=front, GetProcessPID=pid))
    assert _foreground_process_id() == 123
    active[0] = 456
    assert _foreground_process_id() == 456
    status[0] = -1
    with pytest.raises(StardewAdapterError, match='foreground identity is unavailable'):
        _foreground_process_id()


def test_input_deadline_releases_even_while_guard_is_blocked():
    entered, unblock, released = threading.Event(), threading.Event(), threading.Event()
    q = QuartzFixture()
    post = q.CGEventPost
    def record(pid, event):
        post(pid, event)
        if event[1] is False:
            released.set()
    q.CGEventPost = record
    calls = []
    def isolation(_):
        calls.append(True)
        if len(calls) > 1:
            entered.set()
            assert unblock.wait(2)
    d = driver(q, isolation=isolation)
    thread = threading.Thread(target=lambda: d.send(InputCommand(InputKind.KEYBOARD, 's', 'press', 80)))
    thread.start()
    assert entered.wait(1)
    try:
        assert released.wait(.5), 'release must not wait for the blocked identity guard'
        assert not d._held
    finally:
        unblock.set()
        thread.join(2)
    assert not thread.is_alive()


def test_short_pulse_does_not_start_guard_at_release_deadline():
    q = QuartzFixture()
    calls = []
    def provider():
        calls.append(time.monotonic())
        return window()
    d = driver(q, provider=provider)
    d.send(InputCommand(InputKind.KEYBOARD, 's', 'press', 5))
    assert len(calls) == 1
    assert q.events == [('hid', (1, True)), ('hid', (1, False))]


def test_prepared_view_requires_exact_registered_seed_and_full_initial_observation(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from PIL import Image
    import smb3_agent.stardew_setup as module
    from smb3_agent.stardew_adapter import _tree_identity
    launch = module.EngineeringLaunch('fresh', str(tmp_path), '/fixture', '/fixture/bin', str(tmp_path/'config'), str(tmp_path/'data'), str(tmp_path/'isolation.sb'), {}, 123, 'start')
    monkeypatch.setattr(module, '_verify_engineering_launch_identity', lambda *_: None)
    farm = tmp_path/'config/StardewValley/Saves/Test_1'
    farm.mkdir(parents=True)
    for name in (farm.name, 'SaveGameInfo'):
        (farm/name).write_bytes(b'synthetic identity only')
    source = tmp_path/'seed/Test_1'
    import shutil
    shutil.copytree(farm, source)
    record = {'id':'fixture', 'source':str(source), 'tree_sha256':_tree_identity(source)[0]}
    (tmp_path/'prepared-source.json').write_text(json.dumps(record))
    monkeypatch.setattr(module, 'prepared_engineering_farms', lambda: [record])
    capture = tmp_path/'visible.png'
    Image.new('RGB',(100,100)).save(capture)
    frame = {'crops':{(i,0):False for i in range(15)}, 'energy':270, 'water':40, 'player':(0,0), 'uncertainty':2}
    profile = SimpleNamespace(qualified=lambda:True, config={'seed_sha256':record['tree_sha256']}, decode=lambda _:frame, profile_id='fixture')
    setup = module.DisposableSessionSetup()
    first = setup.verify_prepared_view(launch, window(), profile=profile, screenshot=capture)
    second = setup.verify_prepared_view(launch, window(), profile=profile, screenshot=capture)
    assert first.session_id != second.session_id
    assert setup.manager.verify_primary_unchanged(first.save)
    frame['crops'][(0,0)] = None
    with pytest.raises(StardewAdapterError, match='complete dry'):
        setup.verify_prepared_view(launch, window(), profile=profile, screenshot=capture)
    frame['crops'][(0,0)] = False
    (farm/farm.name).write_bytes(b'changed')
    with pytest.raises(StardewAdapterError, match='working copy changed'):
        setup.verify_prepared_view(launch, window(), profile=profile, screenshot=capture)


def test_watering_aim_guard_precedes_mouse_down_and_can_cancel():
    class MouseQuartz(QuartzFixture):
        kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGMouseButtonLeft = 1,2,0
        kCGEventRightMouseDown, kCGEventRightMouseUp, kCGMouseButtonRight = 3,4,1
        kCGEventMouseMoved, kCGMouseEventClickState = 5,6
        def CGEventCreateMouseEvent(self, _, kind, point, button):
            return (kind, point)
        def CGEventSetIntegerValueField(self, *args):
            pass
    q=MouseQuartz()
    def reject(command, current):
        assert command.reviewed_crop_id=='crop'
        assert all(event[1][0]==q.kCGEventMouseMoved for event in q.events)
        raise StardewAdapterError('wrong visible target')
    d=MacOrdinaryInputDriver(window_provider=window,isolation_guard=lambda _:None,authority_guard=lambda:None,
                             quartz=q,before_mouse_press=reject)
    with pytest.raises(StardewAdapterError,match='wrong visible target'):
        d.send(InputCommand(InputKind.MOUSE,'left_button','click',80,target=(20,20),purpose='water_crop',reviewed_crop_id='crop'))
    assert all(event[1][0]==q.kCGEventMouseMoved for event in q.events)
    assert not d._held


def test_native_capture_timeout_and_post_capture_focus_are_rejected(tmp_path,monkeypatch):
    import subprocess
    from smb3_agent.stardew_adapter import MacVisibleStardewBackend
    from PIL import Image
    backend=MacVisibleStardewBackend(process_id=123,process_started_at='start')
    monkeypatch.setattr(backend,'detect_window',window)
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired(args[0],1.5)
    monkeypatch.setattr(subprocess,'run',timeout)
    with pytest.raises(StardewAdapterError,match='freshness bound'):
        backend.capture(window(),tmp_path/'timeout.png')
    assert not (tmp_path/'timeout.png').exists()
    def capture(args,**kwargs):
        Image.new('RGB',(200,200),'red').save(args[-1])
        return type('Result',(),{'returncode':0})()
    monkeypatch.setattr(subprocess,'run',capture)
    backend.capture(window(),tmp_path/'success.png')
    assert Image.open(tmp_path/'success.png').size==(100,100)
    states=iter([window(),replace(window(),window_id='replaced')])
    monkeypatch.setattr(backend,'detect_window',lambda:next(states))
    with pytest.raises(StardewAdapterError,match='changed during'):
        backend.capture(window(),tmp_path/'changed.png')


def test_fast_pulse_focus_guard_stops_and_full_identity_rechecks_after_release():
    q = QuartzFixture()
    def lost(_):
        raise StardewAdapterError('fresh focus lost')
    d = MacOrdinaryInputDriver(window_provider=window, isolation_guard=lambda _: None,
                              authority_guard=lambda: None, quartz=q, pulse_guard=lost)
    with pytest.raises(StardewAdapterError, match='fresh focus lost'):
        d.send(InputCommand(InputKind.KEYBOARD, 'w', 'press', 80))
    assert q.events[-1][1] == (13, False) and not d._held
    q = QuartzFixture()
    states = iter([window(), replace(window(), window_id='new')])
    def full():
        value = next(states)
        if value.window_id == 'new':
            assert q.events[-1][1] == (13, False)
        return value
    d = MacOrdinaryInputDriver(window_provider=full, isolation_guard=lambda _: None,
                              authority_guard=lambda: None, quartz=q, pulse_guard=lambda _: None)
    with pytest.raises(StardewAdapterError, match='Process/window changed'):
        d.send(InputCommand(InputKind.KEYBOARD, 'w', 'press', 25))
    assert not d._held


def test_posting_delay_consumes_hold_budget(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr('smb3_agent.stardew_input.time.monotonic', lambda: clock[0])
    class DelayedPost(QuartzFixture):
        def CGEventPost(self, pid, event):
            super().CGEventPost(pid, event)
            if event[1]:
                clock[0] += .1
    q = DelayedPost()
    intervals = []
    class Timer:
        def __init__(self, interval, callback):
            intervals.append(interval)
            self.callback = callback
        def start(self):
            self.callback()
        def cancel(self):
            pass
        def join(self):
            pass
    monkeypatch.setattr('smb3_agent.stardew_input.threading.Timer', Timer)
    d = driver(q)
    d.send(InputCommand(InputKind.KEYBOARD, 'w', 'press', 80))
    assert intervals == [0]
    assert q.events[-1][1] == (13, False) and not d._held
