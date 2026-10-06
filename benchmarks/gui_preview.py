"""Render the Qt workspace offscreen for visual review."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase
from shape_crop.gui.main_window import MainWindow

app = QApplication([])
app.setStyle('Fusion')
if not QFontDatabase().families():
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
app.setFont(QFont('Microsoft YaHei UI', 9))
window = MainWindow()
window.target.setText('双面格-定制-裁剪有图-蔓生花;80X140cm裁剪有图')
window.library.setText(str(Path('examples').resolve()))
window.output_dir.setText(str(Path('outputs').resolve()))
window.show()
app.processEvents()
Path('outputs').mkdir(exist_ok=True)
window.grab().save('outputs/gui-empty.png')
sample = Path('outputs/v0.2/双面格-定制-裁剪有图-蔓生花;80X140cm裁剪有图.png')
if sample.exists():
    with Image.open(sample) as image:
        window.preview.show_image(image)
window.match_label.setText('匹配 140 × 80cm；比例差 0.00%\n素材：蔓生花;80X140CM.jpg\n自动读取完整边框带，保留原色原层次')
app.processEvents()
window.grab().save('outputs/gui-preview.png')
window.resize(1000, 720)
app.processEvents()
window.grab().save('outputs/gui-compact.png')
window.close()
