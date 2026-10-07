"""Detect the complete outer-to-content band, retaining source colours and lines."""
from dataclasses import dataclass
import numpy as np
from PIL import Image
from shape_crop.services.texture_period import extract_period, extract_dark_period


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


def _touching_ornament_end(pixels, row, left, right, run):
    """Keep a short periodic dark ornament that overlaps non-periodic content."""
    region = pixels[row:row + max(8, 3 * run), left:right]
    active = np.flatnonzero(np.mean(np.max(region, axis=2) < 40, axis=1) >= .01)
    if (len(active) < 3 or active[0] >= run or
            active[-1] >= len(region) - 2 or np.any(np.diff(active) > 1)):
        return None
    # Require the complete bounded ink run, not a periodic one-row fragment.
    end = int(active[-1]) + 2
    _, period = extract_dark_period(region[:end])
    return row + end if period else None


def _blank_content_start(uniform, colours, depth, height, run):
    """Exclude long artwork whitespace after an enclosed thin frame separator."""
    if depth <= 1 or not uniform[depth - 1]:
        return depth
    background = colours[depth - 1]
    matches = uniform & (np.max(np.abs(colours - background), axis=1) <= 18)
    start = depth - 1
    while start > 0 and matches[start - 1]:
        start -= 1
    if start == 0 or depth - start < max(6 * run, round(height * .10)):
        return depth
    # Require a bounded separator returning to the same background on both
    # sides; a solid outer margin alone does not imply a sparse illustration.
    earlier = np.flatnonzero(matches[max(0, start - 4 * run):start])
    return start if earlier.size else depth


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
                # Repetition alone also describes tiled interior artwork. A
                # frame ornament must be a shallow band with a compact repeat;
                # do not scan through a full floral tile to its next blank gap.
                band_depth = end - row
                # Round beads can span about four recognition runs, including
                # their outline. Keep the compact-repeat guard so large tiled
                # flowers still stop the scan at the content boundary.
                if period and band_depth <= 4 * run and period <= max(4 * run, 2 * band_depth):
                    continue
                # A sentence is not periodic. Keep sparse ink on the preceding
                # flat background when it is enclosed by another flat row.
                # Dense/non-periodic artwork must still stop the edge scan.
                background = median[row - 1]
                matches = np.max(np.abs(rows[row:end] - background), axis=2) <= 18
                enclosed = np.max(np.abs(median[end] - background)) <= 18
                if not period and enclosed and np.mean(matches) >= .45 and np.min(np.mean(matches, axis=1)) >= .25:
                    continue
            ornament_end = _touching_ornament_end(pixels, row, columns[0], columns[-1] + 1, run)
            depth = ornament_end if ornament_end is not None else row
            break
    return _blank_content_start(uniform, median, depth, height, run) if depth else 0


def analyze_layout(image):
    if image.height > image.width:
        image = image.transpose(Image.Transpose.ROTATE_90)
    pixels = np.asarray(image)
    height, width = pixels.shape[:2]
    # Scan at a bounded spatial scale. At print resolution thin floral strokes
    # leave many individually flat rows and can delay the transition by thousands
    # of pixels. Only recognition is reduced; all extracted pixels stay original.
    probe = image.copy() if max(width, height) > 2400 else image
    if probe is not image:
        probe.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
    detected = np.asarray(probe)

    def edge(full, small):
        found = boundary_depth(small)
        if not found:
            return 0
        ratio = full.shape[0] / small.shape[0]
        estimate = round(found * ratio)
        if ratio == 1:
            return estimate
        # Refine the flat-frame to artwork transition, not the strongest colour
        # jump: that jump can be the START of a thin black separator and would
        # exclude the entire line from the extracted frame.
        radius = max(2, int(np.ceil(2 * ratio)))
        lo, hi = max(1, estimate - radius), min(full.shape[0] - 1, estimate + radius)
        columns = np.linspace(full.shape[1] * .25, full.shape[1] * .75 - 1, 384).astype(int)
        rows = full[lo - 1:hi + 4, columns].astype(np.float32)
        colours = np.median(rows, axis=1)
        uniform = np.mean(np.max(np.abs(rows - colours[:, None, :]), axis=2) <= 10,
                          axis=1) >= .93
        transitions = [lo - 1 + index for index in range(1, len(uniform) - 2)
                       if uniform[index - 1] and not np.any(uniform[index:index + 3])]
        return min(transitions, key=lambda value: abs(value - estimate)) if transitions else estimate

    depth = edge(pixels, detected)
    bottom = height - edge(pixels[::-1], detected[::-1])
    left = edge(pixels.transpose(1, 0, 2), detected.transpose(1, 0, 2))
    right = width - edge(pixels[:, ::-1].transpose(1, 0, 2), detected[:, ::-1].transpose(1, 0, 2))
    top = depth
    if right <= left or bottom <= top:
        raise ValueError('原素材内容区识别失败，四边边框已占满图片')
    # Extract only the safe horizontal span. Side borders need not equal the top depth.
    safe_left, safe_right = min(left + 1, right - 1), max(left + 1, right - 1)
    region = pixels[:max(1, depth), safe_left:safe_right]
    strip, period = extract_period(region)
    if not period:
        strip, period = extract_dark_period(region)
    # Sampling is read-only; a view avoids retaining a second near-full image.
    content = pixels[top:bottom, left:right]
    message = f'自动读取完整边框带：{depth / height * 100:.2f}% 短边，原色原层次' if depth else '未检测到稳定边框分隔线，保留原图填充；可用高级选区'
    if period:
        message += f'；装饰周期 {period}px'
    return SourceLayout(pixels, strip, depth, width, height, message, content,
                        (left, top, right, bottom), period)
