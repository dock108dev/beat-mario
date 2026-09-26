"""Synthetic history/resource checks; retained real frames qualify pixel reading."""

from types import SimpleNamespace
from PIL import Image
import pytest
from smb3_agent.stardew_adapter import StardewAdapterError, WindowObservation
from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile


def reader(tmp_path):
    image = tmp_path / "fixture.png"
    Image.new("RGB", (1512, 949)).save(image)
    profile = PreparedFarmPixelProfile.__new__(PreparedFarmPixelProfile)
    profile.last_visible = {}
    profile.previous = None
    profile.tool_uses = 0
    profile.qualified = lambda: True
    frame = {
        "crops": {(0, 3): False, (1, 3): False},
        "player": (0, 0),
        "origin": (768, 456),
        "uncertainty": 2,
        "energy": 270,
        "water": 40,
    }
    profile.decode = lambda _: frame
    window = WindowObservation(
        1, "start", "window", "Stardew", (0, 33, 1512, 949), True, True, True
    )
    save = SimpleNamespace(nonce="fresh", disposable_tree_sha256="sha")
    return profile, frame, image, window, save


def test_first_hidden_frame_and_changed_session_cannot_use_old_history(tmp_path):
    p, f, image, w, save = reader(tmp_path)
    f["player"] = (0, 180)
    f["crops"][(0, 3)] = None
    with pytest.raises(StardewAdapterError, match="lacks recent"):
        p.recognize(image, w, save)
    f["crops"][(0, 3)] = False
    p.recognize(image, w, save)
    save.nonce = "another"
    with pytest.raises(StardewAdapterError, match="new perception history"):
        p.recognize(image, w, save)


def test_history_preserves_identity_but_never_supplies_hidden_state(
    tmp_path, monkeypatch
):
    p, f, image, w, save = reader(tmp_path)
    monkeypatch.setattr("smb3_agent.stardew_farm_vision.time.monotonic", lambda: 100)
    p.recognize(image, w, save)
    f["player"] = (0, 180)
    f["crops"][(0, 3)] = None
    partial = p.recognize(image, w, save)
    assert partial.crops[0].occluded and partial.crops[0].confidence == 0
    assert partial.unknown_regions == ("player-occluded:farm-0-3",)
    with pytest.raises(StardewAdapterError):
        partial.validate("sha")
    monkeypatch.setattr("smb3_agent.stardew_farm_vision.time.monotonic", lambda: 131)
    with pytest.raises(StardewAdapterError, match="lacks recent"):
        p.recognize(image, w, save)


def test_resource_and_crop_changes_must_reconcile_before_history_advances(tmp_path):
    p, f, image, w, save = reader(tmp_path)
    p.recognize(image, w, save)
    f["water"] = 39
    f["energy"] = 268
    with pytest.raises(StardewAdapterError, match="lacks a newly visible"):
        p.recognize(image, w, save)
    assert p.previous.energy == 270 and p.tool_uses == 0
    f["crops"][(0, 3)] = True
    result = p.recognize(image, w, save)
    assert result.tool.tool_uses == 1 and result.energy == 268
    f["crops"][(1, 3)] = True
    with pytest.raises(StardewAdapterError, match="do not reconcile"):
        p.recognize(image, w, save)
    assert p.last_visible[(1, 3)][0] is False


def test_aim_requires_unique_marker_on_exact_visible_dry_target(tmp_path):
    from PIL import ImageDraw

    p, frame, _, _, _ = reader(tmp_path)
    before = SimpleNamespace(
        position=SimpleNamespace(world_pixel_x=0, world_pixel_y=0, pixel_uncertainty=2)
    )
    p.decode = lambda image, resources=False, aiming_at=None: frame
    image = Image.new("RGB", (1512, 949), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((744, 576, 791, 623), outline=(205, 70, 39), width=2)
    p.verify_aim(image, (0, 3), before)
    frame["crops"][(0, 4)] = None  # supplementary frame cannot credit this crop
    p.verify_aim(image, (0, 3), before)
    wrong = Image.new("RGB", (1512, 949), "white")
    ImageDraw.Draw(wrong).rectangle(
        (744, 624, 791, 671), outline=(205, 70, 39), width=2
    )
    with pytest.raises(StardewAdapterError, match="uniquely match"):
        p.verify_aim(wrong, (0, 3), before)
    frame["crops"][(0, 3)] = None
    with pytest.raises(StardewAdapterError, match="visibly dry"):
        p.verify_aim(image, (0, 3), before)
