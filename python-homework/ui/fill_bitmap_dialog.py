from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton
from PyQt5.QtCore import Qt

class FillBitmapDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("填充设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setFixedSize(260, 120)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 20, 10, 10) 
        main_layout.setSpacing(15)

        # Content Row
        content_layout = QHBoxLayout()
        content_layout.addStretch()
        content_layout.addWidget(QLabel("位图分辨率:"))
        
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(1, 2000)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setFixedWidth(60)
        self.dpi_spin.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.dpi_spin)
        
        content_layout.addWidget(QLabel("dpi"))
        content_layout.addStretch()
        
        main_layout.addLayout(content_layout)

        # Button Row
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_ok = QPushButton("确定")
        self.btn_ok.setFixedSize(70, 25)
        self.btn_ok.clicked.connect(self.accept)
        button_layout.addWidget(self.btn_ok)
        
        button_layout.addSpacing(20)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedSize(70, 25)
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        self.dpi_spin.selectAll()
        
    def get_dpi(self):
        return self.dpi_spin.value()
