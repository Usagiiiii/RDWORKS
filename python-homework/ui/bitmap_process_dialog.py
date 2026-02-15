from PyQt5.QtCore import Qt, QBuffer, QIODevice, QSize, QRectF
from PyQt5.QtGui import QImage, QPainter, QPixmap, QTransform, QColor, QPen, QPainterPath
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
    QGridLayout,
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
        self._pixmap_item = None
        self._overlay_items = []
        self._zoom = 0
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

    def set_pixmap(self, pixmap: QPixmap, fit=True):
        self._scene.clear()
        self._overlay_items = []
        self._pixmap_item = self._scene.addPixmap(pixmap)
        # 显式转换 QRect 为 QRectF
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        if fit:
            self.fit_to_view()
        self._zoom = 0

    def set_contour_overlay(self, contours, color=None, width=1.6):
        for item in self._overlay_items:
            try:
                self._scene.removeItem(item)
            except Exception:
                pass
        self._overlay_items = []

        if not contours:
            return

        pen = QPen(color or QColor(170, 70, 255))
        pen.setCosmetic(True)
        pen.setWidthF(float(width))
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)

        for contour in contours:
            if not contour or len(contour) < 2:
                continue

            path = QPainterPath()
            x0, y0 = contour[0]
            path.moveTo(float(x0), float(y0))
            for x, y in contour[1:]:
                path.lineTo(float(x), float(y))

            item = self._scene.addPath(path, pen)
            item.setZValue(10)
            self._overlay_items.append(item)

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
        self.resize(1160, 700)
        self.setMinimumSize(1040, 640)
        self.setStyleSheet(
            """
            QCheckBox::indicator, QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            """
        )

        if self.target_item and hasattr(self.target_item, 'pixmap'):
            qimage = self.target_item.pixmap().toImage()
        else:
            # 创建默认空白图
            qimage = QImage(800, 600, QImage.Format_ARGB32)
            qimage.fill(Qt.white)

        buffer = QBuffer()
        buffer.open(QIODevice.ReadWrite)
        qimage.save(buffer, "PNG")
        buffer.seek(0)

        try:
            pil_image = Image.open(io.BytesIO(buffer.data())).convert("RGBA")
        except Exception:
            pil_image = Image.new("RGBA", (100, 100), (255, 255, 255, 255))

        self.original_image = pil_image
        self.preview_image = pil_image.copy()
        self.processed_image = pil_image.copy()
        self.extracted_contours = []
        self._contour_overlay_color = QColor(170, 70, 255)
        self._contour_sensitivity_default = 55
        self._contour_min_area_default = 30

        self._dpi_x, self._dpi_y = self._get_initial_dpi(qimage)
        self.output_dpi = (self._dpi_x, self._dpi_y)

        self._build_ui()
        self._update_info_labels()
        self._update_value_labels()
        self._update_contour_value_labels()
        self._update_output_dpi()
        self.update_preview(force_fit=True)

    # ------------------------- UI construction -------------------------
    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.preview_view = PreviewGraphicsView(self)
        self.preview_view.setMinimumSize(QSize(580, 400))
        main_layout.addWidget(self.preview_view, 1)

        side_panel_container = QWidget(self)
        side_panel_container.setMinimumWidth(400)
        side_panel_container.setMaximumWidth(440)
        side_panel = QVBoxLayout(side_panel_container)
        side_panel.setSpacing(6)
        side_panel.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(side_panel_container, 0)

        # Info box
        info_box = QGroupBox("图像信息")
        form = QFormLayout(info_box)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(5)
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
        resolution_label = QLabel("分辨率(像素/英寸)")
        resolution_label.setMinimumWidth(130)
        resolution_row.addWidget(resolution_label)
        self.edit_resolution = QLineEdit("120")
        self.edit_resolution.setEnabled(False)
        self.edit_resolution.setFixedWidth(84)
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
        self.chk_enable_process.setMinimumHeight(24)
        process_layout.addWidget(self.chk_enable_process)
        process_layout.addSpacing(2)

        self.process_button_group = QButtonGroup(self)
        self.radio_halftone = QRadioButton("网点图")
        self.radio_scatter = QRadioButton("散点图")
        self.radio_bw = QRadioButton("黑白图")
        self.radio_gray = QRadioButton("灰度图")
        self.radio_sharpen = QRadioButton("锐化")

        all_radios = [self.radio_halftone, self.radio_scatter, self.radio_bw, self.radio_gray, self.radio_sharpen]
        for idx, radio in enumerate(all_radios):
            self.process_button_group.addButton(radio, idx)
            radio.setEnabled(False)
            radio.toggled.connect(self._on_adjustment_changed)
            radio.setMinimumHeight(24)

        radio_grid = QGridLayout()
        radio_grid.setHorizontalSpacing(18)
        radio_grid.setVerticalSpacing(9)
        radio_grid.addWidget(self.radio_halftone, 0, 0)
        radio_grid.addWidget(self.radio_scatter, 0, 1)
        radio_grid.addWidget(self.radio_bw, 1, 0)
        radio_grid.addWidget(self.radio_gray, 1, 1)
        radio_grid.addWidget(self.radio_sharpen, 2, 0)
        radio_grid.setColumnStretch(0, 1)
        radio_grid.setColumnStretch(1, 1)
        process_layout.addLayout(radio_grid)
        process_layout.addSpacing(1)

        frequency_row = QHBoxLayout()
        frequency_label = QLabel("频率(线/英寸):")
        frequency_label.setMinimumWidth(130)
        frequency_row.addWidget(frequency_label)
        self.edit_frequency = QLineEdit("1")
        self.edit_frequency.setEnabled(False)
        self.edit_frequency.setFixedWidth(84)
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
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(6)
        self.btn_apply_preview = QPushButton("应用到预览")
        self.btn_apply_preview.clicked.connect(lambda: self.update_preview(fit_to_view=False))
        self.btn_apply_preview.setMinimumHeight(24)
        self.btn_apply_original = QPushButton("应用到原图")
        self.btn_apply_original.clicked.connect(self._apply_to_original)
        self.btn_apply_original.setMinimumHeight(24)
        self.btn_apply_preview.setMinimumWidth(84)
        self.btn_apply_original.setMinimumWidth(84)
        actions_row.addWidget(self.btn_apply_preview)
        actions_row.addWidget(self.btn_apply_original)
        side_panel.addLayout(actions_row)

        contour_group = QGroupBox("轮廓提取参数")
        contour_layout = QVBoxLayout(contour_group)
        contour_layout.setContentsMargins(6, 6, 6, 6)
        contour_layout.setSpacing(4)

        sens_row, self.slider_contour_sensitivity, self.label_contour_sensitivity_value, self.btn_reset_contour_sensitivity = (
            self._create_param_slider_row(
                "轮廓灵敏度:",
                0,
                100,
                self._contour_sensitivity_default,
            )
        )
        contour_layout.addLayout(sens_row)

        min_area_row, self.slider_contour_min_area, self.label_contour_min_area_value, self.btn_reset_contour_min_area = (
            self._create_param_slider_row(
                "最小面积:",
                0,
                100,
                self._contour_min_area_default,
            )
        )
        contour_layout.addLayout(min_area_row)

        self.slider_contour_sensitivity.valueChanged.connect(self._on_contour_params_changed)
        self.slider_contour_min_area.valueChanged.connect(self._on_contour_params_changed)
        self.btn_reset_contour_sensitivity.clicked.connect(
            lambda: self.slider_contour_sensitivity.setValue(self._contour_sensitivity_default)
        )
        self.btn_reset_contour_min_area.clicked.connect(
            lambda: self.slider_contour_min_area.setValue(self._contour_min_area_default)
        )
        side_panel.addWidget(contour_group)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setMaximumHeight(6)
        side_panel.addWidget(separator)


        # Footer buttons
        footer_row_top = QHBoxLayout()
        footer_row_top.setContentsMargins(0, 0, 0, 0)
        self.btn_extract = QPushButton("提取轮廓")
        self.btn_extract.clicked.connect(self._extract_contours)
        self.btn_extract.setMinimumHeight(26)
        footer_row_top.addWidget(self.btn_extract)
        side_panel.addLayout(footer_row_top)

        footer_row_bottom = QHBoxLayout()
        footer_row_bottom.setContentsMargins(0, 0, 0, 0)
        footer_row_bottom.setSpacing(6)
        self.btn_fit = QPushButton("满幅面")
        self.btn_fit.clicked.connect(self.preview_view.fit_to_view)
        self.btn_save = QPushButton("另存图片")
        self.btn_save.clicked.connect(self._save_current_image)
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)

        for btn in [self.btn_fit, self.btn_save, self.btn_ok, self.btn_cancel]:
            btn.setMinimumHeight(26)
            btn.setMinimumWidth(74)
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
        layout.setSpacing(6)
        name_label = QLabel(label_text)
        name_label.setMinimumWidth(58)
        layout.addWidget(name_label)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.setSingleStep(1)
        slider.setPageStep(10)
        slider.setMinimumWidth(150)
        layout.addWidget(slider, 1)

        value_label = QLabel("0.0%")
        value_label.setFixedWidth(56)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(value_label)

        reset_btn = QPushButton("归零")
        reset_btn.setMinimumWidth(62)
        reset_btn.setMinimumHeight(26)
        layout.addWidget(reset_btn)

        return layout, value_label, reset_btn

    def _create_param_slider_row(self, label_text, min_value, max_value, default_value):
        layout = QHBoxLayout()
        layout.setSpacing(6)
        name_label = QLabel(label_text)
        name_label.setMinimumWidth(82)
        layout.addWidget(name_label)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(int(min_value), int(max_value))
        slider.setValue(int(default_value))
        slider.setSingleStep(1)
        slider.setPageStep(5)
        slider.setMinimumWidth(120)
        layout.addWidget(slider, 1)

        value_label = QLabel(str(default_value))
        value_label.setFixedWidth(88)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(value_label)

        reset_btn = QPushButton("默认")
        reset_btn.setMinimumWidth(62)
        reset_btn.setMinimumHeight(26)
        layout.addWidget(reset_btn)
        return layout, slider, value_label, reset_btn

    # ------------------------- Event handlers -------------------------
    def _reset_slider(self, slider):
        slider.setValue(0)

    def _on_adjustment_changed(self):
        self._clear_extracted_contours()
        self._update_value_labels()
        self._update_output_dpi()
        self.update_preview(fit_to_view=False)

    def _on_contour_params_changed(self):
        self._update_contour_value_labels()
        self._clear_extracted_contours()

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
        self.preview_view.set_contour_overlay(self.extracted_contours, color=self._contour_overlay_color)

    def _clear_extracted_contours(self):
        if self.extracted_contours:
            self.extracted_contours = []
        if hasattr(self, 'preview_view'):
            self.preview_view.set_contour_overlay([], color=self._contour_overlay_color)

    def _contour_sensitivity_ratio(self):
        slider = getattr(self, 'slider_contour_sensitivity', None)
        if slider is None:
            return 0.55
        return max(0.0, min(1.0, slider.value() / 100.0))

    def _contour_min_area_ratio(self):
        slider = getattr(self, 'slider_contour_min_area', None)
        if slider is None:
            slider_ratio = self._contour_min_area_default / 100.0
        else:
            slider_ratio = slider.value() / 100.0
        return 0.00005 + (slider_ratio * slider_ratio) * 0.0035

    def _contour_min_area_pixels(self):
        width, height = self.original_image.size if isinstance(self.original_image, Image.Image) else (1, 1)
        image_area = float(max(1, width * height))
        return int(max(20.0, image_area * self._contour_min_area_ratio()))

    def _update_contour_value_labels(self):
        if not hasattr(self, 'slider_contour_sensitivity'):
            return
        self.label_contour_sensitivity_value.setText(f"{self.slider_contour_sensitivity.value()}%")
        self.label_contour_min_area_value.setText(f"{self._contour_min_area_pixels()} px²")

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

        rgba_image = self.preview_image.convert("RGBA")
        rgba_array = np.array(rgba_image)
        gray = cv2.cvtColor(rgba_array, cv2.COLOR_RGBA2GRAY)
        alpha = rgba_array[:, :, 3]

        mask = self._build_binary_contour_mask(gray, alpha, cv2)
        extracted = self._extract_contours_from_mask(mask, cv2)

        # 二值化失败时回退到自动阈值 Canny，避免漏掉弱边缘。
        if not extracted:
            edge_mask = self._build_edge_contour_mask(gray, cv2)
            extracted = self._extract_contours_from_mask(edge_mask, cv2)

        self.extracted_contours = extracted
        self.preview_view.set_contour_overlay(self.extracted_contours, color=self._contour_overlay_color)
        QMessageBox.information(self, "提取轮廓", f"共提取 {len(extracted)} 条轮廓。")

    def _build_binary_contour_mask(self, gray, alpha_channel, cv2):
        height, width = gray.shape[:2]
        image_area = float(max(1, height * width))
        sensitivity = self._contour_sensitivity_ratio()
        min_area_ratio = self._contour_min_area_ratio()
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(blur)
        except Exception:
            enhanced = blur

        _, otsu_inv = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        adaptive_inv = cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            2,
        )

        mask = otsu_inv
        fg_pixels = cv2.countNonZero(mask)
        low_fg_ratio = 0.0015 + (1.0 - sensitivity) * 0.003
        high_fg_ratio = 0.52 + sensitivity * 0.18
        if fg_pixels < image_area * low_fg_ratio:
            mask = cv2.bitwise_or(mask, adaptive_inv)
        elif fg_pixels > image_area * high_fg_ratio:
            mask = cv2.bitwise_and(mask, adaptive_inv)

        if alpha_channel is not None and np.min(alpha_channel) < 250:
            _, alpha_mask = cv2.threshold(alpha_channel, 8, 255, cv2.THRESH_BINARY)
            mask = cv2.bitwise_or(mask, self._normalize_foreground_mask(alpha_mask, cv2))

        mask = self._normalize_foreground_mask(mask, cv2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        close_iterations = 1 + int((1.0 - sensitivity) * 1.2)
        open_iterations = 1 + int((1.0 - sensitivity) * 0.8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=close_iterations)
        mask = self._filter_foreground_components(
            mask,
            cv2,
            min_area_ratio=max(0.00005, min_area_ratio * 0.8),
            max_components=int(round(6 + sensitivity * 12)),
            border_area_ratio=max(0.006, 0.02 - sensitivity * 0.01),
            relative_area_ratio=max(0.006, 0.03 - sensitivity * 0.02),
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=open_iterations)
        return mask

    def _build_edge_contour_mask(self, gray, cv2):
        sensitivity = self._contour_sensitivity_ratio()
        min_area_ratio = self._contour_min_area_ratio()
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        median = float(np.median(blur))
        sigma = 0.45 - sensitivity * 0.22
        low = int(max(0, (1.0 - sigma) * median))
        high = int(min(255, (1.0 + sigma) * median))
        if high - low < 20:
            low = int(28 + (1.0 - sensitivity) * 42)
            high = int(90 + (1.0 - sensitivity) * 130)

        edges = cv2.Canny(blur, low, high, L2gradient=True)
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
        edges = self._filter_foreground_components(
            edges,
            cv2,
            min_area_ratio=max(0.00005, min_area_ratio * 0.5),
            max_components=int(round(5 + sensitivity * 10)),
            border_area_ratio=max(0.004, 0.012 - sensitivity * 0.006),
            relative_area_ratio=max(0.005, 0.014 - sensitivity * 0.007),
        )
        return edges

    def _normalize_foreground_mask(self, mask, cv2):
        total_pixels = float(mask.shape[0] * mask.shape[1])
        if total_pixels <= 0:
            return mask

        foreground_ratio = cv2.countNonZero(mask) / total_pixels
        if 0.65 < foreground_ratio < 0.995:
            return cv2.bitwise_not(mask)
        return mask

    def _filter_foreground_components(
        self,
        mask,
        cv2,
        min_area_ratio=0.0002,
        max_components=24,
        border_area_ratio=0.015,
        relative_area_ratio=0.01,
    ):
        if mask is None or mask.size == 0:
            return mask

        mask = np.ascontiguousarray(mask, dtype=np.uint8)
        height, width = mask.shape[:2]
        image_area = float(max(1, height * width))
        min_component_area = max(64.0, image_area * float(min_area_ratio))

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return mask

        components = []
        for label in range(1, num_labels):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            w = int(stats[label, cv2.CC_STAT_WIDTH])
            h = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < min_component_area:
                continue

            touches_border = x <= 1 or y <= 1 or (x + w) >= (width - 1) or (y + h) >= (height - 1)
            if touches_border and area < image_area * float(border_area_ratio):
                continue

            components.append((area, label))

        if not components:
            return np.zeros_like(mask, dtype=np.uint8)

        components.sort(key=lambda item: item[0], reverse=True)
        largest = float(components[0][0])
        area_floor = max(min_component_area, largest * float(relative_area_ratio))
        keep_limit = max(1, int(max_components))

        keep_labels = []
        for area, label in components:
            if area < area_floor:
                continue
            keep_labels.append(label)
            if len(keep_labels) >= keep_limit:
                break

        if not keep_labels:
            keep_labels = [components[0][1]]

        filtered = np.zeros_like(mask, dtype=np.uint8)
        for label in keep_labels:
            filtered[labels == label] = 255
        return filtered

    def _extract_contours_from_mask(self, mask, cv2):
        if mask is None or mask.size == 0:
            return []

        sensitivity = self._contour_sensitivity_ratio()
        mask = np.ascontiguousarray(mask, dtype=np.uint8)
        height, width = mask.shape[:2]
        image_area = float(width * height)
        min_area = float(max(self._contour_min_area_pixels(), image_area * 0.00005))
        min_perimeter = max(40.0, float(np.sqrt(min_area)) * (2.6 - sensitivity * 0.8))
        max_contours = int(round(8 + sensitivity * 40))

        contours_info = cv2.findContours(mask.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        contours = contours_info[0] if len(contours_info) == 2 else contours_info[1]

        candidates = []
        for cnt in contours:
            if cnt is None or len(cnt) < 3:
                continue

            area = abs(cv2.contourArea(cnt))
            perimeter = cv2.arcLength(cnt, True)
            if area < min_area and perimeter < min_perimeter:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if w <= 1 or h <= 1:
                continue

            touches_full_border = x <= 1 and y <= 1 and (x + w) >= (width - 1) and (y + h) >= (height - 1)
            if touches_full_border and area > (image_area * 0.98):
                continue

            epsilon = max(0.8, perimeter * max(0.0012, 0.0032 - sensitivity * 0.0018))
            approx = cv2.approxPolyDP(cnt, epsilon, closed=True)
            if approx is None or len(approx) < 3:
                approx = cnt

            points = [(float(p[0][0]), float(p[0][1])) for p in approx]
            if len(points) < 2:
                continue
            if points[0] != points[-1]:
                points.append(points[0])

            candidates.append((area, (x, y, w, h), points))

        candidates.sort(key=lambda item: item[0], reverse=True)
        extracted = []
        accepted_boxes = []
        for _, bbox, points in candidates:
            x, y, w, h = bbox
            duplicate = any(
                abs(x - bx) <= 1 and abs(y - by) <= 1 and abs(w - bw) <= 1 and abs(h - bh) <= 1
                for bx, by, bw, bh in accepted_boxes
            )
            if duplicate:
                continue
            accepted_boxes.append(bbox)
            extracted.append(points)
            if len(extracted) >= max_contours:
                break

        return extracted

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

