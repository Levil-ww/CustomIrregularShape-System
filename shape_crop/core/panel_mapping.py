"""Map original panel pixels to curved contours with proportional clearance."""
import numpy as np
from shape_crop.core.sampling import sample


def adapt_panel(layout, mapping, shape, border_cm, x, y, pixel_cm=None):
    panel = layout.inset_panel
    left, top, right, bottom = panel.box
    source_left, source_top, source_right, source_bottom = layout.content_box_px
    usable = source_bottom - source_top
    target_usable = shape.height - 2 * border_cm
    gap_fraction = ((top - source_top) + (source_bottom - bottom)) / 2 / usable
    inset = border_cm + gap_fraction * target_usable
    max_inset = shape.half_height - 1e-6
    if inset >= max_inset:
        inset = max(border_cm, 0.0)
    inner = shape.inset(inset)
    if panel.translucent is not None:
        return _sample_translucent_panel(layout, mapping, inner, x, y, pixel_cm or mapping.scale_cm)
    # Move original pixels, including the fade and fine line, together. Undoing
    # a source fade amplifies JPEG noise and cannot recover ink under the line.
    centre_x, centre_y = (left + right) / 2, (top + bottom) / 2
    source_half_h = (bottom - top) / 2
    target_half_h = max(inner.half_height, 1e-6)
    ay = np.abs(y)
    source_y = np.where(ay <= target_half_h, ay * source_half_h / target_half_h,
        source_half_h + (ay - target_half_h) *
        (usable / 2 - source_half_h) / (target_usable / 2 - target_half_h))
    v = centre_y + np.sign(y) * source_y
    # The panel follows the target arcs. Outside its top/bottom, smoothly return
    # to the original horizontal transform to keep the flower band continuous.
    radius = inner.radius
    centre = getattr(inner, 'center', 0.)
    curve_x = centre + np.sqrt(np.maximum(0., radius**2 - np.minimum(ay, target_half_h)**2))
    source_half_w = (right - left) / 2
    original_half_w = source_half_w * mapping.scale_cm
    strength = np.clip((target_usable / 2 - ay) /
                       (target_usable / 2 - target_half_h), 0, 1)
    target_half_w = curve_x * strength + original_half_w * (1 - strength)
    ax = np.abs(x)
    outer_x = shape.diameter / 2 - border_cm
    source_x = np.where(ax <= target_half_w, ax * source_half_w / target_half_w,
        source_half_w + (ax - target_half_w) *
        ((source_right - source_left) / 2 - source_half_w) / (outer_x - target_half_w))
    u = centre_x + np.sign(x) * source_x
    result = sample(layout.content, u - mapping.left, v - mapping.top)
    if panel.artwork is not None:
        bounds, background = panel.artwork
        a, b, c, d = bounds
        ink_x, ink_y = (a + c) / 2, (b + d) / 2
        # The quiet opaque panel and its original ink are separate layers.
        # Fit the entire ink group uniformly; no row-dependent shear reaches
        # letters, even though the panel's thin outline follows the side arcs.
        target_y = (ink_y - centre_y) / source_half_h * inner.half_height
        target_x = (ink_x - centre_x) / source_half_w * inner.chord / 2
        ink_scale = min(mapping.scale_cm, inner.chord / max(1, c - a + 4),
                        inner.height / max(1, d - b + 4))
        ink_u = ink_x + (x - target_x) / ink_scale
        ink_v = ink_y + (y - target_y) / ink_scale
        inside = inner.depth(x, y) > 3 * mapping.scale_cm
        result = np.where(inside[..., None], background, result).astype(np.uint8)
        selected = inside & (ink_u >= a) & (ink_u <= c) & (ink_v >= b) & (ink_v <= d)
        original = sample(layout.image, ink_u, ink_v)
        result = np.where(selected[..., None], original, result)
    return result


