#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口类
"""
import os
from typing import List

from PIL import Image
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon, QKeySequence, QColor, QPalette
from PyQt5.QtWidgets import (QMainWindow, QAction, QToolBar, QHBoxLayout, QWidget, QLabel, QFileDialog, QMessageBox,
                             QLineEdit, QGraphicsPixmapItem, QDialog)

from my_io.importers.supported_filter import SUPPORTED_FILTER
from ui.left_toolbar import LeftToolbar
from ui.node_edit_toolbar import NodeEditToolbar
from ui.right_panel import RightPanel
from ui.whiteboard import WhiteboardWidget
from utils.import_utils import pil_to_qpixmap, convert_wbmp_to_png
from utils.logging_utils import setup_logging
from utils.tool_utils import check_required_tools
from ui.whiteboard import Path
from my_io.gcode.gcode_exporter import export_to_nc, get_default_config, GCodeExporter
from ui.lead_line_dialog import LeadLineDialog
from ui.preview_dialog import PreviewDialog

from ui.smooth_curve_dialog import SmoothCurveSimpleDialog, SmoothCurveCustomDialog, chaikin_smooth
from ui.auto_close_dialog import AutoCloseDialog
from ui.data_check_dialog import DataCheckDialog
from ui.bitmap_process_dialog import BitmapProcessDialog
from ui.fillet_dialog import FilletDialog
from ui.graphics_items import EditablePathItem
from edit.commands import SmoothItemCommand

from ui.manufacturer_settings_dialog import ManufacturerPasswordDialog, ManufacturerSettingsDialog
from ui.system_settings_dialog import SystemSettingsDialog
from utils.language_manager import language_manager
from ui.graphics_items import EditablePathItem, EditableEllipseItem, TextGraphicsItem
from PyQt5.QtWidgets import QMessageBox
from ui.array_copy_dialog import ArrayCopyDialog
from edit.commands import AddItemCommand, MacroCommand, FilletCommand
import copy

class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        # --------------------- 初始化编辑菜单动作变量 ---------------------
        self.undo_action = None
        self.redo_action = None
        self.cut_action = None
        self.copy_action = None
        self.paste_action = None
        self.delete_action = None
        self.select_all_action = None
        self._updating_path = False

        self.logger = setup_logging()
        self.logger.info("MainWindow初始化开始")
        self.init_ui()  # 调用 init_ui()，内部会通过 create_central_widget() 创建布局
        check_required_tools(self)

        # -------------------------- 删除重复的布局代码！ --------------------------
        # 以下代码全部删除（因为 create_central_widget() 已经完成了同样的工作）
        # ------------------------------------------------------------------------------

        self.logger.info("MainWindow初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('激光加工控制系统')
        self.setGeometry(50, 50, 1600, 950)

        # 设置窗口样式
        self.setup_style()

        # 创建中心区域（左中右布局）
        self.create_central_widget()

        # 创建菜单栏
        self.create_menu_bar()

        # 创建工具栏（三行）
        self.create_toolbars()

        # 状态栏
        # self.show_status_message('就绪')  # Removed: managed by status_label

        # 状态信息标签（替代 showMessage 的常驻显示）
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.statusBar().addWidget(self.status_label, 0) # stretch=0，只占需要的空间

        # 坐标显示标签
        self.coord_label = QLabel("X: 0.000 Y: 0.000 mm")
        self.coord_label.setMinimumWidth(200)
        self.coord_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.statusBar().addWidget(self.coord_label, 0) # stretch=0，紧跟在status_label后面

        # 测量信息标签
        self.measure_label = QLabel("W: 0.00 mm  H: 0.00 mm")
        # QFrame.Sunken = 48, QFrame.StyledPanel = 6
        # self.measure_label.setFrameStyle(54) 
        self.measure_label.setStyleSheet("QLabel { color : blue; }") # 蓝色文字以区分
        self.measure_label.setMinimumWidth(150)
        self.measure_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.statusBar().addWidget(self.measure_label, 0) # stretch=0，在坐标后面

        # 添加一个弹簧占位符，把前面两个挤到左边
        spacer = QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.statusBar().addWidget(spacer, 1) # stretch=1，占据剩余空间
        
        # 连接信号
        self.whiteboard.canvas.headMoved.connect(self.update_mouse_coordinates)
        self.whiteboard.canvas.measurementChanged.connect(self.measure_label.setText)
        self.whiteboard.canvas.scene.changed.connect(self.on_scene_changed)
        # 连接右侧面板的图层参数变化信号，以便更新路径预览
        self.right_panel.layerParamsChanged.connect(self.on_scene_changed)

        # -------------------------- 关键：连接编辑管理器信号 --------------------------
        em = self.whiteboard.canvas.edit_manager
        em.undoAvailable.connect(self.undo_action.setEnabled)
        em.redoAvailable.connect(self.redo_action.setEnabled)
        em.cutCopyAvailable.connect(lambda b: (self.cut_action.setEnabled(b), self.copy_action.setEnabled(b)))
        em.deleteAvailable.connect(self.delete_action.setEnabled)
        em.selectAllAvailable.connect(self.select_all_action.setEnabled)
        # 历史列表更新
        try:
            em.historyChanged.connect(self.right_panel.update_history)
        except Exception:
            pass

        # +++ 新增：初始化时禁用编辑操作 +++
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.cut_action.setEnabled(False)
        self.copy_action.setEnabled(False)
        self.delete_action.setEnabled(False)
        # 全选在没有内容时也应该禁用
        self.select_all_action.setEnabled(False)

        self.current_file = None

        # 连接右侧历史面板的交互（双击跳转、按钮）
        try:
            hl = self.right_panel.history_list
            hl.itemDoubleClicked.connect(lambda item: self._on_history_item_activated(item))
            self.right_panel.history_jump_btn.clicked.connect(lambda: self._on_history_jump())
            self.right_panel.history_clear_btn.clicked.connect(lambda: self._on_history_clear())
        except Exception:
            pass

    def open_laser_window(self):
        """打开激光控制界面"""
        try:
            import sys
            import os
            # Ensure root dir is in path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(current_dir)
            if root_dir not in sys.path:
                sys.path.append(root_dir)
                
            from laser import LaserImageGcodeSender
            
            # Keep reference to prevent garbage collection
            self.laser_window = LaserImageGcodeSender()
            self.laser_window.show()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开激光控制界面: {str(e)}")

    def show_status_message(self, message, timeout=0):
        """
        显示状态信息。
        如果是临时信息（timeout > 0），使用 statusBar().showMessage（会覆盖 widgets）。
        如果是永久信息（timeout == 0），更新 status_label（与坐标共存）。
        """
        if timeout > 0:
            # 使用 QMainWindow 提供的 showMessage 显示临时信息，避免递归调用
            self.statusBar().showMessage(message, int(timeout))
        else:
            self.status_label.setText(message)
            # 确保清除可能存在的临时消息，以便显示永久消息
            self.statusBar().clearMessage()

    def update_mouse_coordinates(self, x, y):
        """更新状态栏鼠标坐标显示"""
        # 检查是否为离开信号
        if x == float('inf') or y == float('inf'):
            self.coord_label.setText("")
        else:
            # 根据原点位置转换坐标
            try:
                canvas = self.whiteboard.canvas
                loc = getattr(canvas, '_origin_location', 1)
                w = getattr(canvas, '_work_w', 0.0)
                h = getattr(canvas, '_work_h', 0.0)
                
                disp_x, disp_y = x, y
                
                if loc == 2: # TR (Top-Right)
                    disp_x = w - x
                elif loc == 3: # BL (Bottom-Left)
                    disp_y = h - y
                elif loc == 4: # BR (Bottom-Right)
                    disp_x = w - x
                    disp_y = h - y
                    
                self.coord_label.setText(f"X: {disp_x:.3f}  Y: {disp_y:.3f} mm")
            except Exception:
                self.coord_label.setText(f"X: {x:.3f}  Y: {y:.3f} mm")

    def on_scene_changed(self, region):
        """场景变化时更新路径预览"""
        if self.show_path_action.isChecked() and not self._updating_path:
            self.toggle_show_path()

    def _on_history_item_activated(self, item):
        try:
            row = self.right_panel.history_list.row(item)
            # 用户希望跳转到包含该项的状态 -> target_index = row + 1
            self.whiteboard.canvas.edit_manager.go_to(row + 1)
        except Exception:
            pass

    def _on_history_jump(self):
        try:
            row = self.right_panel.history_list.currentRow()
            if row >= 0:
                self.whiteboard.canvas.edit_manager.go_to(row + 1)
        except Exception:
            pass

    def _on_history_clear(self):
        try:
            self.whiteboard.canvas.edit_manager.clear_history()
        except Exception:
            pass

    def setup_style(self):
        """设置应用程序样式"""
        # 设置调色板
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, QColor(50, 50, 50))
        self.setPalette(palette)

    def open_manufacturer_settings(self):
        """打开厂家设置"""
        try:
            pwd_dialog = ManufacturerPasswordDialog(self)
            if pwd_dialog.exec_() == QDialog.Accepted:
                settings_dialog = ManufacturerSettingsDialog(self)
                settings_dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开厂家设置失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def common_gallery(self):
        QMessageBox.information(self, "功能未实现", "常用图库功能尚未实现")

    def import_background_image(self):
        # 简单实现导入底图逻辑，或者提示
        file_path, _ = QFileDialog.getOpenFileName(self, "导入底图", "", "Images (*.png *.jpg *.bmp)")
        if file_path:
             QMessageBox.information(self, "提示", f"已选择底图: {file_path}\n(功能开发中)")
             # 如果有 clear_bg_action 可以在这里启用
             if hasattr(self, 'clear_bg_action'):
                 self.clear_bg_action.setEnabled(True)

    def clear_background_image(self):
         QMessageBox.information(self, "提示", "底图已清除")
         if hasattr(self, 'clear_bg_action'):
             self.clear_bg_action.setEnabled(False)

    def get_scanned_image(self):
        QMessageBox.information(self, "功能未实现", "扫描功能需要硬件支持")

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 将菜单保存为实例变量，以便后续更新文本
        self.file_menu = menubar.addMenu('文件(F)')
        
        self.new_action = QAction('新建(&N)...', self)
        self.new_action.setShortcut(QKeySequence.New)
        self.new_action.triggered.connect(self.new_file)
        self.file_menu.addAction(self.new_action)

        self.open_action = QAction('打开(&O)...', self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_file)
        self.file_menu.addAction(self.open_action)

        self.save_action = QAction('保存(&S)', self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_file)
        self.file_menu.addAction(self.save_action)

        self.save_as_action = QAction('另存为(&A)...', self)
        self.save_as_action.triggered.connect(self.save_as_file)
        self.file_menu.addAction(self.save_as_action)

        self.file_menu.addSeparator()

        self.import_action = QAction('导入(&I)...', self)
        self.import_action.setShortcut("Ctrl+I")
        self.import_action.triggered.connect(self.import_image)
        self.file_menu.addAction(self.import_action)

        self.export_action = QAction('导出(&E)...', self)
        self.export_action.setShortcut("Ctrl+E")
        self.export_action.triggered.connect(self.export_to_nc) 
        self.file_menu.addAction(self.export_action)

        gallery_action = QAction('常用图库', self) # 暂未翻译
        gallery_action.triggered.connect(self.common_gallery)
        self.file_menu.addAction(gallery_action)

        self.file_menu.addSeparator()

        self.import_bg_action = QAction('导入底图', self)
        self.import_bg_action.triggered.connect(self.import_background_image)
        self.file_menu.addAction(self.import_bg_action)

        self.clear_bg_action = QAction('清除底图', self)
        self.clear_bg_action.triggered.connect(self.clear_background_image)
        self.clear_bg_action.setEnabled(False) 
        self.file_menu.addAction(self.clear_bg_action)

        self.file_menu.addSeparator()

        self.scan_action = QAction('获取扫描图象', self)
        self.scan_action.setShortcut("Ctrl+8")
        self.scan_action.triggered.connect(self.get_scanned_image)
        self.file_menu.addAction(self.scan_action)

        self.file_menu.addSeparator()

        self.manu_settings_action = QAction('厂家设置', self)
        self.manu_settings_action.triggered.connect(self.open_manufacturer_settings)
        self.file_menu.addAction(self.manu_settings_action)

        self.file_menu.addSeparator()
        
        # ... recent files ...

        self.file_menu.addSeparator()

        self.exit_action = QAction('退出(&X)', self)
        self.exit_action.setShortcut("Ctrl+X")
        self.exit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.exit_action)

        # 编辑菜单
        self.edit_menu = menubar.addMenu('编辑(E)')

        # 定义为实例变量，方便后续连接信号
        self.undo_action = QAction('撤销', self)
        self.undo_action.setShortcut('Ctrl+Z') 
        self.undo_action.triggered.connect(self.whiteboard.canvas.edit_manager.undo)
        self.edit_menu.addAction(self.undo_action)

        self.redo_action = QAction('恢复', self)
        self.redo_action.setShortcut('Ctrl+Y')
        self.redo_action.triggered.connect(self.whiteboard.canvas.edit_manager.redo)
        self.edit_menu.addAction(self.redo_action)

        self.edit_menu.addSeparator()

        self.cut_action = QAction('剪切', self)
        self.cut_action.setShortcut('Ctrl+X')
        self.cut_action.triggered.connect(self.whiteboard.canvas.edit_manager.cut)
        self.edit_menu.addAction(self.cut_action)

        self.copy_action = QAction('复制', self)
        self.copy_action.setShortcut('Ctrl+C')
        self.copy_action.triggered.connect(self.whiteboard.canvas.edit_manager.copy)
        self.edit_menu.addAction(self.copy_action)

        self.paste_action = QAction('粘贴', self)
        self.paste_action.setShortcut('Ctrl+V')
        self.paste_action.triggered.connect(self.whiteboard.canvas.edit_manager.paste)
        self.edit_menu.addAction(self.paste_action)

        self.delete_action = QAction('删除', self)
        self.delete_action.setShortcut('Del')
        self.delete_action.triggered.connect(self.whiteboard.canvas.edit_manager.delete)
        self.edit_menu.addAction(self.delete_action)

        self.edit_menu.addSeparator()
        
        # ... view edit actions (Move, Zoom etc)
        self.move_action = QAction('移动', self)
        self.move_action.triggered.connect(self.set_pan_tool)
        self.edit_menu.addAction(self.move_action)

        self.zoom_in_edit_action = QAction('放大', self)
        self.zoom_in_edit_action.triggered.connect(self.view_zoom_in)
        self.edit_menu.addAction(self.zoom_in_edit_action)

        self.zoom_out_edit_action = QAction('缩小', self)
        self.zoom_out_edit_action.triggered.connect(self.view_zoom_out)
        self.edit_menu.addAction(self.zoom_out_edit_action)

        self.box_zoom_action = QAction('框选查看', self)
        self.box_zoom_action.triggered.connect(self.set_box_zoom_tool)
        self.edit_menu.addAction(self.box_zoom_action)

        self.page_range_action = QAction('页面范围', self)
        self.page_range_action.triggered.connect(self.zoom_to_page)
        self.edit_menu.addAction(self.page_range_action)

        self.data_range_action = QAction('数据范围', self)
        self.data_range_action.triggered.connect(self.zoom_to_data)
        self.edit_menu.addAction(self.data_range_action)

        self.show_all_action = QAction('显示所有', self)
        self.show_all_action.triggered.connect(self.zoom_to_all)
        self.edit_menu.addAction(self.show_all_action)

        self.preview_action = QAction('加工预览', self)
        self.preview_action.triggered.connect(self.show_preview_dialog)
        self.edit_menu.addAction(self.preview_action)

        self.edit_menu.addSeparator()

        # Group 4: 路径设置
        self.show_path_action_menu = QAction('显示路径', self)
        self.show_path_action_menu.setCheckable(True)
        self.show_path_action_menu.setChecked(False)
        self.show_path_action_menu.triggered.connect(self.toggle_show_path)
        self.edit_menu.addAction(self.show_path_action_menu)

        self.set_lead_action = QAction('设置引入引出', self)
        self.set_lead_action.triggered.connect(self.set_lead_line)
        self.edit_menu.addAction(self.set_lead_action)
        
        # ... other edit actions

        self.edit_menu.addSeparator()

        # Group 5: 选择
        self.select_all_action = QAction('选择全部', self)
        self.select_all_action.setShortcut('Ctrl+A')
        self.select_all_action.triggered.connect(self.whiteboard.canvas.edit_manager.select_all)
        self.edit_menu.addAction(self.select_all_action)
        
        # ... select similar actions ...

        self.edit_menu.addSeparator()
        
        # ========== 绘制菜单 (根据截图更新) ==========
        self.draw_menu = menubar.addMenu('绘制(D)')
        
        # 1. 选择工具
        self.select_action = QAction('选择', self)
        self.select_action.setCheckable(True)
        self.select_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_SELECT))
        self.draw_menu.addAction(self.select_action)

        # 2. 节点编辑
        self.node_edit_action = QAction('节点编辑', self)
        self.node_edit_action.setCheckable(True)
        self.node_edit_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_NODE_EDIT))
        self.draw_menu.addAction(self.node_edit_action)

        # 3. 曲线编辑 (子菜单)
        self.curve_edit_menu = self.draw_menu.addMenu('曲线编辑')
        
        # 定义辅助函数快捷添加，并保存Action引用
        # 注意：这里需要修改辅助函数以返回action并保存
        self.curve_add_node_action = QAction('添加节点', self)
        self.curve_add_node_action.triggered.connect(lambda: self.on_node_edit_action(NodeEditToolbar.ACTION_ADD_NODE))
        self.curve_edit_menu.addAction(self.curve_add_node_action)

        self.curve_del_node_action = QAction('删除节点', self)
        self.curve_del_node_action.triggered.connect(lambda: self.on_node_edit_action(NodeEditToolbar.ACTION_DELETE_NODE))
        self.curve_edit_menu.addAction(self.curve_del_node_action)
        
        self.curve_edit_menu.addSeparator()
        
        self.curve_connect_action = QAction('连接节点', self)
        self.curve_connect_action.triggered.connect(lambda: self.on_node_edit_action(NodeEditToolbar.ACTION_CONNECT_NODES))
        self.curve_edit_menu.addAction(self.curve_connect_action)

        self.curve_break_action = QAction('分割曲线', self)
        self.curve_break_action.triggered.connect(lambda: self.on_node_edit_action(NodeEditToolbar.ACTION_BREAK_CURVE))
        self.curve_edit_menu.addAction(self.curve_break_action)
        
        self.curve_edit_menu.addSeparator()
        
        self.curve_to_curve_action = QAction('直线转曲线', self)
        self.curve_to_curve_action.triggered.connect(lambda: self.on_node_edit_action(NodeEditToolbar.ACTION_TO_CURVE))
        self.curve_edit_menu.addAction(self.curve_to_curve_action)

        self.curve_to_line_action = QAction('曲线转直线', self)
        self.curve_to_line_action.triggered.connect(lambda: self.on_node_edit_action(NodeEditToolbar.ACTION_TO_LINE))
        self.curve_edit_menu.addAction(self.curve_to_line_action)

        # 初始状态设为可用
        self.curve_edit_menu.setEnabled(True)

        self.draw_menu.addSeparator()

        # 4. 绘图工具
        self.line_action = QAction('直线', self)
        self.line_action.setCheckable(True)
        self.line_action.setShortcut('Ctrl+1')
        self.line_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_LINE))
        self.draw_menu.addAction(self.line_action)

        self.poly_action = QAction('折线', self)
        self.poly_action.setCheckable(True)
        self.poly_action.setShortcut('Ctrl+2')
        self.poly_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_POLYLINE))
        self.draw_menu.addAction(self.poly_action)

        self.curve_action = QAction('曲线', self)
        self.curve_action.setCheckable(True)
        self.curve_action.setShortcut('Ctrl+3')
        self.curve_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_CURVE))
        self.draw_menu.addAction(self.curve_action)

        self.rect_action = QAction('矩形', self)
        self.rect_action.setCheckable(True)
        self.rect_action.setShortcut('Ctrl+4')
        self.rect_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_RECTANGLE))
        self.draw_menu.addAction(self.rect_action)

        self.ellipse_action = QAction('椭圆', self)
        self.ellipse_action.setCheckable(True)
        self.ellipse_action.setShortcut('Ctrl+5')
        self.ellipse_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_ELLIPSE))
        self.draw_menu.addAction(self.ellipse_action)

        self.text_action = QAction('文本', self)
        self.text_action.setCheckable(True)
        self.text_action.setShortcut('Ctrl+6')
        self.text_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_TEXT))
        self.draw_menu.addAction(self.text_action)

        self.point_action = QAction('点', self)
        self.point_action.setCheckable(True)
        self.point_action.setShortcut('Ctrl+7')
        self.point_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_POINT))
        self.draw_menu.addAction(self.point_action)

        # 倒圆角
        self.fillet_action = QAction('倒圆角', self)
        self.fillet_action.triggered.connect(self.show_fillet_dialog)
        self.draw_menu.addAction(self.fillet_action)

        # 加码齿
        self.gear_action = QAction('加码齿', self)
        self.gear_action.triggered.connect(self.show_gear_dialog)
        self.draw_menu.addAction(self.gear_action)

        self.draw_menu.addSeparator()

        # 5. 编辑操作
        # ...

        self.draw_menu.addSeparator()

        # 6. 镜像与停靠
        self.h_mirror_action = QAction('水平镜像', self)
        self.h_mirror_action.setCheckable(True)
        self.h_mirror_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_H_MIRROR))
        self.draw_menu.addAction(self.h_mirror_action)

        self.v_mirror_action = QAction('垂直镜像', self)
        self.v_mirror_action.setCheckable(True)
        self.v_mirror_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_V_MIRROR))
        self.draw_menu.addAction(self.v_mirror_action)

        self.dock_action = QAction('图形停靠', self)
        self.dock_action.setCheckable(True)
        self.dock_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_DOCK))
        self.draw_menu.addAction(self.dock_action)

        self.array_action = QAction('阵列复制', self)
        self.array_action.setCheckable(True)
        self.array_action.triggered.connect(lambda: self._set_tool_from_menu(LeftToolbar.TOOL_ARRAY))
        self.draw_menu.addAction(self.array_action)

        self.draw_menu.addSeparator()

        # 7. 对齐菜单
        self.align_menu = self.draw_menu.addMenu('对齐')
        
        # 获取 edit_manager 引用
        align_em = self.whiteboard.canvas.edit_manager
        
        # 需要修改 addAction 为 QAction 实例，才能翻译
        self.align_left_action = model_action = QAction('左对齐', self)
        model_action.triggered.connect(lambda: align_em.align_items('left'))
        self.align_menu.addAction(model_action)
        
        self.align_right_action = model_action = QAction('右对齐', self)
        model_action.triggered.connect(lambda: align_em.align_items('right'))
        self.align_menu.addAction(model_action)
        
        self.align_top_action = model_action = QAction('顶端对齐', self)
        model_action.triggered.connect(lambda: align_em.align_items('top'))
        self.align_menu.addAction(model_action)

        self.align_bottom_action = model_action = QAction('底端对齐', self)
        model_action.triggered.connect(lambda: align_em.align_items('bottom'))
        self.align_menu.addAction(model_action)

        self.align_hcenter_action = model_action = QAction('水平居中对齐', self)
        model_action.triggered.connect(lambda: align_em.align_items('hcenter'))
        self.align_menu.addAction(model_action)

        self.align_vcenter_action = model_action = QAction('垂直居中对齐', self)
        model_action.triggered.connect(lambda: align_em.align_items('vcenter'))
        self.align_menu.addAction(model_action)
        
        self.align_page_center_action = model_action = QAction('在页面居中', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('center'))
        self.align_menu.addAction(model_action)
        
        self.align_menu.addSeparator() # 分隔符不需要翻译
        
        self.align_eq_h_action = model_action = QAction('等水平间距', self)
        model_action.triggered.connect(lambda: align_em.distribute_items('horizontal'))
        self.align_menu.addAction(model_action)

        self.align_eq_v_action = model_action = QAction('等垂直间距', self)
        model_action.triggered.connect(lambda: align_em.distribute_items('vertical'))
        self.align_menu.addAction(model_action)
        
        self.align_eq_w_action = model_action = QAction('等宽', self)
        model_action.triggered.connect(lambda: align_em.make_same_size('width'))
        self.align_menu.addAction(model_action)

        self.align_eq_h_size_action = model_action = QAction('等高', self)
        model_action.triggered.connect(lambda: align_em.make_same_size('height'))
        self.align_menu.addAction(model_action)

        self.align_eq_size_action = model_action = QAction('等大小', self)
        model_action.triggered.connect(lambda: align_em.make_same_size('size'))
        self.align_menu.addAction(model_action)
        
        self.align_menu.addSeparator()
        
        self.align_tl_action = model_action = QAction('左上', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('top_left'))
        self.align_menu.addAction(model_action)

        self.align_tr_action = model_action = QAction('右上', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('top_right'))
        self.align_menu.addAction(model_action)

        self.align_br_action = model_action = QAction('右下', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('bottom_right'))
        self.align_menu.addAction(model_action)

        self.align_bl_action = model_action = QAction('左下', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('bottom_left'))
        self.align_menu.addAction(model_action)
        
        self.align_menu.addSeparator()
        
        self.align_dock_l_action = model_action = QAction('靠左', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('left'))
        self.align_menu.addAction(model_action)

        self.align_dock_r_action = model_action = QAction('靠右', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('right'))
        self.align_menu.addAction(model_action)

        self.align_dock_t_action = model_action = QAction('靠上', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('top'))
        self.align_menu.addAction(model_action)

        self.align_dock_b_action = model_action = QAction('靠下', self)
        model_action.triggered.connect(lambda: align_em.align_to_page('bottom'))
        self.align_menu.addAction(model_action)

        # 设置菜单
        self.settings_menu = menubar.addMenu('设置(S)')
        
        self.sys_setting_action = QAction('系统设置', self)
        self.sys_setting_action.triggered.connect(self.open_system_settings)
        self.settings_menu.addAction(self.sys_setting_action)
        
        self.settings_menu.addSeparator()

        self.pwd_setting_action = QAction('密码设置', self)
        self.pwd_setting_action.triggered.connect(self.open_manufacturer_settings)
        self.settings_menu.addAction(self.pwd_setting_action)
        
        self.settings_menu.addSeparator()

        self.dock_point_setting_action = QAction('停靠点设置', self)
        self.dock_point_setting_action.setEnabled(False) # 暂未实现
        self.settings_menu.addAction(self.dock_point_setting_action)
        
        self.settings_menu.addSeparator()

        self.fill_scan_action = QAction('填充扫描图形', self)
        self.fill_scan_action.setEnabled(False) # 暂未实现
        self.settings_menu.addAction(self.fill_scan_action)

        self.show_array_action = QAction('显示阵列', self)
        self.show_array_action.setCheckable(True)
        self.show_array_action.setChecked(True)
        self.settings_menu.addAction(self.show_array_action)

        # 处理菜单
        self.process_menu = menubar.addMenu('处理(W)')
        
        # 保存处理菜单项
        self.process_curve_auto_close_action = add_process_action = QAction('曲线自动闭合', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        self.process_bitmap_handle_action = add_process_action = QAction('位图处理', self)
        add_process_action.triggered.connect(self.show_bitmap_process_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_curve_smooth_action = add_process_action = QAction('曲线平滑', self)
        add_process_action.triggered.connect(self.show_smooth_curve_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_path_optimize_action = add_process_action = QAction('路径优化', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        self.process_merge_lines_action = add_process_action = QAction('合并相连线', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        self.process_del_dup_lines_action = add_process_action = QAction('删除重线', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        self.process_gen_parallel_action = add_process_action = QAction('生成平行线', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        self.process_data_check_action = add_process_action = QAction('数据检查', self)
        add_process_action.triggered.connect(self.show_data_check_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_fill_to_bitmap_action = add_process_action = QAction('填充成位图', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        self.process_bridge_action = add_process_action = QAction('桥位', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        self.process_micro_joint_action = add_process_action = QAction('微连', self)
        add_process_action.setEnabled(False)
        self.process_menu.addAction(add_process_action)

        # 工具菜单
        self.tools_menu = menubar.addMenu('工具(T)')
        
        # Project Cut
        self.tool_project_cut_action = action = QAction('投影切割', self)
        action.setEnabled(False)
        self.tools_menu.addAction(action)

        # Measure
        self.tool_measure_action = action = QAction('测量工具', self)
        action.triggered.connect(self.set_measure_tool)
        self.tools_menu.addAction(action)

        # Auto Nest
        self.tool_auto_nest_action = action = QAction('自动排版', self)
        action.setEnabled(False)
        self.tools_menu.addAction(action)

        # EncLas400G
        self.tool_enclas400g_action = action = QAction('EncLas400G', self)
        action.setEnabled(False)
        self.tools_menu.addAction(action)

        # Mark Point
        self.tool_mark_point_action = action = QAction('Mark点定位', self)
        action.setEnabled(False)
        self.tools_menu.addAction(action)

        # Light Guide
        self.tool_light_guide_action = action = QAction('导光板设计', self)
        action.setEnabled(False)
        self.tools_menu.addAction(action)

        # Add Label
        self.tool_add_label_action = action = QAction('加标签', self)
        action.setEnabled(False)
        self.tools_menu.addAction(action)

        # 主板型号(M) (原主配置)
        self.main_config_menu = menubar.addMenu('主板型号(M)')
        self.main_config_menu.to_ns = "RDLC320-A" # 示例
        action_board = QAction('RDLC320-A', self)
        action_board.setCheckable(True)
        action_board.setChecked(True)
        self.main_config_menu.addAction(action_board)

        # 查看菜单 (原视图)
        # 查看菜单
        self.view_menu = menubar.addMenu('查看(V)')
        
        # 辅助函数：添加可勾选的查看菜单项
        def add_view_action(text, checked=True, callback=None, tr_key=None):
            action = QAction(text, self)
            action.setCheckable(True)
            action.setChecked(checked)
            if callback:
                action.triggered.connect(callback)
            if tr_key:
                action.setProperty('tr_key', tr_key)
            self.view_menu.addAction(action)
            return action

        self.view_sys_toolbar = add_view_action('系统工具栏', True, self.toggle_sys_toolbar, 'View_SysToolbar')
        self.view_status_bar = add_view_action('系统状态栏', True, self.toggle_status_bar, 'View_StatusBar')
        self.view_draw_toolbar = add_view_action('绘制工具栏', True, self.toggle_draw_toolbar, 'View_DrawToolbar')
        self.view_cut_prop_bar = add_view_action('切割属性栏', True, self.toggle_cut_prop_bar, 'View_CutPropBar')
        self.view_align_toolbar = add_view_action('对齐工具栏', True, self.toggle_align_toolbar, 'View_AlignToolbar')
        self.view_color_toolbar = add_view_action('颜色工具栏', True, self.toggle_color_toolbar, 'View_ColorToolbar')
        self.view_sys_workspace = add_view_action('系统工作区', True, self.toggle_sys_workspace, 'View_SysWorkspace')
        self.view_process_ctrl_bar = add_view_action('加工控制栏', True, self.toggle_process_ctrl_bar, 'View_ProcessCtrlBar')
        self.view_add_toolbar = add_view_action('附加工具栏', True, self.toggle_add_toolbar, 'View_AddToolbar')
        
        self.view_menu.addSeparator() 
        
        self.view_lead_io_tool = add_view_action('引入引出工具', False, None, 'View_LeadIOTool')
        self.view_element_name = add_view_action('图元名称', False, None, 'View_ElementName')
        
        self.view_process_toolbar = add_view_action('处理工具栏', True, self.toggle_process_toolbar, 'View_ProcessToolbar')
        self.view_canvas_toolbar = add_view_action('画布工具栏', True, self.toggle_canvas_toolbar, 'View_CanvasToolbar')

        # 帮助菜单
        self.help_menu = menubar.addMenu('帮助(H)')

        self.about_action = QAction('关于', self)
        self.about_action.triggered.connect(self.show_about)
        self.help_menu.addAction(self.about_action)

        self.help_docs_action = QAction('帮助文档', self)
        self.help_docs_action.setShortcut('F1')
        self.help_docs_action.triggered.connect(self.show_help_docs)
        self.help_menu.addAction(self.help_docs_action)

        self.view_log_action = QAction('日志查看', self)
        self.view_log_action.triggered.connect(self.show_logs)
        self.help_menu.addAction(self.view_log_action)

        # Language 子菜单
        self.lang_menu = self.help_menu.addMenu('Language')
        
        # 定义语言列表（按照截图顺序）
        languages = [
            ('简体中文', 'chs'), ('繁体中文', 'cht'), ('英语', 'en'),
            ('日语', 'jp'), ('法语', 'fr'), ('德语', 'de'), 
            ('波兰语', 'pl'), ('葡萄牙语', 'pt'), ('西班牙语', 'es'), ('俄语', 'ru'), ('韩语', 'kr'), 
            ('越南语', 'vn'), ('印尼语', 'id'), ('意大利语', 'it'), ('土耳其语', 'tr'), ('阿拉伯语', 'ar'), ('芬兰语', 'fi')
        ]
        
        self.lang_actions = []
        
        for lang_name, lang_code in languages:
            action = QAction(lang_name, self)
            action.setCheckable(True)
            action.setProperty('lang_code', lang_code)
            
            if lang_code == language_manager.current_lang:
                action.setChecked(True)
                
            self.lang_menu.addAction(action)
            self.lang_actions.append(action)
            
            # 使用闭包连接信号，处理语言切换
            def on_lang_triggered(checked, code=lang_code, act=action):
                if checked:
                     # 取消其他选中
                     for other_act in self.lang_actions:
                         if other_act != act:
                             other_act.setChecked(False)
                     # 切换语言
                     self.switch_language(code)
                else:
                    # 不允许取消所有选中
                    act.setChecked(True)

            # 注意：triggered信号默认传递(checked=False)，所以这里需要用 partial 或者 lambda 包装正确
            # QAction.triggered(checked) is emitted when clicked. checked is bool.
            action.triggered.connect(on_lang_triggered)

        # 社区菜单
        self.community_menu = menubar.addMenu('社区')
        
        def open_browser(url):
            import webbrowser
            webbrowser.open(url)
            
        self.comm_forum_action = QAction('技术论坛', self)
        self.comm_forum_action.triggered.connect(lambda: open_browser('https://www.chanelink.cn/'))
        self.community_menu.addAction(self.comm_forum_action)
        
        self.comm_video_action = QAction('激光视频', self)
        self.comm_video_action.triggered.connect(lambda: open_browser('https://www.chanelink.cn/video'))
        self.community_menu.addAction(self.comm_video_action)
        
        self.comm_vector_action = QAction('切割矢量文件', self)
        self.comm_vector_action.triggered.connect(lambda: open_browser('https://www.chanelink.cn/'))
        self.community_menu.addAction(self.comm_vector_action)
        
        self.comm_app_action = QAction('社区APP', self)
        self.comm_app_action.triggered.connect(lambda: open_browser('https://www.chanelink.com/app_download'))
        self.community_menu.addAction(self.comm_app_action)

        # 初始化翻译
        self.retranslate_ui()
    
    def switch_language(self, lang_code):
        """切换语言"""
        language_manager.load_language(lang_code)
        self.retranslate_ui()
        self.show_status_message(f"Language switched to {lang_code}")

    def retranslate_ui(self):
        """重新设置界面文本（多语言支持）"""
        tr = lambda k, d: language_manager.tr('MainWindow', k, d)
        
        # Menus
        self.file_menu.setTitle(tr('Menu_File', '文件(F)'))
        self.edit_menu.setTitle(tr('Menu_Edit', '编辑(E)'))
        self.draw_menu.setTitle(tr('Menu_Draw', '绘制(D)'))
        self.settings_menu.setTitle(tr('Menu_Settings', '设置(S)'))
        self.process_menu.setTitle(tr('Menu_Process', '处理(W)'))
        self.tools_menu.setTitle(tr('Menu_Tools', '工具(T)'))
        self.main_config_menu.setTitle(tr('Menu_Board', '主板型号(M)'))
        self.view_menu.setTitle(tr('Menu_View', '查看(V)'))
        self.help_menu.setTitle(tr('Menu_Help', '帮助(H)'))
        self.community_menu.setTitle(tr('Menu_Community', '社区'))

        # File actions
        self.new_action.setText(tr('Action_New', '新建(&N)...'))
        self.new_action.setStatusTip(tr('Tip_New', '创建新的RLD文件'))
        self.open_action.setText(tr('Action_Open', '打开(&O)...'))
        self.save_action.setText(tr('Action_Save', '保存(&S)'))
        self.save_as_action.setText(tr('Action_SaveAs', '另存为(&A)...'))
        self.import_action.setText(tr('Action_Import', '导入(&I)...'))
        self.export_action.setText(tr('Action_Export', '导出(&E)...'))
        self.import_bg_action.setText(tr('Action_ImportBg', '导入底图'))
        self.clear_bg_action.setText(tr('Action_ClearBg', '清除底图'))
        self.scan_action.setText(tr('Action_Scan', '获取扫描图象'))
        self.manu_settings_action.setText(tr('Action_ManuSettings', '厂家设置'))
        self.exit_action.setText(tr('Action_Exit', '退出(&X)'))

        # Edit actions
        self.undo_action.setText(tr('Action_Undo', '撤销'))
        self.redo_action.setText(tr('Action_Redo', '恢复'))
        self.cut_action.setText(tr('Action_Cut', '剪切'))
        self.copy_action.setText(tr('Action_Copy', '复制'))
        self.paste_action.setText(tr('Action_Paste', '粘贴'))
        self.delete_action.setText(tr('Action_Delete', '删除'))
        self.select_all_action.setText(tr('Action_SelectAll', '选择全部'))
        self.move_action.setText(tr('Action_Move', '移动'))
        self.zoom_in_edit_action.setText(tr('Action_ZoomIn', '放大'))
        self.zoom_out_edit_action.setText(tr('Action_ZoomOut', '缩小'))
        self.box_zoom_action.setText(tr('Action_BoxZoom', '框选查看'))
        self.page_range_action.setText(tr('Action_PageRange', '页面范围'))
        self.data_range_action.setText(tr('Action_DataRange', '数据范围'))
        self.show_all_action.setText(tr('Action_ShowAll', '显示所有'))
        self.preview_action.setText(tr('Action_Preview', '加工预览'))
        self.show_path_action_menu.setText(tr('Action_ShowPath', '显示路径'))
        self.set_lead_action.setText(tr('Action_SetLead', '设置引入引出'))

        # Draw actions
        self.select_action.setText(tr('Action_Select', '选择'))
        self.node_edit_action.setText(tr('Action_NodeEdit', '节点编辑'))
        self.curve_edit_menu.setTitle(tr('Menu_CurveEdit', '曲线编辑'))
        
        self.line_action.setText(tr('Action_Line', '直线'))
        self.poly_action.setText(tr('Action_Polyline', '折线'))
        self.curve_action.setText(tr('Action_Curve', '曲线'))
        self.rect_action.setText(tr('Action_Rectangle', '矩形'))
        self.ellipse_action.setText(tr('Action_Ellipse', '椭圆'))
        self.text_action.setText(tr('Action_Text', '文本'))
        self.point_action.setText(tr('Action_Point', '点'))
        self.h_mirror_action.setText(tr('Action_HMirror', '水平镜像'))
        self.v_mirror_action.setText(tr('Action_VMirror', '垂直镜像'))
        self.dock_action.setText(tr('Action_Dock', '图形停靠'))
        self.array_action.setText(tr('Action_Array', '阵列复制'))
        self.align_menu.setTitle(tr('Menu_Align', '对齐'))

        # Align actions
        self.align_left_action.setText(tr('Align_Left', '左对齐'))
        self.align_right_action.setText(tr('Align_Right', '右对齐'))
        self.align_top_action.setText(tr('Align_Top', '顶端对齐'))
        self.align_bottom_action.setText(tr('Align_Bottom', '底端对齐'))
        self.align_hcenter_action.setText(tr('Align_HCenter', '水平居中对齐'))
        self.align_vcenter_action.setText(tr('Align_VCenter', '垂直居中对齐'))
        self.align_page_center_action.setText(tr('Align_CenterPage', '在页面居中'))
        self.align_eq_h_action.setText(tr('Align_EqH', '等水平间距'))
        self.align_eq_v_action.setText(tr('Align_EqV', '等垂直间距'))
        self.align_eq_w_action.setText(tr('Align_EqW', '等宽'))
        self.align_eq_h_size_action.setText(tr('Align_EqH_Size', '等高'))
        self.align_eq_size_action.setText(tr('Align_EqSize', '等大小'))
        self.align_tl_action.setText(tr('Align_TopLeft', '左上'))
        self.align_tr_action.setText(tr('Align_TopRight', '右上'))
        self.align_br_action.setText(tr('Align_BottomRight', '右下'))
        self.align_bl_action.setText(tr('Align_BottomLeft', '左下'))
        self.align_dock_l_action.setText(tr('Align_DockLeft', '靠左'))
        self.align_dock_r_action.setText(tr('Align_DockRight', '靠右'))
        self.align_dock_t_action.setText(tr('Align_DockTop', '靠上'))
        self.align_dock_b_action.setText(tr('Align_DockBottom', '靠下'))
        
        # Curve Edit actions
        self.curve_add_node_action.setText(tr('Curve_AddNode', '添加节点'))
        self.curve_del_node_action.setText(tr('Curve_DelNode', '删除节点'))
        self.curve_connect_action.setText(tr('Curve_Connect', '连接节点'))
        self.curve_break_action.setText(tr('Curve_Break', '分割曲线'))
        self.curve_to_curve_action.setText(tr('Curve_ToCurve', '直线转曲线'))
        self.curve_to_line_action.setText(tr('Curve_ToLine', '曲线转直线'))

        # Settings
        self.sys_setting_action.setText(tr('Action_SysSettings', '系统设置'))
        self.pwd_setting_action.setText(tr('Action_PwdSettings', '密码设置'))
        self.dock_point_setting_action.setText(tr('Action_DockPoint', '停靠点设置'))
        self.fill_scan_action.setText(tr('Action_FillScan', '填充扫描图形'))
        self.show_array_action.setText(tr('Action_ShowArray', '显示阵列'))

        # Process
        self.process_curve_auto_close_action.setText(tr('Action_CurveAutoClose', '曲线自动闭合'))
        self.process_bitmap_handle_action.setText(tr('Action_BitmapHandle', '位图处理'))
        self.process_curve_smooth_action.setText(tr('Action_CurveSmooth', '曲线平滑'))
        self.process_path_optimize_action.setText(tr('Action_PathOptimize', '路径优化'))
        self.process_merge_lines_action.setText(tr('Action_MergeLines', '合并相连线'))
        self.process_del_dup_lines_action.setText(tr('Action_DelDupLines', '删除重线'))
        self.process_gen_parallel_action.setText(tr('Action_GenParallel', '生成平行线'))
        self.process_data_check_action.setText(tr('Action_DataCheck', '数据检查'))
        self.process_fill_to_bitmap_action.setText(tr('Action_FillToBitmap', '填充成位图'))
        self.process_bridge_action.setText(tr('Action_Bridge', '桥位'))
        self.process_micro_joint_action.setText(tr('Action_MicroJoint', '微连'))

        # Tools
        self.tool_project_cut_action.setText(tr('Action_ProjectCut', '投影切割'))
        self.tool_measure_action.setText(tr('Action_Measure', '测量工具'))
        self.tool_auto_nest_action.setText(tr('Action_AutoNest', '自动排版'))
        self.tool_enclas400g_action.setText(tr('Action_EncLas400G', 'EncLas400G'))
        self.tool_mark_point_action.setText(tr('Action_MarkPoint', 'Mark点定位'))
        self.tool_light_guide_action.setText(tr('Action_LightGuide', '导光板设计'))
        self.tool_add_label_action.setText(tr('Action_AddLabel', '加标签'))

        # About/Help
        self.about_action.setText(tr('Action_About', '关于'))
        self.help_docs_action.setText(tr('Action_HelpDocs', '帮助文档'))
        self.view_log_action.setText(tr('Action_ViewLog', '日志查看'))
        self.lang_menu.setTitle(tr('Menu_Language', 'Language'))
        self.comm_forum_action.setText(tr('Action_UserForum', '用户论坛')) # Mapped slightly wrong in INI but okay
        self.comm_video_action.setText(tr('Action_LaserVideo', '激光视频'))
        self.comm_vector_action.setText(tr('Action_CutVector', '切割矢量文件'))
        self.comm_app_action.setText(tr('Action_CommunityApp', '社区APP'))
        
        # Update Window Title
        self.setWindowTitle(tr('Title', '激光加工控制系统'))

        # View Menu Actions
        if hasattr(self, 'view_sys_toolbar'):
            self.view_sys_toolbar.setText(tr('View_SysToolbar', '系统工具栏'))
            self.view_status_bar.setText(tr('View_StatusBar', '系统状态栏'))
            self.view_draw_toolbar.setText(tr('View_DrawToolbar', '绘制工具栏'))
            self.view_cut_prop_bar.setText(tr('View_CutPropBar', '切割属性栏'))
            self.view_align_toolbar.setText(tr('View_AlignToolbar', '对齐工具栏'))
            self.view_color_toolbar.setText(tr('View_ColorToolbar', '颜色工具栏'))
            self.view_sys_workspace.setText(tr('View_SysWorkspace', '系统工作区'))
            self.view_process_ctrl_bar.setText(tr('View_ProcessCtrlBar', '加工控制栏'))
            self.view_add_toolbar.setText(tr('View_AddToolbar', '附加工具栏'))
            self.view_lead_io_tool.setText(tr('View_LeadIOTool', '引入引出工具'))
            self.view_element_name.setText(tr('View_ElementName', '图元名称'))
            self.view_process_toolbar.setText(tr('View_ProcessToolbar', '处理工具栏'))
            self.view_canvas_toolbar.setText(tr('View_CanvasToolbar', '画布工具栏'))

        # Update Left Toolbar
        if hasattr(self, 'left_toolbar'):
            self.left_toolbar.retranslate_ui()
            
        # Update Toolbar Actions
        if hasattr(self, 'toolbar_actions_list'):
            for action in self.toolbar_actions_list:
                key = action.property('tr_key')
                default = action.property('default_tooltip')
                text = tr(key, default)
                action.setToolTip(text)
                action.setStatusTip(text)


    def create_toolbars(self):
        """创建三行工具栏"""
        # 第一行工具栏 - toolbar_row1_icons 的所有图标
        self.toolbar1 = QToolBar('工具栏1')
        self.toolbar1.setIconSize(QSize(22, 22))  # 缩小图标尺寸
        self.toolbar1.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar1)

        # 左侧新建和打开按钮
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column1.png', '新建', self.new_file))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column2.png', '打开', self.open_file))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column3.png', '保存', self.save_file))
        self.toolbar1.addSeparator()
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column4.png', '导入', self.import_image, tr_key='Action_Import'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column5.png', '导出', self.export_to_nc, tr_key='Action_Export'))
        self.toolbar1.addSeparator()
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column6.png', '撤销', self.undo, tr_key='Action_Undo'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column7.png', '恢复', self.redo, tr_key='Action_Redo'))
        self.toolbar1.addSeparator()
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column8.png', '平移', self.set_pan_tool, tr_key='Action_Move'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column9.png', '放大', self.view_zoom_in, tr_key='Action_ZoomIn'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column10.png', '缩小', self.view_zoom_out, tr_key='Action_ZoomOut'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column11.png', '页面范围', self.zoom_to_page, tr_key='Action_PageRange'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column12.png', '数据范围', self.zoom_to_data, tr_key='Action_DataRange'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column13.png', '显示所有', self.zoom_to_all, tr_key='Action_ShowAll'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column14.png', '框选查看', self.set_box_zoom_tool, tr_key='Action_BoxZoom'))
        self.toolbar1.addSeparator()
        self.show_path_action = self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column15.png', '显示路径', self.toggle_show_path, is_checkable=True, tr_key='Action_ShowPath')
        self.toolbar1.addAction(self.show_path_action)
        # 连接选择改变信号，以便在选中项改变时更新路径预览
        try:
            self.whiteboard.canvas.scene.selectionChanged.connect(self.toggle_show_path)
        except Exception:
            pass

        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column16.png', '设置引入引出', self.set_lead_line, tr_key='Action_SetLead'))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column17.png', '设置切割属性', self.set_cut_property_tool))
        self.toolbar1.addSeparator()
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column18.png', '加工预览', self.show_preview_dialog, tr_key='Action_Preview'))
        self.toolbar1.addSeparator()
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column19.png', '自动群组', None))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column20.png', '群组', None))
        self.toolbar1.addAction(self.create_tool_action_with_icon('toolbar_row1_icons/icon1_column21.png', '解散群组', None))


        # 第二行工具栏
        self.toolbar2 = QToolBar('工具栏2')
        self.toolbar2.setIconSize(QSize(22, 22))  # 缩小图标尺寸
        self.toolbar2.setMovable(False)
        # 将第二行工具栏放到新的一行
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBarBreak(Qt.TopToolBarArea)

        self.addToolBar(Qt.TopToolBarArea, self.toolbar2)

        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column1.png', '投影切割', self.new_file))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column2.png', '', None))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column3.png', '测量工具', self.set_measure_tool))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column4.png', 'Mark点定位', None))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column5.png', '曲线平滑', self.show_smooth_curve_dialog))
        self.toolbar2.addSeparator()
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column6.png', '位图处理', self.show_bitmap_process_dialog))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column7.png', '曲线自动闭合', self.show_auto_close_dialog))
        self.toolbar2.addSeparator()
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column8.png', '切割优化', self.zoom_in))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column9.png', '合并相连线', self.zoom_out))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column10.png', '删除重线', None))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column11.png', '平行线', self.zoom_reset))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column12.png', '数据检查', self.show_data_check_dialog))
        # 视觉/相机相关工具 (设置为禁用)
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column13.png', '拍照', None)
        action.setEnabled(False)
        self.toolbar2.addAction(action)
        
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column14.png', '框选提边', None)
        action.setEnabled(False)
        self.toolbar2.addAction(action)
        
        self.toolbar2.addSeparator()
        
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column15.png', '提边设置', self.set_cut_property_tool)
        action.setEnabled(False)
        self.toolbar2.addAction(action)
        
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column16.png', '扶正功能', None)
        action.setEnabled(False)
        self.toolbar2.addAction(action)
        
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column17.png', '放置图形', None)
        action.setEnabled(False)
        self.toolbar2.addAction(action)
        
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column18.png', '底图显示', None)
        action.setEnabled(False)
        self.toolbar2.addAction(action)
        
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column19.png', '画布参数设置', None)
        action.setEnabled(False)
        self.toolbar2.addAction(action)

        
        # 新增：激光连接按钮
        self.toolbar2.addSeparator()
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/lianjie.png', '图片处理', self.open_laser_window))

        # 第三行工具栏
        self.toolbar3 = QToolBar('工具栏3')
        self.toolbar3.setIconSize(QSize(25, 25))  # 缩小图标尺寸
        self.toolbar3.setMovable(False)
        self.toolbar3.setMinimumHeight(40)  # 减小最小高度
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar3)

        # 创建属性输入区域
        from PyQt5.QtWidgets import QGridLayout

        properties_widget = QWidget()
        properties_widget.setMinimumHeight(52)  # 进一步减小高度
        properties_widget.setMaximumHeight(52)
        properties_widget.setMaximumWidth(450)
        properties_layout = QGridLayout(properties_widget)
        properties_layout.setContentsMargins(2, 2, 2, 2)  # 减小边距
        properties_layout.setSpacing(2)
        properties_layout.setHorizontalSpacing(3)
        properties_layout.setVerticalSpacing(2)  # 减小垂直间距

        # 第一行
        properties_layout.addWidget(QLabel("X"), 0, 0)
        self.x_input = QLineEdit("0")
        self.x_input.setMaximumWidth(55)
        self.x_input.setMinimumHeight(22)  # 减小输入框高度
        self.x_input.setMaximumHeight(22)
        properties_layout.addWidget(self.x_input, 0, 1)
        properties_layout.addWidget(QLabel("mm"), 0, 2)

        # 宽度图标
        kuandu_icon = QLabel()
        kuandu_icon.setPixmap(QIcon("toolbar_row3_icons/icon3_width.png").pixmap(QSize(18, 18)))
        kuandu_icon.setMaximumWidth(20)
        properties_layout.addWidget(kuandu_icon, 0, 3)

        # 宽度
        self.width_input = QLineEdit("0")
        self.width_input.setMaximumWidth(55)
        self.width_input.setMinimumHeight(22)
        self.width_input.setMaximumHeight(22)
        properties_layout.addWidget(self.width_input, 0, 4)
        properties_layout.addWidget(QLabel("mm"), 0, 5)

        # 百分比
        self.percent_input = QLineEdit("100")
        self.percent_input.setMaximumWidth(55)
        self.percent_input.setMinimumHeight(22)
        self.percent_input.setMaximumHeight(22)
        properties_layout.addWidget(self.percent_input, 0, 6)
        properties_layout.addWidget(QLabel("%"), 0, 7)

        # 第二行
        # Y
        properties_layout.addWidget(QLabel("Y"), 1, 0)
        self.y_input = QLineEdit("0")
        self.y_input.setMaximumWidth(55)
        self.y_input.setMinimumHeight(22)
        self.y_input.setMaximumHeight(22)
        properties_layout.addWidget(self.y_input, 1, 1)
        properties_layout.addWidget(QLabel("mm"), 1, 2)

        # 高度图标（光度）
        gaodu_icon = QLabel()
        gaodu_icon.setPixmap(QIcon("toolbar_row3_icons/icon3_height.png").pixmap(QSize(18, 18)))
        gaodu_icon.setMaximumWidth(20)
        properties_layout.addWidget(gaodu_icon, 1, 3)

        # 高度
        self.height_input = QLineEdit("0")
        self.height_input.setMaximumWidth(55)
        self.height_input.setMinimumHeight(22)
        self.height_input.setMaximumHeight(22)
        properties_layout.addWidget(self.height_input, 1, 4)
        properties_layout.addWidget(QLabel("mm"), 1, 5)

        # 百分比（第二行）
        self.percent_input2 = QLineEdit("100")
        self.percent_input2.setMaximumWidth(55)
        self.percent_input2.setMinimumHeight(22)
        self.percent_input2.setMaximumHeight(22)
        properties_layout.addWidget(self.percent_input2, 1, 6)
        properties_layout.addWidget(QLabel("%"), 1, 7)

        self.toolbar3.addWidget(properties_widget)
        
        # 连接输入框的信号，实现参数化输入
        self.x_input.returnPressed.connect(lambda: self._apply_position_and_size_changes())
        self.y_input.returnPressed.connect(lambda: self._apply_position_and_size_changes())
        self.width_input.returnPressed.connect(lambda: self._apply_position_and_size_changes())
        self.height_input.returnPressed.connect(lambda: self._apply_position_and_size_changes())
        self.percent_input.returnPressed.connect(lambda: self._apply_percent_scale(True))
        self.percent_input2.returnPressed.connect(lambda: self._apply_percent_scale(False))

        # 变换工具
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column1.png', '锁住', None))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column2.png', '选择位置坐标基准', None))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column3.png', '修改尺寸', None))
        self.toolbar3.addSeparator()

        # 使用左侧循环箭头图标作为“按输入角度旋转”的快捷按钮
        try:
            rotate_action = self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column4.png', '按输入角度旋转选中项', None, True)
            self.toolbar3.addAction(rotate_action)
            try:
                rotate_action.triggered.connect(lambda: self.rotate_selected_by_angle())
            except Exception:
                pass
        except Exception:
            # fallback: add original action if creation fails
            self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column4.png', '恢复', None, False))

        # 角度输入框和加工序号输入框（合并到一个widget中，防止全屏时分开）
        from PyQt5.QtWidgets import QSizePolicy

        angle_order_widget = QWidget()
        angle_order_widget.setFixedWidth(230) # 减小固定宽度，使其更紧凑
        angle_order_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        angle_order_layout = QHBoxLayout(angle_order_widget)
        angle_order_layout.setContentsMargins(1, 0, 1, 0) # 减小边距
        angle_order_layout.setSpacing(2) # 减小间距

        # 角度输入框（公开为 self.angle_input）
        self.angle_input = QLineEdit("0")
        self.angle_input.setMaximumWidth(50) # 减小宽度
        self.angle_input.setMinimumHeight(24) # 减小高度
        self.angle_input.setMaximumHeight(24)
        self.angle_input.setAlignment(Qt.AlignCenter)
        angle_order_layout.addWidget(self.angle_input)

        degree_label = QLabel("°")
        degree_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        angle_order_layout.addWidget(degree_label)

        # 角度应用由左侧工具图标触发（或在输入框按回车）

        # 精确旋转按钮（打开对话框，支持增量/绝对）
        from PyQt5.QtWidgets import QPushButton
        precise_btn = QPushButton()
        precise_btn.setToolTip('精确旋转...')
        precise_btn.setFixedSize(22, 22) # 减小按钮尺寸
        try:
            precise_btn.setIcon(QtGui.QIcon('toolbar_row3_icons/xuanzhuan.png'))
            precise_btn.setIconSize(QSize(18, 18))
        except Exception:
            precise_btn.setText('...')
        angle_order_layout.addWidget(precise_btn)

        # 连接信号：按回车或点击左侧工具图标时应用角度旋转；精确按钮打开对话框
        try:
            self.angle_input.returnPressed.connect(lambda: self.rotate_selected_by_angle())
            precise_btn.clicked.connect(lambda: self.open_rotate_dialog())
        except Exception:
            pass

        # 加工序号标签
        order_label = QLabel("加工序号")
        order_label.setStyleSheet("font-size: 12px; font-weight: bold;")  # 加大字体到14px并加粗
        angle_order_layout.addWidget(order_label)

        # 加工序号输入框
        order_input = QLineEdit("0")
        order_input.setMaximumWidth(50) # 减小宽度
        order_input.setMinimumHeight(24) # 减小高度
        order_input.setMaximumHeight(24)
        order_input.setAlignment(Qt.AlignCenter)
        angle_order_layout.addWidget(order_input)

        self.toolbar3.addWidget(angle_order_widget)
        self.toolbar3.addSeparator()  # 在第五个按钮后添加分隔符
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column6.png', '左对齐', lambda: self.whiteboard.canvas.edit_manager.align_items('left')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column7.png', '右对齐', lambda: self.whiteboard.canvas.edit_manager.align_items('right')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column8.png', '顶端对齐', lambda: self.whiteboard.canvas.edit_manager.align_items('top')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column9.png', '底端对齐', lambda: self.whiteboard.canvas.edit_manager.align_items('bottom')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column10.png', '水平居中对齐', lambda: self.whiteboard.canvas.edit_manager.align_items('hcenter')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column11.png', '垂直居中对齐', lambda: self.whiteboard.canvas.edit_manager.align_items('vcenter')))
        self.toolbar3.addSeparator()
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column12.png', '等水平间距 ', lambda: self.whiteboard.canvas.edit_manager.distribute_items('horizontal')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column13.png', '等垂直间距', lambda: self.whiteboard.canvas.edit_manager.distribute_items('vertical')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column14.png', '等宽', lambda: self.whiteboard.canvas.edit_manager.make_same_size('width')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column15.png', '等高', lambda: self.whiteboard.canvas.edit_manager.make_same_size('height')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column16.png', '等大小', lambda: self.whiteboard.canvas.edit_manager.make_same_size('size')))
        self.toolbar3.addSeparator()
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column17.png', '左上', lambda: self.whiteboard.canvas.edit_manager.align_to_page('top_left')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column18.png', '右上', lambda: self.whiteboard.canvas.edit_manager.align_to_page('top_right')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column19.png', '右下', lambda: self.whiteboard.canvas.edit_manager.align_to_page('bottom_right')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column20.png', '左下', lambda: self.whiteboard.canvas.edit_manager.align_to_page('bottom_left')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column21.png', '在页面居中', lambda: self.whiteboard.canvas.edit_manager.align_to_page('center')))
        self.toolbar3.addSeparator()
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column22.png', '移至左边界', lambda: self.whiteboard.canvas.edit_manager.align_to_page('left')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column23.png', '移至右边界', lambda: self.whiteboard.canvas.edit_manager.align_to_page('right')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column24.png', '移至上边界', lambda: self.whiteboard.canvas.edit_manager.align_to_page('top')))
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column25.png', '移至下边界', lambda: self.whiteboard.canvas.edit_manager.align_to_page('bottom')))

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().Expanding, spacer.sizePolicy().Preferred)
        self.toolbar3.addWidget(spacer)

    def create_tool_action(self, icon_text, tooltip, callback):
        """创建工具栏动作（使用文本图标）"""
        action = QAction(icon_text, self)
        action.setToolTip(tooltip)
        action.setStatusTip(tooltip)  # 状态栏显示提示
        if callback:
            action.triggered.connect(callback)
        return action

    def create_tool_action_with_icon(self, icon_path, tooltip, callback, show_tooltip=True, is_checkable=False, tr_key=None):
        """创建工具栏动作（使用真实图标）"""
        action = QAction(self)
        
        # Store translation info
        if tr_key:
            action.setProperty('tr_key', tr_key)
            action.setProperty('default_tooltip', tooltip)
            # Apply initial translation
            tooltip = language_manager.tr('MainWindow', tr_key, tooltip)

        if show_tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)  # 状态栏显示提示

        # 加载图标
        icon = QIcon(icon_path)
        if not icon.isNull():
            action.setIcon(icon)
        else:
            # 如果图标加载失败，使用文本作为备选
            action.setText('?')

        if is_checkable:
            action.setCheckable(True)

        if callback:
            action.triggered.connect(callback)
            
        # Add to the list of toolbar actions to be retranslated later (if needed)
        if not hasattr(self, 'toolbar_actions_list'):
            self.toolbar_actions_list = []
        if tr_key:
            self.toolbar_actions_list.append(action)
            
        return action

    def create_central_widget(self):
        """创建中心部件左中右三栏布局"""
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        from PyQt5.QtWidgets import QSizePolicy

        # 左侧工具栏 (直接放入布局，不放入Splitter以防止压缩)
        self.left_toolbar = LeftToolbar()
        # 强制设置左侧工具栏固定宽度，防止被压缩
        self.left_toolbar.setFixedWidth(50) 
        # 设置适当的 SizePolicy 以确保垂直方向填充但不会撑大父布局
        self.left_toolbar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        main_layout.addWidget(self.left_toolbar, 0)

        # 节点编辑辅助工具栏（默认隐藏，固定宽度）
        self.node_edit_toolbar = NodeEditToolbar()
        self.node_edit_toolbar.setFixedWidth(30)
        self.node_edit_toolbar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        self.node_edit_toolbar.hide()
        main_layout.addWidget(self.node_edit_toolbar, 0)

        from PyQt5.QtWidgets import QSplitter
        from PyQt5.QtCore import Qt as _Qt

        # 使用 QSplitter 管理中间白板和右侧面板
        # 移除了左侧工具栏的Splitter管理，避免左侧工具变形，同时保留右侧面板的可调节性
        self.splitter = QSplitter(_Qt.Horizontal)
        # 为 Splitter 设置 SizePolicy，确保其能正确扩展
        self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 中间白板区域（优先扩展）
        self.whiteboard = WhiteboardWidget()
        self.splitter.addWidget(self.whiteboard)

        # 右侧属性面板
        self.right_panel = RightPanel()
        self.splitter.addWidget(self.right_panel)

        # 初始分配宽度（中, 右）
        # 保证右侧面板可见，根据原比例 1000:420 分配
        self.splitter.setSizes([1000, 420])
        self.splitter.setCollapsible(0, False) # 白板区不可折叠消失

        # 添加 Splitter 到主布局，stretch 系数为 1，确保它占据所有剩余空间
        main_layout.addWidget(self.splitter, 1)
        
        # 将画布引用传递给右侧面板
        self.right_panel.set_canvas(self.whiteboard.canvas)

        self.setCentralWidget(central_widget)

        # 连接左侧工具栏信号
        self.left_toolbar.toolChanged.connect(self.on_tool_changed)
        
        # 连接节点编辑工具栏信号
        self.node_edit_toolbar.actionTriggered.connect(self.on_node_edit_action)
        
        # 连接画布的选中项变化信号，实时更新位置显示
        self.whiteboard.canvas.scene.selectionChanged.connect(self._update_position_display)
        # 同时也更新工具栏状态（镜像、阵列等工具仅在有选中时可用）
        self.whiteboard.canvas.scene.selectionChanged.connect(self.update_toolbar_selection_state)

        # 初始化工具栏状态（默认禁用依赖选择的工具）
        self.update_toolbar_selection_state()
        
        # 创建定时器用于实时更新位置（图形移动时）
        from PyQt5.QtCore import QTimer
        self._position_update_timer = QTimer(self)
        self._position_update_timer.timeout.connect(self._update_position_display)
        self._position_update_timer.setInterval(50)  # 每50ms更新一次
        self._position_update_timer.start()
        # 快捷键：缩放选中项（Ctrl+Shift++ / Ctrl+Shift+-）——若无选中则缩放视图
        try:
            from PyQt5.QtWidgets import QShortcut
            from PyQt5.QtGui import QKeySequence
            from PyQt5.QtCore import Qt

            def _scale_plus():
                self._scale_or_zoom_selected(1.2)

            def _scale_minus():
                self._scale_or_zoom_selected(1.0 / 1.2)

            # 使用明确的 Qt key 常量并设置为 ApplicationShortcut，以优先于菜单快捷键
            sc1 = QShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_Plus), self)
            sc1.setContext(Qt.ApplicationShortcut)
            sc1.activated.connect(_scale_plus)

            sc2 = QShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_Minus), self)
            sc2.setContext(Qt.ApplicationShortcut)
            sc2.activated.connect(_scale_minus)
        except Exception:
            pass

    def on_node_edit_action(self, action_id):
        """处理节点编辑工具栏的动作"""
        # 获取当前场景中处于节点编辑模式的项
        target_item = None
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        from ui.graphics_items import EditablePathItem
        selected_paths = [item for item in selected_items if isinstance(item, EditablePathItem) and getattr(item, '_node_edit_enabled', False)]
        
        # 处理连接节点动作 - 支持跨路径连接
        if action_id == NodeEditToolbar.ACTION_CONNECT_NODES:
            if len(selected_paths) == 2:
                # 尝试连接两个路径
                path1 = selected_paths[0]
                path2 = selected_paths[1]
                nodes1 = list(path1._selected_handle_indices)
                nodes2 = list(path2._selected_handle_indices)
                
                if len(nodes1) == 1 and len(nodes2) == 1:
                    idx1 = nodes1[0]
                    idx2 = nodes2[0]
                    
                    data1 = path1.get_path_data()
                    data2 = path2.get_path_data()
                    
                    pts1 = data1[0]
                    pts2 = data2[0]
                    n1 = len(pts1)
                    n2 = len(pts2)
                    
                    merged_data = None
                    
                    def merge_data(d1, d2):
                        p1, s1, c1 = d1
                        p2, s2, c2 = d2
                        new_pts = p1 + p2
                        new_segs = s1 + [0] + s2
                        new_cps = c1.copy()
                        offset = len(p1)
                        for k, v in c2.items():
                            new_cps[k + offset] = v
                        return (new_pts, new_segs, new_cps)

                    # 1. End of P1 -> Start of P2
                    if idx1 == n1 - 1 and idx2 == 0:
                        merged_data = merge_data(data1, data2)
                    # 2. Start of P1 -> End of P2 (P2 + P1)
                    elif idx1 == 0 and idx2 == n2 - 1:
                        merged_data = merge_data(data2, data1)
                    # 3. End of P1 -> End of P2 (P1 + Rev(P2))
                    elif idx1 == n1 - 1 and idx2 == n2 - 1:
                        rev2 = EditablePathItem.reverse_path_data(data2)
                        merged_data = merge_data(data1, rev2)
                    # 4. Start of P1 -> Start of P2 (Rev(P2) + P1)
                    elif idx1 == 0 and idx2 == 0:
                        rev2 = EditablePathItem.reverse_path_data(data2)
                        merged_data = merge_data(rev2, data1)
                        
                    if merged_data:
                        from edit.commands import MergePathsCommand
                        cmd = MergePathsCommand(self.whiteboard.canvas, path1, path2, merged_data)
                        cmd.redo()
                        self.whiteboard.canvas.edit_manager.push_undo(cmd)
                        # Re-enable node edit for the survivor (path1)
                        path1.enable_node_edit(True)
                        path1._selected_handle_indices.clear()
                        path1._rebuild_handles()
                        return
            elif len(selected_paths) == 1:
                selected_paths[0].connect_selected_nodes()
                return

        # 其他动作仅处理单选（或优先处理第一个）
        if selected_paths:
            target_item = selected_paths[0]
        
        if target_item:
            if action_id == NodeEditToolbar.ACTION_DELETE_NODE:
                target_item.delete_selected_node()
            elif action_id == NodeEditToolbar.ACTION_ADD_NODE:
                target_item.add_node_at_suggestion()
            elif action_id == NodeEditToolbar.ACTION_BREAK_CURVE:
                target_item.break_curve_at_selected_nodes()
            elif action_id == NodeEditToolbar.ACTION_TO_LINE:
                target_item.set_selected_segments_type(False) # 直线
            elif action_id == NodeEditToolbar.ACTION_TO_CURVE:
                target_item.set_selected_segments_type(True)  # 曲线
            elif action_id != NodeEditToolbar.ACTION_CONNECT_NODES: # handled above
                 QMessageBox.information(self, "节点编辑", f"触发动做: {action_id}\n(功能开发中)")
        else:
            # QMessageBox.information(self, "提示", "请先选择处于节点编辑模式的图形")
            pass

    def _set_tool_from_menu(self, tool_id):
        """辅助方法：从菜单设置工具，并同步左侧工具栏状态"""
        # 触发 on_tool_changed 以设置白板工具和状态栏
        self.on_tool_changed(tool_id)
        
        # 同步左侧工具栏按钮状态
        if hasattr(self, 'left_toolbar'):
            for btn in self.left_toolbar.button_group.buttons():
                if btn.property("tool_id") == tool_id:
                    btn.setChecked(True)
                    break

    def update_toolbar_selection_state(self):
        """更新工具栏状态（根据是否有选中项）"""
        try:
            # 获取是否有选中的图形项
            selected = self.whiteboard.canvas.scene.selectedItems()
            has_selection = bool(selected)
            if hasattr(self, 'left_toolbar'):
                self.left_toolbar.update_selection_dependent_tools(has_selection)
        except Exception:
            pass

    def _clone_item(self, item):
        new_item = None
        if isinstance(item, EditablePathItem):
            # args: pts, color, smooth
            new_item = EditablePathItem(item.points(), item.color(), item._smooth)
        elif isinstance(item, EditableEllipseItem):
            # args: cx, cy, rx, ry, color
            rect = item.rect()
            cx = rect.x() + rect.width()/2
            cy = rect.y() + rect.height()/2
            rx = rect.width()/2
            ry = rect.height()/2
            new_item = EditableEllipseItem(cx, cy, rx, ry, item._color)
        elif isinstance(item, TextGraphicsItem):
            # args: text, settings
            new_item = TextGraphicsItem(item.text_data, item.settings)
        
        if new_item:
            # Copy common properties
            new_item.setPos(item.pos())
            new_item.setRotation(item.rotation())
            new_item.setScale(item.scale())
            new_item.setZValue(item.zValue())
            new_item.setTransform(item.transform())
            new_item.setPen(item.pen())
            new_item.setBrush(item.brush())
            
        return new_item

    def _perform_array_copy(self, data, selected_items):
        nx = int(data['x_count'])
        ny = int(data['y_count'])
        dx = float(data['x_interval'])
        dy = float(data['y_interval'])
        
        dir_mode = data['direction_mode']
        order_mode = data['order_mode']

        sx, sy = 1, 1
        # Mapping 4 directions based on typical icon order
        if dir_mode == 0: sx, sy = 1, 1      # 1st Quadrant (Right-Down per screen coords)
        elif dir_mode == 1: sx, sy = 1, -1   # Right-Up
        elif dir_mode == 2: sx, sy = -1, -1  # Left-Up
        elif dir_mode == 3: sx, sy = -1, 1   # Left-Down
        # Adjust mapping if icons are 1=RD, 2=LD, etc. Usually:
        # 1. Right-Down, 2. Left-Down, 3. Left-Up, 4. Right-Up? 
        # Let's stick to standard quadrants or user testing.
        # Assuming: 0: R-D, 1: R-U, 2: L-U, 3: L-D?
        # Actually icons usually rotate clockwise or counter-clockwise.
        # Let's try: 0=RD (Default), 1=LD, 2=LU, 3=RU
        if dir_mode == 0: sx, sy = 1, 1
        elif dir_mode == 1: sx, sy = -1, 1
        elif dir_mode == 2: sx, sy = -1, -1
        elif dir_mode == 3: sx, sy = 1, -1
        
        union_rect = None
        for item in selected_items:
            br = item.sceneBoundingRect()
            if union_rect is None: union_rect = br
            else: union_rect = union_rect.united(br)
                
        if not union_rect: return
        
        # Calculate steps relative to bounding box top-left?
        # Or just relative move.
        # dx is gap. Step = Width + Gap.
        
        width = union_rect.width()
        height = union_rect.height()
        
        step_x = (width + dx) * sx
        step_y = (height + dy) * sy
        
        new_items = []
        macro_cmd = MacroCommand(description="Array Copy")
        scene = self.whiteboard.canvas.scene
        
        # Determine grid execution order
        # We need to generate a list of (i, j) coordinates
        
        grid_coords = []
        
        # Order Mode mapping:
        # 0: X-S (Row priority, Zigzag) -> Right, Left, Right...
        # 1: Y-S (Col priority, Zigzag) -> Down, Up, Down...
        # 2: X-Parallel (Row priority, unidirectional)
        # 3: Y-Parallel (Col priority, unidirectional)
        
        if order_mode == 0: # X-S Zigzag (Row-Major)
            for j in range(ny):
                row_indices = range(nx)
                if j % 2 == 1: 
                    row_indices = reversed(row_indices)
                for i in row_indices:
                    grid_coords.append((i, j))
                    
        elif order_mode == 1: # Y-S Zigzag (Col-Major)
            for i in range(nx):
                col_indices = range(ny)
                if i % 2 == 1:
                    col_indices = reversed(col_indices)
                for j in col_indices:
                    grid_coords.append((i, j))
                    
        elif order_mode == 2: # X-Parallel (Row-Major)
            for j in range(ny):
                for i in range(nx):
                    grid_coords.append((i, j))
                    
        else: # Y-Parallel (Col-Major)
             for i in range(nx):
                for j in range(ny):
                    grid_coords.append((i, j))
        
        # Execute creation
        for i, j in grid_coords:
            if i == 0 and j == 0 and dir_mode == 0:
                 # If origin is at 0,0 and we want to keep original?
                 # Actually array copy usually creates copies including the original position or excluding?
                 # If "Array Copy", usually includes original as one of the N.
                 # If so, we skip creating a NEW one at 0,0, but we should make sure expected count is reached.
                 # If user says 1x1, nothing happens.
                 pass
            
            # Position offset
            ox = i * step_x
            oy = j * step_y
            
            # If (ox, oy) is (0,0), it's the original position.
            # We skip duplication for original items to avoid double stacking.
            if abs(ox) < 0.001 and abs(oy) < 0.001:
                continue

            for item in selected_items:
                clone = self._clone_item(item)
                if clone:
                    # Move relative to original
                    clone.moveBy(ox, oy)
                    scene.addItem(clone)
                    new_items.append(clone)
                    cmd = AddItemCommand(self.whiteboard.canvas, clone)
                    macro_cmd.add_command(cmd)

        if macro_cmd.commands:
            self.whiteboard.canvas.edit_manager.push_undo(macro_cmd)
            # Select new items
            scene.clearSelection()
            for it in new_items:
                it.setSelected(True)


    def on_tool_changed(self, tool_id):
        """左侧工具栏工具切换"""
        # 特殊处理删除工具：如果当前有选中的对象，则直接删除并切回选择工具
        if tool_id == LeftToolbar.TOOL_DELETE:
            # 检查是否有选中的用户图形（排除辅助及背景项）
            selected = self.whiteboard.canvas.get_selected_items() 
            if selected:
                self.whiteboard.delete()
                # 删除完成后自动切回选择工具
                self.left_toolbar.select_tool(LeftToolbar.TOOL_SELECT)
                return

        # 特殊处理图形停靠工具（移动至画布中心）
        if tool_id == LeftToolbar.TOOL_DOCK:
            self.whiteboard.dock_to_center()
            self.left_toolbar.select_tool(LeftToolbar.TOOL_SELECT)
            return

        # 处理阵列复制
        if tool_id == LeftToolbar.TOOL_ARRAY:
            selected = self.whiteboard.canvas.get_selected_items() 
            if not selected:
                QMessageBox.warning(self, "提示", "请选择需要阵列的对象")
                self.left_toolbar.select_tool(LeftToolbar.TOOL_SELECT)
                return
            
            union_rect = None
            for item in selected:
                br = item.sceneBoundingRect()
                if union_rect is None: union_rect = br
                else: union_rect = union_rect.united(br)
            size = (union_rect.width(), union_rect.height()) if union_rect else (0,0)

            # Pass canvas work area
            canvas_w = getattr(self.whiteboard.canvas, '_work_w', 1200.0)
            canvas_h = getattr(self.whiteboard.canvas, '_work_h', 800.0)

            dlg = ArrayCopyDialog(selected_item_size=size, canvas_size=(canvas_w, canvas_h), parent=self)
            if dlg.exec_() == QDialog.Accepted:
                data = dlg.get_data()
                self._perform_array_copy(data, selected)
            
            self.left_toolbar.select_tool(LeftToolbar.TOOL_SELECT)
            return

        # 工具ID映射：LeftToolbar工具ID -> Whiteboard工具ID
        tool_mapping = {
            LeftToolbar.TOOL_SELECT: self.whiteboard.canvas.Tool.SELECT,
            LeftToolbar.TOOL_NODE_EDIT: self.whiteboard.canvas.Tool.NODE_EDIT,
            LeftToolbar.TOOL_LINE: self.whiteboard.canvas.Tool.DRAW_LINE,
            LeftToolbar.TOOL_POLYLINE: self.whiteboard.canvas.Tool.DRAW_POLY,
            LeftToolbar.TOOL_CURVE: self.whiteboard.canvas.Tool.DRAW_CURVE,
            LeftToolbar.TOOL_RECTANGLE: self.whiteboard.canvas.Tool.DRAW_RECT,
            LeftToolbar.TOOL_ELLIPSE: self.whiteboard.canvas.Tool.DRAW_ELLIPSE,
            LeftToolbar.TOOL_TEXT: self.whiteboard.canvas.Tool.DRAW_TEXT,
            LeftToolbar.TOOL_POINT: self.whiteboard.canvas.Tool.DRAW_POINT,
            LeftToolbar.TOOL_GRID: self.whiteboard.canvas.Tool.DRAW_GRID,
            LeftToolbar.TOOL_DELETE: self.whiteboard.canvas.Tool.DELETE,
            LeftToolbar.TOOL_H_MIRROR: self.whiteboard.canvas.Tool.H_MIRROR,
            LeftToolbar.TOOL_V_MIRROR: self.whiteboard.canvas.Tool.V_MIRROR,
            LeftToolbar.TOOL_DOCK: self.whiteboard.canvas.Tool.DOCK,
            # LeftToolbar.TOOL_ARRAY: self.whiteboard.canvas.Tool.ARRAY,
        }

        if tool_id in tool_mapping:
            whiteboard_tool = tool_mapping[tool_id]
            self.whiteboard.set_tool(whiteboard_tool)

            # 更新状态栏提示
            tool_names = {
                LeftToolbar.TOOL_SELECT: "选择工具",
                LeftToolbar.TOOL_NODE_EDIT: "节点编辑工具",
                LeftToolbar.TOOL_LINE: "直线工具",
                LeftToolbar.TOOL_POLYLINE: "折线工具",
                LeftToolbar.TOOL_CURVE: "曲线工具",
                LeftToolbar.TOOL_RECTANGLE: "矩形工具",
                LeftToolbar.TOOL_ELLIPSE: "椭圆工具",
                LeftToolbar.TOOL_TEXT: "文字工具",
                LeftToolbar.TOOL_POINT: "点工具",
                LeftToolbar.TOOL_GRID: "网格工具",
                LeftToolbar.TOOL_DELETE: "删除工具",
                LeftToolbar.TOOL_H_MIRROR: "水平镜像",
                LeftToolbar.TOOL_V_MIRROR: "垂直镜像",
                LeftToolbar.TOOL_DOCK: "图形停靠",
                LeftToolbar.TOOL_ARRAY: "阵列复制",
            }

            if tool_id in tool_names:
                self.show_status_message(f'已选择: {tool_names[tool_id]}')
        
        # 同步更新菜单项的选中状态
        self._update_draw_menu_selection(tool_id)

        # 同步更新曲线编辑菜单的可用性
        # if hasattr(self, 'curve_edit_menu'):
        #    self.curve_edit_menu.setEnabled(tool_id == LeftToolbar.TOOL_NODE_EDIT)

    def _update_draw_menu_selection(self, tool_id):
        """根据当前工具ID更新菜单项选中状态"""
        # 工具ID -> 菜单Action属性名
        action_map = {
            LeftToolbar.TOOL_SELECT: 'select_action',
            LeftToolbar.TOOL_NODE_EDIT: 'node_edit_action',
            LeftToolbar.TOOL_LINE: 'line_action',
            LeftToolbar.TOOL_POLYLINE: 'poly_action',
            LeftToolbar.TOOL_CURVE: 'curve_action',
            LeftToolbar.TOOL_RECTANGLE: 'rect_action',
            LeftToolbar.TOOL_ELLIPSE: 'ellipse_action',
            LeftToolbar.TOOL_TEXT: 'text_action',
            LeftToolbar.TOOL_POINT: 'point_action',
            LeftToolbar.TOOL_H_MIRROR: 'h_mirror_action',
            LeftToolbar.TOOL_V_MIRROR: 'v_mirror_action',
            LeftToolbar.TOOL_DOCK: 'dock_action',
            LeftToolbar.TOOL_ARRAY: 'array_action'
        }
        
        # 先取消所有相关Action的选中状态
        for action_name in action_map.values():
            if hasattr(self, action_name):
                getattr(self, action_name).setChecked(False)
        
        # 选中当前工具对应的Action
        if tool_id in action_map and hasattr(self, action_map[tool_id]):
            getattr(self, action_map[tool_id]).setChecked(True)


            # --- 控制节点编辑工具栏的显示/隐藏 ---
            if tool_id == LeftToolbar.TOOL_NODE_EDIT:
                self.node_edit_toolbar.show()
            else:
                self.node_edit_toolbar.hide()
            # -------------------------------------

            # 特殊工具处理
            if tool_id == LeftToolbar.TOOL_DELETE:
                self.whiteboard.canvas.edit_manager.delete()
                # 删除后自动回到选择工具
                self.left_toolbar.button_group.buttons()[0].setChecked(True)
                self.whiteboard.set_tool(self.whiteboard.canvas.Tool.SELECT)
            # 镜像工具：立即对选中项执行镜像，然后回到选择工具（便于连续点击）
            if tool_id in (LeftToolbar.TOOL_H_MIRROR, LeftToolbar.TOOL_V_MIRROR):
                try:
                    selected = self.whiteboard.canvas.get_selected_items()
                    if selected:
                        from edit.commands import MirrorCommand
                        horizontal = (tool_id == LeftToolbar.TOOL_H_MIRROR)
                        cmd = MirrorCommand(self.whiteboard.canvas, selected, horizontal=horizontal)
                        # 先执行操作再推入历史
                        cmd.redo()
                        self.whiteboard.canvas.edit_manager.push_undo(cmd)
                except Exception:
                    pass
                # 执行后恢复为选择工具，方便用户再次点击镜像按钮执行多次操作
                try:
                    self.left_toolbar.button_group.buttons()[0].setChecked(True)
                except Exception:
                    pass
                self.whiteboard.set_tool(self.whiteboard.canvas.Tool.SELECT)

    def new_file(self):
        """新建RLD文件"""
        reply = QMessageBox.question(self, '新建RLD文件', '是否要清空当前白板并创建新文件？',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.whiteboard.clear()
            self.current_file = None
            self.setWindowTitle('激光加工控制系统 - 新文件')
            self.show_status_message('已创建新RLD文件')
            self.logger.info("创建新RLD文件")

    def show_smooth_curve_dialog(self):
        """显示曲线平滑对话框"""
        # 获取当前选中的项
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要平滑的曲线")
            return
            
        # 过滤出可以平滑的项 (EditablePathItem)
        target_items = [item for item in selected_items if isinstance(item, EditablePathItem)]
        
        if not target_items:
            QMessageBox.warning(self, "提示", "所选对象不支持曲线平滑")
            return
            
        # 如果选中多个，只处理第一个，或者提示不支持多选（简单起见，处理第一个）
        if len(target_items) > 1:
            QMessageBox.information(self, "提示", "检测到多个对象，将仅对第一个选中的曲线进行平滑处理")
            
        target_item = target_items[0]
        original_points = target_item.points()
        
        try:
            # 弹出简单设置对话框
            dlg = SmoothCurveSimpleDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                level = dlg.get_level()
                
                new_points = original_points[:]
                
                if level == "自定义":
                    # 弹出自定义对话框
                    custom_dlg = SmoothCurveCustomDialog(original_points, self)
                    if custom_dlg.exec_() == QDialog.Accepted:
                        new_points, smooth_fit = custom_dlg.get_result()
                        # 使用 Undo Command
                        cmd = SmoothItemCommand(target_item, new_points, smooth_fit)
                        # redo 会自动被调用如果 push 到 stack? 不，通常 push_undo 只是 push
                        # 取决于实现。QundoStack.push 会自动 redo。
                        # 这里 edit_manager.push_undo(cmd) 内部实现看起来是:
                        # self.undo_stack.append(cmd)? No, command pattern usually redo first then add.
                        # 让我们看看 base Command 和 EditManager 
                        # 按照之前 pattern: cmd.redo(); edit_mgr.push_undo(cmd)
                        
                        cmd.redo()
                        self.whiteboard.canvas.edit_manager.push_undo(cmd)
                else:
                    # 预设级别
                    iterations = 0
                    if level == "低":
                        iterations = 1
                    elif level == "中":
                        iterations = 2
                    elif level == "高":
                        iterations = 3
                    
                    if iterations > 0:
                        new_points = chaikin_smooth(original_points, iterations)
                        
                    # 简单模式下默认开启拟合平滑
                    cmd = SmoothItemCommand(target_item, new_points, True)
                    cmd.redo()
                    self.whiteboard.canvas.edit_manager.push_undo(cmd)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"处理平滑曲线时发生错误:\n{str(e)}")

    def show_auto_close_dialog(self):
        """显示曲线自动闭合对话框"""
        # 获取选中项
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要闭合的曲线")
            return
            
        # 过滤EditablePathItem
        target_items = [item for item in selected_items if isinstance(item, EditablePathItem)]
        if not target_items:
            QMessageBox.warning(self, "提示", "所选对象不支持自动闭合")
            return

        # 弹出对话框
        dlg = AutoCloseDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            tolerance, force_close = dlg.get_values()
            
            # 处理选中的曲线
            count = 0
            for item in target_items:
                points = item.points()
                if len(points) < 2:
                    continue
                    
                start_pt = points[0]
                end_pt = points[-1]
                
                # 计算首尾距离
                import math
                dist = math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1])
                
                closed = False
                
                # 如果已经是几何闭合（忽略微小误差），则跳过
                if dist < 1e-9:
                    continue

                if force_close:
                    # 强制闭合模式：无论距离多大都闭合
                    if dist <= tolerance:
                        # 距离很小，优先吸附（修改端点）
                        points[-1] = start_pt
                    else:
                        # 距离较大，添加线段闭合
                        if getattr(item, '_smooth', False):
                            item._straight_close = True
                        points.append(start_pt)
                    closed = True
                else:
                    # 非强制模式：仅当距离小于等于容差时闭合
                    if dist <= tolerance:
                         # 小于容差，闭合（吸附）
                         points[-1] = start_pt
                         closed = True
                    # 大于容差，不处理
                
                if closed:
                    item.set_points(points)
                    count += 1
            
            if count > 0:
                self.show_status_message(f"已自动闭合 {count} 条曲线")
            else:
                self.show_status_message("没有曲线需要闭合")

    def show_data_check_dialog(self):
        """显示数据检查对话框"""
        dlg = DataCheckDialog(self.whiteboard.canvas, self)
        dlg.exec_()

    def show_bitmap_process_dialog(self):
        """显示位图处理对话框"""
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择一张图片")
            return
            
        # 查找图片项 (QGraphicsPixmapItem)
        target_item = None
        for item in selected_items:
            if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                target_item = item
                break
                
        if not target_item:
            QMessageBox.warning(self, "提示", "所选对象不是图片")
            return
            
        try:
            dlg = BitmapProcessDialog(target_item, self)
            if dlg.exec_() == QDialog.Accepted:
                # 应用更改回画布
                processed_img = dlg.get_processed_image()
                
                # Convert PIL Image back to QPixmap
                # ... existing conversion logic ...
                # Re-use the safe logic or implement similar robust conversion here
                # Simplified robust version:
                if processed_img.mode == "1":
                    processed_img = processed_img.convert("L")
                
                if processed_img.mode == "RGB":
                    data = processed_img.tobytes("raw", "RGB")
                    stride = processed_img.width * 3
                    qim = QtGui.QImage(data, processed_img.width, processed_img.height, stride, QtGui.QImage.Format_RGB888)
                elif processed_img.mode == "RGBA":
                    data = processed_img.tobytes("raw", "BGRA")
                    stride = processed_img.width * 4
                    qim = QtGui.QImage(data, processed_img.width, processed_img.height, stride, QtGui.QImage.Format_ARGB32)
                elif processed_img.mode == "L":
                    data = processed_img.tobytes("raw", "L")
                    stride = processed_img.width
                    qim = QtGui.QImage(data, processed_img.width, processed_img.height, stride, QtGui.QImage.Format_Grayscale8)
                else:
                    processed_img = processed_img.convert("RGBA")
                    data = processed_img.tobytes("raw", "BGRA")
                    stride = processed_img.width * 4
                    qim = QtGui.QImage(data, processed_img.width, processed_img.height, stride, QtGui.QImage.Format_ARGB32)
                
                # Copy to safe memory
                qim = qim.copy()
                
                # 恢复 DPI 设置
                if hasattr(dlg, 'get_output_dpi'):
                    dpi_x, dpi_y = dlg.get_output_dpi()
                    if dpi_x and dpi_y:
                        dots_per_meter_x = int(dpi_x / 0.0254)
                        dots_per_meter_y = int(dpi_y / 0.0254)
                        if dots_per_meter_x > 0: qim.setDotsPerMeterX(dots_per_meter_x)
                        if dots_per_meter_y > 0: qim.setDotsPerMeterY(dots_per_meter_y)

                pix = QtGui.QPixmap.fromImage(qim)
                target_item.setPixmap(pix)
                
                # 处理提取的轮廓
                if hasattr(dlg, 'extracted_contours') and dlg.extracted_contours:
                    # ... existing contour logic ...
                    img_pos = target_item.pos()
                    scale_x = target_item.transform().m11()
                    scale_y = target_item.transform().m22()
                    
                    scene_contours = []
                    for contour in dlg.extracted_contours:
                        scene_pts = []
                        for x, y in contour:
                            sx = x * scale_x + img_pos.x()
                            sy = y * scale_y + img_pos.y()
                            scene_pts.append((sx, sy))
                        scene_contours.append(scene_pts)
                    
                    for pts in scene_contours:
                        if len(pts) > 1:
                            self.whiteboard.canvas.add_polyline(pts, color=QtGui.QColor(0, 0, 0))
                            
                    self.show_status_message(f"已生成 {len(scene_contours)} 条轮廓路径")

        except Exception as e:
            self.logger.error(f"Error opening bitmap dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"打开位图处理对话框时发生错误:\n{e}")

    def show_fillet_dialog(self):
        """显示倒圆角对话框并执行倒圆角操作"""
        try:
            dlg = FilletDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                values = dlg.get_values()
                radius = values['radius']
                min_angle = values['min_angle']
                max_angle = values['max_angle']
                mode = values['mode']
                
                if mode == 'manual':
                    self.apply_manual_fillet(radius, min_angle, max_angle)
                elif mode == 'auto':
                    self.apply_auto_fillet(radius, min_angle, max_angle)
        except Exception as e:
            self.logger.error(f"Error in fillet dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"倒圆角操作失败:\n{e}")
    
    def apply_manual_fillet(self, radius, min_angle, max_angle):
        """手动倒圆角：对选中的路径在指定角点处倒圆角"""
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要倒圆角的路径")
            return
        
        from ui.graphics_items import EditablePathItem
        
        filleted_count = 0
        commands = []
        
        for item in selected_items:
            if isinstance(item, EditablePathItem):
                try:
                    # 获取路径点
                    points = item.points()
                    if len(points) < 3:
                        continue
                    
                    # 执行倒圆角
                    new_points = self._fillet_path(points, radius, min_angle, max_angle)
                    if new_points and len(new_points) != len(points):
                        # 创建命令
                        cmd = FilletCommand(item, points, new_points)
                        commands.append(cmd)
                        filleted_count += 1
                except Exception as e:
                    self.logger.error(f"Error applying fillet to item: {e}")
                    continue
        
        if commands:
            # 执行命令
            if len(commands) == 1:
                cmd = commands[0]
                cmd.redo()
                self.whiteboard.canvas.edit_manager.push_undo(cmd)
            else:
                macro_cmd = MacroCommand("倒圆角")
                for cmd in commands:
                    macro_cmd.add_command(cmd)
                macro_cmd.redo()
                self.whiteboard.canvas.edit_manager.push_undo(macro_cmd)
            QMessageBox.information(self, "成功", f"已对 {filleted_count} 条路径进行倒圆角处理")
        else:
            QMessageBox.information(self, "提示", "没有找到可倒圆角的路径")
    
    def apply_auto_fillet(self, radius, min_angle, max_angle):
        """自动倒圆角：对所有路径自动查找符合条件的角点并倒圆角"""
        from ui.graphics_items import EditablePathItem
        
        all_items = []
        for item in self.whiteboard.canvas.scene.items():
            if isinstance(item, EditablePathItem):
                all_items.append(item)
        
        if not all_items:
            QMessageBox.information(self, "提示", "画布中没有路径")
            return
        
        commands = []
        filleted_count = 0
        total_corners = 0
        processed_corners = 0
        
        for item in all_items:
            try:
                points = item.points()
                if len(points) < 3:
                    continue
                
                # 统计角点数量
                num_vertices = len(points)
                # 检查是否闭合
                is_closed = False
                if num_vertices >= 3:
                    import math
                    dist_to_close = math.sqrt((points[0][0] - points[-1][0])**2 + (points[0][1] - points[-1][1])**2)
                    is_closed = dist_to_close < 1e-6
                
                if is_closed:
                    total_corners += num_vertices
                else:
                    total_corners += max(0, num_vertices - 2)  # 开放路径，首尾点不是角点
                
                new_points = self._fillet_path(points, radius, min_angle, max_angle)
                if new_points and len(new_points) != len(points):
                    # 计算实际处理的角点数量（通过点数变化估算）
                    original_segments = len(points) - (0 if is_closed else 1)
                    new_segments = len(new_points) - (0 if is_closed else 1)
                    if new_segments > original_segments:
                        processed_corners += (new_segments - original_segments) // 2  # 粗略估算
                    
                    cmd = FilletCommand(item, points, new_points)
                    commands.append(cmd)
                    filleted_count += 1
            except Exception as e:
                self.logger.error(f"Error applying auto fillet to item: {e}", exc_info=True)
                continue
        
        if commands:
            if len(commands) == 1:
                cmd = commands[0]
                cmd.redo()
                self.whiteboard.canvas.edit_manager.push_undo(cmd)
            else:
                macro_cmd = MacroCommand("自动倒圆角")
                for cmd in commands:
                    macro_cmd.add_command(cmd)
                macro_cmd.redo()
                self.whiteboard.canvas.edit_manager.push_undo(macro_cmd)
            QMessageBox.information(self, "成功", f"已对 {filleted_count} 条路径进行自动倒圆角处理\n总角点数: {total_corners}")
        else:
            QMessageBox.information(self, "提示", "没有找到可倒圆角的路径")
    
    def _fillet_path(self, points, radius, min_angle, max_angle):
        """对路径进行倒圆角处理"""
        import math
        
        if len(points) < 3:
            return points[:]
        
        # 转换为场景坐标（如果需要）
        def get_xy(pt):
            if isinstance(pt, (tuple, list)) and len(pt) >= 2:
                return float(pt[0]), float(pt[1])
            return float(pt.x()), float(pt.y())
        
        # 转换所有点
        pts = [get_xy(p) for p in points]
        
        # 检查路径是否闭合（首尾点距离很近）
        is_closed = False
        had_closure_point = False
        if len(pts) >= 3:
            dist_to_close = math.sqrt((pts[0][0] - pts[-1][0])**2 + (pts[0][1] - pts[-1][1])**2)
            is_closed = dist_to_close < 1e-6
            if is_closed:
                # 避免重复闭合点导致的退化角点
                had_closure_point = True
                pts = pts[:-1]
        
        new_points = []
        
        # 处理每个角点（对于闭合路径，处理所有点；对于开放路径，跳过首尾点）
        num_vertices = len(pts)
        
        # 对于闭合路径，处理所有点；对于开放路径，跳过首尾点
        if is_closed:
            # 闭合路径：处理所有点（包括最后一个点，它连接到第一个点）
            vertex_indices = list(range(num_vertices))
            # 对于闭合路径，不预先添加点，让第一个角点处理时决定起始点
        else:
            # 开放路径：跳过首尾点（它们不是角点）
            vertex_indices = list(range(1, num_vertices - 1))
            # 添加第一个点
            new_points.append(pts[0])
        
        for i in vertex_indices:
            # 确定前一个点、当前点和后一个点
            if is_closed:
                # 闭合路径：使用模运算处理首尾连接
                prev_idx = (i - 1) % num_vertices
                next_idx = (i + 1) % num_vertices
                p0 = pts[prev_idx]
                p1 = pts[i]
                p2 = pts[next_idx]
            else:
                # 开放路径：直接使用相邻索引
                p0 = pts[i - 1]
                p1 = pts[i]
                p2 = pts[i + 1]
            
            # 计算向量（从p1指向p0和p2）
            v1 = (p0[0] - p1[0], p0[1] - p1[1])  # p1 -> p0
            v2 = (p2[0] - p1[0], p2[1] - p1[1])  # p1 -> p2
            
            # 计算向量长度
            len1 = math.sqrt(v1[0]**2 + v1[1]**2)
            len2 = math.sqrt(v2[0]**2 + v2[1]**2)
            
            if len1 < 1e-6 or len2 < 1e-6:
                new_points.append(p1)
                continue
            
            # 归一化向量
            u1 = (v1[0] / len1, v1[1] / len1)  # 从p1指向p0的单位向量
            u2 = (v2[0] / len2, v2[1] / len2)  # 从p1指向p2的单位向量
            
            # 计算夹角（使用点积）
            dot_product = u1[0] * u2[0] + u1[1] * u2[1]
            dot_product = max(-1.0, min(1.0, dot_product))  # 限制在[-1, 1]范围内
            angle = math.acos(dot_product)
            angle_deg = math.degrees(angle)
            
            # 计算叉积以确定路径方向（用于确定圆弧方向）
            cross_product = u1[0] * u2[1] - u1[1] * u2[0]  # 2D叉积
            
            # 计算内角（对于凸角，内角 = angle；对于凹角，内角 = 2π - angle）
            # 通过叉积判断：如果叉积为正，路径是逆时针，内角就是angle；如果叉积为负，路径是顺时针，内角是2π - angle
            # 但更简单的方法：内角就是两个向量之间的夹角，范围是[0, π]
            # 对于倒圆角，我们通常处理的是内角小于180度的角（凸角）
            inner_angle_deg = angle_deg  # 内角（0-180度）
            
            # 检查内角是否在范围内
            # 注意：对于矩形等图形，所有角点都是90度，应该在0-180度范围内
            if inner_angle_deg < min_angle or inner_angle_deg > max_angle:
                # 角度不在范围内，保留原角点
                # 对于闭合路径，需要确保角点之间的连接
                if len(new_points) == 0:
                    # 这是第一个角点，但角度不在范围内
                    # 对于闭合路径，需要添加前一个点（最后一个点）作为起点
                    if is_closed:
                        prev_vertex_idx = (i - 1) % num_vertices
                        prev_pt = pts[prev_vertex_idx]
                        # 检查前一个角点是否被处理
                        # 如果前一个角点没有被处理，它应该已经被添加为 p1
                        # 但这里 new_points 是空的，说明前一个角点也没有被处理
                        # 所以我们需要添加前一个点作为起点
                        new_points.append(prev_pt)
                new_points.append(p1)
                continue
            
            # 对于接近180度的角（几乎直线），不进行倒圆角
            # 但允许在max_angle范围内的角
            if inner_angle_deg > 179.0 and max_angle < 179.0:
                new_points.append(p1)
                continue
            
            # 检查半径是否太大（不能超过线段长度）
            min_seg_len = min(len1, len2)
            # 确保半径不超过线段长度的45%，留出足够空间
            max_radius = min_seg_len * 0.45
            if radius > max_radius:
                # 半径太大，使用最大允许值
                radius_actual = max_radius
                # 如果最大允许值太小，跳过这个角点
                if radius_actual < 1e-6:
                    new_points.append(p1)
                    continue
            else:
                radius_actual = radius
            
            # 计算倒圆角的两个切点
            # 计算角平分线方向（指向角内部）
            bisector = (u1[0] + u2[0], u1[1] + u2[1])
            bisector_len = math.sqrt(bisector[0]**2 + bisector[1]**2)
            if bisector_len < 1e-6:
                new_points.append(p1)
                continue
            
            bisector = (bisector[0] / bisector_len, bisector[1] / bisector_len)
            
            # 计算圆心到角点的距离
            half_angle = angle / 2.0
            if abs(math.sin(half_angle)) < 1e-6:
                new_points.append(p1)
                continue
            
            dist_to_center = radius_actual / math.sin(half_angle)
            
            # 圆心位置（在角平分线上，距离角点dist_to_center）
            # 需要确定圆心在角的内侧还是外侧
            # 对于凸角，圆心在角的内侧（沿角平分线方向）
            center = (p1[0] + bisector[0] * dist_to_center, 
                     p1[1] + bisector[1] * dist_to_center)
            
            # 计算切点
            # 切点1：在p0->p1线段上，距离p1为dist1（向p0方向）
            dist1 = radius_actual / math.tan(half_angle)
            # 确保切点不会超出线段范围
            if dist1 > len1 * 0.85:
                dist1 = len1 * 0.85  # 限制在85%以内，留出安全边距
            if dist1 < 1e-6:
                # 距离太小，跳过这个角点
                new_points.append(p1)
                continue
            # u1是从p1指向p0，所以p1 + u1 * dist1是从p1向p0方向移动
            t1 = (p1[0] + u1[0] * dist1, p1[1] + u1[1] * dist1)
            
            # 切点2：在p1->p2线段上，距离p1为dist2（向p2方向）
            dist2 = radius_actual / math.tan(half_angle)
            # 确保切点不会超出线段范围
            if dist2 > len2 * 0.85:
                dist2 = len2 * 0.85  # 限制在85%以内，留出安全边距
            if dist2 < 1e-6:
                # 距离太小，跳过这个角点
                new_points.append(p1)
                continue
            # u2是从p1指向p2，所以p1 + u2 * dist2是从p1向p2方向移动
            t2 = (p1[0] + u2[0] * dist2, p1[1] + u2[1] * dist2)
            
            # 添加第一个切点（如果与上一个点不同）
            if len(new_points) == 0:
                # 这是第一个被处理的角点
                # 对于闭合路径，不需要添加最后一个点作为起点
                # 让路径自然闭合，在处理完所有角点后检查
                new_points.append(t1)
            else:
                # 检查是否需要添加连接线段
                last_pt = new_points[-1]
                dist_to_last = math.sqrt((t1[0] - last_pt[0])**2 + (t1[1] - last_pt[1])**2)
                if dist_to_last > 1e-6:
                    # 对于闭合路径，如果上一个角点没有被处理，可能需要添加连接线段
                    if is_closed:
                        # 检查上一个角点（索引 i-1）是否被处理
                        # 如果上一个角点没有被处理，它应该已经被添加为 p1
                        # 但为了确保路径连续，我们需要检查是否需要添加中间点
                        prev_vertex_idx = (i - 1) % num_vertices
                        prev_vertex_pt = pts[prev_vertex_idx]
                        dist_to_prev_vertex = math.sqrt((last_pt[0] - prev_vertex_pt[0])**2 + (last_pt[1] - prev_vertex_pt[1])**2)
                        if dist_to_prev_vertex > 1e-6:
                            # 上一个角点没有被处理，但 last_pt 不是 prev_vertex_pt
                            # 这意味着上一个角点被处理了，但 t2 和当前 t1 之间有间隙
                            # 这种情况不应该发生，但为了安全，我们直接添加 t1
                            pass
                    new_points.append(t1)
            
            # 生成圆弧点
            # 计算从圆心到切点的角度
            vec_t1 = (t1[0] - center[0], t1[1] - center[1])
            vec_t2 = (t2[0] - center[0], t2[1] - center[1])
            
            angle1 = math.atan2(vec_t1[1], vec_t1[0])
            angle2 = math.atan2(vec_t2[1], vec_t2[0])
            
            # 确定圆弧方向
            # 根据路径方向（通过叉积判断）确定圆弧是顺时针还是逆时针
            angle_diff = angle2 - angle1
            # 标准化角度差到[-pi, pi]
            while angle_diff > math.pi:
                angle_diff -= 2 * math.pi
            while angle_diff < -math.pi:
                angle_diff += 2 * math.pi
            
            # 如果叉积为正，路径是逆时针，圆弧应该逆时针；如果叉积为负，路径是顺时针，圆弧应该顺时针
            # 但我们需要确保圆弧连接两个切点，所以需要检查角度差的方向
            if abs(angle_diff) < 1e-6:
                # 角度差太小，直接连接两个切点
                new_points.append(t2)
                continue
            
            # 生成圆弧点
            num_arc_points = max(4, int(math.degrees(abs(angle_diff)) / 5))  # 每5度一个点
            for j in range(1, num_arc_points):
                t = j / num_arc_points
                arc_angle = angle1 + angle_diff * t
                arc_x = center[0] + radius_actual * math.cos(arc_angle)
                arc_y = center[1] + radius_actual * math.sin(arc_angle)
                new_points.append((arc_x, arc_y))
            
            # 添加第二个切点
            new_points.append(t2)
        
        # 处理路径的结束
        if is_closed:
            # 闭合路径：确保路径闭合
            if len(new_points) == 0:
                # 如果没有角点被处理，返回原路径并保持闭合
                closed_pts = pts[:]
                if not closed_pts:
                    return closed_pts
                if math.hypot(closed_pts[0][0] - closed_pts[-1][0], closed_pts[0][1] - closed_pts[-1][1]) > 1e-6:
                    closed_pts.append(closed_pts[0])
                return closed_pts
            
            # 对于闭合路径，确保首尾闭合点存在
            first_pt = new_points[0]
            last_pt = new_points[-1]
            dist_to_first = math.sqrt((last_pt[0] - first_pt[0])**2 + (last_pt[1] - first_pt[1])**2)
            if dist_to_first > 1e-6:
                new_points.append(first_pt)
            elif had_closure_point:
                # 若原路径显式闭合，确保闭合点存在（避免精度误差丢失）
                new_points[-1] = first_pt
        else:
            # 非闭合路径：添加最后一个点
            if len(pts) > 0:
                last_pt = pts[-1]
                if len(new_points) == 0:
                    # 如果没有角点被处理，添加起点和终点
                    new_points.append(pts[0])
                    new_points.append(last_pt)
                else:
                    last_new_pt = new_points[-1]
                    dist_to_last = math.sqrt((last_new_pt[0] - last_pt[0])**2 + (last_new_pt[1] - last_pt[1])**2)
                    if dist_to_last > 1e-6:
                        new_points.append(last_pt)
        
        # 确保至少有两个点
        if len(new_points) < 2:
            if is_closed and pts:
                closed_pts = pts[:]
                if math.hypot(closed_pts[0][0] - closed_pts[-1][0], closed_pts[0][1] - closed_pts[-1][1]) > 1e-6:
                    closed_pts.append(closed_pts[0])
                return closed_pts
            return pts[:]
        
        return new_points
    
    def show_gear_dialog(self):
        """显示加码齿对话框"""
        QMessageBox.information(self, "提示", "加码齿功能暂未实现")

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
                    self.show_status_message(f'已打开RLD文件: {os.path.basename(filename)}')
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
                self.show_status_message(f'已保存RLD文件: {os.path.basename(self.current_file)}')
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
                    self.show_status_message(f'已另存为RLD文件: {os.path.basename(filename)}')
                    self.logger.info(f"另存为RLD文件: {filename}")
                else:
                    QMessageBox.warning(self, "保存失败", "保存文件失败，请检查文件权限")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", f"保存文件时发生错误:\n{str(e)}")

    def get_next_layer_color(self):
        """获取下一个可用的图层颜色"""
        import random
        # 获取当前已使用的颜色
        used_colors = set(self.right_panel.layer_data.keys())
        
        # 尝试生成随机颜色，直到找到一个未使用的
        for _ in range(100):
            # 生成鲜艳的颜色 (避免太黑或太白)
            r = random.randint(50, 255)
            g = random.randint(50, 255)
            b = random.randint(50, 255)
            color = QColor(r, g, b)
            if color.name().upper() not in used_colors:
                return color
        
        # 如果尝试多次都失败（不太可能），返回黑色
        return QColor(0, 0, 0)

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
                    self.show_status_message(f"HPGL/PLT文件不存在: {os.path.basename(path)}", 5000)
                    return

                if not os.access(path, os.R_OK):
                    self.show_status_message(f"HPGL/PLT文件不可读: {os.path.basename(path)}", 5000)
                    return

                file_size = os.path.getsize(path)
                if file_size == 0:
                    self.show_status_message("HPGL/PLT文件为空", 5000)
                    return

                self.show_status_message("正在导入HPGL/PLT文件...")
                QtWidgets.QApplication.processEvents()

                try:
                    # --------------------------- 原 import_file_any 中 HPGL/PLT 处理逻辑 ---------------------------
                    from my_io.importers.import_hpgl import import_hpgl
                    paths = import_hpgl(path)

                    if paths:
                        # 生成新图层颜色
                        layer_color = self.get_next_layer_color()

                        # 添加路径到画布
                        for pts in paths:
                            if len(pts) > 0:
                                self.whiteboard.canvas.add_polyline(pts, layer_color)

                        # 更新图层名称
                        self.right_panel.update_layer_list(force=True)
                        hex_color = layer_color.name().upper()
                        if hex_color in self.right_panel.layer_data:
                            self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                            self.right_panel.update_layer_list(force=True) # 刷新显示

                        self.whiteboard.canvas.fit_all()
                        path_count = len(paths)
                        total_points = sum(len(pts) for pts in paths)
                        self.show_status_message(
                            f'HPGL/PLT导入成功: {os.path.basename(path)} (路径数={path_count}, 总点数={total_points})',
                            5000)
                    else:
                        self.show_status_message(f'HPGL/PLT文件 {os.path.basename(path)} 中未找到可导入的图形数据', 5000)

                except Exception as e:
                    self.show_status_message(f'HPGL/PLT导入错误: {str(e)}', 5000)
                    QtWidgets.QMessageBox.warning(self, "导入失败", f"HPGL/PLT文件导入失败:\n{str(e)}")

                return  # HPGL/PLT处理完成，直接返回

            # --------------------------- 处理WBMP文件 - 保留原逻辑 ---------------------------
            if lower.endswith('.wbmp'):
                # 尝试直接转换WBMP为PNG
                wbmp_img = convert_wbmp_to_png(path)
                if wbmp_img:
                    self._current_bitmap = wbmp_img
                    pix = pil_to_qpixmap(wbmp_img)
                    
                    # 生成新图层颜色
                    layer_color = self.get_next_layer_color()
                    self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                    
                    # 更新图层名称
                    self.right_panel.update_layer_list(force=True)
                    hex_color = layer_color.name().upper()
                    if hex_color in self.right_panel.layer_data:
                        self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                        self.right_panel.update_layer_list(force=True)

                    self.whiteboard.canvas.fit_all()
                    self.show_status_message(f'已转换并导入WBMP位图: {os.path.basename(path)}', 5000)
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
                            
                            # 生成新图层颜色
                            layer_color = self.get_next_layer_color()
                            self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                            
                            # 更新图层名称
                            self.right_panel.update_layer_list(force=True)
                            hex_color = layer_color.name().upper()
                            if hex_color in self.right_panel.layer_data:
                                self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                self.right_panel.update_layer_list(force=True)

                            self.whiteboard.canvas.fit_all()
                            self.show_status_message(f'已转换并导入WBMP位图: {os.path.basename(path)}', 5000)
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
                    self.show_status_message("正在处理EPS文件（使用软件自带工具）...")
                    QtWidgets.QApplication.processEvents()

                    # 先尝试矢量导入EPS
                    from my_io.importers.import_eps_vector import import_eps_as_vector
                    paths, status_msg = import_eps_as_vector(path)

                    if paths is not None:
                        # 矢量导入成功
                        # 生成新图层颜色
                        layer_color = self.get_next_layer_color()

                        for pts in paths:
                            self.whiteboard.canvas.add_polyline(pts, layer_color)
                        
                        # 更新图层名称
                        self.right_panel.update_layer_list(force=True)
                        hex_color = layer_color.name().upper()
                        if hex_color in self.right_panel.layer_data:
                            self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                            self.right_panel.update_layer_list(force=True)

                        self.whiteboard.canvas.fit_all()
                        self.show_status_message(f"EPS矢量导入成功: {status_msg}", 5000)
                        return

                    # 矢量导入失败，尝试位图导入
                    from my_io.importers.import_eps_bitmap import import_eps_as_bitmap
                    im, error_msg = import_eps_as_bitmap(path)

                    if im is not None:
                        # 位图导入成功 — 弹出位置/尺寸对话框以便用户输入 X/Y/W/H
                        pix = self.pil_to_qpixmap(im)
                        self._current_bitmap = im.copy()

                        # 内嵌对话框：收集 X, Y, W, H 和 单位(mm/px)
                        class ImageImportDialog(QtWidgets.QDialog):
                            def __init__(self, parent, pixmap):
                                super().__init__(parent)
                                self.setWindowTitle('设置导入图片位置与尺寸')
                                self.pixmap = pixmap
                                mm_per_px = 25.4 / 96.0

                                # 默认尺寸（mm）
                                default_w_mm = pixmap.width() * mm_per_px
                                default_h_mm = pixmap.height() * mm_per_px

                                self.unit_combo = QtWidgets.QComboBox(self)
                                self.unit_combo.setView(QtWidgets.QListView()) # 解决遮挡问题
                                self.unit_combo.addItems(['mm', 'px'])

                                self.x_spin = QtWidgets.QDoubleSpinBox(self)
                                self.y_spin = QtWidgets.QDoubleSpinBox(self)
                                self.w_spin = QtWidgets.QDoubleSpinBox(self)
                                self.h_spin = QtWidgets.QDoubleSpinBox(self)

                                # 设置精度和范围
                                self.x_spin.setRange(-10000.0, 10000.0)
                                self.y_spin.setRange(-10000.0, 10000.0)
                                self.w_spin.setRange(0.01, 100000.0)
                                self.h_spin.setRange(0.01, 100000.0)

                                # 默认单位为mm，精度0.01mm
                                self.unit_combo.setCurrentIndex(0)
                                self.x_spin.setDecimals(2)
                                self.y_spin.setDecimals(2)
                                self.w_spin.setDecimals(2)
                                self.h_spin.setDecimals(2)

                                self.x_spin.setValue(0.0)
                                self.y_spin.setValue(0.0)
                                self.w_spin.setValue(default_w_mm)
                                self.h_spin.setValue(default_h_mm)

                                # 当切换到px时，转为整数显示
                                def on_unit_changed(idx):
                                    cur_unit = self.unit_combo.currentText()
                                    if cur_unit == 'px':
                                        # 将当前值从 mm -> px
                                        self.x_spin.setDecimals(0)
                                        self.y_spin.setDecimals(0)
                                        self.w_spin.setDecimals(0)
                                        self.h_spin.setDecimals(0)
                                        self.x_spin.setSingleStep(1)
                                        self.y_spin.setSingleStep(1)
                                        self.w_spin.setSingleStep(1)
                                        self.h_spin.setSingleStep(1)
                                        # 转换值
                                        self.x_spin.setValue(round(self.x_spin.value() / mm_per_px))
                                        self.y_spin.setValue(round(self.y_spin.value() / mm_per_px))
                                        self.w_spin.setValue(round(self.w_spin.value() / mm_per_px))
                                        self.h_spin.setValue(round(self.h_spin.value() / mm_per_px))
                                    else:
                                        # px -> mm
                                        self.x_spin.setDecimals(2)
                                        self.y_spin.setDecimals(2)
                                        self.w_spin.setDecimals(2)
                                        self.h_spin.setDecimals(2)
                                        self.x_spin.setSingleStep(0.01)
                                        self.y_spin.setSingleStep(0.01)
                                        self.w_spin.setSingleStep(0.01)
                                        self.h_spin.setSingleStep(0.01)
                                        self.x_spin.setValue(self.x_spin.value() * mm_per_px)
                                        self.y_spin.setValue(self.y_spin.value() * mm_per_px)
                                        self.w_spin.setValue(self.w_spin.value() * mm_per_px)
                                        self.h_spin.setValue(self.h_spin.value() * mm_per_px)

                                self.unit_combo.currentIndexChanged.connect(on_unit_changed)

                                form = QtWidgets.QFormLayout()
                                form.addRow('单位', self.unit_combo)
                                form.addRow('X', self.x_spin)
                                form.addRow('Y', self.y_spin)
                                form.addRow('W', self.w_spin)
                                form.addRow('H', self.h_spin)

                                btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
                                btn_box.accepted.connect(self.accept)
                                btn_box.rejected.connect(self.reject)

                                layout = QtWidgets.QVBoxLayout()
                                # 缩略图预览
                                thumb_label = QtWidgets.QLabel(self)
                                thumb = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                thumb_label.setPixmap(thumb)
                                layout.addWidget(thumb_label)
                                layout.addLayout(form)
                                layout.addWidget(btn_box)
                                self.setLayout(layout)

                            def get_values(self):
                                unit = self.unit_combo.currentText()
                                x = self.x_spin.value()
                                y = self.y_spin.value()
                                w = self.w_spin.value()
                                h = self.h_spin.value()
                                return unit, x, y, w, h

                        dlg = ImageImportDialog(self, pix)
                        # 计算默认中心位置（优先使用右侧面板上用户设定的导入中心）
                        mm_per_px = 25.4 / 96.0
                        # 优先使用顶部属性输入中的 X/Y（这些代表导入的中心位置）
                        center_x_mm = None
                        center_y_mm = None
                        try:
                            tx = self.x_input.text().strip()
                            ty = self.y_input.text().strip()
                            if tx != '' and ty != '':
                                center_x_mm = float(tx)
                                center_y_mm = float(ty)
                        except Exception:
                            center_x_mm = None
                            center_y_mm = None

                        # 如果顶部控件无效，再尝试右侧面板
                        if center_x_mm is None or center_y_mm is None:
                            try:
                                center = self.right_panel.get_import_center_mm()
                            except Exception:
                                center = None
                            if center is not None:
                                center_x_mm, center_y_mm = center
                            else:
                                scene_center_x = self.whiteboard.canvas.scene.sceneRect().center().x()
                                scene_center_y = self.whiteboard.canvas.scene.sceneRect().center().y()
                                if scene_center_x == 0 and scene_center_y == 0:
                                    scene_center_x = self.whiteboard.canvas._work_w / 2
                                    scene_center_y = self.whiteboard.canvas._work_h / 2
                                center_x_mm, center_y_mm = scene_center_x, scene_center_y

                        default_w_mm = pix.width() * mm_per_px
                        default_h_mm = pix.height() * mm_per_px
                        # 将对话框的 X/Y 设为“图片左上角”以匹配 add_image 的参数（接受左上角坐标）
                        default_x = center_x_mm - default_w_mm / 2
                        default_y = center_y_mm - default_h_mm / 2
                        # 设定默认值到对话框
                        dlg.x_spin.setValue(round(default_x, 2))
                        dlg.y_spin.setValue(round(default_y, 2))
                        dlg.w_spin.setValue(round(default_w_mm, 2))
                        dlg.h_spin.setValue(round(default_h_mm, 2))

                        if dlg.exec_() == QtWidgets.QDialog.Accepted:
                            unit, x_val, y_val, w_val, h_val = dlg.get_values()
                            # 转换为 mm 单位用于 add_image
                            if unit == 'px':
                                mm_per_px = 25.4 / 96.0
                                x_mm = x_val * mm_per_px
                                y_mm = y_val * mm_per_px
                                w_mm = w_val * mm_per_px
                                h_mm = h_val * mm_per_px
                            else:
                                x_mm = x_val
                                y_mm = y_val
                                w_mm = w_val
                                h_mm = h_val

                            # 调用画布添加图片，传入精确位置与尺寸（毫米）
                            try:
                                # 生成新图层颜色
                                layer_color = self.get_next_layer_color()
                                self.whiteboard.canvas.add_image(pix, x_mm, y_mm, width_mm=w_mm, height_mm=h_mm, layer_color=layer_color)
                                
                                # 更新图层名称
                                self.right_panel.update_layer_list(force=True)
                                hex_color = layer_color.name().upper()
                                if hex_color in self.right_panel.layer_data:
                                    self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                    self.right_panel.update_layer_list(force=True)

                                self.show_status_message(f"EPS位图导入成功", 5000)
                            except Exception as e:
                                # 回退到原有自动居中导入
                                self.logger.exception('自定义尺寸导入失败，使用默认导入')
                                # 生成新图层颜色
                                layer_color = self.get_next_layer_color()
                                self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                                
                                # 更新图层名称
                                self.right_panel.update_layer_list(force=True)
                                hex_color = layer_color.name().upper()
                                if hex_color in self.right_panel.layer_data:
                                    self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                    self.right_panel.update_layer_list(force=True)

                                self.show_status_message(f"EPS位图导入成功(自动)", 5000)
                        else:
                            # 用户取消，使用默认居中导入
                            # 生成新图层颜色
                            layer_color = self.get_next_layer_color()
                            self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                            
                            # 更新图层名称
                            self.right_panel.update_layer_list(force=True)
                            hex_color = layer_color.name().upper()
                            if hex_color in self.right_panel.layer_data:
                                self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                self.right_panel.update_layer_list(force=True)

                            self.show_status_message(f"EPS位图导入已取消自定义，已自动居中导入", 5000)
                    else:
                        raise RuntimeError(f"EPS文件导入失败:\n{error_msg if error_msg else status_msg}")
                    return
                else:
                    # 处理其他位图
                    try:
                        im = Image.open(path)
                        # 不要强制转为RGBA，保持原样以便判断模式，但为了Qt显示兼容性，需确保是Qt支持的格式
                        if im.mode not in ('RGB', 'RGBA', 'L', '1'):
                            im = im.convert('RGBA')

                        self._current_bitmap = im
                        pix = pil_to_qpixmap(im)
                        
                        # 生成新图层颜色
                        layer_color = self.get_next_layer_color()
                        self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                        
                        # 更新图层名称
                        self.right_panel.update_layer_list(force=True)
                        hex_color = layer_color.name().upper()
                        if hex_color in self.right_panel.layer_data:
                            self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                            self.right_panel.update_layer_list(force=True)

                        self.whiteboard.canvas.fit_all()
                        self.show_status_message(f'已导入位图: {os.path.basename(path)}', 5000)
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
                                
                                # 生成新图层颜色
                                layer_color = self.get_next_layer_color()
                                self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                                
                                # 更新图层名称
                                self.right_panel.update_layer_list(force=True)
                                hex_color = layer_color.name().upper()
                                if hex_color in self.right_panel.layer_data:
                                    self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                    self.right_panel.update_layer_list(force=True)

                                self.whiteboard.canvas.fit_all()
                                self.show_status_message(f'已转换并导入位图: {os.path.basename(path)}', 5000)
                                os.unlink(converted_path)
                                return
                            except Exception as e2:
                                os.unlink(converted_path)

            # --------------------------- 处理AI文件 - 保留原核心逻辑 ---------------------------
            if lower.endswith('.ai'):
                self.show_status_message("正在处理AI文件（使用软件自带工具）...")
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
                        
                        # 生成新图层颜色
                        layer_color = self.get_next_layer_color()
                        self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)  # 添加到画布(0,0)位置
                        
                        # 更新图层名称
                        self.right_panel.update_layer_list(force=True)
                        hex_color = layer_color.name().upper()
                        if hex_color in self.right_panel.layer_data:
                            self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                            self.right_panel.update_layer_list(force=True)

                        self.whiteboard.canvas.fit_all()  # 自动调整视图以显示全图

                        # 显示成功信息
                        success_msg = f"✓ AI转换为位图成功: {os.path.basename(path)}"
                        self.show_status_message(success_msg, 5000)  # 5秒后消失
                        self.logger.info("AI文件作为位图成功导入")

                    except Exception as e:
                        # 位图处理失败的异常处理
                        err_msg = f"位图显示失败: {str(e)}"
                        self.show_status_message(err_msg, 5000)
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

                        # 生成新图层颜色
                        layer_color = self.get_next_layer_color()

                        # 绘制所有路径（红色，确保可见）
                        for idx, pts in enumerate(paths):
                            if len(pts) < 2:
                                self.logger.warning(f"路径{idx}点数量不足（{len(pts)}个），跳过绘制")
                                continue
                            self.whiteboard.canvas.add_polyline(pts, layer_color)  # 使用新颜色

                        # 更新图层名称
                        self.right_panel.update_layer_list(force=True)
                        hex_color = layer_color.name().upper()
                        if hex_color in self.right_panel.layer_data:
                            self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                            self.right_panel.update_layer_list(force=True)

                        # 调整视图以显示所有路径
                        self.whiteboard.canvas.fit_all()
                        self.logger.info("所有有效路径已添加到画布，并调用fit_all刷新视图")

                        # 显示成功信息
                        success_msg = f"✓ AI矢量路径导入成功: {os.path.basename(path)}"
                        self.show_status_message(success_msg, 5000)

                    except Exception as e:
                        # 矢量路径处理失败的异常处理
                        err_msg = f"矢量路径绘制失败: {str(e)}"
                        self.show_status_message(err_msg, 5000)
                        self.logger.error(f"矢量路径处理异常: {err_msg}", exc_info=True)
                        QtWidgets.QMessageBox.warning(
                            self,
                            "绘制失败",
                            f"矢量路径导入过程出错:\n{err_msg}"
                        )

                # 3. 所有方法均失败（无位图且无有效路径）
                else:
                    error_msg = f"AI文件导入失败:\n{status_msg}"
                    self.show_status_message(error_msg, 5000)
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
                            
                            # 生成新图层颜色
                            layer_color = self.get_next_layer_color()
                            self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                            
                            # 更新图层名称
                            self.right_panel.update_layer_list(force=True)
                            hex_color = layer_color.name().upper()
                            if hex_color in self.right_panel.layer_data:
                                self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                self.right_panel.update_layer_list(force=True)

                            self.whiteboard.canvas.fit_all()
                            self.show_status_message("✓ PCX文件导入成功", 5000)
                            paths = []  # 位图导入成功，无需返回路径
                        elif pcx_paths is not None:
                            # 如果有矢量路径（理论上PCX不会有）
                            # 生成新图层颜色
                            layer_color = self.get_next_layer_color()
                            for pts in pcx_paths:
                                self.whiteboard.canvas.add_polyline(pts, layer_color)
                            
                            # 更新图层名称
                            self.right_panel.update_layer_list(force=True)
                            hex_color = layer_color.name().upper()
                            if hex_color in self.right_panel.layer_data:
                                self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                self.right_panel.update_layer_list(force=True)

                            self.whiteboard.canvas.fit_all()
                            self.show_status_message("✓ PCX文件导入成功", 5000)
                            paths = pcx_paths
                        else:
                            raise RuntimeError("PCX导入失败")

                    except Exception as e:
                        self.show_status_message(f'PCX导入失败: {str(e)}', 5000)
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
                # 生成新图层颜色
                layer_color = self.get_next_layer_color()

                for pts in paths:
                    self.whiteboard.canvas.add_polyline(pts, layer_color)
                
                # 更新图层名称
                self.right_panel.update_layer_list(force=True)
                hex_color = layer_color.name().upper()
                if hex_color in self.right_panel.layer_data:
                    self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                    self.right_panel.update_layer_list(force=True)

                self.whiteboard.canvas.fit_all()
                self.show_status_message(f'已导入: {os.path.basename(path)} / 路径数={len(paths)}', 5000)
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
                            
                            # 生成新图层颜色
                            layer_color = self.get_next_layer_color()
                            self.whiteboard.canvas.add_image(pix, 0.0, 0.0, layer_color=layer_color)
                            
                            # 更新图层名称
                            self.right_panel.update_layer_list(force=True)
                            hex_color = layer_color.name().upper()
                            if hex_color in self.right_panel.layer_data:
                                self.right_panel.layer_data[hex_color].name = os.path.basename(path)
                                self.right_panel.update_layer_list(force=True)

                            self.whiteboard.canvas.fit_all()
                            self.show_status_message(f'已转换并导入位图: {os.path.basename(path)}', 5000)
                            os.unlink(converted_path)
                            return
                    except Exception as e:
                        self.show_status_message(f'PCX/TGA文件导入失败: {str(e)}', 5000)
                else:
                    self.show_status_message(f'未从 {os.path.basename(path)} 中找到可导入的图形', 5000)

        except Exception as e:
            # 捕获所有未预料的异常 - 保留原逻辑
            err_msg = f"导入总异常: {str(e)}"
            self.show_status_message(err_msg, 5000)
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
            self.show_status_message("正在导出G代码...")

            # 配置导出参数
            config = get_default_config()

            # 根据内容类型优化配置
            if content_info['has_images']:
                # 对于图片，使用更精细的扫描间隔
                config['scan_interval'] = 0.05  # 更精细的扫描
                config['grayscale_threshold'] = 128  # 中等灰度阈值

            # 执行导出
            allowed_colors = None
            layer_params_map = None
            if hasattr(self, 'right_panel'):
                allowed_colors = self.right_panel.get_output_enabled_colors()
                # 从 RightPanel.layer_data 构建一个简化的图层参数字典，传给导出器
                try:
                    layer_params_map = {}
                    for hex_color, p in self.right_panel.layer_data.items():
                        key = str(hex_color).upper()
                        layer_params_map[key] = {
                            'seal_gap': getattr(p, 'seal_gap', 0.0),
                            'laser_on_delay': getattr(p, 'laser_on_delay', 0),
                            'laser_off_delay': getattr(p, 'laser_off_delay', 0),
                            'mode': getattr(p, 'mode', '激光切割'),
                        }
                except Exception:
                    layer_params_map = None

            success = export_to_nc(self.whiteboard.canvas, filename, config, allowed_colors, layer_params_map)

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

                        self.show_status_message(message, 5000)
                        QMessageBox.information(self, "导出成功",
                                                f"G代码导出完成！\n文件已保存到: {filename}\n"
                                                f"共生成 {line_count} 行G代码，{move_count} 个移动指令")
                except Exception as read_error:
                    self.logger.warning(f"读取G代码文件失败: {read_error}")
                    self.show_status_message(f'成功导出G代码: {os.path.basename(filename)}', 5000)
                    QMessageBox.information(self, "导出成功", f"G代码导出完成！\n文件已保存到: {filename}")
            else:
                self.show_status_message('导出失败', 5000)
                QMessageBox.warning(self, "导出失败", "G代码导出失败，请查看日志获取详细信息")

        except Exception as e:
            error_msg = f"导出过程中发生错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.show_status_message('导出错误', 5000)
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
        self.show_status_message('十字定位点模式：请在画布上右键点击设置定位点（点击后自动退出）')

    def enable_circle_fiducial_mode(self):
        """启用圆形定位点模式"""
        self.whiteboard.canvas.set_tool(self.whiteboard.canvas.Tool.ADD_FID_CIRCLE)
        self.show_status_message('圆形定位点模式：请在画布上右键点击设置定位点（点击后自动退出）')

    def remove_fiducial(self):
        """删除定位点"""
        self.whiteboard.remove_fiducial()
        self.show_status_message('定位点已删除')

    # 编辑操作方法
    def undo(self):
        """撤销"""
        self.whiteboard.undo()
        self.show_status_message('撤销')

    def redo(self):
        """重做"""
        self.whiteboard.redo()
        self.show_status_message('重做')

    def cut(self):
        """剪切"""
        self.show_status_message('剪切')

    def copy(self):
        """复制"""
        self.show_status_message('复制')

    def paste(self):
        """粘贴"""
        self.show_status_message('粘贴')

    def delete(self):
        """删除"""
        self.show_status_message('删除')

    def select_all(self):
        """全选"""
        self.show_status_message('全选')

    # 视图操作方法
    def zoom_in(self):
        """放大"""
        # 如果有选中项则放大选中项，否则放大视图
        try:
            self._scale_or_zoom_selected(1.15)
        except Exception:
            try:
                self.whiteboard.zoom_in()
            except Exception:
                pass
        self.show_status_message(f'缩放: {self.whiteboard.get_zoom_percent()}%')

    def zoom_out(self):
        """缩小"""
        try:
            self._scale_or_zoom_selected(1 / 1.15)
        except Exception:
            try:
                self.whiteboard.zoom_out()
            except Exception:
                pass
        self.show_status_message(f'缩放: {self.whiteboard.get_zoom_percent()}%')

    def zoom_reset(self):
        """重置缩放"""
        self.whiteboard.zoom_reset()
        self.show_status_message('缩放: 100%')

    def set_pan_tool(self):
        """平移工具"""
        self.whiteboard.set_tool(self.whiteboard.canvas.Tool.PAN)
        self.show_status_message('工具: 平移')

    def set_measure_tool(self):
        """测量工具"""
        self.whiteboard.set_tool(self.whiteboard.canvas.Tool.MEASURE)
        self.show_status_message('工具: 测量')

    def zoom_to_page(self):
        """页面范围"""
        self.whiteboard.canvas.zoom_to_page()
        self.show_status_message('视图: 页面范围')

    def zoom_to_data(self):
        """数据范围"""
        self.whiteboard.canvas.zoom_to_data()
        self.show_status_message('视图: 数据范围')

    def zoom_to_all(self):
        """显示所有"""
        self.whiteboard.canvas.zoom_to_all()
        self.show_status_message('视图: 显示所有')

    def set_box_zoom_tool(self):
        """框选查看工具"""
        self.whiteboard.set_tool(self.whiteboard.canvas.Tool.BOX_ZOOM)
        self.show_status_message('工具: 框选查看')

    def view_zoom_in(self):
        """仅放大视图"""
        self.whiteboard.zoom_in()
        self.show_status_message(f'缩放: {self.whiteboard.get_zoom_percent()}%')

    def view_zoom_out(self):
        """仅缩小视图"""
        self.whiteboard.zoom_out()
        self.show_status_message(f'缩放: {self.whiteboard.get_zoom_percent()}%')

    def toggle_show_path(self):
        """切换显示切割路径"""
        if self._updating_path:
            return
            
        self._updating_path = True
        try:
            try:
                is_checked = self.show_path_action.isChecked()
                if is_checked:
                    # 显示所有对象的路径（不仅仅是选中对象）
                    # 使用 Qt.AscendingOrder 获取按堆叠顺序（从底到顶，即创建顺序）排列的项
                    items = self.whiteboard.canvas.scene.items(order=Qt.AscendingOrder)
                    
                    # 过滤和排序
                    valid_items = []
                    
                    # 获取图层数据
                    layer_data = self.right_panel.layer_data
                    
                    from ui.graphics_items import EditablePathItem, EditableEllipseItem
                    from ui.whiteboard import RotateHandle
                    from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem

                    # 辅助函数：获取项的颜色Hex
                    def get_item_color_hex(item):
                        color = None
                        if isinstance(item, (EditablePathItem, EditableEllipseItem)):
                            color = item.pen().color()
                        elif isinstance(item, QGraphicsTextItem):
                            color = item.defaultTextColor()
                        
                        if color:
                            return color.name().upper()
                        return None

                    # 收集有效项
                    for item in items:
                        # 排除不可见项
                        if not item.isVisible(): continue

                        # 排除非顶层项（如子项、手柄图标等）
                        if item.parentItem() is not None: continue

                        # 排除辅助项
                        if item.zValue() >= 9999: continue # Preview items
                        if item is getattr(self.whiteboard.canvas, '_work_item', None): continue
                        if item is getattr(self.whiteboard.canvas, '_cursor_preview', None): continue
                        
                        # 排除旋转手柄及其相关项
                        rotate_handle = getattr(self.whiteboard.canvas, '_rotate_handle', None)
                        if item is rotate_handle: continue
                        if rotate_handle and item is getattr(rotate_handle, '_angle_text', None): continue
                        if isinstance(item, RotateHandle): continue

                        # 仅包含用户内容类型
                        if not isinstance(item, (EditablePathItem, EditableEllipseItem, QGraphicsPixmapItem, QGraphicsTextItem)):
                            continue

                        color_hex = get_item_color_hex(item)
                        if color_hex:
                            # 检查图层设置
                            if color_hex in layer_data:
                                params = layer_data[color_hex]
                                if params.is_output:
                                    valid_items.append((item, params.priority))
                            else:
                                # 未知图层，默认输出，优先级最低
                                valid_items.append((item, 9999))
                        else:
                            # 无颜色项（如图片），默认输出
                            valid_items.append((item, 9999))
                    
                    # 排序：优先级越小越靠前
                    # scene.items() 返回的是 stacking order (top first). 
                    # 我们希望按照加工顺序，通常是先加工优先级高的
                    valid_items.sort(key=lambda x: x[1])
                    
                    sorted_items = [x[0] for x in valid_items]
                    
                    self.whiteboard.canvas.show_path_preview(sorted_items)
                    self.show_status_message('显示切割路径')
                else:
                    self.whiteboard.canvas.hide_path_preview()
                    self.show_status_message('隐藏切割路径')
            except Exception as e:
                print(f"Error showing path: {e}")
        finally:
            self._updating_path = False

    def on_scene_changed(self, changes=None):
        """场景变化处理"""
        # 如果路径预览开启，则更新路径
        if self.show_path_action.isChecked():
            self.toggle_show_path()



    def _scale_or_zoom_selected(self, factor: float):
        """如果有选中项则缩放选中项，否则缩放视图。"""
        try:
            selected = self.whiteboard.canvas.get_selected_items()
            if selected:
                self.whiteboard.canvas.scale_selected_items(factor)
                self.show_status_message(f'缩放所选: {int(factor*100)}%')
            else:
                # 缩放视图
                if factor > 1.0:
                    self.whiteboard.zoom_in()
                else:
                    self.whiteboard.zoom_out()
                self.show_status_message(f'缩放: {self.whiteboard.get_zoom_percent()}%')
        except Exception:
            pass

    def toggle_fullscreen(self):
        """切换全屏"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_sys_toolbar(self):
        """切换系统工具栏显示"""
        if hasattr(self, 'toolbar1'):
            self.toolbar1.setVisible(self.view_sys_toolbar.isChecked())

    def toggle_status_bar(self):
        """切换系统状态栏显示"""
        if self.statusBar():
            self.statusBar().setVisible(self.view_status_bar.isChecked())

    def toggle_draw_toolbar(self):
        """切换绘制工具栏显示"""
        if hasattr(self, 'left_toolbar'):
            self.left_toolbar.setVisible(self.view_draw_toolbar.isChecked())

    def toggle_cut_prop_bar(self):
        """切换切割属性栏显示"""
        # 目前属性栏在toolbar3中，暂时控制toolbar3
        if hasattr(self, 'toolbar3'):
            self.toolbar3.setVisible(self.view_cut_prop_bar.isChecked())

    def toggle_align_toolbar(self):
        """切换对齐工具栏显示"""
        # 目前对齐栏也在toolbar3中，暂时控制toolbar3
        if hasattr(self, 'toolbar3'):
            self.toolbar3.setVisible(self.view_align_toolbar.isChecked())

    def toggle_color_toolbar(self):
        """切换颜色工具栏显示"""
        if hasattr(self, 'color_bar'):
            self.color_bar.setVisible(self.view_color_toolbar.isChecked())

    def toggle_sys_workspace(self):
        """切换系统工作区显示"""
        if hasattr(self, 'whiteboard'):
            self.whiteboard.setVisible(self.view_sys_workspace.isChecked())

    def toggle_process_ctrl_bar(self):
        """切换加工控制栏显示"""
        if hasattr(self, 'right_panel'):
            self.right_panel.setVisible(self.view_process_ctrl_bar.isChecked())

    def toggle_add_toolbar(self):
        """切换附加工具栏显示"""
        if hasattr(self, 'toolbar2'):
            self.toolbar2.setVisible(self.view_add_toolbar.isChecked())

    def toggle_process_toolbar(self):
        """切换处理工具栏显示"""
        pass

    def toggle_canvas_toolbar(self):
        """切换画布工具栏显示"""
        pass

    def set_lead_line(self):
        """设置引入引出线"""
        # 检查是否有选中对象
        selected_items = self.whiteboard.canvas.get_selected_items()
        if not selected_items:
            # 未选取对象点击工具无用
            return

        # 使用 QTimer.singleShot 延迟弹出对话框，避免可能的事件冲突导致闪退
        QTimer.singleShot(0, self._show_lead_line_dialog)

    def _show_lead_line_dialog(self):
        """显示引入引出线设置对话框"""
        try:
            # 弹出对话框
            dialog = LeadLineDialog(self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                data = dialog.get_data()
                # TODO: 将设置应用到选中对象
                # 目前仅打印设置，后续可根据需求实现具体的几何修改或属性存储
                print("Lead Line Settings:", data)
                self.show_status_message("引入引出线设置已应用")
        except Exception as e:
            print(f"Error in lead line dialog: {e}")
            self.show_status_message(f"设置出错: {e}")

    def set_cut_property_tool(self):
        """打开切割属性(排序/路径)对话框"""
        from ui.cut_property_dialog import CutPropertyDialog
        dlg = CutPropertyDialog(self.whiteboard.canvas.scene, self)
        dlg.exec_()
        self.whiteboard.canvas.update()

    def show_preview_dialog(self):
        """显示加工预览对话框"""
        try:
            # 获取所有图形项，使用 Qt.AscendingOrder 确保按创建顺序（底层优先）
            all_items = self.whiteboard.canvas.scene.items(order=Qt.AscendingOrder)
            
            # 获取选中项
            selected_items_set = set(self.whiteboard.canvas.scene.selectedItems())
            
            # 如果没有选中任何对象，则预览列表为空（显示黑屏）
            # 如果有选中对象，则只预览选中的对象
            target_items = []
            if selected_items_set:
                for item in all_items:
                    if item in selected_items_set:
                        target_items.append(item)
            else:
                # 没有选中对象，列表为空
                target_items = []
            
            # 过滤掉非图形项（如辅助线、手柄等）
            valid_items = []
            from ui.graphics_items import EditablePathItem, EditableEllipseItem
            from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
            
            for item in target_items:
                if not item.isVisible(): continue
                if item.parentItem() is not None: continue
                if item.zValue() >= 9999: continue # Preview items
                if item is getattr(self.whiteboard.canvas, '_work_item', None): continue
                if item is getattr(self.whiteboard.canvas, '_cursor_preview', None): continue
                
                if isinstance(item, (EditablePathItem, EditableEllipseItem, QGraphicsPixmapItem, QGraphicsTextItem)):
                    valid_items.append(item)
            
            # 获取工作区尺寸
            work_w = self.whiteboard.canvas._work_w
            work_h = self.whiteboard.canvas._work_h
            
            # 获取图层数据
            layer_data = self.right_panel.layer_data
            
            # 获取激光头位置
            laser_pos = self.whiteboard.canvas.get_laser_start_point()
            
            # 延迟弹出，避免事件冲突
            def open_dlg():
                dlg = PreviewDialog(valid_items, (work_w, work_h), layer_data, self, laser_pos=laser_pos)
                # dlg.showFullScreen() # 移除全屏
                dlg.exec_()
                
            QTimer.singleShot(0, open_dlg)
            
        except Exception as e:
            print(f"Error showing preview: {e}")
            self.show_status_message(f"预览出错: {e}")

    def open_system_settings(self):
        """打开系统设置对话框"""
        dialog = SystemSettingsDialog(self)
        
        # Load current settings from whiteboard
        if hasattr(self, 'whiteboard'):
            current_settings = self.whiteboard.get_interface_config()
            dialog.load_interface_settings(current_settings)
        
        if dialog.exec_() == QDialog.Accepted:
            # Apply Interface settings to whiteboard
            try:
                if hasattr(dialog, 'get_interface_settings'):
                    ifsettings = dialog.get_interface_settings()
                    if hasattr(self, 'whiteboard'):
                        self.whiteboard.update_interface_config(ifsettings)
            except Exception as e:
                print(f"Error applying settings: {e}")

    # 工具选择方法
    def select_pen(self):
        """选择画笔"""
        self.whiteboard.set_tool('pen')
        self.show_status_message('画笔工具')

    def select_eraser(self):
        """选择橡皮擦"""
        self.whiteboard.set_tool('eraser')
        self.show_status_message('橡皮擦工具')

    def select_line(self):
        """选择直线"""
        self.whiteboard.set_tool('line')
        self.show_status_message('直线工具')

    def select_rectangle(self):
        """选择矩形"""
        self.whiteboard.set_tool('rectangle')
        self.show_status_message('矩形工具')

    def select_circle(self):
        """选择圆形"""
        self.whiteboard.set_tool('circle')
        self.show_status_message('圆形工具')

    def rotate_selected_by_angle(self):
        """读取角度输入并对当前选中项进行旋转（纳入历史）。"""
        try:
            text = self.angle_input.text().strip()
            if not text:
                return
            angle = float(text)
        except Exception:
            QMessageBox.warning(self, '输入错误', '请输入有效的角度数值')
            return
        try:
            self.whiteboard.canvas.rotate_selected(angle)
            self.show_status_message(f'已按 {angle}° 旋转选中项')
        except Exception as e:
            self.logger.error(f'旋转失败: {e}', exc_info=True)
            QMessageBox.warning(self, '旋转失败', f'旋转选中项时发生错误: {e}')

    def open_rotate_dialog(self):
        """打开精确旋转对话框，支持增量(相对)与绝对两种模式。"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle('精确旋转')
        vbox = QVBoxLayout(dlg)

        # 模式选择
        rb_rel = QRadioButton('增量旋转（相对当前角度）')
        rb_rel.setChecked(True)
        rb_abs = QRadioButton('绝对角度（设置为指定角度）')
        vbox.addWidget(rb_rel)
        vbox.addWidget(rb_abs)

        # 角度输入
        from PyQt5.QtWidgets import QLabel
        lbl = QLabel('角度 (°):')
        ang_input = QLineEdit('0')
        ang_input.setMaximumWidth(120)
        h = QHBoxLayout()
        h.addWidget(lbl)
        h.addWidget(ang_input)
        vbox.addLayout(h)

        # 说明
        note = QLabel('提示: 按确定应用。对路径项使用绝对模式时会尝试根据质心计算当前方向并调整。')
        vbox.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        vbox.addWidget(buttons)

        if dlg.exec_() == QDialog.Accepted:
            try:
                angle = float(ang_input.text().strip())
            except Exception:
                QMessageBox.warning(self, '输入错误', '请输入有效角度')
                return
            try:
                if rb_rel.isChecked():
                    self.whiteboard.canvas.rotate_selected(angle)
                else:
                    # 绝对：对每项按其当前角度计算增量
                    self.whiteboard.canvas.rotate_selected_absolute(angle)
                self.show_status_message(f'已按对话框设置旋转: {angle}°')
            except Exception as e:
                self.logger.error(f'精确旋转失败: {e}', exc_info=True)
                QMessageBox.warning(self, '旋转失败', f'精确旋转失败: {e}')

    def show_help_docs(self):
        """显示帮助文档"""
        QMessageBox.information(self, "帮助文档", "使用说明书正在编制中。\n快捷键: F1")

    def show_logs(self):
        """显示日志"""
        # 简单的日志查看实现
        log_path = 'app.log'
        if os.path.exists(log_path):
            try:
                os.startfile(log_path)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开日志文件: {e}")
        else:
             QMessageBox.information(self, "日志", "当前未生成日志文件。")

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

    def _update_position_display(self):
        """更新工具栏3中X、Y位置以及宽度、高度（横向和纵向间距）的显示"""
        try:
            # 如果用户正在编辑输入框，不更新（避免打断输入）
            if (self.x_input.hasFocus() or self.y_input.hasFocus() or 
                self.width_input.hasFocus() or self.height_input.hasFocus()):
                return
            
            # 获取选中的图形项
            selected_items = self.whiteboard.canvas.scene.selectedItems()
            
            if not selected_items:
                # 没有选中项时，清空显示
                if not self.x_input.hasFocus():
                    self.x_input.setText("0")
                if not self.y_input.hasFocus():
                    self.y_input.setText("0")
                if not self.width_input.hasFocus():
                    self.width_input.setText("0")
                if not self.height_input.hasFocus():
                    self.height_input.setText("0")
                return
            
            # 计算所有选中项的包围矩形
            from PyQt5.QtCore import QRectF
            from ui.graphics_items import EditablePathItem
            from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
            
            bounding_rect = None
            for item in selected_items:
                try:
                    # 对于EditablePathItem，使用sceneBoundingRect获取包围矩形
                    if isinstance(item, EditablePathItem):
                        br = item.sceneBoundingRect()
                    elif isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem)):
                        br = item.sceneBoundingRect()
                    else:
                        # 其他类型的项，尝试获取包围矩形
                        br = item.sceneBoundingRect()
                    
                    if br.isValid():
                        if bounding_rect is None:
                            bounding_rect = br
                        else:
                            bounding_rect = bounding_rect.united(br)
                except Exception:
                    continue
            
            if bounding_rect is not None and bounding_rect.isValid():
                # 使用包围矩形的中心作为位置
                x = bounding_rect.center().x()
                y = bounding_rect.center().y()
                # 计算宽度和高度（横向和纵向间距）
                width = bounding_rect.width()
                height = bounding_rect.height()
                
                # 更新输入框（保留2位小数），仅在输入框没有焦点时更新
                if not self.x_input.hasFocus():
                    self.x_input.setText(f"{x:.2f}")
                if not self.y_input.hasFocus():
                    self.y_input.setText(f"{y:.2f}")
                if not self.width_input.hasFocus():
                    self.width_input.setText(f"{width:.2f}")
                if not self.height_input.hasFocus():
                    self.height_input.setText(f"{height:.2f}")
                
                # 重置百分比显示为100
                if not self.percent_input.hasFocus():
                    self.percent_input.setText("100")
                if not self.percent_input2.hasFocus():
                    self.percent_input2.setText("100")
            else:
                # 无法获取位置时，显示0
                if not self.x_input.hasFocus():
                    self.x_input.setText("0")
                if not self.y_input.hasFocus():
                    self.y_input.setText("0")
                if not self.width_input.hasFocus():
                    self.width_input.setText("0")
                if not self.height_input.hasFocus():
                    self.height_input.setText("0")
                if not self.percent_input.hasFocus():
                    self.percent_input.setText("100")
                if not self.percent_input2.hasFocus():
                    self.percent_input2.setText("100")
        except Exception:
            # 出错时保持当前显示不变
            pass

    def _apply_percent_scale(self, is_width):
        """应用百分比缩放"""
        try:
            # 获取输入值
            if is_width:
                text = self.percent_input.text()
            else:
                text = self.percent_input2.text()
            
            try:
                percent = float(text)
            except ValueError:
                return
            
            # 转换为缩放因子
            factor = percent / 100.0
            
            # 如果因子接近1或无效，忽略
            if abs(factor - 1.0) < 0.001 or factor <= 0:
                return
            
            # 获取当前宽高
            try:
                current_w = float(self.width_input.text())
                current_h = float(self.height_input.text())
            except ValueError:
                return

            # 计算新宽高 (比例缩放：宽高同时缩放)
            new_w = current_w * factor
            new_h = current_h * factor
            
            self.width_input.setText(f"{new_w:.2f}")
            self.height_input.setText(f"{new_h:.2f}")
            
            # 应用更改
            self._apply_position_and_size_changes()
            
            # 重置输入框为100
            self.percent_input.setText("100")
            self.percent_input2.setText("100")
            
        except Exception:
            pass

    def _apply_position_and_size_changes(self):
        """根据X、Y、W、H输入框的值更新选中图形的位置和尺寸"""
        try:
            # 获取选中的图形项
            selected_items = self.whiteboard.canvas.scene.selectedItems()
            if not selected_items:
                return
            
            # 读取输入框的值
            try:
                new_x = float(self.x_input.text())
            except ValueError:
                new_x = None
            try:
                new_y = float(self.y_input.text())
            except ValueError:
                new_y = None
            try:
                new_width = float(self.width_input.text())
            except ValueError:
                new_width = None
            try:
                new_height = float(self.height_input.text())
            except ValueError:
                new_height = None
            
            # 如果所有值都无效，直接返回
            if new_x is None and new_y is None and new_width is None and new_height is None:
                return
            
            # 计算当前选中项的包围矩形
            from PyQt5.QtCore import QRectF
            from ui.graphics_items import EditablePathItem
            from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
            
            bounding_rect = None
            for item in selected_items:
                try:
                    if isinstance(item, EditablePathItem):
                        br = item.sceneBoundingRect()
                    elif isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem)):
                        br = item.sceneBoundingRect()
                    else:
                        br = item.sceneBoundingRect()
                    
                    if br.isValid():
                        if bounding_rect is None:
                            bounding_rect = br
                        else:
                            bounding_rect = bounding_rect.united(br)
                except Exception:
                    continue
            
            if bounding_rect is None or not bounding_rect.isValid():
                return
            
            # 获取当前值
            current_x = bounding_rect.center().x()
            current_y = bounding_rect.center().y()
            current_width = bounding_rect.width()
            current_height = bounding_rect.height()
            
            # 计算位置偏移量
            dx = (new_x - current_x) if new_x is not None else 0.0
            dy = (new_y - current_y) if new_y is not None else 0.0
            
            # 计算缩放比例（如果宽度或高度有效）
            scale_x = (new_width / current_width) if (new_width is not None and current_width > 0) else 1.0
            scale_y = (new_height / current_height) if (new_height is not None and current_height > 0) else 1.0
            
            # 如果既没有位置变化也没有尺寸变化，直接返回
            if dx == 0.0 and dy == 0.0 and scale_x == 1.0 and scale_y == 1.0:
                return
            
            # 记录旧状态，用于撤销/重做
            from edit.commands import MoveItemsCommand
            items_states = []
            
            # 缩放基准点（使用中心点）
            pivot_x = current_x
            pivot_y = current_y
            
            # 应用变化到每个选中的图形项
            for item in selected_items:
                try:
                    if isinstance(item, EditablePathItem):
                        # 对于EditablePathItem，需要修改点数据
                        old_points = item.points()
                        if not old_points:
                            continue
                        
                        # 计算当前项的包围矩形
                        item_br = item.sceneBoundingRect()
                        if not item_br.isValid():
                            continue
                        
                        # 应用位置偏移和缩放
                        new_points = []
                        for px, py in old_points:
                            # 相对于整体中心点进行缩放
                            scaled_x = pivot_x + (px - pivot_x) * scale_x
                            scaled_y = pivot_y + (py - pivot_y) * scale_y
                            # 应用位置偏移
                            final_x = scaled_x + dx
                            final_y = scaled_y + dy
                            new_points.append((final_x, final_y))
                        
                        items_states.append(('path', item, old_points, new_points))
                        
                    elif isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem)):
                        # 对于其他图形项，使用transform
                        from PyQt5.QtGui import QTransform
                        from PyQt5.QtCore import QPointF
                        
                        old_transform = item.transform()
                        
                        # 计算新的transform
                        # 1. 移动到整体中心点
                        # 2. 缩放
                        # 3. 移动回原位 + 偏移
                        
                        # 注意：QTransform是右乘的，所以顺序是反的
                        # 我们需要构建一个变换矩阵 M，使得 new_pos = M * old_pos
                        # M = T(dx, dy) * T(pivot_x, pivot_y) * S(sx, sy) * T(-pivot_x, -pivot_y)
                        
                        transform_matrix = QTransform()
                        transform_matrix.translate(pivot_x + dx, pivot_y + dy)
                        transform_matrix.scale(scale_x, scale_y)
                        transform_matrix.translate(-pivot_x, -pivot_y)
                        
                        # 应用到原有变换上： new_transform = transform_matrix * old_transform
                        # 但这里是对item本身做变换，item的坐标系是局部的
                        # 实际上我们需要修改item的transform，使得其在scene中的表现符合预期
                        
                        # 更简单的方法：直接对item应用变换
                        # item.setTransform(transform_matrix, combine=True)
                        # 但我们需要记录状态用于undo
                        
                        # 正确的矩阵乘法顺序：
                        # 我们希望 item 在 scene 中的变换变为 M * item_in_scene
                        # item_in_scene = old_transform
                        # 所以 new_transform = transform_matrix * old_transform
                        
                        new_transform = transform_matrix * old_transform
                        
                        items_states.append(('transform', item, old_transform, new_transform))
                    else:
                        # 其他类型的项，尝试使用transform
                        try:
                            from PyQt5.QtGui import QTransform
                            item_br = item.sceneBoundingRect()
                            if not item_br.isValid():
                                continue
                            
                            old_transform = item.transform()
                            item_pivot_x = item_br.left()
                            item_pivot_y = item_br.top()
                            
                            new_transform = QTransform()
                            new_transform.translate(-item_pivot_x, -item_pivot_y)
                            new_transform.scale(scale_x, scale_y)
                            new_transform.translate(item_pivot_x + dx, item_pivot_y + dy)
                            new_transform = new_transform * old_transform
                            
                            items_states.append(('transform', item, old_transform, new_transform))
                        except Exception:
                            continue
                except Exception:
                    continue
            
            # 如果有变化，应用并记录命令
            if items_states:
                cmd = MoveItemsCommand(self.whiteboard.canvas, items_states)
                cmd.redo()
                self.whiteboard.canvas.edit_manager.push_undo(cmd)
                
                # 更新显示（因为图形已经改变）
                self._update_position_display()
        except Exception as e:
            # 出错时显示错误信息
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"应用参数化输入时出错: {e}")