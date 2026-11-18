"""Compose circular artwork using physical dimensions."""
import math
from PIL import Image, ImageDraw, ImageOps


def compose_circle(outer, inner, diameter, inner_diameter, gap, line_px, pixels):
    values = (diameter, inner_diameter, gap, line_px, pixels)
    if not all(math.isfinite(v) for v in values) or diameter <= 0 or inner_diameter < 0 or gap < 0 or line_px < 0 or pixels < 2:
        raise ValueError('圆形尺寸、间隙或线宽不合法')
    if inner_diameter and inner_diameter + 2 * gap >= diameter:
        raise ValueError('内圆直径与两侧间隙之和必须小于外圆直径')
    if inner_diameter and inner is None:
        raise ValueError('请提供内圆素材')
    pixels = int(pixels)
    if pixels * pixels > 180_000_000:
        raise ValueError('当前导出超过 1.8 亿像素，请降低 DPI 或尺寸')
    def fitted(image, side):
        return ImageOps.fit(image.convert('RGBA'), (side, side), method=Image.Resampling.LANCZOS)
    mask = Image.new('L', (pixels, pixels), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, pixels - 1, pixels - 1), fill=255)
    result = fitted(outer, pixels)
    result.putalpha(mask)
    if inner_diameter:
        inner_side = max(1, round(pixels * inner_diameter / diameter))
        hole_side = min(pixels, round(pixels * (inner_diameter + 2 * gap) / diameter))
        hole = (pixels - hole_side) // 2
        draw.ellipse((hole, hole, hole + hole_side - 1, hole + hole_side - 1), fill=0)
        result.putalpha(mask)
        small = fitted(inner, inner_side)
        small_mask = Image.new('L', (inner_side, inner_side), 0)
        ImageDraw.Draw(small_mask).ellipse((0, 0, inner_side - 1, inner_side - 1), fill=255)
        small.putalpha(small_mask)
        pos = (pixels - inner_side) // 2
        result.alpha_composite(small, (pos, pos))
    if line_px:
        pen = ImageDraw.Draw(result)
        width = max(1, int(line_px))
        pen.ellipse((0, 0, pixels - 1, pixels - 1), outline='black', width=width)
        if inner_diameter:
            pen.ellipse((pos, pos, pos + inner_side - 1, pos + inner_side - 1), outline='black', width=width)
            if gap:
                pen.ellipse((hole - width, hole - width, hole + hole_side - 1 + width,
                             hole + hole_side - 1 + width), outline='black', width=width)
    return result
