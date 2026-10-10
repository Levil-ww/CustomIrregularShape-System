
"""Filename-driven automatic workflow; optional settings are collapsed."""
from pathlib import Path
from shape_crop import __version__
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QMessageBox, QProgressBar, QCheckBox, QScrollArea, QSplitter, QTabWidget,
    QCompleter)
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
from shape_crop.gui.theme import apply_theme
from shape_crop.services.catalog_session import CatalogSession


TARGET_HISTORY_LIMIT = 15


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'异形智裁 · {__version__}')
        self.resize(1280, 850)
        self.setMinimumSize(1000, 720)
        apply_theme(self)
        self.worker = None
        self.catalog_session = None
        self.sketch_worker = None
        self.sketch_path = ''
        self.close_pending = False
        self.manual_window = None
        self.settings = QSettings('ShapeCrop', 'CircularDesigner')
        root = QWidget()
        root.setObjectName('workspace')
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(24, 18, 24, 18)
        page.setSpacing(16)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel('异形智裁工作台')
        title.setObjectName('title')
        subtitle = QLabel('多模块素材裁剪  ·  本地处理，保留原图花纹与边框')
        subtitle.setObjectName('subtitle')
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        badge = QLabel('本地处理  ·  ' + __version__)
        badge.setObjectName('badge')
        header.addWidget(badge)
        page.addLayout(header)
        self.module_tabs = QTabWidget()
        page.addWidget(self.module_tabs, 1)
        self.table_module = QWidget()
        table_layout = QVBoxLayout(self.table_module)
        table_layout.setContentsMargins(0, 12, 0, 0)
        self.module_tabs.addTab(self.table_module, '圆桌 / 弧形台')
        self.circle_module = QWidget()
        circle_layout = QVBoxLayout(self.circle_module)
        circle_layout.setContentsMargins(24, 24, 24, 24)
        circle_layout.addStretch()
        circle_title = QLabel('正圆 / 同心圆裁剪')
        circle_title.setObjectName('sectionTitle')
        circle_title.setAlignment(Qt.AlignCenter)
        circle_layout.addWidget(circle_title)
        circle_hint = QLabel('模块待开发\n\n此处预留正圆与同心圆裁剪入口。\n圆桌与弧形台排版请切换至「圆桌 / 弧形台」标签。')
        circle_hint.setObjectName('hint')
        circle_hint.setAlignment(Qt.AlignCenter)
        circle_hint.setWordWrap(True)
        circle_layout.addWidget(circle_hint)
        circle_layout.addStretch()
        self.module_tabs.addTab(self.circle_module, '正圆 / 同心圆（待开发）')
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        table_layout.addWidget(splitter, 1)
        panel = QWidget()
        panel.setObjectName('sidebar')
        panel.setMinimumWidth(390)
        panel.setMaximumWidth(510)
        left = QVBoxLayout(panel)
        left.setContentsMargins(16, 12, 16, 16)
        left.setSpacing(10)
        splitter.addWidget(panel)
        preview_card = QWidget()
        preview_card.setObjectName('previewCard')
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(20, 12, 20, 16)
        preview_heading = QHBoxLayout()
        preview_title = QLabel('成品预览')
        preview_title.setObjectName('sectionTitle')
        preview_heading.addWidget(preview_title)
        preview_heading.addStretch()
        preview_hint = QLabel('点击图片放大查看 · 预览最长边 1200px')
        self.preview_hint = preview_hint
        preview_hint.setObjectName('hint')
        preview_heading.addWidget(preview_hint)
        preview_layout.addLayout(preview_heading)
        self.preview = PreviewCanvas()
        self.preview.setText('等待生成预览\n\n输入目标文件名，选择图库\n点击「匹配并预览」查看裁剪效果')
        preview_layout.addWidget(self.preview, 1)
        details = QHBoxLayout()
        geometry_card = QGroupBox('尺寸与轮廓')
        geometry_layout = QVBoxLayout(geometry_card)
        self.outline = ShapePreview()
        geometry_layout.addWidget(self.outline)
        geometry_card.setFixedWidth(270)
        details.addWidget(geometry_card)
        info_card = QGroupBox('当前订单')
        info_layout = QVBoxLayout(info_card)
        self.dimension_label = QLabel()
        self.dimension_label.setWordWrap(True)
        info_layout.addWidget(self.dimension_label)
        self.match_label = QLabel('尚未匹配素材\n生成预览后显示匹配来源与边框识别结果')
        self.match_label.setObjectName('hint')
        self.match_label.setWordWrap(True)
        self.match_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.match_label.setMaximumHeight(115)
        self.match_label.setToolTip('可选中复制素材路径；完整结果显示在悬浮提示中')
        info_layout.addWidget(self.match_label)
        info_layout.addStretch()
        details.addWidget(info_card, 1)
        preview_layout.addLayout(details)
        splitter.addWidget(preview_card)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 810])
        self.controls = QWidget()
        self.controls.setObjectName('controls')
        controls = QVBoxLayout(self.controls)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.controls)
        left.addWidget(scroll, 1)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        intro = QLabel('01  订单与尺寸')
        intro.setObjectName('sectionTitle')
        controls.addWidget(intro)
        self.shape_mode = QComboBox()
        self.shape_mode.addItem('圆桌（直径 + 总高）', 'circular')
        self.shape_mode.addItem('弧形台（最大宽度 + 总高 + 直边）', 'arc')
        controls.addWidget(self.shape_mode)
        controls.addWidget(QLabel('目标文件名'))
        self.target_history = QComboBox()
        self.target_history.setEditable(True)
        self.target_history.setInsertPolicy(QComboBox.NoInsert)
        self.target_history.setMinimumWidth(0)
        self.target_history.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.target_history.setMaxVisibleItems(TARGET_HISTORY_LIMIT)
        saved_history = self.settings.value('target_filename_history', [], type=list)
        self.target_history.addItems(saved_history[:TARGET_HISTORY_LIMIT])
        if len(saved_history) > TARGET_HISTORY_LIMIT:
            self.settings.setValue('target_filename_history', saved_history[:TARGET_HISTORY_LIMIT])
            self.settings.sync()
        self.target_history.setCurrentIndex(-1)
        self.target_history.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.target = self.target_history.lineEdit()
        self.target.setPlaceholderText('双面格-定制-裁剪有图-花幔;80X140cm裁剪有图')
        self.target_history.setToolTip('输入新文件名或下拉查看历史记录；启动预览或生成成品时保存，最多保留最近 15 条')
        target_row = QHBoxLayout()
        target_row.addWidget(self.target_history, 1)
        self.clear_target_history_button = QPushButton('清空历史')
        self.clear_target_history_button.setEnabled(self.target_history.count() > 0)
        self.clear_target_history_button.clicked.connect(self.clear_target_history)
        target_row.addWidget(self.clear_target_history_button)
        controls.addLayout(target_row)
        self.target.textChanged.connect(self.target_changed)
        dimension_form = QFormLayout()
        self.width_value = QDoubleSpinBox()
        self.height_value = QDoubleSpinBox()
        self.straight_value = QDoubleSpinBox()
        for field in (self.width_value, self.height_value, self.straight_value):
            field.setRange(0, 1000)
            field.setDecimals(2)
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
        files_title = QLabel('02  素材与输出')
        files_title.setObjectName('sectionTitle')
        controls.addWidget(files_title)
        self.library = self.directory_row(controls, '矩形 JPG 素材图库', 'library_dir')
        self.library.textChanged.connect(self.library_changed)
        refresh_library = QPushButton('刷新图库索引')
        refresh_library.setToolTip('图库断开重连或怀疑索引未同步时，重新核对目录；正常换单无需刷新')
        refresh_library.clicked.connect(self.refresh_library)
        controls.addWidget(refresh_library)
        self.output_dir = self.directory_row(controls, '输出目录', 'output_dir')
        format_row = QFormLayout()
        self.format = QComboBox()
        self.format.addItems(['JPG（白底）', 'PNG（透明）'])
        format_row.addRow('输出格式', self.format)
        controls.addLayout(format_row)
        self.output_label = QLabel('输出名称与目标名称一致')
        self.output_label.setObjectName('hint')
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
        controls.addStretch()
        self.preview_button = QPushButton('匹配并预览')
        self.target.returnPressed.connect(lambda: self.start_task(True))
        self.preview_button.setToolTip('匹配图库并生成预览（文件名输入框中按 Enter）')
        self.preview_button.clicked.connect(lambda: self.start_task(True))
        self.export_button = QPushButton('生成成品')
        self.export_button.setObjectName('primary')
        self.export_button.clicked.connect(lambda: self.start_task(False))
        actions.addWidget(self.preview_button)
        actions.addWidget(self.export_button)
        left.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        left.addWidget(self.progress)
        self.status = QLabel('就绪')
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.cancel = QPushButton('取消当前任务')
        self.cancel.setObjectName('cancel')
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_task)
        left.addWidget(self.cancel)
        self.update_dimensions()

    def set_target_history(self, names):
        current_text = self.target.text()
        combo_blocked = self.target_history.blockSignals(True)
        line_blocked = self.target.blockSignals(True)
        try:
            self.target_history.clear()
            self.target_history.addItems(names)
            self.target_history.setCurrentIndex(-1)
            self.target.setText(current_text)
        finally:
            self.target.blockSignals(line_blocked)
            self.target_history.blockSignals(combo_blocked)
        self.clear_target_history_button.setEnabled(bool(names))
        self.settings.setValue('target_filename_history', names)
        self.settings.sync()

    def remember_target(self, name):
        names = [self.target_history.itemText(index)
                 for index in range(self.target_history.count())
                 if self.target_history.itemText(index) != name]
        self.set_target_history(([name] + names)[:TARGET_HISTORY_LIMIT])

    def clear_target_history(self):
        self.set_target_history([])

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

    def library_changed(self):
        if self.catalog_session:
            self.catalog_session.close()
            self.catalog_session = None

    def refresh_library(self):
        if self.catalog_session:
            self.catalog_session.request_refresh()
        self.status.setText('已标记刷新图库，下次匹配将核对目录并更新索引')

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
            return ArcBand(w, h, self.straight_value.value())
        return CircularBand(w, h)

    def target_changed(self):
        if not hasattr(self, 'allowance'):
            return
        self.sketch_path = ''
        self.sketch_image.hide()
        self.sketch_review.hide()
        self.sketch_review.setChecked(False)
        fields = (self.width_value, self.height_value, self.straight_value)
        for field in fields:
            field.blockSignals(True)
        self.straight_value.setValue(0)
        try:
            parsed = parse_filename(self.target.text())
            self.width_value.setValue(parsed.width_cm)
            self.height_value.setValue(parsed.height_cm)
        except ValueError:
            self.width_value.setValue(0)
            self.height_value.setValue(0)
        for field in fields:
            field.blockSignals(False)
        self.match_label.setText('尚未匹配当前订单')
        self.match_label.setToolTip('生成预览后显示完整匹配结果')
        if self.preview.original is not None:
            self.preview_hint.setText('订单已更换 · 请重新生成预览')
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
        if pixmap.isNull():
            self.status.setText('草图文件无法识别为图片，请检查格式')
            return
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
            self.dimension_label.setText(f'花型：{parsed.pattern}\n实际{title} {shape.diameter:g}cm · 总高 {shape.height:g}cm\n直边 {shape.chord:.2f}cm' + conflict)
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
            if not request.material_override and self.catalog_session is None:
                self.catalog_session = CatalogSession(request.library_dir)
            self.worker = WorkflowWorker(request, preview, output, self,
                                         catalog_session=self.catalog_session)
            self.worker.status.connect(self.status.setText)
            self.worker.progress.connect(self.progress.setValue)
            self.worker.result.connect(self.task_result)
            self.worker.error.connect(self.show_error)
            self.worker.cancelled.connect(lambda: self.status.setText('已取消'))
            self.worker.finished.connect(self.task_finished)
            self.remember_target(request.target_name)
            self.worker.start()
        except Exception as error:
            self.show_error(str(error))

    def task_result(self, result):
        self.status.setToolTip('')
        self.match_label.setText(result['match_info'])
        self.match_label.setToolTip(result['match_info'])
        if result['image'] is not None:
            self.preview.show_image(result['image'])
            self.preview_hint.setText('点击图片放大查看 · 预览最长边 1200px')
            timings = result.get('timings', {})
            self.status.setText('自动预览已生成 · 匹配 {:.2f}s · 预览 {:.2f}s'.format(
                timings.get('match', 0), timings.get('generate', 0)))
        else:
            timings = result.get('timings', {})
            self.status.setText('成品已保存：{} · 用时 {:.2f}s'.format(
                result['output'], timings.get('match', 0) + timings.get('generate', 0)))
            self.status.setToolTip('匹配 {:.2f}s · 素材读取与分析 {:.2f}s · 渲染 {:.2f}s · 保存 {:.2f}s'.format(
                timings.get('match', 0), timings.get('prepare', 0),
                timings.get('render', 0), timings.get('save', 0)))

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
            if self.catalog_session:
                self.catalog_session.close()
            if self.manual_window:
                self.manual_window.close()
            event.accept()
