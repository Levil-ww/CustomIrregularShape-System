"""Closed pale outlines around a plain centre follow the whole target contour."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from shape_crop.core.geometry import create_shape
from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
from shape_crop.services.layout_analysis import analyze_layout, _nested_pale_frame
from shape_crop.services.materials import PreparedMaterial


BACKGROUND = (248, 244, 232)
PALE = (222, 204, 177)


def nested_source(factor=1, damage=None):
    image = Image.new('RGB', (600, 400), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 599, 399), outline='black')
    for depth in (24, 40):
        draw.rounded_rectangle((depth, depth, 599-depth, 399-depth), radius=8,
                               outline='black', width=3)
    for depth in range(54, 95, 10):
        draw.rectangle((depth, depth, 599-depth, 399-depth), outline=PALE)
    if damage == 'artwork':
        draw.ellipse((270, 170, 330, 230), fill=(60, 90, 40))
    elif damage == 'broken':
        draw.rectangle((90, 140, 98, 260), fill=BACKGROUND)
    return image.resize((600*factor, 400*factor), Image.Resampling.NEAREST)


@pytest.mark.parametrize('factor', [1, 5])
@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_all_nested_pale_outlines_follow_target_contour(factor, mode):
    layout = analyze_layout(nested_source(factor))
    assert 94*factor <= layout.border_depth_px <= 97*factor, '浅色内线被遗留在矩形内容区'
    np.testing.assert_array_equal(layout.content.min(axis=(0, 1)), BACKGROUND)
    design = DesignSpec(diameter_cm=134, height_cm=81, straight_cm=103,
                        shape_mode=mode, border=BorderSpec(0, 0, 0))
    pixels = np.asarray(render_source(design,
        PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout), max_side=1200))
    y, x = np.indices(pixels.shape[:2], dtype=float)
    x = ((x+.5)/pixels.shape[1]-.5)*134
    y = ((y+.5)/pixels.shape[0]-.5)*81
    # The five lines must have constant physical distance from the new edge,
    # including the curved sides rather than surviving at old rectangle x's.
    distance = create_shape(design).depth(x, y)
    scale = 134/600
    is_pale = np.max(np.abs(pixels[..., :3].astype(float)-PALE), axis=2) < 12
    for depth in range(54, 95, 10):
        band = is_pale & (np.abs(distance-(depth+.5)*scale) < .4)
        assert np.count_nonzero(band & (np.abs(x) > 40)) > 10, '浅色线没有沿两侧弧线绘制'
    inner = distance > 97*scale
    np.testing.assert_allclose(pixels[..., :3][inner], np.broadcast_to(BACKGROUND, pixels[..., :3][inner].shape), atol=1)


@pytest.mark.parametrize('damage', ['artwork', 'broken'])
def test_nonempty_or_incomplete_nested_frames_keep_normal_analysis(damage):
    pixels = np.asarray(nested_source(damage=damage))
    assert _nested_pale_frame(pixels, (43, 43, 557, 357)) is None, '不能把中央图案或未闭合线条当成完整边框'


def test_nested_pale_frame_preserves_outer_periodic_ornaments():
    image = nested_source()
    draw = ImageDraw.Draw(image)
    for x in range(60, 540, 20):
        draw.rectangle((x, 6, x+4, 15), fill='black')
    layout = analyze_layout(image)
    assert layout.border_depth_px >= 94
    assert layout.strip_period_px == 20, '内侧浅框不能使外侧周期装饰被压成纯色'
    assert layout.strip[10].min() == 0
    assert layout.strip[10].max() >= 232


def test_nested_frame_tolerates_outer_stroke_refinement_by_one_pixel():
    pixels = np.asarray(nested_source())
    assert _nested_pale_frame(pixels, (42, 42, 558, 358)) == (95, 95, 505, 305)
