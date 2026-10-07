"""Detect the complete outer-to-content band, retaining source colours and lines."""
from dataclasses import dataclass
import numpy as np
from PIL import Image
from shape_crop.services.texture_period import extract_period, extract_dark_period
from shape_crop.services.floating_artwork import detect_floating_artwork


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
    strip_is_sentence: bool = False
    sentence_layers: tuple = ()
    floating_artwork: object = None


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
    if depth <= 1:
        return depth
    end = depth
    while end > max(0, depth - 4 * run):
        if not uniform[end - 1]:
            end -= 1
            continue
        background = colours[end - 1]
        matches = uniform & (np.max(np.abs(colours - background), axis=1) <= 18)
        start = end - 1
        while start > 0 and matches[start - 1]:
            start -= 1
        if start == 0:
            return depth
        if end - start >= max(6 * run, round(height * .10)):
            # Require a bounded separator returning to the same background on
            # both sides. A horizontal artwork line can follow the blank area;
            # it belongs to content and must not become a perimeter stripe.
            earlier = np.flatnonzero(matches[max(0, start - 4 * run):start])
            return start if earlier.size else depth
        end = start
    return depth


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
    scan_end = depth or limit
    blank_start = _blank_content_start(uniform, median, scan_end, height, run)
    if blank_start < scan_end:
        # The 93% flat-row criterion may classify a few glyph descenders as
        # blank. Keep them until three completely clear sampled rows follow.
        end = min(limit, blank_start + 4 * run)
        background = median[end - 1]
        clear = np.all(np.max(np.abs(rows[blank_start:end] - background), axis=2) <= 18, axis=1)
        for offset in range(len(clear) - 2):
            if np.all(clear[offset:offset + 3]):
                return blank_start + offset
        return blank_start
    if depth:
        return depth
    # A centred illustration can lie beyond this edge's bounded scan. A long
    # blank region after an enclosed frame still identifies a valid boundary.
    return 0


def _sentence_layer(strip):
    """Extract sparse original ink and its tangential source anchor."""
    variation = np.std(strip.astype(np.float32), axis=1).mean(axis=1)
    rows = np.flatnonzero(variation > max(2., variation.max() * .25))
    if not rows.size:
        return None
    selected = strip[rows].astype(np.float32)
    background = np.median(selected, axis=1)
    ink = np.max(np.abs(selected - background[:, None, :]), axis=2) > 30
    if np.mean(ink) > .45:
        return None
    columns = np.flatnonzero(np.any(ink, axis=0))
    if not columns.size:
        return None
    # Full-span English can have sparse strokes too. It belongs to continuous
    # perimeter mapping; treating it as four local sentences cuts the side ink.
    if columns[-1] - columns[0] + 1 >= strip.shape[1] * .8:
        return None
    offset = round((strip.shape[1] - 1 - columns[0] - columns[-1]) / 2)
    alpha = np.zeros(strip.shape[:2], dtype=np.uint8)
    alpha[rows] = (np.max(np.abs(selected - background[:, None, :]), axis=2) > 8) * 255
    layer = np.concatenate((strip, alpha[..., None]), axis=2)
    anchor = (columns[0] + columns[-1]) / 2 / max(1, strip.shape[1] - 1)
    return np.roll(layer, offset, axis=1), float(anchor)


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
    floating = detect_floating_artwork(probe)
    if floating is not None and depth:
        # A genuine repeating frame ornament is not a gallery's blank moat.
        # Do not reclassify patterned borders around ordinary cover artwork.
        probe_depth = max(1, round(depth * probe.height / height))
        probe_left = max(0, round(left * probe.width / width))
        probe_right = max(probe_left + 1, round(right * probe.width / width))
        _, frame_period = extract_period(detected[:probe_depth, probe_left:probe_right])
        if frame_period and frame_period >= 4:
            floating = None
    if floating is not None:
        bounds, frame, background = floating
        ratios = (width / probe.width, height / probe.height) * 2
        bounds = tuple(float(value * ratio) for value, ratio in zip(bounds, ratios))
        frame = tuple(float(value * ratio) for value, ratio in zip(frame, ratios))
        floating = bounds, frame, background
        # Gallery whitespace is content. Extract just the actual rectangular
        # frame, including a small recognition margin for antialiased outlines.
        padding = max(1, round(3 * max(width, height) / min(800, max(width, height))))
        left, top = round(frame[0]) + padding, round(frame[1]) + padding
        right, bottom = round(frame[2]) - padding, round(frame[3]) - padding
        depth = top
    if right <= left or bottom <= top:
        raise ValueError('原素材内容区识别失败，四边边框已占满图片')
    # Extract only the safe horizontal span. Side borders need not equal the top depth.
    safe_left, safe_right = min(left + 1, right - 1), max(left + 1, right - 1)
    region = pixels[:max(1, depth), safe_left:safe_right]
    strip, period = extract_period(region)
    if not period:
        strip, period = extract_dark_period(region)
    sentence = False
    layers = ()
    if not period:
        top_layer = _sentence_layer(region)
        if top_layer is not None:
            sentence = True
            # Preserve each original edge separately in clockwise order. Their
            # anchors retain diagonal placement instead of inventing repeats.
            layers = (top_layer,
                _sentence_layer(pixels[top:bottom, right:][:, ::-1].transpose(1, 0, 2)),
                _sentence_layer(pixels[bottom:, safe_left:safe_right][::-1, ::-1]),
                _sentence_layer(pixels[top:bottom, :left].transpose(1, 0, 2)[:, ::-1]))
            # Use a continuous frame without the source sentence; original ink
            # is applied separately at its own source anchor on each edge.
            strip = np.repeat(np.median(region, axis=1).astype(np.uint8)[:, None, :],
                              region.shape[1], axis=1)
    # Sampling is read-only; a view avoids retaining a second near-full image.
    content = pixels[top:bottom, left:right]
    message = f'自动读取完整边框带：{depth / height * 100:.2f}% 短边，原色原层次' if depth else '未检测到稳定边框分隔线，保留原图填充；可用高级选区'
    if period:
        message += f'；装饰周期 {period}px'
    elif sentence:
        message += '；局部英文保留原位置'
    elif np.any(np.std(region.astype(np.float32), axis=1) > 2):
        message += '；满幅装饰带连续环绕'
    if floating is not None:
        message += '；独立图案留白类：完整图案组等比适配，保留原素材最小留白距离'
    return SourceLayout(pixels, strip, depth, width, height, message, content,
                        (left, top, right, bottom), period, sentence, layers, floating)
