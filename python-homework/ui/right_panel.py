#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧属性面板
"""
import os
import configparser

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                             QRadioButton, QGridLayout, QStackedWidget, QHeaderView, QSizePolicy, QFileDialog, QMessageBox, QDialog, QButtonGroup,
                             QStyledItemDelegate, QStyle, QMenu, QTreeWidget, QTreeWidgetItem, QDialogButtonBox, QFrame)
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView, QListView
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter, QPen, QDoubleValidator
from .device_config_dialog import DeviceConfigDialog
from .debug_control_dialog import CommandDebugDialog
from my_io.gcode.gcode_exporter import GCodeExporter
from utils.device_manager import DeviceManager
from my_io.communication.laser_communicator import LaserCommunicator


class LayerParams:
    """图层参数数据结构"""
    def __init__(self, color: QColor):
        self.color = color
        self.mode = "激光切割"
        self.is_output = True
        self.is_visible = True
        self.is_locked = False
        self.speed = 100.0
        self.min_power = 30.0
        self.max_power = 30.0
        self.scan_mode = "水平单向"
        self.scan_interval = 0.1
        self.scan_direction = "跟随全局"
        self.priority = 1
        self.name = "" # 预留
        
        # 新增参数
        self.is_speed_default = False # 速度是否默认
        self.repeat_count = 1
        self.is_blowing = True
        self.seal_gap = 0.0
        self.laser_on_delay = 0
        self.laser_off_delay = 0
        self.is_pierce_mode = False
        self.pierce_power = 50.0  # 简化：统一打穿功率

        # 激光2参数
        self.speed_2 = 100.0
        self.min_power_2 = 30.0
        self.max_power_2 = 30.0

PARAM_OPTIONS = {
    "扫描模式": ["一般模式", "特殊模式"],
    "逐行送料": ["是", "否"],
    "结束送料": ["是", "否"],
    "X轴开机复位": ["是", "否"],
    "Y轴开机复位": ["是", "否"],
    "Z轴开机复位": ["是", "否"],
    "U轴开机复位": ["是", "否"],
    "走边框模式": ["关光走边框", "开光切边框", "四角打点"],
    "阵列加工方式": ["双向走阵列", "单向走阵列"],
    "吹气方式": ["出光吹气", "加工吹气", "一直吹气"],
    "回位位置": ["定位点", "原点", "锚点"],
    "寻焦模式": ["接触式寻焦", "非接触式寻焦"],
    "使能旋转雕刻": ["是", "否"],
    "快慢速切换使能": ["是", "否"],
    "Z轴升降模式": ["电机模式", "IO模式"],
}

class OneClickSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("切割参数")
        self.resize(300, 100)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(QLabel("切割模式"))
        
        self.combo = QComboBox()
        self.combo.addItems(["慢速切割", "精度切割", "普通切割", "快速切割", "超快速切割"])
        
        # 下拉框样式设置
        self.combo.setMaxVisibleItems(10)
        self.combo.setEditable(True)
        self.combo.lineEdit().setReadOnly(True)
        
        layout.addWidget(self.combo)
        
        # 添加标准按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

class RotationSpeedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置旋转速度")
        self.setFixedSize(240, 100)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 中间区域使用 QFrame 模拟 sunken 边框
        container = QFrame(self)
        container.setFrameShape(QFrame.Box) # 或者 QFrame.StyledPanel
        container.setFrameShadow(QFrame.Sunken)
        container.setLineWidth(1)
        
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(5)
        container_layout.setAlignment(Qt.AlignCenter)
        
        lbl = QLabel("速度(mm/s):")
        container_layout.addWidget(lbl)
        
        self.speed_input = QLineEdit("50.00")
        self.speed_input.setFixedWidth(100) 
        # 设置输入校验，仅允许输入数字
        validator = QDoubleValidator(0.0, 9999.0, 3, self.speed_input)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.speed_input.setValidator(validator)
        container_layout.addWidget(self.speed_input)
        
        main_layout.addWidget(container)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        
        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.setFixedSize(60, 22)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setFixedSize(60, 22)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        
        main_layout.addLayout(btn_layout)

class UserParamDelegate(QStyledItemDelegate):
    """自定义委托，用于优化用户参数树的编辑体验（增加高度、字号）"""
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        # 增加行高，设置为32（根据需要调整）
        size.setHeight(max(size.height(), 32))
        return size

    def createEditor(self, parent, option, index):
        # 第0列（参数名）不可编辑
        if index.column() == 0:
            return None
            
        # 第1列是值
        if index.column() == 1:
            # 获取参数名称（第0列）
            name_idx = index.model().index(index.row(), 0, index.parent())
            param_name = name_idx.data()
            
            if param_name in PARAM_OPTIONS:
                combo = QComboBox(parent)
                combo.addItems(PARAM_OPTIONS[param_name])
                
                # 下拉框样式设置
                combo.setMaxVisibleItems(10)
                combo.setEditable(True)
                combo.lineEdit().setReadOnly(True)
                
                return combo
                
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
             val = index.data(Qt.EditRole)
             idx = editor.findText(val)
             if idx >= 0:
                 editor.setCurrentIndex(idx)
        else:
             super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
             model.setData(index, editor.currentText())
        else:
             super().setModelData(editor, model, index)

class LayerColorDelegate(QStyledItemDelegate):
    """自定义委托，用于第一列图层颜色的显示"""
    def paint(self, painter, option, index):
        # 1. 保存当前状态
        painter.save()
        
        # 2. 如果选中，绘制高亮背景（深蓝色）
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#0078d7"))  # 经典选中蓝
            # 注意：不去除 State_Selected，否则文字颜色可能不正确（如果要绘制文字的话）
            
        # 3. 绘制图层颜色块
        # 获取存储的颜色
        bg_brush = index.data(Qt.BackgroundRole)
        if bg_brush:
             # 我们希望颜色块不要填满整个单元格，而是有一定的边距，或者填满但有文字
             # 根据用户截图，颜色块是填满的或者很大的
             # 这里直接使用 BackgroundRole 绘制，但可能会覆盖掉选中的蓝色背景
             # 如果用户想要 "后面覆盖一层蓝色"，意味着颜色块可能比单元格小？
             # 或者颜色块本身是透过一点蓝色的？
             # "图层颜色不要被覆盖，后面覆盖一层蓝色" -> 这通常意味着颜色块是不透明的，且位于蓝色背景之上
             
             # 如果是全填充，那么蓝色就看不见了
             # 所以，可能颜色块需要留一点边距？或者颜色块本来就不是全填充的？
             # 如果直接使用默认的 paint，当选中时，style 会覆盖 background
             
             # 我们手动绘制颜色
             color = bg_brush.color()
             rect = option.rect
             
             # 方案：绘制一个略小的矩形作为颜色块，这样能看到背后的蓝色选中背景
             # 或者，如果用户意思是像 Screenshot 3 那样（第一列依然是全显示的颜色）
             # 那么选中色在第一列其实是被遮挡的？
             # 但是 Screenshot 3 中，选中行第一列的字是白色的吗？如果是，说明选中状态生效了。
             # 让我们尝试绘制全铺满的颜色，但是设置一定的透明度？不对。
             
             # 按照 "图层颜色不要被覆盖" 理解，应该优先显示图层颜色。
             # 按照 "后面覆盖一层蓝色" 理解，如果图层颜色是半透明或者有边距，能看到蓝色。
             # 如果图层颜色是不透明的全填充，那 "后面覆盖一层蓝色" 实际上是看不到的，除了可能文字变白。
             
             # 我们尝试：只绘制背景色，不绘制默认的选中背景覆盖
             painter.fillRect(option.rect, color)
             
        # 4. 绘制文字（如果有）
        text = index.data(Qt.DisplayRole)
        if text:
            # 选中时文字变白
            if option.state & QStyle.State_Selected:
                painter.setPen(Qt.white)
            else:
                # 需考虑背景色深浅
                # 这里简单处理，如果 paint 已经填充了背景色，我们需要对比度
                # 之前代码里有根据背景色判断文字颜色的逻辑
                fg_brush = index.data(Qt.ForegroundRole)
                if fg_brush:
                    painter.setPen(fg_brush.color())
                else:
                     painter.setPen(Qt.black)
            
            painter.drawText(option.rect, Qt.AlignCenter, text)
            
        painter.restore()

class LayerTable(QTableWidget):
    """支持拖拽排序的图层表格"""
    # 修改信号签名，传递源行号和目标行号
    layerMoved = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.drop_indicator_row = -1 # 用于指示插入位置的行号

    def dragMoveEvent(self, event):
        """处理拖动过程中的移动事件，计算并绘制插入指示器"""
        if event.source() == self:
            event.accept()
            # 获取当前鼠标位置对应的行
            index = self.indexAt(event.pos())
            if not index.isValid():
                # 如果在最后一行下面，则指向最后一行之后
                self.drop_indicator_row = self.rowCount()
            else:
                # 否则指向当前鼠标所在行的上方或下方？
                # 通常逻辑：如果覆盖了某行，且是 InternalMove，我们假设插入到该行之前
                # 但如果是最后一行，根据位置可能插入到最后
                
                # 简单处理：插入到鼠标所在行的位置（即该行之前）
                # 为了防止闪烁，我们可以计算一下是在行的上半部分还是下半部分
                # 这里简单点：直接插入到 indexAt 的行位置（即在此行上方插入）
                self.drop_indicator_row = index.row()
                
                # 如果鼠标在最后一行的下半部分，则认为是追加到最后
                # 但 QTableWidget 的 indexAt 是精确的
                pass
            
            # 强制 viewport 重绘以显示指示线
            self.viewport().update()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        """拖出时清除指示器"""
        self.drop_indicator_row = -1
        self.viewport().update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event):
        """重写绘制事件，在 Items 绘制完后绘制插入指示线"""
        super().paintEvent(event)
        
        if self.drop_indicator_row >= 0:
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor("#808080"), 2)) # 灰色，2像素宽
            
            # 计算绘制位置
            if self.drop_indicator_row < self.rowCount():
                # 获取该行的 Y 坐标
                # visualRect 返回的是在 viewport 中的坐标
                rect = self.visualRect(self.model().index(self.drop_indicator_row, 0))
                y = rect.top()
            else:
                # 如果是在最后一行之后
                if self.rowCount() > 0:
                    rect = self.visualRect(self.model().index(self.rowCount() - 1, 0))
                    y = rect.bottom()
                else:
                    y = 0 # 表格为空时
            
            # 绘制横线
            painter.drawLine(0, y, self.viewport().width(), y)

    def dropEvent(self, event):
        self.drop_indicator_row = -1 # 清除指示器
        self.viewport().update()
        
        if event.source() == self:
            event.accept()
            rows = sorted(set(item.row() for item in self.selectedItems()))
            if not rows:
                return
            current_row = rows[0]
            
            target_index = self.indexAt(event.pos())
            if not target_index.isValid():
                target_row = self.rowCount()
            else:
                target_row = target_index.row()
                
            if current_row == target_row:
                return

            # 不再在本地执行 move_row，而是通知上层去刷新数据
            # self.move_row(current_row, target_row)
            self.layerMoved.emit(current_row, target_row)
        else:
            super().dropEvent(event)

    def move_row(self, source_row, target_row):
        # 暂时屏蔽信号，防止在移除和插入过程中触发 itemChanged 等信号
        self.blockSignals(True)
        try:
            items = []
            for col in range(self.columnCount()):
                items.append(self.takeItem(source_row, col))
            
            self.removeRow(source_row)
            
            if source_row < target_row:
                target_row -= 1
                
            self.insertRow(target_row)
            for col, item in enumerate(items):
                # 只有当 item 不为 None 时才设置回表格
                if item:
                    self.setItem(target_row, col, item)
            
            self.selectRow(target_row)
        except Exception as e:
            print(f"Error moving layer row: {e}")
        finally:
            # 恢复信号
            self.blockSignals(False)

class RightPanel(QWidget):
    """右侧属性面板"""
    
    # 信号：当图层参数发生变化时发出（用于通知主窗口更新路径预览等）
    layerParamsChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None # 持有 Canvas 引用
        self._internal_selection_change = False  # 防止循环触发选中的标志
        self.layer_data = {} # Key: hex color string, Value: LayerParams
        self.layer_order = [] # 存储图层顺序（hex color string list）
        
        self.communicator = LaserCommunicator()
        self.communicator.log_message.connect(self.on_comm_log)
        self.communicator.error_occurred.connect(self.on_comm_error)
        self.communicator.sending_finished.connect(self.on_sending_finished)
        self.communicator.connection_changed.connect(self.on_connection_changed) # 添加连接状态监听
        
        self.current_layer_color = None # 当前选中的图层颜色（用于解决焦点丢失时的参数保存问题）
        
        self.init_ui()
        
        # 监听设备列表变化
        DeviceManager().devices_changed.connect(self.refresh_device_list_and_restore_selection)

    def on_connection_changed(self, connected):
        """当底层连接状态改变时触发"""
        # 可以更新UI状态，例如按钮颜色等
        pass
        
    def refresh_device_list_and_restore_selection(self):
        """刷新设备列表，并尝试保持选中项（如果有新增，选中新增）"""
        current_text = self.combo_device.currentText()
        old_count = self.combo_device.count() # 记录刷新前的数量
        
        self.refresh_device_list()
        
        new_count = self.combo_device.count()
        
        # 如果数量增加了，说明很可能是 CommandDebugDialog 添加了新设备，此时应自动选中最新的那个
        if new_count > old_count:
            self.combo_device.setCurrentIndex(new_count - 1)
        else:
            # 否则尝试保持之前的选中
            idx = self.combo_device.findText(current_text)
            if idx >= 0:
                self.combo_device.setCurrentIndex(idx)
            else:
                # 如果之前的项不存在了（被修改了），默认选中第一个
                 if self.combo_device.count() > 0:
                     self.combo_device.setCurrentIndex(0)

    def set_canvas(self, canvas):
        """设置画布引用并连接信号"""
        self.canvas = canvas
        # 监听场景变化以更新图层列表
        self.canvas.scene.changed.connect(self.update_layer_list)
        # 监听选择变化以更新参数显示
        self.canvas.scene.selectionChanged.connect(self.on_selection_changed)
        # 初始化图层列表
        self.update_layer_list(force=True)
        # 延迟加载反向间隙值（确保控件已创建）
        QTimer.singleShot(100, self._load_backlash_values)
    
    def _load_backlash_values(self):
        """加载反向间隙X和Y的值"""
        if not self.canvas or not hasattr(self, 'backlash_x_edit'):
            return
        
        try:
            # 从canvas的user_params或optimize_settings中读取
            if hasattr(self.canvas, 'user_params'):
                params = self.canvas.user_params
                if 'backlash_x' in params:
                    self.backlash_x_edit.setText(f"{params['backlash_x']:.3f}")
                if 'backlash_y' in params:
                    self.backlash_y_edit.setText(f"{params['backlash_y']:.3f}")
            elif hasattr(self.canvas, 'optimize_settings') and 'user_backlash' in self.canvas.optimize_settings:
                config = self.canvas.optimize_settings['user_backlash']
                self.backlash_x_edit.setText(f"{config.get('x', 0.0):.3f}")
                self.backlash_y_edit.setText(f"{config.get('y', 0.0):.3f}")
        except Exception as e:
            print(f"加载反向间隙值失败: {e}")
    
    def _save_backlash_values(self):
        """保存反向间隙X和Y的值"""
        if not self.canvas or not hasattr(self, 'backlash_x_edit'):
            return
        
        try:
            # 读取输入框的值
            try:
                backlash_x = float(self.backlash_x_edit.text().strip() or "0")
            except ValueError:
                backlash_x = 0.0
            
            try:
                backlash_y = float(self.backlash_y_edit.text().strip() or "0")
            except ValueError:
                backlash_y = 0.0
            
            # 保存到canvas的optimize_settings中
            if not hasattr(self.canvas, 'optimize_settings'):
                self.canvas.optimize_settings = {}
            
            self.canvas.optimize_settings['user_backlash'] = {
                'x': backlash_x,
                'y': backlash_y
            }
        except Exception as e:
            print(f"保存反向间隙值失败: {e}")

    def init_ui(self):
        """初始化界面"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # 创建标签页并为每页添加可滚动区域，避免放大/缩放时内部控件被异常拉伸
        self.tabs = QTabWidget()
        self.tabs.addTab(self._wrap_tab(self.create_processing_tab()), "加工")
        self.tabs.addTab(self._wrap_tab(self.create_output_tab()), "输出")
        self.tabs.addTab(self._wrap_tab(self.create_file_tab()), "文档")
        self.tabs.addTab(self._wrap_tab(self.create_user_tab()), "用户")
        self.tabs.addTab(self._wrap_tab(self.create_test_tab()), "测试")
        # 历史面板（列出撤销/重做历史）
        self.tabs.addTab(self._wrap_tab(self.create_history_tab()), "历史")

        root_layout.addWidget(self.tabs, 1)

        self.create_fixed_bottom_area(root_layout)

        # 设置最小宽度并限制最大宽度，防止全屏时右侧面板被过度拉伸导致内部控件变形
        self.setMinimumWidth(320)
        self.setMaximumWidth(520)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

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
        """底部的区域"""
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(6)

        # 防止在高 DPI / 全屏时被过度拉伸：限制底部区域最大高度并固定其纵向策略
        from PyQt5.QtWidgets import QSizePolicy as _QSizePolicy
        bottom_widget.setSizePolicy(_QSizePolicy.Preferred, _QSizePolicy.Fixed)
        # bottom_widget.setMaximumHeight(360)

        # 1. 数据加工 GroupBox
        process_group = QGroupBox("数据加工")
        process_layout = QVBoxLayout()
        process_layout.setContentsMargins(5, 5, 5, 5)
        process_layout.setSpacing(4)

        # Row 1: Start, Pause/Resume, Stop
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(2)
        
        btn_start = QPushButton("开始")
        btn_pause = QPushButton("暂停/继续")
        btn_stop = QPushButton("停止")
        
        btn_start.clicked.connect(self.on_btn_start_clicked)
        btn_pause.clicked.connect(self.on_btn_pause_clicked)
        btn_stop.clicked.connect(self.on_btn_stop_clicked)
        
        for btn in [btn_start, btn_pause, btn_stop]:
             btn.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
             btn.setMinimumHeight(28)
             row1_layout.addWidget(btn)
        
        process_layout.addLayout(row1_layout)

        # Row 2: Save Offline, Offline Output, Download
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(2)

        btn_save_offline = QPushButton("保存为脱机文件")
        btn_offline_output = QPushButton("脱机文件输出")
        btn_download = QPushButton("下载")

        btn_save_offline.clicked.connect(self.on_btn_save_offline_clicked)
        btn_offline_output.clicked.connect(self.on_btn_offline_output_clicked)
        btn_download.clicked.connect(self.on_btn_download_clicked)

        for btn in [btn_save_offline, btn_offline_output, btn_download]:
             btn.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
             btn.setMinimumHeight(28)
             row2_layout.addWidget(btn)

        process_layout.addLayout(row2_layout)

        # Row 3: Graphic Positioning
        row3_layout = QHBoxLayout()
        row3_layout.setSpacing(2)
        
        lbl_pos = QLabel("图形定位位置:")
        combo_pos = QComboBox()
        combo_pos.setView(QListView())
        combo_pos.setMaxVisibleItems(10)
        combo_pos.setEditable(True)
        combo_pos.lineEdit().setReadOnly(True)
        combo_pos.addItems(["当前位置", "原定位点", "机械原点", "绝对坐标"])
        combo_pos.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        combo_pos.setMinimumHeight(24)

        row3_layout.addWidget(lbl_pos)
        row3_layout.addWidget(combo_pos)
        process_layout.addLayout(row3_layout)

        # Row 4: Checkboxes and Border buttons
        row4_layout = QHBoxLayout()
        
        # Left side: Checkboxes
        checks_layout = QVBoxLayout()
        checks_layout.setSpacing(2)
        
        chk_optimize = QCheckBox("路径优化")
        chk_optimize.setChecked(True)
        chk_output_selected = QCheckBox("输出选中图形")
        chk_selected_pos = QCheckBox("选中图形定位")
        chk_selected_pos.setEnabled(False)
        chk_selected_pos.setStyleSheet("color: gray;")

        def on_output_selected_changed(checked):
            chk_selected_pos.setEnabled(checked)
            chk_selected_pos.setStyleSheet("color: black;" if checked else "color: gray;")
        
        chk_output_selected.toggled.connect(on_output_selected_changed)

        checks_layout.addWidget(chk_optimize)
        checks_layout.addWidget(chk_output_selected)
        checks_layout.addWidget(chk_selected_pos)
        
        row4_layout.addLayout(checks_layout)

        # Right side: Border buttons
        border_btns_layout = QVBoxLayout()
        border_btns_layout.setSpacing(2)
        
        btn_cut_border = QPushButton("切边框")
        btn_walk_border = QPushButton("走边框")
        
        btn_cut_border.clicked.connect(self.on_btn_cut_border_clicked)
        btn_walk_border.clicked.connect(self.on_btn_walk_border_clicked)

        for btn in [btn_cut_border, btn_walk_border]:
            btn.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
            btn.setMinimumHeight(28)
            border_btns_layout.addWidget(btn)

        row4_layout.addLayout(border_btns_layout)
        
        process_layout.addLayout(row4_layout)
        process_group.setLayout(process_layout)
        bottom_layout.addWidget(process_group)

        # 2. 设备端口 GroupBox
        device_group = QGroupBox("设备端口")
        device_layout = QHBoxLayout()
        device_layout.setContentsMargins(5, 5, 5, 5)
        device_layout.setSpacing(5)

        btn_config = QPushButton("配置")
        btn_config.setMinimumHeight(28)
        btn_config.clicked.connect(self.open_device_config_dialog)
        self.combo_device = QComboBox()
        self.combo_device.setView(QListView())
        self.combo_device.setMinimumHeight(28)
        self.combo_device.setMaxVisibleItems(10)
        # 防止下拉框遮挡：设置为可编辑但只读
        self.combo_device.setEditable(True)
        self.combo_device.lineEdit().setReadOnly(True)
        self.combo_device.setStyleSheet("QComboBox { background-color: #ffffff; }")
        
        self.refresh_device_list()
        
        device_layout.addWidget(btn_config)
        device_layout.addWidget(self.combo_device, 1) # Stretch combo box

        device_group.setLayout(device_layout)
        bottom_layout.addWidget(device_group)

        parent_layout.addWidget(bottom_widget)

        bottom_widget.setStyleSheet("""
               background-color: #f5f5f5;
               border-top: 1px solid #d0d0d0;
               padding-top: 6px;  /* 缩小顶部内边距 */
           """)

    def refresh_device_list(self):
        """刷新设备列表"""
        self.combo_device.clear()
        devices = DeviceManager().get_devices()
        for dev in devices:
            self.combo_device.addItem(f"{dev['name']}---({dev['address']})")

    def open_device_config_dialog(self):
        """打开设备配置对话框"""
        # 获取当前选中的索引
        current_index = self.combo_device.currentIndex()
        
        dialog = DeviceConfigDialog(self, current_index=current_index)
        dialog.exec_()
        
        # 对话框关闭后刷新列表
        self.refresh_device_list()
        
        # 获取用户在对话框中选中的设备索引
        selected_index = dialog.get_selected_index()
        if selected_index >= 0 and selected_index < self.combo_device.count():
            self.combo_device.setCurrentIndex(selected_index)
            # 自动尝试连接
            self.connect_current_device()

    def connect_current_device(self):
        """尝试连接当前选中的设备"""
        text = self.combo_device.currentText()
        if not text:
            QMessageBox.warning(self, "提示", "请先选择设备")
            return False
            
        try:
            # 解析格式: "Name---(Address)"
            start = text.rfind("(")
            end = text.rfind(")")
            if start == -1 or end == -1:
                # 尝试直接解析
                address = text
            else:
                address = text[start+1:end]
            
            if address.startswith("Web:"):
                ip = address.split(":", 1)[1]
                return self.communicator.connect_tcp(ip, 502)
            elif address.startswith("USB:"):
                port = address.split(":", 1)[1]
                return self.communicator.connect_rtu(port, 115200)
            else:
                # 默认尝试作为串口处理
                return self.communicator.connect_rtu(address, 115200)
                
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法解析设备地址: {text}\n错误: {str(e)}")
            return False

    def check_connection_and_alert(self):
        """检查连接状态，未连接则尝试连接"""
        if not self.communicator.is_connected:
            # 尝试自动连接
            if self.connect_current_device():
                return True
            return False
        return True

    def get_output_enabled_colors(self) -> list:
        """获取允许输出的图层颜色列表"""
        allowed = []
        # 使用 layer_order 确保输出顺序与列表顺序一致
        order = self.layer_order if self.layer_order else self.layer_data.keys()
        
        for color_hex in order:
            if color_hex in self.layer_data:
                params = self.layer_data[color_hex]
                if params.is_output:
                    allowed.append(color_hex)
        return allowed

    def on_btn_start_clicked(self):
        """开始加工"""
        # 1. 检查连接
        if not self.check_connection_and_alert():
            return
        
        # 2. 生成 GCode
        if not self.canvas:
            return
            
        try:
            exporter = GCodeExporter()
            # 更新配置
            exporter.set_config({
                'feed_rate': self.speed_spin.value() * 60, # mm/s -> mm/min
                'max_laser_power': self.max_power_spin.value() * 2.55 # % -> 0-255
            })

            # 从当前 layer_data 构建导出用的简化图层参数
            try:
                layer_params_map = {}
                for hex_color, p in self.layer_data.items():
                    key = str(hex_color).upper()
                    layer_params_map[key] = {
                        'seal_gap': getattr(p, 'seal_gap', 0.0),
                        'laser_on_delay': getattr(p, 'laser_on_delay', 0),
                        'laser_off_delay': getattr(p, 'laser_off_delay', 0),
                        'mode': getattr(p, 'mode', '激光切割'),
                    }
                exporter.set_layer_params(layer_params_map)
            except Exception:
                pass
            
            lines = exporter.export_canvas(self.canvas, allowed_colors=self.get_output_enabled_colors(), layer_settings=self.layer_data)
            if not lines:
                QMessageBox.warning(self, "提示", "画布为空或没有可输出的图形")
                return
                
            # 3. 发送
            self.communicator.start_sending(lines)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动失败: {str(e)}")

    def on_btn_pause_clicked(self):
        """暂停/继续"""
        if not self.check_connection_and_alert():
            return
        QMessageBox.information(self, "提示", "暂停功能暂未实现")

    def on_btn_stop_clicked(self):
        """停止加工"""
        if not self.check_connection_and_alert():
            return
        self.communicator.stop_sending()

    def on_btn_download_clicked(self):
        """下载: 生成 GCode 并作为文件上传到设备"""
        if not self.check_connection_and_alert():
            return
            
        if not self.canvas:
            return

        try:
            # 1. 生成 GCode
            exporter = GCodeExporter()
            exporter.set_config({
                'feed_rate': self.speed_spin.value() * 60, 
                'max_laser_power': self.max_power_spin.value() * 2.55
            })
            
            lines = exporter.export_canvas(self.canvas, allowed_colors=self.get_output_enabled_colors(), layer_settings=self.layer_data)
            if not lines:
                QMessageBox.warning(self, "提示", "画布为空")
                return

            # 2. 写入临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.nc', encoding='utf-8') as tf:
                tf.write('\n'.join(lines))
                temp_path = tf.name
            
            # 3. 询问用户远程文件名 (可选，这里先硬编码或使用默认)
            remote_filename = "job_download.nc"
            
            # 4. 触发上传
            # 注意: 上传是阻塞操作还是异步？我们现在的 communicator.upload_file_to_sd 是同步阻塞循环且处理事件
            # 最好显示一个进度条对话框，但现在先简单处理
            
            QMessageBox.information(self, "开始下载", f"即将上传 {len(lines)} 行代码到设备 SD 卡...")
            
            success = self.communicator.upload_file_to_sd(temp_path, remote_filename)
            
            os.remove(temp_path) # 清理临时文件
            
            if success:
                QMessageBox.information(self, "完成", "文件下载成功")
            else:
                QMessageBox.warning(self, "失败", "文件下载失败，请查看日志")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"下载过程出错: {str(e)}")

    # ----------------- 测试面板功能实现 -----------------
    def on_test_read_position(self):
        """读取当前位置：发送查询指令"""
        if not self.check_connection_and_alert():
            return
        # 常见的查询状态/位置指令，这里使用 '?' 作为示例
        try:
            self.communicator.send_immediate_gcode("?")
            # 临时置为等待状态
            self.coord_x_label.setText("X: -")
            self.coord_y_label.setText("Y: -")
            self.coord_z_label.setText("Z: -")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送查询失败: {e}")

    def on_test_move_to_target(self):
        """移动到目标位置，发送绝对移动指令"""
        if not self.check_connection_and_alert():
            return
        try:
            x = float(self.x_target.text())
            y = float(self.y_target.text())
        except Exception:
            QMessageBox.warning(self, "输入错误", "目标坐标必须为数字")
            return

        # 使用快速移动 G0 指令
        cmd = f"G0 X{float(x):.3f} Y{float(y):.3f}"
        if self.chk_laser_on.isChecked():
            # 如果勾选出光，先关闭出光（安全）或按需处理
            pass

        self.communicator.send_immediate_gcode(cmd)

    def on_test_prev_time(self):
        """显示前次加工时间（示例为占位）"""
        # 目前没有真实记录，显示占位
        self.prev_time_label.setText("00时:00分:00秒:000毫秒")

    def on_axis_move(self, axis: str, direction: int):
        """单轴点动移动，direction: 1 or -1"""
        if not self.check_connection_and_alert():
            return
        try:
            offset = float(self.offset_edit.text()) * direction
        except Exception:
            QMessageBox.warning(self, "输入错误", "偏移必须为数字")
            return

        try:
            speed = float(self.speed_edit.text())
        except Exception:
            speed = 50.0

        # 转换速度到 mm/min（G代码通常使用 mm/min）
        feed = int(speed * 60)
        # 使用 $J 相对插补点动（参考已有快捷命令）
        cmd = f"$J=G91 {axis}{offset:.3f} F{feed}"
        self.communicator.send_immediate_gcode(cmd)

    def on_origin_xy(self):
        if not self.check_connection_and_alert():
            return
        # 将 XY 轴设置为当前为原点
        self.communicator.send_immediate_gcode("G10 L20 P0 X0 Y0")

    def on_origin_z(self):
        if not self.check_connection_and_alert():
            return
        self.communicator.send_immediate_gcode("G10 L20 P0 Z0")

    def on_origin_u(self):
        if not self.check_connection_and_alert():
            return
        # U 轴同样设置为0（如果存在）
        self.communicator.send_immediate_gcode("G10 L20 P0 U0")

    def on_focus(self):
        if not self.check_connection_and_alert():
            return
        # 寻焦为示例命令，具体命令需根据设备定义
        self.communicator.send_immediate_gcode("G28")

    def on_locate(self):
        if not self.check_connection_and_alert():
            return
        # 定位为示例命令
        self.communicator.send_immediate_gcode("G0 X0 Y0")

    def on_btn_cut_border_clicked(self):
        """切边框"""
        if not self.check_connection_and_alert():
            return
        QMessageBox.information(self, "提示", "切边框功能暂未实现")

    def on_btn_walk_border_clicked(self):
        """走边框"""
        if not self.check_connection_and_alert():
            return
        QMessageBox.information(self, "提示", "走边框功能暂未实现")

    def on_comm_log(self, msg):
        print(f"[Comm] {msg}")
        # 可以显示在状态栏或者其他地方

    def on_comm_error(self, msg):
        QMessageBox.critical(self, "通信错误", msg)

    def on_sending_finished(self):
        QMessageBox.information(self, "提示", "加工完成！")

    def on_btn_save_offline_clicked(self):
        """保存为脱机文件"""
        if not self.canvas:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "保存为脱机文件", "", "NC Files (*.nc);;All Files (*)")
        if file_path:
            try:
                exporter = GCodeExporter()
                # 这里可以根据界面设置更新 exporter.config
                # 例如: exporter.set_config({'feed_rate': self.speed_spin.value() * 60}) 

                # 同样传入图层参数
                try:
                    layer_params_map = {}
                    for hex_color, p in self.layer_data.items():
                        key = str(hex_color).upper()
                        layer_params_map[key] = {
                            'seal_gap': getattr(p, 'seal_gap', 0.0),
                            'laser_on_delay': getattr(p, 'laser_on_delay', 0),
                            'laser_off_delay': getattr(p, 'laser_off_delay', 0),
                            'mode': getattr(p, 'mode', '激光切割'),
                        }
                    exporter.set_layer_params(layer_params_map)
                except Exception:
                    pass

                lines = exporter.export_canvas(self.canvas, allowed_colors=self.get_output_enabled_colors())
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                QMessageBox.information(self, "成功", "脱机文件保存成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def on_btn_offline_output_clicked(self):
        """脱机文件输出"""
        # 模拟输出功能，实际可能需要连接设备或保存到特定位置
        if not self.canvas:
            return
            
        QMessageBox.information(self, "提示", "脱机文件输出功能已就绪。\n(此处应连接设备或执行输出逻辑)")

    def on_layer_moved(self, source_row, target_row):
        """处理图层移动"""
        if not self.layer_order:
             # 如果 layer_order 还没被初始化（应该不会，但做个保险）
             self.update_layer_list() # 这会填充 self.layer_order
             
        if source_row < 0 or source_row >= len(self.layer_order):
             return
             
        # 注意: target_row 可能等于 len，表示追加到最后
        
        # 在列表中移动元素
        item = self.layer_order.pop(source_row)
        
        # 计算插入位置
        # 如果是向下拖拽，source_row < target_row
        # 比如 [A, B, C], 拖 A(0) 到 C(2) 位置。
        # dropEvent 中 target_row 是 drop 时的 indexAt row
        # 如果 drop 到 C (2), target_row=2.
        # 我们希望插在 C 之前： [B, A, C]
        # pop(0) -> A. list=[B, C]. 
        # target=2. target-1=1. insert(1, A) -> [B, A, C]. 正确。
        
        # 如果是 drop 到最后空白处, target_row=3.
        # pop(0) -> A. list=[B, C].
        # target=3. target-1=2. insert(2, A) -> [B, C, A]. 正确。
        
        if source_row < target_row:
             target_row -= 1
        
        # 边界检查
        if target_row < 0: target_row = 0
        if target_row > len(self.layer_order): target_row = len(self.layer_order)
         
        self.layer_order.insert(target_row, item)
        
        # 强制刷新表格
        self.update_layer_list(force=True)

    def create_processing_tab(self):
        """创建加工标签页（图层列表与参数设置）"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. 图层列表
        self.layer_table = LayerTable()
        self.layer_table.setColumnCount(5)
        self.layer_table.layerMoved.connect(self.on_layer_moved)
        self.layer_table.setHorizontalHeaderLabels(["图层", "模式", "输出", "显示", "锁定"])
        self.layer_table.horizontalHeader().setStretchLastSection(False)
        self.layer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.layer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.layer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.layer_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.layer_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.layer_table.verticalHeader().setVisible(False)
        self.layer_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.layer_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layer_table.setEditTriggers(QAbstractItemView.NoEditTriggers) # 禁止直接编辑文本，双击弹窗
        self.layer_table.setMinimumHeight(150)
        
        # 设置特定列的委托
        self.layer_table.setItemDelegateForColumn(0, LayerColorDelegate(self.layer_table))

        # 样式优化
        self.layer_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                gridline-color: #e0e0e0;
                selection-background-color: #0078d7; /* 选中背景色：深蓝 */
                selection-color: #ffffff;            /* 选中文字色：白 */
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)
        
        # 双击事件
        self.layer_table.itemDoubleClicked.connect(self.on_layer_double_clicked)
        # 点击事件更新下方参数 (改为 itemSelectionChanged 以支持所有选择变化)
        self.layer_table.itemSelectionChanged.connect(self.on_layer_selected)
        # 单元格改变事件（处理Checkbox）
        self.layer_table.itemChanged.connect(self.on_layer_item_changed)

        main_layout.addWidget(self.layer_table, 1)

        # 2. 参数设置区域
        param_group = QGroupBox("参数设置")
        param_layout = QVBoxLayout(param_group)
        param_layout.setContentsMargins(5, 5, 5, 5)
        param_layout.setSpacing(4)

        # 颜色显示条 + 输出复选框
        color_row = QHBoxLayout()
        self.color_bar = QLabel()
        self.color_bar.setFixedHeight(20)
        self.color_bar.setStyleSheet("background-color: #cccccc; border: 1px solid #888;")
        color_row.addWidget(self.color_bar, 1)
        
        self.output_check = QCheckBox("输出")
        self.output_check.toggled.connect(self.on_output_check_toggled)
        color_row.addWidget(self.output_check, 0)
        
        param_layout.addLayout(color_row)

        # 速度/优先级
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("速度(mm/s)"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0, 5000)
        self.speed_spin.setValue(100.0)
        row1.addWidget(self.speed_spin)
        
        row1.addWidget(QLabel("优先级"))
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 100)
        row1.addWidget(self.priority_spin)
        param_layout.addLayout(row1)

        # 功率
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("最小功率(%)"))
        self.min_power_spin = QDoubleSpinBox()
        self.min_power_spin.setRange(0, 100)
        self.min_power_spin.setValue(30.0)
        row2.addWidget(self.min_power_spin)
        
        row2.addWidget(QLabel("最大功率(%)"))
        self.max_power_spin = QDoubleSpinBox()
        self.max_power_spin.setRange(0, 100)
        self.max_power_spin.setValue(30.0)
        row2.addWidget(self.max_power_spin)
        param_layout.addLayout(row2)
        
        # 连接参数变更信号
        self.speed_spin.valueChanged.connect(self.on_param_changed)
        self.priority_spin.valueChanged.connect(self.on_param_changed)
        self.min_power_spin.valueChanged.connect(self.on_param_changed)
        self.max_power_spin.valueChanged.connect(self.on_param_changed)

        main_layout.addWidget(param_group)

        # 3. 激光控制（保留）
        laser_layout = QHBoxLayout()
        
        btn_style = """
            QPushButton:checked {
                background-color: #a0a0a0;
                border: 2px solid #555;
                font-weight: bold;
                color: white;
            }
        """
        
        self.laser_group = QButtonGroup(self)
        self.laser_group.setExclusive(True)
        
        self.laser1_btn = QPushButton("激光1")
        self.laser1_btn.setCheckable(True)
        self.laser1_btn.setChecked(True)
        self.laser1_btn.setStyleSheet(btn_style)
        self.laser1_btn.toggled.connect(self.on_laser_btn_toggled)
        self.laser_group.addButton(self.laser1_btn)
        
        self.laser2_btn = QPushButton("激光2")
        self.laser2_btn.setCheckable(True)
        self.laser2_btn.setStyleSheet(btn_style)
        self.laser2_btn.toggled.connect(self.on_laser_btn_toggled)
        self.laser_group.addButton(self.laser2_btn)
        
        laser_layout.addWidget(self.laser1_btn)
        laser_layout.addWidget(self.laser2_btn)
        laser_layout.addStretch()
        main_layout.addLayout(laser_layout)

        # 4. 行列设置（保留，简化显示）
        grid_group = QGroupBox("行列设置")
        grid_layout = QGridLayout(grid_group)
        grid_layout.setContentsMargins(5, 5, 5, 5)
        
        grid_layout.addWidget(QLabel("个数"), 0, 1)
        grid_layout.addWidget(QLabel("奇间隔"), 0, 2)
        grid_layout.addWidget(QLabel("偶间隔"), 0, 3)
        
        grid_layout.addWidget(QLabel("X:"), 1, 0)
        grid_layout.addWidget(QLineEdit("1"), 1, 1)
        grid_layout.addWidget(QLineEdit("0.0"), 1, 2)
        grid_layout.addWidget(QLineEdit("0.0"), 1, 3)
        
        grid_layout.addWidget(QLabel("Y:"), 2, 0)
        grid_layout.addWidget(QLineEdit("1"), 2, 1)
        grid_layout.addWidget(QLineEdit("0.0"), 2, 2)
        grid_layout.addWidget(QLineEdit("0.0"), 2, 3)
        
        main_layout.addWidget(grid_group)

        return widget

    def _wrap_tab(self, widget: QWidget) -> QWidget:
        """Wrap a tab page in a QScrollArea so content scrolls instead of stretching."""
        from PyQt5.QtWidgets import QScrollArea, QWidget, QVBoxLayout

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        scroll.setWidget(widget)

        layout.addWidget(scroll)
        return container

    def update_layer_list(self, changes=None, force=False):
        """扫描画布，更新图层列表"""
        if not self.canvas:
            return

        # 1. 扫描画布上的颜色
        used_colors = set()
        from ui.graphics_items import EditablePathItem, EditableEllipseItem, TextGraphicsItem
        from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem
        
        LAYER_COLOR_ROLE = Qt.UserRole + 100

        # 辅助：收集每种颜色的项目类型，用于推断默认模式
        color_item_types = {} 

        for item in self.canvas.scene.items():
            color = None
            if isinstance(item, (EditablePathItem, EditableEllipseItem)):
                color = item.pen().color()
                item_type = 'vector'
            elif isinstance(item, QGraphicsTextItem):
                color = item.defaultTextColor()
                item_type = 'text'
            elif isinstance(item, TextGraphicsItem):
                color = item.pen().color()
                item_type = 'text'
            elif isinstance(item, QGraphicsPixmapItem):
                # 检查是否有绑定的图层颜色
                color_data = item.data(LAYER_COLOR_ROLE)
                if color_data and isinstance(color_data, QColor):
                    color = color_data
                item_type = 'image'
            
            if color and color.isValid():
                hex_color = color.name().upper()
                used_colors.add(hex_color)
                
                if hex_color not in color_item_types:
                    color_item_types[hex_color] = set()
                color_item_types[hex_color].add(item_type)

        # 2. 同步数据
        for hex_color in used_colors:
            if hex_color not in self.layer_data:
                new_params = LayerParams(QColor(hex_color))
                # 智能识别默认模式
                if hex_color in color_item_types:
                    types = color_item_types[hex_color]
                    if 'image' in types:
                        new_params.mode = "激光扫描"  # 图片默认扫描
                    else:
                        new_params.mode = "激光切割" # 其他默认切割
                
                self.layer_data[hex_color] = new_params

        # --- 优化：检查是否需要重建表格 ---
        if not force:
            current_colors = set()
            for row in range(self.layer_table.rowCount()):
                item = self.layer_table.item(row, 0)
                if item:
                    current_colors.add(item.data(Qt.UserRole))
            
            # 如果颜色集合没有变化，则不重建表格，避免打断用户操作或造成卡顿
            if used_colors == current_colors:
                return
        # --------------------------------

        # 3. 更新表格显示
        # 获取当前选中的颜色，以便恢复选中状态
        current_row = self.layer_table.currentRow()
        selected_color = None
        if current_row >= 0:
            item = self.layer_table.item(current_row, 0)
            if item:
                selected_color = item.data(Qt.UserRole)

        self.layer_table.blockSignals(True) # 暂停信号防止触发 itemChanged
        self.layer_table.setRowCount(0)
        
        # 排序：优先使用已保存的顺序
        if not self.layer_order:
             sorted_colors = sorted(list(used_colors))
        else:
             # 保留 self.layer_order 中的顺序，并添加新出现的颜色
             sorted_colors = [c for c in self.layer_order if c in used_colors]
             new_colors = sorted([c for c in used_colors if c not in sorted_colors])
             sorted_colors.extend(new_colors)
        
        # 更新 layer_order 以保持同步
        self.layer_order = sorted_colors
        
        for row, hex_color in enumerate(sorted_colors):
            params = self.layer_data[hex_color]
            self.layer_table.insertRow(row)
            
            # 列0：图层颜色 + 名称
            # 如果有自定义名称显示名称，否则显示颜色代码
            display_name = params.name if params.name else hex_color
            color_item = QTableWidgetItem(display_name)
            # 设置颜色块作为图标或背景
            # 这里用背景色表示颜色直观
            color_item.setBackground(QColor(hex_color))
            # 字体颜色根据背景深浅调整，或者加个描边？这里简单处理：
            # 如果背景太深，字变白
            c = QColor(hex_color)
            if c.lightness() < 128:
                color_item.setForeground(QColor(255, 255, 255))
            else:
                color_item.setForeground(QColor(0, 0, 0))
                
            color_item.setData(Qt.UserRole, hex_color) # 存储颜色key
            self.layer_table.setItem(row, 0, color_item)
            
            # 列1：模式
            mode_item = QTableWidgetItem(params.mode)
            self.layer_table.setItem(row, 1, mode_item)
            
            # 列2：输出 (Checkbox)
            out_item = QTableWidgetItem()
            out_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            out_item.setCheckState(Qt.Checked if params.is_output else Qt.Unchecked)
            self.layer_table.setItem(row, 2, out_item)
            
            # 列3：显示 (Checkbox)
            # 注意：params.is_visible True 表示显示 -> Checked
            vis_item = QTableWidgetItem()
            vis_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            vis_item.setCheckState(Qt.Checked if params.is_visible else Qt.Unchecked)
            self.layer_table.setItem(row, 3, vis_item)
            
            # 列4：锁定 (Checkbox)
            lock_item = QTableWidgetItem()
            lock_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            lock_item.setCheckState(Qt.Checked if params.is_locked else Qt.Unchecked)
            self.layer_table.setItem(row, 4, lock_item)

        self.layer_table.blockSignals(False)

        # 恢复选中
        if selected_color:
            for row in range(self.layer_table.rowCount()):
                if self.layer_table.item(row, 0).data(Qt.UserRole) == selected_color:
                    self.layer_table.selectRow(row)
                    break

    def on_layer_item_changed(self, item):
        """处理表格中Checkbox的变化"""
        row = item.row()
        col = item.column()
        
        # 获取对应图层的参数
        color_item = self.layer_table.item(row, 0)
        if not color_item:
            return
        hex_color = color_item.data(Qt.UserRole)
        params = self.layer_data.get(hex_color)
        if not params:
            return
            
        # 根据列号更新参数
        if col == 2: # 输出
            params.is_output = (item.checkState() == Qt.Checked)
            self.layerParamsChanged.emit()
        elif col == 3: # 显示
            params.is_visible = (item.checkState() == Qt.Checked)
            self.apply_layer_state(params)
            self.layerParamsChanged.emit()
        elif col == 4: # 锁定
            params.is_locked = (item.checkState() == Qt.Checked)
            self.apply_layer_state(params)
            self.layerParamsChanged.emit()

    def on_layer_selected(self):
        """当图层列表选中项变化时，更新下方参数显示"""
        row = self.layer_table.currentRow()
        if row < 0:
            self.current_layer_color = None
            return
            
        hex_color = self.layer_table.item(row, 0).data(Qt.UserRole)
        self.current_layer_color = hex_color # 更新当前选中的颜色
        
        # --- 新增：实现点选图层 -> 选中画布对应图形 ---
        # 只有当不是程序内部同步触发（即用户手动点击图层列表）时才执行
        if not self._internal_selection_change and self.canvas and self.canvas.scene:
            try:
                target_color_name = hex_color
                
                from ui.graphics_items import EditablePathItem, EditableEllipseItem
                from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsItem
                LAYER_COLOR_ROLE = Qt.UserRole + 100
                
                # 遍历所有项，匹配颜色的设为选中，不匹配的取消选中
                # 注意：这里会触发 selectionChanged 信号，进而触发 on_selection_changed
                # 但由于 on_selection_changed 会再次调用 selectRow (如果是同一行则可能是无操作，或者是重入)
                # 关键是我们需要防止 on_layer_selected 再次被递归调用导致的逻辑混乱
                # 基于 self._internal_selection_change 的保护逻辑主要是在 on_selection_changed -> on_layer_selected 这个方向
                # 这里是 on_layer_selected -> canvas -> on_selection_changed -> on_layer_selected
                # 所以我们需要在这里也设置标志，告诉 on_selection_changed "这是我触发的，你别管" 
                # 或者，on_selection_changed 本身就是为了同步 "Canvas -> Layer List"。
                # 如果 Canvas 变了（因为我们在这里改的），on_selection_changed 会再次尝试 selectRow。
                # 如果 Row 已经是对的，selectRow 不会有副作用。
                
                # 为了安全，我们可以临时禁用 on_selection_changed 的影响？
                # 但 on_selection_changed 是 MainWindow 连接的。RightPanel 不好直接断开。
                # 实际上，只要 on_selection_changed 里的 selectRow 不会改变当前行（因为它就是当前行），
                # 那么 on_layer_selected 就不会再次被触发。
                # 只有当 Canvas 上选中的东西导致 逻辑认为应该选中 另一行时 才会出问题。
                # 这里我们是全选该颜色的所有东西，所以 Canvas 选中的只能是这个颜色的，逻辑上会选中当前行。
                # 所以应该是安全的。
                
                for item in self.canvas.scene.items():
                    # 忽略不可选或隐藏的项
                    if not item.flags() & QGraphicsItem.ItemIsSelectable or not item.isVisible():
                        continue
                        
                    color = None
                    if isinstance(item, (EditablePathItem, EditableEllipseItem)):
                         color = item.pen().color()
                    elif isinstance(item, QGraphicsTextItem):
                         color = item.defaultTextColor()
                    elif isinstance(item, QGraphicsPixmapItem):
                         color_data = item.data(LAYER_COLOR_ROLE)
                         if color_data and isinstance(color_data, QColor):
                             color = color_data
                    
                    if color and color.name().upper() == target_color_name:
                        item.setSelected(True)
                    else:
                        item.setSelected(False)
                     
            except Exception as e:
                print(f"Sync layer selection error: {e}")
        # -----------------------------------------------

        params = self.layer_data.get(hex_color)
        if params:
            self.color_bar.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")
            
            # 暂停信号
            self.speed_spin.blockSignals(True)
            self.priority_spin.blockSignals(True)
            self.min_power_spin.blockSignals(True)
            self.max_power_spin.blockSignals(True)
            self.output_check.blockSignals(True)
            
            # 更新通用参数
            self.priority_spin.setValue(params.priority)
            self.output_check.setChecked(params.is_output)
            
            # 根据当前选中的激光按钮更新速度和功率
            if self.laser2_btn.isChecked():
                # 仅选中激光2时显示激光2参数
                # 确保参数存在，如果不存在则初始化
                if not hasattr(params, 'speed_2'):
                    params.speed_2 = 100.0
                    params.min_power_2 = 30.0
                    params.max_power_2 = 30.0

                self.speed_spin.setValue(params.speed_2)
                self.speed_spin.setEnabled(True)
                self.min_power_spin.setValue(getattr(params, 'min_power_2', 30.0))
                self.max_power_spin.setValue(getattr(params, 'max_power_2', 30.0))
            else:
                # 默认显示激光1参数 (或者都选中时优先显示激光1)
                is_default = getattr(params, 'is_speed_default', False)
                if is_default:
                    self.speed_spin.setValue(100.0)
                    self.speed_spin.setEnabled(False)
                else:
                    self.speed_spin.setValue(params.speed)
                    self.speed_spin.setEnabled(True)
                    
                self.min_power_spin.setValue(params.min_power)
                self.max_power_spin.setValue(params.max_power)
            
            # 恢复信号
            self.speed_spin.blockSignals(False)
            self.priority_spin.blockSignals(False)
            self.min_power_spin.blockSignals(False)
            self.max_power_spin.blockSignals(False)
            self.output_check.blockSignals(False)

    def on_param_changed(self):
        """下方参数修改后保存回数据"""
        # 使用 self.current_layer_color 而不是 currentRow()，避免焦点切换时的竞态条件
        if not self.current_layer_color:
            return
            
        params = self.layer_data.get(self.current_layer_color)
        if params:
            params.priority = self.priority_spin.value()
            
            # 根据当前选中的激光按钮保存参数
            # 使用 group.checkedButton() 确保准确
            checked_btn = self.laser_group.checkedButton()
            is_laser2 = (checked_btn == self.laser2_btn)
            
            if is_laser2:
                params.speed_2 = self.speed_spin.value()
                params.min_power_2 = self.min_power_spin.value()
                params.max_power_2 = self.max_power_spin.value()
            else:
                params.speed = self.speed_spin.value()
                params.min_power = self.min_power_spin.value()
                params.max_power = self.max_power_spin.value()

    def on_output_check_toggled(self, checked):
        """输出复选框切换"""
        # 使用 self.current_layer_color 而不是 currentRow()
        if not self.current_layer_color:
            return
        
        params = self.layer_data.get(self.current_layer_color)
        if params:
            params.is_output = checked
            # 同步更新表格中的Checkbox
            # 需要找到对应的行
            for row in range(self.layer_table.rowCount()):
                item = self.layer_table.item(row, 0)
                if item and item.data(Qt.UserRole) == self.current_layer_color:
                    check_item = self.layer_table.item(row, 2)
                    if check_item:
                        check_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                    break
            self.layerParamsChanged.emit()

    # 激光按钮状态切换回调
    def on_laser_btn_toggled(self, checked):
        # 仅在按钮被选中时刷新参数，避免取消选中时重复刷新
        if checked:
            self.on_layer_selected()

    def on_layer_double_clicked(self, item):
        """双击图层行，弹出属性设置对话框"""
        row = item.row()
        hex_color = self.layer_table.item(row, 0).data(Qt.UserRole)
        
        # 延迟打开对话框，避免在事件处理中阻塞导致崩溃
        # 增加延迟到 50ms 确保事件循环完全处理完双击
        QTimer.singleShot(50, lambda: self._open_layer_settings(hex_color))

    def _open_layer_settings(self, hex_color):
        """打开图层设置对话框"""
        try:
            # 使用新的对话框
            from ui.layer_settings_dialog import LayerSettingsDialog
            # 使用 window() 作为父对象，确保对话框在主窗口之上且模态行为正确
            parent = self.window() if self.window() else self
            dlg = LayerSettingsDialog(self.layer_data, hex_color, parent)
            
            if dlg.exec_() == QDialog.Accepted:
                # 应用状态到画布
                params = self.layer_data.get(hex_color)
                if params:
                    self.apply_layer_state(params)
                
                # 刷新列表显示（更新名称、锁定状态等）
                self.update_layer_list(force=True)
                self.on_layer_selected()
                self.layerParamsChanged.emit()
            
            # 显式销毁对话框
            dlg.deleteLater()
        except Exception as e:
            print(f"Error opening layer settings: {e}")

    def _post_layer_edit_update(self):
        """(已废弃) 图层编辑后的延迟更新"""
        pass

    def show_layer_properties_dialog(self, params):
        """(已废弃) 显示图层属性对话框"""
        pass
        """显示图层属性对话框"""
        from PyQt5.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        
        dlg = QDialog(self)
        dlg.setWindowTitle("图层参数设置")
        layout = QVBoxLayout(dlg)
        
        form = QFormLayout()
        
        # 模式
        mode_combo = QComboBox()
        mode_combo.addItems(["激光切割", "激光扫描", "笔式绘图"])
        mode_combo.setCurrentText(params.mode)
        form.addRow("处理模式:", mode_combo)
        
        # 输出/显示
        output_check = QCheckBox("输出")
        output_check.setChecked(params.is_output)
        form.addRow("", output_check)
        
        visible_check = QCheckBox("显示")
        visible_check.setChecked(params.is_visible)
        form.addRow("", visible_check)
        
        # 扫描设置
        scan_mode_combo = QComboBox()
        scan_mode_combo.addItems(["水平单向", "水平双向", "垂直单向", "垂直双向"])
        scan_mode_combo.setCurrentText(params.scan_mode)
        form.addRow("扫描方式:", scan_mode_combo)
        
        scan_interval_spin = QDoubleSpinBox()
        scan_interval_spin.setRange(0.001, 100.0)
        scan_interval_spin.setDecimals(3)
        scan_interval_spin.setSingleStep(0.01)
        scan_interval_spin.setValue(params.scan_interval)
        form.addRow("扫描间隔(mm):", scan_interval_spin)
        
        # 锁定与重命名
        locked_check = QCheckBox("锁定图层")
        locked_check.setChecked(params.is_locked)
        form.addRow("", locked_check)
        
        name_edit = QLineEdit(params.name)
        form.addRow("图层名称:", name_edit)

        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        
        if dlg.exec_() == QDialog.Accepted:
            params.mode = mode_combo.currentText()
            params.is_output = output_check.isChecked()
            params.is_visible = visible_check.isChecked()
            params.scan_mode = scan_mode_combo.currentText()
            params.scan_interval = scan_interval_spin.value()
            params.is_locked = locked_check.isChecked()
            params.name = name_edit.text()
            
            # 应用状态到画布
            self.apply_layer_state(params)
            # 刷新列表显示（更新名称、锁定状态等）
            self.update_layer_list(force=True)
            self.layerParamsChanged.emit()

    def apply_layer_state(self, params):
        """应用图层状态（可见性、锁定等）"""
        if not self.canvas:
            return
            
        target_color_name = params.color.name().upper()
        from ui.graphics_items import EditablePathItem, EditableEllipseItem
        from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsItem, QGraphicsPixmapItem
        
        LAYER_COLOR_ROLE = Qt.UserRole + 100
        
        for item in self.canvas.scene.items():
            color = None
            if isinstance(item, (EditablePathItem, EditableEllipseItem)):
                color = item.pen().color()
            elif isinstance(item, QGraphicsTextItem):
                color = item.defaultTextColor()
            elif isinstance(item, QGraphicsPixmapItem):
                # 检查是否有绑定的图层颜色
                color_data = item.data(LAYER_COLOR_ROLE)
                if color_data and isinstance(color_data, QColor):
                    color = color_data
            
            if color and color.name().upper() == target_color_name:
                # 可见性
                item.setVisible(params.is_visible)
                
                # 锁定状态 (锁定 = 不可移动 + 不可选择)
                # 注意：EditablePathItem 可能还有其他 flag，这里只控制 Movable/Selectable
                is_unlocked = not params.is_locked
                item.setFlag(QGraphicsItem.ItemIsMovable, is_unlocked)
                item.setFlag(QGraphicsItem.ItemIsSelectable, is_unlocked)
                
                # 如果被锁定且当前被选中，则取消选中
                if params.is_locked and item.isSelected():
                    item.setSelected(False)

    def on_selection_changed(self):
        """画布选择变化时，尝试自动选中对应的图层行"""
        # 如果选中了单个Item，跳转到对应颜色行
        if not self.canvas:
            return
        
        selected = self.canvas.get_selected_items()
        if len(selected) == 1:
            item = selected[0]
            color = None
            from ui.graphics_items import EditablePathItem, EditableEllipseItem
            from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem
            
            LAYER_COLOR_ROLE = Qt.UserRole + 100

            if isinstance(item, (EditablePathItem, EditableEllipseItem)):
                color = item.pen().color()
            elif isinstance(item, QGraphicsTextItem):
                color = item.defaultTextColor()
            elif isinstance(item, QGraphicsPixmapItem):
                # 检查是否有绑定的图层颜色
                color_data = item.data(LAYER_COLOR_ROLE)
                if color_data and isinstance(color_data, QColor):
                    color = color_data
            
            if color:
                hex_color = color.name().upper()
                for row in range(self.layer_table.rowCount()):
                    if self.layer_table.item(row, 0).data(Qt.UserRole) == hex_color:
                        self._internal_selection_change = True  # 设置标志，防止反向触发
                        self.layer_table.selectRow(row)
                        self.on_layer_selected() # 刷新参数显示
                        self._internal_selection_change = False # 复位标志
                        break

    # 激光按钮点击回调
    def on_laser_btn_click(self, laser_num):
        print(f"切换到激光{laser_num}")



    def on_layer_header_btn_click(self):
        """图层"""
        pass

    def on_mode_header_btn_click(self):
        """模式"""
        pass

    def on_output_header_btn_click(self):
        """输出"""
        pass

    def on_hide_header_btn_click(self):
        """隐藏"""
        pass

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
        cycle_order.setView(QListView()) # 解决遮挡问题
        cycle_order.setMaxVisibleItems(10)
        cycle_order.setEditable(True)
        cycle_order.lineEdit().setReadOnly(True)
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
        feed_input.setView(QListView()) # 解决遮挡问题
        feed_input.setMaxVisibleItems(10)
        feed_input.setEditable(True)
        feed_input.lineEdit().setReadOnly(True)
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

        # 用正式表头替代自定义 header 按钮，保证列与表头对齐且可自适应宽度
        layer_table = QTableWidget()
        layer_table.setColumnCount(4)
        layer_table.setRowCount(19)
        layer_table.setMinimumHeight(200)
        layer_table.setHorizontalHeaderLabels(["编号", "文件名", "工时(时:分:秒:毫秒)", "件数"])
        layer_table.verticalHeader().setVisible(False)
        layer_table.horizontalHeader().setStretchLastSection(False)
        from PyQt5.QtWidgets import QHeaderView
        layer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layer_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
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

        layout.addWidget(layer_table)

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
        widget = QWidget()
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 左侧参数区域
        param_widget = QWidget()
        param_layout = QVBoxLayout(param_widget)
        param_layout.setContentsMargins(0, 0, 0, 0)
        param_layout.setSpacing(8)

<<<<<<< HEAD
        # 顶部单选按钮：加工参数 / 辅助参数 / 其他参数
        param_type_layout=QHBoxLayout()
=======
        # 顶部单选按钮组
        param_type_layout = QHBoxLayout()
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
        param_type_layout.setSpacing(10)
        
        self.user_param_group = QButtonGroup(self)
        self.radio_process = QRadioButton("加工参数")
        self.radio_assist = QRadioButton("辅助参数")
        self.radio_other = QRadioButton("其他参数")
        
        self.user_param_group.addButton(self.radio_process, 0)
        self.user_param_group.addButton(self.radio_assist, 1)
        self.user_param_group.addButton(self.radio_other, 2)
        
        param_type_layout.addWidget(self.radio_process)
        param_type_layout.addWidget(self.radio_assist)
        param_type_layout.addWidget(self.radio_other)
        param_type_layout.addStretch()
        
        param_layout.addLayout(param_type_layout)

<<<<<<< HEAD
        # 使用 QStackedWidget 在三种参数页面之间切换
        from PyQt5.QtWidgets import QStackedWidget
        stack = QStackedWidget()
        param_layout.addWidget(stack, 1)

        # -------- 页面1：加工参数（保留原来的切割参数 + 扫描参数） --------
        process_page = QWidget()
        process_layout = QVBoxLayout(process_page)
        process_layout.setContentsMargins(0, 0, 0, 0)
        process_layout.setSpacing(8)

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
        process_layout.addWidget(cut_group)

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
        process_layout.addWidget(scan_group)
        process_layout.addStretch()

        # -------- 页面2：辅助参数（参照截图1：送料参数 / 复位参数 / 走边框） --------
        assist_page = QWidget()
        assist_layout = QVBoxLayout(assist_page)
        assist_layout.setContentsMargins(0,0,0,0)
        assist_layout.setSpacing(8)

        feed_group = QGroupBox("送料参数")
        feed_layout = QVBoxLayout(feed_group)
        feed_layout.setContentsMargins(10,10,10,10)
        feed_layout.setSpacing(4)

        # 送料前/后延时，逐行送料栈：数值输入，单位写在标签后面
        def _add_delay_row(label_text, default_val="0.000"):
            hl = QHBoxLayout()
            hl.addWidget(QLabel(label_text), 2)
            edit = QLineEdit(default_val)
            edit.setAlignment(Qt.AlignRight)
            hl.addWidget(edit, 1)
            feed_layout.addLayout(hl)

        _add_delay_row("送料前延时(s)")
        _add_delay_row("送料后延时(ms)")

        # 逐行送料 / 结束送料：是/否 选择
        def _add_yes_no_row(label_text):
            hl = QHBoxLayout()
            hl.addWidget(QLabel(label_text), 2)
            combo = QComboBox()
            combo.addItems(["是", "否"])
            combo.setEditable(True)
            combo.setMaxVisibleItems(10)
            combo.lineEdit().setReadOnly(True)
            hl.addWidget(combo, 1)
            feed_layout.addLayout(hl)

        _add_yes_no_row("逐行送料")
        _add_delay_row("逐行送料栈(mm)")
        _add_yes_no_row("结束送料")
        assist_layout.addWidget(feed_group)

        reset_group = QGroupBox("复位参数")
        reset_layout = QVBoxLayout(reset_group)
        reset_layout.setContentsMargins(10,10,10,10)
        reset_layout.setSpacing(4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("复位速度(mm/s)"), 2)
        edit_speed = QLineEdit("20.000")
        edit_speed.setAlignment(Qt.AlignRight)
        hl.addWidget(edit_speed, 1)
        reset_layout.addLayout(hl)

        for axis, default in [("X轴机复位", True),
                              ("Y轴机复位", True),
                              ("Z轴机复位", False),
                              ("U轴机复位", False)]:
            hl = QHBoxLayout()
            cb = QCheckBox(axis)
            cb.setChecked(default)
            hl.addWidget(cb)
            reset_layout.addLayout(hl)

        assist_layout.addWidget(reset_group)

        border_group = QGroupBox("走边框")
        border_layout = QVBoxLayout(border_group)
        border_layout.setContentsMargins(10,10,10,10)
        border_layout.setSpacing(4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("走边框模式"), 2)
        combo_mode = QComboBox()
        combo_mode.addItems(["关光走边框", "出光走边框"])
        combo_mode.setMaxVisibleItems(10)
        combo_mode.setEditable(True)
        combo_mode.lineEdit().setReadOnly(True)
        hl.addWidget(combo_mode, 1)
        border_layout.addLayout(hl)

        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("白边距离(mm)"), 2)
        edit_margin = QLineEdit("0.000")
        edit_margin.setAlignment(Qt.AlignRight)
        hl2.addWidget(edit_margin, 1)
        border_layout.addLayout(hl2)

        assist_layout.addWidget(border_group)
        assist_layout.addStretch()

        # -------- 页面3：其他参数（参照截图2） --------
        other_page = QWidget()
        other_layout = QVBoxLayout(other_page)
        other_layout.setContentsMargins(0,0,0,0)
        other_layout.setSpacing(8)

        other_group = QGroupBox("其他参数")
        other_g_layout = QVBoxLayout(other_group)
        other_g_layout.setContentsMargins(10,10,10,10)
        other_g_layout.setSpacing(4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("阵列加工方式"), 2)
        combo_array = QComboBox()
        combo_array.addItems(["双向走阵列", "单向走阵列"])
        combo_array.setEditable(True)
        combo_array.setMaxVisibleItems(10)
        combo_array.lineEdit().setReadOnly(True)
        hl.addWidget(combo_array, 1)
        other_g_layout.addLayout(hl)

        # 反向间隙 X / Y：供 GCode 反向补偿使用
        for label in ["反向间隙X(mm)", "反向间隙Y(mm)"]:
            hl = QHBoxLayout()
            hl.addWidget(QLabel(label), 2)
            edit = QLineEdit("0.000")
            edit.setAlignment(Qt.AlignRight)
            hl.addWidget(edit, 1)
            other_g_layout.addLayout(hl)
            # 保存控件引用
            if label.startswith("反向间隙X"):
                self.backlash_x_edit = edit
            else:
                self.backlash_y_edit = edit
        
        # 连接输入框值改变信号，自动保存
        if hasattr(self, 'backlash_x_edit'):
            self.backlash_x_edit.editingFinished.connect(self._save_backlash_values)
        if hasattr(self, 'backlash_y_edit'):
            self.backlash_y_edit.editingFinished.connect(self._save_backlash_values)
        
        # 加载已保存的反向间隙值
        self._load_backlash_values()

        hl = QHBoxLayout()
        hl.addWidget(QLabel("吹气方式"), 2)
        combo_blow = QComboBox()
        combo_blow.addItems(["出光吹气", "加工吹气", "一直吹气"])
        combo_blow.setEditable(True)
        combo_blow.setMaxVisibleItems(10)
        combo_blow.lineEdit().setReadOnly(True)
        hl.addWidget(combo_blow, 1)
        other_g_layout.addLayout(hl)
        other_layout.addWidget(other_group)

        back_group = QGroupBox("回位参数")
        back_layout = QVBoxLayout(back_group)
        back_layout.setContentsMargins(10,10,10,10)
        back_layout.setSpacing(4)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("回位位置"), 2)
        combo_back = QComboBox()
        combo_back.addItems(["机械原点", "回位点", "不回位"])
        combo_back.setEditable(True)
        combo_back.setMaxVisibleItems(10)
        combo_back.lineEdit().setReadOnly(True)
        hl.addWidget(combo_back, 1)
        back_layout.addLayout(hl)
        other_layout.addWidget(back_group)

        focus_group = QGroupBox("对焦参数")
        focus_layout = QVBoxLayout(focus_group)
        focus_layout.setContentsMargins(10,10,10,10)
        focus_layout.setSpacing(4)

        for label, val in [("焦距(mm)", "5.000"), ("材料厚度(mm)", "0.000")]:
            hl = QHBoxLayout()
            hl.addWidget(QLabel(label), 2)
            edit = QLineEdit(val)
            edit.setAlignment(Qt.AlignRight)
            hl.addWidget(edit, 1)
            focus_layout.addLayout(hl)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("寻焦模式"), 2)
        combo_focus = QComboBox()
        combo_focus.addItems(["接触式寻焦", "非接触式寻焦"])
        combo_focus.setEditable(True)
        combo_focus.setMaxVisibleItems(10)
        combo_focus.lineEdit().setReadOnly(True)
        hl.addWidget(combo_focus, 1)
        focus_layout.addLayout(hl)
        other_layout.addWidget(focus_group)

        rotate_group = QGroupBox("旋转雕刻")
        rotate_layout = QVBoxLayout(rotate_group)
        rotate_layout.setContentsMargins(10,10,10,10)
        rotate_layout.setSpacing(4)

        # 使能旋转雕刻：是/否 选择，默认否
        hl_enable = QHBoxLayout()
        hl_enable.addWidget(QLabel("使能旋转雕刻"), 2)
        combo_enable_rotate = QComboBox()
        combo_enable_rotate.addItems(["是", "否"])
        combo_enable_rotate.setCurrentIndex(1)  # 默认 否
        combo_enable_rotate.setEditable(True)
        combo_enable_rotate.setMaxVisibleItems(10)
        combo_enable_rotate.lineEdit().setReadOnly(True)
        hl_enable.addWidget(combo_enable_rotate, 1)
        rotate_layout.addLayout(hl_enable)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("周脉冲"), 2)
        edit_peri = QLineEdit("1000.000")
        edit_peri.setAlignment(Qt.AlignRight)
        hl.addWidget(edit_peri, 1)
        rotate_layout.addLayout(hl)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("工作直径(mm)"), 2)
        edit_diam = QLineEdit("20.000")
        edit_diam.setAlignment(Qt.AlignRight)
        hl.addWidget(edit_diam, 1)
        rotate_layout.addLayout(hl)
        # 周脉冲测试（按钮）
        hl = QHBoxLayout()
        hl.addWidget(QLabel("周脉冲测试"), 2)
        btn_pulse = QPushButton("测试")
        hl.addWidget(btn_pulse, 1)
        rotate_layout.addLayout(hl)

        # 旋转速度设置对话框
        def _show_rotate_speed_dialog():
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
            dlg = QDialog(widget.window())
            dlg.setWindowTitle("设置旋转速度")
            lay = QVBoxLayout(dlg)

            row = QHBoxLayout()
            row.addWidget(QLabel("速度(mm/s):"))
            speed_edit = QLineEdit("50.00")
            speed_edit.setAlignment(Qt.AlignRight)
            row.addWidget(speed_edit)
            lay.addLayout(row)

            btn_row = QHBoxLayout()
            btn_ok = QPushButton("OK")
            btn_cancel = QPushButton("Cancel")
            btn_row.addStretch()
            btn_row.addWidget(btn_ok)
            btn_row.addWidget(btn_cancel)
            lay.addLayout(btn_row)

            btn_ok.clicked.connect(dlg.accept)
            btn_cancel.clicked.connect(dlg.reject)

            dlg.exec_()

        btn_pulse.clicked.connect(_show_rotate_speed_dialog)

        other_layout.addWidget(rotate_group)

        # 无线面板
        wireless_group = QGroupBox("无线面板")
        wireless_layout = QVBoxLayout(wireless_group)
        wireless_layout.setContentsMargins(10,10,10,10)
        wireless_layout.setSpacing(4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("快慢速切换使能"), 2)
        combo_ws = QComboBox()
        combo_ws.addItems(["是", "否"])
        combo_ws.setCurrentIndex(1)  # 默认 否
        combo_ws.setEditable(True)
        combo_ws.setMaxVisibleItems(10)
        combo_ws.lineEdit().setReadOnly(True)
        hl.addWidget(combo_ws, 1)
        wireless_layout.addLayout(hl)

        for label, val in [("快速移动(mm/s)", "100.000"), ("慢速移动(mm/s)", "10.000")]:
            hl = QHBoxLayout()
            hl.addWidget(QLabel(label), 2)
            edit = QLineEdit(val)
            edit.setAlignment(Qt.AlignRight)
            hl.addWidget(edit, 1)
            wireless_layout.addLayout(hl)

        other_layout.addWidget(wireless_group)

        # 特殊笔
        special_group = QGroupBox("特殊参数")
        special_layout = QVBoxLayout(special_group)
        special_layout.setContentsMargins(10,10,10,10)
        special_layout.setSpacing(4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("拾笔高度(mm)"), 2)
        edit_pick = QLineEdit("0.000")
        edit_pick.setAlignment(Qt.AlignRight)
        hl.addWidget(edit_pick, 1)
        special_layout.addLayout(hl)

        other_layout.addWidget(special_group)
        other_layout.addStretch()

        # 添加三个页面到栈中
        stack.addWidget(process_page)  # index 0
        stack.addWidget(assist_page)   # index 1
        stack.addWidget(other_page)    # index 2

        # 单选按钮切换栈页面
        def _on_radio_changed():
            if process_radio.isChecked():
                stack.setCurrentIndex(0)
            elif assist_radio.isChecked():
                stack.setCurrentIndex(1)
            elif other_radio.isChecked():
                stack.setCurrentIndex(2)

        process_radio.toggled.connect(_on_radio_changed)
        assist_radio.toggled.connect(_on_radio_changed)
        other_radio.toggled.connect(_on_radio_changed)
        stack.setCurrentIndex(0)

        # 右侧按钮区（与截图风格一致）
        btn_widget=QWidget()
        btn_layout=QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0,0,0,0)
        btn_layout.setSpacing(6)
        btn_open = QPushButton("打开")
        btn_save = QPushButton("保存")
        btn_save.setEnabled(False)  # 参考截图，保存按钮置灰
        btn_read = QPushButton("读参数")
        btn_write = QPushButton("写参数")
        for b in (btn_open, btn_save, btn_read, btn_write):
            btn_layout.addWidget(b)
        btn_layout.addStretch()

        main_layout.addWidget(param_widget,3)
        main_layout.addWidget(btn_widget,1)
        
        # 如果canvas已设置，加载反向间隙值
        if self.canvas and hasattr(self, 'backlash_x_edit'):
            self._load_backlash_values()
=======
        # 参数树
        self.user_param_tree = QTreeWidget()
        self.user_param_tree.setHeaderHidden(True)
        self.user_param_tree.setColumnCount(2)
        # 调整列宽
        self.user_param_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.user_param_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.user_param_tree.setAlternatingRowColors(True)
        self.user_param_tree.setItemsExpandable(True)
        self.user_param_tree.setRootIsDecorated(True)
        # 设置自定义委托以增加行高
        self.user_param_tree.setItemDelegate(UserParamDelegate(self.user_param_tree))
        self.user_param_tree.itemClicked.connect(self.on_user_param_tree_item_clicked)
        
        param_layout.addWidget(self.user_param_tree)

        # 默认选中第一个并刷新列表
        self.radio_process.setChecked(True)
        self.user_param_group.buttonClicked.connect(self.update_user_param_tree)
        
        # 初始化数据
        self.init_user_params_data()
        self.update_user_param_tree()

        # 右侧按钮区域
        btn_widget = QWidget()
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)
        
        btn_open = QPushButton("打开")
        btn_save = QPushButton("保存")
        btn_read = QPushButton("读参数")
        btn_write = QPushButton("写参数")
        
        btn_open.clicked.connect(self.on_open_params_clicked)
        btn_save.clicked.connect(self.on_save_params_clicked)
        btn_read.clicked.connect(self.on_read_params_clicked)
        btn_write.clicked.connect(self.on_write_params_clicked)
        
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_read)
        btn_layout.addWidget(btn_write)
        btn_layout.addStretch()

        main_layout.addWidget(param_widget, 3)
        main_layout.addWidget(btn_widget, 1)
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)

        return widget

    def init_user_params_data(self):
        """初始化用户参数数据"""
        self.user_params = {
            0: [ # 加工参数
                ("切割参数", [
                    ("空程速度(mm/s)", "200.000"),
                    ("空程加速度(mm/s2)", "3000.000"),
                    ("拐弯速度(mm/s)", "20.000"),
                    ("拐弯加速度(mm/s2)", "400.000"),
                    ("切割加速度(mm/s2)", "3000.000"),
                    ("空走延时(ms)", "0.000"),
                    ("切割加速倍率(0%-200%)", "100"),
                    ("空程加速倍率(0%-200%)", "100"),
                    ("拐弯系数(0%-200%)", "100"),
                    ("一键设置", ""), # Special case
                ]),
                ("扫描参数", [
                    ("x轴起始速度(mm/s)", "10.000"),
                    ("y轴起始速度(mm/s)", "10.000"),
                    ("x轴加速度(mm/s2)", "10000.000"),
                    ("y轴加速度(mm/s2)", "3000.000"),
                    ("扫描换行速度(mm/s)", "100.000"),
                    ("扫描模式", "一般模式"),
                    ("光斑大小(50~99%)(mm)", "80.000"),
                    ("扫描系数", "100"),
                ])
            ],
            1: [ # 辅助参数
                ("送料参数", [
                    ("送料前延时(s)", "0.000"),
                    ("送料后延时(ms)", "0"),
                    ("逐行送料", "否"),
                    ("逐行送料补偿(mm)", "0.000"),
                    ("结束送料", "是"),
                ]),
                ("复位参数", [
                    ("复位速度(mm/s)", "20.000"),
                    ("X轴开机复位", "是"),
                    ("Y轴开机复位", "是"),
                    ("Z轴开机复位", "否"),
                    ("U轴开机复位", "否"),
                ]),
                ("走边框", [
                    ("走边框模式", "关光走边框"),
                    ("白边距离(mm)", "0.000"),
                ])
            ],
            2: [ # 其他参数
                ("其他参数", [
                    ("阵列加工方式", "双向走阵列"),
                    ("反向间隙X(mm)", "0.000"),
                    ("反向间隙Y(mm)", "0.000"),
                    ("吹气方式", "出光吹气"),
                ]),
                ("回位参数", [
                    ("回位位置", "定位点"),
                ]),
                ("对焦参数", [
                     ("焦距(mm)", "5.000"),
                     ("材料厚度(mm)", "0.000"),
                     ("寻焦模式", "接触式寻焦"),
                ]),
                ("旋转雕刻", [
                    ("使能旋转雕刻", "否"),
                    ("周脉冲", "1000.000"),
                    ("工件直径(mm)", "20.000"),
                    ("周脉冲测试", ""),
                ]),
                ("无线面板", [
                    ("快慢速切换使能", "否"),
                    ("快速移动(mm/s)", "100.000"),
                    ("慢速移动(mm/s)", "10.000"),
                ]),
                ("特殊参数", [
                    ("抬笔高度(mm)", "0.000"),
                    ("落笔高度(mm)", "0.000"),
                    ("Z轴升降模式", "电机模式"),
                    ("吸附开延时(ms)", "0"),
                    ("吸附关延时(ms)", "0"),
                ])
            ]
        }

    def update_user_param_tree(self):
        """更新参数树显示"""
        self.user_param_tree.clear()
        
        idx = self.user_param_group.checkedId()
        if idx not in self.user_params:
            return
            
        categories = self.user_params[idx]
        for cat_name, items in categories:
            cat_item = QTreeWidgetItem(self.user_param_tree)
            cat_item.setText(0, cat_name)
            # 设置第一列跨越所有列（像标题一样）？不，截图里在右边可能没有东西
            # 但用户截图里，类别是有一行的。
            # 我们可以设置背景色来区分
            cat_item.setExpanded(True) # 默认展开
            
            for key, value in items:
                child = QTreeWidgetItem(cat_item)
                child.setText(0, key)
                
                # 特殊处理按钮类型的项
                if key == "一键设置":
                     # 创建一个按钮 (...)
                     btn = QPushButton("...")
                     btn.setFixedSize(30, 20) # 小按钮
                     btn.clicked.connect(self.on_one_click_setup)
                     
                     # 放置在第二列
                     self.user_param_tree.setItemWidget(child, 1, btn)
                     
                elif key == "周脉冲测试":
                     # 创建一个按钮
                     btn = QPushButton("...")
                     btn.setFixedSize(30, 20) # 小按钮
                     btn.clicked.connect(self.on_pulse_test_setup)
                     
                     # 放置在第二列
                     self.user_param_tree.setItemWidget(child, 1, btn)
                     
                else:
                    child.setText(1, value)
                    child.setFlags(child.flags() | Qt.ItemIsEditable)

    def on_user_param_tree_item_clicked(self, item, column):
        """用户参数树单击事件处理"""
        # 获取第一列的文本作为参数名
        param_name = item.text(0)
        # 如果是下拉框类型的参数，单击即进入编辑状态（显示下拉框）
        if param_name in PARAM_OPTIONS:
            self.user_param_tree.editItem(item, 1)

    def on_one_click_setup(self):
        """打开一键设置对话框"""
        dialog = OneClickSetupDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # 获取选中的模式，这里暂不执行具体逻辑，因为用户只要求界面
            # mode = dialog.combo.currentText()
            pass

    def on_pulse_test_setup(self):
        """打开周脉冲测试设置对话框"""
        dialog = RotationSpeedDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # 同样暂不执行逻辑
            # speed = dialog.speed_input.text()
            pass

    def on_open_params_clicked(self):
        """打开参数文件"""
        filename, _ = QFileDialog.getOpenFileName(self, "打开参数", "", "INI Files (*.ini)")
        if not filename:
             return
             
        try:
             config = configparser.ConfigParser()
             config.read(filename, encoding='utf-8')
             
             # 更新 self.user_params
             for group_idx, categories in self.user_params.items():
                 for cat_idx, (cat_name, items) in enumerate(categories):
                     if cat_name in config:
                         section = config[cat_name]
                         new_items = []
                         for key, value in items:
                              if key in section:
                                  new_items.append((key, section[key]))
                              else:
                                  new_items.append((key, value))
                         # Update the category items in place
                         categories[cat_idx] = (cat_name, new_items)
             
             self.update_user_param_tree()
             QMessageBox.information(self, "提示", "参数加载成功")
             
        except Exception as e:
             QMessageBox.warning(self, "错误", f"加载参数失败: {str(e)}")

    def on_save_params_clicked(self):
        """保存参数文件"""
        filename, _ = QFileDialog.getSaveFileName(self, "保存参数", "params.ini", "INI Files (*.ini)")
        if not filename:
             return
             
        try:
             config = configparser.ConfigParser()
             
             for group_idx, categories in self.user_params.items():
                 for cat_name, items in categories:
                     config[cat_name] = {}
                     for key, value in items:
                         # Skip buttons
                         if key in ["一键设置", "周脉冲测试"]:
                             continue
                         config[cat_name][key] = str(value)
                         
             with open(filename, 'w', encoding='utf-8') as f:
                 config.write(f)
                 
             QMessageBox.information(self, "提示", "参数保存成功")
             
        except Exception as e:
             QMessageBox.warning(self, "错误", f"保存参数失败: {str(e)}")

    def on_read_params_clicked(self):
        """读取机器参数"""
        if not self.check_connection_and_alert():
             return

        # 模拟读取参数
        QMessageBox.information(self, "提示", "正在从机器读取参数...")
        
        # 模拟：更新一些值
        # 假设读取到了 工件直径=50
        try:
             # 查找 "其他参数" -> "旋转雕刻" -> "工件直径(mm)"
             # loop to find
             found = False
             categories = self.user_params[2] # Other params
             for cat_idx, (cat_name, items) in enumerate(categories):
                 if cat_name == "旋转雕刻":
                     new_items = []
                     for key, value in items:
                         if key == "工件直径(mm)":
                             new_items.append((key, "50.000")) # Simulated read value
                             found = True
                         else:
                             new_items.append((key, value))
                     categories[cat_idx] = (cat_name, new_items)
                     break
            
             if found:
                 self.update_user_param_tree()
                 QMessageBox.information(self, "提示", "参数读取成功 (模拟: 工件直径已更新为 50.000)")
             else:
                 QMessageBox.information(self, "提示", "参数读取成功")

        except Exception as e:
             QMessageBox.warning(self, "错误", f"读取参数失败: {str(e)}")

    def on_write_params_clicked(self):
        """写入机器参数"""
        if not self.check_connection_and_alert():
             return

        # 模拟写入
        QMessageBox.information(self, "提示", "正在写入参数到机器...")
        QMessageBox.information(self, "提示", "参数写入成功 (模拟)")

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
        self.coord_x_label = QLabel("X=?")
        self.coord_y_label = QLabel("Y=?")
        self.coord_z_label = QLabel("Z=?")
        coord_display_layout.addWidget(self.coord_x_label)
        coord_display_layout.addWidget(self.coord_y_label)
        coord_display_layout.addWidget(self.coord_z_label)
        coord_display_layout.addStretch()
        self.btn_read_pos = QPushButton("读当前位置")
        self.btn_read_pos.clicked.connect(self.on_test_read_position)
        coord_display_layout.addWidget(self.btn_read_pos)
        coord_layout.addLayout(coord_display_layout)

        target_layout=QHBoxLayout()
        self.x_target = QLineEdit("0.000")
        self.y_target = QLineEdit("0.000")
        target_layout.addWidget(self.x_target)
        target_layout.addWidget(self.y_target)
        self.btn_move_to_target = QPushButton("移动到目标位置")
        self.btn_move_to_target.clicked.connect(self.on_test_move_to_target)
        target_layout.addWidget(self.btn_move_to_target)
        coord_layout.addLayout(target_layout)

        time_layout=QHBoxLayout()
        self.prev_time_label = QLabel("0时:0分:0秒:0毫秒")
        time_layout.addWidget(self.prev_time_label)
        time_layout.addStretch()
        self.btn_prev_time = QPushButton("前次加工时间")
        self.btn_prev_time.clicked.connect(self.on_test_prev_time)
        time_layout.addWidget(self.btn_prev_time)
        coord_layout.addLayout(time_layout)
        layout.addWidget(coord_group)

        axis_group=QGroupBox("单轴移动")
        axis_layout=QVBoxLayout(axis_group)
        axis_layout.setContentsMargins(10,10,10,10)
        axis_layout.setSpacing(6)

        xy_layout=QHBoxLayout()
        xy_button_layout=QVBoxLayout()
        self.btn_y_plus = QPushButton("Y+")
        self.btn_y_plus.clicked.connect(lambda: self.on_axis_move('Y', 1))
        xy_button_layout.addWidget(self.btn_y_plus)
        xy_mid_layout=QHBoxLayout()
        self.btn_x_minus = QPushButton("X-")
        self.btn_origin_xy = QPushButton("原点")
        self.btn_x_plus = QPushButton("X+")
        self.btn_x_minus.clicked.connect(lambda: self.on_axis_move('X', -1))
        self.btn_origin_xy.clicked.connect(self.on_origin_xy)
        self.btn_x_plus.clicked.connect(lambda: self.on_axis_move('X', 1))
        xy_mid_layout.addWidget(self.btn_x_minus)
        xy_mid_layout.addWidget(self.btn_origin_xy)
        xy_mid_layout.addWidget(self.btn_x_plus)
        xy_button_layout.addLayout(xy_mid_layout)
        self.btn_y_minus = QPushButton("Y-")
        self.btn_y_minus.clicked.connect(lambda: self.on_axis_move('Y', -1))
        xy_button_layout.addWidget(self.btn_y_minus)
        xy_layout.addLayout(xy_button_layout)

        param_layout=QVBoxLayout()
        param_layout.addWidget(QLabel("偏移(mm):"))
        self.offset_edit=QLineEdit("10.000")
        param_layout.addWidget(self.offset_edit)
        param_layout.addWidget(QLabel("速度(mm/s):"))
        self.speed_edit=QLineEdit("50")
        param_layout.addWidget(self.speed_edit)
        param_layout.addWidget(QLabel("激光功率(%):"))
        self.power_edit=QLineEdit("0")
        param_layout.addWidget(self.power_edit)
        xy_layout.addLayout(param_layout)
        axis_layout.addLayout(xy_layout)

        lower_layout=QHBoxLayout()
        zu_button_layout=QVBoxLayout()
        self.btn_z_plus = QPushButton("Z+")
        self.btn_z_plus.clicked.connect(lambda: self.on_axis_move('Z', 1))
        zu_button_layout.addWidget(self.btn_z_plus)
        zu_mid_layout=QHBoxLayout()
        self.btn_origin_z = QPushButton("原点")
        self.btn_z_minus = QPushButton("Z-")
        self.btn_origin_z.clicked.connect(self.on_origin_z)
        self.btn_z_minus.clicked.connect(lambda: self.on_axis_move('Z', -1))
        zu_mid_layout.addWidget(self.btn_origin_z)
        zu_mid_layout.addWidget(self.btn_z_minus)
        zu_button_layout.addLayout(zu_mid_layout)
        self.btn_u_plus = QPushButton("U+")
        self.btn_u_plus.clicked.connect(lambda: self.on_axis_move('U', 1))
        zu_button_layout.addWidget(self.btn_u_plus)
        zu_mid2_layout=QHBoxLayout()
        self.btn_origin_u = QPushButton("原点")
        self.btn_u_minus = QPushButton("U-")
        self.btn_origin_u.clicked.connect(self.on_origin_u)
        self.btn_u_minus.clicked.connect(lambda: self.on_axis_move('U', -1))
        zu_mid2_layout.addWidget(self.btn_origin_u)
        zu_mid2_layout.addWidget(self.btn_u_minus)
        zu_button_layout.addLayout(zu_mid2_layout)
        lower_layout.addLayout(zu_button_layout)

        check_layout=QVBoxLayout()
        self.chk_continuous = QCheckBox("连续运动")
        self.chk_from_origin = QCheckBox("从原点移动")
        self.chk_laser_on = QCheckBox("是否出光")
        check_layout.addWidget(self.chk_continuous)
        check_layout.addWidget(self.chk_from_origin)
        check_layout.addWidget(self.chk_laser_on)
        check_layout.addStretch()
        self.btn_focus = QPushButton("寻焦")
        self.btn_focus.clicked.connect(self.on_focus)
        self.btn_locate = QPushButton("定位")
        self.btn_locate.clicked.connect(self.on_locate)
        check_layout.addWidget(self.btn_focus)
        check_layout.addWidget(self.btn_locate)
        
        # 新增调试按钮 - 已移除，功能合并至主界面工具箱
        # btn_debug = QPushButton("高级调试/命令模式")
        # btn_debug.clicked.connect(self.open_debug_console)
        # btn_debug.setStyleSheet("background-color: #e1f5fe; border: 1px solid #039be5; color: #0277bd; font-weight: bold;")
        # check_layout.addWidget(btn_debug)

        lower_layout.addLayout(check_layout)
        axis_layout.addLayout(lower_layout)
        layout.addWidget(axis_group)

        return widget

    def open_debug_console(self):
        """打开高级调试控制台"""
        dialog = CommandDebugDialog(self.communicator, self)
        dialog.exec_()

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
        # 使用QDoubleSpinBox以支持0.01mm精度并保持可访问性
        self.import_center_x_spin = QDoubleSpinBox()
        self.import_center_x_spin.setRange(-10000.0, 10000.0)
        self.import_center_x_spin.setDecimals(2)
        self.import_center_x_spin.setSingleStep(0.01)
        self.import_center_x_spin.setFixedWidth(200)
        mm_label=QLabel("mm")
        hor_layout.addWidget(hor_label)
        hor_layout.addWidget(self.import_center_x_spin)
        hor_layout.addWidget(mm_label)
        hor_layout.addStretch(0)
        pos_layout.addLayout(hor_layout)

        #垂直行
        ver_layout=QHBoxLayout()
        ver_layout.setSpacing(5)
        ver_layout.addWidget(QLabel("垂直(V)"))
        self.import_center_y_spin = QDoubleSpinBox()
        self.import_center_y_spin.setRange(-10000.0, 10000.0)
        self.import_center_y_spin.setDecimals(2)
        self.import_center_y_spin.setSingleStep(0.01)
        self.import_center_y_spin.setFixedWidth(200)
        ver_mm_label=QLabel("mm")
        ver_layout.addWidget(self.import_center_y_spin)
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

    def get_import_center_mm(self):
        """返回用户在位置面板中设置的导入中心（以毫米为单位）。

        如果面板控件不存在或出错，返回 None。
        """
        try:
            return float(self.import_center_x_spin.value()), float(self.import_center_y_spin.value())
        except Exception:
            return None


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