from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QSpinBox, QCheckBox, QPushButton, 
                             QRadioButton, QButtonGroup, QFrame, QWidget, QSlider, QMessageBox)
from PyQt5.QtCore import Qt, QPoint, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QPalette


def to_xy(pt):
    """Helper to convert QPointF/QPoint or tuple/list to (x, y) tuple."""
    try:
        if hasattr(pt, 'x') and hasattr(pt, 'y'):
            return (float(pt.x()), float(pt.y()))
        return (float(pt[0]), float(pt[1]))
    except Exception:
        return (0.0, 0.0)

def chaikin_smooth(points, iterations):
    """
    Chaikin's corner cutting algorithm for curve smoothing.
    
    Args:
        points: List of (x, y) tuples or lists (or QPointF).
        iterations: Number of smoothing iterations.
        
    Returns:
        List of smoothed points (as tuples).
    """
    if not points:
        return []

    if iterations <= 0:
        return [to_xy(p) for p in points]
        
    current_points = [to_xy(p) for p in points]
    
    for _ in range(iterations):
        if len(current_points) < 2:
            break
            
        new_points = []
        # Handle open curves
        new_points.append(current_points[0]) # Keep first point
        
        for i in range(len(current_points) - 1):
            p0 = current_points[i]
            p1 = current_points[i + 1]
            
            # QPoint = 0.75 * P0 + 0.25 * P1
            # RPoint = 0.25 * P0 + 0.75 * P1
            
            qx = 0.75 * p0[0] + 0.25 * p1[0]
            qy = 0.75 * p0[1] + 0.25 * p1[1]
            
            rx = 0.25 * p0[0] + 0.75 * p1[0]
            ry = 0.25 * p0[1] + 0.75 * p1[1]
            
            new_points.append((qx, qy))
            new_points.append((rx, ry))
            
        new_points.append(current_points[-1]) # Keep last point
        
        current_points = new_points
        
    return current_points

class SmoothCurveSimpleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("曲线平滑")
        self.setFixedSize(260, 140)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # 1. Label
        lbl_question = QLabel("是否进行曲线平滑?")
        lbl_question.setStyleSheet("font-size: 10pt;")
        layout.addWidget(lbl_question)
        
        # 2. Row: Label + ComboBox
        row_layout = QHBoxLayout()
        row_layout.setSpacing(10)
        
        lbl_level = QLabel("平滑程度:")
        lbl_level.setStyleSheet("font-size: 10pt;")
        
        self.combo_level = QComboBox()
        self.combo_level.setMaxVisibleItems(10)
        self.combo_level.setEditable(True)
        if self.combo_level.lineEdit():
             self.combo_level.lineEdit().setReadOnly(True)
        self.combo_level.addItems(["低", "中", "高", "自定义"])
        self.combo_level.setCurrentText("自定义")
        self.combo_level.setFixedHeight(22)
        
        row_layout.addWidget(lbl_level)
        row_layout.addWidget(self.combo_level)
        layout.addLayout(row_layout)
        
        # 3. Line Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #ccc;")
        layout.addWidget(line)
        
        # 4. Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        
        self.btn_ok.setFixedSize(75, 25)
        self.btn_cancel.setFixedSize(75, 25)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
    def get_level(self):
        return self.combo_level.currentText()

class CurvePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_points = []
        self.smoothed_points = []
        self.scale_factor = 1.0
        self.translate_offset = QPointF(0, 0)
        self.last_mouse_pos = QPoint()
        self.is_panning = False
        
        self.setMouseTracking(True)
        self.setBackgroundRole(QPalette.Base)
        self.setAutoFillBackground(True)
        
    def set_data(self, original, smoothed):
        # Normalize points to (x,y) tuples to be safe
        self.original_points = [to_xy(p) for p in original]
        self.smoothed_points = [to_xy(p) for p in smoothed]
        self.fit_to_view()
        self.update()

    def update_smoothed(self, smoothed):
        self.smoothed_points = [to_xy(p) for p in smoothed]
        self.update()

    def fit_to_view(self):
        # Calculate bounding box
        if not self.original_points and not self.smoothed_points:
            return
            
        all_points = self.original_points + self.smoothed_points
        
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        w = max_x - min_x
        h = max_y - min_y
        
        if w == 0 and h == 0:
            self.scale_factor = 1.0
            # Center on the point
            cx_screen = self.width() / 2.0
            cy_screen = self.height() / 2.0
            self.translate_offset = QPointF(cx_screen - min_x, cy_screen - min_y)
            self.update()
            return

        # Add padding
        margin = 40
        view_w = self.width() - margin
        view_h = self.height() - margin
        
        if view_w <= 10: view_w = 10
        if view_h <= 10: view_h = 10

        scale_w = view_w / w if w > 1e-9 else 1.0
        scale_h = view_h / h if h > 1e-9 else 1.0
        
        self.scale_factor = min(scale_w, scale_h)
        if self.scale_factor == 0: self.scale_factor = 1.0
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # Center in view
        cx_screen = self.width() / 2.0
        cy_screen = self.height() / 2.0
        
        self.translate_offset = QPointF(cx_screen - center_x * self.scale_factor, 
                                      cy_screen - center_y * self.scale_factor)
        self.update()

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Use a solid background
            painter.fillRect(self.rect(), Qt.white)
            
            # Draw grid
            self.draw_grid(painter)
            
            # Draw Original (Black)
            if self.original_points:
                painter.setPen(QPen(Qt.black, 1.0))
                path = QPainterPath()
                if len(self.original_points) > 0:
                    start = self.map_to_screen(self.original_points[0])
                    path.moveTo(start)
                    for p in self.original_points[1:]:
                        pt = self.map_to_screen(p)
                        path.lineTo(pt)
                painter.drawPath(path)
                
            # Draw Smoothed (Red)
            if self.smoothed_points:
                painter.setPen(QPen(Qt.red, 1.5))
                path = QPainterPath()
                if len(self.smoothed_points) > 0:
                    start = self.map_to_screen(self.smoothed_points[0])
                    path.moveTo(start)
                    for p in self.smoothed_points[1:]:
                        pt = self.map_to_screen(p)
                        path.lineTo(pt)
                painter.drawPath(path)
        except Exception:
            pass

    def map_to_screen(self, p):
        # p is (x,y) or [x,y]
        x = p[0] * self.scale_factor + self.translate_offset.x()
        y = p[1] * self.scale_factor + self.translate_offset.y()
        return QPointF(x, y)

    def draw_grid(self, painter):
        # Simple grid
        grid_step = 50
        painter.setPen(QPen(QColor(230, 230, 230), 1))
        
        for x in range(0, self.width(), grid_step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_step):
            painter.drawLine(0, y, self.width(), y)

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        factor = 1.1 if angle > 0 else 0.9
        
        mouse_pos = event.pos() 
        # current world pos under mouse
        wx = (mouse_pos.x() - self.translate_offset.x()) / self.scale_factor
        wy = (mouse_pos.y() - self.translate_offset.y()) / self.scale_factor
        
        self.scale_factor *= factor
        
        # new offset to keep world pos under mouse
        new_tx = mouse_pos.x() - wx * self.scale_factor
        new_ty = mouse_pos.y() - wy * self.scale_factor
        
        self.translate_offset = QPointF(new_tx, new_ty)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_panning = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.is_panning:
            delta = event.pos() - self.last_mouse_pos
            self.translate_offset += QPointF(delta)
            self.last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_panning = False
            self.setCursor(Qt.ArrowCursor)

class SmoothCurveCustomDialog(QDialog):
    def __init__(self, original_points, parent=None):
        super().__init__(parent)
        # Normalize points to (x,y) tuples immediately to prevent any QPointF indexing issues
        self.original_points = [to_xy(p) for p in original_points]
        self.smoothed_points = self.original_points[:]
        self.setWindowTitle("曲线平滑")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Preview
        self.preview = CurvePreviewWidget()
        layout.addWidget(self.preview, 1)
        
        # Controls Group
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(10, 10, 10, 10)
        
        # Row 1: Slider and Checkbox
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("平滑度"))
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(37) 
        row1.addWidget(self.slider)
        
        self.lbl_percent = QLabel("37%")
        self.lbl_percent.setFixedWidth(40)
        row1.addWidget(self.lbl_percent)
        
        self.chk_fit = QCheckBox("拟合平滑")
        self.chk_fit.setChecked(True)
        row1.addWidget(self.chk_fit)
        
        control_layout.addLayout(row1)
        
        # Line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        control_layout.addWidget(line)
        
        # Row 2: Buttons
        row2 = QHBoxLayout()
        self.btn_apply = QPushButton("应用")
        self.btn_full = QPushButton("满幅面")
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        
        row2.addStretch()
        row2.addWidget(self.btn_apply)
        row2.addWidget(self.btn_full)
        row2.addWidget(self.btn_ok)
        row2.addWidget(self.btn_cancel)
        
        control_layout.addLayout(row2)
        
        layout.addLayout(control_layout)
        
        # Connections
        self.slider.valueChanged.connect(self.on_slider_change)
        self.btn_full.clicked.connect(self.preview.fit_to_view)
        self.btn_apply.clicked.connect(self.do_apply_preview)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Initial setting
        self.preview.set_data(self.original_points, self.smoothed_points)
        # Apply initial smoothing based on default values
        self.do_apply_preview()
        # Fit to view after initial smoothing (though original points define bounds mostly, smoothing shrinks usually)
        self.preview.fit_to_view()

    def on_slider_change(self, value):
        self.lbl_percent.setText(f"{value}%")
        
    def do_apply_preview(self):
        val = self.slider.value()
        is_fit = self.chk_fit.isChecked()
        
        if not self.original_points:
            return

        if not is_fit:
            self.smoothed_points = self.original_points[:]
        else:
            # Map 0-100 to iterations (0 to 6)
            iterations = max(1, int(val / 16) + 1)
            if val == 0: iterations = 0
            if iterations > 6: iterations = 6
            
            self.smoothed_points = chaikin_smooth(self.original_points, iterations)
            
        self.preview.update_smoothed(self.smoothed_points)

    def get_result(self):
        # We assume the user wants the currently previewed result.
        # Ensure it's up to date with slider if they didn't click apply? 
        # Safest is to re-run apply logic.
        self.do_apply_preview()
        smooth_fit = self.chk_fit.isChecked()
        return self.smoothed_points, smooth_fit
