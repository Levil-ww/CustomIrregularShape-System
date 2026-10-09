"""Central artwork must not become sentence or noise-period perimeter bands."""
from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.design_service import generate
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec


def geometric_source(textured=False):
    image = Image.new('RGB', (600, 600), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 599, 599), outline='black', width=2)
    if textured:
        # Nonperiodic neutral veins distinguish marble from flat gallery space.
        draw.line((30, 3, 190, 90, 125, 180, 240, 330, 170, 597), fill=(200, 200, 200), width=3)
        draw.line((597, 90, 480, 170, 555, 360, 400, 597), fill=(220, 220, 220), width=2)
        for x in (50, 135, 260, 340, 470, 560):
            draw.line((x, 3, x-70, 155, x+20, 370, x-45, 597), fill=(205, 205, 205), width=12)
    draw.polygon([(200, 300), (300, 175), (420, 300), (300, 425)], outline=(180, 130, 60), width=3)
    for x, colour in [(90, (50, 90, 130)), (480, (70, 110, 160))]:
        draw.polygon([(x-35, 300), (x, 265), (x+35, 300), (x, 335)], fill=colour)
    draw.text((270, 280), 'Good Times', fill='black')
    return image


@pytest.mark.parametrize('textured', [False, True])
@pytest.mark.parametrize('factor', [1, 5])
def test_central_geometric_art_is_not_a_perimeter_sentence(textured, factor):
    image = geometric_source(textured).resize((600*factor, 600*factor))
    layout = analyze_layout(image)
    assert layout.floating_artwork is not None, '中央菱形及文字必须作为完整图案组识别'
    assert not layout.strip_is_sentence, '中央图案不能卷入英文边框'
    assert layout.border_depth_px < 12*factor, '只提取真正的外框，不能扫描到中央图案'
    design = DesignSpec(diameter_cm=139, height_cm=87, shape_mode='arc', straight_cm=108, border=BorderSpec(0, 0, 0))
    native = ContentMapping.source_scale(layout, 139, 87)
    border = max(layout.border_depth_px*native, ContentMapping.required_border(layout, 139, 87))
    mapping = ContentMapping.create(layout, 139, 87, border, create_shape(design))
    assert mapping.scale_cm < native, '中央图案组应整体等比缩小'


@pytest.mark.parametrize('textured', [False, True])
def test_render_preserves_complete_side_diamonds_and_centre(textured, tmp_path):
    path = tmp_path/'geometric.png'
    geometric_source(textured).save(path)
    result = np.asarray(generate(DesignSpec(diameter_cm=139, height_cm=87, dpi=30, shape_mode='arc', straight_cm=108, border=BorderSpec(0, 0, 0), material=MaterialSpec(str(path)))))
    for colour in [(50, 90, 130), (70, 110, 160)]:
        selected = np.max(np.abs(result[..., :3].astype(int)-colour), axis=2) < 3
        rows, columns = np.nonzero(selected)
        assert rows.size, '侧边菱形消失'
        assert columns.max()-columns.min() == pytest.approx(rows.max()-rows.min(), abs=2), '菱形被裁剪，横纵尺寸不一致'
    centre = result[:,result.shape[1]//2,:3]
    gold = (centre[:,0]>130)&(centre[:,1]>80)&(centre[:,2]<100)
    rows = np.flatnonzero(gold)
    assert rows.size >= 2 and rows.max()-rows.min() > result.shape[0]*.3, '中央菱形的上下顶点必须完整保留'


@pytest.mark.parametrize('factor', [1, 5])
def test_pale_triangles_above_central_text_remain_artwork(factor):
    image = Image.open(Path(__file__).with_name('fixtures') / 'pale_geometric_gallery.png').convert('RGB')
    image = image.resize((image.width*factor, image.height*factor))
    layout = analyze_layout(image)
    assert layout.floating_artwork is not None, '顶部浅色三角形不能被误认为局部文字边框'
    assert layout.content_box_px[1] < 12*factor, '三角形必须留在花纹区'


@pytest.mark.parametrize('factor', [1, 5])
def test_square_gallery_with_small_real_side_clearance_fits_entire_group(factor):
    image = Image.new('RGB', (600, 600), (247, 240, 232))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 599, 599), outline='black', width=1)
    colours = [(40, 90, 50), (100, 70, 40), (60, 40, 90)]
    for box, colour in zip([(21, 220, 210, 380), (250, 220, 350, 380), (390, 220, 579, 380)], colours):
        image.paste(colour, box)
    image = image.resize((600*factor, 600*factor))
    layout = analyze_layout(image)
    assert layout.floating_artwork is not None, '四边实际留白充分时，方形素材不能因侧边小于短边5%被拒绝'
    assert layout.border_depth_px < 12*factor, '中央图案不能当作厚外框'
