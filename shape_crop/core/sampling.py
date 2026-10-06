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
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    a = image[y0, x0].astype(np.float32) * (1 - fx) + image[y0, x1] * fx
    b = image[y1, x0].astype(np.float32) * (1 - fx) + image[y1, x1] * fx
    return np.clip(a * (1 - fy) + b * fy, 0, 255).astype(np.uint8)


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
