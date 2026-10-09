"""Preserve source frames and uniformly fit artwork according to its visual layout."""
import numpy as np
from PIL import Image
from shape_crop.core.geometry import create_shape, inset_boundary_fraction
from shape_crop.core.sampling import sample_perimeter_strip, sample_sentence_strip, uniform_strip_band, sample
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.framed_artwork_mapping import sample_framed_artwork
from shape_crop.core.panel_mapping import adapt_panel
from shape_crop.core.renderer import RenderCancelled, blend, MAX_PIXEL_COUNT


def render_source(design, material, inner_material=None, max_side=None, progress=None,
                  cancelled=None, block_rows=128):
    width, height = design.pixel_size(max_side)
    if width * height > MAX_PIXEL_COUNT:
        raise ValueError('当前导出超过 1.8 亿像素，请降低 DPI 或尺寸')
    layout = material.source_layout
    shape = create_shape(design)
    # One uniform scale covers both target dimensions; do not stretch the frame
    # to compensate for missing source height.
    scale = ContentMapping.source_scale(layout, design.diameter_cm, design.height_cm)
    if layout.texture_fill:
        # The fine outline follows the fitting rectangle scale; a very narrow
        # source may need a much larger cover scale for its interior texture.
        scale = min(design.diameter_cm / layout.width_px, design.height_cm / layout.height_px)
    native_border_cm = layout.border_depth_px * scale
    if layout.texture_fill:
        # Crop the entire source stroke, but keep the output outline at most
        # two millimetres. Missing source strokes get a half-millimetre line.
        native_border_cm = min(native_border_cm, .20) if native_border_cm else .05
    border_cm = native_border_cm
    # Use one symmetric frame width covering all original edges and the size allowance.
    # Every frame layer shares this radial scale; artwork uses one uniform transform.
    required_border = ContentMapping.required_border(layout, design.diameter_cm, design.height_cm)
    if layout.border_depth_px and not layout.texture_fill:
        border_cm = max(border_cm, required_border)
    if border_cm >= shape.half_height:
        raise ValueError('原素材边框过宽，无法用于当前尺寸')
    if design.inner_diameter_cm and design.inner_diameter_cm / 2 >= shape.half_height - border_cm:
        raise ValueError('内圆超出自动识别的外边框内侧')
    mapping = ContentMapping.create(layout, design.diameter_cm, design.height_cm, border_cm, shape=shape)
    px_cm = max(design.diameter_cm / width, design.height_cm / height)
    extra_cm = border_cm - native_border_cm
    plain_band = uniform_strip_band(layout.strip) if extra_cm > 1e-9 else None
    if extra_cm > 1e-9 and plain_band is None:
        raise ValueError('当前素材边框需要加宽，但没有足够的纯色留白；为避免装饰变形，请换用比例更接近或四边边框一致的素材')
    # Anchor tangential scale near the artwork, not in the expanded blank margin.
    ornament = np.max(np.ptp(layout.strip, axis=1), axis=1).astype(np.float64)
    ring_depth = native_border_cm / 2
    if ornament.sum():
        source_depth = float(np.average(np.arange(len(ornament)) + .5, weights=ornament))
        ring_depth = source_depth * scale
        if plain_band and source_depth >= plain_band[1]:
            ring_depth += extra_cm
    ring_depth = min(ring_depth, shape.half_height - 1e-6) if border_cm else 0.0
    ring = shape.inset(ring_depth) if border_cm else shape
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
        if layout.framed_artwork is not None:
            rgb = sample_framed_artwork(layout, mapping, scale, x, y, px_cm)
        elif layout.inset_panel is not None:
            rgb = adapt_panel(layout, mapping, shape, border_cm, x, y)
        else:
            rgb = mapping.sample(layout, x, y)
        if border_cm:
            # Interior pixels have zero frame coverage. Keep their original
            # artwork and avoid perimeter geometry/interpolation for them.
            border_pixels = depth < border_cm + px_cm / 2
            rows, columns = np.nonzero(border_pixels)
            border_depth = depth[rows, columns]
            # Continuous clockwise coordinates rotate the lower text by 180 degrees.
            # A reflected y coordinate would mirror every glyph on the lower half.
            s = inset_boundary_fraction(shape, x[0, columns], y[rows, 0],
                                        np.clip(border_depth, 0, border_cm), ring) * ring.perimeter
            source_depth_cm = border_depth
            if plain_band:
                band_start, band_end = (value * scale for value in plain_band)
                source_depth_cm = np.where(border_depth < band_start, border_depth,
                    np.where(border_depth < band_end + extra_cm,
                             band_start + (border_depth - band_start) * (band_end - band_start) / (band_end - band_start + extra_cm),
                             border_depth - extra_cm))
            sample_depth = np.maximum(0, source_depth_cm / scale - .5)
            if layout.strip_is_sentence:
                side_length = (ring.perimeter - 2 * ring.chord) / 2
                stripe = sample_sentence_strip(layout.strip, s, sample_depth,
                    (ring.chord, side_length, ring.chord, side_length), scale,
                    layout.sentence_layers)
            else:
                stripe = sample_perimeter_strip(layout.strip, s, sample_depth,
                                                 ring.perimeter, scale, origin)
            if layout.corner_gaps is not None:
                gap_start, gap_end, colours = layout.corner_gaps
                band = (sample_depth >= gap_start - .5) & (sample_depth < gap_end - .5)
                stripe[band] = _complete_corner_ticks(layout.strip, shape, ring, scale,
                    gap_end * scale + extra_cm, colours, x[0, columns[band]],
                    y[rows[band], 0], sample_depth[band], gap_start, gap_end)
            border_rgb = rgb[rows, columns]
            blend(border_rgb, stripe, cov(border_cm - border_depth))
            rgb[rows, columns] = border_rgb
        if design.inner_diameter_cm:
            radius = design.inner_diameter_cm / 2
            selected = inner_material or material
            inner_layout = selected.source_layout
            if inner_layout is None:
                raise ValueError('自动排版的内圆素材也需采用自动模式')
            inner_depth = radius - np.hypot(x, y)
            inner_scale = mapping.scale_cm if layout.texture_fill else scale
            if inner_layout.texture_fill:
                inner_scale = min(2 * radius / inner_layout.width_px,
                                  2 * radius / inner_layout.height_px)
                inner_band = min(inner_layout.border_depth_px * inner_scale, .20) or .05
                inner_mapping = ContentMapping.create(inner_layout, 2 * radius, 2 * radius, inner_band)
            else:
                inner_mapping = ContentMapping(inner_scale, (inner_layout.width_px - 1) / 2,
                                               (inner_layout.height_px - 1) / 2,
                                               inner_layout.content_box_px[0], inner_layout.content_box_px[1])
                inner_band = inner_layout.border_depth_px * inner_scale
            content = inner_mapping.sample(inner_layout, x, y)
            if inner_band >= radius:
                raise ValueError('内圆尺寸小于原素材边框宽度')
            if inner_band:
                arc = ((np.arctan2(y, x) + np.pi / 2) % (2 * np.pi)) * max(radius - inner_band / 2, .001)
                inner_perimeter = 2 * np.pi * max(radius - inner_band / 2, .001)
                stripe = sample_perimeter_strip(inner_layout.strip, arc,
                                                np.maximum(0, inner_depth / inner_scale - .5),
                                                inner_perimeter, inner_scale)
                blend(content, stripe, cov(inner_band - inner_depth))
            blend(rgb, content, cov(inner_depth))
        alpha = np.round(cov(depth) * 255).astype(np.uint8)
        output.paste(Image.fromarray(np.concatenate((rgb, alpha[..., None]), axis=2)), (0, start))
        if progress:
            progress(round(end / height * 100))
    return output


