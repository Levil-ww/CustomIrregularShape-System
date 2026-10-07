"""Full-span English bands share perimeter mapping regardless of ink density."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytest
from shape_crop.services.layout_analysis import _sentence_layer, analyze_layout


def english_band(full_span=True):
    image = Image.new('RGB', (800, 480), (250, 249, 236))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 779, 459), outline='black', width=3)
    font = ImageFont.load_default(size=24)
    text = 'THE SECRET OF STAYING YOUNG IS TO FACE LIFE POSITIVELY.'
    ink = Image.new('RGB', (740, 28), (250, 249, 236))
    ImageDraw.Draw(ink).text((0, 0), text, fill='black', font=font)
    if not full_span:
        ink = ink.resize((300, 28))
    image.paste(ink, (30, 26))
    draw.rectangle((25, 58, 774, 421), outline='black', width=3)
    pixels = np.asarray(image).copy()
    pixels[61:419, 28:772] = np.random.default_rng(67).integers(0, 180, (358, 744, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


@pytest.mark.parametrize('density', [1, 3])
def test_full_span_ink_is_not_a_local_sentence(density):
    strip = np.full((30, 500, 3), 245, dtype=np.uint8)
    # Distinct glyph-like strokes spread across the edge, with different ink weights.
    for index in range(0, 495, 11):
        strip[8:22, index:index + density] = 0
    assert _sentence_layer(strip) is None, '满幅英文不能因笔画稀疏而分成四段独立短句'


def test_continuous_english_retains_original_pixels_for_perimeter_mapping():
    layout = analyze_layout(english_band())
    assert not layout.strip_is_sentence, '连续英文带应统一按周长环绕'
    assert not layout.sentence_layers
    assert np.any(np.std(layout.strip.astype(float), axis=1) > 20), '环绕条带不能抹去英文'


def test_local_sentence_still_retains_its_source_anchor():
    layout = analyze_layout(english_band(False))
    assert layout.strip_is_sentence
    assert layout.sentence_layers[0][1] < .4, '对角短句仍须保留原素材位置'



def test_continuous_band_closes_without_an_added_sentence_break():
    from shape_crop.core.sampling import sample_perimeter_strip
    layout = analyze_layout(english_band())
    positions = np.array([-.01, 0., .01])
    for joint in (0., 80., 180., 260.):
        before = sample_perimeter_strip(layout.strip, positions + joint, 36, 360., .1)
        wrapped = sample_perimeter_strip(layout.strip, positions + joint + 360., 36, 360., .1)
        np.testing.assert_allclose(before, wrapped, atol=1, rtol=0)
