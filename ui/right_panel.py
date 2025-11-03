#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧属性面板
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QIcon


class RightPanel(QWidget):
    """右侧属性面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        
        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_processing_tab(), "加工")
        self.tabs.addTab(self.create_placeholder_tab("输出"), "输出")
        self.tabs.addTab(self.create_placeholder_tab("文件"), "文件")
        self.tabs.addTab(self.create_placeholder_tab("用户"), "用户")
        self.tabs.addTab(self.create_placeholder_tab("测试"), "测试")
        self.tabs.addTab(self.create_placeholder_tab("装载"), "装载")
        
        layout.addWidget(self.tabs)

        # 设置最小宽度和最大宽度（允许用户调整）
        self.setMinimumWidth(380)
        self.setMaximumWidth(600)
        
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
        
    def create_processing_tab(self):
        """创建加工标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 图层选择
        layer_group = QGroupBox("图层")
        layer_layout = QVBoxLayout()
        
        layer_combo = QComboBox()
        layer_combo.addItems(["图层", "输出", "建筑"])
        layer_layout.addWidget(layer_combo)
        
        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)
        
        # 参数设置
        param_group = QGroupBox("参数设置")
        param_layout = QVBoxLayout()
        param_layout.setContentsMargins(5, 5, 5, 5)
        param_layout.setSpacing(6)
        
        # 颜色
        color_row = QHBoxLayout()
        color_row.setSpacing(5)
        color_row.addWidget(QLabel("颜色"), 0)
        color_btn = QPushButton()
        color_btn.setFixedSize(100, 25)
        color_btn.setStyleSheet("background-color: black; border: 1px solid #888;")
        color_row.addWidget(color_btn, 1)
        param_layout.addLayout(color_row)

        # 速度
        speed_row = QHBoxLayout()
        speed_row.setSpacing(5)
        speed_row.addWidget(QLabel("速度(mm/s)"), 0)
        speed_spin = QDoubleSpinBox()
        speed_spin.setRange(0, 1000)
        speed_spin.setValue(100.0)
        speed_spin.setMinimumWidth(100)
        speed_row.addWidget(speed_spin, 1)
        param_layout.addLayout(speed_row)

        # 优先级
        priority_row = QHBoxLayout()
        priority_row.setSpacing(5)
        priority_row.addWidget(QLabel("优先级"), 0)
        priority_spin = QSpinBox()
        priority_spin.setRange(1, 10)
        priority_spin.setValue(1)
        priority_spin.setMinimumWidth(100)
        priority_row.addWidget(priority_spin, 1)
        param_layout.addLayout(priority_row)

        # 最小功率
        min_power_row = QHBoxLayout()
        min_power_row.setSpacing(5)
        min_power_row.addWidget(QLabel("最小功率(%)"), 0)
        min_power_spin = QDoubleSpinBox()
        min_power_spin.setRange(0, 100)
        min_power_spin.setValue(30.0)
        min_power_spin.setMinimumWidth(100)
        min_power_row.addWidget(min_power_spin, 1)
        param_layout.addLayout(min_power_row)

        # 最大功率
        max_power_row = QHBoxLayout()
        max_power_row.setSpacing(5)
        max_power_row.addWidget(QLabel("最大功率(%)"), 0)
        max_power_spin = QDoubleSpinBox()
        max_power_spin.setRange(0, 100)
        max_power_spin.setValue(30.0)
        max_power_spin.setMinimumWidth(100)
        max_power_row.addWidget(max_power_spin, 1)
        param_layout.addLayout(max_power_row)
        
        param_group.setLayout(param_layout)
        layout.addWidget(param_group)
        
        # 激光1/激光2 子标签页
        laser_tabs = QTabWidget()
        laser_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #e8e8e8;
                padding: 6px 12px;
                margin-right: 2px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 2px solid #0078d7;
            }
        """)

        # 激光1标签页
        laser1_widget = QWidget()
        laser1_layout = QVBoxLayout(laser1_widget)
        laser1_layout.setContentsMargins(5, 5, 5, 5)
        laser1_layout.setSpacing(8)

        # 行列设置
        grid_group = QGroupBox("行列设置")
        grid_layout = QVBoxLayout()
        grid_layout.setContentsMargins(5, 5, 5, 5)
        grid_layout.setSpacing(4)

        # 表头
        header_layout = QHBoxLayout()
        header_layout.setSpacing(2)
        header_layout.addWidget(QLabel(""), 0)
        header_layout.addWidget(QLabel("个数"), 1)
        header_layout.addWidget(QLabel("奇间隔"), 1)
        header_layout.addWidget(QLabel("偶间隔"), 1)
        header_layout.addWidget(QLabel("错位"), 1)
        header_layout.addWidget(QLabel("编向"), 1)
        grid_layout.addLayout(header_layout)

        # X行
        x_row = QHBoxLayout()
        x_row.setSpacing(2)
        x_row.addWidget(QLabel("X:"), 0)
        # 个数
        x_count_edit = QLineEdit("1")
        x_count_edit.setMinimumWidth(50)
        x_row.addWidget(x_count_edit, 1)
        # 奇间隔、偶间隔、错位
        for _ in range(3):
            edit = QLineEdit("0.000")
            edit.setMinimumWidth(50)
            x_row.addWidget(edit, 1)
        # 编向 - 两个复选框带标签
        x_checkbox_layout = QHBoxLayout()
        x_checkbox_layout.setSpacing(5)
        x_checkbox1 = QCheckBox("H")
        x_checkbox2 = QCheckBox("V")
        x_checkbox_layout.addWidget(x_checkbox1)
        x_checkbox_layout.addWidget(x_checkbox2)
        x_checkbox_layout.addStretch()
        x_row.addLayout(x_checkbox_layout, 1)
        grid_layout.addLayout(x_row)

        # Y行
        y_row = QHBoxLayout()
        y_row.setSpacing(2)
        y_row.addWidget(QLabel("Y:"), 0)
        # 个数
        y_count_edit = QLineEdit("1")
        y_count_edit.setMinimumWidth(50)
        y_row.addWidget(y_count_edit, 1)
        # 奇间隔、偶间隔、错位
        for _ in range(3):
            edit = QLineEdit("0.000")
            edit.setMinimumWidth(50)
            y_row.addWidget(edit, 1)
        # 编向 - 两个复选框带标签
        y_checkbox_layout = QHBoxLayout()
        y_checkbox_layout.setSpacing(5)
        y_checkbox1 = QCheckBox("H")
        y_checkbox2 = QCheckBox("V")
        y_checkbox_layout.addWidget(y_checkbox1)
        y_checkbox_layout.addWidget(y_checkbox2)
        y_checkbox_layout.addStretch()
        y_row.addLayout(y_checkbox_layout, 1)
        grid_layout.addLayout(y_row)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        # 左侧图标按钮
        icon_btn = QPushButton()
        icon_btn.setFixedSize(32, 32)
        icon_btn.setIcon(QIcon("grid_icon.png"))
        icon_btn.setIconSize(QSize(28, 28))
        icon_btn.setStyleSheet("border: 1px solid #888;")
        btn_row.addWidget(icon_btn, 0)
        # 中间按钮
        btn_row.addWidget(QPushButton("虚拟阵列"), 1)
        btn_row.addWidget(QPushButton("布满"), 1)
        btn_row.addWidget(QPushButton("自动排版"), 1)
        # 右侧...按钮
        more_btn = QPushButton("...")
        more_btn.setFixedWidth(30)
        btn_row.addWidget(more_btn, 0)
        grid_layout.addLayout(btn_row)

        grid_group.setLayout(grid_layout)
        laser1_layout.addWidget(grid_group)

        # 激光2标签页（占位）
        laser2_widget = QWidget()
        laser2_layout = QVBoxLayout(laser2_widget)
        laser2_label = QLabel("激光2功能区")
        laser2_label.setAlignment(Qt.AlignCenter)
        laser2_label.setStyleSheet("color: #888; font-size: 14px;")
        laser2_layout.addWidget(laser2_label)
        laser2_layout.addStretch()

        # 添加子标签页
        laser_tabs.addTab(laser1_widget, "激光1")
        laser_tabs.addTab(laser2_widget, "激光2")
        layout.addWidget(laser_tabs)
        
        # 数据加工
        process_group = QGroupBox("数据加工")
        process_layout = QVBoxLayout()
        process_layout.setContentsMargins(5, 5, 5, 5)
        process_layout.setSpacing(6)

        # 控制按钮
        control_btn_layout = QHBoxLayout()
        control_btn_layout.setSpacing(3)
        start_btn = QPushButton("开始")
        start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        start_btn.setMinimumHeight(36)
        pause_btn = QPushButton("暂停/继续")
        pause_btn.setStyleSheet("background-color: #FF9800; color: white;")
        pause_btn.setMinimumHeight(36)
        stop_btn = QPushButton("停止")
        stop_btn.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
        stop_btn.setMinimumHeight(36)
        control_btn_layout.addWidget(start_btn, 1)
        control_btn_layout.addWidget(pause_btn, 1)
        control_btn_layout.addWidget(stop_btn, 1)
        process_layout.addLayout(control_btn_layout)

        # 文件操作按钮
        file_btn1 = QPushButton("保存为版位文件")
        file_btn1.setMinimumHeight(32)
        process_layout.addWidget(file_btn1)

        file_btn2 = QPushButton("载机文件输出")
        file_btn2.setMinimumHeight(32)
        process_layout.addWidget(file_btn2)

        file_btn3 = QPushButton("下载")
        file_btn3.setMinimumHeight(32)
        process_layout.addWidget(file_btn3)

        # 定位选项
        pos_layout = QHBoxLayout()
        pos_layout.setSpacing(5)
        pos_layout.addWidget(QLabel("图形定位:"), 0)
        pos_combo = QComboBox()
        pos_combo.addItems(["当前位置", "左上角", "中心"])
        pos_layout.addWidget(pos_combo, 1)
        process_layout.addLayout(pos_layout)

        # 优化选项
        optimize_check = QCheckBox("确定优化")
        optimize_check.setChecked(True)
        process_layout.addWidget(optimize_check)

        # 其他选项
        other_layout = QHBoxLayout()
        other_layout.setSpacing(3)
        other_layout.addWidget(QPushButton("切换坐标"), 1)
        other_layout.addWidget(QPushButton("走边"), 1)
        process_layout.addLayout(other_layout)
        
        process_group.setLayout(process_layout)
        layout.addWidget(process_group)
        
        layout.addStretch()
        
        return widget
        
    def create_placeholder_tab(self, name):
        """创建占位标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(f"{name}功能区")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()
        return widget

