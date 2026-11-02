"""Retain complete periodic ornaments and a contour-following textured inset."""
from dataclasses import dataclass, replace
import numpy as np
from PIL import Image
from shape_crop.services.texture_period import extract_period, extract_dark_period
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.framed_artwork import FramedArtwork, detect_rectangular_artwork, _textured_rectangle
from shape_crop.services.floating_artwork import _components


@dataclass(frozen=True)
class ContouredFrame:
    box: tuple
    stroke: np.ndarray
    inset_px: float
    uniform_texture: bool = False
    repeat_stroke: bool = False
    native_margins: bool = False


def _texture_content_box(layout, artwork):
    """Exclude the background padding used by rectangular-picture recognition."""
    box = tuple(round(value) for value in artwork.box)
    a, b, c, d = box
    if not (0 < a < c < layout.width_px and 0 < b < d < layout.height_px):
        return box
    pixels = layout.image[b:d, a:c]
    h, w = pixels.shape[:2]
    centre = np.mean(pixels[h//4:3*h//4, w//4:3*w//4], axis=(0, 1))
    background = np.median(artwork.tile.reshape(-1, 3), axis=0)
    contrast = np.max(np.abs(centre-background))
    if contrast < 24:
        return box
    tolerance = max(12, min(30, contrast*.4))
    limit = max(3, round(min(layout.width_px, layout.height_px)*.015))
    sides = (pixels, pixels[::-1], pixels.transpose(1, 0, 2), pixels[:, ::-1].transpose(1, 0, 2))
    trims = []
    for side in sides:
        rows = side[:min(limit, side.shape[0]//4), side.shape[1]//4:3*side.shape[1]//4]
        colours = np.mean(rows, axis=1)
        matches = np.flatnonzero(np.max(np.abs(colours-centre), axis=1) < tolerance)
        if not matches.size:
            return box
        trims.append(int(matches[0]))
    top, bottom, left, right = trims
    return a+left, b+top, c-right, d-bottom


def adapt_texture_inset(layout):
    """Curve a verified texture rectangle and retain its clean source pixels."""
    artwork = layout.framed_artwork
    if artwork is None and max(layout.width_px, layout.height_px) > 2400:
        # Native JPEG noise can hide a repeat accepted at preview resolution.
        # Recheck structure at the same bounded size, then keep native pixels.
        probe = Image.fromarray(layout.image)
        probe.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        recognized = analyze_layout(probe).framed_artwork
        if recognized is not None:
            sx, sy = layout.width_px / probe.width, layout.height_px / probe.height
            ox, oy = (round(v * r) for v, r in zip(recognized.origin, (sx, sy)))
            h, w = recognized.tile.shape[:2]
            tile = (recognized.tile if recognized.background_colour is not None else
                    layout.image[oy:oy + max(1, round(h * sy)), ox:ox + max(1, round(w * sx))])
            artwork = replace(recognized,
                box=tuple(v * r for v, r in zip(recognized.box, (sx, sy, sx, sy))),
                frame=tuple(v * r for v, r in zip(recognized.frame, (sx, sy, sx, sy))),
                origin=(ox, oy), tile=tile)
            layout = replace(layout, framed_artwork=artwork)
    if artwork is None:
        # Called only for the two named texture insets. A long source may have
        # no single clear margin large enough for the complete background tile.
        artwork = detect_rectangular_artwork(Image.fromarray(layout.image),
                                             layout.content_box_px, split_texture=True)
        if artwork is None:
            return layout
        layout = replace(layout, framed_artwork=artwork)
    box = _texture_content_box(layout, artwork)
    left, top, right, bottom = box
    if not (0 < left < right < layout.width_px and 0 < top < bottom < layout.height_px):
        return layout
    inset = (top + layout.height_px - bottom) / 2
    # These textures meet without an inner outline. An empty stroke preserves
    # their original boundary instead of inventing a line from the fill.
    frame = ContouredFrame(box, np.empty((0, 1, 3), dtype=np.uint8), inset, uniform_texture=True)
    return replace(layout, contoured_frame=frame,
        report=layout.report + '；中央色块随弧形，纹理等比铺入，保留浅色外层间距')


def adapt_outlined_texture_inset(layout):
    """Curve a verified pale texture panel and its complete dark inner trim."""
    image = Image.fromarray(layout.image)
    probe = image.copy()
    probe.thumbnail((1200,1200),Image.Resampling.LANCZOS)
    pixels = np.asarray(probe)
    h,w = pixels.shape[:2]
    sx,sy = layout.width_px/w,layout.height_px/h
    candidates = []
    for (a,b,c,d),_ in _components(np.max(pixels,axis=2)<100):
        if not (w*.4<c-a<w*.96 and h*.3<d-b<h*.92 and
                min(a,b,w-c,h-d)>min(w,h)*.025):
            continue
        # Connected corners alone are insufficient: prove a full dark line
        # on each side, with only a thin ornament footprint around it.
        aa,bb,cc,dd = (round(v*r) for v,r in zip((a,b,c,d),(sx,sy,sx,sy)))
        native = layout.image
        limit = max(4,round(min(layout.width_px,layout.height_px)*.035))
        rows = (native[bb:bb+limit,aa+(cc-aa)//4:cc-(cc-aa)//4],
                native[dd-limit:dd,aa+(cc-aa)//4:cc-(cc-aa)//4][::-1],
                native[bb+(dd-bb)//4:dd-(dd-bb)//4,aa:aa+limit].transpose(1,0,2),
                native[bb+(dd-bb)//4:dd-(dd-bb)//4,cc-limit:cc][:,::-1].transpose(1,0,2))
        extents = []
        for region in rows:
            coverage = np.mean(np.max(region,axis=2)<120,axis=1)
            core = np.flatnonzero(coverage>.9)
            active = np.flatnonzero(coverage>.02)
            if not core.size or not active.size or active[-1]>=limit-2:
                break
            extents.append((max(0,int(active[0])-1),int(active[-1])+2))
        if len(extents)!=4:
            continue
        artwork = _textured_rectangle(image,pixels,(a,b,c,d),layout.content_box_px,sx,sy,
                                      split_texture=True)
        native_margins = artwork is None
        if artwork is None:
            # The pale herringbone can have a repeat taller than the exposed
            # moat. Retain all four native margins instead of fabricating a tile.
            artwork = FramedArtwork((aa,bb,cc,dd),layout.content_box_px,
                                    native[:1,:1],(0,0),native_background=True)
        top,bottom,left,right = extents
        box = (aa+left[1],bb+top[1],cc-right[1],dd-bottom[1])
        if box[2]<=box[0] or box[3]<=box[1]:
            continue
        stroke_start = bb+top[0]
        region = native[stroke_start:box[1],aa+(cc-aa)//5:cc-(cc-aa)//5]
        stroke,period = extract_dark_period(region)
        if not period:
            ink = np.max(region,axis=2)<120
            if np.any(np.std(ink,axis=1)>.1):
                continue
            stroke = np.median(region,axis=1).astype(np.uint8)[:,None,:]
        inset = (stroke_start+layout.height_px-(dd-bottom[0]))/2
        frame = ContouredFrame(box,stroke,inset,uniform_texture=True,
                               repeat_stroke=bool(period),native_margins=native_margins)
        candidates.append(replace(layout,framed_artwork=artwork,contoured_frame=frame,
            report=layout.report+'；中央纹理等比铺入弧形内框，保留原细线及周期装饰'))
    return candidates[0] if len(candidates)==1 else layout


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
