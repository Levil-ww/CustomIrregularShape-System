"""Detect the complete outer-to-content band, retaining source colours and lines."""
from dataclasses import dataclass
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class SourceLayout:
    image: np.ndarray
    strip: np.ndarray
    border_depth_px: int
    width_px: int
    height_px: int
    report: str


def analyze_layout(image):
    if image.height > image.width:
        image = image.transpose(Image.Transpose.ROTATE_90)
    pixels = np.asarray(image)
    height, width = pixels.shape[:2]
    # Evaluate horizontal uniformity inside the middle half, away from rectangular corners.
    limit = max(2, int(height * .22))
    columns = np.linspace(width * .25, width * .75 - 1, min(384, max(2, width // 2))).astype(int)
    rows = pixels[:limit, columns].astype(np.float32)
    median = np.median(rows, axis=1)
    uniform = np.mean(np.max(np.abs(rows - median[:, None, :]), axis=2) <= 10, axis=1) >= .93
    # Last uniform separator before sustained floral texture. The full band includes background,
    # ornament and all final separator lines; no generic line colour/thickness is substituted.
    run = max(5, round(height * .009))
    depth = None
    for row in range(1, limit - run):
        if uniform[row - 1] and not uniform[row] and not np.any(uniform[row:row + run]):
            depth = row
    if depth is None:
        # Some materials have no flat separators. Preserve the image directly, do not fabricate lines.
        depth = 0
    left, right = min(depth + 1, width // 3), max(width - depth - 1, width * 2 // 3)
    strip = pixels[:max(1, depth), left:right].copy()
    message = f'自动读取完整边框带：{depth / height * 100:.2f}% 短边，原色原层次' if depth else '未检测到稳定边框分隔线，保留原图填充；可用高级选区'
    return SourceLayout(pixels, strip, depth, width, height, message)
