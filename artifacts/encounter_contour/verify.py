"""Verify the encounter series against the requested curved texture panel."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec
from shape_crop.services.materials import prepare
from shape_crop.core.source_renderer import render_source
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape
from shape_crop.services.export import save_image
from PIL import Image
import numpy as np

root = Path(r'\\192.168.1.199\打印文件\方果图库\成品图\5068663_宁波大魔法（店铺端）')
out = Path(__file__).resolve().parent
for label, name in [('celadon', '双面格-定制-定制尺寸-闲叙・青釉;80x140cm.jpg'),
                    ('encounter', '双面格-定制-定制尺寸-闲叙・邂逅;90x180CM.jpg')]:
    material = prepare(MaterialSpec(str(root / name)), preview=True)
    layout = material.source_layout
    print(label, layout.category, layout.content_box_px, flush=True)
    Image.fromarray(layout.image).save(out / f'{label}-source.png')
    for mode in ('circular', 'arc'):
        for width, height, straight in ((141, 81, 103), (131, 81, 103), (181, 91, 140)):
            design = DesignSpec(diameter_cm=width, height_cm=height, straight_cm=straight,
                                shape_mode=mode, border=BorderSpec(0, 0, 0))
            result = render_source(design, material, max_side=1200)
            frame = layout.contoured_frame
            assert frame is not None
            scale = ContentMapping.source_scale(layout, width, height)
            border = max(layout.border_depth_px * scale, ContentMapping.required_border(layout, width, height))
            inner = create_shape(design).inset(frame.inset_px * scale + border - layout.border_depth_px * scale)
            pixels = np.asarray(result)
            inner_colours, outer_colours = [], []
            for y in np.linspace(-inner.half_height * .7, inner.half_height * .7, 21):
                side = getattr(inner, 'center', 0) + np.sqrt(inner.radius ** 2 - y ** 2)
                row = round((y / height + .5) * result.height - .5)
                for sign in (-1, 1):
                    a = round((sign * (side - 1) / width + .5) * result.width - .5)
                    b = round((sign * (side + 1) / width + .5) * result.width - .5)
                    inside = np.median(pixels[row-2:row+3, a-2:a+3, :3].mean(axis=2))
                    outside = np.median(pixels[row-2:row+3, b-2:b+3, :3].mean(axis=2))
                    inner_colours.append(inside)
                    outer_colours.append(outside)
            assert np.mean(outer_colours) > np.mean(inner_colours) + 20, (label, mode, width, height)
            result.save(out / f'{label}-{mode}-{width}-{height}.png')
            print('Verified:', label, mode, width, height, flush=True)
    if '--full' in sys.argv:
        material = prepare(MaterialSpec(str(root / name)))
        print('Native layout:', label, material.source_layout.category,
              material.source_layout.content_box_px,
              'has_picture', material.source_layout.framed_artwork is not None,
              'has_contour', material.source_layout.contoured_frame is not None, flush=True)
        assert material.source_layout.contoured_frame is not None, '原分辨率分析未启用纹理内框'
        design = DesignSpec(diameter_cm=141, height_cm=81, border=BorderSpec(0, 0, 0))
        result = render_source(design, material)
        for extension in ('jpg', 'png'):
            target = out / f'{label}-full.{extension}'
            save_image(result, target, design.dpi)
            with Image.open(target) as saved:
                assert saved.size == design.pixel_size()
        result.thumbnail((1200, 1200))
        result.save(out / f'{label}-full-preview.png')
        print('Verified native source and JPG/PNG:', label, design.pixel_size(), flush=True)
