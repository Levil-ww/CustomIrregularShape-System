"""Filename-driven automatic workflow; optional settings are collapsed."""
from pathlib import Path
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QMessageBox, QProgressBar, QCheckBox)
from shape_crop.gui.manual_window import PreviewCanvas, ManualWindow
from shape_crop.models.request import ProductRequest
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.workflow import output_path
from shape_crop.workers.render_worker import WorkflowWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('圆桌素材设计器 · 自动排版 0.2.0')
        self.resize(1280, 850)
        self.worker = None
        self.close_pending = False
        self.manual_window = None
        self.settings = QSettings('ShapeCrop', 'CircularDesigner')
        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        panel = QWidget()
        panel.setFixedWidth(390)
        left = QVBoxLayout(panel)
        main.addWidget(panel)
        self.preview = PreviewCanvas()
        main.addWidget(self.preview, 1)
        self.controls = QWidget()
        controls = QVBoxLayout(self.controls)
        controls.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self.controls)
        intro = QLabel('输入目标名称，自动匹配矩形素材\n原素材边框、色带和花纹一起生成')
        intro.setStyleSheet('font-size: 15px; font-weight: bold; padding: 8px 0;')
        controls.addWidget(intro)
        controls.addWidget(QLabel('目标文件名'))
        self.target = QLineEdit()
        self.target.setPlaceholderText('双面格-定制-裁剪有图-花幔;80X140cm裁剪有图')
        controls.addWidget(self.target)
        self.target.textChanged.connect(self.update_dimensions)
        self.dimension_label = QLabel()
        self.dimension_label.setWordWrap(True)
        controls.addWidget(self.dimension_label)
        self.library = self.directory_row(controls, '矩形 JPG 素材图库', 'library_dir')
        self.output_dir = self.directory_row(controls, '输出目录', 'output_dir')
        format_row = QFormLayout()
        self.format = QComboBox()
        self.format.addItems(['JPG（白底）', 'PNG（透明）'])
        format_row.addRow('输出格式', self.format)
        controls.addLayout(format_row)
        self.output_label = QLabel('输出名称与目标名称一致')
        self.output_label.setWordWrap(True)
        controls.addWidget(self.output_label)
        self.format.currentIndexChanged.connect(self.update_dimensions)
        self.advanced_toggle = QCheckBox('高级选项（通常无需调整）')
        controls.addWidget(self.advanced_toggle)
        self.advanced = QGroupBox('可选设置')
        form = QFormLayout(self.advanced)
        self.allowance = QDoubleSpinBox()
        self.allowance.setRange(0, 10)
        self.allowance.setDecimals(2)
        self.allowance.setValue(1)
        self.allowance.valueChanged.connect(self.update_dimensions)
        form.addRow('总尺寸补偿 cm', self.allowance)
        self.dpi = QSpinBox()
        self.dpi.setRange(1, 1200)
        self.dpi.setValue(150)
        form.addRow('导出 DPI', self.dpi)
        self.inner = QDoubleSpinBox()
        self.inner.setRange(0, 1000)
        form.addRow('同心内圆直径（0 关闭）', self.inner)
        self.override = QLineEdit()
        self.override.setPlaceholderText('空白时自动匹配图库')
        pick = QPushButton('指定素材')
        pick.clicked.connect(self.choose_override)
        override_row = QHBoxLayout()
        override_row.addWidget(self.override)
        override_row.addWidget(pick)
        form.addRow(override_row)
        manual = QPushButton('打开手工排版工具')
        manual.clicked.connect(self.open_manual)
        form.addRow(manual)
        controls.addWidget(self.advanced)
        self.advanced.hide()
        self.advanced_toggle.toggled.connect(self.advanced.setVisible)
        actions = QHBoxLayout()
        self.preview_button = QPushButton('自动匹配并预览')
        self.preview_button.clicked.connect(lambda: self.start_task(True))
        self.export_button = QPushButton('生成成品')
        self.export_button.clicked.connect(lambda: self.start_task(False))
        actions.addWidget(self.preview_button)
        actions.addWidget(self.export_button)
        controls.addLayout(actions)
        self.match_label = QLabel('尚未匹配素材')
        self.match_label.setWordWrap(True)
        left.addWidget(self.match_label)
        self.progress = QProgressBar()
        left.addWidget(self.progress)
        self.status = QLabel('就绪')
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.cancel = QPushButton('取消当前任务')
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_task)
        left.addWidget(self.cancel)
        left.addStretch()
        self.update_dimensions()

    def directory_row(self, layout, title, key):
        layout.addWidget(QLabel(title))
        line = QLineEdit(str(self.settings.value(key, '')))
        row = QHBoxLayout()
        row.addWidget(line)
        button = QPushButton('选择')
        def pick():
            directory = QFileDialog.getExistingDirectory(self, title, line.text())
            if directory:
                line.setText(directory)
        button.clicked.connect(pick)
        row.addWidget(button)
        layout.addLayout(row)
        return line

    def snapshot(self):
        request = ProductRequest(self.target.text().strip(), self.library.text().strip(),
                                 self.override.text().strip(), self.allowance.value(),
                                 self.dpi.value(), self.inner.value())
        parse_filename(request.target_name)
        return request

    def update_dimensions(self):
        if not hasattr(self, 'allowance'):
            return
        try:
            parsed = parse_filename(self.target.text())
            self.dimension_label.setText(f'花型：{parsed.pattern}\n实际直径 {parsed.width_cm + self.allowance.value():g}cm · 总高 {parsed.height_cm + self.allowance.value():g}cm')
            self.output_label.setText('输出：' + parsed.stem + ('.jpg' if self.format.currentIndex() == 0 else '.png'))
        except ValueError as error:
            self.dimension_label.setText(str(error) if self.target.text() else '默认总尺寸补偿 +1cm：80×140 → 直径141cm，总高81cm。')
            self.output_label.setText('输出名称与目标名称一致')

    def choose_override(self):
        path, _ = QFileDialog.getOpenFileName(self, '指定矩形素材', '', 'JPG 素材 (*.jpg *.jpeg);;图片 (*.png)')
        if path:
            self.override.setText(path)

    def open_manual(self):
        if self.manual_window is None:
            self.manual_window = ManualWindow()
        self.manual_window.show()
        self.manual_window.raise_()

    def start_task(self, preview):
        if self.worker:
            return
        try:
            request = self.snapshot()
            if not request.material_override and not request.library_dir:
                raise ValueError('请先选择矩形 JPG 素材图库')
            output = None
            if not preview:
                folder = Path(self.output_dir.text().strip())
                if not self.output_dir.text().strip() or not folder.is_dir():
                    raise ValueError('请选择存在的输出目录')
                output = output_path(request, folder, '.jpg' if self.format.currentIndex() == 0 else '.png')
                if Path(output).exists() and QMessageBox.question(self, '覆盖成品', '同名成品已存在，是否覆盖？') != QMessageBox.Yes:
                    return
            self.settings.setValue('library_dir', request.library_dir)
            self.settings.setValue('output_dir', self.output_dir.text())
            self.controls.setEnabled(False)
            self.cancel.setEnabled(True)
            self.progress.setValue(0)
            self.worker = WorkflowWorker(request, preview, output, self)
            self.worker.status.connect(self.status.setText)
            self.worker.progress.connect(self.progress.setValue)
            self.worker.result.connect(self.task_result)
            self.worker.error.connect(self.show_error)
            self.worker.cancelled.connect(lambda: self.status.setText('已取消'))
            self.worker.finished.connect(self.task_finished)
            self.worker.start()
        except Exception as error:
            self.show_error(str(error))

    def task_result(self, result):
        self.match_label.setText(result['match_info'])
        if result['image'] is not None:
            self.preview.show_image(result['image'])
            self.status.setText('自动预览已生成，采用原素材完整边框带')
        else:
            self.status.setText('成品已保存：' + result['output'])

    def task_finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.controls.setEnabled(True)
        self.cancel.setEnabled(False)
        if self.close_pending:
            self.close()

    def cancel_task(self):
        if self.worker:
            self.worker.requestInterruption()
            self.status.setText('正在取消…')

    def show_error(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, '无法生成', message)

    def closeEvent(self, event):
        if self.worker:
            self.close_pending = True
            self.cancel_task()
            event.ignore()
        else:
            if self.manual_window:
                self.manual_window.close()
            event.accept()
