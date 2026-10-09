"""Recognize isolated artwork surrounded by a flat background, without names."""
import numpy as np


def _components(mask):
    parents, boxes, counts = [], [], []

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    previous = []
    for y, row in enumerate(mask):
        changes = np.diff(np.r_[False, row, False].astype(np.int8))
        spans = zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1))
        current, cursor = [], 0
        for left, right in spans:
            while cursor < len(previous) and previous[cursor][1] < left:
                cursor += 1
            linked, index = [], cursor
            while index < len(previous) and previous[index][0] <= right:
                linked.append(root(previous[index][2]))
                index += 1
            if linked:
                label = linked[0]
                for other in set(linked[1:]):
                    other, label = root(other), root(label)
                    if other != label:
                        parents[other] = label
                        a, b = boxes[label], boxes[other]
                        boxes[label] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                        counts[label] += counts[other]
                box = boxes[label]
                boxes[label] = [min(box[0], left), box[1], max(box[2], right), y + 1]
                counts[label] += right - left
            else:
                label = len(parents)
                parents.append(label)
                boxes.append([left, y, right, y + 1])
                counts.append(right - left)
            current.append((left, right, label))
        previous = current
    return [(boxes[i], counts[i]) for i in range(len(parents)) if root(i) == i]


def detect_floating_artwork(image):
    """Return artwork bounds, frame interior and flat colour for enclosed art."""
    probe = image.copy()
    probe.thumbnail((800, 800))
    pixels = np.asarray(probe)
    height, width = pixels.shape[:2]
    background = np.median(pixels.reshape(-1, 3), axis=0)
    foreground = np.max(np.abs(pixels.astype(np.float32) - background), axis=2) > 24
    if np.mean(~foreground) < .40:
        return None
    frames, artwork = [], []
    for box, count in _components(foreground):
        left, top, right, bottom = box
        if right - left > width * .80 and bottom - top > height * .70:
            frames.append(box)
        elif count >= max(12, width * height * .0002):
            artwork.append(box)
    if not artwork:
        return None
    bounds = (min(b[0] for b in artwork), min(b[1] for b in artwork),
              max(b[2] for b in artwork), max(b[3] for b in artwork))
    frame = (max((b[0] for b in frames), default=0), max((b[1] for b in frames), default=0),
             min((b[2] for b in frames), default=width), min((b[3] for b in frames), default=height))
    gaps = (bounds[0] - frame[0], bounds[1] - frame[1], frame[2] - bounds[2], frame[3] - bounds[3])
    # A real blank moat on ALL sides distinguishes gallery-style compositions
    # from edge-to-edge tiles, horizontal floral bands and decorative frames.
    if min(gaps) < max(3, min(width, height) * .05):
        return None
    # Component bounds alone can mistake a contrasting text/frame band for
    # empty space: large connected outlines are excluded from artwork above.
    # Require the actual four clearance strips to share the content background.
    # Allow a thin frame outline and antialiasing, as in genuine gallery art.
    a, b, c, d = bounds
    left, top, right, bottom = frame
    # Exclude only the measured thin, continuous frame stroke from the blank
    # test. A fixed occupancy allowance counts the same line differently when
    # the source's side clearance changes. Thick contrasting bands still fail.
    limit = max(3, round(min(width, height) * .015))

    def stroke_end(rows):
        count = 0
        for row in rows[:limit + 1]:
            if np.mean(row) < .70:
                return count
            count += 1
        return 0

    clean_top = top + stroke_end(foreground[top:b, a:c])
    clean_bottom = bottom - stroke_end(foreground[d:bottom, a:c][::-1])
    clean_left = left + stroke_end(foreground[b:d, left:a].T)
    clean_right = right - stroke_end(foreground[b:d, c:right].T[::-1])
    moat = (foreground[clean_top:b, a:c], foreground[d:clean_bottom, a:c],
            foreground[b:d, clean_left:a], foreground[b:d, c:clean_right])
    if any(not strip.size or np.mean(strip) > .10 for strip in moat):
        return None
    ratios = (image.width / width, image.height / height) * 2
    bounds = tuple(value * ratio for value, ratio in zip(bounds, ratios))
    frame = tuple(value * ratio for value, ratio in zip(frame, ratios))
    return bounds, frame, tuple(int(value) for value in background)


