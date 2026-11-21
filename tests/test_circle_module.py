import pytest
from PIL import Image

from shape_crop.services.circle import parse_circle_name, match_circle_material, generate_circle
from shape_crop.core.circle_composition import compose_circle


def test_parse_circle_names():
    assert parse_circle_name('双面格-定制-裁剪有图-蔓生花;140CM圆形裁剪有图.jpg').diameter_cm == 140
    assert parse_circle_name('双面格-定制-裁剪有图-蔓生花;直径150CM剪裁有图.jpg').pattern == '蔓生花'


def test_matching_prefers_round_and_closest(tmp_path):
    for name in ['双面格-蔓生花;80X140cm.jpg', '双面格-蔓生花;160cm圆形.jpg', '双面格-蔓生花;140cm圆形.jpg']:
        (tmp_path / name).touch()
    match = match_circle_material(parse_circle_name('双面格-蔓生花;140CM圆形.jpg'), tmp_path, 140)
    assert '140cm圆形' in str(match.path)


def test_match_pattern_after_leading_diameter(tmp_path):
    wrong = '双面格-标准-直径100-中古大花;直径100.jpg'
    correct = '双面格-标准-直径100-蔓生花;直径100.jpg'
    for name in (wrong, correct):
        (tmp_path / name).touch()
    target = parse_circle_name('双面格-标准-直径95-蔓生花;直径95')
    assert target.pattern == '蔓生花'
    assert match_circle_material(target, tmp_path, 96).path.endswith(correct)
    (tmp_path / correct).unlink()
    with pytest.raises(ValueError, match='蔓生花'):
        match_circle_material(target, tmp_path, 96)


def test_circle_name_prefers_order_diameter_and_rejects_missing_pattern():
    parsed = parse_circle_name('双面格-标准-直径100-蔓生花;直径95')
    assert (parsed.pattern, parsed.diameter_cm) == ('蔓生花', 95)
    assert parse_circle_name('双面格-标准-蔓生花-直径100;直径95').pattern == '蔓生花'
    assert parse_circle_name('双面格-标准-直径100-蔓生花.jpg').pattern == '蔓生花'
    assert parse_circle_name('双面格-蔓生花直径100.jpg').pattern == '蔓生花'
    with pytest.raises(ValueError, match='花型'):
        parse_circle_name('双面格-标准-直径100;直径95')


def test_concentric_gap_and_diameter():
    outer = Image.new('RGB', (100, 100), 'red')
    inner = Image.new('RGB', (100, 100), 'blue')
    result = compose_circle(outer, inner, 100, 60, 5, 0, 100)
    assert result.getpixel((50, 50))[:3] == (0, 0, 255)
    assert result.getpixel((50, 18))[3] == 0
    assert result.getpixel((50, 10))[:3] == (255, 0, 0)
    with pytest.raises(ValueError):
        compose_circle(outer, inner, 100, 95, 3, 0, 100)
    outlined = compose_circle(outer, inner, 100, 60, 5, 2, 100)
    assert outlined.getpixel((50, 19))[3] == 0


