"""File I/O and source-region extraction; no UI dependencies."""
from dataclasses import dataclass, replace
from pathlib import Path
from collections import OrderedDict
from threading import RLock
import re
import numpy as np
from PIL import Image, ImageOps
from shape_crop.models.design import MaterialSpec
from shape_crop.services.layout_analysis import analyze_layout, _straight_outline_rows
from shape_crop.services.texture_period import extract_period
from shape_crop.services.inset_panel import _partial_fade_edges
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.contoured_frame import adapt_contoured_frame, adapt_texture_inset


@dataclass(frozen=True)
class PreparedMaterial:
    content: np.ndarray
    strip: np.ndarray
    spec: MaterialSpec
    source_layout: object = None


PREVIEW_SOURCE_SIDE = 2400


def load_image(path, max_side=None):
    try:
        source = Image.open(Path(path))
    except FileNotFoundError:
        raise ValueError(f'素材文件不存在：{path}')
    except PermissionError:
        raise ValueError(f'素材文件无读取权限：{path}')
    except Exception:
        raise ValueError(f'素材文件无法打开，可能已损坏：{path}')
    with source:
        if max_side:
            # JPEG draft reduces pixels in the decoder, before allocating a
            # full print-resolution image. Other formats use bounded resizing.
            scale = min(1, max_side / max(source.size))
            source.draft('RGB', tuple(max(1, round(value * scale)) for value in source.size))
        ImageOps.exif_transpose(source, in_place=True)
        if max_side:
            source.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        # The context closes the file, not the loaded pixel buffer. Avoid the
        # old EXIF copy + unconditional RGB copy for an already RGB image.
        return source if source.mode == 'RGB' else source.convert('RGB')


def extract(image, box):
    box.validate()
    w, h = image.size
    left, top = min(w - 1, round(box.left * w)), min(h - 1, round(box.top * h))
    right, bottom = max(left + 1, round(box.right * w)), max(top + 1, round(box.bottom * h))
    return image.crop((left, top, right, bottom))


_prepared = OrderedDict()
_cache_lock = RLock()
_cache_bytes = 0
_MAX_CACHE_BYTES = 256 * 1024 * 1024


def prepare(material, preview=False):
    """Share immutable source analysis between orders and preview/full-size render.

    File identity/timestamps invalidate edited or replaced images. The LRU is
    bounded by bytes as well as entries so large print sources cannot accumulate.
    """
    if not material.path:
        return None
    path = Path(material.path).resolve()
    info = path.stat()
    identity = (material, str(path), info.st_mtime_ns, info.st_ctime_ns, info.st_size, info.st_ino)
    # Reuse a full material for a small source. A large cached print source must
    # not force later previews back onto the expensive full-resolution analysis.
    with _cache_lock:
        full = _prepared.get(identity + (False,))
        if full and preview and material.layout == 'source' and max(
                full[0].source_layout.width_px, full[0].source_layout.height_px) <= PREVIEW_SOURCE_SIDE:
            return full[0]
    key = identity + (preview,)
    with _cache_lock:
        if key in _prepared:
            _prepared.move_to_end(key)
            return _prepared[key][0]
    result = _prepare(material, preview)
    arrays = [result.content, result.strip]
    if result.source_layout:
        arrays.extend((result.source_layout.image, result.source_layout.content))
        if result.source_layout.layered_strip is not None:
            arrays.append(result.source_layout.layered_strip[1])
        if result.source_layout.contoured_frame is not None:
            arrays.append(result.source_layout.contoured_frame.stroke)
        if result.source_layout.framed_artwork is not None:
            arrays.append(result.source_layout.framed_artwork.tile)
        if result.source_layout.corner_composition is not None:
            arrays.extend(group.alpha for group in result.source_layout.corner_composition.groups)
        arrays.extend(entry[0] for entry in result.source_layout.sentence_layers if entry is not None)
    arrays = {id(array): array for array in arrays}.values()
    size = 0
    owners = set()
    for array in arrays:
        array.setflags(write=False)
        root = array
        while isinstance(root.base, np.ndarray):
            root = root.base
        if id(root) not in owners:
            size += root.nbytes
            owners.add(id(root))
    global _cache_bytes
    if size <= _MAX_CACHE_BYTES:
        with _cache_lock:
            # Another worker may have prepared the same file concurrently.
            if key in _prepared:
                return _prepared[key][0]
            while _prepared and (_cache_bytes + size > _MAX_CACHE_BYTES or len(_prepared) >= 8):
                _, (_, removed) = _prepared.popitem(last=False)
                _cache_bytes -= removed
            _prepared[key] = result, size
            # Small automatic sources are identical in both paths.
            if preview and material.layout == 'source' and max(result.source_layout.width_px,
                    result.source_layout.height_px) < PREVIEW_SOURCE_SIDE:
                # Share the key instead of storing/accounting the entry twice.
                del _prepared[key]
                _prepared[identity + (False,)] = result, size
            _cache_bytes += size
    return result


