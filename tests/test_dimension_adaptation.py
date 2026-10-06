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


def framed_source():
    source = np.full((240, 400, 3), [245, 230, 195], dtype=np.uint8)
    source[:2] = 0
    source[20:24] = [160, 135, 100]
    for x in range(0, 400, 12):
        source[24:32, x:x + 5] = [70, 45, 20]
    source[32:34] = [160, 135, 100]
    source[34:37] = [250, 235, 205]
    source[37:203, 90:310] = np.random.default_rng(5).integers(45, 120, (166, 220, 3), dtype=np.uint8)
    # The source's vertical frame is deeper than the top frame. Never copy its corner
    # fragments into a repeating horizontal ornament, or its lines into the content.
    source[2:238, :90] = [245, 230, 195]
    source[2:238, 310:] = [245, 230, 195]
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
                                           (300, 25), (50, 5), (20, 20), (93.73, 42.19)])
def test_content_has_no_vertical_source_frame_at_multiple_sizes(tmp_path, diameter, height):
    path = tmp_path / 'framed.png'
    framed_source().save(path)
    spec = replace(DesignSpec(), diameter_cm=diameter, height_cm=height, dpi=15,
                   border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    image = np.asarray(generate(spec))
    row = image[image.shape[0] // 2, :, :3]
    scale = max(diameter / 400, height / 240)
    # Sample well inside the contour's content region, near the left inner edge.
    x_cm = -diameter / 2 + 50 * scale
    column = round((x_cm / diameter + .5) * image.shape[1] - .5)
    assert row[column, 0] < 160, '中央花纹采到了原矩形竖边，形成米黄色竖线'


@pytest.mark.parametrize('diameter,height', [(166.3, 86), (141, 81), (200, 83.76), (100, 100), (300, 25)])
def test_period_phase_closes_for_arbitrary_sizes(diameter, height):
    layout = analyze_layout(framed_source())
    perimeter = CircularBand(diameter, height).perimeter
    scale = min(diameter / 400, height / 240)
    s = np.array([0, perimeter, -.001, perimeter - .001])
    pixels = sample_perimeter_strip(layout.strip, s, 27., perimeter, scale)
    np.testing.assert_array_equal(pixels[0], pixels[1])
    np.testing.assert_allclose(pixels[2], pixels[3], atol=1)
