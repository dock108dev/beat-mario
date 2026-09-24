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
    def __init__(self):
        self.events = []
    def CGEventCreateKeyboardEvent(self, _, code, down):
        return code, down
    def CGEventPostToPid(self, pid, event):
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
    assert q.events == [(123, (13, True)), (123, (13, False))]
    with pytest.raises(StardewAdapterError, match="canceled"):
        d.send(InputCommand(InputKind.KEYBOARD, "w", "press", 0))
    assert len(q.events) == 2


def test_focus_loss_releases_original_process():
    q = QuartzFixture()
    calls = []
    def provider():
        calls.append(1)
        return window() if len(calls) == 1 else replace(window(), foreground=False)
    d = driver(q, provider=provider)
    with pytest.raises(StardewAdapterError, match="Foreground"):
        d.send(InputCommand(InputKind.KEYBOARD, "w", "hold", 60))
    assert q.events == [(123, (13, True)), (123, (13, False))]


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
