#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图层参数设置对话框
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QCheckBox, QSpinBox, 
                             QDoubleSpinBox, QGroupBox, QListWidget, QListWidgetItem,
                             QListView, QWidget, QGridLayout, QDialogButtonBox, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap

class SealAdvancedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("其他切割参数")
        self.setFixedSize(320, 180)
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.chk_enable = QCheckBox("使能缝宽补偿")
        layout.addWidget(self.chk_enable)
        
        # GroupBox for the parameter
        self.group = QGroupBox()
        self.group.setStyleSheet("QGroupBox { border: 1px solid #D0D0D0; border-radius: 3px; margin-top: 0px; }")
        group_layout = QHBoxLayout(self.group)
        group_layout.setContentsMargins(10, 20, 10, 20)
        
        group_layout.addWidget(QLabel("补偿宽度"))
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setSuffix(" mm")
        self.spin_width.setRange(0, 10)
        self.spin_width.setDecimals(3)
        self.spin_width.setValue(0.1)
        group_layout.addWidget(self.spin_width)
        layout.addWidget(self.group)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        # Logic
        self.chk_enable.toggled.connect(self.on_enable_toggled)
        self.on_enable_toggled(self.chk_enable.isChecked())

    def on_enable_toggled(self, checked):
        self.group.setEnabled(checked)

class LayerAdvancedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("其他图层参数")
        self.resize(680, 480)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # --- Left Column ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Radio Buttons Group
        radio_group = QGroupBox()
        radio_group.setStyleSheet("QGroupBox { border: 1px solid #D0D0D0; border-radius: 3px; }")
        radio_layout = QVBoxLayout(radio_group)
        radio_layout.setSpacing(5)
        radio_layout.setContentsMargins(10, 10, 10, 10)
        
        self.bg_pen = QButtonGroup(self)
        self.radio_layer_pen = QRadioButton("按图层抬落笔")
        self.radio_layer_pen.toggled.connect(self.on_layer_pen_toggled)
        
        self.chk_layer_all = QCheckBox("图层整体抬落")
        self.chk_layer_all.setStyleSheet("margin-left: 20px;") # Indent
        
        self.radio_all_pen = QRadioButton("按整体抬落笔")
        
        self.bg_pen.addButton(self.radio_layer_pen)
        self.bg_pen.addButton(self.radio_all_pen)
        self.radio_layer_pen.setChecked(True)
        
        radio_layout.addWidget(self.radio_layer_pen)
        radio_layout.addWidget(self.chk_layer_all)
        radio_layout.addWidget(self.radio_all_pen)
        
        # Separator line
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #A0A0A0;")
        radio_layout.addWidget(line)
        
        left_layout.addWidget(radio_group)
        
        # U-axis Enable
        self.chk_u_enable = QCheckBox("抬落笔使能(U轴)")
        self.chk_u_enable.toggled.connect(self.on_u_enable_toggled)
        left_layout.addWidget(self.chk_u_enable)
        
        # Indented Section for U-axis
        u_indent_widget = QWidget()
        u_indent_layout = QGridLayout(u_indent_widget)
        u_indent_layout.setContentsMargins(20, 0, 0, 0) # Indent
        u_indent_layout.setSpacing(8)
        
        # Row 0: Pen Down
        self.chk_pen_down = QCheckBox("落笔位置:")
        self.chk_pen_down.toggled.connect(self.on_pen_down_toggled)
        self.spin_pen_down = QDoubleSpinBox()
        self.spin_pen_down.setSuffix(" mm")
        self.btn_read_down = QPushButton("读取")
        self.btn_read_down.setFixedWidth(50)
        
        u_indent_layout.addWidget(self.chk_pen_down, 0, 0)
        u_indent_layout.addWidget(self.spin_pen_down, 0, 1)
        u_indent_layout.addWidget(self.btn_read_down, 0, 2)
        
        # Row 1: Pen Up
        self.chk_pen_up = QCheckBox("抬笔位置:")
        self.chk_pen_up.toggled.connect(self.on_pen_up_toggled)
        self.spin_pen_up = QDoubleSpinBox()
        self.spin_pen_up.setSuffix(" mm")
        self.btn_read_up = QPushButton("读取")
        self.btn_read_up.setFixedWidth(50)
        
        u_indent_layout.addWidget(self.chk_pen_up, 1, 0)
        u_indent_layout.addWidget(self.spin_pen_up, 1, 1)
        u_indent_layout.addWidget(self.btn_read_up, 1, 2)
        
        # Row 2: Speed
        self.lbl_u_speed = QLabel("速度:(mm/s)")
        u_indent_layout.addWidget(self.lbl_u_speed, 2, 0, Qt.AlignRight)
        self.spin_u_speed = QDoubleSpinBox()
        self.spin_u_speed.setValue(100)
        u_indent_layout.addWidget(self.spin_u_speed, 2, 1, 1, 2) # Span 2 columns
        
        left_layout.addWidget(u_indent_widget)
        
        # XY Offset
        xy_layout = QHBoxLayout()
        self.chk_xy_offset = QCheckBox("XY偏移:")
        self.chk_xy_offset.toggled.connect(self.on_xy_offset_toggled)
        xy_layout.addWidget(self.chk_xy_offset)
        self.spin_x_offset = QDoubleSpinBox()
        self.spin_x_offset.setDecimals(3)
        self.spin_y_offset = QDoubleSpinBox()
        self.spin_y_offset.setDecimals(3)
        xy_layout.addWidget(self.spin_x_offset)
        xy_layout.addWidget(self.spin_y_offset)
        left_layout.addLayout(xy_layout)
        
        # U Axis Pos
        u_pos_layout = QHBoxLayout()
        self.chk_u_pos = QCheckBox("U轴位置:")
        self.chk_u_pos.toggled.connect(self.on_u_pos_toggled)
        u_pos_layout.addWidget(self.chk_u_pos)
        self.spin_u_pos = QDoubleSpinBox()
        self.spin_u_pos.setDecimals(3)
        u_pos_layout.addWidget(self.spin_u_pos)
        self.btn_u_pos_read = QPushButton("读取")
        self.btn_u_pos_read.setFixedWidth(50)
        u_pos_layout.addWidget(self.btn_u_pos_read)
        left_layout.addLayout(u_pos_layout)
        
        # U Axis Relative
        self.chk_u_rel = QCheckBox("U轴相对移动")
        self.chk_u_rel.toggled.connect(self.on_u_rel_toggled)
        left_layout.addWidget(self.chk_u_rel)
        
        u_rel_val_layout = QHBoxLayout()
        u_rel_val_layout.setContentsMargins(20, 0, 0, 0) # Indent
        self.spin_u_rel = QDoubleSpinBox()
        self.spin_u_rel.setSuffix(" mm")
        self.spin_u_rel.setDecimals(3)
        u_rel_val_layout.addWidget(self.spin_u_rel)
        
        self.btn_u_rel_1 = QPushButton("1")
        self.btn_u_rel_1.setFixedWidth(30)
        self.btn_u_rel_2 = QPushButton("2")
        self.btn_u_rel_2.setFixedWidth(30)
        u_rel_val_layout.addWidget(self.btn_u_rel_1)
        u_rel_val_layout.addWidget(self.btn_u_rel_2)
        u_rel_val_layout.addStretch()
        
        left_layout.addLayout(u_rel_val_layout)
        
        # IO Output
        io_group = QGroupBox("联动IO输出")
        io_layout = QHBoxLayout(io_group)
        self.chk_io1 = QCheckBox("IO1")
        self.chk_io2 = QCheckBox("IO2")
        self.chk_io3 = QCheckBox("IO3")
        self.chk_io4 = QCheckBox("IO4")
        io_layout.addWidget(self.chk_io1)
        io_layout.addWidget(self.chk_io2)
        io_layout.addWidget(self.chk_io3)
        io_layout.addWidget(self.chk_io4)
        left_layout.addWidget(io_group)
        
        # Dot
        dot_group = QGroupBox("点")
        dot_layout = QHBoxLayout(dot_group)
        dot_layout.addWidget(QLabel("打点时间(s)"))
        self.spin_dot_time = QDoubleSpinBox()
        dot_layout.addWidget(self.spin_dot_time)
        left_layout.addWidget(dot_group)
        
        content_layout.addWidget(left_widget)
        
        # --- Right Column ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        freq_group = QGroupBox()
        freq_group.setStyleSheet("QGroupBox { border: 1px solid #D0D0D0; border-radius: 3px; margin-top: 0px; }")
        freq_layout = QGridLayout(freq_group)
        freq_layout.setSpacing(12)
        freq_layout.setContentsMargins(10, 15, 10, 15)
        
        self.freq_rows = []
        for i in range(6):
            chk = QCheckBox(f"激光{i+1}频率(KHZ)")
            spin = QDoubleSpinBox()
            spin.setValue(4)
            # Connect signal
            chk.toggled.connect(lambda checked, s=spin: s.setEnabled(checked))
            
            freq_layout.addWidget(chk, i, 0)
            freq_layout.addWidget(spin, i, 1)
            self.freq_rows.append((chk, spin))
            
        right_layout.addWidget(freq_group)
        right_layout.addStretch()
        
        content_layout.addWidget(right_widget)
        
        outer_layout.addLayout(content_layout)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        outer_layout.addLayout(btn_layout)
        
        # Initialize states
        self.on_u_enable_toggled(False)
        self.on_xy_offset_toggled(False)
        self.on_u_pos_toggled(False)
        self.on_u_rel_toggled(False)
        self.on_layer_pen_toggled(self.radio_layer_pen.isChecked())
        for chk, spin in self.freq_rows:
            spin.setEnabled(chk.isChecked())

    def on_layer_pen_toggled(self, checked):
        self.chk_layer_all.setEnabled(checked)

    def on_u_enable_toggled(self, checked):
        self.chk_pen_down.setEnabled(checked)
        self.chk_pen_up.setEnabled(checked)
        self.lbl_u_speed.setEnabled(checked)
        self.spin_u_speed.setEnabled(checked)
        
        # Sub-states depend on master switch AND their own switch
        self.on_pen_down_toggled(self.chk_pen_down.isChecked())
        self.on_pen_up_toggled(self.chk_pen_up.isChecked())

    def on_pen_down_toggled(self, checked):
        # Only enable if master switch is also on
        is_master_on = self.chk_u_enable.isChecked()
        self.spin_pen_down.setEnabled(is_master_on and checked)
        self.btn_read_down.setEnabled(is_master_on and checked)

    def on_pen_up_toggled(self, checked):
        is_master_on = self.chk_u_enable.isChecked()
        self.spin_pen_up.setEnabled(is_master_on and checked)
        self.btn_read_up.setEnabled(is_master_on and checked)

    def on_xy_offset_toggled(self, checked):
        self.spin_x_offset.setEnabled(checked)
        self.spin_y_offset.setEnabled(checked)

    def on_u_pos_toggled(self, checked):
        self.spin_u_pos.setEnabled(checked)
        self.btn_u_pos_read.setEnabled(checked)

    def on_u_rel_toggled(self, checked):
        self.spin_u_rel.setEnabled(checked)
        self.btn_u_rel_1.setEnabled(checked)
        self.btn_u_rel_2.setEnabled(checked)

