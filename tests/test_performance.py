"""Cache work counts, invalidation and output quality, without flaky time limits."""
from unittest.mock import patch
import os
import numpy as np
import pytest
from PIL import Image
from shape_crop.services.catalog import match_material
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.materials import prepare
from shape_crop.models.design import MaterialSpec
from shape_crop.services.export import save_image
from shape_crop.core.renderer import RenderCancelled


def test_repeated_matching_reuses_scan_and_refreshes_nested_changes(tmp_path):
    nested = tmp_path / 'nested'
    nested.mkdir()
    source = nested / '花幔;80x150cm.jpg'
    source.touch()
    target = parse_filename('花幔;80x140cm')
    from shape_crop.services import catalog
    with patch.object(catalog.os, 'walk', wraps=os.walk) as walk:
        assert match_material(target, tmp_path).path == str(source)
        assert match_material(target, tmp_path).path == str(source)
        assert walk.call_count == 1
        exact = nested / '花幔;80x140cm.jpg'
        exact.touch()
        assert match_material(target, tmp_path).path == str(exact)
        exact.unlink()
        assert match_material(target, tmp_path).path == str(source)
        new_folder = nested / 'new'
        new_folder.mkdir()
        new_exact = new_folder / exact.name
        new_exact.touch()
        assert match_material(target, tmp_path).path == str(new_exact)
        new_exact.rename(new_folder / '别的花;80x140cm.jpg')
        assert match_material(target, tmp_path).path == str(source)
        with pytest.raises(RenderCancelled):
            match_material(target, tmp_path, cancelled=lambda: True)


def test_prepared_source_reused_between_preview_and_export_and_refreshed(tmp_path):
    from shape_crop.services import materials
    path = tmp_path / 'source.png'
    Image.new('RGB', (80, 40), 'red').save(path)
    spec = MaterialSpec(path=str(path))
    with patch.object(materials, 'analyze_layout', wraps=materials.analyze_layout) as analyze:
        preview = prepare(spec, True)
        full = prepare(spec, False)
        assert preview is full
        assert not full.content.flags.writeable
        assert analyze.call_count == 1
        Image.new('RGB', (90, 45), 'blue').save(path)
        refreshed = prepare(spec)
        assert refreshed.source_layout.width_px == 90
        assert analyze.call_count == 2
        path.unlink()
        with pytest.raises(FileNotFoundError):
            prepare(spec)


def test_png_export_preserves_rgba_and_dpi(tmp_path):
    image = Image.fromarray(np.random.default_rng(3).integers(0, 256, (50, 80, 4), dtype=np.uint8))
    path = tmp_path / 'export.png'
    save_image(image, path, 150)
    with Image.open(path) as exported:
        np.testing.assert_array_equal(np.asarray(exported), np.asarray(image))
        assert exported.info['dpi'][0] == pytest.approx(150, abs=.02)
    assert not list(tmp_path.glob('.shape-*'))


def test_export_progress_finishes_only_after_file_is_saved(tmp_path):
    from shape_crop.services.design_service import generate
    from shape_crop.models.design import DesignSpec
    from shape_crop.services import design_service
    progress, statuses, timings = [], [], {}
    output = tmp_path / 'output.jpg'
    def save(*args):
        assert progress[-1] < 100
        save_image(*args)
    with patch.object(design_service, 'save_image', side_effect=save):
        generate(DesignSpec(diameter_cm=20, height_cm=20, dpi=20), output=output,
                 progress=progress.append, status=statuses.append, timings=timings)
    assert output.is_file()
    assert progress[-1] == 100
    assert progress == sorted(progress)
    assert '保存' in statuses[-1]
    assert set(timings) == {'prepare', 'render', 'save'}
    assert all(value >= 0 for value in timings.values())


