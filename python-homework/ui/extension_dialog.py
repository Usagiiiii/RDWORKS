import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QCheckBox, QLineEdit, QGroupBox, QPushButton, 
                             QRadioButton, QButtonGroup, QWidget)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QIcon

class ImageToggleButton(QPushButton):
    def __init__(self, img_path1, img_path2, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.img1 = img_path1
        self.img2 = img_path2
        # Set initial icon
        self.update_icon()
        self.toggled.connect(self.update_icon)
        self.setFixedSize(50, 30)
        self.setIconSize(QSize(40, 25))

    def update_icon(self, checked=None):
        if self.isChecked():
            if os.path.exists(self.img2):
                self.setIcon(QIcon(self.img2))
            else:
                self.setText("State 2")
        else:
            if os.path.exists(self.img1):
                self.setIcon(QIcon(self.img1))
            else:
                self.setText("State 1")

class ExtensionDialog(QDialog):
    def __init__(self, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("扩展")
        self.setFixedSize(360, 350)
        self.initial_data = initial_data or {}
        self.setup_ui()
        self.load_data()

    def load_data(self):
        data = self.initial_data
        if not data:
            return
            
        self.chk_reset_sn.setChecked(data.get("reset_sn_enabled", False))
        self.edit_reset_val.setText(data.get("reset_sn_value", "1"))
        self.chk_enable_leading_zero.setChecked(data.get("use_leading_zero", False))
        self.group_array.setChecked(data.get("array_enabled", False))
        
        self.edit_x_count.setText(str(data.get("x_count", "1")))
        self.edit_x_spacing.setText(str(data.get("x_spacing", "0")))
        self.edit_y_count.setText(str(data.get("y_count", "1")))
        self.edit_y_spacing.setText(str(data.get("y_spacing", "0")))
        
        # Load button states if saved
        self.btn_x_type.setChecked(data.get("x_type_state", False))
        self.btn_y_type.setChecked(data.get("y_type_state", False))

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Top section: Reset SN and Enable Leading Zero
        top_grid = QGridLayout()
        
        self.chk_reset_sn = QCheckBox("复位序号")
        self.edit_reset_val = QLineEdit("9999")
        self.edit_reset_val.setEnabled(False) # Initially disabled based on checkbox usually
        
        self.chk_enable_leading_zero = QCheckBox("使能前导零")
        
        top_grid.addWidget(self.chk_reset_sn, 0, 0)
        top_grid.addWidget(self.edit_reset_val, 0, 1)
        top_grid.addWidget(self.chk_enable_leading_zero, 1, 0, 1, 2)
        
        main_layout.addLayout(top_grid)
        
        # Array Group Box
        self.group_array = QGroupBox("使能序号阵列")
        self.group_array.setCheckable(True)
        self.group_array.setChecked(False)
        
        array_layout = QGridLayout(self.group_array)
        
        # Headers
        array_layout.addWidget(QLabel("个数"), 0, 1)
        array_layout.addWidget(QLabel("间隔"), 0, 2)
        
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Row X
        self.lbl_x = QLabel("X:")
        self.lbl_x.setStyleSheet("color: blue")
        self.edit_x_count = QLineEdit("1")
        self.edit_x_spacing = QLineEdit("10")
        
        # Button 1 for X row (11.png / 12.png)
        img11 = os.path.join(base_path, "11.png")
        img12 = os.path.join(base_path, "12.png")
        self.btn_x_type = ImageToggleButton(img11, img12)
        # Adjust size to match screenshot 1 style (more square, side-by-side)
        self.btn_x_type.setFixedSize(38, 38)
        self.btn_x_type.setIconSize(QSize(32, 32))
        
        array_layout.addWidget(self.lbl_x, 1, 0)
        array_layout.addWidget(self.edit_x_count, 1, 1)
        array_layout.addWidget(self.edit_x_spacing, 1, 2)
        
        # Row Y
        self.lbl_y = QLabel("Y:")
        self.lbl_y.setStyleSheet("color: orange") # Use orange/brown to match screenshot
        self.edit_y_count = QLineEdit("1")
        self.edit_y_spacing = QLineEdit("10")
        
        # Button 2 for Y row (13.png / 14.png)
        img13 = os.path.join(base_path, "13.png")
        img14 = os.path.join(base_path, "14.png")
        self.btn_y_type = ImageToggleButton(img13, img14)
        self.btn_y_type.setFixedSize(38, 38)
        self.btn_y_type.setIconSize(QSize(32, 32))

        array_layout.addWidget(self.lbl_y, 2, 0)
        array_layout.addWidget(self.edit_y_count, 2, 1)
        array_layout.addWidget(self.edit_y_spacing, 2, 2)
        
        # Add buttons to the right, spanning 2 rows
        # Btn X at Col 3
        array_layout.addWidget(self.btn_x_type, 1, 3, 2, 1, Qt.AlignHCenter)
        # Btn Y at Col 4
        array_layout.addWidget(self.btn_y_type, 1, 4, 2, 1, Qt.AlignHCenter)
        
        main_layout.addWidget(self.group_array)
        
        main_layout.addStretch()
        
        # Bottom Buttons
        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        
        btn_box.addStretch()
        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addStretch()
        
        main_layout.addLayout(btn_box)
        
        # Connections
        self.chk_reset_sn.toggled.connect(self.edit_reset_val.setEnabled)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def get_data(self):
        return {
            "reset_sn_enabled": self.chk_reset_sn.isChecked(),
            "reset_sn_value": self.edit_reset_val.text(),
            "use_leading_zero": self.chk_enable_leading_zero.isChecked(),
            "array_enabled": self.group_array.isChecked(),
            "x_count": self.edit_x_count.text(),
            "x_spacing": self.edit_x_spacing.text(),
            "y_count": self.edit_y_count.text(),
            "y_spacing": self.edit_y_spacing.text(),
            "x_type_state": self.btn_x_type.isChecked(),
            "y_type_state": self.btn_y_type.isChecked()
        }
