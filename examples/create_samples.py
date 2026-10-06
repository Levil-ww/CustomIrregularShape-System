"""Create reproducible customer-size demos from a user-selected library material.

python examples/create_samples.py --material <image> --output-dir outputs
"""
import argparse
from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shape_crop.models.design import DesignSpec, MaterialSpec
from shape_crop.services.design_service import generate
from shape_crop.services.project_io import save_project


def main():
    parser = argparse.ArgumentParser(description='生成截圆及同心圆示例')
    parser.add_argument('--material', required=True)
    parser.add_argument('--output-dir', default='outputs')
    parser.add_argument('--full-export', action='store_true', help='额外导出 150 DPI 截圆成品')
    parser.add_argument('--target', help='验证目标文件名匹配、+1cm 尺寸补偿和同名输出')
    parser.add_argument('--use-exact-material', action='store_true', help='验证指定参考素材，跳过自动匹配')
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.target:
        from shape_crop.models.request import ProductRequest
        from shape_crop.services.workflow import resolve_request, output_path
        request = ProductRequest(args.target, str(Path(args.material).parent),
                                 args.material if args.use_exact_material else '')
        design, detail = resolve_request(request)
        print(detail)
        path = output_path(request, output, '.png')
        generate(design, preview=not args.full_export, output=path, diagnostics=print)
        save_project(Path(path).with_suffix('.json'), design)
        print(path)
        return
    design = DesignSpec(material=MaterialSpec(str(Path(args.material).resolve())))
    for name, spec in [('截圆-200x83.76', design),
                       ('同心圆-外200-内110', replace(design, height_cm=200, inner_diameter_cm=110))]:
        save_project(output / (name + '.json'), spec)
        generate(spec, preview=True, output=output / (name + '.png'))
        print(output / (name + '.png'))
    if args.full_export:
        generate(design, output=output / '截圆-200x83.76-150DPI.png')
        print(output / '截圆-200x83.76-150DPI.png')


if __name__ == '__main__':
    main()
