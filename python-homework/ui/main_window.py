#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口类
"""
import os
import math
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
from my_io.exporters.export_dxf import export_to_dxf
from ui.lead_line_dialog import LeadLineDialog
from ui.preview_dialog import PreviewDialog
from ui.fill_bitmap_dialog import FillBitmapDialog

from ui.smooth_curve_dialog import SmoothCurveSimpleDialog, SmoothCurveCustomDialog, chaikin_smooth
from ui.auto_close_dialog import AutoCloseDialog
from ui.data_check_dialog import DataCheckDialog
from ui.bitmap_process_dialog import BitmapProcessDialog
from ui.graphics_items import EditablePathItem
from edit.commands import SmoothItemCommand, UpdatePathDataCommand

from ui.manufacturer_settings_dialog import ManufacturerPasswordDialog, ManufacturerSettingsDialog
from ui.system_settings_dialog import SystemSettingsDialog, load_persisted_settings
from ui.auto_layout_dialog import AutoLayoutDialog
from utils.language_manager import language_manager
from ui.graphics_items import EditablePathItem, EditableEllipseItem, TextGraphicsItem, get_item_group_id
from PyQt5.QtWidgets import QMessageBox
from ui.array_copy_dialog import ArrayCopyDialog
from ui.micro_joint_dialog import MicroJointDialog
from edit.commands import AddItemCommand, MacroCommand
import copy

from .combined_tools_dialog import CombinedToolsDialog
from .fillet_dialog import FilletDialog

FILL_SCAN_BITMAP_ROLE = Qt.UserRole + 310
FILL_SCAN_SOURCE_ID_ROLE = Qt.UserRole + 311
FILL_SCAN_HIDDEN_SOURCE_ROLE = Qt.UserRole + 312

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
        self._fill_scan_busy = False
        self._fill_scan_pairs = {}
        self._fillet_dialog = None
        self._fillet_last_hit = None

        self.logger = setup_logging()
        self.logger.info("MainWindow初始化开始")
        self.init_ui()  # 调用 init_ui()，内部会通过 create_central_widget() 创建布局
        try:
            load_persisted_settings(self.whiteboard.canvas)
        except Exception:
            pass
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
        """打开综合工具箱（原激光控制界面位置）"""
        try:
            dlg = CombinedToolsDialog(self, self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开工具箱: {str(e)}")

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

        self.export_dxf_action = QAction('导出为 DXF...', self)
        self.export_dxf_action.triggered.connect(self.export_to_dxf_file)
        self.file_menu.addAction(self.export_dxf_action)

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

        self.group_action = QAction('群组', self)
        self.group_action.setShortcut('Ctrl+G')
        self.group_action.triggered.connect(self.group_selected_items)
        self.group_action.setEnabled(False)
        self.edit_menu.addAction(self.group_action)

        self.ungroup_action = QAction('解散群组', self)
        self.ungroup_action.setShortcut('Ctrl+Shift+G')
        self.ungroup_action.triggered.connect(self.ungroup_selected_items)
        self.ungroup_action.setEnabled(False)
        self.edit_menu.addAction(self.ungroup_action)
        
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

        self.fillet_action = QAction('倒圆角', self)
        self.fillet_action.triggered.connect(self.show_fillet_dialog)
        self.draw_menu.addAction(self.fillet_action)

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
        self.fill_scan_action.setCheckable(True)
        self.fill_scan_action.setChecked(False)
        self.fill_scan_action.toggled.connect(self.on_fill_scan_toggled)
        self.settings_menu.addAction(self.fill_scan_action)

        self.show_array_action = QAction('显示阵列', self)
        self.show_array_action.setCheckable(True)
        self.show_array_action.setChecked(True)
        self.settings_menu.addAction(self.show_array_action)

        # 处理菜单
        self.process_menu = menubar.addMenu('处理(W)')
        
        # 保存处理菜单项
        self.process_curve_auto_close_action = add_process_action = QAction('曲线自动闭合', self)
        add_process_action.triggered.connect(self.show_auto_close_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_bitmap_handle_action = add_process_action = QAction('位图处理', self)
        add_process_action.triggered.connect(self.show_bitmap_process_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_curve_smooth_action = add_process_action = QAction('曲线平滑', self)
        add_process_action.triggered.connect(self.show_smooth_curve_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_path_optimize_action = add_process_action = QAction('路径优化', self)
        add_process_action.triggered.connect(self.show_cut_optimize_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_merge_lines_action = add_process_action = QAction('合并相连线', self)
        add_process_action.triggered.connect(self.show_merge_lines_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_del_dup_lines_action = add_process_action = QAction('删除重线', self)
        add_process_action.triggered.connect(self.show_delete_duplicates_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_gen_parallel_action = add_process_action = QAction('生成平行线', self)
        add_process_action.triggered.connect(self.show_offset_path_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_data_check_action = add_process_action = QAction('数据检查', self)
        add_process_action.triggered.connect(self.show_data_check_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_fill_to_bitmap_action = add_process_action = QAction('填充成位图', self)
        add_process_action.triggered.connect(self.show_fill_bitmap_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_bridge_action = add_process_action = QAction('桥位', self)
        add_process_action.triggered.connect(self.show_bridge_dialog)
        self.process_menu.addAction(add_process_action)

        self.process_micro_joint_action = add_process_action = QAction('微连', self)
        add_process_action.triggered.connect(self.show_micro_joint_dialog)
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
        action.triggered.connect(self.show_auto_layout_dialog)
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
        self.group_action.setText(tr('Action_Group', '群组'))
        self.ungroup_action.setText(tr('Action_Ungroup', '解散群组'))
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
        self.fillet_action.setText(tr('Action_Fillet', '倒圆角'))
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
        self.auto_group_toolbar_action = self.create_tool_action_with_icon(
            'toolbar_row1_icons/icon1_column19.png',
            '自动群组',
            self.toggle_auto_group,
            is_checkable=True,
        )
        self.auto_group_toolbar_action.setChecked(bool(self.whiteboard.canvas.import_settings.get('auto_group', True)))
        self.toolbar1.addAction(self.auto_group_toolbar_action)
        self.group_toolbar_action = self.create_tool_action_with_icon(
            'toolbar_row1_icons/icon1_column20.png',
            '群组',
            self.group_selected_items,
        )
        self.group_toolbar_action.setEnabled(False)
        self.toolbar1.addAction(self.group_toolbar_action)
        self.ungroup_toolbar_action = self.create_tool_action_with_icon(
            'toolbar_row1_icons/icon1_column21.png',
            '解散群组',
            self.ungroup_selected_items,
        )
        self.ungroup_toolbar_action.setEnabled(False)
        self.toolbar1.addAction(self.ungroup_toolbar_action)


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
        action = self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column4.png', 'Mark点定位', None)
        action.setEnabled(False)
        self.toolbar2.addAction(action)
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column5.png', '曲线平滑', self.show_smooth_curve_dialog))
        self.toolbar2.addSeparator()
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column6.png', '位图处理', self.show_bitmap_process_dialog))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column7.png', '曲线自动闭合', self.show_auto_close_dialog))
        self.toolbar2.addSeparator()
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column8.png', '切割优化', self.show_cut_optimize_dialog))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column9.png', '合并相连线', self.show_merge_lines_dialog))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column10.png', '删除重线', self.show_delete_duplicates_dialog))
        self.toolbar2.addAction(self.create_tool_action_with_icon('toolbar_row2_icons/icon2_column11.png', '平行线', self.show_offset_path_dialog))
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
        self.toolbar3.addAction(self.create_tool_action_with_icon('toolbar_row3_icons/icon3_column3.png', '修改尺寸', self.open_resize_dialog))
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
        
        # [Fix] 如果没有通过标准选择机制选中的项（因为节点编辑模式下可能清空了Selection），
        # 尝试获取当前激活的节点编辑对象
        if not selected_paths and hasattr(self.whiteboard.canvas, '_active_node_edit_item'):
            active_item = getattr(self.whiteboard.canvas, '_active_node_edit_item', None)
            if active_item and isinstance(active_item, EditablePathItem) and getattr(active_item, '_node_edit_enabled', False):
                selected_paths = [active_item]

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
            selected = self.whiteboard.canvas.get_selected_items()
            has_selection = bool(selected)
            can_group = len(selected) >= 2
            can_ungroup = any(get_item_group_id(item) is not None for item in selected)
            if hasattr(self, 'left_toolbar'):
                self.left_toolbar.update_selection_dependent_tools(has_selection)
            if hasattr(self, 'group_toolbar_action'):
                self.group_toolbar_action.setEnabled(can_group)
            if hasattr(self, 'ungroup_toolbar_action'):
                self.ungroup_toolbar_action.setEnabled(can_ungroup)
            if hasattr(self, 'group_action'):
                self.group_action.setEnabled(can_group)
            if hasattr(self, 'ungroup_action'):
                self.ungroup_action.setEnabled(can_ungroup)
        except Exception:
            pass

    def toggle_auto_group(self, checked):
        try:
            self.whiteboard.canvas.import_settings['auto_group'] = bool(checked)
            self.show_status_message('自动群组: 开' if checked else '自动群组: 关')
        except Exception:
            pass

    def group_selected_items(self):
        try:
            ok, _ = self.whiteboard.canvas.group_selected_items()
            if ok:
                self.show_status_message('已群组')
            else:
                self.show_status_message('请至少选择两个对象')
            self.update_toolbar_selection_state()
        except Exception as e:
            self.show_status_message(f'群组失败: {e}')

    def ungroup_selected_items(self):
        try:
            ok, _ = self.whiteboard.canvas.ungroup_selected_items()
            if ok:
                self.show_status_message('已解散群组')
            else:
                self.show_status_message('当前选择不在群组中')
            self.update_toolbar_selection_state()
        except Exception as e:
            self.show_status_message(f'解散群组失败: {e}')

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

    def show_fillet_dialog(self):
        """显示倒圆角对话框"""
        if self._fillet_dialog is None:
            dlg = FilletDialog(self)
            dlg.setModal(False)
            dlg.manualRequested.connect(self._on_fillet_manual_requested)
            dlg.autoRequested.connect(self._on_fillet_auto_requested)
            dlg.finished.connect(self._on_fillet_dialog_closed)
            self._fillet_dialog = dlg

        self._fillet_dialog.show()
        self._fillet_dialog.raise_()
        self._fillet_dialog.activateWindow()

    def _on_fillet_dialog_closed(self, _result):
        self._fillet_dialog = None

    def _on_fillet_manual_requested(self):
        if not self._fillet_dialog:
            return
        radius, min_angle, max_angle = self._fillet_dialog.get_values()
        self._start_manual_fillet(radius, min_angle, max_angle)

    def _on_fillet_auto_requested(self):
        if not self._fillet_dialog:
            return
        radius, min_angle, max_angle = self._fillet_dialog.get_values()
        self._apply_auto_fillet(radius, min_angle, max_angle)

    def _sanitize_fillet_params(self, radius, min_angle, max_angle):
        try:
            radius = float(radius)
        except Exception:
            radius = 0.0
        try:
            min_angle = float(min_angle)
        except Exception:
            min_angle = 0.0
        try:
            max_angle = float(max_angle)
        except Exception:
            max_angle = 180.0

        if radius < 0:
            radius = 0.0
        min_angle = max(0.0, min(180.0, min_angle))
        max_angle = max(0.0, min(180.0, max_angle))
        if min_angle > max_angle:
            min_angle, max_angle = max_angle, min_angle
        return radius, min_angle, max_angle

    def _apply_auto_fillet(self, radius, min_angle, max_angle):
        radius, min_angle, max_angle = self._sanitize_fillet_params(radius, min_angle, max_angle)
        if radius <= 0:
            QMessageBox.warning(self, "提示", "圆角半径必须大于0")
            return

        selected_items = self.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择图形")
            return

        target_items = [item for item in selected_items if isinstance(item, EditablePathItem)]
        if not target_items:
            QMessageBox.warning(self, "提示", "所选对象不支持倒圆角")
            return

        commands = []
        for item in target_items:
            new_data, applied = self._build_fillet_path_data(item.points(), radius, min_angle, max_angle)
            if new_data and applied > 0:
                cmd = UpdatePathDataCommand(item, new_data, desc="倒圆角")
                cmd.redo()
                commands.append(cmd)

        if not commands:
            QMessageBox.information(self, "提示", "没有符合角度范围的角点")
            return

        if len(commands) == 1:
            self.whiteboard.canvas.edit_manager.push_undo(commands[0])
        else:
            macro = MacroCommand("倒圆角")
            macro.desc = "倒圆角"
            for cmd in commands:
                macro.add_command(cmd)
            self.whiteboard.canvas.edit_manager.push_undo(macro)

    def _start_manual_fillet(self, radius, min_angle, max_angle):
        radius, min_angle, max_angle = self._sanitize_fillet_params(radius, min_angle, max_angle)
        if radius <= 0:
            QMessageBox.warning(self, "提示", "圆角半径必须大于0")
            return

        selected_items = self.whiteboard.canvas.scene.selectedItems()
        target_items = [item for item in selected_items if isinstance(item, EditablePathItem)]
        if not target_items:
            QMessageBox.warning(self, "提示", "请先选择图形")
            return

        self._fillet_last_hit = None

        def probe(pos):
            info = self._find_fillet_corner(pos, radius, min_angle, max_angle)
            self._fillet_last_hit = info
            return bool(info)

        def apply_at(pos):
            info = self._find_fillet_corner(pos, radius, min_angle, max_angle)
            if not info:
                info = self._fillet_last_hit
            if not info:
                self.show_status_message('未命中角点')
                return False
            item = info['item']
            index = info['index']
            try:
                base_path_data = item.get_path_data()
            except Exception:
                base_path_data = None
            new_data, applied = self._build_fillet_path_data(
                item.points(),
                radius,
                min_angle,
                max_angle,
                target_index=index,
                base_path_data=base_path_data
            )
            if not new_data or applied <= 0:
                self.show_status_message('未能倒圆角：半径过大或角度不在范围内')
                return False
            cmd = UpdatePathDataCommand(item, new_data, desc="倒圆角")
            cmd.redo()
            self.whiteboard.canvas.edit_manager.push_undo(cmd)
            try:
                self.whiteboard.canvas.scene.update()
            except Exception:
                pass
            self.show_status_message('倒圆角完成')
            return True

        self.whiteboard.canvas.enable_fillet_pick(probe, apply_at)
        self.show_status_message('手动倒圆角：移动到角点出现小孔后点击，右键退出')

    def _find_fillet_corner(self, pos, radius, min_angle, max_angle):
        try:
            scale = self.whiteboard.canvas.transform().m11()
        except Exception:
            scale = 1.0
        tol = 5.0 / scale if scale > 0 else 5.0
        tol_fallback = 12.0 / scale if scale > 0 else 12.0

        selected_items = self.whiteboard.canvas.scene.selectedItems()
        target_items = [item for item in selected_items if isinstance(item, EditablePathItem)]
        if not target_items:
            return None

        best = None
        best_dist = None
        for item in target_items:
            try:
                in_bounds = item.sceneBoundingRect().contains(pos)
            except Exception:
                in_bounds = False
            pts, closed = self._normalize_path_points(item.points())
            n = len(pts)
            if n < 3:
                continue

            indices = range(n) if closed else range(1, n - 1)
            for i in indices:
                bx, by = pts[i]
                dx = pos.x() - bx
                dy = pos.y() - by
                dist = math.hypot(dx, dy)
                if dist > tol:
                    if not in_bounds or dist > tol_fallback:
                        continue
                if dist > tol and not in_bounds:
                    continue
                info = self._compute_fillet_corner(pts, i, closed, radius)
                if not info:
                    continue
                if info['angle_deg'] < min_angle or info['angle_deg'] > max_angle:
                    continue
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best = {'item': item, 'index': i}

        return best

    def _normalize_fillet_path_data(self, path_data):
        try:
            pts_raw, segs_raw, cps_raw = path_data
        except Exception:
            return None

        pts, closed = self._normalize_path_points(pts_raw)
        n = len(pts)
        if n < 2:
            return None

        seg_count = n if closed else (n - 1)

        segs = [0] * seg_count
        try:
            src_segs = list(segs_raw) if segs_raw is not None else []
        except Exception:
            src_segs = []
        for i in range(min(seg_count, len(src_segs))):
            segs[i] = 1 if bool(src_segs[i]) else 0

        cps = {}
        try:
            src_cps = dict(cps_raw) if cps_raw is not None else {}
        except Exception:
            src_cps = {}
        for k, v in src_cps.items():
            try:
                idx = int(k)
            except Exception:
                continue
            if not (0 <= idx < seg_count):
                continue
            try:
                cp1, cp2 = v
                cps[idx] = ((float(cp1[0]), float(cp1[1])), (float(cp2[0]), float(cp2[1])))
            except Exception:
                continue

        return pts, closed, segs, cps

    def _normalize_path_points(self, points):
        if len(points) >= 2:
            x0, y0 = points[0]
            x1, y1 = points[-1]
            if math.hypot(x0 - x1, y0 - y1) < 1e-6:
                return points[:-1], True
        return points[:], False

    def _compute_fillet_corner(self, pts, index, closed, radius):
        n = len(pts)
        if n < 3:
            return None

        if closed:
            prev_idx = (index - 1) % n
            next_idx = (index + 1) % n
        else:
            if index <= 0 or index >= n - 1:
                return None
            prev_idx = index - 1
            next_idx = index + 1

        ax, ay = pts[prev_idx]
        bx, by = pts[index]
        cx, cy = pts[next_idx]

        v1x, v1y = bx - ax, by - ay
        v2x, v2y = cx - bx, cy - by
        len1 = math.hypot(v1x, v1y)
        len2 = math.hypot(v2x, v2y)
        if len1 < 1e-6 or len2 < 1e-6:
            return None

        d1x, d1y = v1x / len1, v1y / len1
        d2x, d2y = v2x / len2, v2y / len2

        dot = max(-1.0, min(1.0, d1x * d2x + d1y * d2y))
        angle_between = math.acos(dot)
        interior = math.pi - angle_between
        if interior <= 1e-6 or interior >= math.pi - 1e-6:
            return None

        t = radius * math.tan(interior / 2.0)
        if t <= 1e-6 or t > len1 - 1e-6 or t > len2 - 1e-6:
            return None

        p1 = (bx - d1x * t, by - d1y * t)
        p2 = (bx + d2x * t, by + d2y * t)

        control_dist = (4.0 / 3.0) * math.tan(angle_between / 4.0) * radius
        cp1 = (p1[0] + d1x * control_dist, p1[1] + d1y * control_dist)
        cp2 = (p2[0] - d2x * control_dist, p2[1] - d2y * control_dist)

        return {
            'p1': p1,
            'p2': p2,
            'cp1': cp1,
            'cp2': cp2,
            'angle_deg': math.degrees(interior)
        }

    def _build_fillet_path_data(self, points, radius, min_angle, max_angle, target_index=None, base_path_data=None):
        pts, closed = self._normalize_path_points(points)
        n = len(pts)
        if n < 3:
            return None, 0

        if target_index is not None and base_path_data is not None:
            normalized = self._normalize_fillet_path_data(base_path_data)
            if normalized:
                pts2, closed2, base_seg_types, base_control_points = normalized
                if len(pts2) >= 3:
                    pts, closed = pts2, closed2
                    n = len(pts)

                info = self._compute_fillet_corner(pts, target_index, closed, radius)
                if not info or info['angle_deg'] < min_angle or info['angle_deg'] > max_angle:
                    return None, 0

                prev_idx = (target_index - 1) % n
                next_idx = (target_index + 1) % n
                prev_label = ('v', prev_idx)
                next_label = ('v', next_idx)
                p1_label = ('p1', target_index)
                p2_label = ('p2', target_index)

                new_pts_unique = []
                new_labels = []
                for old_idx in range(n):
                    if old_idx == target_index:
                        new_pts_unique.append(info['p1'])
                        new_labels.append(p1_label)
                        new_pts_unique.append(info['p2'])
                        new_labels.append(p2_label)
                    else:
                        new_pts_unique.append(pts[old_idx])
                        new_labels.append(('v', old_idx))

                if closed:
                    segment_total = len(new_pts_unique)
                else:
                    segment_total = max(0, len(new_pts_unique) - 1)

                new_seg_types = []
                new_control_points = {}

                for seg_idx in range(segment_total):
                    a_label = new_labels[seg_idx]
                    if closed:
                        b_label = new_labels[(seg_idx + 1) % len(new_labels)]
                    else:
                        b_label = new_labels[seg_idx + 1]

                    seg_type = 0
                    cp = None

                    if a_label == prev_label and b_label == p1_label:
                        seg_type = 0
                    elif a_label == p1_label and b_label == p2_label:
                        seg_type = 1
                        cp = (info['cp1'], info['cp2'])
                    elif a_label == p2_label and b_label == next_label:
                        seg_type = 0
                    elif a_label[0] == 'v' and b_label[0] == 'v':
                        a_idx = a_label[1]
                        b_idx = b_label[1]
                        if closed:
                            valid_old_edge = (b_idx == ((a_idx + 1) % n))
                        else:
                            valid_old_edge = (b_idx == (a_idx + 1))

                        if valid_old_edge and 0 <= a_idx < len(base_seg_types):
                            seg_type = 1 if bool(base_seg_types[a_idx]) else 0
                            if seg_type == 1 and a_idx in base_control_points:
                                cp = base_control_points[a_idx]

                    new_seg_types.append(seg_type)
                    if seg_type == 1 and cp is not None:
                        new_control_points[len(new_seg_types) - 1] = cp

                new_pts = new_pts_unique[:]
                if closed and new_pts:
                    new_pts.append(new_pts[0])

                return (new_pts, new_seg_types, new_control_points), 1

        def add_point(new_pts, seg_types, control_points, pt, seg_type=0, cp=None):
            if not new_pts:
                new_pts.append(pt)
                return
            lx, ly = new_pts[-1]
            if math.hypot(lx - pt[0], ly - pt[1]) < 1e-6:
                return
            new_pts.append(pt)
            seg_types.append(seg_type)
            if seg_type == 1 and cp:
                control_points[len(seg_types) - 1] = cp

        new_pts = []
        seg_types = []
        control_points = {}
        applied = 0

        indices = range(n) if closed else range(1, n - 1)

        if not closed:
            new_pts.append(pts[0])

        for i in indices:
            if (target_index is not None) and (i != target_index):
                if closed or (i != 0 and i != n - 1):
                    add_point(new_pts, seg_types, control_points, pts[i], seg_type=0)
                continue

            info = self._compute_fillet_corner(pts, i, closed, radius)
            if not info or info['angle_deg'] < min_angle or info['angle_deg'] > max_angle:
                if closed or (i != 0 and i != n - 1):
                    add_point(new_pts, seg_types, control_points, pts[i], seg_type=0)
                continue

            add_point(new_pts, seg_types, control_points, info['p1'], seg_type=0)
            add_point(new_pts, seg_types, control_points, info['p2'], seg_type=1, cp=(info['cp1'], info['cp2']))
            applied += 1

        if not closed:
            add_point(new_pts, seg_types, control_points, pts[-1], seg_type=0)
        else:
            if new_pts:
                sx, sy = new_pts[0]
                ex, ey = new_pts[-1]
                if math.hypot(sx - ex, sy - ey) > 1e-6:
                    add_point(new_pts, seg_types, control_points, (sx, sy), seg_type=0)

        if applied <= 0:
            return None, 0

        return (new_pts, seg_types, control_points), applied

    def show_delete_duplicates_dialog(self):
        """显示删除重线对话框"""
        # 检查是否有选中项
        items = self.whiteboard.canvas.scene.selectedItems()
        if not items:
            QMessageBox.warning(self, "提示", "请先选择图形")
            return
            
        from .delete_duplicates_dialog import DeleteDuplicatesDialog
        dlg = DeleteDuplicatesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            tolerance = dlg.get_tolerance()
            self._delete_duplicates(items, tolerance)

    def _delete_duplicates(self, selected_items, tolerance):
        """执行删除重线逻辑"""
        if not selected_items:
            return

        from edit.commands import DeleteItemsCommand
        from ui.graphics_items import EditablePathItem
        import math
        
        to_delete = []
        n = len(selected_items)
        if n < 2:
            QMessageBox.information(self, "提示", "至少需要选中2个图形才能进行重线检查")
            return
            
        processed = [False] * n

        def is_same_points(pts1, pts2, tol):
            if len(pts1) != len(pts2):
                return False
            # 正向比较
            match_forward = True
            for i in range(len(pts1)):
                d = math.hypot(pts1[i][0] - pts2[i][0], pts1[i][1] - pts2[i][1])
                if d > tol:
                    match_forward = False
                    break
            if match_forward: return True
            
            # 反向比较
            match_backward = True
            for i in range(len(pts1)):
                d = math.hypot(pts1[i][0] - pts2[len(pts2)-1-i][0], pts1[i][1] - pts2[len(pts2)-1-i][1])
                if d > tol:
                    match_backward = False
                    break
            return match_backward
        
        for i in range(n):
            if processed[i]:
                continue
            item_a = selected_items[i]
            # 只有 EditablePathItem 参与比较
            if not isinstance(item_a, EditablePathItem):
                continue
            pts_a = item_a.points()
            
            for j in range(i + 1, n):
                if processed[j]:
                    continue
                item_b = selected_items[j]
                if not isinstance(item_b, EditablePathItem):
                    continue
                pts_b = item_b.points()
                
                if is_same_points(pts_a, pts_b, tolerance):
                    to_delete.append(item_b)
                    processed[j] = True
        
        if to_delete:
            cmd = DeleteItemsCommand(self.whiteboard.canvas.scene, to_delete)
            cmd.redo()
            self.whiteboard.canvas.edit_manager.push_undo(cmd)
            
        QMessageBox.warning(self, "Laser", f"已删除重叠线数:{len(to_delete)}")

    def show_bridge_dialog(self):
        """显示桥位对话框"""
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        from ui.graphics_items import EditablePathItem
        selected_paths = [item for item in selected_items if isinstance(item, EditablePathItem)]
        
        if not selected_paths:
            QMessageBox.warning(self, "提示", "请选择曲线对象")
            return
            
        from .bridge_dialog import BridgeDialog
        dlg = BridgeDialog(self, selected_paths)
        if dlg.exec_() == QDialog.Accepted:
            # Get bridge definitions: Map { item: [d1, d2, ...] }
            bridge_map = dlg.get_result_bridges()
            width = dlg.get_width()
            self._apply_bridges(bridge_map, width)

    def _is_micro_joint_target(self, item):
        from PyQt5.QtWidgets import (
            QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem,
            QGraphicsRectItem, QGraphicsLineItem, QGraphicsPolygonItem,
            QGraphicsPixmapItem, QGraphicsTextItem
        )
        from ui.graphics_items import EditablePathItem, EditableEllipseItem, TextGraphicsItem

        if item is None:
            return False
        try:
            if item.parentItem() is not None:
                return False
        except Exception:
            return False

        try:
            if not (item.flags() & QGraphicsItem.ItemIsSelectable):
                return False
        except Exception:
            return False

        canvas = self.whiteboard.canvas
        for system_item in (
            getattr(canvas, '_work_item', None),
            getattr(canvas, '_fiducial_item', None),
            getattr(canvas, '_path_preview_item', None),
            getattr(canvas, '_node_select_rect_item', None),
        ):
            if system_item is not None and item is system_item:
                return False

        return isinstance(item, (
            EditablePathItem,
            EditableEllipseItem,
            TextGraphicsItem,
            QGraphicsPathItem,
            QGraphicsEllipseItem,
            QGraphicsRectItem,
            QGraphicsLineItem,
            QGraphicsPolygonItem,
            QGraphicsPixmapItem,
            QGraphicsTextItem,
        ))

    def _get_micro_joint_marker_anchor(self, item):
        from PyQt5.QtGui import QPainterPath
        from PyQt5.QtWidgets import (
            QGraphicsPathItem, QGraphicsLineItem, QGraphicsRectItem,
            QGraphicsEllipseItem, QGraphicsPolygonItem
        )

        try:
            if isinstance(item, QGraphicsPathItem):
                path = item.path()
                if not path.isEmpty():
                    return path.pointAtPercent(0.0)

            if isinstance(item, QGraphicsLineItem):
                return item.line().p1()

            if isinstance(item, QGraphicsRectItem):
                return item.rect().topLeft()

            if isinstance(item, QGraphicsEllipseItem):
                path = QPainterPath()
                path.addEllipse(item.rect())
                if not path.isEmpty():
                    return path.pointAtPercent(0.0)

            if isinstance(item, QGraphicsPolygonItem):
                poly = item.polygon()
                if poly.count() > 0:
                    return poly[0]

            if hasattr(item, 'shape'):
                shape = item.shape()
                if not shape.isEmpty():
                    return shape.pointAtPercent(0.0)

            rect = item.boundingRect()
            if rect.isValid():
                return rect.topLeft()
        except Exception:
            pass
        return None

    def _remove_micro_joint_marker(self, item):
        marker = getattr(item, '_micro_joint_marker_item', None)
        if marker is None:
            return
        try:
            scene = marker.scene()
            if scene:
                scene.removeItem(marker)
        except Exception:
            pass
        try:
            marker.setParentItem(None)
        except Exception:
            pass
        try:
            delattr(item, '_micro_joint_marker_item')
        except Exception:
            item._micro_joint_marker_item = None

    def _sync_micro_joint_marker(self, item):
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPainterPath, QPen, QBrush
        from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPathItem
        from ui.graphics_items import EditablePathItem, EditableEllipseItem

        config = getattr(item, 'micro_joint_config', None)
        enabled = bool(config and config.get('enabled', False))

        if isinstance(item, (EditablePathItem, EditableEllipseItem)):
            self._remove_micro_joint_marker(item)
            return

        if not enabled:
            self._remove_micro_joint_marker(item)
            return

        marker_pos = self._get_micro_joint_marker_anchor(item)
        if marker_pos is None:
            self._remove_micro_joint_marker(item)
            return

        marker = getattr(item, '_micro_joint_marker_item', None)
        if marker is None or marker.scene() is None:
            cross_size = 4.0
            cross = QPainterPath()
            cross.moveTo(-cross_size, -cross_size)
            cross.lineTo(cross_size, cross_size)
            cross.moveTo(-cross_size, cross_size)
            cross.lineTo(cross_size, -cross_size)

            marker = QGraphicsPathItem(cross, item)
            pen = QPen(Qt.blue, 2.0)
            pen.setCosmetic(True)
            marker.setPen(pen)
            marker.setBrush(QBrush(Qt.NoBrush))
            marker.setZValue(1000000)
            marker.setAcceptedMouseButtons(Qt.NoButton)
            marker.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            item._micro_joint_marker_item = marker

        marker.setPos(marker_pos)
        marker.setVisible(True)

    def show_micro_joint_dialog(self):
        """显示微连对话框"""
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        selected_paths = [item for item in selected_items if self._is_micro_joint_target(item)]
        
        # User request: "Enable Micro-joint" is selectable if items are selected. 
        # But per latest request, controls are ALWAYS enabled in UI.
        # But we still need to know if we are in "Edit Mode" (applying to current selection)
        # or "Find Mode" (selecting new items).
        
        has_selection = len(selected_paths) > 0
        
        dlg = MicroJointDialog(self)
        
        # We don't need to set_has_selection visually anymore as controls are always enabled.
        # But we might want to check the box if the SELECTED item already has micro-joint enabled?
        # That would be a nice touch.
        if has_selection:
            # Check the first item
            first_item = selected_paths[0]
            if hasattr(first_item, 'micro_joint_config') and first_item.micro_joint_config:
                cfg = first_item.micro_joint_config
                dlg.cb_enable.setChecked(cfg.get('enabled', False))
                dlg.spin_qty.setValue(int(cfg.get('qty', 1)))
                dlg.spin_dist.setValue(float(cfg.get('dist', 1.0)))
                dlg.spin_width.setValue(float(cfg.get('width', 2.0)))
                mode = cfg.get('mode', 'qty')
                if mode == 'qty': dlg.rb_qty.setChecked(True)
                else: dlg.rb_dist.setChecked(True)
                
                dlg.update_ui_state()
        
        # Connect signal before exec
        dlg.apply_micro_joint.connect(lambda cfg, flt: self._handle_micro_joint_apply(cfg, flt, dlg))
        
        dlg.exec_()

    def _handle_micro_joint_apply(self, config, filters, dlg_instance):
        _ = dlg_instance
        scene = self.whiteboard.canvas.scene
        selected_items = scene.selectedItems()
        target_items = [item for item in selected_items if self._is_micro_joint_target(item)]
        
        # Logic: 
        # If we have selection, apply to it.
        # If we have NO selection, find items based on filters, SELECT them.
        # But user says: "After clicking 'Select'... objects are selected... (or maybe not)".
        # This implies: Always try to filter-select if current selection is empty?
        # Or always respect filters?
        # Usually: If I manually selected items, I want to apply to THEM, ignoring filters.
        # If I selected nothing, I implies I want to use the filters to find items.
        
        did_search = False
        if not target_items:
            # Search mode
            did_search = True
            found_items = []
            for item in scene.items():
                if self._is_micro_joint_target(item):
                    rect = item.sceneBoundingRect()
                    w = rect.width()
                    h = rect.height()
                    
                    # Logic
                    sm_w = filters['small_max_w']
                    sm_h = filters['small_max_h']
                    lm_w = filters['large_min_w']
                    lm_h = filters['large_min_h']
                    
                    is_small = (w <= sm_w and h <= sm_h)
                    is_large = (w >= lm_w and h >= lm_h)
                    is_mid = (not is_small) and (not is_large)
                    
                    select_it = False
                    if filters['check_small'] and is_small: select_it = True
                    if filters['check_mid'] and is_mid: select_it = True
                    if filters['check_large'] and is_large: select_it = True
                    
                    if select_it:
                        found_items.append(item)
            
            # Select them
            if found_items:
                scene.clearSelection()
                for item in found_items:
                    item.setSelected(True)
                target_items = found_items
            else:
                 QMessageBox.information(self, "提示", "未找到符合条件的图形")
                 return # Nothing to apply to

        # Now apply the config to target_items
        # But only if user checked "Enable"?
        # User said: "Enable is selected AFTER objects are selected".
        # If I click Select (and items are found), the checkbox should become CHECKED?
        # Or user manually checks it?
        # "Selected... (checkbox) becomes bright". Bright means "Enabled state" (clickable).
        # My UI fix made it ALWAYS clickable.
        
        # If I click "Select", I am saying "Apply these settings".
        # The settings include "Enable Micro-joint: True/False".
        # If the user UNCHECKED "Enable", they mean "Disable Micro-joint on these items".
        # If the user CHECKED "Enable", they mean "Enable it".
        
        # CAUTION: If I am in "Search Mode" (did_search=True), 
        # the user might just want to SEE what is selected first, BEFORE applying micro-joints?
        # User says: "Click Select... objects are selected... (checkbox) becomes bright."
        # This implies the first click on "Select" MIGHT just be for Selection if nothing is selected?
        # And then user checks "Enable" and clicks "Select" again?
        
        # But current "Select" button triggers `_handle_micro_joint_apply`.
        # If I just selected items, do I also apply the config immediately?
        # If config['enabled'] is False (default), applying it means "Clear Micro-joints".
        # If I just found items, I probably don't want to clear their joints immediately if they had any.
        
        # Let's interpret "Select" button as:
        # 1. Update Selection (if empty).
        # 2. Apply parameters (if enabled is checked OR if we want to enforce current state).
        
        # If I change selection, I should probably STOP there and let user Check "Enable".
        if did_search:
             # Just updated selection.
             # User expects checkbox to become "Bright" (it is always bright now).
             # User might expect it to Auto-Check? No, "Select objects... then Enable".
             # So we stop here?
             # But if I already had "Enable" checked for search?
             # Probably apply if checked.
             pass
        
        # Apply Logic
        if config.get('enabled', False):
            for item in target_items:
                item.micro_joint_config = config.copy()
                self._sync_micro_joint_marker(item)
                item.update()
        else:
            # If Disabled, and we are targeting items.
            # Should we clear?
            # User unchecks Enable -> Click Select -> Clears joints.
            # Sounds correct.
            # But if we just did a search (did_search=True) and Enable was False (default),
            # we shouldn't wipe existing joints?
            # Let's assume search mode shouldn't destructively modify unless explicitly enabled.
            if not did_search:
                for item in target_items:
                    item.micro_joint_config = None
                    self._sync_micro_joint_marker(item)
                    item.update()

    def show_offset_path_dialog(self):
        """显示生成平行线对话框"""
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        from ui.graphics_items import EditablePathItem
        selected_paths = [item for item in selected_items if isinstance(item, EditablePathItem)]
        
        if not selected_paths:
            QMessageBox.warning(self, "提示", "请选择曲线对象")
            return

        from .offset_path_dialog import OffsetPathDialog
        dlg = OffsetPathDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            self._apply_offset_path(selected_paths, data)

    def _apply_offset_path(self, items, data):
        """应用平行线生成"""
        try:
            dist = float(data['distance'])
        except:
            return

        mode = data['mode']
        delete_original = data['delete_original']
        round_corners = data['round_corners']
        
        if dist == 0: return

        from PyQt5.QtGui import QPainterPathStroker, QPainterPath, QColor
        from PyQt5.QtCore import Qt
        from edit.commands import AddItemCommand, DeleteItemsCommand, MacroCommand
        from ui.graphics_items import EditablePathItem
        
        commands = []
        new_cnt = 0
        
        for item in items:
            # Reconstruct path to ensure it is topologically closed if geometrically closed
            pts_src = item.points()
            if not pts_src or len(pts_src) < 2: continue
            
            # 1. Clean consecutive duplicates
            cleaned_pts = [pts_src[0]]
            for pt in pts_src[1:]:
                # Check squared distance
                if (pt[0]-cleaned_pts[-1][0])**2 + (pt[1]-cleaned_pts[-1][1])**2 > 1e-9:
                    cleaned_pts.append(pt)

            path = QPainterPath()
            if not cleaned_pts: continue
            path.moveTo(*cleaned_pts[0])
            
            # Check closure
            is_closed = False
            if len(cleaned_pts) > 2:
                if (cleaned_pts[0][0]-cleaned_pts[-1][0])**2 + (cleaned_pts[0][1]-cleaned_pts[-1][1])**2 < 1e-9:
                    is_closed = True
                    # Remove last point which is duplicate of first
                    cleaned_pts.pop() 

            # Build QPainterPath
            if is_closed:
                for pt in cleaned_pts[1:]:
                    path.lineTo(*pt)
                path.closeSubpath()
            else:
                for pt in cleaned_pts[1:]:
                    path.lineTo(*pt)
            
            stroker = QPainterPathStroker()
            stroker.setWidth(abs(dist) * 2)
            stroker.setCapStyle(Qt.RoundCap if round_corners else Qt.FlatCap)
            stroker.setJoinStyle(Qt.RoundJoin if round_corners else Qt.MiterJoin)
            stroker.setMiterLimit(2.0)
            
            stroke_path = stroker.createStroke(path).simplified()
            sub_polys = stroke_path.toSubpathPolygons()
            
            if not sub_polys: continue
            
            # Sort by Area
            annotated = []
            for p in sub_polys:
                rect = p.boundingRect()
                area = rect.width() * rect.height()
                # Use signed area or similar if needed, but bounding box area is okay for basic determining outer/inner for simple loop
                annotated.append((area, p))
            
            # Sort descending: Largest (Outer) -> Smallest (Inner)
            annotated.sort(key=lambda x: x[0], reverse=True)
            
            target_polys = []
            sorted_polys = [p for a, p in annotated]
            
            if mode == 'both':
                target_polys = sorted_polys
            elif mode == 'outside' or mode == 'auto':
                # Largest is usually outer for a simple closed shape
                if sorted_polys:
                    target_polys.append(sorted_polys[0])
            elif mode == 'inside':
                # Smallest or all except largest
                # For a simple rect loop, sorted_polys has 2 elements. [Outer, Inner].
                # Inner is index 1.
                if len(sorted_polys) > 1:
                    target_polys.append(sorted_polys[1])
                elif len(sorted_polys) == 1 and not is_closed:
                    # If open path, stroke produces 1 poly (the outline). 
                    # Inside doesn't make sense really.
                    pass
            
            # Determine color
            color = QColor(Qt.black)
            if hasattr(item, 'pen'):
                color = item.pen().color()
            elif hasattr(item, '_color'):
                color = item._color

            for poly in target_polys:
                # Convert QPolygonF to pts list [[x,y], ...]
                pts = [[poly.at(i).x(), poly.at(i).y()] for i in range(poly.count())]
                
                # Close the loop
                if len(pts) > 2:
                     if pts[0] != pts[-1]:
                         pts.append(pts[0])
                
                new_item = EditablePathItem(pts, color)
                commands.append(AddItemCommand(self.whiteboard.canvas, new_item))
                new_cnt += 1

        if delete_original and commands:
             commands.append(DeleteItemsCommand(self.whiteboard.canvas, items))
             
        if commands:
            macro = MacroCommand("生成平行线")
            macro.commands = commands
            macro.redo()
            self.whiteboard.canvas.edit_manager.push_undo(macro)
            self.whiteboard.canvas.scene.update()
            self.show_status_message(f"生成了 {new_cnt} 条平行线")

    def _apply_bridges(self, bridge_map, width):
        """应用桥位"""
        if not bridge_map: return
        
        from edit.bridge_commands import ReplaceItemsCommand
        from ui.graphics_items import EditablePathItem
        import math
        from PyQt5.QtGui import QColor

        scene = self.whiteboard.canvas.scene
        old_items = []
        new_items = []
        
        for item, cuts in bridge_map.items():
            if not cuts: continue
            
            old_items.append(item)
            pts = item.points()
            is_closed = item.is_closed()
            
            # Helper to calculate total length and segments
            segments = [] # [(len, p1, p2)]
            total_len = 0.0
            
            path_len = 0.0
            seg_info = [] # (start_d, length, p1, p2)
            
            for i in range(len(pts)-1):
                p1 = pts[i]
                p2 = pts[i+1]
                l = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                seg_info.append( (path_len, l, p1, p2) )
                path_len += l
            
            # Define keep intervals
            cuts.sort()
            
            # Map cuts to intervals to remove
            remove_intervals = []
            for c in cuts:
                s = c - width/2
                e = c + width/2
                
                if is_closed:
                    if s < 0:
                        remove_intervals.append( (s + path_len, path_len) )
                        remove_intervals.append( (0, e) )
                    elif e > path_len:
                        remove_intervals.append( (s, path_len) )
                        remove_intervals.append( (0, e - path_len) )
                    else:
                        remove_intervals.append( (s, e) )
                else:
                    s = max(0, s)
                    e = min(path_len, e)
                    if s < e:
                         remove_intervals.append( (s, e) )
                         
            remove_intervals.sort()
            merged = []
            if remove_intervals:
                curr_s, curr_e = remove_intervals[0]
                for i in range(1, len(remove_intervals)):
                    ns, ne = remove_intervals[i]
                    if ns < curr_e: 
                        curr_e = max(curr_e, ne)
                    else:
                        merged.append((curr_s, curr_e))
                        curr_s, curr_e = ns, ne
                merged.append((curr_s, curr_e))
            remove_intervals = merged
            
            keep_intervals = []
            curr = 0.0
            for s, e in remove_intervals:
                if s > curr:
                    keep_intervals.append((curr, s))
                curr = max(curr, e)
            
            if curr < path_len:
                keep_intervals.append((curr, path_len))
                
            final_intervals = keep_intervals
            if is_closed and len(remove_intervals) > 0:
                 if len(keep_intervals) > 1 and \
                    abs(keep_intervals[0][0] - 0) < 1e-9 and \
                    abs(keep_intervals[-1][1] - path_len) < 1e-9:
                      first = keep_intervals[0]
                      last = keep_intervals[-1]
                      merged_int = (last[0], path_len + first[1])
                      final_intervals = keep_intervals[1:-1] + [merged_int]
            
            
            def get_point_at(d):
                if d > path_len: d -= path_len
                
                cur_Accum = 0.0
                for start_d, l, p1_t, p2_t in seg_info:
                    if d <= start_d + l + 1e-9:
                        remain = d - start_d
                        t = remain / l if l > 0 else 0
                        x = p1_t[0] + (p2_t[0] - p1_t[0]) * t
                        y = p1_t[1] + (p2_t[1] - p1_t[1]) * t
                        return (x, y)
                    cur_Accum += l
                return pts[-1]
            
            def extract_subpath(d1, d2):
                sub_pts = []
                start_p = get_point_at(d1)
                sub_pts.append(start_p)
                
                effective_d2 = d2
                wrapped = False
                if d2 > path_len: 
                    effective_d2 = path_len
                    wrapped = True
                
                for i in range(len(pts)-1):
                     v_d = seg_info[i][0]
                     if v_d > d1 + 1e-5 and v_d < effective_d2 - 1e-5:
                         sub_pts.append(pts[i])

                if effective_d2 == path_len and not wrapped:
                    pass # Don't add last point if loop ends? Wait.
                
                end_p = get_point_at(effective_d2)
                sub_pts.append(end_p)
                
                if wrapped:
                    real_d2 = d2 - path_len
                    for i in range(len(pts)-1):
                        v_d = seg_info[i][0]
                        if v_d > 1e-5 and v_d < real_d2 - 1e-5:
                            sub_pts.append(pts[i])
                    sub_pts.append(get_point_at(real_d2))
                
                return sub_pts
            
            for s, e in final_intervals:
                # If interval is too small (bridge too close to corner/start?), skip?
                if abs(s-e) < 1e-5: continue
                new_pts = extract_subpath(s, e)
                if len(new_pts) >= 2:
                    new_item = EditablePathItem(new_pts, item.color(), getattr(item, '_smooth', False))
                    new_items.append(new_item)
                    
        if new_items:
            cmd = ReplaceItemsCommand(scene, old_items, new_items)
            self.whiteboard.canvas.edit_manager.push_undo(cmd)
            cmd.redo()

    def show_cut_optimize_dialog(self):
        """显示切割优化对话框"""
        from .cut_optimize_dialog import CutOptimizeDialog
        dlg = CutOptimizeDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            settings = dlg.get_settings()
            self.optimize_path(settings)

    def optimize_path(self, settings):
        """执行切割路径优化"""
        scene = self.whiteboard.canvas.scene
        from ui.graphics_items import EditablePathItem, EditableEllipseItem, TextGraphicsItem
        from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
        import math
        from PyQt5.QtCore import QPointF
        import heapq
        from collections import defaultdict
        
        # 1. 获取所有 path items (按照当前 Z 序，或者无关)
        items = list(scene.items())
        path_items = [item for item in items if isinstance(item, (EditablePathItem, EditableEllipseItem, TextGraphicsItem, QGraphicsPixmapItem, QGraphicsTextItem))]
        
        if not path_items:
             QMessageBox.information(self, "提示", "没有可优化的路径对象")
             return

        current_list = path_items[:] 
        
        # --- 策略 1: 按图层顺序 ---
        # 优先级数大的先加工 -> Descending Sort by Layer Priority
        if settings['layer_order']:
            # 尝试获取RightPanel的Layer Map
            try:
                # self.right_panel has layer logic?
                # RightPanel is self.right_panel in MainWindow
                if hasattr(self, 'right_panel'):
                    # 假设 right_panel 有 items() 或者 rows 包含 priority
                    # 参考 right_panel.py: LayerTable uses items. Each row represents a layer.
                    # QTableWidget items don't strictly bind to color unless we parse them.
                    # right_panel 应该有一个数据源维护 LayerParams.
                    # Searching `layer_params_map` didn't work. But `params.priority` exists.
                    # Let's assume right_panel.table (LayerTable) holds the truth.
                    
                    # 构建 Color -> Priority Map
                    color_priority_map = {}
                    table = self.right_panel.table
                    rowCount = table.rowCount()
                    for r in range(rowCount):
                        # Col 0: Color (Background)
                        item0 = table.item(r, 0)
                        if not item0: continue
                        brush = item0.background()
                        if not brush: continue
                        color = brush.color() # QColor
                        color_key = (color.red(), color.green(), color.blue())
                        
                        # Wait, priority is in which column?
                        # In right_panel.py: `self.priority_spin` is used to edit.
                        # Does table show priority?
                        # Probably not in table directly as value, or maybe in hidden column?
                        # Or maybe we rely on `DeviceManager` or `config`? 
                        
                        # 但是用户在 right panel 编辑 priority.
                        # 当选中一行时, priority_spin 显示 priority.
                        # 这意味着 priority 存储在某个地方。
                        # Item Data? 
                        # `LayerParams` class has `priority`.
                        # `item0` might store `LayerParams` object in `Qt.UserRole`?
                        # Let's check `right_panel.py` -> `update_row` or `add_row`
                        pass
                        
                        # 暂时方案：如果不确定，尝试从 UserRole 获取 params
                        layer_params = item0.data(Qt.UserRole)
                        if layer_params and hasattr(layer_params, 'priority'):
                            color_priority_map[color_key] = layer_params.priority
                    
                    # Sort function
                    def layer_sort_key(item):
                        # Get item color
                        pen = item.pen()
                        c = pen.color()
                        k = (c.red(), c.green(), c.blue())
                        return color_priority_map.get(k, 0) # Default 0
                    
                    # Reverse=True allows Larger Priority -> First
                    current_list.sort(key=layer_sort_key, reverse=True)
            except Exception as e:
                print(f"Sort by layer failed: {e}")

        # --- 策略：分块处理 ---
        h = settings['block_height']
        direction = settings['block_direction']
        
        def get_center(item):
            return item.sceneBoundingRect().center()
            
        def block_key(item):
            if h <= 0: return 0 
            c = get_center(item)
            
            if direction in ["从上到下", "从下到上"]:
                  # 水平分条
                  row_idx = int(c.y() / h)
                  prim = row_idx if direction == "从上到下" else -row_idx
                  sec = c.x() # 默认左到右
                  return (prim, sec)
            else:
                  # 垂直分条
                  col_idx = int(c.x() / h)
                  prim = col_idx if direction == "从左到右" else -col_idx
                  sec = c.y() # 默认上到下
                  return (prim, sec)
                  
        if h > 0:
            current_list.sort(key=block_key)
            
        # --- 策略: 拓扑排序 (由内到外 vs 由外到内/默认) ---
        # 如果勾选 "由内到外", 执行 Inner -> Outer.
        # 如果未勾选, 执行 Outer -> Inner (作为默认加工逻辑?). 
        # 用户需求: "如果不勾选这两项...默认的‘由外到内’".
        
        deps = defaultdict(list)
        indegree = {item: 0 for item in current_list}
        
        # 建立依赖关系
        # if Inside-Out checked: Inner comes before Outer. Edge Inner -> Outer.
        # if Inside-Out Unchecked (Default Outside-In): Outer comes before Inner. Edge Outer -> Inner.
        is_inside_out = settings['inside_out']
        
        for i, first in enumerate(current_list):
            first_rect = first.sceneBoundingRect()
            first_path = first.shape()
            
            for j, second in enumerate(current_list):
                if i == j: continue
                second_rect = second.sceneBoundingRect()
                
                # Check if first contains second
                if first_rect.contains(second_rect):
                    if first_path.contains(second_rect.center()):
                        # 'first' contains 'second' (first is Outer, second is Inner)
                        
                        if is_inside_out:
                            # Inner(second) -> Outer(first)
                            deps[second].append(first)
                            indegree[first] += 1
                        else:
                            # Outer(first) -> Inner(second)
                            # Default Logic as requested
                            deps[first].append(second)
                            indegree[second] += 1

        # 使用优先级队列进行拓扑排序，优先级由 Block Sort (或 Layer Sort) 决定 (即 original index 越小越先)
        order_map = {item: i for i, item in enumerate(current_list)}
        
        queue = []
        for item in current_list:
             if indegree[item] == 0:
                 # Priority Queue sorts by first element of tuple.
                 # Python's heap is min-heap. Smaller index -> processed first.
                 heapq.heappush(queue, (order_map[item], id(item), item)) 
                 
        sorted_result = []
        while queue:
             _, _, u = heapq.heappop(queue)
             sorted_result.append(u)
             
             for v in deps[u]:
                 indegree[v] -= 1
                 if indegree[v] == 0:
                     heapq.heappush(queue, (order_map[v], id(v), v))
         
        # Handle cycles (though unlikely for containment) or disconnected items not added
        if len(sorted_result) == len(current_list):
             current_list = sorted_result
        else:
             # Fallback if topological sort failed (cycle?)
             # Just append what's missing
             processed = set(sorted_result)
             remaining = [item for item in current_list if item not in processed]
             sorted_result.extend(remaining)
             current_list = sorted_result

        # --- 策略: 寻找切割点 ---

        # --- 策略: 寻找切割点 ---
        need_start_opt = (settings['inside_out_mode'] == "单个由内到外，寻找切割点") or settings['optimize_start'] or settings['auto_start_dir']
        
        if need_start_opt and len(current_list) > 0:
            last_pos = QPointF(0, 0)
            
            for item in current_list:
                # 1. 优化闭合图形起点
                if hasattr(item, 'is_closed') and item.is_closed() and hasattr(item, 'points'):
                    pts = item.points()
                    if len(pts) > 1:
                        best_idx = 0
                        min_d = float('inf')
                        # 忽略重复的尾点
                        check_len = len(pts) - 1 if len(pts) > 2 else len(pts)
                        
                        for k in range(check_len):
                            p = pts[k]
                            d = (p[0]-last_pos.x())**2 + (p[1]-last_pos.y())**2
                            if d < min_d:
                                min_d = d
                                best_idx = k
                        
                        if best_idx != 0:
                            if hasattr(item, 'change_start_point'):
                                item.change_start_point(best_idx)

                # 2. 更新终点位置
                if hasattr(item, 'points'):
                    pts = item.points()
                    if pts:
                        last_pos = QPointF(*pts[-1])

        # --- 应用顺序: 设置 Z-Values ---
        for i, item in enumerate(current_list):
            item.setZValue(i)
        
        scene.update()
        QMessageBox.information(self, "完成", f"已优化 {len(current_list)} 个对象的切割路径")

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


    def show_merge_lines_dialog(self):
        """显示合并相连线对话框"""
        # 获取选中项
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        target_items = [item for item in selected_items if isinstance(item, EditablePathItem)]
        
        if len(target_items) != 2:
            QMessageBox.warning(self, "提示", "请选择两条待合并的曲线路径")
            return

        # 显示对话框
        from ui.merge_lines_dialog import MergeLinesDialog
        dlg = MergeLinesDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
            
        tolerance = dlg.get_tolerance()
        
        item1 = target_items[0]
        item2 = target_items[1]
        
        ptsA = item1.points()
        ptsB = item2.points()
        
        import math
        def dist(p1, p2):
            return math.hypot(p1[0]-p2[0], p1[1]-p2[1])
            
        d_es = dist(ptsA[-1], ptsB[0])  # Tail A -> Head B
        d_se = dist(ptsA[0], ptsB[-1])  # Head A -> Tail B
        d_ee = dist(ptsA[-1], ptsB[-1]) # Tail A -> Tail B
        d_ss = dist(ptsA[0], ptsB[0])   # Head A -> Head B
        
        best_d = float('inf')
        # mode: (swap_order, reverse_source1, reverse_source2)
        # source1 和 source2 指的是经过 swap_order 后的第一条和第二条曲线
        # 也就是说，最终是: (source1_maybe_reversed) -> 连接 -> (source2_maybe_reversed)
        mode = None 
        
        # 1. A + B (Tail A -> Head B): Keep A, Keep B. Order: A, B.
        if d_es < best_d: best_d, mode = d_es, (False, False, False)
        
        # 2. B + A (Tail B -> Head A): Keep B, Keep A. Order: B, A.
        if d_se < best_d: best_d, mode = d_se, (True, False, False)
        
        # 3. A + Rev(B) (Tail A -> Tail B): Keep A, Reverse B. Order: A, B.
        if d_ee < best_d: best_d, mode = d_ee, (False, False, True)
        
        # 4. Rev(A) + B (Head A -> Head B): Reverse A, Keep B. Order: A, B.
        if d_ss < best_d: best_d, mode = d_ss, (False, True, False)
        
        if best_d > tolerance:
             QMessageBox.warning(self, "提示", f"无法合并：端点最近距离 ({best_d:.4f}) 超过容差")
             return
             
        # Merge
        swap, rev1, rev2 = mode
        source1 = item2 if swap else item1
        source2 = item1 if swap else item2
        
        # 如果 source1 是 item2 (swap=True)，那么 rev1 对应的是 item2 的反转状态
        # 所以这里的 rev1, rev2 直接用于 source1, source2 是正确的
        
        def get_data(itm, rev):
            pts = itm.points()
            segs = getattr(itm, '_segment_types', [])
            cps = getattr(itm, '_control_points', {})
            
            expected_segs = max(0, len(pts)-1)
            if len(segs) < expected_segs:
                segs.extend([1]*(expected_segs-len(segs)))
            segs = segs[:expected_segs]

            data = (pts, segs, cps)
            if rev:
                data = EditablePathItem.reverse_path_data(data)
            return data
            
        p1, s1, c1 = get_data(source1, rev1)
        p2, s2, c2 = get_data(source2, rev2)
        
        new_pts = p1 + p2
        # 连接处使用曲线(type=1)
        new_segs = s1 + [1] + s2
        
        shift = len(s1) + 1
        new_cps = c1.copy()
        for k, v in c2.items():
            new_cps[k + shift] = v
           
        merged_item = EditablePathItem(new_pts, source1._color, smooth=True)
        merged_item._segment_types = new_segs
        merged_item._control_points = new_cps
        merged_item._update_path()
        merged_item.setPen(source1.pen())
        
        # 使用 MergeItemsCommand 支持撤销
        from edit.merge_command import MergeItemsCommand
        cmd = MergeItemsCommand(self.whiteboard.canvas, item1, item2, merged_item)
        cmd.redo()
        self.whiteboard.canvas.edit_manager.push_undo(cmd)

    def show_data_check_dialog(self):
        """显示数据检查对话框"""
        dlg = DataCheckDialog(self.whiteboard.canvas, self)
        dlg.exec_()

    def show_fill_bitmap_dialog(self):
        """显示填充成位图对话框"""
        selected_items = self.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            # QMessageBox.warning(self, "提示", "请先选择要填充的对象")
            return

        # 检查闭合性
        from ui.graphics_items import EditablePathItem
        for item in selected_items:
            if isinstance(item, EditablePathItem):
                if not item.is_closed():
                    QMessageBox.warning(self, "Laser", "无闭合曲线!")
                    return

        dlg = FillBitmapDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
            
        dpi = float(dlg.get_dpi())
        
        # Calculate bounding rect
        rect = None
        target_items = []
        for item in selected_items:
            # 过滤掉非图形项，只保留路径和椭圆等矢量项
             if hasattr(item, 'path') or isinstance(item, QtWidgets.QGraphicsRectItem) or isinstance(item, QtWidgets.QGraphicsEllipseItem):
                 target_items.append(item)
                 if rect is None:
                     rect = item.sceneBoundingRect()
                 else:
                     rect = rect.united(item.sceneBoundingRect())
                     
        if rect is None or not target_items:
            return
            
        # Create Image
        # rect attributes are in scene units (mm)
        scale_factor = dpi / 25.4
        width_px = int(rect.width() * scale_factor) + 2 # Add buffer
        height_px = int(rect.height() * scale_factor) + 2
        
        if width_px <= 0 or height_px <= 0:
            return

        image = QtGui.QImage(width_px, height_px, QtGui.QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False) # Vector fill doesn't need AA if high res
        
        # Transform Logic:
        # We want to map Scene Coords to Image Pixels.
        # Image(0,0) corresponds to Scene(rect.x, rect.y).
        # And 1 Scene Unit = scale_factor Pixels.
        # So: Pixel = (Scene - Offset) * Scale
        
        painter.scale(scale_factor, scale_factor)
        painter.translate(-rect.x(), -rect.y())
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.black)
        
        # Draw items
        for item in target_items:
            if hasattr(item, 'path'): # QGraphicsPathItem, EditablePathItem
                path = item.path()
                scene_path = item.mapToScene(path)
                painter.drawPath(scene_path)
            elif isinstance(item, QtWidgets.QGraphicsRectItem):
                path = QtGui.QPainterPath()
                path.addRect(item.rect())
                scene_path = item.mapToScene(path)
                painter.drawPath(scene_path)
            elif isinstance(item, QtWidgets.QGraphicsEllipseItem):
                 path = QtGui.QPainterPath()
                 path.addEllipse(item.rect())
                 scene_path = item.mapToScene(path)
                 painter.drawPath(scene_path)
            
        painter.end()
        
        # Create Pixmap Item
        pixmap = QtGui.QPixmap.fromImage(image)
        pix_item = QGraphicsPixmapItem(pixmap)
        
        # Set Position (Scene coords)
        pix_item.setPos(rect.x(), rect.y())
        
        # Scale back to scene units
        # Pixmap item displays pixels. We scaled up by scale_factor.
        # So we must scale down by 1/scale_factor to match scene size.
        pix_item.setScale(1.0 / scale_factor)
        
        pix_item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        pix_item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        
        # Set Layer Data
        LAYER_COLOR_ROLE = Qt.UserRole + 100
        pix_item.setData(LAYER_COLOR_ROLE, QColor(Qt.black))
        
        self.whiteboard.canvas.scene.addItem(pix_item)
        pix_item.setSelected(True)
        
        # Deselect vector items
        for item in selected_items:
            item.setSelected(False)
        pix_item.setSelected(True)
        
        # Update Layers
        self.right_panel.update_layer_list(force=True)
        
        black_hex = QColor(Qt.black).name().upper()
        if black_hex in self.right_panel.layer_data:
            params = self.right_panel.layer_data[black_hex]
            params.name = "BMP"
            params.mode = "激光扫描"
            # Refresh table
            self.right_panel.update_layer_list(force=True)

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
        self._import_image_impl()
        # 修复导入后无法框选的问题：强制重置为选择工具
        try:
            from ui.left_toolbar import LeftToolbar
            self._set_tool_from_menu(LeftToolbar.TOOL_SELECT)
        except Exception as e:
            self.logger.error(f"重置工具失败: {e}")

    def _import_image_impl(self):
        """
        文件导入总入口函数：负责文件选择和显示加载进度条
        """
        # 复用原 SUPPORTED_FILTER 常量
        SUPPORTED_FILTER_LOCAL = SUPPORTED_FILTER

        # --------------------------- 文件选择逻辑 ---------------------------
        from ui.import_preview_dialog import PreviewFileDialog
        dlg = PreviewFileDialog(self, "导入", filter=SUPPORTED_FILTER_LOCAL)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            files = dlg.selectedFiles()
            path = files[0] if files else None
        else:
            path = None

        if not path:
            return

        # ================== 导入加载框 (新增) ==================
        # 即使操作很快，显示加载框也能提供良好的用户反馈
        progress_dialog = QtWidgets.QProgressDialog("正导入文件,请稍侯..", None, 0, 100, self)
        progress_dialog.setWindowTitle("导入")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0) # 立即显示
        progress_dialog.setCancelButton(None) # 移除取消按钮
        
        # 样式美化
        progress_dialog.setStyleSheet("""
            QProgressBar {
                border: 1px solid #76797C;
                border-radius: 4px;
                text-align: center;
                color: black;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #05B8CC;
                width: 1px; 
            }
        """)
        progress_dialog.setValue(10) # 起始进度
        progress_dialog.show()
        QtWidgets.QApplication.processEvents() # 强制刷新
        # =======================================================

        try:
            # 调用核心处理逻辑
            self._import_process_file_internal(path)
        finally:
            # 确保无论成功还是失败，进度条都会填满并关闭
            progress_dialog.setValue(100)
            QtWidgets.QApplication.processEvents() # 稍微展示一下100%
            import time
            # 可选：稍微停顿一下（例如0.2秒）让用户看到100%，不然闪太快
            # time.sleep(0.1) 
            progress_dialog.close()

    def _import_process_file_internal(self, path):
        """
        核心文件导入逻辑（由 _import_image_impl 调用）
        """

        def _calc_import_offset(paths_list):
            # 计算包围盒并返回偏移量
            min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
            has_pts = False
            for path_pts in paths_list:
                for px, py in path_pts:
                    if px < min_x:
                        min_x = px
                    if py < min_y:
                        min_y = py
                    if px > max_x:
                        max_x = px
                    if py > max_y:
                        max_y = py
                    has_pts = True

            if not has_pts:
                return 0.0, 0.0

            canvas_w = getattr(self.whiteboard.canvas, '_work_w', 400.0)
            canvas_h = getattr(self.whiteboard.canvas, '_work_h', 300.0)

            imp_settings = getattr(self.whiteboard.canvas, 'import_settings', {})
            dock_pos = imp_settings.get('dock_pos', '中心')
            if not dock_pos:
                dock_pos = '中心'

            cur_w = max_x - min_x
            cur_h = max_y - min_y
            cur_cx = min_x + cur_w / 2
            cur_cy = min_y + cur_h / 2

            dx, dy = 0.0, 0.0
            should_move = True

            if dock_pos == '无' or dock_pos == '按坐标':
                if min_x > canvas_w * 2 or max_x < -canvas_w or min_y > canvas_h * 2 or max_y < -canvas_h:
                    self.show_status_message("提示: 图形坐标超出范围，已自动移至画布中心", 5000)
                    dock_pos = '中心'
                else:
                    should_move = False

            if should_move:
                if dock_pos == '中心':
                    target_x = canvas_w / 2
                    target_y = canvas_h / 2
                    dx = target_x - cur_cx
                    dy = target_y - cur_cy
                elif dock_pos == '左上':
                    dx = 0 - min_x
                    dy = 0 - min_y
                elif dock_pos == '右上':
                    dx = canvas_w - max_x
                    dy = 0 - min_y
                elif dock_pos == '右下':
                    dx = canvas_w - max_x
                    dy = canvas_h - max_y
                elif dock_pos == '左下':
                    dx = 0 - min_x
                    dy = canvas_h - max_y

            return dx, dy

        def _dedupe_layer_name(name, existing_names):
            if name not in existing_names:
                existing_names.add(name)
                return name

            base = name
            idx = 2
            while True:
                candidate = f"{base}_{idx}"
                if candidate not in existing_names:
                    existing_names.add(candidate)
                    return candidate
                idx += 1


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
                        # 自动转换为灰度图 (L模式)
                        im = im.convert('L')

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

                        # ----------------------- 自动归一化逻辑（缩放并居中） -----------------------
                        # 计算原始包围盒
                        min_x, min_y = float('inf'), float('inf')
                        max_x, max_y = float('-inf'), float('-inf')
                        has_points = False
                        for pts in paths:
                            for x, y in pts:
                                min_x = min(min_x, x)
                                min_y = min(min_y, y)
                                max_x = max(max_x, x)
                                max_y = max(max_y, y)
                                has_points = True
                        
                        if has_points:
                            path_w = max_x - min_x
                            path_h = max_y - min_y
                            
                            # 获取画布尺寸（默认为600x400，如果有配置则读取配置）
                            canvas_w = getattr(self.whiteboard.canvas, '_work_w', 600.0)
                            canvas_h = getattr(self.whiteboard.canvas, '_work_h', 400.0)
                            
                            # 1. 单位转换（Points -> mm）
                            # AI/PDF 默认单位为 Point (1/72 inch = 0.352778 mm)
                            # RDWorks 通常使用 mm。如果直接用 Points 数值当 mm 用，会放大约 2.83 倍。
                            # 通常我们希望保持物理尺寸一致，或者用户就是想要“填充画布”。
                            # 鉴于用户之前的请求是“处在画布内”，我们优先保证可见性。
                            # 这里引入一个基础转换系数，如果不合适后续可以调整。
                            unit_scale = 0.352778 
                            
                            # 2. 计算缩放比例 (留出5%边距)
                            # 先应用单位转换后的尺寸
                            phys_w = path_w * unit_scale
                            phys_h = path_h * unit_scale
                            
                            scale_x = (canvas_w * 0.9) / phys_w if phys_w > 0 else 1.0
                            scale_y = (canvas_h * 0.9) / phys_h if phys_h > 0 else 1.0
                            
                            # 决定最终缩放:
                            # 如果图形比画布大，必须缩小 (scale < 1.0)
                            # 如果图形比画布小，通常保持 1.0 (即仅应用 unit_scale)，除非用户强制要求“充满”。
                            # 这里采用：如果太大则缩小，如果太小则保持原物理尺寸（scale=1.0 relative to unit_scale）
                            fit_scale = min(scale_x, scale_y)
                            final_scale = unit_scale * (fit_scale if fit_scale < 1.0 else 1.0)
                            
                            # 3. 计算居中平移
                            center_x = min_x + path_w / 2
                            center_y = min_y + path_h / 2
                            
                            target_x = canvas_w / 2
                            target_y = canvas_h / 2
                            
                            # 修正所有点的坐标
                            new_paths = []
                            for pts in paths:
                                new_pts = []
                                for x, y in pts:
                                    # 先归一化到原点相对坐标，再缩放，再平移到目标
                                    nx = (x - center_x) * final_scale + target_x
                                    ny = (y - center_y) * final_scale + target_y
                                    new_pts.append((nx, ny))
                                new_paths.append(new_pts)
                            paths = new_paths
                            
                            self.logger.info(f"路径已自动归一化: FinalScale={final_scale:.4f} (Original WxH={path_w:.1f}x{path_h:.1f} pts -> Fits Canvas {canvas_w}x{canvas_h})")
                        # ----------------------- 自动归一化逻辑结束 -----------------------

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
                # 处理 DWG/DXF 格式
                if lower.endswith(('.dwg', '.dxf')):
                    if lower.endswith('.dwg'):
                        from my_io.importers.import_dwg import import_dwg
                    else:
                        from my_io.importers.import_dxf import import_dxf
                    
                    scale_val = None
                    try:
                        imp = getattr(self.whiteboard.canvas, 'import_settings', {})
                        d_unit = imp.get('dxf_unit')
                        if d_unit == "毫米": 
                            scale_val = 1.0
                        elif d_unit == "厘米": 
                            scale_val = 10.0
                        elif d_unit == "英寸": 
                            scale_val = 25.4
                        elif d_unit == "自定义": 
                            scale_val = float(imp.get('dxf_custom_unit', 1.0))
                    except Exception:
                        pass

                    if lower.endswith('.dwg'):
                        paths = import_dwg(path, unit_scale=scale_val)
                    else:
                        # 使用分图层导入
                        from my_io.importers.import_dxf import import_dxf_by_layer
                        paths = import_dxf_by_layer(path, unit_scale=scale_val)
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

            # --------------------------- DWG/DXF 图层导入处理 ---------------------------
            if isinstance(paths, dict):
                layer_groups = paths
                if not layer_groups:
                    self.show_status_message(f'未从 {os.path.basename(path)} 中找到可导入的图形', 5000)
                    return

                all_paths = []
                for info in layer_groups.values():
                    all_paths.extend(info.get("paths", []))

                try:
                    dx, dy = _calc_import_offset(all_paths)
                except Exception as e:
                    self.logger.error(f"自动停靠处理出错: {e}")
                    dx, dy = 0.0, 0.0

                existing_names = set()
                for params in self.right_panel.layer_data.values():
                    if getattr(params, "name", ""):
                        existing_names.add(params.name)

                for layer_name, info in layer_groups.items():
                    layer_color = self.get_next_layer_color()

                    adjusted_paths = []
                    for pts in info.get("paths", []):
                        if dx != 0.0 or dy != 0.0:
                            adjusted_paths.append([(px + dx, py + dy) for px, py in pts])
                        else:
                            adjusted_paths.append(pts)

                    for pts in adjusted_paths:
                        self.whiteboard.canvas.add_polyline(pts, layer_color)

                    self.right_panel.update_layer_list(force=True)
                    hex_color = layer_color.name().upper()
                    if hex_color in self.right_panel.layer_data:
                        base_name = layer_name or os.path.basename(path)
                        deduped = _dedupe_layer_name(base_name, existing_names)
                        params = self.right_panel.layer_data[hex_color]
                        if not params.name:
                            params.name = deduped
                        self.right_panel.update_layer_list(force=True)

                self.whiteboard.canvas.fit_all()
                self.show_status_message(f'已导入: {os.path.basename(path)} / 图层数={len(layer_groups)}', 5000)
                return

            # --------------------------- 其他格式导入结果处理 - 保留原逻辑 ---------------------------
            if paths:
                # ----------------- 自动居中/停靠处理 -----------------
                try:
                    dx, dy = _calc_import_offset(paths)
                    if dx != 0.0 or dy != 0.0:
                        new_paths = []
                        for path_pts in paths:
                            new_paths.append([(px + dx, py + dy) for px, py in path_pts])
                        paths = new_paths
                except Exception as e:
                    self.logger.error(f"自动停靠处理出错: {e}")

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
            filename, sel_filter = QFileDialog.getSaveFileName(
                self,
                '导出为NC/AI/PLT文件',
                '',
                'NC文件 (*.nc);;G代码文件 (*.gcode);;AI文件 (*.ai);;PLT文件 (*.plt);;所有文件 (*)'
            )

            if not filename:
                return  # 用户取消

            lower_name = filename.lower()
            # 简单后缀补全
            if '.' not in os.path.basename(filename):
                if 'AI' in sel_filter:
                    filename += '.ai'
                    lower_name += '.ai'
                elif 'PLT' in sel_filter:
                    filename += '.plt'
                    lower_name += '.plt'
                elif 'G代码' in sel_filter:
                    filename += '.gcode'
                    lower_name += '.gcode' 

            # 获取允许导出的颜色层
            allowed_colors = None
            if hasattr(self, 'right_panel'):
                allowed_colors = self.right_panel.get_output_enabled_colors()

            # --- AI/PLT 导出分支 ---
            if lower_name.endswith('.ai'):
                from my_io.exporters.export_ai import export_to_ai
                if export_to_ai(self.whiteboard.canvas, filename, allowed_colors):
                     self.show_status_message(f'成功导出AI文件: {os.path.basename(filename)}', 5000)
                     QMessageBox.information(self, "导出成功", f"成功导出AI文件: {filename}")
                else:
                     self.show_status_message(f'AI文件导出失败', 5000)
                     QMessageBox.warning(self, "导出失败", "AI文件导出失败，详情请查看日志")
                return

            elif lower_name.endswith('.plt'):
                from my_io.exporters.export_plt import export_to_plt
                if export_to_plt(self.whiteboard.canvas, filename, allowed_colors):
                     self.show_status_message(f'成功导出PLT文件: {os.path.basename(filename)}', 5000)
                     QMessageBox.information(self, "导出成功", f"成功导出PLT文件: {filename}")
                else:
                     self.show_status_message(f'PLT文件导出失败', 5000)
                     QMessageBox.warning(self, "导出失败", "PLT文件导出失败，详情请查看日志")
                return
            # -----------------------

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
            layer_settings = None
            export_settings = getattr(self.whiteboard.canvas, 'export_settings', {})
            optimize_settings = getattr(self.whiteboard.canvas, 'optimize_settings', {})
            if hasattr(self, 'right_panel'):
                allowed_colors = self.right_panel.get_output_enabled_colors()
                layer_settings = self.right_panel.layer_data

            scan_direction = export_settings.get('scan_direction')
            if scan_direction:
                config['scan_direction'] = scan_direction
            gap_comp_optimize = (optimize_settings or {}).get(
                'gap_comp_optimize',
                (export_settings or {}).get('gap_comp_optimize', None)
            )
            if gap_comp_optimize is not None:
                config['gap_comp_optimize'] = gap_comp_optimize
            small_circle_enable = (export_settings or {}).get('small_circle_enable', None)
            if small_circle_enable is not None:
                config['small_circle_enable'] = small_circle_enable

            success = export_to_nc(self.whiteboard.canvas, filename, config, allowed_colors, layer_settings)

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

    def export_to_dxf_file(self):
        """导出为DXF文件"""
        try:
             # 选择保存文件路径
            filename, _ = QFileDialog.getSaveFileName(
                self,
                '导出为 DXF 文件',
                '',
                'DXF 文件 (*.dxf)'
            )

            if not filename:
                return

            if not filename.lower().endswith('.dxf'):
                filename += '.dxf'

            self.show_status_message("正在导出 DXF...")
            
            # 允许的颜色
            allowed_colors = None
            if hasattr(self, 'right_panel'):
                allowed_colors = self.right_panel.get_output_enabled_colors()

            count = export_to_dxf(self.whiteboard.canvas, filename, allowed_colors)
            
            if count is not None and count > 0:
                QMessageBox.information(self, "导出成功", f"成功导出 {count} 个对象到 DXF 文件。")
                self.show_status_message(f"已导出 DXF: {filename}")
            elif count == 0:
                QMessageBox.warning(self, "导出警告", "没有导出任何对象，请检查画布内容或图层设置。")
                self.show_status_message("导出 DXF 结束 (无内容)")

        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出 DXF 失败: {str(e)}")
            self.show_status_message("导出 DXF 失败")

    def _analyze_canvas_content(self):
        """详细分析画布内容（增强版）"""
        from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsPathItem

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

                # 矢量路径 (EditablePathItem 或 标准 QGraphicsPathItem)
                if hasattr(item, '_points') and hasattr(item, 'points'):
                    try:
                        points = item.points()
                        if points and len(points) >= 2:
                            info['has_paths'] = True
                            info['path_count'] += 1
                            info['total_points'] += len(points)
                    except Exception as e:
                        self.logger.warning(f"获取路径点时出错: {e}")
                elif isinstance(item, QGraphicsPathItem) and not isinstance(item, QGraphicsPixmapItem):
                    # 处理 TextGraphicsItem 和其他普通 PathItem
                    path = item.path()
                    if not path.isEmpty():
                        info['has_paths'] = True
                        info['path_count'] += 1
                        # 估算点数 (简单按元素数量)
                        info['total_points'] += path.elementCount()

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
                    # Add import for VirtualArrayItem
                    try:
                        from ui.virtual_array_item import VirtualArrayItem
                    except ImportError:
                        VirtualArrayItem = type(None) # Dummy if not found
                    
                    from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem

                    # 辅助函数：获取项的颜色Hex
                    def get_item_color_hex(item):
                        layer_color_role = Qt.UserRole + 100
                        color_hex = None

                        if hasattr(item, 'data'):
                            color_data = item.data(layer_color_role)
                            if isinstance(color_data, QColor):
                                color_hex = color_data.name().upper()
                            elif isinstance(color_data, str):
                                color_hex = color_data.upper()

                        if not color_hex and hasattr(item, '_color'):
                            c = getattr(item, '_color')
                            if isinstance(c, QColor):
                                color_hex = c.name().upper()
                            elif isinstance(c, str):
                                color_hex = c.upper()

                        if not color_hex and hasattr(item, 'pen'):
                            try:
                                pen = item.pen()
                                if pen and pen.color().isValid():
                                    color_hex = pen.color().name().upper()
                            except Exception:
                                pass

                        if not color_hex and hasattr(item, 'defaultTextColor'):
                            try:
                                color = item.defaultTextColor()
                                if color and color.isValid():
                                    color_hex = color.name().upper()
                            except Exception:
                                pass

                        return color_hex

                    def get_layer_state(item):
                        color_hex = get_item_color_hex(item)
                        if color_hex and color_hex in layer_data:
                            params = layer_data[color_hex]
                            return color_hex, params, bool(params.is_output), int(params.priority)
                        return color_hex, None, True, 9999

                    # 收集有效项
                    for item in items:
                        color_hex, layer_params, is_output_enabled, priority = get_layer_state(item)
                        try:
                            visible = bool(item.isVisible())
                        except Exception:
                            visible = True
                        # 仅当该项关联图层且该层允许输出时，隐藏项也参与路径
                        if (not visible) and layer_params is None:
                            continue
                        if not is_output_enabled:
                            continue

                        # 排除非顶层项（如子项、手柄图标等）
                        if item.parentItem() is not None: continue
                        
                        # --- 处理虚阵列 (VirtualArrayItem) ---
                        if isinstance(item, VirtualArrayItem):
                            # 这里我们需要提取其内部的“实线”子项用于路径显示
                            # 而“虚线”部分通常不作为切割路径输出
                            if hasattr(item, 'real_items'):
                                for sub_item in item.real_items:
                                    sub_color_hex, sub_layer_params, sub_output_enabled, sub_priority = get_layer_state(sub_item)
                                    try:
                                        sub_visible = bool(sub_item.isVisible())
                                    except Exception:
                                        sub_visible = True
                                    if (not sub_visible) and sub_layer_params is None:
                                        continue
                                    if not sub_output_enabled:
                                        continue
                                    
                                    # 递归检查类型 (只支持路径/图片/文字)
                                    if not isinstance(sub_item, (EditablePathItem, EditableEllipseItem, QGraphicsPixmapItem, QGraphicsTextItem, TextGraphicsItem)):
                                        continue

                                    valid_items.append((sub_item, sub_priority))
                            continue
                        # ------------------------------------

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
                        # 更新：包含 TextGraphicsItem (自定义文字项)
                        if not isinstance(item, (EditablePathItem, EditableEllipseItem, QGraphicsPixmapItem, QGraphicsTextItem, TextGraphicsItem)):
                            continue

                        valid_items.append((item, priority))
                    
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

    def on_fill_scan_toggled(self, checked):
        """切换“填充扫描图形”实时预览"""
        if checked:
            added, _removed = self._sync_fill_scan_pairs()
            if added > 0:
                self.show_status_message(f"填充扫描图形：已填充 {added} 个闭合路径", 2500)
            else:
                self.show_status_message("填充扫描图形已开启", 2000)
        else:
            restored = self._restore_all_fill_scan_pairs()
            self.show_status_message(f"填充扫描图形已关闭，已恢复 {restored} 个路径", 2500)

        if self.show_path_action.isChecked():
            self.toggle_show_path()

    def _is_item_alive(self, item):
        try:
            item.scene()
            return True
        except Exception:
            return False

    def _source_id(self, item):
        return int(id(item))

    def _is_fill_scan_generated_bitmap(self, item):
        try:
            return bool(item.data(FILL_SCAN_BITMAP_ROLE))
        except Exception:
            return False

    def _get_item_layer_color(self, item):
        """提取图元所属图层颜色"""
        try:
            if hasattr(item, 'pen'):
                c = item.pen().color()
                if c and c.isValid():
                    return c
        except Exception:
            pass

        try:
            if hasattr(item, 'defaultTextColor'):
                c = item.defaultTextColor()
                if c and c.isValid():
                    return c
        except Exception:
            pass

        try:
            color_data = item.data(Qt.UserRole + 100)
            if isinstance(color_data, QColor):
                return color_data
            if isinstance(color_data, str):
                c = QColor(color_data)
                if c.isValid():
                    return c
        except Exception:
            pass

        return None

    def _is_scene_path_closed(self, scene_path):
        """判断场景路径是否为闭合路径（所有子路径首尾闭合）"""
        try:
            polys = scene_path.toSubpathPolygons()
        except Exception:
            return False

        if not polys:
            return False

        for poly in polys:
            if poly.count() < 3:
                return False
            first = poly.at(0)
            last = poly.at(poly.count() - 1)
            if abs(first.x() - last.x()) > 1e-6 or abs(first.y() - last.y()) > 1e-6:
                return False
        return True

    def _build_closed_scene_path(self, item):
        """仅为闭合矢量图元构建场景路径"""
        if isinstance(item, EditablePathItem):
            if not item.is_closed():
                return None
            local_path = item.path()
            if local_path.isEmpty():
                return None
            return item.mapToScene(local_path)

        if isinstance(item, EditableEllipseItem):
            local_path = QtGui.QPainterPath()
            local_path.addEllipse(item.rect())
            return item.mapToScene(local_path)

        if isinstance(item, QtWidgets.QGraphicsPathItem):
            local_path = item.path()
            if local_path.isEmpty():
                return None
            scene_path = item.mapToScene(local_path)
            if not self._is_scene_path_closed(scene_path):
                return None
            return scene_path

        return None

    def _create_filled_bitmap_item(self, scene_path, fill_color, source_id, z_value=0.0):
        """将场景路径光栅化为同色位图图元"""
        rect = scene_path.boundingRect()
        if not rect.isValid() or rect.width() <= 0 or rect.height() <= 0:
            return None

        dpi = 300.0
        scale_factor = dpi / 25.4
        width_px = int(math.ceil(rect.width() * scale_factor)) + 2
        height_px = int(math.ceil(rect.height() * scale_factor)) + 2
        if width_px <= 0 or height_px <= 0:
            return None

        image = QtGui.QImage(width_px, height_px, QtGui.QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.scale(scale_factor, scale_factor)
        painter.translate(-rect.x(), -rect.y())
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill_color)
        painter.drawPath(scene_path)
        painter.end()

        pixmap = QtGui.QPixmap.fromImage(image)
        if pixmap.isNull():
            return None

        pix_item = QGraphicsPixmapItem(pixmap)
        pix_item.setPos(rect.x(), rect.y())
        pix_item.setScale(1.0 / scale_factor)
        pix_item.setTransformationMode(Qt.SmoothTransformation)
        pix_item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
        pix_item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
        pix_item.setAcceptedMouseButtons(Qt.NoButton)
        pix_item.setZValue(z_value)
        pix_item.setData(Qt.UserRole + 100, QColor(fill_color))
        pix_item.setData(FILL_SCAN_BITMAP_ROLE, True)
        pix_item.setData(FILL_SCAN_SOURCE_ID_ROLE, int(source_id))
        return pix_item

    def _restore_one_fill_scan_pair(self, source_id):
        pair = self._fill_scan_pairs.pop(source_id, None)
        if not pair:
            return 0

        src = pair.get('source')
        bmp = pair.get('bitmap')

        try:
            if self._is_item_alive(bmp):
                bmp_scene = bmp.scene()
                if bmp_scene is not None:
                    bmp_scene.removeItem(bmp)
        except Exception:
            pass

        try:
            if self._is_item_alive(src):
                src.setData(FILL_SCAN_HIDDEN_SOURCE_ROLE, False)

                visible = bool(pair.get('source_visible_before', True))
                color = self._get_item_layer_color(src)
                if color and color.isValid() and hasattr(self, 'right_panel'):
                    color_hex = color.name().upper()
                    params = getattr(self.right_panel, 'layer_data', {}).get(color_hex)
                    if params is not None:
                        visible = bool(getattr(params, 'is_visible', True))
                src.setVisible(visible)

                if bool(pair.get('source_selected_before', False)) and visible:
                    try:
                        if src.flags() & QtWidgets.QGraphicsItem.ItemIsSelectable:
                            src.setSelected(True)
                    except Exception:
                        pass
        except Exception:
            pass

        return 1

    def _restore_all_fill_scan_pairs(self):
        if self._fill_scan_busy:
            return 0
        restored = 0
        self._fill_scan_busy = True
        try:
            for source_id in list(self._fill_scan_pairs.keys()):
                restored += self._restore_one_fill_scan_pair(source_id)
        finally:
            self._fill_scan_busy = False

        try:
            self.right_panel.update_layer_list(force=True)
        except Exception:
            pass

        return restored

    def _sync_fill_scan_pairs(self):
        """实时同步：扫描图层闭合路径 <-> 填充位图"""
        if self._fill_scan_busy:
            return (0, 0)
        if not hasattr(self, 'fill_scan_action') or not self.fill_scan_action.isChecked():
            return (0, self._restore_all_fill_scan_pairs())
        if not hasattr(self, 'right_panel') or not hasattr(self.right_panel, 'layer_data'):
            return (0, 0)

        scene = self.whiteboard.canvas.scene
        layer_data = self.right_panel.layer_data or {}

        added = 0
        removed = 0

        self._fill_scan_busy = True
        try:
            # 清理失效映射
            for source_id, pair in list(self._fill_scan_pairs.items()):
                src = pair.get('source')
                bmp = pair.get('bitmap')
                src_scene = src.scene() if self._is_item_alive(src) else None
                bmp_scene = bmp.scene() if self._is_item_alive(bmp) else None

                if src_scene is not scene:
                    if bmp_scene is not None:
                        try:
                            bmp_scene.removeItem(bmp)
                        except Exception:
                            pass
                    self._fill_scan_pairs.pop(source_id, None)
                    continue

                if bmp_scene is not scene:
                    self._fill_scan_pairs.pop(source_id, None)
                    try:
                        src.setData(FILL_SCAN_HIDDEN_SOURCE_ROLE, False)
                        src.setVisible(True)
                    except Exception:
                        pass

            eligible = {}
            for item in scene.items(order=Qt.AscendingOrder):
                if item is getattr(self.whiteboard.canvas, '_drawing_tmp', None):
                    continue
                if item is getattr(self.whiteboard.canvas, '_cursor_preview', None):
                    continue
                if item.zValue() >= 9999:
                    continue
                if item.parentItem() is not None:
                    continue
                if self._is_fill_scan_generated_bitmap(item):
                    continue
                if isinstance(item, QGraphicsPixmapItem):
                    continue
                if not isinstance(item, (EditablePathItem, EditableEllipseItem, QtWidgets.QGraphicsPathItem)):
                    continue

                color = self._get_item_layer_color(item)
                if color is None or not color.isValid():
                    continue

                color_hex = color.name().upper()
                params = layer_data.get(color_hex)
                if params is None:
                    continue
                if getattr(params, 'mode', '') != "激光扫描":
                    continue

                scene_path = self._build_closed_scene_path(item)
                if scene_path is None or scene_path.isEmpty():
                    continue

                eligible[self._source_id(item)] = (item, scene_path, color, params)

            # 移除不再满足条件的映射
            for source_id in list(self._fill_scan_pairs.keys()):
                if source_id not in eligible:
                    removed += self._restore_one_fill_scan_pair(source_id)

            # 新增/修复满足条件的映射
            for source_id, (src_item, scene_path, color, params) in eligible.items():
                color_hex = color.name().upper()
                pair = self._fill_scan_pairs.get(source_id)

                if pair:
                    bmp_item = pair.get('bitmap')
                    rebuild = False

                    if not self._is_item_alive(bmp_item) or bmp_item.scene() is not scene:
                        rebuild = True
                    if pair.get('color_hex') != color_hex:
                        rebuild = True

                    # 勾选状态下，原路径必须隐藏
                    try:
                        src_item.setData(FILL_SCAN_HIDDEN_SOURCE_ROLE, True)
                        src_item.setVisible(False)
                        src_item.setSelected(False)
                    except Exception:
                        pass

                    if rebuild:
                        try:
                            if self._is_item_alive(bmp_item) and bmp_item.scene() is not None:
                                bmp_item.scene().removeItem(bmp_item)
                        except Exception:
                            pass

                        new_bmp = self._create_filled_bitmap_item(
                            scene_path=scene_path,
                            fill_color=color,
                            source_id=source_id,
                            z_value=src_item.zValue(),
                        )
                        if new_bmp is None:
                            continue
                        scene.addItem(new_bmp)
                        new_bmp.setVisible(bool(getattr(params, 'is_visible', True)))
                        pair['bitmap'] = new_bmp
                        pair['color_hex'] = color_hex
                    else:
                        try:
                            bmp_item.setZValue(src_item.zValue())
                            bmp_item.setVisible(bool(getattr(params, 'is_visible', True)))
                            bmp_item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
                            bmp_item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
                            bmp_item.setAcceptedMouseButtons(Qt.NoButton)
                            bmp_item.setData(FILL_SCAN_BITMAP_ROLE, True)
                            bmp_item.setData(FILL_SCAN_SOURCE_ID_ROLE, int(source_id))
                        except Exception:
                            pass
                    continue

                source_selected_before = bool(src_item.isSelected())
                source_visible_before = bool(src_item.isVisible())

                bmp_item = self._create_filled_bitmap_item(
                    scene_path=scene_path,
                    fill_color=color,
                    source_id=source_id,
                    z_value=src_item.zValue(),
                )
                if bmp_item is None:
                    continue

                scene.addItem(bmp_item)
                bmp_item.setVisible(bool(getattr(params, 'is_visible', True)))

                src_item.setData(FILL_SCAN_HIDDEN_SOURCE_ROLE, True)
                src_item.setSelected(False)
                src_item.setVisible(False)

                self._fill_scan_pairs[source_id] = {
                    'source': src_item,
                    'bitmap': bmp_item,
                    'color_hex': color_hex,
                    'source_selected_before': source_selected_before,
                    'source_visible_before': source_visible_before,
                }
                added += 1
        finally:
            self._fill_scan_busy = False

        try:
            self.right_panel.update_layer_list(force=True)
        except Exception:
            pass

        return (added, removed)

    def on_scene_changed(self, changes=None):
        """场景变化处理"""
        if self._fill_scan_busy:
            return

        if hasattr(self, 'fill_scan_action') and self.fill_scan_action.isChecked():
            self._sync_fill_scan_pairs()
        elif self._fill_scan_pairs:
            self._restore_all_fill_scan_pairs()

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
            
            # 如果有选中对象，则只预览选中对象；否则预览所有对象
            if selected_items_set:
                target_items = [item for item in all_items if item in selected_items_set]
            else:
                target_items = list(all_items)
            
            # 过滤掉非图形项（如辅助线、手柄等），并遵循图层输出设置
            valid_items = []
            from ui.graphics_items import EditablePathItem, EditableEllipseItem
            from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem, QGraphicsItemGroup
            
            # Try import VirtualArrayItem
            try:
                from ui.virtual_array_item import VirtualArrayItem
            except ImportError:
                VirtualArrayItem = type(None)
            
            # 获取图层数据
            layer_data = self.right_panel.layer_data if hasattr(self, 'right_panel') else {}

            def get_item_color_hex(item):
                layer_color_role = Qt.UserRole + 100
                color_hex = None

                if hasattr(item, 'data'):
                    color_data = item.data(layer_color_role)
                    if color_data:
                        if isinstance(color_data, QColor):
                            color_hex = color_data.name().upper()
                        elif isinstance(color_data, str):
                            color_hex = color_data.upper()

                if not color_hex and hasattr(item, '_color'):
                    c = getattr(item, '_color')
                    if isinstance(c, QColor):
                        color_hex = c.name().upper()
                    elif isinstance(c, str):
                        color_hex = c.upper()

                if not color_hex and hasattr(item, 'pen'):
                    try:
                        pen = item.pen()
                        if pen and pen.color().isValid():
                            color_hex = pen.color().name().upper()
                    except Exception:
                        pass

                if not color_hex and hasattr(item, 'brush'):
                    try:
                        brush = item.brush()
                        if brush and brush.color().isValid():
                            color_hex = brush.color().name().upper()
                    except Exception:
                        pass

                if not color_hex and hasattr(item, 'defaultTextColor'):
                    try:
                        color = item.defaultTextColor()
                        if color and color.isValid():
                            color_hex = color.name().upper()
                    except Exception:
                        pass

                return color_hex

            def is_output_enabled(item):
                if not layer_data:
                    return True
                color_hex = get_item_color_hex(item)
                if color_hex and color_hex in layer_data:
                    return layer_data[color_hex].is_output
                return True

            def can_include_for_process(item):
                color_hex = get_item_color_hex(item)
                layer = layer_data.get(color_hex) if (color_hex and color_hex in layer_data) else None
                if layer is not None and not layer.is_output:
                    return False
                try:
                    visible = bool(item.isVisible())
                except Exception:
                    visible = True
                if visible:
                    return True
                # 隐藏项仅在关联图层且图层输出开启时参与预览路径
                return layer is not None and bool(layer.is_output)

            def collect_items(items):
                results = []
                for item in items:
                    if not can_include_for_process(item): continue
                    if item.zValue() >= 9999: continue # Preview items
                    if item is getattr(self.whiteboard.canvas, '_work_item', None): continue
                    if item is getattr(self.whiteboard.canvas, '_cursor_preview', None): continue
                    
                    # Support VirtualArrayItem
                    if isinstance(item, VirtualArrayItem):
                        if hasattr(item, 'real_items'):
                            results.extend(collect_items(item.real_items))
                        continue

                    if isinstance(item, (EditablePathItem, EditableEllipseItem, QGraphicsPixmapItem, QGraphicsTextItem, TextGraphicsItem)):
                        if is_output_enabled(item):
                            results.append(item)
                    elif isinstance(item, QGraphicsItemGroup) or (item.childItems() and not isinstance(item, (EditablePathItem, EditableEllipseItem, TextGraphicsItem))):
                         # Recursively collect children for Groups or unknown containers
                         # Exclude known types from recursion to avoid picking up handles/helpers
                         results.extend(collect_items(item.childItems()))
                return results

            valid_items = collect_items(target_items)

            if layer_data:
                def get_priority(item):
                    color_hex = get_item_color_hex(item)
                    if color_hex and color_hex in layer_data:
                        return layer_data[color_hex].priority
                    return 9999

                valid_items = sorted(
                    enumerate(valid_items),
                    key=lambda x: (get_priority(x[1]), x[0])
                )
                valid_items = [item for _, item in valid_items]
            
            # 获取工作区尺寸
            work_w = self.whiteboard.canvas._work_w
            work_h = self.whiteboard.canvas._work_h
            
            # 获取图层数据
            layer_data = self.right_panel.layer_data
            
            # 获取激光头位置
            laser_pos = self.whiteboard.canvas.get_laser_start_point()
            
            # 延迟弹出，避免事件冲突
            def open_dlg():
                export_settings = getattr(self.whiteboard.canvas, 'export_settings', {})
                scan_direction = export_settings.get('scan_direction')
                dlg = PreviewDialog(valid_items, (work_w, work_h), layer_data, self, laser_pos=laser_pos,
                                    scan_direction=scan_direction)
                # dlg.showFullScreen() # 移除全屏
                dlg.exec_()
                
            QTimer.singleShot(0, open_dlg)
            
        except Exception as e:
            print(f"Error showing preview: {e}")
            self.show_status_message(f"预览出错: {e}")

    def show_auto_layout_dialog(self):
        """显示自动排版对话框"""
        items = list(self.whiteboard.canvas.scene.selectedItems())
        # Filter valid items
        from ui.graphics_items import EditablePathItem
        from PyQt5.QtWidgets import QGraphicsPathItem
        
        valid_items = [i for i in items if isinstance(i, (EditablePathItem, QGraphicsPathItem))]
        
        if not valid_items:
            QMessageBox.information(self, "提示", "请先选择要排版的对象")
            return
            
        work_w = getattr(self.whiteboard.canvas, '_work_w', 1200)
        work_h = getattr(self.whiteboard.canvas, '_work_h', 800)
        
        dlg = AutoLayoutDialog(valid_items, (work_w, work_h), self)
        dlg.apply_layout_signal.connect(self.apply_auto_layout)
        dlg.exec_()

    def apply_auto_layout(self, mode, params):
        """执行自动排版"""
        items = list(self.whiteboard.canvas.scene.selectedItems())
        from ui.graphics_items import EditablePathItem
        from PyQt5.QtWidgets import QGraphicsPathItem
        valid_items = [i for i in items if isinstance(i, (EditablePathItem, QGraphicsPathItem))]
        
        if not valid_items:
            return
        
        # Calculate bounding box of selection to determine relative positions
        from PyQt5.QtCore import QRectF, QPointF
        from PyQt5.QtGui import QTransform
        
        rect = QRectF()
        first = True
        for item in valid_items:
            br = item.sceneBoundingRect()
            if first:
                rect = br
                first = False
            else:
                rect = rect.united(br)
        
        start_x = rect.left()
        start_y = rect.top()
        item_w = rect.width()
        item_h = rect.height()
        
        rows = params['rows']
        cols = params['cols']
        odd_r_s = params.get('odd_r_s', 0.0)
        even_r_s = params.get('even_r_s', 0.0)
        odd_c_s = params.get('odd_c_s', 0.0)
        even_c_s = params.get('even_c_s', 0.0)
        r_offset = params.get('r_offset', 0.0)
        c_offset = params.get('c_offset', 0.0)
        row_mirror_h = params.get('row_mirror_h', False)
        row_mirror_v = params.get('row_mirror_v', False)
        col_mirror_h = params.get('col_mirror_h', False)
        col_mirror_v = params.get('col_mirror_v', False)

        from edit.commands import MacroCommand, AddItemCommand
        commands = []
        
        current_y = start_y
        
        for r in range(rows):
            is_even_row = ((r + 1) % 2 == 0)
            row_spacing = even_r_s if is_even_row else odd_r_s
            
            current_x = start_x
            if is_even_row:
                current_x += r_offset
            
            # Row Mirror flags
            mr_x_row = False
            mr_y_row = False
            if row_mirror_h and is_even_row: mr_x_row = True
            if row_mirror_v and is_even_row: mr_y_row = True
                
            for c in range(cols):
                is_even_col = ((c + 1) % 2 == 0)
                col_spacing = even_c_s if is_even_col else odd_c_s
                
                y_pos = current_y
                if is_even_col:
                    y_pos += c_offset
                
                # Combine Mirror flags
                mirror_x = mr_x_row
                mirror_y = mr_y_row
                
                if col_mirror_h and is_even_col: mirror_x = not mirror_x
                if col_mirror_v and is_even_col: mirror_y = not mirror_y
                
                # Center of this cell
                cell_cx = current_x + item_w / 2
                cell_cy = y_pos + item_h / 2
                
                # Create clones
                for template in valid_items:
                    new_item = None
                    if isinstance(template, EditablePathItem):
                        try:
                            # Clone internal state manually
                            new_item = EditablePathItem(list(template._points), template._color, template._smooth)
                            if hasattr(template, '_segment_types'):
                                new_item._segment_types = list(template._segment_types)
                            if hasattr(template, '_control_points'):
                                new_item._control_points = dict(template._control_points)
                            new_item.setPen(template.pen())
                            new_item.setBrush(template.brush())
                        except:
                             new_item = None
                    
                    if new_item is None:
                        # Fallback
                        if hasattr(template, 'path'):
                             new_item = QGraphicsPathItem(template.path())
                             new_item.setPen(template.pen())
                             new_item.setBrush(template.brush())

                    if new_item:
                        # Construct Transform
                        center_src = rect.center()
                         
                        t = QTransform()
                        t.translate(cell_cx, cell_cy) 
                        t.scale(-1 if mirror_x else 1, -1 if mirror_y else 1)
                        t.translate(-center_src.x(), -center_src.y()) 
                        
                        final_transform = template.sceneTransform() * t
                        
                        new_item.setPos(0,0)
                        new_item.setTransform(final_transform)
                        
                        if mode == 'virtual':
                            pen = new_item.pen()
                            pen.setStyle(Qt.DashLine)
                            new_item.setPen(pen)
                            new_item.setFlag(QGraphicsPathItem.ItemIsSelectable, False)
                        
                        commands.append(AddItemCommand(self.whiteboard.canvas, new_item))
                
                current_x += item_w + col_spacing
            
            current_y += item_h + row_spacing

        if mode == 'virtual':
            # 虚阵列逻辑：
            # 1. 创建包含所有新生成虚线项和所有原项克隆的 VirtualArrayItem
            # 2. 从场景中移除原项（通过 Undoable command）
            # 3. 将 VirtualArrayItem 添加到场景
            
            # 由于前面的循环已经把虚线项加到 commands 列表准备添加（但还没加），以及一些克隆项。
            # 刚才的循环对于 virtual 模式是生成了虚线项作为 new_item。
            # 对于原始的 "template" items (0,0 位置)，我们没动。
            # 我们需要把原始项和虚线项打包。
            
            # 让我们重写一下逻辑，上面的循环对于 real 模式是好的。
            # 对于 virtual 模式，我们不需要把每个虚线项单独 AddItemCommand。
            pass

        if mode == 'real':
            # 实阵列简单直接添加所有项
            if commands:
                cmd = MacroCommand("自动排版", commands)
                cmd.redo() 
                self.whiteboard.canvas.edit_manager.push_undo(cmd)
                self.whiteboard.canvas.update()
        
        elif mode == 'virtual':
            # 重新构建 virtual 逻辑
            # 1. 克隆选中的原项 (保持相对位置)
            from ui.virtual_array_item import VirtualArrayItem
            from edit.commands import DeleteItemsCommand, AddItemCommand
            
            real_clones = []
            virtual_parts = []
            
            # 获取原项的中心，用于构建组的参考系
            # rect 是所有选中项的包围盒
            group_center = rect.center()
            
            # 克隆原项 -> real_clones
            # 实际上，VirtualArrayItem 需要接收已经是子项坐标系的对象。
            # 我们希望 VirtualArrayItem 放在 group_center 位置？
            # 或者放在 (0,0) 位置？
            # 最好放在 rect.topLeft() 或者 (0,0)。如果放在 (0,0)，所有子项保持 scenePos 转换后的 coordinates.
            
            # 方案：VirtualArrayItem 放在 (0,0)
            
            # Step A: Clone Real Items
            for item in valid_items:
                clone = self._clone_item(item)
                if clone:
                    # clone 现在的 pos/transform 和原项一样 (Scene 坐标)
                    # 如果作为子项加到 VirtualArrayItem(pos=0,0)，位置正确。
                    real_clones.append(clone)
            
            # Step B: Generate Virtual Items
            # Logic similar to loop but generate items into list, not commands
            current_y = start_y
            
            for r in range(rows):
                is_even_row = ((r + 1) % 2 == 0)
                row_spacing = even_r_s if is_even_row else odd_r_s
                
                current_x = start_x
                if is_even_row:
                    current_x += r_offset
                
                # Row Mirror flags
                mr_x_row = False
                mr_y_row = False
                if row_mirror_h and is_even_row: mr_x_row = True
                if row_mirror_v and is_even_row: mr_y_row = True
                    
                for c in range(cols):
                    is_even_col = ((c + 1) % 2 == 0)
                    col_spacing = even_c_s if is_even_col else odd_c_s
                    
                    y_pos = current_y
                    if is_even_col:
                        y_pos += c_offset
                    
                    # Combine Mirror flags
                    mirror_x = mr_x_row
                    mirror_y = mr_y_row
                    
                    if col_mirror_h and is_even_col: mirror_x = not mirror_x
                    if col_mirror_v and is_even_col: mirror_y = not mirror_y
                    
                    # Skip the first block if it overlaps with original?
                    # Auto layout typically means filling the board.
                    # Screenshot 1 shows original items are part of the array.
                    # If we generate everything, we duplicate original items position.
                    # Should we skip if r=0 and c=0? 
                    # Actually, the loop generates positions. Is the original items included in the loop?
                    # Yes, (start_x, start_y) corresponds to 0,0.
                    # If we generate a virtual item at 0,0, it overlaps real items.
                    # We should SKIP creating virtual items that overlap real items.
                    # Assuming (0,0) is the original set.
                    # But if offsets are used, maybe not exactly.
                    # Let's assume we skip r=0, c=0 for simplicity if no complex offsets.
                    
                    skip = (r == 0 and c == 0)
                    if skip:
                        current_x += item_w + col_spacing
                        continue

                    cell_cx = current_x + item_w / 2
                    cell_cy = y_pos + item_h / 2
                    
                    for template in valid_items:
                        v_clone = self._clone_item(template)
                        if v_clone:
                            # Apply Transform
                            center_src = rect.center()
                            t = QTransform()
                            t.translate(cell_cx, cell_cy)
                            t.scale(-1 if mirror_x else 1, -1 if mirror_y else 1)
                            t.translate(-center_src.x(), -center_src.y())
                            
                            final_transform = template.sceneTransform() * t
                            v_clone.setPos(0,0)
                            v_clone.setTransform(final_transform)
                            
                            # Set Style
                            pen = v_clone.pen()
                            pen.setStyle(Qt.DashLine)
                            v_clone.setPen(pen)
                            v_clone.setFlag(QGraphicsPathItem.ItemIsSelectable, False)
                            
                            virtual_parts.append(v_clone)
                    
                    current_x += item_w + col_spacing
                current_y += item_h + row_spacing

            # Step C: Create VirtualArrayItem
            # We pass items. The class should handle setting parent.
            # But items must not be in scene yet. (Our clones are not)
            virtual_group = VirtualArrayItem(real_clones, virtual_parts)
            
            # Step D: Commands
            # 1. Remove original items
            del_cmd = DeleteItemsCommand(self.whiteboard.canvas, valid_items)
            # 2. Add virtual group
            add_cmd = AddItemCommand(self.whiteboard.canvas, virtual_group)
            
            macro = MacroCommand("虚阵列排版")
            macro.add_command(del_cmd)
            macro.add_command(add_cmd)
            
            macro.redo()
            self.whiteboard.canvas.edit_manager.push_undo(macro)
            self.whiteboard.canvas.update()

    def _clone_item(self, template):
        from ui.graphics_items import EditablePathItem
        from PyQt5.QtWidgets import QGraphicsPathItem
        
        new_item = None
        if isinstance(template, EditablePathItem):
            try:
                new_item = EditablePathItem(list(template._points), template._color, template._smooth)
                if hasattr(template, '_segment_types'):
                    new_item._segment_types = list(template._segment_types)
                if hasattr(template, '_control_points'):
                    new_item._control_points = dict(template._control_points)
                new_item.setPen(template.pen())
                new_item.setBrush(template.brush())
                # Copy Transform and Pos
                new_item.setPos(template.pos())
                new_item.setTransform(template.transform())
            except:
                new_item = None
        
        if new_item is None:
            if hasattr(template, 'path'):
                new_item = QGraphicsPathItem(template.path())
                new_item.setPen(template.pen())
                new_item.setBrush(template.brush())
                new_item.setPos(template.pos())
                new_item.setTransform(template.transform())
        return new_item

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

    def _get_selection_bounding_rect(self):
        """返回当前选中项的联合包围盒（场景坐标）。"""
        try:
            selected_items = self.whiteboard.canvas.scene.selectedItems()
            if not selected_items:
                return None

            bounding_rect = None
            for item in selected_items:
                try:
                    br = item.sceneBoundingRect()
                except Exception:
                    continue
                if not br.isValid():
                    continue
                if bounding_rect is None:
                    bounding_rect = br
                else:
                    bounding_rect = bounding_rect.united(br)

            if bounding_rect is None or not bounding_rect.isValid():
                return None
            return bounding_rect
        except Exception:
            return None

    @staticmethod
    def _parse_positive_float(text):
        """解析正浮点数；非法时返回 None。"""
        try:
            value = float(str(text).strip())
        except Exception:
            return None
        if value <= 0 or math.isnan(value) or math.isinf(value):
            return None
        return value

    def open_resize_dialog(self):
        """打开“修改尺寸”对话框，按输入宽高缩放当前选中对象。"""
        from PyQt5.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QCheckBox,
            QPushButton,
        )
        from PyQt5.QtGui import QDoubleValidator

        selection_rect = self._get_selection_bounding_rect()
        if selection_rect is None:
            QMessageBox.information(self, "修改尺寸", "请先选中需要修改尺寸的对象。")
            return

        original_width = selection_rect.width()
        original_height = selection_rect.height()
        if original_width <= 0 or original_height <= 0:
            QMessageBox.warning(self, "修改尺寸", "当前选中对象的宽度或高度无效。")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("修改尺寸")
        dialog.setModal(True)
        dialog.setMinimumWidth(420)

        root = QVBoxLayout(dialog)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        root.addLayout(grid)

        grid.addWidget(QLabel(""), 0, 0)
        lbl_old = QLabel("原始尺寸")
        lbl_new = QLabel("修改尺寸")
        lbl_old.setAlignment(Qt.AlignCenter)
        lbl_new.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl_old, 0, 1)
        grid.addWidget(lbl_new, 0, 2)

        grid.addWidget(QLabel("宽度:"), 1, 0)
        old_width_edit = QLineEdit(f"{original_width:.3f}")
        old_width_edit.setReadOnly(True)
        old_width_edit.setFocusPolicy(Qt.NoFocus)
        old_width_edit.setStyleSheet("QLineEdit { background: #f0f0f0; color: #666; }")
        grid.addWidget(old_width_edit, 1, 1)
        new_width_edit = QLineEdit(f"{original_width:.3f}")
        grid.addWidget(new_width_edit, 1, 2)

        grid.addWidget(QLabel("高度:"), 2, 0)
        old_height_edit = QLineEdit(f"{original_height:.3f}")
        old_height_edit.setReadOnly(True)
        old_height_edit.setFocusPolicy(Qt.NoFocus)
        old_height_edit.setStyleSheet("QLineEdit { background: #f0f0f0; color: #666; }")
        grid.addWidget(old_height_edit, 2, 1)
        new_height_edit = QLineEdit(f"{original_height:.3f}")
        grid.addWidget(new_height_edit, 2, 2)

        lock_ratio = QCheckBox("锁定比例")
        lock_ratio.setChecked(True)
        grid.addWidget(lock_ratio, 3, 2, 1, 1, Qt.AlignLeft)

        validator = QDoubleValidator(0.0, 1e9, 3, dialog)
        validator.setNotation(QDoubleValidator.StandardNotation)
        new_width_edit.setValidator(validator)
        new_height_edit.setValidator(validator)

        ratio = original_width / original_height if original_height > 0 else 1.0
        syncing = {"busy": False}

        def _sync_height_from_width():
            if syncing["busy"] or not lock_ratio.isChecked():
                return
            width_value = self._parse_positive_float(new_width_edit.text())
            if width_value is None or ratio <= 0:
                return
            syncing["busy"] = True
            new_height_edit.setText(f"{width_value / ratio:.3f}")
            syncing["busy"] = False

        def _sync_width_from_height():
            if syncing["busy"] or not lock_ratio.isChecked():
                return
            height_value = self._parse_positive_float(new_height_edit.text())
            if height_value is None or ratio <= 0:
                return
            syncing["busy"] = True
            new_width_edit.setText(f"{height_value * ratio:.3f}")
            syncing["busy"] = False

        new_width_edit.textEdited.connect(lambda _text: _sync_height_from_width())
        new_height_edit.textEdited.connect(lambda _text: _sync_width_from_height())

        def _on_lock_toggled(checked):
            if not checked:
                return
            if new_height_edit.hasFocus():
                _sync_width_from_height()
            else:
                _sync_height_from_width()

        lock_ratio.toggled.connect(_on_lock_toggled)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        apply_btn = QPushButton("修改")
        apply_btn.setMinimumWidth(110)
        apply_btn.setDefault(True)
        button_row.addWidget(apply_btn)
        root.addLayout(button_row)

        def _apply_resize():
            new_width = self._parse_positive_float(new_width_edit.text())
            new_height = self._parse_positive_float(new_height_edit.text())
            if new_width is None or new_height is None:
                QMessageBox.warning(dialog, "输入错误", "宽度和高度必须是大于 0 的数字。")
                return

            current_rect = self._get_selection_bounding_rect()
            if current_rect is None:
                QMessageBox.information(dialog, "修改尺寸", "当前没有可用的选中对象。")
                return

            # 复用现有参数化缩放逻辑：保持当前中心，仅替换目标宽高。
            self.x_input.setText(f"{current_rect.center().x():.6f}")
            self.y_input.setText(f"{current_rect.center().y():.6f}")
            self.width_input.setText(f"{new_width:.6f}")
            self.height_input.setText(f"{new_height:.6f}")
            self._apply_position_and_size_changes()
            self.show_status_message(f"已修改尺寸: {new_width:.3f} x {new_height:.3f} mm")
            dialog.accept()

        apply_btn.clicked.connect(_apply_resize)
        new_width_edit.returnPressed.connect(_apply_resize)
        new_height_edit.returnPressed.connect(_apply_resize)

        new_width_edit.setFocus()
        new_width_edit.selectAll()
        dialog.exec_()

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
