#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件
可以在这里修改应用程序的默认设置
"""


# 窗口设置

# 窗口标题
WINDOW_TITLE = '切割项目'

# 窗口初始位置和大小 (x, y, width, height)
WINDOW_GEOMETRY = (100, 100, 1400, 900)

# 窗口最小尺寸 (width, height)
WINDOW_MIN_SIZE = (800, 600)

# 画布设置

# 画布尺寸 (width, height) - 单位：像素
# 注意：过大的画布会影响性能
CANVAS_SIZE = (3000, 2000)

# 画布背景色 (R, G, B) - 范围：0-255
CANVAS_BG_COLOR = (255, 255, 255)  # 白色

# 绘图工具默认设置

# 默认画笔颜色 (R, G, B)
DEFAULT_PEN_COLOR = (0, 0, 0)  # 黑色

# 默认画笔宽度 - 单位：像素
DEFAULT_PEN_WIDTH = 2

# 橡皮擦宽度倍数（相对于画笔宽度）
ERASER_WIDTH_MULTIPLIER = 3

# 画笔宽度范围 (min, max)
PEN_WIDTH_RANGE = (1, 50)

# 预设颜色

# 工具箱中显示的预设颜色 (R, G, B)
PRESET_COLORS = [
    (0, 0, 0),         # 黑色
    (255, 0, 0),       # 红色
    (0, 255, 0),       # 绿色
    (0, 0, 255),       # 蓝色
    (255, 255, 0),     # 黄色
    (255, 0, 255),     # 品红
    (0, 255, 255),     # 青色
    (255, 128, 0),     # 橙色
    (128, 0, 128),     # 紫色
    (128, 128, 128),   # 灰色
]

# 每行显示的颜色数量
COLORS_PER_ROW = 5

# 缩放设置

# 缩放范围 (min, max)
ZOOM_RANGE = (0.1, 10.0)  # 10% - 1000%

# 滚轮缩放步长（乘数）
ZOOM_STEP = 1.1  # 每次滚动放大/缩小 10%

# 菜单栏缩放步长（乘数）
ZOOM_MENU_STEP = 1.2  # 每次放大/缩小 20%

# 标尺设置

# 标尺尺寸 - 单位：像素
RULER_SIZE = 30

# 标尺背景色 (R, G, B)
RULER_BG_COLOR = (240, 240, 240)

# 标尺文字颜色 (R, G, B)
RULER_TEXT_COLOR = (80, 80, 80)

# 标尺字体大小
RULER_FONT_SIZE = 8

# 标尺基础间隔（未缩放时）- 单位：像素
RULER_BASE_INTERVAL = 50

# 标尺次刻度分段数
RULER_SUB_DIVISIONS = 5

# 历史记录设置

# 最大撤销/重做步数
MAX_HISTORY = 50

# 界面样式设置

# 应用程序样式（可选：'Fusion', 'Windows', 'WindowsVista', 'Macintosh'）
APP_STYLE = 'Fusion'

# 主题色
THEME_COLORS = {
    'window_bg': (240, 240, 240),      # 窗口背景
    'text': (50, 50, 50),              # 文字颜色
    'border': (204, 204, 204),         # 边框颜色
    'button_hover': (230, 242, 255),   # 按钮悬停
    'button_active': (204, 230, 255),  # 按钮激活
    'accent': (0, 128, 255),           # 强调色
}

# 工具栏图标尺寸
TOOLBAR_ICON_SIZE = (32, 32)

# 工具按钮最小高度
TOOL_BUTTON_HEIGHT = 40

# 颜色按钮尺寸
COLOR_BUTTON_SIZE = (30, 30)

# 操作按钮最小高度
ACTION_BUTTON_HEIGHT = 35

# 工具箱设置

# 工具箱默认宽度
TOOLBOX_WIDTH = 200

# 工具箱边距
TOOLBOX_MARGIN = 10

# 工具箱间距
TOOLBOX_SPACING = 10

# 文件设置

# 默认文件格式
DEFAULT_FILE_FORMAT = 'wbd'  # 白板文件

# 默认导出格式
DEFAULT_EXPORT_FORMAT = 'png'

# 支持的图像格式
SUPPORTED_IMAGE_FORMATS = ['png', 'jpg', 'jpeg', 'bmp', 'gif']

# 性能设置

# 启用抗锯齿（更流畅但稍慢）
ENABLE_ANTIALIASING = True

# 启用高质量渲染（更清晰但更慢）
ENABLE_HIGH_QUALITY_RENDERING = True

# 调试设置

# 显示调试信息
DEBUG_MODE = False

# 显示FPS（每秒帧数）
SHOW_FPS = False

# 显示鼠标坐标
SHOW_MOUSE_COORDS = False

# 快捷键设置

# 自定义快捷键（格式：'Ctrl+Key', 'Alt+Key', 'Shift+Key'）
SHORTCUTS = {
    'new': 'Ctrl+N',
    'open': 'Ctrl+O',
    'save': 'Ctrl+S',
    'save_as': 'Ctrl+Shift+S',
    'export': 'Ctrl+E',
    'undo': 'Ctrl+Z',
    'redo': 'Ctrl+Y',
    'cut': 'Ctrl+X',
    'copy': 'Ctrl+C',
    'paste': 'Ctrl+V',
    'delete': 'Delete',
    'select_all': 'Ctrl+A',
    'zoom_in': 'Ctrl++',
    'zoom_out': 'Ctrl+-',
    'zoom_reset': 'Ctrl+0',
    'fullscreen': 'F11',
    'quit': 'Ctrl+Q',
}

# 实验性功能

# 启用图层系统（未实现）
ENABLE_LAYERS = False

# 启用选择工具（未实现）
ENABLE_SELECTION = False

# 启用文字工具（未实现）
ENABLE_TEXT_TOOL = False

