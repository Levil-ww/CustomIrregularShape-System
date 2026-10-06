"""Cancellable JPG catalog scan and deterministic same-pattern size ranking."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
from collections import OrderedDict
from threading import RLock
from shape_crop.services.filename_parser import parse_filename
from shape_crop.core.renderer import RenderCancelled


@dataclass(frozen=True)
class Match:
    path: str
    source: object
    ratio_error: float


_indexes = OrderedDict()
_index_lock = RLock()


def _check_cancelled(cancelled):
    if cancelled and cancelled():
        raise RenderCancelled('图库扫描已取消')


def _directory_stamp(path):
    # NTFS can defer directory timestamp updates. Compare entry names as well
    # to detect rapid add/rename/delete operations reliably, without reparsing.
    with os.scandir(path) as entries:
        return frozenset(entry.name for entry in entries)


def _catalog(directory, cancelled, progress):
    """Reuse parsed names; inspect every indexed directory for additions/deletions."""
    key = str(directory.resolve())
    with _index_lock:
        cached = _indexes.get(key)
        if cached:
            groups, stamps = cached
            valid = True
            for path, stamp in stamps.items():
                _check_cancelled(cancelled)
                try:
                    if _directory_stamp(path) != stamp:
                        valid = False
                        break
                except OSError:
                    valid = False
                    break
            if valid:
                _indexes.move_to_end(key)
                if progress:
                    progress('已复用图库索引，正在匹配同花型素材…')
                return groups
        groups, stamps, scanned = {}, {}, 0
        def onerror(error):
            raise OSError(f'图库扫描失败：{error.filename}：{error.strerror}') from error
        for root, directories, files in os.walk(directory, onerror=onerror, followlinks=False):
            _check_cancelled(cancelled)
            # Stamp exactly the listing being indexed, so a concurrent rename
            # or addition cannot mark a partial snapshot as current.
            stamps[root] = frozenset(directories + files)
            for name in files:
                _check_cancelled(cancelled)
                if os.path.splitext(name)[1].lower() not in ('.jpg', '.jpeg'):
                    continue
                scanned += 1
                if progress and scanned % 1000 == 0:
                    progress(f'正在建立图库索引：已扫描 {scanned} 张 JPG…')
                if any(word in name for word in ('裁剪有图', '圆形', '直径', '水池', '挖角')):
                    continue
                try:
                    parsed = parse_filename(name)
                except ValueError:
                    continue
                groups.setdefault(parsed.pattern.casefold(), []).append((str(Path(root) / name), parsed))
        _check_cancelled(cancelled)
        _indexes[key] = groups, stamps
        _indexes.move_to_end(key)
        while len(_indexes) > 4:
            _indexes.popitem(last=False)
        return groups


def match_material(target, directory, cancelled=None, progress=None):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError('图库目录不存在或不可访问')
    _check_cancelled(cancelled)
    candidates = []
    groups = _catalog(directory, cancelled, progress)
    for path, parsed in groups.get(target.pattern.casefold(), ()):
        _check_cancelled(cancelled)
        if target.material and parsed.material != target.material:
            continue
        ratio_error = abs(math.log(parsed.ratio / target.ratio))
        size_error = abs(math.log(parsed.width_cm / target.width_cm)) + abs(math.log(parsed.height_cm / target.height_cm))
        candidates.append((ratio_error, size_error, path, parsed))
    if not candidates:
        raise ValueError(f'图库中未找到同材质、同花型“{target.pattern}”的矩形 JPG；可在高级选项指定素材')
    ratio, _, path, parsed = min(candidates, key=lambda item: (item[0], item[1], item[2].casefold()))
    return Match(path, parsed, ratio)
