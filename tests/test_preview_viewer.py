"""Exercise preview inspection through real Qt mouse and wheel events."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PIL import Image
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt5.QtGui import QMouseEvent, QWheelEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QPushButton

from shape_crop.gui.manual_window import PreviewCanvas


@pytest.fixture
def preview():
    app = QApplication.instance() or QApplication([])
    canvas = PreviewCanvas()
    canvas.resize(600, 400)
    canvas.show()
    app.processEvents()
    yield canvas
    canvas.close()
    canvas.deleteLater()
    app.processEvents()


def button(dialog, text):
    return next(item for item in dialog.findChildren(QPushButton) if item.text() == text)


def wheel(view, delta):
    point = view.viewport().rect().center()
    event = QWheelEvent(QPointF(point), QPointF(view.viewport().mapToGlobal(point)),
                        QPoint(), QPoint(0, delta), Qt.NoButton, Qt.NoModifier,
                        Qt.NoScrollPhase, False)
    QApplication.sendEvent(view.viewport(), event)


def test_preview_click_zoom_pan_and_fit(preview):
    QTest.mouseClick(preview, Qt.LeftButton)
    assert preview.viewer is None
    preview.show_image(Image.new('RGBA', (2000, 1000), (200, 180, 160, 128)))
    QTest.mouseClick(preview, Qt.LeftButton)
    QApplication.processEvents()
    dialog = preview.viewer
    assert dialog.isVisible()
    assert dialog.view.item.pixmap().size() == preview.original.size()
    assert dialog.view.transform().m11() < 1
    QTest.mouseClick(button(dialog, '100%'), Qt.LeftButton)
    assert dialog.zoom_label.text() == '100%'
    dialog.resize(1100, 760)
    QApplication.processEvents()
    assert dialog.view.transform().m11() == pytest.approx(1)
    wheel(dialog.view, 120)
    assert dialog.view.transform().m11() == pytest.approx(1.2)
    wheel(dialog.view, -120)
    assert dialog.view.transform().m11() == pytest.approx(1)
    QTest.mouseClick(button(dialog, '放大'), Qt.LeftButton)
    assert dialog.view.transform().m11() == pytest.approx(1.2)
    QTest.mouseClick(button(dialog, '缩小'), Qt.LeftButton)
    assert dialog.view.transform().m11() == pytest.approx(1)
    viewport = dialog.view.viewport()
    point = viewport.rect().center()
    before = dialog.view.horizontalScrollBar().value()
    QTest.mousePress(viewport, Qt.LeftButton, pos=point)
    moved = point - QPoint(80, 0)
    event = QMouseEvent(QEvent.MouseMove, QPointF(moved), Qt.NoButton,
                        Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(viewport, event)
    QTest.mouseRelease(viewport, Qt.LeftButton, pos=moved)
    assert dialog.view.horizontalScrollBar().value() > before
    QTest.mouseDClick(viewport, Qt.LeftButton)
    assert dialog.view.auto_fit
    assert dialog.view.transform().m11() < 1
    QTest.mouseClick(button(dialog, '100%'), Qt.LeftButton)
    QTest.mouseClick(button(dialog, '适应窗口'), Qt.LeftButton)
    assert dialog.view.auto_fit
    QTest.mouseClick(button(dialog, '关闭'), Qt.LeftButton)
    assert not dialog.isVisible()
    QTest.mouseClick(preview, Qt.LeftButton)
    assert preview.viewer is dialog
    assert dialog.isVisible()
    QTest.keyClick(dialog, Qt.Key_Escape)
    assert not dialog.isVisible()


def test_zoom_limits_and_replacing_preview(preview):
    preview.show_image(Image.new('RGB', (1200, 600)))
    QTest.keyClick(preview, Qt.Key_Return)
    QApplication.processEvents()
    dialog = preview.viewer
    for _ in range(10):
        wheel(dialog.view, 960)
    assert dialog.view.transform().m11() == pytest.approx(16)
    for _ in range(10):
        wheel(dialog.view, -960)
    assert dialog.view.transform().m11() == pytest.approx(.05)
    preview.show_image(Image.new('RGB', (900, 900), 'red'))
    assert dialog.view.item.pixmap().width() == 900
    assert dialog.view.item.pixmap().height() == 900
    assert dialog.view.auto_fit
    assert dialog.view.scene().items() == [dialog.view.item]
    preview.hide()
    QApplication.processEvents()
    assert not dialog.isVisible()
