"""Filename → catalog match → design. Shared by GUI and CLI."""
from dataclasses import replace
from pathlib import Path
import math
from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
from shape_crop.services.catalog import match_material
from shape_crop.services.filename_parser import parse_filename


def resolve_request(request, cancelled=None, status=None):
    target = parse_filename(request.target_name)
    if not math.isfinite(request.allowance_cm) or request.allowance_cm < 0:
        raise ValueError('尺寸补偿不能为负数')
    if request.material_override:
        path = request.material_override
        detail = '使用指定素材'
    else:
        match = match_material(target, request.library_dir, cancelled, status)
        path = match.path
        detail = f'匹配 {match.source.width_cm:g} × {match.source.height_cm:g}cm；比例差 {math.expm1(match.ratio_error) * 100:.2f}%'
    design = DesignSpec(diameter_cm=target.width_cm + request.allowance_cm,
                        height_cm=target.height_cm + request.allowance_cm, dpi=request.dpi,
                        border=BorderSpec(0, 0, 0), inner_border_cm=0,
                        material=MaterialSpec(path=path), inner_diameter_cm=request.inner_diameter_cm)
    design.validate()
    return design, f'{detail}\n素材：{path}'


def output_path(request, directory, extension='.jpg'):
    target = parse_filename(request.target_name)
    return str(Path(directory) / (target.stem + extension))
