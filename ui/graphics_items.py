#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图形项定义 - 避免循环导入
"""

from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainterPath, QPen, QColor, QBrush, QMouseEvent


class EditablePathItem(QGraphicsPathItem):
    def __init__(self, pts, color: QColor, smooth: bool = False):
        super().__init__()
        self._points = pts[:]
        self._handles = []
        self._color = color
        self._smooth = smooth
        # 标记当前是否处于节点编辑模式（决定是否显示/重建锚点句柄）
        self._node_edit_enabled = False
        # 记录上一次拖动时项的目标位置（用于增量计算）；首帧置为 None，避免首次跳变
        self._last_item_pos = None
        self._update_path()
        # 允许选择、拖动，并发送几何变化通知（用于在 itemChange 中捕获位移）
        from PyQt5.QtWidgets import QGraphicsItem
        self.setFlags(QGraphicsPathItem.ItemIsSelectable | QGraphicsPathItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        # 用于记录拖动前的原始点（用于生成移动命令）
        self._move_orig_points = None

    def _update_path(self):
        path = QPainterPath()
        if not self._points:
            self.setPath(path)
            return

        if not self._smooth or len(self._points) < 2:
            path.moveTo(self._points[0][0], self._points[0][1])
            for (x, y) in self._points[1:]:
                path.lineTo(x, y)
        else:
            pts = [(float(x), float(y)) for (x, y) in self._points]
            n = len(pts)
            if n == 2:
                path.moveTo(pts[0][0], pts[0][1])
                path.lineTo(pts[1][0], pts[1][1])
            else:
                ext = [pts[0]] + pts + [pts[-1]]
                path.moveTo(pts[0][0], pts[0][1])
                for i in range(1, n):
                    p0 = ext[i - 1]
                    p1 = ext[i]
                    p2 = ext[i + 1]
                    p3 = ext[i + 2]
                    cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
                    cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
                    cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
                    cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
                    path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        self.setPath(path)
        pen = QPen(self._color)
        pen.setCosmetic(True)
        pen.setWidthF(1.2)
        self.setPen(pen)

    def points(self):
        return self._points[:]

    def set_points(self, pts):
        self._points = pts[:]
        self._update_path()
        # 只有在节点编辑模式开启时才显示/重建锚点句柄
        if getattr(self, '_node_edit_enabled', False):
            self._rebuild_handles()

    def enable_node_edit(self, on: bool):
        # 切换节点编辑模式并相应地重建或清理锚点句柄
        self._node_edit_enabled = bool(on)
        if on:
            self._rebuild_handles()
        else:
            self._clear_handles()

    def _clear_handles(self):
        for h in self._handles:
            s = h.scene()
            if s:
                s.removeItem(h)
        self._handles.clear()

    def _rebuild_handles(self):
        self._clear_handles()
        if not self._points:
            return
        for idx, (x, y) in enumerate(self._points):
            h = _DragHandle(self, idx, x, y)
            self._handles.append(h)

    def update_point(self, idx: int, x: float, y: float):
        if 0 <= idx < len(self._points):
            self._points[idx] = (x, y)
            self._update_path()

    def itemChange(self, change, value):
        """当项被移动时：允许项正常随鼠标移动（返回新的目标位置）。

        我们不在拖动过程中修改点坐标，避免鼠标与图形脱节；
        在 mouseReleaseEvent 中一次性将累计位移应用到点坐标并把 pos 复位为 (0,0)。
        """
        from PyQt5.QtWidgets import QGraphicsItem
        try:
            if change == QGraphicsItem.ItemPositionChange:
                # 计算本次拖动的增量，让节点句柄在拖动过程中跟随显示
                try:
                    old_pos = self.pos()
                    new_pos = value
                    dx = float(new_pos.x() - old_pos.x())
                    dy = float(new_pos.y() - old_pos.y())
                    if (dx or dy) and getattr(self, '_node_edit_enabled', False) and self._handles:
                        for h in self._handles:
                            try:
                                h.moveBy(dx, dy)
                            except Exception:
                                pass
                except Exception:
                    pass
                return value
        except Exception:
            pass
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QMouseEvent):
        try:
            # 记录拖动前的点状态与项位置
            self._move_orig_points = self.points()
            self._press_item_pos = self.pos()
        except Exception:
            self._move_orig_points = None
            self._press_item_pos = QPointF(0, 0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """释放鼠标时，将累计的项位移折算到点坐标，并把项位置复位。

        这样可保持外部接口约定：路径点使用场景坐标，项的 pos 恒为初始值（通常为 0,0）。
        同时把本次操作纳入撤销/重做历史。
        """
        try:
            # 计算从按下到释放的累计位移
            press_pos = getattr(self, '_press_item_pos', QPointF(0, 0))
            cur_pos = self.pos()
            dx = float(cur_pos.x() - press_pos.x())
            dy = float(cur_pos.y() - press_pos.y())

            if dx != 0.0 or dy != 0.0:
                # 记录旧点，并生成新点（折算累计位移到点坐标）
                old_points = getattr(self, '_move_orig_points', self.points())
                new_points = [(p[0] + dx, p[1] + dy) for p in old_points]

                # 应用新点
                self.set_points(new_points)
                # 将项位置复位到按下时（通常为 0,0）
                try:
                    self.setPos(press_pos)
                except Exception:
                    pass

                # 若在节点编辑模式下，同步重建/平移句柄（set_points 已处理重建）

                # 推入撤销/重做历史
                try:
                    views = self.scene().views()
                    edit_mgr = None
                    canvas = None
                    for v in views:
                        if hasattr(v, 'edit_manager'):
                            edit_mgr = getattr(v, 'edit_manager')
                            canvas = v
                            break
                    if edit_mgr is not None:
                        from edit.commands import MoveItemsCommand
                        items_states = [('path', self, old_points, new_points)]
                        cmd = MoveItemsCommand(canvas, items_states)
                        edit_mgr.push_undo(cmd)
                except Exception:
                    pass
        except Exception:
            pass
        super().mouseReleaseEvent(event)


class _DragHandle(QGraphicsEllipseItem):
    def __init__(self, owner: EditablePathItem, idx: int, x: float, y: float):
        r = 3.5
        super().__init__(x - r, y - r, 2 * r, 2 * r)
        self._owner = owner
        self._idx = idx
        pen = QPen(QColor(0, 120, 255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(0, 120, 255, 120)))
        self.setZValue(10)
        self.setFlags(QGraphicsEllipseItem.ItemIsMovable | QGraphicsEllipseItem.ItemIsSelectable)
        self.setCursor(Qt.OpenHandCursor)
        owner.scene().addItem(self)

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = self.mapToScene(e.pos())
        x, y = pos.x(), pos.y()
        self._owner.update_point(self._idx, x, y)
        super().mouseMoveEvent(e)
    
    def mousePressEvent(self, event: QMouseEvent):
        try:
            # 记录操作前的点集合
            self._orig_points = self._owner.points()
        except Exception:
            self._orig_points = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            new_points = self._owner.points()
            old_points = getattr(self, '_orig_points', None)
            if old_points is not None and new_points != old_points:
                # 查找拥有 edit_manager 的 view
                try:
                    views = self.scene().views()
                    edit_mgr = None
                    canvas = None
                    for v in views:
                        if hasattr(v, 'edit_manager'):
                            edit_mgr = getattr(v, 'edit_manager')
                            canvas = v
                            break
                    if edit_mgr is not None:
                        from edit.commands import MoveItemsCommand
                        items_states = [('path', self._owner, old_points, new_points)]
                        cmd = MoveItemsCommand(canvas, items_states)
                        edit_mgr.push_undo(cmd)
                except Exception:
                    pass
        except Exception:
            pass
        super().mouseReleaseEvent(event)