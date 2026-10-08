"""Sample a complete independent picture over its original repeating background."""
import numpy as np
from shape_crop.core.sampling import sample
from shape_crop.core.renderer import blend


def sample_framed_artwork(layout, mapping, native_scale, x, y, pixel_cm):
    artwork = layout.framed_artwork
    ox, oy = artwork.origin
    u = x / native_scale + (layout.width_px - 1) / 2 - ox
    v = y / native_scale + (layout.height_px - 1) / 2 - oy
    result = sample(artwork.tile, u, v, wrap_x=True, wrap_y=True)
    left, top, right, bottom = (round(value) for value in artwork.box)
    picture = layout.image[top:bottom, left:right]
    u = x / mapping.scale_cm + mapping.centre_x - left
    v = y / mapping.scale_cm + mapping.centre_y - top
    distance = np.minimum(np.minimum(u + .5, right - left - .5 - u),
                          np.minimum(v + .5, bottom - top - .5 - v)) * mapping.scale_cm
    coverage = np.clip(distance / pixel_cm + .5, 0, 1)
    blend(result, sample(picture, u, v), coverage)
    return result
