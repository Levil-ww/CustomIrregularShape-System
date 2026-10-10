"""A nonperiodic textured frame inside periodic ticks must survive arc cropping."""
import numpy as np
import pytest
from PIL import Image
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.core.source_renderer import render_source
from shape_crop.core.geometry import create_shape
from shape_crop.core.content_mapping import ContentMapping


def layered_source(closed=True):
    yy, xx = np.mgrid[:480, :800]
    depth = np.minimum.reduce((yy, xx, 479-yy, 799-xx))
    p = np.full((480, 800, 3), (205, 190, 165), dtype=np.uint8)
    noise = np.random.default_rng(14).random((160, 267)) < .15
    mask = np.repeat(np.repeat(noise, 3, axis=0), 3, axis=1)[:, :800]
    p[mask] = (145, 143, 95)
    p[depth < 18] = (8, 3, 1)
    p[(depth >= 18) & (depth < 26) & ((xx//8 + yy//8) % 2 == 0)] = 0
    p[depth >= 80] = (102, 108, 56)
    p[depth >= 92] = (90, 98, 45)
    p[(depth >= 88) & (depth < 91)] = (220, 204, 178)
    if not closed:
        p[160:320, 88:91] = (102, 108, 56)
    return Image.fromarray(p)


@pytest.mark.parametrize('factor', [1, 3, 6])
def test_complete_inner_separator_retains_every_frame_layer(factor):
    image = layered_source().resize((800*factor, 480*factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    left, top, right, bottom = layout.content_box_px
    depths = np.array([left, top, image.width-right, image.height-bottom])/factor
    assert np.all(np.abs(depths-91) < 3), '米色织纹、绿色细边和内侧白线必须完整保留'


@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_textured_inner_band_and_separator_survive_side_arc(mode):
    layout = analyze_layout(layered_source())
    m = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
    spec = DesignSpec(diameter_cm=139, height_cm=87, straight_cm=108,
                      shape_mode=mode, border=BorderSpec(0, 0, 0))
    result = np.asarray(render_source(spec, m, max_side=1400))
    shape = create_shape(spec)
    scale = ContentMapping.source_scale(layout,139,87)
    y = np.linspace(-15,15,180)
    for source_depth, minimum in ((50,.6),(89,.9)):
        radius = shape.radius - source_depth*scale
        x = getattr(shape,'center',0.) + np.sqrt(radius**2-y**2)
        rows = np.rint((y/87+.5)*result.shape[0]-.5).astype(int)
        cols = np.rint((x/139+.5)*result.shape[1]-.5).astype(int)
        colour = result[rows,cols,:3]
        assert np.mean(np.min(colour,axis=1)>150) > minimum, '侧弧内层织纹或闭合细线被裁掉'


def test_broken_inner_separator_does_not_expand_frame():
    layout = analyze_layout(layered_source(closed=False))
    assert layout.layered_strip is None
    assert layout.border_depth_px < 40


def test_nonperiodic_inner_texture_keeps_full_horizontal_span():
    layout = analyze_layout(layered_source())
    outer, strip = layout.layered_strip
    assert strip.shape[1] > layout.strip_period_px * 10
    assert outer < layout.border_depth_px
    assert not np.array_equal(strip[40:70, :32], strip[40:70, 32:64])


def test_inner_circle_samples_complete_textured_frame():
    layout = analyze_layout(layered_source())
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
    spec = DesignSpec(diameter_cm=139, height_cm=87, straight_cm=108,
                      inner_diameter_cm=40, border=BorderSpec(0, 0, 0))
    result = np.asarray(render_source(spec, material, max_side=1400))
    assert result.shape[1] == 1400
    scale = ContentMapping.source_scale(layout, 139, 87)
    x = 20 - 89 * scale
    row = result.shape[0] // 2
    col = round((x / 139 + .5) * result.shape[1] - .5)
    assert np.min(result[row, col, :3]) > 150


def test_cached_full_texture_is_readonly(tmp_path):
    from shape_crop.services.materials import prepare
    path = tmp_path / 'layered.jpg'
    layered_source().save(path, quality=100, subsampling=0)
    material = prepare(MaterialSpec(path=str(path)), preview=True)
    assert material.source_layout.layered_strip is not None
    assert not material.source_layout.layered_strip[1].flags.writeable


def test_inner_texture_cannot_change_outer_tick_period():
    image = layered_source()
    pixels = np.array(image)
    yy, xx = np.mgrid[:480, :800]
    depth = np.minimum.reduce((yy, xx, 479-yy, 799-xx))
    noise = np.random.default_rng(3).random((480, 800)) < .03
    pixels[noise & (depth >= 35) & (depth < 75)] = 0
    layout = analyze_layout(Image.fromarray(pixels))
    assert layout.layered_strip is not None
    assert layout.strip_period_px == analyze_layout(image).strip_period_px
