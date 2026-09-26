"""Synthetic navigation contracts; live route qualification is separate."""

from dataclasses import replace
from types import SimpleNamespace
import pytest
from smb3_agent.stardew_adapter import (
    CropObservation,
    PositionObservation,
    StardewAdapterError,
    ToolObservation,
)
from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator


def screen(x=0, y=0, hidden=False):
    return SimpleNamespace(
        position=PositionObservation(
            "Farm", round(x / 48), round(y / 48), x == y == 0, 1, x, y, 2, 768, 456 - y
        ),
        tool=ToolObservation("watering_can", 40, 40, 0, 0),
        crops=(
            CropObservation(
                "crop", 0, 3, True, False, hidden, 0 if hidden else 1, "visible.png"
            ),
        ),
        window=SimpleNamespace(bounds=(0, 33, 1512, 949)),
    )


def navigator():
    return ViewpointNavigator(
        {
            "poses": {"home": [0, 0], "south": [0, 96], "water": [0, 138]},
            "edges": [["home", "south"], ["south", "water"]],
            "watering": {"crop": "water"},
            "return_pose": "home",
        }
    )


def test_partial_motion_is_observed_before_next_pulse():
    nav = navigator()
    nav.validate_scope(screen())
    first, _ = nav.next_command(screen(), {"crop"})
    second, _ = nav.next_command(screen(0, 35), {"crop"})
    assert first.control == second.control == "s"
    assert second.duration_ms <= 80
    assert nav._last_node == "home"
    nav.next_command(screen(0, 94), {"crop"})
    assert nav._last_node == "south"
    action, key = nav.next_command(screen(0, 137), {"crop"})
    assert action.purpose == "water_crop" and key == "crop"
    assert action.target == (748, 516)


def test_no_progress_and_corridor_escape_stop():
    nav = navigator()
    for _ in range(3):
        nav.next_command(screen(), {"crop"})
    with pytest.raises(StardewAdapterError, match="no observed progress"):
        nav.next_command(screen(), {"crop"})
    nav = navigator()
    nav.next_command(screen(), {"crop"})
    with pytest.raises(StardewAdapterError, match="deviated"):
        nav.next_command(screen(10, 35), {"crop"})


def test_hidden_target_never_watered_and_unknown_crop_not_dropped():
    nav = navigator()
    nav.next_command(screen(), {"crop"})
    nav.next_command(screen(0, 96), {"crop"})
    with pytest.raises(StardewAdapterError, match="remains hidden"):
        nav.next_command(screen(0, 138, True), {"crop"})
    bad = screen()
    bad.crops = (replace(bad.crops[0], crop_id="additional"),)
    with pytest.raises(StardewAdapterError, match="lacks a qualified"):
        navigator().validate_scope(bad)


def test_return_requires_observed_arrival_and_reset_discards_route():
    nav = navigator()
    nav.next_command(screen(0, 138), set())
    assert nav._waypoint == "south"
    nav.next_command(screen(0, 96), set())
    assert nav.next_command(screen(), set()) == (None, None)
    nav.reset()
    assert nav._last_node is None and nav._total_pulses == 0


def test_route_uses_observed_distance_instead_of_number_of_edges():
    nav = ViewpointNavigator({
        'poses': {'home': [0,0], 'middle': [10,0], 'near': [10,10], 'far': [200,0]},
        'edges': [['home','middle'], ['middle','near'], ['home','far']],
        'watering': {}, 'return_pose': 'home'})
    assert nav._path('home', {'near','far'}) == ('near', ['middle','near'])


def test_water_from_occluding_pose_returns_for_fresh_complete_observation():
    nav = navigator()
    nav.watering['second'] = 'water'
    first = screen()
    second = replace(first.crops[0], crop_id='second', tile_x=1)
    first.crops = (*first.crops, second)
    nav.next_command(first, {'crop','second'})
    full = screen(0,94)
    full.crops = first.crops
    nav.next_command(full, {'crop','second'})
    partial = screen(0,137)
    partial.crops = (partial.crops[0], replace(second, occluded=True, confidence=0))
    action, _ = nav.next_command(partial, {'crop','second'})
    assert action.purpose == 'water_crop'
    action, _ = nav.next_command(partial, {'second'})
    assert action.control == 'w' and action.purpose == 'navigate'
    assert nav._observation_return == 'south'
    full.crops = (replace(first.crops[0], watered=True), second)
    action, _ = nav.next_command(full, {'second'})
    assert nav._observation_return is None and action.control == 's'


def test_briefly_clear_edge_of_watering_pose_is_not_recovery_view():
    nav = navigator()
    nav.next_command(screen(), {'crop'})
    nav.next_command(screen(0,96), {'crop'})
    # Clear at the observed edge, but the calibrated center overlaps the crop.
    nav.next_command(screen(0,134), {'crop'})
    assert nav._last_node == 'water'
    assert nav._last_complete_node == 'south'
    action, _ = nav.next_command(screen(0,138,True), set())
    assert action.control == 'w'
    assert nav._observation_return == 'south'
