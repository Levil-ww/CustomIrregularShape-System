"""Keep faint fill and sparse flowers separate from whitespace and frames."""

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from shape_crop.services.layout_analysis import analyze_layout, _closed_thin_frame
from shape_crop.services.floating_artwork import detect_floating_artwork


def rounded_double_frame_source(factor=1, broken=False):
    scale=4
    image=Image.new('RGB',(800*scale,320*scale),(121,78,46))
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,800*scale-1,320*scale-1),outline='black',width=scale)
    draw.rounded_rectangle((18*scale,18*scale,781*scale,301*scale),radius=10*scale,fill=(255,242,226))
    for inset,radius,width in ((24,8,2),(28,8,2)):
        draw.rounded_rectangle((inset*scale,inset*scale,(799-inset)*scale,(319-inset)*scale),
                               radius=radius*scale,outline='black',width=width*scale)
    for y in range(29,290,24):
        for x in range(35,766,30):
            draw.ellipse((x*scale,y*scale,(x+17)*scale,(y+19)*scale),fill='black')
    if broken:
        draw.rectangle((27*scale,100*scale,30*scale,180*scale),fill=(255,242,226))
    return image.resize((800*factor,320*factor),Image.Resampling.LANCZOS)


@pytest.mark.parametrize('factor',[1,3])
def test_closed_rounded_inner_line_is_not_lost_at_pattern_transition(factor):
    image=rounded_double_frame_source(factor)
    layout=analyze_layout(image)
    assert layout.border_depth_px >= 29*factor, '紧贴花纹的第二道闭合细线必须完整进入边框带'
    profile=np.median(layout.strip,axis=1)
    dark=np.max(profile,axis=1)<90
    dark[:20*factor]=False
    starts=np.flatnonzero(np.diff(np.r_[False,dark].astype(np.int8))==1)
    assert len(starts)==2, '两道黑色内线都应保留'


def test_broken_rounded_inner_line_is_not_proven_as_a_closed_frame():
    assert _closed_thin_frame(np.asarray(rounded_double_frame_source(broken=True))) is None


def faint_fill_source(pattern=True):
    image = Image.new('RGB', (800, 480), (160, 140, 110))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 783, 463), fill=(246, 240, 230))
    draw.rectangle((34, 34, 765, 445), outline=(160, 140, 110), width=2)
    if pattern:
        for y in range(36, 443, 12):
            for x in range(36, 764, 12):
                draw.ellipse((x, y, x + 8, y + 8), fill=(255, 249, 239))
    draw.rectangle((36, 215, 763, 263), fill=(246, 240, 230))
    draw.text((260, 226), 'THE HEALING FEELING', fill=(140, 110, 80),
              font=ImageFont.load_default(size=20))
    return image


def sparse_framed_source():
    image = Image.new('RGB', (800, 480), (255, 255, 244))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 799, 479), outline='black', width=1)
    draw.rectangle((24, 24, 775, 455), outline='black', width=2)
    for x, y in ((70, 50), (270, 40), (480, 60), (100, 310), (440, 340)):
        draw.ellipse((x, y, x + 100, y + 90), outline='black', width=2)
        draw.line((x + 10, y + 45, x + 90, y + 45), fill='black', width=2)
    draw.rectangle((26, 185, 773, 280), outline='black', width=2)
    draw.text((310, 220), 'WONDERFUL LIFE', fill='black')
    return image


def test_faint_full_fill_is_not_a_blank_moat_around_center_text():
    image = faint_fill_source()
    assert detect_floating_artwork(image) is None, '浅色满铺花纹不能当成英文周围的留白'


@pytest.mark.parametrize('factor', [1, 3])
def test_closed_thin_frame_does_not_absorb_sparse_interior_art(factor):
    image = sparse_framed_source().resize(
        (800 * factor, 480 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    left, top, right, bottom = layout.content_box_px
    depths = np.array([left, top, image.width - right, image.height - bottom]) / factor
    assert np.all(np.abs(depths - 26) <= 3), '四边真实闭合细框不能越过内部花纹'


def test_flat_moat_still_preserves_independent_center_artwork():
    assert detect_floating_artwork(faint_fill_source(pattern=False)) is not None


@pytest.mark.parametrize('damage', ['broken', 'dotted', 'wide'])
def test_incomplete_or_decorative_frames_cannot_override_scans(damage):
    image = sparse_framed_source()
    draw = ImageDraw.Draw(image)
    if damage == 'broken':
        draw.rectangle((24, 80, 25, 160), fill=(255, 255, 244))
    elif damage == 'dotted':
        draw.rectangle((24, 24, 775, 25), fill=(255, 255, 244))
        for x in range(24, 775, 12):
            draw.rectangle((x, 24, x + 3, 25), fill='black')
    else:
        draw.rectangle((24, 24, 775, 455), outline='black', width=14)
    assert _closed_thin_frame(np.asarray(image)) is None


def test_wide_frame_crossing_detection_window_remains_a_border():
    image = Image.new('RGB', (800, 480), (250, 245, 235))
    draw = ImageDraw.Draw(image)
    draw.rectangle((94, 56, 705, 423), outline='black', width=70)
    draw.rectangle((1, 1, 80, 20), fill=(200, 20, 20))
    pixels = np.asarray(image).copy()
    pixels[126:354, 164:636] = np.random.default_rng(4).integers(
        30, 220, (228, 472, 3), dtype=np.uint8)
    assert _closed_thin_frame(pixels) is None
    layout = analyze_layout(Image.fromarray(pixels))
    assert layout.content_box_px == (164, 126, 636, 354)
