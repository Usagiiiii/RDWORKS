from .commands import Command
from ui.graphics_items import TextGraphicsItem

class ChangeTextCommand(Command):
    """Command to change text content and settings"""
    def __init__(self, canvas, item: TextGraphicsItem, old_text, old_settings, new_text, new_settings):
        self.canvas = canvas
        self.item = item
        self.old_text = old_text
        self.old_settings = old_settings
        self.new_text = new_text
        self.new_settings = new_settings
        self.desc = f"修改文字: {self.new_text}"

    def redo(self):
        self.item.text_data = self.new_text
        self.item.settings = self.new_settings
        self.item.rebuild_path()
        self.item.update()
        if hasattr(self.canvas, 'update_selection_handles'):
            self.canvas.update_selection_handles()

    def undo(self):
        self.item.text_data = self.old_text
        self.item.settings = self.old_settings
        self.item.rebuild_path()
        self.item.update()
        if hasattr(self.canvas, 'update_selection_handles'):
            self.canvas.update_selection_handles()
