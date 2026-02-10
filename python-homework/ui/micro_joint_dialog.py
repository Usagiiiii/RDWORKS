#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QDoubleSpinBox, QSpinBox, QCheckBox, QRadioButton, 
                             QPushButton, QGroupBox, QWidget, QMessageBox, QButtonGroup)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

class MicroJointDialog(QDialog):
    # Signal emitted when selection is made: config, selection_filters
    apply_micro_joint = pyqtSignal(dict, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("微连")
        # Removed fixed size to allow compact layout
        self.init_ui()
        self._load_settings()
        self.setFixedSize(self.sizeHint())
        self.update_ui_state()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # --- Top Group: Parameters ---
        param_group = QGroupBox()
        # Compact style
        param_group.setStyleSheet("QGroupBox { border: 1px solid #A0A0A0; border-radius: 3px; margin-top: 0px; padding-top: 5px; }")
        param_layout = QVBoxLayout(param_group)
        param_layout.setContentsMargins(5, 5, 5, 5)
        param_layout.setSpacing(5)
        
        # Row 1: Qty | Enable
        row1 = QHBoxLayout()
        self.rb_qty = QRadioButton("按数量")
        self.rb_qty.setChecked(True)
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 1000)
        self.spin_qty.setValue(1)
        self.spin_qty.setFixedWidth(60)
        
        self.cb_enable = QCheckBox("使能微连")
        
        row1.addWidget(self.rb_qty)
        row1.addWidget(self.spin_qty)
        row1.addStretch()
        row1.addWidget(self.cb_enable)
        param_layout.addLayout(row1)
        
        # Row 2: Dist
        row2 = QHBoxLayout()
        self.rb_dist = QRadioButton("按距离")
        self.spin_dist = QDoubleSpinBox()
        self.spin_dist.setRange(0.1, 10000.0)
        self.spin_dist.setValue(1.000)
        self.spin_dist.setSuffix(" mm")
        self.spin_dist.setDecimals(3)
        self.spin_dist.setFixedWidth(80)
        
        row2.addWidget(self.rb_dist)
        row2.addWidget(self.spin_dist)
        row2.addStretch()
        param_layout.addLayout(row2)
        
        # Mutex
        self.bg_type = QButtonGroup(self)
        self.bg_type.addButton(self.rb_qty)
        self.bg_type.addButton(self.rb_dist)

        # Row 3: Width (Indented)
        row3 = QHBoxLayout()
        lbl_width = QLabel("微连宽度:")
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(0.1, 100.0)
        self.spin_width.setValue(2.000)
        self.spin_width.setSuffix(" mm")
        self.spin_width.setDecimals(3)
        self.spin_width.setFixedWidth(80)
        
        # Indent roughly to align with spinboxes above
        row3.addSpacing(60) 
        row3.addWidget(lbl_width)
        row3.addWidget(self.spin_width)
        row3.addStretch()
        param_layout.addLayout(row3)

        layout.addWidget(param_group)

        # --- Bottom Group: Filters ---
        contour_group = QGroupBox()
        contour_group.setStyleSheet("QGroupBox { border: 1px solid #A0A0A0; border-radius: 3px; margin-top: 0px; padding-top: 5px; }")
        contour_layout = QVBoxLayout(contour_group)
        contour_layout.setContentsMargins(5, 5, 5, 5)
        contour_layout.setSpacing(5)
        
        # Helper for filter rows
        def create_filter_row(label_text, w_val, h_val, w_key, h_key, is_min=False):
            r = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(50)
            r.addWidget(lbl)
            
            p_lbl = "最小" if is_min else "最大"
            
            r.addStretch()
            r.addWidget(QLabel(f"{p_lbl}宽度:"))
            sb_w = QDoubleSpinBox()
            sb_w.setRange(0, 10000)
            sb_w.setValue(w_val)
            sb_w.setSuffix(" mm")
            sb_w.setDecimals(3)
            sb_w.setFixedWidth(80)
            r.addWidget(sb_w)
            
            r.addWidget(QLabel(f"{p_lbl}高度:"))
            sb_h = QDoubleSpinBox()
            sb_h.setRange(0, 10000)
            sb_h.setValue(h_val)
            sb_h.setSuffix(" mm")
            sb_h.setDecimals(3)
            sb_h.setFixedWidth(80)
            r.addWidget(sb_h)
            
            return r, sb_w, sb_h

        curr_row, self.spin_small_w, self.spin_small_h = create_filter_row("小轮廓:", 30.0, 30.0, 'small_w', 'small_h')
        contour_layout.addLayout(curr_row)
        
        curr_row, self.spin_large_w, self.spin_large_h = create_filter_row("大轮廓:", 1000.0, 1000.0, 'large_w', 'large_h', True)
        contour_layout.addLayout(curr_row)
        
        # Line
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #555;") # Darker line
        contour_layout.addWidget(line)
        
        # Checkboxes & Button
        bottom_row = QHBoxLayout()
        self.cb_s = QCheckBox("小")
        self.cb_s.setChecked(True)
        self.cb_m = QCheckBox("中")
        self.cb_m.setChecked(True)
        self.cb_l = QCheckBox("大")
        self.cb_l.setChecked(True)
        
        bottom_row.addSpacing(20)
        bottom_row.addWidget(self.cb_s)
        bottom_row.addStretch()
        bottom_row.addWidget(self.cb_m)
        bottom_row.addStretch()
        bottom_row.addWidget(self.cb_l)
        bottom_row.addStretch()
        
        contour_layout.addLayout(bottom_row)
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_select = QPushButton("选取")
        self.btn_select.setFixedWidth(80)
        self.btn_select.clicked.connect(self.on_select_clicked)
        btn_row.addWidget(self.btn_select)
        contour_layout.addLayout(btn_row)

        layout.addWidget(contour_group)

        # Connections
        self.cb_enable.toggled.connect(self.update_ui_state)
        # self.has_selection will be set externally or checking scene

    def set_has_selection(self, has_selection):
        # According to requirements: "Enabled only if objects are selected"
        # "第一个方框里有一勾选项“使能微连”（只有选取了对象之后才会显示可勾选状态，否则显示灰色）"
        self.cb_enable.setEnabled(has_selection)
        if not has_selection:
            self.cb_enable.setChecked(False)
        self.update_ui_state()

    def update_ui_state(self):
        enabled = self.cb_enable.isChecked()
        
        self.rb_qty.setEnabled(enabled)
        self.rb_dist.setEnabled(enabled)
        self.spin_qty.setEnabled(enabled)
        self.spin_dist.setEnabled(enabled)
        self.spin_width.setEnabled(enabled)
        
        # NOTE: Screenshot logic implies that parameter editing depends on "Enable". 
        # But Filter settings (contours) are for "Selecting" objects, so they should probably be always enabled?
        # User says: "Apply Micro-joint" (Apply settings).
        # Actually user says: "After clicking 'Select'... if no object selected... automatically select".
        # This implies "Select" button triggers selection logic based on filters.
        # "Enable Micro-joint"... "Checked to modify the values behind it".
        # So enable/disable logic for top part is correct.
    
    def on_select_clicked(self):
        # Collect Data
        config = {
            'enabled': self.cb_enable.isChecked(),
            'mode': 'qty' if self.rb_qty.isChecked() else 'dist',
            'qty': self.spin_qty.value(),
            'dist': self.spin_dist.value(),
            'width': self.spin_width.value()
        }
        
        filters = {
            'small_max_w': self.spin_small_w.value(),
            'small_max_h': self.spin_small_h.value(),
            'large_min_w': self.spin_large_w.value(),
            'large_min_h': self.spin_large_h.value(),
            'check_small': self.cb_s.isChecked(),
            'check_mid': self.cb_m.isChecked(),
            'check_large': self.cb_l.isChecked()
        }
        
        self._save_settings(config, filters)
        self.apply_micro_joint.emit(config, filters)
        # self.accept() # Removed to prevent closing dialog on selection

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    def _load_settings(self):
        settings = QSettings("RDWORKS-python", "RDWORKS-python")
        settings.beginGroup("micro_joint_dialog")
        try:
            self.cb_enable.setChecked(self._to_bool(settings.value("enabled", self.cb_enable.isChecked()), self.cb_enable.isChecked()))
            mode = str(settings.value("mode", "qty") or "qty")
            if mode == "dist":
                self.rb_dist.setChecked(True)
            else:
                self.rb_qty.setChecked(True)

            self.spin_qty.setValue(int(settings.value("qty", self.spin_qty.value())))
            self.spin_dist.setValue(float(settings.value("dist", self.spin_dist.value())))
            self.spin_width.setValue(float(settings.value("width", self.spin_width.value())))

            self.spin_small_w.setValue(float(settings.value("small_max_w", self.spin_small_w.value())))
            self.spin_small_h.setValue(float(settings.value("small_max_h", self.spin_small_h.value())))
            self.spin_large_w.setValue(float(settings.value("large_min_w", self.spin_large_w.value())))
            self.spin_large_h.setValue(float(settings.value("large_min_h", self.spin_large_h.value())))

            self.cb_s.setChecked(self._to_bool(settings.value("check_small", self.cb_s.isChecked()), self.cb_s.isChecked()))
            self.cb_m.setChecked(self._to_bool(settings.value("check_mid", self.cb_m.isChecked()), self.cb_m.isChecked()))
            self.cb_l.setChecked(self._to_bool(settings.value("check_large", self.cb_l.isChecked()), self.cb_l.isChecked()))
        except Exception:
            pass
        finally:
            settings.endGroup()

    def _save_settings(self, config, filters):
        settings = QSettings("RDWORKS-python", "RDWORKS-python")
        settings.beginGroup("micro_joint_dialog")
        try:
            settings.setValue("enabled", bool(config.get("enabled", False)))
            settings.setValue("mode", config.get("mode", "qty"))
            settings.setValue("qty", int(config.get("qty", 1)))
            settings.setValue("dist", float(config.get("dist", 1.0)))
            settings.setValue("width", float(config.get("width", 2.0)))

            settings.setValue("small_max_w", float(filters.get("small_max_w", 30.0)))
            settings.setValue("small_max_h", float(filters.get("small_max_h", 30.0)))
            settings.setValue("large_min_w", float(filters.get("large_min_w", 1000.0)))
            settings.setValue("large_min_h", float(filters.get("large_min_h", 1000.0)))
            settings.setValue("check_small", bool(filters.get("check_small", True)))
            settings.setValue("check_mid", bool(filters.get("check_mid", True)))
            settings.setValue("check_large", bool(filters.get("check_large", True)))
            settings.sync()
        except Exception:
            pass
        finally:
            settings.endGroup()
