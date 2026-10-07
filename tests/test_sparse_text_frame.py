"""Sparse sentence frames must exclude corners and keep complete text at joins."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shape_crop.services.layout_analysis import analyze_layout


def sparse_text_source():
    image = Image.new('RGB', (800, 480), 'black')
    image.paste((242, 235, 225), (16, 16, 784, 464))
    image.paste('black', (23, 23, 777, 457))
    image.paste((242, 235, 225), (25, 25, 775, 455))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=22)
    draw.text((40, 32), 'The heart is.Home is where you are.', fill='black', font=font)
    image.paste(image.crop((0, 0, 800, 70)).transpose(Image.Transpose.ROTATE_180), (0, 410))
    # The central motif is beyond the bounded scan on the side edges.
    pixels = np.asarray(image).copy()
    pixels[205:275, 365:435] = np.random.default_rng(73).integers(0, 220, (70, 70, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


def test_sparse_text_frame_detects_all_edges_without_central_content_transition():
    layout = analyze_layout(sparse_text_source())
    left, top, right, bottom = layout.content_box_px
    assert left >= 25 and right <= 775 and bottom <= 435, '未识别竖边或下边，条带混入矩形转角'
    assert 40 <= top < 60, '完整英文应进入外边框带'
    assert np.max(np.mean(np.max(layout.strip, axis=2) < 40, axis=0)) < .8, '边框条带带入黑色转角'


def test_nonperiodic_sentence_retains_original_diagonal_anchors():
    layout = analyze_layout(sparse_text_source())
    assert layout.strip_is_sentence
    assert layout.sentence_layers[1] is None and layout.sentence_layers[3] is None, '无英文的原图侧边不能新增英文'
    for index in (0, 2):
        layer, anchor = layout.sentence_layers[index]
        assert anchor < .4, '左上、右下的原图对角位置不能改成居中'
        assert not np.any(layer[:, :10, 3]) and not np.any(layer[:, -10:, 3])
    assert abs(layout.sentence_layers[0][1] - layout.sentence_layers[2][1]) < .01


def test_sentence_sampling_retains_diagonal_positions_without_added_repeats():
    from shape_crop.core.sampling import sample_sentence_strip
    strip = np.full((12, 300, 3), 240, dtype=np.uint8)
    # An asymmetric coloured marker stands in for distinct letters.
    layer = np.concatenate((strip, np.zeros((12, 300, 1), dtype=np.uint8)), axis=2)
    layer[4:8, 120:145] = [10, 30, 60, 255]
    layer[4:8, 155:180] = [60, 30, 10, 255]
    layers = ((layer, .25), None, (layer, .25), None)
    lengths = np.array([100., 80., 100., 80.])
    starts = np.r_[0., np.cumsum(lengths)[:-1]]
    offsets = np.arange(-14.5, 15., .5)
    sentences = [sample_sentence_strip(strip, starts[index] + lengths[index] * .25 + offsets,
                 5, lengths, .5, layers) for index in (0, 2)]
    np.testing.assert_array_equal(sentences[0], sentences[1])
    for index in (1, 3):
        actual = sample_sentence_strip(strip, starts[index] + np.arange(1, 79), 5, lengths, .5, layers)
        np.testing.assert_array_equal(actual, 240)
    for joint in np.cumsum(lengths):
        actual = sample_sentence_strip(strip, joint + np.array([-.01, 0, .01]), 5, lengths, .5, layers)
        np.testing.assert_array_equal(actual, 240)
    # Source-layer clamping must not smear its last glyph row inward.
    layer[-1, 130:170] = [0, 0, 0, 255]
    actual = sample_sentence_strip(strip, np.array([30., 210.]), 15, lengths, .5, layers)
    np.testing.assert_array_equal(actual, 240)
