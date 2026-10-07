"""Large repeating interior motifs must not be absorbed into the outer frame."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from shape_crop.models.request import ProductRequest
from shape_crop.services.design_service import generate
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.workflow import resolve_request


def periodic_content_source():
    image = Image.new('RGB', (1200, 740), (0, 0, 0))
    image.paste((235, 214, 177), (24, 24, 1176, 716))
    draw = ImageDraw.Draw(image)
    # Bounded flat gaps enclose each repeating flower, just as in Austin.
    for y in range(32, 716, 60):
        for x in range(32, 1176, 60):
            draw.ellipse((x, y, x + 50, y + 50),
                         outline=(170, 115, 75), width=3)
    return image


@pytest.mark.parametrize('factor', [1, 3])
def test_periodic_artwork_stops_all_four_edge_scans(factor):
    image = periodic_content_source()
    if factor != 1:
        image = image.resize((1200 * factor, 740 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    left, top, right, bottom = layout.content_box_px
    depths = np.array([left, top, image.width - right, image.height - bottom])
    assert np.all(depths >= 24 * factor - 2), '外框不能漏入花纹区'
    # The last complete motif leaves a larger bottom gap; no edge may pass
    # through the first 60px tile and consume subsequent rows of artwork.
    assert np.all(depths <= 60 * factor), '中央重复花纹被误识别为边框'


@pytest.mark.parametrize('preview', [True, False])
def test_austin_order_with_periodic_content_can_generate(tmp_path, preview):
    source = tmp_path / '双面格-定制-定制尺寸-奥斯汀;80X130CM.jpg'
    periodic_content_source().save(source, quality=95)
    design, _ = resolve_request(ProductRequest(
        '双面格-定制-裁剪有图-奥斯汀;80x130CM裁剪有图',
        library_dir=str(tmp_path), shape_mode='arc', straight_cm=103, dpi=12))
    image = generate(design, preview=preview)
    assert image.size == design.pixel_size(1200 if preview else None)
    assert image.getpixel((image.width // 2, image.height // 2))[3] == 255
