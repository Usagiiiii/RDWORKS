from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QPushButton, QLineEdit, QComboBox, 
                             QGroupBox, QDialogButtonBox, QWidget)
from PyQt5.QtCore import Qt

class CutOptimizeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("切割优化处理")
        self.setFixedSize(320, 260)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 1. 按图层顺序
        self.chk_layer_order = QCheckBox("按图层顺序")
        layout.addWidget(self.chk_layer_order)
        
        # 2. 由内到外
        self.widget_inside_out = QWidget()
        layout_io = QVBoxLayout(self.widget_inside_out)
        layout_io.setContentsMargins(0, 0, 0, 0)
        
        self.chk_inside_out = QCheckBox("由内到外")
        layout_io.addWidget(self.chk_inside_out)
        
        self.cbo_inside_out_mode = QComboBox()
        self.cbo_inside_out_mode.addItems(["单个由内到外", "单个由内到外，寻找切割点"])
        
        # 设置样式: setMaxVisibleItems(10), setEditable(True), lineEdit().setReadOnly(True)
        self.cbo_inside_out_mode.setMaxVisibleItems(10)
        self.cbo_inside_out_mode.setEditable(True)
        self.cbo_inside_out_mode.lineEdit().setReadOnly(True)
        
        # Indent the combobox slightly
        h_io = QHBoxLayout()
        h_io.addSpacing(20)
        h_io.addWidget(self.cbo_inside_out_mode)
        layout_io.addLayout(h_io)
            
        layout.addWidget(self.widget_inside_out)
        
        # 3. 分块处理
        self.group_block = QGroupBox("分块处理(mm)")
        layout_block = QHBoxLayout(self.group_block)
        
        layout_block.addWidget(QLabel("高度:"))
        self.txt_block_height = QLineEdit("50")
        self.txt_block_height.setFixedWidth(50)
        layout_block.addWidget(self.txt_block_height)
        
        layout_block.addStretch()
        
        layout_block.addWidget(QLabel("方向:"))
        self.cbo_block_dir = QComboBox()
        self.cbo_block_dir.addItems(["从上到下", "从下到上", "从左到右", "从右到左"])
        self.cbo_block_dir.setMaxVisibleItems(10)
        self.cbo_block_dir.setEditable(True)
        self.cbo_block_dir.lineEdit().setReadOnly(True)
        self.cbo_block_dir.setCurrentText("从上到下")
        layout_block.addWidget(self.cbo_block_dir)
        
        layout.addWidget(self.group_block)
        
        # 4. 其他选项
        self.chk_opt_start = QCheckBox("切割起点优化")
        layout.addWidget(self.chk_opt_start)
        
        self.chk_auto_start = QCheckBox("自动确定切割起点和方向")
        layout.addWidget(self.chk_auto_start)
        
        layout.addStretch()
        
        # Buttons
        h_btns = QHBoxLayout()
        h_btns.addStretch()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        # Style buttons to look a bit wider/nicer
        self.btn_ok.setFixedWidth(80)
        self.btn_cancel.setFixedWidth(80)
        
        h_btns.addWidget(self.btn_ok)
        h_btns.addSpacing(20)
        h_btns.addWidget(self.btn_cancel)
        h_btns.addStretch()
        
        layout.addLayout(h_btns)
        
        # Connect
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        # UI Logic
        self.chk_inside_out.toggled.connect(self.cbo_inside_out_mode.setEnabled)
        self.cbo_inside_out_mode.setEnabled(False) 
        
    def get_settings(self):
        return {
            "layer_order": self.chk_layer_order.isChecked(),
            "inside_out": self.chk_inside_out.isChecked(),
            "inside_out_mode": self.cbo_inside_out_mode.currentText(),
            "block_height": float(self.txt_block_height.text()) if self.txt_block_height.text() else 0,
            "block_direction": self.cbo_block_dir.currentText(),
            "optimize_start": self.chk_opt_start.isChecked(),
            "auto_start_dir": self.chk_auto_start.isChecked()
        }
