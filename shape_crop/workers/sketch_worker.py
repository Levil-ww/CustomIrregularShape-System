"""Background adapter for local sketch recognition."""
from PyQt5.QtCore import QThread, pyqtSignal
from shape_crop.core.renderer import RenderCancelled
from shape_crop.services.sketch_recognition import recognize_sketch


class SketchWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        try:
            result = recognize_sketch(self.path, self.isInterruptionRequested)
            if self.isInterruptionRequested():
                raise RenderCancelled('识别已取消')
            self.result.emit(result)
        except RenderCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.error.emit(str(error))
