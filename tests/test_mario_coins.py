"""Coin accounting and actual next-attempt route application (fixture evidence)."""
import time

import pytest

from smb3_agent import mario_coins as coins
from smb3_agent.conversation_service import ConversationService
from smb3_agent.mario_plan_runtime import runtime_fields
from test_conversation_service import FakeLiveManager, FakeRuntime


def events(counters=(0, 1, 1, 2), xs=(20, 30, 510, 520)):
    return [{"event": "coin_observation", "frame": str(i), "counter": str(c), "x": str(x)}
            for i, (c, x) in enumerate(zip(counters, xs))]


def test_observed_accounting_dedup_baseline_reset_and_gap():
    rows = events()
    result = coins.reconcile(rows + rows, finished=False)
    assert result["collected"] == 2
    assert result["segment_yields"]["opening"] == 1
    assert result["segment_yields"]["first_pipes"] == 1
    assert result["complete"] is False
    assert coins.reconcile(events((15, 16, 16, 17)), finished=False)["collected"] == 2
    assert coins.reconcile(events((9, 0, 1, 1)), finished=False)["collected"] is None
    rows[1]["frame"] = "100"
    assert coins.reconcile(rows, finished=False)["collected"] is None
    assert coins.reconcile([], finished=True)["collected"] is None


def test_conflicting_observation_and_counter_wrap_unknown():
    rows = events()
    assert coins.reconcile(rows + [{**rows[0], "counter": "2"}], finished=False)["collected"] is None
    assert coins.reconcile(events((255, 0, 0, 1)), finished=False)["collected"] is None


@pytest.fixture
def service(tmp_path):
    live = FakeLiveManager(tmp_path / "evidence")
    live._game_file_sha256 = "fixture-cartridge"
    return ConversationService(live, runtime=FakeRuntime(live), artifacts_root=tmp_path / "conversation")


def finish(service, counters=(0, 1, 1, 2), status="completed_stop"):
    route = service.runtime.calls[-1][1]["path_choice"]
    service.runtime.state.update(state="finished", owner="player", outcome=status, terminal_frame=10,
        events=[{"event": "coin_route_applied", "route": route}, *events(counters),
                *([{"event": "coin_level_finish_observed"}] if status == "completed_stop" else [])])
    service.live_manager.live.control_owner = "player"
    service.live_manager.live.input_neutralized = True
    service.live_manager.live.takeover_terminal_reason = status
    return service.snapshot()


@pytest.mark.parametrize("words", ["lets find a 100% coin route to the end", "Collect all the coins and finish", "Could you explore a route that gets coins?", "Find coins in World 1-1", "Can we find a coin route to the end?"])
def test_conversational_goal_and_wire(service, words):
    state = service.dispatch("message", {"text": words})
    assert state["plan"]["coin_compatibility"] == coins.COMPATIBILITY
    assert not service.runtime.calls
    service.dispatch("message", {"text": "yes"})
    plan = service.runtime.calls[-1][1]
    assert runtime_fields(plan)["path_choice"] == "coin_high"
    assert plan["stop_point"] == "world_1_1_exit"
    with pytest.raises(ValueError, match="finite approval"):
        runtime_fields({**plan, "practice_expires_epoch": int(time.time()) - 1})


def test_discovery_changes_retry_then_exploits_yield_reopens(service):
    service.dispatch("message", {"text": "find a coin route to the end"})
    service.dispatch("message", {"text": "yes"})
    assert finish(service)["outcome"]["coin_result"]["collected"] == 2
    service.dispatch("retry")
    assert runtime_fields(service.runtime.calls[-1][1])["path_choice"] == "coin_low"
    result = finish(service, (0, 0, 0, 1))["outcome"]["coin_result"]
    assert result["known_missed_lower_bound"] == 1
    service.dispatch("retry")
    assert service.runtime.calls[-1][1]["path_choice"] == "coin_balanced"
    finish(service)
    with pytest.raises(ValueError, match="budget ended"):
        service.dispatch("retry")
    reopened = ConversationService(service.live_manager, runtime=FakeRuntime(service.live_manager), artifacts_root=service.root)
    state = reopened.snapshot()
    assert state["plan"] is None and state["retry_scope"] is None
    assert state["coin_knowledge"]["attempts"] == 3
    assert state["coin_knowledge"]["known_opportunity_lower_bound"] == 2
    reopened.dispatch("message", {"text": "find a coin route"})
    assert reopened.snapshot()["plan"]["path_choice"] == "coin_balanced"
    service.live_manager._game_file_sha256 = "another-cartridge"
    assert reopened.snapshot()["coin_knowledge"]["attempts"] == 0


