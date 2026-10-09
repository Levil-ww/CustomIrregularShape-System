"""Recognize independent rectangular artwork over a verified repeating background."""
from dataclasses import dataclass
import numpy as np
from shape_crop.services.floating_artwork import _components


@dataclass(frozen=True)
class FramedArtwork:
    box: tuple
    frame: tuple
    tile: np.ndarray
    origin: tuple
    native_background: bool = False
    background_colour: tuple | None = None
    clear_box: tuple | None = None


def _repeat(region):
    values = region.astype(np.float32)
    if values.shape[1] < 30 or np.mean(np.std(values, axis=1)) < 3:
        return 0
    errors = [float(np.mean(np.abs(values[:, lag:] - values[:, :-lag])))
              for lag in range(3, values.shape[1] // 3)]
    for index in range(1, len(errors) - 1):
        if errors[index] < 3 and errors[index] < errors[index - 1] and errors[index] <= errors[index + 1]:
            return index + 3
    return 0


def detect_framed_artwork(image, frame, rectangle_mask=None, rectangle_boxes=None):
    probe = image.copy()
    probe.thumbnail((1200, 1200))
    pixels = np.asarray(probe)
    h, w = pixels.shape[:2]
    sx, sy = image.width / w, image.height / h
    left, top, right, bottom = [round(v / r) for v, r in zip(frame, (sx, sy, sx, sy))]
    padding = max(4, round(min(h, w) * .012))
    dark = np.max(pixels, axis=2) < 60 if rectangle_mask is None else rectangle_mask
    candidates = []
    for box, _ in (_components(dark) if rectangle_boxes is None else rectangle_boxes):
        a, b, c, d = box
        if not (w * .4 < c - a < w * (.88 if rectangle_boxes is None else .9) and h * .3 < d - b < h * (.8 if rectangle_boxes is None else .92)):
            continue
        if min(a, b - top, w - c, bottom - d) < max(padding * 2, min(w, h) * .035):
            continue
        if rectangle_boxes is None and np.mean(dark[b:d, a:c]) < .15:
            continue
        # The component's outermost antialiased row can be only partly dark.
        # Require a complete line within the thin edge band on every side.
        band = max(2, round(min(w, h) * .004))
        edges = (dark[b:b + band, a + band:c - band].mean(axis=1),
                 dark[d - band:d, a + band:c - band].mean(axis=1),
                 dark[b + band:d - band, a:a + band].mean(axis=0),
                 dark[b + band:d - band, c - band:c].mean(axis=0))
        if any(np.max(edge) < .94 for edge in edges):
            continue
        # Prove that all four surrounding strips are the same periodic texture,
        # not a floral composition connected to a centre or an arbitrary moat.
        upper = pixels[top + padding:b - padding, left + padding:right - padding]
        lower = pixels[d + padding:bottom - padding, left + padding:right - padding]
        px = _repeat(upper)
        if not px:
            continue
        # A side scan can run through broad plaid and stop at the picture.
        # Locate the actual background span from the same verified top texture.
        clean_left, clean_right = left, right
        if min(a - left, right - c) < padding * 3:
            full_upper = pixels[top + padding:b - padding]
            phase = (np.arange(w) - left - padding) % px
            reference = upper[:, :px][:, phase]
            matches = np.flatnonzero(np.mean(np.abs(full_upper.astype(float) - reference), axis=(0, 2)) < 5)
            runs = np.split(matches, np.flatnonzero(np.diff(matches) > 1) + 1)
            span = max(runs, key=len)
            if len(span) < w * .7:
                continue
            clean_left, clean_right = int(span[0]), int(span[-1]) + 1
            if min(a - clean_left, clean_right - c) < padding * 2:
                continue
        upper = pixels[top + padding:b - padding, clean_left + padding:clean_right - padding]
        lower = pixels[d + padding:bottom - padding, clean_left + padding:clean_right - padding]
        west = pixels[top + padding:bottom - padding, clean_left + padding:a - padding]
        east = pixels[top + padding:bottom - padding, c + padding:clean_right - padding]
        if any(min(region.shape[:2]) < 5 for region in (upper, lower, west, east)):
            continue
        py = _repeat(west.transpose(1, 0, 2))
        if not px or not py:
            continue
        regions = (upper, lower, west.transpose(1, 0, 2), east.transpose(1, 0, 2))
        if any(float(np.mean(np.abs(r[:, period:].astype(float) - r[:, :-period]))) > 4
               for r, period in zip(regions, (px, px, py, py))):
            continue
        if upper.shape[0] < py:
            continue
        origin = (round((clean_left + padding) * sx), round((top + padding) * sy))
        full = np.asarray(image)
        # Refine integer periods at the source resolution; recognition stays
        # bounded, while the saved tile and central picture retain native pixels.
        def refine(region, estimate, ratio):
            width = region.shape[1]
            rows = np.linspace(0, region.shape[0] - 1, min(20, region.shape[0])).astype(int)
            values = region[rows].astype(np.float32)
            radius = max(1, round(ratio))
            return min(range(max(3, estimate - radius), min(width // 2, estimate + radius) + 1),
                       key=lambda lag: float(np.mean(np.abs(values[:, lag:] - values[:, :-lag]))))
        ox, oy = origin
        px = refine(full[oy:round((b - padding) * sy), ox:round((clean_right - padding) * sx)], round(px * sx), sx)
        py = refine(full[oy:round((bottom - padding) * sy), ox:round((a - padding) * sx)].transpose(1, 0, 2), round(py * sy), sy)
        tile = full[oy:oy + py, ox:ox + px].copy()
        # Include the complete original double outline and its antialiasing.
        margin = max(2, round(min(w, h) * .004))
        artwork_box = tuple(float(v * r) for v, r in zip((a - margin, b - margin, c + margin, d + margin), (sx, sy, sx, sy)))
        actual_frame = (clean_left * sx, frame[1], clean_right * sx, frame[3])
        candidates.append(FramedArtwork(artwork_box, actual_frame, tile, origin))
    return candidates[0] if len(candidates) == 1 else None


def detect_rectangular_artwork(image, frame):
    """Recognize complete contrasting rectangles without component connectivity."""
    probe = image.copy()
    probe.thumbnail((1200, 1200))
    pixels = np.asarray(probe)
    h, w = pixels.shape[:2]
    sx, sy = image.width / w, image.height / h
    # Extend only complete, quiet outer frames. Full-span ornament grids and
    # partial edge bands retain the original cover/crop behaviour.
    outer_band = max(3, round(min(w,h)*.005))
    outer = np.concatenate((pixels[1:outer_band+1].reshape(-1,3),pixels[-outer_band-1:-1].reshape(-1,3),
                            pixels[:,1:outer_band+1].reshape(-1,3),pixels[:,-outer_band-1:-1].reshape(-1,3)))
    outer_colour = np.median(outer,axis=0)
    if np.mean(np.max(np.abs(outer.astype(float)-outer_colour),axis=1)<12)<.98:
        return None
    candidates = []
    edge_band = max(3, round(min(w, h) * .05))
    edge_pixels = np.concatenate((pixels[:edge_band].reshape(-1,3),pixels[-edge_band:].reshape(-1,3),pixels[:,:edge_band].reshape(-1,3),pixels[:,-edge_band:].reshape(-1,3)))
    edge_colour = np.median(edge_pixels, axis=0)
    mid_colour = np.median(np.array([pixels[round(h*.05),w//2],pixels[round(h*.95),w//2],
                                    pixels[h//2,round(w*.05)],pixels[h//2,round(w*.95)]]),axis=0)
    masks = (pixels.max(axis=2) < 60, pixels.mean(axis=2) < 155, pixels.mean(axis=2) < 225,
             np.max(np.abs(pixels.astype(float)-edge_colour),axis=2)>24,
             np.max(np.abs(pixels.astype(float)-mid_colour),axis=2)>24)
    for mask in masks:
        spans = {}
        for y, row in enumerate(mask):
            changes = np.diff(np.r_[False, row, False].astype(np.int8))
            for a, c in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)):
                if w * .4 < c - a < w * .9:
                    spans.setdefault((int(a), int(c)), []).append(y)
        boxes = []
        for (a, c), rows in spans.items():
            b, d = rows[0], rows[-1] + 1
            if not h * .3 < d - b < h * .92:
                continue
            if min(a, b, w - c, h - d) < min(w, h) * .035:
                continue
            if min(mask[b:d, a:a + 4].mean(axis=0).max(), mask[b:d, c - 4:c].mean(axis=0).max()) < .94:
                continue
            boxes.append(((a, b, c, d), 0))
        merged = []
        for (a,b,c,d), _ in boxes:
            related = [(x,ys) for x,ys in spans.items() if abs(x[0]-a)<=3 and abs(x[1]-c)<=3]
            bounds = (min(x[0] for x,ys in related), min(min(ys) for x,ys in related),
                      max(x[1] for x,ys in related), max(max(ys) for x,ys in related)+1)
            aa,bb,cc,dd=bounds
            if min(mask[bb:dd,aa:aa+4].mean(axis=0).max(),mask[bb:dd,cc-4:cc].mean(axis=0).max()) >= .94 and bounds not in [x[0] for x in merged]:
                merged.append((bounds,0))
        boxes = merged
        periodic = detect_framed_artwork(image, frame, mask, boxes)
        if periodic is not None:
            return periodic
        for (a, b, c, d), _ in boxes:
            inside = pixels[b + 3:d - 3, a + 3:c - 3]
            colour = np.median(inside.reshape(-1, 3), axis=0)
            quiet = (np.mean(np.max(np.abs(inside.astype(float) - colour), axis=2) < 12) > .90
                     and mask[b:d,a:c].mean() < .15)
            # Blank panels on nonperiodic floral surroundings retain the original layout.
            if quiet:
                continue
            left, top, right, bottom = [round(v / r) for v, r in zip(frame, (sx, sy, sx, sy))]
            background = np.median(pixels[max(0,b - 12):b - 3, a:c].reshape(-1, 3), axis=0)
            # A flat surrounding band can be wider than the old edge scan.
            # Find its actual boundary against the outer frame independently.
            if np.max(np.abs(colour-background)) < 24:
                continue
            textured = _textured_rectangle(image, pixels, (a,b,c,d), frame, sx, sy)
            if textured is not None:
                return textured
            near = np.max(np.abs(pixels.astype(float) - background), axis=2) < 12
            yy = np.flatnonzero(near[:, a:c].mean(axis=1) > .95)
            xx = np.flatnonzero(near[b:d].mean(axis=0) > .95)
            if not yy.size or not xx.size:
                continue
            top, bottom, left, right = int(yy[0]), int(yy[-1])+1, int(xx[0]), int(xx[-1])+1
            regions = (near[top:b, left:right], near[d:bottom, left:right],
                       near[b:d, left:a], near[b:d, c:right])
            if any(not r.size or r.mean() < .95 for r in regions):
                continue
            if min(a-left,b-top,right-c,bottom-d) < max(4,min(w,h)*.015):
                continue
            bg = tuple(int(v) for v in background)
            box = tuple(float(v*r) for v,r in zip((a,b,c,d),(sx,sy,sx,sy)))
            outer = tuple(float(v*r) for v,r in zip((left,top,right,bottom),(sx,sy,sx,sy)))
            candidates.append(FramedArtwork(box,outer,np.array([[bg]],dtype=np.uint8),(0,0),False,bg))
    if not candidates:
        return None
    first = candidates[0]
    if any(max(abs(x-y) for x,y in zip(first.box,item.box)) > max(sx,sy)*4 for item in candidates[1:]):
        return None
    box = tuple((min if i < 2 else max)(item.box[i] for item in candidates) for i in range(4))
    clear_box = tuple(v + (-2 if i < 2 else 2) * (sx if i % 2 == 0 else sy) for i,v in enumerate(box))
    # Crop the picture at its proven stroke, not the cleanup margin: otherwise
    # surrounding flowers become little fragments attached to the new frame.
    return FramedArtwork(first.box, first.frame, first.tile, first.origin,
                         first.native_background, first.background_colour, clear_box)


def _textured_rectangle(image, pixels, box, frame, sx, sy):
    """Accept mildly antialiased periodic backgrounds with a clean source tile."""
    a,b,c,d = box
    left,top,right,bottom = [round(v/r) for v,r in zip(frame,(sx,sy,sx,sy))]
    pad = 4
    regions = (pixels[top+pad:b-pad,left+pad:right-pad], pixels[d+pad:bottom-pad,left+pad:right-pad],
               pixels[top+pad:bottom-pad,left+pad:a-pad].transpose(1,0,2),
               pixels[top+pad:bottom-pad,c+pad:right-pad].transpose(1,0,2))
    if any(min(r.shape[:2]) < 8 for r in regions):
        return None
    def periods(first, second):
        values = (first.astype(float), second.astype(float))
        if any(np.mean(np.std(v,axis=1)) < 3 for v in values):
            return []
        errors = [max(np.mean(np.abs(v[:,lag:]-v[:,:-lag])) for v in values)
                  for lag in range(3,min(v.shape[1] for v in values)//3)]
        return [(float(errors[i]), i+3) for i in range(1,len(errors)-1)
                if errors[i]<8 and errors[i]<errors[i-1] and errors[i]<=errors[i+1]]
    horizontal, vertical = periods(regions[0],regions[1]), periods(regions[2],regions[3])
    ox,oy = left+pad,top+pad
    fits = [(ex+ey, px, py) for ex,px in horizontal for ey,py in vertical
            if (ox+px<=a-pad or oy+py<=b-pad) and ox+px<right-pad and oy+py<bottom-pad]
    if not fits:
        return None
    _,px,py = min(fits)
    # The whole saved tile lies in proven background, never in the picture.
    full=np.asarray(image)
    origin=(round(ox*sx),round(oy*sy))
    def refine(region, estimate, ratio):
        # Thumbnail interpolation can shift a repeat by one or two native pixels.
        rows = region[::max(1, region.shape[0] // 20)].astype(np.float32)
        radius = max(1, int(np.ceil(ratio)))
        candidates = range(max(3, estimate-radius), min(rows.shape[1], estimate+radius+1))
        return min(candidates, key=lambda lag: np.mean(np.abs(rows[:,lag:]-rows[:,:-lag])))
    fl, ft, fr, fb = (round(v) for v in frame)
    aa, bb, cc, dd = (round(v*r) for v,r in zip(box,(sx,sy,sx,sy)))
    padx, pady = int(np.ceil(pad*sx)), int(np.ceil(pad*sy))
    horizontal = full[ft+pady:bb-pady, fl+padx:fr-padx]
    vertical = full[ft+pady:fb-pady, fl+padx:aa-padx].transpose(1,0,2)
    px = refine(horizontal, round(px*sx), sx)
    py = refine(vertical, round(py*sy), sy)
    if not ((origin[0]+px <= aa-padx or origin[1]+py <= bb-pady)
            and origin[0]+px < fr-padx and origin[1]+py < fb-pady):
        return None
    tile=full[origin[1]:origin[1]+py,origin[0]:origin[0]+px].copy()
    # Contrasting rectangles have no outer outline to preserve. Expanding this
    # crop would carry a second, smaller ring of background ornament.
    bounds=tuple(float(v*r) for v,r in zip((a,b,c,d),(sx,sy,sx,sy)))
    return FramedArtwork(bounds,frame,tile,origin,True,None)
