"""User regression: original black edge, inner separator and motif scale survive."""
from dataclasses import replace
import numpy as np
from PIL import Image
from shape_crop.models.design import DesignSpec, MaterialSpec
from shape_crop.services.design_service import generate


def test_original_border_layers_are_not_replaced_or_hidden(tmp_path):
    source = Image.new('RGB', (400, 240), (210, 195, 160))
    source.paste((0, 0, 0), (0, 0, 400, 2))
    source.paste((250, 235, 205), (2, 2, 398, 238))
    source.paste((160, 140, 105), (20, 20, 380, 220))
    source.paste((245, 225, 190), (23, 23, 377, 217))
    source.paste((170, 145, 110), (32, 32, 368, 208))
    source.paste((250, 230, 195), (35, 35, 365, 205))
    source.paste((100, 130, 155), (38, 38, 362, 202))
    # Floral stand-in, keeps border detection from confusing a solid fill with a border.
    texture = np.asarray(source).copy()
    rng = np.random.default_rng(13)
    texture[38:202, 38:362] = rng.integers(70, 235, (164, 324, 3), dtype=np.uint8)
    source = Image.fromarray(texture)
    path = tmp_path / '双面格-定制-定制尺寸-花幔;24X40CM.jpg'
    source.save(path, quality=100, subsampling=0)
    design = replace(DesignSpec(), diameter_cm=40, height_cm=24, dpi=25,
                     material=MaterialSpec(str(path)))
    output = np.asarray(generate(design))
    center_x = output.shape[1] // 2
    assert max(output[0, center_x, :3]) < 30, '原素材最外层黑线被替换'
    # All original separators should remain at their scaled depths, no generic lines.
    row = round(33.5 / 240 * output.shape[0] - .5)
    assert np.linalg.norm(output[row, center_x, :3].astype(float) - [170, 145, 110]) < 40


def test_flower_size_uses_outer_rectangle_scale_not_content_cover(tmp_path):
    source = Image.new('RGB', (400, 240), (245, 230, 190))
    source.paste((0, 0, 0), (0, 0, 400, 2))
    source.paste((200, 170, 120), (22, 22, 378, 218))
    source.paste((240, 220, 185), (25, 25, 375, 215))
    source.paste((180, 150, 110), (30, 30, 370, 210))
    pixels = np.asarray(source).copy()
    pixels[34:206, 34:366] = np.random.default_rng(9).integers(150, 220, (172, 332, 3), dtype=np.uint8)
    # A 20 source-pixel motif must remain 2 cm at the output's physical scale.
    pixels[80:160, 100:120] = [255, 0, 0]
    path = tmp_path / 'motif.png'
    Image.fromarray(pixels).save(path)
    design = replace(DesignSpec(), diameter_cm=40, height_cm=24, dpi=50, material=MaterialSpec(str(path)))
    result = np.asarray(generate(design))
    row = result[result.shape[0] // 2, :, :3]
    red = (row[:, 0] > 240) & (row[:, 1] < 10) & (row[:, 2] < 10)
    width_cm = np.count_nonzero(red) / result.shape[1] * 40
    assert abs(width_cm - 2) < .15, '中央花纹被裁切后单独放大'
