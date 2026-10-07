import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from smb3_agent import paths
from smb3_agent.candidate_resources import resolve_resource_values, import_day2_seed
from smb3_agent.release_resources import stage_resources


def test_portable_calibration_works_without_original_paths(tmp_path, monkeypatch):
    from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
    root = Path(__file__).resolve().parents[1]
    if not (root / 'artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json').is_file():
        pytest.skip('Retained local calibration is a builder prerequisite, excluded from source checkout')
    dest = tmp_path / 'resources'
    records = stage_resources(root, dest)
    monkeypatch.setattr(paths, 'REPOSITORY_ROOT', dest)
    profile = PreparedFarmPixelProfile(dest / 'data/calibration/day2/profile.json')
    assert profile.qualified()
    assert all(str(tmp_path) in name for name in profile.config['evidence_hashes'])
    assert {f'scripts/{name}' for name in ('fceux_live_observer.lua', 'fceux_live_takeover.lua', 'fceux_b2_plan.lua')} <= {r['path'] for r in records}
    sample = next(name for name in profile.config['evidence_hashes'] if name.endswith('.png'))
    Path(sample).write_bytes(b'changed')
    assert not profile.qualified()


def test_resource_traversal_refused():
    with pytest.raises(ValueError):
        resolve_resource_values('gc-resource:../owner-file')


def test_wrong_seed_does_not_create_registration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / 'selected'
    source.mkdir()
    (source / 'save').write_text('different farm')
    with pytest.raises(ValueError, match='supported unchanged Day 2'):
        import_day2_seed(str(source))
    assert not Path('artifacts/stardew-prepared-farms.json').exists()


def test_provider_cleanup_failure_does_not_skip_input_cleanup(monkeypatch):
    from smb3_agent import lab_ui
    events = []
    class Provider:
        def close(self):
            raise ValueError('provider failure')
    class Manager:
        def shutdown(self):
            events.append('input-neutralized')
    monkeypatch.setattr(lab_ui, 'LiveObservationManager', Manager)
    failures = lab_ui._shutdown_session_managers(SimpleNamespace(codex_provider=Provider(), live_observation_manager=Manager()))
    assert events == ['input-neutralized']
    assert failures == ['Codex provider cleanup unconfirmed']


def test_stardew_installation_field_reaches_runtime(tmp_path):
    from smb3_agent.conversation_service import StardewConversationService
    from smb3_agent.stardew_runtime import StardewRuntime
    runtime = StardewRuntime()
    received = []
    runtime.setup = lambda value: received.append(value)
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    service.dispatch('launch_engineering', {'prepared_id': 'pilot-day2', 'installation': '/selected/Stardew Valley.app'})
    assert received == [{'action': 'launch_engineering', 'prepared_id': 'pilot-day2', 'installation': '/selected/Stardew Valley.app'}]
    service.close()


def test_interrupted_startup_is_descriptive(tmp_path, monkeypatch):
    from smb3_agent.app_lifecycle import record_lifecycle
    monkeypatch.chdir(tmp_path)
    record_lifecycle('running')
    record_lifecycle('running')
    value = json.loads(Path('app-lifecycle.json').read_text())
    assert value['interrupted_previous_start']
    assert not value['authority_restored']
    record_lifecycle('closed')
    record_lifecycle('running')
    assert not json.loads(Path('app-lifecycle.json').read_text())['interrupted_previous_start']
    record_lifecycle('cleanup_failed', ['input release unconfirmed'])
    record_lifecycle('running')
    recovered = json.loads(Path('app-lifecycle.json').read_text())
    assert recovered['previous_cleanup_failures'] == ['input release unconfirmed']
    assert not recovered['authority_restored']


def test_independent_watchdog_releases_only_owned_child_group():
    import subprocess
    import sys
    from smb3_agent.process_watchdog import ChildWatchdog
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    try:
        guard = ChildWatchdog(child)
        guard.close()  # Simulates the same EOF delivered after parent termination.
        assert child.wait(timeout=3) == -9
        assert other.poll() is None
    finally:
        for proc in (child, other):
            if proc.poll() is None:
                proc.kill()
            proc.wait()


