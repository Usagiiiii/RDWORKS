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
        # 标记当前是否处于节点编辑模式
        self._node_edit_enabled = False
        self._update_path()
        self.setFlags(QGraphicsPathItem.ItemIsSelectable | QGraphicsPathItem.ItemIsMovable)
        # 用于记录拖动前的原始点
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
        # 如果节点编辑模式开启，同步更新所有句柄的位置
        if getattr(self, '_node_edit_enabled', False) and self._handles:
            self._update_handles_positions()

    def points(self):
        return self._points[:]

    def set_points(self, pts):
        self._points = pts[:]
        self._update_path()
        # 只有在节点编辑模式开启时才显示/重建锚点句柄
        if getattr(self, '_node_edit_enabled', False):
            self._rebuild_handles()

    def set_color(self, color: QColor):
        """设置路径颜色"""
        self._color = color
        self._update_path()

    def set_color(self, color: QColor):
        self._color = color
        self._update_path()

    def color(self):
        return self._color

    def enable_node_edit(self, on: bool):
        # 切换节点编辑模式并相应地重建或清理锚点句柄
        self._node_edit_enabled = bool(on)
        if on:
            self._rebuild_handles()
        else:
            self._clear_handles()

    def _clear_handles(self):
        for h in self._handles:
            # 如果是子项，可以直接清理或者从 scene 移除
            if h.scene():
                h.scene().removeItem(h)
            h.setParentItem(None)
        self._handles.clear()

    def _rebuild_handles(self):
        self._clear_handles()
        if not self._points:
            return
        for idx, (x, y) in enumerate(self._points):
            h = _DragHandle(self, idx, x, y)
            self._handles.append(h)

    def _update_handles_positions(self):
        """更新所有句柄的位置以匹配当前的 _points"""
        if not self._handles or not self._points:
            return

        for idx, handle in enumerate(self._handles):
            if idx < len(self._points):
                x, y = self._points[idx]
                # 直接设置句柄位置，使其中心对准点 (x, y)
                handle.setPos(x, y)

    def update_point(self, idx: int, x: float, y: float):
        if 0 <= idx < len(self._points):
            self._points[idx] = (x, y)
            self._update_path()

    def itemChange(self, change, value):
        # 移除位置锁定逻辑，允许 Item 正常移动
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
            # 处理拖动后的坐标合并
            current_pos = self.pos()
            if not current_pos.isNull() and (current_pos.x() != 0 or current_pos.y() != 0):
                # 将 Item 的位移应用到所有点上
                dx, dy = current_pos.x(), current_pos.y()
                self._points = [(p[0] + dx, p[1] + dy) for p in self._points]
                # 重置 Item 位置为 (0, 0)
                self.setPos(0, 0)
                # 更新路径和句柄
                self._update_path()

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
        # 创建椭圆，初始位置在 (0, 0)，大小为 2r x 2r
        super().__init__(-r, -r, 2 * r, 2 * r, parent=owner)
        self._owner = owner
        self._idx = idx
        pen = QPen(QColor(0, 120, 255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(0, 120, 255, 120)))
        self.setZValue(10)
        # 不设置 ItemIsMovable，避免 Qt 自动移动句柄
        self.setFlags(QGraphicsEllipseItem.ItemIsSelectable)
        self.setCursor(Qt.OpenHandCursor)
        # 设置句柄的场景位置
        # 由于现在是子项，如果不考虑 Item 移动，则相对于父项的位置就是场景位置
        # 如果父项移动了，子项会自动跟随
        self.setPos(x, y)

    def mouseMoveEvent(self, e: QMouseEvent):
        # 获取鼠标在场景中的位置
        pos = self.mapToScene(e.pos())
        x, y = pos.x(), pos.y()
        # 更新拥有者的点坐标
        self._owner.update_point(self._idx, x, y)
        # 手动更新句柄位置（因为没有设置 ItemIsMovable）
        self.setPos(x, y)

    def mousePressEvent(self, event: QMouseEvent):
        try:
            # 记录操作前的点集合
            self._orig_points = self._owner.points()
        except Exception:
            self._orig_points = None
        # 接受事件但不调用 super，避免默认的移动行为
        event.accept()

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
        event.accept()