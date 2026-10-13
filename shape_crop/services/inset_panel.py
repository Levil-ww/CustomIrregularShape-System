"""Recognize closed translucent or pale inset panels over full-span artwork."""
from dataclasses import dataclass
import numpy as np
from shape_crop.services.texture_period import extract_period


@dataclass(frozen=True)
class InsetPanel:
    box: tuple
    artwork: object = None
    translucent: object = None
    translucent_levels: object = None
    stroke_repeat_px: float = 0
    partial_fade_edges: tuple = ()


def _detect_translucent_panel(image):
    probe = image.copy()
    probe.thumbnail((1200, 1200))
    pixels = np.asarray(probe).astype(np.float32)
    h, w = pixels.shape[:2]
    dark = np.max(pixels, axis=2) < 90
    rows = np.flatnonzero(np.mean(dark[:, int(w * .3):int(w * .7)], axis=1) > .95)
    runs = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    lines = [r for r in runs if r.size and len(r) <= max(3, h * .008)]
    tops = [r for r in lines if h * .15 < r.mean() < h * .4]
    bottoms = [r for r in lines if h * .6 < r.mean() < h * .85]
    if len(tops) != 1 or len(bottoms) != 1:
        return None
    top, bottom = int(tops[0][0]), int(bottoms[0][-1])
    columns = np.flatnonzero(np.mean(dark[top:bottom + 1], axis=0) > .95)
    lefts = columns[(columns > w * .08) & (columns < w * .3)]
    rights = columns[(columns > w * .7) & (columns < w * .92)]
    if not lefts.size or not rights.size:
        return None
    left, right = int(lefts[0]), int(rights[-1])
    inner = pixels[top + 4:bottom - 3, left + 4:right - 3]
    outer = np.concatenate((pixels[int(h * .08):top - 8].reshape(-1, 3),
                            pixels[bottom + 9:int(h * .92)].reshape(-1, 3)))
    if not inner.size or not outer.size:
        return None
    # Require faded texture inside and real dark artwork outside. This excludes
    # plain rectangles, text frames and independent gallery pictures.
    background = np.percentile(outer, 90, axis=0)
    faded = np.percentile(inner.reshape(-1, 3), 5, axis=0)
    if np.mean(np.max(inner, axis=2) < 90) > .02 or np.mean(np.max(outer, axis=1) < 90) < .06:
        return None
    opacity = float(np.median(faded / np.maximum(background, 1)))
    if not .65 < opacity < .98 or np.max(background - faded) < 8:
        return None
    ratios = (image.width / w, image.height / h) * 2
    box = tuple(v * r for v, r in zip((left, top, right, bottom), ratios))
    stroke = max(len(tops[0]), len(bottoms[0]), 1)
    colour = np.median(pixels[top:top + stroke, int(w * .35):int(w * .65)].reshape(-1, 3), axis=0)
    clear = np.percentile(inner.reshape(-1, 3), 95, axis=0)
    # The flattened fade may extend beyond its fine outline. Find that
    # connected rectangular region on the source, independently of output
    # dimensions. Clear dark ink ends the region; blank background alone
    # does not establish an extension.
    bounds = [left, top, right, bottom]
    margin = round(min(h, w)*.06)
    for axis, edge, direction, index in ((1,left,-1,0), (0,top,-1,1),
                                        (1,right,1,2), (0,bottom,1,3)):
        for distance in range(stroke+2, margin+1):
            position = edge + direction*distance
            if not 0 <= position < (w if axis else h):
                break
            band = pixels[top+4:bottom-3, position] if axis else pixels[position, left+4:right-3]
            if np.any(np.percentile(band, 5, axis=0) < faded-8):
                break
            ink = np.max(np.abs(band-faded), axis=1) <= 8
            if np.mean(ink) >= .015:
                bounds[index] = position
    fade_bounds = [value*ratio for value, ratio in zip(bounds, ratios)]
    # Resolve the last resampled edge in source pixels. A one-probe-pixel
    # error leaves a visible pale stripe after contrast restoration.
    for axis, direction, index in ((1,-1,0), (0,-1,1), (1,1,2), (0,1,3)):
        edge = round(fade_bounds[index])
        for distance in range(0, max(2, int(np.ceil(max(ratios)*2)))+1):
            position = edge + direction*distance
            if not 0 <= position < (image.width if axis else image.height):
                break
            region = ((position, round(box[1])+4, position+1, round(box[3])-3)
                      if axis else (round(box[0])+4, position, round(box[2])-3, position+1))
            band = np.asarray(image.crop(region)).reshape(-1, 3).astype(np.float32)
            if np.any(np.percentile(band, 5, axis=0) < faded-8):
                break
            if np.mean(np.max(np.abs(band-faded), axis=1) <= 8) >= .015:
                fade_bounds[index] = position
    fade_box = tuple(fade_bounds)
    translucent = (fade_box, opacity, tuple(background), stroke * max(ratios), tuple(colour))
    upper = pixels[round(h*.06):max(round(h*.06), round(fade_bounds[1]/ratios[1])-4),
                   round(w*.1):round(w*.9)].astype(np.uint8)
    repeat = extract_period(upper, max_period_fraction=.75)[1] if min(upper.shape[:2]) >= 3 else 0
    return InsetPanel(box, translucent=translucent, translucent_levels=(tuple(faded), tuple(clear)),
                      stroke_repeat_px=repeat*ratios[0],
                      partial_fade_edges=_partial_fade_edges(image, fade_box, box, background, faded))


