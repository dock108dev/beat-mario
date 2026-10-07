"""Synthetic scene variations and selected-copy contracts; no native acceptance."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_selected_scene import SelectedSceneProfile, scene_routes
from smb3_agent.stardew_preparation import selected_menu_point


def test_observed_targets_and_obstacles_change_routes():
    clear = {(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)}
    left = scene_routes(clear, {(0, 3): False})
    right = scene_routes(clear, {(2, 3): False})
    assert left['watering'] == {'farm-0-3': 'view-0-2'}
    assert right['watering'] == {'farm-2-3': 'view-2-2'}
    with pytest.raises(StardewAdapterError, match='no observed clear approach'):
        scene_routes(clear-{(1, 2)}, {(2, 3): False})


@pytest.mark.parametrize('value', [
    {'screen': 'bedroom', 'action': 'choose', 'point': [600, 300], 'selected_copy_visible': True},
    {'screen': 'load_list', 'action': 'choose', 'point': [600, 300], 'selected_copy_visible': False},
    {'screen': 'load_list', 'action': 'choose', 'point': [10, 10], 'selected_copy_visible': True},
])
def test_model_cannot_click_arbitrary_scene_or_unidentified_copy(value):
    with pytest.raises(StardewAdapterError, match='not visibly established'):
        selected_menu_point(value)


def test_observed_menu_coordinates_are_not_fixture_coordinates():
    for point in ([500, 250], [900, 500]):
        assert selected_menu_point({'screen': 'load_list', 'action': 'choose',
                                    'point': point, 'selected_copy_visible': True}) == tuple(point)


def test_new_targets_and_changed_terrain_refuse_execution(tmp_path):
    # Perception and controller boundaries are exercised independently of any
    # simulated provider claim. No qualification record is manufactured.
    p = SelectedSceneProfile.__new__(SelectedSceneProfile)
    p.route_config = {'return_pose': 'home'}
    p.route_cells = {(0, 0), (0, 1), (0, 2)}
    p.reviewed_edges = p.observed_edges = set()
    p.expected = {(0, 3)}
    p.scan = lambda _: ({(0, 3): False, (1, 3): False}, p.route_cells, (768, 456), (0, 0), 2)
    with pytest.raises(StardewAdapterError, match='unreviewed seed'):
        p.decode(Image.new('RGB', (1512, 949)))
    p.scan = lambda _: ({(0, 3): False}, {(0, 0)}, (768, 456), (0, 0), 2)
    with pytest.raises(StardewAdapterError, match='terrain changed'):
        p.decode(Image.new('RGB', (1512, 949)))


def test_selected_copy_action_preserves_source_choice_and_authorization(tmp_path):
    from smb3_agent.stardew_runtime import StardewRuntime
    from smb3_agent.conversation_service import StardewConversationService
    runtime = StardewRuntime()
    received = []
    runtime.setup = lambda value: received.append(value)
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    try:
        service.dispatch('launch_selected_copy', {'source': '/selected/Ordinary_123',
            'copy_authorized': True, 'installation': '/selected/Stardew Valley.app'})
        assert received == [{'action': 'launch_selected_copy', 'source': '/selected/Ordinary_123',
                             'copy_authorized': True, 'installation': '/selected/Stardew Valley.app'}]
        assert runtime.current_plan is None
    finally:
        service.close()


def test_missing_copy_approval_is_refused_before_launch(tmp_path):
    from smb3_agent.stardew_setup import launch_fresh_engineering
    with pytest.raises(StardewAdapterError, match='approve copying'):
        launch_fresh_engineering(tmp_path/'missing-app', tmp_path/'destination',
                                 selected_source=tmp_path/'selected', copy_authorized=False)
    assert not (tmp_path/'destination').exists()


def test_ordered_loading_and_current_scene_required_for_selected_copy(tmp_path, monkeypatch):
    import json
    from dataclasses import asdict
    import smb3_agent.stardew_setup as setup
    from smb3_agent.stardew_adapter import DisposableSaveManager
    original = tmp_path/'owner'/'Ordinary_123'
    original.mkdir(parents=True)
    (original/original.name).write_bytes(b'owner save preserved without state parsing')
    (original/'SaveGameInfo').write_bytes(b'owner metadata')
    root = tmp_path/'launch'
    farm = root/'config/StardewValley/Saves'/original.name
    manager = DisposableSaveManager()
    identity = manager.create(original, farm)
    (root/'selected-source.json').write_text(json.dumps({'schema': 'stardew-selected-copy/v1',
        'copy_authorized': True, 'save': asdict(identity)}))
    launch = SimpleNamespace(root=str(root), config_root=str(root/'config'))
    monkeypatch.setattr(setup, '_verify_engineering_launch_identity', lambda *_: None)
    window = SimpleNamespace(process_id=42, process_started_at='start', window_id='window')
    load, field = root/'load.png', root/'field.png'
    Image.new('RGB', (200, 200), 'white').save(load)
    Image.new('RGB', (200, 200), 'blue').save(field)
    import os
    os.utime(load, ns=(1_000_000, 1_000_000))
    os.utime(field, ns=(2_000_000, 2_000_000))
    session = setup.DisposableSessionSetup(manager)
    profile = SimpleNamespace(qualified=lambda: True, scene_receipt={'sha256': 'mismatched'})
    with pytest.raises(StardewAdapterError, match='matching observed support'):
        setup.verify_selected_scene(session, launch, window, profile, field, load)
    assert session.session is None and manager.verify_primary_unchanged(identity)


def test_ordinary_form_exposes_selection_and_keeps_fixture_separate():
    from smb3_agent.conversation_ui import render_stardew_conversation_workspace
    page = render_stardew_conversation_workspace()
    assert 'data-action="launch_selected_copy"' in page
    assert 'Copy this selected save and preserve the original' in page
    assert 'Engineering regression: frozen prepared farms' in page
    assert 'data-action="import_day2_seed"' in page
    assert '"launch_selected_copy"].includes(action)' not in page  # JS is served separately


def test_retained_feature_pixels_discover_targets_without_seed_identity():
    manifest = Path(__file__).resolve().parents[1]/'artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json'
    if not manifest.is_file():
        pytest.skip('Native feature bank is a local package prerequisite')
    p = SelectedSceneProfile(manifest)
    assert p.qualified()
    p.select_can(p.reference)
    crops, clear, *_ = p.scan(p.reference)
    assert len(crops) == 15 and {(0, 0), (0, 1), (0, 2)} <= clear
    # Native feature replay qualifies only readers. Fixture layout is expressly
    # refused when this narrower graph cannot establish every required route.
    with pytest.raises(StardewAdapterError, match='no observed clear approach'):
        p.establish(p.reference, screenshot=Path(p.feature_config['reference']))


def test_clear_endpoints_do_not_authorize_an_unknown_swept_corridor():
    clear = {(0, 0), (0, 1), (0, 2), (1, 2)}
    edges = {frozenset(((0, 0), (0, 1))), frozenset(((0, 1), (0, 2)))}
    with pytest.raises(StardewAdapterError, match='no observed clear approach'):
        scene_routes(clear, {(1, 3): False}, edges=edges)
    edges.add(frozenset(((0, 2), (1, 2))))
    assert scene_routes(clear, {(1, 3): False}, edges=edges)['watering'] == {'farm-1-3': 'view-1-2'}


def test_synthetic_changed_seed_layout_uses_current_pixels_and_exact_resources(tmp_path):
    manifest = Path(__file__).resolve().parents[1]/'artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json'
    if not manifest.is_file():
        pytest.skip('Native feature bank is a local package prerequisite')
    p = SelectedSceneProfile(manifest)
    image = p.reference.copy()
    # Deliberately modified replay image, not a player save or live acceptance.
    ground = image.crop((753, 537, 784, 568))
    for x, y in p.feature_config['expected_tiles']:
        if (x, y) != (0, 3):
            image.paste(ground, (768+48*x-15, 456+48*y-15))
    screenshot = tmp_path/'synthetic-one-seed.png'
    image.save(screenshot)
    p.select_can(image)
    navigator = p.establish(image, screenshot=screenshot)
    assert navigator.watering == {'farm-0-3': 'view-0-2'}
    frame = p.decode(image)
    assert frame['crops'] == {(0, 3): False}
    assert (frame['energy'], frame['water']) == (270, 40)
    # A full-width outline check detects clipping beyond the selected can.
    damaged = image.copy()
    damaged.paste('black', (1150, 862, 1157, 932))
    with pytest.raises(StardewAdapterError, match='outline'):
        p.select_can(damaged)


def test_selected_preparation_late_reply_cannot_resume_after_take_control(tmp_path, monkeypatch):
    import json
    import threading
    from dataclasses import asdict
    from smb3_agent.stardew_adapter import DisposableSaveManager, WindowObservation
    from smb3_agent.stardew_runtime import StardewRuntime
    from smb3_agent.stardew_preparation import GoalPreparation
    import smb3_agent.candidate_resources as resources
    import smb3_agent.stardew_adapter as adapter
    import smb3_agent.stardew_selected_scene as scene
    import smb3_agent.stardew_input as inputs
    import smb3_agent.stardew_setup as setup
    original = tmp_path/'original'
    original.mkdir()
    (original/'original').write_bytes(b'save')
    (original/'SaveGameInfo').write_bytes(b'metadata')
    identity = DisposableSaveManager().create(original, tmp_path/'copy')
    (tmp_path/'selected-source.json').write_text(json.dumps({'save': asdict(identity)}))
    entered, release = threading.Event(), threading.Event()
    commands = []
    class Provider:
        status = {'available': True}
        def infer(self, *args, **kwargs):
            entered.set()
            assert release.wait(3)
            return {'screen': 'title', 'action': 'load', 'point': [630, 868],
                    'selected_copy_visible': False, 'reason': 'Load is visible'}
    class Profile:
        viewport_size = (1512, 949)
        def __init__(self, *_):
            pass
        def qualified(self):
            return True
        def geometry(self, *_):
            raise StardewAdapterError('Not a field')
    window = WindowObservation(42, 'start', 'window', 'Stardew', (0, 33, 1512, 949), True, True, True)
    class Native:
        def __init__(self, **kwargs):
            pass
        def activate_window(self, **kwargs):
            return window
        def detect_window(self):
            return window
        def capture(self, window, path):
            Image.new('RGB', (1512, 949)).save(path)
            return path
    class Driver:
        def __init__(self, **kwargs):
            pass
        def arm(self):
            commands.append('arm')
        def send(self, command):
            commands.append(command)
        def neutralize(self):
            pass
    monkeypatch.setattr(resources, 'calibration_registration', lambda: {'manifest': 'fixture'})
    monkeypatch.setattr(scene, 'SelectedSceneProfile', Profile)
    monkeypatch.setattr(adapter, 'MacVisibleStardewBackend', Native)
    monkeypatch.setattr(inputs, 'MacOrdinaryInputDriver', Driver)
    monkeypatch.setattr(setup, '_verify_engineering_launch_identity', lambda *_: None)
    monkeypatch.setattr(setup, '_engineering_farm', lambda *_: None)
    runtime = StardewRuntime()
    runtime.setup_manager = setup.DisposableSessionSetup()
    runtime._engineering_launches = [(SimpleNamespace(root=str(tmp_path), process_id=42,
        process_started_at='start', status=lambda: {}), SimpleNamespace(poll=lambda: None))]
    preparation = runtime._goal_preparation = GoalPreparation(runtime, Provider())
    preparation.start({'maximum_seconds': 30, 'constraints': ['Return promptly'], 'excluded_ids': ['left']})
    assert entered.wait(3)
    assert preparation.result['maximum_seconds'] == 30
    runtime.control('reclaim')
    release.set()
    preparation.worker.join(3)
    assert not preparation.worker.is_alive() and commands == []
    assert preparation.result['status'] == 'stopped' and runtime.controller is None


def test_preparation_release_failure_revokes_authority_and_blocks_new_activity():
    from smb3_agent.stardew_runtime import StardewRuntime
    runtime = StardewRuntime()
    def failed_release():
        raise OSError('Owned native release failed')
    runtime._preparation_driver = SimpleNamespace(neutralize=failed_release)
    state = runtime.control('reclaim')
    assert runtime._cancel.is_set()
    assert state['status'] == 'failed'
    assert state['handback_confirmed'] is False and state['neutralized'] is False
    # An independent cleanup retry must actually release the retained driver.
    runtime._preparation_driver.neutralize = lambda: None
    state = runtime.control('reclaim')
    assert state['handback_confirmed'] is True


def test_changed_menu_after_inference_cannot_receive_an_old_click():
    from smb3_agent.stardew_preparation import verify_preparation_reply
    before = Image.new('RGB', (1512, 949), 'white')
    after = before.copy()
    reply = {'screen': 'load_list', 'action': 'choose', 'point': [600, 300], 'selected_copy_visible': True}
    verify_preparation_reply(before, after, reply)
    after.paste('black', (590, 290, 610, 310))
    with pytest.raises(StardewAdapterError, match='menu target changed'):
        verify_preparation_reply(before, after, reply)


def test_changed_bedroom_pose_after_inference_cannot_receive_old_movement():
    from smb3_agent.stardew_preparation import verify_preparation_reply, PreparationTargetChanged
    before = Image.new('RGB', (1512, 949), 'white')
    before.paste((43, 66, 146), (740, 400, 750, 405))
    after = Image.new('RGB', before.size, 'white')
    after.paste((43, 66, 146), (760, 400, 770, 405))
    with pytest.raises(PreparationTargetChanged, match='player moved'):
        verify_preparation_reply(before, after, {'screen': 'bedroom', 'action': 'down'})


def test_reopened_chat_is_descriptive_and_cannot_restore_disk_authority(tmp_path):
    import json
    from smb3_agent.conversation_service import StardewConversationService
    log = tmp_path/'stardew-conversation-old.jsonl'
    log.write_text(json.dumps({'role': 'user', 'text': 'Water the lower one', 'kind': 'request',
        'plan': {'approved': True}, 'selected_target_ids': ['forged'], 'input_authority': True})+'\n'+
        '{partial interrupted tail\n')
    service = StardewConversationService(artifacts_root=tmp_path)
    try:
        state = service.snapshot()
        assert state['messages'] == [{'role': 'user', 'text': 'Water the lower one',
            'kind': 'request', 'at': '', 'historical': True}]
        assert state['plan'] is None and not state['reviewed']
        assert state['selected_target_ids'] == [] and state['runtime']['session_id'] is None
        assert state['runtime']['handback_confirmed']
        assert log.read_text().endswith('{partial interrupted tail\n')
    finally:
        service.close()


def test_in_bed_actor_patch_is_revalidated_without_authorizing_a_click():
    from smb3_agent.stardew_preparation import verify_preparation_reply, selected_menu_point, PreparationTargetChanged
    before = Image.new('RGB', (1512, 949), 'white')
    before.paste('brown', (990, 590, 1020, 620))
    reply = {'screen':'bedroom', 'action':'left', 'point':[1005,605], 'selected_copy_visible':False}
    verify_preparation_reply(before, before.copy(), reply)
    assert selected_menu_point(reply) is None
    changed = before.copy()
    changed.paste('black', (998, 599, 1012, 613))
    with pytest.raises(PreparationTargetChanged, match='in-bed player changed'):
        verify_preparation_reply(before, changed, reply)



def test_unfinished_native_surface_record_cannot_expand_passable_terrain(tmp_path, monkeypatch):
    import json
    import smb3_agent.stardew_view_settings as features
    receipt = tmp_path/'native.json'
    receipt.write_text(json.dumps({'status':'failed', 'owned_input_released':True, 'steps':[]}))
    monkeypatch.setattr(features, 'ViewSettingFeatures', lambda: SimpleNamespace(config={
        'native_clear_sweeps':[{'receipt':str(receipt), 'reference':'unread'}],
        'evidence_hashes':{str(receipt):'test', 'unread':'test'}}))
    profile = SelectedSceneProfile.__new__(SelectedSceneProfile)
    profile.clear_templates = set()
    with pytest.raises(StardewAdapterError, match='incomplete'):
        profile._extend_native_terrain()
    assert not profile.clear_templates


def test_unknown_microtexture_cannot_supply_a_terrain_edge():
    p = SelectedSceneProfile.__new__(SelectedSceneProfile)
    known = Image.new('RGB',(37,21),(100,120,140)).tobytes()
    p.clear_templates = {known}
    p.clear_motifs = set(p._motifs(known))
    p._terrain_cache = {}
    changed = Image.frombytes('RGB',(37,21),known)
    changed.putpixel((18,10),(101,120,140))
    assert p._passable(known)
    assert not p._passable(changed.tobytes())


def test_qualified_renderer_requires_spatial_pattern_and_both_error_bounds():
    import numpy as np
    p = SelectedSceneProfile.__new__(SelectedSceneProfile)
    colors = [(191,119,51), (202,127,54), (217,145,72)] * 3
    known = np.array(colors, dtype=np.int16).reshape(1,27)
    p.clear_motifs = {known.astype(np.uint8).tobytes()}
    p._renderer_bank = known
    p._renderer_motif_cache = {}
    changed = known.copy()
    changed[0,0] += 5
    assert p._terrain_motif(changed.astype(np.uint8).tobytes())
    changed[0,0] += 5
    assert not p._terrain_motif(changed.astype(np.uint8).tobytes())
    shifted = known + 4  # Per-channel bound alone cannot qualify a new tint.
    assert not p._terrain_motif(shifted.astype(np.uint8).tobytes())
    uniform = np.tile([202,127,54],9).astype(np.uint8).tobytes()
    assert not p._terrain_motif(uniform)


def test_swept_footprint_can_overlap_localized_avatar_but_other_unknowns_block():
    p = SelectedSceneProfile.__new__(SelectedSceneProfile)
    p.tiles = [(0,1)]
    p.route_config = {'return_pose': 'home'}
    p.route_cells = {(0,0),(0,1)}
    p.geometry = lambda _: ([(100,100)], (100,100), (0,119), 2.5)
    p._clear = lambda image,x,y: y != 136
    image = Image.new('RGB',(1512,949))
    p.scan(image)
    edge = frozenset(((0,0),(0,1)))
    assert edge in p.observed_edges
    p._clear = lambda image,x,y: y != 115
    p.scan(image)
    assert edge not in p.observed_edges


@pytest.mark.parametrize('player_y,covered', [(131, True), (143, False)])
def test_route_cell_and_sweep_share_localized_avatar_footprint(player_y, covered):
    p = SelectedSceneProfile.__new__(SelectedSceneProfile)
    p.tiles = [(0, 1)]
    p.route_config = {'return_pose': 'home'}
    p.route_cells = {(0, 0), (0, 1)}
    p.geometry = lambda _: ([(100, 100)], (100, 100), (0, player_y), 2.5)
    p._clear = lambda image, x, y: y != 148
    _, clear, *_ = p.scan(Image.new('RGB', (1512, 949)))
    assert ((0, 1) in clear) is covered
    assert (frozenset(((0, 0), (0, 1))) in p.observed_edges) is covered


def test_reviewed_crop_paths_exclude_unselected_branch_and_rebind_fresh_scope():
    p = SelectedSceneProfile.__new__(SelectedSceneProfile)
    p.route_config = {
        'poses': {'home': [0, 0], 'middle': [0, 48], 'left': [-48, 48], 'right': [48, 48]},
        'edges': [['home', 'middle'], ['middle', 'left'], ['middle', 'right']],
        'return_pose': 'home', 'watering': {'left-seed': 'left', 'middle-seed': 'middle', 'right-seed': 'right'}}
    p.review_targets(['middle-seed', 'right-seed'])
    left_edge = frozenset(((0, 1), (-1, 1)))
    assert left_edge not in p._activity_edges
    assert p._activity_cells == {(0, 0), (0, 1), (1, 1)}
    p.review_targets(['left-seed'])
    assert left_edge in p._activity_edges
    assert (1, 1) not in p._activity_cells
    with pytest.raises(StardewAdapterError, match='no observed approach'):
        p.review_targets(['unknown'])


def test_scene_route_omits_unrelated_observed_terrain():
    clear = {(0, 0), (0, 1), (0, 2), (1, 1), (2, 1), (3, 1)}
    route = scene_routes(clear, {(0, 3): False})
    assert set(route['poses']) == {'view-0-0', 'view-0-1', 'view-0-2'}


@pytest.mark.parametrize('handback,reason', [(False, 'neutral handback'), (True, 'unhashed evidence')])
def test_later_floor_exposure_requires_neutral_handback_and_hash_bound_pixels(tmp_path, monkeypatch, handback, reason):
    import hashlib
    import json
    import smb3_agent.stardew_view_settings as features
    image = tmp_path/'reference.png'
    Image.new('RGB', (100, 100), 'brown').save(image)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    receipt = tmp_path/'native.json'
    receipt.write_text(json.dumps({
        'status': 'native_passable_corridor_observed', 'owned_input_released': True,
        'initial': {'position': [0, 0]}, 'steps': [{
            'before': {'position': [0, 0], 'sha256': digest},
            'after': {'position': [0, 1], 'sha256': digest},
            'pulse_timing': {'post_to_release_seconds': .1}}],
        'neutral_exposure_handback_confirmed': handback,
        'neutral_exposure_frames': [{'sha256': 'unapproved'}]}))
    monkeypatch.setattr(features, 'ViewSettingFeatures', lambda: SimpleNamespace(config={
        'native_clear_sweeps': [{'receipt': str(receipt), 'reference': str(image)}],
        'evidence_hashes': {str(receipt): 'test', str(image): digest}}))
    profile = SelectedSceneProfile.__new__(SelectedSceneProfile)
    profile.clear_templates = set()
    profile.geometry = lambda image: ([], (20, 20), (0, 0), 1)
    profile._reference_crops = lambda image, origin: {}
    with pytest.raises(StardewAdapterError, match=reason):
        profile._extend_native_terrain()
    assert not profile.clear_templates
