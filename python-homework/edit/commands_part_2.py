
class SmoothItemCommand(Command):
    """Command for applying curve smoothing"""
    def __init__(self, item, new_points, is_smooth):
        self.item = item
        self.new_points = new_points # list of (x,y)
        self.is_smooth = is_smooth
        self.old_data = item.get_path_data() 
        self.old_smooth = item._smooth
        self.desc = "曲线平滑"

    def redo(self):
        # Apply smoothing logic
        self.item.set_points(self.new_points)
        self.item._smooth = self.is_smooth
        
        # We force all segments to match the smooth flag property
        # This ensures the "fitting property" is applied to all segments
        count = len(self.new_points)
        seg_len = max(0, count - 1)
        new_type_val = 1 if self.is_smooth else 0
        self.item._segment_types = [new_type_val] * seg_len
        # Control points are likely invalid for new points, clear them
        self.item._control_points = {}
        
        self.item._update_path()
        if getattr(self.item, '_node_edit_enabled', False):
             self.item._rebuild_handles()

    def undo(self):
        self.item.set_path_data(self.old_data)
        self.item._smooth = self.old_smooth
        self.item._update_path()
