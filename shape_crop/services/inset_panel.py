"""Recognize closed translucent or pale inset panels over full-span artwork."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class InsetPanel:
    box: tuple
    artwork: object = None


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
    return InsetPanel(box)


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
