"""Synthetic algorithm/authority checks; none is live game evidence."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import threading

import pytest
from PIL import Image

from smb3_agent.request_planning import ConversationPlan, PlannedAction
from smb3_agent.stardew_adapter import (
    CropObservation, InputKind, OrdinaryInputDriver, PositionObservation, SaveIdentity,
    ScreenObservation, StardewAdapterError, ToolObservation, WindowObservation, WateringLedger,
)
from smb3_agent.stardew_companion import StardewCompanionController
from smb3_agent.stardew_perception import PixelRegion, VisibleWateringPerception, WateringPixelProfile, pixel_digest
from smb3_agent.stardew_runtime import StardewRuntime, WateringNavigator


def configured(tmp_path):
    image = tmp_path / "visible.png"
    Image.new("RGB", (100, 100)).save(image)
    save = SaveIdentity("source", "source", "copy", "copy", "sha", "sha", 1, 1, "now", "session", True, True)
    window = WindowObservation(10, "process-start", "window", "Stardew", (0, 0, 100, 100), True, True, True)
    screen = ScreenObservation("first", datetime.now(timezone.utc).isoformat(), "sha", window,
        (CropObservation("crop", 1, 0, True, False, False, 1, str(image)),), 20, 270,
        ToolObservation("watering_can", 5, 40, 0, 0), PositionObservation("Farm", 0, 0, True, 1),
        (str(image),), scene_complete=True, session_nonce="session", perception_classification="automatic_live")
    state = [screen]
    count = [0]
    def observer():
        count[0] += 1
        return replace(state[0], observation_id=str(count[0]), observed_at=datetime.now(timezone.utc).isoformat())
    commands = []
    def emit(command):
        commands.append(command)
        if command.purpose == "water_crop":
            before = state[0]
            state[0] = replace(before, crops=(replace(before.crops[0], watered=True),), energy=18,
                               tool=replace(before.tool, watering_can_units=4, tool_uses=1))
    driver = OrdinaryInputDriver(keyboard=emit, mouse=emit, neutralizer=lambda: None)
    manager = SimpleNamespace(verify_primary_unchanged=lambda save: True)
    controller = StardewCompanionController(save, manager=manager)
    setup = SimpleNamespace(require_verified=lambda window: None)
    runtime = StardewRuntime(setup=setup, controller=controller, observer=observer, driver=driver,
                             navigator=WateringNavigator({(0, 0)}, {(1, 0): (15, 5)}, (0, 0), energy_cost_upper_bound=2),
                             evidence_root=tmp_path / "attempt")
    runtime.observe()
    context = runtime.planning_context()
    plan = ConversationPlan("plan", "request", "water", "conversation", "stardew", "session", context.observation_id,
                            "water", "water", (PlannedAction("water", "water", ("crop",)),), stop_point="farmhouse_entrance")
    runtime.review(plan)
    return runtime, plan, state, commands


def test_exact_review_water_resources_return_and_handback(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.start(plan, background=False)
    runtime.tick()
    runtime.tick()
    result = runtime.snapshot()
    assert result["status"] == "completed"
    assert result["ledger"]["remaining_count"] == 0
    assert result["ledger"]["can_water_consumed"] == 1
    assert result["ledger"]["energy_spent"] == 2
    assert result["neutralized"] and result["handback_confirmed"]
    assert len(commands) == 1 and commands[0].kind is InputKind.MOUSE
    assert result["outcome"]["owner_acceptance"] is False
    assert list((tmp_path / "attempt").glob("*outcome*.json"))


@pytest.mark.parametrize("change,match", [
    ({"perception_classification": "pixel_fixture_unqualified"}, "fixture/manual"),
    ({"session_nonce": "reset"}, "reset or different"),
    ({"observed_at": (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}, "stale"),
    ({"energy": None}, "resource_unknown"),
])
def test_observation_rejection(tmp_path, change, match):
    runtime, plan, state, commands = configured(tmp_path)
    bad = replace(state[0], **change)
    with pytest.raises(StardewAdapterError, match=match):
        runtime._validate(bad)
    assert not commands


def test_review_hash_and_complete_set_rejected(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    with pytest.raises(StardewAdapterError, match="exact reviewed"):
        runtime.start(replace(plan, revision=2), background=False)
    subset = replace(plan, actions=(PlannedAction("water", "water", ()),))
    runtime.review(subset)
    with pytest.raises(StardewAdapterError, match="every initially"):
        runtime.start(subset, background=False)
    assert not commands


def test_focus_loss_and_reclaim_do_not_queue_inputs(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.start(plan, background=False)
    state[0] = replace(state[0], window=replace(state[0].window, foreground=False))
    runtime.tick()
    assert runtime.status == "stopped" and runtime.controller.authorization is None
    state[0] = replace(state[0], window=replace(state[0].window, foreground=True))
    runtime.tick()
    runtime.control("resume")
    runtime.tick()
    assert not commands


def test_pause_during_observer_rejects_restart_until_old_tick_drains(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.start(plan, background=False)
    entered, release = threading.Event(), threading.Event()
    original = runtime.observer
    def blocked():
        entered.set()
        release.wait(2)
        return original()
    runtime.observer = blocked
    thread = threading.Thread(target=runtime.tick)
    thread.start()
    assert entered.wait(1)
    runtime.control("pause")
    with pytest.raises(StardewAdapterError, match="handback"):
        runtime.start(plan, background=False)
    release.set()
    thread.join(2)
    assert not thread.is_alive() and not commands
    assert runtime.controller.authorization is None


def test_reclaim_during_start_cannot_clear_cancellation(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = runtime.observer
    errors = []
    def blocked():
        entered.set()
        release.wait(2)
        return original()
    runtime.observer = blocked
    def start():
        try:
            runtime.start(plan, background=False)
        except StardewAdapterError as exc:
            errors.append(str(exc))
    thread = threading.Thread(target=start)
    thread.start()
    assert entered.wait(1)
    runtime.control("reclaim")
    release.set()
    thread.join(2)
    assert errors and "canceled" in errors[0]
    assert not commands and runtime.controller.authorization is None


def test_resource_shortage_preserves_partial_result(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    state[0] = replace(state[0], tool=replace(state[0].tool, watering_can_units=0))
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id)
    runtime.review(plan)
    runtime.start(plan, background=False)
    runtime.tick()
    assert "refill" in runtime.reason and not commands
    assert runtime.snapshot()["ledger"]["remaining_count"] == 1


def test_pixel_match_unknowns_and_fixture_classification(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    image = Image.new("RGB", (10, 10), "red")
    path = tmp_path / "pixels.png"
    image.save(path)
    digest = pixel_digest(image)
    def region(value):
        return PixelRegion((0,0,10,10), {digest: value})
    profile = WateringPixelProfile("fixture", (10,10), {(1,0):region("planted_dry")},
        (region(True),), region((0,0)), region("watering_can"), region(20), region(5), 40, 270, (0,0),
        complete_farm_coverage=True)
    observer = VisibleWateringPerception(profile)
    screen = observer.recognize(path, state[0].window, runtime.controller.save)
    assert screen.perception_classification == "pixel_fixture_unqualified"
    with pytest.raises(StardewAdapterError, match="fixture/manual"):
        runtime._validate(screen)
    Image.new("RGB", (10,10), "blue").save(path)
    with pytest.raises(StardewAdapterError, match="unrecognized"):
        observer.recognize(path, state[0].window, runtime.controller.save)


def test_ledger_rejects_unexplained_water_and_energy_gain(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    ledger = WateringLedger.from_observation(state[0])
    with pytest.raises(StardewAdapterError):
        ledger.reconcile(replace(state[0], tool=replace(state[0].tool, watering_can_units=4)))
    assert ledger.can_water_current == 5
    with pytest.raises(StardewAdapterError):
        ledger.reconcile(replace(state[0], energy=21))


def test_unknown_or_insufficient_energy_cost_cannot_cross_reserve(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.navigator.energy_cost_upper_bound = None
    runtime.start(plan, background=False)
    runtime.tick()
    assert "energy cost bound is unknown" in runtime.reason and not commands


def test_already_watered_at_return_point_requires_no_input(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    state[0] = replace(state[0], crops=(replace(state[0].crops[0], watered=True),))
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id)
    runtime.review(plan)
    runtime.start(plan, background=False)
    runtime.tick()
    assert runtime.status == "completed" and not commands


def test_terminal_reclaim_during_completion_cannot_report_success(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.start(plan, background=False)
    runtime.tick()
    entered, release = threading.Event(), threading.Event()
    def checking(_):
        entered.set()
        release.wait(2)
        return True
    runtime.controller.manager.verify_primary_unchanged = checking
    finishing = threading.Thread(target=runtime.tick)
    finishing.start()
    assert entered.wait(1)
    stopping = threading.Thread(target=lambda: runtime.control("reclaim"))
    stopping.start()
    assert runtime._cancel.wait(1)
    release.set()
    finishing.join(2)
    stopping.join(2)
    assert runtime.status == "stopped"
    assert runtime.controller.active_attempt.status.value != "completed"
    assert runtime.controller.authorization is None


def test_reviewed_target_postcondition_rejects_other_crop(tmp_path):
    from smb3_agent.stardew_adapter import InputCommand
    runtime, plan, state, commands = configured(tmp_path)
    before = state[0]
    after = replace(before, crops=(replace(before.crops[0], watered=True),), energy=18,
                    tool=replace(before.tool, watering_can_units=4, tool_uses=1))
    command = InputCommand(InputKind.MOUSE, "left_button", "click", purpose="water_crop", reviewed_crop_id="different")
    with pytest.raises(StardewAdapterError, match="different crop"):
        runtime.controller._verify_postcondition(command, before, after)


def test_neutralization_failure_revokes_authority_and_denies_handback(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.start(plan, background=False)
    def broken():
        raise OSError("release failed")
    runtime.driver.neutralize = broken
    result = runtime.control("reclaim")
    assert runtime.controller.authorization is None
    assert result["status"] == "failed"
    assert result["handback_confirmed"] is False
    runtime.tick()
    assert not commands


def test_explicit_observe_activates_bound_background_process_before_capture(tmp_path, monkeypatch):
    import sys
    import smb3_agent.stardew_input as input_module
    import smb3_agent.stardew_perception as perception_module
    runtime, plan, state, commands = configured(tmp_path)
    save = runtime.controller.save
    events = []
    background = [False]
    class Backend:
        def detect_window(self, *, require_foreground=True):
            events.append(("detect", require_foreground))
            window = replace(state[0].window, foreground=not background[0])
            if require_foreground and not window.foreground:
                raise StardewAdapterError("background")
            return window
        def capture(self, window, path):
            assert window.foreground
            events.append(("capture", True))
            return state[0].screenshot_references[0]
    class Application:
        def activateWithOptions_(self, options):
            events.append(("activate", options))
            background[0] = False
            return True
    native_app = Application()
    monkeypatch.setitem(sys.modules, "AppKit", SimpleNamespace(
        NSRunningApplication=SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda pid: native_app),
        NSApplicationActivateIgnoringOtherApps=1))
    monkeypatch.setattr(input_module, "MacOrdinaryInputDriver", lambda **kwargs: runtime.driver)
    class Perception:
        def __init__(self, profile):
            pass
        def recognize(self, capture, window, identity):
            return replace(state[0], window=window, observed_at=datetime.now(timezone.utc).isoformat())
    monkeypatch.setattr(perception_module, "VisibleWateringPerception", Perception)
    runtime.setup_manager.session = SimpleNamespace(save=save, session_id=save.nonce, input_ready=True)
    runtime.setup_manager.manager = runtime.controller.manager
    runtime.connect_live(profile=SimpleNamespace(qualified=lambda: True), navigator=runtime.navigator,
                         evidence_root=tmp_path / "native-factory", backend=Backend())
    background[0] = True
    events.clear()
    runtime.observe()
    assert events[:3] == [("detect", False), ("activate", 1), ("detect", True)]
    assert ("capture", True) in events
    assert runtime.screen.window.foreground
    assert not commands


def test_failed_setup_invalidates_native_connection_but_retains_outcome(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.start(plan, background=False)
    runtime.control("pause")
    with pytest.raises(StardewAdapterError, match="setup supports"):
        runtime.setup({"action": "pretend_verify"})
    assert runtime.controller is None and runtime.driver is None and runtime.observer is None
    assert runtime.screen is None and runtime.current_plan is None
    assert len(runtime.snapshot()["attempts"]) == 1
    assert not commands


def test_pause_without_live_configuration_does_not_advertise_availability():
    runtime = StardewRuntime()
    state = runtime.control("pause")
    assert not state["available"]
    assert state["owner"] == "player"
    assert state["current_plan"] is None


def test_profile_registry_rejects_fixture_stale_and_changed_evidence(tmp_path):
    session = SimpleNamespace(input_ready=True, session_id="farm-a")
    runtime = StardewRuntime(setup=SimpleNamespace(session=session))
    valid = [False]
    profile = SimpleNamespace(profile_id="reviewed-screen", qualified=lambda: valid[0])
    navigator = WateringNavigator({(0, 0)}, {}, (0, 0))
    with pytest.raises(StardewAdapterError, match="actual-live"):
        runtime.register_qualified_profile(profile, navigator, evidence_root=tmp_path)
    valid[0] = True
    runtime.register_qualified_profile(profile, navigator, evidence_root=tmp_path)
    assert runtime.snapshot()["qualified_profiles"][0]["profile_id"] == "reviewed-screen"
    session.session_id = "farm-b"
    with pytest.raises(StardewAdapterError, match="this farm session"):
        runtime.connect_profile("reviewed-screen")
    session.session_id = "farm-a"
    valid[0] = False
    assert runtime.snapshot()["qualified_profiles"] == []
    with pytest.raises(StardewAdapterError, match="this farm session"):
        runtime.connect_profile("reviewed-screen")


def test_engineering_verify_requires_own_running_launch():
    runtime = StardewRuntime()
    with pytest.raises(StardewAdapterError, match="dedicated engineering"):
        runtime.verify_engineering_session()
    runtime.status = "running"
    with pytest.raises(StardewAdapterError, match="neutral handback"):
        runtime.verify_engineering_session()


def test_subtile_navigation_keeps_waypoint_until_observed_arrival(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    screen = replace(state[0], crops=(replace(state[0].crops[0], tile_x=3),),
        position=PositionObservation('Farm', 0, 0, False, 1, 0, 0, 1, 100, 100))
    nav = WateringNavigator({(0,0),(1,0),(2,0)}, {}, (0,0), energy_cost_upper_bound=2)
    first, _ = nav.next_command(screen, {'crop'})
    assert first.control == 'd' and nav._waypoint == (1,0)
    partial = replace(screen, position=replace(screen.position, world_pixel_x=20))
    second, _ = nav.next_command(partial, {'crop'})
    assert second.control == 'd' and nav._waypoint == (1,0)
    arrived = replace(screen, position=replace(screen.position, tile_x=1, world_pixel_x=48))
    nav.next_command(arrived, {'crop'})
    assert nav._waypoint == (2,0)
    for _ in range(7):
        nav.next_command(arrived, {'crop'})
    with pytest.raises(StardewAdapterError, match='converge'):
        nav.next_command(arrived, {'crop'})


def test_unreachable_initial_crop_refuses_start_without_authority(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    state[0] = replace(state[0], crops=(replace(state[0].crops[0], tile_x=3),))
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id)
    runtime.review(plan)
    with pytest.raises(StardewAdapterError, match='no reachable qualified watering position'):
        runtime.start(plan, background=False)
    assert runtime.controller.authorization is None
    assert not commands


def test_prepared_main_patch_requires_an_additional_qualified_vantage(tmp_path):
    # Geometry calibrated from the retained farm: crop (0,4) has three crop
    # neighbours and a rock at (0,5). Fixture regression, not live qualification.
    runtime, _, state, _ = configured(tmp_path)
    crops = tuple(replace(state[0].crops[0], crop_id=f'{x},{y}', tile_x=x, tile_y=y)
                  for x in (-1, 0, 1) for y in (3, 4))
    screen = replace(state[0], crops=crops)
    corridor = {(x, y) for x in range(-3, 4) for y in range(7)} - {(0,5)}
    nav = WateringNavigator(corridor, {}, (0,0))
    with pytest.raises(StardewAdapterError, match='crop 0,4 has no reachable'):
        nav.validate_scope(screen)


def test_hidden_confirmed_crop_is_history_not_a_new_watering_result(tmp_path):
    from smb3_agent.stardew_adapter import InputCommand
    runtime, _, state, commands = configured(tmp_path)
    initial = replace(state[0], position=PositionObservation('Farm',0,0,True,1,0,0,2,100,100),
        crops=(replace(state[0].crops[0], watered=True), replace(state[0].crops[0], crop_id='second',tile_x=2)))
    controller=runtime.controller
    controller.authorize_do(initial,owner_confirmation=True,input_driver=InputKind.KEYBOARD,
        expires_at=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat())
    hidden=replace(initial,observation_id='hidden',position=replace(initial.position,tile_x=1,world_pixel_x=48,at_farmhouse_entrance=False),
        crops=(replace(initial.crops[0],occluded=True,watered=False,confidence=0),initial.crops[1]),
        unknown_regions=('player-occluded:crop',))
    controller.perform_input(InputCommand(InputKind.KEYBOARD,'d','press',80,purpose='navigate'),initial,runtime.driver,lambda:hidden)
    assert controller.operator.ledger.confirmed_watered_ids == {'crop'}
    with pytest.raises(StardewAdapterError):
        hidden.validate(controller.save.disposable_tree_sha256)
    hidden.validate(controller.save.disposable_tree_sha256,allow_player_occlusion=True)
    controller.authorization=replace(controller.authorization,input_driver=InputKind.MOUSE)
    after=replace(hidden,observation_id='watered',energy=18,tool=replace(hidden.tool,watering_can_units=4,tool_uses=1),
        crops=(hidden.crops[0],replace(hidden.crops[1],watered=True)))
    controller.perform_input(InputCommand(InputKind.MOUSE,'left_button','click',80,target=(15,5),purpose='water_crop',reviewed_crop_id='second'),
        hidden,runtime.driver,lambda:after)
    assert controller.operator.ledger.confirmed_watered_ids == {'crop','second'}
    assert controller.operator.ledger.can_water_consumed == 1
    assert controller.operator.ledger.energy_spent == 2
    # Complete cannot turn historical confirmations into a fully visible final frame.
    result=controller.complete(after,runtime.driver,evidence_root=tmp_path,required_evidence=())
    assert result.status.value == 'failed'


def test_missing_crop_outside_avatar_cannot_be_relabelled_temporary(tmp_path):
    runtime,_,state,_=configured(tmp_path)
    bad=replace(state[0],position=PositionObservation('Farm',0,0,True,1,0,0,2,100,100),
        crops=(replace(state[0].crops[0],occluded=True,confidence=0),),unknown_regions=('player-occluded:crop',))
    with pytest.raises(StardewAdapterError,match='not bounded player occlusion'):
        bad.validate(runtime.controller.save.disposable_tree_sha256,allow_player_occlusion=True)


def test_wrong_target_stops_but_preserves_exact_visible_partial_accounting(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    initial = state[0]
    state[0] = replace(initial, crops=initial.crops+(replace(initial.crops[0],crop_id='other',tile_x=-1),))
    runtime.observe()
    plan=replace(plan,observation_id=runtime.screen.observation_id,
                 actions=(replace(plan.actions[0],target_ids=('crop','other')),))
    runtime.navigator=WateringNavigator({(0,0)},{(1,0):(15,5),(-1,0):(25,5)},(0,0),energy_cost_upper_bound=2)
    runtime.review(plan)
    def wrong(command):
        before=state[0]
        state[0]=replace(before,crops=(before.crops[0],replace(before.crops[1],watered=True)),energy=18,
                         tool=replace(before.tool,watering_can_units=4,tool_uses=1))
    runtime.driver=OrdinaryInputDriver(keyboard=wrong,mouse=wrong,neutralizer=lambda:None)
    runtime.start(plan,background=False)
    runtime.tick()
    result=runtime.snapshot()
    assert result['status']=='stopped' and 'unrelated visible crop' in result['reason']
    assert result['ledger']['confirmed_watered_ids']==['other']
    assert result['ledger']['remaining_count']==1
    assert result['ledger']['energy_spent']==2 and result['ledger']['can_water_consumed']==1
    assert result['handback_confirmed']


def test_failure_after_emission_retains_unverified_action_and_neutral_handback(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    def interrupted(command):
        runtime.driver.gameplay_emission_count += 1
        commands.append(command)
        raise StardewAdapterError('focus changed after button-down')
    runtime.driver = OrdinaryInputDriver(keyboard=interrupted, mouse=interrupted,
                                        neutralizer=lambda: None)
    runtime.driver.gameplay_emission_count = 0
    runtime.start(plan, background=False)
    runtime.tick()
    result = runtime.snapshot()
    assert result['status'] == 'stopped' and result['handback_confirmed']
    assert len(result['outcome']['inputs']) == 1
    assert result['outcome']['inputs'][0]['after_observation_id'] == 'missing_or_unverified'
    assert result['ledger']['watered_count'] == 0
    assert 'focus changed after button-down' in result['reason']


def test_fresh_reconciled_navigation_frame_is_consumed_once(tmp_path):
    from smb3_agent.stardew_adapter import InputCommand
    runtime, plan, state, commands = configured(tmp_path)
    state[0] = replace(state[0], position=replace(state[0].position,
        world_pixel_x=0, world_pixel_y=0, pixel_uncertainty=2, camera_origin_x=0, camera_origin_y=0))
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id)
    runtime.review(plan)
    runtime.start(plan, background=False)
    runtime.navigator = SimpleNamespace(poses={'home': (0, 0)}, energy_cost_upper_bound=2,
        next_command=lambda screen, remaining: (InputCommand(InputKind.KEYBOARD, 'd', 'press', 15, purpose='navigate'), None))
    original = runtime.observer
    calls = []
    def observe():
        result = original()
        calls.append(result)
        return result
    runtime.observer = observe
    runtime.tick()
    assert len(calls) == 2
    previous = calls[-1]
    runtime.tick()
    assert len(calls) == 3
    assert runtime.controller.active_attempt.inputs[-1].before_observation_id == previous.observation_id
    runtime.control('pause')
    assert runtime._pending_navigation_observation is None


def test_old_navigation_frame_requires_new_observation(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    runtime.start(plan, background=False)
    old = replace(runtime.screen, observed_at=(datetime.now(timezone.utc)-timedelta(seconds=3)).isoformat())
    runtime.screen = runtime._pending_navigation_observation = old
    runtime.tick()
    assert len(commands) == 1
    assert runtime.controller.active_attempt.inputs[-1].before_observation_id != old.observation_id
    runtime.tick()
    assert runtime.status == 'completed'


def test_final_independent_frame_has_new_evidence_identity(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    original = runtime.observer
    def observe():
        frame = original()
        return replace(frame, crops=tuple(replace(c, evidence_reference=f'frame-{frame.observation_id}.png') for c in frame.crops))
    runtime.observer = observe
    runtime.start(plan, background=False)
    runtime.tick()
    runtime.tick()
    assert runtime.status == 'completed'
    final = runtime.controller.active_attempt.after_observations[-1]
    assert final.observation_id == runtime.screen.observation_id
    assert runtime.controller.operator.ledger.final_position == final.position
    assert runtime.controller.authorization is None
    assert runtime.snapshot()['handback_confirmed']


@pytest.mark.parametrize('action,status', [('pause','paused'), ('take_control','stopped')])
def test_canceled_pulse_cannot_overwrite_requested_handback(tmp_path, action, status):
    runtime, plan, state, commands = configured(tmp_path)
    def canceled(command):
        runtime.control(action)
        raise StardewAdapterError('Input canceled while aiming')
    runtime.driver = OrdinaryInputDriver(keyboard=canceled, mouse=canceled, neutralizer=lambda:None)
    runtime.start(plan, background=False)
    runtime.tick()
    assert runtime.status == status
    assert 'input_rejected' not in runtime.reason
    assert runtime.controller.authorization is None
    assert runtime.snapshot()['handback_confirmed']
    assert not runtime.controller.active_attempt.inputs


def test_new_start_uses_visible_post_interruption_baseline_without_recredit(tmp_path):
    runtime, plan, state, commands = configured(tmp_path)
    def released_water(command):
        commands.append(command)
        runtime.driver.gameplay_emission_count += 1
        before = state[0]
        state[0] = replace(before, crops=(replace(before.crops[0], watered=True),), energy=18,
                           tool=replace(before.tool, watering_can_units=4, tool_uses=1))
        runtime.control('pause')
        raise StardewAdapterError('canceled before post-observation')
    runtime.driver = OrdinaryInputDriver(keyboard=released_water, mouse=released_water, neutralizer=lambda:None)
    runtime.driver.gameplay_emission_count = 0
    runtime.start(plan, background=False)
    runtime.tick()
    previous = runtime.controller.active_attempt
    assert previous.inputs[-1].after_observation_id == 'missing_or_unverified'
    assert runtime.snapshot()['ledger']['watered_count'] == 0
    runtime.observe()
    plan = replace(plan, observation_id=runtime.screen.observation_id, plan_id='fresh-plan')
    runtime.review(plan)
    runtime.start(plan, background=False)
    runtime.tick()
    result = runtime.snapshot()
    assert result['status'] == 'completed'
    assert len(commands) == 1  # Already visibly wet: never water it again.
    assert result['ledger']['watered_count'] == 1
    assert result['ledger']['energy_start'] == 18 and result['ledger']['energy_spent'] == 0
    assert result['ledger']['can_water_consumed'] == 0
    assert previous.inputs[-1].after_observation_id == 'missing_or_unverified'
    assert previous.status.value == 'stopped'
    assert list((tmp_path/'attempt').glob('*reauthorization-baseline*'))
