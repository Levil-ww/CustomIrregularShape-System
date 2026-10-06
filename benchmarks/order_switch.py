"""Profile two DIFFERENT large-source orders, rather than a same-source cache hit."""
import argparse
import cProfile
from pathlib import Path
import pstats
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from shape_crop.models.request import ProductRequest
from shape_crop.services.workflow import resolve_request
from shape_crop.services.design_service import generate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', help='Read-only existing library (optional)')
    parser.add_argument('--names', nargs=2, help='Two actual order names')
    parser.add_argument('--width', type=int, default=4000)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(args.library or folder)
        names = args.names or ['花型甲;80x140cm', '花型乙;80x140cm']
        if not args.library:
            for name in names:
                w, h = args.width, round(args.width * .6)
                image = Image.new('RGB', (w, h), '#e8d4b0')
                draw = ImageDraw.Draw(image)
                draw.rectangle((0, 0, w - 1, h - 1), outline='black', width=max(5, w // 200))
                for x in range(120, w - 120, 140):
                    for y in range(120, h - 120, 140):
                        draw.ellipse((x, y, x + 75, y + 75), fill='#897255')
                image.save(root / (name + '.jpg'), quality=95)
                image.close()
        for i, name in enumerate(names, 1):
            profiler = cProfile.Profile()
            start = perf_counter()
            profiler.enable()
            design, _ = resolve_request(ProductRequest(name, str(root)))
            matched = perf_counter()
            image = generate(design, preview=True)
            profiler.disable()
            elapsed = perf_counter() - start
            print(f'order={i} match={matched-start:.3f}s preview={elapsed-(matched-start):.3f}s total={elapsed:.3f}s size={image.size}')
            pstats.Stats(profiler).sort_stats('cumulative').print_stats(8)
            image.close()


if __name__ == '__main__':
    main()
