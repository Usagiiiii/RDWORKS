import os
import math
from PyQt5.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QLabel, QCheckBox, QGridLayout, QSizePolicy
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QPainterPath, QPolygonF
from PyQt5.QtCore import Qt, QSize, QPointF

class PreviewFileDialog(QFileDialog):
    def __init__(self, parent=None, caption="Import", directory="", filter=""):
        super().__init__(parent, caption, directory, filter)
        # Use native dialog false to customization
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        
        # Setup preview widget
        self.preview_widget = QWidget(self)
        self.preview_layout = QVBoxLayout(self.preview_widget)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(300, 300)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: black; border: 1px solid gray;")
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.chk_preview = QCheckBox("预览")
        self.chk_preview.setChecked(True)
        self.chk_preview.stateChanged.connect(self.toggle_preview)
        
        self.preview_layout.addWidget(self.preview_label)
        self.preview_layout.addWidget(self.chk_preview)
        
        # Add to main layout
        layout = self.layout()
        if isinstance(layout, QGridLayout):
            # QFileDialog layout is usually a grid. 
            # We want to put the preview pane on the right side.
            # Row 0: Navigation (Look in, buttons)
            # Row 1: Splitter (Sidebar + View) or just View
            # Row 2: File name / type
            # We will try to add it to the right of the main view.
            
            # Find the row count to know where to add or span
            # Usually we can look for the QListView or QTreeView in the layout to find where the main file list is
            
            # For simplicity in PyQt5's non-native dialog, simply appending to a new column often works
            col_count = layout.columnCount()
            # Span multiple rows to fill height
            layout.addWidget(self.preview_widget, 0, col_count, 4, 1)
            
        self.currentChanged.connect(self.on_current_changed)
        
    def toggle_preview(self, state):
        self.preview_label.setVisible(state == Qt.Checked)
        if state == Qt.Checked:
            # Refresh current selection
            files = self.selectedFiles()
            if files:
                self.on_current_changed(files[0])
            else:
                 # Start up might not have selection
                 pass
        
    def on_current_changed(self, path):
        if not self.chk_preview.isChecked():
            return
            
        if not path or not os.path.exists(path) or os.path.isdir(path):
            self.preview_label.clear()
            self.preview_label.setText("没有预览")
            self.preview_label.setStyleSheet("QLabel { background-color : black; color : gray; }")
            return
            
        lower_path = path.lower()
        pixmap = None
        
        try:
            if lower_path.endswith('.dxf'):
                from my_io.importers.import_dxf import import_dxf
                pixmap = self.render_paths(import_dxf(path))
            elif lower_path.endswith(('.plt', '.hpgl')):
                from my_io.importers.import_hpgl import import_hpgl
                pixmap = self.render_paths(import_hpgl(path))
            elif lower_path.endswith('.pdf'):
                from my_io.importers.import_pdf import import_pdf_or_ai
                pixmap = self.render_paths(import_pdf_or_ai(path))
            elif lower_path.endswith('.ai'):
                from my_io.importers.import_ai import import_ai
                paths, msg, img = import_ai(path)
                if paths:
                    pixmap = self.render_paths(paths)
                elif img:
                    from utils.import_utils import pil_to_qpixmap
                    pixmap = pil_to_qpixmap(img)
            elif lower_path.endswith(('.nc', '.gcode', '.ngc')):
                 from my_io.importers.import_gcode import import_gcode
                 pixmap = self.render_paths(import_gcode(path))
            elif lower_path.endswith('.svg'):
                 from my_io.importers.import_svg import import_svg
                 pixmap = self.render_paths(import_svg(path))
            elif lower_path.endswith(('.bmp', '.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff', '.pcx', '.tga', '.wbmp', '.ico', '.cur')):
                 pixmap = QPixmap(path)
            
            if pixmap and not pixmap.isNull():
                # Scale to fit label
                w = self.preview_label.width()
                h = self.preview_label.height()
                if w < 10 or h < 10: 
                    w, h = 300, 300
                scaled_pixmap = pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(scaled_pixmap)
                self.preview_label.setStyleSheet("background-color: black; border: 1px solid gray;")
            else:
                self.preview_label.setText("不支持预览")
                self.preview_label.setStyleSheet("QLabel { background-color : black; color : white; }")
                
        except Exception as e:
            self.preview_label.setText("预览出错")
            self.preview_label.setStyleSheet("QLabel { background-color : black; color : red; }")
            # print(f"Preview Error for {path}: {e}")

    def render_paths(self, paths):
        if not paths: return None
        
        # Calculate bounds
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        has_points = False
        for path in paths:
            for pt in path:
                if len(pt) >= 2:
                    x, y = pt[0], pt[1]
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if x > max_x: max_x = x
                    if y > max_y: max_y = y
                    has_points = True
                
        if not has_points: return None
        
        width = max_x - min_x
        height = max_y - min_y
        
        if width == 0: width = 1.0
        if height == 0: height = 1.0
        
        # Create image
        img_size = 500 # Internal resolution
        image = QImage(img_size, img_size, QImage.Format_ARGB32)
        image.fill(Qt.black)
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate scale to fit
        margin = 10
        view_w = img_size - 2 * margin
        view_h = img_size - 2 * margin
        
        scale_x = view_w / width
        scale_y = view_h / height
        scale = min(scale_x, scale_y)
        
        # Center
        content_w = width * scale
        content_h = height * scale
        
        offset_x = margin + (view_w - content_w) / 2
        offset_y = margin + (view_h - content_h) / 2
        
        pen = QPen(Qt.white)
        # Always use a thin visible line
        pen.setWidthF(1.5)
        painter.setPen(pen)
        
        for path_pts in paths:
            if not path_pts: continue
            
            qpoly = QPolygonF()
            for pt in path_pts:
                if len(pt) < 2: continue
                # Invert Y for display if needed, but for simple preview direct mapping is usually fine
                # Most graphics formats have Y-up or Y-down, but consistency within the file matters most.
                # To make it "upright" relative to screen Y-down:
                # If file is Y-up (like DXF generally), we might want to flip.
                # Here we just map to fit.
                
                px = (pt[0] - min_x) * scale + offset_x
                py = (pt[1] - min_y) * scale + offset_y
                qpoly.append(QPointF(px, py))
            
            if qpoly.count() > 1:
                painter.drawPolyline(qpoly)
            elif qpoly.count() == 1:
                painter.drawPoint(qpoly.first())
                
        painter.end()
        return QPixmap.fromImage(image)
