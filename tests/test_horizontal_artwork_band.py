"""Horizontal artwork separators must stay straight inside the shaped frame."""
import numpy as np
import pytest
from PIL import Image
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.design_service import generate
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec


def band_source():
    image = Image.new('RGB', (650, 400), (245, 235, 227))
    image.paste('black', (14, 14, 636, 386))
    image.paste((245, 235, 227), (17, 17, 633, 383))
    image.paste('black', (24, 24, 626, 376))
    image.paste((245, 235, 227), (27, 27, 623, 373))
    pixels = np.asarray(image).copy()
    pixels[116:119, 27:623] = 0
    pixels[119:281, 27:623] = np.random.default_rng(37).integers(
        60, 225, (162, 596, 3), dtype=np.uint8)
    pixels[281:284, 27:623] = 0
    return Image.fromarray(pixels)


@pytest.mark.parametrize('factor', [1, 5])
def test_horizontal_artwork_separator_is_excluded_from_perimeter_strip(factor):
    image = band_source()
    if factor > 1:
        image = image.resize((650 * factor, 400 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    assert 25 * factor <= layout.border_depth_px <= 29 * factor, '花纹带的水平线被卷入环形边框'
    assert layout.content_box_px[3] >= 371 * factor, '下方水平线被卷入环形边框'


def test_arc_keeps_artwork_band_full_width_and_separator_horizontal(tmp_path):
    path = tmp_path / 'band.png'
    band_source().save(path)
    spec = DesignSpec(diameter_cm=151, height_cm=91, dpi=20,
                      shape_mode='arc', straight_cm=120.5,
                      border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    result = np.asarray(generate(spec))
    scale = 151 / 650
    row = round(((117.5 - 200) * scale / 91 + .5) * result.shape[0] - .5)
    columns = np.array([.10, .25, .50, .75, .90]) * result.shape[1]
    assert np.all(np.max(result[row, columns.astype(int), :3], axis=1) < 40), '花纹带分隔线没有完整水平延伸到两侧'
