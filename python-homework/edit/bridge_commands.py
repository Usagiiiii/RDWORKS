from PyQt5.QtWidgets import QGraphicsItem, QUndoCommand

class ReplaceItemsCommand(QUndoCommand):
    """Replaces a set of items with another set (e.g. for Bridge operation)"""
    def __init__(self, scene, old_items, new_items, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.old_items = old_items
        self.new_items = new_items
        self.setText(f"Wait Replace {len(old_items)} items with {len(new_items)}")
        self.executed = False

    def redo(self):
        # Remove old, add new
        for item in self.old_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        for item in self.new_items:
            if item.scene() != self.scene:
                self.scene.addItem(item)
        self.executed = True

    def undo(self):
        # Remove new, add old
        for item in self.new_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        for item in self.old_items:
            if item.scene() != self.scene:
                self.scene.addItem(item)
        self.executed = False
