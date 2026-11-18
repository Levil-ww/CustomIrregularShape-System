"""Controls for circular artwork."""
from pathlib import Path
from PyQt5.QtCore import Qt, QRectF, QThread, QSettings, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox, QComboBox, QFileDialog, QMessageBox, QSplitter,
    QCheckBox, QGroupBox, QScrollArea)
from shape_crop.gui.manual_window import PreviewCanvas
from shape_crop.services.circle import parse_circle_name, generate_circle


class CircleOutline(QWidget):
    """Show the current circular dimensions without rendering the material."""

    def __init__(self):
        super().__init__()
        self.diameter = 0
        self.inner = 0
        self.gap = 0
        self.setMinimumHeight(160)
        self.setMaximumHeight(180)

    def set_dimensions(self, diameter, inner, gap):
        self.diameter, self.inner, self.gap = diameter, inner, gap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.diameter <= 0:
            painter.drawText(self.rect(), Qt.AlignCenter, '填写尺寸后显示轮廓')
            return
        side = max(0, min(self.width() - 35, self.height() - 38))
        x, y = (self.width() - side) / 2, (self.height() - side) / 2
        painter.setPen(QColor('#286c9a'))
        painter.setBrush(QColor('#e3f0f8'))
        painter.drawEllipse(QRectF(x, y, side, side))
        if 0 < self.inner + 2 * self.gap < self.diameter:
            hole = side * (self.inner + 2 * self.gap) / self.diameter
            offset = (side - hole) / 2
            painter.setBrush(QColor('#ffffff'))
            painter.drawEllipse(QRectF(x + offset, y + offset, hole, hole))
            inside = side * self.inner / self.diameter
            offset = (side - inside) / 2
            painter.setBrush(QColor('#e3f0f8'))
            painter.drawEllipse(QRectF(x + offset, y + offset, inside, inside))


class CircleWorker(QThread):
    result = pyqtSignal(object, str)
    error = pyqtSignal(str)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.options = options

    def run(self):
        try:
            image, detail = generate_circle(**self.options, cancelled=self.isInterruptionRequested)
            self.result.emit(image if self.options['preview'] else None, detail)
        except Exception as error:
            self.error.emit(str(error))