def _sample_translucent_panel(layout, mapping, inner, x, y, pixel_cm):
    """Keep one uniform artwork transform and move only the fade/outline mask."""
    panel = layout.inset_panel
    fade_box, opacity, background, thickness, colour = panel.translucent
    left, top, right, bottom = panel.box
    u, v = np.broadcast_arrays(x / mapping.scale_cm + mapping.centre_x,
                               y / mapping.scale_cm + mapping.centre_y)
    rgb = sample(layout.image, u, v).astype(np.float32)
    # A source outline hides its original ink. Interpolate only across that
    # narrow stroke, never bend the surrounding flowers to move the outline.
    pad = thickness + 1
    for horizontal, lo, hi, start, end in ((True, top, bottom, left, right),
                                          (False, left, right, top, bottom)):
        coordinate, other = (v, u) if horizontal else (u, v)
        for edge in (lo, hi):
            selected = (np.abs(coordinate - edge) <= pad) & (other >= start - pad) & (other <= end + pad)
            rows, columns = np.nonzero(selected)
            if not len(rows):
                continue
            a, b = edge - pad - 1, edge + pad + 1
            o = other[rows, columns]
            first = sample(layout.image, o, a) if horizontal else sample(layout.image, a, o)
            last = sample(layout.image, o, b) if horizontal else sample(layout.image, b, o)
            weight = ((coordinate[rows, columns] - a) / (b - a))[:, None]
            rgb[rows, columns] = first * (1 - weight) + last * weight
    for cx in (left, right):
        for cy in (top, bottom):
            selected = (np.abs(u-cx) <= pad) & (np.abs(v-cy) <= pad)
            rows, columns = np.nonzero(selected)
            if not len(rows):
                continue
            a, b, c, d = cx-pad-1, cy-pad-1, cx+pad+1, cy+pad+1
            fx = ((u[rows, columns]-a)/(c-a))[:, None]
            fy = ((v[rows, columns]-b)/(d-b))[:, None]
            upper = sample(layout.image, a, b)*(1-fx) + sample(layout.image, c, b)*fx
            lower = sample(layout.image, a, d)*(1-fx) + sample(layout.image, c, d)*fx
            rgb[rows, columns] = upper*(1-fy) + lower*fy
    a, b, c, d = fade_box
    background = np.asarray(background, dtype=np.float32)
    levels = panel.translucent_levels
    # A validated source repeat can recover ink hidden by the vertical
    # stroke exactly in place, instead of interpolating across a flower.
    if panel.stroke_repeat_px and levels is not None:
        dark, light = (np.asarray(value, dtype=np.float32) for value in levels)
        contrast = np.maximum(light-dark, 1)
        pending = ((np.minimum(np.abs(u-left), np.abs(u-right)) <= pad) &
                   (v > top+pad) & (v < bottom-pad))
        for shift in (panel.stroke_repeat_px, -panel.stroke_repeat_px):
            ru = u+shift
            valid = (pending & (ru >= 0) & (ru < layout.width_px) &
                     (np.minimum(np.abs(ru-left), np.abs(ru-right)) > pad))
            rows, columns = np.nonzero(valid)
            if not len(rows):
                continue
            consistent = np.ones(len(rows), dtype=bool)
            for offset in (-pad-2, pad+2):
                source_u = u[rows,columns]+offset
                reference_u = ru[rows,columns]+offset
                first = sample(layout.image, source_u, v[rows,columns]).astype(np.float32)
                second = sample(layout.image, reference_u, v[rows,columns]).astype(np.float32)
                first_fade = (source_u >= a) & (source_u <= c)
                second_fade = (reference_u >= a) & (reference_u <= c)
                first = np.where(first_fade[:,None], first, dark+first*contrast/np.maximum(background,1))
                second = np.where(second_fade[:,None], second, dark+second*contrast/np.maximum(background,1))
                consistent &= np.max(np.abs(first-second), axis=1) <= 8
            rows, columns = rows[consistent], columns[consistent]
            if not len(rows):
                continue
            reference = sample(layout.image, ru[rows,columns], v[rows,columns]).astype(np.float32)
            in_fade = ((ru[rows,columns] >= a) & (ru[rows,columns] <= c) &
                       (v[rows,columns] >= b) & (v[rows,columns] <= d))
            reference = np.where(in_fade[:,None], reference,
                                 dark+reference*contrast/np.maximum(background,1))
            rgb[rows,columns] = reference
            pending[rows,columns] = False
    original = rgb.copy()
    faded = (u >= a) & (u <= c) & (v >= b) & (v <= d)
    if levels is not None:
        dark, light = (np.asarray(value, dtype=np.float32) for value in levels)
        contrast = np.maximum(light-dark, 1)
        recovered = (rgb-dark)*background/contrast
        black = np.max(np.abs(rgb-dark), axis=2) <= 8
        recovered[black] = 0
    else:
        recovered = (rgb - background * opacity) / (1 - opacity)
    # Flat-background JPEG fluctuations are not hidden floral detail.
    quiet = np.max(np.abs(rgb - background), axis=2) <= 3
    recovered[quiet] = background
    ceiling = background if levels is not None else 255
    rgb = np.where(faded[..., None], np.clip(recovered, 0, ceiling), rgb)
    boundary = np.zeros(rgb.shape[:-1], dtype=bool)
    if levels is not None:
        # Unflatten before interpolating across the original mask edge.
        # Interpolating clear black with faded black first creates a grey
        # seam that no subsequent binary inside/outside test can remove.
        edge_radius = 1.
        for axis,position,_,_,_ in panel.partial_fade_edges:
            edges = (a,c) if axis else (b,d)
            edge_radius = max(edge_radius, min(abs(position-edges[0]),abs(position-edges[1]))+1)
        boundary = (((np.minimum(np.abs(u-a), np.abs(u-c)) <= edge_radius) & (v >= b-edge_radius) & (v <= d+edge_radius)) |
                    ((np.minimum(np.abs(v-b), np.abs(v-d)) <= edge_radius) & (u >= a-edge_radius) & (u <= c+edge_radius)))
        repaired_stroke = (((np.minimum(np.abs(u-left), np.abs(u-right)) <= pad) &
                            (v >= top-pad) & (v <= bottom+pad)) |
                           ((np.minimum(np.abs(v-top), np.abs(v-bottom)) <= pad) &
                            (u >= left-pad) & (u <= right+pad)))
        boundary &= ~repaired_stroke
        rows, columns = np.nonzero(boundary)
        if len(rows):
            uu, vv = u[rows,columns], v[rows,columns]
            base_u, base_v = np.floor(uu), np.floor(vv)
            fx, fy = uu-base_u, vv-base_v
            clean = np.zeros((len(rows),3), dtype=np.float32)
            for dx, dy, weight in ((0,0,(1-fx)*(1-fy)), (1,0,fx*(1-fy)),
                                   (0,1,(1-fx)*fy), (1,1,fx*fy)):
                source_u, source_v = base_u+dx, base_v+dy
                pixel = sample(layout.image, source_u, source_v).astype(np.float32)
                restored = np.clip((pixel-dark)*background/contrast, 0, background)
                restored[np.max(np.abs(pixel-dark),axis=1) <= 8] = 0
                restored[np.max(np.abs(pixel-background),axis=1) <= 3] = background
                covered = (source_u >= a) & (source_u <= c) & (source_v >= b) & (source_v <= d)
                clean_pixel = np.where(covered[:,None], restored, pixel)
                for axis,position,lo,hi,floor in panel.partial_fade_edges:
                    coordinate, other = (source_u,source_v) if axis else (source_v,source_u)
                    selected = (coordinate == position) & (other >= lo) & (other < hi)
                    edge_floor = np.asarray(floor,dtype=np.float32)
                    edge_pixel = np.clip((pixel-edge_floor)*background/np.maximum(background-edge_floor,1),0,background)
                    edge_pixel[np.max(np.abs(pixel-edge_floor),axis=1) <= 8] = 0
                    edge_pixel[np.max(np.abs(pixel-background),axis=1) <= 3] = background
                    clean_pixel = np.where(selected[:,None],edge_pixel,clean_pixel)
                clean_pixel = _repair_partial_fade_ink(layout,panel,source_u,source_v,
                                                       pixel,clean_pixel,background,dark)
                clean += clean_pixel*weight[:,None]
            rgb[rows,columns] = clean
    depth = inner.depth(x, y)
    # The original fade has clearance outside its fine outline. Move that
    # outer mask with the contour too, rather than cutting the fade at the
    # stroke and exposing a rectangular seam through the flowers.
    side_clearance = max(0., float(np.mean((left-a, c-right)))) * mapping.scale_cm
    limit = 2*max(side_clearance, max(top-b, d-bottom, 0.)*mapping.scale_cm)
    top_clearance = np.clip((mapping.centre_y-b)*mapping.scale_cm-inner.half_height, 0, limit)
    bottom_clearance = np.clip((d-mapping.centre_y)*mapping.scale_cm-inner.half_height, 0, limit)
    vertical_clearance = np.where(y < 0, top_clearance, bottom_clearance)
    weight = np.clip(np.abs(y)/max(inner.half_height, 1e-6), 0, 1)
    fade_clearance = side_clearance*(1-weight) + vertical_clearance*weight
    fade_depth = depth + fade_clearance
    coverage = np.clip(fade_depth / pixel_cm + .5, 0, 1)[..., None]
    painted = dark + rgb*contrast/np.maximum(background, 1) if levels is not None else rgb*(1-opacity)+background*opacity
    rgb = rgb*(1-coverage) + painted*coverage
    overlap = faded & ~boundary & (fade_depth >= pixel_cm/2)
    rgb[overlap] = original[overlap]
    line_cm = thickness * mapping.scale_cm
    line = (np.clip(depth / pixel_cm + .5, 0, 1) *
            np.clip((line_cm - depth) / pixel_cm + .5, 0, 1))[..., None]
    rgb = rgb * (1 - line) + np.asarray(colour) * line
    rgb = _remove_neutral_frame_ringing(rgb, u, v, panel, background)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def _remove_neutral_frame_ringing(rgb, u, v, panel, background):
    """Remove neutral JPEG luminance overshoot only beside the old source frame."""
    radius = max(3., 2*panel.translucent[3])
    selected = np.zeros(rgb.shape[:-1], dtype=bool)
    for a, b, c, d in (panel.box, panel.translucent[0]):
        selected |= ((np.minimum(np.abs(u-a), np.abs(u-c)) <= radius) &
                     (v >= b-radius) & (v <= d+radius))
        selected |= ((np.minimum(np.abs(v-b), np.abs(v-d)) <= radius) &
                     (u >= a-radius) & (u <= c+radius))
    delta = rgb-background
    # Compression ringing shifts luminance while retaining the cream hue.
    # Actual white/coloured artwork changes channel differences and remains.
    selected &= ((np.min(delta, axis=-1) >= 0) & (np.max(delta, axis=-1) > 3) &
                 (np.ptp(delta, axis=-1) <= 6))
    return np.where(selected[...,None], background, rgb)


