from PyQt5.QtCore import QObject, pyqtSignal
from typing import List, Any

from edit.commands import DeleteItemsCommand, AddItemCommand


class EditManager(QObject):
    # 信号：通知界面更新菜单项可用性
    undoAvailable = pyqtSignal(bool)
    redoAvailable = pyqtSignal(bool)
    cutCopyAvailable = pyqtSignal(bool)
    deleteAvailable = pyqtSignal(bool)
    selectAllAvailable = pyqtSignal(bool)

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas  # 关联画布组件
        self.undo_stack = []  # 撤销栈
        self.redo_stack = []  # 重做栈
        self.has_selection = False  # 是否有选中项

    def push_undo(self, command):
        """将操作压入撤销栈，清空重做栈"""
        self.undo_stack.append(command)
        self.redo_stack = []
        self.undoAvailable.emit(True)
        self.redoAvailable.emit(False)

    def undo(self):
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self.undoAvailable.emit(len(self.undo_stack) > 0)
        self.redoAvailable.emit(True)

    def redo(self):
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)
        self.undoAvailable.emit(True)
        self.redoAvailable.emit(len(self.redo_stack) > 0)

    def set_has_selection(self, has_selection: bool):
        """更新选中状态，触发菜单项可用性变化"""
        self.has_selection = has_selection
        self.cutCopyAvailable.emit(has_selection)
        self.deleteAvailable.emit(has_selection)
        self.selectAllAvailable.emit(not has_selection)

    def cut(self):
        if self.has_selection:
            # 剪切逻辑：暂存选中项 → 删除 → 入撤销栈
            selected = self.canvas.get_selected_items()
            if selected:
                cmd = DeleteItemsCommand(self.canvas, selected)
                self.push_undo(cmd)
                cmd.redo()

    def copy(self):
        if self.has_selection:
            # 复制逻辑：将选中项存入剪贴板（示例为简化，实际需序列化图形数据）
            self.clipboard = self.canvas.get_selected_items()

    def paste(self):
        # 粘贴逻辑：从剪贴板恢复图形 → 入撤销栈
        if hasattr(self, 'clipboard') and self.clipboard:
            for item in self.clipboard:
                cmd = AddItemCommand(self.canvas, item)
                self.push_undo(cmd)
                cmd.redo()

    def delete(self):
        if self.has_selection:
            # 删除逻辑：删除选中项 → 入撤销栈
            selected = self.canvas.get_selected_items()
            if selected:
                cmd = DeleteItemsCommand(self.canvas, selected)
                self.push_undo(cmd)
                cmd.redo()

    def select_all(self):
        # 全选逻辑：选中画布所有图形项
        self.canvas.select_all_items()
        self.set_has_selection(True)