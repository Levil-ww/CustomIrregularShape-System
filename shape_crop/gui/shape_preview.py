"""Dimensioned geometry preview; never infers geometry from sketch pixels."""
import math
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPainterPath, QColor
from PyQt5.QtWidgets import QWidget
from shape_crop.core.belly_geometry import BellyOutline


class ShapePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shape = None
        self.belly_mode = False
        self.setMinimumHeight(160)
        self.setMaximumHeight(180)

    def set_shape(self, shape):
        self.shape = shape
        self.update()

    def set_belly_mode(self, enabled):
        self.belly_mode = enabled
        self.update()

    def paint_belly(self, painter):
        shape = self.shape if isinstance(self.shape, BellyOutline) else BellyOutline(140, 80, 63, 120, 15)
        scale = min((self.width() - 80) / shape.width, (self.height() - 75) / shape.height)
        cx, cy = self.width() / 2, (self.height() - 10) / 2
        path = QPainterPath()
        points = shape.points()
        path.moveTo(cx + points[0][0] * scale, cy + points[0][1] * scale)
        for x, y in points[1:]:
            path.lineTo(cx + x * scale, cy + y * scale)
        path.closeSubpath()
        painter.setPen(QColor('#286c9a'))
        painter.setBrush(QColor('#e3f0f8'))
        painter.drawPath(path)
        painter.setPen(QColor('#b52b2b'))
        left, right = cx - shape.width * scale / 2, cx + shape.width * scale / 2
        top, bottom = cy - shape.height * scale / 2, cy + shape.height * scale / 2
        # Lines indicate the measured span; endpoint bars identify its endpoints.
        def horizontal(x1, x2, y):
            painter.drawLine(int(x1), int(y), int(x2), int(y))
            for x in (x1, x2):
                painter.drawLine(int(x), int(y - 3), int(x), int(y + 3))
        def vertical(x, y1, y2):
            painter.drawLine(int(x), int(y1), int(x), int(y2))
            for y in (y1, y2):
                painter.drawLine(int(x - 3), int(y), int(x + 3), int(y))
        horizontal(left, right, cy)
        vertical(cx, top, bottom)
        corner_y = cy + (shape.side_span + shape.corner_diameter) * scale / 2
        horizontal(cx - shape.horizontal_span * scale / 2, cx + shape.horizontal_span * scale / 2, corner_y)
        corner_x = cx + (shape.horizontal_span + shape.corner_diameter) * scale / 2
        vertical(corner_x, cy - shape.side_span * scale / 2, cy + shape.side_span * scale / 2)
        painter.drawText(int(cx + 3), int(top + 13), 'A')
        painter.drawText(int(cx + 7), int(cy - 4), 'B')
        painter.drawText(int(corner_x + 4), int(cy - 5), 'C')
        painter.drawText(int(cx - 15), int(corner_y - 4), 'D')
        painter.setPen(QColor('#333333'))
        painter.drawText(0, self.height() - 25, self.width(), 20, Qt.AlignCenter,
                         f'圆角直径 {shape.corner_diameter:g} cm' if isinstance(self.shape, BellyOutline)
                         else '示意图：圆角直径需填写')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.belly_mode:
            self.paint_belly(painter)
            return
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
        painter.drawText(0, self.height() - 25, self.width(), 25, Qt.AlignCenter, f'L 直边 {shape.chord:.2f}cm')
        painter.save()
        painter.translate(15, self.height() / 2)
        painter.rotate(-90)
        painter.drawText(-70, -10, 140, 20, Qt.AlignCenter, f'H 总高 {shape.height:g}cm')
        painter.restore()
