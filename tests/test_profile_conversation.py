"""Product-service and safety boundaries; simulated hosts are labeled fixtures."""
from dataclasses import asdict, replace
import http.client
import json
import threading
import time
from urllib.parse import urlencode

import pytest

from test_profile_runtime import Host, Driver, Gateway, profile
from smb3_agent.coordinate_contracts import WindowCoordinates, RelativePointerCalibration, relative_pointer_pulse
from smb3_agent.game_profiles import ExecutableProfile, ProfileError
from smb3_agent.host_contracts import HostError
from smb3_agent.profile_conversation import ProfileConversationService
from smb3_agent.profile_runtime import ProfileRuntime
from smb3_agent.skill_registry import exact_delta_verification


class ProductHost(Host):
    permission = True
    fail = None
    activation_count = 0

    def detect_window(self, *, require_foreground=True):
        if self.fail:
            raise HostError(self.fail)
        if require_foreground and not self.window.trusted:
            raise HostError('Foreground window required')
        return self.window

    def observe(self, root, *, execution=False):
        self.detect_window(require_foreground=execution)
        return super().observe(root)

    def activate(self):
        self.activation_count += 1
        self.window = replace(self.window, foreground=True)

    def permissions(self):
        return {'capture': self.permission, 'input': self.permission}


class ProductDriver(Driver):
    closed = False

    def close(self):
        self.neutralize()
        self.closed = True
        return self.receipt


class Launcher:
    def __init__(self):
        self.closed = False

    def binding(self, selection):
        if selection != {'pid': 123, 'started': 'started', 'window_id': '7'}:
            raise HostError('Not an owned window')
        return {'fixture': True}

    def windows(self):
        return []

    def close(self):
        self.closed = True


@pytest.fixture
def service(tmp_path):
    gateway = Gateway()
    gateway.inference_pending = threading.Event()
    gateway.worker_pid = None
    gateway.backend_identity = {'fixture': True}
    host = ProductHost(tmp_path)
    host.window = replace(host.window, foreground=False)
    def factory(selection, owned, folder):
        rt = ProfileRuntime(profile=profile(), host=host, gateway=gateway, driver_factory=ProductDriver,
            root=folder/'runtime', isolation_receipt={'disposable': True, 'load_save_verified': True,
                'evidence_references': ['simulated host, no native input']}, observe_background=True)
        svc._bound_bounds = host.window.bounds
        rt.state_callback = lambda phase: svc._phase(rt, phase)
        return rt
    svc = ProfileConversationService(artifacts_root=tmp_path/'product', profile=profile(),
        runtime_factory=factory, launcher=Launcher())
    svc.dispatch('connect', {'client_id':'page', 'profile_id':'test',
        'selection':{'pid':123,'started':'started','window_id':'7'}})
    settle(svc)
    yield svc
    gateway.unblock.set()
    svc.close()


def settle(svc):
    if svc._worker:
        svc._worker.join(2)
        assert not svc._worker.is_alive()


def send(svc, text='repay once'):
    svc.dispatch('chat', {'client_id':'page'})
    svc.dispatch('message', {'client_id':'page','text':text})
    settle(svc)
    return svc._plan


def reviewed(svc):
    plan = send(svc)
    svc.dispatch('review', {'client_id':'page','expected_plan_id':plan.plan_id,'expected_revision':plan.revision})
    settle(svc)
    return plan


def test_normal_service_observes_background_but_focuses_only_on_explicit_start(service):
    plan = reviewed(service)
    assert service.runtime.host.activation_count == 0
    assert service.snapshot()['runtime']['neutralized']
    service.dispatch('start', {'client_id':'page','expected_plan_id':plan.plan_id,'expected_revision':plan.revision})
    settle(service)
    state = service.snapshot()
    assert state['state'] == 'Completed'
    assert state['outcome']['after_values'] == {'cash':90000,'loan':90000}
    assert state['runtime']['owner'] == 'player'
    assert state['outcome']['release']['confirmed']
    assert service.runtime.host.activation_count == 1
    assert len(state['history']) == 1


