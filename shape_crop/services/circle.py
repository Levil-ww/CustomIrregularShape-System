"""Find and render circular artwork."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import unicodedata
from shape_crop.core.circle_composition import compose_circle
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.materials import load_image
from shape_crop.services.export import save_image


@dataclass(frozen=True)
class CircleName:
    stem: str
    material: str
    pattern: str
    diameter_cm: float


@dataclass(frozen=True)
class CircleMatch:
    path: str
    diameter_cm: float
    round_source: bool


def parse_circle_name(value, require_diameter=True):
    value = value.strip()
    if not value or any(c in value for c in '<>:"/\\|?*'):
        raise ValueError('请输入合法的目标文件名')
    stem = re.sub(r'\.(jpg|jpeg|png)$', '', value, flags=re.I)
    normalized = unicodedata.normalize('NFKC', stem)
    dimension = re.compile(r'(?:直径\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)?|(\d+(?:\.\d+)?)\s*(?:cm|厘米)\s*圆形)', re.I)
    separator = normalized.rfind(';')
    match = (dimension.search(normalized, separator + 1) if separator >= 0 else None) or dimension.search(normalized)
    if not match and require_diameter:
        raise ValueError('文件名中未找到圆形直径，例如：花型;140CM圆形')
    if match and float(match.group(1) or match.group(2)) <= 0:
        raise ValueError('圆形直径必须大于零')
    prefix = normalized[:separator] if separator >= 0 else normalized
    parts = []
    for part in prefix.rstrip(' ;-_').split('-'):
        part = part.strip()
        size = dimension.search(part)
        if size:
            part = part[:size.start()].strip()
        if part:
            parts.append(part)
    if not parts:
        raise ValueError('文件名中缺少花型名称')
    pattern = re.sub(r'[·・\s]+', '', parts[-1])
    if len(parts) > 1 and pattern in ('标准', '定制', '裁剪有图', '剪裁有图'):
        raise ValueError('文件名中缺少花型名称')
    return CircleName(stem, parts[0] if len(parts) > 1 else '', pattern, float(match.group(1) or match.group(2)) if match else 0)


def match_circle_material(target, directory, diameter, cancelled=None):
    if not os.path.isdir(directory):
        raise ValueError('图库目录不存在或不可访问')
    candidates = []
    for root, dirs, files in os.walk(directory, followlinks=False):
        for name in files:
            if cancelled and cancelled():
                from shape_crop.core.renderer import RenderCancelled
                raise RenderCancelled('任务已取消')
            if Path(name).suffix.lower() not in ('.jpg', '.jpeg', '.png'):
                continue
            try:
                parsed = parse_circle_name(name)
                size, is_round = parsed.diameter_cm, True
            except ValueError:
                try:
                    parsed = parse_filename(name)
                    size, is_round = min(parsed.width_cm, parsed.height_cm), False
                except ValueError:
                    continue
            if parsed.pattern.casefold() != target.pattern.casefold() or (target.material and parsed.material != target.material):
                continue
            path = str(Path(root) / name)
            candidates.append(((not is_round, size < diameter * .8, abs(math.log(size / diameter)), path.casefold()), CircleMatch(path, size, is_round)))
    if not candidates:
        raise ValueError(f'图库中未找到同材质、同花型“{target.pattern}”的素材')
    return min(candidates, key=lambda item: item[0])[1]


def generate_circle(target_name, library, diameter, allowance, inner_diameter, gap, line_px, dpi, outer_override='', inner_override='', preview=True, output=None, cancelled=None):
    target = parse_circle_name(target_name, require_diameter=False)
    actual = diameter + allowance
    if not all(math.isfinite(v) for v in (diameter, allowance, dpi)) or diameter <= 0 or allowance < 0 or dpi <= 0:
        raise ValueError('外径、补偿和 DPI 须为有效的正数')
    if not all(math.isfinite(v) for v in (inner_diameter, gap, line_px)) or inner_diameter < 0 or gap < 0 or line_px < 0:
        raise ValueError('内圆直径、间隙和线宽不能为负数')
    if inner_diameter and inner_diameter + 2 * gap >= actual:
        raise ValueError('内圆直径与两侧间隙之和必须小于外圆直径')
    def select(override, size):
        return CircleMatch(override, size, True) if override else match_circle_material(target, library, size, cancelled)
    outer_match = select(outer_override, actual)
    inner_match = select(inner_override, inner_diameter) if inner_diameter else None
    pixels = round(actual / 2.54 * dpi)
    render_pixels = min(pixels, 1200) if preview else pixels
    if render_pixels * render_pixels > 180_000_000:
        raise ValueError('当前导出超过 1.8 亿像素，请降低 DPI 或尺寸')
    outer = load_image(outer_match.path, max_side=render_pixels if preview else None)
    inner = load_image(inner_match.path, max_side=render_pixels if preview else None) if inner_match else None
    width = max(1, round(line_px * render_pixels / pixels)) if line_px else 0
    image = compose_circle(outer, inner, actual, inner_diameter, gap, width, render_pixels)
    if output:
        save_image(image, output, dpi)
    def description(label, match, requested_size):
        warning = '（矩形备选，边框效果请核对）' if not match.round_source else ''
        if match.diameter_cm < requested_size * .8:
            warning += '（素材尺寸偏小）'
        return f'{label}素材：{match.path}{warning}'
    return image, '\n'.join([description('外圆', outer_match, actual)] + ([description('内圆', inner_match, inner_diameter)] if inner_match else []))
