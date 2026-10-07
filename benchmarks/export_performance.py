"""Print-size source rendering and encoding timings, without external artwork."""
from pathlib import Path
import sys
import tempfile
from time import perf_counter
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.layout_analysis import SourceLayout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.core.source_renderer import render_source
from shape_crop.services.export import save_image


def main():
    pixels = np.full((880, 1490, 3), 240, dtype=np.uint8)
    pixels[70:-70, 116:-116] = np.random.default_rng(7).integers(
        40, 235, (740, 1258, 3), dtype=np.uint8)
    strip = np.full((70, 200, 3), 240, dtype=np.uint8)
    strip[10:13] = 0
    strip[60:63] = 0
    layout = SourceLayout(pixels, strip, 70, 1490, 880, '',
                          pixels[70:-70, 116:-116], (116, 70, 1374, 810), 200)
    material = PreparedMaterial(pixels, strip, MaterialSpec(), layout)
    design = DesignSpec(diameter_cm=151, height_cm=91, dpi=150,
                        shape_mode='arc', straight_cm=120.5, border=BorderSpec(0, 0, 0))
    started = perf_counter()
    image = render_source(design, material)
    timings = dict(pixels=image.width * image.height, render_s=perf_counter() - started)
    with tempfile.TemporaryDirectory() as folder:
        for suffix in ('jpg', 'png'):
            started = perf_counter()
            save_image(image, Path(folder) / ('output.' + suffix), design.dpi)
            timings[suffix + '_s'] = perf_counter() - started
    print(json.dumps(timings, indent=2))


if __name__ == '__main__':
    main()
