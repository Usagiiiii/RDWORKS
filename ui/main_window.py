#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口类
"""

from PyQt5.QtWidgets import (QMainWindow, QAction, QToolBar, QDockWidget,
                             QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
                             QLabel, QFileDialog, QMessageBox, QSplitter,
                             QToolButton, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QKeySequence, QColor, QPalette

from ui.whiteboard import WhiteboardWidget
from ui.left_toolbar import LeftToolbar
from ui.right_panel import RightPanel


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('激光加工控制系统')
        self.setGeometry(50, 50, 1600, 950)
        
        # 设置窗口样式
        self.setup_style()
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏（三行）
        self.create_toolbars()
        
        # 创建中心区域（左中右布局）
        self.create_central_widget()
        
        # 状态栏
        self.statusBar().showMessage('就绪')
        
    def setup_style(self):
        """设置应用程序样式"""
        # 设置调色板
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, QColor(50, 50, 50))
        self.setPalette(palette)
        
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件(F)')
        
        new_action = QAction('新建(&N)', self)
        new_action.setShortcut(QKeySequence.New)
        new_action.setStatusTip('创建新的白板')
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        
        open_action = QAction('打开(&O)...', self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.setStatusTip('打开现有文件')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction('保存(&S)', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip('保存当前文件')
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction('另存为(&A)...', self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.setStatusTip('另存为新文件')
        save_as_action.triggered.connect(self.save_as_file)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        export_action = QAction('导出图像(&E)...', self)
        export_action.setStatusTip('导出为图像文件')
        export_action.triggered.connect(self.export_image)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出(&X)', self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.setStatusTip('退出应用程序')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑(E)')
        
        undo_action = QAction('撤销(&U)', self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.setStatusTip('撤销上一步操作')
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction('重做(&R)', self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.setStatusTip('重做上一步操作')
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction('剪切(&T)', self)
        cut_action.setShortcut(QKeySequence.Cut)
        cut_action.setStatusTip('剪切选中内容')
        cut_action.triggered.connect(self.cut)
        edit_menu.addAction(cut_action)
        
        copy_action = QAction('复制(&C)', self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.setStatusTip('复制选中内容')
        copy_action.triggered.connect(self.copy)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction('粘贴(&P)', self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.setStatusTip('粘贴内容')
        paste_action.triggered.connect(self.paste)
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        delete_action = QAction('删除(&D)', self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.setStatusTip('删除选中内容')
        delete_action.triggered.connect(self.delete)
        edit_menu.addAction(delete_action)
        
        select_all_action = QAction('全选(&A)', self)
        select_all_action.setShortcut(QKeySequence.SelectAll)
        select_all_action.setStatusTip('选择全部内容')
        select_all_action.triggered.connect(self.select_all)
        edit_menu.addAction(select_all_action)
        
        # 视图菜单
        view_menu = menubar.addMenu('视图(D)')
        
        # 重命名为视图而不是View
        view_menu.setTitle('视图(D)')
        
        zoom_in_action = QAction('放大(&I)', self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.setStatusTip('放大视图')
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction('缩小(&O)', self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.setStatusTip('缩小视图')
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        zoom_reset_action = QAction('实际大小(&R)', self)
        zoom_reset_action.setShortcut('Ctrl+0')
        zoom_reset_action.setStatusTip('重置为100%')
        zoom_reset_action.triggered.connect(self.zoom_reset)
        view_menu.addAction(zoom_reset_action)
        
        view_menu.addSeparator()
        
        fullscreen_action = QAction('全屏(&F)', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.setStatusTip('切换全屏模式')
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # 设置菜单
        settings_menu = menubar.addMenu('设置(S)')
        settings_menu.addAction(QAction('参数设置', self))
        settings_menu.addAction(QAction('系统配置', self))
        
        # 处理菜单
        process_menu = menubar.addMenu('处理(W)')
        process_menu.addAction(QAction('开始加工', self))
        process_menu.addAction(QAction('停止加工', self))
        
        # 工具菜单
        tools_menu = menubar.addMenu('工具(T)')
        
        pen_action = QAction('画笔(&P)', self)
        pen_action.setStatusTip('选择画笔工具')
        pen_action.triggered.connect(self.select_pen)
        tools_menu.addAction(pen_action)
        
        eraser_action = QAction('橡皮擦(&E)', self)
        eraser_action.setStatusTip('选择橡皮擦工具')
        eraser_action.triggered.connect(self.select_eraser)
        tools_menu.addAction(eraser_action)
        
        line_action = QAction('直线(&L)', self)
        line_action.setStatusTip('绘制直线')
        line_action.triggered.connect(self.select_line)
        tools_menu.addAction(line_action)
        
        rectangle_action = QAction('矩形(&R)', self)
        rectangle_action.setStatusTip('绘制矩形')
        rectangle_action.triggered.connect(self.select_rectangle)
        tools_menu.addAction(rectangle_action)
        
        circle_action = QAction('圆形(&C)', self)
        circle_action.setStatusTip('绘制圆形')
        circle_action.triggered.connect(self.select_circle)
        tools_menu.addAction(circle_action)
        
        # 主配置菜单
        main_config_menu = menubar.addMenu('主配置(M)')
        main_config_menu.addAction(QAction('主要配置', self))
        
        # 查看菜单
        view2_menu = menubar.addMenu('查看(H)')
        view2_menu.addAction(QAction('查看选项', self))
        
        # 属性菜单
        prop_menu = menubar.addMenu('属性(H)')
        prop_menu.addAction(QAction('对象属性', self))
        
        # 社区菜单
        community_menu = menubar.addMenu('社区')
        community_menu.addAction(QAction('在线帮助', self))
        community_menu.addAction(QAction('用户论坛', self))
        
        about_action = QAction('关于', self)
        about_action.setStatusTip('关于本应用程序')
        about_action.triggered.connect(self.show_about)
        community_menu.addAction(about_action)
        
    def create_toolbars(self):
        """创建三行工具栏"""
        # 第一行工具栏 - toolbar_row1_icons 的所有图标
        toolbar1 = QToolBar('工具栏1')
        toolbar1.setIconSize(QSize(28, 28))
        toolbar1.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar1)

        # 左侧新建和打开按钮
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column1.png', '新建', self.new_file))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column2.png', '打开', self.open_file))
        toolbar1.addSeparator()

        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column3.png', '文件', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column4.png', '编辑', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column5.png', '查看', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column6.png', '插入', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column7.png', '格式', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column8.png', '排列', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column9.png', '文字', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column10.png', '绘制', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column11.png', '形状', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column12.png', '线条', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column13.png', '曲线', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column14.png', '填充', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column15.png', '选择', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column16.png', '缩放', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column17.png', '测量', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column18.png', '对齐', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column19.png', '工具', None))

        # 第二行工具栏 - toolbar_row2_icons 的所有19个图标
        toolbar2 = QToolBar('工具栏2')
        toolbar2.setIconSize(QSize(28, 28))
        toolbar2.setMovable(False)
        # 将第二行工具栏放到新的一行
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, toolbar2)

        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column1.png', '新建', self.new_file))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column2.png', '打开文件夹', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column3.png', '打开', self.open_file))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column4.png', '保存', self.save_file))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column5.png', '打印', None))
        toolbar2.addSeparator()

        # 视图操作
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column6.png', '显示', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column7.png', '隐藏', None))
        toolbar2.addSeparator()

        # 缩放工具
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column8.png', '放大', self.zoom_in))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column9.png', '缩小', self.zoom_out))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column10.png', '缩放', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column11.png', '适应窗口', self.zoom_reset))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column12.png', '全选', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column13.png', '框选', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column14.png', '查看', None))
        toolbar2.addSeparator()

        # 显示模式
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column15.png', '显示', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column16.png', '亮度', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column17.png', '设置', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column18.png', '模式1', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column19.png', '模式2', None))

        # 第三行工具栏 - 属性输入区域（堆叠布局）+ 图标工具 - toolbar_row3_icons
        toolbar3 = QToolBar('工具栏3')
        toolbar3.setIconSize(QSize(32, 32))  # 加大图标尺寸到32x32
        toolbar3.setMovable(False)
        toolbar3.setMinimumHeight(70)  # 增加工具栏高度到70
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, toolbar3)

        # 创建属性输入区域（使用网格布局确保对齐）
        from PyQt5.QtWidgets import QGridLayout

        properties_widget = QWidget()
        properties_widget.setMinimumHeight(65)  # 增加最小高度
        properties_widget.setMaximumHeight(65)  # 增加最大高度
        properties_widget.setMaximumWidth(450)  # 调整宽度
        properties_layout = QGridLayout(properties_widget)
        properties_layout.setContentsMargins(5, 5, 5, 5)  # 增加内边距
        properties_layout.setSpacing(3)  # 减小整体间距
        properties_layout.setHorizontalSpacing(3)  # 减小横向间距
        properties_layout.setVerticalSpacing(5)  # 增加纵向间距

        # 第一行
        # X
        properties_layout.addWidget(QLabel("X"), 0, 0)
        x_input = QLineEdit("0")
        x_input.setMaximumWidth(55)
        x_input.setMinimumHeight(24)  # 增加输入框高度
        x_input.setMaximumHeight(24)
        properties_layout.addWidget(x_input, 0, 1)
        properties_layout.addWidget(QLabel("mm"), 0, 2)

        # 宽度图标
        kuandu_icon = QLabel()
        kuandu_icon.setPixmap(QIcon("toolbar_row3_icons/icon3_width.png").pixmap(QSize(20, 20)))
        kuandu_icon.setMaximumWidth(22)
        properties_layout.addWidget(kuandu_icon, 0, 3)

        # 宽度
        width_input = QLineEdit("0")
        width_input.setMaximumWidth(55)
        width_input.setMinimumHeight(24)  # 增加输入框高度
        width_input.setMaximumHeight(24)
        properties_layout.addWidget(width_input, 0, 4)
        properties_layout.addWidget(QLabel("mm"), 0, 5)

        # 百分比
        percent_input = QLineEdit("0")
        percent_input.setMaximumWidth(55)
        percent_input.setMinimumHeight(24)  # 增加输入框高度
        percent_input.setMaximumHeight(24)
        properties_layout.addWidget(percent_input, 0, 6)
        properties_layout.addWidget(QLabel("%"), 0, 7)

        # 第二行
        # Y
        properties_layout.addWidget(QLabel("Y"), 1, 0)
        y_input = QLineEdit("0")
        y_input.setMaximumWidth(55)
        y_input.setMinimumHeight(24)  # 增加输入框高度
        y_input.setMaximumHeight(24)
        properties_layout.addWidget(y_input, 1, 1)
        properties_layout.addWidget(QLabel("mm"), 1, 2)

        # 高度图标（光度）
        gaodu_icon = QLabel()
        gaodu_icon.setPixmap(QIcon("toolbar_row3_icons/icon3_height.png").pixmap(QSize(20, 20)))
        gaodu_icon.setMaximumWidth(22)
        properties_layout.addWidget(gaodu_icon, 1, 3)

        # 高度
        height_input = QLineEdit("0")
        height_input.setMaximumWidth(55)
        height_input.setMinimumHeight(24)  # 增加输入框高度
        height_input.setMaximumHeight(24)
        properties_layout.addWidget(height_input, 1, 4)
        properties_layout.addWidget(QLabel("mm"), 1, 5)

        # 百分比（第二行）
        percent_input2 = QLineEdit("0")
        percent_input2.setMaximumWidth(55)
        percent_input2.setMinimumHeight(24)  # 增加输入框高度
        percent_input2.setMaximumHeight(24)
        properties_layout.addWidget(percent_input2, 1, 6)
        properties_layout.addWidget(QLabel("%"), 1, 7)

        toolbar3.addWidget(properties_widget)

        # 变换工具（前三个按钮紧贴百分比，无分隔符）
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column1.png', '倾斜', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column2.png', '水平翻转', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column3.png', '垂直翻转', None, False))
        toolbar3.addSeparator()  # 在第三个按钮后添加分隔符

        # 对齐工具
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column4.png', '左对齐', None, False))

        # 角度输入框和加工序号输入框（合并到一个widget中，防止全屏时分开）
        from PyQt5.QtWidgets import QSizePolicy

        angle_order_widget = QWidget()
        angle_order_widget.setMinimumWidth(280)  # 设置最小宽度，防止被压缩
        angle_order_widget.setMaximumWidth(280)  # 设置最大宽度，防止被拉伸
        angle_order_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)  # 固定宽度

        angle_order_layout = QHBoxLayout(angle_order_widget)
        angle_order_layout.setContentsMargins(3, 0, 3, 0)
        angle_order_layout.setSpacing(5)  # 两个输入框之间的间距

        # 角度输入框
        angle_input = QLineEdit("0")
        angle_input.setMaximumWidth(70)
        angle_input.setMinimumHeight(40)
        angle_input.setMaximumHeight(40)
        angle_input.setAlignment(Qt.AlignCenter)
        angle_order_layout.addWidget(angle_input)

        degree_label = QLabel("°")
        degree_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        angle_order_layout.addWidget(degree_label)

        # 加工序号标签
        order_label = QLabel("加工序号")
        order_label.setStyleSheet("font-size: 14px; font-weight: bold;")  # 加大字体到14px并加粗
        angle_order_layout.addWidget(order_label)

        # 加工序号输入框
        order_input = QLineEdit("0")
        order_input.setMaximumWidth(70)
        order_input.setMinimumHeight(40)
        order_input.setMaximumHeight(40)
        order_input.setAlignment(Qt.AlignCenter)
        angle_order_layout.addWidget(order_input)

        toolbar3.addWidget(angle_order_widget)

        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column5.png', '中心对齐', None, False))
        toolbar3.addSeparator()  # 在第五个按钮后添加分隔符
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column6.png', '右对齐', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column7.png', '顶部对齐', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column8.png', '中间对齐', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column9.png', '底部对齐', None, False))
        toolbar3.addSeparator()

        # 分布工具
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column10.png', '水平分布', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column11.png', '垂直分布', None, False))
        toolbar3.addSeparator()

        # 组合和排列工具
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column12.png', '取消组合', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column13.png', '锁定', None, False))
        toolbar3.addSeparator()

        # 排序工具
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column14.png', '置于顶层', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column15.png', '置于底层', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column16.png', '上移一层', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column17.png', '下移一层', None, False))
        toolbar3.addSeparator()

        # 路径和编辑工具
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column18.png', '合并', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column19.png', '拆分', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column20.png', '焊接', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column21.png', '偏移', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column22.png', '布尔运算', None, False))
        toolbar3.addSeparator()

        # 其他工具
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column23.png', '文字', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column24.png', '更多', None, False))

        # 添加伸缩空间
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().Expanding, spacer.sizePolicy().Preferred)
        toolbar3.addWidget(spacer)

    def create_tool_action(self, icon_text, tooltip, callback):
        """创建工具栏动作（使用文本图标）"""
        action = QAction(icon_text, self)
        action.setToolTip(tooltip)
        if callback:
            action.triggered.connect(callback)
        return action

    def create_tool_action_with_icon(self, icon_path, tooltip, callback, show_tooltip=True):
        """创建工具栏动作（使用真实图标）"""
        action = QAction(self)
        if show_tooltip:
            action.setToolTip(tooltip)

        # 加载图标
        icon = QIcon(icon_path)
        if not icon.isNull():
            action.setIcon(icon)
        else:
            # 如果图标加载失败，使用文本作为备选
            action.setText('?')

        if callback:
            action.triggered.connect(callback)
        return action
        
    def create_central_widget(self):
        """创建中心部件 - 左中右三栏布局"""
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左侧工具栏
        self.left_toolbar = LeftToolbar()
        main_layout.addWidget(self.left_toolbar)
        
        # 中间白板区域
        self.whiteboard = WhiteboardWidget()
        main_layout.addWidget(self.whiteboard, 1)  # stretch factor = 1
        
        # 右侧属性面板
        self.right_panel = RightPanel()
        main_layout.addWidget(self.right_panel)
        
        self.setCentralWidget(central_widget)
        
    # 文件操作方法
    def new_file(self):
        """新建文件"""
        reply = QMessageBox.question(self, '新建', '是否要清空当前白板？',
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.whiteboard.clear()
            self.statusBar().showMessage('已创建新白板')
            
    def open_file(self):
        """打开文件"""
        filename, _ = QFileDialog.getOpenFileName(self, '打开文件', '', 
                                                  '白板文件 (*.wbd);;所有文件 (*)')
        if filename:
            self.statusBar().showMessage(f'打开文件: {filename}')
            
    def save_file(self):
        """保存文件"""
        self.statusBar().showMessage('保存文件')
        
    def save_as_file(self):
        """另存为文件"""
        filename, _ = QFileDialog.getSaveFileName(self, '另存为', '', 
                                                  '白板文件 (*.wbd);;所有文件 (*)')
        if filename:
            self.statusBar().showMessage(f'保存文件: {filename}')
            
    def export_image(self):
        """导出图像"""
        filename, _ = QFileDialog.getSaveFileName(self, '导出图像', '', 
                                                  'PNG图像 (*.png);;JPEG图像 (*.jpg);;所有文件 (*)')
        if filename:
            self.whiteboard.export_image(filename)
            self.statusBar().showMessage(f'已导出图像: {filename}')
            
    # 编辑操作方法
    def undo(self):
        """撤销"""
        self.whiteboard.undo()
        self.statusBar().showMessage('撤销')
        
    def redo(self):
        """重做"""
        self.whiteboard.redo()
        self.statusBar().showMessage('重做')
        
    def cut(self):
        """剪切"""
        self.statusBar().showMessage('剪切')
        
    def copy(self):
        """复制"""
        self.statusBar().showMessage('复制')
        
    def paste(self):
        """粘贴"""
        self.statusBar().showMessage('粘贴')
        
    def delete(self):
        """删除"""
        self.statusBar().showMessage('删除')
        
    def select_all(self):
        """全选"""
        self.statusBar().showMessage('全选')
        
    # 视图操作方法
    def zoom_in(self):
        """放大"""
        self.whiteboard.zoom_in()
        self.statusBar().showMessage(f'缩放: {self.whiteboard.get_zoom_percent()}%')
        
    def zoom_out(self):
        """缩小"""
        self.whiteboard.zoom_out()
        self.statusBar().showMessage(f'缩放: {self.whiteboard.get_zoom_percent()}%')
        
    def zoom_reset(self):
        """重置缩放"""
        self.whiteboard.zoom_reset()
        self.statusBar().showMessage('缩放: 100%')
        
    def toggle_fullscreen(self):
        """切换全屏"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
            
    # 工具选择方法
    def select_pen(self):
        """选择画笔"""
        self.whiteboard.set_tool('pen')
        self.statusBar().showMessage('画笔工具')
        
    def select_eraser(self):
        """选择橡皮擦"""
        self.whiteboard.set_tool('eraser')
        self.statusBar().showMessage('橡皮擦工具')
        
    def select_line(self):
        """选择直线"""
        self.whiteboard.set_tool('line')
        self.statusBar().showMessage('直线工具')
        
    def select_rectangle(self):
        """选择矩形"""
        self.whiteboard.set_tool('rectangle')
        self.statusBar().showMessage('矩形工具')
        
    def select_circle(self):
        """选择圆形"""
        self.whiteboard.set_tool('circle')
        self.statusBar().showMessage('圆形工具')
        
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, '关于', 
                         '激光加工控制系统 v1.0\n\n'
                         '专业的激光加工控制软件\n'
                         '支持精确绘图、参数设置和加工控制')

    def import_file(self):
        print(1)