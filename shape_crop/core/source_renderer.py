"""Source-faithful layout renderer: one scale for both original borders and floral content."""
import numpy as np
from PIL import Image
from shape_crop.core.geometry import CircularBand
from shape_crop.core.sampling import sample
from shape_crop.core.renderer import RenderCancelled, blend


def render_source(design, material, inner_material=None, max_side=None, progress=None,
                  cancelled=None, block_rows=128):
    width, height = design.pixel_size(max_side)
    if width * height > 180_000_000:
        raise ValueError('当前导出超过 1.8 亿像素，请降低 DPI 或尺寸')
    layout = material.source_layout
    shape = CircularBand(design.diameter_cm, design.height_cm)
    # Uniformly fit the original outer rectangle, not the cropped content rectangle.
    scale = max(design.diameter_cm / layout.width_px, design.height_cm / layout.height_px)
    border_cm = layout.border_depth_px * scale
    if border_cm >= shape.half_height:
        raise ValueError('原素材边框过宽，无法用于当前尺寸')
    if design.inner_diameter_cm and design.inner_diameter_cm / 2 >= shape.half_height - border_cm:
        raise ValueError('内圆超出自动识别的外边框内侧')
    px_cm = max(design.diameter_cm / width, design.height_cm / height)
    ring = shape.inset(border_cm / 2) if border_cm else shape
    strip_width = layout.strip.shape[1]
    origin = (strip_width - ring.chord / scale) / 2
    x = ((np.arange(width, dtype=np.float32) + .5) / width - .5)[None, :] * design.diameter_cm
    output = Image.new('RGBA', (width, height))
    def cov(value):
        return np.clip(value / px_cm + .5, 0, 1)
    for start in range(0, height, block_rows):
        if cancelled and cancelled():
            raise RenderCancelled('任务已取消')
        end = min(height, start + block_rows)
        y = ((np.arange(start, end, dtype=np.float32) + .5) / height - .5)[:, None] * design.height_cm
        depth = shape.depth(x, y)
        rgb = sample(layout.image, x / scale + (layout.width_px - 1) / 2,
                     y / scale + (layout.height_px - 1) / 2)
        if border_cm:
            s = ring.boundary_coordinate(x, y)
            stripe = sample(layout.strip, s / scale + origin, np.maximum(0, depth / scale - .5), True)
            blend(rgb, stripe, cov(border_cm - depth))
        if design.inner_diameter_cm:
            radius = design.inner_diameter_cm / 2
            selected = inner_material or material
            inner_layout = selected.source_layout
            if inner_layout is None:
                raise ValueError('自动排版的内圆素材也需采用自动模式')
            inner_depth = radius - np.hypot(x, y)
            inner_scale = scale  # keep flowers the same physical size as the outer fill
            content = sample(inner_layout.image, x / inner_scale + (inner_layout.width_px - 1) / 2,
                             y / inner_scale + (inner_layout.height_px - 1) / 2)
            inner_band = inner_layout.border_depth_px * inner_scale
            if inner_band >= radius:
                raise ValueError('内圆尺寸小于原素材边框宽度')
            if inner_band:
                arc = ((np.arctan2(y, x) + np.pi / 2) % (2 * np.pi)) * max(radius - inner_band / 2, .001)
                stripe = sample(inner_layout.strip, arc / inner_scale,
                                np.maximum(0, inner_depth / inner_scale - .5), True)
                blend(content, stripe, cov(inner_band - inner_depth))
            blend(rgb, content, cov(inner_depth))
        alpha = np.round(cov(depth) * 255).astype(np.uint8)
        output.paste(Image.fromarray(np.concatenate((rgb, alpha[..., None]), axis=2)), (0, start))
        if progress:
            progress(round(end / height * 100))
    return output
