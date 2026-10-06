import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEventLoop, QTimer
from shape_crop.gui.manual_window import ManualWindow


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
