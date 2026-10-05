"""Flight/reward integration and real Lua controller under a simulated game host."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from smb3_agent import mario_flight as flight
from smb3_agent.conversation_service import ConversationService
from smb3_agent.mario_plan_runtime import runtime_fields, write_fields
from test_conversation_service import FakeLiveManager, FakeRuntime
from test_mario_demonstrations import lua_host


def observation(**changes):
    return dict(fresh=True, level_id=flight.LEVEL, form=3, air=0, x=450, y=384,
                player_is_dying=0, return_map=0, **changes)


@pytest.fixture
def service(tmp_path):
    live = FakeLiveManager(tmp_path / 'evidence')
    live._game_file_sha256 = 'flight-fixture-cartridge'
    # Actual map-to-level identity, not object set alone.
    live.live.samples = [SimpleNamespace(sequence=1, frame=0, object_set=0, world=0,
        map_page=0, map_cursor_x=64, map_cursor_y=32), SimpleNamespace(
        sequence=2, frame=1, object_set=1, world=0, form=3, air=0, x=450, y=384,
        player_is_dying=0, return_map=0, p_meter=0, flight_timer=0, lives=4)]
    live.live.checkpoint_id = 'world_1_1_clear'
    return ConversationService(live, runtime=FakeRuntime(live), artifacts_root=tmp_path / 'conversation')


@pytest.mark.parametrize('words', ['fly to get the hidden 1up', 'Can you soar up for the extra life?',
    'Get that sky one-up mushroom', 'Collect the hidden 1-up in World 1-1'])
def test_conversation_review_start_wire(service, words):
    state = service.dispatch('message', {'text': words})
    plan = state['plan']
    assert plan['flight_compatibility'] == flight.COMPATIBILITY
    assert plan['prerequisites']['ready'] and not service.runtime.calls
    service.dispatch('message', {'text': 'yes'})
    fields = runtime_fields(service.runtime.calls[-1][1])
    assert fields['path_choice'] == flight.PATH and fields['flight_objective'] == 'sky_hidden_1up_v2'
    assert service.snapshot()['retry_scope'] is None


@pytest.mark.parametrize('changes', [{'form': 0}, {'air': 1}, {'x': 700}, {'y': 0}, {'return_map': 1}, {'player_is_dying': 1}])
def test_missing_prerequisites_and_fresh_start_recheck(service, changes):
    for key, value in changes.items():
        setattr(service.live_manager.live.samples[-1], key, value)
    state = service.dispatch('message', {'text': 'fly to the hidden 1up'})
    assert not state['plan']['prerequisites']['ready']
    assert 'Super Leaf' in state['message']
    with pytest.raises(ValueError):
        service.dispatch('message', {'text': 'yes'})
    assert not service.runtime.calls


def test_form_change_after_review_refuses_start(service):
    service.dispatch('message', {'text': 'fly to the hidden 1up'})
    service.live_manager.live.samples[-1].form = 2
    with pytest.raises(ValueError, match='Raccoon'):
        service.dispatch('message', {'text': 'yes'})
    assert not service.runtime.calls


@pytest.mark.parametrize('words', ['fly to a reward', 'fly to the whistle', 'fly for coins',
    'get the hidden 1up in World 2-1', "don't fly to get the 1up"])
def test_ambiguity_never_starts_base_route(service, words):
    state = service.dispatch('message', {'text': words})
    assert state['plan'] is None and not service.runtime.calls


def reward_samples():
    base = dict(event='flight_observation', x=1432, y=144, lives=4, coins=5, level_coins=2,
        dying=0, form=3, p_meter=127, flight_timer=30, slot=2, object_state=2,
        object_id=11, object_x=1440, object_y=128, popup=0)
    return [dict(base, frame=0), dict(base, frame=1, object_state=0, popup=1),
            dict(base, frame=2, object_state=0, popup=0, lives=5)]


def test_reward_requires_hit_not_life_area_reveal_or_despawn():
    rows = reward_samples()
    assert flight.reconcile(rows)['reward_collected'] is True
    despawn = [dict(row, popup=0) for row in rows]
    result = flight.reconcile(despawn)
    assert result['reward_collected'] is None and result['reward_revealed'] and result['area_reached']
    assert flight.reconcile(rows[:1])['reward_collected'] is False
    assert flight.reconcile([dict(row, slot=-1, object_id=0, object_state=0) for row in rows])['reward_collected'] is None
    # A remote/despawned mushroom plus unrelated popup is insufficient.
    assert flight.reconcile([dict(row, object_x=1600) for row in rows])['reward_collected'] is None


def test_coin_rollover_other_rewards_gaps_deaths_and_conflicts():
    rows = reward_samples()
    rollover = [dict(rows[0], coins=99), dict(rows[1], coins=0, level_coins=3, lives=5, popup=0),
                dict(rows[2], coins=0, level_coins=3, lives=5)]
    result = flight.reconcile(rollover)
    assert result['coin_rollover_lives'] == 1 and result['reward_collected'] is False
    both = [rollover[0], dict(rollover[1], popup=1), dict(rollover[2], lives=6)]
    assert flight.reconcile(both)['reward_collected'] is True
    assert flight.reconcile([rows[0], dict(rows[1], frame=3), rows[2]])['reward_collected'] is None
    assert flight.reconcile(rows + [dict(rows[1], lives=9)])['reward_collected'] is None
    assert flight.reconcile(rows + [dict(rows[2], frame=3, lives=6)])['reward_collected'] is None
    assert flight.reconcile([dict(row, dying=1) for row in rows])['reward_collected'] is None
    assert flight.reconcile([])['status'] == 'uncertain'


def test_outcome_stop_and_reopen_retains_no_authority(service):
    service.dispatch('message', {'text': 'fly to the hidden 1up'})
    service.dispatch('message', {'text': 'yes'})
    service.runtime.state['events'] = reward_samples()[:1]
    state = service.dispatch('message', {'text': 'STOP RIGHT NOW WAIT'})
    assert state['outcome']['flight_result']['reward_revealed']
    assert not state['outcome']['flight_result']['reward_collected']
    assert state['outcome']['flight_result']['handback_confirmed']
    reopened = ConversationService(service.live_manager, runtime=FakeRuntime(service.live_manager), artifacts_root=service.root)
    state = reopened.snapshot()
    assert state['flight_knowledge']['attempts'] == 1
    assert state['plan'] is None and state['current_plan'] is None and state['retry_scope'] is None
    assert not reopened.runtime.calls
    service.live_manager._game_file_sha256 = 'other-cartridge'
    assert reopened.snapshot()['flight_knowledge']['attempts'] == 0


def lua_flight(tmp_path, monkeypatch):
    lua, directory = lua_host(tmp_path, monkeypatch)
    write_fields(directory / 'initial.request', dict(session_id='testsession', epoch=1, revision=1,
        path_choice=flight.PATH, stop_point=flight.STOP, speed=1, expires_epoch=9999999999,
        flight_objective='sky_hidden_1up_v2'))
    lua.execute('M=dofile("scripts/fceux_b2_plan.lua"); set_state(420,384,0,0,3,0); M.start({epoch="1"}); M.boundary("world_1_1_flight_runway"); held={}')
    return lua, directory


def test_actual_lua_runup_launch_flap_steer_collect_and_neutral(tmp_path, monkeypatch):
    lua, directory = lua_flight(tmp_path, monkeypatch)
    lua.execute('set_state(720,368,0,0,3,0); M.flight_step(held); M.before_frame(held)')
    assert lua.globals().buttons.right and lua.globals().buttons.B and not lua.globals().buttons.A
    lua.execute('frame=1; set_state(1032,368,48,0,3,0); ram[0x3DD]=127; M.flight_step(held); M.before_frame(held)')
    assert lua.globals().buttons.A
    lua.execute('frame=2; set_state(1410,160,16,-16,3,1); ram[0x56E]=30; M.flight_step(held); M.before_frame(held)')
    lua.execute('frame=3; set_state(1432,144,0,-16,3,1); ram[0x662]=2; ram[0x672]=11; ram[0x92]=160; ram[0x77]=5; ram[0xA4]=128; ram[0x89]=0; ram[0xAD]=100; ram[0xB6]=40; M.flight_step(held); M.before_frame(held)')
    # Target mushroom removal plus its game-owned 1UP popup. No life increment
    # yet; that award is delayed by the game's score animation.
    lua.execute('frame=4; ram[0x662]=0; ram[0x79E]=13; ram[0x7A3]=47; ram[0x7AD]=100; ram[0x7A8]=24')
    lua.execute('M.before_frame(held)')
    assert not lua.globals().buttons.A and not lua.globals().buttons.right
    assert not lua.globals().M.stopped
    # Hold neutral for the game's delayed life award before confirmed handback.
    for frame in range(5, 12):
        lua.execute(f'frame={frame}; ram[0x736]=5; M.flight_step(held); M.before_frame(held)')
    with pytest.raises(Exception, match='reward_hit_observed'):
        lua.execute('frame=12; M.flight_step(held)')
    assert not lua.globals().buttons.A and not lua.globals().buttons.right
    log = directory.joinpath('events.log').read_text()
    assert 'flight_launch_applied' in log and 'flight_progress_observed' in log and 'flight_reward_hit_observed' in log
    # Same event parser as production (key=value wire observations).
    events = [dict(part.split('=', 1) for part in line.split()) for line in log.splitlines()]
    assert flight.reconcile(events, terminal='reward_hit_observed')['reward_collected'] is True


@pytest.mark.parametrize('cause', ['reclaim', 'form', 'speed', 'budget'])
def test_actual_lua_interrupt_prerequisite_loss_and_finite_budget(tmp_path, monkeypatch, cause):
    lua, directory = lua_flight(tmp_path, monkeypatch)
    if cause == 'reclaim':
        tmp_path.joinpath('reclaim').write_text('stop')
    if cause == 'form':
        lua.execute('ram[0xED]=0')
    if cause == 'speed':
        lua.execute('set_state(720,368,0,0,3,0); M.flight_step(held)')  # Stage the long floor.
        lua.execute('ram[0x90]=42; ram[0x75]=4')  # x=1066, no P-speed
    if cause == 'budget':
        lua.execute('M.flight.frames=900')
    with pytest.raises(Exception, match='GAME_COMPANION_B2_STOP'):
        lua.execute('M.flight_step(held)')
    assert lua.globals().M.stopped
    assert not any(lua.globals().buttons[key] for key in ('A', 'B', 'left', 'right'))
    assert lua.eval('M.confirm_neutral()')
    assert 'neutral_ack' in directory.joinpath('events.log').read_text()


def test_wire_contract_rejects_scope_and_missing_identity(service):
    plan = service.dispatch('message', {'text': 'fly to the 1up'})['plan']
    assert runtime_fields(plan)['flight_objective']
    with pytest.raises(ValueError):
        runtime_fields(dict(plan, requested_speed='turbo'))
    with pytest.raises(ValueError):
        runtime_fields(dict(plan, flight_compatibility='invented'))
    with pytest.raises(ValueError):
        runtime_fields(dict(plan, resource_limits={'maximum_seconds': 600}))


def test_ordinary_ui_has_flight_plan_progress_and_saved_result():
    source = Path('src/smb3_agent/conversation_ui.py').read_text()
    assert 'id="conversation-flight"' in source
    assert 'entry.flight_result' in source and 'plan.flight_compatibility' in source


def test_native_authorization_rechecks_level_form_and_30_second_scope(tmp_path, service):
    from smb3_agent.live_observation import LiveObservationManager, LiveSessionAccumulator
    from smb3_agent.takeover import TakeoverController
    from test_b2_mario_runtime import sample
    manager = LiveObservationManager(artifacts_root=tmp_path)
    manager._takeover_controller = TakeoverController(tmp_path, tmp_path / 'control.request')
    manager._allow_takeover = True
    manager._process = SimpleNamespace(pid=42, poll=lambda: None)
    manager._game_file_sha256 = 'hash'
    accumulator = LiveSessionAccumulator('session1', 'token', tmp_path, takeover_controller=manager._takeover_controller)
    accumulator.ingest(sample(frame=600))
    accumulator.ingest(sample(2, frame=820, object_set=1, x=450, y=384, form=3, air=0))
    manager._accumulator = accumulator
    proposal = service.dispatch('message', {'text': 'fly to the hidden 1up'})['plan']
    fields = runtime_fields(dict(proposal, session_id='session1'))
    from dataclasses import replace
    latest = accumulator.samples[-1]
    accumulator.samples[-1] = replace(latest, form=0)
    with pytest.raises(ValueError, match='Raccoon'):
        manager.begin_session_plan(fields)
    assert not (tmp_path / 'control.request').exists()
    accumulator.samples[-1] = replace(latest, world=1)
    with pytest.raises(ValueError, match='World 1-1|fresh supported'):
        manager.begin_session_plan(fields)
    accumulator.samples[-1] = latest
    auth = manager.begin_session_plan(fields)
    from datetime import datetime
    assert (datetime.fromisoformat(auth.expires_at) - datetime.fromisoformat(auth.issued_at)).total_seconds() <= 30
    assert 'flight_objective=sky_hidden_1up_v2' in (tmp_path / 'b2/initial.request').read_text()


def test_observer_flight_fields_roundtrip_and_old_samples_remain_unknown():
    from smb3_agent.live_observation import parse_observer_line, LiveObservationError
    prefix = ('schema=game-companion-live-v1 session=s token=t seq=1 frame=1 actor=player buttons= '
              'world=0 object_set=1 map_page=0 map_cursor_x=64 map_cursor_y=32 x=450 y=384 '
              'form=3 lives=4 dying=0 return_map=0 ')
    items = ' '.join(f'item_{index}=0' for index in range(10))
    sample = parse_observer_line(prefix + items + ' air=0 p_meter=127 flight_timer=30')
    assert sample.air == 0 and sample.p_meter == 127 and sample.flight_timer == 30
    assert parse_observer_line(prefix + items).air is None
    with pytest.raises(LiveObservationError, match='flight observation'):
        parse_observer_line(prefix + items + ' p_meter=256')


def test_confirmed_reward_persists_and_reopened_history_is_input_free(service):
    service.dispatch('message', {'text': 'fly to the hidden 1up'})
    service.dispatch('message', {'text': 'yes'})
    service.runtime.state.update(state='finished', owner='player', outcome='reward_hit_observed',
        terminal_frame=4, events=[{'event': 'flight_objective_applied'}, *reward_samples()])
    service.live_manager.live.control_owner = 'player'
    service.live_manager.live.input_neutralized = True
    state = service.snapshot()
    assert state['outcome']['flight_result']['reward_collected'] is True
    assert state['outcome']['requested_objective_satisfied'] is True
    reopened = ConversationService(service.live_manager, runtime=FakeRuntime(service.live_manager), artifacts_root=service.root)
    state = reopened.dispatch('message', {'text': 'What flight results do you remember?'})
    assert state['flight_knowledge']['confirmed_collections'] == 1
    assert not reopened.runtime.calls and state['plan'] is None


def test_physical_entry_unknown_level_never_uses_same_tileset_guess():
    state = observation()
    state['level_id'] = 'world_1_1'
    assert not flight.prerequisites(state)['ready']
    state['level_id'] = flight.LEVEL
    state['fresh'] = False
    assert not flight.prerequisites(state)['ready']


def test_return_to_route_and_coin_plans_after_flight(service):
    service.dispatch('message', {'text': 'fly to the hidden 1up'})
    state = service.dispatch('select_intent', {'intent': 'existing base route'})
    assert runtime_fields(state['plan'])['path_choice'] == 'default'
    assert not state['plan'].get('flight_compatibility')
    service.dispatch('message', {'text': 'fly to the hidden 1up'})
    state = service.dispatch('message', {'text': 'find a coin route'})
    assert state['plan']['coin_compatibility'] and not state['plan'].get('flight_compatibility')


@pytest.mark.parametrize("interrupted", [False, True])
@pytest.mark.parametrize("cold", [False, True])
def test_preparation_press_native_mask_release_pause_and_one_use(tmp_path, monkeypatch, interrupted, cold):
    import time
    lua, directory = lua_host(tmp_path, monkeypatch)
    images = tmp_path / "images"
    images.mkdir()
    for key, value in {
        "SMB3_LIVE_OBSERVER_TOKEN": "token", "SMB3_LIVE_OBSERVER_LOG": str(tmp_path / "observer.log"),
        "SMB3_LIVE_IMAGE_DIR": str(images), "SMB3_TAKEOVER_CONTROL_PATH": str(tmp_path / "control"),
        "SMB3_TAKEOVER_AGENT_SCRIPT": "scripts/fceux_1_1_agent.lua",
        "SMB3_B2_PLAN_SCRIPT": "scripts/fceux_b2_plan.lua", "SMB3_B2_PAUSE_FOR_PLAN": "1",
    }.items():
        monkeypatch.setenv(key, value)
    lua.execute("""gui.register=function(f) redraw=f end
        emu.registerbefore=function(f) before=f end; emu.registerafter=function(f) after=f end
        emu.pause=function() paused=true end; emu.unpause=function() paused=false end
        emu.frameadvance=function() error('host_boundary') end
    """)
    if cold:
        lua.execute("""ram[0x727]=255; boot_frames=0
            emu.frameadvance=function()
              if boot_frames>=60 then error('host_boundary') end
              assert(not buttons.A and not buttons.right and not buttons.start)
              boot_frames=boot_frames+1; ram[0x727]=0
            end
        """)
    with pytest.raises(Exception, match="host_boundary"):
        lua.execute("dofile('scripts/fceux_live_takeover.lua')")
    if cold:
        assert lua.globals().boot_frames == 60 and lua.globals().paused
    request = directory / "preparation.request"
    request.write_text(f"{'a'*32} testsession 2 {int(time.time())+3} A,right\n")
    lua.execute("redraw(); before(); after()")
    assert lua.globals().buttons.A and lua.globals().buttons.right
    assert not lua.globals().paused
    if interrupted:
        (tmp_path / "reclaim").write_text("stop")
    lua.execute("before(); after(); before(); after(); before(); after()")
    assert not any(lua.globals().buttons[k] for k in ('A', 'B', 'left', 'right', 'start'))
    assert lua.globals().paused
    assert (directory / "preparation.ack").read_text() == 'a'*32 + (' reclaimed' if interrupted else ' neutral')
    writes = lua.globals().writes
    lua.execute("redraw(); before(); after()")
    assert lua.globals().writes == writes
    assert lua.globals().paused


@pytest.mark.parametrize('after_handback', [False, True])
def test_preparation_manager_receipt_returns_without_nested_lock(tmp_path, after_handback):
    import threading
    import time
    from smb3_agent.live_observation import LiveObservationManager, LiveSessionAccumulator
    from smb3_agent.takeover import TakeoverController
    from test_b2_mario_runtime import sample
    manager = LiveObservationManager(artifacts_root=tmp_path)
    manager._takeover_controller = TakeoverController(tmp_path, tmp_path / 'control.request')
    if after_handback:
        from dataclasses import replace
        from smb3_agent.takeover import TakeoverState
        manager._takeover_controller.snapshot = replace(manager._takeover_controller.snapshot,
                                                        state=TakeoverState.RETURNED)
        manager._takeover_controller.reclaim_path.touch()
    manager._allow_takeover = True
    manager._process = SimpleNamespace(pid=42, poll=lambda: None)
    manager._accumulator = LiveSessionAccumulator('session1', 'token', tmp_path, takeover_controller=manager._takeover_controller)
    manager._accumulator.ingest(sample(frame=600))
    result = []
    def run():
        result.append(manager.preparation_press(('right',), 15))
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    request = tmp_path / 'b2' / 'preparation.request'
    deadline = time.monotonic() + 1
    while not request.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert request.exists(), 'preparation request blocked before native dispatch'
    assert not manager._takeover_controller.reclaim_path.exists()
    nonce = request.read_text().split()[0]
    (request.parent / 'preparation.ack').write_text(nonce + ' neutral')
    worker.join(1)
    assert not worker.is_alive() and 'inputs released' in result[0]


def test_reclaim_reports_interruption_with_observed_progress():
    result = flight.reconcile([dict(event='flight_observation', frame=1, x=560, y=352,
        lives=4, coins=1, level_coins=1, dying=0, form=3, p_meter=0, flight_timer=0,
        slot=-1, object_state=0, object_id=0, object_x=0, object_y=0, popup=0)], terminal='reclaimed')
    assert result['status'] == 'interrupted'
    assert result['reward_collected'] is False


def test_actual_lua_stages_forward_over_preparation_shell(tmp_path, monkeypatch):
    lua, directory = lua_flight(tmp_path, monkeypatch)
    lua.execute('set_state(560,352,0,0,3,0); M.flight_step(held)')
    assert lua.globals().held.right and lua.globals().held.A
    lua.execute('set_state(740,300,16,16,3,1); M.flight_step(held)')
    assert lua.globals().held.left and not lua.globals().held.A
    lua.execute('set_state(720,368,0,0,3,0); M.flight_step(held)')
    assert lua.globals().M.flight.phase == 'runup'
    assert 'flight_runway_staged' in directory.joinpath('events.log').read_text()


def test_game_owned_coin_award_can_reach_hud_two_frames_later():
    base = dict(event='flight_observation', x=738, y=368, lives=4, dying=0, form=3,
        p_meter=0, flight_timer=0, slot=-1, object_state=0, object_id=0,
        object_x=0, object_y=0, popup=0)
    rows = [dict(base, frame=i+1, coins=coins, level_coins=level)
        for i, (coins, level) in enumerate([(1,1), (1,2), (1,2), (2,2)])]
    assert not flight.reconcile(rows)['accounting_uncertain']
    assert flight.reconcile(rows[:3])['accounting_uncertain']
    assert flight.reconcile([rows[0], dict(rows[1], coins=2, level_coins=1)])['accounting_uncertain']
    stalled = rows[:3] + [dict(rows[2], frame=i) for i in range(4,8)]
    assert flight.reconcile(stalled)['accounting_uncertain']


def test_history_polling_retains_full_evidence_without_repeating_native_trace(service):
    import json
    events = [{"event": "flight_observation", "frame": frame} for frame in range(100)]
    path = service.history.record("trace-test", {"status": "partial", "runtime": {"events": events},
                                                "flight_result": {"status": "partial"}})
    first = service.snapshot()["history"]
    row = next(row for row in first if row["attempt_id"] == "trace-test")
    assert "events" not in row["runtime"] and row["retained_event_count"] == 100
    assert json.loads(path.read_text())["runtime"]["events"] == events
    service.history.record("new-result", {"status": "refused"})
    assert any(row["attempt_id"] == "new-result" for row in service.snapshot()["history"])
    row["status"] = "tampered"
    assert next(row for row in service.snapshot()["history"] if row["attempt_id"] == "trace-test")["status"] == "partial"
