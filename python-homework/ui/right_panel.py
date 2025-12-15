#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧属性面板
"""
import os

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                             QRadioButton, QGridLayout, QStackedWidget, QHeaderView, QSizePolicy)
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap


class LayerParams:
    """图层参数数据结构"""
    def __init__(self, color: QColor):
        self.color = color
        self.mode = "激光切割"
        self.is_output = True
        self.is_visible = True
        self.is_locked = False
        self.speed = 100.0
        self.min_power = 30.0
        self.max_power = 30.0
        self.scan_mode = "水平单向"
        self.scan_interval = 0.1
        self.priority = 1
        self.name = "" # 预留

class RightPanel(QWidget):
    """右侧属性面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None # 持有 Canvas 引用
        self.layer_data = {} # Key: hex color string, Value: LayerParams
        self.init_ui()

    def set_canvas(self, canvas):
        """设置画布引用并连接信号"""
        self.canvas = canvas
        # 监听场景变化以更新图层列表
        self.canvas.scene.changed.connect(self.update_layer_list)
        # 监听选择变化以更新参数显示
        self.canvas.scene.selectionChanged.connect(self.on_selection_changed)
        # 初始化图层列表
        self.update_layer_list()

    def init_ui(self):
        """初始化界面"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # 创建标签页并为每页添加可滚动区域，避免放大/缩放时内部控件被异常拉伸
        self.tabs = QTabWidget()
        self.tabs.addTab(self._wrap_tab(self.create_processing_tab()), "加工")
        self.tabs.addTab(self._wrap_tab(self.create_output_tab()), "输出")
        self.tabs.addTab(self._wrap_tab(self.create_file_tab()), "文档")
        self.tabs.addTab(self._wrap_tab(self.create_user_tab()), "用户")
        self.tabs.addTab(self._wrap_tab(self.create_test_tab()), "测试")
        # 历史面板（列出撤销/重做历史）
        self.tabs.addTab(self._wrap_tab(self.create_history_tab()), "历史")

        root_layout.addWidget(self.tabs, 1)

        self.create_fixed_bottom_area(root_layout)

        # 设置最小宽度并限制最大宽度，防止全屏时右侧面板被过度拉伸导致内部控件变形
        self.setMinimumWidth(320)
        self.setMaximumWidth(520)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # 样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #e8e8e8;
                padding: 8px 14px;
                margin-right: 2px;
                font-size: 14px;
                font-weight: normal;
                color: #888;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 3px solid #0078d7;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #fafafa;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 4px;
                background-color: #ffffff;
            }
            QPushButton {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 4px;
                background-color: #f0f0f0;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)

    def create_fixed_bottom_area(self, parent_layout):
        """底部的区域（调整后：组件缩小、间距压缩，为上方腾位置）"""
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(6)  # 缩小布局间距

        # 防止在高 DPI / 全屏时被过度拉伸：限制底部区域最大高度并固定其纵向策略
        from PyQt5.QtWidgets import QSizePolicy as _QSizePolicy
        bottom_widget.setSizePolicy(_QSizePolicy.Preferred, _QSizePolicy.Fixed)
        bottom_widget.setMaximumHeight(360)

        process_group = QGroupBox("数据加工")
        process_layout = QVBoxLayout()
        process_layout.setContentsMargins(5, 5, 5, 5)
        process_layout.setSpacing(4)  # 缩小内部间距

        # 控制按钮行：缩小按钮高度、调整样式
        control_btn_layout = QHBoxLayout()
        control_btn_layout.setSpacing(2)
        start_btn = QPushButton("开始")
        start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 15px;")
        start_btn.setMinimumHeight(28)  # 缩小按钮高度
        start_btn.setMaximumHeight(42)
        start_btn.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        pause_btn = QPushButton("暂停/继续")
        pause_btn.setStyleSheet("background-color: #FF9800; color: white; font-size: 15px;")
        pause_btn.setMinimumHeight(28)
        pause_btn.setMaximumHeight(42)
        pause_btn.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        stop_btn = QPushButton("停止")
        stop_btn.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; font-size: 15px;")
        stop_btn.setMinimumHeight(28)
        stop_btn.setMaximumHeight(42)
        stop_btn.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        control_btn_layout.addWidget(start_btn, 1)
        control_btn_layout.addWidget(pause_btn, 1)
        control_btn_layout.addWidget(stop_btn, 1)
        process_layout.addLayout(control_btn_layout)

        # 文件操作按钮：缩小高度、调整字体
        file_btn1 = QPushButton("保存为版位文件")
        file_btn1.setStyleSheet("font-size: 15px;")
        file_btn1.setMinimumHeight(26)  # 缩小按钮高度
        file_btn1.setMaximumHeight(36)
        file_btn1.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        process_layout.addWidget(file_btn1)

        file_btn2 = QPushButton("载机文件输出")
        file_btn2.setStyleSheet("font-size: 15px;")
        file_btn2.setMinimumHeight(26)
        file_btn2.setMaximumHeight(36)
        file_btn2.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        process_layout.addWidget(file_btn2)

        file_btn3 = QPushButton("下载")
        file_btn3.setStyleSheet("font-size: 15px;")
        file_btn3.setMinimumHeight(26)
        file_btn3.setMaximumHeight(36)
        file_btn3.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        process_layout.addWidget(file_btn3)

        # 图形定位行：缩小组件尺寸
        pos_layout = QHBoxLayout()
        pos_layout.setSpacing(3)
        pos_layout.addWidget(QLabel("图形定位:"), 0)
        pos_combo = QComboBox()
        pos_combo.addItems(["当前位置", "左上角", "中心"])
        pos_combo.setStyleSheet("font-size: 12px;")
        pos_combo.setMinimumHeight(24)  # 缩小下拉框高度
        pos_combo.setMaximumHeight(30)
        pos_combo.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        pos_layout.addWidget(pos_combo, 1)
        process_layout.addLayout(pos_layout)

        # 确定优化复选框：缩小尺寸
        optimize_check = QCheckBox("确定优化")
        optimize_check.setStyleSheet("font-size: 15px;")
        optimize_check.setMinimumHeight(22)
        optimize_check.setMaximumHeight(30)
        optimize_check.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        optimize_check.setChecked(True)
        process_layout.addWidget(optimize_check)

        # 其他操作按钮：缩小高度、调整字体
        other_layout = QHBoxLayout()
        other_layout.setSpacing(2)
        btn_left = QPushButton("切换坐标")
        btn_right = QPushButton("走边")
        btn_left.setMinimumHeight(26)
        btn_left.setMaximumHeight(36)
        btn_left.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        btn_left.setStyleSheet("font-size: 15px;")
        btn_right.setMinimumHeight(26)
        btn_right.setMaximumHeight(36)
        btn_right.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        btn_right.setStyleSheet("font-size: 15px;")
        other_layout.addWidget(btn_left, 1)
        other_layout.addWidget(btn_right, 1)
        process_layout.addLayout(other_layout)

        process_group.setLayout(process_layout)
        bottom_layout.addWidget(process_group)
        parent_layout.addWidget(bottom_widget)

        bottom_widget.setStyleSheet("""
               background-color: #f5f5f5;
               border-top: 1px solid #d0d0d0;
               padding-top: 6px;  /* 缩小顶部内边距 */
           """)

    def create_processing_tab(self):
        """创建加工标签页（图层列表与参数设置）"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. 图层列表
        self.layer_table = QTableWidget()
        self.layer_table.setColumnCount(5)
        self.layer_table.setHorizontalHeaderLabels(["图层", "模式", "输出", "显示", "锁定"])
        self.layer_table.horizontalHeader().setStretchLastSection(False)
        self.layer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.layer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.layer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.layer_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.layer_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.layer_table.verticalHeader().setVisible(False)
        self.layer_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.layer_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layer_table.setEditTriggers(QAbstractItemView.NoEditTriggers) # 禁止直接编辑文本，双击弹窗
        self.layer_table.setMinimumHeight(150)
        
        # 样式优化
        self.layer_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                gridline-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #e8f0fe;
                color: #000;
            }
        """)
        
        # 双击事件
        self.layer_table.itemDoubleClicked.connect(self.on_layer_double_clicked)
        # 点击事件更新下方参数
        self.layer_table.itemClicked.connect(self.on_layer_selected)
        # 单元格改变事件（处理Checkbox）
        self.layer_table.itemChanged.connect(self.on_layer_item_changed)

        main_layout.addWidget(self.layer_table, 1)

        # 2. 参数设置区域
        param_group = QGroupBox("参数设置")
        param_layout = QVBoxLayout(param_group)
        param_layout.setContentsMargins(5, 5, 5, 5)
        param_layout.setSpacing(4)

        # 颜色显示条
        self.color_bar = QLabel()
        self.color_bar.setFixedHeight(20)
        self.color_bar.setStyleSheet("background-color: #cccccc; border: 1px solid #888;")
        param_layout.addWidget(self.color_bar)

        # 速度/优先级
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("速度(mm/s)"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0, 5000)
        self.speed_spin.setValue(100.0)
        row1.addWidget(self.speed_spin)
        
        row1.addWidget(QLabel("优先级"))
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 100)
        row1.addWidget(self.priority_spin)
        param_layout.addLayout(row1)

        # 功率
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("最小功率(%)"))
        self.min_power_spin = QDoubleSpinBox()
        self.min_power_spin.setRange(0, 100)
        self.min_power_spin.setValue(30.0)
        row2.addWidget(self.min_power_spin)
        
        row2.addWidget(QLabel("最大功率(%)"))
        self.max_power_spin = QDoubleSpinBox()
        self.max_power_spin.setRange(0, 100)
        self.max_power_spin.setValue(30.0)
        row2.addWidget(self.max_power_spin)
        param_layout.addLayout(row2)
        
        # 连接参数变更信号
        self.speed_spin.valueChanged.connect(self.on_param_changed)
        self.priority_spin.valueChanged.connect(self.on_param_changed)
        self.min_power_spin.valueChanged.connect(self.on_param_changed)
        self.max_power_spin.valueChanged.connect(self.on_param_changed)

        main_layout.addWidget(param_group)

        # 3. 激光控制（保留）
        laser_layout = QHBoxLayout()
        laser1_btn = QPushButton("激光1")
        laser1_btn.setCheckable(True)
        laser1_btn.setChecked(True)
        laser2_btn = QPushButton("激光2")
        laser2_btn.setCheckable(True)
        laser_layout.addWidget(laser1_btn)
        laser_layout.addWidget(laser2_btn)
        laser_layout.addStretch()
        main_layout.addLayout(laser_layout)

        # 4. 行列设置（保留，简化显示）
        grid_group = QGroupBox("行列设置")
        grid_layout = QGridLayout(grid_group)
        grid_layout.setContentsMargins(5, 5, 5, 5)
        
        grid_layout.addWidget(QLabel("个数"), 0, 1)
        grid_layout.addWidget(QLabel("奇间隔"), 0, 2)
        grid_layout.addWidget(QLabel("偶间隔"), 0, 3)
        
        grid_layout.addWidget(QLabel("X:"), 1, 0)
        grid_layout.addWidget(QLineEdit("1"), 1, 1)
        grid_layout.addWidget(QLineEdit("0.0"), 1, 2)
        grid_layout.addWidget(QLineEdit("0.0"), 1, 3)
        
        grid_layout.addWidget(QLabel("Y:"), 2, 0)
        grid_layout.addWidget(QLineEdit("1"), 2, 1)
        grid_layout.addWidget(QLineEdit("0.0"), 2, 2)
        grid_layout.addWidget(QLineEdit("0.0"), 2, 3)
        
        main_layout.addWidget(grid_group)

        return widget

    def _wrap_tab(self, widget: QWidget) -> QWidget:
        """Wrap a tab page in a QScrollArea so content scrolls instead of stretching."""
        from PyQt5.QtWidgets import QScrollArea, QWidget, QVBoxLayout

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        scroll.setWidget(widget)

        layout.addWidget(scroll)
        return container

    def update_layer_list(self):
        """扫描画布，更新图层列表"""
        if not self.canvas:
            return

        # 1. 扫描画布上的颜色
        used_colors = set()
        from ui.graphics_items import EditablePathItem
        from PyQt5.QtWidgets import QGraphicsTextItem
        
        for item in self.canvas.scene.items():
            color = None
            if isinstance(item, EditablePathItem):
                color = item.pen().color()
            elif isinstance(item, QGraphicsTextItem):
                color = item.defaultTextColor()
            
            if color and color.isValid():
                used_colors.add(color.name().upper())

        # 2. 同步数据：新增的颜色初始化参数，未使用的颜色保留（或标记为未使用，这里简化为只显示使用的或全部预设的）
        # 需求说“支持>=20个图层”，通常意味着所有20个预设颜色都应该能被管理，或者动态管理。
        # 为了符合截图“只显示已使用”的惯例，我们这里只显示 used_colors。
        
        # 确保 layer_data 中有这些颜色的数据
        for hex_color in used_colors:
            if hex_color not in self.layer_data:
                self.layer_data[hex_color] = LayerParams(QColor(hex_color))

        # 3. 更新表格显示
        # 获取当前选中的颜色，以便恢复选中状态
        current_row = self.layer_table.currentRow()
        selected_color = None
        if current_row >= 0:
            item = self.layer_table.item(current_row, 0)
            if item:
                selected_color = item.data(Qt.UserRole)

        self.layer_table.blockSignals(True) # 暂停信号防止触发 itemChanged
        self.layer_table.setRowCount(0)
        
        # 排序：按颜色 hex 排序或自定义顺序
        sorted_colors = sorted(list(used_colors))
        
        for row, hex_color in enumerate(sorted_colors):
            params = self.layer_data[hex_color]
            self.layer_table.insertRow(row)
            
            # 列0：图层颜色 + 名称
            # 如果有自定义名称显示名称，否则显示颜色代码
            display_name = params.name if params.name else hex_color
            color_item = QTableWidgetItem(display_name)
            # 设置颜色块作为图标或背景
            # 这里用背景色表示颜色直观
            color_item.setBackground(QColor(hex_color))
            # 字体颜色根据背景深浅调整，或者加个描边？这里简单处理：
            # 如果背景太深，字变白
            c = QColor(hex_color)
            if c.lightness() < 128:
                color_item.setForeground(QColor(255, 255, 255))
            else:
                color_item.setForeground(QColor(0, 0, 0))
                
            color_item.setData(Qt.UserRole, hex_color) # 存储颜色key
            self.layer_table.setItem(row, 0, color_item)
            
            # 列1：模式
            mode_item = QTableWidgetItem(params.mode)
            self.layer_table.setItem(row, 1, mode_item)
            
            # 列2：输出 (Checkbox)
            out_item = QTableWidgetItem()
            out_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            out_item.setCheckState(Qt.Checked if params.is_output else Qt.Unchecked)
            self.layer_table.setItem(row, 2, out_item)
            
            # 列3：显示 (Checkbox)
            # 注意：params.is_visible True 表示显示 -> Checked
            vis_item = QTableWidgetItem()
            vis_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            vis_item.setCheckState(Qt.Checked if params.is_visible else Qt.Unchecked)
            self.layer_table.setItem(row, 3, vis_item)
            
            # 列4：锁定 (Checkbox)
            lock_item = QTableWidgetItem()
            lock_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            lock_item.setCheckState(Qt.Checked if params.is_locked else Qt.Unchecked)
            self.layer_table.setItem(row, 4, lock_item)

        self.layer_table.blockSignals(False)

        # 恢复选中
        if selected_color:
            for row in range(self.layer_table.rowCount()):
                if self.layer_table.item(row, 0).data(Qt.UserRole) == selected_color:
                    self.layer_table.selectRow(row)
                    break

    def on_layer_item_changed(self, item):
        """处理表格中Checkbox的变化"""
        row = item.row()
        col = item.column()
        
        # 获取对应图层的参数
        color_item = self.layer_table.item(row, 0)
        if not color_item:
            return
        hex_color = color_item.data(Qt.UserRole)
        params = self.layer_data.get(hex_color)
        if not params:
            return
            
        # 根据列号更新参数
        if col == 2: # 输出
            params.is_output = (item.checkState() == Qt.Checked)
        elif col == 3: # 显示
            params.is_visible = (item.checkState() == Qt.Checked)
            self.apply_layer_state(params)
        elif col == 4: # 锁定
            params.is_locked = (item.checkState() == Qt.Checked)
            self.apply_layer_state(params)

    def on_layer_selected(self):
        """当图层列表选中项变化时，更新下方参数显示"""
        row = self.layer_table.currentRow()
        if row < 0:
            return
            
        hex_color = self.layer_table.item(row, 0).data(Qt.UserRole)
        params = self.layer_data.get(hex_color)
        if params:
            self.color_bar.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")
            self.speed_spin.blockSignals(True)
            self.priority_spin.blockSignals(True)
            self.min_power_spin.blockSignals(True)
            self.max_power_spin.blockSignals(True)
            
            self.speed_spin.setValue(params.speed)
            self.priority_spin.setValue(params.priority)
            self.min_power_spin.setValue(params.min_power)
            self.max_power_spin.setValue(params.max_power)
            
            self.speed_spin.blockSignals(False)
            self.priority_spin.blockSignals(False)
            self.min_power_spin.blockSignals(False)
            self.max_power_spin.blockSignals(False)

    def on_param_changed(self):
        """下方参数修改后保存回数据"""
        row = self.layer_table.currentRow()
        if row < 0:
            return
            
        hex_color = self.layer_table.item(row, 0).data(Qt.UserRole)
        params = self.layer_data.get(hex_color)
        if params:
            params.speed = self.speed_spin.value()
            params.priority = self.priority_spin.value()
            params.min_power = self.min_power_spin.value()
            params.max_power = self.max_power_spin.value()

    def on_layer_double_clicked(self, item):
        """双击图层行，弹出属性设置对话框"""
        row = item.row()
        hex_color = self.layer_table.item(row, 0).data(Qt.UserRole)
        params = self.layer_data.get(hex_color)
        
        if params:
            self.show_layer_properties_dialog(params)
            # 更新表格显示（模式等可能改变）
            self.update_layer_list()

    def show_layer_properties_dialog(self, params):
        """显示图层属性对话框"""
        from PyQt5.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        
        dlg = QDialog(self)
        dlg.setWindowTitle("图层参数设置")
        layout = QVBoxLayout(dlg)
        
        form = QFormLayout()
        
        # 模式
        mode_combo = QComboBox()
        mode_combo.addItems(["激光切割", "激光扫描", "笔式绘图"])
        mode_combo.setCurrentText(params.mode)
        form.addRow("处理模式:", mode_combo)
        
        # 输出/显示
        output_check = QCheckBox("输出")
        output_check.setChecked(params.is_output)
        form.addRow("", output_check)
        
        visible_check = QCheckBox("显示")
        visible_check.setChecked(params.is_visible)
        form.addRow("", visible_check)
        
        # 扫描设置
        scan_mode_combo = QComboBox()
        scan_mode_combo.addItems(["水平单向", "水平双向", "垂直单向", "垂直双向"])
        scan_mode_combo.setCurrentText(params.scan_mode)
        form.addRow("扫描方式:", scan_mode_combo)
        
        scan_interval_spin = QDoubleSpinBox()
        scan_interval_spin.setRange(0.001, 100.0)
        scan_interval_spin.setDecimals(3)
        scan_interval_spin.setSingleStep(0.01)
        scan_interval_spin.setValue(params.scan_interval)
        form.addRow("扫描间隔(mm):", scan_interval_spin)
        
        # 锁定与重命名
        locked_check = QCheckBox("锁定图层")
        locked_check.setChecked(params.is_locked)
        form.addRow("", locked_check)
        
        name_edit = QLineEdit(params.name)
        form.addRow("图层名称:", name_edit)

        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        
        if dlg.exec_() == QDialog.Accepted:
            params.mode = mode_combo.currentText()
            params.is_output = output_check.isChecked()
            params.is_visible = visible_check.isChecked()
            params.scan_mode = scan_mode_combo.currentText()
            params.scan_interval = scan_interval_spin.value()
            params.is_locked = locked_check.isChecked()
            params.name = name_edit.text()
            
            # 应用状态到画布
            self.apply_layer_state(params)
            # 刷新列表显示（更新名称、锁定状态等）
            self.update_layer_list()

    def apply_layer_state(self, params):
        """应用图层状态（可见性、锁定等）"""
        if not self.canvas:
            return
            
        target_color_name = params.color.name().upper()
        from ui.graphics_items import EditablePathItem
        from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsItem
        
        for item in self.canvas.scene.items():
            color = None
            if isinstance(item, EditablePathItem):
                color = item.pen().color()
            elif isinstance(item, QGraphicsTextItem):
                color = item.defaultTextColor()
            
            if color and color.name().upper() == target_color_name:
                # 可见性
                item.setVisible(params.is_visible)
                
                # 锁定状态 (锁定 = 不可移动 + 不可选择)
                # 注意：EditablePathItem 可能还有其他 flag，这里只控制 Movable/Selectable
                is_unlocked = not params.is_locked
                item.setFlag(QGraphicsItem.ItemIsMovable, is_unlocked)
                item.setFlag(QGraphicsItem.ItemIsSelectable, is_unlocked)
                
                # 如果被锁定且当前被选中，则取消选中
                if params.is_locked and item.isSelected():
                    item.setSelected(False)

    def on_selection_changed(self):
        """画布选择变化时，尝试自动选中对应的图层行"""
        # 如果选中了单个Item，跳转到对应颜色行
        if not self.canvas:
            return
        
        selected = self.canvas.get_selected_items()
        if len(selected) == 1:
            item = selected[0]
            color = None
            from ui.graphics_items import EditablePathItem
            from PyQt5.QtWidgets import QGraphicsTextItem
            if isinstance(item, EditablePathItem):
                color = item.pen().color()
            elif isinstance(item, QGraphicsTextItem):
                color = item.defaultTextColor()
            
            if color:
                hex_color = color.name().upper()
                for row in range(self.layer_table.rowCount()):
                    if self.layer_table.item(row, 0).data(Qt.UserRole) == hex_color:
                        self.layer_table.selectRow(row)
                        self.on_layer_selected() # 手动触发更新参数
                        break

    # 激光按钮点击回调
    def on_laser_btn_click(self, laser_num):
        print(f"切换到激光{laser_num}")



    def on_layer_header_btn_click(self):
        """图层"""
        pass

    def on_mode_header_btn_click(self):
        """模式"""
        pass

    def on_output_header_btn_click(self):
        """输出"""
        pass

    def on_hide_header_btn_click(self):
        """隐藏"""
        pass

    def create_output_tab(self):
        """输出页面"""
        widget=QWidget()
        layout=QVBoxLayout(widget)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(8)

        cycle_group=QGroupBox("")
        cycle_layout=QVBoxLayout()
        cycle_layout.setContentsMargins(5,5,5,5)
        cycle_layout.setSpacing(6)

        cycle_check=QCheckBox("循环加工")
        cycle_layout.addWidget(cycle_check)

        cycle_row1=QHBoxLayout()
        cycle_row1.setSpacing(5)
        cycle_row1.addWidget(QLabel("循环次数:"),0)
        cycle_count=QSpinBox()
        cycle_count.setRange(0,999)
        cycle_count.setValue(0)
        cycle_row1.addWidget(cycle_count,1)
        cycle_row1.addWidget(QLabel("先切割后送料"),0)
        cycle_order=QComboBox()
        cycle_order.addItems(["先切割后送料","先送料后切割","往返送料"])
        cycle_row1.addWidget(cycle_order,1)
        cycle_layout.addLayout(cycle_row1)

        cycle_row2=QHBoxLayout()
        cycle_row2.setSpacing(5)
        cycle_row2.addWidget(QLabel("送料长度:"),0)
        feed_length=QDoubleSpinBox()
        feed_length.setRange(0,9999)
        feed_length.setValue(500.0)
        feed_length.setSuffix("")
        cycle_row2.addWidget(feed_length,1)
        cycle_row2.addWidget(QLabel("手动输入"),0)
        feed_input=QComboBox()
        feed_input.addItems(["手动输入","Y向幅面","图形高度","最小送料长度"])
        cycle_row2.addWidget(feed_input,1)
        cycle_layout.addLayout(cycle_row2)

        cycle_row3=QHBoxLayout()
        cycle_row3.setSpacing(5)
        cycle_row3.addWidget(QLabel("送料补偿:"),0)
        feed_comp=QDoubleSpinBox()
        feed_comp.setRange(0,999)
        feed_comp.setValue(0.000)
        feed_comp.setSuffix("")
        cycle_row3.addWidget(feed_comp,1)
        pause_check=QCheckBox("送料后暂停")
        cycle_row3.addWidget(pause_check,0)
        cycle_layout.addLayout(cycle_row3)

        cycle_group.setLayout(cycle_layout)
        layout.addWidget(cycle_group)

        split_group=QGroupBox("超幅面分块切割")
        split_layout=QVBoxLayout()
        split_layout.setContentsMargins(5,5,5,5)
        split_layout.setSpacing(6)

        split_check=QCheckBox("超幅面分块切割")
        split_layout.addWidget(split_check)

        split_row1=QHBoxLayout()
        split_row1.setSpacing(5)
        split_row1.addWidget(QLabel("幅面高度:"),0)
        height=QDoubleSpinBox()
        height.setRange(0,9999)
        height.setValue(500.000)
        height.setSuffix("")
        split_row1.addWidget(height,1)
        force_split=QCheckBox("强制分块")
        split_row1.addWidget(force_split,0)
        split_layout.addLayout(split_row1)

        split_row2=QHBoxLayout()
        split_row2.setSpacing(5)
        split_row2.addWidget(QLabel("角度补偿:"),0)
        angle_comp=QDoubleSpinBox()
        angle_comp.setRange(0,999)
        angle_comp.setValue(0.000)
        angle_comp.setSuffix("")
        split_row2.addWidget(angle_comp,1)
        end_feed=QCheckBox("结束送料")
        split_row2.addWidget(end_feed,0)
        split_layout.addLayout(split_row2)

        split_row3=QHBoxLayout()
        split_row3.setSpacing(5)
        split_row3.addWidget(QLabel("补偿直径(mm):"),0)
        comp_dia=QDoubleSpinBox()
        comp_dia.setRange(0,999)
        comp_dia.setValue(1.000)
        comp_dia.setSuffix("")
        split_row3.addWidget(comp_dia,1)
        joint_comp=QCheckBox("拼接补偿")
        split_row3.addWidget(joint_comp,0)
        split_layout.addLayout(split_row3)

        split_group.setLayout(split_layout)
        layout.addWidget(split_group)

        head_group=QGroupBox("双头互移头2优先")
        head_layout=QVBoxLayout()
        head_layout.setContentsMargins(5,5,5,5)
        head_layout.setSpacing(6)

        head_check=QCheckBox("双头互移头2优先")
        head_layout.addWidget(head_check)

        head_group.setLayout(head_layout)
        layout.addWidget(head_group)

        layout.addStretch()

        return widget

    def create_file_tab(self):
        """创建文档标签页"""
        widget=QWidget()
        layout=QVBoxLayout(widget)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(8)

        # 用正式表头替代自定义 header 按钮，保证列与表头对齐且可自适应宽度
        layer_table = QTableWidget()
        layer_table.setColumnCount(4)
        layer_table.setRowCount(19)
        layer_table.setMinimumHeight(200)
        layer_table.setHorizontalHeaderLabels(["编号", "文件名", "工时(时:分:秒:毫秒)", "件数"])
        layer_table.verticalHeader().setVisible(False)
        layer_table.horizontalHeader().setStretchLastSection(False)
        from PyQt5.QtWidgets import QHeaderView
        layer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layer_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layer_table.setStyleSheet("""
            QTableWidget {
                border:1px solid #d0d0d0;
                border-radius:4px;
                background-color:#ffffff;
                gridline-color:#d0d0d0;
            }
            QTableWidget::item {
                padding:4px;
                border:none;
            }
            QTableWidget::item:selected {
                background-color:#e8f0fe;
                color:#000;
            }
        """)

        layout.addWidget(layer_table)

        btn_group=QWidget()
        btn_layout=QVBoxLayout(btn_group)
        btn_layout.setContentsMargins(0,0,0,0)
        btn_layout.setSpacing(4)

        row1=QHBoxLayout()
        row1.setSpacing(4)
        row1.addWidget(QPushButton("读取"))
        row1.addWidget(QPushButton("加工"))
        row1.addWidget(QPushButton("加载"))
        btn_layout.addLayout(row1)

        row2=QHBoxLayout()
        row2.setSpacing(4)
        row2.addWidget(QPushButton("删除"))
        row2.addWidget(QPushButton("全部删除"))
        row2.addWidget(QPushButton("上传"))
        btn_layout.addLayout(row2)

        row3=QHBoxLayout()
        row3.setSpacing(4)
        row3.addWidget(QPushButton("工时计算"))
        row3.addWidget(QPushButton("修改件数"))
        btn_layout.addLayout(row3)

        layout.addWidget(btn_group)
        layout.addStretch()

        return widget

    def on_number_header_btn_click(self):
        """编号"""

    def on_filename_header_btn_click(self):
        """文档名"""

    def on_worktime_header_btn_click(self):
        """工时"""

    def on_quantity_header_btn_click(self):
        """件数"""

    def create_user_tab(self):
        """创建用户标签页（加工参数界面）"""
        widget=QWidget()
        main_layout=QHBoxLayout(widget)
        main_layout.setContentsMargins(8,8,8,8)
        main_layout.setSpacing(8)

        param_widget=QWidget()
        param_layout=QVBoxLayout(param_widget)
        param_layout.setContentsMargins(0,0,0,0)
        param_layout.setSpacing(8)

        param_type_layout=QHBoxLayout()
        param_type_layout.setSpacing(10)
        process_radio=QRadioButton("加工参数")
        process_radio.setChecked(True)
        assist_radio=QRadioButton("辅助参数")
        other_radio=QRadioButton("其他参数")
        param_type_layout.addWidget(process_radio)
        param_type_layout.addWidget(assist_radio)
        param_type_layout.addWidget(other_radio)
        param_type_layout.addStretch()
        param_layout.addLayout(param_type_layout)

        cut_group=QGroupBox("切割参数")
        cut_layout=QVBoxLayout(cut_group)
        cut_layout.setContentsMargins(10,10,10,10)
        cut_layout.setSpacing(6)

        cut_rows=[
            ("空程速度(mm/s)","200.000"),
            ("空程加速度(mm/s2)","3000.000"),
            ("拐弯速度(mm/s)","20.000"),
            ("拐弯加速度(mm/s2)","400.000"),
            ("切割加速度(mm/s2)","3000.000"),
            ("空走延时(ms)","0.000"),
            ("切割加速倍率(0%~200%)","100"),
            ("空程加速倍率(0%~200%)","100"),
            ("拐弯系数(0%~200%)","100"),
        ]
        for label_text,value in cut_rows:
            row_layout=QHBoxLayout()
            row_layout.addWidget(QLabel(label_text),1)
            edit=QLineEdit(value)
            edit.setAlignment(Qt.AlignRight)
            row_layout.addWidget(edit,1)
            cut_layout.addLayout(row_layout)

        cut_layout.addWidget(QPushButton("一键设置"),0,Qt.AlignRight)
        param_layout.addWidget(cut_group)

        scan_group=QGroupBox("扫描参数")
        scan_layout=QVBoxLayout(scan_group)
        scan_layout.setContentsMargins(10,10,10,10)
        scan_layout.setSpacing(6)

        scan_rows=[
            ("x轴起始速度(mm/s)","10.000"),
            ("y轴起始速度(mm/s)","10.000"),
            ("x轴加速度(mm/s2)","10000.000"),
            ("y轴加速度(mm/s2)","3000.000"),
            ("扫描行速度(mm/s)","100.000"),
            ("扫描模式","一般模式"),
            ("光斑大小(50~99%)(mm)","80.000"),
            ("扫描系数","100"),
        ]
        for label_text,value in scan_rows:
            row_layout=QHBoxLayout()
            row_layout.addWidget(QLabel(label_text),1)
            edit=QLineEdit(value)
            edit.setAlignment(Qt.AlignRight)
            row_layout.addWidget(edit,1)
            scan_layout.addLayout(row_layout)
        param_layout.addWidget(scan_group)

        btn_widget=QWidget()
        btn_layout=QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0,0,0,0)
        btn_layout.setSpacing(6)
        btn_layout.addWidget(QPushButton("打开"))
        btn_layout.addWidget(QPushButton("保存"))
        btn_layout.addWidget(QPushButton("读参数"))
        btn_layout.addWidget(QPushButton("写参数"))
        btn_layout.addStretch()

        main_layout.addWidget(param_widget,3)
        main_layout.addWidget(btn_widget,1)

        return widget

    def create_test_tab(self):
        """创建测试标签页"""
        widget=QWidget()
        layout=QVBoxLayout(widget)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(8)

        coord_group=QGroupBox("坐标控制")
        coord_layout=QVBoxLayout(coord_group)
        coord_layout.setContentsMargins(10,10,10,10)
        coord_layout.setSpacing(6)

        coord_display_layout=QHBoxLayout()
        coord_display_layout.addWidget(QLabel("X=?"))
        coord_display_layout.addWidget(QLabel("Y=?"))
        coord_display_layout.addWidget(QLabel("Z=?"))
        coord_display_layout.addStretch()
        coord_display_layout.addWidget(QPushButton("读当前位置"))
        coord_layout.addLayout(coord_display_layout)

        target_layout=QHBoxLayout()
        x_target=QLineEdit("0.000")
        y_target=QLineEdit("0.000")
        target_layout.addWidget(x_target)
        target_layout.addWidget(y_target)
        target_layout.addWidget(QPushButton("移动到目标位置"))
        coord_layout.addLayout(target_layout)

        time_layout=QHBoxLayout()
        time_layout.addWidget(QLabel("0时:0分:0秒:0毫秒"))
        time_layout.addStretch()
        time_layout.addWidget(QPushButton("前次加工时间"))
        coord_layout.addLayout(time_layout)
        layout.addWidget(coord_group)

        axis_group=QGroupBox("单轴移动")
        axis_layout=QVBoxLayout(axis_group)
        axis_layout.setContentsMargins(10,10,10,10)
        axis_layout.setSpacing(6)

        xy_layout=QHBoxLayout()
        xy_button_layout=QVBoxLayout()
        xy_button_layout.addWidget(QPushButton("Y+"))
        xy_mid_layout=QHBoxLayout()
        xy_mid_layout.addWidget(QPushButton("X-"))
        xy_mid_layout.addWidget(QPushButton("原点"))
        xy_mid_layout.addWidget(QPushButton("X+"))
        xy_button_layout.addLayout(xy_mid_layout)
        xy_button_layout.addWidget(QPushButton("Y-"))
        xy_layout.addLayout(xy_button_layout)

        param_layout=QVBoxLayout()
        param_layout.addWidget(QLabel("偏移(mm):"))
        offset_edit=QLineEdit("10.000")
        param_layout.addWidget(offset_edit)
        param_layout.addWidget(QLabel("速度(mm/s):"))
        speed_edit=QLineEdit("50")
        param_layout.addWidget(speed_edit)
        param_layout.addWidget(QLabel("激光功率(%):"))
        power_edit=QLineEdit("0")
        param_layout.addWidget(power_edit)
        xy_layout.addLayout(param_layout)
        axis_layout.addLayout(xy_layout)

        lower_layout=QHBoxLayout()
        zu_button_layout=QVBoxLayout()
        zu_button_layout.addWidget(QPushButton("Z+"))
        zu_mid_layout=QHBoxLayout()
        zu_mid_layout.addWidget(QPushButton("原点"))
        zu_mid_layout.addWidget(QPushButton("Z-"))
        zu_button_layout.addLayout(zu_mid_layout)
        zu_button_layout.addWidget(QPushButton("U+"))
        zu_mid2_layout=QHBoxLayout()
        zu_mid2_layout.addWidget(QPushButton("原点"))
        zu_mid2_layout.addWidget(QPushButton("U-"))
        zu_button_layout.addLayout(zu_mid2_layout)
        lower_layout.addLayout(zu_button_layout)

        check_layout=QVBoxLayout()
        check_layout.addWidget(QCheckBox("连续运动"))
        check_layout.addWidget(QCheckBox("从原点移动"))
        check_layout.addWidget(QCheckBox("是否出光"))
        check_layout.addStretch()
        check_layout.addWidget(QPushButton("寻焦"))
        check_layout.addWidget(QPushButton("定位"))
        lower_layout.addLayout(check_layout)
        axis_layout.addLayout(lower_layout)
        layout.addWidget(axis_group)

        return widget

    def create_transform_tab(self):
        """创建变换标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        #顶部按钮
        btn_layout = QHBoxLayout()
        #按钮+对应的页面索引
        self.transform_btns = []

        position_btn = QPushButton()
        position_icon_path = os.path.join("right_panel_icons", "position.png")
        position_btn.setIcon(QIcon(QPixmap(position_icon_path)))
        position_btn.setIconSize(QSize(32, 32))
        position_btn.setFixedSize(40, 40)
        position_btn.setCheckable(True)
        position_btn.setChecked(True)
        self.transform_btns.append((position_btn, 0))

        rotate_btn = QPushButton()
        rotate_icon_path = os.path.join("right_panel_icons", "rotate.png")
        rotate_btn.setIcon(QIcon(QPixmap(rotate_icon_path)))
        rotate_btn.setIconSize(QSize(32, 32))
        rotate_btn.setFixedSize(40, 40)
        rotate_btn.setCheckable(True)
        self.transform_btns.append((rotate_btn, 1)) #绑定索引1

        scale_btn = QPushButton()
        scale_icon_path = os.path.join("right_panel_icons", "scale.png")
        scale_btn.setIcon(QIcon(QPixmap(scale_icon_path)))
        scale_btn.setIconSize(QSize(32, 32))
        scale_btn.setFixedSize(40, 40)
        scale_btn.setCheckable(True)
        self.transform_btns.append((scale_btn, 2))

        size_btn = QPushButton()
        size_icon_path = os.path.join("right_panel_icons", "size.png")
        size_btn.setIcon(QIcon(QPixmap(size_icon_path)))
        size_btn.setIconSize(QSize(32, 32))
        size_btn.setFixedSize(40, 40)
        self.transform_btns.append((size_btn, 4))

        incline_btn = QPushButton()
        incline_icon_path = os.path.join("right_panel_icons", "incline.png")
        incline_btn.setIcon(QIcon(QPixmap(incline_icon_path)))
        incline_btn.setIconSize(QSize(32, 32))
        incline_btn.setFixedSize(40, 40)
        incline_btn.setCheckable(True)
        self.transform_btns.append((incline_btn, 3))

        #将按钮加入布局，并连接点击事件
        for btn, idx in self.transform_btns:
            btn_layout.addWidget(btn)
            #点击按钮切换到对应页面
            btn.clicked.connect(lambda checked, i=idx: self.switch_transform_page(i))
        main_layout.addLayout(btn_layout)

        #堆栈窗口管理5个页面
        self.transform_stack = QStackedWidget()

        self.transform_stack.addWidget(self.create_position_page())
        self.transform_stack.addWidget(self.create_rotate_page())
        self.transform_stack.addWidget(self.create_scale_page())
        self.transform_stack.addWidget(self.create_size_page())
        self.transform_stack.addWidget(self.create_incline_page())
        main_layout.addWidget(self.transform_stack)

        return widget

    def create_history_tab(self):
        """创建历史记录标签页：显示撤销/重做历史并支持跳转"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        info_label = QLabel("操作历史（双击某项跳转到该状态）：")
        layout.addWidget(info_label)

        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_list.setAlternatingRowColors(True)
        layout.addWidget(self.history_list, 1)

        # 跳转说明和清空按钮
        btn_row = QHBoxLayout()
        self.history_jump_btn = QPushButton("跳转到选中")
        self.history_clear_btn = QPushButton("清空历史")
        btn_row.addWidget(self.history_jump_btn)
        btn_row.addWidget(self.history_clear_btn)
        layout.addLayout(btn_row)

        # 事件连接由 MainWindow 负责（需要访问 edit_manager）
        # 但提供本地槽以便被 MainWindow 连接
        # 事件将在 MainWindow 中连接到 edit_manager 的操作
        self.history_jump_btn.clicked.connect(lambda: None)
        self.history_clear_btn.clicked.connect(lambda: None)

        return widget

    def update_history(self, descriptions: list, current_index: int):
        """外部调用以更新历史列表显示。"""
        try:
            self.history_list.clear()
            for i, d in enumerate(descriptions):
                item = QListWidgetItem(f"{i+1}. {d}")
                # 默认样式
                item.setBackground(QColor(255, 255, 255))
                item.setForeground(QColor(40, 40, 40))
                self.history_list.addItem(item)

            # current_index 表示下一个将被 redo 的索引
            # 我们高亮当前状态前一项（即已执行的最后一项）
            cur_row = current_index - 1
            for r in range(self.history_list.count()):
                it = self.history_list.item(r)
                if r == cur_row:
                    # 深色高亮
                    it.setBackground(QColor(30, 120, 200))
                    it.setForeground(QColor(255, 255, 255))
                else:
                    it.setBackground(QColor(255, 255, 255))
                    it.setForeground(QColor(40, 40, 40))
        except Exception:
            pass

    #5个页面的创建函数
    def create_position_page(self):
        """创建移动页面"""
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(6)
        page.setStyleSheet("""
                    /* 旋转/中心框：背景白色，边框浅灰（和页面融合） */
                    QGroupBox {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，弱化边界感 */
                        border-radius:2px;
                    }
                    /* 标签：背景透明，消除灰色 */
                    QLabel {
                        background-color:transparent;
                        color:#333333;  /* 文字颜色（可选，保持可读性） */
                    }
                    /* 输入框：背景白色，边框浅灰（与背景融合） */
                    QLineEdit {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，避免突兀 */
                        padding:2px;
                    }
                """)

        pos_group=QGroupBox("位置:")
        pos_layout=QVBoxLayout(pos_group)
        pos_layout.setContentsMargins(10,10,10,10)
        pos_layout.setSpacing(6)

        #水平行
        hor_layout=QHBoxLayout()
        hor_layout.setSpacing(5)
        hor_label=QLabel("水平(H)")
        # 使用QDoubleSpinBox以支持0.01mm精度并保持可访问性
        self.import_center_x_spin = QDoubleSpinBox()
        self.import_center_x_spin.setRange(-10000.0, 10000.0)
        self.import_center_x_spin.setDecimals(2)
        self.import_center_x_spin.setSingleStep(0.01)
        self.import_center_x_spin.setFixedWidth(200)
        mm_label=QLabel("mm")
        hor_layout.addWidget(hor_label)
        hor_layout.addWidget(self.import_center_x_spin)
        hor_layout.addWidget(mm_label)
        hor_layout.addStretch(0)
        pos_layout.addLayout(hor_layout)

        #垂直行
        ver_layout=QHBoxLayout()
        ver_layout.setSpacing(5)
        ver_layout.addWidget(QLabel("垂直(V)"))
        self.import_center_y_spin = QDoubleSpinBox()
        self.import_center_y_spin.setRange(-10000.0, 10000.0)
        self.import_center_y_spin.setDecimals(2)
        self.import_center_y_spin.setSingleStep(0.01)
        self.import_center_y_spin.setFixedWidth(200)
        ver_mm_label=QLabel("mm")
        ver_layout.addWidget(self.import_center_y_spin)
        ver_layout.addWidget(ver_mm_label)
        ver_layout.addStretch(0)
        pos_layout.addLayout(ver_layout)

        layout.addWidget(pos_group)

        apply_layout=QVBoxLayout()
        apply_layout.addWidget(QCheckBox("不按比例"))

        dir_check_layout=QHBoxLayout()
        dir_check_layout.addStretch()
        dir_checks=[QCheckBox("") for _ in range(9)]
        grid=QGridLayout()
        for i in range(3):
            for j in range(3):
                grid.addWidget(dir_checks[i*3+j],i,j)
        dir_check_layout.addLayout(grid)
        dir_check_layout.addStretch()
        apply_layout.addLayout(dir_check_layout)

        btn_row=QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(QPushButton("应用到复制"))
        btn_row.addWidget(QPushButton("应用"))
        btn_row.addStretch()
        apply_layout.addLayout(btn_row)
        layout.addLayout(apply_layout)

        return page

    def get_import_center_mm(self):
        """返回用户在位置面板中设置的导入中心（以毫米为单位）。

        如果面板控件不存在或出错，返回 None。
        """
        try:
            return float(self.import_center_x_spin.value()), float(self.import_center_y_spin.value())
        except Exception:
            return None


    def create_rotate_page(self):
        """创建旋转页面"""
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(5,5,5,5)
        layout.setSpacing(3)

        #全局样式
        page.setStyleSheet("""
            /* 旋转/中心框：背景白色，边框浅灰（和页面融合） */
            QGroupBox {
                background-color:#ffffff;
                border:1px solid #e0e0e0;  /* 浅灰边框，弱化边界感 */
                border-radius:2px;
            }
            /* 标签：背景透明，消除灰色 */
            QLabel {
                background-color:transparent;
                color:#333333;  /* 文字颜色（可选，保持可读性） */
            }
            /* 输入框：背景白色，边框浅灰（与背景融合） */
            QLineEdit {
                background-color:#ffffff;
                border:1px solid #e0e0e0;  /* 浅灰边框，避免突兀 */
                padding:2px;
            }
        """)

        rotate_group=QGroupBox("旋转:")
        rotate_layout=QVBoxLayout(rotate_group)
        rotate_layout.setContentsMargins(5,8,5,8)
        rotate_layout.setSpacing(4)

        #角度
        angle_row_layout=QHBoxLayout()
        angle_row_layout.setSpacing(3)
        angle_row_layout.addWidget(QLabel("角度"))
        angle_edit=QLineEdit("0")
        angle_edit.setFixedWidth(100)
        angle_row_layout.addWidget(angle_edit)
        angle_row_layout.addWidget(QLabel("°"))
        angle_row_layout.addStretch(1)
        rotate_layout.addLayout(angle_row_layout)

        rotate_group.setFixedHeight(80)
        layout.addWidget(rotate_group)

        #中心
        center_group=QGroupBox("中心:")
        center_layout=QVBoxLayout(center_group)
        center_layout.setContentsMargins(10,0,10,0)
        center_layout.setSpacing(2)

        hor_layout=QHBoxLayout()
        hor_layout.setSpacing(5)
        hor_label=QLabel("水平(H)")
        hor_edit=QLineEdit("0")
        hor_edit.setFixedWidth(200)
        hor_edit.setFixedHeight(22)
        mm_label=QLabel("mm")
        hor_layout.addWidget(hor_label)
        hor_layout.addWidget(hor_edit)
        hor_layout.addWidget(mm_label)
        hor_layout.addStretch(0)
        center_layout.addLayout(hor_layout)

        ver_layout=QHBoxLayout()
        ver_layout.setSpacing(5)
        ver_layout.addWidget(QLabel("垂直(V)"))
        ver_edit=QLineEdit("0")
        ver_edit.setFixedWidth(200)
        ver_edit.setFixedHeight(22)
        ver_mm_label=QLabel("mm")
        ver_layout.addWidget(ver_edit)
        ver_layout.addWidget(ver_mm_label)
        ver_layout.addStretch(0)
        center_layout.addLayout(ver_layout)

        center_group.setFixedHeight(120)
        layout.addWidget(center_group)

        apply_layout=QVBoxLayout()
        apply_layout.setSpacing(2)
        apply_layout.addWidget(QCheckBox("锁定旋转中心位置"))
        apply_layout.addWidget(QCheckBox("相对中心"))

        #方向九宫格
        dir_check_layout=QHBoxLayout()
        dir_check_layout.addStretch(1)
        dir_checks=[QCheckBox("") for _ in range(9)]
        grid=QGridLayout()
        grid.setSpacing(2)
        for i in range(3):
            for j in range(3):
                grid.addWidget(dir_checks[i*3+j],i,j)
        dir_check_layout.addLayout(grid)
        dir_check_layout.addStretch(1)
        apply_layout.addLayout(dir_check_layout)

        #应用按钮行
        btn_row=QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(QPushButton("应用到复制"))
        btn_row.addWidget(QPushButton("应用"))
        btn_row.addStretch(1)
        apply_layout.addLayout(btn_row)
        layout.addLayout(apply_layout)

        return page

    def create_scale_page(self):
        """创建比例页面"""
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(6)

        page.setStyleSheet("""
                    /* 旋转/中心框：背景白色，边框浅灰（和页面融合） */
                    QGroupBox {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，弱化边界感 */
                        border-radius:2px;
                    }
                    /* 标签：背景透明，消除灰色 */
                    QLabel {
                        background-color:transparent;
                        color:#333333;  /* 文字颜色（可选，保持可读性） */
                    }
                    /* 输入框：背景白色，边框浅灰（与背景融合） */
                    QLineEdit {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，避免突兀 */
                        padding:2px;
                    }
                """)

        scale_group=QGroupBox("比例:")
        scale_layout=QVBoxLayout(scale_group)
        scale_layout.setContentsMargins(10,10,10,10)
        scale_layout.setSpacing(6)

        hor_layout=QHBoxLayout()
        hor_layout.setSpacing(5)
        hor_label=QLabel("水平(H)")
        hor_edit=QLineEdit("0")
        hor_edit.setFixedWidth(200)
        hor_edit.setFixedHeight(22)
        mm_label=QLabel("mm")
        hor_layout.addWidget(hor_label)
        hor_layout.addWidget(hor_edit)
        hor_layout.addWidget(mm_label)
        hor_layout.addStretch(0)
        scale_layout.addLayout(hor_layout)

        ver_layout=QHBoxLayout()
        ver_layout.setSpacing(5)
        ver_layout.addWidget(QLabel("垂直(V)"))
        ver_edit=QLineEdit("0")
        ver_edit.setFixedWidth(200)
        ver_edit.setFixedHeight(22)
        ver_mm_label=QLabel("mm")
        ver_layout.addWidget(ver_edit)
        ver_layout.addWidget(ver_mm_label)
        ver_layout.addStretch(0)
        scale_layout.addLayout(ver_layout)
        layout.addWidget(scale_group)

        mirror_group=QGroupBox("镜向:")
        mirror_layout=QHBoxLayout(mirror_group)
        mirror_layout.addStretch()
        #镜向按钮
        mirror_layout.addWidget(QPushButton("水平镜向"))
        mirror_layout.addWidget(QPushButton("垂直镜向"))
        mirror_layout.addStretch()
        layout.addWidget(mirror_group)

        apply_layout=QVBoxLayout()
        apply_layout.addWidget(QCheckBox("不按比例"))
        #方向选择
        dir_check_layout=QHBoxLayout()
        dir_check_layout.addStretch()
        dir_checks=[QCheckBox("") for _ in range(9)]
        grid=QGridLayout()
        for i in range(3):
            for j in range(3):
                grid.addWidget(dir_checks[i*3+j],i,j)
        dir_check_layout.addLayout(grid)
        dir_check_layout.addStretch()
        apply_layout.addLayout(dir_check_layout)

        btn_row=QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(QPushButton("应用到复制"))
        btn_row.addWidget(QPushButton("应用"))
        btn_row.addStretch()
        apply_layout.addLayout(btn_row)
        layout.addLayout(apply_layout)

        return page


    def create_size_page(self):
        """创建大小页面"""
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(6)

        page.setStyleSheet("""
                    /* 旋转/中心框：背景白色，边框浅灰（和页面融合） */
                    QGroupBox {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，弱化边界感 */
                        border-radius:2px;
                    }
                    /* 标签：背景透明，消除灰色 */
                    QLabel {
                        background-color:transparent;
                        color:#333333;  /* 文字颜色（可选，保持可读性） */
                    }
                    /* 输入框：背景白色，边框浅灰（与背景融合） */
                    QLineEdit {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，避免突兀 */
                        padding:2px;
                    }
                """)

        size_group=QGroupBox("大小:")
        size_layout=QVBoxLayout(size_group)
        size_layout.setContentsMargins(10,10,10,10)
        size_layout.setSpacing(6)

        hor_layout=QHBoxLayout()
        hor_layout.setSpacing(5)
        hor_label=QLabel("水平(H)")
        hor_edit=QLineEdit("0")
        hor_edit.setFixedWidth(200)
        hor_edit.setFixedHeight(22)
        mm_label=QLabel("mm")
        hor_layout.addWidget(hor_label)
        hor_layout.addWidget(hor_edit)
        hor_layout.addWidget(mm_label)
        hor_layout.addStretch(0)
        size_layout.addLayout(hor_layout)

        ver_layout=QHBoxLayout()
        ver_layout.setSpacing(5)
        ver_layout.addWidget(QLabel("垂直(V)"))
        ver_edit=QLineEdit("0")
        ver_edit.setFixedWidth(200)
        ver_edit.setFixedHeight(22)
        ver_mm_label=QLabel("mm")
        ver_layout.addWidget(ver_edit)
        ver_layout.addWidget(ver_mm_label)
        ver_layout.addStretch(0)
        size_layout.addLayout(ver_layout)

        layout.addWidget(size_group)

        apply_layout=QVBoxLayout()
        apply_layout.addWidget(QCheckBox("不按比例"))
        #方向选择
        dir_check_layout=QHBoxLayout()
        dir_check_layout.addStretch()
        dir_checks=[QCheckBox("") for _ in range(9)]
        grid=QGridLayout()
        for i in range(3):
            for j in range(3):
                grid.addWidget(dir_checks[i*3+j],i,j)
        dir_check_layout.addLayout(grid)
        dir_check_layout.addStretch()
        apply_layout.addLayout(dir_check_layout)

        btn_row=QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(QPushButton("应用到复制"))
        btn_row.addWidget(QPushButton("应用"))
        btn_row.addStretch()
        apply_layout.addLayout(btn_row)
        layout.addLayout(apply_layout)

        return page

    def create_incline_page(self):
        """创建倾斜页面"""
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(6)

        page.setStyleSheet("""
                    /* 旋转/中心框：背景白色，边框浅灰（和页面融合） */
                    QGroupBox {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，弱化边界感 */
                        border-radius:2px;
                    }
                    /* 标签：背景透明，消除灰色 */
                    QLabel {
                        background-color:transparent;
                        color:#333333;  /* 文字颜色（可选，保持可读性） */
                    }
                    /* 输入框：背景白色，边框浅灰（与背景融合） */
                    QLineEdit {
                        background-color:#ffffff;
                        border:1px solid #e0e0e0;  /* 浅灰边框，避免突兀 */
                        padding:2px;
                    }
                """)

        skew_group=QGroupBox("倾斜:")
        skew_layout=QVBoxLayout(skew_group)
        skew_layout.setContentsMargins(10,10,10,10)
        skew_layout.setSpacing(6)

        hor_layout=QHBoxLayout()
        hor_layout.setSpacing(5)
        hor_label=QLabel("水平(H)")
        hor_edit=QLineEdit("0")
        hor_edit.setFixedWidth(200)
        hor_edit.setFixedHeight(22)
        mm_label=QLabel("mm")
        hor_layout.addWidget(hor_label)
        hor_layout.addWidget(hor_edit)
        hor_layout.addWidget(mm_label)
        hor_layout.addStretch(0)
        skew_layout.addLayout(hor_layout)

        ver_layout=QHBoxLayout()
        ver_layout.setSpacing(5)
        ver_layout.addWidget(QLabel("垂直(V)"))
        ver_edit=QLineEdit("0")
        ver_edit.setFixedWidth(200)
        ver_edit.setFixedHeight(22)
        ver_mm_label=QLabel("mm")
        ver_layout.addWidget(ver_edit)
        ver_layout.addWidget(ver_mm_label)
        ver_layout.addStretch(0)
        skew_layout.addLayout(ver_layout)

        layout.addWidget(skew_group)

        apply_layout=QVBoxLayout()
        apply_layout.addWidget(QCheckBox("使用锚点"))
        #方向选择
        dir_check_layout=QHBoxLayout()
        dir_check_layout.addStretch()
        dir_checks=[QCheckBox("") for _ in range(9)]
        grid=QGridLayout()
        for i in range(3):
            for j in range(3):
                grid.addWidget(dir_checks[i*3+j],i,j)
        dir_check_layout.addLayout(grid)
        dir_check_layout.addStretch()
        apply_layout.addLayout(dir_check_layout)

        btn_row=QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(QPushButton("应用到复制"))
        btn_row.addWidget(QPushButton("应用"))
        btn_row.addStretch()
        apply_layout.addLayout(btn_row)
        layout.addLayout(apply_layout)

        return page


    #页面切换函数
    def switch_transform_page(self, page_idx):
        """切换变换页面，并更新按钮选中状态"""
        self.transform_stack.setCurrentIndex(page_idx)
        for btn, idx in self.transform_btns:
            btn.setChecked(idx == page_idx)