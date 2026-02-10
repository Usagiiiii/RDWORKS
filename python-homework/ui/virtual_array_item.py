from PyQt5.QtWidgets import QGraphicsItemGroup
from PyQt5.QtGui import QPainterPath

class VirtualArrayItem(QGraphicsItemGroup):
    """
    虚阵列组合项。
    包含：
    1. 实线部分（原对象的克隆）：这一部分构成此 Item 的响应区域 (Shape)。
    2. 虚线部分（阵列克隆）：这一部分不可选，不参与碰撞检测，但跟随移动。
    """
    def __init__(self, real_items, virtual_items, parent=None):
        super().__init__(parent)
        
        # 将所有项添加为子项
        for item in real_items:
            # 确保是顶级项（相对于 Group）
            item.setParentItem(self) # 这会自动添加到 group 中吗？QGraphicsItemGroup.addToGroup 是标准做法
            # 但是 addToGroup 会改变 item 的 pos 使其保持 visual pos。
            # 这里我们假设传入的 items 已经设置好了相对于 Group 原点（通常是 (0,0)）的位置？
            # 或者我们应该在这里调整。
            # 为了简单，我们使用 setParentItem，并假设调用者已经处理好坐标。
            # QGraphicsItemGroup 会自动计算 boundingRect 为所有 children 的并集。
            # 但是我们要重写 shape。
            pass
            
        for item in virtual_items:
            item.setParentItem(self)
        
        self.real_items = real_items
        self.virtual_items = virtual_items
        
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        
    def shape(self):
        # Override shape to include ONLY real items
        path = QPainterPath()
        for item in self.real_items:
            # Map child shape to group coordinate system
            child_shape = item.shape()
            child_transform = item.transform()
            child_pos = item.pos()
            
            # 组合变换：移动 + 自身变换
            # item.shape() 是在 item 本地坐标系。
            # 我们需要 mapToParent。
            
            mapped_path = self.mapFromItem(item, child_shape)
            path.addPath(mapped_path)
            
        return path

    def paint(self, painter, option, widget=None):
        # Group 默认不绘制自身，只绘制子项。
        # 这里不需要做任何事，除非我们想画一些调试框。
        pass
