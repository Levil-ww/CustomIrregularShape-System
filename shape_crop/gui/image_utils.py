from PyQt5.QtGui import QImage, QPixmap


def to_pixmap(image):
    rgba = image.convert('RGBA')
    data = rgba.tobytes()
    qt_image = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(qt_image)
