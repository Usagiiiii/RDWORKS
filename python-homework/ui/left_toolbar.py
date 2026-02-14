#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
左侧垂直工具栏
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QToolButton, QButtonGroup
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon
from utils.language_manager import language_manager
from utils.tool_utils import get_resource_path

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
        
        # 工具列表: key, icon_text, default_tooltip, icon_path, tool_id
        tools = [
            ("Tool_Select", "↖", "图形选取", get_resource_path("left_sidebar_icons/sidebar_icon1.png"), self.TOOL_SELECT),
            ("Tool_NodeEdit", "✏", "节点编辑", get_resource_path("left_sidebar_icons/sidebar_icon2.png"), self.TOOL_NODE_EDIT),
            ("Tool_Line", "▭", "直线", get_resource_path("left_sidebar_icons/sidebar_icon3.png"), self.TOOL_LINE),
            ("Tool_Polyline", "○", "折线", get_resource_path("left_sidebar_icons/sidebar_icon4.png"), self.TOOL_POLYLINE),
            ("Tool_Curve", "⬢", "曲线", get_resource_path("left_sidebar_icons/sidebar_icon5.png"), self.TOOL_CURVE),
            ("Tool_Rectangle", "▲", "矩形", get_resource_path("left_sidebar_icons/sidebar_icon6.png"), self.TOOL_RECTANGLE),
            ("Tool_Ellipse", "◀", "椭圆", get_resource_path("left_sidebar_icons/sidebar_icon7.png"), self.TOOL_ELLIPSE),
            ("Tool_Text", "☰", "文字", get_resource_path("left_sidebar_icons/sidebar_icon8.png"), self.TOOL_TEXT),
            ("Tool_Point", "≋", "点", get_resource_path("left_sidebar_icons/sidebar_icon9.png"), self.TOOL_POINT),
            ("Tool_Grid", "⊞", "生成网络", get_resource_path("left_sidebar_icons/sidebar_icon10.png"), self.TOOL_GRID),
            ("Tool_Delete", "✂", "删除", get_resource_path("left_sidebar_icons/sidebar_icon11.png"), self.TOOL_DELETE),
            ("Tool_HMirror", "◐", "水平镜像", get_resource_path("left_sidebar_icons/sidebar_icon12.png"), self.TOOL_H_MIRROR),
            ("Tool_VMirror", "✱", "垂直镜像", get_resource_path("left_sidebar_icons/sidebar_icon13.png"), self.TOOL_V_MIRROR),
            ("Tool_Dock", "T", "图形停靠", get_resource_path("left_sidebar_icons/sidebar_icon14.png"), self.TOOL_DOCK),
            ("Tool_Array", "", "阵列复制", get_resource_path("left_sidebar_icons/sidebar_icon15.png"), self.TOOL_ARRAY),
        ]
        
        # 保存所有按钮引用以便后续更新
        self.tool_buttons = []

        for tr_key, icon_text, default_tooltip, icon_path, tool_id in tools:
            btn = self.create_tool_button(icon_text, default_tooltip, icon_path, tool_id)
            btn.setProperty('tr_key', tr_key)
            btn.setProperty('default_tooltip', default_tooltip)
            
            layout.addWidget(btn)
            self.button_group.addButton(btn)
            self.tool_buttons.append(btn)
        
        # 第一个按钮默认选中
        if self.button_group.buttons():
            self.button_group.buttons()[0].setChecked(True)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置固定宽度
        self.setFixedWidth(36)  # 减小宽度
        
        # 样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-right: 1px solid #d0d0d0;
            }
        """)

        # 初始翻译
        self.retranslate_ui()
        
    def retranslate_ui(self):
        """更新界面语言"""
        for btn in self.tool_buttons:
            tr_key = btn.property('tr_key')
            default_tooltip = btn.property('default_tooltip')
            tooltip = language_manager.tr('LeftToolbar', tr_key, default_tooltip)
            btn.setToolTip(tooltip)

    def create_tool_button(self, text, tooltip, icon_path=None, tool_id=None):
        """创建工具按钮"""
        btn = QToolButton()
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(32, 32)  # 减小按钮尺寸
        btn.setProperty("tool_id", tool_id)  # 存储工具ID

        # 尝试加载图标，如果失败则使用文本
        if icon_path:
            icon = QIcon(icon_path)
            if not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QSize(24, 24))  # 减小图标尺寸
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

    def select_tool(self, tool_id):
        """手动选中指定工具（并触发所有相关逻辑）"""
        for btn in self.button_group.buttons():
            if btn.property("tool_id") == tool_id:
                btn.setChecked(True)
                self.toolChanged.emit(tool_id)
                break

    def update_selection_dependent_tools(self, has_selection):
        """更新依赖选择的工具按钮状态"""
        dependent_tools = [
            self.TOOL_H_MIRROR,
            self.TOOL_V_MIRROR,
            self.TOOL_DOCK,
            self.TOOL_ARRAY,
            self.TOOL_DELETE  # 删除工具通常也依赖选择（虽然有点选模式，但为了符合用户“只有选取了对象那四个工具才变成可点击”的描述，可能用户指的是最下面那几个。不过用户明确说是“最下面的四个”。）
        ]
        # 用户指明是“最下面的四个”，即 11, 12, 13, 14。DELETE 是 10，在它们上面。
        # 所以只处理 11, 12, 13, 14
        target_tools = [self.TOOL_H_MIRROR, self.TOOL_V_MIRROR, self.TOOL_DOCK, self.TOOL_ARRAY]

        for btn in self.tool_buttons:
            tid = btn.property("tool_id")
            if tid in target_tools:
                btn.setEnabled(has_selection)
                # 如果当前禁用的工具是被选中的，则切回选择工具
                if not has_selection and btn.isChecked():
                     if self.button_group.buttons():
                         self.button_group.buttons()[0].click()

