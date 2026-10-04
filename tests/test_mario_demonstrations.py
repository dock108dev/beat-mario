"""Behavioral recording and real Lua controller tests with simulated game state."""
from copy import deepcopy
from pathlib import Path
import time

from lupa.lua51 import LuaRuntime
import pytest

from smb3_agent import mario_demonstrations as demos
from smb3_agent.conversation_service import ConversationService
from smb3_agent.mario_plan_runtime import runtime_fields
from test_conversation_service import FakeLiveManager, FakeRuntime


def frames(count=3, x=1600):
    return [dict(zip(demos.COLUMNS, [i, x+i, 100, 16, 0, 0, 0, 0, 1, 1, 64, 0, 0, 4, 2, 33, x+i+1, 100]))
            for i in range(count)]


class RecordingLive(FakeLiveManager):
    def __init__(self, path):
        super().__init__(path)
        self._game_file_sha256 = 'fixture-cart'
        self.commands = []
        self.rows = frames()

    def demonstration_command(self, identity, action, session):
        assert session == self.live.session_id
        if self.live.control_owner != 'player':
            raise ValueError('player control required')
        directory = self.live.artifact_dir / 'b2'
        directory.mkdir(parents=True, exist_ok=True)
        self.commands.append(action)
        if action == 'start':
            directory.joinpath('recording-' + identity + '.trace').write_text(
                ''.join(','.join(str(row[k]) for k in demos.COLUMNS)+'\n' for row in self.rows))
        if action in {'start', 'stop'}:
            directory.joinpath('recording.ack').write_text(identity + (' recording' if action == 'start' else ' stopped'))
        return directory


@pytest.fixture
def service(tmp_path):
    live = RecordingLive(tmp_path / 'live')
    return ConversationService(live, runtime=FakeRuntime(live), artifacts_root=tmp_path / 'conversation')


def record(service):
    service.dispatch('player_play')
    assert service.dispatch('record_start')['recording']['active']['status'] == 'recording'
    assert not service.runtime.calls
    with pytest.raises(ValueError, match='Stop recording'):
        service.dispatch('message', {'text': 'find a coin route'})
    assert service.dispatch('record_stop')['recording']['draft']['frame_count'] == 3
    result = service.dispatch('record_save', {'name': 'Stairs', 'lesson': 'Hold jump to climb'})
    return result['demonstrations'][0]['id']


def test_full_record_review_edit_use_outcome_reopen_delete(service):
    identity = record(service)
    state = service.dispatch('demo_review', {'demonstration_id': identity})
    assert state['demonstration_review']['preview'][0]['buttons'] == 33
    service.dispatch('demo_edit', {'demonstration_id': identity, 'name': 'My stairs', 'lesson': 'Run and jump'})
    state = service.dispatch('demo_use', {'demonstration_id': identity})
    assert 'frame by frame' in state['message']
    assert not service.runtime.calls
    assert state['plan']['resource_limits']['maximum_attempts'] == 1
    service.dispatch('message', {'text': 'yes'})
    plan = service.runtime.calls[-1][1]
    assert runtime_fields(plan)['demonstration_id'] == identity
    assert plan['demonstration']['lesson'] == 'Run and jump'
    service.runtime.state.update(state='finished', outcome='completed_stop', terminal_frame=10, events=[
        {'event': 'demonstration_applied'}, {'event': 'demonstration_frame'}, {'event': 'demonstration_sequence_completed'}])
    service.live_manager.live.control_owner = 'player'
    service.live_manager.live.input_neutralized = True
    service.live_manager.live.takeover_terminal_reason = 'completed_stop'
    outcome = service.snapshot()['outcome']['demonstration_result']
    assert outcome['application_observed'] and outcome['sequence_completed_observed']
    assert outcome['helped_overcome_failure'] is None
    reopened = ConversationService(service.live_manager, runtime=FakeRuntime(service.live_manager), artifacts_root=service.root)
    state = reopened.snapshot()
    assert state['plan'] is None and state['recording']['active'] is None
    assert state['history'][0]['demonstration_result'] == outcome
    assert state['demonstrations'][0]['name'] == 'My stairs'
    reopened.dispatch('demo_delete', {'demonstration_id': identity})
    assert not reopened.snapshot()['demonstrations']
    assert reopened.snapshot()['history'][0]['demonstration_result'] == outcome


