from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QPushButton, QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt

class DeleteDuplicatesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("删除重叠线")
        self.setFixedSize(300, 120)
        
        layout = QVBoxLayout(self)
        
        # Group Box style frame? Screenshot shows simple widget
        
        self.chk_enable = QCheckBox("使能重叠容差")
        self.chk_enable.setChecked(True)
        layout.addWidget(self.chk_enable)
        
        h_layout = QHBoxLayout()
        h_layout.addSpacing(20) # Indent
        h_layout.addWidget(QLabel("重叠容差(mm):"))
        self.txt_tolerance = QLineEdit("1")
        self.txt_tolerance.setFixedWidth(60)
        h_layout.addWidget(self.txt_tolerance)
        h_layout.addStretch()
        layout.addLayout(h_layout)
        
        layout.addStretch()
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("确定")
        button_box.button(QDialogButtonBox.Cancel).setText("取消")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Connect settings
        self.chk_enable.toggled.connect(self.txt_tolerance.setEnabled)
        
    def get_tolerance(self):
        if not self.chk_enable.isChecked():
            return 1e-7 # Extremely small tolerance -> exact match
        try:
            return float(self.txt_tolerance.text())
        except ValueError:
            return 0.01
