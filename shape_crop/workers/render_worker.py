"""Qt adapter for the application service. Does not import gui."""
from PyQt5.QtCore import QThread, pyqtSignal
from shape_crop.services.design_service import generate
from shape_crop.core.renderer import RenderCancelled


class RenderWorker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, design, preview=True, output=None, parent=None):
        super().__init__(parent)
        self.design, self.preview, self.output = design, preview, output

    def run(self):
        try:
            image = generate(self.design, self.preview, self.output,
                             self.progress.emit, self.isInterruptionRequested)
            self.result.emit(image if self.preview else None)
        except RenderCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.error.emit(str(error))


class WorkflowWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, request, preview=True, output=None, parent=None):
        super().__init__(parent)
        self.request, self.preview, self.output = request, preview, output

    def run(self):
        from shape_crop.services.workflow import resolve_request
        try:
            self.status.emit('正在匹配同花型、比例相近的矩形 JPG…')
            design, match_info = resolve_request(self.request, self.isInterruptionRequested, self.status.emit)
            self.status.emit('读取原素材边框层次与花纹…')
            reports = []
            image = generate(design, self.preview, self.output, self.progress.emit, self.isInterruptionRequested, reports.append)
            self.result.emit(dict(image=image if self.preview else None, design=design,
                                  match_info=match_info + '\n' + '\n'.join(reports), output=self.output))
        except RenderCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.error.emit(str(error))
