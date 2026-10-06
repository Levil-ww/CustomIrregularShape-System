"""Headless entry: python -m shape_crop.cli --config design.json --output result.png"""
import argparse
from shape_crop.services.project_io import load_project
from shape_crop.services.design_service import generate
from shape_crop.models.design import DesignSpec


def main():
    parser = argparse.ArgumentParser(description='圆桌 / 弧形台素材生成器')
    parser.add_argument('--config', help='界面保存的 JSON 项目文件')
    parser.add_argument('--target', help='目标文件名，长边/短边各加 1cm')
    parser.add_argument('--library', help='递归匹配矩形 JPG 的素材图库')
    parser.add_argument('--material', help='可选：指定素材，跳过图库匹配')
    parser.add_argument('--shape', choices=['circular', 'arc'], default='circular', help='目标轮廓模块')
    parser.add_argument('--straight', type=float, default=0, help='弧形台直边厘米数，不参与补偿')
    parser.add_argument('--allowance', type=float, default=1, help='宽、高各增加的总尺寸，默认 1cm')
    parser.add_argument('--output', help='输出 PNG / JPG 路径（JSON 模式）')
    parser.add_argument('--output-dir', help='目标名称模式：输出目录，自动使用同名 JPG')
    parser.add_argument('--preview', action='store_true', help='输出最长边 1200px 的预览图')
    args = parser.parse_args()
    if args.target:
        from shape_crop.models.request import ProductRequest
        from shape_crop.services.workflow import resolve_request
        design, detail = resolve_request(ProductRequest(args.target, args.library or '', args.material or '',
                                                       allowance_cm=args.allowance, shape_mode=args.shape,
                                                       straight_cm=args.straight))
        print(detail)
        if not args.output_dir:
            parser.error('--target 模式需提供 --output-dir，输出自动命名')
        from shape_crop.services.workflow import output_path
        args.output = output_path(ProductRequest(args.target), args.output_dir)
    else:
        if not args.output:
            parser.error('JSON 模式需提供 --output')
        design = load_project(args.config) if args.config else DesignSpec()
    generate(design, preview=args.preview, output=args.output)


if __name__ == '__main__':
    main()
