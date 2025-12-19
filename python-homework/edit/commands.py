from typing import List

from PyQt5.QtWidgets import QGraphicsItem, QUndoCommand, QGraphicsTextItem

from ui.graphics_items import EditablePathItem
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
from PyQt5.QtGui import QTransform, QColor
import math

class Command:
    def undo(self):
        raise NotImplementedError

    def redo(self):
        raise NotImplementedError

class AddItemCommand(Command):
    def __init__(self, canvas, item: QGraphicsItem):
        self.canvas = canvas
        self.item = item
        # 标记项当前是否在场景中（如果调用方已经手动添加则保持 True）
        try:
            self.added = (self.item.scene() is not None)
        except Exception:
            self.added = False
        # 描述用于历史面板显示
        try:
            name = item.__class__.__name__
        except Exception:
            name = 'Item'
        self.desc = f"添加: {name}"

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
        # 描述用于历史面板显示
        try:
            count = len(items)
        except Exception:
            count = 0
        self.desc = f"删除: {count} 项"

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


class SetFiducialSizeCommand(Command):
    """更改定位点尺寸的命令（可撤销/重做）"""
    def __init__(self, canvas, new_size: float):
        self.canvas = canvas
        self.fiducial_manager = canvas.fiducial_manager
        self.new_size = float(new_size)
        self.old_size = getattr(self.fiducial_manager, '_fiducial_size', None)
        self.desc = f'定位点尺寸 -> {self.new_size}'

    def redo(self):
        try:
            self.fiducial_manager.set_fiducial_size(self.new_size)
        except Exception:
            pass

    def undo(self):
        try:
            if self.old_size is not None:
                self.fiducial_manager.set_fiducial_size(self.old_size)
        except Exception:
            pass


class AlignItemsCommand(Command):
    """对齐选中项的命令"""
    def __init__(self, canvas, items, align_type):
        self.canvas = canvas
        self.items = items
        self.align_type = align_type
        self.desc = f'对齐: {align_type}'
        self.items_states = []

        # 计算对齐参考线
        if not items:
            return

        # 获取所有项的包围盒
        rects = []
        valid_items = []
        for it in items:
            try:
                rects.append(it.sceneBoundingRect())
                valid_items.append(it)
            except Exception:
                pass
        
        if not rects:
            return

        min_x = min(r.left() for r in rects)
        max_x = max(r.right() for r in rects)
        min_y = min(r.top() for r in rects)
        max_y = max(r.bottom() for r in rects)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        from PyQt5.QtCore import QPointF

        # 计算每个项的新位置
        for it in valid_items:
            try:
                br = it.sceneBoundingRect()
                dx = 0
                dy = 0
                
                if align_type == 'left':
                    dx = min_x - br.left()
                elif align_type == 'right':
                    dx = max_x - br.right()
                elif align_type == 'top':
                    dy = min_y - br.top()
                elif align_type == 'bottom':
                    dy = max_y - br.bottom()
                elif align_type == 'hcenter':
                    # 水平居中对齐：让所有对象在水平方向上居中（即 Y 轴对齐，变成水平一行）
                    # 注意：这与某些软件的定义可能相反，但符合中文语境下的“水平对齐”直觉
                    dy = center_y - br.center().y()
                elif align_type == 'vcenter':
                    # 垂直居中对齐：让所有对象在垂直方向上居中（即 X 轴对齐，变成垂直一列）
                    dx = center_x - br.center().x()
                
                if abs(dx) < 1e-9 and abs(dy) < 1e-9:
                    continue

                old_pos = it.pos()
                new_pos = QPointF(old_pos.x() + dx, old_pos.y() + dy)
                self.items_states.append((it, old_pos, new_pos))

            except Exception:
                continue

    def redo(self):
        for it, old, new in self.items_states:
            try:
                it.setPos(new)
            except Exception:
                continue

    def undo(self):
        for it, old, new in self.items_states:
            try:
                it.setPos(old)
            except Exception:
                continue


# 在 edit/commands.py 中添加图形命令