@pytest.mark.parametrize('action', ['stop','reclaim','edit','ui_disconnect'])
def test_control_cancels_late_planner_without_waiting_for_planner_or_history(service, action):
    rt = service.runtime
    rt.gateway.block = True
    service.dispatch('message', {'client_id':'page','text':'repay once'})
    assert rt.gateway.entered.wait(1)
    assert rt._operation.locked()
    epoch = rt.control_epoch
    started = time.monotonic()
    state = service.dispatch(action, {'client_id':'page'})
    assert time.monotonic()-started < .1
    assert state['control_receipt']['confirmed']
    assert rt.control_epoch > epoch and rt.cancel.is_set()
    rt.gateway.unblock.set()
    settle(service)
    assert service.snapshot()['state'] == 'Stopped'
    assert service._plan is None and not rt.driver.sent and not rt._authority


def test_draft_edit_invalidates_exact_review_and_new_correction_needs_review(service):
    old = reviewed(service)
    service.dispatch('edit', {'client_id':'page'})
    with pytest.raises(ProfileError, match='changed'):
        service.dispatch('start', {'client_id':'page','expected_plan_id':old.plan_id,'expected_revision':old.revision})
    new = send(service, 'repay once, do not borrow')
    assert new.revision > old.revision
    assert not service.snapshot()['reviewed']
    assert not service.runtime.driver.sent


@pytest.mark.parametrize('fault', ['permission','window','geometry','lease'])
def test_independent_watchdog_revokes_review_on_connection_faults(service, fault):
    reviewed(service)
    rt = service.runtime
    if fault == 'permission':
        rt.host.permission = False  # simulated denial; never changes macOS permissions
    elif fault == 'window':
        rt.host.fail = 'Selected window disappeared'
    elif fault == 'geometry':
        rt.host.window = replace(rt.host.window, bounds=(-100, -1440, 800, 600))
    else:
        service._heartbeat = 0
    deadline = time.monotonic()+1
    while service.snapshot()['state'] != 'Needs attention' and time.monotonic() < deadline:
        service._watch_stop.wait(.01)
    assert service.snapshot()['state'] == 'Needs attention'
    assert rt.cancel.is_set() and not rt._reviewed and not rt._authority
    assert rt.release['confirmed'] and not rt.driver.sent


def test_stale_capture_never_reaches_planner_or_input(service):
    service.runtime.host.stale = True
    send(service)
    assert service.snapshot()['state'] == 'Needs attention'
    assert 'Stale' in service.snapshot()['reason']
    assert not service.runtime.gateway.entered.is_set()
    assert not service.runtime.driver.sent


def test_wrong_owned_window_is_refused_without_rebinding(service):
    with pytest.raises(HostError, match='owned'):
        service.dispatch('connect', {'client_id':'page','profile_id':'test',
            'selection':{'pid':123,'started':'started','window_id':'other'}})
    assert service.runtime.host.window.window_id == '7'


def test_unconfirmed_native_release_blocks_switch_and_start(service):
    plan = reviewed(service)
    service.runtime.driver.receipt = False
    assert not service.invalidate_for_switch()
    with pytest.raises(ProfileError):
        service.dispatch('start', {'client_id':'page','expected_plan_id':plan.plan_id,'expected_revision':plan.revision})
    service.runtime.driver.receipt = True
    assert service.dispatch('stop', {'client_id':'page'})['control_receipt']['confirmed']


def test_shutdown_cancels_pending_request_and_fresh_service_has_no_authority(service, tmp_path):
    rt = service.runtime
    rt.gateway.block = True
    service.dispatch('message', {'client_id':'page','text':'repay once'})
    assert rt.gateway.entered.wait(1)
    assert service.close()
    assert rt.cancel.is_set() and rt.driver.closed and rt.release['confirmed']
    assert not rt._events.thread.is_alive()
    assert service.close()
    fresh = ProfileConversationService(artifacts_root=tmp_path/'restart', profile=profile(),
        launcher=Launcher(), watchdog=False)
    assert not fresh.snapshot()['connected'] and not fresh.snapshot()['reviewed']
    assert fresh.close()


