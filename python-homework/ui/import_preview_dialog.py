import os
import math
import time
from PyQt5.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QLabel, QCheckBox, QGridLayout, QSizePolicy, QFileSystemModel, QComboBox
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QPolygonF
from PyQt5.QtCore import Qt, QSize, QPointF, QThread, pyqtSignal, QTimer

class PreviewWorker(QThread):
    finished_signal = pyqtSignal(str, object, str) # path, QImage/QPixmap, error_msg

    def __init__(self, path, width, height, parent=None):
        super().__init__(parent)
        self.path = path
        self.width = width
        self.height = height

    def run(self):
        try:
            image = self.load_preview(self.path)
            self.finished_signal.emit(self.path, image, "")
        except Exception as e:
            self.finished_signal.emit(self.path, None, str(e))

    def load_preview(self, path):
        lower_path = path.lower()
        
        # 针对位图直接加载 QImage
        if lower_path.endswith(('.bmp', '.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff', '.pcx', '.tga', '.wbmp', '.ico', '.cur')):
             return QImage(path)

        pixmap = None
        paths = None
        
        if lower_path.endswith('.dxf'):
            from my_io.importers.import_dxf import import_dxf
            paths = import_dxf(path)
        elif lower_path.endswith(('.plt', '.hpgl')):
            from my_io.importers.import_hpgl import import_hpgl
            paths = import_hpgl(path)
        elif lower_path.endswith('.pdf'):
            from my_io.importers.import_pdf import import_pdf_or_ai
            paths = import_pdf_or_ai(path)
        elif lower_path.endswith('.ai'):
            from my_io.importers.import_ai import import_ai
            paths, msg, img = import_ai(path)
            if img:
                # PIL Image to QImage
                return self.pil_to_qimage(img)
        elif lower_path.endswith(('.nc', '.gcode', '.ngc')):
             from my_io.importers.import_gcode import import_gcode
             paths = import_gcode(path)
        elif lower_path.endswith('.svg'):
             from my_io.importers.import_svg import import_svg
             paths = import_svg(path)

        if paths:
            return self.render_paths(paths)
        
        return None

    def pil_to_qimage(self, im):
        if im.mode == "RGB":
            data = im.tobytes("raw", "RGB")
            qimg = QImage(data, im.size[0], im.size[1], im.size[0] * 3, QImage.Format_RGB888)
        elif im.mode == "RGBA":
            data = im.tobytes("raw", "BGRA")
            qimg = QImage(data, im.size[0], im.size[1], im.size[0] * 4, QImage.Format_ARGB32)
        elif im.mode == "L":
            data = im.tobytes("raw", "L")
            qimg = QImage(data, im.size[0], im.size[1], im.size[0], QImage.Format_Grayscale8)
        else:
            im = im.convert("RGBA")
            data = im.tobytes("raw", "BGRA")
            qimg = QImage(data, im.size[0], im.size[1], im.size[0] * 4, QImage.Format_ARGB32)
        return qimg.copy()

    def render_paths(self, paths):
        if not paths: return None
        
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
        
        # Use white lines on dark background
        img_size = 500
        image = QImage(img_size, img_size, QImage.Format_ARGB32)
        image.fill(QColor(43, 43, 43)) # Match background
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        
        margin = 10
        view_w = img_size - 2 * margin
        view_h = img_size - 2 * margin
        
        scale = min(view_w / width, view_h / height)
        
        content_w = width * scale
        content_h = height * scale
        
        offset_x = margin + (view_w - content_w) / 2
        offset_y = margin + (view_h - content_h) / 2
        
        pen = QPen(Qt.white)
        pen.setWidthF(1.5)
        painter.setPen(pen)
        
        for path_pts in paths:
            if not path_pts: continue
            qpoly = QPolygonF()
            for pt in path_pts:
                px = (pt[0] - min_x) * scale + offset_x
                py = (pt[1] - min_y) * scale + offset_y
                qpoly.append(QPointF(px, py))
            if qpoly.count() > 1:
                painter.drawPolyline(qpoly)
            elif qpoly.count() == 1:
                painter.drawPoint(qpoly.first())
                
        painter.end()
        return image


