
"""Filename-driven automatic workflow; optional settings are collapsed."""
from pathlib import Path
from shape_crop import __version__
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QMessageBox, QProgressBar, QCheckBox, QScrollArea, QTabWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from shape_crop.core.geometry import CircularBand, ArcBand
from shape_crop.gui.shape_preview import ShapePreview
from shape_crop.workers.sketch_worker import SketchWorker
from shape_crop.gui.manual_window import PreviewCanvas, ManualWindow
from shape_crop.models.request import ProductRequest
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.workflow import output_path
from shape_crop.workers.render_worker import WorkflowWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'圆桌 / 弧形台素材设计器 · 自动排版 {__version__}')
        self.resize(1280, 850)
        self.worker = None
        self.sketch_worker = None
        self.sketch_path = ''
        self.close_pending = False
        self.manual_window = None
        self.settings = QSettings('ShapeCrop', 'CircularDesigner')
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        root = QWidget()
        tabs.addTab(root, '裁剪 · 圆桌 / 弧形台')
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.controls)
        left.addWidget(scroll, 1)
        intro = QLabel('输入目标名称，自动匹配矩形素材\n原素材边框、色带和花纹一起生成')
        intro.setStyleSheet('font-size: 15px; font-weight: bold; padding: 8px 0;')
        controls.addWidget(intro)
        self.shape_mode = QComboBox()
        self.shape_mode.addItem('圆桌（直径 + 总高）', 'circular')
        self.shape_mode.addItem('弧形台（最大宽度 + 总高 + 直边）', 'arc')
        controls.addWidget(self.shape_mode)
        controls.addWidget(QLabel('目标文件名'))
        self.target = QLineEdit()
        self.target.setPlaceholderText('双面格-定制-裁剪有图-花幔;80X140cm裁剪有图')
        controls.addWidget(self.target)
        self.target.textChanged.connect(self.target_changed)
        dimension_form = QFormLayout()
        self.width_value = QDoubleSpinBox()
        self.height_value = QDoubleSpinBox()
        self.straight_value = QDoubleSpinBox()
        for field in (self.width_value, self.height_value, self.straight_value):
            field.setRange(0, 1000)
            field.setDecimals(3)
            field.setSpecialValueText('待填写')
            field.valueChanged.connect(self.update_dimensions)
        dimension_form.addRow('W 最大宽度 cm', self.width_value)
        dimension_form.addRow('H 总高 cm', self.height_value)
        dimension_form.addRow('L 直边 cm（不补偿）', self.straight_value)
        self.straight_value.setEnabled(False)
        controls.addLayout(dimension_form)
        self.shape_mode.currentIndexChanged.connect(self.mode_changed)
        upload = QPushButton('上传草图并识别尺寸')
        upload.clicked.connect(self.choose_sketch)
        controls.addWidget(upload)
        self.sketch_image = QLabel()
        self.sketch_image.setAlignment(Qt.AlignCenter)
        self.sketch_image.hide()
        controls.addWidget(self.sketch_image)
        self.sketch_report = QLabel('尺寸来自目标文件名，可手工修改。弧形台采用对称圆弧模型。')
        self.sketch_report.setWordWrap(True)
        controls.addWidget(self.sketch_report)
        self.sketch_review = QCheckBox('已对照草图核对模块及尺寸')
        self.sketch_review.hide()
        controls.addWidget(self.sketch_review)
        for field in (self.width_value, self.height_value, self.straight_value):
            field.valueChanged.connect(lambda: self.sketch_review.setChecked(False))
        self.outline = ShapePreview()
        controls.addWidget(self.outline)
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
        left.addLayout(actions)
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
                                 self.dpi.value(), self.inner.value(), self.shape_mode.currentData(),
                                 self.straight_value.value(), self.width_value.value(), self.height_value.value())
        parse_filename(request.target_name)
        if self.sketch_path and not self.sketch_review.isChecked():
            raise ValueError('请先对照草图核对模块和尺寸，再勾选确认')
        self.current_shape()
        return request

    def current_shape(self):
        w = self.width_value.value() + self.allowance.value()
        h = self.height_value.value() + self.allowance.value()
        if min(self.width_value.value(), self.height_value.value()) <= 0:
            raise ValueError('请填写最大宽度和总高')
        if self.shape_mode.currentData() == 'arc':
            ArcBand(self.width_value.value(), self.height_value.value(), self.straight_value.value())
            return ArcBand(w, h, self.straight_value.value())
        return CircularBand(w, h)

    def target_changed(self):
        if not hasattr(self, 'allowance'):
            return
        self.sketch_path = ''
        self.sketch_image.hide()
        self.sketch_review.hide()
        self.sketch_review.setChecked(False)
        self.straight_value.setValue(0)
        try:
            parsed = parse_filename(self.target.text())
            self.width_value.setValue(parsed.width_cm)
            self.height_value.setValue(parsed.height_cm)
        except ValueError:
            self.width_value.setValue(0)
            self.height_value.setValue(0)
        self.sketch_report.setText('尺寸来自目标文件名，可手工修改。弧形台采用对称圆弧模型。')
        self.update_dimensions()

    def mode_changed(self):
        self.straight_value.setEnabled(self.shape_mode.currentData() == 'arc')
        if self.sketch_path:
            self.sketch_review.setChecked(False)
        self.update_dimensions()

    def choose_sketch(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择尺寸草图', '', '草图 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)')
        if path:
            self.start_sketch(path)

    def start_sketch(self, path):
        if self.worker or self.sketch_worker:
            return
        try:
            parsed = parse_filename(self.target.text())
            self.width_value.setValue(parsed.width_cm)
            self.height_value.setValue(parsed.height_cm)
        except ValueError:
            self.width_value.setValue(0)
            self.height_value.setValue(0)
        self.sketch_path = path
        self.sketch_review.setChecked(False)
        self.sketch_review.show()
        self.straight_value.setValue(0)
        pixmap = QPixmap(path)
        self.sketch_image.setPixmap(pixmap.scaled(320, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.sketch_image.show()
        self.controls.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.cancel.setEnabled(True)
        self.status.setText('正在使用本地 Windows OCR 识别草图…')
        self.sketch_worker = SketchWorker(path, self)
        self.sketch_worker.result.connect(self.sketch_result)
        self.sketch_worker.error.connect(self.sketch_error)
        self.sketch_worker.cancelled.connect(lambda: self.status.setText('识别已取消，请手工填写'))
        self.sketch_worker.finished.connect(self.sketch_finished)
        self.sketch_worker.start()

    def sketch_result(self, result):
        if result.width_cm is not None:
            self.width_value.setValue(result.width_cm)
        if result.height_cm is not None:
            self.height_value.setValue(result.height_cm)
        if result.straight_cm is not None:
            self.shape_mode.setCurrentIndex(1)
            self.straight_value.setValue(result.straight_cm)
        else:
            self.straight_value.setValue(0)
        self.sketch_report.setText(result.report)
        self.status.setText('识别结束，请对照草图核对尺寸；宽高补偿，直边不补偿。')
        self.update_dimensions()

    def sketch_error(self, message):
        self.sketch_report.setText(message)
        self.status.setText('自动识别失败，可参照草图手工填写尺寸')

    def sketch_finished(self):
        worker, self.sketch_worker = self.sketch_worker, None
        worker.deleteLater()
        self.controls.setEnabled(True)
        self.preview_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.cancel.setEnabled(False)
        if self.close_pending:
            self.close()

    def update_dimensions(self):
        if not hasattr(self, 'allowance'):
            return
        try:
            parsed = parse_filename(self.target.text())
            shape = self.current_shape()
            title = '最大宽度' if self.shape_mode.currentData() == 'arc' else '直径'
            conflict = ''
            if (abs(self.width_value.value() - parsed.width_cm) > .001 or
                    abs(self.height_value.value() - parsed.height_cm) > .001):
                conflict = '\n注意：当前尺寸与文件名不同，按当前填写尺寸生成，输出名称保持原名。'
            self.dimension_label.setText(f'花型：{parsed.pattern}\n实际{title} {shape.diameter:g}cm · 总高 {shape.height:g}cm\n直边 {shape.chord:.3f}cm' + conflict)
            self.outline.set_shape(shape)
            self.output_label.setText('输出：' + parsed.stem + ('.jpg' if self.format.currentIndex() == 0 else '.png'))
        except ValueError as error:
            self.outline.set_shape(None)
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
        if self.worker or self.sketch_worker:
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
            self.preview_button.setEnabled(False)
            self.export_button.setEnabled(False)
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
        self.preview_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.cancel.setEnabled(False)
        if self.close_pending:
            self.close()

    def cancel_task(self):
        if self.sketch_worker:
            self.sketch_worker.requestInterruption()
            self.status.setText('正在取消识别…')
        if self.worker:
            self.worker.requestInterruption()
            self.status.setText('正在取消…')

    def show_error(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, '无法生成', message)

    def closeEvent(self, event):
        if self.worker or self.sketch_worker:
            self.close_pending = True
            self.cancel_task()
            event.ignore()
        else:
            if self.manual_window:
                self.manual_window.close()
            event.accept()