@pytest.mark.parametrize('scaling', [1,2])
def test_coordinate_mapping_includes_negative_origin_and_clamps_inside(scaling):
    coords = WindowCoordinates((-550,-1440,800,600),(800*scaling,600*scaling))
    assert coords.native_point(.5,.5) == (-150,-1140)
    assert coords.native_point(.9999,.9999) == (249,-841)
    for x,y in [(1,.5),(-.01,.1),(float('nan'),.1),(True,.1)]:
        with pytest.raises(HostError):
            coords.native_point(x,y)
    with pytest.raises(HostError):
        WindowCoordinates((0,0,800,600),(1200,900)).native_point(.5,.5)
    with pytest.raises(HostError, match='not qualified'):
        relative_pointer_pulse(5,0,80,RelativePointerCalibration('test','7','settings'))


@pytest.mark.parametrize('change', ['unknown-version','camera','executable','predicate','unbounded','missing-reference'])
def test_profile_registry_rejects_unsupported_configuration_before_authority(change):
    data = asdict(profile())
    if change == 'unknown-version':
        data['skills'][0]['verifier_contract'] = 'exact-deltas/v2'
    elif change == 'camera':
        data['capabilities'] += ('camera/v1',)
    elif change == 'executable':
        data['on_start'] = 'shell command'
    elif change == 'predicate':
        data['sensors'][0]['pattern'] = '(.*)'
    elif change == 'unbounded':
        data['skills'][0]['pulse_ms'] = 251
    else:
        del data['sensors'][0]['detector_id']
    with pytest.raises(ProfileError):
        ExecutableProfile.from_dict(data)


def test_integer_grouping_and_complete_delta_reconciliation(service):
    rt = service.runtime
    frame = rt.host.observe(rt.root)
    corrupt = replace(frame,text=tuple(replace(t,text='Cash: £1,0,0,000') if t.text.startswith('Cash') else t for t in frame.text))
    with pytest.raises(ProfileError, match='grouping'):
        rt.profile.values(corrupt)
    assert not exact_delta_verification({'cash':100000,'loan':100000},{'cash':90000,'loan':90001},(('cash',-10000),('loan',-10000)))
    assert not exact_delta_verification({'cash':100000},{'cash':90000,'loan':90000},(('cash',-10000),))


def test_profile_http_priority_bypasses_action_lock_and_keeps_origin_csrf_checks(monkeypatch, tmp_path):
    from smb3_agent import lab_ui
    from smb3_agent.companion_catalog import CatalogPreferenceStore
    monkeypatch.setattr(lab_ui,'CatalogPreferenceStore',lambda:CatalogPreferenceStore(tmp_path/'catalog.json'))
    server = lab_ui._new_lab_ui_server('127.0.0.1',0)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    def request(method,path,body=None,origin=None):
        conn = http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
        headers = {'Content-Type':'application/x-www-form-urlencoded'}
        if origin is not None:
            headers['Origin'] = origin
        conn.request(method,path,body=urlencode(body) if body else None,headers=headers)
        res = conn.getresponse()
        result = res.status,res.read().decode(),res.getheader('Referrer-Policy')
        conn.close()
        return result
    try:
        status,page,policy = request('GET','/openttd')
        assert status == 200 and 'profile-workspace' in page and policy == 'same-origin'
        token = server.csrf_token
        body = {'csrf_token':token,'action':'stop','payload':'{}'}
        with server.action_lock:
            status,page,_ = request('POST','/api/profile/conversation',body,f'http://127.0.0.1:{server.server_port}')
        assert status == 200 and json.loads(page)['control_receipt']['confirmed']
        assert request('POST','/api/profile/conversation',body,'null')[0] == 403
        assert request('POST','/api/profile/conversation',body,'http://external.example')[0] == 403
        assert request('POST','/api/profile/conversation',{**body,'csrf_token':'wrong'})[0] == 403
    finally:
        server.profile_conversation_service.close()
        server.shutdown()
        server.server_close()
        thread.join(2)
