from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt

class MergeLinesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置合并容差")
        
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Tolerance input
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("合并容差(mm):"))
        self.edit_tolerance = QLineEdit("5")
        h_layout.addWidget(self.edit_tolerance)
        layout.addLayout(h_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.btn_ok.clicked.connect(self.check_and_accept)
        self.btn_cancel.clicked.connect(self.reject)
        
    def check_and_accept(self):
        try:
            val = float(self.edit_tolerance.text())
            if 0.005 <= val <= 5:
                self.accept()
            else:
                raise ValueError
        except ValueError:
             QMessageBox.warning(self, "Laser", "请输入一个介于 0.005 和 5 之间的数字。")
             self.edit_tolerance.selectAll()
             self.edit_tolerance.setFocus()

    def get_tolerance(self):
        try:
            return float(self.edit_tolerance.text())
        except ValueError:
            return 5.0
