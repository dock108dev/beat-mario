"""Synthetic cave contracts only; these do not qualify a native cave route."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest
from PIL import Image

from smb3_agent.stardew_cave import CaveRoute, CaveNavigator, proposal, resolve_destination
from smb3_agent.stardew_adapter import OrdinaryInputDriver, InputKind
from smb3_agent.conversation_service import StardewConversationService
from test_gc3_inspection import screen_at
from test_gc3_planting import PassiveRuntime
from test_stardew_conversation import request
from test_stardew_runtime import configured


def route(tmp_path):
    image = tmp_path/'reference.png'
    Image.new('RGB', (100,100)).save(image)
    record = tmp_path/'qualification.json'
    record.write_text('{"evidence_class":"synthetic-test"}')
    patch = {'image':str(image), 'reference_box':[20,20,25,25], 'world_origin':[20,20]}
    config = {'schema':'stardew-cave-route/v1','profile_id':'test','destination':'farm-cave',
        'classification':'actual_live',  # Exercising validation, never a registered live profile.
        'qualified_roles':['approach','return','exterior','corridor','resources','handback'],
        'poses':{'home':[0,0], 'turn':[0,48], 'entrance':[48,48]},
        'edges':[['home','turn'],['turn','entrance']], 'return_pose':'home',
        'qualification_record':str(record), 'exterior':patch,
        'edge_records':[{'edge':edge, 'approach':str(record),'return':str(record),'patches':[patch]}
                        for edge in [['home','turn'],['turn','entrance']]],
        'evidence_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (image,record)}}
    manifest = tmp_path/'route.json'
    manifest.write_text(json.dumps(config))
    return CaveRoute(manifest,profile_id='test')


def ready(tmp_path):
    runtime,_,state,commands = configured(tmp_path)
    state[0] = replace(state[0],position=screen_at(0,0,True).position)
    runtime._cave_route = route(tmp_path)
    def emit(command):
        commands.append(command)
        p = state[0].position
        dx,dy = {'s':(0,1),'w':(0,-1),'a':(-1,0),'d':(1,0)}[command.control]
        distance = min(10,command.duration_ms*.2)
        x,y = p.world_pixel_x+dx*distance,p.world_pixel_y+dy*distance
        state[0] = replace(state[0],position=screen_at(x,y,max(abs(x),abs(y))<=7).position)
    runtime.driver = OrdinaryInputDriver(keyboard=emit,neutralizer=lambda:None)
    runtime.driver.arm = lambda:None
    plan = runtime.propose_cave('Explore Farm Cave','chat')
    runtime.review(plan)
    return runtime,state,commands,plan


def run(runtime, predicate):
    for _ in range(100):
        runtime.tick()
        if predicate():
            return
    pytest.fail('bounded cave loop did not reach expected state')


@pytest.mark.parametrize('text,previous,expected',[
    ('Explore a cave',None,None), ('that cave',None,None), ('Farm Cave',None,'farm-cave'),
    ('the farm one','farm-cave','farm-cave'),('that cave','farm-cave','farm-cave'),
    ('explore the Mines','farm-cave',None),('Skull cavern',None,None),
    ('return home','farm-cave','farm-cave')])
def test_resolution(text,previous,expected):
    assert resolve_destination(text,previous)[0] == expected


def test_reviewed_route_limits_and_start_outside_coverage(tmp_path):
    runtime,state,_,plan = ready(tmp_path)
    assert plan.actions[0].parameters['approach'] == ['home','turn','entrance']
    assert plan.actions[0].parameters['return'] == ['entrance','turn','home']
    assert plan.effective_boundary == 'exterior_only' and plan.resource_limits['tool_uses'] == 0
    assert 'hazards remain unknown' in plan.fallback_explanation
    assert not plan.authorization_scope['granted']
    with pytest.raises(ValueError,match='outside'):
        proposal(replace(state[0],position=screen_at(100,100).position),runtime._cave_route,'Farm Cave','chat')


@pytest.mark.parametrize('field,value',[('effective_boundary','interior'),('stop_point','cave'),
    ('resource_limits',{'maximum_seconds':900}),('requested_objective','Mine resources')])
def test_tampered_review_cannot_authorize(tmp_path,field,value):
    runtime,_,commands,plan = ready(tmp_path)
    bad = replace(plan,**{field:value})
    runtime.review(bad)
    with pytest.raises(ValueError,match='scope'):
        runtime.start(bad,background=False)
    assert not commands and runtime.controller.authorization is None


def test_complete_round_trip_preserves_resources_and_distinct_gates(tmp_path):
    runtime,state,commands,plan = ready(tmp_path)
    runtime.start(plan,background=False)
    run(runtime,lambda:runtime.status!='running')
    result = runtime.cave_result
    assert result['status']=='completed',runtime.reason
    assert result['arrival_observation'] and result['return_observation'] and result['handback_confirmed']
    assert result['arrival_observation']['observation_id'] != result['findings']['observation']['observation_id']
    assert result['findings']['interior_access']=='unknown' and result['findings']['hazards']=='unknown'
    assert result['findings']['observation']['image'].startswith('data:image/png;base64,')
    assert all(c.kind is InputKind.KEYBOARD and c.purpose=='navigate' for c in commands)
    assert state[0].energy==20 and state[0].tool.watering_can_units==5 and not state[0].crops[0].watered


def test_stop_preserves_findings_then_new_approved_return_only(tmp_path):
    runtime,_,commands,plan = ready(tmp_path)
    runtime.start(plan,background=False)
    run(runtime,lambda:runtime.cave_result['findings'] is not None)
    findings = runtime.cave_result['findings']
    runtime.control('stop')
    count = len(commands)
    runtime.tick()
    assert len(commands)==count and runtime.cave_result['handback_confirmed']
    assert runtime.cave_result['return_observation'] is None
    with pytest.raises(ValueError,match='exact reviewed'):
        runtime.start(plan,background=False)
    revised = runtime.propose_cave('return home','chat',return_only=True)
    runtime.review(revised)
    runtime.start(revised,background=False)
    run(runtime,lambda:runtime.status!='running')
    assert runtime.cave_result['status']=='completed' and runtime.cave_result['findings']==findings


def test_cancel_during_capture_preserves_arrival_without_findings(tmp_path):
    runtime,state,commands,plan = ready(tmp_path)
    runtime.start(plan,background=False)
    state[0] = replace(state[0],position=screen_at(48,48).position)
    runtime.screen=state[0]
    runtime._cave_navigation._last_node='entrance'
    original = runtime.observer
    calls = [0]
    def capture():
        calls[0]+=1
        if calls[0]==2:
            runtime.control('stop')
        return original()
    runtime.observer=capture
    runtime.tick()
    assert runtime.cave_result['arrival_observation'] and not runtime.cave_result['findings']
    assert not commands and runtime.snapshot()['handback_confirmed']


@pytest.mark.parametrize('change',[{'session_nonce':'other'}, {'observation_id':'baseline'},
    {'observed_at':(datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat()}])
def test_fresh_findings_guard(tmp_path,change):
    runtime,state,_,_ = ready(tmp_path)
    screen = replace(state[0],position=screen_at(48,48).position,observation_id='fresh',**change) if 'observation_id' not in change else replace(state[0],position=screen_at(48,48).position,**change)
    with pytest.raises(ValueError,match='fresh'):
        runtime._cave_route.findings(screen,session_id='session',baseline_id='baseline')


def test_unknown_exterior_and_changed_corridor(tmp_path):
    runtime,state,commands,plan = ready(tmp_path)
    runtime._cave_route.config['exterior'] = {**runtime._cave_route.config['exterior'],'world_origin':[50,50]}
    # Bind this separate synthetic calibration before exercising unknown appearance.
    runtime._cave_route.path.write_text(json.dumps(runtime._cave_route.config))
    runtime._cave_route.raw = runtime._cave_route.path.read_bytes()
    image=Image.open(state[0].screenshot_references[0])
    image.putpixel((50,50),(255,0,0))
    image.save(state[0].screenshot_references[0])
    screen=replace(state[0],position=screen_at(48,48).position,observation_id='fresh')
    assert runtime._cave_route.findings(screen,session_id='session',baseline_id='old')['entrance']=='unknown'
    image.putpixel((20,20),(255,0,0))
    image.save(state[0].screenshot_references[0])
    with pytest.raises(ValueError,match='hidden or changed'):
        runtime._cave_route.validate_view(state[0])
    assert not commands


def test_manifest_and_evidence_mutation_refuse(tmp_path):
    calibrated=route(tmp_path)
    calibrated.path.write_text('{}')
    with pytest.raises(ValueError,match='changed'):
        calibrated.check()


def test_cave_navigation_stalls_and_has_no_interior_step(tmp_path):
    nav=CaveNavigator(route(tmp_path).navigator)
    with pytest.raises(ValueError,match='no observed progress'):
        for _ in range(6):
            nav.next_inspection_command(screen_at(0,0,True))
    nav=CaveNavigator(route(tmp_path).navigator)
    nav._last_node='entrance'
    assert nav.next_inspection_command(screen_at(48,48))==(None,'observe')


class CaveRuntime(PassiveRuntime):
    def propose_cave(self,*args,**kwargs):
        raise ValueError('Farm Cave route is not qualified. Use fresh Day 2 setup; separate approach verification required.')


def test_conversational_ambiguity_refusal_and_saved_incomplete_return(tmp_path):
    runtime=CaveRuntime()
    service=StardewConversationService(runtime=runtime,artifacts_root=tmp_path)
    first=request(service,'Explore a cave')
    assert first['plan'] is None and 'Which cave' in first['messages'][-1]['text']
    second=request(service,'Farm Cave')
    assert second['plan'] is None and 'not qualified' in second['messages'][-1]['text']
    with pytest.raises(ValueError,match='Approval'):
        request(service,'yes')
    runtime.state['cave_result']={'status':'running','plan':{'original_request':'Farm Cave'},
        'arrival_observation':{'observation_id':'arrival'},'findings':{'message':'Exterior only','observation':{'image':'retained-image'}},
        'return_observation':None,'handback_confirmed':False}
    service.snapshot()
    reopened=StardewConversationService(runtime=CaveRuntime(),artifacts_root=tmp_path).snapshot()
    assert reopened['cave_result']['historical'] and reopened['cave_result']['status']=='interrupted'
    assert reopened['cave_result']['findings']['observation']['image']=='retained-image'
    assert reopened['plan'] is None and not reopened['reviewed']


def test_expired_cave_authority_stops_without_pulse(tmp_path):
    runtime,_,commands,plan=ready(tmp_path)
    runtime.start(plan,background=False)
    runtime.controller.authorization=replace(runtime.controller.authorization,
        expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
    runtime.tick()
    assert not commands and runtime.cave_result['status']=='stopped'
    assert runtime.cave_result['handback_confirmed'] and runtime.cave_result['return_observation'] is None


def test_discussion_cancels_authority_and_plan_then_reopened_completed_result(tmp_path):
    runtime,_,commands,plan=ready(tmp_path)
    service=StardewConversationService(runtime=runtime,artifacts_root=tmp_path/'conversation')
    service._plan=plan.to_dict()
    runtime.start(plan,background=False)
    run(runtime,lambda:runtime.cave_result['findings'] is not None)
    count=len(commands)
    request(service,'What did you find?')
    runtime.tick()
    assert len(commands)==count and runtime.controller.authorization is None
    assert service.snapshot()['plan'] is None and runtime.cave_result['findings']
    revised=runtime.propose_cave('return home','chat',return_only=True)
    runtime.review(revised)
    runtime.start(revised,background=False)
    run(runtime,lambda:runtime.status!='running')
    service.snapshot()
    reopened=StardewConversationService(runtime=CaveRuntime(),artifacts_root=tmp_path/'conversation').snapshot()
    assert reopened['cave_result']['status']=='completed' and reopened['cave_result']['historical']
    assert reopened['cave_result']['plan']['original_request']=='return home'
    assert reopened['cave_result']['initial_request']=='Explore Farm Cave'
    assert not reopened['reviewed'] and reopened['plan'] is None


def test_missing_return_evidence_and_changed_file_refuse(tmp_path):
    calibrated=route(tmp_path)
    c=json.loads(calibrated.raw)
    del c['edge_records'][0]['return']
    calibrated.path.write_text(json.dumps(c))
    with pytest.raises(ValueError,match='approach/return'):
        CaveRoute(calibrated.path,profile_id='test')
    calibrated=route(tmp_path)
    (tmp_path/'qualification.json').write_text('changed')
    with pytest.raises(ValueError,match='changed'):
        calibrated.check()


def test_entrance_capture_cannot_predate_arrival(tmp_path):
    runtime,state,_,_=ready(tmp_path)
    screen=replace(state[0],position=screen_at(48,48).position,observation_id='fresh')
    with pytest.raises(ValueError,match='predates'):
        runtime._cave_route.findings(screen,session_id='session',baseline_id='arrival',
            baseline_time=(datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat())


def test_interior_scene_refuses_even_at_matching_geometry(tmp_path):
    runtime,state,commands,_=ready(tmp_path)
    screen=replace(state[0],position=replace(state[0].position,location='FarmCave'))
    with pytest.raises(ValueError,match='exterior only'):
        runtime._cave_route.validate_view(screen)
    assert not commands


def test_urgent_stop_is_not_consumed_by_pending_clarification(tmp_path):
    runtime=CaveRuntime()
    service=StardewConversationService(runtime=runtime,artifacts_root=tmp_path)
    request(service,'Explore a cave')
    state=request(service,'stop')
    assert state['plan'] is None and not service._cave_pending
    assert ('stop',) in runtime.calls