def _complete_corner_ticks(strip, shape, ring, scale, inner_depth, colours,
                           x, y, source_depth, start, end):
    """Fit whole ticks on each straight/arc segment without radial clipping."""
    inner_depth = min(inner_depth, shape.half_height - 1e-6)
    inner = shape.inset(inner_depth)
    period = strip.shape[1]
    # Begin/end the repeated cell in actual source background, never midway
    # through its white stroke. Keep all original colour/antialias pixels.
    background = np.asarray(colours[0])
    ink = np.mean(np.max(np.abs(strip[start:end].astype(np.float32) - background), axis=2), axis=0)
    shifted = np.roll(strip, -int(np.argmin(ink)), axis=1)
    centre = getattr(shape, 'center', 0.)
    theta = np.arctan2(y, np.abs(x) - centre)
    radial = shape.radius - np.hypot(np.abs(x) - centre, y)
    on_line = shape.half_height - np.abs(y) <= radial
    # The innermost band boundary limits every row. With one x transform on
    # straights and one angular transform on arcs, each tick has full length.
    straight_count = max(0, int(np.floor(inner.chord / (period * scale))))
    arc_count = max(0, int(np.floor(2 * ring.radius * inner.angle / (period * scale))))
    straight_u = x / scale + straight_count * period / 2
    arc_u = theta * ring.radius / scale + arc_count * period / 2
    u = np.where(on_line, straight_u, arc_u)
    limit = np.where(on_line, straight_count, arc_count) * period
    valid = (u >= 0) & (u < limit)
    ticks = sample(shifted, u, source_depth, wrap_x=True)
    corner = np.where(x >= 0, np.where(y >= 0, 2, 1), np.where(y >= 0, 3, 0))
    return np.where(valid[:, None], ticks, np.asarray(colours, dtype=np.uint8)[corner])