class PreviewFileDialog(QFileDialog):
    def __init__(self, parent=None, caption="Import", directory="", filter=""):
        super().__init__(parent, caption, directory, filter)
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        
        # Customize internal filter combobox
        self._customize_comboboxes()
        
        # Style adjustments to make it look cleaner
        self.setViewMode(QFileDialog.Detail)
        
        # Setup preview widget
        self.preview_widget = QWidget(self)
        self.preview_layout = QVBoxLayout(self.preview_widget)
        self.preview_layout.setContentsMargins(5, 0, 5, 0)
        
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(300, 300)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;") # Dark but not pitch black
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.chk_preview = QCheckBox("预览")
        self.chk_preview.setChecked(True)
        self.chk_preview.stateChanged.connect(self.toggle_preview)
        
        self.preview_layout.addWidget(self.preview_label)
        self.preview_layout.addWidget(self.chk_preview)
        
        # Add to layout
        layout = self.layout()
        if isinstance(layout, QGridLayout):
            col_count = layout.columnCount()
            layout.addWidget(self.preview_widget, 0, col_count, 4, 1)
            
        self.currentChanged.connect(self.on_current_changed)
        
        # Async preview loading
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200) # 200ms debounce
        self.preview_timer.timeout.connect(self.start_preview_loading)
        
        self.current_worker = None
        self.target_path = None

    def _customize_comboboxes(self):
        # Locate the file type combobox and apply user requested styles
        # Typically named 'fileTypeCombo' in Qt's non-native dialog
        combos = self.findChildren(QComboBox)
        for combo in combos:
            # We target filtering comboboxes specifically or filter by name if needed.
            # Applying to filters combo seems to be the request.
            # objectName might be 'fileTypeCombo' or similar on various Qt versions.
            if "fileType" in combo.objectName() or "filter" in combo.objectName().lower():
                combo.setMaxVisibleItems(10)
                combo.setEditable(True)
                if combo.lineEdit():
                    combo.lineEdit().setReadOnly(True)
            # Fallback: if we can't determine by name, we might check content, 
            # but usually finding by name is safest or just applying to the last one (often filters)
            # However, simpler to apply to all or check behavior.
            # Let's try to be specific first. If not found, check the one that is NOT 'lookInCombo'
            elif "lookIn" not in combo.objectName() and "directory" not in combo.objectName():
                 # This is likely the filter combo or filename combo (if it was a combo)
                 combo.setMaxVisibleItems(10)
                 combo.setEditable(True)
                 if combo.lineEdit():
                    combo.lineEdit().setReadOnly(True)
        
    def toggle_preview(self, state):
        self.preview_label.setVisible(state == Qt.Checked)
        if state == Qt.Checked:
            files = self.selectedFiles()
            if files:
                self.on_current_changed(files[0])
        elif self.current_worker and self.current_worker.isRunning():
             # Stop loading if preview disabled
             pass 
        
    def on_current_changed(self, path):
        if not self.chk_preview.isChecked():
            return
            
        if not path or not os.path.exists(path) or os.path.isdir(path):
            self.preview_label.clear()
            self.preview_label.setText("没有预览")
            self.preview_label.setStyleSheet("QLabel { background-color : #2b2b2b; color : gray; }")
            return
            
        self.target_path = path
        # Show loading indicator
        self.preview_label.setText("加载中...")
        self.preview_label.setStyleSheet("QLabel { background-color : #2b2b2b; color : yellow; }")
        
        # Debounce
        self.preview_timer.start()
        
    def start_preview_loading(self):
        if not self.target_path: return
        
        # Cancel previous worker if running (we can't force kill but we can ignore)
        if self.current_worker and self.current_worker.isRunning():
             try:
                self.current_worker.finished_signal.disconnect()
             except:
                pass
        
        w = self.preview_label.width()
        h = self.preview_label.height()
        if w < 10 or h < 10: w, h = 300, 300
        
        self.current_worker = PreviewWorker(self.target_path, w, h)
        self.current_worker.finished_signal.connect(self.on_preview_ready)
        self.current_worker.start()
        
    def on_preview_ready(self, path, image, error):
        # Check if this result is still relevant
        if path != self.target_path:
            return
            
        if error:
            self.preview_label.setText("预览出错") # Simple error text
            self.preview_label.setStyleSheet("QLabel { background-color : #2b2b2b; color : red; }")
            return
            
        if image and not image.isNull():
            # Convert to pixmap on main thread
            pixmap = QPixmap.fromImage(image)
            
            w = self.preview_label.width()
            h = self.preview_label.height()
            if w < 10 or h < 10: w, h = 300, 300
            
            scaled = pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
        else:
            self.preview_label.setText("不支持预览")
            self.preview_label.setStyleSheet("QLabel { background-color : #2b2b2b; color : white; }")
