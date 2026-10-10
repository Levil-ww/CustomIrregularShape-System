"""Extract inset textures and corner compositions without mixing frame pixels."""
from dataclasses import dataclass
from collections import deque
import numpy as np
from PIL import Image, ImageFilter
from shape_crop.services.floating_artwork import _components
from shape_crop.services.texture_period import extract_period


@dataclass(frozen=True)
class PatternedInset:
    box: tuple
    background: tuple


@dataclass(frozen=True)
class CornerGroup:
    box: tuple
    alpha: np.ndarray
    anchor: str


@dataclass(frozen=True)
class CornerComposition:
    groups: tuple
    text_box: tuple
    background: tuple



def _clear_connected_white(mask, point):
    """Clear an eight-connected white region with bounded scanline work."""
    queue=deque([point]); height,width=mask.shape
    while queue:
        x,y=queue.popleft()
        if not mask[y,x]: continue
        left,right=x,x+1
        while left>0 and mask[y,left-1]: left-=1
        while right<width and mask[y,right]: right+=1
        mask[y,left:right]=False
        start,end=max(0,left-1),min(width,right+1)
        for row in (y-1,y+1):
            if 0<=row<height:
                values=mask[row,start:end]
                changes=np.diff(np.r_[False,values].astype(np.int8))
                queue.extend((start+int(column),row) for column in np.flatnonzero(changes==1))


def detect_patterned_inset(image):
    probe=image.copy(); probe.thumbnail((1200,1200))
    pixels=np.asarray(probe).astype(np.float32); h,w=pixels.shape[:2]
    background=np.median(pixels[round(h*.08):round(h*.14),round(w*.3):round(w*.7)].reshape(-1,3),axis=0)
    foreground=np.max(np.abs(pixels-background),axis=2)>18
    candidates=[]
    for box,count in _components(foreground):
        a,b,c,d=box
        if (w*.04<a<w*.20 and w*.80<c<w*.96 and h*.10<b<h*.30
                and h*.70<d<h*.90 and count>(c-a)*(d-b)*.60):
            candidates.append(box)
    if len(candidates)!=1: return None
    left,top,right,bottom=candidates[0]
    # The dense inset and the broad outer band share their original colour.
    inside=pixels[top:bottom,left:right]; colour=np.median(inside.reshape(-1,3),axis=0)
    outer=np.median(pixels[2:max(3,round(h*.025)),round(w*.3):round(w*.7)].reshape(-1,3),axis=0)
    if np.max(np.abs(colour-outer))>15 or np.max(np.abs(colour-background))<24: return None
    def depth(region):
        indices=np.flatnonzero(np.mean(region,axis=1)>.95)
        return int(indices[-1])+1 if indices.size else 0
    frame_top=depth(foreground[:top,round(w*.3):round(w*.7)])
    frame_bottom=h-depth(foreground[bottom:,round(w*.3):round(w*.7)][::-1])
    frame_left=depth(foreground[round(h*.3):round(h*.7),:left].T)
    frame_right=w-depth(foreground[round(h*.3):round(h*.7),right:][:,::-1].T)
    if min(left-frame_left,top-frame_top,frame_right-right,frame_bottom-bottom)<min(w,h)*.02: return None
    moat=(foreground[frame_top:top,left:right],foreground[bottom:frame_bottom,left:right],
          foreground[top:bottom,frame_left:left],foreground[top:bottom,right:frame_right])
    if any(not a.size or a.mean()>.08 for a in moat): return None
    ratios=(image.width/w,image.height/h)*2
    box=tuple(round(v*r) for v,r in zip((left,top,right,bottom),ratios))
    frame=tuple(round(v*r) for v,r in zip((frame_left,frame_top,frame_right,frame_bottom),ratios))
    return PatternedInset(box,tuple(int(v) for v in background)),frame


