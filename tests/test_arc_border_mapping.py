"""Arc frames must use finite side arcs, including inside their circle centres."""
import numpy as np
import pytest

from shape_crop.core.geometry import ArcBand, _compute_depth_and_radial, inset_boundary_fraction
from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.layout_analysis import SourceLayout
from shape_crop.services.materials import PreparedMaterial


@pytest.mark.parametrize('width,height,straight', [
    (112.5, 58, 70.5), (141, 81, 90), (200, 84, 130), (100, 90, 80), (60, 36, 44),
])
def test_straight_frame_coordinates_remain_linear(width, height, straight):
    shape = ArcBand(width, height, straight)
    ring = shape.inset(3)
    x = np.linspace(-straight / 4, straight / 4, 101)
    for sign in (-1, 1):
        y = np.full_like(x, sign * (height / 2 - 3))
        s = inset_boundary_fraction(shape, x, y, np.full_like(x, 3), ring) * ring.perimeter
        # Each centimetre along a straight edge advances exactly one centimetre.
        np.testing.assert_allclose(np.diff(s), -sign * np.diff(x), atol=1e-9,
                                   err_msg='直边中央误采侧弧，导致花边横向拉成长线')


@pytest.mark.parametrize('width,height,straight', [
    (112.5, 58, 70.5), (100, 90, 80), (60, 36, 44), (100, 60, 40),
])
def test_vectorized_arc_depth_matches_finite_arc(width, height, straight):
    shape = ArcBand(width, height, straight)
    x = np.linspace(-width * .55, width * .55, 103)[None, :]
    y = np.linspace(-height * .55, height * .55, 79)[:, None]
    actual, radial = _compute_depth_and_radial(shape, x * x, y)
    np.testing.assert_allclose(actual, shape.depth(x, y), atol=1e-10)
    np.testing.assert_allclose(radial, np.hypot(x, y), atol=1e-10)


def test_straight_mapping_across_300_valid_arc_dimensions():
    random = np.random.default_rng(20261012)
    for _ in range(300):
        width = random.uniform(1, 300)
        height = width * random.uniform(.02, 1)
        sagitta = height / 2 * random.uniform(.001, .999)
        shape = ArcBand(width, height, width - 2 * sagitta)
        depth = height * random.uniform(.001, .20)
        ring = shape.inset(depth)
        # Use the actual parallel contour when a deep inset is clamped.
        depth = shape.half_height - ring.half_height
        x = np.linspace(-ring.chord / 4, ring.chord / 4, 31)
        for sign in (-1, 1):
            y = np.full_like(x, sign * ring.half_height)
            s = inset_boundary_fraction(shape, x, y, np.full_like(x, depth), ring) * ring.perimeter
            np.testing.assert_allclose(np.diff(s), -sign * np.diff(x), atol=1e-8,
                                       err_msg=f'弧形台直边映射不连续：{shape}')


@pytest.mark.parametrize('width,height,straight', [
    (112.5, 58, 70.5), (141, 81, 90), (200, 84, 130), (100, 90, 80),
])
def test_rendered_arc_has_no_missing_dots_in_straight_middle(width, height, straight):
    strip = np.full((48, 24, 3), 240, dtype=np.uint8)
    yy, xx = np.mgrid[:48, :24]
    strip[(xx - 12) ** 2 + (yy - 32) ** 2 <= 6 ** 2] = (255, 0, 0)
    image = np.full((360, 600, 3), 240, dtype=np.uint8)
    layout = SourceLayout(image, strip, 48, 600, 360, '', image[48:-48, 48:-48],
                          (48, 48, 552, 312), 24)
    material = PreparedMaterial(image, strip, MaterialSpec(), layout)
    design = DesignSpec(diameter_cm=width, height_cm=height, dpi=40,
                        border=BorderSpec(0, 0, 0), shape_mode='arc', straight_cm=straight)
    pixels = np.asarray(render_source(design, material, max_side=1200))
    xs = ((np.arange(pixels.shape[1]) + .5) / pixels.shape[1] - .5) * width
    # Project all dots in the top frame onto x. A whole missing central run
    # must fail, even when edge dots and the interior still look correct.
    top = pixels[:pixels.shape[0] // 4, :, :3]
    occupied = np.any((top[..., 0] > 250) & (top[..., 1] < 15), axis=0)
    columns = np.flatnonzero(occupied & (np.abs(xs) < straight / 4))
    assert len(columns) > 0
    assert np.max(np.diff(columns)) * width / pixels.shape[1] < width / 600 * 24 * 1.2, \
        '直边中央出现连续缺失的圆点花边'
