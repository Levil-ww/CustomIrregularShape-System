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


def test_circle_gui_manual_diameter_survives_edit(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shape_crop.gui.circle_module import CircleModule
    widget = CircleModule()
    widget.target.setText('双面格-蔓生花;140CM圆形.jpg')
    assert widget.diameter.value() == 140
    widget.diameter.setValue(145)
    assert widget.snapshot()['diameter'] == 145
    widget.target.setText('双面格-蔓生花;160CM圆形.jpg')
    assert widget.diameter.value() == 145
    widget.reset_diameter()
    assert widget.diameter.value() == 160
    assert parse_circle_name('双面格-蔓生花', require_diameter=False).pattern == '蔓生花'


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
