import copy
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QGraphicsView, QGraphicsScene, QCheckBox, QGroupBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
                             QAbstractItemView, QLabel, QMessageBox, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform, QBrush
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem
import math

class CutPropertyView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.viewport().setMouseTracking(True)
        self.zoom_factor = 1.0

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        self.zoom_factor *= 1.2
        self.scale(1.2, 1.2)

    def zoom_out(self):
        self.zoom_factor /= 1.2
        self.scale(1/1.2, 1/1.2)
    
    def fit_scene(self):
        rect = self.scene().itemsBoundingRect()
        if not rect.isNull():
            self.fitInView(rect, Qt.KeepAspectRatio)
            self.zoom_factor = 1.0


class NodeItem(QGraphicsRectItem):
    """Path node item for editing cut start point"""
    def __init__(self, point, index, parent_item, dialog):
        super().__init__(-3, -3, 6, 6) # 6x6 square
        self.setPos(point)
        self.index = index
        self.dialog = dialog
        self.parent_path_item = parent_item
        self.setBrush(QBrush(Qt.blue))
        self.setPen(QPen(Qt.white, 0))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(100) # above path

    def mouseDoubleClickEvent(self, event):
        # Set this node as start point
        self.dialog.set_start_point(self.parent_path_item, self.index)
        super().mouseDoubleClickEvent(event)


