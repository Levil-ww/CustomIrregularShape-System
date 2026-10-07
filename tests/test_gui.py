import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEventLoop, QTimer
import pytest
from PyQt5.QtCore import QSettings
from shape_crop.gui.manual_window import ManualWindow


@pytest.fixture(autouse=True)
def isolated_desktop_settings(tmp_path, monkeypatch):
    from shape_crop.gui import main_window
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.IniFormat)
    monkeypatch.setattr(main_window, 'QSettings', lambda *args: settings)
    return settings


def test_gui_snapshot_presets_and_background_worker():
    app = QApplication.instance() or QApplication([])
    window = ManualWindow()
    assert window.snapshot().diameter_cm == 200
    assert window.snapshot().height_cm == 83.76
    window.fields['height'].setValue(200)
    window.fields['inner'].setValue(100)
    assert window.snapshot().inner_diameter_cm == 100
    loop = QEventLoop()
    errors = []
    window.show_error = errors.append
    window.start_preview()
    worker = window.worker
    assert worker is not None
    worker.finished.connect(loop.quit)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(20000)
    loop.exec_()
    # finished handlers schedule deleteLater; the wrapper may already be deleted.
    assert window.worker is None
    assert not errors
    assert window.preview.original is not None
    assert window.worker is None
    window.close()
    app.processEvents()


def test_automatic_gui_filename_and_worker(tmp_path):
    from PIL import Image
    from shape_crop.gui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    source = tmp_path / '双面格-定制-定制尺寸-花幔;80X140CM.jpg'
    Image.new('RGB', (140, 80), (240, 220, 190)).save(source)
    window = MainWindow()
    window.target.setText('双面格-定制-裁剪有图-花幔;80X140cm裁剪有图')
    window.library.setText(str(tmp_path))
    assert not window.advanced_toggle.isChecked()
    assert '141cm' in window.dimension_label.text() and '81cm' in window.dimension_label.text()
    loop = QEventLoop()
    errors = []
    window.show_error = errors.append
    window.start_task(True)
    worker = window.worker
    assert worker is not None
    worker.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(20000)
    loop.exec_()
    assert window.worker is None
    assert not errors
    assert window.preview.original is not None
    assert '140 × 80cm' in window.match_label.text()
    # Export the same order after preview through the actual background workflow.
    timer.stop()
    window.dpi.setValue(10)
    window.output_dir.setText(str(tmp_path))
    window.start_task(False)
    worker = window.worker
    assert worker is not None
    worker.finished.connect(loop.quit)
    timer.start(20000)
    loop.exec_()
    timer.stop()
    assert window.worker is None
    assert not errors
    exported = tmp_path / (window.target.text() + '.jpg')
    with Image.open(exported) as result:
        assert result.mode == 'RGB'
        assert result.size == (555, 319)
    assert window.progress.value() == 100
    assert '成品已保存' in window.status.text()
    window.close()
    app.processEvents()


def test_arc_gui_sketch_review_and_new_order():
    import pytest
    from shape_crop.gui.main_window import MainWindow
    from shape_crop.services.sketch_recognition import SketchDimensions
    from shape_crop.services.workflow import resolve_request
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.target.setText('花幔;86x138cm')
    window.override.setText('unused.jpg')
    window.sketch_path = 'sketch.png'
    window.sketch_result(SketchDimensions(138,86,108,'核对尺寸'))
    assert window.shape_mode.currentData() == 'arc'
    with pytest.raises(ValueError, match='核对'):
        window.snapshot()
    window.sketch_review.setChecked(True)
    design, _ = resolve_request(window.snapshot())
    assert (design.diameter_cm,design.height_cm,design.straight_cm) == (139,87,108)
    window.width_value.setValue(140)
    assert not window.sketch_review.isChecked()
    assert '与文件名不同' in window.dimension_label.text()
    window.target.setText('花幔;80x130cm')
    assert window.sketch_path == ''
    assert window.straight_value.value() == 0
    assert (window.width_value.value(),window.height_value.value()) == (130,80)
    window.close()
    app.processEvents()


def test_manual_arc_snapshot():
    app = QApplication.instance() or QApplication([])
    window = ManualWindow()
    window.fields['diameter'].setValue(139)
    window.fields['height'].setValue(87)
    window.fields['straight'].setValue(108)
    window.shape_mode.setCurrentIndex(1)
    assert window.snapshot().shape_mode == 'arc'
    assert window.snapshot().straight_cm == 108
    window.close()
    app.processEvents()


