#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加工预览对话框
"""
import math
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QSlider, QWidget, QGraphicsView, 
                             QGraphicsScene, QGraphicsItem, QGraphicsPathItem,
                             QGroupBox, QProgressBar, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QLineF
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QFont

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
        
        # 激光头标记
        self.head_marker = self.scene.addRect(-5, -5, 10, 10, QPen(Qt.NoPen), QBrush(QColor(0, 255, 0)))
        self.head_marker.setZValue(1000)
        self.head_marker.setVisible(False)
        
        # 已加工路径（绿色）
        self.traversed_path_item = QGraphicsPathItem()
        self.traversed_path_item.setPen(QPen(QColor(0, 255, 0), 1.5)) # 绿色，稍粗
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
    def __init__(self, canvas_items, work_size=(600, 400), layer_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加工预览")
        self.resize(1000, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        
        self.items = canvas_items
        self.work_w, self.work_h = work_size
        self.layer_data = layer_data or {}
        
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

    def get_scan_segments(self, shape_path, interval, mode):
        """生成扫描线段列表"""
        segments = []
        
        # 1. 获取多边形近似
        polys = shape_path.toSubpathPolygons()
        if not polys: return []
        
        # 2. 获取Y范围
        br = shape_path.boundingRect()
        min_y = br.top()
        max_y = br.bottom()
        
        # 3. 扫描
        y = min_y
        left_to_right = True
        
        # 防止死循环
        if interval <= 0.001: interval = 0.1

        while y <= max_y:
            x_intersects = []
            
            for poly in polys:
                # 遍历多边形的每一条边
                if poly.count() < 2: continue
                
                p1 = poly.first()
                for i in range(1, poly.count()):
                    p2 = poly.at(i)
                    # 检查边 (p1, p2) 是否与 y 相交
                    y1, y2 = p1.y(), p2.y()
                    x1, x2 = p1.x(), p2.x()
                    
                    if y1 > y2: 
                        y1, y2 = y2, y1
                        x1, x2 = x2, x1
                    
                    # 半开半闭区间 [y1, y2)
                    if y1 <= y < y2: 
                         if abs(y2 - y1) > 1e-9:
                             x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                             x_intersects.append(x)
                    
                    p1 = p2
                
                # 闭合边的检查
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
            
            # 配对生成线段
            for i in range(0, len(x_intersects), 2):
                if i + 1 < len(x_intersects):
                    x_start = x_intersects[i]
                    x_end = x_intersects[i+1]
                    
                    if left_to_right:
                        segments.append(QLineF(x_start, y, x_end, y))
                    else:
                        segments.append(QLineF(x_end, y, x_start, y))
            
            if mode == "水平双向":
                left_to_right = not left_to_right
            
            y += interval
            
        return segments

    def generate_scan_path(self, shape_path, interval, mode):
        """生成用于显示的扫描路径"""
        segments = self.get_scan_segments(shape_path, interval, mode)
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
        
        last_pos = QPointF(0, 0)
        
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for item in self.items:
            # 获取路径
            path = None
            if hasattr(item, 'path'):
                path = item.path()
            elif hasattr(item, 'shape'):
                path = item.shape()
            
            if not path or path.isEmpty():
                continue
                
            # 转换到场景坐标（假设items来自主场景，且PreviewCanvas使用相同坐标系）
            # 但我们需要在PreviewCanvas中重新绘制，所以需要提取几何信息
            # 这里我们直接在PreviewCanvas中添加新的PathItem
            
            # 复制路径并应用变换
            scene_path = self.preview_view.mapFromScene(item.sceneBoundingRect()) # No, this is view mapping
            # Correct way: map path to scene
            item_transform = item.sceneTransform()
            scene_path = item_transform.map(path)
            
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
            
            if hasattr(item, 'color'):
                c = item.color()
                if c.isValid():
                    hex_color = c.name().upper()
                    # 尝试精确匹配
                    if hex_color in self.layer_data:
                        params = self.layer_data[hex_color]
                        mode = params.mode
                        scan_interval = params.scan_interval
                        scan_mode = params.scan_mode
                    else:
                        # 尝试模糊匹配 (忽略Alpha通道，或者长度不一致)
                        # layer_data keys are usually #RRGGBB
                        # hex_color might be #AARRGGBB or #RRGGBB
                        found = False
                        for k, v in self.layer_data.items():
                            # 比较最后6位 (RRGGBB)
                            if len(k) >= 7 and len(hex_color) >= 7:
                                if k[-6:] == hex_color[-6:]:
                                    params = v
                                    mode = params.mode
                                    scan_interval = params.scan_interval
                                    scan_mode = params.scan_mode
                                    found = True
                                    break
                        
                        if not found:
                            # 如果还是没找到，可能是颜色有微小差异，或者使用了默认颜色
                            # 这里可以打印日志，或者使用默认值
                            pass

            # 根据模式生成路径
            final_path = scene_path
            if mode == "激光扫描":
                final_path = self.generate_scan_path(scene_path, scan_interval, scan_mode)
                # 扫描模式下，预览显示填充效果（或者密集的线）
                # 这里我们显示生成的扫描线
                preview_item = QGraphicsPathItem(final_path)
                preview_item.setPen(QPen(QColor(255, 0, 255), 0.5)) # 细线
            else:
                preview_item = QGraphicsPathItem(scene_path)
                preview_item.setPen(QPen(QColor(255, 0, 255), 1)) # 紫色路径

            self.preview_view.scene.addItem(preview_item)
            
            # 生成仿真段
            # 1. 空走到起点
            if final_path.elementCount() > 0:
                start_pt = final_path.pointAtPercent(0)
                travel_line = QLineF(last_pos, start_pt)
                travel_len = travel_line.length()
                if travel_len > 0.001:
                    self.sim_paths.append({
                        'type': 'travel',
                        'path': travel_line,
                        'length': travel_len,
                        'speed': self.default_speed # 用户要求空走速度与切割速度一致
                    })
                    total_travel_len += travel_len
                    
                    # 绘制空走路径（虚线）
                    travel_item = self.preview_view.scene.addLine(travel_line, QPen(QColor(0, 0, 100), 1, Qt.DashLine))
                    travel_item.setZValue(-1)
            
            # 2. 切割/扫描路径
            # 对于扫描路径，它可能包含很多 MoveTo，我们需要将其拆分为多个段
            # 或者，如果 generate_scan_path 返回的是一个连续的路径（包含 MoveTo），
            # 我们可以遍历它的元素来生成 sim_paths
            
            if mode == "激光扫描":
                # 扫描路径由多条线段组成，中间有 MoveTo
                # 我们需要将其拆解，因为仿真逻辑是基于连续路径的
                # 实际上，generate_scan_path 返回的 path 包含 MoveTo
                # 我们可以遍历 path 的元素
                
                # 简单处理：将整个 path 作为一个 cut 段？
                # 不行，因为中间的 MoveTo 应该是 travel（不发光）
                # 但是扫描通常是快速开关光，中间的连接线（如果是双向）是发光的
                # 如果是单向，回程是不发光的
                
                # 让我们解析 final_path
                # QPainterPath 迭代比较麻烦，我们重新生成 sim_paths
                # 或者在 generate_scan_path 里直接生成 sim_paths?
                # 为了保持结构清晰，我们在这里解析 final_path
                
                # 更好的方法：generate_scan_path 返回线段列表
                scan_segments = self.get_scan_segments(scene_path, scan_interval, scan_mode)
                
                for i, seg_line in enumerate(scan_segments):
                    # 空走到线段起点 (如果是第一段，已经在上面处理了空走到起点)
                    # 但上面的逻辑是基于 final_path.pointAtPercent(0)
                    # 如果我们在这里处理，上面的逻辑可能重复或者不对
                    
                    # 让我们调整一下：
                    # 如果是扫描模式，上面的 final_path 只是为了显示
                    # 仿真路径我们在这里重新生成
                    
                    p1 = seg_line.p1()
                    p2 = seg_line.p2()
                    
                    # 从当前位置(last_pos) 移动到 p1
                    # 注意：如果是第一段，last_pos 是 (0,0) 或者上一图层的结束点
                    # 上面的代码已经处理了 "空走到起点"，但是是基于 final_path 的起点
                    # 如果 final_path 的起点就是 scan_segments[0].p1()，那就没问题
                    
                    # 但是，上面的代码已经添加了一个 travel 到 final_path 的起点
                    # 如果我们在这里再添加 travel，就会重复
                    # 所以，如果是扫描模式，我们跳过上面的 "空走到起点" 逻辑？
                    # 或者让 final_path 就是扫描路径，但是我们需要正确处理其中的 MoveTo
                    
                    pass # 逻辑在下面统一处理
            
            # 重新组织逻辑：
            
            if mode == "激光扫描":
                scan_segments = self.get_scan_segments(scene_path, scan_interval, scan_mode)
                if not scan_segments: continue
                
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
                        'speed': self.default_speed
                    })
                    total_travel_len += travel_len
                    travel_item = self.preview_view.scene.addLine(travel_line, QPen(QColor(0, 0, 100), 1, Qt.DashLine))
                    travel_item.setZValue(-1)
                
                last_pos = first_pt
                
                for i, line in enumerate(scan_segments):
                    # 如果不是第一段，需要从上一段终点移动到这一段起点
                    if i > 0:
                        curr_start = line.p1()
                        if last_pos != curr_start:
                            # 扫描时的连接线
                            # 如果是双向扫描，通常是直接连过去的，但是是空走还是切割？
                            # 扫描通常是：切 -> 移 -> 切
                            # 即使是双向，换行的时候也是不发光的（通常）
                            # 除非是 "S" 形扫描且边缘也切
                            # 这里假设换行是空走
                            t_line = QLineF(last_pos, curr_start)
                            t_len = t_line.length()
                            if t_len > 0.001:
                                self.sim_paths.append({
                                    'type': 'travel',
                                    'path': t_line,
                                    'length': t_len,
                                    'speed': self.default_speed
                                })
                                total_travel_len += t_len
                                # 扫描太密集，空走线可能不需要画，或者画淡一点
                                # travel_item = self.preview_view.scene.addLine(t_line, QPen(QColor(0, 0, 100), 0.5, Qt.DashLine))
                    
                    # 切割当前线段
                    # 将 QLineF 转为 QPainterPath 以统一格式
                    seg_path = QPainterPath(line.p1())
                    seg_path.lineTo(line.p2())
                    length = line.length()
                    
                    self.sim_paths.append({
                        'type': 'cut',
                        'path': seg_path,
                        'length': length,
                        'speed': self.default_speed, # 扫描速度通常很快，这里暂用默认
                        'power': 30.0
                    })
                    total_cut_len += length
                    last_pos = line.p2()
                    
            else:
                # 切割模式 (原逻辑)
                # 1. 空走到起点
                start_pt = scene_path.pointAtPercent(0)
                travel_line = QLineF(last_pos, start_pt)
                travel_len = travel_line.length()
                if travel_len > 0.001:
                    self.sim_paths.append({
                        'type': 'travel',
                        'path': travel_line,
                        'length': travel_len,
                        'speed': self.default_speed
                    })
                    total_travel_len += travel_len
                    travel_item = self.preview_view.scene.addLine(travel_line, QPen(QColor(0, 0, 100), 1, Qt.DashLine))
                    travel_item.setZValue(-1)
                
                # 2. 切割路径
                length = scene_path.length()
                if length > 0:
                    self.sim_paths.append({
                        'type': 'cut',
                        'path': scene_path,
                        'length': length,
                        'speed': self.default_speed,
                        'power': 30.0
                    })
                    total_cut_len += length
                last_pos = scene_path.pointAtPercent(1)

        # 更新统计
        if min_x == float('inf'):
            self.update_stat_value(self.lbl_size, "0.0mm, 0.0mm")
        else:
            w = max_x - min_x
            h = max_y - min_y
            self.update_stat_value(self.lbl_size, f"{w:.1f}mm, {h:.1f}mm")
            
        self.update_stat_value(self.lbl_travel_dist, f"{total_travel_len:.1f}mm")
        self.update_stat_value(self.lbl_proc_dist, f"{total_cut_len:.1f}mm")
        
        # 估算时间
        t_travel = total_travel_len / self.default_speed
        t_cut = total_cut_len / self.default_speed
        self.total_time = t_travel + t_cut
        self.update_stat_value(self.lbl_proc_time, self.format_time(self.total_time))
        self.update_stat_value(self.lbl_laser_time, self.format_time(t_cut))
        
        # 自动缩放视图
        self.preview_view.scene.setSceneRect(QRectF(min_x-10, min_y-10, (max_x-min_x)+20, (max_y-min_y)+20))
        self.preview_view.fitInView(self.preview_view.scene.sceneRect(), Qt.KeepAspectRatio)

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h)}:{int(m):02d}:{s:06.3f}"

    def update_stats(self):
        pass

    def on_speed_changed(self, val):
        self.default_speed = float(val)
        self.lbl_speed_val.setText(str(val))
        # 更新仿真路径中的速度
        for seg in self.sim_paths:
            # 用户要求空走速度也与切割速度一致
            seg['speed'] = self.default_speed
        # 重新计算总时间
        # ... (略)

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
            
        self.current_t += t_step
        
        # 如果超过当前段
        while self.current_t >= 1.0:
            # 完成当前段的处理
            seg = self.sim_paths[self.current_path_index]
            
            if seg['type'] == 'cut':
                end_pos = seg['path'].pointAtPercent(1.0)
                # 补齐到终点的线段
                if self.last_sim_pos:
                    # 确保路径已开始
                    if self.traversed_path.elementCount() == 0:
                        self.traversed_path.moveTo(self.last_sim_pos)
                    self.traversed_path.lineTo(end_pos)
                    self.preview_view.traversed_path_item.setPath(self.traversed_path)
                self.last_sim_pos = end_pos
            else:
                # Travel
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
            self.current_t = remain_dist / seg_len if seg_len > 0 else 1.0
            
        # 更新位置
        if seg['type'] == 'travel':
            # QLineF
            line = seg['path']
            pos = line.pointAt(self.current_t)
            self.update_stat_value(self.lbl_cur_power, "0.0%")
            # 空走不画线，但更新最后位置
            self.last_sim_pos = pos
        else:
            # QPainterPath
            path = seg['path']
            pos = path.pointAtPercent(self.current_t)
            self.update_stat_value(self.lbl_cur_power, f"{seg['power']}%")
            
            # 绘制已加工路径（绿色）
            if self.last_sim_pos is None:
                self.traversed_path.moveTo(pos)
            else:
                # 如果是新的一段开始（或者上一段是空走），可能需要 moveTo
                # 但这里我们简单处理：如果是连续切割，lineTo；如果是断开的，moveTo
                # 实际上，last_sim_pos 应该是上一次的位置
                # 检查距离，如果距离过大（说明是空走过来的），则 moveTo
                dist = QLineF(self.last_sim_pos, pos).length()
                if dist > 1.0 and seg['type'] == 'cut': # 阈值
                     # 理论上不应该发生，因为空走也会更新 last_sim_pos
                     # 但为了保险
                     pass
                
                # 只有在切割时才画线
                if self.traversed_path.elementCount() == 0:
                    self.traversed_path.moveTo(self.last_sim_pos)
                
                # 只有当起点和终点不同时才画线
                if self.last_sim_pos != pos:
                     self.traversed_path.lineTo(pos)
                     self.preview_view.traversed_path_item.setPath(self.traversed_path)
            
            self.last_sim_pos = pos
            
        self.preview_view.head_marker.setPos(pos) # Center marker
        
        # 更新状态
        self.update_stat_value(self.lbl_cur_pos, f"{pos.x():.1f}mm, {pos.y():.1f}mm")
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

