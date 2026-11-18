"""Render a symmetric belly outline while preserving the source perimeter strip."""
import math
import numpy as np
from PIL import Image, ImageDraw
from shape_crop.core.belly_geometry import BellyOutline
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.renderer import MAX_PIXEL_COUNT, RenderCancelled, blend
from shape_crop.core.sampling import sample_perimeter_strip, uniform_strip_band


def render_belly(design, material, inner_material=None, max_side=None, progress=None,
                 cancelled=None, block_rows=128):
    width, height = design.pixel_size(max_side)
    if width * height > MAX_PIXEL_COUNT:
        raise ValueError('当前导出超过 1.8 亿像素，请降低 DPI 或尺寸')
    if material is None or material.source_layout is None:
        raise ValueError('马肚形需要使用自动排版的矩形素材')
    if design.inner_diameter_cm or inner_material is not None:
        raise ValueError('马肚形暂不支持同心内圆')
    if design.belly_reference_approximation:
        raise ValueError('马肚形必须按输入的 C、D 生成，不能使用修改尺寸的效果图近似模式')
    layout = material.source_layout
    if (layout.category not in ('纯色边框类', '原图填充类', '周期装饰边框类') or
            layout.strip_is_sentence or layout.corner_gaps is not None or
            layout.layered_strip is not None or layout.corner_composition is not None or
            layout.contoured_frame is not None or layout.floating_artwork is not None or
            layout.framed_artwork is not None or layout.inset_panel is not None or
            layout.patterned_inset is not None):
        raise ValueError('此素材含特殊边框或独立图案，马肚形暂不支持自动适配，请使用普通矩形边框素材')
    shape = BellyOutline(design.diameter_cm, design.height_cm, design.belly_c_cm,
                         design.belly_d_cm, design.belly_corner_cm)
    source_scale = ContentMapping.source_scale(layout, shape.width, shape.height)
    border = max(layout.border_depth_px * source_scale,
                 ContentMapping.required_border(layout, shape.width, shape.height)) if layout.border_depth_px else 0
    if border >= shape.height / 2:
        raise ValueError('素材边框过宽，无法用于当前马肚形尺寸')
    extra = max(0., border - layout.border_depth_px * source_scale)
    plain_band = uniform_strip_band(layout.strip) if extra > 1e-9 and layout.border_depth_px else None
    if extra > 1e-9 and layout.strip_period_px and plain_band is None:
        raise ValueError('素材边框需要加宽，但缺少可扩展的纯色留白，请选择尺寸比例更接近的素材')
    mapping = ContentMapping.create(layout, shape.width, shape.height, border)
    strip = layout.strip
    if layout.category == '纯色边框类':
        # A closed thin frame is uniform along its length.  Median sampling
        # removes occasional artwork that touches the detected source strip.
        strip = np.median(strip, axis=1).astype(np.uint8)[:, None, :]
    px_cm = max(shape.width / width, shape.height / height)
    points = np.asarray(shape.points(96), dtype=np.float64)
    vertices = np.column_stack(((points[:, 0] / shape.width + .5) * width - .5,
                                (points[:, 1] / shape.height + .5) * height - .5))
    starts, ends = vertices[:-1], vertices[1:]
    vectors = ends - starts
    lengths = np.hypot(vectors[:, 0], vectors[:, 1])
    cumulative = np.r_[0., np.cumsum(lengths)]
    perimeter_cm = cumulative[-1] * px_cm
    reference_depth = 0.
    if layout.strip_period_px and border:
        strength = np.max(np.ptp(layout.strip, axis=1), axis=1).astype(np.float64)
        if strength.sum():
            source_centre = float(np.average(np.arange(len(strength)) + .5, weights=strength))
            reference_depth = source_centre * source_scale
            if plain_band and source_centre >= plain_band[1]:
                reference_depth += extra
            reference_depth = min(reference_depth, border, perimeter_cm / (2 * math.pi) * .9)
    angles = np.unwrap(np.arctan2(vectors[:, 1], vectors[:, 0]))
    turns = angles - angles[0]
    turns = np.r_[turns, 2 * math.pi]
    reference_perimeter = perimeter_cm - 2 * math.pi * reference_depth
    mask = Image.new('L', (width, height))
    ImageDraw.Draw(mask).polygon([tuple(p) for p in vertices], fill=255)
    band_px = border / px_cm + 2
    output = Image.new('RGBA', (width, height))
    x = ((np.arange(width, dtype=np.float32) + .5) / width - .5)[None, :] * shape.width
    for start in range(0, height, block_rows):
        if cancelled and cancelled():
            raise RenderCancelled('任务已取消')
        end = min(height, start + block_rows)
        y = ((np.arange(start, end, dtype=np.float32) + .5) / height - .5)[:, None] * shape.height
        rgb = mapping.sample(layout, x, y)
        inside = np.asarray(mask.crop((0, start, width, end))) > 0
        best_grid = np.full((end - start, width), np.inf, dtype=np.float32)
        along_grid = np.zeros((end - start, width), dtype=np.float32)
        for i, (a, vector, length) in enumerate(zip(starts, vectors, lengths)):
            if length < 1e-9 or max(a[1], a[1] + vector[1]) + band_px < start or min(a[1], a[1] + vector[1]) - band_px >= end:
                continue
            x0 = max(0, math.floor(min(a[0], a[0] + vector[0]) - band_px))
            x1 = min(width, math.ceil(max(a[0], a[0] + vector[0]) + band_px) + 1)
            y0 = max(start, math.floor(min(a[1], a[1] + vector[1]) - band_px))
            y1 = min(end, math.ceil(max(a[1], a[1] + vector[1]) + band_px) + 1)
            if x0 >= x1 or y0 >= y1:
                continue
            dx = np.arange(x0, x1)[None, :] - a[0]
            dy = np.arange(y0, y1)[:, None] - a[1]
            t = np.clip((dx * vector[0] + dy * vector[1]) / (length * length), 0, 1)
            distance = np.hypot(dx - t * vector[0], dy - t * vector[1])
            best_region = best_grid[y0 - start:y1 - start, x0:x1]
            along_region = along_grid[y0 - start:y1 - start, x0:x1]
            better = distance < best_region
            best_region[better] = distance[better]
            coordinate = ((cumulative[i] + t * length) * px_cm -
                          reference_depth * (turns[i] + t * (turns[i + 1] - turns[i])))
            along_region[better] = coordinate[better]
        rows, cols = np.nonzero(best_grid <= band_px)
        best = best_grid[rows, cols]
        along = along_grid[rows, cols]
        depth = best * px_cm
        if border:
            selected = inside[rows, cols] & (depth < border + px_cm / 2)
            rr, cc = rows[selected], cols[selected]
            # Map the physical border depth back onto the original strip.
            physical_depth = depth[selected]
            if plain_band is not None:
                band_start, band_end = (v * source_scale for v in plain_band)
                physical_depth = np.where(physical_depth < band_start, physical_depth,
                    np.where(physical_depth < band_end + extra,
                             band_start + (physical_depth - band_start) * (band_end - band_start) / (band_end - band_start + extra),
                             physical_depth - extra))
                source_depth = np.maximum(0, physical_depth / source_scale - .5)
            else:
                source_depth = np.maximum(0, physical_depth / border * layout.border_depth_px - .5)
            stripe = sample_perimeter_strip(strip, along[selected] % reference_perimeter, source_depth,
                                             reference_perimeter, source_scale)
            pixels = rgb[rr, cc]
            blend(pixels, stripe, np.clip((border - depth[selected]) / px_cm + .5, 0, 1))
            rgb[rr, cc] = pixels
        # Draw coverage at four samples per axis.  Work one block at a time so
        # full-resolution exports do not allocate a 16x-sized image.
        antialias = 4
        coverage = Image.new('L', (width * antialias, (end - start) * antialias))
        ImageDraw.Draw(coverage).polygon([
            ((vx + .5) * antialias - .5, (vy + .5 - start) * antialias - .5)
            for vx, vy in vertices], fill=255)
        alpha = np.asarray(coverage.resize((width, end - start), Image.Resampling.BOX))
        result = np.concatenate((rgb, alpha[..., None]), axis=2)
        output.paste(Image.fromarray(result, 'RGBA'), (0, start))
        if progress:
            progress(round(end / height * 100))
    return output
