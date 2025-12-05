#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧属性面板
"""
import os

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                             QRadioButton, QGridLayout, QStackedWidget)
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPixmap


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
        # 新增：历史面板（列出撤销/重做历史）
        self.tabs.addTab(self.create_history_tab(), "历史")

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
        """底部的区域（调整后：组件缩小、间距压缩，为上方腾位置）"""
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(6)  # 缩小布局间距

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
        pause_btn = QPushButton("暂停/继续")
        pause_btn.setStyleSheet("background-color: #FF9800; color: white; font-size: 15px;")
        pause_btn.setMinimumHeight(28)
        stop_btn = QPushButton("停止")
        stop_btn.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; font-size: 15px;")
        stop_btn.setMinimumHeight(28)
        control_btn_layout.addWidget(start_btn, 1)
        control_btn_layout.addWidget(pause_btn, 1)
        control_btn_layout.addWidget(stop_btn, 1)
        process_layout.addLayout(control_btn_layout)

        # 文件操作按钮：缩小高度、调整字体
        file_btn1 = QPushButton("保存为版位文件")
        file_btn1.setStyleSheet("font-size: 15px;")
        file_btn1.setMinimumHeight(26)  # 缩小按钮高度
        process_layout.addWidget(file_btn1)

        file_btn2 = QPushButton("载机文件输出")
        file_btn2.setStyleSheet("font-size: 15px;")
        file_btn2.setMinimumHeight(26)
        process_layout.addWidget(file_btn2)

        file_btn3 = QPushButton("下载")
        file_btn3.setStyleSheet("font-size: 15px;")
        file_btn3.setMinimumHeight(26)
        process_layout.addWidget(file_btn3)

        # 图形定位行：缩小组件尺寸
        pos_layout = QHBoxLayout()
        pos_layout.setSpacing(3)
        pos_layout.addWidget(QLabel("图形定位:"), 0)
        pos_combo = QComboBox()
        pos_combo.addItems(["当前位置", "左上角", "中心"])
        pos_combo.setStyleSheet("font-size: 12px;")
        pos_combo.setMinimumHeight(24)  # 缩小下拉框高度
        pos_layout.addWidget(pos_combo, 1)
        process_layout.addLayout(pos_layout)

        # 确定优化复选框：缩小尺寸
        optimize_check = QCheckBox("确定优化")
        optimize_check.setStyleSheet("font-size: 15px;")
        optimize_check.setMinimumHeight(22)
        optimize_check.setChecked(True)
        process_layout.addWidget(optimize_check)

        # 其他操作按钮：缩小高度、调整字体
        other_layout = QHBoxLayout()
        other_layout.setSpacing(2)
        other_layout.addWidget(QPushButton("切换坐标"), 1)
        other_layout.addWidget(QPushButton("走边"), 1)
        for btn in other_layout.findChildren(QPushButton):
            btn.setStyleSheet("font-size: 15px;")
            btn.setMinimumHeight(26)
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
        """创建加工标签页（调整后：激光1/2为独立按钮，行列设置固定显示）"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setSpacing(0)

        # 表头按钮区域（保持原逻辑）
        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: transparent;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(1)

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

        # 图层表格（保持原逻辑）
        layer_table = QTableWidget()
        layer_table.setColumnCount(4)
        layer_table.setRowCount(7)
        layer_table.setMinimumHeight(80)
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

        # 参数设置组（保持原逻辑）
        param_group = QGroupBox("")
        param_layout = QVBoxLayout()
        param_layout.setContentsMargins(5, 0, 5, 5)
        param_layout.setSpacing(3)

        color_row = QHBoxLayout()
        color_row.setSpacing(5)
        color_row.addWidget(QLabel("颜色"), 0)
        color_btn = QPushButton()
        color_btn.setFixedSize(100, 25)
        color_btn.setStyleSheet("background-color: black; border: 1px solid #888;")
        color_row.addWidget(color_btn, 1)
        param_layout.addLayout(color_row)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(5)
        speed_row.addWidget(QLabel("速度(mm/s)"), 0)
        speed_spin = QDoubleSpinBox()
        speed_spin.setRange(0, 1000)
        speed_spin.setValue(100.0)
        speed_spin.setMinimumWidth(100)
        speed_row.addWidget(speed_spin, 1)
        param_layout.addLayout(speed_row)

        priority_row = QHBoxLayout()
        priority_row.setSpacing(5)
        priority_row.addWidget(QLabel("优先级"), 0)
        priority_spin = QSpinBox()
        priority_spin.setRange(1, 10)
        priority_spin.setValue(1)
        priority_spin.setMinimumWidth(100)
        priority_row.addWidget(priority_spin, 1)
        param_layout.addLayout(priority_row)

        min_power_row = QHBoxLayout()
        min_power_row.setSpacing(5)
        min_power_row.addWidget(QLabel("最小功率(%)"), 0)
        min_power_spin = QDoubleSpinBox()
        min_power_spin.setRange(0, 100)
        min_power_spin.setValue(30.0)
        min_power_spin.setMinimumWidth(100)
        min_power_row.addWidget(min_power_spin, 1)
        param_layout.addLayout(min_power_row)

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

        # ========== 激光1/2 独立按钮 + 固定行列设置 ==========
        laser_btn_layout = QHBoxLayout()  # 激光按钮的水平布局
        laser_btn_layout.setContentsMargins(0,3,0,3)
        laser1_btn = QPushButton("激光1")
        laser1_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8;
                border: 1px solid #d0d0d0;
                width: 35px;     
                height: 1px;   
                padding: 1px 8px;
                font-size: 14px;
                text-align: center
            }
            QPushButton:checked {
                background-color: #ffffff;
                border-bottom: 2px solid #0078d7;
            }
        """)
        laser1_btn.setCheckable(True)
        laser1_btn.setChecked(True)
        laser1_btn.clicked.connect(lambda: self.on_laser_btn_click(1))

        laser2_btn = QPushButton("激光2")
        laser2_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8;
                border: 1px solid #d0d0d0;
                width: 35px;     
                height: 1px;   
                padding: 1px 8px;
                font-size: 14px;
                text-align: center
            }
            QPushButton:checked {
                background-color: #ffffff;
                border-bottom: 2px solid #0078d7;
            }
        """)
        laser2_btn.setCheckable(True)
        laser2_btn.clicked.connect(lambda: self.on_laser_btn_click(2))

        laser_btn_layout.addWidget(laser1_btn)
        laser_btn_layout.addWidget(laser2_btn)
        laser_btn_layout.addStretch()  # 让按钮靠左显示
        top_layout.addLayout(laser_btn_layout)

        # 行列设置
        grid_group = QGroupBox("行列设置")
        grid_layout = QVBoxLayout()
        grid_layout.setContentsMargins(5, 5, 5, 5)
        grid_layout.setSpacing(4)

        # 行列设置表头
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
        x_count_edit = QLineEdit("1")
        x_count_edit.setMinimumWidth(50)
        x_row.addWidget(x_count_edit, 1)
        for _ in range(3):
            edit = QLineEdit("0.000")
            edit.setMinimumWidth(50)
            x_row.addWidget(edit, 1)
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
        y_count_edit = QLineEdit("1")
        y_count_edit.setMinimumWidth(50)
        y_row.addWidget(y_count_edit, 1)
        for _ in range(3):
            edit = QLineEdit("0.000")
            edit.setMinimumWidth(50)
            y_row.addWidget(edit, 1)
        y_checkbox_layout = QHBoxLayout()
        y_checkbox_layout.setSpacing(5)
        y_checkbox1 = QCheckBox("H")
        y_checkbox2 = QCheckBox("V")
        y_checkbox_layout.addWidget(y_checkbox1)
        y_checkbox_layout.addWidget(y_checkbox2)
        y_checkbox_layout.addStretch()
        y_row.addLayout(y_checkbox_layout, 1)
        grid_layout.addLayout(y_row)

        # 行列设置按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        icon_btn = QPushButton()
        icon_btn.setFixedSize(32, 32)
        icon_btn.setIcon(QIcon("grid_icon.png"))
        icon_btn.setIconSize(QSize(28, 28))
        icon_btn.setStyleSheet("border: 1px solid #888;")
        btn_row.addWidget(icon_btn, 0)
        btn_row.addWidget(QPushButton("虚拟阵列"), 1)
        btn_row.addWidget(QPushButton("布满"), 1)
        btn_row.addWidget(QPushButton("自动排版"), 1)
        more_btn = QPushButton("...")
        more_btn.setFixedWidth(30)
        btn_row.addWidget(more_btn, 0)
        grid_layout.addLayout(btn_row)

        grid_group.setLayout(grid_layout)
        top_layout.addWidget(grid_group)

        main_layout.addWidget(top_widget, 1)
        return widget

    # 激光按钮点击回调
    def on_laser_btn_click(self, laser_num):
        print(f"切换到激光{laser_num}")



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

        table_widget=QWidget()
        table_layout=QVBoxLayout(table_widget)
        table_layout.setSpacing(0)

        header_widget=QWidget()
        header_widget.setStyleSheet("background-color:transparent;")
        header_layout=QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0,0,0,0)
        header_layout.setSpacing(1)

        header_btns=[
            ("编号",self.on_number_header_btn_click),
            ("文件名",self.on_filename_header_btn_click),
            ("工时(时:分:秒:毫秒)",self.on_worktime_header_btn_click),
            ("件数",self.on_quantity_header_btn_click)
        ]
        for btn_text,btn_callback in header_btns:
            btn=QPushButton(btn_text)
            btn.setStyleSheet("""
                                QPushButton {
                                    border:1px solid #d0d0d0;
                                    border-radius:4px;
                                    background-color:#f0f0f0;
                                    font-weight:bold;
                                    font-size:12px;
                                    text-align:center;
                                    padding:8px 0;
                                    margin:0;
                                }
                                QPushButton:hover {
                                    background-color:#e0e0e0;
                                    border-color:#b0b0b0;
                                }
                                QPushButton:pressed {
                                    background-color:#d0d0d0;
                                    border-color:#909090;
                                }
                            """)
            btn.clicked.connect(btn_callback)
            header_layout.addWidget(btn,1)

        layer_table=QTableWidget()
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

        table_layout.addWidget(header_widget)
        table_layout.addWidget(layer_table)
        layout.addWidget(table_widget)

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
        hor_edit=QLineEdit("0")
        hor_edit.setFixedWidth(200)
        hor_edit.setFixedHeight(22)
        mm_label=QLabel("mm")
        hor_layout.addWidget(hor_label)
        hor_layout.addWidget(hor_edit)
        hor_layout.addWidget(mm_label)
        hor_layout.addStretch(0)
        pos_layout.addLayout(hor_layout)

        #垂直行
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