def test_death_stop_memory_partial_and_input_free_question(service):
    service.dispatch("message", {"text": "find a coin route for two attempts"})
    service.dispatch("message", {"text": "yes"})
    finish(service, status="death")
    service.dispatch("retry")
    assert service.runtime.calls[-1][1]["path_choice"] == "coin_low"
    state = service.dispatch("message", {"text": "STOP RIGHT NOW WAIT"})
    assert state["retry_scope"] is None
    assert state["outcome"]["neutralized"]
    calls = list(service.runtime.calls)
    service.dispatch("message", {"text": "What coin discoveries do you remember?"})
    assert service.runtime.calls == calls
    assert len(service.snapshot()["history"]) == 2


def test_lua_changes_across_level_and_observes_per_frame():
    from pathlib import Path
    controller = Path("scripts/fceux_b2_plan.lua").read_text()
    engine = Path("scripts/fceux_1_1_agent.lua").read_text()
    assert 'M.path_choice == "coin_high" and -20 or 20' in controller
    assert 'M.path_choice == "coin_high" and 28 or 12' in controller
    assert 'b2_plan.coin_window(m.x, scheduled_jumps)' in engine
    assert 'jump_frames = b2_plan.coin_jump_frames(m.x)' in engine
    assert 'event("coin_observation"' in controller


def test_landmark_boundary_shift_never_adds_cross_attempt_coins():
    def row(xs):
        result = coins.reconcile(events((0, 1, 1, 1), xs), finished=False)
        result['controller_application_observed'] = True
        return {'cartridge_sha256': 'cart', 'initial_plan': {'coin_compatibility': coins.COMPATIBILITY, 'path_choice': 'coin_high'}, 'coin_result': result}
    # The same single pickup can be attributed to either side of a band edge.
    history = [row((480, 490, 510, 520)), row((480, 510, 520, 530))]
    known = coins.knowledge(history, 'cart')
    assert sum(known['best_observed_segment_yields'].values()) == 2
    assert known['known_opportunity_lower_bound'] == 1
    assert coins.reconcile([], finished=False)['unvisited_landmarks'] == list(coins.LANDMARKS)


def test_active_coin_scope_refuses_mid_attempt_path_edits(service):
    service.dispatch('message', {'text': 'find a coin route'})
    service.dispatch('message', {'text': 'yes'})
    calls = list(service.runtime.calls)
    with pytest.raises(ValueError, match='fresh attempts'):
        service._queue(service.snapshot()['plan'], 'edit')
    assert service.runtime.calls == calls


def test_contextual_route_question_is_advice_only(service):
    service.dispatch('message', {'text': 'find a coin route'})
    plan = service.snapshot()['plan']
    state = service.dispatch('message', {'text': 'Why this route?'})
    assert not service.runtime.calls
    assert state['plan'] == plan
    assert 'untried surface alternative' in state['message']


def test_retry_expiry_cancels_without_input(service):
    service.dispatch('message', {'text': 'find a coin route'})
    service.dispatch('message', {'text': 'yes'})
    finish(service, status='death')
    service._retry_scope['deadline'] = 0
    calls = list(service.runtime.calls)
    with pytest.raises(ValueError, match='budget ended'):
        service.dispatch('retry')
    assert service.runtime.calls == calls
    assert service.snapshot()['retry_scope'] is None


def test_stairs_death_remembers_adjustment_and_separates_cartridges():
    row = {'cartridge_sha256': 'cart', 'status': 'death',
           'initial_plan': {'coin_compatibility': coins.COMPATIBILITY, 'path_choice': 'coin_balanced'},
           'coin_result': {'controller_application_observed': True, 'furthest_x': 1652,
                           'collected': 2, 'segment_yields': {'middle_gap': 2},
                           'level_finish_observed': False}}
    route, reason = coins.choose_route([row], 'cart')
    assert route == 'coin_balanced' and 'left stair top' in reason
    assert coins.route_guidance([row], 'cart')['stairs_tactic'] == coins.STAIRS_TACTIC
    assert coins.choose_route([row], 'other')[0] == 'coin_high'
    assert coins.coin_request('Improve traversal through the stairs toward the finish')
    finished = {**row, 'status': 'completed_stop',
                'initial_plan': {**row['initial_plan'], 'path_choice': 'coin_balanced', 'route_guidance': {'stairs_tactic': coins.STAIRS_TACTIC}},
                'coin_result': {**row['coin_result'], 'level_finish_observed': True}}
    assert coins.choose_route([row, finished], 'cart')[0] == 'coin_balanced'


