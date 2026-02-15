from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGridLayout,
    QGroupBox,
    QWidget,
    QCheckBox,
    QRadioButton,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsPathItem,
    QFrame,
    QShortcut,
    QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QPen, QColor, QPainterPath, QPainter, QTransform, QKeySequence, QBrush
from functools import partial


class AutoLayoutDialog(QDialog):
    # mode: 'real' or 'virtual'
    # params: dict of layout parameters
    apply_layout_signal = pyqtSignal(str, dict)

    def __init__(self, selected_items, canvas_size=(1200, 800), parent=None):
        super().__init__(parent)
        self.setWindowTitle("排版处理")
        self.resize(1100, 720)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.selected_items = selected_items
        self.orig_canvas_w = float(canvas_size[0])
        self.orig_canvas_h = float(canvas_size[1])

        self.item_rect = self._calculate_selection_bounds()
        self.item_w = max(0.1, self.item_rect.width())
        self.item_h = max(0.1, self.item_rect.height())
        # Global array orientation used by preview/apply. Values: 0 or 90.
        self.layout_rot_deg = 0.0
        self._validated_field_specs = {}
        self._committed_values = {}

        self.setup_ui()
        self.update_preview()

    def _calculate_selection_bounds(self):
        if not self.selected_items:
            return QRectF(0, 0, 100, 100)

        rect = QRectF()
        first = True
        for item in self.selected_items:
            br = item.sceneBoundingRect()
            if first:
                rect = br
                first = False
            else:
                rect = rect.united(br)

        if first:
            return QRectF(0, 0, 100, 100)
        return rect

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Left: Preview ---
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)

        self.work_area_rect_item = QGraphicsRectItem(0, 0, self.orig_canvas_w, self.orig_canvas_h)
        self.work_area_rect_item.setPen(QPen(Qt.black, 2))
        self.scene.addItem(self.work_area_rect_item)

        self.view.fitInView(self.work_area_rect_item, Qt.KeepAspectRatio)
        main_layout.addWidget(self.view, stretch=1)

        # --- Right: Controls ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(5)
        right_panel.setFixedWidth(360)

        # 1. Rows/Cols
        row_col_layout = QHBoxLayout()
        self.row_edit = QLineEdit("1")
        self.col_edit = QLineEdit("1")
        row_col_layout.addWidget(QLabel("行数:"))
        row_col_layout.addWidget(self.row_edit)
        row_col_layout.addWidget(QLabel("列数:"))
        row_col_layout.addWidget(self.col_edit)
        right_layout.addLayout(row_col_layout)

        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(line1)

        # 2. Spacings
        grid_params = QGridLayout()

        self.odd_row_space = QLineEdit("0.000")
        self.even_row_space = QLineEdit("0.000")
        self.btn_auto_row_space = QPushButton("自动计算")
        grid_params.addWidget(QLabel("奇行间距(mm):"), 0, 0)
        grid_params.addWidget(self.odd_row_space, 0, 1)
        grid_params.addWidget(self.btn_auto_row_space, 0, 2)
        grid_params.addWidget(QLabel("偶行间距(mm):"), 1, 0)
        grid_params.addWidget(self.even_row_space, 1, 1)

        self.odd_col_space = QLineEdit("0.000")
        self.even_col_space = QLineEdit("0.000")
        self.btn_auto_col_space = QPushButton("自动计算")
        grid_params.addWidget(QLabel("奇列间距(mm):"), 2, 0)
        grid_params.addWidget(self.odd_col_space, 2, 1)
        grid_params.addWidget(self.btn_auto_col_space, 2, 2)
        grid_params.addWidget(QLabel("偶列间距(mm):"), 3, 0)
        grid_params.addWidget(self.even_col_space, 3, 1)
        right_layout.addLayout(grid_params)

        # 3. Offsets
        offset_grid = QGridLayout()
        self.row_offset = QLineEdit("0.000")
        self.col_offset = QLineEdit("0.000")
        self.btn_auto_row_offset = QPushButton("自动计算")
        self.btn_auto_col_offset = QPushButton("自动计算")
        offset_grid.addWidget(QLabel("行错位(mm):"), 0, 0)
        offset_grid.addWidget(self.row_offset, 0, 1)
        offset_grid.addWidget(self.btn_auto_row_offset, 0, 2)
        offset_grid.addWidget(QLabel("列错位(mm):"), 1, 0)
        offset_grid.addWidget(self.col_offset, 1, 1)
        offset_grid.addWidget(self.btn_auto_col_offset, 1, 2)
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

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
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
        self.rb_offset = QRadioButton("行列错位")
        self.rb_all.setChecked(True)

        radio_layout.addWidget(self.rb_odd, 0, 0)
        radio_layout.addWidget(self.rb_even, 0, 1)
        radio_layout.addWidget(self.rb_all, 1, 0)
        radio_layout.addWidget(self.rb_offset, 1, 1)
        manual_layout.addLayout(radio_layout)

        right_layout.addWidget(manual_grp)

        # 7. Work Area Group
        area_grp = QGroupBox()
        area_layout = QGridLayout(area_grp)
        self.x_area = QLineEdit(f"{self.orig_canvas_w:.1f}")
        self.y_area = QLineEdit(f"{self.orig_canvas_h:.1f}")
        self.btn_machine_area = QPushButton("机器幅面")
        self.btn_software_area = QPushButton("软件幅面")

        area_layout.addWidget(QLabel("X幅面(mm):"), 0, 0)
        area_layout.addWidget(self.x_area, 0, 1)
        area_layout.addWidget(self.btn_machine_area, 0, 2)
        area_layout.addWidget(QLabel("Y幅面(mm):"), 1, 0)
        area_layout.addWidget(self.y_area, 1, 1)
        area_layout.addWidget(self.btn_software_area, 1, 2)
        right_layout.addWidget(area_grp)

        # 8. Auto adjust
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

        # 9. Fill
        self.btn_fill = QPushButton("布满幅面")
        right_layout.addWidget(self.btn_fill)

        # 10. Bottom buttons
        bottom_btns = QHBoxLayout()
        self.btn_real = QPushButton("转实阵列")
        self.btn_virtual = QPushButton("转虚拟阵列")
        self.btn_cancel = QPushButton("取消")

        bottom_btns.addWidget(self.btn_real)
        bottom_btns.addWidget(self.btn_virtual)
        bottom_btns.addWidget(self.btn_cancel)
        right_layout.addLayout(bottom_btns)

        main_layout.addWidget(right_panel)

        # Signal connections
        self._register_validated_field(self.row_edit, "int", min_value=1)
        self._register_validated_field(self.col_edit, "int", min_value=1)
        self._register_validated_field(self.odd_row_space, "float", min_value=0.0)
        self._register_validated_field(self.even_row_space, "float", min_value=0.0)
        self._register_validated_field(self.odd_col_space, "float", min_value=0.0)
        self._register_validated_field(self.even_col_space, "float", min_value=0.0)
        self._register_validated_field(self.row_offset, "float", min_value=None)
        self._register_validated_field(self.col_offset, "float", min_value=None)
        self._register_validated_field(self.safe_dist, "float", min_value=0.0)
        self._register_validated_field(self.x_area, "float", min_value=0.1)
        self._register_validated_field(self.y_area, "float", min_value=0.1)

        checks = [self.row_mirror_h, self.row_mirror_v, self.col_mirror_h, self.col_mirror_v]
        for w in checks:
            w.stateChanged.connect(self.update_preview)

        self.btn_auto_row_space.clicked.connect(self.auto_calc_row_spacing)
        self.btn_auto_col_space.clicked.connect(self.auto_calc_col_spacing)
        self.btn_auto_row_offset.clicked.connect(self.auto_calc_row_offset)
        self.btn_auto_col_offset.clicked.connect(self.auto_calc_col_offset)

        self.btn_machine_area.clicked.connect(self.on_machine_area)
        self.btn_software_area.clicked.connect(self.on_software_area)

        self.btn_fill.clicked.connect(self.calculate_fill)
        self.btn_real.clicked.connect(self.on_real)
        self.btn_virtual.clicked.connect(self.on_virtual)
        self.btn_cancel.clicked.connect(self.reject)

        self._setup_nudge_shortcuts()
        self._snapshot_committed_values()

    def _setup_nudge_shortcuts(self):
        self._nudge_shortcuts = []
        for key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda k=key: self._on_nudge_key(k))
            self._nudge_shortcuts.append(shortcut)

    def _on_nudge_key(self, key):
        if self._apply_manual_adjust(key):
            self.update_preview()

    def _register_validated_field(self, field, kind, min_value=None):
        self._validated_field_specs[field] = {"kind": kind, "min": min_value}
        field.editingFinished.connect(partial(self._on_validated_field_commit, field))

    def _parse_field_value(self, field, text=None):
        spec = self._validated_field_specs.get(field)
        if spec is None:
            raise ValueError("unknown field")

        raw = field.text() if text is None else text
        raw = str(raw).strip()
        if raw == "":
            raise ValueError("empty")

        if spec["kind"] == "int":
            value = int(raw)
        else:
            value = float(raw)

        min_value = spec.get("min")
        if min_value is not None and value < min_value:
            raise ValueError("below_min")
        return value

    def _format_field_value(self, field, value):
        spec = self._validated_field_specs.get(field, {})
        if spec.get("kind") == "int":
            return str(int(round(float(value))))
        if field in (self.x_area, self.y_area):
            return f"{float(value):.1f}"
        return f"{float(value):.3f}"

    def _set_field_value(self, field, value):
        field.setText(self._format_field_value(field, value))

    def _snapshot_committed_values(self):
        for field in list(self._validated_field_specs.keys()):
            try:
                self._committed_values[field] = self._parse_field_value(field)
            except Exception:
                pass

    def _layout_bounds(self):
        rows = max(1, int(float(self.row_edit.text())))
        cols = max(1, int(float(self.col_edit.text())))
        board_w = max(0.1, float(self.x_area.text()))
        board_h = max(0.1, float(self.y_area.text()))

        safe = max(0.0, float(self.safe_dist.text()))
        odd_r_gap = max(0.0, float(self.odd_row_space.text())) + safe
        even_r_gap = max(0.0, float(self.even_row_space.text())) + safe
        odd_c_gap = max(0.0, float(self.odd_col_space.text())) + safe
        even_c_gap = max(0.0, float(self.even_col_space.text())) + safe

        r_offset = float(self.row_offset.text())
        c_offset = float(self.col_offset.text())
        rot_deg = self._normalize_layout_rotation(self.layout_rot_deg)
        item_w, item_h = self._layout_item_size(rot_deg)

        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for _, _, x_pos, y_pos, _, _ in self._iter_layout_cells(
            rows,
            cols,
            item_w,
            item_h,
            odd_r_gap,
            even_r_gap,
            odd_c_gap,
            even_c_gap,
            r_offset,
            c_offset,
            self.row_mirror_h.isChecked(),
            self.row_mirror_v.isChecked(),
            self.col_mirror_h.isChecked(),
            self.col_mirror_v.isChecked(),
        ):
            min_x = min(min_x, x_pos)
            min_y = min(min_y, y_pos)
            max_x = max(max_x, x_pos + item_w)
            max_y = max(max_y, y_pos + item_h)

        if min_x == float("inf"):
            min_x = min_y = 0.0
            max_x = max_y = 0.0

        return min_x, min_y, max_x, max_y, board_w, board_h

    def _would_layout_overflow(self):
        min_x, min_y, max_x, max_y, board_w, board_h = self._layout_bounds()
        eps = 1e-9
        reasons = []
        if min_x < -eps:
            reasons.append(f"左边超出 {abs(min_x):.3f} mm")
        if min_y < -eps:
            reasons.append(f"上边超出 {abs(min_y):.3f} mm")
        if max_x > board_w + eps:
            reasons.append(f"右边超出 {max_x - board_w:.3f} mm")
        if max_y > board_h + eps:
            reasons.append(f"下边超出 {max_y - board_h:.3f} mm")

        if reasons:
            return True, "当前参数会导致排版越界：\n" + "；".join(reasons)
        return False, ""

    def _on_validated_field_commit(self, field):
        if field not in self._validated_field_specs:
            self.update_preview()
            return

        previous = self._committed_values.get(field)
        raw = field.text().strip()
        try:
            value = self._parse_field_value(field, raw)
        except Exception:
            if previous is not None:
                self._set_field_value(field, previous)
            QMessageBox.warning(self, "输入错误", "输入值无效，已恢复修改前的数值。")
            self.update_preview()
            return

        # normalize integer input text immediately
        if self._validated_field_specs[field]["kind"] == "int":
            field.setText(str(int(value)))

        overflow, reason = self._would_layout_overflow()
        if overflow:
            if previous is not None:
                self._set_field_value(field, previous)
            QMessageBox.warning(self, "参数越界", reason + "\n\n已恢复修改前的数值。")
            self.update_preview()
            return

        self._committed_values[field] = value
        self.update_preview()

    def on_enable_auto_changed(self, state):
        self.auto_sub_widget.setEnabled(state == Qt.Checked)

    def get_float(self, field):
        try:
            return float(field.text())
        except Exception:
            return 0.0

    def get_int(self, field):
        try:
            val = int(field.text())
            return max(1, val)
        except Exception:
            return 1

    def _set_float(self, field, value, digits=3):
        field.setText(f"{float(value):.{digits}f}")

    def _normalize_layout_rotation(self, deg):
        try:
            d = float(deg) % 360.0
        except Exception:
            return 0.0
        # Only keep 0/90 modes for RDWorks-like optimization.
        d = 90.0 if abs(d - 90.0) <= 45.0 or abs(d - 270.0) <= 45.0 else 0.0
        return d

    def _layout_item_size(self, rot_deg=None):
        rot = self.layout_rot_deg if rot_deg is None else rot_deg
        rot = self._normalize_layout_rotation(rot)
        if abs(rot - 90.0) < 1e-9:
            return self.item_h, self.item_w
        return self.item_w, self.item_h

    def _scene_shape_path(self, item):
        local_path = QPainterPath()

        # Prefer geometry path when available, fallback to shape.
        if hasattr(item, "path"):
            try:
                p = item.path()
                if p and not p.isEmpty():
                    local_path = QPainterPath(p)
            except Exception:
                local_path = QPainterPath()

        if local_path.isEmpty() and hasattr(item, "shape"):
            try:
                local_path = QPainterPath(item.shape())
            except Exception:
                local_path = QPainterPath()

        if local_path.isEmpty():
            br = item.boundingRect()
            if br.isValid() and not br.isEmpty():
                local_path.addRect(br)

        try:
            return item.mapToScene(local_path)
        except Exception:
            return QPainterPath()

    def _spacing_sum(self, count, odd_gap, even_gap):
        total = 0.0
        for idx in range(max(0, count - 1)):
            is_even = ((idx + 1) % 2 == 0)
            total += even_gap if is_even else odd_gap
        return total

    def _iter_layout_cells(self, rows, cols, item_w, item_h, odd_r_gap, even_r_gap, odd_c_gap, even_c_gap, r_offset, c_offset, row_mirror_h, row_mirror_v, col_mirror_h, col_mirror_v):
        current_y = 0.0
        for r in range(rows):
            is_even_row = ((r + 1) % 2 == 0)
            row_spacing = even_r_gap if is_even_row else odd_r_gap

            current_x = r_offset if is_even_row else 0.0

            row_mx = bool(row_mirror_h and is_even_row)
            row_my = bool(row_mirror_v and is_even_row)

            for c in range(cols):
                is_even_col = ((c + 1) % 2 == 0)
                col_spacing = even_c_gap if is_even_col else odd_c_gap

                y_pos = current_y + (c_offset if is_even_col else 0.0)

                mirror_x = row_mx ^ bool(col_mirror_h and is_even_col)
                mirror_y = row_my ^ bool(col_mirror_v and is_even_col)

                yield r, c, current_x, y_pos, mirror_x, mirror_y

                current_x += item_w + col_spacing

            current_y += item_h + row_spacing

    def _layout_span(self, rows, cols, item_w, item_h, odd_r_gap, even_r_gap, odd_c_gap, even_c_gap, r_offset, c_offset):
        width = cols * item_w + self._spacing_sum(cols, odd_c_gap, even_c_gap)
        height = rows * item_h + self._spacing_sum(rows, odd_r_gap, even_r_gap)
        if rows >= 2:
            width += abs(r_offset)
        if cols >= 2:
            height += abs(c_offset)
        return width, height

    def _max_offset_limits(self, rows, cols, board_w, board_h, item_w, item_h, odd_r_gap, even_r_gap, odd_c_gap, even_c_gap):
        """Return non-negative max allowed |row_offset| and |col_offset| that still keep layout in board."""
        base_w = cols * item_w + self._spacing_sum(cols, odd_c_gap, even_c_gap)
        base_h = rows * item_h + self._spacing_sum(rows, odd_r_gap, even_r_gap)

        max_r_offset = max(0.0, board_w - base_w) if rows >= 2 else 0.0
        max_c_offset = max(0.0, board_h - base_h) if cols >= 2 else 0.0
        return max_r_offset, max_c_offset

    def _estimate_max_count(self, axis_len, item_len, odd_gap, even_gap, hard_cap=1000):
        if axis_len <= 0.0:
            return 1
        if item_len <= 0.0:
            return 1

        n = 1
        used = item_len
        while n < hard_cap:
            gap = even_gap if (n % 2 == 0) else odd_gap
            candidate = used + gap + item_len
            if candidate <= axis_len + 1e-9:
                used = candidate
                n += 1
            else:
                break
        return max(1, n)

    def auto_calc_row_spacing(self):
        rows = self.get_int(self.row_edit)
        cols = self.get_int(self.col_edit)
        board_h = max(0.1, self.get_float(self.y_area))
        safe = max(0.0, self.get_float(self.safe_dist))
        c_offset = self.get_float(self.col_offset)
        _, item_h = self._layout_item_size()

        if rows <= 1:
            self._set_float(self.odd_row_space, 0.0)
            self._set_float(self.even_row_space, 0.0)
            self.update_preview()
            return

        base_h = rows * item_h + (abs(c_offset) if cols >= 2 else 0.0)
        available_for_gaps = max(0.0, board_h - base_h)
        avg_gap = available_for_gaps / (rows - 1)
        user_gap = max(0.0, avg_gap - safe)

        self._set_float(self.odd_row_space, user_gap)
        self._set_float(self.even_row_space, user_gap)
        self.update_preview()

    def auto_calc_col_spacing(self):
        rows = self.get_int(self.row_edit)
        cols = self.get_int(self.col_edit)
        board_w = max(0.1, self.get_float(self.x_area))
        safe = max(0.0, self.get_float(self.safe_dist))
        r_offset = self.get_float(self.row_offset)
        item_w, _ = self._layout_item_size()

        if cols <= 1:
            self._set_float(self.odd_col_space, 0.0)
            self._set_float(self.even_col_space, 0.0)
            self.update_preview()
            return

        base_w = cols * item_w + (abs(r_offset) if rows >= 2 else 0.0)
        available_for_gaps = max(0.0, board_w - base_w)
        avg_gap = available_for_gaps / (cols - 1)
        user_gap = max(0.0, avg_gap - safe)

        self._set_float(self.odd_col_space, user_gap)
        self._set_float(self.even_col_space, user_gap)
        self.update_preview()

    def auto_calc_row_offset(self):
        rows = self.get_int(self.row_edit)
        cols = self.get_int(self.col_edit)
        board_w = max(0.1, self.get_float(self.x_area))
        board_h = max(0.1, self.get_float(self.y_area))
        safe = max(0.0, self.get_float(self.safe_dist))
        odd_r_gap = max(0.0, self.get_float(self.odd_row_space)) + safe
        even_r_gap = max(0.0, self.get_float(self.even_row_space)) + safe
        odd_c_gap = max(0.0, self.get_float(self.odd_col_space)) + safe
        even_c_gap = max(0.0, self.get_float(self.even_col_space)) + safe

        avg_col_gap = (max(0.0, self.get_float(self.odd_col_space)) + max(0.0, self.get_float(self.even_col_space))) * 0.5
        item_w, item_h = self._layout_item_size()
        pitch_x = item_w + safe + avg_col_gap
        desired = pitch_x * 0.5
        max_r_offset, _ = self._max_offset_limits(
            rows, cols, board_w, board_h, item_w, item_h, odd_r_gap, even_r_gap, odd_c_gap, even_c_gap
        )
        self._set_float(self.row_offset, min(desired, max_r_offset))
        self.update_preview()

    def auto_calc_col_offset(self):
        rows = self.get_int(self.row_edit)
        cols = self.get_int(self.col_edit)
        board_w = max(0.1, self.get_float(self.x_area))
        board_h = max(0.1, self.get_float(self.y_area))
        safe = max(0.0, self.get_float(self.safe_dist))
        odd_r_gap = max(0.0, self.get_float(self.odd_row_space)) + safe
        even_r_gap = max(0.0, self.get_float(self.even_row_space)) + safe
        odd_c_gap = max(0.0, self.get_float(self.odd_col_space)) + safe
        even_c_gap = max(0.0, self.get_float(self.even_col_space)) + safe

        avg_row_gap = (max(0.0, self.get_float(self.odd_row_space)) + max(0.0, self.get_float(self.even_row_space))) * 0.5
        item_w, item_h = self._layout_item_size()
        pitch_y = item_h + safe + avg_row_gap
        desired = pitch_y * 0.5
        _, max_c_offset = self._max_offset_limits(
            rows, cols, board_w, board_h, item_w, item_h, odd_r_gap, even_r_gap, odd_c_gap, even_c_gap
        )
        self._set_float(self.col_offset, min(desired, max_c_offset))
        self.update_preview()

    def _distribute_row_spacing(self, rows, cols, board_h, safe, c_offset, item_h):
        if rows <= 1:
            self._set_float(self.odd_row_space, 0.0)
            self._set_float(self.even_row_space, 0.0)
            return

        base_h = rows * item_h + (abs(c_offset) if cols >= 2 else 0.0)
        available_for_gaps = max(0.0, board_h - base_h)
        avg_gap = available_for_gaps / (rows - 1)
        user_gap = max(0.0, avg_gap - safe)

        self._set_float(self.odd_row_space, user_gap)
        self._set_float(self.even_row_space, user_gap)

    def _distribute_col_spacing(self, rows, cols, board_w, safe, r_offset, item_w):
        if cols <= 1:
            self._set_float(self.odd_col_space, 0.0)
            self._set_float(self.even_col_space, 0.0)
            return

        base_w = cols * item_w + (abs(r_offset) if rows >= 2 else 0.0)
        available_for_gaps = max(0.0, board_w - base_w)
        avg_gap = available_for_gaps / (cols - 1)
        user_gap = max(0.0, avg_gap - safe)

        self._set_float(self.odd_col_space, user_gap)
        self._set_float(self.even_col_space, user_gap)

    def calculate_fill(self):
        board_w = max(0.1, self.get_float(self.x_area))
        board_h = max(0.1, self.get_float(self.y_area))

        safe = max(0.0, self.get_float(self.safe_dist))
        auto_enabled = self.chk_enable_auto.isChecked()

        # Minimum gaps considered by fill solver
        min_odd_r = safe if (auto_enabled and self.chk_auto_row.isChecked()) else max(0.0, self.get_float(self.odd_row_space)) + safe
        min_even_r = safe if (auto_enabled and self.chk_auto_row.isChecked()) else max(0.0, self.get_float(self.even_row_space)) + safe
        min_odd_c = safe if (auto_enabled and self.chk_auto_col.isChecked()) else max(0.0, self.get_float(self.odd_col_space)) + safe
        min_even_c = safe if (auto_enabled and self.chk_auto_col.isChecked()) else max(0.0, self.get_float(self.even_col_space)) + safe

        cur_r_offset = self.get_float(self.row_offset)
        cur_c_offset = self.get_float(self.col_offset)

        current_rot = self._normalize_layout_rotation(self.layout_rot_deg)
        rotate_candidates = [current_rot]
        if auto_enabled:
            for rot in (0.0, 90.0):
                if all(abs(rot - x) > 1e-9 for x in rotate_candidates):
                    rotate_candidates.append(rot)

        # In auto mode, offsets should not lock filling into low count layouts.
        # Try several offset candidates and pick the one with:
        # 1) max quantity, 2) max used area, 3) min leftover.
        best_rows = 1
        best_cols = 1
        best_score = 1
        best_r_offset = cur_r_offset
        best_c_offset = cur_c_offset
        best_rot = current_rot
        best_area = 0.0
        best_leftover = float("inf")

        for rot_deg in rotate_candidates:
            item_w, item_h = self._layout_item_size(rot_deg)
            max_cols = self._estimate_max_count(board_w, item_w, min_odd_c, min_even_c)
            max_rows = self._estimate_max_count(board_h, item_h, min_odd_r, min_even_r)

            offset_candidates = [(cur_r_offset, cur_c_offset)]
            if auto_enabled:
                half_x = 0.5 * (item_w + min_odd_c)
                half_y = 0.5 * (item_h + min_odd_r)
                offset_candidates.extend(
                    [
                        (0.0, 0.0),
                        (0.0, cur_c_offset),
                        (cur_r_offset, 0.0),
                        (half_x, cur_c_offset),
                        (cur_r_offset, half_y),
                        (half_x, half_y),
                    ]
                )

            # Deduplicate candidates with stable order.
            seen = set()
            dedup_offsets = []
            for ro, co in offset_candidates:
                key = (round(float(ro), 6), round(float(co), 6))
                if key in seen:
                    continue
                seen.add(key)
                dedup_offsets.append((float(ro), float(co)))

            for r_offset, c_offset in dedup_offsets:
                for r in range(1, max_rows + 1):
                    for c in range(1, max_cols + 1):
                        span_w, span_h = self._layout_span(
                            r,
                            c,
                            item_w,
                            item_h,
                            min_odd_r,
                            min_even_r,
                            min_odd_c,
                            min_even_c,
                            r_offset,
                            c_offset,
                        )
                        if span_w <= board_w + 1e-9 and span_h <= board_h + 1e-9:
                            score = r * c
                            used_area = span_w * span_h
                            leftover = (board_w - span_w) + (board_h - span_h)
                            better = False
                            if score > best_score:
                                better = True
                            elif score == best_score and used_area > best_area + 1e-9:
                                better = True
                            elif score == best_score and abs(used_area - best_area) <= 1e-9 and leftover < best_leftover - 1e-9:
                                better = True
                            elif (
                                score == best_score
                                and abs(used_area - best_area) <= 1e-9
                                and abs(leftover - best_leftover) <= 1e-9
                                and (r + c > best_rows + best_cols)
                            ):
                                better = True
                            elif (
                                score == best_score
                                and abs(used_area - best_area) <= 1e-9
                                and abs(leftover - best_leftover) <= 1e-9
                                and (r + c == best_rows + best_cols)
                                and abs(rot_deg - current_rot) < 1e-9
                                and abs(best_rot - current_rot) > 1e-9
                            ):
                                # Keep stable when completely tied.
                                better = True

                            if better:
                                best_score = score
                                best_rows = r
                                best_cols = c
                                best_r_offset = r_offset
                                best_c_offset = c_offset
                                best_rot = rot_deg
                                best_area = used_area
                                best_leftover = leftover

        self.row_edit.setText(str(best_rows))
        self.col_edit.setText(str(best_cols))
        self.layout_rot_deg = best_rot

        if auto_enabled:
            self._set_float(self.row_offset, best_r_offset)
            self._set_float(self.col_offset, best_c_offset)
            best_item_w, best_item_h = self._layout_item_size(best_rot)
            if self.chk_auto_row.isChecked():
                self._distribute_row_spacing(best_rows, best_cols, board_h, safe, best_c_offset, best_item_h)
            if self.chk_auto_col.isChecked():
                self._distribute_col_spacing(best_rows, best_cols, board_w, safe, best_r_offset, best_item_w)
            if self.chk_auto_mirror.isChecked():
                # Keep behavior stable and predictable: row horizontal mirror as default auto mirror mode.
                self.row_mirror_h.setChecked(best_rows > 1)
                self.row_mirror_v.setChecked(False)
                self.col_mirror_h.setChecked(False)
                self.col_mirror_v.setChecked(False)

        self.update_preview()

    def update_preview(self):
        for item in self.scene.items():
            if item != self.work_area_rect_item:
                self.scene.removeItem(item)

        board_w = max(0.1, self.get_float(self.x_area))
        board_h = max(0.1, self.get_float(self.y_area))
        self.work_area_rect_item.setRect(0, 0, board_w, board_h)
        self.view.fitInView(self.work_area_rect_item, Qt.KeepAspectRatio)

        rows = self.get_int(self.row_edit)
        cols = self.get_int(self.col_edit)

        safe = max(0.0, self.get_float(self.safe_dist))
        odd_r_gap = max(0.0, self.get_float(self.odd_row_space)) + safe
        even_r_gap = max(0.0, self.get_float(self.even_row_space)) + safe
        odd_c_gap = max(0.0, self.get_float(self.odd_col_space)) + safe
        even_c_gap = max(0.0, self.get_float(self.even_col_space)) + safe

        r_offset = self.get_float(self.row_offset)
        c_offset = self.get_float(self.col_offset)
        rot_deg = self._normalize_layout_rotation(self.layout_rot_deg)
        item_w, item_h = self._layout_item_size(rot_deg)

        # Build base shape path from all selected items (scene coordinates -> selection local)
        base_path = QPainterPath()
        for item in self.selected_items:
            p = self._scene_shape_path(item)
            if p and not p.isEmpty():
                base_path.addPath(p)

        if base_path.isEmpty():
            base_path.addRect(-self.item_w / 2.0, -self.item_h / 2.0, self.item_w, self.item_h)
        else:
            center = self.item_rect.center()
            base_path.translate(-center.x(), -center.y())

        for _, _, x_pos, y_pos, mirror_x, mirror_y in self._iter_layout_cells(
            rows,
            cols,
            item_w,
            item_h,
            odd_r_gap,
            even_r_gap,
            odd_c_gap,
            even_c_gap,
            r_offset,
            c_offset,
            self.row_mirror_h.isChecked(),
            self.row_mirror_v.isChecked(),
            self.col_mirror_h.isChecked(),
            self.col_mirror_v.isChecked(),
        ):
            preview_item = QGraphicsPathItem(base_path)
            preview_item.setPen(QPen(QColor(255, 100, 50), 1))
            preview_item.setBrush(QBrush(Qt.NoBrush))
            preview_item.setPos(x_pos + item_w / 2.0, y_pos + item_h / 2.0)

            tr = QTransform()
            if abs(rot_deg) > 1e-9:
                tr.rotate(rot_deg)
            if mirror_x or mirror_y:
                sx = -1 if mirror_x else 1
                sy = -1 if mirror_y else 1
                tr.scale(sx, sy)
            preview_item.setTransform(tr)

            self.scene.addItem(preview_item)

        self._snapshot_committed_values()

    def _manual_mode(self):
        if self.rb_odd.isChecked():
            return "odd"
        if self.rb_even.isChecked():
            return "even"
        if self.rb_offset.isChecked():
            return "offset"
        return "all"

    def _apply_manual_adjust(self, key):
        step = max(0.001, self.get_float(self.nudge_dist))
        mode = self._manual_mode()

        dx = 0.0
        dy = 0.0
        if key == Qt.Key_Left:
            dx = -step
        elif key == Qt.Key_Right:
            dx = step
        elif key == Qt.Key_Up:
            dy = step
        elif key == Qt.Key_Down:
            dy = -step
        else:
            return False

        def add_value(field, delta, clamp_non_negative=False):
            val = self.get_float(field) + delta
            if clamp_non_negative:
                val = max(0.0, val)
            self._set_float(field, val)

        if mode == "offset":
            # 左右调行错位，上下调列错位
            if dx != 0.0:
                add_value(self.row_offset, dx, clamp_non_negative=False)
            if dy != 0.0:
                add_value(self.col_offset, dy, clamp_non_negative=False)
        elif mode == "odd":
            if dx != 0.0:
                add_value(self.odd_col_space, dx, clamp_non_negative=True)
            if dy != 0.0:
                add_value(self.odd_row_space, dy, clamp_non_negative=True)
        elif mode == "even":
            if dx != 0.0:
                add_value(self.even_col_space, dx, clamp_non_negative=True)
            if dy != 0.0:
                add_value(self.even_row_space, dy, clamp_non_negative=True)
        else:
            if dx != 0.0:
                add_value(self.odd_col_space, dx, clamp_non_negative=True)
                add_value(self.even_col_space, dx, clamp_non_negative=True)
            if dy != 0.0:
                add_value(self.odd_row_space, dy, clamp_non_negative=True)
                add_value(self.even_row_space, dy, clamp_non_negative=True)

        return True

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

    def on_machine_area(self):
        # Prefer current canvas size from parent window
        w = self.orig_canvas_w
        h = self.orig_canvas_h
        try:
            parent = self.parent()
            if parent and hasattr(parent, "whiteboard") and hasattr(parent.whiteboard, "canvas"):
                canvas = parent.whiteboard.canvas
                w = float(getattr(canvas, "_work_w", w))
                h = float(getattr(canvas, "_work_h", h))
        except Exception:
            pass

        self.x_area.setText(f"{w:.1f}")
        self.y_area.setText(f"{h:.1f}")
        self.update_preview()

    def on_software_area(self):
        self.x_area.setText(f"{self.orig_canvas_w:.1f}")
        self.y_area.setText(f"{self.orig_canvas_h:.1f}")
        self.update_preview()

    def on_real(self):
        self._apply("real")

    def on_virtual(self):
        self._apply("virtual")

    def _apply(self, mode):
        params = {
            "rows": self.get_int(self.row_edit),
            "cols": self.get_int(self.col_edit),
            "odd_r_s": max(0.0, self.get_float(self.odd_row_space)),
            "even_r_s": max(0.0, self.get_float(self.even_row_space)),
            "odd_c_s": max(0.0, self.get_float(self.odd_col_space)),
            "even_c_s": max(0.0, self.get_float(self.even_col_space)),
            "r_offset": self.get_float(self.row_offset),
            "c_offset": self.get_float(self.col_offset),
            "row_mirror_h": self.row_mirror_h.isChecked(),
            "row_mirror_v": self.row_mirror_v.isChecked(),
            "col_mirror_h": self.col_mirror_h.isChecked(),
            "col_mirror_v": self.col_mirror_v.isChecked(),
            "safe_dist": max(0.0, self.get_float(self.safe_dist)),
            "nudge_dist": max(0.001, self.get_float(self.nudge_dist)),
            "manual_mode": self._manual_mode(),
            "board_w": max(0.1, self.get_float(self.x_area)),
            "board_h": max(0.1, self.get_float(self.y_area)),
            "enable_auto": self.chk_enable_auto.isChecked(),
            "auto_row": self.chk_auto_row.isChecked(),
            "auto_col": self.chk_auto_col.isChecked(),
            "auto_mirror": self.chk_auto_mirror.isChecked(),
            "layout_rot_deg": self._normalize_layout_rotation(self.layout_rot_deg),
        }
        self.apply_layout_signal.emit(mode, params)
        self.accept()
