#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget,
    QWidget, QGroupBox, QLabel, QLineEdit, QCheckBox, QComboBox,
    QRadioButton, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QGridLayout, QFormLayout, QFrame, QButtonGroup, QAbstractItemView,
    QColorDialog, QFileDialog
)
from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QIcon, QColor

class CustomColorDialog(QColorDialog):
    def __init__(self, initial=Qt.white, parent=None, title="Color"):
        super().__init__(initial, parent)
        self.setWindowTitle(title)
        self.setOption(QColorDialog.DontUseNativeDialog)
        
        self.selected_custom_index = -1
        self.setup_custom_ui()
        
    def setup_custom_ui(self):
        # Find Add button
        buttons = self.findChildren(QPushButton)
        self.add_btn = None
        for btn in buttons:
            # "Add to Custom Colors" or Chinese equivalent
            # We assume the last big button or one with specific text
            # To be safe, look for "Add" or "添加" or "Custom"
            if "Custom" in btn.text() or "自定义" in btn.text():
                 self.add_btn = btn
                 break
        
        if self.add_btn:
            self.add_btn.setVisible(False)
            
            self.my_add_btn = QPushButton(self.add_btn.text())
            self.my_add_btn.clicked.connect(self.on_add_clicked)
            
            layout = self.find_layout_containing(self.add_btn)
            if layout:
                idx = layout.indexOf(self.add_btn)
                layout.insertWidget(idx, self.my_add_btn)
                
                self.del_btn = QPushButton("删除选中颜色")
                self.del_btn.setEnabled(False)
                self.del_btn.clicked.connect(self.on_delete_clicked)
                
                layout.insertWidget(idx + 1, self.del_btn)

        # Find Custom Colors Array
        widgets = self.findChildren(QWidget)
        self.basic_well_array = None
        self.custom_well_array = None
        
        for w in widgets:
            meta_name = w.metaObject().className()
            if "QWellArray" in meta_name:
                h = w.height()
                if h > 100:
                    self.basic_well_array = w
                elif h < 100:
                    self.custom_well_array = w
        
        if self.custom_well_array:
            self.custom_well_array.installEventFilter(self)
        if self.basic_well_array:
            self.basic_well_array.installEventFilter(self)

    def find_layout_containing(self, widget):
        if not self.layout(): return None
        queue = [self.layout()]
        while queue:
            lay = queue.pop(0)
            if lay.indexOf(widget) != -1:
                return lay
            for i in range(lay.count()):
                item = lay.itemAt(i)
                if item.layout():
                    queue.append(item.layout())
        return None

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QEvent.MouseButtonPress or etype == QEvent.MouseButtonRelease or etype == QEvent.MouseMove:
            if obj == getattr(self, 'custom_well_array', None):
                # Only process MouseMove if button is down
                if etype == QEvent.MouseMove and not (event.buttons() & Qt.LeftButton):
                    return super().eventFilter(obj, event)

                w = obj.width()
                h = obj.height()
                cols = 8
                rows = 2
                
                if cols > 0 and rows > 0:
                    cw = w / cols
                    ch = h / rows
                    
                    pos = event.pos()
                    col = int(pos.x() / cw)
                    row = int(pos.y() / ch)
                    
                    # Ensure selection is within bounds
                    col = min(max(col, 0), cols - 1)
                    row = min(max(row, 0), rows - 1)

                    self.selected_custom_index = row * cols + col
                    # print(f"DEBUG: Index: {self.selected_custom_index} (Event: {etype})")
                    
                    if getattr(self, 'del_btn', None):
                        self.del_btn.setEnabled(True)
                        # self.del_btn.setText(f"删除选中颜色 ({self.selected_custom_index + 1})") 

            elif obj == getattr(self, 'basic_well_array', None):
                if etype == QEvent.MouseButtonPress:
                    # Basic colors clicked - deselect custom
                    self.selected_custom_index = -1
                    if getattr(self, 'del_btn', None):
                        self.del_btn.setEnabled(False)
                        # self.del_btn.setText("删除选中颜色")
                    
        return super().eventFilter(obj, event)

    def on_add_clicked(self):
        color = self.currentColor()
        target_index = -1
        
        # 1. Prioritize finding a "White" slot to overwrite
        for i in range(16):
            c = QColorDialog.customColor(i)
            # Compare with pure white. 
            if c == QColor(Qt.white): 
                target_index = i
                break
        
        # 2. If no empty slot found, defaults to the first slot (Index 0)
        if target_index == -1:
            target_index = 0
            
            # Note: We intentionally ignore self.selected_custom_index here
            # to strictly follow the rule: "Fill empty -> Overwrite First"
        
        QColorDialog.setCustomColor(target_index, color)
        
        # Refresh arrays
        if getattr(self, 'custom_well_array', None):
            self.custom_well_array.update()
        if getattr(self, 'basic_well_array', None):
             self.basic_well_array.update()

    def on_delete_clicked(self):
        print(f"DEBUG: Delete clicked. Index: {self.selected_custom_index}")
        if self.selected_custom_index != -1:
            old_c = QColorDialog.customColor(self.selected_custom_index)
            print(f"DEBUG: Color at {self.selected_custom_index} was {old_c.name()}")
            
            QColorDialog.setCustomColor(self.selected_custom_index, QColor(Qt.white))
            
            new_c = QColorDialog.customColor(self.selected_custom_index)
            print(f"DEBUG: Color at {self.selected_custom_index} set to {new_c.name()}")

            if hasattr(self, 'custom_well_array') and self.custom_well_array:
                self.custom_well_array.update()
                self.custom_well_array.repaint()

class SystemSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("参数设置")
        self.resize(780, 580)
        self.init_ui()

    def init_ui(self):
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Upper area layout (List + Stack)
        content_layout = QHBoxLayout()
        
        # Left sidebar (Navigation)
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(120)
        self.list_widget.addItems([
            "机器配置",
            "优化参数",
            "导入/导出",
            "界面参数",
            "主板信息"
        ])
        self.list_widget.currentRowChanged.connect(self.change_page)
        content_layout.addWidget(self.list_widget)
        
        # Right area (Stacked Widget)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setFrameShape(QFrame.StyledPanel)
        
        # Add pages
        self.stacked_widget.addWidget(self.create_machine_config_page())
        self.stacked_widget.addWidget(self.create_optimize_config_page())
        self.stacked_widget.addWidget(self.create_import_export_page())
        self.stacked_widget.addWidget(self.create_interface_config_page())
        self.stacked_widget.addWidget(self.create_mainboard_info_page())
        
        content_layout.addWidget(self.stacked_widget)
        main_layout.addLayout(content_layout)
        
        # Bottom Export/Import buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.btn_import_param = QPushButton("导入软件参数")
        self.btn_import_param.setFixedWidth(120)
        bottom_layout.addWidget(self.btn_import_param)
        
        self.btn_export_param = QPushButton("导出软件参数")
        self.btn_export_param.setFixedWidth(120)
        bottom_layout.addWidget(self.btn_export_param)
        
        bottom_layout.addStretch()
        
        # OK / Cancel Buttons
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        bottom_layout.addWidget(self.btn_ok)
        bottom_layout.addWidget(self.btn_cancel)
        
        main_layout.addLayout(bottom_layout)
        
        # Default selection
        self.list_widget.setCurrentRow(0)

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def accept(self):
        try:
            wb = None
            if self.parent() and hasattr(self.parent(), 'whiteboard'):
                 wb = self.parent().whiteboard

            if wb:
                # Update Page Size
                if hasattr(self, 'edit_page_w') and hasattr(self, 'edit_page_h'):
                    w = float(self.edit_page_w.text())
                    h = float(self.edit_page_h.text())
                    wb.set_work_size(w, h)
                
                # Update Origin
                if hasattr(self, 'origin_bg'):
                    loc = self.origin_bg.checkedId() # 1, 2, 3, 4
                    if loc > 0:
                        wb.set_origin_location(loc)
                
                # Update Laser Head Config
                if hasattr(self, 'pos_bg') and hasattr(self, 'chk_laser_relative'):
                    anchor = self.pos_bg.checkedId()
                    relative = self.chk_laser_relative.isChecked()
                    if hasattr(wb.canvas, 'set_laser_head_config'):
                        wb.canvas.set_laser_head_config(anchor, relative)
                
                # Update Pen/Laser/Process Offsets
                if hasattr(self, 'le_pen_x') and hasattr(wb.canvas, 'set_pen_offset_config'):
                    try:
                        pen_off = (float(self.le_pen_x.text()), float(self.le_pen_y.text()))
                        l2_off = (self.chk_laser2.isChecked(), float(self.le_l2_x.text()), float(self.le_l2_y.text()))
                        proc_off = (self.chk_process.isChecked(), float(self.le_proc_x.text()), float(self.le_proc_y.text()))
                        wb.canvas.set_pen_offset_config(pen_off, l2_off, proc_off)
                    except ValueError:
                        print("Error parsing offset values")

                # Update Import/Export Settings
                if hasattr(self, 'combo_plt_unit'):
                     imp_settings = {}
                     try:
                         imp_settings['plt_unit'] = self.combo_plt_unit.currentText()
                         imp_settings['text_height'] = float(self.edit_text_height.text() or 0)
                         imp_settings['dxf_unit'] = self.combo_dxf_unit.currentText()
                         imp_settings['dxf_custom_unit'] = float(self.edit_dxf_custom_unit.text() or 1.0)
                         
                         imp_settings['dxf_text'] = self.chk_dxf_text.isChecked()
                         imp_settings['dxf2'] = self.chk_dxf2.isChecked()
                         imp_settings['dxf_point'] = self.chk_dxf_point.isChecked()
                         
                         imp_settings['pt_circle'] = (self.chk_pt_circle.isChecked(), float(self.edit_pt_circle.text() or 0))
                         
                         imp_settings['ai_image'] = self.chk_ai_image.isChecked()
                         imp_settings['new_ai'] = self.chk_new_ai.isChecked()
                         imp_settings['ai_fill'] = self.chk_ai_fill.isChecked()
                         imp_settings['dst_color'] = self.chk_dst_color.isChecked()
                         imp_settings['no_ext'] = self.chk_no_ext.isChecked()
                         imp_settings['nc_unit'] = float(self.edit_nc_unit.text() or 0.1)
                         
                         imp_settings['d1d2'] = (self.chk_d1d2.isChecked(), int(self.combo_d1.currentText()))
                         imp_settings['field_name'] = self.chk_field_name.isChecked()
                         
                         # Right column settings
                         imp_settings['close_check'] = (self.chk_close.isChecked(), float(self.edit_close_tol.text() or 0))
                         imp_settings['merge_lines'] = (self.chk_merge.isChecked(), float(self.edit_merge_tol.text() or 0))
                         imp_settings['node_handle'] = (self.chk_node.isChecked(), float(self.edit_node_tol.text() or 0))
                         imp_settings['curve_smooth'] = (self.chk_smooth.isChecked(), float(self.edit_smooth_prec.text() or 0))
                         imp_settings['auto_group'] = self.chk_auto_group.isChecked()
                         imp_settings['imp_rdimage'] = self.chk_imp_rdimage.isChecked()
                         imp_settings['imp_clear'] = self.chk_imp_clear.isChecked()
                         imp_settings['imp_move'] = self.chk_imp_move.isChecked()
                         imp_settings['gap'] = (self.chk_gap.isChecked(), float(self.edit_gap.text() or 0))
                         
                         imp_settings['multi_file'] = self.chk_multi_file.isChecked()
                         imp_settings['single_app'] = self.chk_single_app.isChecked()
                         imp_settings['auto_rot'] = int(self.combo_auto_rot.currentText())
                         imp_settings['dock_pos'] = self.combo_dock_pos.currentText()
                     except Exception as e:
                         print(f"Error parsing import settings: {e}")
                     
                     wb.canvas.import_settings = imp_settings
                     
                     # Export Settings
                     exp_settings = {}
                     try:
                         exp_settings['out_call'] = self.chk_out_call.isChecked()
                         exp_settings['enable_count'] = self.chk_enable_count.isChecked()
                         exp_settings['f1_start'] = self.chk_f1_start.isChecked()
                         exp_settings['out_curve_prec'] = float(self.edit_out_curve_prec.text() or 80.0)
                         exp_settings['unit_size'] = self.combo_unit_size.currentText()
                         exp_settings['unit_speed'] = self.combo_unit_speed.currentText()
                     except Exception as e:
                         print(f"Error parsing export settings: {e}")
                     
                     wb.canvas.export_settings = exp_settings

        except Exception as e:
            print(f"Error saving page settings: {e}")
        super().accept()

    def create_machine_config_page(self):
        page = QWidget()
        layout = QGridLayout(page)
        layout.setAlignment(Qt.AlignTop)
        
        # --- Left Column ---
        left_layout = QVBoxLayout()
        
        # Page Size Group
        group_page = QGroupBox("页面尺寸")
        grid_page = QGridLayout(group_page)
        
        current_w = "1200.000"
        current_h = "800.000"
        try:
            if self.parent() and hasattr(self.parent(), 'whiteboard'):
                 canvas = self.parent().whiteboard.canvas
                 current_w = f"{canvas._work_w:.3f}"
                 current_h = f"{canvas._work_h:.3f}"
        except:
             pass

        grid_page.addWidget(QLabel("页面宽:"), 0, 0)
        self.edit_page_w = QLineEdit(current_w)
        grid_page.addWidget(self.edit_page_w, 0, 1)
        grid_page.addWidget(QLabel("mm"), 0, 2)
        grid_page.addWidget(QLabel("页面高:"), 1, 0)
        self.edit_page_h = QLineEdit(current_h)
        grid_page.addWidget(self.edit_page_h, 1, 1)
        grid_page.addWidget(QLabel("mm"), 1, 2)
        left_layout.addWidget(group_page)

        # Head Move Group
        group_head = QGroupBox()
        grid_head = QGridLayout(group_head)
        grid_head.addWidget(QLabel("互移头数:"), 0, 0)
        combo_head = QComboBox()
        combo_head.addItems(["1", "2", "3", "4"])
        combo_head.setMaxVisibleItems(10)
        combo_head.setEditable(True)
        combo_head.lineEdit().setReadOnly(True)
        grid_head.addWidget(combo_head, 0, 1)
        
        # Spacing inputs
        for i in range(1, 6):
            grid_head.addWidget(QLabel(f"间距{i}:"), i, 0)
            le = QLineEdit("100.000")
            le.setEnabled(False) # Probably disabled if head count is 1
            grid_head.addWidget(le, i, 1)
            grid_head.addWidget(QLabel("mm"), i, 2)
            
        left_layout.addWidget(group_head)
        
        # Sync checkbox
        hbox_sync = QHBoxLayout()
        hbox_sync.addWidget(QCheckBox("自动同步页面设置"))
        hbox_sync.addWidget(QPushButton("读取"))
        left_layout.addLayout(hbox_sync)
        left_layout.addStretch()

        # --- Right Column ---
        right_layout = QVBoxLayout()
        
        # Machine Origin & Laser Head Pos
        hbox_top_right = QHBoxLayout()
        
        # Machine Origin
        group_origin = QGroupBox("机器原点")
        grid_origin = QGridLayout(group_origin)
        # 4 corners radio buttons
        self.origin_bg = QButtonGroup(page)
        # Using radio buttons to simulate the circle indicators
        r1 = QRadioButton()
        r2 = QRadioButton()
        r3 = QRadioButton()
        r4 = QRadioButton() # Top-Left, Top-Right, Bottom-Left, Bottom-Right
        
        self.origin_bg.addButton(r1, 1)
        self.origin_bg.addButton(r2, 2)
        self.origin_bg.addButton(r3, 3)
        self.origin_bg.addButton(r4, 4)

        # Initialize from existing setting
        current_loc = 1
        try:
             if self.parent() and hasattr(self.parent(), 'whiteboard'):
                 canvas = self.parent().whiteboard.canvas
                 current_loc = getattr(canvas, '_origin_location', 1)
        except:
             pass
        
        # Check correct button
        if current_loc == 2: r2.setChecked(True)
        elif current_loc == 3: r3.setChecked(True)
        elif current_loc == 4: r4.setChecked(True)
        else: r1.setChecked(True)

        grid_origin.addWidget(r1, 0, 0)
        grid_origin.addWidget(r2, 0, 1)
        grid_origin.addWidget(r3, 1, 0)
        grid_origin.addWidget(r4, 1, 1)
        hbox_top_right.addWidget(group_origin)
        
        # Laser Head Pos
        group_laser_pos = QGroupBox("激光头位置")
        grid_pos = QGridLayout(group_laser_pos)
        self.pos_bg = QButtonGroup(page)
        # 3x3 grid
        idx = 1
        for r in range(3):
            for c in range(3):
                rb = QRadioButton()
                self.pos_bg.addButton(rb, idx)
                grid_pos.addWidget(rb, r, c)
                idx += 1
        
        self.chk_laser_relative = QCheckBox("相对页面定位")
        grid_pos.addWidget(self.chk_laser_relative, 3, 0, 1, 3)

        # Init from canvas settings
        current_laser_anchor = 1
        current_laser_relative = False
        try:
             if self.parent() and hasattr(self.parent(), 'whiteboard'):
                 canvas = self.parent().whiteboard.canvas
                 # If method exists
                 if hasattr(canvas, 'get_laser_head_config'):
                     current_laser_anchor, current_laser_relative = canvas.get_laser_head_config()
        except:
             pass
        
        btn = self.pos_bg.button(current_laser_anchor)
        if btn: btn.setChecked(True)
        else: 
            if self.pos_bg.button(1): self.pos_bg.button(1).setChecked(True)
            
        self.chk_laser_relative.setChecked(current_laser_relative)

        hbox_top_right.addWidget(group_laser_pos)
        
        right_layout.addLayout(hbox_top_right)
        
        # Pen Up/Down Mapping
        group_map = QGroupBox()
        hbox_map = QHBoxLayout(group_map)
        hbox_map.addWidget(QLabel("抬落笔轴映射:"))
        combo_map = QComboBox()
        combo_map.addItems(["Z", "U"])
        combo_map.setCurrentText("U")
        combo_map.setMaxVisibleItems(10)
        combo_map.setEditable(True)
        combo_map.lineEdit().setReadOnly(True)
        hbox_map.addWidget(combo_map)
        right_layout.addWidget(group_map)
        
        # Pen Offset
        group_offset = QGroupBox("画笔偏移:")
        grid_offset = QGridLayout(group_offset)
        
        # Pen Offset Widgets
        self.le_pen_x = QLineEdit("0.000")
        self.le_pen_y = QLineEdit("0.000")
        grid_offset.addWidget(QLabel("X:"), 0, 0)
        grid_offset.addWidget(self.le_pen_x, 0, 1)
        grid_offset.addWidget(QLabel("Y:"), 0, 2)
        grid_offset.addWidget(self.le_pen_y, 0, 3)
        
        # Laser 2 Offset Widgets
        self.chk_laser2 = QCheckBox("激光2偏移:")
        self.le_l2_x = QLineEdit("0.000")
        self.le_l2_y = QLineEdit("0.000")
        self.le_l2_x.setEnabled(False)
        self.le_l2_y.setEnabled(False)
        
        grid_offset.addWidget(self.chk_laser2, 1, 0, 1, 4)
        grid_offset.addWidget(QLabel("X:"), 2, 0)
        grid_offset.addWidget(self.le_l2_x, 2, 1)
        grid_offset.addWidget(QLabel("Y:"), 2, 2)
        grid_offset.addWidget(self.le_l2_y, 2, 3)
        self.chk_laser2.toggled.connect(self.le_l2_x.setEnabled)
        self.chk_laser2.toggled.connect(self.le_l2_y.setEnabled)
        
        # Process Offset Widgets
        self.chk_process = QCheckBox("加工偏移:")
        self.le_proc_x = QLineEdit("0.000")
        self.le_proc_y = QLineEdit("0.000")
        self.le_proc_x.setEnabled(False)
        self.le_proc_y.setEnabled(False)

        grid_offset.addWidget(self.chk_process, 3, 0, 1, 4)
        grid_offset.addWidget(QLabel("X:"), 4, 0)
        grid_offset.addWidget(self.le_proc_x, 4, 1)
        grid_offset.addWidget(QLabel("Y:"), 4, 2)
        grid_offset.addWidget(self.le_proc_y, 4, 3)
        self.chk_process.toggled.connect(self.le_proc_x.setEnabled)
        self.chk_process.toggled.connect(self.le_proc_y.setEnabled)

        # Initialize values from canvas
        if self.parent() and hasattr(self.parent(), 'whiteboard'):
            wb = self.parent().whiteboard
            if hasattr(wb.canvas, 'get_pen_offset_config'):
                pen_off, l2_off, proc_off = wb.canvas.get_pen_offset_config()
                # pen_off: (x, y)
                self.le_pen_x.setText(f"{pen_off[0]:.3f}")
                self.le_pen_y.setText(f"{pen_off[1]:.3f}")
                
                # l2_off: (enabled, x, y)
                self.chk_laser2.setChecked(l2_off[0])
                self.le_l2_x.setText(f"{l2_off[1]:.3f}")
                self.le_l2_y.setText(f"{l2_off[2]:.3f}")
                self.le_l2_x.setEnabled(l2_off[0])
                self.le_l2_y.setEnabled(l2_off[0])
                
                # proc_off: (enabled, x, y)
                self.chk_process.setChecked(proc_off[0])
                self.le_proc_x.setText(f"{proc_off[1]:.3f}")
                self.le_proc_y.setText(f"{proc_off[2]:.3f}")
                self.le_proc_x.setEnabled(proc_off[0])
                self.le_proc_y.setEnabled(proc_off[0])

        right_layout.addWidget(group_offset)
        right_layout.addStretch()

        # Combine
        layout.addLayout(left_layout, 0, 0)
        layout.addLayout(right_layout, 0, 1)
        return page

    def create_optimize_config_page(self):
        page = QWidget()
        layout = QGridLayout(page)
        
        # Left Side
        left_layout = QVBoxLayout()
        
        # Small Circle Speed Limit
        group_circle = QGroupBox("小圆限速")
        group_circle.setCheckable(True)
        group_circle.setChecked(False)
        vbox_circle = QVBoxLayout(group_circle)
        
        table_circle = QTableWidget(7, 2)
        table_circle.setHorizontalHeaderLabels(["直径(mm)", "速度(mm/s)"])
        table_circle.verticalHeader().setVisible(False)
        table_circle.setAlternatingRowColors(True)
        # Mock data
        data = [
            ("1.100", "15.00000"), ("2.100", "20.00000"), ("3.100", "25.00000"),
            ("4.100", "30.00000"), ("6.100", "35.00000"), ("8.100", "40.00000")
        ]
        for r, (d, s) in enumerate(data):
            table_circle.setItem(r, 0, QTableWidgetItem(d))
            table_circle.setItem(r, 1, QTableWidgetItem(s))
            
        vbox_circle.addWidget(table_circle)
        
        hbox_circle_btns = QHBoxLayout()
        hbox_circle_btns.addWidget(QPushButton("增加..."))
        hbox_circle_btns.addWidget(QPushButton("删除"))
        vbox_circle.addLayout(hbox_circle_btns)
        
        left_layout.addWidget(group_circle)
        
        # Cut controls
        grid_cut = QGridLayout()
        
        # Cut Direction
        chk_cut_dir = QCheckBox("切割旋向控制")
        grid_cut.addWidget(chk_cut_dir, 0, 0)
        
        combo_cut = QComboBox()
        combo_cut.addItems(["顺时针", "逆时针"])
        combo_cut.setEnabled(False)
        combo_cut.setMaxVisibleItems(10)
        combo_cut.setEditable(True)
        combo_cut.lineEdit().setReadOnly(True)
        grid_cut.addWidget(combo_cut, 0, 1)
        
        chk_cut_dir.toggled.connect(combo_cut.setEnabled)
        
        # Resonance Suppression
        chk_resonance = QCheckBox("共振速度区间抑制")
        grid_cut.addWidget(chk_resonance, 1, 0)
        
        # Container for resonance inputs to easily enable/disable all
        res_widget = QWidget()
        res_widget.setEnabled(False)
        hbox_res = QHBoxLayout(res_widget)
        hbox_res.setContentsMargins(0, 0, 0, 0)
        
        le_res_start = QLineEdit("20.0")
        hbox_res.addWidget(le_res_start)
        hbox_res.addWidget(QLabel("—"))
        le_res_end = QLineEdit("25.0")
        hbox_res.addWidget(le_res_end)
        hbox_res.addWidget(QLabel("mm/s"))
        
        grid_cut.addWidget(res_widget, 1, 1)
        
        chk_resonance.toggled.connect(res_widget.setEnabled)
        
        left_layout.addLayout(grid_cut)
        left_layout.addStretch()

        # Right Side
        right_layout = QVBoxLayout()
        
        # Scan settings
        hb_scan_dir = QHBoxLayout()
        hb_scan_dir.addWidget(QLabel("扫描方向:"))
        combo_scan = QComboBox()
        combo_scan.addItems([
            "从下往上(从左往右)",
            "从下往上(从右往左)",
            "从上往下(从左往右)",
            "从上往下(从右往左)"
        ])
        combo_scan.setMaxVisibleItems(10)
        combo_scan.setEditable(True)
        combo_scan.lineEdit().setReadOnly(True)
        hb_scan_dir.addWidget(combo_scan)
        right_layout.addLayout(hb_scan_dir)
        
        right_layout.addWidget(QCheckBox("启用主板补偿方式"))
        
        chk_scan_backlash = QCheckBox("扫描(反向间隙)")
        right_layout.addWidget(chk_scan_backlash)
        
        # Container for backlash settings to enable/disable
        backlash_widget = QWidget()
        backlash_layout = QVBoxLayout(backlash_widget)
        backlash_layout.setContentsMargins(0,0,0,0)
        
        # X/Y Radio
        hbox_xy = QHBoxLayout()
        rb_x = QRadioButton("X")
        rb_x.setChecked(True)
        hbox_xy.addWidget(rb_x)
        hbox_xy.addWidget(QRadioButton("Y"))
        hbox_xy.addStretch()
        backlash_layout.addLayout(hbox_xy)
        
        # Scan Table
        table_scan = QTableWidget(5, 3)
        table_scan.setHorizontalHeaderLabels(["速度(mm/s)", "反向间隙(mm)", "偏移补偿"])
        table_scan.verticalHeader().setVisible(False)
        backlash_layout.addWidget(table_scan)
        
        # Buttons
        hbox_scan_btns = QHBoxLayout()
        hbox_scan_btns.addWidget(QPushButton("增加..."))
        hbox_scan_btns.addWidget(QPushButton("删除"))
        hbox_scan_btns.addWidget(QPushButton("读"))
        hbox_scan_btns.addWidget(QPushButton("写"))
        backlash_layout.addLayout(hbox_scan_btns)
        
        right_layout.addWidget(backlash_widget)

        # Logic: Disable backlash settings if not checked
        backlash_widget.setEnabled(False) 
        chk_scan_backlash.toggled.connect(backlash_widget.setEnabled)
        
        btn_energy = QPushButton("能量映射")
        right_layout.addWidget(btn_energy)
        right_layout.addStretch()

        layout.addLayout(left_layout, 0, 0)
        layout.addLayout(right_layout, 0, 1)
        return page

    def create_import_export_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        
        # Left: Import Settings & Output Settings
        left_widget = QWidget()
        left_vbox = QVBoxLayout(left_widget)
        left_vbox.setContentsMargins(0,0,0,0)
        
        # Import Params Group
        grp_import = QGroupBox("导入文件的参数设置")
        grid_imp = QGridLayout(grp_import)
        
        # Row 0
        grid_imp.addWidget(QLabel("PLT的绘图单位:"), 0, 0)
        self.combo_plt_unit = QComboBox()
        self.combo_plt_unit.addItems(["1016", "1000"])
        self.combo_plt_unit.setMaxVisibleItems(10)
        self.combo_plt_unit.setEditable(True)
        self.combo_plt_unit.lineEdit().setReadOnly(True)
        grid_imp.addWidget(self.combo_plt_unit, 0, 1)
        
        # Row 1
        grid_imp.addWidget(QLabel("文字高度:"), 1, 0)
        self.edit_text_height = QLineEdit("10.000")
        grid_imp.addWidget(self.edit_text_height, 1, 1)
        
        # Row 2
        grid_imp.addWidget(QLabel("DXF数据单位:"), 2, 0)
        
        dxf_widget = QWidget()
        dxf_layout = QHBoxLayout(dxf_widget)
        dxf_layout.setContentsMargins(0, 0, 0, 0)
        
        self.edit_dxf_custom_unit = QLineEdit("1.000")
        self.edit_dxf_custom_unit.setVisible(False)
        dxf_layout.addWidget(self.edit_dxf_custom_unit)
        
        self.combo_dxf_unit = QComboBox()
        self.combo_dxf_unit.addItems(["毫米", "厘米", "英寸", "自定义"])
        self.combo_dxf_unit.setMaxVisibleItems(10)
        self.combo_dxf_unit.setEditable(True)
        self.combo_dxf_unit.lineEdit().setReadOnly(True)
        dxf_layout.addWidget(self.combo_dxf_unit)
        
        grid_imp.addWidget(dxf_widget, 2, 1)
        
        self.combo_dxf_unit.currentTextChanged.connect(lambda t: self.edit_dxf_custom_unit.setVisible(t == "自定义"))
        
        # Checkboxes
        self.chk_dxf_text = QCheckBox("导入Dxf文字信息")
        grid_imp.addWidget(self.chk_dxf_text, 3, 0)
        self.chk_dxf2 = QCheckBox("DXF2格式导入")
        grid_imp.addWidget(self.chk_dxf2, 3, 1)
        self.chk_dxf_point = QCheckBox("导入DXF点")
        grid_imp.addWidget(self.chk_dxf_point, 4, 0)
        
        hbox_pt = QHBoxLayout()
        self.chk_pt_circle = QCheckBox()
        self.chk_pt_circle.setChecked(False)
        hbox_pt.addWidget(self.chk_pt_circle)
        hbox_pt.addWidget(QLabel("点转圆"))
        self.edit_pt_circle = QLineEdit("1.000")
        self.edit_pt_circle.setEnabled(False)
        hbox_pt.addWidget(self.edit_pt_circle)
        self.chk_pt_circle.toggled.connect(self.edit_pt_circle.setEnabled)
        grid_imp.addLayout(hbox_pt, 4, 1)
        
        self.chk_ai_image = QCheckBox("导入AI文件图片数据")
        grid_imp.addWidget(self.chk_ai_image, 5, 0)
        self.chk_new_ai = QCheckBox("新AI导入")
        grid_imp.addWidget(self.chk_new_ai, 5, 1)
        self.chk_ai_fill = QCheckBox("允许导入AI填充轮廓")
        grid_imp.addWidget(self.chk_ai_fill, 6, 0)
        
        self.chk_dst_color = QCheckBox("导入DST支持颜色层")
        grid_imp.addWidget(self.chk_dst_color, 7, 0, 1, 2)
        self.chk_no_ext = QCheckBox("支持无后缀名文件")
        grid_imp.addWidget(self.chk_no_ext, 8, 0, 1, 2)
        
        hbox_nc = QHBoxLayout()
        hbox_nc.addWidget(QLabel("NC图形单位:"))
        self.edit_nc_unit = QLineEdit("0.10000")
        hbox_nc.addWidget(self.edit_nc_unit)
        grid_imp.addLayout(hbox_nc, 9, 0, 1, 2)
        
        hbox_d1d2 = QHBoxLayout()
        self.chk_d1d2 = QCheckBox("使能D1/D2指令")
        self.combo_d1 = QComboBox()
        self.combo_d1.addItems([str(i) for i in range(1, 21)])
        self.combo_d1.setCurrentText("14")
        self.combo_d1.setFixedWidth(60)
        self.combo_d1.setMaxVisibleItems(10)
        self.combo_d1.setEditable(True)
        self.combo_d1.lineEdit().setReadOnly(True)
        
        self.chk_d1d2.toggled.connect(self.combo_d1.setEnabled)
        self.combo_d1.setEnabled(False) # Default disabled
        
        hbox_d1d2.addWidget(self.chk_d1d2)
        hbox_d1d2.addWidget(self.combo_d1)
        hbox_d1d2.addStretch()
        grid_imp.addLayout(hbox_d1d2, 10, 0, 1, 2)
        
        self.chk_field_name = QCheckBox("取名称中指定字段为裁片名称")
        grid_imp.addWidget(self.chk_field_name, 11, 0, 1, 2)
        
        left_vbox.addWidget(grp_import)
        
        # Output Settings Group
        grp_out = QGroupBox("输出数据的设置:")
        grid_out = QGridLayout(grp_out)
        
        self.chk_out_call = QCheckBox("外部调用时直接输出加工")
        grid_out.addWidget(self.chk_out_call, 0, 0, 1, 2)
        
        self.chk_enable_count = QCheckBox("使能直接输出计件")
        self.btn_clear_count = QPushButton("件数清零")
        self.chk_enable_count.toggled.connect(self.btn_clear_count.setEnabled)
        self.btn_clear_count.setEnabled(False) # Initial state
        
        grid_out.addWidget(self.chk_enable_count, 1, 0)
        grid_out.addWidget(self.btn_clear_count, 1, 1)
        
        self.chk_f1_start = QCheckBox("快捷键启动加工(F1)")
        grid_out.addWidget(self.chk_f1_start, 2, 0)
        
        hbox_curve = QHBoxLayout()
        hbox_curve.addWidget(QLabel("输出数据的曲线精度(%):"))
        self.edit_out_curve_prec = QLineEdit("80.000")
        hbox_curve.addWidget(self.edit_out_curve_prec)
        grid_out.addLayout(hbox_curve, 3, 0, 1, 2)
        
        hbox_unit_size = QHBoxLayout()
        hbox_unit_size.addWidget(QLabel("界面显示的尺寸单位:"))
        self.combo_unit_size = QComboBox()
        self.combo_unit_size.addItems(["mm", "inch"])
        self.combo_unit_size.setMaxVisibleItems(10)
        self.combo_unit_size.setEditable(True)
        self.combo_unit_size.lineEdit().setReadOnly(True)
        hbox_unit_size.addWidget(self.combo_unit_size)
        grid_out.addLayout(hbox_unit_size, 4, 0, 1, 2)
        
        hbox_unit_spd = QHBoxLayout()
        hbox_unit_spd.addWidget(QLabel("界面显示的速度单位:"))
        self.combo_unit_speed = QComboBox()
        self.combo_unit_speed.addItems(["m/min", "mm/s", "inch/s"])
        self.combo_unit_speed.setCurrentText("mm/s")
        self.combo_unit_speed.setMaxVisibleItems(10)
        self.combo_unit_speed.setEditable(True)
        self.combo_unit_speed.lineEdit().setReadOnly(True)
        hbox_unit_spd.addWidget(self.combo_unit_speed)
        grid_out.addLayout(hbox_unit_spd, 5, 0, 1, 2)
        
        left_vbox.addWidget(grp_out)
        layout.addWidget(left_widget)
        
        # Right Widget
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Grouped options
        gb_handle = QGroupBox()
        gl_handle = QGridLayout(gb_handle)
        
        # Close Check
        self.chk_close = QCheckBox("闭合检查")
        self.edit_close_tol = QLineEdit("0.100")
        self.chk_close.toggled.connect(self.edit_close_tol.setEnabled)
        self.edit_close_tol.setEnabled(False)
        gl_handle.addWidget(self.chk_close, 0, 0)
        gl_handle.addWidget(QLabel("闭合容差(mm):"), 0, 1)
        gl_handle.addWidget(self.edit_close_tol, 0, 2)

        # Merge Lines
        self.chk_merge = QCheckBox("合并相连线")
        self.edit_merge_tol = QLineEdit("0.100")
        self.chk_merge.toggled.connect(self.edit_merge_tol.setEnabled)
        self.edit_merge_tol.setEnabled(False)
        gl_handle.addWidget(self.chk_merge, 1, 0)
        gl_handle.addWidget(QLabel("合并容差(mm):"), 1, 1)
        gl_handle.addWidget(self.edit_merge_tol, 1, 2)

        # Node Handle
        self.chk_node = QCheckBox("节点处理")
        self.edit_node_tol = QLineEdit("0.000")
        self.chk_node.toggled.connect(self.edit_node_tol.setEnabled)
        self.edit_node_tol.setEnabled(False)
        gl_handle.addWidget(self.chk_node, 2, 0)
        gl_handle.addWidget(QLabel("节点容差(mm):"), 2, 1)
        gl_handle.addWidget(self.edit_node_tol, 2, 2)
        
        # Curve Smooth
        self.chk_smooth = QCheckBox("曲线平滑")
        self.edit_smooth_prec = QLineEdit("30.0")
        self.chk_smooth.toggled.connect(self.edit_smooth_prec.setEnabled)
        self.edit_smooth_prec.setEnabled(False)
        gl_handle.addWidget(self.chk_smooth, 3, 0)
        gl_handle.addWidget(QLabel("平滑精度(%):"), 3, 1)
        gl_handle.addWidget(self.edit_smooth_prec, 3, 2)
        
        # Import Advanced
        self.chk_imp_adv = QCheckBox("导入高级参数")
        self.btn_imp_adv = QPushButton("...")
        self.chk_imp_adv.toggled.connect(self.btn_imp_adv.setEnabled)
        self.btn_imp_adv.setEnabled(False)
        gl_handle.addWidget(self.chk_imp_adv, 4, 0)
        gl_handle.addWidget(self.btn_imp_adv, 4, 2)
        
        self.chk_auto_group = QCheckBox("自动群组")
        gl_handle.addWidget(self.chk_auto_group, 5, 0)
        
        right_layout.addWidget(gb_handle)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        right_layout.addWidget(line)
        
        self.chk_imp_rdimage = QCheckBox("导入图片默认用RDImage打开")
        right_layout.addWidget(self.chk_imp_rdimage)
        self.chk_imp_clear = QCheckBox("导入时自动清空所有图形")
        right_layout.addWidget(self.chk_imp_clear)
        
        hbox_bg = QHBoxLayout()
        self.chk_imp_move = QCheckBox("导入时下移所有图形")
        hbox_bg.addWidget(self.chk_imp_move)
        hbox_bg.addStretch()
        right_layout.addLayout(hbox_bg)
        
        hbox_gap = QHBoxLayout()
        hbox_gap.addStretch()
        self.chk_gap = QCheckBox("图形间隔:")
        self.edit_gap = QLineEdit("0.000")
        self.chk_gap.toggled.connect(self.edit_gap.setEnabled)
        self.edit_gap.setEnabled(False)
        hbox_gap.addWidget(self.chk_gap)
        hbox_gap.addWidget(self.edit_gap)
        hbox_gap.addWidget(QLabel("mm"))
        right_layout.addLayout(hbox_gap)
        
        self.chk_multi_file = QCheckBox("一次导入多个文件")
        right_layout.addWidget(self.chk_multi_file)
        self.chk_single_app = QCheckBox("只允许打开一个应用")
        right_layout.addWidget(self.chk_single_app)
        
        hbox_rot = QHBoxLayout()
        hbox_rot.addWidget(QLabel("导入图形自动旋转:"))
        self.combo_auto_rot = QComboBox()
        self.combo_auto_rot.addItems(["0", "90", "180", "270"])
        self.combo_auto_rot.setCurrentText("0")
        self.combo_auto_rot.setMaxVisibleItems(10)
        self.combo_auto_rot.setEditable(True)
        self.combo_auto_rot.lineEdit().setReadOnly(True)
        hbox_rot.addWidget(self.combo_auto_rot)
        right_layout.addLayout(hbox_rot)
        
        hbox_dock = QHBoxLayout()
        hbox_dock.addWidget(QLabel("导入图形停靠位置:"))
        self.combo_dock_pos = QComboBox()
        self.combo_dock_pos.addItems(["无", "中心", "左上", "右上", "右下", "左下", "按坐标"])
        self.combo_dock_pos.setMaxVisibleItems(10)
        self.combo_dock_pos.setEditable(True)
        self.combo_dock_pos.lineEdit().setReadOnly(True)
        hbox_dock.addWidget(self.combo_dock_pos)
        right_layout.addLayout(hbox_dock)
        
        right_layout.addStretch()
        layout.addWidget(right_widget)
        
        # Load logic (if exists)
        self._load_import_export_ui()
        
        return page

    def _load_import_export_ui(self, widget=None):
        try:
             if self.parent() and hasattr(self.parent(), 'whiteboard'):
                 canvas = self.parent().whiteboard.canvas
                 # Import Settings
                 imp = getattr(canvas, 'import_settings', {})
                 # Example: {'plt_unit': '1016', 'text_height': '10.0', ...}
                 
                 if 'plt_unit' in imp: self.combo_plt_unit.setCurrentText(str(imp['plt_unit']))
                 if 'text_height' in imp: self.edit_text_height.setText(str(imp['text_height']))
                 if 'dxf_unit' in imp: self.combo_dxf_unit.setCurrentText(str(imp['dxf_unit']))
                 if 'dxf_custom_unit' in imp: self.edit_dxf_custom_unit.setText(str(imp['dxf_custom_unit']))
                 
                 if 'dxf_text' in imp: self.chk_dxf_text.setChecked(imp['dxf_text'])
                 if 'dxf2' in imp: self.chk_dxf2.setChecked(imp['dxf2'])
                 if 'dxf_point' in imp: self.chk_dxf_point.setChecked(imp['dxf_point'])
                 
                 if 'pt_circle' in imp: 
                     self.chk_pt_circle.setChecked(imp['pt_circle'][0])
                     self.edit_pt_circle.setText(str(imp['pt_circle'][1]))
                     
                 if 'ai_image' in imp: self.chk_ai_image.setChecked(imp['ai_image'])
                 if 'new_ai' in imp: self.chk_new_ai.setChecked(imp['new_ai'])
                 if 'ai_fill' in imp: self.chk_ai_fill.setChecked(imp['ai_fill'])
                 if 'dst_color' in imp: self.chk_dst_color.setChecked(imp['dst_color'])
                 if 'no_ext' in imp: self.chk_no_ext.setChecked(imp['no_ext'])
                 if 'nc_unit' in imp: self.edit_nc_unit.setText(str(imp['nc_unit']))
                 
                 if 'd1d2' in imp:
                     self.chk_d1d2.setChecked(imp['d1d2'][0])
                     self.combo_d1.setCurrentText(str(imp['d1d2'][1]))
                     
                 if 'field_name' in imp: self.chk_field_name.setChecked(imp['field_name'])
                 
                 # Right settings
                 if 'close_check' in imp:
                     self.chk_close.setChecked(imp['close_check'][0])
                     self.edit_close_tol.setText(str(imp['close_check'][1]))
                     
                 if 'merge_lines' in imp:
                     self.chk_merge.setChecked(imp['merge_lines'][0])
                     self.edit_merge_tol.setText(str(imp['merge_lines'][1]))
                     
                 if 'node_handle' in imp:
                     self.chk_node.setChecked(imp['node_handle'][0])
                     self.edit_node_tol.setText(str(imp['node_handle'][1]))
                 
                 if 'curve_smooth' in imp:
                     self.chk_smooth.setChecked(imp['curve_smooth'][0])
                     self.edit_smooth_prec.setText(str(imp['curve_smooth'][1]))
                     
                 if 'auto_group' in imp: self.chk_auto_group.setChecked(imp['auto_group'])
                 if 'imp_rdimage' in imp: self.chk_imp_rdimage.setChecked(imp['imp_rdimage'])
                 if 'imp_clear' in imp: self.chk_imp_clear.setChecked(imp['imp_clear'])
                 if 'imp_move' in imp: self.chk_imp_move.setChecked(imp['imp_move'])
                 if 'gap' in imp: 
                      self.chk_gap.setChecked(imp['gap'][0])
                      self.edit_gap.setText(str(imp['gap'][1]))
                 
                 if 'multi_file' in imp: self.chk_multi_file.setChecked(imp['multi_file'])
                 if 'single_app' in imp: self.chk_single_app.setChecked(imp['single_app'])
                 if 'auto_rot' in imp: self.combo_auto_rot.setCurrentText(str(imp['auto_rot']))
                 if 'dock_pos' in imp: self.combo_dock_pos.setCurrentText(str(imp['dock_pos']))

                 # Output Settings (Export Settings)
                 exp = getattr(canvas, 'export_settings', {})
                 if 'out_call' in exp: self.chk_out_call.setChecked(exp['out_call'])
                 if 'enable_count' in exp: self.chk_enable_count.setChecked(exp['enable_count'])
                 if 'f1_start' in exp: self.chk_f1_start.setChecked(exp['f1_start'])
                 if 'out_curve_prec' in exp: self.edit_out_curve_prec.setText(str(exp['out_curve_prec']))
                 if 'unit_size' in exp: self.combo_unit_size.setCurrentText(str(exp['unit_size']))
                 if 'unit_speed' in exp: self.combo_unit_speed.setCurrentText(str(exp['unit_speed']))
        except Exception as e:
            print(f"Error loading import/export settings: {e}")

    def get_interface_settings(self):
        return {
            "grid_enabled": self.chk_grid_enable.isChecked(),
            "grid_spacing": float(self.edit_grid_spacing.text()),
            "color_background": self.lbl_bg_color.color,
            "color_workspace": self.lbl_work_color.color,
            "color_grid": self.lbl_grid_color.color,
            "grid_line_width": int(self.combo_lw.currentText()),
            "nudge_distance": float(self.edit_nudge_dist.text()),
            "big_nudge_scale": float(self.edit_big_nudge_scale.text()),
            "rotate_angle": float(self.edit_rotate_angle.text()),
            "disable_stretch": self.chk_disable_stretch.isChecked(),
            "paste_offset_enable": self.rb_paste_offset.isChecked(),
            "paste_x": float(self.edit_paste_x.text()),
            "paste_y": float(self.edit_paste_y.text()),
            "log_enabled": self.grp_log.isChecked(),
            "log_operator": self.edit_operator.text(),
            "log_area": self.edit_area.text(),
            "log_path": self.edit_log_path.text(),
            
            # Output
            "out_call_processing": self.chk_out_call.isChecked(),
            "enable_piece_count": self.chk_enable_count.isChecked(),
            "f1_start_processing": self.chk_f1_start.isChecked(),
            "out_curve_precision": self.edit_out_curve_prec.text(),
            
            # Handle Group
            "close_check": self.chk_close.isChecked(),
            "close_tol": self.edit_close_tol.text(),
            "merge_lines": self.chk_merge.isChecked(),
            "merge_tol": self.edit_merge_tol.text(),
            "node_handle": self.chk_node.isChecked(),
            "node_tol": self.edit_node_tol.text(),
            "curve_smooth": self.chk_smooth.isChecked(),
            "smooth_prec": self.edit_smooth_prec.text(),
            "import_adv": self.chk_imp_adv.isChecked(),
            "auto_group": self.chk_auto_group.isChecked(),
            "point_circle": self.chk_pt_circle.isChecked(),
            "point_circle_val": self.edit_pt_circle.text(),
            
            # Import Misc
            "imp_rdimage": self.chk_imp_rdimage.isChecked(),
            "imp_clear": self.chk_imp_clear.isChecked(),
            "imp_move_down": self.chk_imp_move.isChecked(),
            "graph_spacing_enable": self.chk_gap.isChecked(),
            "graph_spacing": self.edit_gap.text(),
            
            # Import D1D2
            "d1d2_enable": self.chk_d1d2.isChecked(),
            "d1d2_value": self.combo_d1.currentText(),
        }

    def choose_log_path(self):
        directory = QFileDialog.getExistingDirectory(self, "选择日志目录", self.edit_log_path.text())
        if directory:
            # Ensure trailing slash if you want consistency with screenshot, though not strictly required by logic
            # Screenshot has C:\RDWorksV8\Log\
            import os
            self.edit_log_path.setText(os.path.normpath(directory) + os.sep)

    def load_interface_settings(self, settings):
        if not settings: return
        self.chk_grid_enable.setChecked(settings.get("grid_enabled", True))
        self.edit_grid_spacing.setText(str(settings.get("grid_spacing", 20.0)))
        if "color_background" in settings:
            self.lbl_bg_color.color = settings["color_background"]
            self.lbl_bg_color.updated_color()
        if "color_workspace" in settings:
            self.lbl_work_color.color = settings["color_workspace"]
            self.lbl_work_color.updated_color()
        if "color_grid" in settings:
            self.lbl_grid_color.color = settings["color_grid"]
            self.lbl_grid_color.updated_color()
        if "grid_line_width" in settings:
            self.combo_lw.setCurrentText(str(settings.get("grid_line_width", 1)))
            
        self.edit_nudge_dist.setText(str(settings.get("nudge_distance", 1.0)))
        self.edit_big_nudge_scale.setText(str(settings.get("big_nudge_scale", 10.0)))
        self.edit_rotate_angle.setText(str(settings.get("rotate_angle", 1.0)))
        self.chk_disable_stretch.setChecked(settings.get("disable_stretch", False))
        
        if settings.get("paste_offset_enable", True):
            self.rb_paste_offset.setChecked(True)
        else:
            self.rb_paste_mouse.setChecked(True)
            
        self.edit_paste_x.setText(str(settings.get("paste_x", 0.0)))
        self.edit_paste_y.setText(str(settings.get("paste_y", 0.0)))
        
        self.grp_log.setChecked(settings.get("log_enabled", True))
        self.edit_operator.setText(settings.get("log_operator", "Normal operator"))
        self.edit_area.setText(settings.get("log_area", "A"))
        self.edit_log_path.setText(settings.get("log_path", r"C:\RDWorksV8\Log\\"))

        # New Settings
        self.chk_out_call.setChecked(settings.get("out_call_processing", False))
        self.chk_enable_count.setChecked(settings.get("enable_piece_count", False))
        self.btn_clear_count.setEnabled(self.chk_enable_count.isChecked())
        
        self.chk_f1_start.setChecked(settings.get("f1_start_processing", False))
        self.edit_out_curve_prec.setText(settings.get("out_curve_precision", "80.000"))
        
        self.chk_close.setChecked(settings.get("close_check", False))
        self.edit_close_tol.setText(settings.get("close_tol", "0.100"))
        self.edit_close_tol.setEnabled(self.chk_close.isChecked())
        
        self.chk_merge.setChecked(settings.get("merge_lines", False))
        self.edit_merge_tol.setText(settings.get("merge_tol", "0.100"))
        self.edit_merge_tol.setEnabled(self.chk_merge.isChecked())
        
        self.chk_node.setChecked(settings.get("node_handle", False))
        self.edit_node_tol.setText(settings.get("node_tol", "0.000"))
        self.edit_node_tol.setEnabled(self.chk_node.isChecked())
        
        self.chk_smooth.setChecked(settings.get("curve_smooth", False))
        self.edit_smooth_prec.setText(settings.get("smooth_prec", "30.0"))
        self.edit_smooth_prec.setEnabled(self.chk_smooth.isChecked())
        
        self.chk_imp_adv.setChecked(settings.get("import_adv", False))
        self.btn_imp_adv.setEnabled(self.chk_imp_adv.isChecked())
        
        self.chk_auto_group.setChecked(settings.get("auto_group", False))
        
        self.chk_pt_circle.setChecked(settings.get("point_circle", False))
        self.edit_pt_circle.setText(settings.get("point_circle_val", "1.000"))
        self.edit_pt_circle.setEnabled(self.chk_pt_circle.isChecked())
        
        self.chk_imp_rdimage.setChecked(settings.get("imp_rdimage", False))
        self.chk_imp_clear.setChecked(settings.get("imp_clear", False))
        self.chk_imp_move.setChecked(settings.get("imp_move_down", False))
        
        self.chk_gap.setChecked(settings.get("graph_spacing_enable", False))
        self.edit_gap.setText(settings.get("graph_spacing", "0.000"))
        self.edit_gap.setEnabled(self.chk_gap.isChecked())
        
        self.chk_d1d2.setChecked(settings.get("d1d2_enable", False))
        self.combo_d1.setCurrentText(settings.get("d1d2_value", "14"))
        self.combo_d1.setEnabled(self.chk_d1d2.isChecked())

    def create_interface_config_page(self):
        page = QWidget()
        layout = QGridLayout(page)
        
        # Left
        left_layout = QVBoxLayout()
        
        # Grid
        grp_grid = QGroupBox("网格")
        hbox_grid = QHBoxLayout(grp_grid)
        self.chk_grid_enable = QCheckBox()
        self.chk_grid_enable.setChecked(True)
        hbox_grid.addWidget(self.chk_grid_enable)
        hbox_grid.addWidget(QLabel("网格间距:"))
        self.edit_grid_spacing = QLineEdit("20.000")
        hbox_grid.addWidget(self.edit_grid_spacing)
        hbox_grid.addWidget(QLabel("mm"))
        left_layout.addWidget(grp_grid)
        
        # Color
        grp_color = QGroupBox("颜色配置")
        grid_color = QGridLayout(grp_color)
        grid_color.addWidget(QLabel("背景"), 0, 0)
        grid_color.addWidget(QLabel("工作区"), 0, 1)
        grid_color.addWidget(QLabel("网格"), 0, 2)
        
        class ColorLabel(QLabel):
            def __init__(self, color_name):
                super().__init__()
                self.setFixedSize(40, 20)
                self.color = QColor(color_name)
                self.updated_color()

            def updated_color(self):
                # Update style sheet but keep the border
                self.setStyleSheet(f"background-color: {self.color.name()}; border: 1px solid gray;")

            def mousePressEvent(self, event):
                if event.button() == Qt.LeftButton:
                    dlg = CustomColorDialog(self.color, self.window(), "颜色")
                    if dlg.exec_() == QDialog.Accepted:
                        if dlg.selectedColor().isValid():
                            self.color = dlg.selectedColor()
                            self.updated_color()
        
        self.lbl_bg_color = ColorLabel("white")
        self.lbl_work_color = ColorLabel("black")
        self.lbl_grid_color = ColorLabel("gray")

        grid_color.addWidget(self.lbl_bg_color, 1, 0)
        grid_color.addWidget(self.lbl_work_color, 1, 1)
        grid_color.addWidget(self.lbl_grid_color, 1, 2)
        
        hbox_lw = QHBoxLayout()
        hbox_lw.addStretch()
        hbox_lw.addWidget(QLabel("线宽:"))
        self.combo_lw = QComboBox()
        self.combo_lw.addItems([str(i) for i in range(1, 6)])
        self.combo_lw.setCurrentText("1")
        self.combo_lw.setMaxVisibleItems(10)
        self.combo_lw.setEditable(True)
        self.combo_lw.lineEdit().setReadOnly(True)
        hbox_lw.addWidget(self.combo_lw)
        
        # Add layout to grid (spanning)
        grid_color.addLayout(hbox_lw, 2, 0, 1, 3)
        left_layout.addWidget(grp_color)
        
        # Keyboard
        grp_kb = QGroupBox("键盘")
        grid_kb = QGridLayout(grp_kb)
        
        grid_kb.addWidget(QLabel("微调距离:"), 0, 0)
        self.edit_nudge_dist = QLineEdit("1.000")
        grid_kb.addWidget(self.edit_nudge_dist, 0, 1)
        grid_kb.addWidget(QLabel("mm"), 0, 2)
        
        grid_kb.addWidget(QLabel("大调整比例:"), 1, 0)
        self.edit_big_nudge_scale = QLineEdit("10.000")
        grid_kb.addWidget(self.edit_big_nudge_scale, 1, 1)
        
        grid_kb.addWidget(QLabel("旋转角度:"), 2, 0)
        self.edit_rotate_angle = QLineEdit("1.000")
        grid_kb.addWidget(self.edit_rotate_angle, 2, 1)
        grid_kb.addWidget(QLabel("°"), 2, 2)
        
        left_layout.addWidget(grp_kb)
        
        self.chk_disable_stretch = QCheckBox("禁用图形拉伸拖动")
        left_layout.addWidget(self.chk_disable_stretch)
        left_layout.addStretch()
        
        # Right
        right_layout = QVBoxLayout()
        
        # Copy Paste
        grp_cp = QGroupBox("复制粘贴")
        vbox_cp = QVBoxLayout(grp_cp)
        self.rb_paste_mouse = QRadioButton("在鼠标当前位置粘贴")
        self.rb_paste_offset = QRadioButton("偏移复制") # Default check comes in load
        vbox_cp.addWidget(self.rb_paste_mouse)
        vbox_cp.addWidget(self.rb_paste_offset)
        
        hbox_cp_input = QHBoxLayout()
        hbox_cp_input.addSpacing(20)
        hbox_cp_input.addWidget(QLabel("X:"))
        self.edit_paste_x = QLineEdit("0.000")
        hbox_cp_input.addWidget(self.edit_paste_x)
        hbox_cp_input.addWidget(QLabel("Y:"))
        self.edit_paste_y = QLineEdit("0.000")
        hbox_cp_input.addWidget(self.edit_paste_y)
        vbox_cp.addLayout(hbox_cp_input)
        right_layout.addWidget(grp_cp)

        # Logic
        self.rb_paste_mouse.setChecked(True)
        self.edit_paste_x.setEnabled(False)
        self.edit_paste_y.setEnabled(False)
        
        self.rb_paste_offset.toggled.connect(self.edit_paste_x.setEnabled)
        self.rb_paste_offset.toggled.connect(self.edit_paste_y.setEnabled)
        
        # Log
        self.grp_log = QGroupBox()
        self.grp_log.setCheckable(True)
        self.grp_log.setTitle("启用日志")
        self.grp_log.setChecked(True)
        grid_log = QGridLayout(self.grp_log)
        
        grid_log.addWidget(QLabel("操作员:"), 0, 0)
        self.edit_operator = QLineEdit("Normal operator")
        grid_log.addWidget(self.edit_operator, 0, 1)
        
        grid_log.addWidget(QLabel("区域:"), 1, 0)
        self.edit_area = QLineEdit("A")
        grid_log.addWidget(self.edit_area, 1, 1)
        
        self.edit_log_path = QLineEdit("C:\\RDWorksV8\\Log\\")
        grid_log.addWidget(self.edit_log_path, 2, 0, 1, 2)
        btn_log_path = QPushButton("指定日志路径")
        btn_log_path.clicked.connect(self.choose_log_path)
        grid_log.addWidget(btn_log_path, 3, 0, 1, 2)
        right_layout.addWidget(self.grp_log)
        
        # IOT (Keep simplified as placeholder if needed, or remove if not requested, but keeping existing is good)
        grp_iot = QGroupBox()
        grp_iot.setStyleSheet("border: none")
        vbox_iot = QVBoxLayout(grp_iot)
        vbox_iot.setContentsMargins(0, 5, 0, 5)
        
        chk_iot = QCheckBox("IOT")
        vbox_iot.addWidget(chk_iot)
        
        iot_file_widget = QWidget()
        hbox_iot_file = QHBoxLayout(iot_file_widget)
        hbox_iot_file.setContentsMargins(20, 0, 0, 0)
        
        chk_iot_file = QCheckBox("IOT控制文件导入")
        btn_iot_file = QPushButton("...")
        btn_iot_file.setFixedWidth(60)
        
        hbox_iot_file.addWidget(chk_iot_file)
        hbox_iot_file.addWidget(btn_iot_file)
        hbox_iot_file.addStretch()
        
        vbox_iot.addWidget(iot_file_widget)
        right_layout.addWidget(grp_iot)
        
        # Logic
        iot_file_widget.setEnabled(False)
        chk_iot.toggled.connect(iot_file_widget.setEnabled)
        
        right_layout.addStretch()

        layout.addLayout(left_layout, 0, 0)
        layout.addLayout(right_layout, 0, 1)
        return page

    def create_mainboard_info_page(self):
        page = QWidget()
        layout = QGridLayout(page)
        
        # Info Box (Simulated with GroupBox or Frame) frame on right
        right_frame = QFrame()
        right_frame.setFrameShape(QFrame.Box)
        right_frame.setFrameShadow(QFrame.Sunken)
        
        vbox = QVBoxLayout(right_frame)
        vbox.addStretch()
        
        hbox_pwd = QHBoxLayout()
        hbox_pwd.addWidget(QLabel("厂家密码:"))
        hbox_pwd.addWidget(QLineEdit())
        hbox_pwd.addWidget(QPushButton("输入"))
        vbox.addLayout(hbox_pwd)
        
        hbox_ver = QHBoxLayout()
        hbox_ver.addWidget(QLabel("主板版本号:"))
        txt_ver = QTextEdit()
        txt_ver.setMaximumHeight(60)
        hbox_ver.addWidget(txt_ver)
        vbox.addLayout(hbox_ver)
        
        hbox_btns1 = QHBoxLayout()
        hbox_btns1.addWidget(QPushButton("升级HMI"))
        hbox_btns1.addWidget(QPushButton("读取"))
        vbox.addLayout(hbox_btns1)
        
        layout.addWidget(right_frame, 0, 1, 2, 1) # Occupy right side
        
        # Bottom area
        hbox_bottom = QHBoxLayout()
        hbox_bottom.addWidget(QFrame()) # Spacer
        hbox_bottom.addWidget(QPushButton("主板升级"))
        hbox_bottom.addWidget(QPushButton("字库升级"))
        
        layout.addLayout(hbox_bottom, 2, 1)
        layout.setColumnStretch(0, 1) # Empty space on left column like screenshot
        layout.setColumnStretch(1, 3) 
        
        return page
