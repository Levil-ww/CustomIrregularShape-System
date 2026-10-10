"""Local OCR adapter and conservative dimension association; no Qt dependency."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class SketchDimensions:
    width_cm: float | None
    height_cm: float | None
    straight_cm: float | None
    report: str


def associate_dimensions(words, width, height):
    # OCR may split "138" into "1" and "38" around a dimension marker.
    numeric = []
    for word in words:
        normalized = word['text'].strip().replace('，', '.').replace(',', '.')
        if re.fullmatch(r'\d+(?:\.\d+)?\s*(?:cm|厘米)?', normalized, re.I):
            numeric.append(dict(word, text=normalized))
    merged = []
    for word in sorted(numeric, key=lambda item: item['x']):
        neighbor = next((item for item in merged
                         if abs((item['y'] + item['height'] / 2) - (word['y'] + word['height'] / 2))
                         < .45 * max(item['height'], word['height'])
                         and 0 <= word['x'] - item['x'] - item['width'] < .65 * max(item['height'], word['height'])
                         and not re.search(r'cm|厘米', item['text'], re.I)), None)
        if neighbor is None:
            merged.append(word.copy())
        else:
            text_height = max(neighbor['height'], word['height'])
            decimal = any(
                neighbor['x'] + neighbor['width'] <= mark['x'] < word['x']
                and mark['width'] < .4 * text_height and mark['height'] < .4 * text_height
                and mark['y'] > min(neighbor['y'], word['y']) + .5 * text_height
                for mark in words)
            neighbor['text'] += ('.' if decimal else '') + word['text']
            neighbor['width'] = word['x'] + word['width'] - neighbor['x']
    candidates = []
    for word in merged:
        text = word['text'].strip().replace('，', '.').replace(',', '.')
        match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:cm|厘米)?', text, re.I)
        if match:
            value = float(match[1])
            if value > 0:
                candidates.append((value, (word['x'] + word['width'] / 2) / width,
                                   (word['y'] + word['height'] / 2) / height))
    # Titles such as "1. 弧形台" are outside the dimension region.
    candidates = [item for item in candidates if .12 < item[2] < .90]
    if len(candidates) == 3:
        left = min(candidates, key=lambda item: item[1])
        others = sorted([item for item in candidates if item is not left], key=lambda item: item[2])
        if left[1] < .25 and others[0][2] < left[2] < others[1][2]:
            w, h, straight = others[0][0], left[0], others[1][0]
            if 0 < h <= w and 0 < straight < w:
                return SketchDimensions(w, h, straight, '识别到三处尺寸：最大宽度、总高、直边。请核对位置及小数。')
    if len(candidates) == 2:
        h, w = sorted(item[0] for item in candidates)
        widest = max(candidates, key=lambda item: item[0])
        if widest[2] < .70:
            return SketchDimensions(w, h, None, '识别到两处尺寸，按长边/总高给出候选。弧形台仍需填写直边；请核对。')
    readable = '、'.join(f'{item[0]:g}' for item in candidates) or '无'
    return SketchDimensions(None, None, None, f'无法可靠关联尺寸（候选：{readable}）。请参照草图手工填写。')


def recognize_sketch(path, cancelled=None):
    if os.name != 'nt':
        raise ValueError('自动识别使用 Windows 系统 OCR；当前平台请手工输入草图尺寸。')
    try:
        image = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    except FileNotFoundError:
        raise ValueError(f'草图文件不存在：{path}')
    except PermissionError:
        raise ValueError(f'草图文件无权限：{path}')
    except Exception:
        raise ValueError('草图文件无法识别为图片，请检查格式')
    image.thumbnail((2400, 2400))
    pixels = np.asarray(image).astype(np.int16)
    red = ((pixels[..., 0] > 170) & (pixels[..., 1] < 150) &
           (pixels[..., 0] - pixels[..., 1] > 65) & (pixels[..., 0] - pixels[..., 2] > 65))
    variants = []
    if np.count_nonzero(red) > 25:
        variants.append(Image.fromarray(np.where(red, 0, 255).astype(np.uint8)).convert('RGB'))
    variants.append(image)
    script = str(Path(__file__).with_name('windows_ocr.ps1'))
    fallback = None
    with tempfile.TemporaryDirectory(prefix='shape-sketch-') as directory:
        for index, variant in enumerate(variants):
            if cancelled and cancelled():
                from shape_crop.core.renderer import RenderCancelled
                raise RenderCancelled('识别已取消')
            # Upscale small annotations for the system OCR without changing positions.
            if max(variant.size) < 1200:
                ratio = min(3, 1600 / max(variant.size))
                variant = variant.resize(tuple(round(n * ratio) for n in variant.size), Image.Resampling.LANCZOS)
            prepared = str(Path(directory) / f'ocr-{index}.png')
            variant.save(prepared)
            try:
                result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy',
                                         'Bypass', '-File', script, '-ImagePath', prepared],
                                        capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
            except subprocess.TimeoutExpired:
                raise ValueError('Windows OCR 超时（45 秒），请手工填写尺寸')
            if result.returncode:
                raise ValueError('Windows OCR 不可用，请手工填写尺寸。' + result.stderr.decode('utf-8', errors='replace')[-500:])
            try:
                data = json.loads(result.stdout.decode('utf-8-sig'))
                fallback = associate_dimensions(data['words'], data['width'], data['height'])
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                raise ValueError('Windows OCR 返回结果无法解析，请手工填写草图尺寸。')
            if fallback.width_cm is not None:
                return fallback
    return fallback