def test_selected_stardew_installation_reopens_without_authority(tmp_path):
    from smb3_agent.conversation_service import StardewConversationService
    from smb3_agent.stardew_runtime import StardewRuntime
    runtime = StardewRuntime()
    runtime.setup = lambda payload: None
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    service.dispatch('launch_engineering', {'installation':'/selected/Stardew Valley.app'})
    service.close()
    reopened = StardewConversationService(artifacts_root=tmp_path)
    state = reopened.snapshot()
    assert state['runtime']['setup_selection']['installation'] == '/selected/Stardew Valley.app'
    assert state['plan'] is None
    assert state['runtime']['status'] == 'unconfigured'
    assert state['runtime']['handback_confirmed']
    reopened.close()


def test_candidate_quit_uses_served_script_under_existing_csp():
    from smb3_agent.companion_catalog import CatalogSession, CatalogPreferenceStore, build_default_catalog_registry
    from smb3_agent.lab_ui import render_combined_catalog, CANDIDATE_JS
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        html = render_combined_catalog(CatalogSession(build_default_catalog_registry(), CatalogPreferenceStore(Path(folder)/'preferences.json')))
    assert '<script src="/assets/candidate.js" defer></script>' in html
    assert '<script>' not in html
    assert '/api/delivery/shutdown' in CANDIDATE_JS


def test_permission_setup_requests_missing_access_without_input(monkeypatch):
    from smb3_agent.screen_host import MacSelectedWindowHost
    import sys
    events = []
    quartz = SimpleNamespace(CGPreflightScreenCaptureAccess=lambda: False,
                            CGPreflightPostEventAccess=lambda: False,
                            CGRequestScreenCaptureAccess=lambda: events.append('capture-request'),
                            CGRequestPostEventAccess=lambda: events.append('input-request'))
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    assert MacSelectedWindowHost.request_permissions() == {'capture':False, 'input':False}
    assert events == ['capture-request', 'input-request']


def test_packaged_legacy_native_endpoint_refuses_before_launch(tmp_path, monkeypatch):
    import http.client
    import threading
    from urllib.parse import urlencode
    from smb3_agent import lab_ui
    monkeypatch.chdir(tmp_path)
    server = lab_ui._new_lab_ui_server('127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(lab_ui, 'sys', SimpleNamespace(frozen=True))
    try:
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
        connection.request('POST', '/run', urlencode({'csrf_token':server.csrf_token}), {'Content-Type':'application/x-www-form-urlencoded'})
        response = connection.getresponse()
        assert response.status == 403
        assert b'experimental execution is unavailable' in response.read()
        connection.close()
        assert not server.delivery_game_processes.processes
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_default_save_choices_exclude_metadata_aliases_and_partial_saves(tmp_path):
    from smb3_agent.stardew_setup import default_save_choices
    root = tmp_path / 'Saves'
    root.mkdir()
    farm = root / 'Ordinary_123'
    farm.mkdir()
    (farm / farm.name).write_text('game save')
    (farm / 'SaveGameInfo').write_text('game metadata')
    (root / 'steam_autocloud.vdf').write_text('metadata')
    (root / 'unfinished').mkdir()
    (root / 'alias').symlink_to(farm, target_is_directory=True)
    assert default_save_choices(root) == [{'id': 'Ordinary_123', 'label': 'Ordinary'}]


def test_default_save_selection_revalidates_name_and_requires_copy_approval(tmp_path, monkeypatch):
    from smb3_agent import stardew_setup
    from smb3_agent.conversation_service import StardewConversationService
    from smb3_agent.stardew_runtime import StardewRuntime
    monkeypatch.setattr(stardew_setup, 'default_save_choices', lambda: [{'id':'Ordinary_123', 'label':'Ordinary'}])
    with pytest.raises(ValueError):
        stardew_setup.selected_default_save('../private')
    runtime = StardewRuntime()
    received = []
    runtime.setup = lambda payload: received.append(payload)
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    try:
        service.dispatch('launch_default_copy', {'save_id':'Ordinary_123', 'copy_authorized':False})
        assert received[-1]['copy_authorized'] is False
        assert received[-1]['source'].endswith('/.config/StardewValley/Saves/Ordinary_123')
        assert service.snapshot()['plan'] is None
        assert not service.snapshot()['reviewed']
    finally:
        service.close()
