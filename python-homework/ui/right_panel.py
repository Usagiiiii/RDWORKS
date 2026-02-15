#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧属性面板
"""
import os
import re
import time
import tempfile
import configparser

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                             QRadioButton, QGridLayout, QStackedWidget, QHeaderView, QSizePolicy, QFileDialog, QMessageBox, QDialog, QButtonGroup,
                             QStyledItemDelegate, QStyle, QTreeWidget, QTreeWidgetItem, QDialogButtonBox, QFrame)
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView, QListView
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter, QPen, QDoubleValidator
from utils.tool_utils import get_resource_path
from .device_config_dialog import DeviceConfigDialog
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
        self.min_power = 0.0
        self.max_power = 100.0
        self.scan_mode = "水平单向"
        self.scan_interval = 0.1
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
        self.min_power_2 = 0.0
        self.max_power_2 = 100.0


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
    USER_PARAMS_PERSIST_FILENAME = "user_params.ini"
    USER_PARAMS_REMOTE_FILENAME = "user_params.ini"
    # 按顺序尝试，直到返回可解析 INI 文本
    USER_PARAMS_READ_COMMANDS = [
        "+CPRM:READ,{filename}",
        "+CREG:16,0,{filename}",
        "+CREG:16,0",
    ]
    # 上传后尝试通知下位机应用参数（命令因固件而异，按顺序兜底）
    USER_PARAMS_APPLY_COMMANDS = [
        "+CPRM:LOAD,{filename}",
        "+CPRM:APPLY,{filename}",
        "+CREG:12,1,{filename}",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None # 持有 Canvas 引用
        self.layer_data = {} # Key: hex color string, Value: LayerParams
        self.layer_order = [] # 存储图层顺序（hex color string list）
        self.user_params_file_path = self._get_user_params_persist_path()
        self.user_params_last_open_path = self.user_params_file_path
        
        self.communicator = LaserCommunicator()
        self.communicator.log_message.connect(self.on_comm_log)
        self.communicator.error_occurred.connect(self.on_comm_error)
        self.communicator.sending_finished.connect(self.on_sending_finished)
        
        self.current_layer_color = None # 当前选中的图层颜色（用于解决焦点丢失时的参数保存问题）
        self._process_defaults = {
            'position_mode': '当前位置',
            'path_optimize': True,
            'output_selected': False,
            'selected_position': False,
        }
        self._output_defaults = {
            'cycle_enabled': False,
            'cycle_count': 0,
            'cycle_order': '先切割后送料',
            'feed_length': 500.0,
            'feed_source': '手动输入',
            'feed_comp': 0.0,
            'pause_after_feed': False,
            'split_enabled': False,
            'panel_height': 500.0,
            'force_split': False,
            'angle_comp': 0.0,
            'end_feed': False,
            'comp_diameter': 1.0,
            'joint_comp': False,
            'dual_head_priority': False,
        }

        self._debug_process_start_ts = None
        self._debug_last_process_duration_ms = None
        self._process_paused = False
        self._last_remote_job_name = ""
        self._manual_stop_requested = False

        self.init_ui()

    def set_canvas(self, canvas):
        """设置画布引用并连接信号"""
        self.canvas = canvas
        self.canvas.scene.changed.connect(self.update_layer_list)
        self.canvas.scene.selectionChanged.connect(self.on_selection_changed)
        self.update_layer_list(force=True)
        self._load_process_settings_from_canvas()
        self._load_output_settings_from_canvas()
        QTimer.singleShot(100, self._load_backlash_values)

    def _load_backlash_values(self):
        """加载反向间隙X和Y的值"""
        if not self.canvas:
            return

        backlash_x = 0.0
        backlash_y = 0.0
        try:
            # 优先从 canvas.user_params 读取，回退到 optimize_settings
            if hasattr(self.canvas, 'user_params') and isinstance(self.canvas.user_params, dict):
                params = self.canvas.user_params
                backlash_x = float(params.get('backlash_x', 0.0) or 0.0)
                backlash_y = float(params.get('backlash_y', 0.0) or 0.0)
            elif hasattr(self.canvas, 'optimize_settings') and isinstance(self.canvas.optimize_settings, dict):
                config = self.canvas.optimize_settings.get('user_backlash', {}) or {}
                backlash_x = float(config.get('x', 0.0) or 0.0)
                backlash_y = float(config.get('y', 0.0) or 0.0)
        except Exception as e:
            print(f"加载反向间隙值失败: {e}")

        # 兼容旧版输入框
        if hasattr(self, 'backlash_x_edit'):
            self.backlash_x_edit.setText(f"{backlash_x:.3f}")
        if hasattr(self, 'backlash_y_edit'):
            self.backlash_y_edit.setText(f"{backlash_y:.3f}")

        # 同步到当前用户参数树数据（用于“切割反向间隙”）
        changed = False
        changed |= self._set_user_param_value(2, "其他参数", "反向间隙X(mm)", f"{backlash_x:.3f}")
        changed |= self._set_user_param_value(2, "其他参数", "反向间隙Y(mm)", f"{backlash_y:.3f}")
        if changed and hasattr(self, 'user_param_tree'):
            self.update_user_param_tree()

    def _save_backlash_values(self):
        """保存反向间隙X和Y的值"""
        if not self.canvas:
            return

        try:
            backlash_x = 0.0
            backlash_y = 0.0

            # 优先读旧版输入框，回退到用户参数树
            if hasattr(self, 'backlash_x_edit') and hasattr(self, 'backlash_y_edit'):
                try:
                    backlash_x = float(self.backlash_x_edit.text().strip() or "0")
                except ValueError:
                    backlash_x = 0.0

                try:
                    backlash_y = float(self.backlash_y_edit.text().strip() or "0")
                except ValueError:
                    backlash_y = 0.0
            else:
                try:
                    backlash_x = float(self._get_user_param_value(2, "其他参数", "反向间隙X(mm)", "0").strip() or "0")
                except ValueError:
                    backlash_x = 0.0
                try:
                    backlash_y = float(self._get_user_param_value(2, "其他参数", "反向间隙Y(mm)", "0").strip() or "0")
                except ValueError:
                    backlash_y = 0.0

            # 保存到 canvas.optimize_settings
            if not hasattr(self.canvas, 'optimize_settings') or self.canvas.optimize_settings is None:
                self.canvas.optimize_settings = {}

            self.canvas.optimize_settings['user_backlash'] = {
                'x': backlash_x,
                'y': backlash_y
            }

            # 同步到 canvas.user_params，兼容旧读取路径
            if not hasattr(self.canvas, 'user_params') or not isinstance(self.canvas.user_params, dict):
                self.canvas.user_params = {}
            self.canvas.user_params['backlash_x'] = backlash_x
            self.canvas.user_params['backlash_y'] = backlash_y
        except Exception as e:
            print(f"保存反向间隙值失败: {e}")

    def _get_user_param_value(self, group_idx, category_name, key_name, default=""):
        if not hasattr(self, 'user_params'):
            return default
        categories = self.user_params.get(group_idx, [])
        for cat_name, items in categories:
            if cat_name != category_name:
                continue
            for key, value in items:
                if key == key_name:
                    return str(value)
        return default

    def _set_user_param_value(self, group_idx, category_name, key_name, value):
        if not hasattr(self, 'user_params'):
            return False
        categories = self.user_params.get(group_idx)
        if categories is None:
            return False

        new_value = str(value)
        for cat_idx, (cat_name, items) in enumerate(categories):
            if cat_name != category_name:
                continue
            for item_idx, (key, old_value) in enumerate(items):
                if key != key_name:
                    continue
                if str(old_value) == new_value:
                    return False
                new_items = list(items)
                new_items[item_idx] = (key, new_value)
                categories[cat_idx] = (cat_name, new_items)
                return True
        return False

    def _get_user_params_persist_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(base_dir, "..", self.USER_PARAMS_PERSIST_FILENAME))

    def _build_user_params_config(self):
        cfg = configparser.ConfigParser(interpolation=None)
        for _, categories in (self.user_params or {}).items():
            for cat_name, items in categories:
                if not cfg.has_section(cat_name):
                    cfg.add_section(cat_name)
                for key, value in items:
                    if key in ("一键设置", "周脉冲测试"):
                        continue
                    cfg.set(cat_name, key, str(value))
        return cfg

    def _apply_user_params_config(self, cfg):
        if not hasattr(self, 'user_params'):
            return
        for _, categories in self.user_params.items():
            for cat_idx, (cat_name, items) in enumerate(categories):
                if not cfg.has_section(cat_name):
                    continue
                section = cfg[cat_name]
                new_items = []
                for key, value in items:
                    if key in ("一键设置", "周脉冲测试"):
                        new_items.append((key, value))
                        continue
                    new_items.append((key, section.get(key, str(value))))
                categories[cat_idx] = (cat_name, new_items)

    def _save_user_params_to_ini(self, filename):
        cfg = self._build_user_params_config()
        with open(filename, "w", encoding="utf-8") as f:
            cfg.write(f)

    def _load_user_params_from_ini(self, filename):
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(filename, encoding="utf-8")
        if not cfg.sections():
            raise ValueError("INI文件为空或格式不正确")
        self._apply_user_params_config(cfg)
        self.update_user_param_tree()
        self._save_backlash_values()

    def _persist_user_params_silent(self):
        try:
            self._save_user_params_to_ini(self.user_params_file_path)
        except Exception:
            pass

    def _looks_like_ini_text(self, text):
        if not text:
            return False
        lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
        if not lines:
            return False
        has_section = any(ln.startswith("[") and ln.endswith("]") for ln in lines)
        has_kv = any("=" in ln for ln in lines)
        return has_section and has_kv

    def _extract_ini_text_from_response(self, text):
        raw = str(text or "")
        if not raw.strip():
            return ""

        if self._looks_like_ini_text(raw):
            return raw

        up = raw.upper()
        begin_tag = "INI_BEGIN"
        end_tag = "INI_END"
        b = up.find(begin_tag)
        e = up.find(end_tag)
        if b >= 0 and e > b:
            block = raw[b + len(begin_tag):e]
            if self._looks_like_ini_text(block):
                return block

        # 兜底：从混合响应中提取 section/key=value 行
        ini_lines = []
        for ln in raw.splitlines():
            s = ln.strip()
            if not s:
                continue
            if (s.startswith("[") and s.endswith("]")) or ("=" in s):
                ini_lines.append(s)
        candidate = "\n".join(ini_lines)
        if self._looks_like_ini_text(candidate):
            return candidate
        return ""

    def _parse_machine_ini_text(self, text):
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read_string(text)
        if not cfg.sections():
            raise ValueError("下位机返回内容不是有效INI")
        self._apply_user_params_config(cfg)
        self.update_user_param_tree()
        self._save_backlash_values()

    def _remote_user_params_filename(self):
        if self.user_params_last_open_path:
            base = os.path.basename(self.user_params_last_open_path).strip()
            if base:
                return base
        return self.USER_PARAMS_REMOTE_FILENAME
    def sync_user_backlash_to_canvas(self):
        self._save_backlash_values()

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
        self.tabs.addTab(self._wrap_tab(self.create_test_tab()), "调试")
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
        self.proc_combo_pos = QComboBox()
        self.proc_combo_pos.setView(QListView())
        self.proc_combo_pos.setMaxVisibleItems(10)
        self.proc_combo_pos.setEditable(True)
        self.proc_combo_pos.lineEdit().setReadOnly(True)
        self.proc_combo_pos.addItems(["当前位置", "原定位点", "机械原点", "绝对坐标"])
        self.proc_combo_pos.setSizePolicy(_QSizePolicy.Expanding, _QSizePolicy.Fixed)
        self.proc_combo_pos.setMinimumHeight(24)
        self.proc_combo_pos.currentIndexChanged.connect(self._on_process_settings_changed)

        row3_layout.addWidget(lbl_pos)
        row3_layout.addWidget(self.proc_combo_pos)
        process_layout.addLayout(row3_layout)

        # Row 4: Checkboxes and Border buttons
        row4_layout = QHBoxLayout()
        
        # Left side: Checkboxes
        checks_layout = QVBoxLayout()
        checks_layout.setSpacing(2)
        
        self.proc_chk_optimize = QCheckBox("路径优化")
        self.proc_chk_optimize.setChecked(True)
        self.proc_chk_output_selected = QCheckBox("输出选中图形")
        self.proc_chk_selected_pos = QCheckBox("选中图形定位")
        self.proc_chk_selected_pos.setEnabled(False)
        self.proc_chk_selected_pos.setStyleSheet("color: gray;")

        self.proc_chk_optimize.toggled.connect(self._on_process_settings_changed)
        self.proc_chk_selected_pos.toggled.connect(self._on_process_settings_changed)
        self.proc_chk_output_selected.toggled.connect(self._on_output_selected_changed)

        checks_layout.addWidget(self.proc_chk_optimize)
        checks_layout.addWidget(self.proc_chk_output_selected)
        checks_layout.addWidget(self.proc_chk_selected_pos)
        
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

        self._apply_process_settings_to_ui(dict(self._process_defaults))

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

    def _normalize_process_settings(self, raw):
        base = dict(self._process_defaults)
        if isinstance(raw, dict):
            base.update(raw)

        valid_modes = {"当前位置", "原定位点", "机械原点", "绝对坐标"}
        try:
            base['position_mode'] = str(base.get('position_mode', '当前位置'))
            if base['position_mode'] not in valid_modes:
                base['position_mode'] = '当前位置'

            base['path_optimize'] = bool(base.get('path_optimize', True))
            base['output_selected'] = bool(base.get('output_selected', False))
            base['selected_position'] = bool(base.get('selected_position', False))
            if not base['output_selected']:
                base['selected_position'] = False
        except Exception:
            return dict(self._process_defaults)
        return base

    def _collect_process_settings_from_ui(self):
        if not hasattr(self, 'proc_combo_pos'):
            return dict(self._process_defaults)
        settings = {
            'position_mode': self.proc_combo_pos.currentText(),
            'path_optimize': self.proc_chk_optimize.isChecked(),
            'output_selected': self.proc_chk_output_selected.isChecked(),
            'selected_position': self.proc_chk_selected_pos.isChecked(),
        }
        return self._normalize_process_settings(settings)

    def _refresh_process_option_state(self):
        if not hasattr(self, 'proc_chk_selected_pos'):
            return
        enabled = bool(self.proc_chk_output_selected.isChecked())
        self.proc_chk_selected_pos.setEnabled(enabled)
        self.proc_chk_selected_pos.setStyleSheet("color: black;" if enabled else "color: gray;")
        if not enabled and self.proc_chk_selected_pos.isChecked():
            self.proc_chk_selected_pos.blockSignals(True)
            self.proc_chk_selected_pos.setChecked(False)
            self.proc_chk_selected_pos.blockSignals(False)

    def _apply_process_settings_to_ui(self, settings):
        if not hasattr(self, 'proc_combo_pos'):
            return
        cfg = self._normalize_process_settings(settings)
        controls = [
            self.proc_combo_pos,
            self.proc_chk_optimize,
            self.proc_chk_output_selected,
            self.proc_chk_selected_pos,
        ]
        for w in controls:
            w.blockSignals(True)
        try:
            self.proc_combo_pos.setCurrentText(cfg['position_mode'])
            self.proc_chk_optimize.setChecked(cfg['path_optimize'])
            self.proc_chk_output_selected.setChecked(cfg['output_selected'])
            self.proc_chk_selected_pos.setChecked(cfg['selected_position'])
        finally:
            for w in controls:
                w.blockSignals(False)
        self._refresh_process_option_state()

    def _save_process_settings_to_canvas(self):
        if not self.canvas:
            return
        try:
            if not hasattr(self.canvas, 'optimize_settings') or self.canvas.optimize_settings is None:
                self.canvas.optimize_settings = {}
            self.canvas.optimize_settings['process_panel'] = self._collect_process_settings_from_ui()
        except Exception:
            pass

    def _load_process_settings_from_canvas(self):
        if not hasattr(self, 'proc_combo_pos'):
            return
        try:
            raw = {}
            if self.canvas and hasattr(self.canvas, 'optimize_settings') and isinstance(self.canvas.optimize_settings, dict):
                raw = self.canvas.optimize_settings.get('process_panel', {}) or {}
            self._apply_process_settings_to_ui(raw)
        except Exception:
            self._apply_process_settings_to_ui(dict(self._process_defaults))

    def _on_process_settings_changed(self, *_args):
        self._save_process_settings_to_canvas()

    def _on_output_selected_changed(self, checked):
        self._refresh_process_option_state()
        self._on_process_settings_changed()

    def _normalize_output_settings(self, raw):
        """规范化输出页参数，保证类型和枚举值稳定。"""
        base = dict(self._output_defaults)
        if not isinstance(raw, dict):
            return base

        base.update(raw)

        cycle_orders = {"先切割后送料", "先送料后切割", "往返送料"}
        feed_sources = {"手动输入", "Y向幅面", "图形高度", "最小送料长度"}

        try:
            base['cycle_enabled'] = bool(base.get('cycle_enabled', False))
            base['cycle_count'] = max(0, int(base.get('cycle_count', 0)))
            base['cycle_order'] = str(base.get('cycle_order', '先切割后送料'))
            if base['cycle_order'] not in cycle_orders:
                base['cycle_order'] = '先切割后送料'

            base['feed_length'] = max(0.0, float(base.get('feed_length', 500.0)))
            base['feed_source'] = str(base.get('feed_source', '手动输入'))
            if base['feed_source'] not in feed_sources:
                base['feed_source'] = '手动输入'
            base['feed_comp'] = float(base.get('feed_comp', 0.0))
            base['pause_after_feed'] = bool(base.get('pause_after_feed', False))

            base['split_enabled'] = bool(base.get('split_enabled', False))
            base['panel_height'] = max(1e-6, float(base.get('panel_height', 500.0)))
            base['force_split'] = bool(base.get('force_split', False))
            base['angle_comp'] = float(base.get('angle_comp', 0.0))
            base['end_feed'] = bool(base.get('end_feed', False))
            base['comp_diameter'] = max(0.0, float(base.get('comp_diameter', 1.0)))
            base['joint_comp'] = bool(base.get('joint_comp', False))

            base['dual_head_priority'] = bool(base.get('dual_head_priority', False))
        except Exception:
            return dict(self._output_defaults)

        return base

    def _collect_output_settings_from_ui(self):
        """从输出页控件读取当前参数。"""
        if not hasattr(self, 'output_cycle_check'):
            return dict(self._output_defaults)

        settings = {
            'cycle_enabled': self.output_cycle_check.isChecked(),
            'cycle_count': self.output_cycle_count.value(),
            'cycle_order': self.output_cycle_order.currentText(),
            'feed_length': self.output_feed_length.value(),
            'feed_source': self.output_feed_source.currentText(),
            'feed_comp': self.output_feed_comp.value(),
            'pause_after_feed': self.output_pause_after_feed.isChecked(),
            'split_enabled': self.output_split_check.isChecked(),
            'panel_height': self.output_panel_height.value(),
            'force_split': self.output_force_split.isChecked(),
            'angle_comp': self.output_angle_comp.value(),
            'end_feed': self.output_end_feed.isChecked(),
            'comp_diameter': self.output_comp_diameter.value(),
            'joint_comp': self.output_joint_comp.isChecked(),
            'dual_head_priority': self.output_dual_head_priority.isChecked(),
        }
        return self._normalize_output_settings(settings)

    def _apply_output_settings_to_ui(self, settings):
        """将输出页参数回填到界面控件。"""
        if not hasattr(self, 'output_cycle_check'):
            return

        cfg = self._normalize_output_settings(settings)
        controls = [
            self.output_cycle_check,
            self.output_cycle_count,
            self.output_cycle_order,
            self.output_feed_length,
            self.output_feed_source,
            self.output_feed_comp,
            self.output_pause_after_feed,
            self.output_split_check,
            self.output_panel_height,
            self.output_force_split,
            self.output_angle_comp,
            self.output_end_feed,
            self.output_comp_diameter,
            self.output_joint_comp,
            self.output_dual_head_priority,
        ]

        for w in controls:
            w.blockSignals(True)

        try:
            self.output_cycle_check.setChecked(cfg['cycle_enabled'])
            self.output_cycle_count.setValue(cfg['cycle_count'])
            self.output_cycle_order.setCurrentText(cfg['cycle_order'])
            self.output_feed_length.setValue(cfg['feed_length'])
            self.output_feed_source.setCurrentText(cfg['feed_source'])
            self.output_feed_comp.setValue(cfg['feed_comp'])
            self.output_pause_after_feed.setChecked(cfg['pause_after_feed'])

            self.output_split_check.setChecked(cfg['split_enabled'])
            self.output_panel_height.setValue(cfg['panel_height'])
            self.output_force_split.setChecked(cfg['force_split'])
            self.output_angle_comp.setValue(cfg['angle_comp'])
            self.output_end_feed.setChecked(cfg['end_feed'])
            self.output_comp_diameter.setValue(cfg['comp_diameter'])
            self.output_joint_comp.setChecked(cfg['joint_comp'])

            self.output_dual_head_priority.setChecked(cfg['dual_head_priority'])
        finally:
            for w in controls:
                w.blockSignals(False)

        self._refresh_output_section_visibility()
        self._refresh_feed_length_editor_state()

    def _save_output_settings_to_canvas(self):
        """保存输出页参数到 canvas.optimize_settings。"""
        if not self.canvas:
            return
        try:
            if not hasattr(self.canvas, 'optimize_settings') or self.canvas.optimize_settings is None:
                self.canvas.optimize_settings = {}
            self.canvas.optimize_settings['output_panel'] = self._collect_output_settings_from_ui()
        except Exception:
            pass

    def _load_output_settings_from_canvas(self):
        """从 canvas.optimize_settings 加载输出页参数。"""
        if not hasattr(self, 'output_cycle_check'):
            return
        try:
            raw = {}
            if self.canvas and hasattr(self.canvas, 'optimize_settings') and isinstance(self.canvas.optimize_settings, dict):
                raw = self.canvas.optimize_settings.get('output_panel', {}) or {}
            self._apply_output_settings_to_ui(self._normalize_output_settings(raw))
        except Exception:
            self._apply_output_settings_to_ui(dict(self._output_defaults))

    def _on_output_settings_changed(self, *_args):
        self._refresh_output_section_visibility()
        self._refresh_feed_length_editor_state()
        self._save_output_settings_to_canvas()

    def _refresh_output_section_visibility(self):
        if hasattr(self, 'output_cycle_content'):
            self.output_cycle_content.setVisible(True)
            self.output_cycle_content.setEnabled(self.output_cycle_check.isChecked())
        if hasattr(self, 'output_split_content'):
            self.output_split_content.setVisible(True)
            self.output_split_content.setEnabled(self.output_split_check.isChecked())

    def _refresh_feed_length_editor_state(self):
        if not hasattr(self, 'output_feed_source'):
            return
        is_manual = self.output_feed_source.currentText() == "手动输入"
        if hasattr(self, 'output_cycle_check'):
            is_manual = is_manual and self.output_cycle_check.isChecked()
        self.output_feed_length.setEnabled(is_manual)

    def get_output_panel_settings(self):
        return self._collect_output_settings_from_ui()

    def _is_system_scene_item(self, item) -> bool:
        if not self.canvas:
            return False
        try:
            for attr in ('_work_item', '_fiducial_item', '_grid_item'):
                if hasattr(self.canvas, attr) and item == getattr(self.canvas, attr):
                    return True
            if hasattr(self.canvas, '_workarea_items') and item in self.canvas._workarea_items:
                return True
        except Exception:
            pass
        return False

    def _get_item_color_hex(self, item):
        color_hex = None
        layer_role = Qt.UserRole + 100
        try:
            if hasattr(item, 'data'):
                c = item.data(layer_role)
                if isinstance(c, QColor):
                    color_hex = c.name().upper()
                elif isinstance(c, str):
                    color_hex = c.upper()
        except Exception:
            pass
        if not color_hex and hasattr(item, 'pen'):
            try:
                p = item.pen()
                if p and p.color().isValid():
                    color_hex = p.color().name().upper()
            except Exception:
                pass
        if not color_hex and hasattr(item, 'defaultTextColor'):
            try:
                c = item.defaultTextColor()
                if c and c.isValid():
                    color_hex = c.name().upper()
            except Exception:
                pass
        return color_hex

    def _get_scene_data_bounds(self, selected_only=False):
        """计算可输出图形在场景中的包围盒。"""
        if not self.canvas:
            return None

        bounds = None
        try:
            all_items = self.canvas.scene.items(order=Qt.AscendingOrder)
        except Exception:
            all_items = self.canvas.scene.items()

        for item in all_items:
            if self._is_system_scene_item(item):
                continue
            color_hex = self._get_item_color_hex(item)
            layer_cfg = self.layer_data.get(color_hex) if color_hex else None
            if layer_cfg and not layer_cfg.is_output:
                continue

            try:
                visible = bool(item.isVisible())
            except Exception:
                visible = True

            # 隐藏图层仍可参与输出路径：仅当该层允许输出时纳入边界计算
            if (not visible) and not (layer_cfg and layer_cfg.is_output):
                continue

            if selected_only:
                try:
                    if not item.isSelected():
                        continue
                except Exception:
                    continue

            try:
                br = item.sceneBoundingRect()
            except Exception:
                continue
            if not br.isValid() or br.isNull():
                continue

            if bounds is None:
                bounds = br
            else:
                bounds = bounds.united(br)
        return bounds

    def _resolve_cycle_feed_length(self, settings):
        """根据送料长度来源计算实际送料长度。"""
        cfg = self._normalize_output_settings(settings)
        src = cfg['feed_source']
        if src == "手动输入":
            return cfg['feed_length']

        process_cfg = self._collect_process_settings_from_ui()
        data_bounds = self._get_scene_data_bounds(selected_only=process_cfg['output_selected'])
        data_h = float(data_bounds.height()) if data_bounds and data_bounds.isValid() else 0.0
        work_h = float(getattr(self.canvas, '_work_h', 0.0) or 0.0) if self.canvas else 0.0

        if src == "Y向幅面":
            return work_h if work_h > 0 else cfg['feed_length']
        if src == "图形高度":
            return data_h if data_h > 0 else cfg['feed_length']
        if src == "最小送料长度":
            vals = [v for v in (data_h, work_h) if v > 0]
            if vals:
                return min(vals)
            return cfg['feed_length']
        return cfg['feed_length']

    def _build_exporter_config(self):
        """构建导出器配置（含输出页高级参数）。"""
        output_cfg = self.get_output_panel_settings()
        process_cfg = self._collect_process_settings_from_ui()
        resolved_feed_length = self._resolve_cycle_feed_length(output_cfg)
        gap_comp_optimize = None
        small_circle_enable = None
        if self.canvas:
            exp = getattr(self.canvas, 'export_settings', {}) or {}
            optimize = getattr(self.canvas, 'optimize_settings', {}) or {}
            gap_comp_optimize = optimize.get('gap_comp_optimize', exp.get('gap_comp_optimize', None))
            small_circle_enable = exp.get('small_circle_enable', None)

        config = {
            'feed_rate': self.speed_spin.value(),
            'max_laser_power': self.max_power_spin.value(),
            'position_mode': process_cfg['position_mode'],
            'path_optimize': process_cfg['path_optimize'],
            'output_selected_only': process_cfg['output_selected'],
            'selected_positioning': process_cfg['selected_position'],
            'gap_comp_optimize': gap_comp_optimize,
            'small_circle_enable': small_circle_enable,
            'output_cycle': {
                'enabled': output_cfg['cycle_enabled'],
                'count': output_cfg['cycle_count'],
                'order': output_cfg['cycle_order'],
                'feed_length': resolved_feed_length,
                'feed_source': output_cfg['feed_source'],
                'feed_comp': output_cfg['feed_comp'],
                'pause_after_feed': output_cfg['pause_after_feed'],
            },
            'output_split': {
                'enabled': output_cfg['split_enabled'],
                'panel_height': output_cfg['panel_height'],
                'force_split': output_cfg['force_split'],
                'angle_comp': output_cfg['angle_comp'],
                'end_feed': output_cfg['end_feed'],
                'comp_diameter': output_cfg['comp_diameter'],
                'joint_comp': output_cfg['joint_comp'],
            },
            'dual_head_priority': output_cfg['dual_head_priority'],
        }
        return config

    def _build_layer_params_map(self):
        layer_params_map = {}
        for hex_color, p in self.layer_data.items():
            key = str(hex_color).upper()
            layer_params_map[key] = {
                'seal_gap': getattr(p, 'seal_gap', 0.0),
                'laser_on_delay': getattr(p, 'laser_on_delay', 0),
                'laser_off_delay': getattr(p, 'laser_off_delay', 0),
                'mode': getattr(p, 'mode', '激光切割'),
            }
        return layer_params_map

    def _create_configured_exporter(self):
        self._save_backlash_values()
        exporter = GCodeExporter()
        exporter.set_config(self._build_exporter_config())
        exporter.set_layer_params(self._build_layer_params_map())
        return exporter

    def _build_current_job_lines(self):
        if not self.canvas:
            return []
        self._save_process_settings_to_canvas()
        self._save_output_settings_to_canvas()
        exporter = self._create_configured_exporter()
        return exporter.export_canvas(
            self.canvas,
            allowed_colors=self.get_output_enabled_colors(),
            layer_settings=self.layer_data,
        )

    def _make_remote_job_name(self, prefix="job"):
        safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "_", str(prefix or "job"))
        ts = time.strftime("%Y%m%d_%H%M%S")
        return f"{safe_prefix}_{ts}.nc"

    def _upload_lines_to_device(self, lines, remote_name):
        if not lines:
            return False

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".nc",
                delete=False,
                encoding="utf-8",
            ) as fp:
                fp.write("\n".join(lines))
                temp_path = fp.name

            ok = self.communicator.upload_file_to_sd(temp_path, remote_name)
            if ok:
                self._last_remote_job_name = remote_name
            return bool(ok)
        finally:
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

    def _run_remote_file(self, remote_name):
        if not remote_name:
            return False, False
        ok_select, _ = self.communicator.send_system_command(f"+CREG:12,1,{remote_name}")
        ok_run, _ = self.communicator.send_system_command("+CREG:13,1")
        return bool(ok_select), bool(ok_run)

    def _send_realtime_gcode_sequence(self, commands):
        for cmd in commands:
            text = str(cmd or "").strip()
            if not text:
                continue
            ok, _ = self.communicator.send_custom_command(35, text)
            if not ok:
                return False, text
        return True, ""

    def _build_border_gcode_commands(self, laser_on=False):
        if not self.canvas:
            raise RuntimeError("画布未初始化")

        process_cfg = self._collect_process_settings_from_ui()
        bounds = self._get_scene_data_bounds(selected_only=process_cfg['output_selected'])
        if bounds is None or not bounds.isValid() or bounds.isNull():
            if process_cfg['output_selected']:
                raise RuntimeError("当前未选中可输出图形")
            raise RuntimeError("画布为空或没有可输出图形")

        exporter = self._create_configured_exporter()
        fiducial = exporter._get_fiducial_offset(self.canvas)

        scene_points = [
            (bounds.left(), bounds.top()),
            (bounds.right(), bounds.top()),
            (bounds.right(), bounds.bottom()),
            (bounds.left(), bounds.bottom()),
            (bounds.left(), bounds.top()),
        ]
        gcode_points = [exporter._apply_fiducial_offset(pt, fiducial) for pt in scene_points]

        commands = ["G90"]
        x0, y0 = gcode_points[0]
        commands.append(f"G0 X{x0:.3f} Y{y0:.3f}")

        if laser_on:
            power = max(0.0, min(100.0, float(self.max_power_spin.value())))
            if power <= 0:
                power = 10.0
            feed = max(1.0, float(self.speed_spin.value()) * 60.0)
            commands.append(f"M3 S{power:.1f}")
            for x, y in gcode_points[1:]:
                commands.append(f"G1 X{x:.3f} Y{y:.3f} F{feed:.1f}")
            commands.append("M5")
        else:
            for x, y in gcode_points[1:]:
                commands.append(f"G0 X{x:.3f} Y{y:.3f}")

        return commands

    def on_btn_start_clicked(self):
        """开始加工"""
        if not self.check_connection_and_alert():
            return

        if not self.canvas:
            return

        try:
            lines = self._build_current_job_lines()
            if not lines:
                QMessageBox.warning(self, "提示", "画布为空或没有可输出的图形")
                return

            self._manual_stop_requested = False
            self._process_paused = False
            self._debug_process_start_ts = time.time()
            self.communicator.start_sending(lines)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动失败: {str(e)}")

    def on_btn_pause_clicked(self):
        """暂停/继续"""
        # 上位机流式发送：直接暂停/恢复发送定时器
        if self.communicator.is_sending:
            if self.communicator.send_timer.isActive():
                self.communicator.send_timer.stop()
                self._process_paused = True
                QMessageBox.information(self, "提示", "已暂停上位机发送")
            else:
                self.communicator.send_timer.start(10)
                self._process_paused = False
                QMessageBox.information(self, "提示", "已继续上位机发送")
            return

        # 下位机离线任务：通过系统指令暂停/继续
        if not self.check_connection_and_alert():
            return

        cmd = "+CREG:13,0" if not self._process_paused else "+CREG:13,1"
        ok, _ = self.communicator.send_system_command(cmd)
        if ok:
            self._process_paused = not self._process_paused
            text = "已暂停下位机离线任务" if self._process_paused else "已继续下位机离线任务"
            QMessageBox.information(self, "提示", text)
        else:
            QMessageBox.warning(self, "提示", "暂停/继续命令下发失败，请确认固件支持 +CREG:13")

    def on_btn_stop_clicked(self):
        """停止加工"""
        if self.communicator.is_sending:
            self._manual_stop_requested = True
            self.communicator.stop_sending()
            self._process_paused = False
            return

        if not self.check_connection_and_alert():
            return

        ok1, _ = self.communicator.send_custom_command(35, "!")
        ok2, _ = self.communicator.send_system_command("+CREG:13,0")
        self._process_paused = False
        if ok1 or ok2:
            QMessageBox.information(self, "提示", "停止命令已发送")
        else:
            QMessageBox.warning(self, "提示", "停止命令下发失败")

    def on_btn_download_clicked(self):
        """下载"""
        if not self.check_connection_and_alert():
            return
        if not self.canvas:
            return
        try:
            lines = self._build_current_job_lines()
            if not lines:
                QMessageBox.warning(self, "提示", "画布为空或没有可输出的图形")
                return

            remote_name = self._make_remote_job_name("job")
            if not self._upload_lines_to_device(lines, remote_name):
                QMessageBox.warning(self, "提示", "下载失败：文件上传下位机失败")
                return

            ok_select, _ = self.communicator.send_system_command(f"+CREG:12,1,{remote_name}")
            self._process_paused = False
            if ok_select:
                QMessageBox.information(self, "提示", f"下载成功：{remote_name}\n已设置为当前离线文件")
            else:
                QMessageBox.warning(self, "提示", f"下载成功：{remote_name}\n但设置当前文件失败，请检查固件支持 +CREG:12")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"下载失败: {str(e)}")

    def on_btn_cut_border_clicked(self):
        """切边框"""
        if not self.check_connection_and_alert():
            return
        try:
            commands = self._build_border_gcode_commands(laser_on=True)
            ok, failed_cmd = self._send_realtime_gcode_sequence(commands)
            if ok:
                QMessageBox.information(self, "提示", "切边框命令已下发")
            else:
                QMessageBox.warning(self, "提示", f"切边框失败，命令下发失败: {failed_cmd}")
        except Exception as e:
            QMessageBox.warning(self, "提示", f"切边框失败: {str(e)}")

    def on_btn_walk_border_clicked(self):
        """走边框"""
        if not self.check_connection_and_alert():
            return
        try:
            commands = self._build_border_gcode_commands(laser_on=False)
            ok, failed_cmd = self._send_realtime_gcode_sequence(commands)
            if ok:
                QMessageBox.information(self, "提示", "走边框命令已下发")
            else:
                QMessageBox.warning(self, "提示", f"走边框失败，命令下发失败: {failed_cmd}")
        except Exception as e:
            QMessageBox.warning(self, "提示", f"走边框失败: {str(e)}")

    def on_comm_log(self, msg):
        print(f"[Comm] {msg}")
        # 可以显示在状态栏或者其他地方

    def on_comm_error(self, msg):
        QMessageBox.critical(self, "通信错误", msg)

    def on_sending_finished(self):
        self._process_paused = False
        if self._debug_process_start_ts is not None:
            self._debug_last_process_duration_ms = max(
                0,
                int((time.time() - self._debug_process_start_ts) * 1000),
            )
            self._debug_process_start_ts = None
            if hasattr(self, "dbg_last_time_label"):
                self.dbg_last_time_label.setText(
                    self._format_duration_text(self._debug_last_process_duration_ms)
                )
        if getattr(self, "_manual_stop_requested", False):
            self._manual_stop_requested = False
            QMessageBox.information(self, "提示", "加工已停止")
        else:
            QMessageBox.information(self, "提示", "加工完成！")

    def on_btn_save_offline_clicked(self):
        """保存为脱机文件"""
        if not self.canvas:
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "保存为脱机文件", "", "NC Files (*.nc);;All Files (*)")
        if file_path:
            try:
                lines = self._build_current_job_lines()
                if not lines:
                    QMessageBox.warning(self, "提示", "画布为空或没有可输出的图形")
                    return
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                QMessageBox.information(self, "成功", "脱机文件保存成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def on_btn_offline_output_clicked(self):
        """脱机文件输出"""
        if not self.check_connection_and_alert():
            return
        if not self.canvas:
            return

        try:
            remote_name = self._last_remote_job_name
            if not remote_name:
                lines = self._build_current_job_lines()
                if not lines:
                    QMessageBox.warning(self, "提示", "画布为空或没有可输出的图形")
                    return
                remote_name = self._make_remote_job_name("offline")
                if not self._upload_lines_to_device(lines, remote_name):
                    QMessageBox.warning(self, "提示", "脱机文件输出失败：文件上传下位机失败")
                    return

            ok_select, ok_run = self._run_remote_file(remote_name)
            self._process_paused = False
            if ok_select and ok_run:
                QMessageBox.information(self, "提示", f"脱机文件已开始输出：{remote_name}")
            elif ok_select and not ok_run:
                QMessageBox.warning(self, "提示", f"文件已选中：{remote_name}\n但启动执行失败，请检查固件支持 +CREG:13")
            else:
                QMessageBox.warning(self, "提示", f"脱机文件输出失败：{remote_name}\n请检查固件支持 +CREG:12/+CREG:13")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"脱机文件输出失败: {str(e)}")

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
        self.min_power_spin.setValue(0.0)
        row2.addWidget(self.min_power_spin)
        
        row2.addWidget(QLabel("最大功率(%)"))
        self.max_power_spin = QDoubleSpinBox()
        self.max_power_spin.setRange(0, 100)
        self.max_power_spin.setValue(100.0)
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
        bitmap_colors = set()
        from ui.graphics_items import EditablePathItem, EditableEllipseItem
        from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem
        
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
                    bitmap_colors.add(color.name().upper())
            
            if color and color.isValid():
                used_colors.add(color.name().upper())

        # 2. 同步数据
        for hex_color in used_colors:
            if hex_color not in self.layer_data:
                params = LayerParams(QColor(hex_color))
                # 位图导入是特例：新建图层默认使用激光扫描模式
                if hex_color in bitmap_colors:
                    params.mode = "激光扫描"
                self.layer_data[hex_color] = params

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
                    params.min_power_2 = 0.0
                    params.max_power_2 = 100.0

                self.speed_spin.setValue(params.speed_2)
                self.speed_spin.setEnabled(True)
                self.min_power_spin.setValue(getattr(params, 'min_power_2', 0.0))
                self.max_power_spin.setValue(getattr(params, 'max_power_2', 100.0))
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
                is_interactive = bool(params.is_visible and (not params.is_locked))
                item.setFlag(QGraphicsItem.ItemIsMovable, is_interactive)
                item.setFlag(QGraphicsItem.ItemIsSelectable, is_interactive)
                
                # 隐藏或锁定时，如果当前被选中则取消选中
                if (not params.is_visible or params.is_locked) and item.isSelected():
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
                        self.layer_table.selectRow(row)
                        self.on_layer_selected() # 手动触发更新参数
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
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        def _make_readonly_combo(items):
            combo = QComboBox()
            combo.setView(QListView())
            combo.setMaxVisibleItems(10)
            combo.setEditable(True)
            combo.lineEdit().setReadOnly(True)
            combo.addItems(items)
            return combo

        # 1) 循环加工
        cycle_group = QGroupBox("")
        cycle_layout = QVBoxLayout(cycle_group)
        cycle_layout.setContentsMargins(5, 5, 5, 5)
        cycle_layout.setSpacing(6)

        self.output_cycle_check = QCheckBox("循环加工")
        cycle_layout.addWidget(self.output_cycle_check)

        self.output_cycle_content = QWidget()
        cycle_grid = QGridLayout(self.output_cycle_content)
        cycle_grid.setContentsMargins(22, 0, 0, 0)
        cycle_grid.setHorizontalSpacing(6)
        cycle_grid.setVerticalSpacing(6)

        cycle_grid.addWidget(QLabel("循环次数:"), 0, 0)
        self.output_cycle_count = QSpinBox()
        self.output_cycle_count.setRange(0, 9999)
        self.output_cycle_count.setValue(0)
        cycle_grid.addWidget(self.output_cycle_count, 0, 1)

        self.output_cycle_order = _make_readonly_combo(["先切割后送料", "先送料后切割", "往返送料"])
        cycle_grid.addWidget(self.output_cycle_order, 0, 2)

        cycle_grid.addWidget(QLabel("送料长度:"), 1, 0)
        self.output_feed_length = QDoubleSpinBox()
        self.output_feed_length.setRange(0.0, 99999.0)
        self.output_feed_length.setDecimals(3)
        self.output_feed_length.setValue(500.0)
        cycle_grid.addWidget(self.output_feed_length, 1, 1)

        self.output_feed_source = _make_readonly_combo(["手动输入", "Y向幅面", "图形高度", "最小送料长度"])
        cycle_grid.addWidget(self.output_feed_source, 1, 2)

        cycle_grid.addWidget(QLabel("送料补偿:"), 2, 0)
        self.output_feed_comp = QDoubleSpinBox()
        self.output_feed_comp.setRange(-9999.0, 9999.0)
        self.output_feed_comp.setDecimals(3)
        self.output_feed_comp.setValue(0.0)
        cycle_grid.addWidget(self.output_feed_comp, 2, 1)

        self.output_pause_after_feed = QCheckBox("送料后暂停")
        cycle_grid.addWidget(self.output_pause_after_feed, 2, 2)

        cycle_layout.addWidget(self.output_cycle_content)
        layout.addWidget(cycle_group)

        # 2) 超幅面分块切割
        split_group = QGroupBox("")
        split_layout = QVBoxLayout(split_group)
        split_layout.setContentsMargins(5, 5, 5, 5)
        split_layout.setSpacing(6)

        self.output_split_check = QCheckBox("超幅面分块切割")
        split_layout.addWidget(self.output_split_check)

        self.output_split_content = QWidget()
        split_grid = QGridLayout(self.output_split_content)
        split_grid.setContentsMargins(22, 0, 0, 0)
        split_grid.setHorizontalSpacing(6)
        split_grid.setVerticalSpacing(6)

        split_grid.addWidget(QLabel("幅面高度:"), 0, 0)
        self.output_panel_height = QDoubleSpinBox()
        self.output_panel_height.setRange(0.001, 99999.0)
        self.output_panel_height.setDecimals(3)
        self.output_panel_height.setValue(500.0)
        split_grid.addWidget(self.output_panel_height, 0, 1)

        self.output_force_split = QCheckBox("强制分块")
        split_grid.addWidget(self.output_force_split, 0, 2)

        split_grid.addWidget(QLabel("角度补偿:"), 1, 0)
        self.output_angle_comp = QDoubleSpinBox()
        self.output_angle_comp.setRange(-180.0, 180.0)
        self.output_angle_comp.setDecimals(4)
        self.output_angle_comp.setValue(0.0)
        split_grid.addWidget(self.output_angle_comp, 1, 1)

        self.output_end_feed = QCheckBox("结束送料")
        split_grid.addWidget(self.output_end_feed, 1, 2)

        split_grid.addWidget(QLabel("补偿直径(mm):"), 2, 0)
        self.output_comp_diameter = QDoubleSpinBox()
        self.output_comp_diameter.setRange(0.0, 999.0)
        self.output_comp_diameter.setDecimals(3)
        self.output_comp_diameter.setValue(1.0)
        split_grid.addWidget(self.output_comp_diameter, 2, 1)

        self.output_joint_comp = QCheckBox("拼接补偿")
        split_grid.addWidget(self.output_joint_comp, 2, 2)

        split_layout.addWidget(self.output_split_content)
        layout.addWidget(split_group)

        # 3) 双头互移头2优先
        head_group = QGroupBox("")
        head_layout = QVBoxLayout(head_group)
        head_layout.setContentsMargins(5, 5, 5, 5)
        self.output_dual_head_priority = QCheckBox("双头互移头2优先")
        head_layout.addWidget(self.output_dual_head_priority)
        layout.addWidget(head_group)

        self.output_cycle_check.toggled.connect(self._on_output_settings_changed)
        self.output_cycle_count.valueChanged.connect(self._on_output_settings_changed)
        self.output_cycle_order.currentTextChanged.connect(self._on_output_settings_changed)
        self.output_feed_length.valueChanged.connect(self._on_output_settings_changed)
        self.output_feed_source.currentTextChanged.connect(self._on_output_settings_changed)
        self.output_feed_comp.valueChanged.connect(self._on_output_settings_changed)
        self.output_pause_after_feed.toggled.connect(self._on_output_settings_changed)

        self.output_split_check.toggled.connect(self._on_output_settings_changed)
        self.output_panel_height.valueChanged.connect(self._on_output_settings_changed)
        self.output_force_split.toggled.connect(self._on_output_settings_changed)
        self.output_angle_comp.valueChanged.connect(self._on_output_settings_changed)
        self.output_end_feed.toggled.connect(self._on_output_settings_changed)
        self.output_comp_diameter.valueChanged.connect(self._on_output_settings_changed)
        self.output_joint_comp.toggled.connect(self._on_output_settings_changed)
        self.output_dual_head_priority.toggled.connect(self._on_output_settings_changed)

        layout.addStretch()

        self._apply_output_settings_to_ui(dict(self._output_defaults))
        self._load_output_settings_from_canvas()
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

        # 顶部单选按钮组
        param_type_layout = QHBoxLayout()
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
        self.user_param_tree.itemChanged.connect(self.on_user_param_tree_item_changed)
        
        param_layout.addWidget(self.user_param_tree)

        # 默认选中第一个并刷新列表
        self.radio_process.setChecked(True)
        self.user_param_group.buttonClicked.connect(self.update_user_param_tree)
        
        # 初始化数据
        self.init_user_params_data()
        if os.path.exists(self.user_params_file_path):
            try:
                self._load_user_params_from_ini(self.user_params_file_path)
            except Exception as e:
                print(f"加载用户参数持久化文件失败: {e}")
        self._load_backlash_values()
        self.update_user_param_tree()
        self._persist_user_params_silent()

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
        self.user_param_tree.blockSignals(True)
        self.user_param_tree.clear()
        
        idx = self.user_param_group.checkedId()
        if idx not in self.user_params:
            self.user_param_tree.blockSignals(False)
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
                child.setData(0, Qt.UserRole, (idx, cat_name, key))
                
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
        self.user_param_tree.blockSignals(False)

    def on_user_param_tree_item_clicked(self, item, column):
        """用户参数树单击事件处理"""
        # 获取第一列的文本作为参数名
        param_name = item.text(0)
        # 如果是下拉框类型的参数，单击即进入编辑状态（显示下拉框）
        if param_name in PARAM_OPTIONS:
            self.user_param_tree.editItem(item, 1)

    def on_user_param_tree_item_changed(self, item, column):
        """用户参数树编辑完成后，回写到数据模型并同步反向间隙配置"""
        if column != 1:
            return

        meta = item.data(0, Qt.UserRole)
        if not meta or len(meta) != 3:
            return

        group_idx, cat_name, key_name = meta
        value = item.text(1)
        updated = self._set_user_param_value(group_idx, cat_name, key_name, value)

        if not updated:
            return

        if group_idx == 2 and key_name in ("反向间隙X(mm)", "反向间隙Y(mm)"):
            self._save_backlash_values()
        self._persist_user_params_silent()

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
        start_dir = os.path.dirname(self.user_params_last_open_path) if self.user_params_last_open_path else ""
        filename, _ = QFileDialog.getOpenFileName(self, "打开参数", start_dir, "INI Files (*.ini)")
        if not filename:
            return

        try:
            self._load_user_params_from_ini(filename)
            self.user_params_last_open_path = filename
            self._persist_user_params_silent()
            QMessageBox.information(self, "提示", f"参数加载成功\n{filename}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载参数失败: {str(e)}")

    def on_save_params_clicked(self):
        """保存参数文件"""
        self._save_backlash_values()
        default_path = self.user_params_last_open_path or self.user_params_file_path
        filename, _ = QFileDialog.getSaveFileName(self, "保存参数", default_path, "INI Files (*.ini)")
        if not filename:
            return

        if not filename.lower().endswith(".ini"):
            filename += ".ini"

        try:
            self._save_user_params_to_ini(filename)
            self.user_params_last_open_path = filename
            self._persist_user_params_silent()
            QMessageBox.information(self, "提示", f"参数保存成功\n{filename}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存参数失败: {str(e)}")

    def on_read_params_clicked(self):
        """读取机器参数"""
        if not self.check_connection_and_alert():
            return

        try:
            remote_name = self._remote_user_params_filename()
            ini_text = ""
            tried = []

            for cmd_tpl in self.USER_PARAMS_READ_COMMANDS:
                cmd = cmd_tpl.format(filename=remote_name)
                tried.append(cmd)
                ok, resp_text = self.communicator.send_system_command(cmd)
                if not ok:
                    continue
                extracted = self._extract_ini_text_from_response(resp_text)
                if extracted:
                    ini_text = extracted
                    break

            if not ini_text:
                raise RuntimeError(
                    "下位机未返回可解析的 INI 参数文本。\n"
                    f"已尝试命令: {' | '.join(tried)}"
                )

            self._parse_machine_ini_text(ini_text)
            self._persist_user_params_silent()
            QMessageBox.information(self, "提示", "参数读取成功，界面已更新。")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"读取参数失败: {str(e)}")

    def on_write_params_clicked(self):
        """写入机器参数"""
        if not self.check_connection_and_alert():
            return

        try:
            # 先确保界面参数落盘为 INI
            self._save_backlash_values()
            self._save_user_params_to_ini(self.user_params_file_path)
            self.user_params_last_open_path = self.user_params_file_path
            remote_name = self._remote_user_params_filename()

            # 上传 INI 到下位机
            upload_ok = self.communicator.upload_file_to_sd(self.user_params_file_path, remote_name)
            if not upload_ok:
                raise RuntimeError("参数文件上传失败。")

            # 尝试通知下位机应用参数
            applied = False
            applied_cmd = ""
            for cmd_tpl in self.USER_PARAMS_APPLY_COMMANDS:
                cmd = cmd_tpl.format(filename=remote_name)
                ok, _ = self.communicator.send_system_command(cmd)
                if ok:
                    applied = True
                    applied_cmd = cmd
                    break

            self._persist_user_params_silent()
            if applied:
                QMessageBox.information(
                    self,
                    "提示",
                    f"参数写入成功。\nINI已上传: {remote_name}\n已发送应用命令: {applied_cmd}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "提示",
                    f"INI已上传到下位机: {remote_name}\n但未确认应用命令执行，请检查固件支持的参数加载指令。",
                )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"写入参数失败: {str(e)}")

    def create_test_tab(self):
        """创建调试标签页（布局与 RDWorks 风格一致）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        main_group = QGroupBox()
        main_layout = QVBoxLayout(main_group)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(8)
        top_grid.setVerticalSpacing(6)

        self.dbg_pos_label_x = QLabel("X=?")
        self.dbg_pos_label_y = QLabel("Y=?")
        self.dbg_pos_label_z = QLabel("Z=?")

        pos_box = QWidget()
        pos_box_layout = QVBoxLayout(pos_box)
        pos_box_layout.setContentsMargins(4, 4, 4, 4)
        pos_box_layout.setSpacing(2)
        pos_box_layout.addWidget(self.dbg_pos_label_x)
        pos_box_layout.addWidget(self.dbg_pos_label_y)
        pos_box_layout.addWidget(self.dbg_pos_label_z)

        self.dbg_btn_read_pos = QPushButton("读取当前位置")
        self.dbg_btn_move_target = QPushButton("移动到目标位置")
        self.dbg_btn_last_time = QPushButton("前次加工时间")

        self.dbg_target_x_edit = QLineEdit("0.000")
        self.dbg_target_y_edit = QLineEdit("0.000")
        self.dbg_target_x_edit.setFixedWidth(96)
        self.dbg_target_y_edit.setFixedWidth(96)

        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 0, 0, 0)
        target_row.setSpacing(6)
        target_row.addWidget(self.dbg_target_x_edit)
        target_row.addWidget(self.dbg_target_y_edit)

        self.dbg_last_time_label = QLabel("0时:0分:0秒:0毫秒")

        top_grid.addWidget(pos_box, 0, 0)
        top_grid.addWidget(self.dbg_btn_read_pos, 0, 1)
        top_grid.addLayout(target_row, 1, 0)
        top_grid.addWidget(self.dbg_btn_move_target, 1, 1)
        top_grid.addWidget(self.dbg_last_time_label, 2, 0)
        top_grid.addWidget(self.dbg_btn_last_time, 2, 1)

        main_layout.addLayout(top_grid)

        axis_group = QGroupBox("单轴移动")
        axis_layout = QVBoxLayout(axis_group)
        axis_layout.setContentsMargins(8, 8, 8, 8)
        axis_layout.setSpacing(6)

        upper_layout = QHBoxLayout()
        upper_layout.setSpacing(10)

        xy_panel = QWidget()
        xy_panel_layout = QGridLayout(xy_panel)
        xy_panel_layout.setContentsMargins(0, 0, 0, 0)
        xy_panel_layout.setHorizontalSpacing(4)
        xy_panel_layout.setVerticalSpacing(4)

        self.dbg_btn_y_plus = QPushButton("Y+")
        self.dbg_btn_x_minus = QPushButton("X-")
        self.dbg_btn_xy_home = QPushButton("原点")
        self.dbg_btn_x_plus = QPushButton("X+")
        self.dbg_btn_y_minus = QPushButton("Y-")

        xy_panel_layout.addWidget(self.dbg_btn_y_plus, 0, 1)
        xy_panel_layout.addWidget(self.dbg_btn_x_minus, 1, 0)
        xy_panel_layout.addWidget(self.dbg_btn_xy_home, 1, 1)
        xy_panel_layout.addWidget(self.dbg_btn_x_plus, 1, 2)
        xy_panel_layout.addWidget(self.dbg_btn_y_minus, 2, 1)

        upper_layout.addWidget(xy_panel, 0, Qt.AlignTop)

        param_panel = QWidget()
        param_grid = QGridLayout(param_panel)
        param_grid.setContentsMargins(0, 0, 0, 0)
        param_grid.setHorizontalSpacing(6)
        param_grid.setVerticalSpacing(4)

        self.dbg_offset_edit = QLineEdit("10.000")
        self.dbg_speed_edit = QLineEdit("50")
        self.dbg_power_edit = QLineEdit("0")
        self.dbg_offset_edit.setFixedWidth(88)
        self.dbg_speed_edit.setFixedWidth(88)
        self.dbg_power_edit.setFixedWidth(88)

        param_grid.addWidget(QLabel("偏移(mm):"), 0, 0)
        param_grid.addWidget(self.dbg_offset_edit, 0, 1)
        param_grid.addWidget(QLabel("速度(mm/s):"), 1, 0)
        param_grid.addWidget(self.dbg_speed_edit, 1, 1)
        param_grid.addWidget(QLabel("激光功率(%):"), 2, 0)
        param_grid.addWidget(self.dbg_power_edit, 2, 1)

        upper_layout.addWidget(param_panel, 1)
        axis_layout.addLayout(upper_layout)

        check_row = QHBoxLayout()
        check_row.setSpacing(18)

        self.dbg_chk_continuous = QCheckBox("连续运动")
        self.dbg_chk_from_origin = QCheckBox("从原点移动")
        self.dbg_chk_laser_on = QCheckBox("是否出光")

        check_row.addWidget(self.dbg_chk_continuous)
        check_row.addWidget(self.dbg_chk_from_origin)
        check_row.addWidget(self.dbg_chk_laser_on)
        check_row.addStretch()
        axis_layout.addLayout(check_row)

        lower_layout = QGridLayout()
        lower_layout.setHorizontalSpacing(4)
        lower_layout.setVerticalSpacing(4)

        self.dbg_btn_z_plus = QPushButton("Z+")
        self.dbg_btn_z_home = QPushButton("原点")
        self.dbg_btn_z_minus = QPushButton("Z-")

        self.dbg_btn_u_plus = QPushButton("U+")
        self.dbg_btn_u_home = QPushButton("原点")
        self.dbg_btn_u_minus = QPushButton("U-")

        self.dbg_btn_focus = QPushButton("寻焦")
        self.dbg_btn_locate = QPushButton("定位")
        self.dbg_btn_shot = QPushButton("点射")

        lower_layout.addWidget(self.dbg_btn_z_plus, 0, 0)
        lower_layout.addWidget(self.dbg_btn_z_home, 0, 1)
        lower_layout.addWidget(self.dbg_btn_z_minus, 0, 2)

        lower_layout.addWidget(self.dbg_btn_u_plus, 0, 3)
        lower_layout.addWidget(self.dbg_btn_u_home, 0, 4)
        lower_layout.addWidget(self.dbg_btn_u_minus, 0, 5)

        lower_layout.addWidget(self.dbg_btn_focus, 0, 6)
        lower_layout.addWidget(self.dbg_btn_locate, 1, 6)
        lower_layout.addWidget(self.dbg_btn_shot, 2, 6)

        axis_layout.addLayout(lower_layout)

        main_layout.addWidget(axis_group)
        layout.addWidget(main_group)
        layout.addStretch()

        self._wire_debug_panel_actions()
        return widget

    def _wire_debug_panel_actions(self):
        self.dbg_btn_read_pos.clicked.connect(self.on_debug_read_current_position)
        self.dbg_btn_move_target.clicked.connect(self.on_debug_move_to_target)
        self.dbg_btn_last_time.clicked.connect(self.on_debug_show_last_time)

        self.dbg_btn_x_minus.clicked.connect(lambda: self.on_debug_axis_move("X", -1))
        self.dbg_btn_x_plus.clicked.connect(lambda: self.on_debug_axis_move("X", 1))
        self.dbg_btn_y_minus.clicked.connect(lambda: self.on_debug_axis_move("Y", -1))
        self.dbg_btn_y_plus.clicked.connect(lambda: self.on_debug_axis_move("Y", 1))

        self.dbg_btn_z_minus.clicked.connect(lambda: self.on_debug_axis_move("Z", -1))
        self.dbg_btn_z_plus.clicked.connect(lambda: self.on_debug_axis_move("Z", 1))
        self.dbg_btn_u_minus.clicked.connect(lambda: self.on_debug_axis_move("U", -1))
        self.dbg_btn_u_plus.clicked.connect(lambda: self.on_debug_axis_move("U", 1))

        self.dbg_btn_xy_home.clicked.connect(lambda: self.on_debug_axis_home("XY"))
        self.dbg_btn_z_home.clicked.connect(lambda: self.on_debug_axis_home("Z"))
        self.dbg_btn_u_home.clicked.connect(lambda: self.on_debug_axis_home("U"))

        self.dbg_btn_focus.clicked.connect(self.on_debug_focus)
        self.dbg_btn_locate.clicked.connect(self.on_debug_locate)
        self.dbg_btn_shot.clicked.connect(self.on_debug_shot)

    def _debug_send_gcode(self, command: str, need_connection: bool = True):
        cmd = (command or "").strip()
        if not cmd:
            return False, ""
        if need_connection and not self.check_connection_and_alert():
            return False, ""
        return self.communicator.send_custom_command(35, cmd)

    def _debug_send_system(self, command: str, need_connection: bool = True):
        cmd = (command or "").strip()
        if not cmd:
            return False, ""
        if need_connection and not self.check_connection_and_alert():
            return False, ""
        return self.communicator.send_system_command(cmd)

    def _debug_read_float(self, editor: QLineEdit, field_name: str, default: float = None):
        raw = editor.text().strip()
        if raw == "" and default is not None:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            raise ValueError(f"{field_name} 请输入有效数字")

    def _debug_move_rate_to_feed(self, mm_per_sec: float):
        return max(1.0, float(mm_per_sec) * 60.0)

    def _format_duration_text(self, total_ms: int):
        ms = max(0, int(total_ms))
        hour = ms // 3600000
        ms -= hour * 3600000
        minute = ms // 60000
        ms -= minute * 60000
        second = ms // 1000
        ms -= second * 1000
        return f"{hour}时:{minute}分:{second}秒:{ms}毫秒"

    def _parse_position_from_response(self, resp_text: str):
        text = resp_text or ""
        result = {}

        mpos = re.search(r"MPos\s*:\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)", text, re.IGNORECASE)
        if mpos:
            result["X"] = float(mpos.group(1))
            result["Y"] = float(mpos.group(2))
            result["Z"] = float(mpos.group(3))

        for axis in ("X", "Y", "Z"):
            if axis in result:
                continue
            m = re.search(rf"\b{axis}\s*[:=]\s*([-+]?\d*\.?\d+)", text, re.IGNORECASE)
            if m:
                result[axis] = float(m.group(1))

        return result

    def _update_debug_position_labels(self, pos_dict):
        x = pos_dict.get("X")
        y = pos_dict.get("Y")
        z = pos_dict.get("Z")

        self.dbg_pos_label_x.setText(f"X={x:.3f}" if x is not None else "X=?")
        self.dbg_pos_label_y.setText(f"Y={y:.3f}" if y is not None else "Y=?")
        self.dbg_pos_label_z.setText(f"Z={z:.3f}" if z is not None else "Z=?")

    def on_debug_read_current_position(self):
        ok, resp = self._debug_send_system("+CREG:6,0")
        if not ok:
            QMessageBox.warning(self, "提示", "读取当前位置失败")
            return

        pos = self._parse_position_from_response(resp)
        if pos:
            self._update_debug_position_labels(pos)
            return

        ok2, resp2 = self._debug_send_gcode("?")
        if ok2:
            pos2 = self._parse_position_from_response(resp2)
            if pos2:
                self._update_debug_position_labels(pos2)
                return

        QMessageBox.information(
            self,
            "提示",
            "已发送读取位置命令，但响应未解析到坐标。请检查下位机返回格式。",
        )

    def _build_debug_motion_command(self, axis_delta: dict, from_origin: bool, continuous: bool, speed_mm_s: float):
        if from_origin:
            parts = ["G90", "G0"]
            for axis, value in axis_delta.items():
                parts.append(f"{axis}{value:.3f}")
            parts.append(f"F{self._debug_move_rate_to_feed(speed_mm_s):.1f}")
            return " ".join(parts)

        if continuous:
            parts = ["$J=G91"]
            for axis, value in axis_delta.items():
                parts.append(f"{axis}{value:.3f}")
            parts.append(f"F{self._debug_move_rate_to_feed(speed_mm_s):.1f}")
            return " ".join(parts)

        parts = ["G91", "G0"]
        for axis, value in axis_delta.items():
            parts.append(f"{axis}{value:.3f}")
        parts.append(f"F{self._debug_move_rate_to_feed(speed_mm_s):.1f}")
        return " ".join(parts)

    def on_debug_axis_move(self, axis: str, direction: int):
        try:
            offset = abs(self._debug_read_float(self.dbg_offset_edit, "偏移", 10.0))
            speed = abs(self._debug_read_float(self.dbg_speed_edit, "速度", 50.0))
            power = self._debug_read_float(self.dbg_power_edit, "激光功率", 0.0)
        except ValueError as e:
            QMessageBox.warning(self, "参数错误", str(e))
            return

        if offset <= 0:
            QMessageBox.warning(self, "参数错误", "偏移必须大于 0")
            return
        if speed <= 0:
            QMessageBox.warning(self, "参数错误", "速度必须大于 0")
            return
        if power < 0 or power > 100:
            QMessageBox.warning(self, "参数错误", "激光功率范围为 0~100")
            return

        delta = float(direction) * offset
        cmd = self._build_debug_motion_command(
            {axis.upper(): delta},
            from_origin=self.dbg_chk_from_origin.isChecked(),
            continuous=self.dbg_chk_continuous.isChecked(),
            speed_mm_s=speed,
        )

        if self.dbg_chk_laser_on.isChecked() and power > 0:
            sequence = [f"M3 S{power:.1f}", cmd, "M5"]
        else:
            sequence = [cmd]

        for item in sequence:
            ok, _ = self._debug_send_gcode(item)
            if not ok:
                QMessageBox.warning(self, "执行失败", f"下发失败: {item}")
                return

    def on_debug_axis_home(self, axis_group: str):
        axis_group = (axis_group or "").upper()
        if axis_group == "XY":
            cmd = "G90 G0 X0 Y0"
        elif axis_group == "Z":
            cmd = "G90 G0 Z0"
        elif axis_group == "U":
            cmd = "G90 G0 U0"
        else:
            return

        ok, _ = self._debug_send_gcode(cmd)
        if not ok:
            QMessageBox.warning(self, "执行失败", f"原点回位失败: {axis_group}")

    def on_debug_move_to_target(self):
        try:
            target_x = self._debug_read_float(self.dbg_target_x_edit, "目标X", 0.0)
            target_y = self._debug_read_float(self.dbg_target_y_edit, "目标Y", 0.0)
            speed = abs(self._debug_read_float(self.dbg_speed_edit, "速度", 50.0))
        except ValueError as e:
            QMessageBox.warning(self, "参数错误", str(e))
            return

        if speed <= 0:
            QMessageBox.warning(self, "参数错误", "速度必须大于 0")
            return

        cmd = (
            f"G90 G0 X{target_x:.3f} Y{target_y:.3f} "
            f"F{self._debug_move_rate_to_feed(speed):.1f}"
        )
        ok, _ = self._debug_send_gcode(cmd)
        if not ok:
            QMessageBox.warning(self, "执行失败", "移动到目标位置失败")
            return

        self.dbg_pos_label_x.setText(f"X={target_x:.3f}")
        self.dbg_pos_label_y.setText(f"Y={target_y:.3f}")

    def on_debug_focus(self):
        commands = ["+CREG:18,1", "+CREG:17,1"]
        for cmd in commands:
            ok, _ = self._debug_send_system(cmd)
            if ok:
                return
        QMessageBox.warning(self, "执行失败", "寻焦命令下发失败，请确认固件支持 +CREG:18 或 +CREG:17")

    def on_debug_locate(self):
        commands = ["+CREG:10,1", "+CREG:6,0"]
        for cmd in commands:
            ok, resp = self._debug_send_system(cmd)
            if ok:
                pos = self._parse_position_from_response(resp)
                if pos:
                    self._update_debug_position_labels(pos)
                return
        QMessageBox.warning(self, "执行失败", "定位命令下发失败，请确认固件支持 +CREG:10")

    def on_debug_shot(self):
        try:
            power = self._debug_read_float(self.dbg_power_edit, "激光功率", 0.0)
        except ValueError as e:
            QMessageBox.warning(self, "参数错误", str(e))
            return

        if power <= 0 or power > 100:
            QMessageBox.warning(self, "参数错误", "点射功率需在 0~100 且大于 0")
            return

        sequence = [
            f"M3 S{power:.1f}",
            "G4 P200",
            "M5",
        ]
        for cmd in sequence:
            ok, _ = self._debug_send_gcode(cmd)
            if not ok:
                QMessageBox.warning(self, "执行失败", f"点射失败: {cmd}")
                return

    def on_debug_show_last_time(self):
        if self._debug_last_process_duration_ms is None:
            QMessageBox.information(self, "提示", "当前没有前次加工时间记录")
            return
        self.dbg_last_time_label.setText(
            self._format_duration_text(self._debug_last_process_duration_ms)
        )

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
        position_icon_path = get_resource_path(os.path.join("right_panel_icons", "position.png"))
        position_btn.setIcon(QIcon(QPixmap(position_icon_path)))
        position_btn.setIconSize(QSize(32, 32))
        position_btn.setFixedSize(40, 40)
        position_btn.setCheckable(True)
        position_btn.setChecked(True)
        self.transform_btns.append((position_btn, 0))

        rotate_btn = QPushButton()
        rotate_icon_path = get_resource_path(os.path.join("right_panel_icons", "rotate.png"))
        rotate_btn.setIcon(QIcon(QPixmap(rotate_icon_path)))
        rotate_btn.setIconSize(QSize(32, 32))
        rotate_btn.setFixedSize(40, 40)
        rotate_btn.setCheckable(True)
        self.transform_btns.append((rotate_btn, 1)) #绑定索引1

        scale_btn = QPushButton()
        scale_icon_path = get_resource_path(os.path.join("right_panel_icons", "scale.png"))
        scale_btn.setIcon(QIcon(QPixmap(scale_icon_path)))
        scale_btn.setIconSize(QSize(32, 32))
        scale_btn.setFixedSize(40, 40)
        scale_btn.setCheckable(True)
        self.transform_btns.append((scale_btn, 2))

        size_btn = QPushButton()
        size_icon_path = get_resource_path(os.path.join("right_panel_icons", "size.png"))
        size_btn.setIcon(QIcon(QPixmap(size_icon_path)))
        size_btn.setIconSize(QSize(32, 32))
        size_btn.setFixedSize(40, 40)
        self.transform_btns.append((size_btn, 4))

        incline_btn = QPushButton()
        incline_icon_path = get_resource_path(os.path.join("right_panel_icons", "incline.png"))
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
