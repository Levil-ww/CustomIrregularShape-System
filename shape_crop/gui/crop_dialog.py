"""Source-region selection; stored coordinates are independent of display size."""
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
from shape_crop.gui.image_utils import to_pixmap
from shape_crop.models.design import CropBox


class CropCanvas(QLabel):
    def __init__(self, image, box):
        super().__init__()
        image = image.copy()
        image.thumbnail((1050, 680))
        self.setPixmap(to_pixmap(image))
        self.setFixedSize(image.width, image.height)
        self.box = box
        self.anchor = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.anchor = event.pos()

    def mouseMoveEvent(self, event):
        if self.anchor is not None:
            rect = QRect(self.anchor, event.pos()).normalized().intersected(self.rect())
            if rect.width() > 1 and rect.height() > 1:
                self.box = CropBox(rect.left() / self.width(), rect.top() / self.height(),
                                   (rect.right() + 1) / self.width(), (rect.bottom() + 1) / self.height())
                self.update()

    def mouseReleaseEvent(self, event):
        self.mouseMoveEvent(event)
        self.anchor = None

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor('#27b574'), 2))
        painter.drawRect(QRect(round(self.box.left * self.width()), round(self.box.top * self.height()),
                               round((self.box.right - self.box.left) * self.width()),
                               round((self.box.bottom - self.box.top) * self.height())))


class CropDialog(QDialog):
    def __init__(self, image, box, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('拖动鼠标框选区域。花边请选择上边的一段水平装饰带，避开矩形转角。'))
        self.canvas = CropCanvas(image, box)
        layout.addWidget(self.canvas)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
