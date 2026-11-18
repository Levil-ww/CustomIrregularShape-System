"""Exercise the actual belly workflow and exported physical dimensions."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.models.request import ProductRequest
from shape_crop.services.design_service import generate
from shape_crop.services.workflow import resolve_request


def test_belly_workflow_and_png_export(tmp_path):
    source = tmp_path / '花幔;80x140cm.png'
    im = Image.new('RGB', (700, 400), (250, 249, 239))
    draw = ImageDraw.Draw(im)
    draw.rectangle((18, 18, 681, 381), outline='black', width=3)
    draw.line((18, 155, 681, 155), fill='black', width=2)
    draw.line((18, 245, 681, 245), fill='black', width=2)
    draw.text((300, 190), 'FLOWER', fill='black')
    for x in (80, 180, 300, 450, 620):
        draw.ellipse((x - 20, 30, x + 20, 80), outline='black', width=2)
        draw.line((x - 20, 55, x + 20, 110), fill='black', width=2)
        draw.ellipse((x - 20, 320, x + 20, 370), outline='black', width=2)
    im.save(source)
    request = ProductRequest('花幔;80x140cm', material_override=str(source), dpi=10,
                             shape_mode='belly', width_cm=140, height_cm=80,
                             belly_c_cm=63, belly_d_cm=120, belly_corner_cm=15)
    design, _ = resolve_request(request)
    path = tmp_path / 'result.png'
    preview = generate(design, preview=True)
    result = generate(design, output=path)
    assert result.size == (round(141 * 10 / 2.54), round(81 * 10 / 2.54))
    assert preview.size == result.size
    pixels = np.asarray(result)
    assert pixels[0, 0, 3] == 0
    assert pixels[result.height // 2, result.width // 2, 3] == 255
    def alpha_at(x, y):
        px = round((x / design.diameter_cm + .5) * result.width - .5)
        py = round((y / design.height_cm + .5) * result.height - .5)
        return pixels[py, px, 3]
    # The C endpoints are at y = ±C/2; D endpoints are at x = ±D/2.
    side_x = (design.belly_d_cm + design.belly_corner_cm) / 2
    side_y = -design.belly_c_cm / 2
    assert alpha_at(side_x - .8, side_y) > 240
    assert alpha_at(side_x + .8, side_y) < 15
    top_x = design.belly_d_cm / 2
    top_y = -(design.belly_c_cm + design.belly_corner_cm) / 2
    assert alpha_at(top_x, top_y + .35) > 220
    assert alpha_at(top_x, top_y - .35) < 35
    with Image.open(path) as saved:
        assert saved.mode == 'RGBA'
        assert saved.size == result.size
        assert saved.info['dpi'][0] == pytest.approx(10, abs=.1)


def test_belly_rejects_invalid_dimensions_and_inner_circle(tmp_path):
    common = dict(target_name='花幔;80x140cm', material_override=str(tmp_path / 'unused'),
                  shape_mode='belly', belly_c_cm=63, belly_d_cm=120, belly_corner_cm=15)
    with pytest.raises(ValueError, match='内圆'):
        resolve_request(ProductRequest(**common, inner_diameter_cm=10))
    with pytest.raises(ValueError, match='C 加圆角直径'):
        resolve_request(ProductRequest(**{**common, 'belly_c_cm': 66}))
    with pytest.raises(ValueError, match='必须按输入的 C、D'):
        resolve_request(ProductRequest(**common, belly_reference_approximation=True))


def test_periodic_border_survives_belly_render():
    from shape_crop.core.belly_renderer import render_belly
    from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
    from shape_crop.services.layout_analysis import SourceLayout
    from shape_crop.services.materials import PreparedMaterial
    image = np.full((360, 600, 3), 240, dtype=np.uint8)
    strip = np.full((48, 24, 3), 240, dtype=np.uint8)
    yy, xx = np.mgrid[:48, :24]
    strip[(xx - 12) ** 2 + (yy - 24) ** 2 <= 6 ** 2] = (180, 20, 20)
    layout = SourceLayout(image, strip, 48, 600, 360, '', image[48:-48, 48:-48],
                          (48, 48, 552, 312), strip_period_px=24)
    material = PreparedMaterial(image, strip, MaterialSpec(), layout)
    design = DesignSpec(diameter_cm=121, height_cm=76, dpi=18,
                        border=BorderSpec(0, 0, 0), shape_mode='belly',
                        belly_c_cm=60, belly_d_cm=100, belly_corner_cm=15)
    pixels = np.asarray(render_belly(design, material))
    red = (pixels[..., 0] > 120) & (pixels[..., 1] < 80) & (pixels[..., 3] > 128)
    assert np.count_nonzero(red[:pixels.shape[0] // 3]) > 80, '上边装饰应完整可见'
    assert np.count_nonzero(red[2 * pixels.shape[0] // 3:]) > 80, '下边装饰应完整可见'


def test_belly_outline_antialias_matches_supersampled_coverage(tmp_path):
    from test_huaman_frame import huaman_source
    from shape_crop.core.belly_geometry import BellyOutline
    source = tmp_path / '花幔;80x140cm.png'
    huaman_source().save(source)
    request = ProductRequest('花幔;80x140cm', material_override=str(source), dpi=30,
                             shape_mode='belly', width_cm=140, height_cm=80,
                             belly_c_cm=63, belly_d_cm=125, belly_corner_cm=12)
    design, _ = resolve_request(request)
    output = generate(design, preview=True)
    w, h = output.size
    shape = BellyOutline(design.diameter_cm, design.height_cm, 63, 125, 12)
    n = 4
    reference = Image.new('L', (w * n, h * n))
    ImageDraw.Draw(reference).polygon([((x / shape.width + .5) * w * n - .5,
                                        (y / shape.height + .5) * h * n - .5)
                                       for x, y in shape.points(250)], fill=255)
    expected = np.asarray(reference.resize((w, h), Image.Resampling.BOX), dtype=float)
    actual = np.asarray(output)[..., 3].astype(float)
    edge = (expected > 0) & (expected < 255)
    assert np.abs(actual - expected)[edge].mean() < 30, '透明边缘应按轮廓覆盖率平滑过渡'
