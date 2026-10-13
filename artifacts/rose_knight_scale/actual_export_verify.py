"""Compare actual compensated JPEG edge ink against regenerated lossless output."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from PIL import Image
from shape_crop.models.design import DesignSpec,MaterialSpec,BorderSpec
from shape_crop.services.materials import prepare
from shape_crop.services.export import save_image
from shape_crop.core.source_renderer import render_source
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape
from shape_crop.core.sampling import sample

out = Path(__file__).resolve().parent
source = Path(r'\\192.168.1.199\打印文件\方果图库\成品图\5068663_宁波大魔法（店铺端）')/'双面格-定制-定制尺寸-玫瑰骑士;85x135cm.jpg'
old_path = Path(r'E:\异形裁剪设计器\圆弧台\输出\双面格-定制-裁剪有图-玫瑰骑士;85x130CM裁剪有图王.jpg')
design = DesignSpec(diameter_cm=131,height_cm=86,straight_cm=99,
                    shape_mode='arc',border=BorderSpec(0,0,0))
material = prepare(MaterialSpec(str(source)))
layout = material.source_layout
panel = layout.inset_panel
assert panel.partial_fade_edges and {edge[0] for edge in panel.partial_fade_edges} == {0,1}
result = (Image.open(out/'actual-131-86-full.png').convert('RGBA') if '--reuse' in sys.argv else
          render_source(design,material))
assert result.size == design.pixel_size() == (7736,5079)
if '--reuse' not in sys.argv:
    for suffix in ('png','jpg'):
        save_image(result,out/f'actual-131-86-full.{suffix}',design.dpi)
old = np.asarray(Image.open(old_path).convert('RGB'))
new = np.asarray(result)[...,:3]
assert old.shape[:2] == new.shape[:2]
scale = ContentMapping.source_scale(layout,131,86)
border = max(layout.border_depth_px*scale,ContentMapping.required_border(layout,131,86))
a,b,c,d = panel.translucent[0]
left,top,right,bottom = panel.box
cl,ct,cr,cb = layout.content_box_px
inset = border+((top-ct)+(cb-bottom))/2/(cb-ct)*(86-2*border)
inner = create_shape(design).inset(inset)
dark = np.array(panel.translucent_levels[0])
positions = []
counts = {'left':0,'top':0,'right':0,'bottom':0}
for axis,position,lo,hi,floor in panel.partial_fade_edges:
    other = np.arange(lo+8,hi-8,3,dtype=float)
    u,v = (np.full_like(other,position),other) if axis else (other,np.full_like(other,position))
    floor = np.array(floor)
    solid = np.ones(len(other),dtype=bool)
    for offset in (-2,0,2):
        pixel = sample(layout.image,u if axis else u+offset,v+offset if axis else v)
        solid &= np.max(abs(pixel.astype(float)-floor),axis=1) <= 3
    edge_bounds = (a,c) if axis else (b,d)
    low_edge = abs(position-edge_bounds[0]) < abs(position-edge_bounds[1])
    related = [item[1] for item in panel.partial_fade_edges if item[0] == axis and
               (abs(item[1]-edge_bounds[0]) < abs(item[1]-edge_bounds[1])) == low_edge]
    exterior = min(related)-2 if low_edge else max(related)+2
    interior = edge_bounds[0]+8 if low_edge else edge_bounds[1]-8
    # Require uninterrupted ink on BOTH unaffected sides of the transition.
    # This excludes normal leaf edges and veins whose antialiasing is grey.
    for offset in (-2,0,2):
        outside_pixel = sample(layout.image,np.full_like(u,exterior) if axis else u+offset,
                               v+offset if axis else np.full_like(v,exterior))
        inside_pixel = sample(layout.image,np.full_like(u,interior) if axis else u+offset,
                              v+offset if axis else np.full_like(v,interior))
        solid &= np.max(outside_pixel,axis=1) < 20
        solid &= np.max(abs(inside_pixel.astype(float)-dark),axis=1) <= 5
    x,y = (u-(layout.width_px-1)/2)*scale,(v-(layout.height_px-1)/2)*scale
    side = np.mean((left-a,c-right))*scale
    limit = 2*max(side,max(top-b,d-bottom,0)*scale)
    vertical = np.where(y<0,np.clip(((layout.height_px-1)/2-b)*scale-inner.half_height,0,limit),
                       np.clip((d-(layout.height_px-1)/2)*scale-inner.half_height,0,limit))
    weight = np.clip(abs(y)/inner.half_height,0,1)
    outside = inner.depth(x,y)+side*(1-weight)+vertical*weight < -2*131/result.width
    # The regenerated outer cream frame intentionally replaces source ink.
    # Check the flower region beyond its antialiased inner boundary only.
    outside &= create_shape(design).depth(x,y) > border+2*131/result.width
    column = np.rint((x/131+.5)*result.width-.5).astype(int)
    row = np.rint((y/86+.5)*result.height-.5).astype(int)
    valid = solid & outside & (column>=0) & (column<result.width) & (row>=0) & (row<result.height)
    counts[('left' if low_edge else 'right') if axis else ('top' if low_edge else 'bottom')] += int(np.count_nonzero(valid))
    positions.extend(zip(row[valid].tolist(),column[valid].tolist()))
assert positions, '没有可核对的原过渡边缘墨色样本'
assert all(counts.values()), '必须覆盖四个方向的过渡边缘'
print('Four-edge samples:',counts,flush=True)
rows,columns = np.array(positions).T
old_bad = int(np.count_nonzero(np.max(old[rows,columns],axis=1)>80))
new_bad = int(np.count_nonzero(np.max(new[rows,columns],axis=1)>80))
print('Transition ink:',len(rows),'samples;',old_bad,'old grey-line pixels;',new_bad,'new',flush=True)
if new_bad:
    indexes = np.flatnonzero(np.max(new[rows,columns],axis=1)>80)[:8]
    print('Remaining samples:',[(int(rows[i]),int(columns[i]),new[rows[i],columns[i]].tolist()) for i in indexes],flush=True)
    for i in indexes[:3]:
        wx = ((columns[i]+.5)/result.width-.5)*131
        wy = ((rows[i]+.5)/result.height-.5)*86
        print('Outer depth/border:',create_shape(design).depth(np.array(wx),np.array(wy)),border,flush=True)
        su = ((columns[i]+.5)/result.width-.5)*131/scale+(layout.width_px-1)/2
        sv = ((rows[i]+.5)/result.height-.5)*86/scale+(layout.height_px-1)/2
        print('Source point:',su,sv,'corners:',
              [(int(np.floor(su))+dx,int(np.floor(sv))+dy,layout.image[int(np.floor(sv))+dy,int(np.floor(su))+dx].tolist())
               for dx,dy in ((0,0),(1,0),(0,1),(1,1))],flush=True)
assert old_bad > 0, '未复现用户成品图的灰白边'
assert new_bad == 0, '恢复后的边缘墨色仍有灰白线'
encoded = np.asarray(Image.open(out/'actual-131-86-full.jpg').convert('RGB'))
assert encoded.shape == new.shape
jpg_bad = int(np.count_nonzero(np.max(encoded[rows,columns],axis=1)>80))
print('JPEG transition ink grey pixels:',jpg_bad,flush=True)
assert jpg_bad == 0, 'JPEG导出的过渡墨色仍有灰白线'
for label, region in {'top':(900,950,1500,1100),
                      'left':(500,2000,750,2600),
                      'right':(6990,2000,7240,2600),
                      'bottom':(900,4000,1500,4150)}.items():
    result.crop(region).save(out/f'actual-edge-{label}.png')
result.thumbnail((1200,1200))
result.save(out/'actual-131-86-full-preview.png')
print('Verified actual compensated PNG/JPG:',design.pixel_size(),flush=True)