def test_record_control_exclusion_and_urgent_stop(service):
    service.dispatch('message', {'text': 'find a coin route'})
    service.dispatch('message', {'text': 'yes'})
    with pytest.raises(ValueError, match='Stop companion'):
        service.dispatch('record_start')
    service.dispatch('stop')
    service.dispatch('record_start')
    calls = deepcopy(service.runtime.calls)
    state = service.dispatch('message', {'text': 'STOP RIGHT NOW WAIT'})
    assert state['recording']['active'] is None
    assert state['recording']['draft']['reason'] == 'stopped'
    assert service.runtime.calls == calls
    assert state['retry_scope'] is None


def test_cartridge_changed_saved_trace_changed_and_normal_speed(service):
    identity = record(service)
    service.live_manager._game_file_sha256 = 'other'
    with pytest.raises(ValueError, match='same cartridge'):
        service.dispatch('demo_use', {'demonstration_id': identity})
    service.live_manager._game_file_sha256 = 'fixture-cart'
    state = service.dispatch('demo_use', {'demonstration_id': identity})
    plan = deepcopy(state['plan'])
    plan['practice_expires_epoch'] = int(time.time()) + 600
    with pytest.raises(ValueError, match='normal speed'):
        runtime_fields({**plan, 'requested_speed': 'turbo'})
    service.demonstrations.edit(identity, name='Changed', lesson='Changed lesson')
    with pytest.raises(ValueError, match='changed'):
        service.dispatch('message', {'text': 'yes'})
    assert not service.runtime.calls


def test_disable_revokes_attempt_and_requires_new_review(service):
    identity = record(service)
    service.dispatch('demo_use', {'demonstration_id': identity})
    service.dispatch('message', {'text': 'yes'})
    state = service.dispatch('demo_disable')
    assert state['plan'] is None and state['retry_scope'] is None
    assert service.runtime.calls[-1][0] == 'stop'
    assert state['outcome']['demonstration_result']['application_observed'] is False
    with pytest.raises(ValueError):
        service.dispatch('retry')


def test_trim_segment_continuity_tamper_and_path_safety(service):
    service.live_manager.rows = frames(8)
    service.dispatch('record_start')
    service.dispatch('record_stop')
    state = service.dispatch('record_save', {'name': 'Short segment', 'lesson': 'Take this jump', 'first': '2', 'last': '5'})
    identity = state['demonstrations'][0]['id']
    saved = service.demonstrations.load(identity)
    assert len(saved['frames']) == 3 and saved['frames'][0]['frame'] == 2
    with pytest.raises(ValueError):
        service.demonstrations.load('../anything')
    bad = frames()
    bad[1]['frame'] += 1
    with pytest.raises(ValueError, match='discontinuous'):
        demos.validate_rows(bad)
    bad = frames()
    bad[1]['dying'] = 1
    with pytest.raises(ValueError, match='alive'):
        demos.validate_rows(bad)
    saved['frames'][0]['buttons'] = 1
    from smb3_agent.mario_coaching import CoachingStore
    CoachingStore(service.demonstrations._path(identity)).write(saved)
    with pytest.raises(ValueError, match='changed'):
        service.demonstrations.load(identity)


def test_disconnect_retains_raw_trace_but_never_restores_recording(service):
    service.dispatch('record_start')
    service.live_manager.live.session_id = 'replacement'
    state = service.snapshot()
    assert state['recording']['active'] is None
    assert state['recording']['draft']['saveable'] is False
    with pytest.raises(ValueError, match='Record and stop'):
        service.dispatch('record_save', {'name': 'No', 'lesson': 'No'})
    assert Path(state['recording']['draft']['source_path']).exists()


