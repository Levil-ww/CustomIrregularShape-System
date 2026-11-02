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


@pytest.mark.parametrize('pattern', ['闲叙青釉', '闲叙・青釉', '闲序青釉', '闲序·青釉',
                                    '闲序.青釉', '闲叙·邂逅', '闲叙邂逅',
                                    '闲序邂逅', '闲序·邂逅', '闲序・邂逅', '闲序.邂逅'])
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


@pytest.mark.parametrize('pattern', ['普通画框', '闲叙秋山', '闲叙夜兰'])
def test_other_picture_keeps_independent_rectangle(tmp_path, pattern):
    path = tmp_path / f'{pattern};84x140cm.png'
    source().save(path)
    layout = prepare(MaterialSpec(str(path)), preview=True).source_layout
    assert layout.framed_artwork is not None
    assert layout.contoured_frame is None


@pytest.mark.parametrize('pattern', ['闲叙青釉', '闲叙・邂逅'])
def test_texture_inset_with_repeat_larger_than_each_clear_margin(tmp_path, pattern):
    top = 60
    rng = np.random.default_rng(7)
    tile = rng.integers(180, 241, (64, 64, 1), dtype=np.uint8)
    pixels = np.repeat(np.tile(tile, (4, 10, 1))[:240, :600], 3, axis=2)
    pixels[top:240-top, 55:545] = (40, 65, 50)
    image = Image.fromarray(pixels)
    ImageDraw.Draw(image).rectangle((0, 0, 599, 239), outline='black', width=10)
    path = tmp_path / f'{pattern};40x100cm.png'
    image.save(path)
    layout = prepare(MaterialSpec(str(path)), preview=True).source_layout
    assert layout.contoured_frame is not None, '四侧留白单独放不下完整周期时，中央纹理仍应随弧形'
    assert layout.contoured_frame.box == pytest.approx((55, top, 545, 240-top), abs=2)
    artwork = layout.framed_artwork
    assert np.min(artwork.tile) >= 180, '背景周期不能混入中央色块或黑边'
    for x, y in ((20, 20), (120, 30), (400, 210), (580, 110)):
        ox, oy = artwork.origin
        th, tw = artwork.tile.shape[:2]
        np.testing.assert_array_equal(artwork.tile[(y-oy)%th, (x-ox)%tw], pixels[y, x])
    from shape_crop.core.geometry import create_shape
    from shape_crop.core.content_mapping import ContentMapping
    material = prepare(MaterialSpec(str(path)), preview=True)
    for mode in ('arc', 'circular'):
        design = DesignSpec(diameter_cm=140, height_cm=84, straight_cm=100,
                            shape_mode=mode, border=BorderSpec(0, 0, 0))
        rendered = np.asarray(render_source(design, material, max_side=1000))
        inset = layout.contoured_frame.inset_px * ContentMapping.source_scale(layout, 140, 84)
        inner = create_shape(design).inset(inset)
        for y in (-10, 0, 10):
            edge = getattr(inner, 'center', 0) + np.sqrt(inner.radius**2-y**2)
            row = round((y/84+.5)*rendered.shape[0]-.5)
            for sign in (-1, 1):
                for delta, green in ((-1, True), (1, False)):
                    col = round((sign*(edge+delta)/140+.5)*rendered.shape[1]-.5)
                    assert (rendered[row,col,1]<130) == green, '内外纹理应在弧形边界分开'


@pytest.mark.parametrize('pattern', ['闲叙青釉', '闲叙邂逅'])
def test_curved_texture_keeps_uniform_scale_at_sides_and_centre(tmp_path, pattern):
    image = source()
    draw = ImageDraw.Draw(image)
    draw.ellipse((90, 140, 110, 160), fill=(0, 0, 240))
    draw.ellipse((490, 200, 510, 220), fill=(0, 0, 240))
    path = tmp_path / f'{pattern};84x140cm.png'
    image.save(path)
    material = prepare(MaterialSpec(str(path)), preview=True)
    design = DesignSpec(diameter_cm=140, height_cm=84, straight_cm=100,
                        shape_mode='arc', border=BorderSpec(0, 0, 0))
    pixels = np.asarray(render_source(design, material, max_side=1000))
    blue = (pixels[..., 2] > 180) & (pixels[..., 0] < 20) & (pixels[..., 1] < 20)
    for half in (blue[:, :500], blue[:, 500:]):
        rows, columns = np.nonzero(half)
        assert rows.size > 20
        assert abs(np.ptp(rows)-np.ptp(columns)) <= 2, '侧边纹理应保持原比例，不可挤压变形'
    red = (pixels[..., 0] > 170) & (pixels[..., 1] < 20)
    rows, columns = np.nonzero(red)
    assert abs(np.ptp(rows) - np.ptp(columns)) <= 2, '中央花纹应保持原比例'

    from shape_crop.core.geometry import create_shape
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.sampling import sample
    layout = material.source_layout
    a,b,c,d = layout.contoured_frame.box
    inner = create_shape(design).inset(layout.contoured_frame.inset_px *
        ContentMapping.source_scale(layout, 140, 84))
    height,width = pixels.shape[:2]
    x = ((np.arange(width)+.5)/width-.5)[None,:]*140
    y = ((np.arange(height)+.5)/height-.5)[:,None]*84
    scale = max(inner.diameter/(c-a),inner.height/(d-b))
    expected = sample(layout.image[b:d,a:c],x/scale+(c-a-1)/2,y/scale+(d-b-1)/2)
    visible = (inner.depth(x,y)>2) & (np.abs(x)>inner.diameter*.25)
    np.testing.assert_allclose(pixels[...,:3][visible],expected[visible],atol=1,
        err_msg='中央色块可以随弧形裁取，但原纹理不能随位置被拉伸或挤压')


