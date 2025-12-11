import logging

from PyQt5.QtCore import QObject, pyqtSignal
from typing import List, Any
logger = logging.getLogger(__name__)
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem

from edit.commands import DeleteItemsCommand, AddItemCommand


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