def detect_contrasting_artwork(image):
    """Detect one dense picture whose flat moat differs from its interior."""
    probe = image.copy()
    probe.thumbnail((800, 800))
    pixels = np.asarray(probe)
    h, w = pixels.shape[:2]
    band = max(3, round(min(h, w) * .035))
    edges = np.concatenate((pixels[:band].reshape(-1, 3), pixels[-band:].reshape(-1, 3),
                            pixels[:, :band].reshape(-1, 3), pixels[:, -band:].reshape(-1, 3)))
    background = np.median(edges, axis=0)
    if np.mean(np.max(np.abs(edges.astype(float) - background), axis=1) < 12) < .60:
        return None
    foreground = np.max(np.abs(pixels.astype(np.float32) - background), axis=2) > 24
    frames, pictures, outlines = [], [], []
    for box, count in _components(foreground):
        a, b, c, d = box
        area = (c - a) * (d - b)
        if c - a > w * .8 and d - b > h * .7 and count < area * .15:
            # Only complete thin rectangles are outer frames. Dense filled
            # pictures can be equally large but belong to the artwork group.
            frame_mask = foreground[b:d, a:c]
            edge_width = max(2, round(min(w, h) * .008))
            sides = (frame_mask[:edge_width, edge_width:-edge_width].mean(axis=1),
                     frame_mask[-edge_width:, edge_width:-edge_width].mean(axis=1),
                     frame_mask[edge_width:-edge_width, :edge_width].mean(axis=0),
                     frame_mask[edge_width:-edge_width, -edge_width:].mean(axis=0))
            if all(values.size and np.max(values) > .95 for values in sides):
                frames.append(box)
            else:
                outlines.append(box)
        elif c - a > w * .5 and d - b > h * .4 and count > area * .6:
            pictures.append(box)
        elif count > max(12, w * h * .0002):
            return None
    if len(pictures) != 1 or not frames:
        return None
    bounds = pictures[0]
    for outline in outlines:
        a, b, c, d = bounds
        e, f, g, j = outline
        tolerance = max(4, min(w, h) * .035)
        if not (e <= a and f <= b and g >= c and j >= d and
                max(a - e, b - f, g - c, j - d) < tolerance):
            return None
        bounds = (e, f, g, j)
    a, b, c, d = bounds
    left, top, right, bottom = frame = (max(box[0] for box in frames), max(box[1] for box in frames),
                                       min(box[2] for box in frames), min(box[3] for box in frames))
    # The image edge alone is not an independent frame: coloured border
    # bands with an attached inner outline must keep their established path.
    if min(left, top, w - right, h - bottom) < max(2, min(w, h) * .005):
        return None
    if min(a - left, b - top, right - c, bottom - d) < max(3, min(w, h) * .015):
        return None
    # A complete quiet strip on every side proves isolation. Remove only the
    # verified thin outer frame strokes, not arbitrary contrasting colour bands.
    padding = max(2, round(min(w, h) * .008))
    moat = (foreground[top + padding:b, left + padding:right - padding],
            foreground[d:bottom - padding, left + padding:right - padding],
            foreground[b:d, left + padding:a], foreground[b:d, c:right - padding])
    if any(not region.size or np.mean(region) > .10 for region in moat):
        return None
    ratios = (image.width / w, image.height / h) * 2
    return (tuple(float(v * r) for v, r in zip(bounds, ratios)),
            tuple(float(v * r) for v, r in zip(frame, ratios)), tuple(int(v) for v in background))
