#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加工预览对话框
"""
import math
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QSlider, QWidget, QGraphicsView, 
                             QGraphicsScene, QGraphicsItem, QGraphicsPathItem,
                             QGroupBox, QProgressBar, QSizePolicy, QGraphicsEllipseItem, QGraphicsRectItem,
                             QGraphicsPixmapItem)
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QLineF
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QFont, QTransform, QPolygonF

def calculate_micro_joint_splits(points, config):
    if not points or len(points) < 2:
        return [points]
        
    # Convert QPointF to list of tuples if needed, or work with QPointF directly
    # Working with QPointF objects
    
    segment_lengths = []
    total_len = 0.0
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i+1]
        dist = math.hypot(p2.x()-p1.x(), p2.y()-p1.y())
        segment_lengths.append(dist)
        total_len += dist
        
    if total_len <= 1e-6:
        return [points]

    cut_centers = []
    mode = config.get('mode', 'qty')
    if mode == 'qty':
        qty = int(config.get('qty', 0))
        if qty > 0:
            step = total_len / (qty + 1)
            for i in range(1, qty + 1):
                cut_centers.append(step * i)
    else: # dist
        dist_val = float(config.get('dist', 0))
        if dist_val > 0:
            cur = dist_val
            while cur < total_len:
                cut_centers.append(cur)
                cur += dist_val
    
    if not cut_centers:
        return [points]
        
    width = float(config.get('width', 0.0))
    half_w = width / 2.0
    
    # Generate Keep Intervals
    # Intervals to remove
    remove_ranges = []
    for c in cut_centers:
        s = max(0.0, c - half_w)
        e = min(total_len, c + half_w)
        if s < e:
            remove_ranges.append((s,e))
    
    if not remove_ranges:
        return [points]
        
    remove_ranges.sort()
    
    # Invert to Keep Intervals
    keep_intervals = []
    curr = 0.0
    for r_s, r_e in remove_ranges:
        if r_s > curr:
            keep_intervals.append((curr, r_s))
        curr = max(curr, r_e)
    if curr < total_len:
        keep_intervals.append((curr, total_len))
        
    result_paths = []
    
    def get_pt_at_dist(d):
        accum = 0.0
        for i, seg_len in enumerate(segment_lengths):
            if d <= accum + seg_len + 1e-9:
                local_d = d - accum
                t = local_d / seg_len if seg_len > 1e-9 else 0
                p1 = points[i]
                p2 = points[i+1]
                return QPointF(p1.x() + (p2.x()-p1.x())*t, p1.y() + (p2.y()-p1.y())*t)
            accum += seg_len
        return points[-1]

    for k_s, k_e in keep_intervals:
        if k_e <= k_s + 1e-9: continue
        
        subpath = []
        subpath.append(get_pt_at_dist(k_s))
        
        # Add intermediate points
        accum = 0.0
        # Iterate original points (vertices)
        for i in range(len(points)):
            if i == 0: 
                accum = 0.0
            else:
                accum += segment_lengths[i-1]
            
            # If vertex is strictly inside interval
            if accum > k_s + 1e-5 and accum < k_e - 1e-5:
                subpath.append(points[i])
        
        subpath.append(get_pt_at_dist(k_e))
        result_paths.append(subpath)
        
    return result_paths

class CrosshairItem(QGraphicsItem):
    def __init__(self, size=20, color=QColor(0, 255, 0), parent=None):
        super().__init__(parent)
        self.size = size
        self.color = color
        self.setZValue(1000)

    def boundingRect(self):
        s = self.size / 2
        return QRectF(-s, -s, self.size, self.size)

    def paint(self, painter, option, widget):
        pen = QPen(self.color)
        pen.setWidth(1) # Thin line
        pen.setCosmetic(True)
        painter.setPen(pen)
        
        s = self.size / 2
        # Horizontal
        painter.drawLine(QPointF(-s, 0), QPointF(s, 0))
        # Vertical
        painter.drawLine(QPointF(0, -s), QPointF(0, s))
        # Optional: Small box in center
        # painter.drawRect(QRectF(-2, -2, 4, 4))

class PreviewCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor(0, 0, 0)) # 黑色背景
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # 坐标轴/边框
        self.border_item = None
        
        # 激光头标记 (改为十字架)
        self.head_marker = CrosshairItem(size=30, color=QColor(0, 255, 0))
        self.scene.addItem(self.head_marker)
        self.head_marker.setVisible(False)
        
        # 已加工路径（改为粉红色）
        self.traversed_path_item = QGraphicsPathItem()
        # 类似截图3的粉红色
        self.traversed_path_item.setPen(QPen(QColor(255, 105, 180), 1.5)) 
        self.traversed_path_item.setZValue(500) # 在原路径之上，激光头之下
        self.scene.addItem(self.traversed_path_item)

    def wheelEvent(self, event):
        zoom_in = event.angleDelta().y() > 0
        factor = 1.1 if zoom_in else 0.9
        self.scale(factor, factor)

    def set_work_area(self, width, height):
        if self.border_item:
            self.scene.removeItem(self.border_item)
        
        rect = QRectF(0, 0, width, height)
        pen = QPen(QColor(100, 100, 100))
        pen.setWidth(1)
        self.border_item = self.scene.addRect(rect, pen)
        self.scene.setSceneRect(rect.adjusted(-50, -50, 50, 50))

class PreviewDialog(QDialog):
    def __init__(self, canvas_items, work_size=(600, 400), layer_data=None, parent=None, laser_pos=QPointF(0,0),
                 scan_direction=None):
        super().__init__(parent)
        self.setWindowTitle("加工预览")
        self.resize(1000, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        
        self.items = canvas_items
        self.work_w, self.work_h = work_size
        self.layer_data = layer_data or {}
        self.laser_start_pos = laser_pos # 激光头初始位置
        self.scan_direction = scan_direction or "从上往下(从左往右)"
        
        # 仿真状态
        self.is_running = False
        self.is_paused = False
        self.sim_speed_ratio = 1.0
        self.default_speed = 497.0 # mm/s
        self.current_path_index = 0
        self.current_segment_index = 0
        self.current_t = 0.0 # 0.0 to 1.0 along segment
        self.total_time = 0.0
        self.elapsed_time = 0.0
        
        # 路径数据 [(type, path_item, length, speed, power)]
        # type: 'cut' or 'move'
        self.sim_paths = [] 
        
        self.init_ui()
        self.process_paths()
        self.update_stats()
        
        # 定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_tick)
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧预览区
        self.preview_view = PreviewCanvas()
        self.preview_view.set_work_area(self.work_w, self.work_h)
        layout.addWidget(self.preview_view, 1)
        
        # 右侧控制面板
        right_panel = QWidget()
        right_panel.setFixedWidth(280)
        right_panel.setStyleSheet("background-color: #f0f0f0; border-left: 1px solid #ccc;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)
        
        # 1. 统计信息
        stats_group = QGroupBox()
        stats_group.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 3px; margin-top: 0px; }")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(5)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_size = self.create_stat_label("图形尺寸:", "0.0mm, 0.0mm")
        self.lbl_proc_time = self.create_stat_label("加工时间:", "0:00:00.000")
        self.lbl_laser_time = self.create_stat_label("开光时间:", "0:00:00.000")
        self.lbl_travel_dist = self.create_stat_label("空走距离:", "0.0mm")
        self.lbl_proc_dist = self.create_stat_label("加工距离:", "0.0mm")
        
        stats_layout.addWidget(self.lbl_size)
        stats_layout.addWidget(self.lbl_proc_time)
        stats_layout.addWidget(self.lbl_laser_time)
        stats_layout.addWidget(self.lbl_travel_dist)
        stats_layout.addWidget(self.lbl_proc_dist)
        right_layout.addWidget(stats_group)
        
        # 2. 实时状态
        status_group = QGroupBox()
        status_group.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 3px; margin-top: 0px; }")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(5)
        status_layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_cur_pos = self.create_stat_label("当前位置:", "0.0mm, 0.0mm")
        self.lbl_cur_speed = self.create_stat_label("当前速度:", "0.0mm/s")
        self.lbl_cur_power = self.create_stat_label("当前能量:", "0.0%")
        
        status_layout.addWidget(self.lbl_cur_pos)
        status_layout.addWidget(self.lbl_cur_speed)
        status_layout.addWidget(self.lbl_cur_power)
        
        # 进度条
        progress_container = QWidget()
        pc_layout = QHBoxLayout(progress_container)
        pc_layout.setContentsMargins(0,0,0,0)
        pc_layout.addWidget(QLabel("当前进度:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 2px;
                background-color: #f0f0f0;
                height: 15px;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                width: 5px;
                margin: 1px;
            }
        """)
        pc_layout.addWidget(self.progress_bar)
        status_layout.addWidget(progress_container)
        
        right_layout.addWidget(status_group)
        
        # 3. 设置
        settings_group = QGroupBox()
        settings_group.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 3px; margin-top: 0px; }")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(5, 5, 5, 5)
        
        # 默认速度
        spd_layout = QHBoxLayout()
        spd_layout.addWidget(QLabel("默认速度:"))
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(1, 1000)
        self.slider_speed.setValue(int(self.default_speed))
        self.slider_speed.valueChanged.connect(self.on_speed_changed)
        spd_layout.addWidget(self.slider_speed)
        self.lbl_speed_val = QLabel(f"{int(self.default_speed)}")
        self.lbl_speed_val.setStyleSheet("background-color: black; color: #00FF00; padding: 2px; font-weight: bold;")
        self.lbl_speed_val.setFixedWidth(40)
        self.lbl_speed_val.setAlignment(Qt.AlignCenter)
        spd_layout.addWidget(self.lbl_speed_val)
        settings_layout.addLayout(spd_layout)
        
        # 仿真速比
        ratio_layout = QHBoxLayout()
        ratio_layout.addWidget(QLabel("仿真速比:"))
        self.slider_ratio = QSlider(Qt.Horizontal)
        self.slider_ratio.setRange(1, 100) # 0.1x to 10.0x
        self.slider_ratio.setValue(10) # 1.0x
        self.slider_ratio.valueChanged.connect(self.on_ratio_changed)
        ratio_layout.addWidget(self.slider_ratio)
        self.lbl_ratio_val = QLabel("1.0")
        self.lbl_ratio_val.setStyleSheet("background-color: black; color: #00FF00; padding: 2px; font-weight: bold;")
        self.lbl_ratio_val.setFixedWidth(40)
        self.lbl_ratio_val.setAlignment(Qt.AlignCenter)
        ratio_layout.addWidget(self.lbl_ratio_val)
        settings_layout.addLayout(ratio_layout)
        
        # 4. 按钮 (移入设置组下方)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 5, 0, 0)
        self.btn_sim = QPushButton("仿真")
        self.btn_sim.setFixedHeight(30)
        self.btn_sim.clicked.connect(self.start_simulation)
        self.btn_pause = QPushButton("暂停/继续")
        self.btn_pause.setFixedHeight(30)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setFixedHeight(30)
        self.btn_stop.clicked.connect(self.stop_simulation)
        
        btn_layout.addWidget(self.btn_sim)
        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(self.btn_stop)
        
        settings_layout.addLayout(btn_layout)
        
        right_layout.addWidget(settings_group)
        
        right_layout.addStretch()
        
        layout.addWidget(right_panel)

    def create_stat_label(self, title, default_val):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl_title = QLabel(title)
        lbl_title.setFixedWidth(70) # 固定宽度对齐
        lbl_title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        lbl_val = QLabel(default_val)
        lbl_val.setStyleSheet("background-color: black; color: #00FF00; padding: 2px; font-weight: bold; border: 1px solid #555;")
        lbl_val.setAlignment(Qt.AlignCenter)
        lbl_val.setFixedHeight(24)
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        return container

    def update_stat_value(self, container, value):
        label = container.findChild(QLabel, "")
        # The second label is the value label, but findChild might find the first one if not careful.
        # Better way: store references.
        # Re-implementing create_stat_label to return the value label directly would be cleaner, 
        # but here I'll just iterate layout items.
        layout = container.layout()
        if layout.count() > 1:
            widget = layout.itemAt(1).widget()
            if isinstance(widget, QLabel):
                widget.setText(value)

    def get_scan_segments(self, shape_path, interval, mode, scan_direction=None):
        """生成扫描线段列表"""
        segments = []
        
        # 1. 获取多边形近似
        polys = shape_path.toSubpathPolygons()
        if not polys: return []
        
        scan_direction = scan_direction or self.scan_direction
        is_vertical = "垂直" in mode
        is_bidirectional = "双向" in mode
        start_from_bottom = "从下往上" in scan_direction
        start_from_left = "从左往右" in scan_direction

        # 2. 获取范围
        br = shape_path.boundingRect()
        min_y = br.top()
        max_y = br.bottom()
        min_x = br.left()
        max_x = br.right()
        
        # 防止死循环
        if interval <= 0.001: interval = 0.1

        if not is_vertical:
            y = max_y if start_from_bottom else min_y
            line_index = 0

            def y_in_range(val):
                return val >= min_y if start_from_bottom else val <= max_y

            while y_in_range(y):
                x_intersects = []

                for poly in polys:
                    if poly.count() < 2:
                        continue

                    p1 = poly.first()
                    for i in range(1, poly.count()):
                        p2 = poly.at(i)
                        y1, y2 = p1.y(), p2.y()
                        x1, x2 = p1.x(), p2.x()

                        if y1 > y2:
                            y1, y2 = y2, y1
                            x1, x2 = x2, x1

                        if y1 <= y < y2:
                            if abs(y2 - y1) > 1e-9:
                                x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                                x_intersects.append(x)

                        p1 = p2

                    p2 = poly.first()
                    y1, y2 = p1.y(), p2.y()
                    x1, x2 = p1.x(), p2.x()

                    if y1 > y2:
                        y1, y2 = y2, y1
                        x1, x2 = x2, x1

                    if y1 <= y < y2:
                        if abs(y2 - y1) > 1e-9:
                            x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                            x_intersects.append(x)

                x_intersects.sort()

                left_to_right = start_from_left
                if is_bidirectional and (line_index % 2 == 1):
                    left_to_right = not left_to_right

                for i in range(0, len(x_intersects), 2):
                    if i + 1 < len(x_intersects):
                        x_start = x_intersects[i]
                        x_end = x_intersects[i + 1]

                        if left_to_right:
                            segments.append(QLineF(x_start, y, x_end, y))
                        else:
                            segments.append(QLineF(x_end, y, x_start, y))

                y += -interval if start_from_bottom else interval
                line_index += 1
        else:
            x = min_x if start_from_left else max_x
            line_index = 0

            def x_in_range(val):
                return val <= max_x if start_from_left else val >= min_x

            while x_in_range(x):
                y_intersects = []

                for poly in polys:
                    if poly.count() < 2:
                        continue

                    p1 = poly.first()
                    for i in range(1, poly.count()):
                        p2 = poly.at(i)
                        x1, x2 = p1.x(), p2.x()
                        y1, y2 = p1.y(), p2.y()

                        if x1 > x2:
                            x1, x2 = x2, x1
                            y1, y2 = y2, y1

                        if x1 <= x < x2:
                            if abs(x2 - x1) > 1e-9:
                                y_val = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
                                y_intersects.append(y_val)

                        p1 = p2

                    p2 = poly.first()
                    x1, x2 = p1.x(), p2.x()
                    y1, y2 = p1.y(), p2.y()

                    if x1 > x2:
                        x1, x2 = x2, x1
                        y1, y2 = y2, y1

                    if x1 <= x < x2:
                        if abs(x2 - x1) > 1e-9:
                            y_val = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
                            y_intersects.append(y_val)

                y_intersects.sort()

                bottom_to_top = start_from_bottom
                if is_bidirectional and (line_index % 2 == 1):
                    bottom_to_top = not bottom_to_top

                for i in range(0, len(y_intersects), 2):
                    if i + 1 < len(y_intersects):
                        y_low = y_intersects[i]
                        y_high = y_intersects[i + 1]

                        if bottom_to_top:
                            segments.append(QLineF(x, y_high, x, y_low))
                        else:
                            segments.append(QLineF(x, y_low, x, y_high))

                x += interval if start_from_left else -interval
                line_index += 1
            
        return segments

    def generate_scan_path(self, shape_path, interval, mode, scan_direction=None):
        """生成用于显示的扫描路径"""
        segments = self.get_scan_segments(shape_path, interval, mode, scan_direction)
        path = QPainterPath()
        for line in segments:
            path.moveTo(line.p1())
            path.lineTo(line.p2())
        return path

    def process_paths(self):
        """处理路径数据，生成仿真指令"""
        self.sim_paths = []
        total_cut_len = 0.0
        total_travel_len = 0.0
        
        # 1. 收集所有需要加工的项并排序
        # 这里简化处理，直接按列表顺序，实际应按图层优先级
        # 假设传入的 items 已经是排好序的
        
        last_pos = self.laser_start_pos
        
        # 显示激光头初始位置
        self.preview_view.head_marker.setPos(last_pos - QPointF(5, 5)) # Offset needed because rect is -5,-5
        self.preview_view.head_marker.setVisible(True)
        
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        # 1. 收集所有需要加工的项
        pending_items = []
        
        # 用于检测重复项 (位置和形状完全相同的项)
        processed_signatures = set()
        
        for item in self.items:
            # 获取路径
            path = None
            
            # 支持传入类名进行检查，避免循环导入
            item_class_name = type(item).__name__

            if isinstance(item, QGraphicsPathItem) or item_class_name == 'EditablePathItem' or item_class_name == 'TextGraphicsItem':
                path = item.path()
            elif isinstance(item, QGraphicsEllipseItem) or item_class_name == 'EditableEllipseItem':
                path = QPainterPath()
                path.addEllipse(item.rect())
            elif isinstance(item, QGraphicsRectItem):
                path = QPainterPath()
                path.addRect(item.rect())
            elif hasattr(item, 'path'): # Fallback for duck typing
                path = item.path()
            elif hasattr(item, 'shape'):
                # 注意：shape() 包含 stroke width，对于切割预览可能不准确 (会产生双线)
                # 尽量避免使用 shape() 除非是未知类型
                path = item.shape()
            
            if not path or path.isEmpty():
                continue
                
            # 转换到场景坐标
            item_transform = item.sceneTransform()
            scene_path = item_transform.map(path)
            
            # 生成唯一签名以检测重复项
            br_sig = scene_path.boundingRect()
            # 放宽精度以更好去重 (3 -> 2 bits)
            rect_sig = (round(br_sig.x(), 2), round(br_sig.y(), 2), round(br_sig.width(), 2), round(br_sig.height(), 2))
            color_sig = "NONE"
            if hasattr(item, 'color'):
                c = item.color()
                if c.isValid():
                    color_sig = c.name()
            
            # 路径长度也放宽精度
            path_sig = (scene_path.elementCount(), round(scene_path.length(), 2))
            signature = (rect_sig, color_sig, path_sig)
            
            if signature in processed_signatures:
                # print(f"Skipping duplicate item: {signature}")
                continue
            processed_signatures.add(signature)
            
            # 更新包围盒
            br = scene_path.boundingRect()
            min_x = min(min_x, br.left())
            min_y = min(min_y, br.top())
            max_x = max(max_x, br.right())
            max_y = max(max_y, br.bottom())
            
            # 获取图层参数
            mode = "激光切割"
            scan_interval = 0.1
            scan_mode = "水平单向"
            repeat_count = 1
            current_speed = self.default_speed
            min_power = 0.0
            max_power = 100.0
            speed_source = 'default'
            pixmap_item = None

            def get_item_color_hex(it):
                layer_color_role = Qt.UserRole + 100
                color_hex = None

                if hasattr(it, 'data'):
                    color_data = it.data(layer_color_role)
                    if color_data:
                        if isinstance(color_data, QColor):
                            color_hex = color_data.name().upper()
                        elif isinstance(color_data, str):
                            color_hex = color_data.upper()

                if not color_hex and hasattr(it, '_color'):
                    c = getattr(it, '_color')
                    if isinstance(c, QColor):
                        color_hex = c.name().upper()
                    elif isinstance(c, str):
                        color_hex = c.upper()

                if not color_hex and hasattr(it, 'pen'):
                    try:
                        pen = it.pen()
                        if pen and pen.color().isValid():
                            color_hex = pen.color().name().upper()
                    except Exception:
                        pass

                if not color_hex and hasattr(it, 'brush'):
                    try:
                        brush = it.brush()
                        if brush and brush.color().isValid():
                            color_hex = brush.color().name().upper()
                    except Exception:
                        pass

                if not color_hex and hasattr(it, 'defaultTextColor'):
                    try:
                        color = it.defaultTextColor()
                        if color and color.isValid():
                            color_hex = color.name().upper()
                    except Exception:
                        pass

                return color_hex

            hex_color = get_item_color_hex(item)
            if hex_color and hex_color in self.layer_data:
                params = self.layer_data[hex_color]
                mode = params.mode
                scan_interval = params.scan_interval
                scan_mode = params.scan_mode
                repeat_count = getattr(params, 'repeat_count', 1)
                scan_direction = getattr(params, 'scan_direction', None)
                if hasattr(params, 'speed'):
                    current_speed = params.speed
                    speed_source = 'layer'
                if hasattr(params, 'min_power'):
                    min_power = params.min_power
                if hasattr(params, 'max_power'):
                    max_power = params.max_power
            elif hex_color:
                for k, v in self.layer_data.items():
                    if len(k) >= 7 and len(hex_color) >= 7:
                        if k[-6:] == hex_color[-6:]:
                            params = v
                            mode = params.mode
                            scan_interval = params.scan_interval
                            scan_mode = params.scan_mode
                            repeat_count = getattr(params, 'repeat_count', 1)
                            scan_direction = getattr(params, 'scan_direction', None)
                            if hasattr(params, 'speed'):
                                current_speed = params.speed
                                speed_source = 'layer'
                            if hasattr(params, 'min_power'):
                                min_power = params.min_power
                            if hasattr(params, 'max_power'):
                                max_power = params.max_power
                            break

            if isinstance(item, QGraphicsPixmapItem):
                pixmap_item = item
            
            # 小圆限速检测
            small_circle_limit = []
            enable_small_circle = False
            if self.parent() and hasattr(self.parent(), 'whiteboard') and hasattr(self.parent().whiteboard, 'canvas'):
                canvas = self.parent().whiteboard.canvas
                exp = getattr(canvas, 'export_settings', {})
                enable_small_circle = bool(exp.get('small_circle_enable', False))
                raw_limits = exp.get('small_circle_limits', []) or getattr(canvas, 'small_circle_limit', [])
                for d_val, s_val in raw_limits:
                    try:
                        small_circle_limit.append((float(d_val), float(s_val)))
                    except Exception:
                        continue

            if enable_small_circle and small_circle_limit:
                br = scene_path.boundingRect()
                w, h = br.width(), br.height()

                # Check if it is a circle
                is_circle = False
                item_cls = type(item).__name__
                if isinstance(item, QGraphicsEllipseItem) or item_cls == 'EditableEllipseItem':
                    is_circle = True
                elif hasattr(item, 'path'):
                    try:
                        path = item.path()
                        if not path.isEmpty() and abs(w - h) < 0.05 and path.elementCount() > 8:
                            is_circle = True
                    except Exception:
                        pass

                tol = max(0.5, 0.02 * max(w, h))
                if abs(w - h) <= tol:
                    diameter = (w + h) / 2.0
                    sorted_limits = sorted(small_circle_limit, key=lambda x: x[0])
                    applied_speed = None
                    for d_limit, v_limit in sorted_limits:
                        if diameter <= d_limit:
                            current_speed = v_limit
                            applied_speed = v_limit
                            break
                    print(f"[SmallCircle] diameter={diameter:.3f}mm, limits={sorted_limits}, applied_speed={applied_speed}")
                else:
                    print(f"[SmallCircle] skip: w={w:.3f}, h={h:.3f}, tol={tol:.3f}, limits={small_circle_limit}")
            
            # 强制修正可能的异常重复次数
            if repeat_count < 1: repeat_count = 1
            if repeat_count > 100: repeat_count = 1 

            # 预计算起点 (用于就近排序)
            # 对于扫描模式，起点大概在包围盒顶部或底部，这里简化用包围盒左上角近似
            start_pt = QPointF(0,0)
            if mode == "激光扫描":
                start_pt = br.topLeft()
            else:
                start_pt = scene_path.pointAtPercent(0)
            
            mj_config = None
            if hasattr(item, 'micro_joint_config') and item.micro_joint_config and item.micro_joint_config.get('enabled'):
                mj_config = item.micro_joint_config

            pending_items.append({
                'scene_path': scene_path,
                'mode': mode,
                'scan_interval': scan_interval,
                'scan_mode': scan_mode,
                'scan_direction': scan_direction,
                'repeat_count': repeat_count,
                'start_pt': start_pt,
                'speed': current_speed,
                'mj_config': mj_config,
                'min_power': min_power,
                'max_power': max_power,
                'speed_source': speed_source,
                'pixmap_item': pixmap_item,
                'bbox': scene_path.boundingRect()
            })

        # 2. 生成仿真路径 (严格按照列表顺序，即 Z-Order / 优化后的顺序)
        for item_data in pending_items:
            # 移除原来的贪婪就近算法，尊重用户的“路径优化”结果

            scene_path = item_data['scene_path']
            mode = item_data['mode']
            scan_interval = item_data['scan_interval']
            scan_mode = item_data['scan_mode']
            scan_direction = item_data.get('scan_direction') or self.scan_direction
            repeat_count = item_data['repeat_count']
            speed = item_data['speed']
            min_power = item_data.get('min_power', 0.0)
            max_power = item_data.get('max_power', 100.0)
            speed_source = item_data.get('speed_source', 'default')
            pixmap_item = item_data.get('pixmap_item')
            bbox = item_data.get('bbox')

            def get_scan_power_for_segment(line: QLineF) -> float:
                if not pixmap_item:
                    return max_power

                try:
                    img = pixmap_item.pixmap().toImage()
                    if img.isNull():
                        return max_power

                    mid = line.pointAt(0.5)
                    local_pt = pixmap_item.mapFromScene(mid)
                    px = int(round(local_pt.x()))
                    py = int(round(local_pt.y()))
                    if px < 0 or py < 0 or px >= img.width() or py >= img.height():
                        return max_power

                    c = img.pixelColor(px, py)
                    gray = int(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
                    power = min_power + (max_power - min_power) * (1.0 - gray / 255.0)
                    return max(0.0, min(100.0, power))
                except Exception:
                    return max_power
            mj_config = item_data.get('mj_config')
            
            if mode != "激光扫描" and mj_config:
                # Apply Micro-joints
                # Decompose into polygon points
                scale_factor = 100.0
                t = QTransform().scale(scale_factor, scale_factor)
                polys_high_res = scene_path.toSubpathPolygons(t)
                orig_polys = []
                inv_t, _ = t.inverted()
                for p in polys_high_res:
                    orig_polys.append(inv_t.map(p))
                
                if not orig_polys:
                    orig_polys = scene_path.toSubpathPolygons()
                
                # Split
                new_path = QPainterPath()
                for poly in orig_polys:
                     pts = [poly[i] for i in range(poly.count())]
                     # apply helper
                     sub_paths = calculate_micro_joint_splits(pts, mj_config)
                     for sub_pts in sub_paths:
                         if len(sub_pts) < 2: continue
                         new_path.moveTo(sub_pts[0])
                         for pt in sub_pts[1:]:
                             new_path.lineTo(pt)
                
                if not new_path.isEmpty():
                    scene_path = new_path

            # 根据模式生成路径
            repeat_count = item_data['repeat_count']
            speed = item_data['speed']

            # 根据模式生成路径
            final_path = scene_path
            if mode == "激光扫描":
                final_path = self.generate_scan_path(scene_path, scan_interval, scan_mode, scan_direction)
                preview_item = QGraphicsPathItem(final_path)
                preview_item.setPen(QPen(QColor(255, 0, 255), 0.5)) # 细线
            else:
                preview_item = QGraphicsPathItem(scene_path)
                preview_item.setPen(QPen(QColor(255, 0, 255), 1)) # 紫色路径

            self.preview_view.scene.addItem(preview_item)
            
            # 生成仿真段
            
            if mode == "激光扫描":
                scan_segments = self.get_scan_segments(scene_path, scan_interval, scan_mode, scan_direction)
                if not scan_segments: continue
                
                if repeat_count > 1:
                    print(f"Scan mode repeat count: {repeat_count}")
                    
                for _ in range(repeat_count):
                    # 第一段的起点
                    first_pt = scan_segments[0].p1()
                    
                    # 空走到第一段起点
                    travel_line = QLineF(last_pos, first_pt)
                    travel_len = travel_line.length()
                    if travel_len > 0.001:
                        self.sim_paths.append({
                            'type': 'travel',
                            'path': travel_line,
                            'length': travel_len,
                            'speed': self.default_speed,
                            'speed_source': 'default',
                            'bbox': bbox
                        })
                        total_travel_len += travel_len
                    
                    last_pos = first_pt
                    
                    for i, line in enumerate(scan_segments):
                        # 如果不是第一段，需要从上一段终点移动到这一段起点
                        if i > 0:
                            curr_start = line.p1()
                            if last_pos != curr_start:
                                t_line = QLineF(last_pos, curr_start)
                                t_len = t_line.length()
                                if t_len > 0.001:
                                    self.sim_paths.append({
                                        'type': 'travel',
                                        'path': t_line,
                                        'length': t_len,
                                        'speed': self.default_speed,
                                        'speed_source': 'default',
                                        'bbox': bbox
                                    })
                                    total_travel_len += t_len
                        
                        # 切割当前线段
                        seg_path = QPainterPath(line.p1())
                        seg_path.lineTo(line.p2())
                        length = line.length()
                        
                        self.sim_paths.append({
                            'type': 'cut',
                            'path': seg_path,
                            'length': length,
                            'speed': speed,
                            'power': get_scan_power_for_segment(line),
                            'speed_source': speed_source,
                            'bbox': bbox
                        })
                        total_cut_len += length
                        last_pos = line.p2()
                    
            else:
                # 切割模式 - 使用高精度分解路径以解决连线和锯齿问题
                
                # 初始空走 (到路径的绝对起点)
                # 使用 toSubpathPolygons 分解为多边形，可以自然处理 MoveTo (断点)
                # 使用 Scaling Transform 提高精度 (避免 flat 导致的锯齿)
                scale_factor = 100.0
                t = QTransform().scale(scale_factor, scale_factor)
                polys_high_res = scene_path.toSubpathPolygons(t)
                
                # 转换回实际坐标
                polys = []
                inv_t, _ = t.inverted()
                for p in polys_high_res:
                    polys.append(inv_t.map(p))
                    
                if not polys: 
                    # 尝试直接获取 (针对直线等简单情况)
                    polys = scene_path.toSubpathPolygons()
                
                # 过滤掉不足两点的多边形 (无效路径)
                polys = [p for p in polys if p.count() >= 2]

                if not polys: continue
                
                # 第一段起点
                start_pt = polys[0].first()
                if mode == "激光扫描": # Fallback logic just in case
                     start_pt = scene_path.boundingRect().topLeft()
                
                travel_line = QLineF(last_pos, start_pt)
                travel_len = travel_line.length()
                if travel_len > 0.001:
                    self.sim_paths.append({
                        'type': 'travel',
                        'path': travel_line,
                        'length': travel_len,
                        'speed': self.default_speed,
                        'speed_source': 'default',
                        'bbox': bbox
                    })
                    total_travel_len += travel_len
                
                last_pos = start_pt
                
                if repeat_count > 1:
                    print(f"Cut mode repeat count: {repeat_count}")

                # 循环执行切割
                for _ in range(repeat_count):
                    # 遍历每个子路径 (Connect disjoint parts with travel)
                    for i, poly in enumerate(polys):
                        if poly.count() < 2: continue
                        
                        curr_start = poly.first()
                        
                        # 检测段间空走
                        if last_pos != curr_start:
                             t_line = QLineF(last_pos, curr_start)
                             t_len = t_line.length()
                             if t_len > 0.001:
                                self.sim_paths.append({
                                    'type': 'travel',
                                    'path': t_line,
                                    'length': t_len,
                                    'speed': self.default_speed,
                                    'speed_source': 'default',
                                    'bbox': bbox
                                })
                                total_travel_len += t_len
                        
                        # 构建切割路径
                        cut_path = QPainterPath()
                        cut_path.addPolygon(poly)
                        l = cut_path.length()
                        
                        self.sim_paths.append({
                            'type': 'cut',
                            'path': cut_path,
                            'length': l,
                            'speed': speed,
                            'power': max_power,
                            'speed_source': speed_source,
                            'bbox': bbox
                        })
                        total_cut_len += l
                        
                        last_pos = poly.last()

        # 初始化尺寸显示为首个加工对象尺寸（如果有）
        if self.sim_paths:
            first_bbox = self.sim_paths[0].get('bbox')
            if first_bbox:
                self.update_stat_value(self.lbl_size, f"{first_bbox.width():.1f}mm, {first_bbox.height():.1f}mm")
            else:
                self.update_stat_value(self.lbl_size, "0.0mm, 0.0mm")
        else:
            self.update_stat_value(self.lbl_size, "0.0mm, 0.0mm")
            
        self.update_stat_value(self.lbl_travel_dist, f"{total_travel_len:.1f}mm")
        self.update_stat_value(self.lbl_proc_dist, f"{total_cut_len:.1f}mm")
        
        self._recalculate_time_stats()
        
        # 自动缩放视图
        self.preview_view.scene.setSceneRect(QRectF(min_x-10, min_y-10, (max_x-min_x)+20, (max_y-min_y)+20))
        self.preview_view.fitInView(self.preview_view.scene.sceneRect(), Qt.KeepAspectRatio)

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h)}:{int(m):02d}:{s:06.3f}"

    def _recalculate_time_stats(self):
        t_travel = 0.0
        t_cut = 0.0

        for seg in self.sim_paths:
            speed = float(seg.get('speed', self.default_speed))
            if speed <= 0.0001:
                continue
            if seg.get('type') == 'cut':
                t_cut += seg['length'] / speed
            else:
                t_travel += seg['length'] / speed

        self.total_time = t_travel + t_cut
        self.update_stat_value(self.lbl_proc_time, self.format_time(self.total_time))
        self.update_stat_value(self.lbl_laser_time, self.format_time(t_cut))

    def update_stats(self):
        pass

    def on_speed_changed(self, val):
        self.default_speed = float(val)
        self.lbl_speed_val.setText(str(val))
        # 更新仿真路径中的默认/空走速度
        for seg in self.sim_paths:
            if seg.get('type') == 'travel' or seg.get('speed_source') == 'default':
                seg['speed'] = self.default_speed
        self._recalculate_time_stats()

    def on_ratio_changed(self, val):
        self.sim_speed_ratio = val / 10.0
        self.lbl_ratio_val.setText(f"{self.sim_speed_ratio:.1f}")

    def start_simulation(self):
        if not self.sim_paths: return
        if self.is_running and self.is_paused:
            self.is_paused = False
            self.timer.start(30)
            return
            
        self.is_running = True
        self.is_paused = False
        self.current_path_index = 0
        self.current_t = 0.0
        self.elapsed_time = 0.0
        self.preview_view.head_marker.setVisible(True)
        
        # 重置已加工路径
        self.traversed_path = QPainterPath()
        self.preview_view.traversed_path_item.setPath(self.traversed_path)
        
        # 初始化起始位置
        if self.sim_paths:
            first_seg = self.sim_paths[0]
            if first_seg['type'] == 'travel':
                self.last_sim_pos = first_seg['path'].p1()
            else:
                # 如果第一段就是切割，需要先移动到起点
                start_pt = first_seg['path'].pointAtPercent(0.0)
                self.last_sim_pos = start_pt
                self.traversed_path.moveTo(start_pt)
        else:
            self.last_sim_pos = None
            
        if self.last_sim_pos:
            self.preview_view.head_marker.setPos(self.last_sim_pos)
        
        self.timer.start(30) # 30ms interval

    def toggle_pause(self):
        if not self.is_running: return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.timer.stop()
        else:
            self.timer.start(30)

    def stop_simulation(self):
        self.is_running = False
        self.is_paused = False
        self.timer.stop()
        self.preview_view.head_marker.setVisible(False)
        self.progress_bar.setValue(0)
        self.update_stat_value(self.lbl_cur_pos, "0.0mm, 0.0mm")
        # 清除已加工路径
        self.traversed_path = QPainterPath()
        self.preview_view.traversed_path_item.setPath(self.traversed_path)

    def _append_path_segment(self, path, t_start, t_end, total_length):
        """辅助方法：将路径片段添加到已加工路径中，支持采样以平滑曲线"""
        if t_start >= t_end: return
        
        # 检查是否需要移动到起点 (处理空走后的断点)
        # 逻辑优化：比较画笔当前位置与仿真头位置(last_sim_pos)
        # 如果两者不一致，说明刚才发生了空走(Travel)，需要抬笔移动到仿真头位置
        current_pen_pos = self.traversed_path.currentPosition()
        
        if self.traversed_path.elementCount() == 0:
            # 第一次绘制，直接移动到起点
            start_pos = path.pointAtPercent(t_start)
            self.traversed_path.moveTo(start_pos)
        elif self.last_sim_pos:
            # 如果画笔不在仿真头位置，移动过去
            if QLineF(current_pen_pos, self.last_sim_pos).length() > 0.001:
                self.traversed_path.moveTo(self.last_sim_pos)
        
        # 采样步长 (mm)，越小越平滑但性能开销越大
        step_size = 0.2  # 提高精度以减少锯齿感 (原为2.0)
        
        # 需要覆盖的长度
        dist = (t_end - t_start) * total_length
        
        if dist <= step_size:
            # 距离很短，直接画直线到终点
            pos = path.pointAtPercent(t_end)
            self.traversed_path.lineTo(pos)
            self.last_sim_pos = pos
        else:
            # 距离较长，进行采样以拟合曲线
            num_steps = int(dist / step_size)
            if num_steps < 1: num_steps = 1
            dt = (t_end - t_start) / num_steps
            
            for i in range(1, num_steps + 1):
                t = t_start + i * dt
                if t > t_end: t = t_end # 避免浮点误差
                pos = path.pointAtPercent(t)
                self.traversed_path.lineTo(pos)
            
            # 确保最后一点精确
            end_pos = path.pointAtPercent(t_end)
            # 避免重复点（如果采样恰好落在终点）
            if self.last_sim_pos != end_pos: 
                 self.traversed_path.lineTo(end_pos)
            self.last_sim_pos = end_pos
            
        self.preview_view.traversed_path_item.setPath(self.traversed_path)

    def on_timer_tick(self):
        if not self.is_running or self.current_path_index >= len(self.sim_paths):
            self.stop_simulation()
            return
            
        dt = 0.030 * self.sim_speed_ratio # 30ms * ratio
        
        seg = self.sim_paths[self.current_path_index]
        speed = seg['speed']
        dist_step = speed * dt
        
        # 当前段总长度
        seg_len = seg['length']
        
        # 计算当前步进对应的百分比增量
        if seg_len > 0:
            t_step = dist_step / seg_len
        else:
            t_step = 1.0
            
        # 记录本此 tick 的起始 t
        t_start = self.current_t
        self.current_t += t_step
        
        # 如果超过当前段
        while self.current_t >= 1.0:
            # 完成当前段的处理
            seg = self.sim_paths[self.current_path_index]
            
            if seg['type'] == 'cut':
                # 绘制从 t_start 到 1.0 的路径
                self._append_path_segment(seg['path'], t_start, 1.0, seg_len)
            else:
                # Travel: 直接更新位置
                self.last_sim_pos = seg['path'].p2()

            # 剩余距离
            remain_t = self.current_t - 1.0
            remain_dist = remain_t * seg_len
            
            self.current_path_index += 1
            if self.current_path_index >= len(self.sim_paths):
                self.current_t = 1.0
                self.stop_simulation()
                return
            
            # 进入下一段
            seg = self.sim_paths[self.current_path_index]
            seg_len = seg['length']
            speed = seg['speed']
            
            # 重置 t_start 为 0，并计算新的 current_t
            t_start = 0.0
            self.current_t = remain_dist / seg_len if seg_len > 0 else 1.0
            
        # 处理当前段剩余部分 (t_start 到 current_t)
        seg = self.sim_paths[self.current_path_index]
        if seg['type'] == 'travel':
            # QLineF
            line = seg['path']
            pos = line.pointAt(self.current_t)
            self.update_stat_value(self.lbl_cur_power, "0.0%")
            # 空走不画线，但更新最后位置
            self.last_sim_pos = pos
        else:
            # Cut
            self._append_path_segment(seg['path'], t_start, self.current_t, seg_len)
            self.update_stat_value(self.lbl_cur_power, f"{seg['power']}%")

        bbox = seg.get('bbox')
        if bbox:
            self.update_stat_value(self.lbl_size, f"{bbox.width():.1f}mm, {bbox.height():.1f}mm")
            
        if self.last_sim_pos:
            self.preview_view.head_marker.setPos(self.last_sim_pos)
        
        # 更新状态
        if self.last_sim_pos:
            self.update_stat_value(self.lbl_cur_pos, f"{self.last_sim_pos.x():.1f}mm, {self.last_sim_pos.y():.1f}mm")
        self.update_stat_value(self.lbl_cur_speed, f"{speed:.1f}mm/s")
        
        # 更新进度条
        total_progress = 0.0
        current_progress = 0.0
        for i, s in enumerate(self.sim_paths):
            total_progress += s['length']
            if i < self.current_path_index:
                current_progress += s['length']
            elif i == self.current_path_index:
                current_progress += s['length'] * self.current_t
                
        if total_progress > 0:
            pct = int((current_progress / total_progress) * 100)
            self.progress_bar.setValue(pct)

