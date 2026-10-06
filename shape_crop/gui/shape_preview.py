"""Dimensioned geometry preview; never infers geometry from sketch pixels."""
import math
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPainterPath, QColor
from PyQt5.QtWidgets import QWidget


class ShapePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shape = None
        self.setMinimumHeight(160)
        self.setMaximumHeight(180)

    def set_shape(self, shape):
        self.shape = shape
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.shape is None:
            painter.drawText(self.rect(), Qt.AlignCenter, '填写尺寸后显示轮廓')
            return
        shape = self.shape
        scale = min((self.width() - 70) / shape.diameter, (self.height() - 65) / shape.height)
        cx, cy = self.width() / 2, self.height() / 2
        center = getattr(shape, 'center', 0.)
        path = QPainterPath()
        path.moveTo(cx - shape.chord / 2 * scale, cy - shape.half_height * scale)
        path.lineTo(cx + shape.chord / 2 * scale, cy - shape.half_height * scale)
        for step in range(65):
            theta = -shape.angle + 2 * shape.angle * step / 64
            path.lineTo(cx + (center + shape.radius * math.cos(theta)) * scale,
                        cy + shape.radius * math.sin(theta) * scale)
        path.lineTo(cx - shape.chord / 2 * scale, cy + shape.half_height * scale)
        for step in range(65):
            theta = shape.angle - 2 * shape.angle * step / 64
            path.lineTo(cx - (center + shape.radius * math.cos(theta)) * scale,
                        cy + shape.radius * math.sin(theta) * scale)
        path.closeSubpath()
        painter.setPen(QColor('#286c9a'))
        painter.setBrush(QColor('#e3f0f8'))
        painter.drawPath(path)
        painter.setPen(QColor('#333333'))
        painter.drawText(0, 0, self.width(), 25, Qt.AlignCenter, f'W 最大宽度 {shape.diameter:g}cm')
        painter.drawText(0, self.height() - 25, self.width(), 25, Qt.AlignCenter, f'L 直边 {shape.chord:.3f}cm')
        painter.save()
        painter.translate(15, self.height() / 2)
        painter.rotate(-90)
        painter.drawText(-70, -10, 140, 20, Qt.AlignCenter, f'H 总高 {shape.height:g}cm')
        painter.restore()
