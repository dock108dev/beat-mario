"""Synthetic inspection contracts; live proof is retained separately."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from smb3_agent.stardew_inspection import InspectionNavigator, fresh_findings, proposal
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator
from smb3_agent.stardew_adapter import PositionObservation, InputKind
from smb3_agent.conversation_service import StardewConversationService
from test_gc3_planting import PassiveRuntime, survey
from test_stardew_conversation import request
from test_stardew_runtime import configured


def navigator():
    return ViewpointNavigator({'poses': {'home': [0,0], 'south': [0,96], 'east-up':[288,96]},
        'edges': [['home','south'], ['south','east-up']], 'watering': {}, 'return_pose':'home'})


def screen_at(x,y,home=False):
    return SimpleNamespace(session_nonce='session',observation_id='frame',position=PositionObservation(
        'Farm',round(x/48),round(y/48),home,1,world_pixel_x=x,world_pixel_y=y,pixel_uncertainty=1,camera_origin_x=0,camera_origin_y=0))


def findings():
    return {**survey(),'session_id':'session','observation_id':'second','targets':[
        {'id':'east-margin-a','label':'margin a','state':'empty_dirt'},
        {'id':'east-margin-b','label':'margin b','state':'unknown'}]}


def test_plan_scope_and_unknown_area_refusal():
    plan=proposal(screen_at(0,0,True),navigator(),'Inspect eastern margin','chat')
    assert plan.actions[0].kind=='inspect' and plan.resource_limits=={'maximum_seconds':120}
    assert plan.actions[0].parameters['route']==['home','south','east-up']
    assert not plan.authorization_scope['granted']
    with pytest.raises(ValueError,match='no qualified'):
        proposal(screen_at(0,0,True),navigator(),'Inspect cave','chat')
    with pytest.raises(ValueError,match='outside'):
        proposal(screen_at(100,50),navigator(),'Inspect eastern margin','chat')


def test_outward_observation_return_and_bounded_movement():
    nav=InspectionNavigator(navigator())
    command,event=nav.next_inspection_command(screen_at(0,0,True))
    assert command.kind is InputKind.KEYBOARD and command.duration_ms<=40
    command,event=nav.next_inspection_command(screen_at(0,96))
    assert command.control=='d'
    assert nav.next_inspection_command(screen_at(288,96))==(None,'observe')
    nav.observed=True
    assert nav.next_inspection_command(screen_at(288,96))[0].control=='a'
    nav.next_inspection_command(screen_at(0,96))
    assert nav.next_inspection_command(screen_at(0,0,True))==(None,'returned')


def test_stalled_navigation_refuses_instead_of_blind_walk():
    nav=InspectionNavigator(navigator())
    with pytest.raises(ValueError,match='no observed progress'):
        for _ in range(6):
            nav.next_inspection_command(screen_at(0,0,True))


@pytest.mark.parametrize('change',[{'session_id':'other'},{'observation_id':'frame'},
    {'observed_at':(datetime.now(timezone.utc)-timedelta(seconds=6)).isoformat()}, {'targets':[]}])
def test_findings_need_fresh_independent_session_bound_coverage(change):
    with pytest.raises(ValueError):
        fresh_findings({**findings(),**change},'session','frame')


def test_unknown_access_stays_unknown():
    result=fresh_findings(findings(),'session','frame')
    assert 'unknown' in result['message'] and 'Access' in result['message']
    assert not result['observation'].get('authorization_granted')


class InspectionRuntime(PassiveRuntime):
    def propose_inspection(self,text,conversation_id):
        return proposal(screen_at(0,0,True),navigator(),text,conversation_id)


def test_request_revision_cancels_old_approval_and_reopened_findings(tmp_path):
    runtime=InspectionRuntime()
    service=StardewConversationService(runtime=runtime,artifacts_root=tmp_path)
    state=request(service,'Inspect eastern margin')
    old=state['plan']
    request(service,'Where should we grow parsnips instead?')
    with pytest.raises(ValueError,match='plan changed'):
        service.dispatch('start',{'expected_plan_id':old['plan_id'],'expected_revision':old['revision']})
    assert not any(c[0]=='start' for c in runtime.calls)
    runtime.state['inspection_result']={'status':'completed','findings':fresh_findings(findings(),'session','frame'), 'handback_confirmed':True}
    service.snapshot()
    reopened=StardewConversationService(runtime=InspectionRuntime(),artifacts_root=tmp_path).snapshot()
    assert reopened['inspection_result']['historical'] and reopened['plan'] is None
    assert not reopened['reviewed']
    assert json.loads((tmp_path/'inspection-result.json').read_text())['status']=='completed'


def test_runtime_tampered_scope_and_stop_authority(tmp_path):
    runtime,_,state,commands=configured(tmp_path)
    state[0]=replace(state[0],position=screen_at(0,0,True).position)
    runtime.navigator=navigator()
    runtime._planting_observer=lambda **kw: findings()
    plan=runtime.propose_inspection('Inspect eastern margin','chat')
    bad=replace(plan,resource_limits={'maximum_seconds':600})
    runtime.review(bad)
    with pytest.raises(ValueError,match='scope'):
        runtime.start(bad,background=False)
    runtime.review(plan)
    runtime.start(plan,background=False)
    runtime.control('stop')
    runtime.tick()
    assert not commands and runtime.snapshot()['handback_confirmed']
    assert runtime.inspection_result['status']=='stopped'


def test_new_coverage_is_separate_from_porch_and_pixel_changes_stay_unknown(tmp_path):
    from pathlib import Path
    from PIL import Image, ImageDraw
    from smb3_agent.stardew_planting import PlantingSurvey
    from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
    manifest=Path('artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json')
    if not manifest.is_file():
        pytest.skip('local retained-frame profile absent')
    inspector=PlantingSurvey(PreparedFarmPixelProfile(manifest))
    reference=inspector.config['image']
    assert not any(t['id'].startswith('east-margin-') for t in inspector.inspect(reference,session_id='replay')['targets'])
    observed=inspector.inspect(reference,session_id='replay',inspection=True)
    targets=[t for t in observed['targets'] if t['id'].startswith('east-margin-')]
    assert [t['state'] for t in targets]==['empty_dirt','protected']
    assert not any(t['access_observed'] for t in targets)
    image=Image.open(reference).convert('RGB')
    ImageDraw.Draw(image).rectangle(targets[0]['box'],fill='magenta')
    changed=tmp_path/'blocked.png'
    image.save(changed)
    result=inspector.inspect(changed,session_id='replay',inspection=True)
    assert next(t for t in result['targets'] if t['id']==targets[0]['id'])['state']=='unknown'


def preparation_runtime(tmp_path,monkeypatch):
    from smb3_agent.stardew_runtime import StardewRuntime
    from smb3_agent.stardew_adapter import WindowObservation
    from PIL import Image
    runtime=StardewRuntime()
    launch=SimpleNamespace(root=str(tmp_path),process_id=1,process_started_at='start',status=lambda: {})
    runtime._engineering_launches=[(launch,SimpleNamespace(poll=lambda: None))]
    runtime.show_engineering_game=lambda: runtime.control('pause')
    window=WindowObservation(1,'start','window','Stardew',(0,33,1512,949),True,True,True)
    class Native:
        def __init__(self,**kwargs):
            pass
        def detect_window(self):
            return window
        def capture(self,window,path):
            Image.new('RGB',(1512,949)).save(path)
            return path
    commands=[]
    class Driver:
        def __init__(self,**kwargs):
            self.guard=kwargs['authority_guard']
        def arm(self):
            self.guard()
        def send(self,command):
            commands.append(command)
        def neutralize(self):
            pass
    monkeypatch.setattr('smb3_agent.stardew_adapter.MacVisibleStardewBackend',Native)
    monkeypatch.setattr('smb3_agent.stardew_input.MacOrdinaryInputDriver',Driver)
    monkeypatch.setattr('smb3_agent.stardew_setup._verify_engineering_launch_identity',lambda *a: None)
    monkeypatch.setattr(runtime,'snapshot',lambda: {'handback_confirmed':True})
    return runtime,commands


def test_preparation_bound_to_displayed_view_and_no_tool_use(tmp_path,monkeypatch):
    runtime,commands=preparation_runtime(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='Refresh'):
        runtime.prepare_engineering('left','missing')
    runtime.prepare_engineering('view')
    assert not commands
    old=runtime.preparation_view['id']
    runtime.prepare_engineering('left_short',old)
    assert len(commands)==1 and commands[0].duration_ms==100
    with pytest.raises(ValueError,match='Refresh'):
        runtime.prepare_engineering('down',old)
    with pytest.raises(ValueError,match='Unsupported'):
        runtime.prepare_engineering('plant')


def test_preparation_stop_cancels_remaining_pulses(tmp_path,monkeypatch):
    runtime,commands=preparation_runtime(tmp_path,monkeypatch)
    runtime.prepare_engineering('view')
    class StoppingDriver:
        def __init__(self,**kwargs):
            self.guard=kwargs['authority_guard']
        def arm(self):
            self.guard()
        def send(self,command):
            commands.append(command)
            runtime.control('stop')
        def neutralize(self):
            pass
    monkeypatch.setattr('smb3_agent.stardew_input.MacOrdinaryInputDriver',StoppingDriver)
    with pytest.raises(ValueError,match='canceled'):
        runtime.prepare_engineering('left',runtime.preparation_view['id'])
    assert len(commands)==1 and runtime._preparation_driver is None


def test_runtime_walk_fresh_findings_return_and_resource_preservation(tmp_path):
    from smb3_agent.stardew_adapter import OrdinaryInputDriver
    runtime,_,state,commands=configured(tmp_path)
    state[0]=replace(state[0],position=screen_at(0,0,True).position)
    runtime.navigator=navigator()
    def emit(command):
        commands.append(command)
        p=state[0].position
        dx,dy={'s':(0,1),'w':(0,-1),'a':(-1,0),'d':(1,0)}[command.control]
        distance=min(12,command.duration_ms*.2)
        x,y=p.world_pixel_x+dx*distance,p.world_pixel_y+dy*distance
        state[0]=replace(state[0],position=screen_at(x,y,max(abs(x),abs(y))<=7).position)
    runtime.driver=OrdinaryInputDriver(keyboard=emit,neutralizer=lambda: None)
    runtime.driver.arm=lambda: None
    runtime._planting_observer=lambda **kw: findings()
    plan=runtime.propose_inspection('Inspect eastern margin','chat')
    runtime.review(plan)
    runtime.start(plan,background=False)
    for _ in range(150):
        runtime.tick()
        if runtime.status!='running':
            break
    result=runtime.snapshot()
    assert runtime.inspection_result['status']=='completed',result['reason']
    assert result['handback_confirmed'] and result['owner']=='player'
    assert runtime.inspection_result['findings']['observation']['observation_id']=='second'
    assert commands and all(c.kind is InputKind.KEYBOARD and c.purpose=='navigate' for c in commands)
    assert state[0].energy==20 and state[0].tool.watering_can_units==5
    assert not state[0].crops[0].watered


def test_plain_changed_request_discards_inspection_even_without_crop_context(tmp_path):
    service=StardewConversationService(runtime=InspectionRuntime(),artifacts_root=tmp_path)
    request(service,'Inspect eastern margin')
    state=request(service,'Why?')
    assert state['plan'] is None and not state['reviewed']


def test_expired_inspection_never_emits_and_retains_stopped_result(tmp_path):
    runtime,_,state,commands=configured(tmp_path)
    state[0]=replace(state[0],position=screen_at(0,0,True).position)
    runtime.navigator=navigator()
    runtime._planting_observer=lambda **kw: findings()
    plan=runtime.propose_inspection('Inspect eastern margin','chat')
    runtime.review(plan)
    runtime.start(plan,background=False)
    runtime.controller.authorization=replace(runtime.controller.authorization,expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
    runtime.tick()
    assert not commands and runtime.inspection_result['status']=='stopped'
    assert runtime.snapshot()['handback_confirmed']


def test_cancel_during_fresh_capture_never_publishes_findings(tmp_path):
    runtime,_,state,commands=configured(tmp_path)
    state[0]=replace(state[0],position=screen_at(0,0,True).position)
    runtime.navigator=navigator()
    runtime._planting_observer=lambda **kw: findings()
    plan=runtime.propose_inspection('Inspect eastern margin','chat')
    runtime.review(plan)
    runtime.start(plan,background=False)
    state[0]=replace(state[0],position=screen_at(288,96).position)
    runtime.screen=state[0]
    nav=runtime._inspection_navigation
    nav._last_node='east-up'
    def capture(**kw):
        runtime.control('stop')
        return findings()
    runtime._planting_observer=capture
    runtime.tick()
    assert runtime.inspection_result['findings'] is None
    assert not commands and runtime.snapshot()['handback_confirmed']


def test_qualified_entrance_releases_without_extra_movement():
    nav=InspectionNavigator(navigator())
    nav.observed=True
    nav._last_node='south'
    nav._waypoint='home'
    assert nav.next_inspection_command(screen_at(0,7.5,True))==(None,'returned')


def test_live_calibration_variants_preserve_tiny_occupancy_and_hash_binding(tmp_path):
    import copy
    from pathlib import Path
    from PIL import Image
    from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
    from smb3_agent.stardew_planting import PlantingSurvey
    manifest=Path('artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json')
    if not manifest.is_file():
        pytest.skip('local live calibration absent')
    survey=PlantingSurvey(PreparedFarmPixelProfile(manifest))
    for index,variant in enumerate(survey.config.get('variants', [])):
        if not Path(variant['image']).is_file():
            pytest.skip('local live variant absent')
        result=survey.inspect(variant['image'],session_id='replay')
        target=next(t for t in result['targets'] if t['id']=='survey-4-3')
        assert target['state']=='empty_dirt'
        image=Image.open(variant['image']).convert('RGB')
        left,top,right,bottom=target['box']
        image.putpixel(((left+right)//2,(top+bottom)//2),(86,54,52))
        path=tmp_path/f'variant-seed-{index}.png'
        image.save(path)
        changed=survey.inspect(path,session_id='replay')
        assert next(t for t in changed['targets'] if t['id']==target['id'])['state']=='unknown'
    survey.config=copy.deepcopy(survey.config)
    survey.config['variants'][0]['sha256']='changed'
    with pytest.raises(Exception,match='variant evidence changed'):
        survey.inspect(survey.config['image'],session_id='replay')


def test_inspection_turn_uses_qualified_arrival_without_overshoot():
    nav=InspectionNavigator(ViewpointNavigator({'poses':{'home':[0,0],
        'south':[0,96],'main-right-join':[31,96],'east-up':[288,96]},
        'edges':[['home','south'],['south','main-right-join'],['main-right-join','east-up']],
        'watering':{},'return_pose':'home'}))
    nav._last_node='south'
    nav._waypoint='main-right-join'
    screen=screen_at(31.5,91)
    screen.position=replace(screen.position,pixel_uncertainty=2.5)
    command,_=nav.next_inspection_command(screen)
    assert command.control=='d'
    assert nav._last_node=='main-right-join'


def test_survey_pause_wraps_each_reviewed_pulse_and_can_end(tmp_path, monkeypatch):
    runtime, commands = preparation_runtime(tmp_path, monkeypatch)
    runtime.prepare_engineering('view')
    runtime.prepare_engineering('survey_pause', runtime.preparation_view['id'])
    assert runtime._survey_paused and commands[-1].control == 'escape'
    runtime.prepare_engineering('right_micro', runtime.preparation_view['id'])
    assert [c.control for c in commands[-3:]] == ['escape', 'd', 'escape']
    assert commands[-2].duration_ms == 15
    assert runtime.preparation_view['clock_paused_after_capture']
    runtime.prepare_engineering('menu', runtime.preparation_view['id'])
    assert not runtime._survey_paused
    assert commands[-1].control == 'escape'


def test_paused_verification_preserves_menu_ownership(tmp_path, monkeypatch):
    runtime, _ = preparation_runtime(tmp_path, monkeypatch)
    runtime.prepare_engineering('view')
    runtime.prepare_engineering('survey_pause', runtime.preparation_view['id'])
    view = runtime.preparation_view
    with pytest.raises(ValueError, match='End the survey pause'):
        runtime.verify_engineering_session()
    assert runtime._survey_paused and runtime.preparation_view is view
