from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QGridLayout, QGroupBox, 
                             QWidget, QCheckBox, QRadioButton, QButtonGroup,
                             QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                             QGraphicsPathItem, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QPen, QColor, QPainterPath

import copy
import math

class AutoLayoutDialog(QDialog):
    # Signal to create array in main window
    # mode: 'real' or 'virtual'
    # params: dict of layout parameters
    apply_layout_signal = pyqtSignal(str, dict)

    def __init__(self, selected_items, canvas_size=(1200, 800), parent=None):
        super().__init__(parent)
        self.setWindowTitle("排版处理")
        self.resize(1000, 700)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # Data
        self.selected_items = selected_items
        self.orig_canvas_w = canvas_size[0]
        self.orig_canvas_h = canvas_size[1]
        
        # Calculate bounding box of selected items
        self.item_rect = self._calculate_selection_bounds()
        self.item_w = self.item_rect.width()
        self.item_h = self.item_rect.height()

        self.setup_ui()
        self.update_preview()

    def _calculate_selection_bounds(self):
        if not self.selected_items:
            return QRectF(0, 0, 100, 100)
        
        # Combine all bounding rects
        rect = QRectF()
        first = True
        for item in self.selected_items:
            # item.sceneBoundingRect() is better if available, but let's assume item.boundingRect() mapped to scene
            # If items are from different parents, we should map to scene.
            # Assuming items are from the main scene.
            br = item.sceneBoundingRect()
            if first:
                rect = br
                first = False
            else:
                rect = rect.united(br)
        return rect

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        # --- Left: Preview ---
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(0x1) # Antialiasing (QPainter.Antialiasing = 1)
        # Draw a border rectangle representing the work area
        self.work_area_rect_item = QGraphicsRectItem(0, 0, self.orig_canvas_w, self.orig_canvas_h)
        self.work_area_rect_item.setPen(QPen(Qt.black, 2))
        self.scene.addItem(self.work_area_rect_item)
        
        # We need to scale the view to fit the work area
        self.view.fitInView(self.work_area_rect_item, Qt.KeepAspectRatio)
        
        main_layout.addWidget(self.view, stretch=1)
        
        # --- Right: Controls ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(5)
        right_panel.setFixedWidth(300)
        
        # 1. Rows/Cols
        row_col_layout = QHBoxLayout()
        self.row_edit = QLineEdit("1")
        self.col_edit = QLineEdit("1")
        row_col_layout.addWidget(QLabel("行数:"))
        row_col_layout.addWidget(self.row_edit)
        row_col_layout.addWidget(QLabel("列数:"))
        row_col_layout.addWidget(self.col_edit)
        right_layout.addLayout(row_col_layout)
        
        # Separator line like in screenshot
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(line1)
        
        # 2. Spacings
        grid_params = QGridLayout()
        
        self.odd_row_space = QLineEdit("0.000")
        self.even_row_space = QLineEdit("0.000")
        grid_params.addWidget(QLabel("奇行间距(mm):"), 0, 0)
        grid_params.addWidget(self.odd_row_space, 0, 1)
        grid_params.addWidget(QPushButton("自动计算"), 0, 2)
        grid_params.addWidget(QLabel("偶行间距(mm):"), 1, 0)
        grid_params.addWidget(self.even_row_space, 1, 1)

        self.odd_col_space = QLineEdit("0.000")
        self.even_col_space = QLineEdit("0.000")
        grid_params.addWidget(QLabel("奇列间距(mm):"), 2, 0)
        grid_params.addWidget(self.odd_col_space, 2, 1)
        grid_params.addWidget(QPushButton("自动计算"), 2, 2)
        grid_params.addWidget(QLabel("偶列间距(mm):"), 3, 0)
        grid_params.addWidget(self.even_col_space, 3, 1)
        
        right_layout.addLayout(grid_params)
        
        # 3. Offsets
        offset_grid = QGridLayout()
        self.row_offset = QLineEdit("0.000")
        self.col_offset = QLineEdit("0.000")
        offset_grid.addWidget(QLabel("行错位(mm):"), 0, 0)
        offset_grid.addWidget(self.row_offset, 0, 1)
        offset_grid.addWidget(QPushButton("自动计算"), 0, 2)
        offset_grid.addWidget(QLabel("列错位(mm):"), 1, 0)
        offset_grid.addWidget(self.col_offset, 1, 1)
        offset_grid.addWidget(QPushButton("自动计算"), 1, 2)
        right_layout.addLayout(offset_grid)
        
        # 4. Mirror
        mirror_layout = QGridLayout()
        self.row_mirror_h = QCheckBox("H")
        self.row_mirror_v = QCheckBox("V")
        self.col_mirror_h = QCheckBox("H")
        self.col_mirror_v = QCheckBox("V")
        
        mirror_layout.addWidget(QLabel("行镜像:"), 0, 0)
        mirror_layout.addWidget(self.row_mirror_h, 0, 1)
        mirror_layout.addWidget(self.row_mirror_v, 0, 2)
        mirror_layout.addWidget(QLabel("列镜像:"), 1, 0)
        mirror_layout.addWidget(self.col_mirror_h, 1, 1)
        mirror_layout.addWidget(self.col_mirror_v, 1, 2)
        right_layout.addLayout(mirror_layout)
        
        # Line
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        right_layout.addWidget(line2)
        
        # 5. Safe Distance
        safe_layout = QHBoxLayout()
        self.safe_dist = QLineEdit("0.000")
        safe_layout.addWidget(QLabel("安全距离(mm):"))
        safe_layout.addWidget(self.safe_dist)
        right_layout.addLayout(safe_layout)
        
        # 6. Manual Adjust Group
        manual_grp = QGroupBox("手动调整")
        manual_layout = QVBoxLayout(manual_grp)
        
        nudge_layout = QHBoxLayout()
        self.nudge_dist = QLineEdit("0.100")
        nudge_layout.addWidget(QLabel("按键点动距离:"))
        nudge_layout.addWidget(self.nudge_dist)
        nudge_layout.addWidget(QLabel("mm"))
        manual_layout.addLayout(nudge_layout)
        
        radio_layout = QGridLayout()
        self.rb_odd = QRadioButton("奇数行/列")
        self.rb_even = QRadioButton("偶数行/列")
        self.rb_all = QRadioButton("所有行/列")
        self.rb_all.setChecked(True)
        self.rb_offset = QRadioButton("行列错位")
        
        radio_layout.addWidget(self.rb_odd, 0, 0)
        radio_layout.addWidget(self.rb_even, 0, 1)
        radio_layout.addWidget(self.rb_all, 1, 0)
        radio_layout.addWidget(self.rb_offset, 1, 1)
        manual_layout.addLayout(radio_layout)
        
        right_layout.addWidget(manual_grp)
        
        # 7. Work Area Group
        area_grp = QGroupBox()
        area_layout = QGridLayout(area_grp)
        self.x_area = QLineEdit(str(self.orig_canvas_w))
        self.y_area = QLineEdit(str(self.orig_canvas_h))
        
        area_layout.addWidget(QLabel("X幅面(mm):"), 0, 0)
        area_layout.addWidget(self.x_area, 0, 1)
        area_layout.addWidget(QPushButton("机器幅面"), 0, 2)
        area_layout.addWidget(QLabel("Y幅面(mm):"), 1, 0)
        area_layout.addWidget(self.y_area, 1, 1)
        area_layout.addWidget(QPushButton("软件幅面"), 1, 2)
        right_layout.addWidget(area_grp)
        
        # 8. Auto Adjust Check
        self.chk_enable_auto = QCheckBox("使能自动调整功能")
        self.chk_enable_auto.stateChanged.connect(self.on_enable_auto_changed)
        right_layout.addWidget(self.chk_enable_auto)
        
        auto_sub_layout = QVBoxLayout()
        auto_sub_layout.setContentsMargins(20, 0, 0, 0)
        self.chk_auto_row = QCheckBox("自动调整行间距")
        self.chk_auto_col = QCheckBox("自动调整列间距")
        self.chk_auto_mirror = QCheckBox("自动调整镜像")
        self.chk_auto_row.setChecked(True)
        self.chk_auto_col.setChecked(True)
        self.chk_auto_mirror.setChecked(True)
        
        auto_sub_layout.addWidget(self.chk_auto_row)
        auto_sub_layout.addWidget(self.chk_auto_col)
        auto_sub_layout.addWidget(self.chk_auto_mirror)
        
        self.auto_sub_widget = QWidget()
        self.auto_sub_widget.setLayout(auto_sub_layout)
        self.auto_sub_widget.setEnabled(False)
        right_layout.addWidget(self.auto_sub_widget)
        
        # 9. Fill Button
        self.btn_fill = QPushButton("布满幅面")
        self.btn_fill.clicked.connect(self.calculate_fill)
        right_layout.addWidget(self.btn_fill)
        
        # 10. Bottom Buttons
        bottom_btns = QHBoxLayout()
        self.btn_real = QPushButton("转实阵列")
        self.btn_virtual = QPushButton("转虚拟阵列")
        self.btn_cancel = QPushButton("取消")
        
        self.btn_real.clicked.connect(self.on_real)
        self.btn_virtual.clicked.connect(self.on_virtual)
        self.btn_cancel.clicked.connect(self.reject)
        
        bottom_btns.addWidget(self.btn_real)
        bottom_btns.addWidget(self.btn_virtual)
        bottom_btns.addWidget(self.btn_cancel)
        right_layout.addLayout(bottom_btns)
        
        main_layout.addWidget(right_panel)

        # Connect signals for live update
        for w in [self.row_edit, self.col_edit, 
                  self.odd_row_space, self.even_row_space,
                  self.odd_col_space, self.even_col_space,
                  self.row_offset, self.col_offset,
                  self.row_mirror_h, self.row_mirror_v,
                  self.col_mirror_h, self.col_mirror_v]:
             if isinstance(w, QLineEdit):
                 w.editingFinished.connect(self.update_preview)
             elif isinstance(w, QCheckBox):
                 w.stateChanged.connect(self.update_preview)

    def on_enable_auto_changed(self, state):
        self.auto_sub_widget.setEnabled(state == Qt.Checked)

    def get_float(self, field):
        try:
            return float(field.text())
        except ValueError:
            return 0.0

    def get_int(self, field):
        try:
            return int(field.text())
        except ValueError:
            return 1

    def calculate_fill(self):
        # Calculate max rows and columns to fill the area
        board_w = self.get_float(self.x_area)
        board_h = self.get_float(self.y_area)
        
        safe = self.get_float(self.safe_dist)
        
        # Use existing settings for spacing if auto is NOT checked?
        # User prompt check: "Enable auto adjust function... software automatically layout based on algorithm"
        # If enabled, we might want to minimize spacing.
        # Simplest fill logic:
        # Columns: Need (ColCount * ItemW) + (ColCount -1) * Space <= BoardW
        
        # Spacing logic
        space_x = self.get_float(self.odd_col_space) # Simplify to one spacing for standard fill
        space_y = self.get_float(self.odd_row_space)
        
        # Effective dimension of one item + gap
        # Only if we don't do complex nesting.
        # Stagger/Offset effects:
        # If row offset exists, keys into the column count?
        
        # Simple Grid Estimate
        nx = int((board_w + space_x) / (self.item_w + space_x))
        ny = int((board_h + space_y) / (self.item_h + space_y))
        
        if nx < 1: nx = 1
        if ny < 1: ny = 1
            
        self.row_edit.setText(str(ny))
        self.col_edit.setText(str(nx))
        
        self.update_preview()
        
    def update_preview(self):
        # Clear existing preview items (BUT NOT the board rect)
        for item in self.scene.items():
            if item != self.work_area_rect_item:
                self.scene.removeItem(item)
        
        # Update board rect from inputs
        board_w = self.get_float(self.x_area)
        board_h = self.get_float(self.y_area)
        self.work_area_rect_item.setRect(0, 0, board_w, board_h)
        self.view.fitInView(self.work_area_rect_item, Qt.KeepAspectRatio)

        # Get Params
        rows = self.get_int(self.row_edit)
        cols = self.get_int(self.col_edit)
        
        odd_r_s = self.get_float(self.odd_row_space)
        even_r_s = self.get_float(self.even_row_space)
        odd_c_s = self.get_float(self.odd_col_space)
        even_c_s = self.get_float(self.even_col_space)
        
        r_offset = self.get_float(self.row_offset)
        c_offset = self.get_float(self.col_offset)
        
        # Build layout
        # Origin of selection relative to its bounding box
        # We need to clone the shape.
        # For preview, we can just draw the bounding box or the path if it's a path item.
        # But user wants to see the shape (Screenshot 2 shows shapes).
        
        # Base Path/Shape
        # We'll create a single QPainterPath for the selection
        base_path = QPainterPath()
        for item in self.selected_items:
            # Map item path to the selection bounding box coordinate system
            # offset = item.pos() - self.item_rect.topLeft()
            # actually we want them relative to the top-left of the group
            
            # Simple way: Map everything to scene, then translate to (0,0)
            if hasattr(item, 'path'): # QGraphicsPathItem
                # Get scene path
                p = item.mapToScene(item.path())
                base_path.addPath(p)
            elif hasattr(item, 'shape'):
                p = item.mapToScene(item.shape())
                base_path.addPath(p)
        
        # Translate base_path so its top-left is at (0,0)
        br = base_path.boundingRect()
        base_path.translate(-br.left(), -br.top())
        
        # Loop and Place
        current_y = 0.0
        
        for r in range(rows):
            is_even_row = ((r + 1) % 2 == 0)
            
            # Determine row height (use item height usually)
            # Spacing AFTER this row
            row_spacing = even_r_s if is_even_row else odd_r_s
            
            current_x = 0.0
            
            # Row Offset apply to X start
            if is_even_row:
                current_x += r_offset
            
            # Row Mirror Check
            # If row mirror is checked, we flip the item?
            # self.row_mirror_h.isChecked() -> Flip Horizontally for this row? 
            # Usually means alternating rows are flipped.
            mirror_x = False
            mirror_y = False
            
            if self.row_mirror_h.isChecked() and is_even_row:
                mirror_x = not mirror_x
            if self.row_mirror_v.isChecked() and is_even_row:
                mirror_y = not mirror_y
                
            for c in range(cols):
                is_even_col = ((c + 1) % 2 == 0)
                col_spacing = even_c_s if is_even_col else odd_c_s
                
                # Column Offset apply to Y? Usually col offset shifts the column vertically.
                y_pos = current_y
                if is_even_col:
                    y_pos += c_offset
                
                # Column Mirror
                if self.col_mirror_h.isChecked() and is_even_col:
                    mirror_x = not mirror_x
                if self.col_mirror_v.isChecked() and is_even_col:
                    mirror_y = not mirror_y
                
                # Create Item
                preview_item = QGraphicsPathItem(base_path)
                preview_item.setPen(QPen(QColor(255, 100, 50), 1)) # Orange color like screenshot
                
                # Transform (Scale for mirror, Translate for pos)
                # Note: Mirroring about the center of the item item_w/2, item_h/2
                
                sx = -1 if mirror_x else 1
                sy = -1 if mirror_y else 1
                
                # If we scale -1, the pos changes.
                # Center of the item is at current_x + w/2, y_pos + h/2
                
                # Simple translate first
                preview_item.setPos(current_x, y_pos)
                
                # Apply mirror transform locally if needed
                if sx == -1 or sy == -1:
                    # Transform origin to center
                    tr = preview_item.transform()
                    tr.translate(self.item_w/2, self.item_h/2)
                    tr.scale(sx, sy)
                    tr.translate(-self.item_w/2, -self.item_h/2)
                    preview_item.setTransform(tr)

                self.scene.addItem(preview_item)
                
                current_x += self.item_w + col_spacing
                
            current_y += self.item_h + row_spacing

    def on_real(self):
        self._apply('real')

    def on_virtual(self):
        self._apply('virtual')

    def _apply(self, mode):
        # Gather all params and emit
        params = {
            'rows': self.get_int(self.row_edit),
            'cols': self.get_int(self.col_edit),
            'odd_r_s': self.get_float(self.odd_row_space),
            'even_r_s': self.get_float(self.even_row_space),
            'odd_c_s': self.get_float(self.odd_col_space),
            'even_c_s': self.get_float(self.even_col_space),
            'r_offset': self.get_float(self.row_offset),
            'c_offset': self.get_float(self.col_offset),
            'row_mirror_h': self.row_mirror_h.isChecked(),
            'row_mirror_v': self.row_mirror_v.isChecked(),
            'col_mirror_h': self.col_mirror_h.isChecked(),
            'col_mirror_v': self.col_mirror_v.isChecked(),
        }
        self.apply_layout_signal.emit(mode, params)
        self.accept()
