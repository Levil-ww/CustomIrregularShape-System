"""Preserve enamel ornaments and curve the central panel."""
import numpy as np
import pytest
from pathlib import Path
from PIL import Image, ImageDraw
from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
from shape_crop.services.materials import prepare
from shape_crop.core.source_renderer import render_source


def enamel_source():
    image = Image.new('RGB', (1200, 800), (52, 70, 40))
    tile = Image.open(Path(__file__).parent / 'fixtures' / 'enamel_ornament.png').convert('RGB')
    for y in range(0, 800, tile.height):
        for x in range(0, 1200, tile.width):
            image.paste(tile, (x, y))
    draw = ImageDraw.Draw(image)
    draw.rectangle((150, 150, 1050, 650), fill=(239, 227, 203))
    draw.rectangle((0, 0, 1199, 799), outline='black', width=10)
    return image


@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_enamel_keeps_ornaments_and_curves_panel(tmp_path, mode, monkeypatch):
    from dataclasses import replace
    from shape_crop.services import materials
    from shape_crop.services.framed_artwork import FramedArtwork
    analyze = materials.analyze_layout
    def with_known_outer_frame(image, **kwargs):
        layout = analyze(image, **kwargs)
        frame = (10, 10, 1190, 790)
        artwork = FramedArtwork((150, 150, 1051, 651), frame,
                                np.asarray(image)[20:30, 20:30].copy(), (20, 20))
        return replace(layout, content_box_px=frame, framed_artwork=artwork)
    monkeypatch.setattr(materials, 'analyze_layout', with_known_outer_frame)
    path = tmp_path / '岁月珐琅;80x120.jpg'
    enamel_source().save(path, quality=94)
    material = prepare(MaterialSpec(str(path)), preview=True)
    layout = material.source_layout
    assert layout.contoured_frame is not None
    tile = layout.framed_artwork.tile
    assert tile.shape[1] > 100 and tile.shape[0] > 40, '背景必须包含完整的花纹周期'
    assert np.mean(np.max(tile, axis=2) > 150) < .005, '背景周期不能混入中央浅色区'
    design = DesignSpec(diameter_cm=121, height_cm=81, straight_cm=103,
                        shape_mode=mode, border=BorderSpec(0, 0, 0))
    pixels = np.asarray(render_source(design, material, max_side=900))
    from shape_crop.core.geometry import create_shape
    from shape_crop.core.content_mapping import ContentMapping
    inner = create_shape(design).inset(layout.contoured_frame.inset_px *
                                      ContentMapping.source_scale(layout, 121, 81))
    for y in (-15, 0, 15):
        side = getattr(inner, 'center', 0) + np.sqrt(inner.radius**2-y**2)
        row = round((y/81+.5)*pixels.shape[0]-.5)
        for sign in (-1, 1):
            inside = round((sign*(side-1)/121+.5)*pixels.shape[1]-.5)
            outside = round((sign*(side+1)/121+.5)*pixels.shape[1]-.5)
            assert pixels[row, inside, 1] > 180
            assert pixels[row, outside, 1] < 100


def test_enamel_adaptation_does_not_change_other_patterns(tmp_path):
    path = tmp_path / '其他花型;80x120.png'
    enamel_source().save(path)
    assert prepare(MaterialSpec(str(path)), preview=True).source_layout.contoured_frame is None
