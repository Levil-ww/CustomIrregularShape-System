"""Periodic perimeter ticks remain a frame around a completely plain centre."""
import numpy as np
import pytest
from PIL import Image

from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial


def empty_striped_source(factor):
    pixels = np.full((800, 1200, 3), (250, 244, 230), dtype=np.uint8)
    pixels[:2] = pixels[-2:] = 0
    pixels[:, :2] = pixels[:, -2:] = 0
    for x in range(90, 1110, 22):
        pixels[30:62, x:x+8] = (200, 190, 174)
        pixels[738:770, x:x+8] = (200, 190, 174)
    for y in range(62, 738, 18):
        pixels[y:y+7, 38:74] = (200, 190, 174)
        pixels[y:y+7, 1126:1162] = (200, 190, 174)
    return Image.fromarray(pixels).resize((1200*factor, 800*factor), Image.Resampling.NEAREST)


@pytest.mark.parametrize('factor', [1, 3])
@pytest.mark.parametrize('mode', ['arc', 'circular'])
def test_empty_centre_does_not_discard_verified_periodic_frame(factor, mode):
    layout = analyze_layout(empty_striped_source(factor))
    assert 61*factor <= layout.border_depth_px <= 64*factor, '纯色中央使已识别的虚线边框宽度归零'
    assert layout.strip_period_px > 0, '虚线装饰没有保留在边框条带中'
    design = DesignSpec(diameter_cm=134, height_cm=86, straight_cm=103,
                        shape_mode=mode, dpi=15, border=BorderSpec(0, 0, 0))
    result = np.asarray(render_source(design,
        PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout), max_side=1200))
    np.testing.assert_allclose(result[result.shape[0]//2, result.shape[1]//2, :3],
                               (250, 244, 230), atol=1)
    # Top ticks survive rather than bypassing coverage by discarding the frame.
    assert np.max(np.std(result[:70, result.shape[1]//3:2*result.shape[1]//3, :3], axis=1)) > 8
