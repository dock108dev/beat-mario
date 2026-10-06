from copy import deepcopy
import threading
from types import SimpleNamespace

import pytest
from lupa.lua51 import LuaRuntime
from smb3_agent.mario_strategy import MarioStrategyAgent, validate_choice, CONTRACT
from smb3_agent.mario_plan_runtime import runtime_fields, write_fields, MarioPlanRuntime
from test_b2_mario_runtime import FakeLive, plan, emit


def choice(skill="hop", frames=18, delay=0):
    return dict(
        skill=skill,
        frames=frames,
        delay_frames=delay,
        reason="Use current state",
        expected_effect="Observe motion",
    )


def adaptive_plan():
    p = plan(path="opening_hop", stop="world_1_1_opening_end")
    p.update(
        coaching_compatibility="smb3/world-1-1/opening-hop/v1",
        strategy_contract=CONTRACT,
    )
    return p


def test_wire_scope_and_canceled_native_boundary(tmp_path):
    live = FakeLive(tmp_path)
    runtime = MarioPlanRuntime(live)
    runtime.start(adaptive_plan())
    emit(runtime, "strategy_boundary", boundary_id=1, air=0, lives=4)
    b = runtime.snapshot()["strategy_boundary"]
    runtime.strategy_skill(choice(), b)
    wire = list(tmp_path.glob("b2/*.request"))[0].read_text()
    assert "frames=18" in wire and "skill=hop" in wire
    runtime.control("stop")
    with pytest.raises(ValueError, match="authority changed"):
        runtime.strategy_skill(choice(), b)
    p = adaptive_plan()
    p["requested_speed"] = "turbo"
    with pytest.raises(ValueError):
        runtime_fields(p)


