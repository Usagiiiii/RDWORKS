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
        # 记录上一次拖动请求的位置（用于增量计算）
        self._last_pos = QPointF(0, 0)
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
        """当项被移动时，将位移应用到内部点集合，保持点为场景坐标。

        实现方法：在接收到 ItemPositionChange（拖动前的目标位置）时，计算相对于
        当前记录的旧位置的位移(delta)，将 delta 加到所有点上，然后返回 (0,0)
        以保持项本身的位置不变（因为点已包含位移）。这样导出会使用更新后的
       点坐标，而不会因为项的 pos 而造成双重平移。
        """
        from PyQt5.QtWidgets import QGraphicsItem
        try:
            if change == QGraphicsItem.ItemPositionChange:
                new_pos = value
                old_pos = getattr(self, '_last_pos', QPointF(0, 0))
                # 计算位移
                dx = float(new_pos.x() - old_pos.x())
                dy = float(new_pos.y() - old_pos.y())
                if dx != 0.0 or dy != 0.0:
                    # 将位移应用到所有存储的点（假定 _points 存储的是场景坐标）
                    try:
                        self._points = [(p[0] + dx, p[1] + dy) for p in self._points]
                        # 更新路径并保持项位置为 (0,0)
                        self._update_path()
                        # --- 新增：如果当前处于节点编辑模式，同时平移所有节点句柄 ---
                        if getattr(self, '_node_edit_enabled', False) and self._handles:
                            try:
                                for h in self._handles:
                                    h.moveBy(dx, dy)
                            except Exception:
                                # 如果平移句柄失败，至少不要影响正常拖动
                                pass
                    except Exception:
                        pass
                    # 记录本次请求的位置作为 last_pos（用于下一次增量计算），
                    # 然后将项位置重置为 (0,0) （因为点已被更新到场景坐标）
                    self._last_pos = QPointF(new_pos)
                    return QPointF(0, 0)
            # 在其他情况下，保留默认行为
        except Exception:
            pass
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QMouseEvent):
        try:
            # 记录拖动前的点状态
            self._move_orig_points = self.points()
        except Exception:
            self._move_orig_points = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            new_points = self.points()
            old_points = getattr(self, '_move_orig_points', None)
            if old_points is not None and new_points != old_points:
                # 寻找拥有 edit_manager 的 view
                try:
                    views = self.scene().views()
                    edit_mgr = None
                    for v in views:
                        if hasattr(v, 'edit_manager'):
                            edit_mgr = getattr(v, 'edit_manager')
                            canvas = v
                            break
                    if edit_mgr is not None:
                        from edit.commands import MoveItemsCommand
                        items_states = [('path', self, old_points, new_points)]
                        cmd = MoveItemsCommand(canvas, items_states)
                        # 移动已完成，直接将命令记录到历史
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