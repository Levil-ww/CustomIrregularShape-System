"""Gallery compositions share automatic recognition and preserved frame clearance."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape
from shape_crop.models.design import DesignSpec, BorderSpec
from shape_crop.services.floating_artwork import detect_floating_artwork


@pytest.mark.parametrize('factor', [1, 4])
@pytest.mark.parametrize('line_width', [2, 3])
def test_narrow_gallery_clearance_does_not_count_thin_frame_as_artwork(factor, line_width):
    image = Image.new('RGB', (600, 360), (247, 240, 232))
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 12, 587, 347), outline=(170, 130, 70), width=line_width)
    for box, colour in [((32, 100, 200, 260), (50, 65, 35)),
                        ((240, 100, 360, 260), (170, 130, 70)),
                        ((400, 100, 568, 260), (25, 24, 24))]:
        image.paste(colour, box)
    image = image.resize((600 * factor, 360 * factor), Image.Resampling.NEAREST)
    assert detect_floating_artwork(image) is not None, '窄留白中的细外框不能计作图案导致尺寸识别不一致'


@pytest.mark.parametrize('factor', [1, 4])
def test_coloured_frame_is_not_a_blank_moat(factor):
    # The large connected frame is ignored as an artwork component, but its
    # contrasting colour must not count as whitespace around the small motifs.
    image = Image.new('RGB', (800, 480), (106, 104, 63))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 799, 479), outline=(92, 63, 51), width=16)
    draw.rectangle((16, 16, 783, 463), outline=(239, 228, 209), width=28)
    for x in range(70, 740, 60):
        for y in range(70, 420, 60):
            draw.ellipse((x, y, x + 20, y + 20), outline='black', width=2)
    if factor != 1:
        image = image.resize((800 * factor, 480 * factor), Image.Resampling.NEAREST)
    assert detect_floating_artwork(image) is None, '米色英文框与咖色外框不能当作绿色背景留白'


@pytest.mark.parametrize('factor', [1, 4])
def test_connected_full_span_pattern_with_central_panel_keeps_source_scale(factor):
    image = Image.new('RGB', (600, 360), (255, 244, 221))
    draw = ImageDraw.Draw(image)
    # Connected full-span floral strokes surround a textured central panel.
    # The large component must not be discarded as a frame to create a gallery.
    for x in range(0, 600, 32):
        draw.line((x, 0, x, 359), fill='black', width=2)
    for y in range(0, 360, 32):
        draw.line((0, y, 599, y), fill='black', width=2)
    draw.rectangle((90, 70, 509, 289), fill=(255, 244, 221))
    panel = np.random.default_rng(19).integers(165, 215, (200, 400, 3), dtype=np.uint8)
    image.paste(Image.fromarray(panel), (100, 80))
    if factor != 1:
        image = image.resize((600 * factor, 360 * factor), Image.Resampling.NEAREST)
    assert detect_floating_artwork(image) is None, '外围相连花纹不能被忽略为画框'
    layout = analyze_layout(image)
    assert layout.floating_artwork is None, '外围满幅花纹不能当成中央画框的留白'
    shape = create_shape(DesignSpec(diameter_cm=139, height_cm=87,
                         shape_mode='arc', straight_cm=108, border=BorderSpec(0, 0, 0)))
    scale = ContentMapping.source_scale(layout, 139, 87)
    border = max(layout.border_depth_px * scale, ContentMapping.required_border(layout, 139, 87))
    mapping = ContentMapping.create(layout, 139, 87, border, shape=shape)
    assert mapping.scale_cm == scale, '中央纹理面板与外围花纹必须按原图等比裁剪'
    assert mapping.background is None, '圆弧两侧不能补出纯色竖带'


@pytest.mark.parametrize('outlined', [False, True])
@pytest.mark.parametrize('factor', [1, 4])
@pytest.mark.parametrize('width,height,straight', [(131, 81, 103), (139, 87, 108), (105, 66.5, 82)])
def test_floating_gallery_fits_shape_with_original_minimum_clearance(outlined, factor, width, height, straight):
    image = Image.new('RGB', (650, 400), (247, 240, 232))
    if outlined:
        image.paste((170, 130, 70), (16, 16, 634, 384))
        image.paste((247, 240, 232), (18, 18, 632, 382))
    for box, colour in [((70, 110, 210, 290), (90, 30, 40)),
                        ((240, 110, 410, 290), (30, 90, 40)),
                        ((440, 110, 580, 290), (40, 30, 90))]:
        image.paste(colour, box)
    if factor != 1:
        image = image.resize((650 * factor, 400 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    assert layout.floating_artwork is not None, '独立画框应自动归为留白图案类'
    design = DesignSpec(diameter_cm=width, height_cm=height, shape_mode='arc', straight_cm=straight,
                        border=BorderSpec(0, 0, 0))
    shape = create_shape(design)
    native = ContentMapping.source_scale(layout, width, height)
    border = max(layout.border_depth_px * native, ContentMapping.required_border(layout, width, height))
    mapping = ContentMapping.create(layout, width, height, border, shape=shape)
    bounds, frame, _ = layout.floating_artwork
    left, top, right, bottom = bounds
    gap = min(left - frame[0], top - frame[1], frame[2] - right, frame[3] - bottom) * native
    xs = np.array([left, left, right, right]) - layout.width_px / 2
    ys = np.array([top, bottom, top, bottom]) - layout.height_px / 2
    assert mapping.scale_cm < native, '弧形内框挤占留白时必须整体等比缩小'
    assert np.min(shape.depth(xs * mapping.scale_cm, ys * mapping.scale_cm)) - border >= gap - .01


def test_dense_flower_band_is_not_classified_as_floating_artwork():
    image = Image.fromarray(np.random.default_rng(5).integers(0, 256, (400, 650, 3), dtype=np.uint8))
    assert analyze_layout(image).floating_artwork is None


def test_render_keeps_entire_gallery_and_reports_shared_scaling(tmp_path):
    from shape_crop.services.design_service import generate
    from shape_crop.models.design import MaterialSpec
    image = Image.new('RGB', (650, 400), (247, 240, 232))
    colours = [(90, 30, 40), (30, 90, 40), (40, 30, 90)]
    for box, colour in zip([(70, 110, 210, 290), (240, 110, 410, 290), (440, 110, 580, 290)], colours):
        image.paste(colour, box)
    path = tmp_path / 'unnamed-gallery.png'
    image.save(path)
    reports = []
    design = DesignSpec(diameter_cm=131, height_cm=81, dpi=30, shape_mode='arc', straight_cm=103,
                        border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))
    result = np.asarray(generate(design, diagnostics=reports.append))
    widths = []
    for colour in colours:
        selected = np.max(np.abs(result[..., :3].astype(int) - colour), axis=2) < 3
        rows, columns = np.nonzero(selected)
        width, height = columns.max() - columns.min() + 1, rows.max() - rows.min() + 1
        assert selected.sum() >= width * height * .99, '独立画框不能被圆弧剪掉角部'
        widths.append(width)
    assert widths[1] / widths[0] == pytest.approx(170 / 140, abs=.02), '图案组必须共用一个等比缩放'
    assert widths[2] == pytest.approx(widths[0], abs=1)
    assert '独立图案留白类' in reports[0] and '最小留白' in reports[0]
