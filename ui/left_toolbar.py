#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
左侧垂直工具栏
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QToolButton, QButtonGroup
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon


class LeftToolbar(QWidget):
    """左侧垂直工具栏"""
    
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
        
        # 工具列表 - 使用 left_sidebar_icons 中的图标
        tools = [
            ("↖", "选择工具", "left_sidebar_icons/sidebar_icon1.png"),
            ("✏", "画笔工具", "left_sidebar_icons/sidebar_icon2.png"),
            ("▭", "矩形工具", "left_sidebar_icons/sidebar_icon3.png"),
            ("○", "圆形工具", "left_sidebar_icons/sidebar_icon4.png"),
            ("⬢", "多边形工具", "left_sidebar_icons/sidebar_icon5.png"),
            ("▲", "三角形", "left_sidebar_icons/sidebar_icon6.png"),
            ("◀", "箭头", "left_sidebar_icons/sidebar_icon7.png"),
            ("☰", "直线", "left_sidebar_icons/sidebar_icon8.png"),
            ("≋", "波浪线", "left_sidebar_icons/sidebar_icon9.png"),
            ("⊞", "网格", "left_sidebar_icons/sidebar_icon10.png"),
            ("✂", "剪切", "left_sidebar_icons/sidebar_icon11.png"),
            ("◐", "扇形", "left_sidebar_icons/sidebar_icon12.png"),
            ("✱", "星形", "left_sidebar_icons/sidebar_icon13.png"),
            ("T", "文字工具", "left_sidebar_icons/sidebar_icon14.png"),
        ]

        for icon_text, tooltip, icon_path in tools:
            btn = self.create_tool_button(icon_text, tooltip, icon_path)
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
        
    def create_tool_button(self, text, tooltip, icon_path=None):
        """创建工具按钮"""
        btn = QToolButton()
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(44, 44)

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

