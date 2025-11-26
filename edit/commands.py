from typing import List

from PyQt5.QtWidgets import QGraphicsItem

class Command:
    def undo(self):
        raise NotImplementedError

    def redo(self):
        raise NotImplementedError

class AddItemCommand(Command):
    def __init__(self, canvas, item: QGraphicsItem):
        self.canvas = canvas
        self.item = item
        self.added = False

    def redo(self):
        if not self.added:
            self.canvas.scene.addItem(self.item)
            self.added = True

    def undo(self):
        if self.added:
            self.canvas.scene.removeItem(self.item)
            self.added = False

class DeleteItemsCommand(Command):
    def __init__(self, canvas, items: List[QGraphicsItem]):
        self.canvas = canvas
        self.items = items
        self.deleted = False

    def redo(self):
        if not self.deleted:
            for item in self.items:
                self.canvas.scene.removeItem(item)
            self.deleted = True

    def undo(self):
        if self.deleted:
            for item in self.items:
                self.canvas.scene.addItem(item)
            self.deleted = False

# 在 commands.py 中添加定位点命令类
class AddFiducialCommand(Command):
    def __init__(self, canvas, point, shape):
        self.canvas = canvas
        self.point = point
        self.shape = shape
        self.fiducial_manager = canvas.fiducial_manager
        self.added = False

    def redo(self):
        if not self.added:
            self.fiducial_manager.add_fiducial(self.point, self.shape)
            self.added = True

    def undo(self):
        if self.added:
            self.fiducial_manager.remove_fiducial()
            self.added = False

class RemoveFiducialCommand(Command):
    def __init__(self, canvas):
        self.canvas = canvas
        self.fiducial_manager = canvas.fiducial_manager
        # 保存当前定位点信息以便撤销
        current_fiducial = self.fiducial_manager.get_fiducial()
        self.old_point = current_fiducial[0] if current_fiducial else None
        self.old_shape = current_fiducial[1] if current_fiducial else None
        self.removed = False

    def redo(self):
        if not self.removed and self.old_point:
            self.fiducial_manager.remove_fiducial()
            self.removed = True

    def undo(self):
        if self.removed and self.old_point:
            self.fiducial_manager.add_fiducial(self.old_point, self.old_shape)
            self.removed = False