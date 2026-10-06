from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from shape_crop.models.request import ProductRequest
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.workflow import resolve_request, output_path
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.core.renderer import RenderCancelled


def test_customer_filename_compensation_and_exact_output_name(tmp_path):
    name = '双面格-定制-裁剪有图-花幔;80X140cm裁剪有图'
    parsed = parse_filename(name + '.jpg')
    assert (parsed.width_cm, parsed.height_cm, parsed.pattern) == (140, 80, '花幔')
    spec, _ = resolve_request(ProductRequest(name, material_override='material.jpg'))
    assert (spec.diameter_cm, spec.height_cm) == (141, 81)
    assert Path(output_path(ProductRequest(name), tmp_path)).name == name + '.jpg'


@pytest.mark.parametrize('name', ['花幔;140×80CM.png', '花幔；８０Ｘ１４０cm', '花幔;80x140cm裁剪有图'])
def test_filename_variants(name):
    assert parse_filename(name).width_cm == 140
    assert parse_filename(name).height_cm == 80


def test_catalog_prioritizes_pattern_material_then_ratio_then_size(tmp_path):
    names = ['双面格-定制-定制尺寸-花幔;80X140CM.jpg',
             '双面格-定制-定制尺寸-花幔;40X70CM.jpg',
             '双面格-定制-定制尺寸-花幔;80X150CM.jpg',
             '双面格-定制-定制尺寸-别的花;80X140CM.jpg',
             '其他材质-定制-定制尺寸-花幔;80X140CM.jpg',
             '双面格-定制-裁剪有图-花幔;80X140CM.jpg']
    for name in names:
        Image.new('RGB', (70, 40)).save(tmp_path / name)
    design, _ = resolve_request(ProductRequest('双面格-定制-裁剪有图-花幔;80X140cm裁剪有图', str(tmp_path)))
    assert Path(design.material.path).name == names[0]
    with pytest.raises(ValueError, match='未找到'):
        resolve_request(ProductRequest('双面格-定制-裁剪有图-不存在;80X140CM', str(tmp_path)))
    with pytest.raises(RenderCancelled):
        resolve_request(ProductRequest('双面格-定制-裁剪有图-花幔;80X140CM', str(tmp_path)), cancelled=lambda: True)


def test_original_complete_strip_includes_all_separators():
    pixels = np.full((200, 350, 3), 240, dtype=np.uint8)
    pixels[:2] = 0
    pixels[12:15] = [160, 140, 100]
    pixels[15:23, ::3] = 100
    pixels[23:25] = [160, 140, 100]
    pixels[25:28] = [250, 230, 200]
    pixels[28:] = np.random.default_rng(7).integers(50, 235, (172, 350, 3), dtype=np.uint8)
    layout = analyze_layout(Image.fromarray(pixels))
    assert layout.border_depth_px == 28
    np.testing.assert_array_equal(layout.strip[0, 0], [0, 0, 0])
    np.testing.assert_array_equal(layout.strip[-1, 0], [250, 230, 200])