class CircleModule(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.diameter_manual = False
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)
        self.sidebar = QWidget()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setMinimumWidth(390)
        self.sidebar.setMaximumWidth(510)
        left = QVBoxLayout(self.sidebar)
        left.setContentsMargins(16, 12, 16, 16)
        left.setSpacing(10)
        splitter.addWidget(self.sidebar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls = QWidget()
        controls.setObjectName('controls')
        scroll.setWidget(controls)
        left.addWidget(scroll, 1)
        layout = QVBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        title = QLabel('01  订单与尺寸')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        self.mode = QComboBox()
        self.mode.addItems(['正圆', '同心圆'])
        self.mode.currentIndexChanged.connect(self.update_mode)
        layout.addWidget(self.mode)
        layout.addWidget(QLabel('目标文件名'))
        self.target = QLineEdit()
        self.target.setPlaceholderText('例如：双面格-蔓生花;140CM圆形裁剪有图')
        self.target.textChanged.connect(self.read_target)
        layout.addWidget(self.target)
        form = QFormLayout()
        layout.addLayout(form)
        self.diameter = self.number(0, 1000, 0)
        self.diameter.valueChanged.connect(self.mark_manual)
        form.addRow('标称外径 cm', self.diameter)
        self.auto_diameter = QPushButton('恢复文件名直径')
        self.auto_diameter.clicked.connect(self.reset_diameter)
        layout.addWidget(self.auto_diameter)
        self.inner = self.number(0, 1000, 0)
        form.addRow('内圆实际直径 cm', self.inner)
        self.gap = self.number(0, 1000, 0)
        form.addRow('径向间隙 cm', self.gap)
        hint = QLabel('外径来自目标文件名，可手工修改；同心圆的内径按实际成品尺寸填写。')
        hint.setObjectName('hint')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        title = QLabel('02  素材与输出')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        files = QFormLayout()
        layout.addLayout(files)
        self.library = self.path_row(files, '素材图库', True)
        self.output_dir = self.path_row(files, '输出目录', True)
        self.format = QComboBox()
        self.format.addItems(['JPG（白底）', 'PNG（透明）'])
        files.addRow('输出格式', self.format)
        output_hint = QLabel('输出名称与目标名称一致')
        output_hint.setObjectName('hint')
        layout.addWidget(output_hint)
        self.advanced_toggle = QCheckBox('高级选项（通常无需调整）')
        layout.addWidget(self.advanced_toggle)
        self.advanced = QGroupBox('可选设置')
        advanced = QFormLayout(self.advanced)
        self.allowance = self.number(0, 10, 1)
        advanced.addRow('直径损耗补偿 cm', self.allowance)
        self.line = QSpinBox()
        self.line.setRange(0, 1000)
        self.line.setValue(10)
        advanced.addRow('黑色轮廓线 px', self.line)
        self.dpi = QSpinBox()
        self.dpi.setRange(1, 1200)
        self.dpi.setValue(150)
        advanced.addRow('输出 DPI', self.dpi)
        self.outer_override = self.path_row(advanced, '指定外圆素材', False)
        self.inner_override = self.path_row(advanced, '指定内圆素材', False)
        layout.addWidget(self.advanced)
        self.advanced.hide()
        self.advanced_toggle.toggled.connect(self.advanced.setVisible)
        layout.addStretch()
        self.diameter.valueChanged.connect(self.update_size)
        self.allowance.valueChanged.connect(self.update_size)
        actions = QHBoxLayout()
        self.preview_button = QPushButton('匹配并预览')
        self.export_button = QPushButton('生成成品')
        self.export_button.setObjectName('primary')
        self.preview_button.clicked.connect(lambda: self.start(True))
        self.export_button.clicked.connect(lambda: self.start(False))
        self.target.returnPressed.connect(lambda: self.start(True))
        actions.addWidget(self.preview_button)
        actions.addWidget(self.export_button)
        left.addLayout(actions)
        self.status = QLabel('就绪')
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.preview_card = QWidget()
        self.preview_card.setObjectName('previewCard')
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(20, 12, 20, 16)
        heading = QHBoxLayout()
        preview_title = QLabel('成品预览')
        preview_title.setObjectName('sectionTitle')
        heading.addWidget(preview_title)
        heading.addStretch()
        preview_hint = QLabel('点击图片放大查看 · 预览最长边 1200px')
        preview_hint.setObjectName('hint')
        heading.addWidget(preview_hint)
        preview_layout.addLayout(heading)
        self.preview = PreviewCanvas()
        self.preview.setText('等待生成预览\n\n输入目标文件名，选择图库\n点击「匹配并预览」查看裁剪效果')
        preview_layout.addWidget(self.preview, 1)
        details = QHBoxLayout()
        geometry = QGroupBox('尺寸与轮廓')
        geometry.setFixedWidth(270)
        geometry_layout = QVBoxLayout(geometry)
        self.outline = CircleOutline()
        geometry_layout.addWidget(self.outline)
        details.addWidget(geometry)
        info = QGroupBox('当前订单')
        info_layout = QVBoxLayout(info)
        self.size_label = QLabel()
        self.size_label.setWordWrap(True)
        info_layout.addWidget(self.size_label)
        self.match_label = QLabel('尚未匹配素材\n生成预览后显示匹配来源')
        self.match_label.setObjectName('hint')
        self.match_label.setWordWrap(True)
        self.match_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.match_label.setMaximumHeight(115)
        info_layout.addWidget(self.match_label)
        info_layout.addStretch()
        details.addWidget(info, 1)
        preview_layout.addLayout(details)
        splitter.addWidget(self.preview_card)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 810])
        self.inner.valueChanged.connect(self.update_size)
        self.gap.valueChanged.connect(self.update_size)
        self.update_mode()
        self.update_size()

    def number(self, low, high, value):
        field = QDoubleSpinBox()
        field.setRange(low, high)
        field.setDecimals(2)
        field.setValue(value)
        return field

    def path_row(self, form, label, directory):
        row = QHBoxLayout()
        field = QLineEdit()
        field.setPlaceholderText('选择目录' if directory else '留空自动匹配')
        button = QPushButton('选择')
        def pick():
            path = QFileDialog.getExistingDirectory(self, label, field.text()) if directory else QFileDialog.getOpenFileName(self, label, '', '图片 (*.jpg *.jpeg *.png)')[0]
            if path:
                field.setText(path)
        button.clicked.connect(pick)
        row.addWidget(field)
        row.addWidget(button)
        form.addRow(label, row)
        return field

    def update_mode(self):
        active = self.mode.currentIndex() == 1
        self.inner.setEnabled(active)
        self.gap.setEnabled(active)
        self.inner_override.setEnabled(active)
        if hasattr(self, 'size_label'):
            self.update_size()

    def update_size(self):
        actual = self.diameter.value() + self.allowance.value()
        text = f'实际外径 {actual:g} cm · 标称外径 {self.diameter.value():g} cm'
        if self.mode.currentIndex():
            text += f'\n内圆实际直径 {self.inner.value():g} cm · 径向间隙 {self.gap.value():g} cm'
        self.size_label.setText(text)
        self.outline.set_dimensions(actual if self.diameter.value() else 0,
                                    self.inner.value() if self.mode.currentIndex() else 0,
                                    self.gap.value() if self.mode.currentIndex() else 0)

    def read_target(self):
        if self.diameter_manual:
            return
        try:
            value = parse_circle_name(self.target.text()).diameter_cm
            self.diameter.blockSignals(True)
            self.diameter.setValue(value)
            self.diameter.blockSignals(False)
            self.update_size()
        except ValueError:
            pass

    def mark_manual(self):
        self.diameter_manual = True

    def reset_diameter(self):
        self.diameter_manual = False
        self.read_target()

    def snapshot(self):
        inner = self.inner.value() if self.mode.currentIndex() else 0
        if self.mode.currentIndex() and inner <= 0:
            raise ValueError('请填写同心圆的内圆实际直径')
        return dict(target_name=self.target.text().strip(), library=self.library.text().strip(),
                    diameter=self.diameter.value(), allowance=self.allowance.value(),
                    inner_diameter=inner, gap=self.gap.value() if inner else 0,
                    line_px=self.line.value(), dpi=self.dpi.value(),
                    outer_override=self.outer_override.text().strip(), inner_override=self.inner_override.text().strip())

    def start(self, preview):
        if self.worker:
            return
        try:
            options = self.snapshot()
            target = parse_circle_name(options['target_name'], require_diameter=False)
            output = None
            if not preview:
                directory = Path(self.output_dir.text().strip())
                if not self.output_dir.text().strip() or not directory.is_dir():
                    raise ValueError('请选择有效的输出目录')
                output = str(directory / (target.stem + ('.jpg' if self.format.currentIndex() == 0 else '.png')))
            options.update(preview=preview, output=output)
            settings = QSettings('ShapeCrop', 'CircularDesigner')
            settings.setValue('library_dir', self.library.text().strip())
            settings.setValue('output_dir', self.output_dir.text().strip())
            self.worker = CircleWorker(options, self)
            self.worker.result.connect(lambda image, detail: self.finished(image, detail, output))
            self.worker.error.connect(self.failed)
            self.worker.finished.connect(self.clear_worker)
            self.preview_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.status.setText('正在匹配素材并生成，请稍候…')
            self.worker.start()
        except ValueError as error:
            QMessageBox.warning(self, '无法生成', str(error))

    def finished(self, image, detail, output):
        if image is not None:
            self.preview.show_image(image)
        self.match_label.setText(detail)
        self.match_label.setToolTip(detail)
        self.status.setText(f'成品已保存：{output}' if output else '自动预览已生成')

    def failed(self, error):
        self.status.setText(error)
        QMessageBox.warning(self, '生成失败', error)

    def clear_worker(self):
        self.worker.deleteLater()
        self.worker = None
        self.preview_button.setEnabled(True)
        self.export_button.setEnabled(True)
