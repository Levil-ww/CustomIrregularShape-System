from dataclasses import replace
import threading
import numpy as np
import pytest
from PIL import Image
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec, CropBox
from shape_crop.core.renderer import render, RenderCancelled
from shape_crop.services.materials import prepare
from shape_crop.services.design_service import generate
from shape_crop.services.project_io import save_project, load_project
from shape_crop.services.export import save_image


def small_design(**changes):
    return replace(DesignSpec(diameter_cm=20, height_cm=8.376, dpi=50,
                              border=BorderSpec(.35, .25, .01)), **changes)


def test_nominal_pixel_size():
    assert DesignSpec().pixel_size() == (11811, 4946)
    assert DesignSpec().pixel_size(1200) == (1200, 503)


@pytest.mark.parametrize('changes', [dict(height_cm=201), dict(height_cm=float('nan')),
    dict(inner_diameter_cm=80), dict(border=BorderSpec(40, 3, .1)), dict(dpi=0),
    dict(border=BorderSpec(0, 0, .1)), dict(inner_diameter_cm=40, inner_border_cm=20)])
def test_invalid_design(changes):
    with pytest.raises(ValueError):
        replace(DesignSpec(), **changes).validate()


def test_shape_alpha_is_symmetric_and_chunk_size_independent():
    design = small_design()
    image = render(design, block_rows=11)
    other = render(design, block_rows=23)
    np.testing.assert_array_equal(np.asarray(image), np.asarray(other))
    alpha = np.asarray(image)[..., 3]
    np.testing.assert_allclose(alpha, alpha[::-1, ::-1], atol=1)
    assert alpha[0, 0] == 0
    assert alpha[alpha.shape[0] // 2, alpha.shape[1] // 2] == 255


def test_material_reconstruction_and_independent_inner_fill(tmp_path):
    # The source has a red decorative strip and blue central content.
    source = Image.new('RGB', (120, 80), (0, 0, 255))
    source.paste((255, 0, 0), (0, 0, 120, 20))
    path = tmp_path / '素材.png'
    source.save(path)
    material = MaterialSpec(path=str(path), layout='manual', content_box=CropBox(0, .25, 1, 1), strip_box=CropBox(0, 0, 1, .25))
    design = small_design(material=material)
    pixels = np.asarray(generate(design))
    center = pixels.shape[0] // 2, pixels.shape[1] // 2
    np.testing.assert_array_equal(pixels[center][:3], [0, 0, 255])
    # Right arc carries the source red strip, rather than old rectangular borders.
    column = round((20 - .475) / 20 * pixels.shape[1] - .5)
    np.testing.assert_array_equal(pixels[center[0], column, :3], [255, 0, 0])
    inner_path = tmp_path / '内圆.png'
    Image.new('RGB', (80, 80), (0, 255, 0)).save(inner_path)
    inner = replace(material, path=str(inner_path))
    spec = replace(design, inner_diameter_cm=5, inner_border_cm=.25, inner_material=inner)
    result = np.asarray(generate(spec))
    np.testing.assert_array_equal(result[center][:3], [0, 255, 0])
    outside_inner = center[0], round(result.shape[1] * .7)
    np.testing.assert_array_equal(result[outside_inner][:3], [0, 0, 255])


def test_full_circle_transparency_matches_radius():
    design = small_design(height_cm=20)
    result = np.asarray(render(design))
    assert result.shape[0] == result.shape[1]
    assert result[0, 0, 3] == 0
    assert result[result.shape[0] // 2, 0, 3] > 200


def test_json_round_trip_relative_material_and_unicode(tmp_path):
    source = tmp_path / '蔓生花.png'
    Image.new('RGB', (20, 20)).save(source)
    design = small_design(material=MaterialSpec(str(source)))
    path = tmp_path / '设计.json'
    save_project(path, design)
    loaded = load_project(path)
    assert loaded == design
    assert '蔓生花.png' in path.read_text(encoding='utf-8')


def test_png_jpg_dimensions_alpha_and_dpi(tmp_path):
    image = render(small_design())
    for suffix in ('.png', '.jpg'):
        path = tmp_path / ('输出' + suffix)
        save_image(image, path, 50)
        with Image.open(path) as result:
            assert result.size == image.size
            assert result.info['dpi'][0] == pytest.approx(50, abs=.05)
            if suffix == '.png':
                assert result.mode == 'RGBA'
                assert result.getpixel((0, 0))[3] == 0
            else:
                assert all(c >= 245 for c in result.getpixel((0, 0)))
    assert not list(tmp_path.glob('.shape-*'))


def test_cancellation_and_progress():
    progress = []
    with pytest.raises(RenderCancelled):
        render(small_design(), cancelled=lambda: True)
    render(small_design(), progress=progress.append)
    assert progress[-1] == 100
    assert progress == sorted(progress)


def test_failed_export_does_not_replace_existing_file(tmp_path):
    path = tmp_path / '输出.png'
    path.write_bytes(b'existing')
    class BrokenImage:
        def save(self, *args, **kwargs):
            raise OSError('simulated write failure')
    with pytest.raises(OSError):
        save_image(BrokenImage(), path, 50)
    assert path.read_bytes() == b'existing'
    assert not list(tmp_path.glob('.shape-*'))


def test_preview_export_uses_effective_dpi(tmp_path):
    path = tmp_path / '预览.png'
    generate(DesignSpec(), preview=True, output=path)
    with Image.open(path) as image:
        assert image.info['dpi'][0] == pytest.approx(1200 / 200 * 2.54, abs=.05)
