"""Vectorized bilinear sampling. Coordinates are source pixel centres."""
import numpy as np


def sample(image, x, y, wrap_x=False, wrap_y=False):
    height, width = image.shape[:2]
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    x = x % width if wrap_x else np.clip(x, 0, width - 1)
    y = y % height if wrap_y else np.clip(y, 0, height - 1)
    x0, y0 = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
    x1 = (x0 + 1) % width if wrap_x else np.minimum(x0 + 1, width - 1)
    y1 = (y0 + 1) % height if wrap_y else np.minimum(y0 + 1, height - 1)
    # Subtracting int32 indices promotes float32 coordinates to float64 in NumPy.
    # Keep interpolation at float32 to halve temporary bandwidth and memory.
    fx, fy = (x - x0.astype(np.float32))[..., None], (y - y0.astype(np.float32))[..., None]
    a = image[y0, x0].astype(np.float32) * (1 - fx) + image[y0, x1] * fx
    b = image[y1, x0].astype(np.float32) * (1 - fx) + image[y1, x1] * fx
    return np.clip(a * (1 - fy) + b * fy, 0, 255).astype(np.uint8)


def sample_perimeter_strip(image, arc_length, depth_px, perimeter_cm, source_scale_cm, origin=0.):
    """Close the perimeter with an integer count of complete source periods.

    The tiny tangential scale adjustment avoids a phase jump at the contour start for
    arbitrary centimetre dimensions. Radial thickness continues to use the source scale.
    """
    period_px = image.shape[1]
    repeats = max(1, round(perimeter_cm / (period_px * source_scale_cm)))
    u = arc_length / perimeter_cm * repeats * period_px + origin
    return sample(image, u, depth_px, wrap_x=True)


def sample_sentence_strip(image, arc_length, depth_px, segment_lengths_cm, source_scale_cm,
                          sentence_layers):
    """Apply original edge ink at its source anchor without perimeter repeats."""
    lengths = np.asarray(segment_lengths_cm, dtype=np.float64)
    ends = np.cumsum(lengths)
    position = np.asarray(arc_length) % ends[-1]
    segment = np.minimum(np.searchsorted(ends, position, side='right'), len(lengths) - 1)
    starts = np.r_[0., ends[:-1]]
    depths = np.broadcast_to(depth_px, position.shape)
    result = sample(image, np.zeros_like(position), depths)
    for index, entry in enumerate(sentence_layers):
        if entry is None:
            continue
        layer, anchor = entry
        selected = segment == index
        ink_columns = np.flatnonzero(np.any(layer[..., 3] > 0, axis=0))
        if not ink_columns.size:
            continue
        half_ink_px = (ink_columns[-1] - ink_columns[0] + 1) / 2
        half_ink_cm = half_ink_px * source_scale_cm
        half_fraction = half_ink_px / max(1, layer.shape[1] - 1)
        ink_rows = np.flatnonzero(np.any(layer[..., 3] > 0, axis=1))
        clearance = (ink_rows[-1] - ink_rows[0] + 1) * source_scale_cm
        if anchor < .5:
            centre = max(clearance, max(0., anchor - half_fraction) * lengths[index]) + half_ink_cm
        else:
            centre = lengths[index] - max(clearance, max(0., 1 - anchor - half_fraction) * lengths[index]) - half_ink_cm
        local = position[selected] - starts[index] - centre
        u = (layer.shape[1] - 1) / 2 + local / source_scale_cm
        ink = sample(layer, u, depths[selected])
        alpha = ink[..., 3:4].astype(np.float32) / 255
        valid = (u >= 0) & (u <= layer.shape[1] - 1) & (depths[selected] >= 0) & (depths[selected] <= layer.shape[0] - 1)
        alpha *= valid[..., None]
        result[selected] = np.clip(result[selected] * (1 - alpha) + ink[..., :3] * alpha, 0, 255).astype(np.uint8)
    return result


def uniform_strip_band(strip):
    """Find the longest flat colour band that can absorb extra frame clearance."""
    uniform = np.max(np.ptp(strip, axis=1), axis=1) <= 8
    colours = np.mean(strip, axis=1)
    best, start = (0, 0), None
    for row in range(len(strip)):
        same_colour = row == 0 or np.max(np.abs(colours[row] - colours[row - 1])) <= 8
        if start is not None and (not uniform[row] or not same_colour):
            if row - start > best[1] - best[0]:
                best = (start, row)
            start = None
        if uniform[row] and start is None:
            start = row
    if start is not None and len(strip) - start > best[1] - best[0]:
        best = (start, len(strip))
    return best if best[1] - best[0] >= 3 else None


def content_sample(image, x, y, width_cm, height_cm, material):
    h, w = image.shape[:2]
    if material.fit == 'tile':
        tile_h = material.tile_width_cm * h / w
        return sample(image, (x + width_cm / 2) * w / material.tile_width_cm - .5,
                      (y + height_cm / 2) * h / tile_h - .5, True, True)
    scale = max(width_cm / w, height_cm / h)
    return sample(image, x / scale + (w - 1) / 2, y / scale + (h - 1) / 2)


def strip_sample(image, arc_length, depth, perimeter, band_width, repeat_cm):
    h, w = image.shape[:2]
    if repeat_cm == 0:
        repeat_cm = band_width * w / h
    repeats = max(1, round(perimeter / repeat_cm))
    u = arc_length / perimeter * repeats * w - .5
    v = depth / band_width * h - .5
    return sample(image, u, v, wrap_x=True)
