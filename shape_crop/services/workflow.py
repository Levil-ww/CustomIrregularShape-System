"""Filename → catalog match → design. Shared by GUI and CLI."""
from dataclasses import replace
from pathlib import Path
import math
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.catalog import match_material
from shape_crop.services.filename_parser import parse_filename


def resolve_request(request, cancelled=None, status=None, catalog_session=None):
    target = parse_filename(request.target_name)
    if not math.isfinite(request.allowance_cm) or request.allowance_cm < 0:
        raise ValueError('尺寸补偿不能为负数')
    width = target.width_cm if request.width_cm is None else request.width_cm
    height = target.height_cm if request.height_cm is None else request.height_cm
    if not all(math.isfinite(v) for v in (width, height)) or not 0 < height <= width:
        raise ValueError('原始尺寸须满足 0 < 总高 ≤ 最大宽度')
    if request.shape_mode == 'arc':
        from shape_crop.core.geometry import ArcBand
        ArcBand(width, height, request.straight_cm)
    target = replace(target, width_cm=width, height_cm=height)
    design = DesignSpec(diameter_cm=width + request.allowance_cm,
                        height_cm=height + request.allowance_cm, dpi=request.dpi,
                        border=BorderSpec(0, 0, 0), inner_border_cm=0,
                        inner_diameter_cm=request.inner_diameter_cm,
                        shape_mode=request.shape_mode, straight_cm=request.straight_cm)
    design.validate()
    if request.material_override:
        path = request.material_override
        detail = '使用指定素材'
    else:
        match = (catalog_session.match(target, cancelled, status) if catalog_session else
                 match_material(target, request.library_dir, cancelled, status))
        path = match.path
        detail = f'匹配 {match.source.width_cm:g} × {match.source.height_cm:g}cm；比例差 {math.expm1(match.ratio_error) * 100:.2f}%'
    design = replace(design, material=MaterialSpec(path=path))
    design.validate()
    return design, f'{detail}\n素材：{path}'


def output_path(request, directory, extension='.jpg'):
    target = parse_filename(request.target_name)
    return str(Path(directory) / (target.stem + extension))