def test_concentric_gui_gap_direction_and_compensation(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shape_crop.gui.circle_module import CircleModule
    widget = CircleModule()
    assert widget.mode.currentText() == '同心圆'
    assert widget.inner.isEnabled() and widget.gap.isEnabled()
    widget.diameter.setValue(100)
    widget.inner.setValue(55)
    assert widget.snapshot()['inner_diameter'] == 56
    widget.gap.setValue(2)
    assert widget.snapshot()['inner_diameter'] == 56
    assert '空洞直径 60 cm' in widget.size_label.text()
    widget.gap_direction.setCurrentIndex(1)
    assert widget.snapshot()['inner_diameter'] == 52
    assert '内圆成品直径 52 cm' in widget.size_label.text()
    assert '空洞直径 56 cm' in widget.size_label.text()
    assert widget.outline.inner == 52
    widget.gap.setValue(28)
    with pytest.raises(ValueError, match='内圆成品直径'):
        widget.snapshot()


def test_rgb_resize_preserves_previous_output():
    import numpy as np
    from PIL import ImageOps
    source = Image.fromarray(np.random.default_rng(42).integers(0, 256, (70, 90, 3), dtype=np.uint8))
    expected = ImageOps.fit(source.convert('RGBA'), (50, 50), method=Image.Resampling.LANCZOS)
    actual = compose_circle(source, None, 50, 0, 0, 0, 50)
    assert actual.getpixel((25, 25)) == expected.getpixel((25, 25))
    assert np.array_equal(np.asarray(actual)[10:40, 10:40], np.asarray(expected)[10:40, 10:40])


def test_circle_gui_uses_manual_diameter_until_filename_changes(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shape_crop.gui.circle_module import CircleModule
    widget = CircleModule()
    widget.mode.setCurrentIndex(0)
    widget.target.setText('双面格-蔓生花;140CM圆形.jpg')
    assert widget.diameter.value() == 140
    widget.diameter.setValue(145)
    assert widget.snapshot()['diameter'] == 145
    widget.target.setText('双面格-蔓生花;160CM圆形.jpg')
    assert widget.diameter.value() == 160
    assert '161 cm' in widget.size_label.text()
    widget.diameter.setValue(165)
    assert widget.snapshot()['diameter'] == 165
    widget.reset_diameter()
    assert widget.diameter.value() == 160
    widget.target.setText('双面格-蔓生花')
    assert widget.diameter.value() == 0
    widget.diameter.setValue(140)
    assert widget.snapshot()['diameter'] == 140
    assert parse_circle_name('双面格-蔓生花', require_diameter=False).pattern == '蔓生花'


def test_circle_history_selection_updates_diameter(monkeypatch, tmp_path):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtCore import QSettings
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shape_crop.gui import circle_module
    monkeypatch.setattr(circle_module, 'QSettings', lambda *args: QSettings(str(tmp_path / 'settings.ini'), QSettings.IniFormat))
    widget = circle_module.CircleModule()
    widget.remember_target('双面格-蔓生花;直径105CM裁剪有图')
    widget.remember_target('双面格-蔓生花;140cm圆形裁剪有图')
    widget.target.setText('双面格-蔓生花;直径150CM')
    widget.diameter.setValue(155)
    widget.target_history.setCurrentIndex(1)
    assert widget.diameter.value() == 105
    assert widget.outline.diameter == 106


def test_circle_gui_layout_keeps_advanced_options_and_actions_accessible(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shape_crop.gui.circle_module import CircleModule
    widget = CircleModule()
    widget.show()
    app.processEvents()
    assert widget.sidebar.objectName() == 'sidebar'
    assert widget.preview_card.objectName() == 'previewCard'
    assert widget.export_button.objectName() == 'primary'
    assert not widget.advanced.isVisible()
    widget.advanced_toggle.setChecked(True)
    assert widget.advanced.isVisible()
    assert widget.dpi.value() == 150
    assert widget.preview_button.isVisible() and widget.export_button.isVisible()
    widget.close()


def test_export_size_and_resolution(tmp_path):
    source = tmp_path / 'source.png'
    output = tmp_path / 'result.png'
    Image.new('RGB', (100, 100), 'red').save(source)
    generate_circle('双面格-蔓生花;140CM圆形', '', 10, 1, 0, 0, 10, 100,
                    str(source), preview=False, output=str(output))
    with Image.open(output) as result:
        assert result.size == (round(11 / 2.54 * 100),) * 2
        assert result.info['dpi'][0] == pytest.approx(100, abs=0.1)


def test_concentric_generation_scans_library_once(tmp_path, monkeypatch):
    from shape_crop.services import circle
    for size in (60, 100):
        Image.new('RGB', (50, 50), 'red').save(tmp_path / f'双面格-蔓生花;直径{size}.jpg')
    original = circle.os.walk
    scans = []
    def tracked(*args, **kwargs):
        scans.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(circle.os, 'walk', tracked)
    generate_circle('双面格-蔓生花;直径100', str(tmp_path), 100, 1, 60, 0, 10, 150)
    assert len(scans) == 1


def test_circle_history_is_saved_and_restored(monkeypatch, tmp_path):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtCore import QSettings
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shape_crop.gui import circle_module
    monkeypatch.setattr(circle_module, 'QSettings', lambda *args: QSettings(str(tmp_path / 'settings.ini'), QSettings.IniFormat))
    first = circle_module.CircleModule()
    first.remember_target('双面格-蔓生花;直径105')
    first.remember_target('双面格-蔓生花;直径95')
    second = circle_module.CircleModule()
    assert second.target_history.itemText(0) == '双面格-蔓生花;直径95'
    assert second.target_history.itemText(1) == '双面格-蔓生花;直径105'
    assert second.dpi.value() == 150


def test_circle_catalog_warm_lookup_and_change_notification(tmp_path, monkeypatch):
    from unittest.mock import patch
    from shape_crop.services import catalog
    from shape_crop.services.circle import CircleCatalogSession
    old = tmp_path / '双面格-蔓生花;直径120.jpg'
    old.touch()
    session = CircleCatalogSession(tmp_path)
    session._ready.set()
    session._thread = object()
    session._active = True
    target = parse_circle_name('双面格-蔓生花;直径100')
    assert session.match_many(target, [100, 60])[0].path == str(old)
    new = tmp_path / '双面格-蔓生花;直径100.jpg'
    new.touch()
    session._events.append((1, str(new)))
    with patch.object(catalog.os, 'scandir', side_effect=AssertionError('重复遍历图库')):
        assert session.match_many(target, [100])[0].path == str(new)
        assert session.match_many(target, [100])[0].path == str(new)
        new.unlink()
        session._events.append((2, str(new)))
        assert session.match_many(target, [100])[0].path == str(old)


def test_same_source_is_loaded_once_for_concentric_export(tmp_path, monkeypatch):
    from shape_crop.services import circle
    path = tmp_path / '素材.jpg'
    Image.new('RGB', (100, 100), 'red').save(path)
    load = circle.load_image
    calls = []
    def tracked(*args, **kwargs):
        calls.append(args[0])
        return load(*args, **kwargs)
    monkeypatch.setattr(circle, 'load_image', tracked)
    generate_circle('双面格-蔓生花;直径100', '', 10, 1, 5, 0, 10, 100,
                    str(path), str(path), preview=False, output=str(tmp_path / 'result.png'))
    assert calls == [str(path)]


def test_rectangular_source_rebuilds_frame_for_both_circles(tmp_path, monkeypatch):
    from PIL import ImageDraw
    from shape_crop.services import design_service
    path = tmp_path / '双面格-复古大花;50x140cm.jpg'
    Image.new('RGB', (280, 100), '#c99').save(path)
    calls = []
    def render(design, preview=False, **kwargs):
        calls.append((design.diameter_cm, design.height_cm, design.material.path))
        image = Image.new('RGBA', (200, 200), (190, 110, 80, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((0, 0, 199, 199), outline=(30, 30, 30), width=20)
        return image
    monkeypatch.setattr(design_service, 'generate', render)
    image, detail = generate_circle('双面格-复古大花;直径100', str(tmp_path), 100, 1, 60, 5, 0, 50)
    assert [call[:2] for call in calls] == [(101, 101), (60, 60)]
    assert image.getpixel((image.width // 2, 1))[:3] == (30, 30, 30)
    assert '矩形素材' in detail


def test_circle_history_deduplicates_and_can_be_cleared(monkeypatch, tmp_path):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtCore import QSettings
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shape_crop.gui import circle_module
    monkeypatch.setattr(circle_module, 'QSettings', lambda *args: QSettings(str(tmp_path / 'settings.ini'), QSettings.IniFormat))
    widget = circle_module.CircleModule()
    widget.clear_target_history()
    for i in range(18):
        widget.remember_target(f'花{i};直径100')
    widget.remember_target('花10;直径100')
    assert widget.target_history.count() == 15
    assert widget.target_history.itemText(0) == '花10;直径100'
    assert sum(widget.target_history.itemText(i) == '花10;直径100' for i in range(15)) == 1
    widget.target.setText('正在输入的名称')
    widget.clear_target_history()
    assert widget.target.text() == '正在输入的名称'
    assert widget.target_history.count() == 0
