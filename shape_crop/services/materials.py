"""File I/O and source-region extraction; no UI dependencies."""
from dataclasses import dataclass
from pathlib import Path
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


def prepare(material, preview=False):
    if not material.path:
        return None
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
