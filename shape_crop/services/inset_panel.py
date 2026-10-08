"""Recognize a thin rectangular outline over translucent full-span artwork."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class InsetPanel:
    box: tuple


def detect_inset_panel(image):
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
