"""Blank space around centred illustrations belongs to the artwork, not the frame."""
import numpy as np
import pytest
from PIL import Image
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.design_service import generate
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec


def gallery_source():
    image = Image.new('RGB', (650, 400), (245, 239, 229))
    image.paste((0, 0, 0), (0, 0, 650, 2))
    image.paste((170, 130, 70), (14, 14, 636, 386))
    image.paste((245, 239, 229), (17, 17, 633, 383))
    for left, colour in [(130, (30, 90, 40)), (270, (180, 100, 40)), (410, (30, 40, 90))]:
        image.paste(colour, (left, 138, left + 110, 262))
    return image


@pytest.mark.parametrize('factor', [1, 5])
def test_blank_margin_after_thin_outline_is_not_a_wide_frame(factor):
    image = gallery_source()
    if factor > 1:
        image = image.resize((650 * factor, 400 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    left, top, right, bottom = layout.content_box_px
    depths = np.array([left, top, image.width - right, image.height - bottom])
    assert np.all(depths <= 20 * factor), '中央画框四周留白被误识别为外边框'
    assert np.all(depths >= 17 * factor - 2), '原素材细外框不能漏入花纹区'


def test_arc_keeps_all_three_centred_pictures_complete(tmp_path):
    path = tmp_path / 'gallery.png'
    gallery_source().save(path)
    design = DesignSpec(diameter_cm=131, height_cm=81, dpi=20,
                        shape_mode='arc', straight_cm=103,
                        border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    result = np.asarray(generate(design))
    for colour in [(30, 90, 40), (180, 100, 40), (30, 40, 90)]:
        selected = np.max(np.abs(result[..., :3].astype(int) - colour), axis=2) <= 2
        rows, columns = np.nonzero(selected)
        assert selected.sum() > .97 * (columns.max() - columns.min() + 1) * (rows.max() - rows.min() + 1), '左右画框被弧形边框覆盖'
        width_cm = (columns.max() - columns.min() + 1) / result.shape[1] * 131
        assert abs(width_cm - 110 * 81 / 400) < .4, '完整图案应保持原素材等比尺寸'
