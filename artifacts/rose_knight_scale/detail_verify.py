"""Verify the exact rose knight order and export source-resolution results."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from PIL import Image
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.materials import prepare
from shape_crop.services.export import save_image
from shape_crop.core.source_renderer import render_source
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape

out = Path(__file__).resolve().parent
source = Path(r'\\192.168.1.199\打印文件\方果图库\成品图\5068663_宁波大魔法（店铺端）') / '双面格-定制-定制尺寸-玫瑰骑士;85x135cm.jpg'
reference = None
for preview in (True, False):
    material = prepare(MaterialSpec(str(source)), preview=preview)
    layout = material.source_layout
    panel = layout.inset_panel
    assert panel.translucent is not None
    a, b, c, d = panel.translucent[0]
    left, top, right, bottom = panel.box
    assert a < left < right < c and b < top < bottom < d
    assert panel.stroke_repeat_px > 0
    coordinates = np.array(panel.translucent[0]) / np.array([layout.width_px, layout.height_px]*2)
    if reference is None:
        reference = coordinates
    else:
        np.testing.assert_allclose(coordinates, reference, atol=.002)
    for w, h, straight in ((130, 85, 99), (104, 65.5, 79), (181, 86, 105.2)):
        design = DesignSpec(diameter_cm=w, height_cm=h, straight_cm=straight,
                            shape_mode='arc', border=BorderSpec(0, 0, 0))
        result = render_source(design, material, max_side=1200)
        assert result.width == 1200
        scale = ContentMapping.source_scale(layout, w, h)
        u = (((np.arange(result.width)+.5)/result.width-.5)*w/scale+(layout.width_px-1)/2)[None,:]
        v = (((np.arange(result.height)+.5)/result.height-.5)*h/scale+(layout.height_px-1)/2)[:,None]
        radius = max(3., 2*panel.translucent[3])
        band = np.zeros((result.height,result.width), dtype=bool)
        for fa,fb,fc,fd in (panel.box,panel.translucent[0]):
            band |= (np.minimum(abs(u-fa),abs(u-fc)) <= radius) & (v >= fb-radius) & (v <= fd+radius)
            band |= (np.minimum(abs(v-fb),abs(v-fd)) <= radius) & (u >= fa-radius) & (u <= fc+radius)
        delta = np.asarray(result)[...,:3].astype(float)-np.array(panel.translucent[2])
        white = band & (np.min(delta,axis=2) >= 0) & (np.max(delta,axis=2) > 3) & (np.ptp(delta,axis=2) <= 6)
        border = max(layout.border_depth_px*scale, ContentMapping.required_border(layout,w,h))
        x, y = (u-(layout.width_px-1)/2)*scale, (v-(layout.height_px-1)/2)*scale
        white &= create_shape(design).depth(x,y) > border+2*w/result.width
        assert not np.any(white), '原矩形边界仍有过亮白线'
        result.save(out / f'detail-{w}-{h}-{"preview" if preview else "native"}.png')
        print('Verified:', preview, w, h, straight, flush=True)
    if not preview:
        design = DesignSpec(diameter_cm=130, height_cm=85, straight_cm=99,
                            shape_mode='arc', border=BorderSpec(0, 0, 0))
        result = render_source(design, material)
        for suffix in ('jpg', 'png'):
            path = out / f'detail-130-85-full.{suffix}'
            save_image(result, path, design.dpi)
            with Image.open(path) as saved:
                assert saved.size == design.pixel_size()
        result.thumbnail((1200, 1200))
        result.save(out / 'detail-130-85-full-preview.png')
        print('Verified full JPG/PNG:', design.pixel_size(), flush=True)
