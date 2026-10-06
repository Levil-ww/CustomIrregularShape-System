"""Desktop warm lookups must not enumerate the SMB share on every order."""
import os
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch
import pytest
from shape_crop.services.catalog_session import CatalogSession
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services import catalog


def fake_watched_session(directory):
    session = CatalogSession(directory)
    session._ready.set()
    session._thread = object()
    session._active = True
    return session


def test_switch_orders_never_lists_watched_share_again(tmp_path):
    (tmp_path / '花甲;80x140cm.jpg').touch()
    second = tmp_path / '花乙;80x140cm.jpg'
    second.touch()
    session = fake_watched_session(tmp_path)
    session.match(parse_filename('花甲;80x140cm'))
    with patch.object(catalog.os, 'scandir', side_effect=AssertionError('重新遍历网络图库')):
        assert session.match(parse_filename('花乙;80x140cm')).path == str(second)


def test_changed_files_update_only_notifications_without_listing(tmp_path):
    original = tmp_path / '花甲;80x150cm.jpg'
    original.touch()
    target = parse_filename('花甲;80x140cm')
    session = fake_watched_session(tmp_path)
    assert session.match(target).path == str(original)
    new = tmp_path / '花甲;80x140cm.jpg'
    new.touch()
    session._events.append((1, str(new)))
    with patch.object(catalog.os, 'scandir', side_effect=AssertionError('增量通知仍全库扫描')):
        assert session.match(target).path == str(new)
        renamed = tmp_path / '花乙;80x140cm.jpg'
        new.rename(renamed)
        session._events.extend([(4, str(new)), (5, str(renamed))])
        assert session.match(target).path == str(original)
        assert session.match(parse_filename('花乙;80x140cm')).path == str(renamed)


def test_watcher_failure_and_manual_refresh_verify_directory(tmp_path):
    (tmp_path / '花甲;80x150cm.jpg').touch()
    session = fake_watched_session(tmp_path)
    target = parse_filename('花甲;80x140cm')
    session.match(target)
    new = tmp_path / '花甲;80x140cm.jpg'
    new.touch()
    session.request_refresh()
    assert session.match(target).path == str(new)
    new.unlink()
    session._active = False
    assert session.match(target).path.endswith('80x150cm.jpg')


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows recursive watcher')
def test_native_recursive_watcher_and_shutdown(tmp_path):
    (tmp_path / '花甲;80x150cm.jpg').touch()
    session = CatalogSession(tmp_path)
    try:
        target = parse_filename('花甲;80x140cm')
        session.match(target)
        assert session.active, session.watch_error
        nested = tmp_path / 'new'
        nested.mkdir()
        new = nested / '花甲;80x140cm.jpg'
        new.touch()
        deadline = monotonic() + 3
        while monotonic() < deadline:
            with session._lock:
                notified = any(path == str(new) for _, path in session._events)
            if notified:
                break
            sleep(.02)
        assert notified
        assert session.match(target).path == str(new)
    finally:
        session.close()
        session._thread.join(2)
    assert not session._thread.is_alive()
