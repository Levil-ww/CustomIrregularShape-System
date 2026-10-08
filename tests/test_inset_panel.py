"""Translucent rectangular panels adapt to the outline without losing clearance."""
import numpy as np
from PIL import Image, ImageDraw
import pytest
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.core.source_renderer import render_source
from shape_crop.core.geometry import create_shape
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec


def panel_source():
    pixels = np.full((360, 600, 3), (242, 237, 217), dtype=np.uint8)
    for y in range(10, 350, 20):
        for x in range(10, 590, 20):
            pixels[y:y + 8, x:x + 8] = 0
    pixels[72:288, 72:528] = np.round(pixels[72:288, 72:528] * .12 + np.array([242, 237, 217]) * .88)
    image = Image.fromarray(pixels)
    ImageDraw.Draw(image).rectangle((84, 84, 515, 275), outline=(20, 20, 18), width=1)
    return image


@pytest.mark.parametrize('factor', [1, 4])
def test_translucent_panel_is_recognized_separately_from_outer_frame(factor):
    image = panel_source().resize((600 * factor, 360 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    assert layout.inset_panel is not None, '中央半透明矩形框应单独识别以适配轮廓'
    np.testing.assert_allclose(np.array(layout.inset_panel.box) / factor, (84, 84, 515, 275), atol=2)


@pytest.mark.parametrize('width,height,straight', [(139, 87, 108), (105, 66.5, 82)])
@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_panel_side_follows_arc_and_preserves_clearance_fraction(width, height, straight, mode):
    layout = analyze_layout(panel_source())
    design = DesignSpec(diameter_cm=width, height_cm=height, straight_cm=straight,
                        shape_mode=mode, border=BorderSpec(0, 0, 0))
    shape = create_shape(design)
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(''), layout)
    result = np.asarray(render_source(design, material, max_side=1800))
    left, top, right, bottom = layout.inset_panel.box
    fraction = (top + layout.height_px - bottom) / 2 / layout.height_px
    inner = shape.inset(fraction * height)
    h, w = result.shape[:2]
    # Check points at the side centre and near the top: a rectangle would have
    # a constant side x. Sample the actual rendered thin line, not a formula.
    for y in (0., inner.half_height * .8):
        x = getattr(inner, 'center', 0.) + np.sqrt(inner.radius**2 - y**2)
        column = round((x / width + .5) * w - .5)
        row = round((y / height + .5) * h - .5)
        assert np.min(np.max(result[row - 1:row + 2, column - 2:column + 3, :3], axis=2)) < 90, '内框侧边未跟随圆弧'
    column = w // 2
    top_row = round((fraction * height / height) * h - .5)
    assert np.min(np.max(result[top_row - 2:top_row + 3, column - 1:column + 2, :3], axis=2)) < 90, '内框与外边框间距比例改变'


def test_plain_rectangular_artwork_does_not_trigger_panel_adaptation():
    image = panel_source()
    pixels = np.asarray(image).copy()
    pixels[85:275, 85:515] = (242, 237, 217)
    assert analyze_layout(Image.fromarray(pixels)).inset_panel is None
