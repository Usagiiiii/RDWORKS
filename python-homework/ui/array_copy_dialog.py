from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QGridLayout, QGroupBox, 
                             QWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPixmap
import os

class IconButton(QPushButton):
    def __init__(self, icon_paths, parent=None):
        super().__init__(parent)
        self.icon_paths = icon_paths
        self.current_index = 0
        self.setFixedSize(38, 38) # Reduced size to fit tighter
        # Increase icon size ratio to reduce padding (0.8 -> 0.95)
        self.setIconSize(self.size() * 0.95)
        self.setStyleSheet("QPushButton { border: 1px solid #ccc; background-color: white; border-radius: 4px; margin: 0px; padding: 0px; } QPushButton:hover { border: 1px solid #999; }")
        self.update_icon()
        self.clicked.connect(self.rotate_icon)

    def update_icon(self):
        if self.icon_paths:
            path = self.icon_paths[self.current_index]
            if os.path.exists(path):
                self.setIcon(QIcon(path))
            else:
                pass

    def rotate_icon(self):
        self.current_index = (self.current_index + 1) % len(self.icon_paths)
        self.update_icon()
        
    def get_current_index(self):
        return self.current_index

class FillDialog(QDialog):
    def __init__(self, default_w=1200, default_h=800, parent=None):
        super().__init__(parent)
        self.setWindowTitle("布满幅面设置")
        self.setFixedSize(250, 120) # More compact
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        grid = QGridLayout()
        grid.setVerticalSpacing(5)
        
        self.x_width_edit = QLineEdit(str(default_w))
        self.y_width_edit = QLineEdit(str(default_h))
        
        grid.addWidget(QLabel("X幅面(mm):"), 0, 0)
        grid.addWidget(self.x_width_edit, 0, 1)
        grid.addWidget(QLabel("Y幅面(mm):"), 1, 0)
        grid.addWidget(self.y_width_edit, 1, 1)
        
        layout.addLayout(grid)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
    def get_values(self):
        try:
            return float(self.x_width_edit.text()), float(self.y_width_edit.text())
        except ValueError:
            return 0.0, 0.0

class ArrayCopyDialog(QDialog):
    def __init__(self, selected_item_size=(0, 0), canvas_size=(1200, 800), parent=None):
        super().__init__(parent)
        self.setWindowTitle("阵列复制")
        # Reduced height because we remove stretch and compact items
        self.setFixedSize(420, 150) 
        self.selected_item_size = selected_item_size 
        self.canvas_size = canvas_size
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Grid Layout
        grid = QGridLayout()
        grid.setHorizontalSpacing(5) 
        grid.setVerticalSpacing(5)
        grid.setContentsMargins(0, 0, 0, 0)
        
        # 1. Initialize Controls FIRST
        self.x_count = QLineEdit("1")
        self.y_count = QLineEdit("1")
        self.x_interval = QLineEdit("0.000")
        self.y_interval = QLineEdit("0.000")
        
        # Resolve absolute paths for images
        import os
        base_dir = os.path.dirname(os.path.dirname(__file__)) # python-homework/
        
        img_paths_1 = [os.path.join(base_dir, f"{i}.png") for i in range(1, 5)]
        img_paths_2 = [os.path.join(base_dir, f"{i}.png") for i in range(5, 9)]
        
        self.btn_direction = IconButton(img_paths_1)
        self.btn_direction.setToolTip("阵列方向")
        self.btn_order = IconButton(img_paths_2)
        self.btn_order.setToolTip("切割顺序")

        # 2. Add to Layout
        # Row 0
        grid.addWidget(QLabel("X个数:"), 0, 0, Qt.AlignRight)
        grid.addWidget(self.x_count, 0, 1)
        grid.addWidget(QLabel("X间隔:"), 0, 2, Qt.AlignRight)
        grid.addWidget(self.x_interval, 0, 3)
        # Span buttons across 2 rows. Col 4 and Col 5
        grid.addWidget(self.btn_direction, 0, 4, 2, 1, Qt.AlignHCenter)
        grid.addWidget(self.btn_order, 0, 5, 2, 1, Qt.AlignHCenter)
        
        # Set column stretch to make buttons sit tight but input expand?
        # Actually standard behavior is usually fine, but let's ensure spacing is tight
        # grid.setColumnStretch(1, 1)
        # grid.setColumnStretch(3, 1)
        
        # Row 1
        grid.addWidget(QLabel("Y个数:"), 1, 0, Qt.AlignRight)
        grid.addWidget(self.y_count, 1, 1)
        grid.addWidget(QLabel("Y间隔:"), 1, 2, Qt.AlignRight)
        grid.addWidget(self.y_interval, 1, 3)

        main_layout.addLayout(grid)
        
        # Removed addStretch to close the gap at the bottom
        # main_layout.addStretch() 
        main_layout.addSpacing(10) # Just a small gap
        
        # Bottom Buttons
        hbox = QHBoxLayout()
        self.btn_fill = QPushButton("布满...")
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        
        hbox.addWidget(self.btn_fill)
        hbox.addStretch()
        hbox.addWidget(self.btn_ok)
        hbox.addWidget(self.btn_cancel)
        
        self.btn_fill.clicked.connect(self.on_fill)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        main_layout.addLayout(hbox)

    def on_fill(self):
        w_def, h_def = self.canvas_size
        dialog = FillDialog(default_w=w_def, default_h=h_def, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            w, h = dialog.get_values()
            try:
                obj_w, obj_h = self.selected_item_size
                x_gap = float(self.x_interval.text())
                y_gap = float(self.y_interval.text())
                
                # Avoid division by zero
                # If object width is effectively 0 (e.g. vertical line), use gap or small epsilon
                denom_x = obj_w + x_gap
                if denom_x <= 0.001: denom_x = 0.001
                    
                denom_y = obj_h + y_gap
                if denom_y <= 0.001: denom_y = 0.001
                
                # Calculate Max Count: Count * (Size + Gap) - Gap <= Width
                # Count * (Size + Gap) <= Width + Gap
                
                if w > 0:
                    nx = int((w + x_gap) / denom_x)
                    self.x_count.setText(str(max(1, nx)))
                    
                if h > 0:
                    ny = int((h + y_gap) / denom_y)
                    self.y_count.setText(str(max(1, ny)))
                    
            except ValueError:
                pass


    def get_data(self):
        try:
            xc = int(self.x_count.text())
        except: xc = 1
        
        try:
            yc = int(self.y_count.text())
        except: yc = 1
        
        try:
            xi = float(self.x_interval.text())
        except: xi = 0.0
        
        try:
            yi = float(self.y_interval.text())
        except: yi = 0.0

        return {
            'x_count': max(1, xc),
            'y_count': max(1, yc),
            'x_interval': xi,
            'y_interval': yi,
            'direction_mode': self.btn_direction.get_current_index(),
            'order_mode': self.btn_order.get_current_index()
        }
