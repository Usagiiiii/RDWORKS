#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图形项定义 - 避免循环导入
"""


from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem, QGraphicsSimpleTextItem
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainterPath, QPen, QColor, QBrush, QMouseEvent, QFont, QTransform, QFontMetrics, QFontDatabase, QFontMetricsF

import math
import traceback

class EditablePathItem(QGraphicsPathItem):
    def __init__(self, pts, color: QColor, smooth: bool = False):
        super().__init__()
        self._points = pts[:]
        # 初始化段类型: 1=曲线, 0=直线 (长度对应 segment 数量, 即 len(pts)-1)
        self._smooth = smooth
        seg_len = max(0, len(pts) - 1)
        self._segment_types = [1 if smooth else 0] * seg_len
        # Explicit Cubic Bezier Control Points map: index -> (cp1, cp2)
        # cp1 is control point near points[index], cp2 is near points[index+1]
        self._control_points = {}

        self._handles = []
        self._color = color

        self._smooth = smooth
        self._straight_close = False # 新增：是否使用直线强制闭合

        self._orig_color = color # 备份原始颜色

        # 标记当前是否处于节点编辑模式
        self._node_edit_enabled = False
        # 节点编辑状态变量
        self._suggested_node_visual = None
        self._suggested_segment_index = -1
        self._suggested_point_pos = None
        self._selected_handle_indices = set()
        
        self._update_path()
        self.setFlags(QGraphicsPathItem.ItemIsSelectable | QGraphicsPathItem.ItemIsMovable)
        # 用于记录拖动前的原始点
        self._move_orig_points = None

    def setPen(self, pen):
        super().setPen(pen)
        # 只有在非节点编辑模式下才更新 _color，避免被选中时的红色覆盖原始颜色
        if not getattr(self, '_node_edit_enabled', False):
            self._color = pen.color()
            self._orig_color = pen.color()

    def _update_path(self):
        path = QPainterPath()
        if not self._points:
            self.setPath(path)
            # update pen anyway
            return

        # Ensure segment types length matches (auto-repair if mismatch due to external modification)
        target_len = max(0, len(self._points) - 1)
        if len(self._segment_types) != target_len:
            if len(self._segment_types) < target_len:
                 # Extend with default smoothness
                 extra = [1 if self._smooth else 0] * (target_len - len(self._segment_types))
                 self._segment_types.extend(extra)
            else:
                 # Truncate
                 self._segment_types = self._segment_types[:target_len]
        
        if target_len == 0:
             if self._points:
                 path.moveTo(self._points[0][0], self._points[0][1])
        else:
            pts = [(float(x), float(y)) for (x, y) in self._points]

            
            # 检查是否开启了“直线闭合”模式
            use_straight_close = getattr(self, '_straight_close', False)
            closed_pt = None
            original_pts = pts.copy()  # 保存原始点集，用于后续恢复

            # 如果开启了直线闭合，且确实是闭合形状（首尾距离极小），且点数足够多
            if use_straight_close and len(pts) > 2:
                # 检查首尾是否重合（距离小于极小值）
                dx = pts[0][0] - pts[-1][0]
                dy = pts[0][1] - pts[-1][1]
                if math.hypot(dx, dy) < 1e-9:
                    closed_pt = pts[-1]
                    pts = pts[:-1]  # 暂时移除闭合点，保留尖角
                    
                    # 适配点集变化：同步更新分段相关属性（避免索引错位）
                    if hasattr(self, '_segment_types') and len(self._segment_types) > 0:
                        self._segment_types = self._segment_types[:-1]  # 分段数减少1
                    if hasattr(self, '_control_points') and len(self._control_points) > 0:
                        # 移除最后一个分段的自定义控制点（仅保留有效索引）
                        self._control_points = {k: v for k, v in self._control_points.items() if k < len(pts)-1}

            # ====================== 保留右侧核心：分段类型控制 ======================
            if len(pts) < 2:
                # 点数不足，无法绘制（边界保护）
                pass
            else:
                path.moveTo(pts[0][0], pts[0][1])
                # Catmull-Rom 扩展点（兼容分段遍历，统一索引逻辑）
                ext = [pts[0]] + pts + [pts[-1]]
                # 统一分段数：点数-1（n个点对应n-1个分段），兼容target_len
                target_len = len(pts) - 1

                for i in range(target_len):
                    # 1. 获取当前分段类型（兼容边界：避免索引越界）
                    is_curve = True  # 默认是曲线
                    if hasattr(self, '_segment_types') and i < len(self._segment_types):
                        is_curve = self._segment_types[i]
                    
                    if not is_curve:
                        # 分段类型：直线段
                        path.lineTo(pts[i+1][0], pts[i+1][1])
                    
                    elif hasattr(self, '_control_points') and i in self._control_points:
                        # 分段类型：自定义贝塞尔曲线（显式控制点）
                        cp1, cp2 = self._control_points[i]
                        path.cubicTo(cp1[0], cp1[1], cp2[0], cp2[1], pts[i+1][0], pts[i+1][1])
                    
                    else:
                        # 分段类型：自动 Catmull-Rom 曲线（兜底逻辑）
                        # 索引保护：避免ext越界（核心修复冲突点）
                        p0 = ext[i] if i < len(ext) else pts[i]
                        p1 = ext[i+1] if (i+1) < len(ext) else pts[i]
                        p2 = ext[i+2] if (i+2) < len(ext) else pts[i+1]
                        p3 = ext[i+3] if (i+3) < len(ext) else pts[i+1]
                        
                        # Catmull-Rom 转贝塞尔曲线的核心计算（保留原公式）
                        cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
                        cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
                        cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
                        cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
                        
                        path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])

            # ====================== 保留左侧核心：直线闭合处理 ======================
            if closed_pt:
                # 用直线连接回闭合点，完成闭合（保留尖角）
                path.lineTo(closed_pt[0], closed_pt[1])
                # 恢复原始点集（避免影响后续逻辑）
                pts = original_pts

        self.setPath(path)
        
        # 根据模式决定颜色
        current_color = QColor(Qt.red) if getattr(self, '_node_edit_enabled', False) else self._color
        pen = QPen(current_color)
        pen.setCosmetic(True)
        pen.setWidthF(1.2)
        # 直接调用父类 setPen 避免递归或逻辑循环
        super().setPen(pen)
        
        # 如果节点编辑模式开启，同步更新所有句柄的位置
        if getattr(self, '_node_edit_enabled', False) and self._handles:
            self._update_handles_positions()

    def points(self):
        return self._points[:]

    def set_points(self, pts):
        self._points = pts[:]
        # Invalidate control points cache if size changes mismatch (simple safety check)
        # Note: Ideally we should preserve CPs if points just moved, but if count changes logic is tricky.
        # This function is used by Undo, so we assume full state restoration is handled by undo command usually,
        # but here we just update points.
        # If points count changed, we might have dangling CPs in dict, but that's handled in `_update_path`.
        self._update_path()
        # 只有在节点编辑模式开启时才显示/重建锚点句柄
        if getattr(self, '_node_edit_enabled', False):
            self._rebuild_handles()

    def get_path_data(self):
        """返回路径完整数据(点,段类型,控制点)"""
        cp = {k: v for k, v in self._control_points.items()}
        return (self._points[:], self._segment_types[:], cp)

    def set_path_data(self, data):
        """设置路径完整数据"""
        pts, segs, cps = data
        self._points = pts[:]
        self._segment_types = segs[:]
        self._control_points = {k: v for k, v in cps.items()}
        self._update_path()
        if getattr(self, '_node_edit_enabled', False):
            self._rebuild_handles()

    @staticmethod
    def reverse_path_data(data):
        """反转路径数据"""
        pts, segs, cps = data
        n = len(pts)
        if n < 2:
            return (pts[::-1], [], {})
            
        new_pts = pts[::-1]
        new_segs = segs[::-1]
        new_cps = {}
        
        max_seg_idx = n - 2
        for k, (cp1, cp2) in cps.items():
            new_k = max_seg_idx - k
            new_cps[new_k] = (cp2, cp1)
            
        return (new_pts, new_segs, new_cps)

    def update_control_point(self, segment_index, which_cp, new_pos):
        """Update a specific control point (0=cp1, 1=cp2) for a segment"""
        if segment_index in self._control_points:
            cp1, cp2 = self._control_points[segment_index]
            if which_cp == 0:
                self._control_points[segment_index] = (new_pos, cp2)
            else:
                self._control_points[segment_index] = (cp1, new_pos)
            self._update_path()

    def set_color(self, color: QColor):
        """设置路径颜色"""
        self._color = color
        self._orig_color = color
        self._update_path()

    def color(self):
        return self._color

    def enable_node_edit(self, on: bool):
        # 切换节点编辑模式并相应地重建或清理锚点句柄
        self._node_edit_enabled = bool(on)
        self._update_path() # 更新颜色
        if on:
            self._rebuild_handles()
        else:
            self._clear_handles()
            if self._suggested_node_visual:
                self._suggested_node_visual.hide()
            self._suggested_segment_index = -1
            self._selected_handle_indices.clear()

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
        
        # Build Node Handles
        for idx, (x, y) in enumerate(self._points):
            h = _DragHandle(self, idx, x, y)
             # 若为选中状态，设置不同颜色
            if idx in self._selected_handle_indices:
                h.setBrush(QBrush(QColor(0, 0, 255))) # 选中显示蓝色填充
            self._handles.append(h)
            
        # Build Control Point Handles for selected curves
        # Only show control handles for segments adjacent to selected nodes? Or all curves?
        # User request: "Select two nodes... then handles appear".
        # Standard vector: Select a node -> Show its adjacent control points.
        # Select two nodes -> Show control points for the segment between them (if curve).
        
        for i, val in enumerate(self._segment_types):
            is_selected_start = (i in self._selected_handle_indices)
            is_selected_end = ((i + 1) in self._selected_handle_indices)
            
            # Show handles if connected nodes are selected and it is a curve with generic CPs
            if (is_selected_start or is_selected_end) and i in self._control_points:
                 cp1, cp2 = self._control_points[i]
                 
                 # CP1 (Near Start Node)
                 if i < len(self._points):
                    h1 = _ControlPointHandle(self, i, 0, cp1[0], cp1[1], self._points[i])
                    self._handles.append(h1)
                 
                 # CP2 (Near End Node)
                 if i + 1 < len(self._points):
                    h2 = _ControlPointHandle(self, i, 1, cp2[0], cp2[1], self._points[i+1])
                    self._handles.append(h2)

    def _update_handles_positions(self):
        """Update positions of all handles (Nodes and Control Points)"""
        if not self._handles: return
        
        for h in self._handles:
            # Check type by name to avoid reference issues if class defined below
            t_name = h.__class__.__name__
            
            # Avoid moving the item that is currently being dragged by mouse
            # This prevents jitter fighting between Qt Mouse Move and SetPos
            if hasattr(h, 'isUnderMouse') and h.isUnderMouse() and h.flags() & QGraphicsItem.ItemIsMovable:
                 # If it's a movable handle under mouse, likely being dragged. 
                 # We still want to update 'anchor_pos' for dashed line repaint though.
                 if t_name == '_ControlPointHandle':
                      # Update dashed line anchor only
                      seg_idx = h._segment_idx
                      if h._which_cp == 0:
                        if seg_idx < len(self._points):
                             h._anchor_pos = self._points[seg_idx]
                      else:
                        if seg_idx + 1 < len(self._points):
                             h._anchor_pos = self._points[seg_idx+1]
                      h.update() 
                 continue

            if t_name == '_DragHandle':
                if h._idx < len(self._points):
                    pt = self._points[h._idx]
                    h.setPos(pt[0], pt[1])
            elif t_name == '_ControlPointHandle':
                seg_idx = h._segment_idx
                # Check if this control point still valid in data
                if seg_idx in self._control_points:
                    c1, c2 = self._control_points[seg_idx]
                    pos = c1 if h._which_cp == 0 else c2
                    h.setPos(pos[0], pos[1])
                    # Update anchor for the dashed line
                    if h._which_cp == 0:
                        if seg_idx < len(self._points):
                             h._anchor_pos = self._points[seg_idx]
                    else:
                        if seg_idx + 1 < len(self._points):
                             h._anchor_pos = self._points[seg_idx+1]
                    h.update() # Trigger repaint of the dashed line
                else:
                    h.setVisible(False)

    def update_point(self, idx: int, x: float, y: float):
        if 0 <= idx < len(self._points):
            # Calculate delta
            dx = x - self._points[idx][0]
            dy = y - self._points[idx][1]
            
            # If dragged point is selected, move all selected points
            indices_to_move = self._selected_handle_indices if idx in self._selected_handle_indices else {idx}
            
            for i in indices_to_move:
                if 0 <= i < len(self._points):
                    px, py = self._points[i]
                    self._points[i] = (px + dx, py + dy)
                    
                    # Move attached control points 
                    # Segment starting at i (CP1)
                    if i in self._control_points:
                        c1, c2 = self._control_points[i]
                        new_c1 = (c1[0] + dx, c1[1] + dy)
                        self._control_points[i] = (new_c1, c2)
                        
                    # Segment ending at i (previous segment i-1, CP2)
                    prev = i - 1
                    if prev >= 0 and prev in self._control_points:
                         c1, c2 = self._control_points[prev]
                         new_c2 = (c2[0] + dx, c2[1] + dy)
                         self._control_points[prev] = (c1, new_c2)

            self._update_path()
            if getattr(self, '_node_edit_enabled', False):
                 self._update_handles_positions()

    def update_control_point(self, seg_idx, which_cp, pos):
        """Update just one control point (interactive drag)"""
        # seg_idx: index of segment
        # which_cp: 0 for CP1 (start), 1 for CP2 (end)
        # pos: (x, y) tuple
        if seg_idx in self._control_points:
            c1, c2 = self._control_points[seg_idx]
            if which_cp == 0:
                self._control_points[seg_idx] = (pos, c2)
            else:
                self._control_points[seg_idx] = (c1, pos)
            self._update_path()
            
            # Optimization: If dragging, maybe we don't need to rebuild ALL handle positions?
            # Or at least, if we do, we need to ensure it doesn't fight the mouse.
            # But simpler is just to update.
            if getattr(self, '_node_edit_enabled', False):
                 self._update_handles_positions()

    def set_selected_handle(self, idx: int, modifiers=Qt.NoModifier):
        """设置当前选中的节点句柄索引"""
        # Debug modifiers
        # print(f"Select handle {idx}, modifiers: {modifiers}, Shift: {modifiers & Qt.ShiftModifier}")
        
        # 兼容 Shift 和 Ctrl
        is_multi_select = (modifiers & Qt.ShiftModifier) or (modifiers & Qt.ControlModifier)

        if is_multi_select:
            # Shift/Ctrl键：切换选中状态
            if idx in self._selected_handle_indices:
                self._selected_handle_indices.remove(idx)
            else:
                self._selected_handle_indices.add(idx)
        else:
            # 无修饰键：单选
            self._selected_handle_indices.clear()
            self._selected_handle_indices.add(idx)
            
        # Re-verify handles visually
        # Sometimes handles might not be rebuilt yet, so iterate safely
        if self._handles:
            for h in self._handles:
                # Check if it's a DragHandle (has _idx attribute)
                if hasattr(h, '_idx'):
                    if h._idx in self._selected_handle_indices:
                        h.setBrush(QBrush(QColor(0, 0, 255))) # 选中：蓝色填充
                    else:
                        h.setBrush(QBrush(QColor(255, 255, 255))) # 未选中：白色填充
                # Also hide/show Control Points based on selection?
                # Logic: If node i is selected, show CP1 of segment i and CP2 of segment i-1?
                # For now let's just stick to rebuild_handles doing it, or trigger update.
        
        # If selection changed, we might need to show/hide control handles dynamically?
        # self._rebuild_handles() is heavy but accurate.
        # But if we just click, maybe we don't want rebuild.
        # Current logic in _rebuild_handles depends on _selected_handle_indices.
        # So we SHOULD rebuild handles (or at least visibility) when selection changes.
        if getattr(self, '_node_edit_enabled', False):
             self._rebuild_handles()
        
        # Hide suggested node visual when selecting existing nodes
        if self._suggested_node_visual:
            self._suggested_node_visual.hide()
        self._suggested_segment_index = -1

    def _dist_to_segment(self, p: QPointF, s1: QPointF, s2: QPointF):
        """计算点 p 到线段 s1-s2 的距离及最近点"""
        x, y = p.x(), p.y()
        x1, y1 = s1.x(), s1.y()
        x2, y2 = s2.x(), s2.y()
        
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return (p - s1).manhattanLength(), s1
            
        t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))
        
        nearest = QPointF(x1 + t * dx, y1 + t * dy)
        dist = math.sqrt((x - nearest.x())**2 + (y - nearest.y())**2)
        return dist, nearest

    def _calculate_suggested_point(self, pos: QPointF):
        """计算点击位置附近的路径点"""
        min_dist = 1000.0
        best_idx = -1
        best_pt = QPointF()
        
        pts = self._points
        if not pts or len(pts) < 2: return
        
        for i in range(len(pts) - 1):
            p1 = QPointF(pts[i][0], pts[i][1])
            p2 = QPointF(pts[i+1][0], pts[i+1][1])
            dist, pt = self._dist_to_segment(pos, p1, p2)
            if dist < min_dist:
                min_dist = dist
                best_idx = i
                best_pt = pt
                
        # 阈值判断，比如距离小于 5 像素则认为点击在路径上
        if min_dist < 5.0:
            self._suggested_segment_index = best_idx
            self._suggested_point_pos = (best_pt.x(), best_pt.y())
            self._update_suggested_node_visual()
        else:
            self._suggested_segment_index = -1
            if self._suggested_node_visual:
                self._suggested_node_visual.hide()
                
    def _update_suggested_node_visual(self):
        if self._suggested_point_pos is None: return
        x, y = self._suggested_point_pos
        if not self._suggested_node_visual:
            r = 3.0
            self._suggested_node_visual = QGraphicsRectItem(-r, -r, 2*r, 2*r, parent=self)
            self._suggested_node_visual.setPen(QPen(Qt.red))
            self._suggested_node_visual.setBrush(QBrush(Qt.red))
            self._suggested_node_visual.setZValue(15)
        self._suggested_node_visual.setPos(x, y)
        self._suggested_node_visual.show()

    def add_node_at_suggestion(self):
        """在建议位置添加节点"""
        if self._suggested_segment_index != -1 and self._suggested_point_pos:
            idx = self._suggested_segment_index + 1
            old_points = self._points[:]

            # Update segment types: split the segment, preserving its type
            if 0 <= self._suggested_segment_index < len(self._segment_types):
                 original_type = self._segment_types[self._suggested_segment_index]
                 self._segment_types.insert(self._suggested_segment_index, original_type)
                 # Shift control points > index
                 k = self._suggested_segment_index
                 # If original was curve with CPs, we should split the Bezier?
                 # Too complex for now, just drop CPs for the new segments or keep line default?
                 # Shifting keys:
                 new_cps = {}
                 for key, val in self._control_points.items():
                     if key < k:
                         new_cps[key] = val
                     elif key >= k:
                         new_cps[key + 1] = val
                 self._control_points = new_cps
            
            self._points.insert(idx, self._suggested_point_pos)
            self._update_path()
            if self._node_edit_enabled:
                self._rebuild_handles()
            
            # 记录 Undo
            self._record_undo(old_points, self.points())
            
            self._suggested_segment_index = -1
            if self._suggested_node_visual: self._suggested_node_visual.hide()

    def set_segment_types(self, types):
        self._segment_types = types[:]
        self._update_path()

    def set_selected_segments_type(self, is_curve: bool):
        """将选中的线段类型转换 (is_curve=True为曲线, False为直线)"""
        try:
            if not self._selected_handle_indices:
                return
                
            old_types = self._segment_types[:]
            changed = False
            
            n_segments = len(self._segment_types)
            
            for idx in self._selected_handle_indices:
                if 0 <= idx < n_segments:
                    # STRICT REQUIREMENT: Only convert segment if BOTH ends are selected.
                    # This prevents modifying segments connected to only one selected node.
                    if (idx + 1) not in self._selected_handle_indices:
                        continue

                    target_val = 1 if is_curve else 0
                    if self._segment_types[idx] != target_val:
                        self._segment_types[idx] = target_val
                        changed = True
                        
                        if target_val == 1:
                            # Converting to Curve: Generate default control points if missing
                            # Warning: Ensure idx+1 is valid for _points
                            if idx + 1 < len(self._points):
                                if idx not in self._control_points:
                                    p1 = self._points[idx]
                                    p2 = self._points[idx+1]
                                     # 1/3 and 2/3 points
                                    dx = p2[0] - p1[0]
                                    dy = p2[1] - p1[1]
                                    cp1 = (p1[0] + dx/3.0, p1[1] + dy/3.0)
                                    cp2 = (p1[0] + 2*dx/3.0, p1[1] + 2*dy/3.0)
                                    self._control_points[idx] = (cp1, cp2)
                        else:
                            # Converting to Line: Remove CPs
                            if idx in self._control_points:
                                del self._control_points[idx]
                        
            if changed:
                self._update_path()
                if getattr(self, '_node_edit_enabled', False):
                    self._rebuild_handles()
                # Push Undo Command
                try:
                    views = self.scene().views()
                    edit_mgr = None
                    for v in views:
                        if hasattr(v, 'edit_manager'):
                            edit_mgr = getattr(v, 'edit_manager')
                            break
                    if edit_mgr:
                        from edit.commands import ChangeSegmentTypeCommand
                        cmd = ChangeSegmentTypeCommand(self, old_types, self._segment_types[:])
                        edit_mgr.push_undo(cmd)
                except Exception:
                    print("Undo command creation failed")
                    traceback.print_exc()
        except Exception as e:
            print(f"Error in set_selected_segments_type: {e}")
            traceback.print_exc()

    def delete_selected_node(self):
        """删除当前选中的节点"""
        if not self._selected_handle_indices:
            return
            
        old_points = self._points[:]
        
        # 按索引从大到小排序，防止删除导致索引错位
        indices = sorted(list(self._selected_handle_indices), reverse=True)
        for i in indices:
            if 0 <= i < len(self._points):
                # Maintain segment types sync
                if self._segment_types:
                    # Logic: removing node i removes one segment.
                    # If i is last point, remove last segment (i-1)
                    # If i is anything else, remove segment i (that started at i)
                    type_idx = i if i < len(self._points) - 1 else i - 1
                    if 0 <= type_idx < len(self._segment_types):
                        self._segment_types.pop(type_idx)                        # Rebuild control points dictionary keys... this is painful (keys shift)
                        # Need to shift all keys > type_idx down by 1
                        new_cps = {}
                        for k, v in self._control_points.items():
                            if k < type_idx:
                                new_cps[k] = v
                            elif k > type_idx:
                                new_cps[k - 1] = v
                        self._control_points = new_cps
                self._points.pop(i)
                
        self._update_path()
        # 清除选中状态
        self._selected_handle_indices.clear()
        if self._node_edit_enabled:
            self._rebuild_handles()
        
        # 记录 Undo
        self._record_undo(old_points, self.points())

    def _record_undo(self, old_points, new_points):
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
                # 虽然不是 move，但这里复用 MoveItemsCommand 或者应创建一个 ModifyPathCommand
                # MoveItemsCommand 接受 list of (type, item, old, new)
                # 这完全适用于 points 变化
                items_states = [('path', self, old_points, new_points)]
                cmd = MoveItemsCommand(canvas, items_states)
                edit_mgr.push_undo(cmd)
        except Exception:
            pass

    def connect_selected_nodes(self):
        """连接两选中的节点"""
        # Ensure 2 nodes selected
        if len(self._selected_handle_indices) != 2:
            return
            
        indices = sorted(list(self._selected_handle_indices))
        start_idx, end_idx = indices[0], indices[1]
        n = len(self._points)
        
        # Check if endpoints (0 and n-1)
        if start_idx == 0 and end_idx == n - 1:
            p0 = self._points[0]
            pn = self._points[-1]
            if abs(p0[0]-pn[0]) < 1e-5 and abs(p0[1]-pn[1]) < 1e-5:
                return
            
            old_points = self._points[:]
            self._points.append(p0)
            self._update_path()
            if self._node_edit_enabled:
                self._rebuild_handles()
            
            self._record_undo(old_points, self.points())

    def break_curve_at_selected_nodes(self):
        """在选中的节点位置打断曲线"""
        if not self._selected_handle_indices:
            return

        # Pick one node
        indices = sorted(list(self._selected_handle_indices))
        k = indices[0]
        
        n = len(self._points)
        if k <= 0 or k >= n - 1:
            return # Cannot break at endpoints
            
        # Split logic
        # Data 1
        pts1 = self._points[:k+1]
        segs1 = self._segment_types[:k]
        cp1 = {}
        for i, val in self._control_points.items():
            if i < k:
                cp1[i] = val
        
        # Data 2
        pts2 = self._points[k:]
        segs2 = self._segment_types[k:]
        cp2 = {}
        for i, val in self._control_points.items():
            if i >= k:
                cp2[i - k] = val
        
        self._execute_break((pts1, segs1, cp1), (pts2, segs2, cp2))
        
    def _execute_break(self, data1, data2):
        try:
            views = self.scene().views()
            edit_mgr = None
            canvas = None
            for v in views:
                if hasattr(v, 'edit_manager'):
                    edit_mgr = getattr(v, 'edit_manager')
                    canvas = v
                    break
            
            if edit_mgr:
                from edit.commands import BreakCurveCommand
                cmd = BreakCurveCommand(canvas, self, data1, data2)
                cmd.redo() # Execute
                edit_mgr.push_undo(cmd)
                
                # Update edit mode for original item (now shorter)
                if getattr(self, '_node_edit_enabled', False):
                    self._clear_handles()
                    self._selected_handle_indices.clear()
                    self._rebuild_handles()
        except Exception as e:
            print(f"Break curve error: {e}")

    def itemChange(self, change, value):
        # 移除位置锁定逻辑，允许 Item 正常移动
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QMouseEvent):
        # logging.info(f"Path press. Modifiers: {event.modifiers()}")
        
        # 节点编辑模式下，点击路径预览插入点
        if getattr(self, '_node_edit_enabled', False):
            # 只有当点击位置不在任何句柄上时才计算建议点
            # 由于句柄是子项且接受事件，通常不需要额外判断，但为了保险起见
            self._calculate_suggested_point(event.pos())
            
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
                
                # 同时更新控制点，防止控制点错位
                new_cps = {}
                for k, (c1, c2) in self._control_points.items():
                    new_c1 = (c1[0] + dx, c1[1] + dy)
                    new_c2 = (c2[0] + dx, c2[1] + dy)
                    new_cps[k] = (new_c1, new_c2)
                self._control_points = new_cps
                
                # 重置 Item 位置为 (0, 0)
                self.setPos(0, 0)
                # 更新路径和句柄
                self._update_path()
                if getattr(self, '_node_edit_enabled', False):
                     self._update_handles_positions()

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

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # 双击直接添加节点
        if getattr(self, '_node_edit_enabled', False):
            self._calculate_suggested_point(event.pos())
            if self._suggested_segment_index != -1:
                self.add_node_at_suggestion()
                return # 阻止传递
        super().mouseDoubleClickEvent(event)


class _ControlPointHandle(QGraphicsRectItem):
    """Bézier Control Point Handle (Small hollow square connected to node)"""
    def __init__(self, owner, segment_idx, which_cp, x, y, anchor_pos):
        r = 2.5 # Smaller than node handle
        super().__init__(-r, -r, 2*r, 2*r, parent=owner)
        self._owner = owner
        self._segment_idx = segment_idx
        self._which_cp = which_cp # 0 or 1
        
        self.setPos(x, y)
        self.setFlags(QGraphicsItem.ItemSendsGeometryChanges)
        
        # Appearance
        self.setPen(QPen(Qt.black, 0)) # Thin black border
        self.setBrush(QBrush(Qt.white)) # White fill
        self.setCursor(Qt.PointingHandCursor)
        
        # Store anchor pos to draw line
        self._anchor_pos = anchor_pos
        self.setZValue(12) # Above nodes? Or below? Nodes are 10. Let's make this 12 or 11.
        
    def paint(self, painter, option, widget=None):
        # Draw the square
        super().paint(painter, option, widget)
        
        # Draw dashed line to anchor
        painter.setPen(QPen(Qt.blue, 0, Qt.DashLine))
        local_anchor = self.mapFromParent(QPointF(self._anchor_pos[0], self._anchor_pos[1]))
        painter.drawLine(QPointF(0, 0), local_anchor)

    def mousePressEvent(self, event):
        # Crucial: Accept event to prevent parent PathItem from handling it (which would move the whole path)
        event.accept()
        # Ensure owner is selected so we don't exit Node Edit mode
        if not self._owner.isSelected():
            self._owner.setSelected(True)

    def mouseMoveEvent(self, event):
        event.accept()
        # Manual drag implementation
        # Get scene pos, map to parent (PathItem) to get local coordinates for setPos
        scene_pos = event.scenePos()
        new_pos = self.parentItem().mapFromScene(scene_pos)
        
        self.setPos(new_pos)
        self._owner.update_control_point(self._segment_idx, self._which_cp, (new_pos.x(), new_pos.y()))

    def mouseReleaseEvent(self, event):
        event.accept()

    def itemChange(self, change, value):
        return super().itemChange(change, value)


class _DragHandle(QGraphicsRectItem):
    def __init__(self, owner, idx: int, x: float, y: float):
        r = 3.0  # Slightly smaller for square
        # 创建矩形，初始位置在 (0, 0)，大小为 2r x 2r
        super().__init__(-r, -r, 2 * r, 2 * r, parent=owner)
        self._owner = owner
        self._idx = idx
        # 蓝色正方形
        pen = QPen(QColor(0, 0, 255))
        pen.setWidth(1)
        pen.setCosmetic(True)
        self.setPen(pen)
        # 白色填充或浅蓝填充? User said "blue square". 
        # Usually handles are white with blue border or solid blue.
        # Screenshot shows small squares with white interior maybe?
        # Let's use blue border, white fill to be clean, or blue fill. 
        # User said "tip of arrow... small blue square". Solid blue implies filled.
        # But previous code had alpha 120.
        self.setBrush(QBrush(QColor(255, 255, 255))) # White fill
        # Or blue fill? "small blue square".
        # Let's try White fill with Blue border similar to standard node tools.
        # Screenshot provided: Nodes on rectangle are small squares.
        
        self.setZValue(10)
        # 不设置 ItemIsMovable，避免 Qt 自动移动句柄
        self.setFlags(QGraphicsItem.ItemIsSelectable)
        self.setCursor(Qt.ArrowCursor) # Or CrossCursor? Or inherit?
        # Node edit cursor usually is specific.
        
        # 设置句柄的场景位置 (Set local pos relative to parent)
        self.setPos(x, y)

    def mouseMoveEvent(self, e: QMouseEvent):
        # 获取鼠标在场景中的位置
        scene_pos = self.mapToScene(e.pos())
        # 转换为 Owner (PathItem) 的局部坐标，因为 update_point 需要局部坐标
        local_pos = self._owner.mapFromScene(scene_pos)
        x, y = local_pos.x(), local_pos.y()
        # 更新拥有者的点坐标
        self._owner.update_point(self._idx, x, y)
        # 手动更新句柄位置（因为没有设置 ItemIsMovable）
        pass

    def mousePressEvent(self, event: QMouseEvent):
        # 阻止事件传递，确保父项不会处理
        event.accept()
        
        # 兼容 Shift 和 Ctrl (Whiteboard 会将 Shift 转换为 Ctrl 模拟多选)
        is_multi_select = (event.modifiers() & Qt.ShiftModifier) or (event.modifiers() & Qt.ControlModifier)

        # 选中当前节点
        if hasattr(self._owner, 'set_selected_handle'):
            self._owner.set_selected_handle(self._idx, event.modifiers())
            
        # 确保父路径被选中 (重要：否则连接操作找不到选中的路径)
        if is_multi_select:
            # Shift/Ctrl: 追加/保持选中
            self._owner.setSelected(True)
        else:
            # 单选：先清除场景中其他选中项
            scene = self.scene()
            if scene:
                for item in scene.selectedItems():
                    if item != self._owner:
                        item.setSelected(False)
            self._owner.setSelected(True)

        try:
            # 记录操作前的点集合
            if hasattr(self._owner, 'points'):
                self._orig_points = self._owner.points()
            elif hasattr(self._owner, 'get_params'):
                self._orig_params = self._owner.get_params()
        except Exception:
            pass
        # 接受事件但不调用 super，避免默认的移动行为
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            if hasattr(self._owner, 'points'):
                new_points = self._owner.points()
                old_points = getattr(self, '_orig_points', None)
                # ... existing logic for PathItem ...
                if old_points is not None and new_points != old_points:
                    self._record_undo('path', old_points, new_points)
                    
            elif hasattr(self._owner, 'get_params'):
                # Handle Ellipse undo
                # This requires implementing set_params/get_params on EllipseItem 
                # and a command for it.
                pass
        except Exception:
            pass
        event.accept()

    def _record_undo(self, typ, old, new):
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
                # Note: MoveItemsCommand expects (type, item, old, new)
                # For path: ('path', item, old_pts, new_pts)
                items_states = [(typ, self._owner, old, new)]
                cmd = MoveItemsCommand(canvas, items_states)
                edit_mgr.push_undo(cmd)
        except Exception:
            pass



class EditableEllipseItem(QGraphicsEllipseItem):
    def __init__(self, cx, cy, rx, ry, color: QColor):
        # 确保参数有效
        if rx <= 0: rx = 0.1
        if ry <= 0: ry = 0.1
        super().__init__(cx - rx, cy - ry, 2 * rx, 2 * ry)
        self._color = color
        self._orig_color = color
        self._handles = []
        self._node_edit_enabled = False
        self._update_pen()
        self.setFlags(QGraphicsEllipseItem.ItemIsSelectable | QGraphicsEllipseItem.ItemIsMovable)
        

        # 节点编辑相关
        self._node_edit_enabled = False
        self._handles = []
        self._move_orig_rect = None

    def setPen(self, pen):
        # 只有在非节点编辑模式下才更新颜色
        if not getattr(self, '_node_edit_enabled', False):
            super().setPen(pen)
            self._color = pen.color()
            self._orig_color = pen.color()
        else:
            # 即使在编辑模式，也可能需要调用 super().setPen 如果必须的话，但最好忽略颜色的改变
            pass

    def _update_pen(self):
        # 决定颜色
        c = QColor(Qt.red) if getattr(self, '_node_edit_enabled', False) else self._color
        pen = QPen(c)
        pen.setCosmetic(True)
        pen.setWidthF(1.2)
        # 强制调用父类 setPen
        QGraphicsEllipseItem.setPen(self, pen)

    def set_color(self, color: QColor):
        self._color = color
        self._orig_color = color
        self._update_pen()
        
    def color(self):
        return self._color

    def enable_node_edit(self, on: bool):

        """切换节点编辑模式"""

        self._node_edit_enabled = bool(on)
        self._update_pen()

        if on:
            self._rebuild_handles()
        else:
            self._clear_handles()

    def _clear_handles(self):
        for h in self._handles:
            if h.scene():
                h.scene().removeItem(h)
            h.setParentItem(None)
        self._handles.clear()

        
    def _rebuild_handles(self):
        self._clear_handles()
        rect = self.rect()
        c = rect.center()
        rx = rect.width() / 2
        ry = rect.height() / 2
        
        # 保留右侧：通过中心+半径计算句柄坐标（逻辑更严谨）
        pts = [
            QPointF(c.x(), c.y() - ry), # Top
            QPointF(c.x() + rx, c.y()), # Right
            QPointF(c.x(), c.y() + ry), # Bottom
            QPointF(c.x() - rx, c.y())  # Left
        ]
        
        # 统一句柄类：优先用 _DragHandle（右侧），若项目中是 _EllipseHandle 可替换
        for idx, pt in enumerate(pts):
            h = _DragHandle(self, idx, pt.x(), pt.y())
            self._handles.append(h)

def _update_handles_positions(self):
    if not self._handles: return
    rect = self.rect()
    c = rect.center()
    rx = rect.width() / 2
    ry = rect.height() / 2
    pts = [
        QPointF(c.x(), c.y() - ry),
        QPointF(c.x() + rx, c.y()),
        QPointF(c.x(), c.y() + ry),
        QPointF(c.x() - rx, c.y()) 
    ]
    # 保留右侧：索引越界保护 + 中心+半径计算位置
    for idx, h in enumerate(self._handles):
        if idx < len(pts):
            h.setPos(pts[idx])

def update_handle(self, idx: int, x: float, y: float):
    """
    统一对外接口：兼容左侧命名+类型注解，实现右侧核心逻辑
    :param idx: 句柄索引（0=上，1=右，2=下，3=左）
    :param x: 场景坐标x
    :param y: 场景坐标y
    """
    # 保留右侧：场景坐标转本地坐标（适配Qt图形场景体系）
    local_pos = self.mapFromScene(QPointF(x, y))
    lx, ly = local_pos.x(), local_pos.y()
    
    rect = self.rect()
    c = rect.center()
    rx = rect.width() / 2
    ry = rect.height() / 2
    
    # 保留右侧：固定中心，只修改半径（符合椭圆调整直觉）
    # 融合左侧：尺寸保护（取0.1更合理，兼容左侧1e-3的最小阈值）
    min_size = 0.1
    new_rect = QRectF(rect)
    
    if idx == 0: # Top
        new_ry = abs(c.y() - ly)
        new_ry = max(new_ry, min_size)  # 尺寸保护
        new_rect.setRect(c.x() - rx, c.y() - new_ry, 2*rx, 2*new_ry)
    elif idx == 1: # Right
        new_rx = abs(lx - c.x())
        new_rx = max(new_rx, min_size)  # 尺寸保护
        new_rect.setRect(c.x() - new_rx, c.y() - ry, 2*new_rx, 2*ry)
    elif idx == 2: # Bottom
        new_ry = abs(ly - c.y())
        new_ry = max(new_ry, min_size)  # 尺寸保护
        new_rect.setRect(c.x() - rx, c.y() - new_ry, 2*rx, 2*new_ry)
    elif idx == 3: # Left
        new_rx = abs(c.x() - lx)
        new_rx = max(new_rx, min_size)  # 尺寸保护
        new_rect.setRect(c.x() - new_rx, c.y() - ry, 2*new_rx, 2*ry)
    
    # 保留左侧：normalized() 确保矩形有效（避免宽高为负）
    self.setRect(new_rect.normalized())
    self._update_handles_positions()

# 兼容右侧的 update_point 命名（避免旧代码调用报错）
def update_point(self, idx, x, y):
    self.update_handle(idx, x, y)



    def get_params(self):
        """获取椭圆参数 (cx, cy, rx, ry) 场景坐标"""
        rect = self.rect()
        
        if not self.scene():
            return rect.center().x(), rect.center().y(), rect.width()/2, rect.height()/2

        center_scene = self.mapToScene(rect.center())
        cx = center_scene.x()
        cy = center_scene.y()
        
        rx = rect.width() / 2
        ry = rect.height() / 2
        
        transform = self.sceneTransform()
        scale_x = math.sqrt(transform.m11()**2 + transform.m12()**2)
        scale_y = math.sqrt(transform.m21()**2 + transform.m22()**2)
        
        return cx, cy, rx * scale_x, ry * scale_y


class _EllipseHandle(QGraphicsEllipseItem):
    def __init__(self, owner: EditableEllipseItem, idx: int, x: float, y: float):
        r = 3.5
        super().__init__(-r, -r, 2 * r, 2 * r, parent=owner)
        self._owner = owner
        self._idx = idx
        pen = QPen(QColor(255, 100, 0)) # 橙色区分
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(255, 100, 0, 120)))
        self.setZValue(10)
        self.setFlags(QGraphicsEllipseItem.ItemIsSelectable)
        
        # 设置光标
        if idx in (0, 2): # Top, Bottom
            self.setCursor(Qt.SizeVerCursor)
        elif idx in (1, 3): # Right, Left
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
            
        self.setPos(x, y)

    def mouseMoveEvent(self, e: QMouseEvent):
        # 获取本地坐标 (因为是子项，mapToParent 即 mapToOwner)
        pos = self.mapToParent(e.pos())
        x, y = pos.x(), pos.y()
        self._owner.update_handle(self._idx, x, y)

    def mousePressEvent(self, event: QMouseEvent):
        try:
            self._orig_rect = self._owner.rect()
        except Exception:
            self._orig_rect = None
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            new_rect = self._owner.rect()
            old_rect = getattr(self, '_orig_rect', None)
            if old_rect is not None and new_rect != old_rect:
                # 记录撤销逻辑（暂时跳过复杂 Command 实现）
                pass
        except Exception:
            pass
        event.accept()

class TextGraphicsItem(QGraphicsPathItem):
    def __init__(self, text, settings, parent=None):
        super().__init__(parent)
        self.text_data = text
        self.settings = settings
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.rebuild_path()


    def rebuild_path(self):
        try:
            txt = self.text_data
            if not txt:
                self.setPath(QPainterPath())
                return

            font_family = self.settings.get('font_family', 'Arial')
            db = QFontDatabase()
            
            # Basic existence check
            if font_family not in db.families():
                font_family = 'Arial'

            # Note: We removed the isSmoothlyScalable check as it was not reliable enough
            # and sometimes false-positived on valid fonts, or ignored crashing fonts.
            # Instead, we rely on QGraphicsSimpleTextItem's robust shape logic.

            is_bold = self.settings.get('is_bold', False)
            is_italic = self.settings.get('is_italic', False)
            height_mm = self.settings.get('height', 10.0)
            if height_mm <= 0.001: height_mm = 10.0

            width_percent = self.settings.get('width_percent', 100) / 100.0
            if width_percent <= 0.001: width_percent = 1.0
            char_spacing = self.settings.get('char_spacing', 0.0)
            line_spacing = self.settings.get('line_spacing', 0.0)

            # Construct Font
            font = QFont(font_family)
            font.setBold(is_bold)
            font.setItalic(is_italic)
            
            # Using a fixed pixel size for the "base" path generation.
            # 48px is a safe balance between precision and stability
            base_size = 48.0
            font.setPixelSize(int(base_size))
            
            fm = QFontMetricsF(font)
            # Safety checks for metrics
            if fm.height() <= 0.001:
                font.setPixelSize(12)
                base_size = 12.0
                fm = QFontMetricsF(font)

            full_path = QPainterPath()
            lines = txt.split('\n')
            current_y = 0.0
            
            scale_factor = height_mm / base_size
            scale_x = scale_factor * width_percent
            scale_y = scale_factor

            for line_str in lines:
                if not line_str:
                    current_y += fm.height() * scale_y + line_spacing
                    continue
                
                # CRITICAL CHANGE: Use QGraphicsSimpleTextItem to generate path
                # This bypasses direct QPainterPath.addText calls which can be fragile.
                # QGraphicsSimpleTextItem.shape() usually handles platform specifics better.
                
                current_x_base = 0.0
                spacing_base = char_spacing / scale_x if scale_x else 0
                
                line_base_path = QPainterPath()
                
                # current_x_base = 0.0
                # spacing_base = char_spacing / scale_x if scale_x else 0
                
                line_base_path = QPainterPath()
                
                # Use addText to generate the actual glyph outlines (vectors)
                # Ensure we handle potential errors or weird states
                if abs(spacing_base) < 0.001:
                    line_base_path.addText(0, 0, font, line_str)
                else:
                    for char in line_str:
                        if not char: continue
                        
                        line_base_path.addText(current_x_base, 0, font, char)
                        
                        # Use QFontMetricsF for precision
                        cw = fm.width(char)
                        current_x_base += cw + spacing_base

                # Transform line path to final world size
                t_line = QTransform()
                t_line.scale(scale_x, scale_y)
                
                path_final = t_line.map(line_base_path)
                path_final.translate(0, current_y)
                full_path.addPath(path_final)
                
                current_y += fm.height() * scale_y + line_spacing

            self.prepareGeometryChange()
            self.setPath(full_path)

        except Exception:
            import traceback
            traceback.print_exc()
            print(f"Error: {e}")