def test_float32_sampling_stays_within_one_channel_level():
    from shape_crop.core.sampling import sample
    rng = np.random.default_rng(17)
    image = rng.integers(0, 256, (73, 91, 3), dtype=np.uint8)
    for wrap in (False, True):
        x = rng.uniform(-150, 150, (1, 200)).astype(np.float32)
        y = rng.uniform(-120, 120, (150, 1)).astype(np.float32)
        actual = sample(image, x, y, wrap, wrap)
        x = x % 91 if wrap else np.clip(x, 0, 90)
        y = y % 73 if wrap else np.clip(y, 0, 72)
        x0, y0 = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
        x1 = (x0 + 1) % 91 if wrap else np.minimum(x0 + 1, 90)
        y1 = (y0 + 1) % 73 if wrap else np.minimum(y0 + 1, 72)
        fx, fy = (x - x0)[..., None], (y - y0)[..., None]
        a = image[y0, x0].astype(np.float32) * (1 - fx) + image[y0, x1] * fx
        b = image[y1, x0].astype(np.float32) * (1 - fx) + image[y1, x1] * fx
        reference = np.clip(a * (1 - fy) + b * fy, 0, 255).astype(np.uint8)
        assert np.abs(actual.astype(int) - reference.astype(int)).max() <= 1


@pytest.mark.parametrize('shape_mode', ['circular', 'arc'])
@pytest.mark.parametrize('side_border', [20, 40])
def test_source_border_only_samples_covered_pixels_and_matches_dense_render(shape_mode, side_border):
    from shape_crop.core import source_renderer
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import create_shape, inset_boundary_fraction
    from shape_crop.core.renderer import blend
    from shape_crop.core.sampling import sample_perimeter_strip, uniform_strip_band
    from shape_crop.models.design import DesignSpec, BorderSpec
    from shape_crop.services.layout_analysis import SourceLayout
    from shape_crop.services.materials import PreparedMaterial

    pixels = np.random.default_rng(19).integers(0, 256, (240, 400, 3), dtype=np.uint8)
    strip = pixels[:20, :100].copy()
    strip[4:12] = 240
    layout = SourceLayout(pixels, strip, 20, 400, 240, '',
                          pixels[20:-20, side_border:-side_border],
                          (side_border, 20, 400 - side_border, 220), 100)
    material = PreparedMaterial(pixels, strip, MaterialSpec(), layout)
    design = DesignSpec(diameter_cm=40, height_cm=24, dpi=30,
                        border=BorderSpec(0, 0, 0), shape_mode=shape_mode, straight_cm=30)
    width, height = design.pixel_size()
    x = ((np.arange(width, dtype=np.float32) + .5) / width - .5)[None, :] * 40
    y = ((np.arange(height, dtype=np.float32) + .5) / height - .5)[:, None] * 24
    shape = create_shape(design)
    depth = shape.depth(x, y)
    scale = ContentMapping.source_scale(layout, 40, 24)
    native_border = layout.border_depth_px * scale
    border = max(native_border, ContentMapping.required_border(layout, 40, 24))
    extra = border - native_border
    plain_band = uniform_strip_band(strip) if extra else None
    px_cm = max(40 / width, 24 / height)
    ornament = np.max(np.ptp(strip, axis=1), axis=1).astype(np.float64)
    source_depth = float(np.average(np.arange(len(ornament)) + .5, weights=ornament))
    ring_depth = source_depth * scale
    if plain_band and source_depth >= plain_band[1]:
        ring_depth += extra
    ring = shape.inset(ring_depth)
    arc = inset_boundary_fraction(shape, x, y, np.clip(depth, 0, border), ring) * ring.perimeter
    expected = ContentMapping.create(layout, 40, 24, border).sample(layout, x, y)
    sample_depth = depth
    if plain_band:
        start, end = (value * scale for value in plain_band)
        sample_depth = np.where(depth < start, depth,
                               np.where(depth < end + extra,
                                        start + (depth - start) * (end - start) / (end - start + extra),
                                        depth - extra))
    stripe = sample_perimeter_strip(strip, arc, np.maximum(0, sample_depth / scale - .5),
                                    ring.perimeter, scale, (100 - ring.chord / scale) / 2)
    blend(expected, stripe, np.clip((border - depth) / px_cm + .5, 0, 1))
    sampled_pixels = []

    def counted_sample(image, arc_length, *args):
        sampled_pixels.append(arc_length.size)
        return sample_perimeter_strip(image, arc_length, *args)

    with patch.object(source_renderer, 'sample_perimeter_strip', side_effect=counted_sample):
        actual = np.asarray(source_renderer.render_source(design, material))
    np.testing.assert_array_equal(actual[..., :3], expected)
    np.testing.assert_array_equal(actual[..., 3],
                                  np.round(np.clip(depth / px_cm + .5, 0, 1) * 255).astype(np.uint8))
    assert sum(sampled_pixels) == np.count_nonzero(depth < border + px_cm / 2), '只计算实际覆盖的边框像素'
