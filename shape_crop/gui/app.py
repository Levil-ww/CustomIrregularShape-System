import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase, QIcon
from shape_crop.gui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    if 'Microsoft YaHei UI' in QFontDatabase().families():
        app.setFont(QFont('Microsoft YaHei UI', 9))
    icon_path = Path(__file__).parent.parent.parent / 'outputs' / 'icon' / 'CustomIrregularShape-256.png'
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec_()
