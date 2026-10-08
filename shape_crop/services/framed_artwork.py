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


def detect_framed_artwork(image, frame):
    probe = image.copy()
    probe.thumbnail((1200, 1200))
    pixels = np.asarray(probe)
    h, w = pixels.shape[:2]
    sx, sy = image.width / w, image.height / h
    left, top, right, bottom = [round(v / r) for v, r in zip(frame, (sx, sy, sx, sy))]
    padding = max(4, round(min(h, w) * .012))
    dark = np.max(pixels, axis=2) < 60
    candidates = []
    for box, _ in _components(dark):
        a, b, c, d = box
        if not (w * .4 < c - a < w * .88 and h * .3 < d - b < h * .8):
            continue
        if min(a, b - top, w - c, bottom - d) < max(padding * 2, min(w, h) * .035):
            continue
        if np.mean(dark[b:d, a:c]) < .15:
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
