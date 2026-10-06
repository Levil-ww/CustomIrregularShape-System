"""Block renderer. Physical geometry is shared by preview and full-size export."""
import math
import numpy as np
from PIL import Image
from shape_crop.core.geometry import create_shape
from shape_crop.core.sampling import content_sample, strip_sample


class RenderCancelled(Exception):
    pass


def blend(rgb, color, coverage):
    weight = np.clip(coverage, 0, 1)[..., None]
    rgb[:] = np.clip(rgb * (1 - weight) + color * weight, 0, 255).astype(np.uint8)


def render(design, outer_material=None, inner_material=None, max_side=None,
           progress=None, cancelled=None, block_rows=128):
    design.validate()
    if block_rows < 1:
        raise ValueError('分块行数必须大于零')
    width, height = design.pixel_size(max_side)
    if width * height > 180_000_000:
        raise ValueError('当前导出超过 1.8 亿像素，请降低 DPI 或尺寸')
    shape = create_shape(design)
    border = design.border
    px_cm = max(design.diameter_cm / width, design.height_cm / height)
    x = ((np.arange(width, dtype=np.float32) + .5) / width - .5) * design.diameter_cm
    x = x[None, :]
    output = Image.new('RGBA', (width, height))
    frame = shape.inset(border.margin_cm)
    content_shape = shape.inset(border.inset_cm)
    inner_r = design.inner_diameter_cm / 2

    def coverage(depth):
        return np.clip(depth / px_cm + .5, 0, 1)

    for start in range(0, height, block_rows):
        if cancelled and cancelled():
            raise RenderCancelled('任务已取消')
        end = min(start + block_rows, height)
        y = ((np.arange(start, end, dtype=np.float32) + .5) / height - .5) * design.height_cm
        y = y[:, None]
        radial = np.hypot(x, y)
        depth = shape.depth(x, y)
        rgb = np.empty((end - start, width, 3), dtype=np.uint8)
        rgb[:] = design.background
        if outer_material:
            content = content_sample(outer_material.content, x, y, content_shape.diameter,
                                     content_shape.height, outer_material.spec)
            blend(rgb, content, coverage(depth - border.inset_cm))
        if border.width_cm > 0:
            band_depth = depth - border.margin_cm
            band_coverage = np.minimum(coverage(band_depth), coverage(border.width_cm - band_depth))
            if outer_material:
                s = frame.boundary_coordinate(x, y)
                texture = strip_sample(outer_material.strip, s, band_depth, frame.perimeter,
                                       border.width_cm, outer_material.spec.border_repeat_cm)
                blend(rgb, texture, band_coverage)
            if border.line_cm > 0:
                for offset in (border.margin_cm, border.inset_cm):
                    blend(rgb, np.asarray(border.color), coverage(border.line_cm / 2 - np.abs(depth - offset)))
        # Thin outline follows the exact outer cut, drawn inward to retain nominal dimensions.
        if border.line_cm > 0:
            blend(rgb, np.asarray(border.color), np.minimum(coverage(depth), coverage(border.line_cm - depth)))
        if inner_r:
            inner_depth = inner_r - radial
            blend(rgb, np.asarray(design.background), coverage(inner_depth))
            selected = inner_material or outer_material
            if selected:
                inner_content_d = 2 * (inner_r - design.inner_border_cm)
                content = content_sample(selected.content, x, y, inner_content_d, inner_content_d, selected.spec)
                blend(rgb, content, coverage(inner_depth - design.inner_border_cm))
                if design.inner_border_cm > 0:
                    s = ((np.arctan2(y, x) + np.pi / 2) % (2 * np.pi)) * inner_r
                    texture = strip_sample(selected.strip, s, inner_depth, 2 * math.pi * inner_r,
                                           design.inner_border_cm, selected.spec.border_repeat_cm)
                    band_cov = np.minimum(coverage(inner_depth), coverage(design.inner_border_cm - inner_depth))
                    blend(rgb, texture, band_cov)
            if border.line_cm > 0:
                for offset in (0, design.inner_border_cm):
                    line = coverage(border.line_cm / 2 - np.abs(inner_depth - offset))
                    blend(rgb, np.asarray(border.color), line)
        alpha = np.round(coverage(depth) * 255).astype(np.uint8)
        rgba = np.concatenate((rgb, alpha[..., None]), axis=2)
        output.paste(Image.fromarray(rgba), (0, start))
        if progress:
            progress(round(end / height * 100))
    return output
