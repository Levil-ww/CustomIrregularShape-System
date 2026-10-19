"""Encounter textures fill a curved inset without shrinking as a rectangle."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from dataclasses import replace
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.materials import prepare
from shape_crop.core.source_renderer import render_source


def source():
    yy, xx = np.mgrid[:360, :600]
    pixels = np.where(((xx // 8 + yy // 8) % 2)[..., None],
                      (235, 225, 205), (175, 165, 145)).astype(np.uint8)
    pixels[60:300, 55:545] = np.where(((xx[60:300, 55:545] // 12 +
        yy[60:300, 55:545] // 12) % 2)[..., None], (40, 65, 50), (80, 100, 65))
    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 599, 359), outline='black', width=10)
    draw.ellipse((290, 170, 309, 189), fill=(200, 0, 0))
    return image


@pytest.mark.parametrize('pattern', ['闲叙青釉', '闲叙・青釉', '闲叙·邂逅', '闲叙邂逅'])
@pytest.mark.parametrize('mode', ['circular', 'arc'])
def test_texture_side_follows_curved_inset(tmp_path, pattern, mode):
    path = tmp_path / f'双面格-定制-定制尺寸-{pattern};84x140cm.png'
    source().save(path)
    material = prepare(MaterialSpec(str(path)), preview=True)
    design = DesignSpec(diameter_cm=140, height_cm=84, straight_cm=100,
                        shape_mode=mode, border=BorderSpec(0, 0, 0))
    pixels = np.asarray(render_source(design, material, max_side=1000))
    # The source top/bottom clearance is 60px at 140/600 cm per pixel.
    from shape_crop.core.geometry import create_shape
    inner = create_shape(design).inset(14)
    for y in (0, -20, 20):
        side = getattr(inner, 'center', 0) + np.sqrt(inner.radius ** 2 - y ** 2)
        row = round((y / 84 + .5) * pixels.shape[0] - .5)
        for sign in (-1, 1):
            inside = round(((sign * (side - 1)) / 140 + .5) * pixels.shape[1] - .5)
            outside = round(((sign * (side + 1)) / 140 + .5) * pixels.shape[1] - .5)
            assert pixels[row, inside, 1] < 130, '中央纹理应填满内侧弧形轮廓'
            assert pixels[row, outside, 1] > 140, '浅色外层应保留在内侧轮廓之外'
    red = (pixels[..., 0] > 170) & (pixels[..., 1] < 20)
    rows, columns = np.nonzero(red)
    assert abs(np.ptp(rows) - np.ptp(columns)) <= 2, '内层纹理不能随弧形横向拉伸'
    assert np.ptp(columns) > 28, '中央纹理不应作为独立画框整体缩小'


def test_other_picture_keeps_independent_rectangle(tmp_path):
    path = tmp_path / '普通画框;84x140cm.png'
    source().save(path)
    layout = prepare(MaterialSpec(str(path)), preview=True).source_layout
    assert layout.framed_artwork is not None
    assert layout.contoured_frame is None


@pytest.mark.parametrize('pattern', ['闲叙青釉', '闲叙邂逅'])
def test_curved_texture_preserves_side_motifs_without_distorting_centre(tmp_path, pattern):
    image = source()
    draw = ImageDraw.Draw(image)
    draw.rectangle((58, 90, 72, 108), fill=(0, 0, 240))
    draw.rectangle((527, 251, 541, 269), fill=(0, 0, 240))
    path = tmp_path / f'{pattern};84x140cm.png'
    image.save(path)
    material = prepare(MaterialSpec(str(path)), preview=True)
    design = DesignSpec(diameter_cm=140, height_cm=84, straight_cm=100,
                        shape_mode='arc', border=BorderSpec(0, 0, 0))
    pixels = np.asarray(render_source(design, material, max_side=1000))
    blue = (pixels[..., 2] > 180) & (pixels[..., 0] < 20) & (pixels[..., 1] < 20)
    assert blue[:, :500].sum() > 20, '左侧花纹应随内弧收拢，不能直接裁掉'
    assert blue[:, 500:].sum() > 20, '右侧花纹应随内弧收拢，不能直接裁掉'
    red = (pixels[..., 0] > 170) & (pixels[..., 1] < 20)
    rows, columns = np.nonzero(red)
    assert abs(np.ptp(rows) - np.ptp(columns)) <= 2, '中央花纹应保持原比例'


def test_encounter_name_without_verified_picture_keeps_original_layout(tmp_path):
    path = tmp_path / '闲叙邂逅;84x140cm.png'
    Image.new('RGB', (600, 360), 'white').save(path)
    assert prepare(MaterialSpec(str(path)), preview=True).source_layout.contoured_frame is None


def test_native_analysis_without_picture_recovers_verified_texture_bounds():
    from shape_crop.services.layout_analysis import analyze_layout
    from shape_crop.services.contoured_frame import adapt_texture_inset
    image = source().resize((3000, 1800), Image.Resampling.NEAREST)
    # The native path can reject a repeat that the bounded analysis verifies.
    layout = replace(analyze_layout(image), framed_artwork=None)
    result = adapt_texture_inset(layout)
    assert result.contoured_frame is not None, '原分辨率识别失败后仍应保留已验证的弧形纹理内框'
    assert result.image is layout.image, '重新识别不能降低原分辨率像素'
    assert result.contoured_frame.inset_px == pytest.approx(300, abs=15)


def test_texture_inset_removes_background_margin_from_picture_selection():
    from shape_crop.services.layout_analysis import analyze_layout
    from shape_crop.services.contoured_frame import adapt_texture_inset
    layout = analyze_layout(source())
    picture = replace(layout.framed_artwork, box=(52, 57, 548, 303))
    result = adapt_texture_inset(replace(layout, framed_artwork=picture))
    a, b, c, d = result.contoured_frame.box
    assert a >= 55 and b >= 60 and c <= 545 and d <= 300, '外层纹理不能混入随弧线收拢的内花纹'


def test_native_fallback_keeps_flat_background_colour():
    from shape_crop.services.layout_analysis import analyze_layout
    from shape_crop.services.contoured_frame import adapt_texture_inset
    from shape_crop.services.materials import PreparedMaterial
    image = Image.new('RGB', (600, 360), (235, 225, 205))
    image.paste(source().crop((55, 60, 545, 300)), (55, 60))
    ImageDraw.Draw(image).rectangle((0, 0, 599, 359), outline='black', width=10)
    image = image.resize((3000, 1800), Image.Resampling.NEAREST)
    layout = adapt_texture_inset(replace(analyze_layout(image), framed_artwork=None))
    assert layout.contoured_frame is not None
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
    design = DesignSpec(diameter_cm=140, height_cm=84, border=BorderSpec(0, 0, 0))
    pixels = np.asarray(render_source(design, material, max_side=700))
    np.testing.assert_array_equal(pixels[45, 350, :3], (235, 225, 205),
                                  err_msg='原分辨率回退不能把浅色外层换成黑色描边')
