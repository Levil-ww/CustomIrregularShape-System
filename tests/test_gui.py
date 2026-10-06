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
    assert not worker.isRunning()
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
    assert not worker.isRunning()
    assert not errors
    assert window.preview.original is not None
    assert '140 × 80cm' in window.match_label.text()
    window.close()
    app.processEvents()
