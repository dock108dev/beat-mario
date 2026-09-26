"""Synthetic failure-boundary checks
these are not live farm qualification."""
from types import SimpleNamespace

import pytest
from PIL import Image

from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_farm_perception import FarmPixelProfile
from smb3_agent.stardew_perception import pixel_digest


def menu_fixture(tmp_path, monkeypatch, *, capacity=12):
    monkeypatch.setattr('smb3_agent.stardew_farm_perception.time.sleep', lambda _: None)
    p = FarmPixelProfile.__new__(FarmPixelProfile)
    p.geometry = lambda _: ([], (0, 0), (0, 0), 2)
    p.menu_observation = {'time': 1, 'old': True}
    im = Image.new('RGB', (4, 4), 'orange')
    digest = pixel_digest(im)
    def spec(value):
        return {'box': [0, 0, 4, 4], 'values': {digest: value}}
    p.config = {'inventory': [None] * 12, 'menu_regions': {
        'menu': spec(True), 'capacity': spec(capacity),
        'calendar': spec({'season': 'spring', 'day': 5})}}
    def capture(_, path):
        im.save(path)
        return path
    native = SimpleNamespace(detect_window=lambda: object(), capture=capture)
    commands = []
    driver = SimpleNamespace(send=commands.append)
    return p, native, driver, commands


def test_capacity_mismatch_leaves_menu_open_without_observation(tmp_path, monkeypatch):
    p, native, driver, commands = menu_fixture(tmp_path, monkeypatch, capacity=24)
    with pytest.raises(StardewAdapterError, match='capacity differs'):
        p.read_menu(native, driver, tmp_path)
    assert [c.purpose for c in commands] == ['observe_farm_inventory']
    assert p.menu_observation is None


def test_canceled_menu_close_cannot_publish_facts(tmp_path, monkeypatch):
    p, native, driver, commands = menu_fixture(tmp_path, monkeypatch)
    def send(command):
        commands.append(command)
        if len(commands) == 2:
            raise StardewAdapterError('reclaimed')
    driver.send = send
    with pytest.raises(StardewAdapterError, match='reclaimed'):
        p.read_menu(native, driver, tmp_path)
    assert p.menu_observation is None


def test_unrecognized_farm_invalidates_previous_menu_before_input(tmp_path, monkeypatch):
    p, native, driver, commands = menu_fixture(tmp_path, monkeypatch)
    def reject(_):
        raise StardewAdapterError('unknown farm')
    p.geometry = reject
    with pytest.raises(StardewAdapterError, match='unknown farm'):
        p.read_menu(native, driver, tmp_path)
    assert not commands and p.menu_observation is None


def test_recognized_menu_publishes_captured_capacity_and_calendar(tmp_path, monkeypatch):
    p, native, driver, commands = menu_fixture(tmp_path, monkeypatch)
    p.read_menu(native, driver, tmp_path)
    assert len(commands) == 2
    assert p.menu_observation['values']['capacity'] == 12
    assert p.menu_observation['values']['calendar'] == {'season': 'spring', 'day': 5}


@pytest.mark.parametrize('age', [-1, 5.01])
def test_future_or_stale_menu_cannot_supply_field_facts(monkeypatch, age):
    p = FarmPixelProfile.__new__(FarmPixelProfile)
    p.menu_observation = {'time': 100-age}
    monkeypatch.setattr('smb3_agent.stardew_farm_perception.time.monotonic', lambda: 100)
    with pytest.raises(StardewAdapterError, match='fresh visible inventory'):
        p.decode(Image.new('RGB', (4, 4)))


def test_movement_during_inventory_observation_rejects_field_facts(monkeypatch):
    p = FarmPixelProfile.__new__(FarmPixelProfile)
    p.menu_observation = {'time': 100, 'player': (0, 0), 'uncertainty': 2}
    p.geometry = lambda _: ([], (0, 0), (0, 20), 2)
    monkeypatch.setattr('smb3_agent.stardew_farm_perception.time.monotonic', lambda: 100)
    with pytest.raises(StardewAdapterError, match='player moved during inventory'):
        p.decode(Image.new('RGB', (4, 4)))


