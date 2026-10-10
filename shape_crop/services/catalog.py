"""Cancellable JPG catalog scan and size ranking within a ratio tolerance."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
from collections import OrderedDict
from threading import RLock
from shape_crop.services.filename_parser import parse_filename
from shape_crop.core.renderer import RenderCancelled


MAX_RATIO_ERROR = math.log(1.05)


@dataclass(frozen=True)
class Match:
    path: str
    source: object
    ratio_error: float


@dataclass
class CatalogIndex:
    groups: dict
    stamps: dict
    records: dict
    children: dict


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


def _parse_entry(name):
    if os.path.splitext(name)[1].lower() not in ('.jpg', '.jpeg') or any(
            word in name for word in ('裁剪有图', '圆形', '直径', '水池', '挖角')):
        return None
    try:
        return parse_filename(name)
    except ValueError:
        return None


def _regroup(index):
    groups = {}
    for root, records in index.records.items():
        for name, parsed in records.items():
            groups.setdefault(parsed.pattern.casefold(), []).append((str(Path(root) / name), parsed))
    index.groups = groups


def _refresh_directory(index, path, cancelled):
    """Update one changed directory; descend only into newly added folders."""
    _check_cancelled(cancelled)
    if not os.path.isdir(path):
        prefix = path + os.sep
        for root in list(index.stamps):
            if root == path or root.startswith(prefix):
                index.stamps.pop(root, None)
                index.records.pop(root, None)
                index.children.pop(root, None)
        return
    with os.scandir(path) as entries:
        names, files, children = set(), set(), set()
        for entry in entries:
            _check_cancelled(cancelled)
            names.add(entry.name)
            if entry.is_dir(follow_symlinks=False):
                children.add(os.path.join(path, entry.name))
            elif not entry.is_symlink():
                files.add(entry.name)
    old = index.records.get(path, {})
    previous = index.stamps.get(path, frozenset())
    records = {name: parsed for name, parsed in old.items() if name in files}
    for name in files - previous:
        _check_cancelled(cancelled)
        parsed = _parse_entry(name)
        if parsed:
            records[name] = parsed
    old_children = index.children.get(path, set())
    for removed in old_children - children:
        _refresh_directory(index, removed, cancelled)
    for added in children - old_children:
        _refresh_directory(index, added, cancelled)
    index.stamps[path] = frozenset(names)
    index.records[path] = records
    index.children[path] = children


def _apply_events(index, events, cancelled):
    """Apply native file notifications without enumerating the network directory."""
    touched, copied = {}, set()
    for action, path in events:
        _check_cancelled(cancelled)
        parent, name = os.path.dirname(path), os.path.basename(path)
        if action in (2, 4):  # removed / old name of a rename
            if path in index.stamps:
                prefix = path + os.sep
                for root in list(index.stamps):
                    if root == path or root.startswith(prefix):
                        index.stamps.pop(root, None)
                        index.records.pop(root, None)
                        index.children.pop(root, None)
                index.children[parent] = index.children.get(parent, set()) - {path}
            elif parent in index.records:
                if parent not in copied:
                    index.records[parent] = dict(index.records[parent])
                    copied.add(parent)
                index.records[parent].pop(name, None)
            if parent in index.stamps:
                touched.setdefault(parent, set(index.stamps[parent])).discard(name)
        elif action in (1, 5):  # added / new name of a rename
            if os.path.isdir(path):
                _refresh_directory(index, path, cancelled)
                index.children[parent] = index.children.get(parent, set()) | {path}
            elif parent in index.records:
                parsed = _parse_entry(name)
                if parsed:
                    if parent not in copied:
                        index.records[parent] = dict(index.records[parent])
                        copied.add(parent)
                    index.records[parent][name] = parsed
            if parent in index.stamps:
                touched.setdefault(parent, set(index.stamps[parent])).add(name)
    for root, names in touched.items():
        if root in index.stamps:
            index.stamps[root] = frozenset(names)


def _catalog(directory, cancelled, progress, verify=True, changes=(), events=()):
    """Reuse parsed names; inspect every indexed directory for additions/deletions."""
    key = str(directory.resolve())
    with _index_lock:
        cached = _indexes.get(key)
        if cached:
            dirty = set(changes)
            if verify:
                for path, stamp in cached.stamps.items():
                    _check_cancelled(cancelled)
                    try:
                        if _directory_stamp(path) != stamp:
                            dirty.add(path)
                    except OSError:
                        dirty.add(path)
            if not dirty and not events:
                _indexes.move_to_end(key)
                if progress:
                    progress('已复用图库索引，正在匹配同花型素材…')
                return cached.groups
            if progress:
                progress(f'正在增量更新图库：{len(events)} 个变动条目…')
            updated = CatalogIndex({}, dict(cached.stamps), dict(cached.records), dict(cached.children))
            _apply_events(updated, events, cancelled)
            for path in sorted(dirty, key=len):
                _refresh_directory(updated, path, cancelled)
            _regroup(updated)
            _indexes[key] = updated
            _indexes.move_to_end(key)
            return updated.groups
        directory = Path(key)
        groups, stamps, records, children, scanned = {}, {}, {}, {}, 0
        def onerror(error):
            pass
        for root, directories, files in os.walk(directory, onerror=onerror, followlinks=False):
            _check_cancelled(cancelled)
            # Stamp exactly the listing being indexed, so a concurrent rename
            # or addition cannot mark a partial snapshot as current.
            stamps[root] = frozenset(directories + files)
            children[root] = {os.path.join(root, name) for name in directories
                              if not os.path.islink(os.path.join(root, name))}
            records[root] = {}
            for name in files:
                _check_cancelled(cancelled)
                if os.path.splitext(name)[1].lower() not in ('.jpg', '.jpeg'):
                    continue
                scanned += 1
                if progress and scanned % 1000 == 0:
                    progress(f'正在建立图库索引：已扫描 {scanned} 张 JPG…')
                parsed = _parse_entry(name)
                if parsed is None:
                    continue
                records[root][name] = parsed
                groups.setdefault(parsed.pattern.casefold(), []).append((str(Path(root) / name), parsed))
        _check_cancelled(cancelled)
        _indexes[key] = CatalogIndex(groups, stamps, records, children)
        _indexes.move_to_end(key)
        while len(_indexes) > 4:
            _indexes.popitem(last=False)
        return groups


def match_material(target, directory, cancelled=None, progress=None, *, verify=True, changes=(), events=()):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError('图库目录不存在或不可访问')
    _check_cancelled(cancelled)
    candidates = []
    groups = _catalog(directory, cancelled, progress, verify, changes, events)
    for path, parsed in groups.get(target.pattern.casefold(), ()):
        _check_cancelled(cancelled)
        if target.material and parsed.material != target.material:
            continue
        ratio_error = abs(math.log(parsed.ratio / target.ratio))
        size_error = abs(math.log(parsed.width_cm / target.width_cm)) + abs(math.log(parsed.height_cm / target.height_cm))
        candidates.append((ratio_error, size_error, path, parsed))
    if not candidates:
        raise ValueError(f'图库中未找到同材质、同花型“{target.pattern}”的矩形 JPG；可在高级选项指定素材')
    def rank(item):
        ratio, size, path, _ = item
        if ratio <= MAX_RATIO_ERROR:
            return (0, size, ratio, path.casefold(), path)
        return (1, ratio, size, path.casefold(), path)

    ratio, _, path, parsed = min(candidates, key=rank)
    return Match(path, parsed, ratio)
