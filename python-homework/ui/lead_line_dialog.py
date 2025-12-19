#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引入引出线设置对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QDoubleSpinBox, QComboBox, QCheckBox, 
                             QDialogButtonBox, QGridLayout, QWidget)
from PyQt5.QtCore import Qt

class LeadLineDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("引入引出线设置")
        self.setFixedSize(300, 450)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- 引入线设置 ---
        self.gb_lead_in = QGroupBox("引入线")
        layout_in = QGridLayout(self.gb_lead_in)
        
        self.chk_enable_in = QCheckBox("是否引入")
        self.chk_enable_in.toggled.connect(self.on_enable_in_toggled)
        
        self.spin_len_in = QDoubleSpinBox()
        self.spin_len_in.setRange(0, 1000)
        self.spin_len_in.setValue(5)
        self.spin_len_in.setSuffix(" mm")
        
        self.spin_angle_in = QDoubleSpinBox()
        self.spin_angle_in.setRange(0, 360)
        self.spin_angle_in.setValue(90)
        
        self.combo_type_in = QComboBox()
        self.combo_type_in.addItems(["直线", "圆弧"])
        
        self.chk_center_in = QCheckBox("从中心引入")

        layout_in.addWidget(self.chk_enable_in, 0, 0, 1, 2)
        
        label_len_in = QLabel("引入线长度(mm):")
        label_len_in.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout_in.addWidget(label_len_in, 1, 0)
        layout_in.addWidget(self.spin_len_in, 1, 1)
        
        label_angle_in = QLabel("夹角(度):")
        label_angle_in.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout_in.addWidget(label_angle_in, 2, 0)
        layout_in.addWidget(self.spin_angle_in, 2, 1)
        
        label_type_in = QLabel("引入线类型:")
        label_type_in.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout_in.addWidget(label_type_in, 3, 0)
        layout_in.addWidget(self.combo_type_in, 3, 1)
        
        layout_in.addWidget(self.chk_center_in, 4, 0, 1, 2)

        layout.addWidget(self.gb_lead_in)

        # --- 引出线设置 ---
        self.gb_lead_out = QGroupBox("引出线")
        layout_out = QGridLayout(self.gb_lead_out)
        
        self.chk_enable_out = QCheckBox("是否引出")
        self.chk_enable_out.toggled.connect(self.on_enable_out_toggled)
        
        self.spin_len_out = QDoubleSpinBox()
        self.spin_len_out.setRange(0, 1000)
        self.spin_len_out.setValue(5)
        self.spin_len_out.setSuffix(" mm")
        
        self.spin_angle_out = QDoubleSpinBox()
        self.spin_angle_out.setRange(0, 360)
        self.spin_angle_out.setValue(90)
        
        self.combo_type_out = QComboBox()
        self.combo_type_out.addItems(["直线", "圆弧"])
        
        self.chk_center_out = QCheckBox("向中心引出")

        layout_out.addWidget(self.chk_enable_out, 0, 0, 1, 2)
        
        label_len_out = QLabel("引出线长度(mm):")
        label_len_out.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout_out.addWidget(label_len_out, 1, 0)
        layout_out.addWidget(self.spin_len_out, 1, 1)
        
        label_angle_out = QLabel("夹角(度):")
        label_angle_out.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout_out.addWidget(label_angle_out, 2, 0)
        layout_out.addWidget(self.spin_angle_out, 2, 1)
        
        label_type_out = QLabel("引出线类型:")
        label_type_out.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout_out.addWidget(label_type_out, 3, 0)
        layout_out.addWidget(self.combo_type_out, 3, 1)
        
        layout_out.addWidget(self.chk_center_out, 4, 0, 1, 2)

        layout.addWidget(self.gb_lead_out)

        # --- 其他选项 ---
        self.chk_auto_inner_outer = QCheckBox("自动设置内外切")
        self.chk_auto_inner_outer.setChecked(True)
        layout.addWidget(self.chk_auto_inner_outer)
        
        self.chk_auto_angle = QCheckBox("自动查找合适角度")
        layout.addWidget(self.chk_auto_angle)
        
        self.chk_check_valid = QCheckBox("自动检查引线有效性")
        layout.addWidget(self.chk_check_valid)

        # --- 按钮 ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # 初始化状态
        self.on_enable_in_toggled(False)
        self.on_enable_out_toggled(False)

    def on_enable_in_toggled(self, checked):
        self.spin_len_in.setEnabled(checked)
        self.spin_angle_in.setEnabled(checked)
        self.combo_type_in.setEnabled(checked)
        # self.chk_center_in.setEnabled(checked) # 保持独立

    def on_enable_out_toggled(self, checked):
        self.spin_len_out.setEnabled(checked)
        self.spin_angle_out.setEnabled(checked)
        self.combo_type_out.setEnabled(checked)
        # self.chk_center_out.setEnabled(checked) # 保持独立

    def get_data(self):
        return {
            'lead_in': {
                'enabled': self.chk_enable_in.isChecked(),
                'length': self.spin_len_in.value(),
                'angle': self.spin_angle_in.value(),
                'type': self.combo_type_in.currentText(),
                'from_center': self.chk_center_in.isChecked()
            },
            'lead_out': {
                'enabled': self.chk_enable_out.isChecked(),
                'length': self.spin_len_out.value(),
                'angle': self.spin_angle_out.value(),
                'type': self.combo_type_out.currentText(),
                'to_center': self.chk_center_out.isChecked()
            },
            'options': {
                'auto_inner_outer': self.chk_auto_inner_outer.isChecked(),
                'auto_angle': self.chk_auto_angle.isChecked(),
                'check_valid': self.chk_check_valid.isChecked()
            }
        }