def test_real_lua_stairs_stages_landing_and_releases_jump(tmp_path, monkeypatch):
    from test_mario_demonstrations import lua_host
    lua, directory = lua_host(tmp_path, monkeypatch)
    lua.execute("M=dofile('scripts/fceux_b2_plan.lua'); M.path_choice='coin_balanced'; M.stairs_tactic='land_then_cross_v1'; held={}")
    def step(x, y, air):
        lua.execute(f'set_state({x},{y},16,0,0,{air}); M.stairs_step(held, {{x={x},y={y},air={air}}})')
        return lua.globals().held
    assert not step(1500, 368, 0).A
    assert not step(1571, 368, 0).A  # release before first jump
    assert step(1571, 364, 1).A
    assert not step(1583, 310, 1).right  # brake over left platform
    assert not step(1590, 300, 1).A
    assert not step(1590, 320, 0).A  # grounded release before crossing
    crossing = step(1590, 320, 0)
    assert crossing.A and crossing.B and crossing.right
    step(1755, 368, 0)
    assert lua.globals().M.stairs_done
    assert 'landmark=stairs_landing' in (directory/'events.log').read_text()
    lua.execute("M.stairs_done=false; M.stairs_phase='settle'; M.stairs_frames=240")
    with pytest.raises(Exception, match='stairs_stalled'):
        step(1590, 310, 1)
    assert not lua.globals().buttons.A and not lua.globals().buttons.right


def test_app_instruction_reaches_next_attempt_wire_and_survives_reopen(service):
    service.dispatch('message', {'text': 'Find a coin route for two attempts'})
    state = service.dispatch('message', {'text': 'At the stairs land on the left top before jumping across the gap'})
    assert not service.runtime.calls
    assert state['plan']['route_guidance']['basis'] == 'player_instruction'
    service.dispatch('message', {'text': 'yes'})
    plan = service.runtime.calls[-1][1]
    assert plan['path_choice'] == 'coin_balanced'
    assert runtime_fields(plan)['stairs_tactic'] == 'land_then_cross_v1'
    bad = {**plan, 'route_guidance': {**plan['route_guidance'], 'stairs_tactic': 'arbitrary'}}
    with pytest.raises(ValueError, match='Unsupported route guidance'):
        runtime_fields(bad)
    finish(service, status='death')
    service.dispatch('retry')
    assert runtime_fields(service.runtime.calls[-1][1])['stairs_tactic'] == 'land_then_cross_v1'
    reopened = ConversationService(service.live_manager, runtime=FakeRuntime(service.live_manager), artifacts_root=service.root)
    assert reopened.snapshot()['plan'] is None and reopened.snapshot()['retry_scope'] is None
    reopened.dispatch('message', {'text': 'Improve stairs traversal toward the finish'})
    assert reopened.snapshot()['plan']['route_guidance']['original_words'].startswith('At the stairs')


def test_pipe_failure_adds_instruction_to_next_plan_not_to_old_attempt(service):
    service.dispatch('message', {'text': 'Find a coin route'})
    service.dispatch('message', {'text': 'yes'})
    old = finish(service, status='death')['outcome']
    record = {**old, 'attempt_id': 'pipe-failure', 'initial_plan': {**old['initial_plan'], 'path_choice': 'coin_balanced'},
              'coin_result': {**old['coin_result'], 'furthest_x': 1855, 'stairs_landing_observed': True}}
    service.history.record('pipe-failure', record)
    stairs = {**record, 'attempt_id': 'stairs-failure', 'coin_result': {**record['coin_result'], 'furthest_x': 1652}}
    service.history.record('stairs-failure', stairs)
    state = service.dispatch('message', {'text': 'Improve stairs traversal to the finish'})
    plan = state['plan']
    assert plan['route_guidance']['pipe_tactic'] == coins.PIPE_TACTIC
    assert 'pipe-failure' in plan['route_guidance']['pipe_source_attempt_ids']
    service.dispatch('message', {'text': 'yes'})
    assert runtime_fields(service.runtime.calls[-1][1])['pipe_tactic'] == coins.PIPE_TACTIC
    assert 'route_guidance' not in old['initial_plan']


def test_real_lua_pipe_stages_on_top_and_times_out_neutrally(tmp_path, monkeypatch):
    from test_mario_demonstrations import lua_host
    lua, directory = lua_host(tmp_path, monkeypatch)
    lua.execute("M=dofile('scripts/fceux_b2_plan.lua'); M.stairs_done=true; M.pipe_tactic='land_on_pipe_then_cross_v1'; held={}")
    def step(x, y, air, vx=16):
        lua.execute(f'set_state({x},{y},{vx},0,0,{air}); M.pipe_step(held, {{x={x},y={y},air={air}}})')
        return lua.globals().held
    assert not step(1779, 384, 0).A
    assert step(1785, 340, 1).A
    assert step(1795, 320, 1).left
    assert not step(1804, 315, 1, 0).right
    assert not step(1804, 352, 0, 0).A
    runup = step(1804, 352, 0, 0)
    assert not runup.A and runup.B and runup.right
    assert not step(1812, 352, 0, 20).A
    crossing = step(1814, 352, 0, 20)
    assert crossing.A and crossing.B and crossing.right
    step(1935, 368, 0)
    assert lua.globals().M.pipe_done
    assert 'landmark=pipe_landing' in (directory/'events.log').read_text()
    lua.execute("M.pipe_done=false; M.pipe_phase='settle'; M.pipe_frames=240")
    with pytest.raises(Exception, match='pipe_stalled'):
        step(1804, 310, 1)
    assert not lua.globals().buttons.right
