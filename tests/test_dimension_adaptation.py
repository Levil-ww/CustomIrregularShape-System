"""General size regressions: source vertical borders and repeat seams must not leak."""
from dataclasses import replace
import numpy as np
import pytest
from PIL import Image
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.design_service import generate
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.core.sampling import sample_perimeter_strip
from shape_crop.core.geometry import CircularBand
from shape_crop.core.content_mapping import ContentMapping


def framed_source(wide_sides=True, height=240):
    source = np.full((height, 400, 3), [245, 230, 195], dtype=np.uint8)
    source[:2] = 0
    source[20:24] = [160, 135, 100]
    for x in range(0, 400, 12):
        source[24:32, x:x + 5] = [70, 45, 20]
    source[32:34] = [160, 135, 100]
    source[34:37] = [250, 235, 205]
    side = 90 if wide_sides else 37
    source[37:height-37, side:400-side] = np.random.default_rng(5).integers(45, 120, (height-74, 400-2*side, 3), dtype=np.uint8)
    source[-37:] = source[:37][::-1]
    # The source's vertical frame is deeper than the top frame. Never copy its corner
    # fragments into a repeating horizontal ornament, or its lines into the content.
    source[2:height-2, :side] = [245, 230, 195]
    source[2:height-2, 400-side:] = [245, 230, 195]
    source[:, :2] = 0
    source[:, -2:] = 0
    source[-2:] = 0
    return Image.fromarray(source)


def test_horizontal_repeat_excludes_source_vertical_frame():
    layout = analyze_layout(framed_source())
    row = layout.strip[27]
    dark = row[:, 0] < 100
    # A natural period has at most seven background columns, not tens of corner columns.
    positions = np.flatnonzero(dark)
    assert positions.size >= 5
    gaps = np.diff(np.r_[positions[-1] - len(row), positions, positions[0] + len(row)])
    assert gaps.max() <= 8, '条带带入竖向边框，重复时形成遮挡圆点的背景线'


@pytest.mark.parametrize('diameter,height', [(166.3, 86), (141, 81), (200, 83.76), (100, 100),
                                           (20, 20), (93.73, 42.19)])
def test_content_has_no_vertical_source_frame_at_multiple_sizes(tmp_path, diameter, height):
    path = tmp_path / 'framed.png'
    source_height = max(240, int(np.ceil(height / diameter * 400)))
    framed_source(False, source_height).save(path)
    spec = replace(DesignSpec(), diameter_cm=diameter, height_cm=height, dpi=15,
                   border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    image = np.asarray(generate(spec))
    row = image[image.shape[0] // 2, :, :3]
    scale = diameter / 400
    # Sample well inside the contour's content region, near the left inner edge.
    x_cm = -diameter / 2 + 50 * scale
    column = round((x_cm / diameter + .5) * image.shape[1] - .5)
    assert row[column, 0] < 160, '中央花纹采到了原矩形竖边，形成米黄色竖线'


def test_insufficient_clean_content_is_rejected_instead_of_mirrored(tmp_path):
    layout = analyze_layout(framed_source())
    with pytest.raises(ValueError, match='不会镜像'):
        ContentMapping.create(layout, 40, 24, 3.7)


def test_unequal_source_edges_share_frame_scale_without_flower_mirroring(tmp_path):
    path = tmp_path / 'unequal-edges.png'
    source = framed_source()
    source.save(path)
    spec = replace(DesignSpec(), diameter_cm=40, height_cm=24, dpi=25,
                   border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    result = np.asarray(generate(spec))
    h, w = result.shape[:2]
    xs = ((np.arange(w) + .5) / w - .5) * 40
    ys = ((np.arange(h) + .5) / h - .5) * 24
    from shape_crop.core.sampling import sample
    expected = sample(np.asarray(source), xs[None, :] / .1 + 199.5,
                      ys[:, None] / .1 + 119.5)
    interior = CircularBand(40, 24).depth(xs[None, :], ys[:, None]) > 9 + 2 * 40 / w
    assert interior.any()
    np.testing.assert_allclose(result[..., :3][interior], expected[interior], atol=1)


@pytest.mark.parametrize('diameter,height', [(300, 25), (50, 5)])
def test_border_wider_than_target_is_rejected(tmp_path, diameter, height):
    path = tmp_path / 'thick-frame.png'
    framed_source(False).save(path)
    spec = replace(DesignSpec(), diameter_cm=diameter, height_cm=height, dpi=15,
                   border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    with pytest.raises(ValueError, match='边框过宽'):
        generate(spec)


@pytest.mark.parametrize('diameter,height', [(166.3, 86), (141, 81), (200, 83.76), (100, 100), (300, 25)])
def test_period_phase_closes_for_arbitrary_sizes(diameter, height):
    layout = analyze_layout(framed_source())
    perimeter = CircularBand(diameter, height).perimeter
    scale = min(diameter / 400, height / 240)
    s = np.array([0, perimeter, -.001, perimeter - .001])
    pixels = sample_perimeter_strip(layout.strip, s, 27., perimeter, scale)
    np.testing.assert_array_equal(pixels[0], pixels[1])
    np.testing.assert_allclose(pixels[2], pixels[3], atol=1)
