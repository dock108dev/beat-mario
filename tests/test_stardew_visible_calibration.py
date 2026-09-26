"""Synthetic calibration algorithm checks, not actual game/perception evidence."""
import json

import pytest
from PIL import Image

from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_perception import (
    CalibratedBarRegion, ExactGlyph, MaskedPixelTemplate, MaskedTemplateRegion,
    NumericHudRegion, retain_region_calibration,
)


def test_masked_features_ignore_only_explicitly_unexamined_pixels():
    source = Image.new("RGBA", (8, 8), "red")
    source.putalpha(Image.frombytes("L", (8, 8), bytes([255]*32+[0]*32)))
    template = MaskedPixelTemplate.from_image(source, "dry")
    region = MaskedTemplateRegion((0, 0, 8, 8), (template,))
    frame = Image.new("RGB", (8, 8), "red")
    frame.paste("blue", (0, 4, 8, 8))
    assert region.recognize(frame) == "dry"
    frame.putpixel((0, 0), (0, 0, 0))
    with pytest.raises(StardewAdapterError, match="unrecognized or occluded"):
        region.recognize(frame)


def test_conflicting_calibration_does_not_choose_a_state():
    source = Image.new("RGBA", (4, 4), "red")
    region = MaskedTemplateRegion((0, 0, 4, 4), tuple(
        MaskedPixelTemplate.from_image(source, state) for state in ("dry", "watered")))
    with pytest.raises(StardewAdapterError, match="ambiguous"):
        region.recognize(source)


def glyph(pattern):
    image = Image.new("RGB", (len(pattern[0]), len(pattern)), "white")
    for y, row in enumerate(pattern):
        for x, bit in enumerate(row):
            if bit == "1":
                image.putpixel((x, y), (0, 0, 0))
    return image


def test_exact_numeric_tooltip_reader_rejects_unknown_glyph_and_maximum():
    samples = {"2": glyph(("111", "001", "111", "100", "111")),
               "7": glyph(("111", "001", "010", "010", "010")),
               "0": glyph(("111", "101", "101", "101", "111")),
               "/": glyph(("001", "001", "010", "100", "100"))}
    palette = ((0, 0, 0),)
    glyphs = tuple(ExactGlyph.calibrate(char, image, palette) for char, image in samples.items())
    text = "270/270"
    frame = Image.new("RGB", (len(text)*4, 5), "white")
    for index, char in enumerate(text):
        frame.paste(samples[char], (index*4, 0))
    reader = NumericHudRegion((0, 0, frame.width, 5), palette, glyphs, expected_maximum=270)
    assert reader.recognize(frame) == 270
    assert reader.recognize_text(frame) == text
    wrong_max = NumericHudRegion(reader.box, palette, glyphs, expected_maximum=300)
    with pytest.raises(StardewAdapterError, match="maximum changed"):
        wrong_max.recognize(frame)
    frame.putpixel((1, 0), (255, 255, 255))
    with pytest.raises(StardewAdapterError, match="unknown or ambiguous"):
        reader.recognize(frame)


def test_bar_requires_unique_calibration_contiguous_fill_and_known_colors():
    frame = Image.new("RGB", (10, 2), "white")
    frame.paste("blue", (0, 0, 5, 2))
    decoder = CalibratedBarRegion((0, 0, 10, 2), ((0, 0, 255),), ((255, 255, 255),), {5: (20,)})
    assert decoder.recognize(frame) == 20
    ambiguous = CalibratedBarRegion(decoder.box, decoder.filled_colors, decoder.empty_colors, {5: (20, 21)})
    with pytest.raises(StardewAdapterError, match="uniquely establish"):
        ambiguous.recognize(frame)
    frame.putpixel((0, 0), (255, 0, 0))
    with pytest.raises(StardewAdapterError, match="unknown, mixed, or occluded"):
        decoder.recognize(frame)
    frame = Image.new("RGB", (10, 2), "white")
    frame.paste("blue", (5, 0, 10, 2))
    with pytest.raises(StardewAdapterError, match="not contiguous"):
        decoder.recognize(frame)


def test_calibration_retains_source_and_stays_unqualified(tmp_path):
    source = tmp_path / "capture.png"
    Image.new("RGB", (10, 10), "red").save(source)
    root = tmp_path / "calibration"
    region = retain_region_calibration(root, box=(0, 0, 8, 8), samples=((source, "planted_dry"),),
                                      examined_boxes=((0, 0, 4, 4),))
    manifest = json.loads((root / "calibration.json").read_text())
    assert manifest["classification"] == "manual_calibration_unqualified"
    assert manifest["automatic_live_qualified"] is False
    assert manifest["complete_farm_coverage"] is False
    assert manifest["samples"][0]["source_sha256"]
    with Image.open(source) as image:
        assert region.recognize(image) == "planted_dry"
    with pytest.raises(StardewAdapterError, match="already exists"):
        retain_region_calibration(root, box=(0, 0, 8, 8), samples=((source, "watered"),))


def test_camera_alignment_preserves_adjacent_uncertainty_and_rejects_duplicates():
    from smb3_agent.stardew_perception import CameraAlignment
    patch = Image.new('RGB', (9, 9))
    patch.putdata([(x*17, y*19, (x+y)*11) for y in range(9) for x in range(9)])
    patch = patch.resize((27, 27), Image.Resampling.NEAREST)
    alignment = CameraAlignment.calibrate(patch)
    frame = Image.new('RGB', (100, 100), 'black')
    frame.paste(patch, (20, 30))
    offsets = alignment.offsets(frame)
    assert (20, 30) in offsets
    assert len(offsets) > 1  # no fabricated single exact-pixel answer
    frame.paste(patch, (60, 60))
    with pytest.raises(StardewAdapterError, match='ambiguous'):
        alignment.offsets(frame)
    with pytest.raises(StardewAdapterError, match='not recognized'):
        alignment.offsets(Image.new('RGB', (100, 100), 'black'))
