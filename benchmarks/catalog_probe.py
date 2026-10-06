"""Read-only profiling of a real library and two different source previews."""
import argparse
import cProfile
import pstats
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shape_crop.services.catalog import match_material
from shape_crop.services.catalog_session import CatalogSession
from shape_crop.services.filename_parser import parse_filename
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.design_service import generate
import os
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('library')
parser.add_argument('--session', action='store_true', help='Desktop recursive-watch fast lookup')
args = parser.parse_args()
session = CatalogSession(args.library) if args.session else None
if session:
    session.start()
    print(f'watch_active={session.active} error={session.watch_error}', flush=True)
start = perf_counter()
sources = []
for root, _, files in os.walk(args.library):
    for name in files:
        if Path(name).suffix.lower() not in ('.jpg', '.jpeg') or any(
                word in name for word in ('裁剪有图', '圆形', '直径', '水池', '挖角')):
            continue
        try:
            parsed = parse_filename(name)
        except ValueError:
            continue
        if any(parsed.pattern == old[1].pattern for old in sources):
            continue
        sources.append((str(Path(root) / name), parsed))
        if len(sources) == 2:
            break
    if len(sources) == 2:
        break
print(f'sample_selection_s={perf_counter()-start:.3f}', flush=True)
for i, (path, parsed) in enumerate(sources, 1):
    start = perf_counter()
    match = (session.match(parsed) if session else match_material(parsed, args.library))
    print(f'order={i} match_s={perf_counter()-start:.3f}', flush=True)
    with Image.open(match.path) as source:
        print(f'source_pixels={source.size} file_mb={Path(match.path).stat().st_size/1e6:.1f}', flush=True)
    design = DesignSpec(diameter_cm=parsed.width_cm, height_cm=parsed.height_cm,
                        border=BorderSpec(0, 0, 0), material=MaterialSpec(match.path))
    profiler = cProfile.Profile()
    start = perf_counter()
    profiler.enable()
    try:
        image = generate(design, preview=True, status=lambda message: print(message, flush=True))
        image.close()
    except Exception as error:
        print(f'preview_error={type(error).__name__}: {error}', flush=True)
    profiler.disable()
    print(f'preview_s={perf_counter()-start:.3f}', flush=True)
    pstats.Stats(profiler).sort_stats('cumulative').print_stats(7)
if session:
    session.close()
