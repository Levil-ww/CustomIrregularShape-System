"""Detect over-bright rectangular JPEG seams in the exact rose knight preview."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import Image
import numpy as np
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec
from shape_crop.core.source_renderer import render_source
from shape_crop.core.content_mapping import ContentMapping

root = Path(__file__).resolve().parent
layout = analyze_layout(Image.open(root / 'source-85-135.png'))
material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
design = DesignSpec(diameter_cm=130, height_cm=85, straight_cm=99,
                    shape_mode='arc', border=BorderSpec(0, 0, 0))
result = render_source(design, material, max_side=1200)
pixels = np.asarray(result)[...,:3].astype(float)
scale = ContentMapping.source_scale(layout, 130, 85)
u = (((np.arange(result.width)+.5)/result.width-.5)*130/scale+(layout.width_px-1)/2)[None,:]
v = (((np.arange(result.height)+.5)/result.height-.5)*85/scale+(layout.height_px-1)/2)[:,None]
band = np.zeros((result.height, result.width), dtype=bool)
for a,b,c,d in (layout.inset_panel.box, layout.inset_panel.translucent[0]):
    band |= ((np.minimum(abs(u-a),abs(u-c)) <= 8) & (v >= b-8) & (v <= d+8))
    band |= ((np.minimum(abs(v-b),abs(v-d)) <= 8) & (u >= a-8) & (u <= c+8))
delta = pixels-np.array(layout.inset_panel.translucent[2])
bright = band & (np.min(delta,axis=2) >= 0) & (np.max(delta,axis=2) > 3) & (np.ptp(delta,axis=2) <= 6)
count = int(np.count_nonzero(bright))
print('Over-bright old-frame pixels:', count, flush=True)
result.save(root / 'white-line-130-85-preview.png')
assert count == 0, f'旧矩形边界仍有{count}个超过底色的白线像素'
