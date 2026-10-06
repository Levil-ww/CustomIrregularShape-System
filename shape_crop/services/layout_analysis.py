"""Detect the complete outer-to-content band, retaining source colours and lines."""
from dataclasses import dataclass
import numpy as np
from PIL import Image
from shape_crop.services.texture_period import extract_period


@dataclass(frozen=True)
class SourceLayout:
    image: np.ndarray
    strip: np.ndarray
    border_depth_px: int
    width_px: int
    height_px: int
    report: str
    content: np.ndarray
    content_box_px: tuple[int, int, int, int]
    strip_period_px: int = 0


def boundary_depth(pixels):
    """Scan one edge toward the middle, independent of the other three edge widths."""
    height, width = pixels.shape[:2]
    # Evaluate horizontal uniformity inside the middle half, away from rectangular corners.
    limit = max(2, int(height * .40))
    columns = np.linspace(width * .25, width * .75 - 1, min(384, max(2, width // 2))).astype(int)
    rows = pixels[:limit, columns].astype(np.float32)
    median = np.median(rows, axis=1)
    uniform = np.mean(np.max(np.abs(rows - median[:, None, :]), axis=2) <= 10, axis=1) >= .93
    # Stop at the first sustained content transition. A later blank row inside an illustration
    # is artwork, not another separator; scanning past content silently discards the picture.
    run = max(5, round(height * .009))
    depth = None
    for row in range(1, limit - run):
        if uniform[row - 1] and not uniform[row] and not np.any(uniform[row:row + run]):
            # A short, genuinely periodic ornament followed by another separator is still
            # a border layer. A later white gap after non-periodic floral content is not.
            following = np.flatnonzero(uniform[row:row + max(run + 1, round(height * .10))])
            if following.size:
                end = row + int(following[0])
                _, period = extract_period(pixels[row:end, columns[0]:columns[-1] + 1])
                if period:
                    continue
            depth = row
            break
    return depth or 0


def analyze_layout(image):
    if image.height > image.width:
        image = image.transpose(Image.Transpose.ROTATE_90)
    pixels = np.asarray(image)
    height, width = pixels.shape[:2]
    depth = boundary_depth(pixels)
    bottom = height - boundary_depth(pixels[::-1])
    left = boundary_depth(pixels.transpose(1, 0, 2))
    right = width - boundary_depth(pixels[:, ::-1].transpose(1, 0, 2))
    top = depth
    if right <= left or bottom <= top:
        raise ValueError('原素材内容区识别失败，四边边框已占满图片')
    # Extract only the safe horizontal span. Side borders need not equal the top depth.
    safe_left, safe_right = min(left + 1, right - 1), max(left + 1, right - 1)
    strip, period = extract_period(pixels[:max(1, depth), safe_left:safe_right])
    content = pixels[top:bottom, left:right].copy()
    message = f'自动读取完整边框带：{depth / height * 100:.2f}% 短边，原色原层次' if depth else '未检测到稳定边框分隔线，保留原图填充；可用高级选区'
    if period:
        message += f'；装饰周期 {period}px'
    return SourceLayout(pixels, strip, depth, width, height, message, content,
                        (left, top, right, bottom), period)
