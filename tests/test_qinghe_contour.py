"""The dark Qinghe inset and its outline follow the finished contour."""
from pathlib import Path
import numpy as np
import pytest
from shape_crop.models.design import MaterialSpec, DesignSpec, BorderSpec
from shape_crop.services.materials import prepare
from shape_crop.core.source_renderer import render_source


@pytest.mark.parametrize("fixture", ["qinghe.jpg", "qinghe_80x140.png", "qinghe_55x60.png"])
def test_qinghe_dark_pattern_follows_arc_and_keeps_outline(tmp_path, fixture):
    path = tmp_path / 'double-custom-\u9752\u79be\u56db\u9526;90x150CM.jpg'
    path.write_bytes((Path(__file__).parent / 'fixtures' / fixture).read_bytes())
    material = prepare(MaterialSpec(str(path)), preview=True)
    assert material.source_layout.contoured_frame is not None
    for mode in ('arc', 'circular'):
        design = DesignSpec(diameter_cm=135, height_cm=86, straight_cm=104, shape_mode=mode, border=BorderSpec(0, 0, 0))
        result = np.asarray(render_source(design, material, max_side=800))
        green = (result[:, :, 1] > result[:, :, 0] + 3) & (result[:, :, 0] < 180)
        middle = np.flatnonzero(green[result.shape[0] // 2])
        upper = np.flatnonzero(green[result.shape[0] // 4])
        assert middle[0] < upper[0] - 10 and middle[-1] > upper[-1] + 10
        dark = np.max(result[:, :, :3], axis=2) < 60
        assert dark[result.shape[0] // 2, middle[0] - 4:middle[0]].any()





def test_vertical_qinghe_filename_keeps_curved_inset(tmp_path):
    path = tmp_path / 'mirror-custom-\u9752\u79be\u56db\u9526;\u65b9\u5f62\u7ad6\u7248100x110CM.jpg'
    path.write_bytes((Path(__file__).parent / 'fixtures' / 'qinghe_vertical.png').read_bytes())
    material = prepare(MaterialSpec(str(path)), preview=True)
    assert material.source_layout.contoured_frame is not None
