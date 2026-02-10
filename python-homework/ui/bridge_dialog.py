#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QRadioButton, QPushButton, QGraphicsView, 
                             QGraphicsScene, QWidget, QGroupBox, QButtonGroup, QMessageBox)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QLineF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath

import math
from ui.graphics_items import EditablePathItem

class BridgePreviewScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(Qt.black))
        self.temp_bridge_pos = None # For mouse hover (previewing bridge placement)
        self.temp_bridge_width = 4.0
        self.manual_mode = False

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if self.manual_mode and self.temp_bridge_pos:
            # Draw the red cross
            pt, tangible_vec = self.temp_bridge_pos
            
            # tangible_vec is direction of the line
            # We want cross size = bridge width
            w = self.temp_bridge_width
            
            painter.setPen(QPen(Qt.red, 2))
            
            # Horizontal-ish line (along the path)
            # Normalize vector
            length = math.hypot(tangible_vec.x(), tangible_vec.y())
            if length > 1e-9:
                u = tangible_vec / length
                
                # Line along the path
                p1 = pt - u * (w/2)
                p2 = pt + u * (w/2)
                painter.drawLine(p1, p2)
                
                # Perpendicular line
                v = QPointF(-u.y(), u.x())
                p3 = pt - v * (w/2)
                p4 = pt + v * (w/2)
                painter.drawLine(p3, p4)


class BridgePreviewView(QGraphicsView):
    clicked = pyqtSignal(QPointF) # Signal when clicked in manual mode
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMouseTracking(True) # Enable mouse tracking for hover effects
        self.setDragMode(QGraphicsView.NoDrag)
        self._last_pan_point = None
        self._panning = False

    def wheelEvent(self, event):
        zoomInFactor = 1.10
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.scale(zoomFactor, zoomFactor)

    def mouseMoveEvent(self, event):
        if self._panning:
             # Pan logic
             delta = event.pos() - self._last_pan_point
             hBar = self.horizontalScrollBar()
             vBar = self.verticalScrollBar()
             hBar.setValue(hBar.value() - delta.x())
             vBar.setValue(vBar.value() - delta.y())
             self._last_pan_point = event.pos()
             return

        if self.scene().manual_mode:
            # Check overlap with items
            sp = self.mapToScene(event.pos())
            
            # Find closest point on path
            # This is expensive if many items. 
            items = self.scene().items()
            min_dist = float('inf')
            best_pt = None
            best_vec = None
            
            # Simple hit test radius
            SEARCH_RADIUS = 20.0 
            
            for item in items:
                if isinstance(item, EditablePathItem):
                    # Find closest point on this item's path
                    # We iterate segments
                    pts = item.points()
                    if len(pts) < 2: continue
                    
                    for i in range(len(pts)-1):
                        p1 = QPointF(*pts[i])
                        p2 = QPointF(*pts[i+1])
                        
                        # Distance from sp to segment p1-p2
                        l2 = (p1.x()-p2.x())**2 + (p1.y()-p2.y())**2
                        if l2 == 0: continue
                        
                        t = ((sp.x()-p1.x())*(p2.x()-p1.x()) + (sp.y()-p1.y())*(p2.y()-p1.y())) / l2
                        t = max(0, min(1, t))
                        proj = p1 + (p2 - p1) * t
                        
                        dist = math.hypot(sp.x()-proj.x(), sp.y()-proj.y())
                        
                        if dist < SEARCH_RADIUS and dist < min_dist:
                            min_dist = dist
                            best_pt = proj
                            best_vec = p2 - p1
            
            if best_pt:
                self.scene().temp_bridge_pos = (best_pt, best_vec)
            else:
                self.scene().temp_bridge_pos = None
            self.scene().update()
            
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._last_pan_point = event.pos()
            self._panning = True
            # Store initial visual cursor or change it if in Manual Mode it isn't set?
            # Actually, standard pan behavior is "hold to pan".
            # If Manual Mode is ON, we might want to Add Bridge on release if not moved much?
            # User said "hold left button displays cross... move mouse moves view".
            # This implies when button is DOWN, we are panning.
            if self.scene().manual_mode:
                 pass # We still pan. We add bridge only on click-with-no-drag (in release).
            else:
                 self.setCursor(Qt.ClosedHandCursor)

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
             was_panning_moved = False
             if self._panning and self._last_pan_point:
                 # Check if moved significantly?
                 # Actually if we are panning, mouseMoveEvent handles motion.
                 # If mouseMoveEvent was trigged, then we panned.
                 pass

             self._panning = False
             self.setCursor(Qt.ArrowCursor)

             # If we didn't drag/pan much, treat as click for Manual Mode
             # But we need to track if we actually moved.
             # Simplified: bridge adding logic happens if we are in manual mode. 
             # Let's rely on standard 'clicked' signal logic?
             # No, standard signals don't fire if we handled mouse events.
             
             if self.scene().manual_mode:
                 # Just use logic: if we have temp_bridge_pos?
                 # Wait, if we moved, temp_bridge_pos might have changed or cleared?
                 # Let's assume user is precise.
                 if self.scene().temp_bridge_pos:
                     self.clicked.emit(self.scene().temp_bridge_pos[0])
        
        super().mouseReleaseEvent(event)


