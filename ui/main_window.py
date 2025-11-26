#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口类
"""
import os
from typing import List

from PIL import Image
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QKeySequence, QColor, QPalette
from PyQt5.QtWidgets import (QMainWindow, QAction, QToolBar, QHBoxLayout, QWidget, QLabel, QFileDialog, QMessageBox,
                             QLineEdit, QGraphicsPixmapItem)

from my_io.importers.supported_filter import SUPPORTED_FILTER
from ui.left_toolbar import LeftToolbar
from ui.right_panel import RightPanel
from ui.whiteboard import WhiteboardWidget
from utils.import_utils import pil_to_qpixmap, convert_wbmp_to_png
from utils.logging_utils import setup_logging
from utils.tool_utils import check_required_tools
from ui.whiteboard import Path
from my_io.gcode.gcode_exporter import export_to_nc, get_default_config, GCodeExporter

class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.undo_action = None
        self.redo_action = None
        self.cut_action = None
        self.copy_action = None
        self.paste_action = None
        self.delete_action = None
        self.select_all_action = None

        self.logger = setup_logging()
        self.logger.info("MainWindow初始化开始")
        self.init_ui()
        check_required_tools(self)
        self.logger.info("MainWindow初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('激光加工控制系统')
        self.setGeometry(50, 50, 1600, 950)

        self.setup_style()

        self.create_central_widget()

        self.create_menu_bar()

        self.create_toolbars()

        self.statusBar().showMessage('就绪')
        """连接编辑管理器信号"""
        em = self.whiteboard.canvas.edit_manager
        em.undoAvailable.connect(self.undo_action.setEnabled)
        em.redoAvailable.connect(self.redo_action.setEnabled)
        em.cutCopyAvailable.connect(lambda b: (self.cut_action.setEnabled(b), self.copy_action.setEnabled(b)))
        em.deleteAvailable.connect(self.delete_action.setEnabled)
        em.selectAllAvailable.connect(self.select_all_action.setEnabled)

        self.current_file = None

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

        file_menu = menubar.addMenu('文件(F)')

        new_action = QAction('新建(&N)', self)
        new_action.setShortcut(QKeySequence.New)
        new_action.setStatusTip('创建新的RLD文件')
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)

        open_action = QAction('打开(&O)...', self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.setStatusTip('打开现有RLD文件')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_action = QAction('保存(&S)', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip('保存当前RLD文件')
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction('另存为(&A)...', self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.setStatusTip('另存为新RLD文件')
        save_as_action.triggered.connect(self.save_as_file)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_action = QAction('导入(&E)...', self)
        export_action.setStatusTip('导入图像文件')
        export_action.triggered.connect(self.import_image)
        file_menu.addAction(export_action)

        # 添加导出动作
        export_nc_action = QAction('导出为NC(&X)...', self)
        export_nc_action.setStatusTip('导出为G代码NC文件')
        export_nc_action.triggered.connect(self.export_to_nc)
        file_menu.addAction(export_nc_action)

        file_menu.addSeparator()

        exit_action = QAction('退出(&X)', self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.setStatusTip('退出应用程序')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu('编辑(E)')

        self.undo_action = QAction('撤销(&U)', self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setStatusTip('撤销上一步操作')
        self.undo_action.triggered.connect(self.whiteboard.canvas.edit_manager.undo)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction('重做(&R)', self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.setStatusTip('重做上一步操作')
        self.redo_action.triggered.connect(self.whiteboard.canvas.edit_manager.redo)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()

        self.cut_action = QAction('剪切(&T)', self)
        self.cut_action.setShortcut(QKeySequence.Cut)
        self.cut_action.setStatusTip('剪切选中内容')
        self.cut_action.triggered.connect(self.whiteboard.canvas.edit_manager.cut)
        edit_menu.addAction(self.cut_action)

        self.copy_action = QAction('复制(&C)', self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.setStatusTip('复制选中内容')
        self.copy_action.triggered.connect(self.whiteboard.canvas.edit_manager.copy)
        edit_menu.addAction(self.copy_action)

        self.paste_action = QAction('粘贴(&P)', self)
        self.paste_action.setShortcut(QKeySequence.Paste)
        self.paste_action.setStatusTip('粘贴内容')
        self.paste_action.triggered.connect(self.whiteboard.canvas.edit_manager.paste)
        edit_menu.addAction(self.paste_action)

        edit_menu.addSeparator()

        self.delete_action = QAction('删除(&D)', self)
        self.delete_action.setShortcut(QKeySequence.Delete)
        self.delete_action.setStatusTip('删除选中内容')
        self.delete_action.triggered.connect(self.whiteboard.canvas.edit_manager.delete)
        edit_menu.addAction(self.delete_action)

        self.select_all_action = QAction('全选(&A)', self)
        self.select_all_action.setShortcut(QKeySequence.SelectAll)
        self.select_all_action.setStatusTip('选择全部内容')
        self.select_all_action.triggered.connect(self.whiteboard.canvas.edit_manager.select_all)
        edit_menu.addAction(self.select_all_action)

        # ========== 新增：定位点菜单 ==========
        edit_menu.addSeparator()

        # 添加十字定位点
        self.add_cross_fiducial_action = QAction('添加十字定位点', self)
        self.add_cross_fiducial_action.setStatusTip('添加十字形定位点（右键点击设置位置）')
        self.add_cross_fiducial_action.triggered.connect(self.enable_cross_fiducial_mode)
        edit_menu.addAction(self.add_cross_fiducial_action)

        # 添加圆形定位点
        self.add_circle_fiducial_action = QAction('添加圆形定位点', self)
        self.add_circle_fiducial_action.setStatusTip('添加圆形定位点（右键点击设置位置）')
        self.add_circle_fiducial_action.triggered.connect(self.enable_circle_fiducial_mode)
        edit_menu.addAction(self.add_circle_fiducial_action)

        # 删除定位点
        self.remove_fiducial_action = QAction('删除定位点', self)
        self.remove_fiducial_action.setStatusTip('删除当前定位点')
        self.remove_fiducial_action.triggered.connect(self.remove_fiducial)
        edit_menu.addAction(self.remove_fiducial_action)

        # 视图菜单
        view_menu = menubar.addMenu('视图(D)')
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

        settings_menu = menubar.addMenu('设置(S)')
        settings_menu.addAction(QAction('参数设置', self))
        settings_menu.addAction(QAction('系统配置', self))

        process_menu = menubar.addMenu('处理(W)')
        process_menu.addAction(QAction('开始加工', self))
        process_menu.addAction(QAction('停止加工', self))

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

        main_config_menu = menubar.addMenu('主配置(M)')
        main_config_menu.addAction(QAction('主要配置', self))

        view2_menu = menubar.addMenu('查看(H)')
        view2_menu.addAction(QAction('查看选项', self))

        prop_menu = menubar.addMenu('属性(H)')
        prop_menu.addAction(QAction('对象属性', self))

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
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column3.png', '保存', None))
        toolbar1.addSeparator()
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column4.png', '导入', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column5.png', '导出', None))
        toolbar1.addSeparator()
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column6.png', '撤销', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column7.png', '恢复', None))
        toolbar1.addSeparator()
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column8.png', '平移', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column9.png', '放大', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column10.png', '缩小', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column11.png', '页面范围', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column12.png', '数据范围 ', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column13.png', '显示所有', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column14.png', '框选查看', None))
        toolbar1.addSeparator()
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column15.png', '显示路径', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column16.png', '设置导入导出', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column17.png', '设置切割属性', None))
        toolbar1.addSeparator()
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column18.png', '加工预览', None))
        toolbar1.addSeparator()
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column19.png', '自动群组', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column20.png', '群组', None))
        toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column21.png', '解散群组', None))


        # 第二行工具栏
        toolbar2 = QToolBar('工具栏2')
        toolbar2.setIconSize(QSize(28, 28))
        toolbar2.setMovable(False)
        # 将第二行工具栏放到新的一行
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, toolbar2)

        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column1.png', '投影切割', self.new_file))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column2.png', '', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column3.png', '测量工具', self.open_file))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column4.png', 'Mark点定位', self.save_file))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column5.png', '曲线平滑', None))
        toolbar2.addSeparator()
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column6.png', '位图处理', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column7.png', '曲线自动闭合', None))
        toolbar2.addSeparator()
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column8.png', '切割优化', self.zoom_in))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column9.png', '合并相连线', self.zoom_out))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column10.png', '删除重线', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column11.png', '平行线', self.zoom_reset))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column12.png', '数据检查', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column13.png', '拍照', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column14.png', '框选提边', None))
        toolbar2.addSeparator()
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column15.png', '提边设置', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column16.png', '扶正功能', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column17.png', '放置图形', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column18.png', '底图显示', None))
        toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column19.png', '画布参数设置', None))

        # 第三行工具栏
        toolbar3 = QToolBar('工具栏3')
        toolbar3.setIconSize(QSize(32, 32))
        toolbar3.setMovable(False)
        toolbar3.setMinimumHeight(70)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, toolbar3)

        # 创建属性输入区域
        from PyQt5.QtWidgets import QGridLayout

        properties_widget = QWidget()
        properties_widget.setMinimumHeight(65)
        properties_widget.setMaximumHeight(65)
        properties_widget.setMaximumWidth(450)
        properties_layout = QGridLayout(properties_widget)
        properties_layout.setContentsMargins(5, 5, 5, 5)
        properties_layout.setSpacing(3)
        properties_layout.setHorizontalSpacing(3)
        properties_layout.setVerticalSpacing(5)

        # 第一行
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

        # 变换工具
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column1.png', '锁住', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column2.png', '选择位置坐标基准', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column3.png', '修改尺寸', None))
        toolbar3.addSeparator()

        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column4.png', '恢复', None, False))

        # 角度输入框和加工序号输入框（合并到一个widget中，防止全屏时分开）
        from PyQt5.QtWidgets import QSizePolicy

        angle_order_widget = QWidget()
        angle_order_widget.setMinimumWidth(280)
        angle_order_widget.setMaximumWidth(280)
        angle_order_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)  # 固定宽度

        angle_order_layout = QHBoxLayout(angle_order_widget)
        angle_order_layout.setContentsMargins(3, 0, 3, 0)
        angle_order_layout.setSpacing(5)

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

        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column5.png', '恢复', None,False))
        toolbar3.addSeparator()  # 在第五个按钮后添加分隔符
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column6.png', '左对齐', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column7.png', '右对齐', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column8.png', '顶端对齐', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column9.png', '底端对齐', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column10.png', '水平居中对齐', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column11.png', '垂直居中对齐', None))
        toolbar3.addSeparator()
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column12.png', '等水平间距 ', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column13.png', '等垂直间距', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column14.png', '等宽', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column15.png', '等高', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column16.png', '等大小', None))
        toolbar3.addSeparator()
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column17.png', '左上', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column18.png', '右上', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column19.png', '右下', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column20.png', '左下', None))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column21.png', '在页面居中', None))
        toolbar3.addSeparator()
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column22.png', '', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column23.png', '', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column24.png', '', None, False))
        toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column25.png', '', None, False))

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
        """创建中心部件左中右三栏布局"""
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

    def new_file(self):
        """新建RLD文件"""
        reply = QMessageBox.question(self, '新建RLD文件', '是否要清空当前白板并创建新文件？',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.whiteboard.clear()
            self.current_file = None
            self.setWindowTitle('激光加工控制系统 - 新文件')
            self.statusBar().showMessage('已创建新RLD文件')
            self.logger.info("创建新RLD文件")

    def open_file(self):
        """打开RLD文件"""
        from my_io.RLD.init_rld import RLDFileHandler

        filename, _ = QFileDialog.getOpenFileName(
            self,
            '打开RLD文件',
            '',
            'RLD文件 (*.rld *.rldf);;所有文件 (*)'
        )

        if filename and RLDFileHandler.is_rld_file(filename):
            try:
                # 加载文件
                success = RLDFileHandler.load_from_file(self.whiteboard.canvas, filename)
                if success:
                    self.current_file = filename
                    self.setWindowTitle(f'激光加工控制系统 - {os.path.basename(filename)}')
                    self.statusBar().showMessage(f'已打开RLD文件: {os.path.basename(filename)}')
                    self.logger.info(f"打开RLD文件: {filename}")
                else:
                    QMessageBox.warning(self, "打开失败", "无法打开RLD文件，文件可能已损坏")
            except Exception as e:
                QMessageBox.critical(self, "打开错误", f"打开文件时发生错误:\n{str(e)}")
        elif filename:
            QMessageBox.warning(self, "文件格式错误", "请选择有效的RLD文件格式(.rld, .rldf)")

    def save_file(self):
        """保存RLD文件"""
        from my_io.RLD.init_rld import RLDFileHandler

        if hasattr(self, 'current_file') and self.current_file:
            # 保存到当前文件
            success = RLDFileHandler.save_to_file(self.whiteboard.canvas, self.current_file)
            if success:
                self.statusBar().showMessage(f'已保存RLD文件: {os.path.basename(self.current_file)}')
                self.logger.info(f"保存RLD文件: {self.current_file}")
            else:
                QMessageBox.warning(self, "保存失败", "保存文件失败，请检查文件权限")
        else:
            # 没有当前文件，执行另存为
            self.save_as_file()

    def save_as_file(self):
        """另存为RLD文件"""
        from my_io.RLD.init_rld import RLDFileHandler

        filename, _ = QFileDialog.getSaveFileName(
            self,
            '另存为RLD文件',
            '',
            'RLD文件 (*.rld);;所有文件 (*)'
        )

        if filename:
            # 确保文件扩展名
            if not filename.lower().endswith('.rld'):
                filename += '.rld'

            try:
                success = RLDFileHandler.save_to_file(self.whiteboard.canvas, filename)
                if success:
                    self.current_file = filename
                    self.setWindowTitle(f'激光加工控制系统 - {os.path.basename(filename)}')
                    self.statusBar().showMessage(f'已另存为RLD文件: {os.path.basename(filename)}')
                    self.logger.info(f"另存为RLD文件: {filename}")
                else:
                    QMessageBox.warning(self, "保存失败", "保存文件失败，请检查文件权限")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", f"保存文件时发生错误:\n{str(e)}")

    def import_image(self):
        """
        合成后的图像/矢量文件导入总函数：整合原 _on_import_any、_filter、import_file_any 所有逻辑
        支持格式：HPGL/PLT、WBMP、BMP/PNG/JPG等位图、EPS、AI、DXF/SVG、G-code、PDF、PCX/TGA 等
        保持原所有处理逻辑、交互提示、异常处理不变
        """
        # --------------------------- 原 _filter 函数逻辑（直接返回支持的过滤器） ---------------------------
        SUPPORTED_FILTER_LOCAL = SUPPORTED_FILTER  # 复用原 SUPPORTED_FILTER 常量

        # --------------------------- 原 _on_import_any 开头：文件选择与初始化 ---------------------------
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, '导入', filter=SUPPORTED_FILTER_LOCAL)
        if not path:
            return

        lower = path.lower()
        self.logger.info(f"开始导入文件: {path}")  # 记录导入的文件路径

        try:
            # --------------------------- HPGL/PLT文件导入部分 - 保留原简化版逻辑 ---------------------------
            if lower.endswith(('.plt', '.hpgl')):
                # 基础文件检查
                if not os.path.exists(path):
                    self.statusBar().showMessage(f"HPGL/PLT文件不存在: {os.path.basename(path)}", 5000)
                    return

                if not os.access(path, os.R_OK):
                    self.statusBar().showMessage(f"HPGL/PLT文件不可读: {os.path.basename(path)}", 5000)
                    return

                file_size = os.path.getsize(path)
                if file_size == 0:
                    self.statusBar().showMessage("HPGL/PLT文件为空", 5000)
                    return

                self.statusBar().showMessage("正在导入HPGL/PLT文件...")
                QtWidgets.QApplication.processEvents()

                try:
                    # --------------------------- 原 import_file_any 中 HPGL/PLT 处理逻辑 ---------------------------
                    from my_io.importers.import_hpgl import import_hpgl
                    paths = import_hpgl(path)

                    if paths:
                        # 添加路径到画布
                        for pts in paths:
                            if len(pts) > 0:
                                self.whiteboard.canvas.add_polyline(pts, QtGui.QColor(0, 0, 0))

                        self.whiteboard.canvas.fit_all()
                        path_count = len(paths)
                        total_points = sum(len(pts) for pts in paths)
                        self.statusBar().showMessage(
                            f'HPGL/PLT导入成功: {os.path.basename(path)} (路径数={path_count}, 总点数={total_points})',
                            5000)
                    else:
                        self.statusBar().showMessage(f'HPGL/PLT文件 {os.path.basename(path)} 中未找到可导入的图形数据', 5000)

                except Exception as e:
                    self.statusBar().showMessage(f'HPGL/PLT导入错误: {str(e)}', 5000)
                    QtWidgets.QMessageBox.warning(self, "导入失败", f"HPGL/PLT文件导入失败:\n{str(e)}")

                return  # HPGL/PLT处理完成，直接返回

            # --------------------------- 处理WBMP文件 - 保留原逻辑 ---------------------------
            if lower.endswith('.wbmp'):
                # 尝试直接转换WBMP为PNG
                wbmp_img = convert_wbmp_to_png(path)
                if wbmp_img:
                    self._current_bitmap = wbmp_img
                    pix = pil_to_qpixmap(wbmp_img)
                    self.whiteboard.canvas.add_image(pix, 0.0, 0.0)
                    self.whiteboard.canvas.fit_all()
                    self.statusBar().showMessage(f'已转换并导入WBMP位图: {os.path.basename(path)}', 5000)
                    return
                else:
                    # 尝试用inkscape转换
                    from utils.import_utils import auto_convert_file
                    converted_path, convert_msg = auto_convert_file(path, 'png')
                    if converted_path:
                        try:
                            im = Image.open(converted_path).convert('RGBA')
                            self._current_bitmap = im
                            pix = pil_to_qpixmap(im)
                            self.whiteboard.canvas.add_image(pix, 0.0, 0.0)
                            self.whiteboard.canvas.fit_all()
                            self.statusBar().showMessage(f'已转换并导入WBMP位图: {os.path.basename(path)}', 5000)
                            os.unlink(converted_path)
                            return
                        except Exception as e2:
                            os.unlink(converted_path)

            # --------------------------- 位图/EPS/WMF/EMF 处理 - 保留原逻辑 ---------------------------
            if lower.endswith((
                    '.bmp', '.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff', '.webp',
                    '.pbm', '.pgm', '.ppm', '.pnm', '.ras', '.raw', '.ico', '.cur',
                    '.emf', '.wmf', '.eps', '.jp2'
            )):
                if lower.endswith('.eps'):
                    # 先尝试矢量导入EPS
                    self.statusBar().showMessage("正在处理EPS文件（使用软件自带工具）...")
                    QtWidgets.QApplication.processEvents()

                    # 先尝试矢量导入EPS
                    from my_io.importers.import_eps_vector import import_eps_as_vector
                    paths, status_msg = import_eps_as_vector(path)

                    if paths is not None:
                        # 矢量导入成功
                        for pts in paths:
                            self.whiteboard.canvas.add_polyline(pts, QtGui.QColor(0, 0, 0))
                        self.whiteboard.canvas.fit_all()
                        self.statusBar().showMessage(f"EPS矢量导入成功: {status_msg}", 5000)
                        return

                    # 矢量导入失败，尝试位图导入
                    from my_io.importers.import_eps_bitmap import import_eps_as_bitmap
                    im, error_msg = import_eps_as_bitmap(path)

                    if im is not None:
                        # 位图导入成功
                        pix = self.pil_to_qpixmap(im)
                        self._current_bitmap = im.copy()
                        self.whiteboard.canvas.add_image(pix, 0.0, 0.0)
                        self.whiteboard.canvas.fit_all()
                        self.statusBar().showMessage(f"EPS位图导入成功", 5000)
                    else:
                        raise RuntimeError(f"EPS文件导入失败:\n{error_msg if error_msg else status_msg}")
                    return
                else:
                    # 处理其他位图
                    try:
                        im = Image.open(path).convert('RGBA')
                        self._current_bitmap = im
                        pix = pil_to_qpixmap(im)
                        self.whiteboard.canvas.add_image(pix, 0.0, 0.0)
                        self.whiteboard.canvas.fit_all()
                        self.statusBar().showMessage(f'已导入位图: {os.path.basename(path)}', 5000)
                        return
                    except Exception as e:
                        # 尝试转换
                        from utils.import_utils import auto_convert_file
                        converted_path, convert_msg = auto_convert_file(path, 'png')
                        if converted_path:
                            try:
                                im = Image.open(converted_path).convert('RGBA')
                                self._current_bitmap = im
                                pix = pil_to_qpixmap(im)
                                self.whiteboard.canvas.add_image(pix, 0.0, 0.0)
                                self.whiteboard.canvas.fit_all()
                                self.statusBar().showMessage(f'已转换并导入位图: {os.path.basename(path)}', 5000)
                                os.unlink(converted_path)
                                return
                            except Exception as e2:
                                os.unlink(converted_path)

            # --------------------------- 处理AI文件 - 保留原核心逻辑 ---------------------------
            if lower.endswith('.ai'):
                self.statusBar().showMessage("正在处理AI文件（使用软件自带工具）...")
                QtWidgets.QApplication.processEvents()  # 刷新UI，显示状态
                self.logger.info("开始处理AI文件，调用import_ai")

                from my_io.importers.import_ai import import_ai
                paths, status_msg, bitmap_image = import_ai(path)  # 调用导入函数

                self.logger.info(
                    f"import_ai返回结果: "
                    f"paths={bool(paths)}, "
                    f"bitmap={bool(bitmap_image)}, "
                    f"msg={status_msg}"
                )

                # 1. 优先处理位图（如果存在）
                if bitmap_image is not None:
                    try:
                        # 转换PIL图像为QPixmap
                        pix = pil_to_qpixmap(bitmap_image)
                        if pix.isNull():
                            raise ValueError("位图转换为QPixmap失败（空图像）")

                        # 保存位图副本并添加到画布
                        self._current_bitmap = bitmap_image.copy()
                        self.whiteboard.canvas.add_image(pix, 0.0, 0.0)  # 添加到画布(0,0)位置
                        self.whiteboard.canvas.fit_all()  # 自动调整视图以显示全图

                        # 显示成功信息
                        success_msg = f"✓ AI转换为位图成功: {os.path.basename(path)}"
                        self.statusBar().showMessage(success_msg, 5000)  # 5秒后消失
                        self.logger.info("AI文件作为位图成功导入")

                    except Exception as e:
                        # 位图处理失败的异常处理
                        err_msg = f"位图显示失败: {str(e)}"
                        self.statusBar().showMessage(err_msg, 5000)
                        self.logger.error(f"位图处理异常: {err_msg}", exc_info=True)  # 记录堆栈
                        QtWidgets.QMessageBox.warning(
                            self,
                            "显示失败",
                            f"位图导入过程出错:\n{err_msg}"
                        )

                # 2. 处理矢量路径（如果位图不存在且路径有效）
                elif paths is not None and len(paths) > 0:
                    try:
                        # 日志记录路径基本信息
                        self.logger.info(f"AI矢量路径有效，共{len(paths)}条路径")
                        first_path_pts = paths[0] if len(paths) > 0 else []
                        self.logger.info(
                            f"第一条路径包含{len(first_path_pts)}个点，"
                            f"第一个点坐标: {first_path_pts[0] if first_path_pts else '无'}"
                        )

                        # 绘制所有路径（红色，确保可见）
                        for idx, pts in enumerate(paths):
                            if len(pts) < 2:
                                self.logger.warning(f"路径{idx}点数量不足（{len(pts)}个），跳过绘制")
                                continue
                            self.whiteboard.canvas.add_polyline(pts, QtGui.QColor(255, 0, 0))  # 红色线条

                        # 调整视图以显示所有路径
                        self.whiteboard.canvas.fit_all()
                        self.logger.info("所有有效路径已添加到画布，并调用fit_all刷新视图")

                        # 显示成功信息
                        success_msg = f"✓ AI矢量路径导入成功: {os.path.basename(path)}"
                        self.statusBar().showMessage(success_msg, 5000)

                    except Exception as e:
                        # 矢量路径处理失败的异常处理
                        err_msg = f"矢量路径绘制失败: {str(e)}"
                        self.statusBar().showMessage(err_msg, 5000)
                        self.logger.error(f"矢量路径处理异常: {err_msg}", exc_info=True)
                        QtWidgets.QMessageBox.warning(
                            self,
                            "绘制失败",
                            f"矢量路径导入过程出错:\n{err_msg}"
                        )

                # 3. 所有方法均失败（无位图且无有效路径）
                else:
                    error_msg = f"AI文件导入失败:\n{status_msg}"
                    self.statusBar().showMessage(error_msg, 5000)
                    self.logger.error(f"AI导入完全失败: {error_msg}")
                    QtWidgets.QMessageBox.warning(
                        self,
                        "导入失败",
                        error_msg,
                        QtWidgets.QMessageBox.Ok
                    )

                return  # 结束AI文件处理

            # --------------------------- 其他格式：原 import_file_any 核心逻辑 ---------------------------
            paths: List[Path] = []
            try:
                # 处理 DXF 格式
                if lower.endswith(('.dxf',)):
                    from my_io.importers.import_dxf import import_dxf
                    paths = import_dxf(path)
                # 处理 SVG 格式
                elif lower.endswith(('.svg',)):
                    from my_io.importers.import_svg import import_svg
                    paths = import_svg(path)
                elif lower.endswith(('.nc', '.ngc', '.gcode')):
                    from my_io.importers.import_gcode import import_gcode
                    paths = import_gcode(path)
                elif lower.endswith(('.pdf', '.ai')):
                    from my_io.importers.import_pdf import import_pdf_or_ai
                    paths = import_pdf_or_ai(path)
                elif lower.endswith(('.eps',)):
                    # 尝试先作为矢量导入EPS
                    try:
                        from my_io.importers.import_eps_vector import import_eps_as_vector
                        vector_paths = import_eps_as_vector(path)
                        if vector_paths:
                            paths = vector_paths
                    except:
                        pass
                elif lower.endswith('.pcx'):
                    try:
                        from my_io.importers.import_pcx import import_pcx
                        pcx_paths, status_msg, bitmap_image = import_pcx(path)

                        if bitmap_image is not None:
                            # 直接显示位图
                            pix = self.pil_to_qpixmap(bitmap_image)  # 使用实例方法
                            self._current_bitmap = bitmap_image.copy()
                            self.whiteboard.canvas.add_image(pix, 0.0, 0.0)
                            self.whiteboard.canvas.fit_all()
                            self.statusBar().showMessage("✓ PCX文件导入成功", 5000)
                            paths = []  # 位图导入成功，无需返回路径
                        elif pcx_paths is not None:
                            # 如果有矢量路径（理论上PCX不会有）
                            for pts in pcx_paths:
                                self.whiteboard.canvas.add_polyline(pts, QtGui.QColor(0, 0, 0))
                            self.whiteboard.canvas.fit_all()
                            self.statusBar().showMessage("✓ PCX文件导入成功", 5000)
                            paths = pcx_paths
                        else:
                            raise RuntimeError("PCX导入失败")

                    except Exception as e:
                        self.statusBar().showMessage(f'PCX导入失败: {str(e)}', 5000)
                        QtWidgets.QMessageBox.warning(
                            self,
                            "PCX导入失败",
                            "PCX文件导入失败。\n\n建议：\n1. 使用其他图像软件将PCX转换为PNG格式\n2. 或使用更新的图像格式替代PCX"
                        )
                        paths = []
                # 其他图片格式保持原处理逻辑（返回空列表，不处理矢量）
                elif lower.endswith(('.bmp', '.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff',
                                     '.tga', '.wbmp', '.jp2', '.ppm', '.pgm', '.pnm', '.ras', '.raw',
                                     '.ico', '.cur', '.emf', '.wmf')):
                    paths = []
                else:
                    raise RuntimeError('不支持的文件类型: ' + path)
            except Exception as e:
                # 新增：导入失败时尝试自动转换为SVG再导入
                from utils.import_utils import auto_convert_file
                converted_path, convert_msg = auto_convert_file(path, 'svg')  # 转换为临时SVG
                if converted_path:
                    try:
                        from my_io.importers.import_svg import import_svg
                        paths = import_svg(converted_path)  # 解析转换后的SVG
                    except Exception as e2:
                        os.unlink(converted_path)  # 转换后仍失败，清理临时文件
                        raise RuntimeError(f"导入失败，自动转换为SVG也失败: {str(e2)}") from e2
                    finally:
                        if os.path.exists(converted_path):
                            os.unlink(converted_path)  # 确保临时文件被清理
                else:
                    raise e  # 转换失败，抛出原始错误

            # --------------------------- 其他格式导入结果处理 - 保留原逻辑 ---------------------------
            if paths:
                for pts in paths:
                    self.whiteboard.canvas.add_polyline(pts, QtGui.QColor(0, 0, 0))
                self.whiteboard.canvas.fit_all()
                self.statusBar().showMessage(f'已导入: {os.path.basename(path)} / 路径数={len(paths)}', 5000)
            else:
                # 如果是位图格式但导入失败，尝试直接作为位图处理
                if lower.endswith(('.pcx', '.tga')):
                    try:
                        # 尝试使用转换工具
                        from utils.import_utils import auto_convert_file
                        converted_path, convert_msg = auto_convert_file(path, 'png')
                        if converted_path:
                            im = Image.open(converted_path).convert('RGBA')
                            self._current_bitmap = im
                            pix = pil_to_qpixmap(im)
                            self.whiteboard.canvas.add_image(pix, 0.0, 0.0)
                            self.whiteboard.canvas.fit_all()
                            self.statusBar().showMessage(f'已转换并导入位图: {os.path.basename(path)}', 5000)
                            os.unlink(converted_path)
                            return
                    except Exception as e:
                        self.statusBar().showMessage(f'PCX/TGA文件导入失败: {str(e)}', 5000)
                else:
                    self.statusBar().showMessage(f'未从 {os.path.basename(path)} 中找到可导入的图形', 5000)

        except Exception as e:
            # 捕获所有未预料的异常 - 保留原逻辑
            err_msg = f"导入总异常: {str(e)}"
            self.statusBar().showMessage(err_msg, 5000)
            self.logger.error(err_msg, exc_info=True)  # 记录完整堆栈
            QtWidgets.QMessageBox.critical(self, "导入错误", f"无法导入文件: {str(e)}\n查看日志获取详情")

    def export_to_nc(self):
        """导出为NC文件 - 增强版（支持矢量和位图）"""
        try:
            # 详细分析画布内容
            content_info = self._analyze_canvas_content()
            self.logger.info(f"画布内容分析: {content_info}")

            if not content_info['has_any_content']:
                QMessageBox.warning(self, "导出失败", "画布中没有可导出的内容")
                return

            # 如果只有图片，更新提示语
            if content_info['has_images'] and not content_info['has_paths']:
                reply = QMessageBox.question(
                    self,
                    "导出图片",
                    "检测到画布中只有图片。\n将生成灰度雕刻G代码（可调整参数控制精度）。\n是否继续？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

            # 选择保存文件路径
            filename, _ = QFileDialog.getSaveFileName(
                self,
                '导出为NC文件',
                '',
                'NC文件 (*.nc);;G代码文件 (*.gcode);;所有文件 (*)'
            )

            if not filename:
                return  # 用户取消

            # 确保文件扩展名
            if not filename.lower().endswith(('.nc', '.gcode')):
                filename += '.nc'

            # 显示导出进度
            self.statusBar().showMessage("正在导出G代码...")

            # 配置导出参数
            config = get_default_config()

            # 根据内容类型优化配置
            if content_info['has_images']:
                # 对于图片，使用更精细的扫描间隔
                config['scan_interval'] = 0.05  # 更精细的扫描
                config['grayscale_threshold'] = 128  # 中等灰度阈值

            # 执行导出
            success = export_to_nc(self.whiteboard.canvas, filename, config)

            if success:
                # 读取生成的文件以获取更多信息
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        gcode_lines = f.readlines()
                        line_count = len(gcode_lines)

                        # 统计实际加工指令
                        move_count = sum(1 for line in gcode_lines if line.startswith(('G00', 'G01')))
                        laser_on_count = sum(1 for line in gcode_lines if 'M03' in line)

                        message = f'成功导出G代码: {os.path.basename(filename)}'
                        message += f" (共 {line_count} 行, {move_count} 个移动指令)"

                        if content_info['has_images']:
                            message += f" (包含 {content_info['image_count']} 张图片)"
                        if content_info['has_paths']:
                            message += f" (包含 {content_info['path_count']} 条路径)"

                        self.statusBar().showMessage(message, 5000)
                        QMessageBox.information(self, "导出成功",
                                                f"G代码导出完成！\n文件已保存到: {filename}\n"
                                                f"共生成 {line_count} 行G代码，{move_count} 个移动指令")
                except Exception as read_error:
                    self.logger.warning(f"读取G代码文件失败: {read_error}")
                    self.statusBar().showMessage(f'成功导出G代码: {os.path.basename(filename)}', 5000)
                    QMessageBox.information(self, "导出成功", f"G代码导出完成！\n文件已保存到: {filename}")
            else:
                self.statusBar().showMessage('导出失败', 5000)
                QMessageBox.warning(self, "导出失败", "G代码导出失败，请查看日志获取详细信息")

        except Exception as e:
            error_msg = f"导出过程中发生错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.statusBar().showMessage('导出错误', 5000)
            QMessageBox.critical(self, "导出错误", error_msg)

    def _analyze_canvas_content(self):
        """详细分析画布内容（增强版）"""
        from PyQt5.QtWidgets import QGraphicsPixmapItem

        info = {
            'has_paths': False,
            'has_images': False,
            'has_any_content': False,
            'path_count': 0,
            'image_count': 0,
            'total_points': 0,
            'image_sizes': []
        }

        try:
            for item in self.whiteboard.canvas.scene.items():
                # 排除工作区网格等系统项
                if hasattr(self.whiteboard.canvas, '_work_item') and item == self.whiteboard.canvas._work_item:
                    continue
                if hasattr(self.whiteboard.canvas, '_fiducial_item') and item == self.whiteboard.canvas._fiducial_item:
                    continue

                # 矢量路径
                if hasattr(item, '_points') and hasattr(item, 'points'):
                    try:
                        points = item.points()
                        if points and len(points) >= 2:
                            info['has_paths'] = True
                            info['path_count'] += 1
                            info['total_points'] += len(points)
                    except Exception as e:
                        self.logger.warning(f"获取路径点时出错: {e}")

                # 位图图片
                elif isinstance(item, QGraphicsPixmapItem):
                    if not item.pixmap().isNull():
                        info['has_images'] = True
                        info['image_count'] += 1
                        # 记录图片尺寸
                        pixmap = item.pixmap()
                        info['image_sizes'].append(f"{pixmap.width()}x{pixmap.height()}")

            info['has_any_content'] = info['has_paths'] or info['has_images']

            # 添加详细日志
            if info['has_paths']:
                self.logger.info(f"找到 {info['path_count']} 条路径，共 {info['total_points']} 个点")
            if info['has_images']:
                self.logger.info(f"找到 {info['image_count']} 张图片，尺寸: {', '.join(info['image_sizes'])}")

        except Exception as e:
            self.logger.error(f"分析画布内容时出错: {e}")

        return info

    def _has_exportable_content(self) -> bool:
        """检查画布中是否有可导出的内容（支持矢量和位图）"""
        try:
            from PyQt5.QtWidgets import QGraphicsPixmapItem

            # 检查是否有路径项或图片项
            for item in self.whiteboard.canvas.scene.items():
                # 检查矢量路径
                if hasattr(item, '_points') and hasattr(item, 'points'):
                    points = item.points()
                    if len(points) >= 2:
                        return True

                # 检查位图图片
                if isinstance(item, QGraphicsPixmapItem):
                    if not item.pixmap().isNull():
                        return True

            return False
        except Exception as e:
            self.logger.error(f"检查可导出内容时出错: {e}")
            return False

    def enable_cross_fiducial_mode(self):
        """启用十字定位点模式"""
        self.whiteboard.canvas.set_tool(self.whiteboard.canvas.Tool.ADD_FID_CROSS)
        self.statusBar().showMessage('十字定位点模式：请在画布上右键点击设置定位点（点击后自动退出）')

    def enable_circle_fiducial_mode(self):
        """启用圆形定位点模式"""
        self.whiteboard.canvas.set_tool(self.whiteboard.canvas.Tool.ADD_FID_CIRCLE)
        self.statusBar().showMessage('圆形定位点模式：请在画布上右键点击设置定位点（点击后自动退出）')

    def remove_fiducial(self):
        """删除定位点"""
        self.whiteboard.remove_fiducial()
        self.statusBar().showMessage('定位点已删除')

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

    def closeEvent(self, event):
        """关闭事件处理 - 在用户尝试关闭窗口时调用"""
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                '未保存的更改',
                '文档已修改，是否保存更改？',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save  # 默认选择保存
            )

            if reply == QMessageBox.Save:
                # 尝试保存文件
                try:
                    self.save_file()
                    event.accept()  # 接受关闭事件
                    self.logger.info("用户选择保存并关闭")
                except Exception as e:
                    # 保存失败，让用户选择
                    retry_reply = QMessageBox.question(
                        self,
                        '保存失败',
                        f'保存文件失败: {str(e)}\n是否不保存直接退出？',
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if retry_reply == QMessageBox.Yes:
                        event.accept()
                    else:
                        event.ignore()  # 忽略关闭事件
                        self.logger.info("用户取消关闭")
            elif reply == QMessageBox.Discard:
                # 不保存直接退出
                event.accept()
                self.logger.info("用户选择不保存直接关闭")
            else:
                # 取消关闭
                event.ignore()
                self.logger.info("用户取消关闭操作")
        else:
            # 没有未保存的更改，直接关闭
            event.accept()
            self.logger.info("无未保存更改，直接关闭")

    def _has_unsaved_changes(self) -> bool:
        """检查是否有未保存的更改"""
        try:
            # 如果有当前文件，检查是否修改过
            # 这里简化处理：只要画布有内容就认为可能有未保存更改
            # 实际应用中可以根据需要实现更精确的修改检测

            # 检查画布是否有内容（排除工作区网格和定位点）
            has_content = False

            for item in self.whiteboard.canvas.scene.items():
                # 跳过工作区网格
                if hasattr(self.whiteboard.canvas, '_work_item') and item == self.whiteboard.canvas._work_item:
                    continue

                # 跳过定位点
                if hasattr(self.whiteboard.canvas, 'fiducial_manager'):
                    fiducial_manager = self.whiteboard.canvas.fiducial_manager
                    fiducial_item = fiducial_manager.get_fiducial_item() if fiducial_manager else None
                    if fiducial_item and item == fiducial_item:
                        continue

                # 如果有任何图形项或图片项，认为有内容
                if (hasattr(item, '_points') or  # 路径项
                        hasattr(item, 'pixmap') or  # 图片项
                        isinstance(item, QGraphicsPixmapItem)):
                    has_content = True
                    break

            # 如果有内容且没有关联文件，或者有内容且文件是新创建的，认为有未保存更改
            if has_content and (not hasattr(self, 'current_file') or self.current_file is None):
                return True

            # 这里可以添加更复杂的修改检测逻辑
            # 例如：记录初始状态，比较当前状态与保存状态

            return False

        except Exception as e:
            self.logger.error(f"检查未保存更改时出错: {e}")
            # 出错时保守处理，提示用户保存
            return True