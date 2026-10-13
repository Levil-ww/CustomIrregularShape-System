"""Compare rose knight panel mapping across source sizes."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import Image
from shape_crop.services.materials import prepare
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.core.source_renderer import render_source
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape
from shape_crop.core.sampling import sample
from shape_crop.services.export import save_image
import numpy as np

root = Path(r'\\192.168.1.199\打印文件\方果图库\成品图\5068663_宁波大魔法（店铺端）')
out = Path(__file__).resolve().parent
for label, name in [('large', '双面格-定制-定制尺寸-玫瑰骑士;90X200CM.jpg'),
                    ('small', '双面格-标准-80x140-玫瑰骑士;80x140.jpg')]:
    material = prepare(MaterialSpec(str(root / name)), preview=True)
    layout = material.source_layout
    reference_bounds = np.asarray(layout.content_box_px) / np.array([layout.width_px, layout.height_px]*2)
    print(label, layout.category, layout.content_box_px, 'panel', layout.inset_panel, flush=True)
    Image.fromarray(layout.image).save(out / f'{label}-source.png')
    for preview in ((True, False) if '--full' in sys.argv else (True,)):
        if not preview:
            material = prepare(MaterialSpec(str(root / name)))
            layout = material.source_layout
            print('Native:', label, layout.content_box_px, layout.border_depth_px,
                  layout.inset_panel.translucent, flush=True)
            np.testing.assert_allclose(np.asarray(layout.content_box_px)/np.array([layout.width_px,layout.height_px]*2),
                                       reference_bounds, atol=.003, err_msg='原分辨率边框识别与预览不一致')
        assert layout.inset_panel.translucent is not None
        for mode in ('arc', 'circular'):
            for width, height, straight in ((181, 86, 105.2), (141, 81, 103), (105, 66.5, 82)):
                if '--layout-only' in sys.argv:
                    continue
                spec = DesignSpec(diameter_cm=width, height_cm=height, straight_cm=straight,
                                  shape_mode=mode, border=BorderSpec(0, 0, 0))
                result = render_source(spec, material, max_side=1200)
                scale = ContentMapping.source_scale(layout, width, height)
                border = max(layout.border_depth_px * scale, ContentMapping.required_border(layout, width, height))
                left, top, right, bottom = layout.inset_panel.box
                a, b, c, d = layout.content_box_px
                inset = border + ((top-b)+(d-bottom))/2/(d-b)*(height-2*border)
                shape = create_shape(spec)
                inner = shape.inset(inset)
                x = ((np.arange(result.width)+.5)/result.width-.5)[None, :] * width
                y = ((np.arange(result.height)+.5)/result.height-.5)[:, None] * height
                u, v = x/scale+(layout.width_px-1)/2, y/scale+(layout.height_px-1)/2
                expected = sample(layout.image, u, v)
                fa, fb, fc, fd = layout.inset_panel.translucent[0]
                margin = max(layout.inset_panel.translucent[3] + 5,
                             min(layout.width_px, layout.height_px)*.04 + 5)
                unchanged = ((u < fa-margin) | (u > fc+margin) | (v < fb-margin) | (v > fd+margin))
                safe = unchanged & (inner.depth(x,y) < -2*width/result.width) & (shape.depth(x,y) > border+2*width/result.width)
                assert np.count_nonzero(safe) > 100, (label, preview, mode, width, height, border, inset)
                np.testing.assert_allclose(np.asarray(result)[..., :3][safe], expected[safe], atol=1,
                                           err_msg='外层花纹不再符合统一源图坐标')
                result.save(out / f'{label}-{mode}-{width}-{height}-{"preview" if preview else "native"}.png')
                print('Verified uniform artwork:', label, preview, mode, width, height, flush=True)
        if not preview and '--layout-only' not in sys.argv:
            spec = DesignSpec(diameter_cm=181, height_cm=86, straight_cm=105.2,
                              shape_mode='arc', border=BorderSpec(0, 0, 0))
            result = render_source(spec, material)
            for extension in ('jpg', 'png'):
                target = out / f'{label}-full.{extension}'
                save_image(result, target, spec.dpi)
                with Image.open(target) as saved:
                    assert saved.size == spec.pixel_size()
            result.thumbnail((1200, 1200))
            result.save(out / f'{label}-full-preview.png')
            print('Verified JPG/PNG export:', label, spec.pixel_size(), flush=True)
