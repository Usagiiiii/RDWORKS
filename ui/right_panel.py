#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧属性面板
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                             QRadioButton, QGridLayout)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QIcon


class RightPanel(QWidget):
    """右侧属性面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_processing_tab(), "加工")
        self.tabs.addTab(self.create_output_tab(), "输出")
        self.tabs.addTab(self.create_file_tab(), "文档")
        self.tabs.addTab(self.create_user_tab(), "用户")
        self.tabs.addTab(self.create_test_tab(), "测试")
        self.tabs.addTab(self.create_transform_tab(), "变换")

        root_layout.addWidget(self.tabs, 1)

        self.create_fixed_bottom_area(root_layout)

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

    def create_fixed_bottom_area(self, parent_layout):
        """底部的区域"""
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(8)

        process_group = QGroupBox("数据加工")
        process_layout = QVBoxLayout()
        process_layout.setContentsMargins(5, 5, 5, 5)
        process_layout.setSpacing(6)

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

        file_btn1 = QPushButton("保存为版位文件")
        file_btn1.setMinimumHeight(32)
        process_layout.addWidget(file_btn1)

        file_btn2 = QPushButton("载机文件输出")
        file_btn2.setMinimumHeight(32)
        process_layout.addWidget(file_btn2)

        file_btn3 = QPushButton("下载")
        file_btn3.setMinimumHeight(32)
        process_layout.addWidget(file_btn3)

        pos_layout = QHBoxLayout()
        pos_layout.setSpacing(5)
        pos_layout.addWidget(QLabel("图形定位:"), 0)
        pos_combo = QComboBox()
        pos_combo.addItems(["当前位置", "左上角", "中心"])
        pos_layout.addWidget(pos_combo, 1)
        process_layout.addLayout(pos_layout)

        optimize_check = QCheckBox("确定优化")
        optimize_check.setChecked(True)
        process_layout.addWidget(optimize_check)

        other_layout = QHBoxLayout()
        other_layout.setSpacing(3)
        other_layout.addWidget(QPushButton("切换坐标"), 1)
        other_layout.addWidget(QPushButton("走边"), 1)
        process_layout.addLayout(other_layout)

        process_group.setLayout(process_layout)
        bottom_layout.addWidget(process_group)
        parent_layout.addWidget(bottom_widget)

        bottom_widget.setStyleSheet("""
               background-color: #f5f5f5;
               border-top: 1px solid #d0d0d0;  /* 顶部加一条分割线，区分上下区域 */
               padding-top: 8px;
           """)

    def create_processing_tab(self):
        """创建加工标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: transparent;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(1)

        # 4个表头按钮（真正的按钮样式：有边框、hover、按压效果）
        header_btns = [
            ("图层", self.on_layer_header_btn_click),
            ("模式", self.on_mode_header_btn_click),
            ("输出", self.on_output_header_btn_click),
            ("隐藏", self.on_hide_header_btn_click)
        ]
        for btn_text, btn_callback in header_btns:
            btn = QPushButton(btn_text)
            btn.setStyleSheet("""
                        QPushButton {
                            border: 1px solid #d0d0d0;
                            border-radius: 4px;
                            background-color: #f0f0f0;
                            font-weight: bold;
                            font-size: 12px;
                            text-align: center;
                            padding: 8px 0;
                            margin: 0;
                        }
                        QPushButton:hover {
                            background-color: #e0e0e0;
                            border-color: #b0b0b0;
                        }
                        QPushButton:pressed {
                            background-color: #d0d0d0;
                            border-color: #909090;
                        }
                    """)
            btn.clicked.connect(btn_callback)
            header_layout.addWidget(btn, 1)

        layer_table = QTableWidget()
        layer_table.setColumnCount(4)
        layer_table.setRowCount(7)
        layer_table.setMinimumHeight(240)
        layer_table.verticalHeader().setVisible(False)
        layer_table.verticalHeader().setDefaultSectionSize(30)
        layer_table.horizontalHeader().setDefaultSectionSize(135)
        layer_table.horizontalHeader().setVisible(False)
        layer_table.horizontalHeader().setStretchLastSection(True)
        layer_table.setStyleSheet("""
                    QTableWidget {
                        border: 1px solid #d0d0d0;
                        border-radius: 4px;
                        background-color: #ffffff;
                        gridline-color: #d0d0d0;
                    }
                    QTableWidget::item {
                        padding: 4px;
                        border: none;
                    }
                    QTableWidget::item:selected {
                        background-color: #e8f0fe;
                        color: #000;
                    }
                """)

        top_layout.addWidget(header_widget)
        top_layout.addWidget(layer_table)

        # 参数设置
        param_group = QGroupBox("")
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
        top_layout.addWidget(param_group)

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
        top_layout.addWidget(laser_tabs)

        main_layout.addWidget(top_widget, 1)

        return widget

    def on_layer_header_btn_click(self):
        """图层"""

    def on_mode_header_btn_click(self):
        """模式"""

    def on_output_header_btn_click(self):
        """输出"""

    def on_hide_header_btn_click(self):
        """隐藏"""

    def create_output_tab(self):
        """输出页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        cycle_group = QGroupBox("")
        cycle_layout = QVBoxLayout()
        cycle_layout.setContentsMargins(5, 5, 5, 5)
        cycle_layout.setSpacing(6)

        cycle_check = QCheckBox("循环加工")
        cycle_layout.addWidget(cycle_check)

        cycle_row1 = QHBoxLayout()
        cycle_row1.setSpacing(5)
        cycle_row1.addWidget(QLabel("循环次数:"), 0)
        cycle_count = QSpinBox()
        cycle_count.setRange(0, 999)
        cycle_count.setValue(0)
        cycle_row1.addWidget(cycle_count, 1)
        cycle_row1.addWidget(QLabel("先切割后送料"), 0)
        cycle_order = QComboBox()
        cycle_order.addItems(["先切割后送料", "先送料后切割", "往返送料"])
        cycle_row1.addWidget(cycle_order, 1)
        cycle_layout.addLayout(cycle_row1)

        cycle_row2 = QHBoxLayout()
        cycle_row2.setSpacing(5)
        cycle_row2.addWidget(QLabel("送料长度:"), 0)
        feed_length = QDoubleSpinBox()
        feed_length.setRange(0, 9999)
        feed_length.setValue(500.0)
        feed_length.setSuffix("")
        cycle_row2.addWidget(feed_length, 1)
        cycle_row2.addWidget(QLabel("手动输入"), 0)
        feed_input = QComboBox()
        feed_input.addItems(["手动输入", "Y向幅面", "图形高度", "最小送料长度"])
        cycle_row2.addWidget(feed_input, 1)
        cycle_layout.addLayout(cycle_row2)

        cycle_row3 = QHBoxLayout()
        cycle_row3.setSpacing(5)
        cycle_row3.addWidget(QLabel("送料补偿:"), 0)
        feed_comp = QDoubleSpinBox()
        feed_comp.setRange(0, 999)
        feed_comp.setValue(0.000)
        feed_comp.setSuffix("")
        cycle_row3.addWidget(feed_comp, 1)
        pause_check = QCheckBox("送料后暂停")
        cycle_row3.addWidget(pause_check, 0)
        cycle_layout.addLayout(cycle_row3)

        cycle_group.setLayout(cycle_layout)
        layout.addWidget(cycle_group)

        split_group = QGroupBox("超幅面分块切割")
        split_layout = QVBoxLayout()
        split_layout.setContentsMargins(5, 5, 5, 5)
        split_layout.setSpacing(6)

        split_check = QCheckBox("超幅面分块切割")
        split_layout.addWidget(split_check)

        split_row1 = QHBoxLayout()
        split_row1.setSpacing(5)
        split_row1.addWidget(QLabel("幅面高度:"), 0)
        height = QDoubleSpinBox()
        height.setRange(0, 9999)
        height.setValue(500.000)
        height.setSuffix("")
        split_row1.addWidget(height, 1)
        force_split = QCheckBox("强制分块")
        split_row1.addWidget(force_split, 0)
        split_layout.addLayout(split_row1)

        split_row2 = QHBoxLayout()
        split_row2.setSpacing(5)
        split_row2.addWidget(QLabel("角度补偿:"), 0)
        angle_comp = QDoubleSpinBox()
        angle_comp.setRange(0, 999)
        angle_comp.setValue(0.000)
        angle_comp.setSuffix("")
        split_row2.addWidget(angle_comp, 1)
        end_feed = QCheckBox("结束送料")
        split_row2.addWidget(end_feed, 0)
        split_layout.addLayout(split_row2)

        split_row3 = QHBoxLayout()
        split_row3.setSpacing(5)
        split_row3.addWidget(QLabel("补偿直径(mm):"), 0)
        comp_dia = QDoubleSpinBox()
        comp_dia.setRange(0, 999)
        comp_dia.setValue(1.000)
        comp_dia.setSuffix("")
        split_row3.addWidget(comp_dia, 1)
        joint_comp = QCheckBox("拼接补偿")
        split_row3.addWidget(joint_comp, 0)
        split_layout.addLayout(split_row3)

        split_group.setLayout(split_layout)
        layout.addWidget(split_group)

        head_group = QGroupBox("双头互移头2优先")
        head_layout = QVBoxLayout()
        head_layout.setContentsMargins(5, 5, 5, 5)
        head_layout.setSpacing(6)

        head_check = QCheckBox("双头互移头2优先")
        head_layout.addWidget(head_check)

        head_group.setLayout(head_layout)
        layout.addWidget(head_group)

        layout.addStretch()

        return widget

    def create_file_tab(self):
        """创建文档标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setStyleSheet("background-color:transparent;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(1)

        header_btns = [
            ("编号", self.on_number_header_btn_click),
            ("文件名", self.on_filename_header_btn_click),
            ("工时(时:分:秒:毫秒)", self.on_worktime_header_btn_click),
            ("件数", self.on_quantity_header_btn_click)
        ]
        for btn_text, btn_callback in header_btns:
            btn = QPushButton(btn_text)
            btn.setStyleSheet("""
                                QPushButton {
                                    border: 1px solid #d0d0d0;
                                    border-radius: 4px;
                                    background-color: #f0f0f0;
                                    font-weight: bold;
                                    font-size: 12px;
                                    text-align: center;
                                    padding: 8px 0;
                                    margin: 0;
                                }
                                QPushButton:hover {
                                    background-color: #e0e0e0;
                                    border-color: #b0b0b0;
                                }
                                QPushButton:pressed {
                                    background-color: #d0d0d0;
                                    border-color: #909090;
                                }
                            """)
            btn.clicked.connect(btn_callback)
            header_layout.addWidget(btn, 1)

        layer_table = QTableWidget()
        layer_table.setColumnCount(4)
        layer_table.setRowCount(19)
        layer_table.setMinimumHeight(240)
        layer_table.verticalHeader().setVisible(False)
        layer_table.verticalHeader().setDefaultSectionSize(12)
        layer_table.horizontalHeader().setDefaultSectionSize(135)
        layer_table.horizontalHeader().setVisible(False)
        layer_table.horizontalHeader().setStretchLastSection(True)
        layer_table.setStyleSheet("""
                            QTableWidget {
                                border: 1px solid #d0d0d0;
                                border-radius: 4px;
                                background-color: #ffffff;
                                gridline-color: #d0d0d0;
                            }
                            QTableWidget::item {
                                padding: 4px;
                                border: none;
                            }
                            QTableWidget::item:selected {
                                background-color: #e8f0fe;
                                color: #000;
                            }
                        """)

        table_layout.addWidget(header_widget)
        table_layout.addWidget(layer_table)
        layout.addWidget(table_widget)

        btn_group = QWidget()
        btn_layout = QVBoxLayout(btn_group)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row1.addWidget(QPushButton("读取"))
        row1.addWidget(QPushButton("加工"))
        row1.addWidget(QPushButton("加载"))
        btn_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addWidget(QPushButton("删除"))
        row2.addWidget(QPushButton("全部删除"))
        row2.addWidget(QPushButton("上传"))
        btn_layout.addLayout(row2)

        row3 = QHBoxLayout()
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
        widget = QWidget()
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        param_widget = QWidget()
        param_layout = QVBoxLayout(param_widget)
        param_layout.setContentsMargins(0, 0, 0, 0)
        param_layout.setSpacing(8)

        param_type_layout = QHBoxLayout()
        param_type_layout.setSpacing(10)
        process_radio = QRadioButton("加工参数")
        process_radio.setChecked(True)
        assist_radio = QRadioButton("辅助参数")
        other_radio = QRadioButton("其他参数")
        param_type_layout.addWidget(process_radio)
        param_type_layout.addWidget(assist_radio)
        param_type_layout.addWidget(other_radio)
        param_type_layout.addStretch()
        param_layout.addLayout(param_type_layout)

        cut_group = QGroupBox("切割参数")
        cut_layout = QVBoxLayout(cut_group)
        cut_layout.setContentsMargins(10, 10, 10, 10)
        cut_layout.setSpacing(6)

        cut_rows = [
            ("空程速度(mm/s)", "200.000"),
            ("空程加速度(mm/s2)", "3000.000"),
            ("拐弯速度(mm/s)", "20.000"),
            ("拐弯加速度(mm/s2)", "400.000"),
            ("切割加速度(mm/s2)", "3000.000"),
            ("空走延时(ms)", "0.000"),
            ("切割加速倍率(0%~200%)", "100"),
            ("空程加速倍率(0%~200%)", "100"),
            ("拐弯系数(0%~200%)", "100"),
        ]
        for label_text, value in cut_rows:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(label_text), 1)
            edit = QLineEdit(value)
            edit.setAlignment(Qt.AlignRight)
            row_layout.addWidget(edit, 1)
            cut_layout.addLayout(row_layout)

        cut_layout.addWidget(QPushButton("一键设置"), 0, Qt.AlignRight)
        param_layout.addWidget(cut_group)

        scan_group = QGroupBox("扫描参数")
        scan_layout = QVBoxLayout(scan_group)
        scan_layout.setContentsMargins(10, 10, 10, 10)
        scan_layout.setSpacing(6)

        scan_rows = [
            ("x轴起始速度(mm/s)", "10.000"),
            ("y轴起始速度(mm/s)", "10.000"),
            ("x轴加速度(mm/s2)", "10000.000"),
            ("y轴加速度(mm/s2)", "3000.000"),
            ("扫描行速度(mm/s)", "100.000"),
            ("扫描模式", "一般模式"),
            ("光斑大小(50~99%)(mm)", "80.000"),
            ("扫描系数", "100"),
        ]
        for label_text, value in scan_rows:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(label_text), 1)
            edit = QLineEdit(value)
            edit.setAlignment(Qt.AlignRight)
            row_layout.addWidget(edit, 1)
            scan_layout.addLayout(row_layout)
        param_layout.addWidget(scan_group)

        btn_widget = QWidget()
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)
        btn_layout.addWidget(QPushButton("打开"))
        btn_layout.addWidget(QPushButton("保存"))
        btn_layout.addWidget(QPushButton("读参数"))
        btn_layout.addWidget(QPushButton("写参数"))
        btn_layout.addStretch()

        main_layout.addWidget(param_widget, 3)
        main_layout.addWidget(btn_widget, 1)

        return widget

    def create_test_tab(self):
        """创建测试标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        coord_group = QGroupBox("坐标控制")
        coord_layout = QVBoxLayout(coord_group)
        coord_layout.setContentsMargins(10, 10, 10, 10)
        coord_layout.setSpacing(6)

        coord_display_layout = QHBoxLayout()
        coord_display_layout.addWidget(QLabel("X=?"))
        coord_display_layout.addWidget(QLabel("Y=?"))
        coord_display_layout.addWidget(QLabel("Z=?"))
        coord_display_layout.addStretch()
        coord_display_layout.addWidget(QPushButton("读当前位置"))
        coord_layout.addLayout(coord_display_layout)

        target_layout = QHBoxLayout()
        x_target = QLineEdit("0.000")
        y_target = QLineEdit("0.000")
        target_layout.addWidget(x_target)
        target_layout.addWidget(y_target)
        target_layout.addWidget(QPushButton("移动到目标位置"))
        coord_layout.addLayout(target_layout)

        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("0时:0分:0秒:0毫秒"))
        time_layout.addStretch()
        time_layout.addWidget(QPushButton("前次加工时间"))
        coord_layout.addLayout(time_layout)
        layout.addWidget(coord_group)

        axis_group = QGroupBox("单轴移动")
        axis_layout = QVBoxLayout(axis_group)
        axis_layout.setContentsMargins(10, 10, 10, 10)
        axis_layout.setSpacing(6)

        xy_layout = QHBoxLayout()
        xy_button_layout = QVBoxLayout()
        xy_button_layout.addWidget(QPushButton("Y+"))
        xy_mid_layout = QHBoxLayout()
        xy_mid_layout.addWidget(QPushButton("X-"))
        xy_mid_layout.addWidget(QPushButton("原点"))
        xy_mid_layout.addWidget(QPushButton("X+"))
        xy_button_layout.addLayout(xy_mid_layout)
        xy_button_layout.addWidget(QPushButton("Y-"))
        xy_layout.addLayout(xy_button_layout)

        param_layout = QVBoxLayout()
        param_layout.addWidget(QLabel("偏移(mm):"))
        offset_edit = QLineEdit("10.000")
        param_layout.addWidget(offset_edit)
        param_layout.addWidget(QLabel("速度(mm/s):"))
        speed_edit = QLineEdit("50")
        param_layout.addWidget(speed_edit)
        param_layout.addWidget(QLabel("激光功率(%):"))
        power_edit = QLineEdit("0")
        param_layout.addWidget(power_edit)
        xy_layout.addLayout(param_layout)
        axis_layout.addLayout(xy_layout)

        lower_layout = QHBoxLayout()
        zu_button_layout = QVBoxLayout()
        zu_button_layout.addWidget(QPushButton("Z+"))
        zu_mid_layout = QHBoxLayout()
        zu_mid_layout.addWidget(QPushButton("原点"))
        zu_mid_layout.addWidget(QPushButton("Z-"))
        zu_button_layout.addLayout(zu_mid_layout)
        zu_button_layout.addWidget(QPushButton("U+"))
        zu_mid2_layout = QHBoxLayout()
        zu_mid2_layout.addWidget(QPushButton("原点"))
        zu_mid2_layout.addWidget(QPushButton("U-"))
        zu_button_layout.addLayout(zu_mid2_layout)
        lower_layout.addLayout(zu_button_layout)

        check_layout = QVBoxLayout()
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
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        btn_layout = QHBoxLayout()
        move_btn = QPushButton()
        move_btn.setIcon(QIcon.fromTheme("transform-move"))
        move_btn.setIconSize(QSize(32, 32))
        rotate_btn = QPushButton()
        rotate_btn.setIcon(QIcon.fromTheme("transform-rotate"))
        rotate_btn.setIconSize(QSize(32, 32))
        mirror_btn = QPushButton()
        mirror_btn.setIcon(QIcon.fromTheme("transform-mirror"))
        mirror_btn.setIconSize(QSize(32, 32))
        scale_btn = QPushButton()
        scale_btn.setIcon(QIcon.fromTheme("transform-scale"))
        scale_btn.setIconSize(QSize(32, 32))
        skew_btn = QPushButton()
        skew_btn.setIcon(QIcon.fromTheme("transform-skew"))
        skew_btn.setIconSize(QSize(32, 32))

        btn_layout.addWidget(move_btn)
        btn_layout.addWidget(rotate_btn)
        btn_layout.addWidget(mirror_btn)
        btn_layout.addWidget(scale_btn)
        btn_layout.addWidget(skew_btn)
        layout.addLayout(btn_layout)

        pos_group = QGroupBox("位置:")
        pos_layout = QVBoxLayout(pos_group)
        pos_layout.setContentsMargins(10, 10, 10, 10)
        pos_layout.setSpacing(6)

        hor_layout = QHBoxLayout()
        hor_layout.addWidget(QLabel("水平(H)"))
        hor_edit = QLineEdit("0")
        hor_edit.setPlaceholderText("mm")
        hor_layout.addWidget(hor_edit)
        pos_layout.addLayout(hor_layout)

        ver_layout = QHBoxLayout()
        ver_layout.addWidget(QLabel("垂直(V)"))
        ver_edit = QLineEdit("0")
        ver_edit.setPlaceholderText("mm")
        ver_layout.addWidget(ver_edit)
        pos_layout.addLayout(ver_layout)
        layout.addWidget(pos_group)

        apply_layout = QVBoxLayout()
        apply_layout.addWidget(QCheckBox("相对位置"))
        dir_check_layout = QHBoxLayout()
        dir_check_layout.addStretch()
        dir_checks = [
            QCheckBox(""), QCheckBox(""), QCheckBox(""),
            QCheckBox(""), QCheckBox(""), QCheckBox(""),
            QCheckBox(""), QCheckBox(""), QCheckBox("")
        ]
        grid = QGridLayout()
        for i in range(3):
            for j in range(3):
                grid.addWidget(dir_checks[i * 3 + j], i, j)
        dir_check_layout.addLayout(grid)
        dir_check_layout.addStretch()
        apply_layout.addLayout(dir_check_layout)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(QPushButton("应用到复制"))
        btn_row.addWidget(QPushButton("应用"))
        btn_row.addStretch()
        apply_layout.addLayout(btn_row)
        layout.addLayout(apply_layout)

        return widget

