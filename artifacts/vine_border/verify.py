"""Inspect the original vine frame at changing dimensions."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from PIL import Image
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.materials import prepare
from shape_crop.core.source_renderer import render_source
from shape_crop.core.round_rings import recognize_round_ring
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.sampling import uniform_strip_band
from shape_crop.services.export import save_image

directory = Path(__file__).resolve().parent
source = (r'\\192.168.1.199\打印文件\方果图库\成品图\5068663_宁波大魔法（店铺端）'
          r'\双面格-定制-定制尺寸-蔓生花;57x111cm.jpg')
material = prepare(MaterialSpec(source), preview=True)
layout = material.source_layout
print(layout.report, layout.content_box_px, layout.strip.shape, 'gaps', layout.corner_gaps is not None,
      'round', recognize_round_ring(layout.strip) is not None, flush=True)
Image.fromarray(layout.image).save(directory / 'source-preview.png')
Image.fromarray(layout.strip).resize((720, 400)).save(directory / 'strip.png')
for width, height, straight in [(112.5, 58, 70.5), (141, 81, 90), (200, 84, 130)]:
    design = DesignSpec(diameter_cm=width, height_cm=height, straight_cm=straight,
                        shape_mode='arc', border=BorderSpec(0, 0, 0))
    image = render_source(design, material, max_side=1200)
    image.save(directory / f'{width}-{height}.png')
    scale = ContentMapping.source_scale(layout, width, height)
    extra = max(0, ContentMapping.required_border(layout, width, height) - layout.border_depth_px * scale)
    row = int(np.argmax(np.std(layout.strip.astype(float), axis=1).mean(axis=1)))
    band = uniform_strip_band(layout.strip)
    depth = (row + .5) * scale + (extra if band and row >= band[1] else 0)
    output_row = round(depth / height * image.height - .5)
    pixels = np.asarray(image)
    for output_row in (output_row, image.height - 1 - output_row):
        centre = pixels[output_row, image.width * 3 // 8:image.width * 5 // 8, 0]
        assert np.std(centre) > 12, '上下直边中央花边仍被横线覆盖'
    print('Verified preview:', width, height, straight, flush=True)

if '--full' in sys.argv:
    material = prepare(MaterialSpec(source))
    design = DesignSpec(diameter_cm=112.5, height_cm=58, straight_cm=70.5,
                        shape_mode='arc', border=BorderSpec(0, 0, 0))
    image = render_source(design, material)
    for extension in ('jpg', 'png'):
        path = directory / f'full-export.{extension}'
        save_image(image, path, design.dpi)
        with Image.open(path) as saved:
            assert saved.size == design.pixel_size()
    image.thumbnail((1200, 1200))
    image.save(directory / 'full-export-preview.png')
    print('Verified full JPG/PNG export:', design.pixel_size(), flush=True)
