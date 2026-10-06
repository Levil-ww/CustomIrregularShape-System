"""Text is a frame layer even when the sentence has no repeating period."""
import numpy as np
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.design_service import generate
from shape_crop.core.geometry import ArcBand, CircularBand, inset_boundary_fraction
import pytest


def text_frame():
    image = Image.new('RGB', (600, 360), (92, 63, 51))
    image.paste((239, 228, 209), (15, 15, 585, 345))
    draw = ImageDraw.Draw(image)
    draw.text((40, 19), 'THE SECRET OF STAYING YOUNG IS TO FACE LIFE POSITIVELY.', fill=(92, 63, 51))
    image.paste((92, 63, 51), (36, 36, 564, 324))
    pixels = np.asarray(image).copy()
    pixels[38:322, 38:562] = np.random.default_rng(91).integers(35, 150, (284, 524, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


def test_nonperiodic_english_and_inner_separator_belong_to_frame():
    layout = analyze_layout(text_frame())
    assert layout.border_depth_px == 38, '英文环误判为中央花纹，内侧咖色细线丢失'
    assert layout.content_box_px == (38, 38, 562, 322)
    assert layout.strip.shape[0] == 38


def test_print_resolution_keeps_the_same_complete_text_frame():
    image = text_frame().resize((3600, 2160), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    np.testing.assert_allclose(layout.content_box_px, (228, 228, 3372, 1932), atol=4)
    assert layout.image.shape == (2160, 3600, 3)
    assert layout.strip.shape[0] == layout.border_depth_px


def test_taller_order_scales_motif_uniformly_instead_of_stretching_text_band(tmp_path):
    pixels = np.asarray(text_frame()).copy()
    pixels[160:200, 290:310] = (255, 0, 0)
    path = tmp_path / 'text-frame.png'
    Image.fromarray(pixels).save(path)
    result = np.asarray(generate(DesignSpec(diameter_cm=60, height_cm=45, dpi=50,
        border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))))
    red = (result[..., 0] > 240) & (result[..., 1] < 10) & (result[..., 2] < 10)
    h, w = red.shape
    width_cm = red[h // 2].sum() / w * 60
    height_cm = red[:, w // 2].sum() / h * 45
    # Height requires 45/360 cm per source pixel, shared by both axes.
    assert abs(width_cm - 2.5) < .15
    assert abs(height_cm - 5) < .15


@pytest.mark.parametrize('shape', [ArcBand(139, 91, 104), CircularBand(139, 91)])
def test_text_coordinates_follow_each_inset_joint_and_rotate_lower_half(shape):
    reference = shape.inset(4)
    for depth in (1, 4, 7):
        inner = shape.inset(depth)
        # Every radial row joins the same text phase; no letter is cut at a joint.
        actual = inset_boundary_fraction(shape, inner.chord / 2, -inner.half_height,
                                         depth, reference)
        assert actual == pytest.approx(reference.chord / reference.perimeter)
        xs = np.linspace(-inner.chord / 2, inner.chord / 2, 15)
        top = inset_boundary_fraction(shape, xs, -inner.half_height, depth, reference)
        bottom = inset_boundary_fraction(shape, -xs, inner.half_height, depth, reference)
        np.testing.assert_allclose((bottom - top) % 1, .5, atol=1e-8)