def test_target_history_records_both_modes_and_survives_restart(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from shape_crop.gui import main_window
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, 'WorkflowWorker', lambda request, *args, **kwargs: Mock(request=request))
    window = main_window.MainWindow()
    errors = []
    window.show_error = errors.append
    window.override.setText('unused.jpg')
    window.output_dir.setText(str(tmp_path))
    circle_name = '花幔;80x140cm'
    arc_name = '花幔;86x138cm'
    window.target.setText('  ' + circle_name + '  ')
    assert window.target_history.count() == 0
    window.start_task(True)
    assert window.worker.request.target_name == circle_name
    window.task_finished()
    window.shape_mode.setCurrentIndex(1)
    window.target.setText(arc_name)
    window.straight_value.setValue(108)
    window.sketch_path = 'sketch.png'
    window.sketch_review.setChecked(True)
    window.start_task(False)
    assert window.straight_value.value() == 108
    assert window.sketch_review.isChecked()
    window.task_finished()
    assert [window.target_history.itemText(i) for i in range(2)] == [arc_name, circle_name]
    window.shape_mode.setCurrentIndex(0)
    window.target_history.setCurrentIndex(1)
    assert window.target.text() == circle_name
    assert (window.width_value.value(), window.height_value.value()) == (140, 80)
    assert window.sketch_path == ''
    window.start_task(True)
    window.task_finished()
    assert not errors
    assert [window.target_history.itemText(i) for i in range(2)] == [circle_name, arc_name]
    window.close()
    restored = main_window.MainWindow()
    assert restored.target.text() == ''
    assert [restored.target_history.itemText(i) for i in range(2)] == [circle_name, arc_name]
    restored.target_history.setCurrentIndex(1)
    assert restored.target.text() == arc_name
    assert (restored.width_value.value(), restored.height_value.value()) == (138, 86)
    restored.close()
    app.processEvents()


def test_target_history_limit_and_clear_preserve_current_order(isolated_desktop_settings, monkeypatch):
    from unittest.mock import Mock
    from shape_crop.gui import main_window
    app = QApplication.instance() or QApplication([])
    names = [f'花型{i};80x140cm' for i in range(50)]
    isolated_desktop_settings.setValue('target_filename_history', names)
    monkeypatch.setattr(main_window, 'WorkflowWorker', lambda request, *args, **kwargs: Mock(request=request))
    window = main_window.MainWindow()
    errors = []
    window.show_error = errors.append
    window.target.setText('新花型;86x138cm')
    window.override.setText('unused.jpg')
    window.start_task(True)
    assert not errors
    window.task_finished()
    assert window.target_history.count() == 50
    assert window.target_history.itemText(0) == '新花型;86x138cm'
    assert window.target_history.findText(names[-1]) == -1
    window.shape_mode.setCurrentIndex(1)
    window.straight_value.setValue(108)
    window.sketch_path = 'sketch.png'
    window.sketch_review.setChecked(True)
    window.clear_target_history_button.click()
    assert window.target_history.count() == 0
    assert not window.clear_target_history_button.isEnabled()
    assert window.target.text() == '新花型;86x138cm'
    assert (window.width_value.value(), window.height_value.value(), window.straight_value.value()) == (138, 86, 108)
    assert window.sketch_path == 'sketch.png'
    assert window.sketch_review.isChecked()
    window.close()
    restored = main_window.MainWindow()
    assert restored.target_history.count() == 0
    restored.close()
    app.processEvents()


def test_target_history_ignores_invalid_or_abandoned_tasks(tmp_path, monkeypatch):
    from shape_crop.gui.main_window import MainWindow
    from PyQt5.QtWidgets import QMessageBox
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    errors = []
    window.show_error = errors.append
    window.target.setText('无尺寸文件名')
    window.start_task(True)
    window.target.setText('花幔;80x140cm')
    window.library.setText('')
    window.start_task(True)
    window.override.setText('unused.jpg')
    window.output_dir.setText('')
    window.start_task(False)
    assert len(errors) == 3
    window.output_dir.setText(str(tmp_path))
    (tmp_path / '花幔;80x140cm.jpg').touch()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.No)
    window.start_task(False)
    assert window.worker is None
    assert window.target_history.count() == 0
    window.close()
    app.processEvents()


@pytest.mark.skipif(os.name != 'nt', reason='Windows recursive catalog watcher')
def test_desktop_export_then_different_order_does_not_rescan(tmp_path):
    from unittest.mock import patch
    from PIL import Image
    from shape_crop.gui.main_window import MainWindow
    from shape_crop.services import catalog
    app = QApplication.instance() or QApplication([])
    for pattern in ('花甲', '花乙'):
        Image.new('RGB', (140, 80), (240, 220, 190)).save(tmp_path / (pattern + ';80x140cm.jpg'))
    window = MainWindow()
    window.target.setText('花甲;80x140cm裁剪有图')
    window.library.setText(str(tmp_path))
    window.output_dir.setText(str(tmp_path))
    window.dpi.setValue(10)
    errors = []
    window.show_error = errors.append
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    def run(preview):
        window.start_task(preview)
        window.worker.finished.connect(loop.quit)
        timer.start(10000)
        loop.exec_()
        timer.stop()
        assert window.worker is None
        assert not errors
    try:
        run(False)
        assert window.catalog_session.active
        window.target.setText('花乙;80x140cm裁剪有图')
        with patch.object(catalog.os, 'scandir', side_effect=AssertionError('换订单重新全库扫描')):
            run(True)
        assert window.preview.original is not None
        assert '花乙' in window.match_label.text()
        assert '匹配' in window.status.text() and '预览' in window.status.text()
    finally:
        window.close()
        app.processEvents()
