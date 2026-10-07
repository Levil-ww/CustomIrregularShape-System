"""Keep broad periodic beads and their flat inner margin in the source frame."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout


def beaded_source():
    image = Image.new('RGB', (1600, 1000), 'black')
    image.paste((242, 241, 236), (50, 50, 1550, 950))
    draw = ImageDraw.Draw(image)
    for x in range(118, 1500, 34):
        for y in (50, 949):
            draw.ellipse((x - 17, y - 17, x + 17, y + 17),
                         fill=(242, 241, 236), outline='black', width=3)
    for y in range(118, 900, 34):
        for x in (50, 1549):
            draw.ellipse((x - 17, y - 17, x + 17, y + 17),
                         fill=(242, 241, 236), outline='black', width=3)
    pixels = np.asarray(image).copy()
    pixels[110:890, 110:1490] = np.random.default_rng(17).integers(
        0, 256, (780, 1380, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


@pytest.mark.parametrize('factor', [1, 3])
def test_beads_and_inner_margin_survive_edge_analysis(factor):
    image = beaded_source()
    if factor != 1:
        image = image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    assert layout.border_depth_px >= 108 * factor, '圆珠与浅色留白被误判为中央花纹'
    assert layout.strip_period_px > 0, '圆珠边框必须提取完整重复周期'
    assert np.median(layout.strip[80 * factor]) > 230, '浅色内边框层丢失'
