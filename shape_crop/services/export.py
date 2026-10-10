"""Atomic image export; PNG retains transparency, JPEG composites onto white."""
import os
from pathlib import Path
import tempfile
from PIL import Image


def save_image(image, path, dpi):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in ('.png', '.jpg', '.jpeg'):
        raise ValueError('导出格式须为 PNG 或 JPG')
    handle, temporary = tempfile.mkstemp(prefix='.shape-', suffix=suffix, dir=path.parent)
    os.close(handle)
    try:
        if suffix == '.png':
            # PNG remains lossless; lower compression spends less time encoding.
            image.save(temporary, format='PNG', compress_level=1, dpi=(dpi, dpi))
        else:
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            flat = Image.new('RGB', image.size, 'white')
            flat.paste(image, mask=image.getchannel('A'))
            flat.save(temporary, format='JPEG', quality=95, subsampling=0, dpi=(dpi, dpi))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