def _prepare(material, preview):
    image = load_image(material.path, PREVIEW_SOURCE_SIDE if preview else None)
    if material.layout == 'source':
        try:
            pattern = parse_filename(Path(material.path).name).pattern
        except ValueError:
            pattern = ''
        # Plain colour marble has veins all the way to a single black outline.
        # Crowned/framed marble designs must keep normal structural analysis.
        texture_fill = bool(re.fullmatch(r'(?:浅|深)?(?:白|灰|黑|褐|棕|米|黄|绿|蓝|红|粉)(?:色)?大理石\d*(?:号)?(?:方形)?', pattern))
        hint = {'素缕花肆': 'patterned_inset', '花漾之约': 'corner_composition'}.get(pattern)
        if hint:
            layout = analyze_layout(image, composition_hint=hint)
        else:
            layout = analyze_layout(image, texture_fill=True) if texture_fill else analyze_layout(image)
        if (not preview and max(image.size) > PREVIEW_SOURCE_SIDE and
                layout.inset_panel is not None and layout.inset_panel.translucent is not None):
            reference = analyze_layout(load_image(material.path, PREVIEW_SOURCE_SIDE))
            layout = _align_translucent_layout(layout, reference)
        if pattern == '哥特玫瑰':
            layout = adapt_contoured_frame(layout)
        elif re.fullmatch(r'闲叙[·・.\s]*(?:青釉|邂逅)', pattern):
            layout = adapt_texture_inset(layout)
        return PreparedMaterial(layout.image, layout.strip, material, layout)
    content = extract(image, material.content_box)
    strip = extract(image, material.strip_box)
    if preview:
        content.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        strip.thumbnail((1800, 500), Image.Resampling.LANCZOS)
    return PreparedMaterial(np.asarray(content), np.asarray(strip), material)


def _align_translucent_layout(layout, reference):
    """Use preview structure for the same translucent source, retaining native ink."""
    panel = reference.inset_panel
    if panel is None or panel.translucent is None:
        return layout
    # Sentence ink and split/gapped strips have associated anchors and masks.
    # Keep their established preparation rather than reread ink into the base.
    if any(item.strip_is_sentence or item.corner_gaps is not None or item.layered_strip is not None
           for item in (layout, reference)):
        return layout
    sx, sy = layout.width_px/reference.width_px, layout.height_px/reference.height_px
    def box(values):
        return tuple(v*r for v, r in zip(values, (sx, sy, sx, sy)))
    bounds = tuple(round(v) for v in box(reference.content_box_px))
    left, top, right, bottom = bounds
    depth = round(reference.border_depth_px*sy)
    region = _straight_outline_rows(layout.image[:max(1, depth), left+1:right-1])
    strip, period = extract_period(region)
    if not period and reference.strip_period_px:
        period = max(1, round(reference.strip_period_px*sx))
        start = max(0, (region.shape[1]-period)//2)
        strip = region[:, start:start+period].copy()
    fade, opacity, background, thickness, colour = panel.translucent
    native_panel = layout.inset_panel
    native_fade = (native_panel.translucent[0] if native_panel is not None and
                   native_panel.translucent is not None else box(fade))
    native_thickness = thickness*max(sx,sy)
    panel_bounds = box(panel.box)
    # JPEG preview filtering can underestimate a solid native outline by a
    # few pixels. Measure its horizontal runs before interpolating over it,
    # so the interpolation endpoints cannot sample the old black stroke.
    centre_left, centre_right = round(layout.width_px*.35), round(layout.width_px*.65)
    for edge in (panel_bounds[1], panel_bounds[3]):
        lo = max(0, round(edge-4*native_thickness))
        hi = min(layout.height_px, round(edge+4*native_thickness)+1)
        dark_rows = np.mean(np.max(layout.image[lo:hi,centre_left:centre_right], axis=2) < 90, axis=1) > .95
        native_thickness = max(native_thickness, float(np.count_nonzero(dark_rows)+2))
    panel = replace(panel, box=box(panel.box),
        translucent=(native_fade, opacity, background, native_thickness, colour),
        stroke_repeat_px=panel.stroke_repeat_px*sx,
        partial_fade_edges=_partial_fade_edges(layout.image,native_fade,panel_bounds,
                                             background,panel.translucent_levels[0]))
    return replace(layout, content_box_px=bounds, border_depth_px=depth, strip=strip,
        strip_period_px=period, content=layout.image[top:bottom,left:right], inset_panel=panel)
