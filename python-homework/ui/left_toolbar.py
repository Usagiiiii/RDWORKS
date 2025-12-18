#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
左侧垂直工具栏
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QToolButton, QButtonGroup
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon


class LeftToolbar(QWidget):
    """左侧垂直工具栏"""

    # 定义工具信号
    toolChanged = pyqtSignal(int)

    # 工具ID常量（与WhiteboardWidget中的工具常量对应）
    TOOL_SELECT = 0
    TOOL_NODE_EDIT = 1
    TOOL_LINE = 2
    TOOL_POLYLINE = 3
    TOOL_CURVE = 4
    TOOL_RECTANGLE = 5
    TOOL_ELLIPSE = 6
    TOOL_TEXT = 7
    TOOL_POINT = 8
    TOOL_GRID = 9
    TOOL_DELETE = 10
    TOOL_H_MIRROR = 11
    TOOL_V_MIRROR = 12
    TOOL_DOCK = 13
    TOOL_ARRAY = 14
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 5, 2, 5)
        layout.setSpacing(2)

        # 按钮组（互斥选择）
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.buttonClicked.connect(self.on_tool_button_clicked)
        
        # 工具列表 - 使用 left_sidebar_icons 中的图标
        tools = [
            ("↖", "图形选取", "left_sidebar_icons/sidebar_icon1.png", self.TOOL_SELECT),
            ("✏", "节点编辑", "left_sidebar_icons/sidebar_icon2.png", self.TOOL_NODE_EDIT),
            ("▭", "直线", "left_sidebar_icons/sidebar_icon3.png", self.TOOL_LINE),
            ("○", "折线", "left_sidebar_icons/sidebar_icon4.png", self.TOOL_POLYLINE),
            ("⬢", "曲线", "left_sidebar_icons/sidebar_icon5.png", self.TOOL_CURVE),
            ("▲", "矩形", "left_sidebar_icons/sidebar_icon6.png", self.TOOL_RECTANGLE),
            ("◀", "椭圆", "left_sidebar_icons/sidebar_icon7.png", self.TOOL_ELLIPSE),
            ("☰", "文字", "left_sidebar_icons/sidebar_icon8.png", self.TOOL_TEXT),
            ("≋", "点", "left_sidebar_icons/sidebar_icon9.png", self.TOOL_POINT),
            ("⊞", "生成网络", "left_sidebar_icons/sidebar_icon10.png", self.TOOL_GRID),
            ("✂", "删除", "left_sidebar_icons/sidebar_icon11.png", self.TOOL_DELETE),
            ("◐", "水平镜像", "left_sidebar_icons/sidebar_icon12.png", self.TOOL_H_MIRROR),
            ("✱", "垂直镜像", "left_sidebar_icons/sidebar_icon13.png", self.TOOL_V_MIRROR),
            ("T", "图形停靠", "left_sidebar_icons/sidebar_icon14.png", self.TOOL_DOCK),
            ("", "阵列复制", "left_sidebar_icons/sidebar_icon15.png", self.TOOL_ARRAY),
        ]

        # 修改这里：解包所有4个元素
        for icon_text, tooltip, icon_path, tool_id in tools:  # 解包4个变量
            btn = self.create_tool_button(icon_text, tooltip, icon_path, tool_id)  # 传递tool_id
            layout.addWidget(btn)
            self.button_group.addButton(btn)
        
        # 第一个按钮默认选中
        if self.button_group.buttons():
            self.button_group.buttons()[0].setChecked(True)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置固定宽度
        self.setFixedWidth(50)
        
        # 样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-right: 1px solid #d0d0d0;
            }
        """)
        
    def create_tool_button(self, text, tooltip, icon_path=None, tool_id=None):
        """创建工具按钮"""
        btn = QToolButton()
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(44, 44)
        btn.setProperty("tool_id", tool_id)  # 存储工具ID

        # 尝试加载图标，如果失败则使用文本
        if icon_path:
            icon = QIcon(icon_path)
            if not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QSize(36, 36))
            else:
                btn.setText(text)
        else:
            btn.setText(text)

        btn.setStyleSheet("""
            QToolButton {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                font-size: 16px;
            }
            QToolButton:hover {
                background-color: #e6f2ff;
                border: 1px solid #4da6ff;
            }
            QToolButton:checked {
                background-color: #cce6ff;
                border: 2px solid #0080ff;
            }
        """)
        return btn

    def on_tool_button_clicked(self, button):
        """工具按钮点击事件"""
        tool_id = button.property("tool_id")
        if tool_id is not None:
            self.toolChanged.emit(tool_id)

