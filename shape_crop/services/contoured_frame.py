"""Retain complete periodic ornaments and a contour-following textured inset."""
from dataclasses import dataclass, replace
import numpy as np
from PIL import Image
from shape_crop.services.texture_period import extract_period, extract_dark_period


@dataclass(frozen=True)
class ContouredFrame:
    box: tuple
    stroke: np.ndarray
    inset_px: float


def adapt_contoured_frame(layout):
    artwork = layout.framed_artwork
    if artwork is None or artwork.native_background:
        return layout
    probe = Image.fromarray(layout.image)
    probe.thumbnail((1200,1200),Image.Resampling.LANCZOS)
    pixels = np.asarray(probe)
    h,w = pixels.shape[:2]
    sx,sy = layout.width_px/w,layout.height_px/h
    a,b,c,d = [round(v/r) for v,r in zip(artwork.box,(sx,sy,sx,sy))]
    # Background plaid is dark; the original pale ornaments have a bounded
    # shallow footprint on every edge. Never search into the floral picture.
    sides=(pixels,pixels.transpose(1,0,2),pixels[::-1],pixels[:,::-1].transpose(1,0,2))
    limits=(b,a,h-d,w-c)
    depths=[]
    for side,limit in zip(sides,limits):
        band=side[:max(1,round(limit*.8)),round(side.shape[1]*.3):round(side.shape[1]*.7)]
        bright=np.mean(np.min(band,axis=2)>170,axis=1)
        ink=np.flatnonzero((bright>.02)&(bright<.95))
        if not ink.size:
            return layout
        depths.append(int(ink[-1])+3)
    top,left,bottom,right=depths
    region=pixels[b:min(d,b+max(12,round(h*.03))),round(w*.3):round(w*.7)].astype(np.float32)
    median=np.median(region,axis=1)
    quiet=np.mean(np.max(np.abs(region-median[:,None]),axis=2)<12,axis=1)>.95
    dark=np.flatnonzero(quiet & (np.max(median,axis=1)<60))
    if not dark.size:
        return layout
    start=int(dark[0])
    while start and np.max(median[start-1])<110:
        start-=1
    end=start+1
    while end<len(quiet) and quiet[end]:
        end+=1
    # The inner black line can touch the roses. Preserve its antialias row too.
    end=min(end+2,len(quiet))
    if end-start>h*.025 or end<=start:
        return layout
    stroke_start=round((b+start)*sy)
    stroke_end=round((b+end)*sy)
    native=layout.image
    stroke=np.median(native[stroke_start:stroke_end,round(w*.3*sx):round(w*.7*sx)],axis=1).astype(np.uint8)[:,None,:]
    pad_x=round(end*sx)
    pad_y=round(end*sy)
    box=(round(artwork.box[0])+pad_x,round(artwork.box[1])+pad_y,
         round(artwork.box[2])-pad_x,round(artwork.box[3])-pad_y)
    if box[2]<=box[0] or box[3]<=box[1]:
        return layout
    top,left,bottom,right=[round(v*r) for v,r in zip(depths,(sy,sx,sy,sx))]
    bounds=(left,top,layout.width_px-right,layout.height_px-bottom)
    full_strip=native[:top,left+1:layout.width_px-right-1]
    strip,period=extract_period(full_strip)
    if not period:
        strip,period=extract_dark_period(full_strip)
    if not period:
        return layout
    inset=(stroke_start+layout.height_px-(round(artwork.box[3])-round(start*sy)))/2
    return replace(layout,strip=strip,border_depth_px=top,content_box_px=bounds,
        content=native[top:bounds[3],left:bounds[2]],strip_period_px=period,
        contoured_frame=ContouredFrame(box,stroke,inset),
        report='完整菱形装饰沿轮廓排列；内侧双线框随侧弧适配，玫瑰花纹等比满铺')
