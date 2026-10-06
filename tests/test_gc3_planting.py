"""Synthetic behavior and retained-frame replay, never live gameplay proof."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from smb3_agent.stardew_planting import PlantingSurvey, recommend, location_request
from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
from smb3_agent.conversation_service import StardewConversationService
from smb3_agent.conversation_ui import render_stardew_conversation_workspace, STARDEW_CONVERSATION_JS
from test_stardew_conversation import FakeStardewRuntime, request


def survey():
    return {'observation_id':'frame', 'session_id':'copy', 'observed_at':datetime.now(timezone.utc).isoformat(),
        'season':'spring', 'day':2, 'targets':[
            {'id':'a','tile':[3,2], 'box':[1,1,49,49], 'state':'empty_dirt','access_observed':True, 'label':'bare ground just right of the starter crops'},
            {'id':'b','tile':[4,2], 'box':[49,1,97,49], 'state':'empty_dirt','access_observed':True, 'label':'bare ground below the mailbox'},
            {'id':'crop','tile':[0,3], 'state':'occupied','label':'existing crop patch'},
            {'id':'path','tile':[3,1], 'state':'access','label':'access strip beside the porch'},
            {'id':'tree','tile':[-2,4], 'state':'protected','label':'vegetation'},
            {'id':'stone','tile':[0,5], 'state':'debris','label':'stone'}]}


def test_season_alternative_and_future_location_are_separate():
    result = recommend('Where should we plant corn?', survey())
    assert result['status'] == 'unsuitable'
    assert result['location_id'] == 'a'
    assert 'summer or fall' in result['message'] and 'parsnip' in result['message']
    assert 'future seasonal plan' in result['message'] and not result['authorization_granted']


@pytest.mark.parametrize('season,day,crop,status', [('spring',24,'parsnip','suitable'),
    ('spring',25,'parsnip','unsuitable'),('summer',28,'corn','suitable'),('fall',14,'corn','suitable'),
    ('fall',15,'corn','unsuitable'),('winter',1,'tomato','unsuitable'),(None,2,'parsnip','unknown'),('spring',None,'parsnip','unknown')])
def test_growth_calendar_boundaries(season,day,crop,status):
    obs = {**survey(),'season':season,'day':day}
    result = recommend(f'Where should we grow {crop}?',obs)
    expected = status if status != 'unknown' else 'insufficiently_observed'
    assert result['status'] == expected


def test_occupied_protected_reserved_and_unobserved():
    obs=survey()
    obs['targets'][0]['state']='unknown'
    obs['targets'][1]['access_observed']=False
    result = recommend('Where should we grow parsnip?',obs)
    assert result['location_id'] is None
    assert [t['suitability'] for t in result['assessments']] == ['insufficiently_observed']*2+['unsuitable']*4
    stale = recommend('Where should we grow parsnip?', {**survey(), 'observed_at':(datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat()})
    assert stale['location_id'] is None


def test_revisions_explanation_and_trellis_access():
    obs=survey()
    corn=recommend('Where to plant corn?',obs)
    parsnip=recommend('Actually parsnips instead of corn',obs,corn)
    assert parsnip['crop']=='parsnip' and parsnip['status']=='suitable'
    other=recommend('How about another spot?',obs,parsnip)
    assert other['location_id']=='b'
    why=recommend('Why?',obs,other)
    assert why['location_id']=='b' and 'adjacent reserved access' in why['message']
    porch=recommend('What about beside the porch?',obs,why)
    assert 'Keep this access strip clear' in porch['message']
    bean=recommend('Change to green beans',obs,porch)
    assert 'blocks walking' in bean['message']
    unsupported=recommend('Change to zucchini',obs,bean)
    assert unsupported['crop']=='zucchini' and unsupported['location_id'] is None
    assert not location_request('Water the tomatoes',bean)


class PassiveRuntime(FakeStardewRuntime):
    def __init__(self):
        super().__init__()
        self.survey=survey()
    def inspect_planting(self):
        self.calls.append(('capture_only',))
        return deepcopy(self.survey)
    def observe(self):
        raise AssertionError('location discussion must not use the input-capable farm observer')


def test_service_discussion_reopen_and_no_authority(tmp_path):
    runtime=PassiveRuntime()
    service=StardewConversationService(runtime=runtime,artifacts_root=tmp_path)
    request(service,'Where should we plant corn?')
    state=request(service,'Actually grow parsnips instead')
    assert state['planting_recommendation']['crop']=='parsnip'
    assert state['plan'] is None and not state['reviewed']
    request(service,'yes')
    assert all(call[0]=='capture_only' for call in runtime.calls)
    reopened=StardewConversationService(runtime=PassiveRuntime(),artifacts_root=tmp_path)
    state=reopened.snapshot()
    assert state['planting_recommendation']['historical']
    assert state['planting_recommendation']['location_id']=='a'
    assert len(state['planting_messages'])==4
    assert state['plan'] is None and not state['reviewed']
    # A reopened crop preference can be discussed, but needs new pixels.
    request(reopened,'Why?')
    assert reopened.runtime.calls==[('capture_only',)]


def test_question_pauses_existing_work_and_discards_actionable_plan(tmp_path):
    runtime=PassiveRuntime()
    runtime.state['status']='running'
    service=StardewConversationService(runtime=runtime,artifacts_root=tmp_path)
    service._plan={'old':'watering'}
    request(service,'Where should we plant parsnips?')
    assert runtime.calls==[('pause',),('capture_only',)]
    assert service.snapshot()['plan'] is None


def test_unavailable_inspection_has_useful_remedy(tmp_path):
    service=StardewConversationService(runtime=FakeStardewRuntime(),artifacts_root=tmp_path)
    state=request(service,'Where should we plant corn?')
    assert state['planting_recommendation']['status']=='insufficiently_observed'
    assert not state['plan']


def test_visual_surface_and_saved_discussion():
    html=render_stardew_conversation_workspace()
    assert 'stardew-planting-visual' in html and 'Earlier location discussion' in html
    assert 'id="stardew-planting-discussion"' in html
    assert 'createElementNS' in STARDEW_CONVERSATION_JS and 'Saved recommendation from an earlier view' in STARDEW_CONVERSATION_JS


@pytest.mark.parametrize('index',[0,1])
def test_retained_actual_frame_replay_and_occupancy_change(tmp_path,index):
    configs=json.loads(Path('data/stardew-planting-survey.json').read_text())['profiles']
    config=configs[index]
    manifest=Path('artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json')
    if not manifest.exists() or not Path(config['image']).exists():
        pytest.skip('local retained calibration absent; synthetic tests remain mandatory')
    profile=PreparedFarmPixelProfile(manifest)
    # Geometry proof remains real-retained, while this test chooses the survey pairing.
    profile.profile_id=config['profile_id']
    inspector=PlantingSurvey(profile)
    observation=inspector.inspect(config['image'],session_id='replay')
    result=recommend('Where should we plant parsnips?',observation)
    assert result['status']=='suitable'
    selected=next(t for t in observation['targets'] if t['id']==result['location_id'])
    im=Image.open(config['image']).convert('RGB')
    ImageDraw.Draw(im).rectangle(selected['box'],fill='magenta')
    changed=tmp_path/'occupied.png'
    im.save(changed)
    observation=inspector.inspect(changed,session_id='replay')
    tile=next(t for t in observation['targets'] if t['id']==selected['id'])
    assert tile['state']=='unknown'
    assert recommend('Where should we plant parsnips?',observation)['location_id']!=selected['id']
    # Unknown calendar never comes from the prepared-day label.
    ImageDraw.Draw(im).rectangle(config['day_box'],fill='black')
    im.save(changed)
    assert inspector.inspect(changed,session_id='replay')['day'] is None


def test_unconfirmed_handback_prevents_passive_inspection(tmp_path):
    from test_stardew_runtime import configured
    runtime, _, _, commands = configured(tmp_path)
    runtime._planting_observer=lambda: survey()
    assert runtime.inspect_planting()['observation_id']=='frame'
    runtime.controller.operator.input_neutralized=False
    with pytest.raises(ValueError, match='handback'):
        runtime.inspect_planting()
    assert not commands


def test_single_pixel_occupancy_is_not_filtered_away(tmp_path):
    config=json.loads(Path('data/stardew-planting-survey.json').read_text())['profiles'][0]
    manifest=Path('artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json')
    if not manifest.exists() or not Path(config['image']).exists():
        pytest.skip('local retained calibration absent')
    profile=PreparedFarmPixelProfile(manifest)
    inspector=PlantingSurvey(profile)
    target=next(t for t in config['targets'] if t['state']=='empty_dirt')
    im=Image.open(config['image']).convert('RGB')
    left,top,right,bottom=target['box']
    im.putpixel(((left+right)//2,(top+bottom)//2),(86,54,52))
    changed=tmp_path/'seed.png'
    im.save(changed)
    result=inspector.inspect(changed,session_id='replay')
    assert next(t for t in result['targets'] if t['id']==target['id'])['state']=='unknown'


def test_unseen_preference_and_crop_patch_are_not_silently_accepted():
    prior=recommend('Where should we plant parsnips?',survey())
    result=recommend('What about left of the farmhouse?',survey(),prior)
    assert result['location_id'] is None and 'outside the observed' in result['message']
    result=recommend('What about in the crop patch?',survey(),prior)
    assert 'Existing crops must be preserved' in result['message']


def test_synthetic_pixel_survey_access_unknown_and_evidence_binding(tmp_path):
    import hashlib
    class Profile:
        profile_id='synthetic'
        def qualified(self):
            return True
        def geometry(self,image):
            return [(24,24)], (24,24), (-1000,-1000), 1
    source=tmp_path/'sample.png'
    im=Image.new('RGB',(200,200),(200,180,90))
    im.save(source)
    config={'profile_id':'synthetic','image':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'origin':[24,24],'season':'spring','day':2,'season_box':[0,0,10,10],'day_box':[10,0,20,10],
            'targets':[{'id':'entry','tile':[1,2],'box':[48,96,96,144],'state':'access','label':'porch access'},
                       {'id':'soil','tile':[2,2],'box':[96,96,144,144],'state':'empty_dirt','label':'bare dirt'}]}
    manifest=tmp_path/'survey.json'
    manifest.write_text(json.dumps({'profiles':[config]}))
    inspector=PlantingSurvey(Profile(),manifest)
    assert recommend('Where should we plant parsnips?',inspector.inspect(source,session_id='fixture'))['status']=='suitable'
    changed=tmp_path/'unknown-access.png'
    ImageDraw.Draw(im).rectangle([50,100,80,120],fill='black')
    im.save(changed)
    observation=inspector.inspect(changed,session_id='fixture')
    assert observation['targets'][0]['state']=='unknown'
    assert not observation['targets'][1]['access_observed']
    assert recommend('Where should we plant parsnips?',observation)['location_id'] is None
    # Losing retained evidence disables recognition rather than refreshing labels.
    source.write_bytes(b'changed')
    with pytest.raises(ValueError,match='evidence changed'):
        inspector.inspect(changed,session_id='fixture')