class AddPathCommand(QUndoCommand):
    """添加路径命令"""

    def __init__(self, canvas, points, color, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.points = points
        self.color = color
        self.path_item = None
        self.setText("添加路径")

    def redo(self):
        """执行/重做添加路径"""
        if not self.path_item:
            self.path_item = EditablePathItem(self.points, self.color)
            self.canvas.scene.addItem(self.path_item)
        else:
            self.canvas.scene.addItem(self.path_item)

    def undo(self):
        """撤销添加路径"""
        if self.path_item:
            self.canvas.scene.removeItem(self.path_item)


class AddTextCommand(QUndoCommand):
    """添加文字命令"""

    def __init__(self, canvas, x, y, text, color, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.text_item = None
        self.setText("添加文字")

    def redo(self):
        if not self.text_item:
            self.text_item = QGraphicsTextItem(self.text)
            self.text_item.setDefaultTextColor(self.color)
            self.text_item.setPos(self.x, self.y)
            self.text_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.text_item.setFlag(QGraphicsItem.ItemIsMovable, True)

        self.canvas.scene.addItem(self.text_item)

    def undo(self):
        if self.text_item:
            self.canvas.scene.removeItem(self.text_item)


class MirrorCommand(Command):
    """对一组图形执行水平或垂直镜像，并支持撤销/重做"""

    def __init__(self, canvas, items: List, horizontal: bool = True):
        self.canvas = canvas
        self.items = items[:]  # 直接引用场景中的项
        self.horizontal = horizontal
        # 存储原始状态：对于路径存点，对于其他项存 transform
        self._orig = []
        for it in self.items:
            if isinstance(it, EditablePathItem):
                self._orig.append(('path', it, it.points()))
            elif isinstance(it, QGraphicsPixmapItem) or isinstance(it, QGraphicsTextItem):
                self._orig.append(('transform', it, it.transform()))
            else:
                # 通用处理，尽可能保存 transform
                try:
                    self._orig.append(('transform', it, it.transform()))
                except Exception:
                    self._orig.append(('unknown', it, None))

    def redo(self):
        for typ, it, state in self._orig:
            if typ == 'path':
                pts = state[:]
                if not pts:
                    continue
                # 使用图形在场景中的包围盒中心作为镜像中轴（按照你的定义）
                try:
                    br = it.sceneBoundingRect()
                    cx = br.center().x()
                    cy = br.center().y()
                except Exception:
                    # 回退到点平均值（兼容性）
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                if self.horizontal:
                    mirrored = [(2 * cx - p[0], p[1]) for p in pts]
                else:
                    mirrored = [(p[0], 2 * cy - p[1]) for p in pts]
                it.set_points(mirrored)
            elif typ == 'transform' and state is not None:
                # 关于项的外接矩形中心进行镜像变换
                try:
                    # 获取当前场景变换（包含 pos）
                    pos = it.pos()
                    m_pos = QTransform()
                    m_pos.translate(pos.x(), pos.y())
                    
                    m_transform = state # it.transform()
                    
                    # 完整的场景变换矩阵
                    m_scene = m_transform * m_pos
                    
                    # 计算镜像中心
                    br = it.sceneBoundingRect()
                    cx = br.center().x()
                    cy = br.center().y()
                    
                    m_mirror = QTransform()
                    m_mirror.translate(cx, cy)
                    if self.horizontal:
                        m_mirror.scale(-1, 1)
                    else:
                        m_mirror.scale(1, -1)
                    m_mirror.translate(-cx, -cy)
                    
                    # 新的场景变换：先应用旧的场景变换，再应用镜像
                    m_scene_new = m_scene * m_mirror
                    
                    # 还原回 transform (保持 pos 不变)
                    # M_transform_new = M_scene_new * M_pos^(-1)
                    m_pos_inv = QTransform()
                    m_pos_inv.translate(-pos.x(), -pos.y())
                    
                    new_transform = m_scene_new * m_pos_inv
                    
                    it.setTransform(new_transform)
                except Exception:
                    continue
            else:
                # unknown: 忽略
                continue

    def undo(self):
        # 恢复原始状态
        for typ, it, state in self._orig:
            try:
                if typ == 'path' and state is not None:
                    it.set_points(state)
                elif typ == 'transform' and state is not None:
                    it.setTransform(state)
            except Exception:
                continue


class MirrorCopyCommand(Command):
    """复制并创建镜像副本（水平放到右侧，垂直放到下方），支持撤销/重做"""

    def __init__(self, canvas, items: List, horizontal: bool = True, gap: float = 5.0):
        self.canvas = canvas
        self.items = items[:]  # 原始项引用
        self.horizontal = horizontal
        self.gap = gap
        self._created = []  # 新建的副本

    def redo(self):
        # 为每个选中项生成一个镜像副本并添加到场景
        for it in self.items:
            try:
                if isinstance(it, EditablePathItem):
                    pts = it.points()
                    if not pts:
                        continue
                    # 使用项的场景包围盒中心作为轴
                    try:
                        br = it.sceneBoundingRect()
                        cx = br.center().x()
                        cy = br.center().y()
                    except Exception:
                        cx = sum(p[0] for p in pts) / len(pts)
                        cy = sum(p[1] for p in pts) / len(pts)
                    if self.horizontal:
                        mirrored = [(2 * cx - p[0], p[1]) for p in pts]
                    else:
                        mirrored = [(p[0], 2 * cy - p[1]) for p in pts]
                    # 计算移动量，使副本出现在原图右侧或下方
                    xs = [p[0] for p in mirrored]
                    ys = [p[1] for p in mirrored]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    obr = it.sceneBoundingRect()
                    if self.horizontal:
                        shift_x = obr.right() - min_x + self.gap
                        shifted = [(x + shift_x, y) for (x, y) in mirrored]
                    else:
                        shift_y = obr.bottom() - min_y + self.gap
                        shifted = [(x, y + shift_y) for (x, y) in mirrored]
                    new_item = EditablePathItem(shifted, it._color if hasattr(it, '_color') else QColor(0, 0, 0), smooth=it._smooth if hasattr(it, '_smooth') else False)
                    self.canvas.scene.addItem(new_item)
                    self._created.append(new_item)

                elif isinstance(it, QGraphicsPixmapItem):
                    pix = it.pixmap()
                    new_item = QGraphicsPixmapItem(pix)
                    # 复制 transform 并应用镜像
                    try:
                        br = it.sceneBoundingRect()
                        cx = br.center().x()
                        cy = br.center().y()
                        m = QTransform()
                        m.translate(cx, cy)
                        if self.horizontal:
                            m.scale(-1, 1)
                        else:
                            m.scale(1, -1)
                        m.translate(-cx, -cy)
                        new_item.setTransform(m * it.transform())
                    except Exception:
                        # fallback: mirror by setting transform around item's pos
                        try:
                            if self.horizontal:
                                new_item.setTransform(QTransform(-1, 0, 0, 1, 0, 0))
                            else:
                                new_item.setTransform(QTransform(1, 0, 0, -1, 0, 0))
                        except Exception:
                            pass
                    # 放置位置调整：将副本移动到右侧或下方
                    obr = it.sceneBoundingRect()
                    nbr = new_item.boundingRect()
                    # convert to scene coords: use obr
                    if self.horizontal:
                        dx = obr.right() - (obr.left()) + self.gap
                        new_item.setPos(it.pos().x() + dx, it.pos().y())
                    else:
                        dy = obr.bottom() - (obr.top()) + self.gap
                        new_item.setPos(it.pos().x(), it.pos().y() + dy)
                    self.canvas.scene.addItem(new_item)
                    self._created.append(new_item)

                elif isinstance(it, QGraphicsTextItem):
                    text = it.toPlainText()
                    new_item = QGraphicsTextItem(text)
                    new_item.setDefaultTextColor(it.defaultTextColor())
                    new_item.setFont(it.font())
                    # mirror transform similar to pixmap
                    try:
                        br = it.sceneBoundingRect()
                        cx = br.center().x()
                        cy = br.center().y()
                        m = QTransform()
                        m.translate(cx, cy)
                        if self.horizontal:
                            m.scale(-1, 1)
                        else:
                            m.scale(1, -1)
                        m.translate(-cx, -cy)
                        new_item.setTransform(m * it.transform())
                    except Exception:
                        pass
                    obr = it.sceneBoundingRect()
                    if self.horizontal:
                        dx = obr.right() - obr.left() + self.gap
                        new_item.setPos(it.pos().x() + dx, it.pos().y())
                    else:
                        dy = obr.bottom() - obr.top() + self.gap
                        new_item.setPos(it.pos().x(), it.pos().y() + dy)
                    self.canvas.scene.addItem(new_item)
                    self._created.append(new_item)
                else:
                    # 其它类型：尝试复制 transform + clone via sceneBoundingRect placement
                    try:
                        # 最简单的尝试：不复制，跳过
                        continue
                    except Exception:
                        continue
            except Exception:
                continue

    def undo(self):
        for it in list(self._created):
            try:
                self.canvas.scene.removeItem(it)
            except Exception:
                pass
        self._created = []


class MoveItemsCommand(Command):
    """移动或修改项（位置/点/transform）。

    items_states: list of tuples (typ, item, old_state, new_state)
    typ == 'path' -> state is points list
    typ == 'pos' -> state is QPointF (pos)
    typ == 'transform' -> state is QTransform
    """
    def __init__(self, canvas, items_states):
        self.canvas = canvas
        self.items_states = items_states
        self.desc = '移动/修改 项'

    def redo(self):
        from PyQt5.QtCore import QPointF
        for typ, it, old, new in self.items_states:
            try:
                if typ == 'path':
                    it.set_points(new)
                elif typ == 'pos':
                    it.setPos(new)
                elif typ == 'transform':
                    it.setTransform(new)
            except Exception:
                continue

    def undo(self):
        for typ, it, old, new in self.items_states:
            try:
                if typ == 'path':
                    it.set_points(old)
                elif typ == 'pos':
                    it.setPos(old)
                elif typ == 'transform':
                    it.setTransform(old)
            except Exception:
                continue


class ScaleCommand(Command):
    """缩放所选项的命令：保存旧状态与新状态"""
    def __init__(self, canvas, items_states, factor=None):
        self.canvas = canvas
        self.items_states = items_states
        self.desc = '缩放 项'

    def redo(self):
        for typ, it, old, new in self.items_states:
            try:
                if typ == 'path':
                    it.set_points(new)
                elif typ == 'transform':
                    it.setTransform(new)
            except Exception:
                continue
    
    def undo(self):
        for typ, it, old, new in self.items_states:
            try:
                if typ == 'path':
                    it.set_points(old)
                elif typ == 'transform':
                    it.setTransform(old)
            except Exception:
                continue


class RotateCommand(Command):
    """旋转所选项的命令：保存旧状态与新状态

    items_states: list of tuples (typ, item, old_state, new_state)
    typ == 'path' -> state is points list
    typ == 'transform' -> state is QTransform
    """
    def __init__(self, canvas, items_states, angle=None):
        self.canvas = canvas
        self.items_states = items_states
        self.desc = '旋转 项'

    def redo(self):
        for typ, it, old, new in self.items_states:
            try:
                if typ == 'path':
                    it.set_points(new)
                elif typ == 'transform':
                    it.setTransform(new)
            except Exception:
                continue

    def undo(self):
        for typ, it, old, new in self.items_states:
            try:
                if typ == 'path':
                    it.set_points(old)
                elif typ == 'transform':
                    it.setTransform(old)
            except Exception:
                continue


class ChangeColorCommand(QUndoCommand):
    """修改选中项颜色的命令"""
    def __init__(self, canvas, items_states):
        """
        items_states: list of tuples (typ, item, old_val, new_val)
        - typ='path': old_val/new_val 是 QPen
        - typ='text': old_val/new_val 是 QColor
        """
        self.canvas = canvas
        self.items_states = items_states
        self.desc = '修改颜色'

    def redo(self):
        for typ, item, old_val, new_val in self.items_states:
            try:
                if typ == 'path':
                    item.setPen(new_val)
                elif typ == 'text':
                    item.setDefaultTextColor(new_val)
            except Exception:
                pass
        self.canvas.scene.update()

    def undo(self):
        for typ, item, old_val, new_val in self.items_states:
            try:
                if typ == 'path':
                    item.setPen(old_val)
                elif typ == 'text':
                    item.setDefaultTextColor(old_val)
            except Exception:
                pass
        self.canvas.scene.update()
