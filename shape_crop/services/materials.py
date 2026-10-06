"""File I/O and source-region extraction; no UI dependencies."""
from dataclasses import dataclass
from pathlib import Path
from collections import OrderedDict
from threading import RLock
import numpy as np
from PIL import Image, ImageOps
from shape_crop.models.design import MaterialSpec
from shape_crop.services.layout_analysis import analyze_layout


@dataclass(frozen=True)
class PreparedMaterial:
    content: np.ndarray
    strip: np.ndarray
    spec: MaterialSpec
    source_layout: object = None


def load_image(path):
    with Image.open(Path(path)) as source:
        return ImageOps.exif_transpose(source).convert('RGB')


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
    key = (material, str(path), info.st_mtime_ns, info.st_ctime_ns, info.st_size,
           info.st_ino, preview if material.layout == 'manual' else False)
    with _cache_lock:
        if key in _prepared:
            _prepared.move_to_end(key)
            return _prepared[key][0]
    result = _prepare(material, preview)
    arrays = [result.content, result.strip]
    if result.source_layout:
        arrays.extend((result.source_layout.image, result.source_layout.content))
    arrays = {id(array): array for array in arrays}.values()
    size = 0
    for array in arrays:
        array.setflags(write=False)
        size += array.nbytes
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
            _cache_bytes += size
    return result


def _prepare(material, preview):
    image = load_image(material.path)
    if material.layout == 'source':
        layout = analyze_layout(image)
        return PreparedMaterial(layout.image, layout.strip, material, layout)
    content = extract(image, material.content_box)
    strip = extract(image, material.strip_box)
    if preview:
        content.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        strip.thumbnail((1800, 500), Image.Resampling.LANCZOS)
    return PreparedMaterial(np.asarray(content), np.asarray(strip), material)