def _partial_fade_edges(image, fade_box, outline_box, background, dark):
    """Measure connected partial-opacity source pixels outside the closed fade."""
    pil = hasattr(image, 'crop')
    width, height = (image.width,image.height) if pil else (image.shape[1],image.shape[0])
    background = np.asarray(background, dtype=np.float32)
    active = background > 32
    if not np.any(active):
        return ()
    opacity = float(np.median(np.asarray(dark)[active]/background[active]))
    left, top, right, bottom = outline_box
    result = []
    extent = max(3, int(np.ceil(max(width,height)/1200))*2)
    for axis, edge, direction in ((1,fade_box[0],-1), (0,fade_box[1],-1),
                                  (1,fade_box[2],1), (0,fade_box[3],1)):
        start = int(np.ceil(edge)-1) if direction < 0 else int(np.floor(edge)+1)
        lo, hi = (round(top)+4,round(bottom)-3) if axis else (round(left)+4,round(right)-3)
        candidates = []
        partial = False
        for distance in range(extent):
            position = start + direction*distance
            if not 0 <= position < (width if axis else height):
                break
            region = (position,lo,position+1,hi) if axis else (lo,position,hi,position+1)
            band = (np.asarray(image.crop(region)) if pil else image[region[1]:region[3],region[0]:region[2]])
            band = band.reshape(-1,3).astype(np.float32)
            floor = np.percentile(band,5,axis=0)
            alpha = floor[active]/background[active]
            # A connected, shared-colour fade differs from isolated grey ink.
            strength = float(np.median(alpha))
            if not .01 < strength < .995 or np.ptp(alpha) > .04:
                break
            if np.mean(np.max(np.abs(band-floor),axis=1) <= 8) < .04:
                break
            apply_lo, apply_hi = (int(np.floor(fade_box[1])),int(np.ceil(fade_box[3]))+1) if axis else (
                int(np.floor(fade_box[0])),int(np.ceil(fade_box[2]))+1)
            partial |= strength < opacity-.02
            candidates.append((axis,position,apply_lo,apply_hi,tuple(float(value) for value in floor)))
        # JPEG ringing can make the first transition row nearly opaque.
        # Admit it only with a connected weaker fade farther out, not merely
        # because an isolated natural pale detail resembles the background.
        if partial:
            result.extend(candidates)
    return tuple(result)


def _detect_pale_panel(image):
    """Require a closed light outline, a quiet centre and textured surroundings."""
    probe = image.copy()
    probe.thumbnail((1200, 1200))
    pixels = np.asarray(probe).astype(np.float32)
    h, w = pixels.shape[:2]
    background = np.median(pixels[int(h * .35):int(h * .65),
                                  int(w * .35):int(w * .65)].reshape(-1, 3), axis=0)
    difference = np.max(np.abs(pixels - background), axis=2)
    # Pale lines are distinct from both the cream centre and dark artwork.
    line = (difference > 10) & (difference < 100) & (np.min(pixels, axis=2) > 110)
    rows = np.flatnonzero(np.mean(line[:, int(w * .35):int(w * .65)], axis=1) > .97)
    runs = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    thin = [r for r in runs if r.size and len(r) <= max(4, h * .012)]
    tops = [r for r in thin if h * .12 < r.mean() < h * .4]
    bottoms = [r for r in thin if h * .6 < r.mean() < h * .88]
    for a in tops:
        for b in bottoms:
            top, bottom = int(a[0]), int(b[-1])
            # Resampling a one-pixel line gives different edge colours on
            # horizontal and vertical sides. Test closure against the quiet
            # centre rather than requiring identical antialiased colours.
            matches = line
            columns = np.flatnonzero(np.mean(matches[top:bottom + 1], axis=0) > .95)
            lefts = columns[(columns > w * .06) & (columns < w * .3)]
            rights = columns[(columns > w * .7) & (columns < w * .94)]
            if not lefts.size or not rights.size:
                continue
            left, right = int(lefts[0]), int(rights[-1])
            if (np.mean(matches[top, left:right + 1]) < .95 or
                    np.mean(matches[bottom, left:right + 1]) < .95):
                continue
            inner = difference[top + 4:bottom - 3, left + 4:right - 3]
            outer = np.concatenate((difference[max(1, int(h * .06)):top - 4,
                                              left:right].ravel(),
                                    difference[bottom + 5:int(h * .94), left:right].ravel()))
            if not inner.size or not outer.size:
                continue
            if np.mean(inner < 10) < .90 or np.mean(outer > 15) < .08:
                continue
            ratios = (image.width / w, image.height / h) * 2
            box = tuple(v * r for v, r in zip((left, top, right, bottom), ratios))
            ink_y, ink_x = np.nonzero(inner > 10)
            artwork = None
            if ink_x.size:
                ink_box = (left + 4 + ink_x.min() - 2, top + 4 + ink_y.min() - 2,
                           left + 4 + ink_x.max() + 2, top + 4 + ink_y.max() + 2)
                artwork = (tuple(float(v * r) for v, r in zip(ink_box, ratios)),
                           tuple(int(v) for v in background))
            return InsetPanel(box, artwork)
    return None


def detect_inset_panel(image):
    return _detect_translucent_panel(image) or _detect_pale_panel(image)
