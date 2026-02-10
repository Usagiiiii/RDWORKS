from edit.commands import Command

class MergeItemsCommand(Command):
    def __init__(self, canvas, item1, item2, merged_item):
        self.canvas = canvas
        self.item1 = item1
        self.item2 = item2
        self.merged_item = merged_item
        self.desc = "合并相连线"
        
        # 标记是否已经合并状态
        self.merged = False

    def redo(self):
        if not self.merged:
            scene = self.canvas.scene
            # Remove old
            if self.item1.scene() == scene: scene.removeItem(self.item1)
            if self.item2.scene() == scene: scene.removeItem(self.item2)
            # Add new
            if self.merged_item.scene() != scene: scene.addItem(self.merged_item)
            
            self.merged_item.setSelected(True)
            self.merged = True
            
    def undo(self):
        if self.merged:
            scene = self.canvas.scene
            # Remove new
            if self.merged_item.scene() == scene: scene.removeItem(self.merged_item)
            # Restore old
            if self.item1.scene() != scene: scene.addItem(self.item1)
            if self.item2.scene() != scene: scene.addItem(self.item2)
            
            self.item1.setSelected(True)
            self.item2.setSelected(True)
            self.merged = False
