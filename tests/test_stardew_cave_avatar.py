"""Synthetic sprite contracts; retained native replay has a separate evidence log."""

import pytest
from PIL import Image, ImageDraw

from smb3_agent.stardew_cave_avatar import locate_avatar


def sprite(image, x, y, *, shaded=False):
    d = ImageDraw.Draw(image)
    blue = (39, 70, 119) if shaded else (43, 66, 146)
    brown = (81, 52, 18) if shaded else (62, 25, 5)
    d.rectangle((x-8, y-15, x-3, y-1), fill=blue)
    d.rectangle((x+3, y-15, x+8, y-1), fill=blue)
    d.rectangle((x-9, y+1, x-3, y+12), fill=brown)
    d.rectangle((x+3, y+1, x+9, y+12), fill=brown)


def reference(tmp_path, shaded=True):
    image = Image.new('RGB', (320, 240), (120, 150, 40))
    sprite(image, 100, 100, shaded=shaded)
    path = tmp_path/'sprite.png'
    image.save(path)
    return [{'image': str(path), 'foot_reference': [100, 100]}]


def test_shaded_sprite_translation_is_independent_of_camera_center(tmp_path):
    refs = reference(tmp_path)
    image = Image.new('RGB', (320, 240), (130, 160, 60))
    sprite(image, 240, 155, shaded=True)
    (x, y), interval = locate_avatar(image, refs)
    assert abs(x-240) <= interval and abs(y-155) <= interval
    assert interval <= 3
    assert type(x) is float and type(y) is float


@pytest.mark.parametrize('condition', ['absent', 'two_players', 'pants_only', 'unknown_colors'])
def test_missing_or_ambiguous_avatar_never_returns_a_last_known_location(tmp_path, condition):
    refs = reference(tmp_path)
    image = Image.new('RGB', (320, 240), (120, 150, 40))
    if condition == 'two_players':
        sprite(image, 100, 100, shaded=True)
        sprite(image, 220, 150, shaded=True)
    elif condition == 'pants_only':
        sprite(image, 100, 100, shaded=True)
        ImageDraw.Draw(image).rectangle((80, 100, 120, 120), fill=(120, 150, 40))
    elif condition == 'unknown_colors':
        sprite(image, 100, 100)
    with pytest.raises(ValueError, match='hidden|ambiguous'):
        locate_avatar(image, refs)


def test_translucent_foliage_boots_need_their_own_reviewed_palette(tmp_path):
    reference_image = Image.new('RGB', (320, 240), (130, 160, 60))
    sprite(reference_image, 100, 100, shaded=True)
    draw = ImageDraw.Draw(reference_image)
    # Retained pine-frame palette: brown contrast is muted by translucent leaves.
    for left, right in ((91, 97), (103, 109)):
        draw.rectangle((left, 101, right, 112), fill=(46, 41, 24))
    path = tmp_path/'foliage.png'
    reference_image.save(path)
    refs = [{'image': str(path), 'foot_reference': [100, 100]}]
    current = Image.new('RGB', (320, 240), (120, 150, 40))
    current.paste(reference_image.crop((80, 66, 121, 114)), (210, 121))
    (x, y), interval = locate_avatar(current, refs)
    assert abs(x-230) <= interval and abs(y-155) <= interval
    ImageDraw.Draw(current).rectangle((210, 155, 251, 169), fill=(120, 150, 40))
    with pytest.raises(ValueError, match='hidden|ambiguous'):
        locate_avatar(current, refs)
