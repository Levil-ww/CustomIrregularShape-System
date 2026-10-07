"""Interactive image inspection with bounded zoom and drag panning."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QPainter, QPixmap
from PyQt5.QtWidgets import (QDialog, QGraphicsScene, QGraphicsView, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout)


class ImageView(QGraphicsView):
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.item = None
        self.auto_fit = True
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        checker = QPixmap(32, 32)
        checker.fill(QColor('#f5f7fa'))
        painter = QPainter(checker)
        painter.fillRect(0, 0, 16, 16, QColor('#eaf0f6'))
        painter.fillRect(16, 16, 16, 16, QColor('#eaf0f6'))
        painter.end()
        self.setBackgroundBrush(QBrush(checker))

    def set_image(self, pixmap):
        self.scene().clear()
        self.item = self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(self.item.boundingRect())
        self.fit_image()

    def fit_image(self):
        if self.item is not None:
            self.auto_fit = True
            self.resetTransform()
            self.fitInView(self.item, Qt.KeepAspectRatio)
            self.zoom_changed.emit(self.transform().m11())

    def set_zoom(self, zoom):
        if self.item is not None:
            self.auto_fit = False
            zoom = min(16., max(.05, zoom))
            factor = zoom / self.transform().m11()
            self.scale(factor, factor)
            self.zoom_changed.emit(zoom)

    def zoom_by(self, factor):
        self.set_zoom(self.transform().m11() * factor)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            # Limit one event's exponent; rapid/high-resolution wheels stay bounded.
            self.zoom_by(1.2 ** max(-8., min(8., delta / 120)))
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.fit_image()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.auto_fit:
            self.fit_image()


class ImagePreviewDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle('成品预览 · 放大查看')
        self.resize(1000, 720)
        self.setMinimumSize(480, 360)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.view = ImageView(self)
        self.zoom_label = QLabel()
        for label, callback in (
                ('缩小', lambda: self.view.zoom_by(1 / 1.2)),
                ('放大', lambda: self.view.zoom_by(1.2)),
                ('适应窗口', self.view.fit_image),
                ('100%', lambda: self.view.set_zoom(1.))):
            button = QPushButton(label)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addWidget(self.zoom_label)
        toolbar.addStretch()
        close = QPushButton('关闭')
        close.clicked.connect(self.close)
        toolbar.addWidget(close)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)
        layout.addWidget(QLabel('滚轮缩放 · 按住左键拖动 · 双击适应窗口 · Esc 关闭'))
        self.view.zoom_changed.connect(lambda zoom: self.zoom_label.setText(f'{zoom:.0%}'))
        self.view.set_image(pixmap)

    def set_image(self, pixmap):
        self.view.set_image(pixmap)
