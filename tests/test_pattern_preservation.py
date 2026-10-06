"""Non-periodic content must remain one centred affine sample of the original source."""
from dataclasses import replace
import numpy as np
from PIL import Image
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.design_service import generate
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.core.sampling import sample
from shape_crop.core.geometry import CircularBand


def test_plain_black_frame_is_not_confused_with_blank_rows_inside_flowers():
    pixels = np.full((240, 400, 3), 0, dtype=np.uint8)
    pixels[5:-5, 5:-5] = np.random.default_rng(4).integers(30, 220, (230, 390, 3), dtype=np.uint8)
    # A white gap inside an asymmetric illustration is artwork, not another frame layer.
    pixels[60:66, 5:-5] = 255
    layout = analyze_layout(Image.fromarray(pixels))
    assert layout.border_depth_px == 5, '花纹内部的空白行被误判为边框'
    assert layout.content_box_px == (5, 5, 395, 235)


def test_nonperiodic_flower_is_not_mirrored_or_repeated(tmp_path):
    source = np.full((240, 400, 3), 0, dtype=np.uint8)
    source[5:-5, 5:-5] = np.random.default_rng(7).integers(40, 235, (230, 390, 3), dtype=np.uint8)
    path = tmp_path / 'asymmetric.png'
    Image.fromarray(source).save(path)
    spec = replace(DesignSpec(), diameter_cm=40, height_cm=20, dpi=25,
                   border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    result = np.asarray(generate(spec))
    w, h = result.shape[1], result.shape[0]
    # Fixed original-image scale follows the full diameter. The shorter height is a central crop.
    scale = spec.diameter_cm / source.shape[1]
    xs = ((np.arange(w) + .5) / w - .5) * spec.diameter_cm
    ys = ((np.arange(h) + .5) / h - .5) * spec.height_cm
    expected = sample(source, xs[None, :] / scale + 199.5, ys[:, None] / scale + 119.5)
    depth = CircularBand(spec.diameter_cm, spec.height_cm).depth(xs[None, :], ys[:, None])
    interior = depth > 5 * scale + 2 * spec.diameter_cm / w
    np.testing.assert_allclose(result[..., :3][interior], expected[interior], atol=1,
                               err_msg='原花纹位置/大小改变；应仅居中裁剪')


def test_small_edge_detection_difference_only_adjusts_frame(tmp_path):
    source = np.zeros((240, 400, 3), dtype=np.uint8)
    source[5:-6, 6:-7] = np.random.default_rng(8).integers(40, 235, (229, 387, 3), dtype=np.uint8)
    path = tmp_path / 'edge-difference.png'
    Image.fromarray(source).save(path)
    spec = replace(DesignSpec(), diameter_cm=40, height_cm=24, dpi=25,
                   border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    result = np.asarray(generate(spec))
    h, w = result.shape[:2]
    xs = ((np.arange(w) + .5) / w - .5) * 40
    ys = ((np.arange(h) + .5) / h - .5) * 24
    depth = CircularBand(40, 24).depth(xs[None, :], ys[:, None])
    frame = (depth > .1) & (depth < .5)
    np.testing.assert_array_equal(result[..., :3][frame], 0)
    np.testing.assert_array_equal(result[..., :3][frame], result[::-1, :, :3][frame])
    expected = sample(source, xs[None, :] / .1 + 199.5, ys[:, None] / .1 + 119.5)
    interior = depth > .7 + 2 * 40 / w
    np.testing.assert_allclose(result[..., :3][interior], expected[interior], atol=1)
