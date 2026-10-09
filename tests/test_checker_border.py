"""Opposite checker rows must retain their full period and all frame layers."""
from io import BytesIO
import numpy as np
import pytest
from PIL import Image
from shape_crop.services.texture_period import extract_period
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec


def checker_source():
    yy, xx = np.mgrid[:400, :600]
    depth = np.minimum.reduce((xx, 599-xx, yy, 399-yy))
    pixels = np.zeros((400, 600, 3), dtype=np.uint8)
    pixels[depth >= 12] = (245, 230, 195)
    checker = (depth >= 18) & (depth < 46)
    dark = ((xx-18)//14 + (yy-18)//14) % 2 == 0
    pixels[checker & dark] = 0
    pixels[52:348, 52:548] = np.random.default_rng(42).integers(65, 190, (296, 496, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


@pytest.mark.parametrize('jpeg', [False, True])
def test_opposite_checker_rows_do_not_cancel_period(jpeg):
    yy, xx = np.mgrid[:28, :560]
    pixels = np.repeat(np.where((xx//14 + yy//14) % 2 == 0, 0, 240)[...,None], 3, axis=2).astype(np.uint8)
    image = Image.fromarray(pixels)
    if jpeg:
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=95)
        image = Image.open(buffer).convert('RGB')
    _, period = extract_period(np.asarray(image))
    assert period == 28, '两行反相棋盘格的平均信号不能抵消真实周期'


@pytest.mark.parametrize('factor', [1, 4])
@pytest.mark.parametrize('jpeg', [False, True])
def test_checker_frame_is_completely_excluded_from_flower_content(factor, jpeg):
    image = checker_source().resize((600*factor, 400*factor), Image.Resampling.NEAREST)
    if jpeg:
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=95)
        image = Image.open(buffer).convert('RGB')
    layout = analyze_layout(image)
    left, top, right, bottom = layout.content_box_px
    assert np.all(np.abs(np.array([left, top, image.width-right, image.height-bottom])/factor - 52) <= 2), '棋盘格和内侧留白必须完整计入外框'
    assert layout.strip_period_px == pytest.approx(28*factor, abs=2)
    assert np.max(layout.strip[30*factor]) > 200 and np.min(layout.strip[30*factor]) < 20


@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_render_keeps_black_and_light_checker_cells_on_top_and_side(mode):
    layout = analyze_layout(checker_source())
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
    spec = DesignSpec(diameter_cm=139, height_cm=87, dpi=30, shape_mode=mode, straight_cm=108, border=BorderSpec(0, 0, 0))
    result = np.asarray(render_source(spec, material))
    scale = max(139/600, 87/400)
    y = -87/2 + 30*scale
    row = round((y/87 + .5)*len(result)-.5)
    top = result[row, int(result.shape[1]*.35):int(result.shape[1]*.65), :3]
    assert np.mean(np.min(top, axis=1) > 180) > .25, '直边棋盘格浅色方块缺失'
    assert np.mean(np.max(top, axis=1) < 30) > .25, '直边棋盘格黑色方块缺失'
    from shape_crop.core.geometry import create_shape
    shape = create_shape(spec)
    ys = np.linspace(-10, 10, 200)
    xs = getattr(shape, 'center', 0.) + np.sqrt((shape.radius-30*scale)**2-ys**2)
    rows = np.rint((ys/87+.5)*len(result)-.5).astype(int)
    columns = np.rint((xs/139+.5)*result.shape[1]-.5).astype(int)
    side = result[rows, columns, :3]
    assert np.mean(np.min(side, axis=1) > 180) > .25, '侧弧棋盘格浅色方块缺失'
    assert np.mean(np.max(side, axis=1) < 30) > .25, '侧弧棋盘格黑色方块缺失'
