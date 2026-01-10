#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点编辑辅助工具栏
点击"节点编辑"工具后在左侧工具栏右边显示
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QToolButton, QButtonGroup
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon


class NodeEditToolbar(QWidget):
    """节点编辑辅助工具栏"""

    # 定义工具信号
    actionTriggered = pyqtSignal(str)

    # 动作常量
    ACTION_ADD_NODE = "add_node"
    ACTION_DELETE_NODE = "delete_node"
    ACTION_CONNECT_NODES = "connect_nodes"
    ACTION_BREAK_CURVE = "break_curve"
    ACTION_TO_LINE = "to_line"
    ACTION_TO_CURVE = "to_curve"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5) # 极窄边距
        layout.setSpacing(2)
        
        # 动作列表
        tools = [
            ("➕", "在指定位置添加节点", "left_sidebar_icons/sidebar_icon2-1.png", self.ACTION_ADD_NODE),
            ("➖", "删除选中的节点", "left_sidebar_icons/sidebar_icon2-2.png", self.ACTION_DELETE_NODE),
            ("🔗", "连接两选中的节点", "left_sidebar_icons/sidebar_icon2-3.png", self.ACTION_CONNECT_NODES),
            ("✂", "在选中的节点位置分割曲线", "left_sidebar_icons/sidebar_icon2-4.png", self.ACTION_BREAK_CURVE),
            ("📏", "将当前选中的曲线段转化为直线", "left_sidebar_icons/sidebar_icon2-5.png", self.ACTION_TO_LINE),
            ("〰", "将当前选中的直线段转化为曲线", "left_sidebar_icons/sidebar_icon2-6.png", self.ACTION_TO_CURVE),
        ]

        for icon_text, tooltip, icon_path, action_id in tools:
            btn = self.create_tool_button(icon_text, tooltip, icon_path, action_id)
            layout.addWidget(btn)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置固定宽度 - 比主工具栏更窄
        self.setFixedWidth(30)
        
        # 样式 - 稍微深一点的背景以示区分，或者保持一致
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-right: 1px solid #d0d0d0;
            }
        """)
        
    def create_tool_button(self, text, tooltip, icon_path, action_id):
        """创建工具按钮"""
        btn = QToolButton()
        # 暂时不设置tooltip，或者使用更短的tips，因为太窄可能挡住视线
        btn.setToolTip(tooltip) 
        btn.setFixedSize(28, 28)
        btn.setProperty("action_id", action_id)

        # 尝试加载图标，如果失败则使用文本
        icon = QIcon(icon_path)
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QSize(20, 20)) # 更小的图标
        else:
            btn.setText(text)
            print(f"Loading icon failed: {icon_path}")

        btn.clicked.connect(lambda: self.on_button_clicked(action_id))

        btn.setStyleSheet("""
            QToolButton {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
                border-radius: 2px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: #e6f2ff;
                border: 1px solid #4da6ff;
            }
            QToolButton:pressed {
                background-color: #cce6ff;
                border: 1px solid #0080ff;
            }
        """)
        return btn

    def on_button_clicked(self, action_id):
        """工具按钮点击事件"""
        self.actionTriggered.emit(action_id)