class CutPropertyDialog(QDialog):
    def __init__(self, canvas_scene, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置切割属性")
        self.resize(800, 550)
        self.original_scene = canvas_scene
        self.items_map = {} # Map dialog_item -> original_item
        self.dialog_items = [] # List of items in dialog
        self.sorted_items = [] # Items moved to right list
        
        # Temp scene for preview
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor(250, 250, 250))
        
        self.init_ui()
        self.load_items()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # === Left: Preview Canvas ===
        self.view = CutPropertyView(self.scene)
        self.view.setFrameShape(QGraphicsView.Box)
        self.view.setFrameShadow(QGraphicsView.Plain)
        main_layout.addWidget(self.view, 1)

        # === Right: Controls & Lists ===
        right_panel = QWidget()
        right_panel.setFixedWidth(260)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        main_layout.addWidget(right_panel, 0)

        # --- Top Buttons (Reverse Orders / Reverse Direction) ---
        top_btns_layout = QHBoxLayout()
        top_btns_layout.setSpacing(2)

        self.btn_reverse_seq_left = QPushButton("反序")
        self.btn_reverse_seq_left.clicked.connect(lambda: self.reverse_list_order(self.table_left))
        
        self.btn_reverse_dir = QPushButton("反向")
        self.btn_reverse_dir.clicked.connect(self.reverse_direction)
        
        self.btn_reverse_seq_right = QPushButton("反序") 
        self.btn_reverse_seq_right.clicked.connect(lambda: self.reverse_list_order(self.table_right))

        top_btns_layout.addWidget(self.btn_reverse_seq_left, 1)
        top_btns_layout.addWidget(self.btn_reverse_dir, 1)
        top_btns_layout.addWidget(self.btn_reverse_seq_right, 1)
        right_layout.addLayout(top_btns_layout)

        # --- Lists Area (Left Table | Buttons | Right Table) ---
        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(2)

        # Left List
        self.table_left = QTableWidget()
        self.table_left.setColumnCount(2)
        self.table_left.setHorizontalHeaderLabels(["序号", "名称"])
        self.table_left.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_left.horizontalHeader().resizeSection(0, 40)
        self.table_left.horizontalHeader().setStretchLastSection(True)
        self.table_left.verticalHeader().setVisible(False)
        self.table_left.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_left.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_left.itemSelectionChanged.connect(self.on_left_selection_changed)
        lists_layout.addWidget(self.table_left, 1)

        # Middle Buttons
        mid_btns_layout = QVBoxLayout()
        mid_btns_layout.setContentsMargins(0, 0, 0, 0)
        mid_btns_layout.setSpacing(8)
        
        self.btn_move_right = QPushButton(">>")
        self.btn_move_right.setFixedSize(32, 26)
        self.btn_move_right.clicked.connect(self.move_to_right)

        self.btn_move_all_right = QPushButton(">>>")
        self.btn_move_all_right.setFixedSize(32, 26)
        self.btn_move_all_right.clicked.connect(self.move_all_to_right)

        self.btn_move_all_left = QPushButton("<<<")
        self.btn_move_all_left.setFixedSize(32, 26)
        self.btn_move_all_left.clicked.connect(self.move_all_to_left)

        mid_btns_layout.addWidget(self.btn_move_right, 0, Qt.AlignTop)
        mid_btns_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        mid_btns_layout.addWidget(self.btn_move_all_right, 0, Qt.AlignBottom)
        mid_btns_layout.addSpacing(4)
        mid_btns_layout.addWidget(self.btn_move_all_left, 0, Qt.AlignBottom)
        lists_layout.addLayout(mid_btns_layout, 0)

        # Right List
        self.table_right = QTableWidget()
        self.table_right.setColumnCount(2)
        self.table_right.setHorizontalHeaderLabels(["序号", "名称"])
        self.table_right.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_right.horizontalHeader().resizeSection(0, 40)
        self.table_right.horizontalHeader().setStretchLastSection(True)
        self.table_right.verticalHeader().setVisible(False)
        self.table_right.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_right.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_right.itemSelectionChanged.connect(self.on_right_selection_changed)
        lists_layout.addWidget(self.table_right, 1)

        right_layout.addLayout(lists_layout)

        # --- Bottom Options and Sort Buttons ---
        opts_sort_layout = QHBoxLayout()
        
        # Checkboxes
        opts_layout = QVBoxLayout()
        opts_layout.setSpacing(2)
        self.chk_show_path = QCheckBox("显示路径")
        self.chk_show_path.setChecked(True)
        self.chk_show_path.toggled.connect(self.toggle_path_visibilities)
        self.chk_show_seq = QCheckBox("显示序号")
        self.chk_show_seq.setChecked(True)
        self.chk_show_seq.toggled.connect(self.toggle_path_visibilities)
        opts_layout.addWidget(self.chk_show_path)
        opts_layout.addWidget(self.chk_show_seq)
        opts_sort_layout.addLayout(opts_layout)
        
        opts_sort_layout.addStretch()

        # Up/Down Buttons
        self.btn_up = QPushButton("↑")
        self.btn_up.setFixedSize(30, 30)
        self.btn_up.clicked.connect(self.move_item_up)
        
        self.btn_down = QPushButton("↓")
        self.btn_down.setFixedSize(30, 30)
        self.btn_down.clicked.connect(self.move_item_down)

        opts_sort_layout.addWidget(self.btn_up)
        opts_sort_layout.addWidget(self.btn_down)
        
        right_layout.addLayout(opts_sort_layout)

        # --- Footer Toolbar ---
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 5, 0, 0)
        
        # Tools (Delete, Select) - Icons from text for now
        self.btn_delete = QPushButton("✕") # Delete icon
        self.btn_delete.setFixedSize(30, 30)
        self.btn_delete.setToolTip("删除选中")
        # self.btn_delete.clicked.connect(self.delete_selected) # TODO

        self.btn_select_tool = QPushButton("↖") # Select icon
        self.btn_select_tool.setFixedSize(30, 30)
        self.btn_select_tool.setCheckable(True)
        self.btn_select_tool.setChecked(True)
        self.btn_select_tool.setToolTip("选择模式")

        footer_layout.addWidget(self.btn_delete)
        footer_layout.addWidget(self.btn_select_tool)
        footer_layout.addStretch()

        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        footer_layout.addWidget(self.btn_ok)
        footer_layout.addWidget(self.btn_cancel)
        
        right_layout.addLayout(footer_layout)

    def reverse_list_order(self, table_widget):
        # Stupid simple reverse of table rows
        count = table_widget.rowCount()
        rows = []
        for i in range(count):
            rows.append([table_widget.item(i, 0).clone(), table_widget.item(i, 1).clone()])
            
        rows.reverse()
        
        for i in range(count):
            table_widget.setItem(i, 0, rows[i][0])
            table_widget.setItem(i, 1, rows[i][1])
            
        if table_widget == self.table_right:
            self.sorted_items.reverse()
            self.renumber_right_list() # Sequence numbers should probably reset to 1..N order visually?
            # Usually "Reverse Order" means the cutting order is reversed.
            # So item at top (seq 1) becomes item at bottom (seq N).
            # But the SEQ display usually indicates "Order of execution".
            # So the new top item should display "1".
            # My renumber_right_list does exactly that.

    def move_all_to_right(self):
        # Select all left -> move right
        self.table_left.selectAll()
        self.move_to_right()

    def move_to_left(self):
        """Move selected items from Right to Left list"""
        rows = sorted([index.row() for index in self.table_right.selectionModel().selectedRows()], reverse=True)
        
        for row in rows:
            # Get item info
            t_item_seq = self.table_right.item(row, 0)
            t_item_name = self.table_right.item(row, 1)
            item = t_item_seq.data(Qt.UserRole)
            item_name_text = t_item_name.text() # Keep name

            # Remove from right
            self.table_right.removeRow(row)
            if row < len(self.sorted_items):
                del self.sorted_items[row]
            
            # Reset item state
            item.sorted_seq = None

            # Add to left
            l_row = self.table_left.rowCount()
            self.table_left.insertRow(l_row)
            
            # Use original index for display
            seq_text = str(item.original_index + 1)
            
            new_t_item_seq = QTableWidgetItem(seq_text)
            new_t_item_seq.setData(Qt.UserRole, item)
            
            self.table_left.setItem(l_row, 0, new_t_item_seq)
            self.table_left.setItem(l_row, 1, QTableWidgetItem(item_name_text))
            
        self.renumber_right_list()
        self.scene.update()

    def move_all_to_left(self):
        self.table_right.selectAll()
        self.move_to_left()

    def renumber_right_list(self):
        for row in range(self.table_right.rowCount()):
            seq = row + 1
            item_widget = self.table_right.item(row, 0)
            if item_widget:
                item_widget.setText(str(seq))
                item = item_widget.data(Qt.UserRole)
                if item:
                    item.sorted_seq = seq

    def load_items(self):
        """Load items from original scene to dialog scene"""
        # Get all path items
        items = [i for i in self.original_scene.items() if (isinstance(i, QGraphicsPathItem) or hasattr(i, "path")) and i.isVisible()]
        # Sort by Z value roughly to keep visual order, though we will override cuts
        # BUT usually CNC cut order is determined by a list. 
        # Here we assume current Z-order or just random if not set. 
        # We will put them in Left Table.
        
        items.reverse() # scene.items() returns top-first (highest Z). We usually want bottom-up for initial list? 
        # Actually usually 'drawn first' (bottom) is cut first unless optimized.
        
        self.dialog_items = []
        
        for idx, item in enumerate(items):
            # Create a clone for the dialog
            path = item.path()
            
            new_item = DialogPathItem(path)
            new_item.setPen(QPen(Qt.black, 0))
            new_item.setBrush(QBrush(Qt.NoBrush))
            
            # Transfer transform
            new_item.setTransform(item.transform())
            new_item.setPos(item.pos())
            
            # Store map
            new_item.original_item = item
            new_item.original_index = idx
            new_item.dialog = self
            
            self.scene.addItem(new_item)
            self.dialog_items.append(new_item)
            
            # Add to Left Table
            row = self.table_left.rowCount()
            self.table_left.insertRow(row)
            self.table_left.setItem(row, 0, QTableWidgetItem(str(idx + 1)))
            name = f"图元 {idx + 1}"
            self.table_left.setItem(row, 1, QTableWidgetItem(name))
            
            # Store reference in table item
            self.table_left.item(row, 0).setData(Qt.UserRole, new_item)

        self.view.fit_scene()
        self.update_overlays()

    def update_overlays(self):
        """Draw direction arrows or sequence numbers"""
        for item in self.dialog_items:
            item.show_path = self.chk_show_path.isChecked()
            item.show_seq = self.chk_show_seq.isChecked()
            item.update()

    def toggle_path_visibilities(self):
        self.scene.update()

    def on_left_selection_changed(self):
        # Sync selection to scene
        self.scene.clearSelection()
        selected_rows = self.table_left.selectionModel().selectedRows()
        for idx in selected_rows:
            item = self.table_left.item(idx.row(), 0).data(Qt.UserRole)
            if item:
                item.setSelected(True)
        self.show_nodes_for_selection()

    def on_right_selection_changed(self):
        self.scene.clearSelection()
        selected_rows = self.table_right.selectionModel().selectedRows()
        for idx in selected_rows:
            item = self.table_right.item(idx.row(), 0).data(Qt.UserRole)
            if item:
                item.setSelected(True)
        self.show_nodes_for_selection()
    
    def on_scene_selection_changed(self):
        # Determine which list contains the selected items and highlight rows
        pass # To be implemented if bi-directional selection is needed strictly

    def show_nodes_for_selection(self):
        # Remove old nodes
        for item in self.scene.items():
            if isinstance(item, NodeItem):
                self.scene.removeItem(item)
        
        # Get single selected item
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], DialogPathItem):
            item = selected[0]
            # Create node items
            path = item.path()
            for i in range(path.elementCount()):
                elem = path.elementAt(i)
                # Apply item transform to point
                pt = item.mapToScene(QPointF(elem.x, elem.y))
                node = NodeItem(pt, i, item, self)
                self.scene.addItem(node)

    def move_to_right(self):
        """Move selected items from Left to Right list"""
        rows = sorted([index.row() for index in self.table_left.selectionModel().selectedRows()], reverse=True)
        
        for row in rows:
            # Get item
            t_item_seq = self.table_left.item(row, 0)
            t_item_name = self.table_left.item(row, 1)
            item = t_item_seq.data(Qt.UserRole)
            item_name_text = t_item_name.text()  # 获取文本，因为 removeRow 会删除 item

            # Remove from left
            self.table_left.removeRow(row)
            
            # Add to right
            r_row = self.table_right.rowCount()
            self.table_right.insertRow(r_row)
            
            # Update sequence number for display in right list?
            # Or keep original ID? Usually new sequence.
            new_seq = r_row + 1
            
            new_t_item_seq = QTableWidgetItem(str(new_seq))
            new_t_item_seq.setData(Qt.UserRole, item)
            
            self.table_right.setItem(r_row, 0, new_t_item_seq)
            self.table_right.setItem(r_row, 1, QTableWidgetItem(item_name_text))
            
            self.sorted_items.append(item)
            item.sorted_seq = new_seq # Mark as sorted

        self.scene.update()

    def move_item_up(self):
        current_row = self.table_right.currentRow()
        if current_row > 0:
            self._swap_rows(current_row, current_row - 1)
            self.table_right.selectRow(current_row - 1)

    def move_item_down(self):
        current_row = self.table_right.currentRow()
        if current_row < self.table_right.rowCount() - 1:
            self._swap_rows(current_row, current_row + 1)
            self.table_right.selectRow(current_row + 1)

    def _swap_rows(self, row1, row2):
        # Swap data in list
        item1 = self.sorted_items[row1]
        item2 = self.sorted_items[row2]
        self.sorted_items[row1], self.sorted_items[row2] = item2, item1
        
        # Update Table (lazy way: just swap item pointers and text)
        i1_seq = self.table_right.item(row1, 0)
        i1_name = self.table_right.item(row1, 1)
        
        i2_seq = self.table_right.item(row2, 0)
        i2_name = self.table_right.item(row2, 1)
        
        # Swap UserData
        d1 = i1_seq.data(Qt.UserRole)
        d2 = i2_seq.data(Qt.UserRole)
        i1_seq.setData(Qt.UserRole, d2)
        i2_seq.setData(Qt.UserRole, d1)
        
        # Swap Names
        n1 = i1_name.text()
        n2 = i2_name.text()
        i1_name.setText(n2)
        i2_name.setText(n1)

    def reverse_direction(self):
        selected = self.scene.selectedItems()
        for item in selected:
            if isinstance(item, DialogPathItem):
                path = item.path()
                path = path.toReversed()
                item.setPath(path)
                item.update()

    def set_start_point(self, item, index):
        """Change the start point of the path to index"""
        path = item.path()
        # Only works for polygons/closed paths easily. 
        # For general paths, we need to reconstruction.
        # Simple algorithm for polygons:
        # Get all elements, rotate list so index is 0.
        
        elements = []
        for i in range(path.elementCount()):
            elements.append(path.elementAt(i))
            
        # Check closed?
        if len(elements) < 3: return
        
        # Start constructing new path
        new_path = QPainterPath()
        
        # If it's a closed loop (last point == first point usually or implicit close)
        # We assume standard polygon logic: MoveTo P0, LineTo P1... Close
        
        # Rotate points:
        # Old: 0, 1, 2, 3, 4 (assume 0 is start)
        # New Start: 2
        # New: 2, 3, 4, 0, 1
        
        # Warning: Element 0 is usually MoveTo. Others are LineTo/CurveTo.
        # This simple logic works for Polylines (all LineTo). 
        # For Curves it's harder because connection types matter.
        
        # Let's try simple rotation for MoveTo/LineTo sequences.
        p_start = elements[index]
        new_path.moveTo(p_start.x, p_start.y)
        
        count = len(elements)
        # Are last and first same?
        is_closed = (abs(elements[0].x - elements[-1].x) < 1e-5 and abs(elements[0].y - elements[-1].y) < 1e-5)
        
        # If explicit close, trim last
        actual_points = elements[:-1] if is_closed else elements
        
        count = len(actual_points)
        for i in range(1, count + 1): # loop count times
            idx = (index + i) % count
            p = actual_points[idx]
            new_path.lineTo(p.x, p.y)
            
        if is_closed:
            new_path.closeSubpath()
            
        item.setPath(new_path)
        item.update()
        self.show_nodes_for_selection() # Refresh nodes

    def accept(self):
        # Apply changes to original items
        # 1. Update paths (Reverse / StartPoint)
        for d_item in self.dialog_items:
            # Map transform back? No, we didn't change positions, only path content.
            # But path is local coords.
            o_item = d_item.original_item
            o_item.setPath(d_item.path())
            # o_item.setTransform(d_item.transform()) # If we allowed moving
            
            # 2. Update Order
            # Strategy: We have a sorted list `self.sorted_items`.
            # And remaining items in `table_left`.
            # We can re-assign Z-values.
            # For now, let's just log or set a 'cut_order' property if defined.
        
        # Re-stacking original scene
        # Determine base Z
        base_z = 0
        
        # Apply sorted list first
        for i, d_item in enumerate(self.sorted_items):
            d_item.original_item.setZValue(base_z + i)
            d_item.original_item.setFlag(QGraphicsItem.ItemIsSelectable, True) # Ensure selectable
        
        current_z = base_z + len(self.sorted_items)
        
        # Apply remaining items
        remaining = []
        for row in range(self.table_left.rowCount()):
            d_item = self.table_left.item(row, 0).data(Qt.UserRole)
            if d_item:
                d_item.original_item.setZValue(current_z + row)
        
        
        super().accept()


