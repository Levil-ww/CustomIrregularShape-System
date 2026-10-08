"""Map original panel pixels to curved contours with proportional clearance."""
import numpy as np
from shape_crop.core.sampling import sample


def adapt_panel(layout, mapping, shape, border_cm, x, y):
    panel = layout.inset_panel
    left, top, right, bottom = panel.box
    source_left, source_top, source_right, source_bottom = layout.content_box_px
    usable = source_bottom - source_top
    target_usable = shape.height - 2 * border_cm
    gap_fraction = ((top - source_top) + (source_bottom - bottom)) / 2 / usable
    inset = border_cm + gap_fraction * target_usable
    inner = shape.inset(inset)
    # Move original pixels, including the fade and fine line, together. Undoing
    # a source fade amplifies JPEG noise and cannot recover ink under the line.
    centre_x, centre_y = (left + right) / 2, (top + bottom) / 2
    source_half_h = (bottom - top) / 2
    target_half_h = inner.half_height
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
    return sample(layout.content, u - mapping.left, v - mapping.top)
