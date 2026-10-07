"""Periodic dots touching artwork must remain part of the complete frame."""
import numpy as np
import pytest
from PIL import Image

from shape_crop.core.geometry import create_shape
from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial


def touching_dot_source():
    rng = np.random.default_rng(54)
    pixels = rng.integers(100, 235, (240, 400, 3), dtype=np.uint8)
    pixels[:6] = 0
    pixels[6:13] = (170, 125, 85)
    pixels[-13:] = pixels[:13][::-1]
    pixels[:, :6] = 0
    pixels[:, -6:] = 0
    pixels[6:-6, 6:13] = (170, 125, 85)
    pixels[6:-6, -13:-6] = (170, 125, 85)
    yy, xx = np.mgrid[:240, :400]
    # The ornament runs directly into non-periodic artwork, without a flat separator.
    for centre in range(18, 386, 10):
        pixels[(xx - centre) ** 2 + (yy - 15) ** 2 <= 3 ** 2] = 0
        pixels[(xx - centre) ** 2 + (yy - 224) ** 2 <= 3 ** 2] = 0
    for centre in range(18, 226, 10):
        pixels[(xx - 15) ** 2 + (yy - centre) ** 2 <= 3 ** 2] = 0
        pixels[(xx - 384) ** 2 + (yy - centre) ** 2 <= 3 ** 2] = 0
    return Image.fromarray(pixels)


def test_dots_touching_artwork_are_not_left_in_content():
    layout = analyze_layout(touching_dot_source())
    left, top, right, bottom = layout.content_box_px
    assert 19 <= top <= 21, '边框识别停在圆点起始处，截断装饰带'
    assert left >= 19 and right <= 381 and bottom <= 221
    assert layout.strip_period_px == 10
    assert np.any(np.max(layout.strip[14:18], axis=2) < 20)


def test_continuous_dark_artwork_is_not_extended_into_frame():
    from shape_crop.services.layout_analysis import boundary_depth
    pixels = np.full((240, 400, 3), 210, dtype=np.uint8)
    pixels[:6] = 0
    pixels[6:13] = (170, 125, 85)
    # A periodic dark fill continues indefinitely instead of ending like an ornament.
    pixels[13:, np.arange(400) % 10 < 5] = 0
    assert boundary_depth(pixels) == 13


@pytest.mark.parametrize('shape_mode', ['arc', 'circular'])
def test_side_arcs_keep_black_dots_touching_artwork(shape_mode):
    layout = analyze_layout(touching_dot_source())
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
    design = DesignSpec(diameter_cm=39, height_cm=25, dpi=80,
                        border=BorderSpec(0, 0, 0), shape_mode=shape_mode,
                        straight_cm=30 if shape_mode == 'arc' else 0)
    pixels = np.asarray(render_source(design, material))
    shape = create_shape(design)
    depth = 15 * 25 / 240
    ys = np.linspace(-6, 6, 300)
    centre = getattr(shape, 'center', 0.)
    xs = centre + np.sqrt((shape.radius - depth) ** 2 - ys ** 2)
    rows = np.rint((ys / 25 + .5) * pixels.shape[0] - .5).astype(int)
    for sign in (-1, 1):
        columns = np.rint((sign * xs / 39 + .5) * pixels.shape[1] - .5).astype(int)
        black = np.max(pixels[rows, columns, :3], axis=1) < 40
        assert black.sum() > 50, '左右侧弧未显示完整黑色圆点装饰带'
