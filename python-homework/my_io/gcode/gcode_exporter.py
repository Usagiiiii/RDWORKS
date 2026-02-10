#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复版G代码导出模块 - 解决位图导出问题
"""

import logging
import os
<<<<<<< HEAD
from typing import List, Tuple, Optional, Dict, Any
=======
import math
from typing import List, Tuple, Optional
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsPathItem
from PyQt5.QtGui import QPixmap, QImage, QColor, QTransform, QPainterPath
import numpy as np
from PIL import Image

LAYER_COLOR_ROLE = Qt.UserRole + 100
# 尝试导入 EditableEllipseItem，如果失败则忽略（避免循环依赖或路径问题）
try:
    from ui.graphics_items import EditableEllipseItem
except ImportError:
    EditableEllipseItem = None

logger = logging.getLogger(__name__)

# 类型定义
Point = Tuple[float, float]
Path = List[Point]


def calculate_micro_joint_splits(points, config):
    """计算微连分割路径"""
    if not points or len(points) < 2:
        return [points]
        
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
    remove_ranges = []
    for c in cut_centers:
        s = max(0.0, c - half_w)
        e = min(total_len, c + half_w)
        if s < e:
            remove_ranges.append((s,e))
    
    if not remove_ranges:
        return [points]
        
    remove_ranges.sort()
    
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
        for i in range(len(points)):
            if i == 0: 
                accum = 0.0
            else:
                accum += segment_lengths[i-1]
            if accum > k_s + 1e-5 and accum < k_e - 1e-5:
                subpath.append(points[i])
        
        subpath.append(get_pt_at_dist(k_e))
        result_paths.append(subpath)
        
    return result_paths


class GCodeExporter:
    """G代码导出器（修复版）"""

    def __init__(self):
        self.gcode_lines = []
        self.current_x = 0.0
        self.current_y = 0.0
        self.laser_on = False
        # 按图层颜色存放的简化参数字典:
        # key: '#RRGGBB'  value: {'seal_gap': float, 'laser_on_delay': int(ms), 'laser_off_delay': int(ms), 'mode': str}
        self.layer_params: Dict[str, Dict[str, Any]] = {}
        
        # 反向间隙补偿配置
        self.scan_backlash_config = None
        self.user_backlash_x = 0.0  # 用户参数中的反向间隙X
        self.user_backlash_y = 0.0  # 用户参数中的反向间隙Y
        self.last_move_dir_x = None  # 上一次X方向移动方向：1=正向, -1=负向, None=未移动
        self.last_move_dir_y = None  # 上一次Y方向移动方向

        # 修复配置参数
        self.config = {
            'feed_rate': 1000,  # 进给速度 mm/min
            'max_laser_power': 255,  # 最大激光功率
            'rapid_move_rate': 3000,  # 快速移动速度
            'units': 'G21',  # 毫米单位
            'absolute_positioning': 'G90',  # 绝对坐标
            'scan_interval': 0.1,  # 扫描间隔（毫米）
            'grayscale_threshold': 128,  # 灰度阈值
            'dpi': 96.0,  # 图像DPI
            'min_segment_length': 0.5,  # 最小段长度（避免过短路径）
        }

    # ------------------------------------------------------------------
    # 外部配置接口
    # ------------------------------------------------------------------

    def set_config(self, config: dict):
        """设置导出配置"""
        if config:
            self.config.update(config)

<<<<<<< HEAD
    def set_layer_params(self, params: Dict[str, Dict[str, Any]]):
        """
        设置按颜色存放的图层参数（来自 UI 的 LayerParams 做了简化拷贝）
        key 必须是大写 '#RRGGBB'
        """
        self.layer_params = params or {}

    def export_canvas(self, canvas, allowed_colors: List[str] = None) -> List[str]:
        """导出整个画布为G代码（支持定位点偏移）"""
        self.gcode_lines = []
        
        # 重置运动方向跟踪
        self.last_move_dir_x = None
        self.last_move_dir_y = None
        
        # 读取反向间隙补偿配置
        try:
            if hasattr(canvas, 'optimize_settings') and 'scan_backlash' in canvas.optimize_settings:
                self.scan_backlash_config = canvas.optimize_settings['scan_backlash']
            else:
                self.scan_backlash_config = None
            
            # 读取用户参数中的反向间隙X和Y
            if hasattr(canvas, 'optimize_settings') and 'user_backlash' in canvas.optimize_settings:
                user_backlash = canvas.optimize_settings['user_backlash']
                self.user_backlash_x = float(user_backlash.get('x', 0.0))
                self.user_backlash_y = float(user_backlash.get('y', 0.0))
            else:
                self.user_backlash_x = 0.0
                self.user_backlash_y = 0.0
        except Exception:
            self.scan_backlash_config = None
            self.user_backlash_x = 0.0
            self.user_backlash_y = 0.0
=======
    def export_canvas(self, canvas, allowed_colors: List[str] = None, layer_settings: dict = None) -> List[str]:
        """导出整个画布为G代码（支持定位点偏移和图层参数）"""
        self.gcode_lines = []
        self.layer_settings = layer_settings or {}
        
        # Load small circle limits from canvas
        if hasattr(canvas, 'small_circle_limit'):
            self.small_circle_limit = canvas.small_circle_limit
        else:
            self.small_circle_limit = []
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)

        try:
            # 检查是否存在定位点
            fiducial_point = self._get_fiducial_offset(canvas)

            # 添加文件头
            self._add_header(fiducial_point)

            # 获取所有可导出项
            exportable_items = self._get_exportable_items(canvas, allowed_colors)
            logger.info(f"找到 {len(exportable_items)} 个可导出项目")

            if not exportable_items:
                logger.warning("画布中没有可导出的内容")
                self._add_no_content_warning()
            else:
                # 按照图层顺序或优先级排序处理可能更好，这里保持原序
                # 处理每个项目（应用定位点偏移）
                for item_data in exportable_items:
                    self._process_exportable_item(item_data, fiducial_point)

            # 添加文件尾
            self._add_footer(fiducial_point)

        except Exception as e:
            logger.error(f"导出过程中发生错误: {e}")
            self._add_error_message(f"导出错误: {str(e)}")

        return self.gcode_lines

    def _get_fiducial_offset(self, canvas) -> Tuple[float, float]:
        """获取原点偏移量（优先使用激光头位置，其次定位点）"""
        try:
            # 1. 尝试获取激光头起始位置 (新的逻辑)
            if hasattr(canvas, 'get_laser_start_point'):
                pt = canvas.get_laser_start_point()
                logger.info(f"使用激光头位置作为原点偏移: ({pt.x():.2f}, {pt.y():.2f})")
                return (pt.x(), pt.y())

            # 2. 回退到旧的定位点逻辑
            fiducial = canvas.get_fiducial()
            if fiducial:
                point, shape = fiducial
                x, y = point
                logger.info(f"检测到定位点: ({x:.2f}, {y:.2f}), 形状: {shape}")
                return (x, y)
            else:
                logger.info("未检测到定位点，使用默认原点(0,0)")
                return (0.0, 0.0)
        except Exception as e:
            logger.warning(f"获取原点偏移失败: {e}, 使用默认原点")
            return (0.0, 0.0)

    def _apply_fiducial_offset(self, point: Point, fiducial_offset: Tuple[float, float]) -> Point:
        """应用定位点偏移 (并在导出时反转Y轴以适配标准G代码坐标系)"""
        x, y = point
        offset_x, offset_y = fiducial_offset
        # PyQt坐标系Y向下，G代码/CNC通常Y向上。
        # 为了让预览看起来方向正确（不倒置），我们需要反转Y轴。
        # 使用 - (y - offset_y) = offset_y - y
        return (x - offset_x, offset_y - y)

    def _get_exportable_items(self, canvas, allowed_colors: List[str] = None) -> List[tuple]:
        """获取所有可导出项"""
        items = []

        try:
            for item in canvas.scene.items():
                # 排除系统项
                if self._is_system_item(item, canvas):
                    continue

                # 检查图层是否允许输出，并记录颜色
                item_color_hex = None
                if allowed_colors is not None:
                    # 尝试从 data 获取
                    color_data = item.data(LAYER_COLOR_ROLE)
                    if color_data:
                        if isinstance(color_data, QColor):
                            item_color_hex = color_data.name().upper()
                        elif isinstance(color_data, str):
                            item_color_hex = color_data.upper()
                    
                    # 如果 data 没有，尝试从 pen 获取 (针对矢量图)
                    if not item_color_hex and hasattr(item, 'pen'):
                        try:
                            pen = item.pen()
                            if pen and pen.color().isValid():
                                item_color_hex = pen.color().name().upper()
                        except:
                            pass
                            
                    # 如果找到了颜色，且不在允许列表中，则跳过
                    if item_color_hex and item_color_hex not in allowed_colors:
                        continue

                # 如果没有限制 allowed_colors，也仍然尝试获取颜色，供后续按图层参数使用
                if allowed_colors is None and item_color_hex is None:
                    color_data = item.data(LAYER_COLOR_ROLE)
                    if color_data:
                        if isinstance(color_data, QColor):
                            item_color_hex = color_data.name().upper()
                        elif isinstance(color_data, str):
                            item_color_hex = color_data.upper()
                    elif hasattr(item, 'pen'):
                        try:
                            pen = item.pen()
                            if pen and pen.color().isValid():
                                item_color_hex = pen.color().name().upper()
                        except Exception:
                            pass

                # 优先检查是否为椭圆/圆 (EditableEllipseItem)
                if EditableEllipseItem and isinstance(item, EditableEllipseItem):
                    items.append(('ellipse', item, item_color_hex))
                    continue

                # 矢量路径项 (EditablePathItem 或其他具有 points 方法的项)
                # 注意：EditablePathItem 也是 QGraphicsPathItem，所以要先判断 points
                if hasattr(item, 'points') and callable(getattr(item, 'points')):
                    try:
                        points = item.points()
                        if points and len(points) >= 2:
                            items.append(('vector', item, item_color_hex))
                    except Exception as e:
                        logger.warning(f"获取矢量路径点时出错: {e}")
                
                # 通用 QGraphicsPathItem (TextGraphicsItem 等)
                elif isinstance(item, QGraphicsPathItem):
                    path = item.path()
                    if not path.isEmpty():
                         items.append(('qt_path', item))

                # 位图项
                elif isinstance(item, QGraphicsPixmapItem):
                    if not item.pixmap().isNull():
                        items.append(('bitmap', item, item_color_hex))

        except Exception as e:
            logger.error(f"获取可导出项时出错: {e}")

        return items

    def _is_system_item(self, item, canvas) -> bool:
        """判断是否为系统项 (包括网格、定位点、坐标轴箭头等)"""
        try:
            system_attrs = ['_work_item', '_fiducial_item', '_grid_item']
            for attr in system_attrs:
                if hasattr(canvas, attr) and item == getattr(canvas, attr):
                    return True
                    
            # Check against _workarea_items (which includes axes arrows, origin marker)
            if hasattr(canvas, '_workarea_items'):
                if item in canvas._workarea_items:
                    return True
            
        except Exception as e:
            logger.debug(f"检查系统项时出错: {e}")
        return False



    def _get_item_color_hex(self, item) -> Optional[str]:
        """提取图元颜色（HEX 大写），用于匹配图层参数。"""
        color_hex = None

        if hasattr(item, 'data'):
            color_data = item.data(LAYER_COLOR_ROLE)
            if color_data:
                if isinstance(color_data, QColor):
                    color_hex = color_data.name().upper()
                elif isinstance(color_data, str):
                    color_hex = color_data.upper()

        if not color_hex and hasattr(item, '_color'):
            c = getattr(item, '_color')
            if isinstance(c, QColor):
                color_hex = c.name().upper()
            elif isinstance(c, str):
                color_hex = c.upper()

        if not color_hex and hasattr(item, 'pen'):
            try:
                pen = item.pen()
                if pen and pen.color().isValid():
                    color_hex = pen.color().name().upper()
            except Exception:
                pass

        if not color_hex and hasattr(item, 'brush'):
            try:
                brush = item.brush()
                if brush and brush.color().isValid():
                    color_hex = brush.color().name().upper()
            except Exception:
                pass

        if not color_hex and hasattr(item, 'defaultTextColor'):
            try:
                color = item.defaultTextColor()
                if color and color.isValid():
                    color_hex = color.name().upper()
            except Exception:
                pass

        return color_hex

    def _get_item_params(self, item):
        """获取项目的加工参数（速度、功率、模式等）"""
        params = {
            'speed': self.config.get('feed_rate', 1000),
            'min_power': 0.0,
            'max_power': self.config.get('max_laser_power', 255),
            'power': self.config.get('max_laser_power', 255),
            'mode': 'cut', # cut or scan
            'scan_interval': self.config.get('scan_interval', 0.1),
            'scan_mode': 'horizontal', # horizontal or bidirectional
            'scan_direction': self.config.get('scan_direction', '从上往下(从左往右)')
        }

        color_hex = self._get_item_color_hex(item)

        if color_hex and hasattr(self, 'layer_settings') and color_hex in self.layer_settings:
            layer = self.layer_settings[color_hex]
            # LayerParams 对象
            params['speed'] = layer.speed * 60 # mm/s -> mm/min
            params['min_power'] = layer.min_power * 2.55 # % -> 0-255
            params['max_power'] = layer.max_power * 2.55 # % -> 0-255
            params['power'] = params['max_power']

            # 判断模式
            if "雕刻" in layer.mode or "扫描" in layer.mode:
                params['mode'] = 'scan'
            else:
                params['mode'] = 'cut'

            params['scan_interval'] = layer.scan_interval
            params['scan_mode'] = layer.scan_mode
            if hasattr(layer, 'scan_direction') and layer.scan_direction and layer.scan_direction != '跟随全局':
                params['scan_direction'] = layer.scan_direction

        return params

    def _process_exportable_item(self, item_data, fiducial_offset: Tuple[float, float]):
        """处理可导出项（应用定位点偏移）"""
        try:
<<<<<<< HEAD
            # item_data: (item_type, item, color_hex)
            if len(item_data) == 3:
                item_type, item, color_hex = item_data
            else:
                # 兼容旧格式 (item_type, item)
                item_type, item = item_data
                color_hex = None

            if item_type == 'vector':
                self._process_vector_item(item, fiducial_offset, color_hex)
            elif item_type == 'ellipse':
                self._process_ellipse_item(item, fiducial_offset, color_hex)
=======
            item_type, item = item_data
            params = self._get_item_params(item)
            
            # 添加调试注释到G代码
            self.gcode_lines.append(f"(处理项目类型: {item_type}, 类: {type(item).__name__})")
            
            if item_type == 'vector':
                self._process_vector_item(item, fiducial_offset, params)
            elif item_type == 'qt_path':
                self._process_generic_path_item(item, fiducial_offset, params)
            elif item_type == 'ellipse':
                self._process_ellipse_item(item, fiducial_offset, params)
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
            elif item_type == 'bitmap':
                # 位图默认强制使用扫描模式处理，除非另有指定
                self._process_bitmap_item(item, fiducial_offset, params)

        except Exception as e:
            logger.error(f"处理{item_type}项时出错: {e}")
            self.gcode_lines.append(f"(处理出错: {str(e)})")

<<<<<<< HEAD
    def _get_layer_params_for_color(self, color_hex: Optional[str]) -> Optional[Dict[str, Any]]:
        """根据颜色代码获取简化后的图层参数字典"""
        if not color_hex:
            return None
        return self.layer_params.get(color_hex.upper())

    def _process_vector_item(self, item, fiducial_offset: Tuple[float, float], color_hex: Optional[str]):
=======

    def _process_generic_path_item(self, item, fiducial_offset: Tuple[float, float], params):
        """处理通用 QGraphicsPathItem (如 TextGraphicsItem)"""
        try:
            path = item.path()
            if path.isEmpty(): 
                self.gcode_lines.append("(路径为空)")
                return
            
            # 将路径映射到场景坐标
            scene_path = item.mapToScene(path)
            
            # CRITICAL FIX: 使用变换来提高 toSubpathPolygons 的精度
            # 否则小尺寸图形可能会退化
            scale_factor = 100.0
            t = QTransform().scale(scale_factor, scale_factor)
            polygons_high_res = scene_path.toSubpathPolygons(t)
            
            polygons = []
            inv_t, _ = t.inverted()
            for p in polygons_high_res:
                polygons.append(inv_t.map(p))

            self.gcode_lines.append(f"(检测到 {len(polygons)} 个多边形轮廓)")
            
            # Check for micro joint config
            mj_config = None
            if hasattr(item, 'micro_joint_config') and item.micro_joint_config and item.micro_joint_config.get('enabled'):
                mj_config = item.micro_joint_config
                self.gcode_lines.append(f"(应用微连配置: {mj_config})")

            for index, poly in enumerate(polygons):
                # Apply micro joints if enabled
                poly_segments = [poly]
                if mj_config:
                    # poly is QPolygonF, compatible with list access
                    poly_segments = calculate_micro_joint_splits(poly, mj_config)

                for seg_idx, segment in enumerate(poly_segments):
                    points = []
                    for pt in segment: # QPointF
                        points.append((pt.x(), pt.y()))
                    
                    # FIX: 不要强制闭合未闭合的路径，也不要过滤掉只有2个点的线段 (除非是同一个点)
                    # 只有当点数 >= 2 且长度 > 0 时才处理
                    
                    if points and len(points) >= 2:
                         # 应用定位点偏移
                        offset_points = [self._apply_fiducial_offset(pt, fiducial_offset) for pt in points]
                        
                        self.gcode_lines.append(f"(轮廓 {index+1}-{seg_idx+1}, 点数: {len(points)})")
                        self._process_polyline(offset_points, params)
                    
        except Exception as e:
            logger.error(f"处理通用路径项时出错: {e}")
            self.gcode_lines.append(f"(处理路径项出错: {str(e)})")

    def _get_exportable_items(self, canvas, allowed_colors: List[str] = None) -> List[tuple]:
        """获取所有可导出项 (增加对 Line, Rect, SimpleText 的支持)"""
        items = []
        self.debug_logs = [] # Debug
        self.debug_logs.append(f"Start exporting. Allowed colors: {allowed_colors}")

        try:
            from PyQt5.QtWidgets import QGraphicsLineItem, QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsSimpleTextItem

            # [Fix] 使用 AscendingOrder 以匹配 Z-Order (即 "路径优化" 的结果)
            all_items = canvas.scene.items(order=Qt.AscendingOrder)
            # all_items = canvas.scene.items()
            self.debug_logs.append(f"Total scene items: {len(all_items)}")
            
            for item in all_items:
                # Debug info for current item
                item_name = type(item).__name__
                
                # 排除系统项
                if self._is_system_item(item, canvas):
                    self.debug_logs.append(f"System Item: {item_name}")
                    continue

                # 检查隐藏项
                if not item.isVisible():
                    self.debug_logs.append(f"Invisible Item: {item_name}")
                    continue

                # 检查图层是否允许输出
                processed_color = "NONE"
                should_skip_color = False
                
                if allowed_colors is not None:
                    item_color_hex = self._get_item_color_hex(item)

                    processed_color = str(item_color_hex)
                    
                    # 如果找到了颜色，且不在允许列表中，则跳过
                    if item_color_hex and item_color_hex not in allowed_colors:
                        self.debug_logs.append(f"Skip {item_name}, Color: {item_color_hex}")
                        should_skip_color = True
                    
                    if not should_skip_color and self.layer_settings and item_color_hex:
                        layer = self.layer_settings.get(item_color_hex)
                        if layer and not layer.is_output:
                            self.debug_logs.append(f"Skip {item_name}, is_output=False, Color: {item_color_hex}")
                            should_skip_color = True
                    # [Critical Fallback] If no color found, should we skip?
                    # For now, allow it but log it. Usually user drawing has color.
                    
                if should_skip_color:
                    continue

                matched_type = False

                # 1. 优先检查是否为椭圆/圆 (EditableEllipseItem)
                if EditableEllipseItem and isinstance(item, EditableEllipseItem):
                    items.append(('ellipse', item))
                    matched_type = True
                    self.debug_logs.append(f"Add Ellipse {item_name} {processed_color}")
                    continue

                # 2. 矢量路径项 (EditablePathItem 或其他具有 points 方法的项)
                # Modified: Treat as qt_path but ensure we handle it
                
                # 3. 通用 QGraphicsPathItem (TextGraphicsItem 等)
                if isinstance(item, QGraphicsPathItem):
                    path = item.path()
                    if not path.isEmpty():
                         items.append(('qt_path', item))
                         matched_type = True
                         self.debug_logs.append(f"Add Path {item_name} {processed_color}")
                         continue
                    else:
                         self.debug_logs.append(f"Empty Path {item_name}")

                # 4. 位图项
                elif isinstance(item, QGraphicsPixmapItem):
                    if not item.pixmap().isNull():
                        items.append(('bitmap', item))
                        matched_type = True
                        continue
                
                # 5. [NEW] 简单线条 QGraphicsLineItem
                elif isinstance(item, QGraphicsLineItem):
                    line = item.line()
                    # 转换为 QPainterPath
                    path = QGraphicsPathItem(item.parentItem())
                    pp = QPainterPath()
                    pp.moveTo(line.p1())
                    pp.lineTo(line.p2())
                    # 设置新的临时 PathItem，继承位置变换
                    path.setPath(pp)
                    path.setPos(item.pos())
                    path.setTransform(item.transform())
                    
                    # [Fix] 复制属性以确保颜色识别和参数正确
                    path.setPen(item.pen())
                    if item.data(LAYER_COLOR_ROLE):
                        path.setData(LAYER_COLOR_ROLE, item.data(LAYER_COLOR_ROLE))
                    if hasattr(item, 'micro_joint_config'):
                        path.micro_joint_config = item.micro_joint_config
                    if hasattr(item, '_color'):
                        path._color = item._color

                    items.append(('qt_path', path))
                    matched_type = True
                    self.debug_logs.append(f"Add Line {item_name} {processed_color}")

                # 6. [NEW] 矩形 QGraphicsRectItem
                elif isinstance(item, QGraphicsRectItem):
                     # 转换为 QPainterPath
                    path = QGraphicsPathItem(item.parentItem())
                    pp = QPainterPath()
                    pp.addRect(item.rect())
                    path.setPath(pp)
                    path.setPos(item.pos())
                    path.setTransform(item.transform())
                    
                    # [Fix] 复制属性
                    path.setPen(item.pen())
                    path.setBrush(item.brush()) # Rect可能由brush填充
                    if item.data(LAYER_COLOR_ROLE):
                        path.setData(LAYER_COLOR_ROLE, item.data(LAYER_COLOR_ROLE))
                    if hasattr(item, 'micro_joint_config'):
                        path.micro_joint_config = item.micro_joint_config
                    if hasattr(item, '_color'):
                        path._color = item._color

                    items.append(('qt_path', path))
                    matched_type = True
                    self.debug_logs.append(f"Add Rect {item_name} {processed_color}")
                
                # 7. [NEW] 多边形 QGraphicsPolygonItem
                elif isinstance(item, QGraphicsPolygonItem):
                    path = QGraphicsPathItem(item.parentItem())
                    pp = QPainterPath()
                    pp.addPolygon(item.polygon())
                    path.setPath(pp)
                    path.setPos(item.pos())
                    path.setTransform(item.transform())
                    
                    # [Fix] 复制属性
                    path.setPen(item.pen())
                    path.setBrush(item.brush())
                    if item.data(LAYER_COLOR_ROLE):
                        path.setData(LAYER_COLOR_ROLE, item.data(LAYER_COLOR_ROLE))
                    if hasattr(item, 'micro_joint_config'):
                        path.micro_joint_config = item.micro_joint_config
                    if hasattr(item, '_color'):
                        path._color = item._color

                    items.append(('qt_path', path))
                    matched_type = True
                
                if not matched_type:
                    self.debug_logs.append(f"Unmatched Type: {item_name}, Color: {processed_color}")

        except Exception as e:
            logger.error(f"获取可导出项时出错: {e}")

        if self.layer_settings:
            def get_priority(entry):
                _, it = entry
                color_hex = self._get_item_color_hex(it)
                if color_hex and color_hex in self.layer_settings:
                    return getattr(self.layer_settings[color_hex], 'priority', 9999)
                return 9999

            items.sort(key=get_priority)

        # 排序：图层优先，同图层就近原则
        # [Fix] 禁用自动排序，完全尊重 "路径优化" (Z-Order) 的结果
        # items = self._sort_items(items)
        return items

    def _sort_items(self, items):
        """对导出项进行排序：图层优先级 -> 路径优化"""
        if not items: return []
        
        # 1. 按图层/颜色分组
        # 假设图层列表顺序即为优先级 (allowed_colors order? or just string sort?)
        # 理想情况是 layer_settings 有一个 'priority' 字段，或按 keys 排序
        # 这里把 items 归类到不同的 bucket
        
        layer_groups = {} # color_hex -> list of (type, item)
        unknown_layer = []
        
        for entry in items:
            item_type, item = entry
            color_hex = "DEFAULT"
            
            # Extract color again (redundant but safe)
            if hasattr(item, 'data') and item.data(LAYER_COLOR_ROLE):
                c = item.data(LAYER_COLOR_ROLE)
                color_hex = c.name().upper() if isinstance(c, QColor) else str(c).upper()
            elif hasattr(item, 'pen'):
                 try:
                     pen = item.pen()
                     if pen and pen.color().isValid():
                         color_hex = pen.color().name().upper()
                 except: pass
            
            if color_hex not in layer_groups:
                layer_groups[color_hex] = []
            layer_groups[color_hex].append(entry)

        # 2. 决定图层加工顺序
        # 如果 layer_settings 存在，尝试遵循某种顺序
        sorted_keys = sorted(layer_groups.keys()) 
        # TODO: Apply user-defined layer priority
        
        sorted_items = []
        
        # 3. 对每个图层及其内部进行路径优化 (Greedy Nearest Neighbor)
        from PyQt5.QtCore import QPointF, QLineF
        
        current_pos = QPointF(0, 0)
        # 获取上次结束位置可能会更好，但在 group loop 里更新 current_pos 即可
        
        for color in sorted_keys:
            group_items = layer_groups[color]
            
            # 将 item 包装成带有起点信息的对象
            # 为了效率，预计算起点
            weighted_items = []
            for entry in group_items:
                itype, obj = entry
                start_pt = QPointF(0,0)
                
                # 估算起点
                if itype == 'vector' or itype == 'qt_path':
                    # Need mapToScene
                    if hasattr(obj, 'path'): # qt_path
                        # 这是一个耗时操作，但在导出时可以接受
                         scene_br = obj.mapToScene(obj.path()).boundingRect()
                         start_pt = scene_br.topLeft() # 近似
                    elif hasattr(obj, 'points'): # vector
                         pts = obj.points()
                         if pts:
                             start_pt = obj.mapToScene(QPointF(pts[0][0], pts[0][1]))
                elif itype == 'ellipse' or itype == 'bitmap':
                     scene_br = obj.sceneBoundingRect()
                     start_pt = scene_br.topLeft()
                
                weighted_items.append({
                    'entry': entry,
                    'start_pt': start_pt
                })
            
            # Nearest Neighbor Sort
            while weighted_items:
                # Find closest to current_pos
                nearest_idx = -1
                min_dist = float('inf')
                
                for i, w_item in enumerate(weighted_items):
                    # dist_sq = (current_pos.x() - w_item['start_pt'].x())**2 + ...
                    line = QLineF(current_pos, w_item['start_pt'])
                    d = line.length() # or len_sq
                    if d < min_dist:
                        min_dist = d
                        nearest_idx = i
                
                if nearest_idx != -1:
                    popped = weighted_items.pop(nearest_idx)
                    sorted_items.append(popped['entry'])
                    # Update current_pos to item's approx end point? 
                    # For simplicity, use start point as we "moved" there.
                    # Or ideally, calculate end point.
                    current_pos = popped['start_pt'] 
                else:
                    break
        
        return sorted_items

    def _process_vector_item(self, item, fiducial_offset: Tuple[float, float], params):
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
        """处理矢量路径项（应用定位点偏移）"""
        try:
            # 尝试修复 EditablePathItem 的位置问题
            # 如果是 EditablePathItem，points() 返回的是局部坐标
            # 我们应该应用 mapToScene
            points = item.points()
            params.setdefault('power', 255) # Ensure power is set
            params.setdefault('speed', 1000)

            if points and len(points) >= 2:
                # 转换坐标系
                new_points = []
                from PyQt5.QtCore import QPointF
                for px, py in points:
                    scene_pt = item.mapToScene(QPointF(px, py))
                    new_points.append((scene_pt.x(), scene_pt.y()))
                points = new_points

                # 应用定位点偏移
                offset_points = [self._apply_fiducial_offset(pt, fiducial_offset) for pt in points]
<<<<<<< HEAD
                logger.info(f"处理矢量路径，包含 {len(points)} 个点，应用定位点偏移")
                self._process_polyline(offset_points, color_hex=color_hex)
        except Exception as e:
            logger.error(f"处理矢量项时出错: {e}")

    def _process_ellipse_item(self, item, fiducial_offset: Tuple[float, float], color_hex: Optional[str]):
=======
                logger.info(f"处理矢量路径，包含 {len(points)} 个点")
                
                # Check for Micro-joint config
                if hasattr(item, 'micro_joint_config') and item.micro_joint_config and item.micro_joint_config.get('enabled'):
                    sub_paths = self._apply_micro_joints_to_polyline(offset_points, item.micro_joint_config)
                    for sub_p in sub_paths:
                        if len(sub_p) >= 2:
                            self._process_polyline(sub_p, params)
                else:
                    self._process_polyline(offset_points, params)
        except Exception as e:
            logger.error(f"处理矢量项时出错: {e}")

    def _apply_micro_joints_to_polyline(self, points, config):
        """Applies micro-joints to a list of points (polyline), returning a list of polylines"""
        if not points or len(points) < 2:
            return [points]
            
        # 1. Calculate Distances and Total Length
        segment_lengths = []
        total_len = 0.0
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i+1]
            dist = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
            segment_lengths.append(dist)
            total_len += dist
            
        if total_len <= 1e-6:
            return [points]

        # 2. Determine Cut Locations (Centers)
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
            
        # 3. Determine Cut Ranges (Start, End)
        width = float(config.get('width', 0.0))
        half_w = width / 2.0
        cut_ranges = []
        for c in cut_centers:
            s = max(0.0, c - half_w)
            e = min(total_len, c + half_w)
            if s < e:
                cut_ranges.append((s, e))
        
        # Merge overlapping cuts
        cut_ranges.sort()
        merged_cuts = []
        if cut_ranges:
            curr_s, curr_e = cut_ranges[0]
            for next_s, next_e in cut_ranges[1:]:
                if next_s < curr_e:
                    curr_e = max(curr_e, next_e)
                else:
                    merged_cuts.append((curr_s, curr_e))
                    curr_s, curr_e = next_s, next_e
            merged_cuts.append((curr_s, curr_e))
            
        # 4. Generate Keep Intervals
        keep_intervals = []
        last_pos = 0.0
        for c_s, c_e in merged_cuts:
            if c_s > last_pos:
                keep_intervals.append((last_pos, c_s))
            last_pos = max(last_pos, c_e)
        if last_pos < total_len:
            keep_intervals.append((last_pos, total_len))
            
        # 5. Map Intervals to Polylines
        result_paths = []
        
        # Helper: Get point at absolute dist
        def get_pt_at_dist(d):
            # Find segment
            accum = 0.0
            for i, seg_len in enumerate(segment_lengths):
                if d <= accum + seg_len + 1e-9: # Found segment (with tolerance)
                    local_d = d - accum
                    t = local_d / seg_len if seg_len > 1e-9 else 0
                    p1 = points[i]
                    p2 = points[i+1]
                    return (p1[0] + (p2[0]-p1[0])*t, p1[1] + (p2[1]-p1[1])*t)
                accum += seg_len
            return points[-1]

        # Optimization: We can walk segments and intervals in parallel
        # But brute force map is safer and easier to implement correctly for now
        
        for k_s, k_e in keep_intervals:
            if k_e <= k_s: continue
            
            subpath = []
            # Add start point
            subpath.append(get_pt_at_dist(k_s))
            
            # Add intermediate vertices
            accum = 0.0
            for i, seg_len in enumerate(segment_lengths):
                seg_start = accum
                seg_end = accum + seg_len
                
                # Check if vertex i+1 is strictly inside interval (excluding endpoints to avoid duplication)
                # But we need vertices to maintain shape.
                # If segment is fully inside interval, we add end point.
                if seg_start >= k_s - 1e-9 and seg_end <= k_e + 1e-9:
                     subpath.append(points[i+1])
                elif seg_start < k_s and seg_end > k_s:
                    # Segment crosses start of interval. 
                    # We already added get_pt_at_dist(k_s) which is on this segment.
                    # We should add points[i+1] if seg_end <= k_e based on above logic.
                    # Wait, simplified logic:
                    # Iterate all original vertices. If a vertex is inside (k_s, k_e), add it.
                    pass
            
            # Re-do intermediate vertices logic carefully
            # Find index of first vertex > k_s
            # Find index of last vertex < k_e
            
            # Vertices are at accum=0 (p0), accum=seg_len0 (p1), etc.
            accum = 0.0
            for i in range(len(points)):
                if i == 0: 
                    accum = 0.0
                else: 
                     accum += segment_lengths[i-1]
                
                # If vertex is strictly inside interval (k_s < accum < k_e)
                if accum > k_s + 1e-5 and accum < k_e - 1e-5:
                    subpath.append(points[i])
                    
            # Add end point
            subpath.append(get_pt_at_dist(k_e))
            
            result_paths.append(subpath)

        return result_paths

    def _process_ellipse_item(self, item, fiducial_offset: Tuple[float, float], params):
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
        """处理椭圆/圆项（使用G2/G3指令）"""
        try:
            cx, cy, rx, ry = item.get_params()
            
            # 应用定位点偏移
            # item.get_params() 返回的是 Item 坐标系下的参数? 
            # 通常 EditableEllipseItem 的 get_params 返回的是 Rect 的中心和半径
            # 但我们需要 Scene 坐标。
            # 先转换圆心
            from PyQt5.QtCore import QPointF
            scene_center = item.mapToScene(QPointF(cx, cy))
            
            # 半径受 Scale 影响。假设等比缩放
            # 如果是非等比缩放，应该变成椭圆处理。
            # 简化：取 X 方向 Scale
            transform = item.sceneTransform()
            scale_x = (transform.m11()**2 + transform.m12()**2)**0.5
            
            r_scene = rx * scale_x # 简化处理
            
            offset_cx, offset_cy = self._apply_fiducial_offset((scene_center.x(), scene_center.y()), fiducial_offset)
            
            # 检查是否为正圆（允许微小误差）
            # 注意：如果 Scale X != Scale Y，那场景中就是椭圆
            # 这里简单判断原始 radii
            
            if abs(rx - ry) < 1e-4:
<<<<<<< HEAD
                logger.info(f"处理圆形: 圆心({offset_cx:.2f}, {offset_cy:.2f}), 半径 {rx:.2f}")
                # 圆形暂时仍然使用 G2/G3，不做封口和延时的几何修改
                self._generate_circle_gcode(offset_cx, offset_cy, rx)
=======
                self._generate_circle_gcode(offset_cx, offset_cy, r_scene, params)
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
            else:
                # 椭圆转换为多段线
                import math
                steps = 128
                points = []
                for i in range(steps + 1):
                    angle = 2 * math.pi * i / steps
                    # 本地坐标点
                    lx = cx + rx * math.cos(angle)
                    ly = cy + ry * math.sin(angle)
                    # 转换到场景
                    scene_pt = item.mapToScene(QPointF(lx, ly))
                    points.append((scene_pt.x(), scene_pt.y()))
                
                if points and len(points) >= 2:
                    offset_points = [self._apply_fiducial_offset(pt, fiducial_offset) for pt in points]
<<<<<<< HEAD
                    self._process_polyline(offset_points, color_hex=color_hex)
=======
                    self._process_polyline(offset_points, params)
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
                    
        except Exception as e:
            logger.error(f"处理椭圆项时出错: {e}")

    def _generate_circle_gcode(self, cx, cy, r, params):
        """生成圆形的G代码（使用G2/G3）"""
        # 移动到起点（圆的最右侧点）
        start_x = cx + r
        start_y = cy
        
        self.gcode_lines.append(f"G0 X{start_x:.3f} Y{start_y:.3f}")
        
        feed = params['speed']
        
        # Check for small circle speed limit
        diameter = 2 * r
        limit_speed = None
        if hasattr(self, 'small_circle_limit') and self.small_circle_limit:
            # Sort limits by diameter just in case
            sorted_limits = sorted(self.small_circle_limit, key=lambda x: x[0])
            for d_limit, v_limit in sorted_limits:
                if diameter <= d_limit:
                    limit_speed = v_limit
                    break # Found the bracket
        
        if limit_speed is not None:
             # Convert mm/s to mm/min for G-code
             feed = min(feed, limit_speed * 60)
             self.gcode_lines.append(f"(小圆限速生效: Dia={diameter:.2f}mm, Speed={limit_speed}mm/s, Feed={feed:.1f})")

        self.gcode_lines.append(f"M3 S{int(params['power'])}") # 激光开启
        
        # 使用G2（顺时针）或G3（逆时针）画圆
        # 兼容性处理：分成两段半圆
        mid_x = cx - r
        mid_y = cy
        
        # Segment 1
        self.gcode_lines.append(f"G3 X{mid_x:.3f} Y{mid_y:.3f} I{-r:.3f} J0.000 F{feed:.1f}")
        # Segment 2
        self.gcode_lines.append(f"G3 X{start_x:.3f} Y{start_y:.3f} I{r:.3f} J0.000")
        
        self.gcode_lines.append("M5") # 激光关闭

    def _process_bitmap_item(self, item, fiducial_offset: Tuple[float, float], params):
        """处理位图项（应用定位点偏移）"""
        try:
            if not isinstance(item, QGraphicsPixmapItem):
                return

            pixmap = item.pixmap()
            if pixmap.isNull():
                return

            logger.info("开始处理位图项（应用定位点偏移）")

            bounding_rect = item.sceneBoundingRect()
            if bounding_rect.isNull():
                return

            # [Fix] bounding_rect 是 Scene 坐标下的 BBox
            # 我们传递给 _raster_scan_bitmap 的需要是原始的 Scene BBox
            # 而不是在这里提前进行 offset. offset 应该在 G 代码生成时统一应用 (_apply_fiducial_offset)
            # 但旧代码 logic 是传 offset_bounding_rect?
            # 让我们看看 _raster_scan_bitmap 怎么用的。
            # 老代码：offset_bounding_rect = bounding_rect.translated(-offset_x, -offset_y)
            # 新逻辑：我需要在 _raster_scan_bitmap 内部调用 _apply_fiducial_offset
            # 所以这里最好传递原始的 Scene bounding_rect，以及 fiducial_offset
            
            # 由于 _raster_scan_bitmap 需要 bounding_rect 来计算 scale，
            # 只要宽高对就行。位置信息我们需要用原始的来计算 Scene 坐标。
            
            # 为了明确，我们传递原始 scene bounding_rect 和 fiducial offset
            
            # 强制使用光栅扫描 (除非用户真的很想要轮廓，那以后再加开关)
            # 绝大多数位图用途是灰度扫描
            logger.info("位图项强制使用优化版双向扫描")
            self._raster_scan_bitmap(pixmap, bounding_rect, fiducial_offset, params)

        except Exception as e:
            logger.error(f"位图处理失败: {e}")
            # 计算 offset_bounding_rect 以备 fallback 使用
            # offset_x, offset_y = fiducial_offset
            # offset_bounding_rect = bounding_rect.translated(-offset_x, -offset_y)
            # self._process_bounding_box(offset_bounding_rect, params)




    def _try_contour_detection(self, pixmap: QPixmap, bounding_rect, params) -> bool:
        """尝试使用轮廓检测生成连续路径"""
        try:
            # 检查OpenCV是否可用
            try:
                import cv2
            except ImportError:
                logger.warning("未安装OpenCV，跳过轮廓检测")
                return False
            # 安全地将QPixmap转换为PIL图像，然后转换为numpy数组供OpenCV使用
            from PyQt5.QtCore import QBuffer, QIODevice, QByteArray
            from io import BytesIO

            qimage = pixmap.toImage()
            if qimage.isNull():
                return False

            ba = QByteArray()
            buf = QBuffer(ba)
            if not buf.open(QIODevice.WriteOnly):
                return False
            qimage.save(buf, 'PNG')
            buf.close()

            pil_img = Image.open(BytesIO(ba.data())).convert('L')
            arr_gray = np.array(pil_img)

            gray = arr_gray

            # 二值化
            threshold = self.config['grayscale_threshold']
            _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)

            # 查找轮廓
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return False

            # 转换轮廓为路径
            scale_x = bounding_rect.width() / qimage.width()
            scale_y = bounding_rect.height() / qimage.height()
            offset_x = bounding_rect.left()
            offset_y = bounding_rect.top()

            contour_paths = []
            for contour in contours:
                if len(contour) >= 3:  # 至少需要3个点
                    points = []
                    for point in contour:
                        x = offset_x + point[0][0] * scale_x
                        y = offset_y + point[0][1] * scale_y
                        points.append((x, y))

                    if len(points) >= 3:
                        # 闭合路径
                        points.append(points[0])
                        contour_paths.append(points)

            if contour_paths:
                logger.info(f"找到 {len(contour_paths)} 个轮廓")
                for path in contour_paths:
                    self._process_polyline(path, params)
                return True

            return False

        except Exception as e:
            logger.warning(f"轮廓检测失败: {e}")
            return False

    def _raster_scan_bitmap(self, pixmap: QPixmap, bounding_rect, fiducial_offset, params):
        """光栅扫描位图（优化版双向扫描 - C++算法移植）"""
        try:
            try:
                import cv2
            except ImportError:
                logger.error("需安装 opencv-python 以支持位图导出")
                # 提示用户
                self.gcode_lines.append("(Error: OpenCV not installed, cannot process bitmap)")
                return

            import numpy as np
            from PyQt5.QtCore import QBuffer, QIODevice, QByteArray
            from io import BytesIO

            # 1. Image Conversion
            qimage = pixmap.toImage()
            if qimage.isNull(): return

            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            qimage.save(buf, "BMP")
            buf.close()
            
            nparr = np.frombuffer(ba.data(), np.uint8)
            mat = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            
            if mat is None: return

            # 2. Setup Parameters and Resize
            width_mm = bounding_rect.width()
            height_mm = bounding_rect.height()
            
            # Scene top-left
            scene_left = bounding_rect.left()
            scene_top = bounding_rect.top()

            scan_interval = float(params.get('scan_interval', 0.1))
            if scan_interval <= 0.001: scan_interval = 0.1
            resolution = 1.0 / scan_interval

            target_w = int(width_mm * resolution)
            target_h = int(height_mm * resolution)
            
            if target_w <= 0 or target_h <= 0: return

            # Inter_Linear gives smoother result than Nearest
            image = cv2.resize(mat, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            
            rows, cols = image.shape
            
            max_power = float(params.get('max_power', params.get('power', 255)))
            min_power = float(params.get('min_power', 0.0))
            scan_mode = params.get('scan_mode', '水平单向')
            scan_direction = params.get('scan_direction', '从上往下(从左往右)')

            is_vertical = '垂直' in scan_mode
            is_bidirectional = '双向' in scan_mode
            start_from_bottom = '从下往上' in scan_direction
            start_from_left = '从左往右' in scan_direction

            line_count = cols if is_vertical else rows
            scan_count = rows if is_vertical else cols

            def map_scan_to_pixel(scan_idx, line_idx):
                if is_vertical:
                    return (line_idx, scan_idx)
                return (scan_idx, line_idx)
            
            # Helper: Calculate G-Code position
            # px, py are pixel indices in the RESIZED image
            def get_position(px, py):
                # 1. Convert Pixel -> Local mm (relative to Top-Left)
                rel_x = px / resolution
                rel_y = py / resolution
                
                # 2. Convert Local mm -> Scene Abs
                scene_x = scene_left + rel_x
                scene_y = scene_top + rel_y
                
                # 3. Apply Fiducial Offset (Scene -> GCode)
                # This handles axis inversion (Y-flip) and origin shift
                return self._apply_fiducial_offset((scene_x, scene_y), fiducial_offset)

            def get_g_move(px, py):
                gx, gy = get_position(px, py)
                return f"G0 X{gx:.3f} Y{gy:.3f}"
            
            def get_g_x_only(px, py):
                # Since we are scanning horizontally, Y is typically constant for the line.
                # However, _apply_fiducial_offset might include rotation/skew in future (unlikely here)
                # But it DOES flip Y. So if scene_y is const, gy is const.
                gx, _ = get_position(px, py)
                return f"X{gx:.3f}"
            
            def get_g_linear(px, py, s_val):
                gx, gy = get_position(px, py)
                return f"G1 X{gx:.3f} Y{gy:.3f} {s_val}"

            def get_g_move_idx(scan_idx, line_idx):
                px, py = map_scan_to_pixel(scan_idx, line_idx)
                return get_g_move(px, py)

            def get_g_linear_idx(scan_idx, line_idx, s_val):
                px, py = map_scan_to_pixel(scan_idx, line_idx)
                return get_g_linear(px, py, s_val)

            logger.info(f"Bitmap Scan: {target_w}x{target_h}, Res: {resolution:.2f}")
            self.gcode_lines.append(f"(Bitmap Scan: {target_w}x{target_h} pixels, Step={scan_interval}mm)")

            # 3. Scanning Loop (respect scan direction)
            if is_vertical:
                line_indices = range(cols) if start_from_left else range(cols - 1, -1, -1)
            else:
                line_indices = range(rows - 1, -1, -1) if start_from_bottom else range(rows)

            for line_i, line_idx in enumerate(line_indices):
                if is_vertical:
                    forward = start_from_bottom
                else:
                    forward = start_from_left

                if is_bidirectional and (line_i % 2 == 1):
                    forward = not forward

                start = 0 if forward else scan_count - 1
                end = scan_count if forward else -1
                step = 1 if forward else -1

                scan_idx = start
                while scan_idx != end:
                    px, py = map_scan_to_pixel(scan_idx, line_idx)
                    pixel = image[py, px]

                    if pixel == 255:
                        scan_idx += step
                        continue

                    current_gray = pixel
                    seg_start = scan_idx

                    while True:
                        next_idx = scan_idx + step
                        if next_idx == end:
                            break
                        n_px, n_py = map_scan_to_pixel(next_idx, line_idx)
                        next_pixel = image[n_py, n_px]
                        if next_pixel == 255 or next_pixel != current_gray:
                            break
                        scan_idx = next_idx

                    seg_end = scan_idx

                    p_val = min_power + (max_power - min_power) * (1.0 - float(current_gray) / 255.0)
                    s_cmd = f"S{int(p_val)}"
                    self.gcode_lines.append(get_g_move_idx(seg_start, line_idx))
                    self.gcode_lines.append(get_g_linear_idx(seg_end, line_idx, s_cmd))

                    scan_idx += step

            
            # Post-loop cleanup
            self.gcode_lines.append("M5")
            
        except Exception as e:
            logger.error(f"光栅扫描失败: {e}")
            self.gcode_lines.append(f"(Bitmap Scan Error: {e})")



    def _process_raster_segment(self, points: List[Point]):
        """(Legacy) 处理光栅扫描段"""
        pass

    def _process_bounding_box(self, bounding_rect, params):
        """处理边界框（降级方案）"""
        points = [
            (bounding_rect.left(), bounding_rect.top()),
            (bounding_rect.right(), bounding_rect.top()),
            (bounding_rect.right(), bounding_rect.bottom()),
            (bounding_rect.left(), bounding_rect.bottom()),
            (bounding_rect.left(), bounding_rect.top())
        ]
        self._process_polyline(points, params)

    def _calculate_segment_length(self, points: List[Point]) -> float:
        """计算路径段长度"""
        return 0.0

<<<<<<< HEAD
        total_length = 0.0
        for i in range(1, len(points)):
            x1, y1 = points[i - 1]
            x2, y2 = points[i]
            length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            total_length += length

        return total_length

    def _apply_seal_gap(self, points: List[Point], seal_gap: float) -> List[Point]:
        """根据封口参数对首尾点做几何调整（正值多切，负值少切）"""
        if len(points) < 2 or abs(seal_gap) < 1e-6:
            return points[:]

        pts = points[:]
        g = float(seal_gap)

        # 首段
        x0, y0 = pts[0]
        x1, y1 = pts[1]
        dx0, dy0 = x1 - x0, y1 - y0
        L0 = (dx0 * dx0 + dy0 * dy0) ** 0.5
        if L0 > 1e-6:
            ux0, uy0 = dx0 / L0, dy0 / L0
            if g > 0:
                # 多切：向首段反方向延长
                pts[0] = (x0 - ux0 * g, y0 - uy0 * g)
            else:
                # 少切：沿首段方向前移
                d = min(abs(g), max(L0 - 1e-6, 0.0))
                pts[0] = (x0 + ux0 * d, y0 + uy0 * d)

        # 末段
        xn_1, yn_1 = pts[-2]
        xn, yn = pts[-1]
        dx1, dy1 = xn - xn_1, yn - yn_1
        L1 = (dx1 * dx1 + dy1 * dy1) ** 0.5
        if L1 > 1e-6:
            ux1, uy1 = dx1 / L1, dy1 / L1
            if g > 0:
                # 多切：向末段方向延长
                pts[-1] = (xn + ux1 * g, yn + uy1 * g)
            else:
                # 少切：沿末段反方向回缩
                d = min(abs(g), max(L1 - 1e-6, 0.0))
                pts[-1] = (xn - ux1 * d, yn - uy1 * d)

        return pts

    def _polyline_total_length(self, points: List[Point]) -> float:
        L = 0.0
        for i in range(1, len(points)):
            x0, y0 = points[i - 1]
            x1, y1 = points[i]
            dx, dy = x1 - x0, y1 - y0
            L += (dx * dx + dy * dy) ** 0.5
        return L

    def _process_polyline(self, points: List[Point], color_hex: Optional[str] = None):
        """处理折线路径，支持封口以及激光开/关延时"""
=======
    def _process_polyline(self, points: List[Point], params):
        """处理折线路径"""
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
        if len(points) < 2:
            return

        # 获取图层参数
        lp = self._get_layer_params_for_color(color_hex)
        seal_gap = float(lp.get('seal_gap', 0.0)) if lp else 0.0
        laser_on_delay_ms = int(lp.get('laser_on_delay', 0)) if lp else 0
        laser_off_delay_ms = int(lp.get('laser_off_delay', 0)) if lp else 0

        # 先应用封口几何调整
        pts = self._apply_seal_gap(points, seal_gap)

        # 计算总长度和进给速度（mm/s）
        total_len = self._polyline_total_length(pts)
        if total_len <= 1e-6:
            return

        feed_rate_mm_min = float(self.config.get('feed_rate', 1000.0))
        v = max(feed_rate_mm_min / 60.0, 1e-6)  # mm/s，避免除零

        # 处理激光开延时（负值 = 提前出光，正值 = 延后出光）
        # 负值：在首段前再生成一段预切路径
        if laser_on_delay_ms < 0:
            adv_mm = abs(laser_on_delay_ms) / 1000.0 * v
            if adv_mm > 1e-6 and len(pts) >= 2:
                x0, y0 = pts[0]
                x1, y1 = pts[1]
                dx, dy = x1 - x0, y1 - y0
                L0 = (dx * dx + dy * dy) ** 0.5
                if L0 > 1e-6:
                    d = min(adv_mm, max(L0 - 1e-6, 0.0))
                    ux, uy = dx / L0, dy / L0
                    pre_pt = (x0 - ux * d, y0 - uy * d)
                    pts = [pre_pt] + pts
                    total_len = self._polyline_total_length(pts)
            # 预切模式下，后续按 0 延时处理（即一开始就出光）
            laser_on_delay_mm = 0.0
        else:
            laser_on_delay_mm = laser_on_delay_ms / 1000.0 * v
            # 如果延时时间超过总长度，截断到 90% 长度，避免整条路径都不出光
            laser_on_delay_mm = min(laser_on_delay_mm, max(total_len * 0.9, 0.0))

        # 激光关延时
        if laser_off_delay_ms < 0:
            # 负值：提前关光 => 计算在路径上的截止距离
            off_early_mm = abs(laser_off_delay_ms) / 1000.0 * v
            cut_stop_dist = max(total_len - off_early_mm, 0.0)
        else:
            # 非负：不提前关光，可能稍后延长路径
            cut_stop_dist = total_len

        # 移动到起点
        start_x, start_y = pts[0]
        self._add_rapid_move(start_x, start_y)

<<<<<<< HEAD
        # 逐段生成路径，并在合适位置打开/关闭激光
        acc = 0.0  # 已沿路径走过的长度
        laser_on = False
        laser_off_done = False

        # 预先计算延后关光对应的长度（用于稍后延长）
        laser_off_delay_mm_pos = 0.0
        if laser_off_delay_ms > 0:
            laser_off_delay_mm_pos = laser_off_delay_ms / 1000.0 * v

        last_dir = None  # 用于正延时关光时的末段延长

        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            dx, dy = bx - ax, by - ay
            seg_len = (dx * dx + dy * dy) ** 0.5
            if seg_len <= 1e-9:
                continue

            # 当前段剩余部分的起点
            cur_ax, cur_ay = ax, ay
            remaining = seg_len

            while remaining > 1e-9:
                seg_start_len = acc
                seg_end_len = acc + remaining

                # 计算本段中可能发生的事件：开光 / 早关光
                event_dist = None
                event_type = None

                # 延后开光：在第一次超过 laser_on_delay_mm 时出光
                if (not laser_on) and laser_on_delay_mm > 0.0 and seg_start_len < laser_on_delay_mm <= seg_end_len:
                    event_dist = laser_on_delay_mm
                    event_type = 'on'

                # 提前关光：在第一次超过 cut_stop_dist 时关光
                if (not laser_off_done) and laser_off_delay_ms < 0 and seg_start_len < cut_stop_dist <= seg_end_len:
                    # 与开光事件比较谁先发生
                    if event_dist is None or cut_stop_dist < event_dist:
                        event_dist = cut_stop_dist
                        event_type = 'off'

                if event_dist is None:
                    # 本段内无事件，直接走到段终点
                    if not laser_on and laser_on_delay_mm <= 0.0:
                        # 无延后，且尚未开光 => 在首次需要切割时立即开光
                        self._add_laser_on()
                        laser_on = True

                    self._add_linear_move(bx, by)
                    last_dir = (dx / seg_len, dy / seg_len)
                    acc += remaining
                    remaining = 0.0
                else:
                    # 段内有事件，需要拆分
                    dist_along = event_dist - seg_start_len  # 事件点距离当前小段起点的距离
                    t = dist_along / remaining
                    ex = cur_ax + (bx - cur_ax) * t
                    ey = cur_ay + (by - cur_ay) * t

                    # 先走到事件点
                    if not (abs(ex - cur_ax) < 1e-9 and abs(ey - cur_ay) < 1e-9):
                        if not laser_on and laser_on_delay_mm <= 0.0:
                            self._add_laser_on()
                            laser_on = True
                        self._add_linear_move(ex, ey)
                        last_seg_len = ((ex - cur_ax) ** 2 + (ey - cur_ay) ** 2) ** 0.5
                        if last_seg_len > 1e-9:
                            last_dir = ((ex - cur_ax) / last_seg_len, (ey - cur_ay) / last_seg_len)

                    acc = event_dist

                    # 在事件点切换激光状态
                    if event_type == 'on':
                        self._add_laser_on()
                        laser_on = True
                    elif event_type == 'off':
                        self._add_laser_off()
                        laser_off_done = True
                        laser_on = False

                    # 更新当前小段起点为事件点，继续检查本段剩余部分
                    cur_ax, cur_ay = ex, ey
                    remaining = seg_end_len - event_dist
                    if remaining <= 1e-9:
                        remaining = 0.0

        # 处理正向关光延时（多切）
        if not laser_off_done:
            if laser_off_delay_mm_pos > 1e-6 and last_dir is not None:
                # 在末端沿最后一段方向延长一小段
                end_x, end_y = pts[-1]
                ux, uy = last_dir
                ext_x = end_x + ux * laser_off_delay_mm_pos
                ext_y = end_y + uy * laser_off_delay_mm_pos
                if not laser_on and (laser_on_delay_mm <= 0.0 or acc >= laser_on_delay_mm):
                    self._add_laser_on()
                    laser_on = True
                self._add_linear_move(ext_x, ext_y)

            # 正常关光
            self._add_laser_off()
=======
        # 开启激光
        self.gcode_lines.append(f"M3 S{int(params['power'])}")
        self.laser_on = True

        # 连续移动
        feed = params['speed']
        for i in range(1, len(points)):
            x, y = points[i]
            self.gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed:.1f}")
            self.current_x = x
            self.current_y = y

        # 关闭激光
        self.gcode_lines.append("M5")
        self.laser_on = False

>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)

    def _add_header(self, fiducial_offset: Tuple[float, float]):
        """添加文件头（包含定位点信息）"""
        offset_x, offset_y = fiducial_offset

        header = [
            "%",
            "O1000 (激光加工G代码)",
            f"{self.config['units']} (毫米单位)",
            f"{self.config['absolute_positioning']} (绝对坐标)",
            "G17 (XY平面选择)",
            "G40 (取消刀具半径补偿)",
            "G49 (取消刀具长度补偿)",
            "G80 (取消固定循环)",
            "G54 (工作坐标系)",
            "",
            "M05 (确保激光关闭)",
            "G00 Z10 (快速移动到安全高度)",
        ]

        # 添加定位点信息注释
        if offset_x != 0 or offset_y != 0:
            header.extend([
                f"(定位点偏移: X{offset_x:.3f} Y{offset_y:.3f})",
                f"(所有坐标已相对于定位点进行偏移)",
            ])
        else:
            header.append("(使用默认原点)")

        header.extend([
            "",
            "(开始加工路径)",
        ])

        self.gcode_lines.extend(header)

    def _add_footer(self, fiducial_offset: Tuple[float, float]):
        """添加文件尾"""
        offset_x, offset_y = fiducial_offset

        footer = [
            "",
            "(结束加工路径)",
            "M05 (关闭激光)",
            "G00 Z10 (移动到安全高度)",
        ]

        # 如果使用了定位点，回到定位点位置
        if offset_x != 0 or offset_y != 0:
            footer.append(f"G00 X0 Y0 (回到定位点位置)")
        else:
            footer.append("G00 X0 Y0 (回到原点)")

        footer.extend([
            "M30 (程序结束)",
            "%",
        ])

        self.gcode_lines.extend(footer)

    def _add_no_content_warning(self):
        """无内容警告"""
        warning = [
            "(警告: 没有找到可导出的图形)",
        ]
        
        if hasattr(self, 'debug_logs'):
            warning.append("(Debug Logs:)")
            for msg in self.debug_logs[-50:]:
                safe_msg = str(msg).replace('\n', ' ').replace('\r', '')
                warning.append(f"({safe_msg})")

        warning.append("M00 (程序暂停)")
        self.gcode_lines.extend(warning)

    def _add_error_message(self, message: str):
        """错误消息"""
        error_msg = [
            f"(错误: {message})",
            "M00 (程序暂停)",
        ]
        self.gcode_lines.extend(error_msg)

    def _get_backlash_compensation(self, speed_mm_s: float, axis: str) -> float:
        """
        根据速度和轴获取反向间隙补偿值
        axis: 'X' 或 'Y'
        返回: 补偿值（mm），如果没有配置则返回0
        """
        if not self.scan_backlash_config or not self.scan_backlash_config.get('enabled', False):
            return 0.0
        
        config_axis = self.scan_backlash_config.get('axis', 'X')
        if axis != config_axis:
            return 0.0
        
        table_data = self.scan_backlash_config.get('table_data', [])
        if not table_data:
            return 0.0
        
        # 查找速度对应的反向间隙值（使用最接近的速度）
        best_match = None
        min_diff = float('inf')
        
        for entry in table_data:
            entry_speed = entry.get('speed', 0)
            diff = abs(entry_speed - speed_mm_s)
            if diff < min_diff:
                min_diff = diff
                best_match = entry
        
        if best_match:
            backlash = best_match.get('backlash', 0.0)
            offset = best_match.get('offset', 0.0)
            return backlash + offset
        
        return 0.0

    def _add_rapid_move(self, x: float, y: float):
        """快速移动"""
        line = f"G00 X{x:.3f} Y{y:.3f}"
        self.gcode_lines.append(line)
        self.current_x = x
        self.current_y = y
        # 快速移动不应用反向间隙补偿，重置方向跟踪
        self.last_move_dir_x = None
        self.last_move_dir_y = None

    def _add_linear_move(self, x: float, y: float):
        """线性移动（应用反向间隙补偿）"""
        dx = x - self.current_x
        dy = y - self.current_y
        
        # 计算当前运动方向
        dir_x = 0
        dir_y = 0
        if abs(dx) > 1e-6:
            dir_x = 1 if dx > 0 else -1
        if abs(dy) > 1e-6:
            dir_y = 1 if dy > 0 else -1
        
        # 计算速度（mm/s）
        feed_rate_mm_min = float(self.config.get('feed_rate', 1000.0))
        speed_mm_s = feed_rate_mm_min / 60.0
        
        # 应用反向间隙补偿
        compensation_x = 0.0
        compensation_y = 0.0
        
        # 1. 扫描反向间隙补偿（基于速度表的动态补偿）
        if self.scan_backlash_config and self.scan_backlash_config.get('enabled', False):
            config_axis = self.scan_backlash_config.get('axis', 'X')
            
            # X轴方向改变时应用补偿
            if config_axis == 'X' and self.last_move_dir_x is not None and dir_x != 0:
                if dir_x != self.last_move_dir_x:
                    compensation_x = self._get_backlash_compensation(speed_mm_s, 'X')
                    if dir_x < 0:  # 反向移动，补偿取负
                        compensation_x = -compensation_x
            
            # Y轴方向改变时应用补偿
            if config_axis == 'Y' and self.last_move_dir_y is not None and dir_y != 0:
                if dir_y != self.last_move_dir_y:
                    compensation_y = self._get_backlash_compensation(speed_mm_s, 'Y')
                    if dir_y < 0:  # 反向移动，补偿取负
                        compensation_y = -compensation_y
        
        # 2. 用户参数中的反向间隙补偿（固定值补偿）
        # X轴方向改变时应用固定补偿
        if abs(self.user_backlash_x) > 1e-6 and self.last_move_dir_x is not None and dir_x != 0:
            if dir_x != self.last_move_dir_x:
                # 方向改变，应用固定补偿
                user_comp_x = self.user_backlash_x
                if dir_x < 0:  # 反向移动，补偿取负
                    user_comp_x = -user_comp_x
                compensation_x += user_comp_x
        
        # Y轴方向改变时应用固定补偿
        if abs(self.user_backlash_y) > 1e-6 and self.last_move_dir_y is not None and dir_y != 0:
            if dir_y != self.last_move_dir_y:
                # 方向改变，应用固定补偿
                user_comp_y = self.user_backlash_y
                if dir_y < 0:  # 反向移动，补偿取负
                    user_comp_y = -user_comp_y
                compensation_y += user_comp_y
        
        # 如果有补偿，先移动到补偿位置
        if abs(compensation_x) > 1e-6 or abs(compensation_y) > 1e-6:
            comp_x = self.current_x + compensation_x
            comp_y = self.current_y + compensation_y
            line_comp = f"G01 X{comp_x:.3f} Y{comp_y:.3f} F{self.config['feed_rate']}"
            # 添加补偿注释
            comp_note = "; 反向间隙补偿"
            if abs(compensation_x) > 1e-6:
                comp_note += f" X:{compensation_x:.3f}"
            if abs(compensation_y) > 1e-6:
                comp_note += f" Y:{compensation_y:.3f}"
            self.gcode_lines.append(comp_note)
            self.gcode_lines.append(line_comp)
            self.current_x = comp_x
            self.current_y = comp_y
        
        # 移动到目标位置
        line = f"G01 X{x:.3f} Y{y:.3f} F{self.config['feed_rate']}"
        self.gcode_lines.append(line)
        self.current_x = x
        self.current_y = y
        
        # 更新方向跟踪
        if dir_x != 0:
            self.last_move_dir_x = dir_x
        if dir_y != 0:
            self.last_move_dir_y = dir_y

    def _add_laser_on(self):
        """开启激光"""
        if not self.laser_on:
            self.gcode_lines.append(f"M03 S{self.config['max_laser_power']}")
            self.laser_on = True

    def _add_laser_off(self):
        """关闭激光"""
        if self.laser_on:
            self.gcode_lines.append("M05")
        self.laser_on = False


<<<<<<< HEAD
def export_to_nc(canvas,
                 filename: str,
                 config: dict = None,
                 allowed_colors: List[str] = None,
                 layer_params: Dict[str, Dict[str, Any]] = None) -> bool:
    """导出画布为NC文件（支持定位点）"""
=======
def export_to_nc(canvas, filename: str, config: dict = None, allowed_colors: List[str] = None,
                 layer_settings: dict = None) -> bool:
    """导出画布为NC文件（支持定位点和图层参数）"""
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)
    try:
        exporter = GCodeExporter()

        if config:
            exporter.set_config(config)

<<<<<<< HEAD
        if layer_params:
            exporter.set_layer_params(layer_params)

        gcode_lines = exporter.export_canvas(canvas, allowed_colors)
=======
        gcode_lines = exporter.export_canvas(canvas, allowed_colors, layer_settings)
>>>>>>> 3ec087f (feat: restore and apply local 72-file changes)

        # 检查定位点信息
        fiducial = canvas.get_fiducial()
        if fiducial:
            point, shape = fiducial
            logger.info(f"导出完成，定位点位置: {point}, 形状: {shape}")

        with open(filename, 'w', encoding='utf-8') as f:
            for line in gcode_lines:
                f.write(line + '\n')

        logger.info(f"成功导出G代码到: {filename}")
        return True

    except Exception as e:
        logger.error(f"导出失败: {e}")
        return False


def get_default_config() -> dict:
    """获取默认配置"""
    return {
        'feed_rate': 1000,
        'max_laser_power': 255,
        'rapid_move_rate': 3000,
        'units': 'G21',
        'absolute_positioning': 'G90',
        'scan_interval': 0.1,
        'scan_direction': '从上往下(从左往右)',
        'grayscale_threshold': 128,
        'dpi': 96.0,
        'min_segment_length': 0.5,
    }