def detect_corner_composition(image):
    probe=image.copy(); probe.thumbnail((1200,1200))
    pixels=np.asarray(probe); h,w=pixels.shape[:2]
    background=np.median(pixels.reshape(-1,3),axis=0)
    if np.min(background)<235: return None
    dark=np.max(pixels,axis=2)<160
    def edge(rows):
        values=np.mean(rows,axis=1)
        black=0
        while black<len(values) and values[black]>.98: black+=1
        ink=np.flatnonzero(values[:max(2,round(h*.10))]>.02)
        return black,int(ink[-1])+1 if ink.size else 0
    bt,top=edge(dark[:round(h*.15),round(w*.3):round(w*.6)])
    bb,bdepth=edge(dark[::-1][:round(h*.15),round(w*.36):round(w*.40)])
    bl,left=edge(dark[round(h*.12):round(h*.30),:round(w*.15)].T)
    br,rdepth=edge(dark[round(h*.70):round(h*.82),::-1][:,:round(w*.15)].T)
    if min(bt,bb,bl,br)<1 or max(top,bdepth,left,rdepth)>min(w,h)*.12: return None
    right,bottom=w-rdepth,h-bdepth
    _,period=extract_period(pixels[:top,round(w*.3):round(w*.6)])
    if not period: return None
    ink=dark.copy(); ink[:bt]=False; ink[h-bb:]=False; ink[:,:bl]=False; ink[:,w-br:]=False
    components=_components(ink)
    large=[box for box,count in components if count>max(40,w*h*.0005)]
    left_boxes=[box for box in large if (box[0]+box[2])/2<w*.35 and (box[1]+box[3])/2>h*.60]
    right_boxes=[box for box in large if (box[0]+box[2])/2>w*.65 and (box[1]+box[3])/2<h*.40]
    if not left_boxes or not right_boxes: return None
    if any(box not in left_boxes+right_boxes for box in large): return None
    # Remove isolated frame dots before extracting text or closing flower silhouettes.
    for box,count in components:
        a,b,c,d=box
        vertical = a<left+2 or c>right-2
        horizontal = b<top+2 or d>bottom-2
        # Adjacent dot rows can join into one compact component at a corner.
        # Only allow the larger extent where both frame edges meet.
        compact = max(c-a,d-b)<=period*(1.8 if vertical and horizontal else .9)+2
        dense = count/((c-a)*(d-b))>.35
        if compact and dense and (vertical or horizontal):
            ink[b:d,a:c]=False
    text_mask=ink[top:bottom,round(w*.35):round(w*.65)]
    ys,xs=np.nonzero(text_mask)
    if not xs.size: return None
    text=(round(w*.35)+int(xs.min())-2,top+int(ys.min())-2,
          round(w*.35)+int(xs.max())+3,top+int(ys.max())+3)
    if text[2]-text[0]>w*.27 or text[3]-text[1]>h*.18: return None
    ratios=(image.width/w,image.height/h)*2
    groups=[]
    rim=np.zeros_like(ink)
    rim[:bt]=True; rim[h-bb:]=True; rim[:,:bl]=True; rim[:,w-br:]=True
    rim_white=rim & (np.min(pixels,axis=2)>200)
    # Where petals overlap the black source rim, removing the rim opens their
    # contours. Close just those measured white-petal intervals at the rim's
    # inner edge; no rectangular frame or dot row enters the silhouette.
    barrier=ink.copy()
    barrier[:,bl] |= np.any(rim_white[:,:bl],axis=1)
    barrier[:,w-br-1] |= np.any(rim_white[:,w-br:],axis=1)
    barrier[bt] |= np.any(rim_white[:bt],axis=0)
    barrier[h-bb-1] |= np.any(rim_white[h-bb:],axis=0)
    # Rim removal and neighbouring frame-dot removal can leave a three-pixel
    # opening in a petal contour. Seal that recognition-scale gap before the
    # background flood fill, so the petal's white interior remains opaque.
    closed=np.asarray(Image.fromarray(barrier.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(5)))>0
    holes=(~closed).copy()
    _clear_connected_white(holes,(w//2,h//2))
    silhouette=ink | holes | rim_white
    # Disconnected tiny islands from JPEG/dot-edge whites are not bouquets.
    for box,count in _components(silhouette):
        if count<max(8,w*h*.00008):
            a,b,c,d=box
            if np.count_nonzero(silhouette[b:d,a:c])==count:
                silhouette[b:d,a:c]=False
    for boxes,anchor in ((left_boxes,'bottom_left'),(right_boxes,'top_right')):
        padding=max(bt,bb,bl,br,3)
        a=max(0,min(b[0] for b in boxes)-padding); b=max(0,min(b[1] for b in boxes)-padding)
        c=min(w,max(b[2] for b in boxes)+padding); d=min(h,max(b[3] for b in boxes)+padding)
        filled=silhouette[b:d,a:c]
        filled=np.asarray(Image.fromarray(filled.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(3)))>0

        full_box=tuple(round(v*r) for v,r in zip((a,b,c,d),ratios))
        alpha=np.asarray(Image.fromarray(filled.astype(np.uint8)*255).resize(
            (full_box[2]-full_box[0],full_box[3]-full_box[1]),Image.Resampling.LANCZOS))
        groups.append(CornerGroup(full_box,alpha,anchor))
    frame=tuple(round(v*r) for v,r in zip((left,top,right,bottom),ratios))
    text=tuple(round(v*r) for v,r in zip(text,ratios))
    # A quiet top span contains every frame layer but no corner flower pixels.
    full=np.asarray(image); strip=full[:frame[1],round(image.width*.3):round(image.width*.6)]
    return CornerComposition(tuple(groups),text,tuple(int(v) for v in background)),frame,strip
