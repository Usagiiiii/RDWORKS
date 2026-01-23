from PyQt5.QtCore import Qt, QBuffer, QIODevice, QSize, QRectF
from PyQt5.QtGui import QImage, QPainter, QPixmap, QTransform
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from PIL import Image, ImageEnhance, ImageOps, ImageFilter
# import cv2  # Moved to inside function to avoid potential conflicts or crashes if missing
import io
import numpy as np


class PreviewGraphicsView(QGraphicsView):
    """Graphics view with mouse wheel zoom and panning."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._zoom = 0
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

    def set_pixmap(self, pixmap: QPixmap, fit=True):
        self._scene.clear()
        self._scene.addPixmap(pixmap)
        # 显式转换 QRect 为 QRectF
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        if fit:
            self.fit_to_view()
        self._zoom = 0

    def fit_to_view(self):
        if self._scene.itemsBoundingRect().isNull():
            return
        self.setTransform(QTransform())
        self.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        self._zoom = 0

    def wheelEvent(self, event):  # noqa: N802 (Qt API)
        if not self._scene.itemsBoundingRect().isValid():
            return
        delta = event.angleDelta().y()
        zoom_factor = 1.25 if delta > 0 else 0.8
        self.scale(zoom_factor, zoom_factor)
        self._zoom += 1 if delta > 0 else -1
        event.accept()


class BitmapProcessDialog(QDialog):
    def __init__(self, target_item, parent=None):
        super().__init__(parent)
        self.target_item = target_item
        self.setWindowTitle("位图处理")
        self.resize(900, 540)

        qimage = self.target_item.pixmap().toImage()
        buffer = QBuffer()
        buffer.open(QIODevice.ReadWrite)
        qimage.save(buffer, "PNG")
        buffer.seek(0)

        try:
            pil_image = Image.open(io.BytesIO(buffer.data())).convert("RGBA")
        except Exception:  # 粗略兜底，确保对话框可用
            pil_image = Image.new("RGBA", (100, 100), (255, 255, 255, 255))

        self.original_image = pil_image
        self.preview_image = pil_image.copy()
        self.processed_image = pil_image.copy()
        self.extracted_contours = []

        self._dpi_x, self._dpi_y = self._get_initial_dpi(qimage)
        self.output_dpi = (self._dpi_x, self._dpi_y)

        self._build_ui()
        self._update_info_labels()
        self._update_value_labels()
        self._update_output_dpi()
        self.update_preview(force_fit=True)

    # ------------------------- UI construction -------------------------
    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        self.preview_view = PreviewGraphicsView(self)
        self.preview_view.setMinimumSize(QSize(480, 0))
        main_layout.addWidget(self.preview_view, 1)

        side_panel = QVBoxLayout()
        side_panel.setSpacing(8)
        main_layout.addLayout(side_panel, 0)

        # Info box
        info_box = QGroupBox("图像信息")
        form = QFormLayout(info_box)
        self.label_size = QLabel()
        self.label_height = QLabel()
        self.label_resolution = QLabel()
        self.label_v_resolution = QLabel()
        
        form.addRow("宽度:", self.label_size)
        form.addRow("高度:", self.label_height)
        form.addRow("水平分辨率:", self.label_resolution)
        form.addRow("垂直分辨率:", self.label_v_resolution)
        side_panel.addWidget(info_box)

        # Brightness / Contrast controls
        bright_group = QGroupBox("亮度 / 对比度")
        bright_layout = QVBoxLayout(bright_group)
        self.slider_brightness_row, self.label_brightness_value, self.btn_reset_brightness = self._create_slider_row(
            "亮度:"
        )
        bright_layout.addLayout(self.slider_brightness_row)
        self.slider_contrast_row, self.label_contrast_value, self.btn_reset_contrast = self._create_slider_row(
            "对比度:"
        )
        bright_layout.addLayout(self.slider_contrast_row)
        side_panel.addWidget(bright_group)

        self.btn_reset_brightness.clicked.connect(lambda: self._reset_slider(self.slider_brightness_widget))
        self.btn_reset_contrast.clicked.connect(lambda: self._reset_slider(self.slider_contrast_widget))

        # Because helper returns layout, we need access to widgets
        self.slider_brightness_widget = self.slider_brightness_row.itemAt(1).widget()
        self.slider_contrast_widget = self.slider_contrast_row.itemAt(1).widget()

        self.label_brightness_value.setText("0.0%")
        self.label_contrast_value.setText("0.0%")

        self.slider_brightness_widget.valueChanged.connect(self._on_adjustment_changed)
        self.slider_contrast_widget.valueChanged.connect(self._on_adjustment_changed)

        # Additional toggles
        toggles_box = QGroupBox("基础处理")
        toggles_layout = QVBoxLayout(toggles_box)
        self.chk_invert = QCheckBox("反色")
        self.chk_invert.toggled.connect(self._on_adjustment_changed)
        toggles_layout.addWidget(self.chk_invert)

        self.chk_resolution = QCheckBox("修改输出分辨率")
        self.chk_resolution.toggled.connect(self._on_resolution_toggled)
        toggles_layout.addWidget(self.chk_resolution)

        resolution_row = QHBoxLayout()
        resolution_row.addSpacing(12)
        resolution_row.addWidget(QLabel("分辨率(像素/英寸)"))
        self.edit_resolution = QLineEdit("120")
        self.edit_resolution.setEnabled(False)
        self.edit_resolution.setMaximumWidth(80)
        self.edit_resolution.textChanged.connect(self._on_adjustment_changed)
        resolution_row.addWidget(self.edit_resolution)
        resolution_row.addStretch()
        toggles_layout.addLayout(resolution_row)
        side_panel.addWidget(toggles_box)

        # Process group
        process_box = QGroupBox("处理")
        process_layout = QVBoxLayout(process_box)
        self.chk_enable_process = QCheckBox("启用处理")
        self.chk_enable_process.toggled.connect(self._on_process_toggled)
        process_layout.addWidget(self.chk_enable_process)

        self.process_button_group = QButtonGroup(self)
        self.radio_halftone = QRadioButton("网点图")
        self.radio_scatter = QRadioButton("散点图")
        self.radio_bw = QRadioButton("黑白图")
        self.radio_gray = QRadioButton("灰度图")
        self.radio_sharpen = QRadioButton("锐化")

        for idx, radio in enumerate(
            [self.radio_halftone, self.radio_scatter, self.radio_bw, self.radio_gray, self.radio_sharpen]
        ):
            self.process_button_group.addButton(radio, idx)
            radio.setEnabled(False)
            radio.toggled.connect(self._on_adjustment_changed)
            process_layout.addWidget(radio)

        frequency_row = QHBoxLayout()
        frequency_row.addSpacing(20)
        frequency_row.addWidget(QLabel("频率(线/英寸):"))
        self.edit_frequency = QLineEdit("1")
        self.edit_frequency.setEnabled(False)
        self.edit_frequency.setMaximumWidth(80)
        # 信号连接延后，防止初始化时触发

        frequency_row.addWidget(self.edit_frequency)
        frequency_row.addStretch()
        process_layout.addLayout(frequency_row)
        side_panel.addWidget(process_box)

        # 延后设置初始值以触发信号（在此处 edit_frequency 已创建）
        self.radio_scatter.setChecked(True)
        self.edit_frequency.textChanged.connect(self._on_adjustment_changed)

        # Action buttons above footer
        actions_row = QHBoxLayout()
        # 移除“应用到预览”按钮，因为预览是实时更新的
        self.btn_apply_original = QPushButton("应用到原图")
        self.btn_apply_original.clicked.connect(self._apply_to_original)
        actions_row.addWidget(self.btn_apply_original)
        side_panel.addLayout(actions_row)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        side_panel.addWidget(separator)


        # Footer buttons
        footer_row_top = QHBoxLayout()
        self.btn_extract = QPushButton("提取轮廓")
        self.btn_extract.clicked.connect(self._extract_contours)
        footer_row_top.addWidget(self.btn_extract)
        side_panel.addLayout(footer_row_top)

        footer_row_bottom = QHBoxLayout()
        self.btn_fit = QPushButton("满幅面")
        self.btn_fit.clicked.connect(self.preview_view.fit_to_view)
        self.btn_save = QPushButton("另存图片")
        self.btn_save.clicked.connect(self._save_current_image)
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)

        footer_row_bottom.addWidget(self.btn_fit)
        footer_row_bottom.addWidget(self.btn_save)
        footer_row_bottom.addWidget(self.btn_ok)
        footer_row_bottom.addWidget(self.btn_cancel)
        side_panel.addLayout(footer_row_bottom)

        side_panel.addStretch(1)

    def showEvent(self, event):
        super().showEvent(event)
        # 窗口显示后强制适应视图，确保预览图充满
        if hasattr(self, 'preview_view'):
            self.preview_view.fit_to_view()

    def _create_slider_row(self, label_text):
        layout = QHBoxLayout()
        name_label = QLabel(label_text)
        layout.addWidget(name_label)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.setSingleStep(1)
        slider.setPageStep(10)
        layout.addWidget(slider, 1)

        value_label = QLabel("0.0%")
        value_label.setFixedWidth(50)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(value_label)

        reset_btn = QPushButton("归零")
        layout.addWidget(reset_btn)

        return layout, value_label, reset_btn

    # ------------------------- Event handlers -------------------------
    def _reset_slider(self, slider):
        slider.setValue(0)

    def _on_adjustment_changed(self):
        self._update_value_labels()
        self._update_output_dpi()
        self.update_preview(fit_to_view=False)

    def _on_resolution_toggled(self, checked):
        self.edit_resolution.setEnabled(checked)
        self._on_adjustment_changed()

    def _on_process_toggled(self, checked):
        for btn in self.process_button_group.buttons():
            btn.setEnabled(checked)
        self.edit_frequency.setEnabled(checked and self.radio_halftone.isChecked())
        self._on_adjustment_changed()

    # ------------------------- Preview updates -------------------------
    def update_preview(self, force_fit=False, fit_to_view=True):
        self.preview_image = self._build_preview_image()
        pixmap = self._pil_to_qpixmap(self.preview_image)
        self.preview_view.set_pixmap(pixmap, fit=force_fit or fit_to_view)

    def _build_preview_image(self):
        img = self.original_image.copy()

        brightness_ratio = 1.0 + (self.slider_brightness_widget.value() / 100.0)
        contrast_ratio = 1.0 + (self.slider_contrast_widget.value() / 100.0)

        if not np.isclose(brightness_ratio, 1.0):
            img = ImageEnhance.Brightness(img).enhance(brightness_ratio)

        if not np.isclose(contrast_ratio, 1.0):
            img = ImageEnhance.Contrast(img).enhance(contrast_ratio)

        if self.chk_invert.isChecked():
            base = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
            if base.mode == "RGBA":
                rgb = base.convert("RGB")
                inv = ImageOps.invert(rgb).convert("RGBA")
                inv.putalpha(base.split()[-1])
                img = inv
            else:
                img = ImageOps.invert(base)

        if self.chk_enable_process.isChecked():
            img = self._apply_processing(img)

        return img

    def _apply_processing(self, img):
        chosen = self.process_button_group.checkedButton()
        if not chosen:
            return img

        label = chosen.text()
        base = img
        if label == "网点图":
            frequency = self._safe_float(self.edit_frequency.text(), default=1.0)
            base = self._apply_halftone(base, max(frequency, 0.1))
        elif label == "散点图":
            base = base.convert("L").convert("1", dither=Image.FLOYDSTEINBERG).convert("RGBA")
        elif label == "黑白图":
            gray = base.convert("L")
            base = gray.point(lambda p: 255 if p > 128 else 0, mode="1").convert("RGBA")
        elif label == "灰度图":
            base = base.convert("L").convert("RGBA")
        elif label == "锐化":
            base = base.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

        return base

    def _apply_halftone(self, img, frequency):
        gray = img.convert("L")
        dpi = self._dpi_x or 120
        cell_size = max(4, int(dpi / frequency / 4))
        width, height = gray.size
        halftone = Image.new("L", (width, height), 255)

        pixels = gray.load()
        output = halftone.load()
        for y in range(0, height, cell_size):
            for x in range(0, width, cell_size):
                block = [pixels[min(x + dx, width - 1), min(y + dy, height - 1)] for dy in range(cell_size) for dx in range(cell_size)]
                avg = sum(block) / len(block)
                radius = int((avg / 255.0) * (cell_size / 2))
                for dy in range(cell_size):
                    for dx in range(cell_size):
                        px = x + dx
                        py = y + dy
                        if px >= width or py >= height:
                            continue
                        dist = ((dx - cell_size / 2) ** 2 + (dy - cell_size / 2) ** 2) ** 0.5
                        output[px, py] = 0 if dist <= radius else 255

        return halftone.convert("RGBA")

    # ------------------------- Toolbar actions -------------------------
    def _apply_to_original(self):
        committed = self.preview_image.copy()
        self.original_image = committed
        self.processed_image = committed
        QMessageBox.information(self, "提示", "已将当前效果应用到原图。")

    def _save_current_image(self):
        filename, _ = QFileDialog.getSaveFileName(self, "另存图片", "", "PNG 文件 (*.png);;JPEG 文件 (*.jpg *.jpeg)")
        if not filename:
            return
        try:
            self.preview_image.save(filename)
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"保存图片时出错: {exc}")

    def _extract_contours(self):
        try:
            import cv2
        except ImportError:
            QMessageBox.warning(self, "缺少组件", "请安装 opencv-python 以使用轮廓提取功能。")
            return
            
        # Use preview image (what the user sees) for extraction
        if self.preview_image.mode != "L":
             # Convert to grayscale for edge detection
             work_img = self.preview_image.convert("L")
        else:
             work_img = self.preview_image.copy()
             
        np_img = np.array(work_img)
        # 简单边缘检测
        edges = cv2.Canny(np_img, 100, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        extracted = []
        for cnt in contours:
            if len(cnt) < 3:
                continue
            approx = cv2.approxPolyDP(cnt, 1.5, closed=False) # 简化多边形
            points = [(float(p[0][0]), float(p[0][1])) for p in approx]
            if len(points) > 1:
                extracted.append(points)

        self.extracted_contours = extracted
        QMessageBox.information(self, "提取轮廓", f"共提取 {len(extracted)} 条轮廓。")

    # ------------------------- Helpers -------------------------
    def _pil_to_qpixmap(self, image: Image.Image) -> QPixmap:
        # 确保 image 是 PIL Image
        if not isinstance(image, Image.Image):
             return QPixmap()
             
        try:
            if image.mode == "RGB":
                data = image.tobytes("raw", "RGB")
                stride = image.width * 3
                qim = QImage(data, image.width, image.height, stride, QImage.Format_RGB888)
            elif image.mode == "RGBA":
                data = image.tobytes("raw", "BGRA")
                stride = image.width * 4
                qim = QImage(data, image.width, image.height, stride, QImage.Format_ARGB32)
            elif image.mode == "L":
                data = image.tobytes("raw", "L")
                stride = image.width
                qim = QImage(data, image.width, image.height, stride, QImage.Format_Grayscale8)
            elif image.mode == "1":
                image = image.convert("L")
                data = image.tobytes("raw", "L")
                stride = image.width
                qim = QImage(data, image.width, image.height, stride, QImage.Format_Grayscale8)
            else:
                image = image.convert("RGBA")
                data = image.tobytes("raw", "BGRA")
                stride = image.width * 4
                qim = QImage(data, image.width, image.height, stride, QImage.Format_ARGB32)

            # Deep copy to ensure data persists immediately
            qim = qim.copy()
            return QPixmap.fromImage(qim)
        except Exception as e:
            print(f"Error converting image to pixmap: {e}")
            # 返回一个红色占位图表示错误，防止崩溃
            fallback = QPixmap(100, 100)
            fallback.fill(Qt.red)
            return fallback

    def _update_info_labels(self):
        width, height = self.original_image.size
        self.label_size.setText(f"{width} 像素")
        self.label_height.setText(f"{height} 像素")

        self.label_resolution.setText(f"{self._dpi_x:.0f} 像素/英寸")
        self.label_v_resolution.setText(f"{self._dpi_y:.0f} 像素/英寸")
        self.edit_resolution.setText(f"{self.output_dpi[0]:.0f}")

    def _update_value_labels(self):
        self.label_brightness_value.setText(f"{self.slider_brightness_widget.value():.1f}%")
        self.label_contrast_value.setText(f"{self.slider_contrast_widget.value():.1f}%")
        if self.chk_enable_process.isChecked():
            self.edit_frequency.setEnabled(self.radio_halftone.isChecked())
        else:
            self.edit_frequency.setEnabled(False)

    def _safe_float(self, text, default=0.0):
        try:
            return float(text)
        except ValueError:
            return default

    def _get_initial_dpi(self, qimage: QImage):
        dots_per_meter_x = qimage.dotsPerMeterX()
        dots_per_meter_y = qimage.dotsPerMeterY()
        if dots_per_meter_x > 0 and dots_per_meter_y > 0:
            dpi_x = dots_per_meter_x * 0.0254
            dpi_y = dots_per_meter_y * 0.0254
        else:
            dpi_x = dpi_y = 120.0
        return dpi_x, dpi_y

    def _update_output_dpi(self):
        if self.chk_resolution.isChecked():
            dpi_value = max(self._safe_float(self.edit_resolution.text(), default=self._dpi_x), 1.0)
            self.output_dpi = (dpi_value, dpi_value)
        else:
            self.output_dpi = (self._dpi_x, self._dpi_y)

    def get_processed_image(self):
        return self.processed_image

    def accept(self):
        self.processed_image = self.preview_image.copy()
        super().accept()

    def get_output_dpi(self):
        return self.output_dpi

