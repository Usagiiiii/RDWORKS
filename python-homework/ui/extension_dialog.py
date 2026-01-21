from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QCheckBox, QLineEdit, QGroupBox, QPushButton, 
                             QRadioButton, QButtonGroup, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QIcon

class ExtensionDialog(QDialog):
    def __init__(self, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("扩展")
        self.setFixedSize(300, 350)
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
        
        direction = data.get("direction", "x_priority")
        if direction == "x_priority":
            self.btn_dir_x.setChecked(True)
        else:
            self.btn_dir_y.setChecked(True)

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
        
        # Row X
        self.lbl_x = QLabel("X:")
        self.lbl_x.setStyleSheet("color: blue")
        self.edit_x_count = QLineEdit("1")
        self.edit_x_spacing = QLineEdit("10")
        
        array_layout.addWidget(self.lbl_x, 1, 0)
        array_layout.addWidget(self.edit_x_count, 1, 1)
        array_layout.addWidget(self.edit_x_spacing, 1, 2)
        
        # Row Y
        self.lbl_y = QLabel("Y:")
        self.lbl_y.setStyleSheet("color: orange") # Use orange/brown to match screenshot
        self.edit_y_count = QLineEdit("1")
        self.edit_y_spacing = QLineEdit("10")
        
        array_layout.addWidget(self.lbl_y, 2, 0)
        array_layout.addWidget(self.edit_y_count, 2, 1)
        array_layout.addWidget(self.edit_y_spacing, 2, 2)
        
        # Direction Buttons (Icons simulated with text/style for now, or custom paint)
        # 1. X Priority (Vertical bars, green arrow right)
        # 2. Y Priority / Snake (Horizontal bars, blue arrows)
        
        # Since we don't have the exact icons, we will create simple push buttons 
        # that toggle state, or use radio buttons styled as icons. 
        # For simplicity, let's make them buttons that look checkable.
        
        btn_layout = QVBoxLayout()
        self.btn_dir_x = QPushButton()
        self.btn_dir_x.setCheckable(True)
        self.btn_dir_x.setChecked(True)
        self.btn_dir_x.setFixedSize(40, 30)
        # Custom painting or stylesheet to simulate the icon simply
        self.btn_dir_x.setStyleSheet("""
            QPushButton { background-color: #f0f0f0; border: 1px solid #999; }
            QPushButton:checked { background-color: #ddd; border: 2px solid #555; }
        """)
        # We can set an icon if we had one, or text "||->"
        self.btn_dir_x.setText("|||->") 

        self.btn_dir_y = QPushButton()
        self.btn_dir_y.setCheckable(True)
        self.btn_dir_y.setFixedSize(40, 30)
        self.btn_dir_y.setStyleSheet(self.btn_dir_x.styleSheet())
        self.btn_dir_y.setText("==\nv")
        
        # Exclusive check
        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.btn_dir_x)
        self.btn_group.addButton(self.btn_dir_y)
        
        btn_layout.addWidget(self.btn_dir_x)
        btn_layout.addWidget(self.btn_dir_y)
        
        array_layout.addLayout(btn_layout, 1, 3, 2, 1)
        
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
            "direction": "x_priority" if self.btn_dir_x.isChecked() else "y_priority" # Simply mapping
        }
