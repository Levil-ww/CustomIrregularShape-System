"""Cancellable JPG catalog scan and deterministic same-pattern size ranking."""
from dataclasses import dataclass
import math
import os
import unicodedata
from pathlib import Path
from shape_crop.services.filename_parser import parse_filename
from shape_crop.core.renderer import RenderCancelled


@dataclass(frozen=True)
class Match:
    path: str
    source: object
    ratio_error: float


def match_material(target, directory, cancelled=None, progress=None):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError('图库目录不存在或不可访问')
    candidates, scanned = [], 0
    def onerror(error):
        raise OSError(f'图库扫描失败：{error.filename}：{error.strerror}') from error
    for root, _, files in os.walk(directory, onerror=onerror, followlinks=False):
        for name in files:
            if cancelled and cancelled():
                raise RenderCancelled('图库扫描已取消')
            if Path(name).suffix.lower() not in ('.jpg', '.jpeg'):
                continue
            scanned += 1
            if progress and scanned % 1000 == 0:
                progress(f'已扫描 {scanned} 张 JPG…')
            if target.pattern.casefold() not in unicodedata.normalize('NFKC', name).casefold():
                continue
            try:
                parsed = parse_filename(name)
            except ValueError:
                continue
            # Rectangular products only; do not silently substitute another pattern/material.
            if any(word in name for word in ('裁剪有图', '圆形', '直径', '水池', '挖角')):
                continue
            if parsed.pattern.casefold() != target.pattern.casefold():
                continue
            if target.material and parsed.material != target.material:
                continue
            ratio_error = abs(math.log(parsed.ratio / target.ratio))
            size_error = abs(math.log(parsed.width_cm / target.width_cm)) + abs(math.log(parsed.height_cm / target.height_cm))
            candidates.append((ratio_error, size_error, str(Path(root) / name), parsed))
    if not candidates:
        raise ValueError(f'图库中未找到同材质、同花型“{target.pattern}”的矩形 JPG；可在高级选项指定素材')
    ratio, _, path, parsed = min(candidates, key=lambda item: (item[0], item[1], item[2].casefold()))
    return Match(path, parsed, ratio)