class DialogPathItem(QGraphicsPathItem):
    def __init__(self, path, parent=None):
        super().__init__(path, parent)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.show_path = True
        self.show_seq = False
        self.sorted_seq = None

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        if self.show_path:
            # Draw direction arrows
            path = self.path()
            count = path.elementCount()
            if count > 1:
                # Draw arrow at mid point or end
                pt1 = path.elementAt(0)
                pt2 = path.elementAt(1)
                
                # ... Simple arrow on first segment ...
                painter.setPen(QPen(Qt.red, 2))
                # painter.drawLine(QPointF(pt1.x, pt1.y), QPointF(pt2.x, pt2.y))
                # Draw Arrow Head
                
                # Better: mid point of path
                length = path.length()
                if length > 0:
                    mid_pct = 0.5
                    pt = path.pointAtPercent(mid_pct)
                    angle = path.angleAtPercent(mid_pct)
                    
                    painter.save()
                    painter.translate(pt)
                    painter.rotate(-angle) # QPainterPath angles are CCW?
                    
                    painter.setBrush(Qt.red)
                    painter.drawPolygon(QPointF(0,0), QPointF(-5, 3), QPointF(-5, -3))
                    painter.restore()

        if self.show_seq and self.sorted_seq is not None:
            # Draw sequence number
            rect = self.boundingRect()
            painter.setPen(Qt.blue)
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, str(self.sorted_seq))
        
        if self.isSelected():
            painter.setPen(QPen(Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())