def _repair_partial_fade_ink(layout,panel,u,v,pixel,clean,background,dark):
    """Resolve nearly opaque edge ambiguity from ink on both untouched sides."""
    a,b,c,d = panel.translucent[0]
    for axis,edge,low in ((1,a,True),(1,c,False),(0,b,True),(0,d,False)):
        ends = (a,c) if axis else (b,d)
        entries = [item for item in panel.partial_fade_edges if item[0] == axis and
                   (abs(item[1]-ends[0]) < abs(item[1]-ends[1])) == low]
        if not entries:
            continue
        positions = [item[1] for item in entries]
        exterior = min(positions)-2 if low else max(positions)+2
        # JPEG's eight-pixel block can contaminate the first complete-fade
        # pixels too; the reference must lie beyond that transition block.
        interior = edge+(1 if low else -1)*max(8,len(entries)+2)
        coordinate,other = (u,v) if axis else (v,u)
        selected = ((coordinate >= min(exterior,interior)+1) &
                    (coordinate <= max(exterior,interior)-1) &
                    (other >= entries[0][2]) & (other < entries[0][3]))
        indexes = np.flatnonzero(selected)
        if not len(indexes):
            continue
        other = other[indexes]
        outside = sample(layout.image,np.full_like(other,exterior) if axis else other,
                         other if axis else np.full_like(other,exterior)).astype(np.float32)
        inside = sample(layout.image,np.full_like(other,interior) if axis else other,
                        other if axis else np.full_like(other,interior)).astype(np.float32)
        foreground = (np.max(outside,axis=1) < 40) & (np.max(np.abs(inside-dark),axis=1) <= 8)
        plain = (np.max(np.abs(outside-background),axis=1) <= 6) & (np.max(np.abs(inside-background),axis=1) <= 6)
        opaque = np.zeros(len(indexes),dtype=bool)
        for _,position,_,_,floor in entries:
            if np.median(np.asarray(floor)/np.maximum(background,1)) > .94:
                opaque |= coordinate[indexes] == position
        # Near opaque source pixels contain too little contrast to distinguish
        # ink from blank JPEG noise. Use only agreeing endpoint evidence.
        suspect = (np.max(np.abs(pixel[indexes]-background),axis=1) > 3) | opaque
        clean[indexes[foreground & suspect]] = 0
        clean[indexes[plain & opaque]] = background
    return clean
