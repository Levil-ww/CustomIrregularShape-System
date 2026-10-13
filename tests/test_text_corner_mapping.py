"""Corner clipping must not shear continuous decoration strokes."""
import numpy as np
import pytest

from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape
from shape_crop.core.sampling import sample_perimeter_strip
from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
from shape_crop.services.layout_analysis import SourceLayout
from shape_crop.services.materials import PreparedMaterial


def stroke_material():
    strip = np.full((60, 180, 3), 240, dtype=np.uint8)
    strip[:16] = (92, 63, 51)
    # Upright narrow strokes stand in for letters on a flat band background.
    for column in range(0, 180, 13):
        strip[23:47, column:column + 4] = (30, 20, 10)
    pixels = np.full((740, 1200, 3), (120, 130, 80), dtype=np.uint8)
    layout = SourceLayout(pixels, strip, 60, 1200, 740, '',
                          pixels[60:680, 60:1140], (60, 60, 1140, 680))
    return PreparedMaterial(pixels, strip, MaterialSpec(), layout)


@pytest.mark.parametrize('mode', ['circular', 'arc'])
@pytest.mark.parametrize('periodic', [False, True])
def test_arc_strokes_keep_one_angular_phase_right_up_to_each_corner(mode, periodic):
    from dataclasses import replace
    material = stroke_material()
    if periodic:
        material = replace(material, source_layout=replace(material.source_layout, strip_period_px=180))
    spec = DesignSpec(diameter_cm=120, height_cm=74, straight_cm=94,
                      shape_mode=mode, border=BorderSpec(0, 0, 0))
    image = np.asarray(render_source(spec, material, max_side=1200))
    shape = create_shape(spec)
    scale = ContentMapping.source_scale(material.source_layout, 120, 74)
    ring = shape.inset(35 * scale)
    yy, xx = np.indices(image.shape[:2])
    x, y = (xx + .5) / 10 - 60, (yy + .5) / 10 - 37
    center = getattr(shape, 'center', 0.)
    theta = np.arctan2(y, np.abs(x) - center)
    radial_depth = shape.radius - np.hypot(np.abs(x) - center, y)
    line_depth = shape.half_height - np.abs(y)
    depths = np.minimum(radial_depth, line_depth)
    arc = 2 * ring.radius * ring.angle
    s = np.where(x >= 0, ring.chord + ring.radius * (theta + ring.angle),
                 2 * ring.chord + arc + ring.radius * (ring.angle - theta))
    near_joint = ((radial_depth < line_depth) & (np.abs(theta) < ring.angle) &
                  (np.abs(theta) > ring.angle - .025) & (depths > 2.4) & (depths < 4.5))
    expected = sample_perimeter_strip(material.strip, s[near_joint],
        depths[near_joint] / scale - .5, ring.perimeter, scale,
        (material.strip.shape[1] - ring.chord / scale) / 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            assert np.any(near_joint & (x * sx > 0) & (y * sy > 0))
    np.testing.assert_allclose(image[near_joint, :3].astype(float), expected, atol=2,
                               err_msg='转角附近同角度的字母笔画被接头补偿拉歪')


@pytest.mark.parametrize('mode', ['circular', 'arc'])
def test_joint_overhang_is_cropped_to_original_band_background(mode):
    material = stroke_material()
    spec = DesignSpec(diameter_cm=120, height_cm=74, straight_cm=94,
                      shape_mode=mode, border=BorderSpec(0, 0, 0))
    image = np.asarray(render_source(spec, material, max_side=1200))
    shape = create_shape(spec)
    ring = shape.inset(3.5)
    yy, xx = np.indices(image.shape[:2])
    x, y = (xx + .5) / 10 - 60, (yy + .5) / 10 - 37
    theta = np.arctan2(y, np.abs(x) - getattr(shape, 'center', 0.))
    radial_depth = shape.radius - np.hypot(np.abs(x) - getattr(shape, 'center', 0.), y)
    line_depth = shape.half_height - np.abs(y)
    on_line = line_depth <= radial_depth
    cropped = np.where(on_line, np.abs(x) > ring.chord / 2, np.abs(theta) > ring.angle)
    depth = np.minimum(radial_depth, line_depth)
    cropped &= (depth > 2.4) & (depth < 4.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            assert np.any(cropped & (sx * x > 0) & (sy * y > 0))
    np.testing.assert_array_equal(image[cropped, :3], 240,
                                  err_msg='接头越界字母必须自然裁去并保留底带原色')


def test_full_circle_has_no_added_corner_blank_and_blocks_do_not_change_output():
    material = stroke_material()
    spec = DesignSpec(diameter_cm=120, height_cm=120, border=BorderSpec(0, 0, 0))
    from shape_crop.core.geometry import clipped_boundary_coordinate
    shape = create_shape(spec)
    angles = np.linspace(-np.pi, np.pi, 1000)
    _, valid = clipped_boundary_coordinate(shape, 57 * np.cos(angles),
                                            57 * np.sin(angles), shape.inset(3.5))
    assert np.all(valid), '完整圆周不能新增转角留白'
    a = np.asarray(render_source(spec, material, max_side=360, block_rows=17))
    b = np.asarray(render_source(spec, material, max_side=360, block_rows=128))
    np.testing.assert_array_equal(a, b)
