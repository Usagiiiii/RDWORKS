#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QRadioButton, QPushButton, QCheckBox, 
                             QGroupBox, QButtonGroup, QWidget)
from PyQt5.QtCore import Qt

class OffsetPathDialog(QDialog):
    # Class variable to store last used settings
    _last_settings = {
        "distance": "0",
        "delete_original": False,
        "mode": "outside",
        "round_corners": True
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成平行线")
        # Match screenshot 2 visually - compact
        self.resize(300, 180)
        self.setFixedSize(300, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # 1. Offset Distance & Delete Original Row
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("偏移距离"))
        
        self.offset_edit = QLineEdit(self._last_settings.get("distance", "0"))
        self.offset_edit.setFixedWidth(60)
        row1.addWidget(self.offset_edit)
        
        row1.addWidget(QLabel("mm"))
        row1.addStretch()
        
        self.check_delete_original = QCheckBox("删除原图")
        self.check_delete_original.setChecked(self._last_settings.get("delete_original", False))
        row1.addWidget(self.check_delete_original)
        
        layout.addLayout(row1)
        
        # 2. GroupBox with Radio Buttons
        mode_group = QGroupBox()
        # Ensure it looks like the screenshot (flat groupbox with line) or just standard groupbox
        # Screenshot 2 has a subtle border.
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setContentsMargins(10, 10, 10, 10)
        
        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        
        self.rb_inside = QRadioButton("内缩")
        self.rb_outside = QRadioButton("外扩")
        self.rb_auto = QRadioButton("自动内缩外扩")
        self.rb_both = QRadioButton("内缩+外扩")
        
        # Restore mode
        last_mode = self._last_settings.get("mode", "outside")
        if last_mode == "inside": self.rb_inside.setChecked(True)
        elif last_mode == "outside": self.rb_outside.setChecked(True)
        elif last_mode == "auto": self.rb_auto.setChecked(True)
        elif last_mode == "both": self.rb_both.setChecked(True)
        else: self.rb_outside.setChecked(True)
        
        col1.addWidget(self.rb_inside)
        col1.addWidget(self.rb_outside)

        col2.addWidget(self.rb_auto)
        col2.addWidget(self.rb_both)
        
        mode_layout.addLayout(col1)
        mode_layout.addLayout(col2)
        
        layout.addWidget(mode_group)
        
        # 3. Bottom Row: Round Corners & Buttons
        bottom_row = QHBoxLayout()
        self.check_round_corners = QCheckBox("圆弧过渡")
        self.check_round_corners.setChecked(self._last_settings.get("round_corners", True))
        bottom_row.addWidget(self.check_round_corners)
        
        bottom_row.addStretch()
        
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        bottom_row.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_row.addWidget(self.btn_cancel)
        
        layout.addLayout(bottom_row)
        
        self.bg = QButtonGroup(self)
        self.bg.addButton(self.rb_inside)
        self.bg.addButton(self.rb_outside)
        self.bg.addButton(self.rb_auto)
        self.bg.addButton(self.rb_both)

    def get_data(self):
        try:
            dist_str = self.offset_edit.text()
            dist = float(dist_str)
        except ValueError:
            dist = 0.0
            dist_str = "0"
            
        mode = "outside"
        if self.rb_inside.isChecked(): mode = "inside"
        elif self.rb_outside.isChecked(): mode = "outside"
        elif self.rb_auto.isChecked(): mode = "auto"
        elif self.rb_both.isChecked(): mode = "both"
        
        delete_orig = self.check_delete_original.isChecked()
        round_corners = self.check_round_corners.isChecked()

        # Save settings
        OffsetPathDialog._last_settings = {
            "distance": dist_str,
            "delete_original": delete_orig,
            "mode": mode,
            "round_corners": round_corners
        }
        
        return {
            "distance": dist,
            "delete_original": delete_orig,
            "mode": mode,
            "round_corners": round_corners
        }