def test_encounter_name_without_verified_picture_keeps_original_layout(tmp_path):
    path = tmp_path / '闲叙邂逅;84x140cm.png'
    Image.new('RGB', (600, 360), 'white').save(path)
    assert prepare(MaterialSpec(str(path)), preview=True).source_layout.contoured_frame is None


@pytest.mark.parametrize('pattern',['闲叙青釉','闲序青釉','闲序·青釉'])
@pytest.mark.parametrize('mode',['arc','circular'])
def test_celadon_dark_panel_with_nonperiodic_background_follows_arc(tmp_path,pattern,mode):
    rng=np.random.default_rng(38)
    values=rng.integers(170,241,(360,600,1),dtype=np.uint8)
    pixels=np.repeat(values,3,axis=2)
    values=rng.integers(35,85,(240,490,1),dtype=np.uint8)
    pixels[60:300,55:545]=np.concatenate((values,values+15,values+5),axis=2)
    image=Image.fromarray(pixels)
    ImageDraw.Draw(image).rectangle((0,0,599,359),outline='black',width=10)
    path=tmp_path/f'{pattern};85x137cm.png'
    image.save(path)
    material=prepare(MaterialSpec(str(path)),preview=True)
    assert material.source_layout.contoured_frame is not None, '深色中央纹理应识别为内框'
    design=DesignSpec(diameter_cm=140,height_cm=84,straight_cm=100,
                      shape_mode=mode,border=BorderSpec(0,0,0))
    rendered=np.asarray(render_source(design,material,max_side=1000))
    from shape_crop.core.geometry import create_shape
    from shape_crop.core.content_mapping import ContentMapping
    layout=material.source_layout
    inner=create_shape(design).inset(layout.contoured_frame.inset_px*
                                     ContentMapping.source_scale(layout,140,84))
    for y in (-15,0,15):
        side=getattr(inner,'center',0)+np.sqrt(inner.radius**2-y**2)
        row=round((y/84+.5)*rendered.shape[0]-.5)
        for sign in (-1,1):
            for offset,dark in ((-2,True),(2,False)):
                col=round((sign*(side+offset)/140+.5)*rendered.shape[1]-.5)
                assert (rendered[row,col,1]<140)==dark,'内外纹理应沿弧形分界'


@pytest.mark.parametrize('pattern', ['闲叙青釉', '闲叙邂逅'])
@pytest.mark.parametrize('straight', [100, 102])
def test_semicircular_sides_keep_background_around_texture_panel(tmp_path, pattern, straight):
    path = tmp_path / f'{pattern};80x180cm.png'
    source().save(path)
    material = prepare(MaterialSpec(str(path)), preview=True)
    design = DesignSpec(diameter_cm=180, height_cm=80, straight_cm=straight,
                        shape_mode='arc', border=BorderSpec(0, 0, 0))
    pixels = np.asarray(render_source(design, material, max_side=1200))
    for x,y in ((0,-32),(0,32),(-76,0),(76,0)):
        row = round((y/80+.5)*pixels.shape[0]-.5)
        col = round((x/180+.5)*pixels.shape[1]-.5)
        assert pixels[row,col,1] > 140, '半圆侧弧内框不能退化为外框并吞掉浅色留白'
    assert pixels[pixels.shape[0]//2,pixels.shape[1]//2+100,1] < 130


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

@pytest.mark.parametrize('width,height', [(600, 600), (1000, 250), (1800, 180)])
def test_celadon_dark_panel_recognition_for_varied_source_proportions(width, height):
    from shape_crop.services.layout_analysis import analyze_layout
    from shape_crop.services.contoured_frame import _adapt_dark_texture_panel
    rng = np.random.default_rng(52)
    values = rng.integers(170, 241, (height, width, 1), dtype=np.uint8)
    pixels = np.repeat(values, 3, axis=2)
    margin = round(min(width, height) * .1)
    pixels[margin:height-margin, margin:width-margin] = (45, 65, 50)
    image = Image.fromarray(pixels)
    ImageDraw.Draw(image).rectangle((0, 0, width-1, height-1), outline='black', width=4)
    layout = _adapt_dark_texture_panel(analyze_layout(image))
    assert layout.contoured_frame is not None, '不同长宽比的青釉内框都应识别'