class BridgeDialog(QDialog):
    def __init__(self, parent=None, selected_items=None):
        super().__init__(parent)
        self.setWindowTitle("加桥位")
        # Resize to be smaller and compact
        self.resize(600, 380)
        
        self.original_items = selected_items or []
        self.bridges = [] # List of tuples: (item_index, distance_on_path)
        
        # Setup UI
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Left: Preview
        self.scene = BridgePreviewScene()
        self.view = BridgePreviewView(self.scene)
        self.view.clicked.connect(self.on_manual_click)
        layout.addWidget(self.view, 1)
        
        # Right: Settings
        right_panel = QWidget()
        right_panel.setFixedWidth(220) # Fixed width for compactness
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        layout.addWidget(right_panel, 0)
        
        # Width Row
        width_row = QWidget()
        width_layout = QHBoxLayout(width_row)
        width_layout.setContentsMargins(0, 0, 0, 0)
        width_layout.addWidget(QLabel("宽度(mm):"))
        self.width_edit = QLineEdit("4.000")
        width_layout.addWidget(self.width_edit)
        right_layout.addWidget(width_row)
        
        # Group Box
        group = QGroupBox("桥位生成方式")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)
        group_layout.setContentsMargins(5, 15, 5, 5)
        
        self.bg = QButtonGroup(self)
        
        # Interval
        self.rb_interval = QRadioButton("按间隔设置桥位")
        self.rb_interval.setChecked(True)
        self.bg.addButton(self.rb_interval)
        group_layout.addWidget(self.rb_interval)
        
        # Indented Interval Input
        inter_widget = QWidget()
        inter_layout = QHBoxLayout(inter_widget)
        inter_layout.setContentsMargins(20, 0, 0, 0) # Indent
        inter_layout.setSpacing(5)
        inter_layout.addWidget(QLabel("间隔(mm):"))
        self.interval_edit = QLineEdit("10.000")
        inter_layout.addWidget(self.interval_edit)
        group_layout.addWidget(inter_widget)
        
        # Count
        self.rb_count = QRadioButton("按数量设置桥位")
        self.bg.addButton(self.rb_count)
        group_layout.addWidget(self.rb_count)
        
        # Indented Count Input
        count_widget = QWidget()
        count_layout = QHBoxLayout(count_widget)
        count_layout.setContentsMargins(20, 0, 0, 0) # Indent
        count_layout.setSpacing(5)
        count_layout.addWidget(QLabel("数量"))
        self.count_edit = QLineEdit("3")
        count_layout.addWidget(self.count_edit)
        group_layout.addWidget(count_widget)
        
        # Manual
        self.rb_manual = QRadioButton("手动设置桥位")
        self.bg.addButton(self.rb_manual)
        group_layout.addWidget(self.rb_manual)
        
        right_layout.addWidget(group)
        
        # Apply button
        self.btn_apply = QPushButton("应 用")
        self.btn_apply.setFixedHeight(30)
        self.btn_apply.clicked.connect(self.apply_preview)
        right_layout.addWidget(self.btn_apply)
        
        right_layout.addStretch()
        
        # OK/Cancel
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_ok.setFixedHeight(30)
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("退出")
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        right_layout.addLayout(btn_layout)
        
        # Connect signals
        self.rb_manual.toggled.connect(self.on_mode_changed)
        self.width_edit.textChanged.connect(self.update_bridge_width)
        
        # Init preview
        self.init_preview()

    def showEvent(self, event):
        super().showEvent(event)
        # Ensure the view is fitted to the scene content when the dialog is shown
        if not self.view.sceneRect().isEmpty():
            self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)
        
    def init_preview(self):
        self.scene.clear()
        self.preview_items = []
        
        if not self.original_items:
            return

        # Calculate bounding rect to fit view
        rect = QRectF()
        for item in self.original_items:
            if isinstance(item, EditablePathItem):
                rect = rect.united(item.sceneBoundingRect())
                
        # Padding
        rect.adjust(-10, -10, 10, 10)
        self.view.setSceneRect(rect)
        self.view.fitInView(rect, Qt.KeepAspectRatio)
        
        for i, item in enumerate(self.original_items):
            if isinstance(item, EditablePathItem):
                # Clone item for preview
                # Note: We need deep clone of points
                pts = item.points()
                new_item = EditablePathItem(pts, QColor(Qt.green), getattr(item, '_smooth', False))
                
                # Update: Use SolidLine as requested (Screenshot 3 issue)
                pen = QPen(Qt.green)
                pen.setStyle(Qt.SolidLine) 
                pen.setWidthF(1) # Thin
                new_item.setPen(pen)
                
                new_item.setPos(item.pos())
                new_item.setTransform(item.transform())
                
                self.scene.addItem(new_item)
                self.preview_items.append((i, new_item)) # Keep mapping to original index
                
    def on_mode_changed(self):
        is_manual = self.rb_manual.isChecked()
        self.scene.manual_mode = is_manual
        self.scene.temp_bridge_pos = None
        
        # Update: Reset preview to initial state when switching modes
        self.bridges = []
        self.update_preview_visuals()
        
        self.scene.update()
        
        # Disable/Enable inputs
        self.interval_edit.setEnabled(self.rb_interval.isChecked())
        self.count_edit.setEnabled(self.rb_count.isChecked())


    def update_bridge_width(self, text):
        try:
            w = float(text)
            self.scene.temp_bridge_width = w
            self.scene.update()
        except ValueError:
            pass

    def on_manual_click(self, pos):
        # Add bridge at pos
        # We need to associate this pos with a specific item and segment
        # We redo the search from mouseMove to be sure
        
        # Use simple distance check to find which preview item is closest
        min_dist = float('inf')
        best_item_idx = -1
        best_d_along = 0.0
        
        for idx, item in self.preview_items:
            # Map pos to item local
            local_pos = item.mapFromScene(pos)
            pts = item.points()
            
            # Find closest point on path
            d_accum = 0.0
            for i in range(len(pts)-1):
                p1 = QPointF(*pts[i])
                p2 = QPointF(*pts[i+1])
                seg_len = math.hypot(p2.x()-p1.x(), p2.y()-p1.y())
                
                # Proj
                l2 = seg_len*seg_len
                if l2 == 0: continue
                
                t = ((local_pos.x()-p1.x())*(p2.x()-p1.x()) + (local_pos.y()-p1.y())*(p2.y()-p1.y())) / l2
                t = max(0, min(1, t))
                
                proj = p1 + (p2 - p1) * t
                dist = math.hypot(local_pos.x()-proj.x(), local_pos.y()-proj.y())
                
                if dist < min_dist:
                    min_dist = dist
                    best_item_idx = idx
                    best_d_along = d_accum + seg_len * t
                
                d_accum += seg_len
                
        if best_item_idx != -1 and min_dist < 5.0: # Tolerance
            self.bridges.append((best_item_idx, best_d_along))
            self.update_preview_visuals()

    def apply_preview(self):
        # Auto generate bridges
        self.bridges = []
        
        try:
            width = float(self.width_edit.text())
            if width <= 0: return
        except ValueError:
            return

        for idx, item in self.preview_items:
            # Calculate total length
            pts = item.points()
            total_len = 0.0
            for i in range(len(pts)-1):
                total_len += math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
            
            # Physical close?
            is_closed = item.is_closed()
            
            if self.rb_interval.isChecked():
                try:
                    interval = float(self.interval_edit.text())
                    if interval <= 0: continue
                    
                    # Generate
                    d = 0.0
                    while d < total_len:
                        if d > 0: # Avoid start point for now, unless wrapper
                            self.bridges.append((idx, d))
                        d += interval
                        
                except ValueError:
                    pass
            
            elif self.rb_count.isChecked():
                try:
                    count = int(self.count_edit.text())
                    if count <= 0: continue
                    
                    if is_closed:
                        step = total_len / count
                        for i in range(count):
                             self.bridges.append((idx, i * step))
                    else:
                        step = total_len / (count + 1)
                        for i in range(1, count + 1):
                             self.bridges.append((idx, i * step))
                             
                except ValueError:
                    pass
                    
        self.update_preview_visuals()

    def update_preview_visuals(self):
        # Redraw bridges on the preview items
        # Currently we just showed the item. We need to visualize cuts.
        # Since we can't easily cut the QGraphicsPathItem visually without modifying geometry,
        # we will draw "blockers" (black rectangles?) over the bridges.
        
        # Remove old blockers
        for item in self.scene.items():
            if getattr(item, "is_blocker", False):
                self.scene.removeItem(item)
                
        try:
            width = float(self.width_edit.text())
        except ValueError:
            width = 4.0

        for bridge in self.bridges:
            item_idx, d_at = bridge
            
            # Find the item
            target_item = None
            for idx, item in self.preview_items:
                if idx == item_idx:
                    target_item = item
                    break
            
            if not target_item: continue
            
            # Locate position and tangent
            pts = target_item.points()
            current_d = 0.0
            found = False
            pt = QPointF(0,0)
            tangent = QPointF(1,0)
            
            for i in range(len(pts)-1):
                p1 = QPointF(*pts[i])
                p2 = QPointF(*pts[i+1])
                seg_len = math.hypot(p2.x()-p1.x(), p2.y()-p1.y())
                
                if current_d + seg_len >= d_at:
                    # Found segment
                    remain = d_at - current_d
                    t = remain / seg_len if seg_len > 0 else 0
                    pt = p1 + (p2 - p1) * t
                    tangent = p2 - p1
                    found = True
                    break
                current_d += seg_len
                
            if found:
                # Draw black rect oriented along tangent
                # Tangent normal
                l = math.hypot(tangent.x(), tangent.y())
                if l > 0:
                    u = tangent / l
                    v = QPointF(-u.y(), u.x())
                    
                    # Create a polygon for the gap
                    # Length = width, Height = something noticeable (e.g. 5)
                    # Use scene coordinates
                    
                    # In Manual mode, user wants to see "Gap". 
                    # If I draw black on black, I see nothing.
                    # But the lines are Green. If I draw Black on top of Green, I see a gap.
                    
                    poly_pts = [
                        pt - u*(width/2) - v*5,
                        pt + u*(width/2) - v*5,
                        pt + u*(width/2) + v*5,
                        pt - u*(width/2) + v*5
                    ]
                    
                    poly_item = self.scene.addPolygon(QPolygonF(poly_pts), QPen(Qt.NoPen), QBrush(Qt.black))
                    poly_item.setZValue(10) # Over green lines
                    poly_item.is_blocker = True
                    # Also need to transform if item has transform? 
                    # We calculated pt in item local space? No, I need to check.
                    # mapToScene logic required if item has transform.
                    # But wait, self.preview_items were cloned with transform.
                    # pts are local. So pt is local.
                    
                    # I need to place blocker in Item Local space and set Item Parent?
                    # Or map to scene.
                    # Simpler to make it child of item.
                    
                    poly_item.setParentItem(target_item)
                    poly_item.setBrush(QBrush(Qt.black)) # Black cuts the green line visually
                    
    def get_result_bridges(self):
        """Returns list of (original_item, list_of_absolute_cut_points)"""
        # Map bridge (idx, d) to real cut objects
        results = {}
        for bridge in self.bridges:
            idx, d = bridge
            item = self.original_items[idx]
            if item not in results:
                results[item] = []
            results[item].append(d)
        
        # Sort cuts by distance
        for item in results:
            results[item].sort()
            
        return results
        
    def get_width(self):
        try:
            return float(self.width_edit.text())
        except:
            return 0.0

from PyQt5.QtGui import QPolygonF
