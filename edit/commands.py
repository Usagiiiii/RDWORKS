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