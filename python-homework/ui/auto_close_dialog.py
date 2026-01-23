from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QCheckBox, QPushButton)
from PyQt5.QtCore import Qt

class AutoCloseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("曲线自动闭合")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout(self)
        
        # Tolerance input
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("闭合容差(mm):"))
        self.edit_tolerance = QLineEdit("0.1")
        h_layout.addWidget(self.edit_tolerance)
        layout.addLayout(h_layout)
        
        # Force close checkbox
        self.chk_force = QCheckBox("强制闭合(无论距离)")
        self.chk_force.setChecked(False)
        layout.addWidget(self.chk_force)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
    def get_values(self):
        try:
            tolerance = float(self.edit_tolerance.text())
        except ValueError:
            tolerance = 0.1
        return tolerance, self.chk_force.isChecked()