def lua_strategy(tmp_path, monkeypatch, *, expanded=False):
    directory = tmp_path / "b2"
    directory.mkdir()
    for k, v in {
        "SMB3_B2_DIRECTORY": directory,
        "SMB3_LIVE_SESSION_ID": "session1",
        "SMB3_TAKEOVER_RECLAIM_PATH": tmp_path / "reclaim",
        "SMB3_LIVE_DETACH_PATH": tmp_path / "detach",
    }.items():
        monkeypatch.setenv(k, str(v))
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
      frame=0; paused=false; buttons={}; ram={[0x90]=32,[0xA2]=128,[0x87]=1,[0x70A]=1,[0x736]=4}
      memory={readbyte=function(a) return ram[a] or 0 end,readbytesigned=function(a) return ram[a] or 0 end}
      movie={framecount=function() return frame end}
      emu={unpause=function() paused=false end,pause=function() paused=true end,speedmode=function() end}
      joypad={get=function() return buttons end,set=function(_,b) buttons=b end}
      gui={gdscreenshot=function() return '' end}
      M=dofile('scripts/fceux_b2_plan.lua')
    """)
    write_fields(
        directory / "initial.request",
        dict(
            session_id="session1",
            epoch=1,
            revision=1,
            path_choice="adaptive_segment" if expanded else "opening_hop",
            stop_point="world_1_1_segment_end" if expanded else "world_1_1_opening_end",
            strategy=2 if expanded else 1,
            speed=1,
            expires_epoch=9999999999,
        ),
    )
    lua.execute(
        "M.start({epoch='1'}); M.boundary('world_1_1_opening'); frame=frame+1; M.strategy_after_frame()"
    )
    return lua, directory


def test_real_lua_skill_parameters_effect_boundary_and_reclaim(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch)
    assert lua.globals().paused
    write_fields(
        d / "1-000001.request",
        dict(
            session_id="session1",
            epoch=1,
            expected_revision=1,
            sequence=1,
            command_id="skill1",
            action="strategy_skill",
            boundary_id=1,
            boundary_frame=1,
            skill="hop",
            frames=7,
            delay_frames=3,
        ),
    )
    lua.execute(
        "M.poll(); held={}; jump_count=0; walk_count=0; for i=1,10 do M.strategy_step(held); M.before_frame(held); if held.A then jump_count=jump_count+1 else walk_count=walk_count+1 end; frame=frame+1; ram[0x90]=ram[0x90]+2 end; M.strategy_step(held); M.strategy_after_frame()"
    )
    assert lua.globals().jump_count == 7 and lua.globals().walk_count == 3
    assert lua.globals().paused
    events = (d / "events.log").read_text()
    assert (
        "boundary_id=2" in events and "x=52" in events and "skill_frames=10" in events
    )
    (tmp_path / "reclaim").write_text("stop")
    lua.execute("M.poll()")
    assert lua.globals().M.stopped and not lua.globals().buttons.A
    assert "reason=reclaimed" in (d / "events.log").read_text()


def test_real_lua_rejects_changed_frame_and_out_of_scope_parameters(
    tmp_path, monkeypatch
):
    lua, d = lua_strategy(tmp_path, monkeypatch)
    write_fields(
        d / "1-000001.request",
        dict(
            session_id="session1",
            epoch=1,
            expected_revision=1,
            sequence=1,
            command_id="skill1",
            action="strategy_skill",
            boundary_id=1,
            boundary_frame=1,
            skill="walk_right",
            frames=26,
            delay_frames=0,
        ),
    )
    lua.execute("M.poll()")
    assert lua.globals().M.stopped
    assert "invalid_strategy_skill" in (d / "events.log").read_text()


def test_python_loop_supplies_observed_effect_and_rejects_late_reply(tmp_path):
    class Runtime:
        state = dict(
            owner="agent",
            state="paused",
            session_id="s",
            revision=1,
            emulator_pid=42,
            strategy_boundary=dict(
                boundary_id="1", frame="0", x="32", y="384", air="0"
            ),
        )
        commands = []

        def snapshot(self):
            return deepcopy(self.state)

        def strategy_skill(self, result, boundary):
            self.commands.append(result)
            self.state["strategy_boundary"] = dict(
                boundary_id="2", frame="18", x="70", y="344", air="1"
            )

        def control(self, _):
            self.state["owner"] = "player"

    runtime = Runtime()
    entered = threading.Event()
    release = threading.Event()
    supplied = []

    class Provider:
        def infer(self, role, ctx, schema, cancel):
            supplied.append(ctx)
            if len(supplied) == 2:
                entered.set()
                release.wait(2)
            return choice(
                "hop" if len(supplied) == 1 else "walk_right",
                18 if len(supplied) == 1 else 12,
            )

    service = SimpleNamespace(
        runtime=runtime,
        _control_generation=0,
        _outcome={
            "status": "changed_strategy_boundary",
            "neutralized": True,
            "controller_owner": "player",
            "ignored_history": "x" * 40000,
        },
        _lock=threading.RLock(),
        ai=None,
        _message=lambda *a: None,
    )
    agent = MarioStrategyAgent(service, Provider())
    agent.start(dict(model_intent={"constraints": ["low jump"]}))
    assert entered.wait(2)
    assert len(str(supplied[0])) < 10000
    assert supplied[0]["previous_attempt_outcome"]["handback_confirmed"] is True
    assert supplied[0]["authority"]["review_and_start_observed"] is True
    assert supplied[1]["observation"]["air"] == "1"
    assert supplied[1]["prior_effects"][0]["decision"]["frames"] == 18
    assert supplied[1]["prior_effects"][0]["effect"]["x"] == "70"
    agent.stop()
    runtime.control("stop")
    release.set()
    agent.worker.join(2)
    assert len(runtime.commands) == 1


@pytest.mark.parametrize(
    "result",
    [
        choice("walk_right", 25),
        choice("walk_right", 12, 3),
        choice("inspect", 2),
        choice("hop", 18, 13),
    ],
)
def test_invalid_choice_cannot_reach_controller(result):
    with pytest.raises(ValueError):
        validate_choice(result)


def test_segment_contract_cannot_expand_legacy_wire_without_its_contract():
    from smb3_agent.mario_segment import expand_plan
    p = adaptive_plan()
    expand_plan(p)
    p['jump_delay_frames'] = 5  # Existing opening advice cannot block the scoped segment.
    assert runtime_fields(p)['strategy'] == 2
    p['strategy_contract'] = CONTRACT
    with pytest.raises(ValueError):
        runtime_fields(p)


def test_segment_landing_stops_on_observed_ground_and_arrival_requires_ground(tmp_path, monkeypatch):
    lua, directory = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.execute('ram[0xD8]=1')
    write_fields(directory/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='land1', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill='land_right', frames=48, delay_frames=0))
    lua.execute('M.poll(); held={}; M.strategy_step(held); frame=frame+1; ram[0xD8]=0; M.strategy_step(held)')
    assert lua.globals().paused and lua.globals().M.strategy_frames == 1
    assert not lua.globals().held.A and not lua.globals().held.right
    lua.execute('ram[0x75]=2; ram[0x90]=200; ram[0xD8]=1; M.before_frame({})')
    assert not lua.globals().M.stopped
    with pytest.raises(Exception, match='completed_stop'):
        lua.execute('ram[0xD8]=0; M.before_frame({})')
    assert 'segment_arrival_observed' in (directory/'events.log').read_text()


def test_strategy_memory_compatibility_supersession_and_reset_preserve_history(tmp_path):
    from smb3_agent.mario_coaching import CoachingStore
    from smb3_agent.mario_segment import remember, compatible_guidance
    store = CoachingStore(tmp_path/'coaching.json')
    first = remember(store, {'constraints':['short hops'], 'objective':'early segment'}, 'Use short hops', 'cart')
    assert compatible_guidance(store.read()['coaching'], 'other') == ([], [first['id']])
    second = remember(store, {'constraints':['land first'], 'objective':'early segment'}, 'Land first', 'cart')
    rows = store.read()['coaching']
    assert rows[0]['status'] == 'superseded'
    applicable, excluded = compatible_guidance(rows, 'cart')
    assert [r['id'] for r in applicable] == [second['id']] and not excluded
    history = tmp_path/'historical-outcome.json'
    history.write_text(__import__('json').dumps({'requested':first, 'improvement':None}))
    store.reset()
    assert not store.read()['coaching'] and first['id'] in history.read_text()


def test_native_objects_and_unsafe_animation_are_facts_not_bounce():
    from smb3_agent.mario_segment import observed_state
    facts = observed_state({'air': '0', 'dying': '1', 'vx': '24', 'vy': '-64',
        'object_2_x': '360', 'object_2_y': '320', 'object_2_state': '1', 'object_2_id': '9'})
    assert facts['unsafe_animation'] and facts['ground_contact']
    assert facts['vertical_pixels_per_frame'] == -4
    assert facts['active_objects'] == [{'slot': 2, 'x': 360, 'y': 320, 'state': 1, 'id': 9}]
    assert 'Unknown' in facts['predictions']


@pytest.mark.parametrize('skill', ['run_hop', 'run_right', 'build_run', 'land_run_right'])
def test_real_lua_running_skill_is_bounded_and_releases(tmp_path, monkeypatch, skill):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    if skill == 'land_run_right':
        lua.execute('ram[0xD8]=1')
    write_fields(d/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='run1', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill=skill, frames=8, delay_frames=0))
    lua.execute('M.poll(); held={}; M.strategy_step(held)')
    assert lua.globals().held.B and lua.globals().held.right
    assert bool(lua.globals().held.A) == (skill == 'run_hop')
    lua.execute('for i=1,8 do frame=frame+1; M.strategy_step(held) end')
    assert lua.globals().paused and lua.globals().M.strategy_frames == 8
    assert not lua.globals().held.A and not lua.globals().held.B


def test_segment_unsafe_animation_cannot_claim_grounded_arrival(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    with pytest.raises(Exception, match='unsafe_player_state'):
        lua.execute('ram[0x75]=2; ram[0x90]=200; ram[0xD8]=0; ram[0xF1]=1; M.before_frame({})')
    events = (d/'events.log').read_text()
    assert 'segment_arrival_observed' not in events and 'reason=unsafe_player_state' in events
    assert not lua.globals().buttons.A and not lua.globals().buttons.B


def test_running_skills_cannot_expand_legacy_or_jump_from_air():
    for skill in ['run_hop', 'run_right', 'build_run', 'land_run_right']:
        c = choice(skill, 8) | {'guidance_id': ''}
        validate_choice(c, expanded=True)
        with pytest.raises(ValueError):
            validate_choice(c)
    with pytest.raises(ValueError):
        validate_choice(choice('run_hop', 27) | {'guidance_id': ''}, expanded=True)


def test_native_boundary_exposes_actual_object_id_and_animation(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.execute('ram[0x661]=2; ram[0x671]=-90; ram[0x91]=100; ram[0xA3]=64; ram[0x88]=1; M.strategy_observation_pending=true; M.strategy_after_frame()')
    events = (d/'events.log').read_text()
    assert 'object_1_id=-90' in events and 'object_1_x=100' in events
    assert 'object_1_y=320' in events and 'dying=0' in events


def test_running_landing_releases_b_at_first_ground(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.execute('ram[0xD8]=1')
    write_fields(d/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='landrun', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill='land_run_right', frames=48, delay_frames=0))
    lua.execute('M.poll(); held={}; M.strategy_step(held); frame=frame+1; ram[0xD8]=0; M.strategy_step(held)')
    assert lua.globals().paused and lua.globals().M.strategy_frames == 1
    assert not lua.globals().held.A and not lua.globals().held.B and not lua.globals().held.right


def test_after_frame_inertia_arrival_is_confirmed_before_next_inference(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.execute('ram[0x75]=2; ram[0x90]=189; M.strategy_observation_pending=true; M.strategy_after_frame()')
    assert lua.globals().M.stopped
    events=(d/'events.log').read_text()
    assert 'segment_arrival_observed' in events and 'reason=completed_stop' in events
    assert not lua.globals().buttons.A and not lua.globals().buttons.B


@pytest.mark.parametrize('address,value', [(0xF1,1),(0xD8,1),(0x14,1),(0x727,1)])
def test_after_frame_never_claims_unsafe_or_changed_scene_arrival(tmp_path, monkeypatch, address, value):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.globals().ram[address]=value
    lua.execute('ram[0x75]=2; ram[0x90]=189; M.strategy_observation_pending=true; M.strategy_after_frame()')
    assert 'segment_arrival_observed' not in (d/'events.log').read_text()


def test_gameplay_budget_reason_does_not_masquerade_as_player_interruption(tmp_path):
    live=FakeLive(tmp_path)
    runtime=MarioPlanRuntime(live)
    runtime.start(adaptive_plan())
    runtime.abort_strategy('decision_budget_exhausted', 'Mario gameplay decision budget exhausted')
    assert runtime.snapshot()['strategy_stop']['reason']=='decision_budget_exhausted'
    runtime.abort_strategy('no_progress', 'late error')
    assert runtime.snapshot()['strategy_stop']['reason']=='decision_budget_exhausted'


def test_inference_returning_after_attempt_deadline_cannot_emit_input(monkeypatch):
    import smb3_agent.mario_strategy as module
    now=[0.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: now[0])

    class Runtime:
        commands=[]
        reason=None
        state={'owner':'agent', 'state':'paused', 'session_id':'s', 'revision':1,
               'emulator_pid':42, 'strategy_boundary':{'boundary_id':'1','frame':'0','x':'32','air':'0'}}

        def snapshot(self):
            return deepcopy(self.state)

        def strategy_skill(self, *args):
            self.commands.append(args)

        def abort_strategy(self, reason, detail):
            self.reason=reason
            self.state['owner']='player'

    class Provider:
        def infer(self, *args):
            now[0]=121.0
            return choice()

    runtime=Runtime()
    service=SimpleNamespace(runtime=runtime, _control_generation=0, _outcome=None,
        _lock=threading.RLock(), ai=None, _message=lambda *args: None)
    agent=module.MarioStrategyAgent(service, Provider())
    agent.start({})
    agent.worker.join(2)
    assert not runtime.commands and runtime.reason=='wall_budget_exhausted'


@pytest.mark.parametrize('air,speed', [(0,40),(1,20)])
def test_runup_yields_on_native_speed_or_lost_ground_without_more_input(tmp_path, monkeypatch, air, speed):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    write_fields(d/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='runup', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill='build_run', frames=32, delay_frames=0))
    lua.execute('M.poll(); held={}; M.strategy_step(held)')
    assert lua.globals().held.right and lua.globals().held.B
    lua.execute(f'ram[0xBD]={speed}; ram[0xD8]={air}; M.strategy_step(held)')
    assert lua.globals().paused and lua.globals().M.strategy_frames==1
    assert not lua.globals().held.right and not lua.globals().held.B
    assert 'reason=runup_observed' in (d/'events.log').read_text()


def test_runup_cannot_start_airborne(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.execute('ram[0xD8]=1')
    write_fields(d/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='runup', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill='build_run', frames=32, delay_frames=0))
    lua.execute('M.poll()')
    assert lua.globals().M.stopped
    assert 'invalid_strategy_skill' in (d/'events.log').read_text()


def test_retreat_jump_immediate_lift_and_bounded_release(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    write_fields(d/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='evade', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill='retreat_hop', frames=16, delay_frames=0))
    lua.execute('M.poll(); held={}; M.strategy_step(held)')
    assert lua.globals().held.left and lua.globals().held.A
    assert not lua.globals().held.right and not lua.globals().held.B
    lua.execute('for i=1,16 do frame=frame+1; M.strategy_step(held) end')
    assert lua.globals().paused and lua.globals().M.strategy_frames==16
    assert not lua.globals().held.left and not lua.globals().held.A


@pytest.mark.parametrize('air,delay', [(1,0),(0,1)])
def test_retreat_jump_rejects_airborne_or_delayed_launch(tmp_path, monkeypatch, air, delay):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.execute(f'ram[0xD8]={air}')
    write_fields(d/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='evade', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill='retreat_hop', frames=16, delay_frames=delay))
    lua.execute('M.poll()')
    assert lua.globals().M.stopped
    assert 'invalid_strategy_skill' in (d/'events.log').read_text()


def test_native_special_projectile_position_wrapping_and_raw_id(tmp_path, monkeypatch):
    from smb3_agent.mario_segment import observed_state
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    lua.execute('ram[0x90]=250; ram[0x7FC6]=7; ram[0x5C9]=5; ram[0x5BF]=70; ram[0x7FD5]=1; M.strategy_observation_pending=true; M.strategy_after_frame()')
    line=(d/'events.log').read_text().splitlines()[-1]
    assert 'special_0_dx=11' in line and 'special_0_y=326' in line
    facts=observed_state({'special_0_id':'7','special_0_dx':'11','special_0_y':'326'})
    assert facts['special_objects']==[{'slot':0,'id':7,'relative_x_modulo_256':11,'y':326}]
    assert 'unknown' in facts['special_position_limits']


def test_wait_advances_bounded_frames_with_neutral_input(tmp_path, monkeypatch):
    lua, d = lua_strategy(tmp_path, monkeypatch, expanded=True)
    write_fields(d/'1-000001.request', dict(session_id='session1', epoch=1,
        expected_revision=1, sequence=1, command_id='waitshot', action='strategy_skill',
        boundary_id=1, boundary_frame=1, skill='wait', frames=8, delay_frames=0))
    lua.execute('M.poll(); held={}; M.strategy_step(held)')
    assert not any(bool(lua.globals().held[k]) for k in ['A','B','left','right','down','up'])
    lua.execute('for i=1,8 do frame=frame+1; M.strategy_step(held) end')
    assert lua.globals().paused and lua.globals().M.strategy_frames==8
