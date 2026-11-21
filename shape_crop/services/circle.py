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
from shape_crop.services.catalog import _catalog
from shape_crop.services.catalog_session import CatalogSession


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


@dataclass(frozen=True)
class CircleSource:
    pattern: str
    material: str
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


def _circle_entry(name):
    if Path(name).suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        return None
    try:
        parsed = parse_circle_name(name)
        return CircleSource(parsed.pattern, parsed.material, parsed.diameter_cm, True)
    except ValueError:
        try:
            parsed = parse_filename(name)
            return CircleSource(parsed.pattern, parsed.material, min(parsed.width_cm, parsed.height_cm), False)
        except ValueError:
            return None


def match_circle_materials(target, directory, diameters, cancelled=None, progress=None, *, verify=True, events=()):
    if not os.path.isdir(directory):
        raise ValueError('图库目录不存在或不可访问')
    groups = _catalog(Path(directory), cancelled, progress, verify=verify, events=events,
                      parse_entry=_circle_entry, namespace='circle')
    candidates = [(path, parsed) for path, parsed in groups.get(target.pattern.casefold(), ())
                  if not target.material or parsed.material == target.material]
    if not candidates:
        raise ValueError(f'图库中未找到同材质、同花型“{target.pattern}”的素材')
    results = []
    for diameter in diameters:
        path, parsed = min(candidates, key=lambda item: (not item[1].round_source,
            item[1].diameter_cm < diameter * .8, abs(math.log(item[1].diameter_cm / diameter)), item[0].casefold()))
        results.append(CircleMatch(path, parsed.diameter_cm, parsed.round_source))
    return results


def match_circle_material(target, directory, diameter, cancelled=None):
    return match_circle_materials(target, directory, [diameter], cancelled)[0]


class CircleCatalogSession(CatalogSession):
    """Maintain a circular catalog using the existing directory watcher."""

    def match_many(self, target, diameters, cancelled=None, progress=None):
        self.start()
        with self._lock:
            events, self._events = self._events, []
            verify = self._verify or self._overflow or not self._active
            self._verify = self._overflow = False
        try:
            matches = match_circle_materials(target, self.directory, diameters, cancelled, progress,
                                             verify=verify, events=events)
            if any(not os.path.isfile(match.path) for match in matches):
                matches = match_circle_materials(target, self.directory, diameters, cancelled, progress, verify=True)
            return matches
        except Exception:
            with self._lock:
                self._events = events + self._events
                self._verify = self._verify or verify
            raise


def generate_circle(target_name, library, diameter, allowance, inner_diameter, gap, line_px, dpi, outer_override='', inner_override='', preview=True, output=None, cancelled=None, catalog_session=None, status=None):
    target = parse_circle_name(target_name, require_diameter=False)
    actual = diameter + allowance
    if not all(math.isfinite(v) for v in (diameter, allowance, dpi)) or diameter <= 0 or allowance < 0 or dpi <= 0:
        raise ValueError('外径、补偿和 DPI 须为有效的正数')
    if not all(math.isfinite(v) for v in (inner_diameter, gap, line_px)) or inner_diameter < 0 or gap < 0 or line_px < 0:
        raise ValueError('内圆直径、间隙和线宽不能为负数')
    if inner_diameter and inner_diameter + 2 * gap >= actual:
        raise ValueError('内圆直径与两侧间隙之和必须小于外圆直径')
    needed = ([actual] if not outer_override else []) + ([inner_diameter] if inner_diameter and not inner_override else [])
    matches = iter((catalog_session.match_many(target, needed, cancelled, status) if catalog_session else
                    match_circle_materials(target, library, needed, cancelled, status)) if needed else [])
    def manual_match(path, size):
        parsed = _circle_entry(Path(path).name)
        if parsed is not None:
            return CircleMatch(path, size, parsed.round_source)
        from PIL import Image
        try:
            with Image.open(path) as source:
                is_round = source.width == source.height
        except OSError:
            raise ValueError(f'素材文件无法打开：{path}')
        return CircleMatch(path, size, is_round)
    outer_match = manual_match(outer_override, actual) if outer_override else next(matches)
    inner_match = (manual_match(inner_override, inner_diameter) if inner_override else next(matches)) if inner_diameter else None
    pixels = round(actual / 2.54 * dpi)
    render_pixels = min(pixels, 1200) if preview else pixels
    if render_pixels * render_pixels > 180_000_000:
        raise ValueError('当前导出超过 1.8 亿像素，请降低 DPI 或尺寸')
    if status:
        status('正在读取素材…')
    def artwork(match, size):
        if match.round_source:
            return load_image(match.path, max_side=render_pixels if preview else None)
        from shape_crop.models.design import DesignSpec, MaterialSpec, BorderSpec
        from shape_crop.services.design_service import generate
        design = DesignSpec(diameter_cm=size, height_cm=size, dpi=dpi,
                            border=BorderSpec(0, 0, 0), inner_border_cm=0,
                            material=MaterialSpec(path=match.path))
        return generate(design, preview=preview, cancelled=cancelled, status=status)
    outer = artwork(outer_match, actual)
    inner = (outer if inner_match and inner_match.path == outer_match.path and outer_match.round_source and inner_match.round_source else
             artwork(inner_match, inner_diameter)) if inner_match else None
    width = max(1, round(line_px * render_pixels / pixels)) if line_px else 0
    if status:
        status('正在生成圆形图案…')
    image = compose_circle(outer, inner, actual, inner_diameter, gap, width, render_pixels)
    if output:
        if status:
            status('正在保存成品…')
        save_image(image, output, dpi)
    def description(label, match, requested_size):
        warning = '（矩形素材，已按圆形重建边框，请核对预览）' if not match.round_source else ''
        if match.diameter_cm < requested_size * .8:
            warning += '（素材尺寸偏小）'
        return f'{label}素材：{match.path}{warning}'
    return image, '\n'.join([description('外圆', outer_match, actual)] + ([description('内圆', inner_match, inner_diameter)] if inner_match else []))
