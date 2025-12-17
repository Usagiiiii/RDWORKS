import logging

from PyQt5.QtCore import QObject, pyqtSignal, QPointF
from PyQt5.QtGui import QTransform
from typing import List, Any
logger = logging.getLogger(__name__)
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem

from edit.commands import DeleteItemsCommand, AddItemCommand, AlignItemsCommand, MoveItemsCommand
from ui.graphics_items import EditablePathItem


class EditManager(QObject):
    # 信号：通知界面更新菜单项可用性
    undoAvailable = pyqtSignal(bool)
    redoAvailable = pyqtSignal(bool)
    cutCopyAvailable = pyqtSignal(bool)
    deleteAvailable = pyqtSignal(bool)
    selectAllAvailable = pyqtSignal(bool)
    # 信号：历史列表变化，参数 (list_of_descriptions, current_index)
    historyChanged = pyqtSignal(list, int)

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas  # 关联画布组件
        # 使用线性历史+索引模型，支持跳转（go_to）和显示完整历史
        self._history = []  # 列表: [cmd0, cmd1, ...]
        self._history_index = 0  # 下一个将要 redo 的索引（0..len(history)）
        # 最大历史容量（默认 >=50）。可按需修改。
        self.capacity = 100
        self.has_selection = False  # 是否有选中项

    def push_undo(self, command):
        """将操作记入历史（假设调用者已经执行了 command.redo()）。

        行为：如果当前 index 未到历史末尾，则截断历史至 index，再追加新命令。
        超出容量时丢弃最早的记录。
        """
        # 截断未来记录
        if self._history_index < len(self._history):
            self._history = self._history[:self._history_index]

        self._history.append(command)

        # 超出容量时丢弃最早的命令
        if len(self._history) > self.capacity:
            # 丢弃最早的 n 项，调整 index
            drop = len(self._history) - self.capacity
            self._history = self._history[drop:]
            self._history_index = max(0, self._history_index - drop)

        # 移动索引到历史末尾（表示已执行最新命令）
        self._history_index = len(self._history)

        # 发信号更新外部按钮与历史面板
        self.undoAvailable.emit(self._history_index > 0)
        self.redoAvailable.emit(self._history_index < len(self._history))
        self.historyChanged.emit(self._build_history_descriptions(), self._history_index)

    def undo(self):
        if self._history_index == 0:
            return
        # 上一步命令在 history_index-1
        self._history_index -= 1
        cmd = self._history[self._history_index]
        try:
            cmd.undo()
        except Exception:
            pass
        self.undoAvailable.emit(self._history_index > 0)
        self.redoAvailable.emit(self._history_index < len(self._history))
        self.historyChanged.emit(self._build_history_descriptions(), self._history_index)

    def redo(self):
        if self._history_index >= len(self._history):
            return
        cmd = self._history[self._history_index]
        try:
            cmd.redo()
        except Exception:
            pass
        self._history_index += 1
        self.undoAvailable.emit(self._history_index > 0)
        self.redoAvailable.emit(self._history_index < len(self._history))
        self.historyChanged.emit(self._build_history_descriptions(), self._history_index)

    # 修改 EditManager 类的 set_has_selection 方法
    def set_has_selection(self, has_selection: bool):
        """更新选中状态，触发菜单项可用性变化"""
        self.has_selection = has_selection
        self.cutCopyAvailable.emit(has_selection)
        self.deleteAvailable.emit(has_selection)

        # +++ 修改：检查画布是否有内容来决定全选是否可用 +++
        has_content = self._check_canvas_has_content()
        self.selectAllAvailable.emit(has_content)

    def _build_history_descriptions(self):
        """返回历史描述字符串列表，供 UI 显示。"""
        descs = []
        for cmd in self._history:
            # QUndoCommand 子类可能有 text() 方法
            try:
                if hasattr(cmd, 'text') and callable(getattr(cmd, 'text')):
                    t = cmd.text()
                elif hasattr(cmd, 'text') and isinstance(cmd.text, str):
                    t = cmd.text
                elif hasattr(cmd, 'desc'):
                    t = getattr(cmd, 'desc')
                else:
                    t = cmd.__class__.__name__
            except Exception:
                t = cmd.__class__.__name__
            descs.append(t)
        return descs

    def get_history(self):
        """返回 (descriptions_list, current_index)"""
        return self._build_history_descriptions(), self._history_index

    def go_to(self, target_index: int):
        """跳转到指定的历史索引位置（0..len(history)）。

        例如 target_index=0 表示回到初始状态（全部撤销），
        target_index=len(history) 表示前进到最新状态（全部重做）。
        """
        if target_index < 0:
            target_index = 0
        if target_index > len(self._history):
            target_index = len(self._history)

        # 向后撤销
        while self._history_index > target_index:
            self.undo()

        # 向前重做
        while self._history_index < target_index:
            self.redo()

        # historyChanged 信号在 undo/redo 中已发出

    def clear_history(self):
        """清空历史记录（不会触碰当前场景状态）。仅用于界面清理历史条目。"""
        self._history = []
        self._history_index = 0
        self.undoAvailable.emit(False)
        self.redoAvailable.emit(False)
        self.historyChanged.emit([], 0)

    def _check_canvas_has_content(self) -> bool:
        """检查画布是否有可选择的图形内容"""
        try:
            for item in self.canvas.scene.items():
                # 排除工作区网格和定位点
                if (hasattr(self.canvas, '_work_item') and item == self.canvas._work_item):
                    continue
                if (hasattr(self.canvas, 'fiducial_manager') and
                        self.canvas.fiducial_manager.get_fiducial_item() == item):
                    continue

                # 如果有图形项或图片项，则认为有内容
                if (hasattr(item, '_points') or  # 路径项
                        isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem))):  # 图片或文字项
                    return True
            return False
        except Exception as e:
            logger.error(f"检查画布内容时出错: {e}")
            return False

    def cut(self):
        if self.has_selection:
            # 剪切逻辑：暂存选中项 → 删除 → 入撤销栈
            selected = self.canvas.get_selected_items()
            if selected:
                cmd = DeleteItemsCommand(self.canvas, selected)
                # 先执行删除操作，再将命令记录到历史
                cmd.redo()
                self.push_undo(cmd)

    def copy(self):
        if self.has_selection:
            # 复制逻辑：将选中项存入剪贴板（示例为简化，实际需序列化图形数据）
            self.clipboard = self.canvas.get_selected_items()

    def paste(self):
        # 粘贴逻辑：从剪贴板恢复图形 → 入撤销栈
        if hasattr(self, 'clipboard') and self.clipboard:
            for item in self.clipboard:
                cmd = AddItemCommand(self.canvas, item)
                # 先执行添加，再记录历史
                cmd.redo()
                self.push_undo(cmd)

    def delete(self):
        if self.has_selection:
            # 删除逻辑：删除选中项 → 入撤销栈
            selected = self.canvas.get_selected_items()
            if selected:
                cmd = DeleteItemsCommand(self.canvas, selected)
                # 先执行删除，再记录历史
                cmd.redo()
                self.push_undo(cmd)

    def select_all(self):
        # 全选逻辑：选中画布所有图形项
        self.canvas.select_all_items()
        self.set_has_selection(True)

    def align_items(self, align_type):
        """对齐选中项"""
        items = self.canvas.get_selected_items()
        if not items or len(items) < 2:
            return
        
        cmd = AlignItemsCommand(self.canvas, items, align_type)
        # 执行并推入历史
        cmd.redo()
        self.push_undo(cmd)

    def align_to_page(self, align_type):
        """将选中项对齐到页面"""
        items = self.canvas.get_selected_items()
        if not items:
            return

        # 计算整体包围盒
        br = None
        for it in items:
            try:
                r = it.sceneBoundingRect()
                br = r if br is None else br.united(r)
            except Exception:
                continue
        
        if br is None:
            return

        # 获取页面尺寸
        work_w = getattr(self.canvas, '_work_w', 600.0)
        work_h = getattr(self.canvas, '_work_h', 400.0)

        dx = 0.0
        dy = 0.0

        if align_type == 'top_left':
            dx = -br.left()
            dy = -br.top()
        elif align_type == 'top_right':
            dx = work_w - br.right()
            dy = -br.top()
        elif align_type == 'bottom_left':
            dx = -br.left()
            dy = work_h - br.bottom()
        elif align_type == 'bottom_right':
            dx = work_w - br.right()
            dy = work_h - br.bottom()
        elif align_type == 'center':
            dx = (work_w / 2) - br.center().x()
            dy = (work_h / 2) - br.center().y()
        elif align_type == 'left':
            dx = -br.left()
        elif align_type == 'right':
            dx = work_w - br.right()
        elif align_type == 'top':
            dy = -br.top()
        elif align_type == 'bottom':
            dy = work_h - br.bottom()

        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return

        # 构建 MoveItemsCommand 需要的状态列表
        items_states = []
        from ui.graphics_items import EditablePathItem
        from PyQt5.QtCore import QPointF

        for it in items:
            try:
                if isinstance(it, EditablePathItem):
                    old_pts = it.points()
                    new_pts = [(p[0] + dx, p[1] + dy) for p in old_pts]
                    items_states.append(('path', it, old_pts, new_pts))
                else:
                    # 对于其他项（图片、文字等），修改 pos
                    old_pos = it.pos()
                    new_pos = QPointF(old_pos.x() + dx, old_pos.y() + dy)
                    items_states.append(('pos', it, old_pos, new_pos))
            except Exception:
                continue

        if items_states:
            cmd = MoveItemsCommand(self.canvas, items_states)
            cmd.redo()
            self.push_undo(cmd)

    def distribute_items(self, axis):
        """等间距分布选中项"""
        items = self.canvas.get_selected_items()
        if len(items) < 3: return # 至少需要3个对象才能体现间距分布

        states = []
        
        if axis == 'horizontal':
            # 按左边缘排序
            items.sort(key=lambda it: it.sceneBoundingRect().left())
            # 计算总跨度
            total_span = items[-1].sceneBoundingRect().right() - items[0].sceneBoundingRect().left()
            # 计算所有对象的宽度之和
            sum_width = sum(it.sceneBoundingRect().width() for it in items)
            # 计算总间隙空间
            total_gap = total_span - sum_width
            # 计算单个间隙
            gap = total_gap / (len(items) - 1)
            
            # 从第一个对象的右边缘开始放置
            current_x = items[0].sceneBoundingRect().right() + gap
            
            # 调整中间对象的位置（首尾不动）
            for it in items[1:-1]:
                rect = it.sceneBoundingRect()
                new_left = current_x
                dx = new_left - rect.left()
                
                if abs(dx) > 1e-9:
                    # 记录移动状态
                    if isinstance(it, EditablePathItem):
                        old_pts = it.points()
                        new_pts = [(p[0] + dx, p[1]) for p in old_pts]
                        states.append(('path', it, old_pts, new_pts))
                    else:
                        old_pos = it.pos()
                        new_pos = QPointF(old_pos.x() + dx, old_pos.y())
                        states.append(('pos', it, old_pos, new_pos))
                
                current_x += rect.width() + gap
        
        elif axis == 'vertical':
            # 按顶边缘排序
            items.sort(key=lambda it: it.sceneBoundingRect().top())
            total_span = items[-1].sceneBoundingRect().bottom() - items[0].sceneBoundingRect().top()
            sum_height = sum(it.sceneBoundingRect().height() for it in items)
            total_gap = total_span - sum_height
            gap = total_gap / (len(items) - 1)

            current_y = items[0].sceneBoundingRect().bottom() + gap
            
            for it in items[1:-1]:
                rect = it.sceneBoundingRect()
                new_top = current_y
                dy = new_top - rect.top()
                
                if abs(dy) > 1e-9:
                    if isinstance(it, EditablePathItem):
                        old_pts = it.points()
                        new_pts = [(p[0], p[1] + dy) for p in old_pts]
                        states.append(('path', it, old_pts, new_pts))
                    else:
                        old_pos = it.pos()
                        new_pos = QPointF(old_pos.x(), old_pos.y() + dy)
                        states.append(('pos', it, old_pos, new_pos))
                
                current_y += rect.height() + gap
        
        if states:
            cmd = MoveItemsCommand(self.canvas, states)
            cmd.redo()
            self.push_undo(cmd)

    def make_same_size(self, mode):
        """使选中项等宽/等高/等大小"""
        items = self.canvas.get_selected_items()
        if len(items) < 2: return

        # 确定目标尺寸（取最大值）
        max_w = max(it.sceneBoundingRect().width() for it in items)
        max_h = max(it.sceneBoundingRect().height() for it in items)

        states = []
        for it in items:
            rect = it.sceneBoundingRect()
            w = rect.width()
            h = rect.height()
            if w == 0 or h == 0: continue

            sx = 1.0
            sy = 1.0
            
            if mode == 'width' or mode == 'size':
                sx = max_w / w
            if mode == 'height' or mode == 'size':
                sy = max_h / h
            
            if abs(sx - 1.0) < 1e-5 and abs(sy - 1.0) < 1e-5:
                continue

            # 以中心为基准进行缩放
            cx = rect.center().x()
            cy = rect.center().y()

            if isinstance(it, EditablePathItem):
                old_pts = it.points()
                new_pts = []
                for x, y in old_pts:
                    nx = cx + (x - cx) * sx
                    ny = cy + (y - cy) * sy
                    new_pts.append((nx, ny))
                states.append(('path', it, old_pts, new_pts))
            else:
                # 使用 transform
                old_t = it.transform()
                m = QTransform()
                m.translate(cx, cy)
                m.scale(sx, sy)
                m.translate(-cx, -cy)
                # 将新的缩放应用到原有变换之上
                new_t = m * old_t
                states.append(('transform', it, old_t, new_t))

        if states:
            cmd = MoveItemsCommand(self.canvas, states)
            cmd.redo()
            self.push_undo(cmd)
