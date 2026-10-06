import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase
from shape_crop.gui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    if 'Microsoft YaHei UI' in QFontDatabase().families():
        app.setFont(QFont('Microsoft YaHei UI', 9))
    window = MainWindow()
    window.show()
    return app.exec_()
