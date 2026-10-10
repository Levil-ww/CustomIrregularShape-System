"""Outlined round ornaments stay whole where straight edges meet side arcs."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec
from shape_crop.services.layout_analysis import SourceLayout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.core.source_renderer import render_source
from shape_crop.core.geometry import create_shape
from shape_crop.core.content_mapping import ContentMapping


def ring_material():
    strip = Image.new('RGB', (28, 88), (250, 232, 217))
    draw = ImageDraw.Draw(strip)
    draw.rectangle((0, 0, 27, 29), fill='black')
    draw.ellipse((2, 56, 26, 80), outline=(35, 30, 25), width=2)
    pixels = np.full((740, 1200, 3), (139, 96, 66), dtype=np.uint8)
    layout = SourceLayout(pixels, np.asarray(strip), 88, 1200, 740, '',
                          pixels[88:652, 88:1112], (88, 88, 1112, 652), 28)
    return PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)


@pytest.mark.parametrize('mode', ['arc', 'circular'])
@pytest.mark.parametrize('dimensions', [(139, 87, 108), (151, 91, 120.5), (131, 81, 103)])
def test_four_joints_have_complete_round_ornaments(mode, dimensions):
    material = ring_material()
    w, h, chord = dimensions
    spec = DesignSpec(diameter_cm=w, height_cm=h, straight_cm=chord,
                      shape_mode=mode, border=BorderSpec(0, 0, 0))
    layout = material.source_layout
    scale = ContentMapping.source_scale(layout, w, h)
    weights = np.max(np.ptp(layout.strip, axis=1), axis=1)
    source_depth = np.average(np.arange(len(weights)) + .5, weights=weights)
    shape = create_shape(spec).inset(source_depth * scale)
    image = np.asarray(render_source(spec, material, max_side=1800))
    px = w / image.shape[1]
    radius = 12 * scale / px
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx = (sx * shape.chord / 2 / w + .5) * image.shape[1] - .5
            cy = (sy * shape.half_height / h + .5) * image.shape[0] - .5
            a, b = int(cx - radius - 3), int(cy - radius - 3)
            patch = image[b:int(cy + radius + 4), a:int(cx + radius + 4), :3]
            yy, xx = np.indices(patch.shape[:2])
            distance = np.hypot(xx + a - cx, yy + b - cy)
            ink = (np.max(patch, axis=2) < 110) & (distance <= radius + 3)
            assert ink.sum() > radius * 3, '转角圆环缺失'
            assert np.mean(np.abs(distance[ink] - radius) < 3) > .90, '转角圆环被切开或变形'


def test_non_round_ornaments_keep_existing_mapping():
    from shape_crop.core.round_rings import recognize_round_ring
    for kind in ('filled', 'square', 'broken'):
        strip = Image.new('RGB', (28, 88), (250, 232, 217))
        draw = ImageDraw.Draw(strip)
        if kind == 'filled':
            draw.ellipse((2, 56, 26, 80), fill='black')
        elif kind == 'square':
            draw.rectangle((2, 56, 26, 80), outline='black', width=2)
        else:
            draw.arc((2, 56, 26, 80), 20, 330, fill='black', width=2)
        assert recognize_round_ring(np.asarray(strip)) is None, kind


@pytest.mark.parametrize('kind', ['small_gap', 'alternate_colour', 'alternate_width'])
def test_open_or_alternating_ring_patterns_keep_source_layout(kind):
    from shape_crop.core.round_rings import recognize_round_ring
    strip = Image.new('RGB', (28 if kind == 'small_gap' else 56, 88), (250, 232, 217))
    draw = ImageDraw.Draw(strip)
    if kind == 'small_gap':
        draw.arc((2, 56, 26, 80), 0, 350, fill='black', width=2)
    else:
        draw.ellipse((2, 56, 26, 80), outline='black',
                     width=1 if kind == 'alternate_width' else 2)
        draw.ellipse((30, 56, 54, 80),
                     outline='black' if kind == 'alternate_width' else (180, 30, 20), width=2)
    assert recognize_round_ring(np.asarray(strip)) is None


@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_tiny_straight_segment_preserves_existing_mapping(monkeypatch, mode):
    import shape_crop.core.source_renderer as renderer
    material = ring_material()
    spec = DesignSpec(diameter_cm=100, height_cm=99.99, straight_cm=.05,
                      shape_mode=mode, border=BorderSpec(0, 0, 0))
    actual = np.asarray(renderer.render_source(spec, material, max_side=900))
    monkeypatch.setattr(renderer, 'recognize_round_ring', lambda strip: None)
    original = np.asarray(renderer.render_source(spec, material, max_side=900))
    assert np.array_equal(actual, original), '不足容纳完整相邻圆的短直边保留原排版'
