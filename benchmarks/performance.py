"""Reproducible local timings: python benchmarks/performance.py."""
import json
from pathlib import Path
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from shape_crop.services.catalog import match_material
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.materials import prepare
from shape_crop.models.design import MaterialSpec, DesignSpec, BorderSpec
from shape_crop.services.design_service import generate
from shape_crop.services.export import save_image


def timed(callback, count=1):
    start = perf_counter()
    for _ in range(count):
        callback()
    return round((perf_counter() - start) / count, 4)


def main():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for i in range(6000):
            (root / f'花型{i % 30};{40 + i // 30}x500cm.jpg').touch()
        target = parse_filename('花型7;80x140cm')
        cold = timed(lambda: match_material(target, root))
        warm = timed(lambda: match_material(target, root), 12)
        source = root / 'source.png'
        pixels = np.random.default_rng(7).integers(0, 256, (900, 1600, 3), dtype=np.uint8)
        Image.fromarray(pixels).save(source)
        material = MaterialSpec(path=str(source))
        prep_cold = timed(lambda: prepare(material))
        prep_warm = timed(lambda: prepare(material), 3)
        design = DesignSpec(diameter_cm=140, height_cm=78, dpi=40,
                            border=BorderSpec(0, 0, 0), material=material)
        render = timed(lambda: generate(design))
        image = generate(design)
        png = timed(lambda: save_image(image, root / 'output.png', 40), 3)
        jpg = timed(lambda: save_image(image, root / 'output.jpg', 40), 3)
        print(json.dumps(dict(match_cold_s=cold, match_repeat_s=warm,
                              prepare_cold_s=prep_cold, prepare_repeat_s=prep_warm,
                              render_s=render, png_s=png, jpg_s=jpg), indent=2))


if __name__ == '__main__':
    main()
