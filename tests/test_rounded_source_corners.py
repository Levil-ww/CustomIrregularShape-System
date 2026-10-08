"""Rounded source rectangle corners must not bend a sampled outline."""
import numpy as np
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.core.source_renderer import render_source
from shape_crop.core.geometry import create_shape
import pytest


def rounded_frame_source():
    image = Image.new('RGB', (600, 360), (120, 76, 43))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, 583, 343), radius=24, fill=(254, 242, 226))
    draw.rounded_rectangle((24, 24, 575, 335), radius=20, outline='black', width=2)
    draw.rounded_rectangle((30, 30, 569, 329), radius=18, outline='black', width=2)
    pixels = np.asarray(image).copy()
    pixels[32:328, 32:568] = np.random.default_rng(42).integers(100, 220, (296, 536, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


def test_outline_strip_excludes_original_rectangular_corner_excursions():
    layout = analyze_layout(rounded_frame_source())
    assert np.max(np.ptp(layout.strip[24:26], axis=1)) <= 8, '原矩形圆角被带入轮廓条带，造成局部起伏'
    assert np.max(np.ptp(layout.strip[30:32], axis=1)) <= 8


@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_black_separator_stays_continuous_along_both_side_arcs(mode):
    layout = analyze_layout(rounded_frame_source())
    design = DesignSpec(diameter_cm=60, height_cm=36, shape_mode=mode,
                        straight_cm=46, border=BorderSpec(0, 0, 0))
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
    pixels = np.asarray(render_source(design, material, max_side=1600))
    inner = create_shape(design).inset(2.45)
    ys = np.linspace(-inner.half_height * .99, inner.half_height * .99, 250)
    xs = getattr(inner, 'center', 0.) + np.sqrt(inner.radius**2 - ys**2)
    rows = np.rint((ys / 36 + .5) * pixels.shape[0] - .5).astype(int)
    for sign in (-1, 1):
        cols = np.rint((sign * xs / 60 + .5) * pixels.shape[1] - .5).astype(int)
        assert np.all(np.max(pixels[rows, cols, :3], axis=1) < 90), '原矩形圆角造成目标侧弧细线局部偏离'


def wide_outline_source():
    image = Image.new('RGB', (600, 360), (120, 76, 43))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, 583, 343), radius=24, fill=(254, 242, 226))
    draw.rounded_rectangle((24, 24, 575, 335), radius=32, outline='black', width=2)
    draw.rounded_rectangle((38, 38, 561, 321), radius=24, outline='black', width=2)
    pixels = np.asarray(image).copy()
    pixels[40:320, 40:560] = np.random.default_rng(42).integers(100, 220, (280, 520, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


def test_space_between_outline_strokes_has_no_source_corner_fragments():
    layout = analyze_layout(wide_outline_source())
    gap = layout.strip[26:38]
    assert np.all(gap == (254, 242, 226)), 'Triangle fragments remain between outline strokes'


def test_sparse_decoration_between_strokes_is_preserved():
    image = wide_outline_source()
    ImageDraw.Draw(image).line((300, 29, 300, 33), fill='black')
    layout = analyze_layout(image)
    assert np.any(np.max(layout.strip[29:34], axis=2) < 80), 'Sparse decoration was removed with corner fragments'
