"""Recognize isolated outline circles and sample whole glyphs at contour joints."""
import numpy as np
from shape_crop.core.sampling import sample


def recognize_round_ring(strip):
    """Return a verified circular source glyph; other ornaments keep their mapping."""
    height, width = strip.shape[:2]
    if width < 8 or height < 8:
        return None
    background = np.median(strip, axis=1).astype(np.float32)
    difference = np.max(np.abs(strip.astype(np.float32) - background[:, None]), axis=2)
    rows = np.flatnonzero(np.max(difference, axis=1) > 30)
    if not len(rows):
        return None
    start, end = int(rows[0]), int(rows[-1]) + 1
    diameter = end - start
    if diameter < 8 or np.max(np.ptp(background[start:end], axis=0)) > 20:
        return None
    ink = difference > 24
    middle = (start + end - 1) / 2
    repeated = np.tile(ink[int(round(middle))], 3)
    changes = np.diff(np.r_[True, repeated, True].astype(np.int8))
    starts, ends = np.flatnonzero(changes == -1), np.flatnonzero(changes == 1)
    centres = [(a + b - 1) / 2 - width for a, b in zip(starts, ends)
               if width <= (a + b - 1) / 2 < 2 * width and
               .70 * diameter <= b - a <= 1.05 * diameter]
    if not centres:
        return None
    pitch = width / len(centres)
    if not .85 * diameter <= pitch <= 1.35 * diameter:
        return None
    radius = (diameter - 1) / 2
    pad = int(np.ceil(radius)) + 2
    xs = np.arange(-pad, pad + 1)
    ys = np.arange(max(0, start - 2), min(height, end + 2))
    first_glyph, first_colour, first_mass = None, None, None
    for centre in centres:
        glyph = sample(strip, (xs + centre)[None], ys[:, None], wrap_x=True)
        yy, xx = np.meshgrid(ys - middle, xs, indexing='ij')
        distance = np.hypot(xx, yy)
        bg = background[ys]
        contrast = np.max(np.abs(glyph.astype(float) - bg[:, None]), axis=2)
        foreground = contrast > 24
        inside = distance < radius * .65
        boundary = foreground & (distance <= radius + 1)
        if (np.mean(foreground[inside]) > .03 or boundary.sum() < radius * 2 or
                np.mean(np.abs(distance[boundary] - radius) <= max(2, radius * .18)) < .90):
            return None
        # Angular coverage is only a shape check; prove the actual hole is
        # enclosed with four-connected background reachability as well.
        angles = ((np.arctan2(yy[boundary], xx[boundary]) + np.pi) *
                  16 / (2 * np.pi)).astype(int) % 16
        if len(np.unique(angles)) < 16:
            return None
        clear = contrast <= 12
        reachable = np.zeros_like(clear)
        reachable[0] = clear[0]
        reachable[-1] = clear[-1]
        reachable[:, 0] = clear[:, 0]
        reachable[:, -1] = clear[:, -1]
        while True:
            expanded = reachable.copy()
            expanded[1:] |= reachable[:-1]
            expanded[:-1] |= reachable[1:]
            expanded[:, 1:] |= reachable[:, :-1]
            expanded[:, :-1] |= reachable[:, 1:]
            expanded &= clear
            if np.array_equal(expanded, reachable):
                break
            reachable = expanded
        if np.any(reachable[inside]):
            return None
        solid = contrast > 60
        if not np.any(solid):
            return None
        colour = np.median(glyph[solid], axis=0)
        # Every cell in the source period must be round and share its ink.
        # Do not replace alternating coloured or mixed ornaments by one glyph.
        if first_colour is not None and np.max(np.abs(colour - first_colour)) > 20:
            return None
        mass = contrast[distance <= radius + 1].sum()
        if first_mass is not None and abs(mass - first_mass) > first_mass * .20:
            return None
        if first_glyph is None:
            glyph[distance > radius + 1] = np.broadcast_to(bg[:, None], glyph.shape)[distance > radius + 1]
            first_glyph, first_colour, first_mass = glyph, colour, mass
    glyph = first_glyph
    return glyph, pad, middle - ys[0], middle, pitch, start, end, background


def sample_round_rings(ornament, ring, scale, x, y, source_depth, stripe):
    """Place complete source circles with a shared centre at every contour joint."""
    glyph, gx, gy, middle, pitch, start, end, background = ornament
    selected = (source_depth >= start - 1) & (source_depth <= end)
    if not np.any(selected):
        return stripe
    xx, yy = x[selected], y[selected]
    spacing = pitch * scale
    centre = getattr(ring, 'center', 0.)
    # Each segment includes its endpoint circles. Adjacent segments agree on
    # the same Cartesian centre, avoiding the miter split of perimeter pixels.
    count = max(1, round(ring.chord / spacing))
    step = ring.chord / count
    line_x = (-ring.chord / 2 + np.clip(np.rint((xx + ring.chord / 2) / step), 0, count) * step
              if step > 1e-9 else np.zeros_like(xx))
    line_y = np.where(yy < 0, -ring.half_height, ring.half_height)
    theta = np.arctan2(yy, np.abs(xx) - centre)
    arc_count = max(1, round(2 * ring.radius * ring.angle / spacing))
    angle_step = 2 * ring.angle / arc_count
    angle = -ring.angle + np.clip(np.rint((theta + ring.angle) / angle_step), 0, arc_count) * angle_step
    arc_x = np.where(xx < 0, -1, 1) * (centre + ring.radius * np.cos(angle))
    arc_y = ring.radius * np.sin(angle)
    line_distance = np.hypot(xx - line_x, yy - line_y)
    arc_distance = np.hypot(xx - arc_x, yy - arc_y)
    line = line_distance <= arc_distance
    cx, cy = np.where(line, line_x, arc_x), np.where(line, line_y, arc_y)
    u, v = gx + (xx - cx) / scale, gy + (yy - cy) / scale
    base = sample(background[:, None].astype(np.uint8), np.zeros_like(u), source_depth[selected])
    valid = (u >= 0) & (u <= glyph.shape[1]-1) & (v >= 0) & (v <= glyph.shape[0]-1)
    colours = sample(glyph, u, v)
    stripe[selected] = np.where(valid[:, None], colours, base)
    return stripe
