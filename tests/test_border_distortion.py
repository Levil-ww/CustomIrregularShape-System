"""Circular border ornaments must not be sheared along straight frame sections."""
import numpy as np
import pytest

from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.layout_analysis import SourceLayout
from shape_crop.services.materials import PreparedMaterial


@pytest.mark.parametrize('side_border', [48, 100])
@pytest.mark.parametrize('shape_mode', ['circular', 'arc'])
def test_border_dots_remain_round_and_keep_size(side_border, shape_mode):
    # A single red circle per actual repeating source period.
    yy, xx = np.mgrid[:48, :24]
    strip = np.full((48, 24, 3), 240, dtype=np.uint8)
    strip[(xx - 12) ** 2 + (yy - 32) ** 2 <= 6 ** 2] = (255, 0, 0)
    image = np.full((360, 600, 3), 240, dtype=np.uint8)
    layout = SourceLayout(image, strip, 48, 600, 360, '',
                          image[48:-48, side_border:-side_border],
                          (side_border, 48, 600 - side_border, 312), 24)
    material = PreparedMaterial(image, strip, MaterialSpec(), layout)
    design = DesignSpec(diameter_cm=60, height_cm=36, dpi=100,
                        border=BorderSpec(0, 0, 0), shape_mode=shape_mode,
                        straight_cm=44 if shape_mode == 'arc' else 0)
    result = np.asarray(render_source(design, material))
    # Inspect one dot on the left of the top straight band, away from the joint.
    red = (result[..., 0] > 250) & (result[..., 1] < 15)
    rows, columns = np.nonzero(red)
    top_left = (rows < 11 / 36 * len(result)) & (columns > .2 * result.shape[1]) & (
        columns < .35 * result.shape[1])
    rows, columns = rows[top_left], columns[top_left]
    # Separate horizontally spaced dots and select a complete central one.
    occupied = np.unique(columns)
    groups = np.split(occupied, np.flatnonzero(np.diff(occupied) > 1) + 1)
    group = groups[len(groups) // 2]
    selected = (columns >= group[0]) & (columns <= group[-1])
    covariance = np.cov(np.array([columns[selected], rows[selected]]))
    eigenvalues = np.linalg.eigvalsh(covariance)
    axis_ratio = np.sqrt(eigenvalues[-1] / eigenvalues[0])
    assert axis_ratio < 1.1, f'原素材圆点变成倾斜椭圆，长短轴比 {axis_ratio:.3f}'
    # A wider safety frame must expand blank background, not the 12px ornament.
    diameter_cm = (rows[selected].max() - rows[selected].min() + 1) * 36 / len(result)
    assert abs(diameter_cm - 1.2) < .15, f'圆点被径向放大至 {diameter_cm:.3f}cm'
    # The side arc must preserve roundness too, away from the miter joint.
    rows, columns = np.nonzero(red)
    side = (columns > .8 * result.shape[1]) & (rows > .4 * len(result)) & (rows < .6 * len(result))
    rows, columns = rows[side], columns[side]
    occupied = np.unique(rows)
    groups = np.split(occupied, np.flatnonzero(np.diff(occupied) > 1) + 1)
    group = groups[len(groups) // 2]
    selected = (rows >= group[0]) & (rows <= group[-1])
    eigenvalues = np.linalg.eigvalsh(np.cov(np.array([columns[selected], rows[selected]])))
    assert np.sqrt(eigenvalues[-1] / eigenvalues[0]) < 1.1, '侧弧上的圆点发生变形'