class LayerSettingsDialog(QDialog):
    def __init__(self, layer_data, current_hex_color, parent=None):
        super().__init__(parent)
        self.layer_data = layer_data
        self.current_hex_color = current_hex_color
        self.current_params = layer_data.get(current_hex_color)
        
        self.setWindowTitle("图层参数")
        self.resize(750, 550)
        self.init_ui()
        self.load_params()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 1. 左侧图层列表
        self.layer_list = QListWidget()
        self.layer_list.setFixedWidth(50)
        self.layer_list.setIconSize(QSize(24, 24))
        self.layer_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn) # 强制显示滚动条
        self.layer_list.itemClicked.connect(self.on_layer_list_clicked)
        
        # 填充列表
        sorted_colors = sorted(self.layer_data.keys())
        for hex_color in sorted_colors:
            item = QListWidgetItem()
            # 创建颜色图标
            pixmap = QPixmap(24, 24)
            pixmap.fill(QColor(hex_color))
            item.setIcon(QIcon(pixmap))
            item.setData(Qt.UserRole, hex_color)
            self.layer_list.addItem(item)
            
            if hex_color == self.current_hex_color:
                self.layer_list.setCurrentItem(item)
                
        main_layout.addWidget(self.layer_list)
        
        # 中间和右侧区域容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(5)
        
        # 上方参数区域 (左右分栏)
        params_container = QHBoxLayout()
        params_container.setSpacing(10)
        
        # 2. 中间参数区域
        mid_group = QGroupBox("从参数库取参数")
        mid_layout = QGridLayout(mid_group)
        mid_layout.setSpacing(8)
        mid_layout.setContentsMargins(10, 15, 10, 10)
        
        # 图层颜色显示
        mid_layout.addWidget(QLabel("图层:"), 0, 0)
        self.lbl_layer_color = QLabel()
        self.lbl_layer_color.setFixedSize(100, 22)
        self.lbl_layer_color.setStyleSheet("background-color: black; border: 1px solid gray;")
        mid_layout.addWidget(self.lbl_layer_color, 0, 1, 1, 2)
        
        # 是否输出
        mid_layout.addWidget(QLabel("是否输出:"), 1, 0)
        self.combo_output = self.create_combobox(["是", "否"])
        mid_layout.addWidget(self.combo_output, 1, 1, 1, 2)
        
        # 速度
        mid_layout.addWidget(QLabel("速度(mm/s):"), 2, 0)
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0, 5000)
        self.spin_speed.setDecimals(2)
        mid_layout.addWidget(self.spin_speed, 2, 1)
        self.chk_speed_default = QCheckBox("默认")
        mid_layout.addWidget(self.chk_speed_default, 2, 2)
        
        # 重复加工次数
        mid_layout.addWidget(QLabel("重复加工次数:"), 3, 0)
        self.spin_repeat = QSpinBox()
        self.spin_repeat.setRange(1, 100)
        mid_layout.addWidget(self.spin_repeat, 3, 1, 1, 2)
        
        # 加工方式
        mid_layout.addWidget(QLabel("加工方式:"), 4, 0)
        self.combo_mode = self.create_combobox(["激光切割", "激光扫描", "笔式绘图", "激光打孔"])
        self.combo_mode.currentIndexChanged.connect(self.on_mode_changed)
        mid_layout.addWidget(self.combo_mode, 4, 1)
        btn_mode_adv = QPushButton("高级...")
        btn_mode_adv.clicked.connect(self.open_layer_advanced)
        mid_layout.addWidget(btn_mode_adv, 4, 2)
        
        # 扫描参数 (默认隐藏，仅在扫描模式显示)
        self.lbl_scan_mode = QLabel("扫描方式:")
        self.combo_scan_mode = self.create_combobox(["水平单向", "水平双向", "垂直单向", "垂直双向"])
        self.lbl_scan_interval = QLabel("扫描间隔(mm):")
        self.spin_scan_interval = QDoubleSpinBox()
        self.spin_scan_interval.setRange(0.001, 100.0)
        self.spin_scan_interval.setDecimals(3)
        self.spin_scan_interval.setSingleStep(0.01)
        self.spin_scan_interval.setValue(0.1)
        
        mid_layout.addWidget(self.lbl_scan_mode, 5, 0)
        mid_layout.addWidget(self.combo_scan_mode, 5, 1, 1, 2)
        mid_layout.addWidget(self.lbl_scan_interval, 6, 0)
        mid_layout.addWidget(self.spin_scan_interval, 6, 1, 1, 2)
        
        # 是否吹气
        mid_layout.addWidget(QLabel("是否吹气:"), 7, 0)
        self.combo_blowing = self.create_combobox(["是", "否"])
        mid_layout.addWidget(self.combo_blowing, 7, 1, 1, 2)
        
        # 功率设置区域 (使用 QFrame 模拟分割线效果)
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #A0A0A0;")
        mid_layout.addWidget(line, 8, 0, 1, 3)

        power_container = QWidget()
        power_layout = QGridLayout(power_container)
        power_layout.setContentsMargins(0, 5, 0, 0)
        power_layout.setSpacing(5)
        
        power_layout.addWidget(QLabel("最小功率(%)"), 0, 1, Qt.AlignCenter)
        power_layout.addWidget(QLabel("最大功率(%)"), 0, 2, Qt.AlignCenter)
        
        self.power_rows = []
        for i in range(6):
            chk = QCheckBox(f"{i+1}:")
            chk.setChecked(i < 2) # 默认前两个选中
            
            spin_min = QDoubleSpinBox()
            spin_min.setRange(0, 100)
            spin_min.setDecimals(2)
            spin_min.setValue(30.00)
            
            spin_max = QDoubleSpinBox()
            spin_max.setRange(0, 100)
            spin_max.setDecimals(2)
            spin_max.setValue(30.00)
            
            # 模拟截图：3-6行禁用
            if i >= 2:
                chk.setChecked(False)
                chk.setEnabled(False) # 暂时禁用，如需启用可修改逻辑
                spin_min.setEnabled(False)
                spin_max.setEnabled(False)
            
            power_layout.addWidget(chk, i+1, 0)
            power_layout.addWidget(spin_min, i+1, 1)
            power_layout.addWidget(spin_max, i+1, 2)
            
            self.power_rows.append((chk, spin_min, spin_max))
            
        # 默认 Checkbox
        self.chk_power_default = QCheckBox("默认")
        power_layout.addWidget(self.chk_power_default, 7, 2, Qt.AlignRight)

        mid_layout.addWidget(power_container, 9, 0, 1, 3)
        
        # 底部横线
        line2 = QWidget()
        line2.setFixedHeight(1)
        line2.setStyleSheet("background-color: #A0A0A0;")
        mid_layout.addWidget(line2, 10, 0, 1, 3)
        
        params_container.addWidget(mid_group, 1)
        
        # 3. 右侧高级参数区域
        right_widget = QWidget()
        right_layout = QGridLayout(right_widget)
        right_layout.setContentsMargins(0, 10, 0, 0)
        right_layout.setSpacing(8)
        
        # 封口
        right_layout.addWidget(QLabel("封口:"), 0, 0, Qt.AlignRight)
        self.spin_seal = QDoubleSpinBox()
        self.spin_seal.setSuffix(" mm")
        self.spin_seal.setDecimals(3)
        right_layout.addWidget(self.spin_seal, 0, 1)
        btn_seal_adv = QPushButton("高级...")
        btn_seal_adv.clicked.connect(self.open_seal_advanced)
        right_layout.addWidget(btn_seal_adv, 0, 2)
        
        # 延时
        right_layout.addWidget(QLabel("激光开延时:"), 1, 0, Qt.AlignRight)
        self.spin_on_delay = QSpinBox()
        self.spin_on_delay.setSuffix(" ms")
        self.spin_on_delay.setRange(0, 10000)
        right_layout.addWidget(self.spin_on_delay, 1, 1)
        
        right_layout.addWidget(QLabel("激光关延时:"), 2, 0, Qt.AlignRight)
        self.spin_off_delay = QSpinBox()
        self.spin_off_delay.setSuffix(" ms")
        self.spin_off_delay.setRange(0, 10000)
        right_layout.addWidget(self.spin_off_delay, 2, 1)
        
        # 打穿模式
        self.chk_pierce = QCheckBox("激光打穿模式")
        self.chk_pierce.toggled.connect(self.on_pierce_toggled)
        right_layout.addWidget(self.chk_pierce, 3, 0, 1, 3)
        
        # 打穿功率列表
        self.pierce_group = QGroupBox() # 无标题边框
        self.pierce_group.setStyleSheet("QGroupBox { border: 1px solid #D0D0D0; border-radius: 3px; margin-top: 0px; }")
        pierce_layout = QGridLayout(self.pierce_group)
        pierce_layout.setContentsMargins(10, 10, 10, 10)
        pierce_layout.setSpacing(8)
        
        self.pierce_spins = []
        for i in range(6):
            lbl = QLabel(f"打穿功率{i+1}:")
            spin = QDoubleSpinBox()
            spin.setSuffix(" %")
            spin.setRange(0, 100)
            spin.setDecimals(2)
            spin.setValue(50.00)
            
            pierce_layout.addWidget(lbl, i, 0)
            pierce_layout.addWidget(spin, i, 1)
            self.pierce_spins.append(spin)
            
        right_layout.addWidget(self.pierce_group, 4, 0, 1, 3)
        right_layout.setRowStretch(5, 1) # 底部填充
        
        params_container.addWidget(right_widget, 1)
        
        content_layout.addLayout(params_container)
        
        # 4. 底部按钮区域
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 5, 0, 5)
        self.chk_sync = QCheckBox("修改激光参数自动同步到各路激光")
        self.chk_sync.setChecked(True)
        bottom_layout.addWidget(self.chk_sync)
        bottom_layout.addStretch()
        
        btn_apply = QPushButton("应用到同类图层")
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        
        # 设置按钮固定高度
        for btn in [btn_apply, btn_ok, btn_cancel]:
            btn.setFixedHeight(28)
        
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        
        bottom_layout.addWidget(btn_apply)
        bottom_layout.addWidget(btn_ok)
        bottom_layout.addWidget(btn_cancel)
        
        content_layout.addLayout(bottom_layout)
        
        main_layout.addWidget(content_widget)

    def create_combobox(self, items):
        combo = QComboBox()
        combo.setView(QListView()) # 解决遮挡问题
        combo.addItems(items)
        return combo

    def on_layer_list_clicked(self, item):
        # 保存当前参数
        self.save_current_params()
        # 切换到新图层
        hex_color = item.data(Qt.UserRole)
        self.current_hex_color = hex_color
        self.current_params = self.layer_data.get(hex_color)
        self.load_params()

    def on_mode_changed(self, index):
        mode = self.combo_mode.currentText()
        is_scan = (mode == "激光扫描")
        self.lbl_scan_mode.setVisible(is_scan)
        self.combo_scan_mode.setVisible(is_scan)
        self.lbl_scan_interval.setVisible(is_scan)
        self.spin_scan_interval.setVisible(is_scan)

    def load_params(self):
        if not self.current_params:
            return
            
        p = self.current_params
        self.lbl_layer_color.setStyleSheet(f"background-color: {self.current_hex_color}; border: 1px solid gray;")
        
        self.combo_output.setCurrentIndex(0 if p.is_output else 1)
        self.spin_speed.setValue(p.speed)
        self.spin_repeat.setValue(getattr(p, 'repeat_count', 1))
        self.combo_mode.setCurrentText(p.mode)
        
        # 加载扫描参数
        self.combo_scan_mode.setCurrentText(getattr(p, 'scan_mode', "水平单向"))
        self.spin_scan_interval.setValue(getattr(p, 'scan_interval', 0.1))
        self.on_mode_changed(0) # 更新可见性
        
        self.combo_blowing.setCurrentIndex(0 if getattr(p, 'is_blowing', True) else 1)
        
        # 加载功率 (目前只支持第一路，后续可扩展)
        if self.power_rows:
            self.power_rows[0][1].setValue(p.min_power)
            self.power_rows[0][2].setValue(p.max_power)
            # 第二路示例
            self.power_rows[1][1].setValue(0.0)
            self.power_rows[1][2].setValue(0.0)
        
        self.spin_seal.setValue(getattr(p, 'seal_gap', 0.0))
        self.spin_on_delay.setValue(getattr(p, 'laser_on_delay', 0))
        self.spin_off_delay.setValue(getattr(p, 'laser_off_delay', 0))
        
        is_pierce = getattr(p, 'is_pierce_mode', False)
        self.chk_pierce.setChecked(is_pierce)
        self.pierce_group.setEnabled(is_pierce)
        
        pierce_val = getattr(p, 'pierce_power', 50.0)
        for spin in self.pierce_spins:
            spin.setValue(pierce_val)

    def save_current_params(self):
        if not self.current_params:
            return
            
        p = self.current_params
        p.is_output = (self.combo_output.currentIndex() == 0)
        p.speed = self.spin_speed.value()
        p.repeat_count = self.spin_repeat.value()
        p.mode = self.combo_mode.currentText()
        
        # 保存扫描参数
        p.scan_mode = self.combo_scan_mode.currentText()
        p.scan_interval = self.spin_scan_interval.value()
        
        p.is_blowing = (self.combo_blowing.currentIndex() == 0)
        
        if self.power_rows:
            p.min_power = self.power_rows[0][1].value()
            p.max_power = self.power_rows[0][2].value()
        
        p.seal_gap = self.spin_seal.value()
        p.laser_on_delay = self.spin_on_delay.value()
        p.laser_off_delay = self.spin_off_delay.value()
        
        p.is_pierce_mode = self.chk_pierce.isChecked()
        p.pierce_power = self.pierce_spins[0].value() # 简化：只取第一个

    def on_pierce_toggled(self, checked):
        self.pierce_group.setEnabled(checked)

    def open_layer_advanced(self):
        dlg = LayerAdvancedDialog(self)
        dlg.exec_()

    def open_seal_advanced(self):
        dlg = SealAdvancedDialog(self)
        dlg.exec_()

    def accept(self):
        self.save_current_params()
        super().accept()