def lua_host(tmp_path, monkeypatch):
    directory = tmp_path / 'b2'
    directory.mkdir()
    env = {'SMB3_B2_DIRECTORY': str(directory), 'SMB3_LIVE_SESSION_ID': 'testsession',
           'SMB3_TAKEOVER_RECLAIM_PATH': str(tmp_path / 'reclaim'), 'SMB3_LIVE_DETACH_PATH': str(tmp_path / 'detach')}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
        frame=0; writes=0; buttons={A=true,right=true}; ram={}
        memory={readbyte=function(a) return ram[a] or 0 end,
                readbytesigned=function(a) return ram[a] or 0 end}
        movie={framecount=function() return frame end}
        emu={unpause=function() end, speedmode=function() end, pause=function() end}
        joypad={get=function() return buttons end, set=function(_, b) writes=writes+1; buttons=b end}
        gui={gdscreenshot=function() return '' end}
        function set_state(x,y,vx,vy,form,air)
            ram[0x90]=x%256; ram[0x75]=math.floor(x/256); ram[0xA2]=y%256; ram[0x87]=math.floor(y/256)
            ram[0xBD]=vx; ram[0xCF]=vy; ram[0xED]=form; ram[0xD8]=air
            ram[0x727]=0;ram[0x70A]=1;ram[0x77]=1;ram[0x79]=64;ram[0x736]=4;ram[0x7967]=2
        end
        set_state(1600,100,16,0,0,0)
    ''')
    return lua, directory


def test_real_lua_passive_frame_pairing_stop_and_ownership(tmp_path, monkeypatch):
    lua, directory = lua_host(tmp_path, monkeypatch)
    lua.execute("D=dofile('scripts/fceux_demonstration.lua')")
    identity = 'a'*32
    request = directory / 'recording.request'
    request.write_text(identity + ' start testsession\n')
    lua.execute('D.poll(false); D.before(); set_state(1601,100,16,0,0,0); D.after()')
    assert lua.globals().writes == 0
    row = demos.read_trace(directory / ('recording-'+identity+'.trace'))[0]
    assert row['x'] == 1600 and row['end_x'] == 1601 and row['buttons'] == 33
    lua.execute('frame=1; D.before(); set_state(1602,100,16,0,0,0); D.after(); D.poll(true)')
    assert directory.joinpath('recording.ack').read_text().endswith('ownership_changed')
    assert lua.globals().writes == 0
    assert len(demos.read_trace(directory / ('recording-'+identity+'.trace'))) == 2
    lua.execute("D=dofile('scripts/fceux_demonstration.lua')")
    request.write_text('b'*32 + ' start testsession\n')
    lua.execute('D.poll(false); D.before(); D.after()')
    request.write_text('b'*32 + ' stop testsession\n')
    lua.execute('D.poll(false)')
    assert directory.joinpath('recording.ack').read_text().endswith('stopped')
    assert not lua.globals().D.active


def start_lua_replay(lua, directory, rows):
    record = {'frames': rows}
    demos.write_replay(directory / 'demonstration.trace', record)
    directory.joinpath('initial.request').write_text(
        f'session_id=testsession\nepoch=1\nrevision=1\npath_choice=coin_balanced\nstop_point=world_1_1_exit\n'
        f'expires_epoch={int(time.time())+180}\nspeed=1\ndemonstration_id={"a"*32}\ndemonstration_frames={len(rows)}\n')
    lua.execute("M=dofile('scripts/fceux_b2_plan.lua'); M.start({epoch='1'}); M.completed_opening=true; M.last_lives=4")


def test_real_lua_replay_overrides_route_inputs_and_finishes(tmp_path, monkeypatch):
    lua, directory = lua_host(tmp_path, monkeypatch)
    rows = frames()
    start_lua_replay(lua, directory, rows)
    for i in range(3):
        lua.execute(f'frame={i}; set_state({1600+i},100,16,0,0,0); M.before_frame({{left=true,B=true}})')
        assert lua.globals().buttons.A and lua.globals().buttons.right
        assert not lua.globals().buttons.left and not lua.globals().buttons.B
        lua.execute('M.audit_input()')
    lua.execute('set_state(1603,100,16,0,0,0)')
    with pytest.raises(Exception, match='completed_stop'):
        lua.execute('M.before_frame({})')
    log = directory.joinpath('events.log').read_text()
    assert 'event=demonstration_applied' in log
    assert log.count('event=demonstration_frame ') == 3
    assert 'event=demonstration_sequence_completed' in log
    assert not lua.globals().buttons.A and not lua.globals().buttons.right
    lua.execute('assert(M.confirm_neutral())')


@pytest.mark.parametrize('failure', ['position', 'form', 'velocity', 'level', 'death', 'reclaim', 'missed', 'end_drift'])
def test_real_lua_incompatible_drift_and_interruptions(tmp_path, monkeypatch, failure):
    lua, directory = lua_host(tmp_path, monkeypatch)
    start_lua_replay(lua, directory, frames(1))
    if failure == 'missed':
        lua.execute('set_state(1650,100,16,0,0,0)')
    else:
        lua.execute('M.before_frame({})')
        if failure in {'position','end_drift'}:
            lua.execute('set_state(1700,100,16,0,0,0)')
        elif failure == 'form':
            lua.execute('ram[0xED]=1')
        elif failure == 'velocity':
            lua.execute('ram[0xBD]=50')
        elif failure == 'level':
            lua.execute('ram[0x727]=1')
        elif failure == 'death':
            lua.execute('ram[0x736]=3')
        elif failure == 'reclaim':
            tmp_path.joinpath('reclaim').touch()
    # Extend the replay for per-frame state mismatch scenarios.
    if failure in {'position','form','velocity','level'}:
        lua.execute('M.demo_index=1')
    expected = 'death' if failure == 'death' else 'reclaimed' if failure == 'reclaim' else 'demonstration_entry_missed' if failure == 'missed' else 'demonstration_drift'
    with pytest.raises(Exception, match=expected):
        lua.execute('M.before_frame({right=true})')
    assert not lua.globals().buttons.right
    assert lua.globals().M.stopped
    assert 'event=demonstration_sequence_completed' not in directory.joinpath('events.log').read_text()


def test_fresh_attempt_preparation_is_input_free_and_cancellable(service):
    identity = record(service)
    calls = []
    def restart(*, expected_session, cancelled):
        assert not cancelled()
        calls.append(expected_session)
        service.live_manager.live.session_id = 'fresh-demo-session'
    service.live_manager.restart_coaching_session = restart
    state = service.dispatch('demo_fresh')
    assert calls == ['fixture-session'] and state['plan'] is None
    assert not service.runtime.calls
    state = service.dispatch('demo_use', {'demonstration_id': identity})
    assert state['plan']['session_id'] == 'fresh-demo-session'
    service.dispatch('message', {'text': 'yes'})
    with pytest.raises(ValueError, match='normal speed'):
        service.dispatch('speed', {'rate': 'turbo'})


def test_native_manager_blocks_recording_start_before_ack_and_legacy_input(tmp_path):
    from types import SimpleNamespace
    from smb3_agent.live_observation import LiveObservationManager
    manager = LiveObservationManager()
    manager._accumulator = SimpleNamespace(artifact_dir=tmp_path)
    directory = tmp_path / 'b2'
    directory.mkdir()
    identity = 'a'*32
    directory.joinpath('recording.request').write_text(identity + ' start session')
    with pytest.raises(ValueError, match='Stop recording'):
        manager._require_no_recording()
    directory.joinpath('recording.ack').write_text(identity + ' recording')
    with pytest.raises(ValueError, match='Stop recording'):
        manager._require_no_recording()
    directory.joinpath('recording.ack').write_text(identity + ' stopped')
    manager._require_no_recording()


def test_recorder_stop_timeout_never_saves_open_trace(service, monkeypatch):
    service.dispatch('record_start')
    original = service.live_manager.demonstration_command
    def no_ack(identity, action, session):
        if action == 'stop':
            return service.live_manager.live.artifact_dir / 'b2'
        return original(identity, action, session)
    service.live_manager.demonstration_command = no_ack
    ticks = iter([0, 0, 4])
    monkeypatch.setattr(time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(time, 'sleep', lambda seconds: None)
    with pytest.raises(ValueError, match='awaiting'):
        service.recording.stop()
    assert service.recording.draft is None
    assert service.recording.current


def test_saved_visual_frames_are_local_and_deleted_with_demonstration(tmp_path):
    from PIL import Image
    image = tmp_path / 'recorded.png'
    Image.new('RGB', (256, 224)).save(image)
    store = demos.DemonstrationStore(tmp_path / 'demonstrations')
    saved = store.save(frames(), name='Segment', lesson='Jump', cartridge='cart',
                       source={'images': [{'frame': 0, 'path': str(image)}]})
    saved_image = Path(saved['images'][0]['path'])
    assert saved_image.exists()
    assert store.load(saved['id'])['images'] == saved['images']
    store.delete(saved['id'])
    assert not saved_image.exists()
    assert image.exists()


def test_disable_unstarted_proposal_clears_choice_without_input(service):
    identity = record(service)
    service.dispatch('demo_use', {'demonstration_id': identity})
    state = service.dispatch('demo_disable')
    assert state['plan'] is None and not service.runtime.calls
    assert state['demonstrations'][0]['id'] == identity


def test_real_manager_record_requests_do_not_reenter_its_lock(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from smb3_agent.companion_session import Freshness
    from smb3_agent.live_observation import LiveObservationManager
    manager = LiveObservationManager()
    # Fail deterministically if the manager's locking snapshot is reentered.
    monkeypatch.setattr(manager, 'snapshot', lambda: pytest.fail('reentered observation lock'))
    with pytest.raises(ValueError, match='Open a fresh'):
        manager.demonstration_command('a'*32, 'start', 'session')
    snapshot = SimpleNamespace(session_id='session', artifact_dir=tmp_path, takeover_capable=True,
                               control_owner='player', freshness=Freshness.FRESH)
    manager._accumulator = SimpleNamespace(snapshot=lambda: snapshot)
    manager._allow_takeover = True
    manager._takeover_controller = object()
    manager._process = SimpleNamespace(poll=lambda: None)
    directory = manager.demonstration_command('a'*32, 'play', 'session')
    assert directory.joinpath('recording.request').read_text() == 'a'*32+' play session\n'
    manager.demonstration_command('a'*32, 'stop', 'session')
    assert directory.joinpath('recording.request').read_text() == 'a'*32+' stop session\n'


def test_player_play_mailbox_is_consumed_once_preserving_manual_pause(tmp_path, monkeypatch):
    lua, directory = lua_host(tmp_path, monkeypatch)
    lua.execute("unpauses=0; emu.unpause=function() unpauses=unpauses+1 end; D=dofile('scripts/fceux_demonstration.lua')")
    directory.joinpath('recording.request').write_text('a'*32+' play testsession\n')
    lua.execute('D.poll(false); D.poll(false); D.poll(false)')
    assert lua.globals().unpauses == 1
    assert lua.globals().writes == 0
    assert not lua.globals().D.active


def test_visible_time_trim_saves_exact_segment_and_preserves_draft_on_refusal(service):
    service.live_manager.rows = frames(180)
    service.dispatch('record_start')
    service.dispatch('record_stop')
    for start, end in [('nan', '2'), ('-1', '2'), ('2', '1'), ('0', '4')]:
        with pytest.raises(ValueError, match='Choose'):
            service.dispatch('record_save', {'name': 'Stairs', 'lesson': 'Climb',
                             'start_seconds': start, 'end_seconds': end})
        assert len(service.recording.draft['frames']) == 180
        assert not service.demonstrations.list()
    result = service.dispatch('record_save', {'name': 'Stairs', 'lesson': 'Climb',
                              'start_seconds': '0.5', 'end_seconds': '2'})
    saved = service.demonstrations.load(result['demonstrations'][0]['id'])
    assert saved['frames'] == service.live_manager.rows[30:120]
    assert saved['source']['first'] == 30 and saved['source']['last'] == 120
    assert len(service.recording.draft['frames']) == 180
    assert demos.segment_range({'end_seconds': str(8 / 60)}, 8) == (0, 8)