def test_calibration_cache_rechecks_evidence_and_changed_configuration(tmp_path, monkeypatch):
    import hashlib
    from copy import deepcopy
    from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
    monkeypatch.setattr(PreparedFarmPixelProfile, 'qualified', lambda _: True)
    frame = tmp_path/'sample.png'
    im = Image.new('RGB', (4, 4), 'orange')
    im.save(frame)
    digest = pixel_digest(im)
    spec = {'box': [0, 0, 4, 4], 'values': {digest: True},
            'samples': [{'image': str(frame), 'digest': digest}]}
    p = FarmPixelProfile.__new__(FarmPixelProfile)
    p.geometry_config = {}
    p.clock_reader = None
    p.farm_manifest = tmp_path/'profile.json'
    p.farm_manifest_bytes = b'fixture'
    p.farm_manifest.write_bytes(p.farm_manifest_bytes)
    roles = ['coverage', 'maturity', 'empty_plots', 'inventory', 'seed_counts', 'debris',
             'protected_targets', 'tools', 'calendar', 'clock', 'approaches', 'negative_frames']
    p.config = {'coverage_bounds': [0, 0, 0, 0], 'targets': [{'id': 't', 'tile': [0, 0], 'region': spec}],
                'farm_approaches': {'harvest': {'t': {}}}, 'protected_neighbors': {'t': []},
                'coverage_mode': 'selected_targets_and_observed_neighbors', 'classification': 'actual_live',
                'qualified_roles': roles, 'geometry_manifest': str(frame), 'qualification_record': str(frame),
                'evidence_hashes': {str(frame): hashlib.sha256(frame.read_bytes()).hexdigest()},
                'inventory': [spec], 'menu_regions': dict.fromkeys(['menu', 'capacity', 'calendar'], spec),
                'aim_regions': dict.fromkeys(['harvest_crop', 'plant_seed', 'clear_debris', 'water_crop', 'select_farm_item'], spec),
                **dict.fromkeys(['selected_slot', 'season', 'day', 'can_water', 'clock'], spec)}
    assert p.qualified() and p.qualified()
    original = frame.read_bytes()
    Image.new('RGB', (4, 4), 'blue').save(frame)
    assert not p.qualified()
    frame.write_bytes(original)
    assert p.qualified()
    p.config = deepcopy(p.config)
    del p.config['aim_regions']['harvest_crop']
    assert not p.qualified()


def test_raster_match_rejects_localized_core_change_and_broad_change():
    import numpy as np
    from smb3_agent.stardew_farm_perception import patch_matches
    reference = np.zeros((38, 36, 3), dtype=np.int16)
    assert patch_matches(reference, reference.copy())
    local = reference.copy()
    local[15:18, 15:18] = 50
    assert not patch_matches(local, reference)  # mean alone would miss this
    assert not patch_matches(reference+3, reference)


def test_toolbar_selection_uses_visible_icon_and_fresh_owned_item():
    from types import SimpleNamespace as N
    from smb3_agent.stardew_farm_perception import FarmPixelProfile
    p = FarmPixelProfile.__new__(FarmPixelProfile)
    p.geometry = lambda _: ([], (0, 0), (0, 0), 2)
    image = Image.new('RGB', (40, 40), 'blue')
    digest = pixel_digest(image.crop((2, 2, 18, 18)))
    p.selection_samples = [(digest, 'parsnip_seeds')]
    p.config = {'inventory_slot_points': {'0': [20, 20]}, 'inventory': [{'icon': {'box': [0, 0, 30, 30]}}]}
    owned = N(slot=0, item='parsnip_seeds', count=13)
    before = N(farm=N(inventory=[owned]), window=N(bounds=(0, 0, 40, 40)),
               position=N(world_pixel_x=0, world_pixel_y=0, pixel_uncertainty=2))
    command = N(purpose='select_farm_item', target=(20, 20))
    p.verify_action_aim(command, image, before)
    owned.count = 0
    with pytest.raises(StardewAdapterError, match='observed owned'):
        p.verify_action_aim(command, image, before)
    owned.count = 13
    p.selection_samples.append((digest, 'pickaxe'))
    with pytest.raises(StardewAdapterError, match='ambiguous'):
        p.verify_action_aim(command, image, before)
    command.target = (25, 20)
    with pytest.raises(StardewAdapterError, match='outside'):
        p.verify_action_aim(command, image, before)


@pytest.mark.parametrize("recover", [False, True])
def test_menu_boundary_retries_occlusion_without_input(tmp_path, monkeypatch, recover):
    p, native, driver, commands = menu_fixture(tmp_path, monkeypatch)
    calls = []
    def geometry(_):
        calls.append(1)
        assert not commands
        if recover and len(calls) == 2:
            return [], (0, 0), (0, 0), 2
        raise StardewAdapterError("camera anchor not recognized")
    p.geometry = geometry
    if recover:
        p.read_menu(native, driver, tmp_path)
        assert len(commands) == 2 and p.menu_observation is not None
    else:
        with pytest.raises(StardewAdapterError, match="anchor"):
            p.read_menu(native, driver, tmp_path)
        assert len(calls) == 8 and not commands and p.menu_observation is None
    assert list(tmp_path.glob("menu-retry-*.json"))
