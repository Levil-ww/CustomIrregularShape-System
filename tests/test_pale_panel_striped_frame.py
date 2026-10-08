"""Regression for pale inset panels and shallow striped perimeter frames."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec
from shape_crop.core.source_renderer import render_source


def pale_panel_source():
    image = Image.new('RGB', (600, 360), (211, 203, 176))
    draw = ImageDraw.Draw(image)
    draw.rectangle((14, 14, 585, 345), fill=(255, 251, 241))
    pixels = np.asarray(image).copy()
    noise = np.random.default_rng(27).random((332, 572)) < .3
    pixels[14:346, 14:586][noise] = (179, 162, 120)
    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    draw.rectangle((62, 65, 537, 295), fill=(255, 251, 241), outline=(211, 203, 176), width=2)
    draw.line((62, 67, 62, 293), fill=(220, 211, 189), width=2)
    draw.text((235, 266), 'FANTASY STORIES', fill=(179, 162, 120))
    return image


def striped_source(width=600, height=360):
    pixels = np.full((height, width, 3), (230, 217, 184), dtype=np.uint8)
    pixels[[0, -1]] = 0
    pixels[:, [0, -1]] = 0
    pixels[12:height-12, 12:width-12] = 255
    pixels[15:height-15, 15:width-15] = (230, 217, 184)
    for x in range(30, width-30, 4):
        pixels[15:44, x:x+2] = 255
        pixels[height-44:height-15, x:x+2] = 255
    for y in range(44, height-44, 4):
        pixels[y:y+2, 15:44] = 255
        pixels[y:y+2, width-44:width-15] = 255
    pixels[44:height-44, 30:width-30] = 255
    pixels[47:height-47, 47:width-47] = np.random.default_rng(8).integers(180, 245, (height - 94, width - 94, 3))
    return Image.fromarray(pixels)


@pytest.mark.parametrize('factor', [1, 3])
def test_pale_closed_panel_is_classified(factor):
    image = pale_panel_source().resize((600 * factor, 360 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    assert layout.category == '中央内框类'
    assert layout.inset_panel is not None, '浅色封闭中央框没有被识别'
    np.testing.assert_allclose(np.array(layout.inset_panel.box) / factor, (62, 65, 537, 295), atol=3)


@pytest.mark.parametrize('width,height', [(600, 360), (650, 430), (690, 430), (750, 455)])
def test_striped_frame_keeps_all_layers_across_source_sizes(width, height):
    layout = analyze_layout(striped_source(width, height))
    assert 46 <= layout.border_depth_px <= 49, '条纹装饰及内分隔线被截掉'
    assert layout.category == '周期装饰边框类'
    assert layout.strip_period_px == 4
    assert layout.content_box_px[0] >= 46


@pytest.mark.parametrize('width,height', [(151, 91), (139, 87), (131, 87)])
def test_pale_panel_render_has_curved_sides(width, height):
    layout = analyze_layout(pale_panel_source())
    assert layout.inset_panel is not None
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(''), layout)
    design = DesignSpec(diameter_cm=width, height_cm=height, border=BorderSpec(0, 0, 0))
    result = np.asarray(render_source(design, material, max_side=1200))
    # Detect the pale panel boundary along rows, away from the outer frame.
    edges = []
    for fraction in (.5, .3):
        row = result[round(result.shape[0] * fraction), :, :3]
        cream = np.max(np.abs(row.astype(float) - (255, 251, 241)), axis=1) < 5
        middle = len(row) // 2
        end = middle
        while end < len(row) and cream[end]:
            end += 1
        edges.append(end)
    assert edges[0] - edges[1] > 10, '中央框侧边仍为矩形直线'


@pytest.mark.parametrize('mode', ['arc', 'circular'])
@pytest.mark.parametrize('width,height', [(151,91), (139,87), (131,87)])
def test_stripes_are_present_on_top_and_curved_side(width, height, mode):
    layout = analyze_layout(striped_source())
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(''), layout)
    design = DesignSpec(diameter_cm=width, height_cm=height, shape_mode=mode,
                        straight_cm=width * .79, border=BorderSpec(0, 0, 0))
    result = np.asarray(render_source(design, material, max_side=1200))
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import create_shape
    scale = ContentMapping.source_scale(layout, width, height)
    depth = 29 * scale
    h, w = result.shape[:2]
    # The top ticks vary tangentially. At mid-height the side ticks must also
    # alternate rather than leaving a rectangular frame inside the artwork.
    top = round(depth / height * h)
    assert np.std(result[top, w//3:2*w//3, 0]) > 7
    side = round((create_shape(design).inset(depth).diameter / 2 / width + .5) * w)
    assert np.std(result[h//2-12:h//2+13, side, 0]) > 7


def test_open_pale_rectangle_is_not_a_panel():
    image = pale_panel_source()
    ImageDraw.Draw(image).rectangle((60, 68, 65, 292), fill=(255, 251, 241))
    assert analyze_layout(image).inset_panel is None


@pytest.mark.parametrize('width,height', [(151, 91), (139, 87), (131, 87)])
def test_pale_panel_ink_uses_uniform_transform(width, height):
    from shape_crop.core.panel_mapping import adapt_panel
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import create_shape
    image = pale_panel_source()
    # A square glyph stand-in reveals both unequal scaling and row shear.
    ImageDraw.Draw(image).rectangle((290, 260, 309, 279), fill=(170, 150, 110))
    layout = analyze_layout(image)
    design = DesignSpec(diameter_cm=width, height_cm=height, border=BorderSpec(0, 0, 0))
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(''), layout)
    pixels = np.asarray(render_source(design, material, max_side=1800))
    mask = np.max(np.abs(pixels[..., :3].astype(float) - (170, 150, 110)), axis=2) < 5
    rows, columns = np.nonzero(mask)
    assert abs((columns.max()-columns.min()) - (rows.max()-rows.min())) <= 2
    spans = [(np.flatnonzero(row)[0], np.flatnonzero(row)[-1]) for row in mask if np.count_nonzero(row) > 2]
    assert max(a for a,b in spans)-min(a for a,b in spans) <= 1, '英文笔画随圆弧产生倾斜'


@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_stripe_corner_gaps_survive_perimeter_mapping(mode):
    from shape_crop.core.geometry import create_shape
    from shape_crop.core.content_mapping import ContentMapping
    layout = analyze_layout(striped_source())
    design = DesignSpec(diameter_cm=151, height_cm=91, shape_mode=mode,
                        straight_cm=120.5, border=BorderSpec(0, 0, 0))
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(''), layout)
    pixels = np.asarray(render_source(design, material, max_side=1800))
    depth = 29 * ContentMapping.source_scale(layout, 151, 91)
    inner = create_shape(design).inset(depth)
    h,w = pixels.shape[:2]
    for sx in (-1,1):
        for sy in (-1,1):
            x = round((sx*inner.chord/2/151+.5)*w-.5)
            y = round((sy*inner.half_height/91+.5)*h-.5)
            patch = pixels[y-2:y+3,x-2:x+3,:3]
            assert np.max(np.abs(patch.astype(float)-(230,217,184))) < 8, '转角空隙被重复条纹填满'


@pytest.mark.parametrize('mode', ['arc', 'circular'])
@pytest.mark.parametrize('width,height', [(151, 91), (139, 87), (131, 87)])
def test_stripes_reach_inner_corner_without_wide_blank(mode, width, height):
    from shape_crop.core.geometry import create_shape
    from shape_crop.core.content_mapping import ContentMapping
    layout = analyze_layout(striped_source())
    design = DesignSpec(diameter_cm=width, height_cm=height, shape_mode=mode,
                        straight_cm=width * .79, border=BorderSpec(0, 0, 0))
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(''), layout)
    pixels = np.asarray(render_source(design, material, max_side=1800))
    scale = ContentMapping.source_scale(layout, width, height)
    shape = create_shape(design)
    h, w = pixels.shape[:2]
    depth = 40 * scale
    inner = shape.inset(depth)
    for sx in (-1, 1):
        for sy in (-1, 1):
            row = round((sy * inner.half_height / height + .5) * h - .5)
            a = round((sx * (inner.chord / 2 - 15 * scale) / width + .5) * w - .5)
            b = round((sx * (inner.chord / 2 - 6 * scale) / width + .5) * w - .5)
            patch = pixels[row-1:row+2, min(a,b):max(a,b)+1, :3]
            assert np.std(patch[..., 2]) > 10, '内侧转角附近条纹被过宽留白遮掉'


@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_arc_ticks_near_corner_span_whole_decoration_depth(mode):
    from shape_crop.core.geometry import create_shape
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.sampling import sample
    layout = analyze_layout(striped_source())
    design = DesignSpec(diameter_cm=151, height_cm=91, shape_mode=mode,
                        straight_cm=120.5, border=BorderSpec(0, 0, 0))
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(''), layout)
    pixels = np.asarray(render_source(design, material, max_side=2400))
    shape = create_shape(design)
    scale = ContentMapping.source_scale(layout, 151, 91)
    inner = shape.inset(44 * scale)
    # Inspect the side arc in polar coordinates so an intact tick is a
    # constant column across radial rows. A sloping mask produces half ticks.
    angles = np.linspace(inner.angle - .06, inner.angle + .04, 600)[None, :]
    depths = np.array([20, 26, 32, 38])[:, None] * scale
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = sx * (getattr(shape, 'center', 0.) + (shape.radius - depths) * np.cos(angles))
            y = sy * (shape.radius - depths) * np.sin(angles)
            values = sample(pixels[..., :3], (x / 151 + .5) * pixels.shape[1] - .5,
                            (y / 91 + .5) * pixels.shape[0] - .5)
            # Ignore interpolation at stroke edges; salient stroke interiors
            # cannot turn into background at another radial depth.
            white = values[..., 2] > 245
            beige = values[..., 2] < 195
            assert not np.any(np.any(white, axis=0) & np.any(beige, axis=0)), '侧弧接头出现只画了一半的条纹'
            assert np.count_nonzero(np.all(white, axis=0)) > 10, '不能通过删除角部全部条纹来规避残缺'
