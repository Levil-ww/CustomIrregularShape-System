"""Filled dot bands must not acquire blank slivers at contour joints."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape, clipped_boundary_coordinate
from shape_crop.core.sampling import sample_perimeter_strip
from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
from shape_crop.services.layout_analysis import SourceLayout
from shape_crop.services.materials import PreparedMaterial


def dot_strip():
    image = Image.new('RGB', (48, 100), (248, 235, 210))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 47, 7), fill=(170, 150, 120))
    draw.rectangle((0, 92, 47, 99), fill=(170, 150, 120))
    draw.ellipse((12, 49, 36, 73), fill=(170, 150, 120))
    for x in (4, 44):
        for y in (43, 79):
            draw.ellipse((x-3, y-3, x+3, y+3), fill=(170, 150, 120))
    return np.asarray(image)


@pytest.mark.parametrize('mode', ['arc', 'circular'])
@pytest.mark.parametrize('size', [(154,80,100)])
def test_dot_ink_is_not_erased_at_four_joints(mode, size):
    strip = dot_strip()
    pixels = np.full((700, 1500, 3), 220, dtype=np.uint8)
    layout = SourceLayout(pixels, strip, 100, 1500, 700, '',
                          pixels[100:-100,100:-100], (100,100,1400,600),48)
    material = PreparedMaterial(pixels, strip, MaterialSpec(), layout)
    w,h,straight = size
    design = DesignSpec(diameter_cm=w,height_cm=h,straight_cm=straight,
                        shape_mode=mode,border=BorderSpec(0,0,0))
    rendered = np.asarray(render_source(design,material,max_side=2400))
    scale = ContentMapping.source_scale(layout,w,h)
    weights = np.max(np.ptp(strip,axis=1),axis=1)
    ring = create_shape(design).inset(float(np.average(np.arange(100)+.5,weights=weights))*scale)
    yy,xx = np.indices(rendered.shape[:2])
    x,y = ((xx+.5)/rendered.shape[1]-.5)*w,((yy+.5)/rendered.shape[0]-.5)*h
    depth = create_shape(design).depth(x,y)
    coordinate,valid = clipped_boundary_coordinate(create_shape(design),x,y,ring)
    source_depth = depth/scale-.5
    selected = ~valid & (source_depth>50) & (source_depth<72)
    expected = sample_perimeter_strip(strip,coordinate[selected],source_depth[selected],
        ring.perimeter,scale,(strip.shape[1]-ring.chord/scale)/2)
    ink = np.max(expected,axis=1)<200
    assert np.count_nonzero(ink)>0, '必须覆盖被旧规则裁掉的实心圆点'
    np.testing.assert_allclose(rendered[selected,:3][ink],expected[ink],atol=1,
                               err_msg='实心圆点被转角留白切出白色竖线')
