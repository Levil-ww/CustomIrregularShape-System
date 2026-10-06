"""Parameter editing and task presentation. Rendering remains in services/core."""
from dataclasses import replace
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QDoubleSpinBox, QSpinBox, QPushButton, QLabel, QLineEdit, QComboBox,
    QFileDialog, QMessageBox, QScrollArea, QProgressBar, QColorDialog)
from shape_crop.models.design import DesignSpec, MaterialSpec
from shape_crop.core.geometry import create_shape
from shape_crop.services.materials import load_image
from shape_crop.services.project_io import save_project, load_project
from shape_crop.workers.render_worker import RenderWorker
from shape_crop.gui.crop_dialog import CropDialog
from shape_crop.gui.image_utils import to_pixmap
from shape_crop.gui.theme import apply_theme


class PreviewCanvas(QLabel):
    def __init__(self):
        super().__init__('设置尺寸与素材后，点击“生成预览”')
        self.original = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 350)
        self._scaled_key = None
        self._checker = QPixmap(32, 32)
        self._checker.fill(QColor('#f5f7fa'))
        painter = QPainter(self._checker)
        painter.fillRect(0, 0, 16, 16, QColor('#eaf0f6'))
        painter.fillRect(16, 16, 16, 16, QColor('#eaf0f6'))
        painter.end()

    def show_image(self, image):
        self.original = to_pixmap(image)
        self.refresh()

    def refresh(self):
        if self.original is not None:
            key = (self.original.cacheKey(), self.width(), self.height())
            if key != self._scaled_key:
                self._scaled_key = key
                self.setPixmap(self.original.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawTiledPixmap(self.rect(), self._checker)
        if self.original is None:
            painter.fillRect(self.rect(), QColor('#f8faff'))
        painter.end()
        super().paintEvent(event)


class ManualWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('手工排版 · 圆桌素材设计器')
        self.resize(1280, 860)
        apply_theme(self)
        self.base = DesignSpec()
        self.worker = None
        self.close_pending = False
        self.fields = {}
        self.toolbar = self.addToolBar('设计操作')
        self.toolbar.setMovable(False)
        for title, callback in (('打开设计', self.open_design), ('保存设计', self.save_design),
                                ('生成预览', self.start_preview), ('导出图片', self.start_export)):
            self.toolbar.addAction(title, callback)
        root = QWidget()
        self.setCentralWidget(root)
        horizontal = QHBoxLayout(root)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        scroll.setMaximumWidth(450)
        controls = QWidget()
        self.controls = controls
        left = QVBoxLayout(controls)
        scroll.setWidget(controls)
        horizontal.addWidget(scroll)
        self.preview = PreviewCanvas()
        horizontal.addWidget(self.preview, 1)

        group, form = self.group('外轮廓（厘米）')
        left.addWidget(group)
        self.shape_mode = QComboBox()
        self.shape_mode.addItem('圆桌', 'circular')
        self.shape_mode.addItem('弧形台（对称圆弧）', 'arc')
        form.addRow('轮廓模块', self.shape_mode)
        self.add_number(form, 'diameter', '最大宽度 / 圆直径', 200, 0.01, 1000)
        self.add_number(form, 'height', '保留总高度', 83.76, 0.01, 1000)
        self.add_number(form, 'straight', '弧形台直边长度', 108, 0, 1000)
        self.fields['straight'].setEnabled(False)
        circle = QPushButton('完整圆：高度等于直径')
        circle.clicked.connect(lambda: self.fields['height'].setValue(self.fields['diameter'].value()))
        form.addRow(circle)
        self.dimensions = QLabel()
        self.dimensions.setWordWrap(True)
        form.addRow(self.dimensions)

        group, form = self.group('外边框（厘米）')
        left.addWidget(group)
        self.add_number(form, 'margin', '外缘到花边', 3.5, 0, 200)
        self.add_number(form, 'border_width', '装饰花边宽度', 2.5, 0, 100)
        self.add_number(form, 'line', '细线宽度', .10, 0, 10)
        colors = QHBoxLayout()
        for label, key in (('底色', 'background'), ('描边色', 'border')):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, name=key: self.choose_color(name))
            colors.addWidget(button)
        form.addRow(colors)

        group, form = self.group('外部素材')
        left.addWidget(group)
        self.outer_path = self.path_row(form, '选择素材', False)
        crops = QHBoxLayout()
        for text, key in (('框选中央花纹', 'content_box'), ('框选水平花边', 'strip_box')):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, region=key: self.select_region(region, False))
            crops.addWidget(button)
        form.addRow(crops)
        self.fit = QComboBox()
        self.fit.addItems(['等比覆盖', '花纹平铺'])
        form.addRow('花纹填充', self.fit)
        self.add_number(form, 'tile', '花纹平铺宽度 cm', 40, .01, 1000)
        self.add_number(form, 'repeat', '花边重复长度 cm（0 自动）', 0, 0, 1000)
        note = QLabel('初始选区按蔓生花示例估计；正式输出前请框选确认。花边长度为 0 时按选区比例计算，避免圆点被明显压扁。')
        note.setWordWrap(True)
        form.addRow(note)

        group, form = self.group('中心圆（厘米）')
        left.addWidget(group)
        self.add_number(form, 'inner', '内圆外径（0 关闭）', 0, 0, 1000)
        self.add_number(form, 'inner_border', '内圆花边宽度', 2.5, 0, 100)
        self.inner_path = self.path_row(form, '选择内圆素材', True)
        inner_note = QLabel('不选内圆素材时复用外部素材。内圆直径包含内圆花边。')
        inner_note.setWordWrap(True)
        form.addRow(inner_note)
        inner_crops = QHBoxLayout()
        for text, key in (('内圆花纹选区', 'content_box'), ('内圆花边选区', 'strip_box')):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, region=key: self.select_region(region, True))
            inner_crops.addWidget(button)
        form.addRow(inner_crops)

        group, form = self.group('生成与项目文件')
        left.addWidget(group)
        dpi = QSpinBox()
        dpi.setRange(1, 1200)
        dpi.setValue(150)
        self.fields['dpi'] = dpi
        form.addRow('导出 DPI', dpi)
        actions = QHBoxLayout()
        for label, callback in (('生成预览', self.start_preview), ('导出图片', self.start_export)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        form.addRow(actions)
        projects = QHBoxLayout()
        for label, callback in (('保存设计', self.save_design), ('打开设计', self.open_design)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            projects.addWidget(button)
        form.addRow(projects)
        self.progress = QProgressBar()
        form.addRow(self.progress)
        self.status = QLabel('就绪 · PNG 外部透明，JPG 外部白底')
        self.status.setWordWrap(True)
        form.addRow(self.status)
        left.addStretch()
        self.cancel = QPushButton('取消当前任务')
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_task)
        self.statusBar().addPermanentWidget(self.cancel)
        for field in self.fields.values():
            field.valueChanged.connect(self.update_dimensions)
        self.shape_mode.currentIndexChanged.connect(self.change_shape_mode)
        self.update_dimensions()

    def change_shape_mode(self):
        self.fields['straight'].setEnabled(self.shape_mode.currentData() == 'arc')
        self.update_dimensions()

    @staticmethod
    def group(title):
        group = QGroupBox(title)
        return group, QFormLayout(group)

    def add_number(self, form, key, label, value, minimum, maximum):
        field = QDoubleSpinBox()
        field.setDecimals(3)
        field.setRange(minimum, maximum)
        field.setValue(value)
        field.setSingleStep(.1)
        self.fields[key] = field
        form.addRow(label, field)

    def path_row(self, form, label, inner):
        line = QLineEdit()
        line.setPlaceholderText('可留空')
        button = QPushButton(label)
        button.clicked.connect(lambda: self.choose_material(inner))
        layout = QHBoxLayout()
        layout.addWidget(line, 1)
        layout.addWidget(button)
        form.addRow(layout)
        return line

    def choose_material(self, inner):
        path, _ = QFileDialog.getOpenFileName(self, '选择素材', '', '图片 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp)')
        if path:
            (self.inner_path if inner else self.outer_path).setText(path)

    def choose_color(self, key):
        current = self.base.background if key == 'background' else self.base.border.color
        color = QColorDialog.getColor(QColor(*current), self)
        if color.isValid():
            value = (color.red(), color.green(), color.blue())
            self.base = replace(self.base, background=value) if key == 'background' else replace(
                self.base, border=replace(self.base.border, color=value))

    def select_region(self, region, inner):
        path = (self.inner_path if inner else self.outer_path).text().strip()
        if not path:
            QMessageBox.information(self, '素材选区', '请先选择对应素材图片')
            return
        try:
            material = (self.base.inner_material or MaterialSpec()) if inner else self.base.material
            dialog = CropDialog(load_image(path), getattr(material, region), '框选素材区域', self)
            if dialog.exec_():
                selected = replace(material, **{region: dialog.canvas.box})
                self.base = replace(self.base, **{'inner_material' if inner else 'material': selected})
        except Exception as error:
            self.show_error(str(error))

    def snapshot(self):
        v = {key: item.value() for key, item in self.fields.items()}
        material = replace(self.base.material, layout='manual', path=self.outer_path.text().strip(),
                           fit='cover' if self.fit.currentIndex() == 0 else 'tile',
                           tile_width_cm=v['tile'], border_repeat_cm=v['repeat'])
        inner_path = self.inner_path.text().strip()
        inner = replace(self.base.inner_material or MaterialSpec(), layout='manual', path=inner_path,
                        fit=material.fit, tile_width_cm=v['tile'], border_repeat_cm=v['repeat']) if inner_path else None
        spec = replace(self.base, diameter_cm=v['diameter'], height_cm=v['height'], dpi=v['dpi'],
                       shape_mode=self.shape_mode.currentData(), straight_cm=v['straight'],
                       border=replace(self.base.border, margin_cm=v['margin'], width_cm=v['border_width'], line_cm=v['line']),
                       material=material, inner_diameter_cm=v['inner'], inner_border_cm=v['inner_border'], inner_material=inner)
        spec.validate()
        return spec

    def update_dimensions(self):
        try:
            spec = self.snapshot()
            shape = create_shape(spec)
            w, h = spec.pixel_size()
            self.dimensions.setText(f'上下各 {spec.height_cm / 2:.3f} cm\n上下直边 {shape.chord:.4f} cm\n导出 {w} × {h} px')
            self.dimensions.setStyleSheet('')
        except ValueError as error:
            self.dimensions.setText(str(error))
            self.dimensions.setStyleSheet('color: #bb3535;')

    def start_preview(self):
        self.start_task(True)

    def start_export(self):
        try:
            spec = self.snapshot()
            width, height = spec.pixel_size()
            if width * height > 180_000_000:
                raise ValueError('导出超过 1.8 亿像素，请降低 DPI 或尺寸')
        except ValueError as error:
            self.show_error(str(error))
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出图片', '圆桌成品.png', 'PNG (*.png);;JPG (*.jpg)')
        if path:
            if not Path(path).suffix:
                path += '.png'
            self.start_task(False, path)

    def start_task(self, preview, output=None):
        if self.worker is not None:
            return
        try:
            design = self.snapshot()
        except ValueError as error:
            self.show_error(str(error))
            return
        self.controls.setEnabled(False)
        self.toolbar.setEnabled(False)
        self.cancel.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText('正在生成预览…' if preview else '正在生成全尺寸图片，完成渲染后写入文件…')
        worker = RenderWorker(design, preview, output, self)
        self.worker = worker
        worker.progress.connect(self.progress.setValue)
        worker.status.connect(self.status.setText)
        worker.result.connect(lambda image: self.task_result(image, output))
        worker.error.connect(self.show_error)
        worker.cancelled.connect(lambda: self.status.setText('任务已取消'))
        worker.finished.connect(self.task_finished)
        worker.start()

    def task_result(self, image, output):
        if image is not None:
            self.preview.show_image(image)
            self.status.setText('预览已更新 · 实际尺寸以左侧参数为准')
        else:
            self.status.setText(f'已导出：{output}')

    def task_finished(self):
        worker = self.worker
        self.worker = None
        worker.deleteLater()
        self.controls.setEnabled(True)
        self.toolbar.setEnabled(True)
        self.cancel.setEnabled(False)
        if self.close_pending:
            self.close()

    def cancel_task(self):
        if self.worker:
            self.worker.requestInterruption()
            self.status.setText('正在取消，等待当前处理步骤结束…')

    def show_error(self, message):
        self.status.setText('生成失败：' + message)
        QMessageBox.warning(self, '无法完成', message)

    def save_design(self):
        try:
            spec = self.snapshot()
            path, _ = QFileDialog.getSaveFileName(self, '保存设计', '圆桌设计.json', '设计文件 (*.json)')
            if path:
                if not Path(path).suffix:
                    path += '.json'
                save_project(path, spec)
                self.status.setText('设计参数及素材选区已保存')
        except Exception as error:
            self.show_error(str(error))

    def open_design(self):
        path, _ = QFileDialog.getOpenFileName(self, '打开设计', '', '设计文件 (*.json)')
        if not path:
            return
        try:
            spec = load_project(path)
            self.base = spec
            values = dict(diameter=spec.diameter_cm, height=spec.height_cm, dpi=spec.dpi,
                          straight=spec.straight_cm,
                          margin=spec.border.margin_cm, border_width=spec.border.width_cm,
                          line=spec.border.line_cm, tile=spec.material.tile_width_cm,
                          repeat=spec.material.border_repeat_cm, inner=spec.inner_diameter_cm,
                          inner_border=spec.inner_border_cm)
            for key, value in values.items():
                self.fields[key].blockSignals(True)
                self.fields[key].setMaximum(max(self.fields[key].maximum(), value))
                self.fields[key].setValue(value)
                self.fields[key].blockSignals(False)
            self.outer_path.setText(spec.material.path)
            self.inner_path.setText(spec.inner_material.path if spec.inner_material else '')
            self.fit.setCurrentIndex(0 if spec.material.fit == 'cover' else 1)
            self.shape_mode.setCurrentIndex(1 if spec.shape_mode == 'arc' else 0)
            self.fields['straight'].setEnabled(spec.shape_mode == 'arc')
            self.update_dimensions()
            self.status.setText('设计已载入，点击“生成预览”查看')
        except Exception as error:
            self.show_error(str(error))

    def closeEvent(self, event):
        if self.worker:
            self.close_pending = True
            self.cancel_task()
            event.ignore()
        else:
            event.accept()
