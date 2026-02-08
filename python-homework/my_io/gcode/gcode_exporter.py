#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复版G代码导出模块 - 解决位图导出问题
"""

import logging
import os
from typing import List, Tuple, Optional, Dict, Any
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem
from PyQt5.QtGui import QPixmap, QImage, QColor
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
        """应用定位点偏移"""
        x, y = point
        offset_x, offset_y = fiducial_offset
        return (x - offset_x, y - offset_y)

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
                if hasattr(item, 'points') and callable(getattr(item, 'points')):
                    try:
                        points = item.points()
                        if points and len(points) >= 2:
                            items.append(('vector', item, item_color_hex))
                    except Exception as e:
                        logger.warning(f"获取矢量路径点时出错: {e}")

                # 位图项
                elif isinstance(item, QGraphicsPixmapItem):
                    if not item.pixmap().isNull():
                        items.append(('bitmap', item, item_color_hex))

        except Exception as e:
            logger.error(f"获取可导出项时出错: {e}")

        return items

    def _is_system_item(self, item, canvas) -> bool:
        """判断是否为系统项"""
        try:
            system_attrs = ['_work_item', '_fiducial_item', '_grid_item']
            for attr in system_attrs:
                if hasattr(canvas, attr) and item == getattr(canvas, attr):
                    return True
        except Exception as e:
            logger.debug(f"检查系统项时出错: {e}")
        return False

    def _process_exportable_item(self, item_data, fiducial_offset: Tuple[float, float]):
        """处理可导出项（应用定位点偏移）"""
        try:
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
            elif item_type == 'bitmap':
                self._process_bitmap_item(item, fiducial_offset)

        except Exception as e:
            logger.error(f"处理{item_type}项时出错: {e}")

    def _get_layer_params_for_color(self, color_hex: Optional[str]) -> Optional[Dict[str, Any]]:
        """根据颜色代码获取简化后的图层参数字典"""
        if not color_hex:
            return None
        return self.layer_params.get(color_hex.upper())

    def _process_vector_item(self, item, fiducial_offset: Tuple[float, float], color_hex: Optional[str]):
        """处理矢量路径项（应用定位点偏移）"""
        try:
            points = item.points()
            if points and len(points) >= 2:
                # 应用定位点偏移
                offset_points = [self._apply_fiducial_offset(pt, fiducial_offset) for pt in points]
                logger.info(f"处理矢量路径，包含 {len(points)} 个点，应用定位点偏移")
                self._process_polyline(offset_points, color_hex=color_hex)
        except Exception as e:
            logger.error(f"处理矢量项时出错: {e}")

    def _process_ellipse_item(self, item, fiducial_offset: Tuple[float, float], color_hex: Optional[str]):
        """处理椭圆/圆项（使用G2/G3指令）"""
        try:
            cx, cy, rx, ry = item.get_params()
            
            # 应用定位点偏移
            offset_cx, offset_cy = self._apply_fiducial_offset((cx, cy), fiducial_offset)
            
            # 检查是否为正圆（允许微小误差）
            if abs(rx - ry) < 1e-4:
                logger.info(f"处理圆形: 圆心({offset_cx:.2f}, {offset_cy:.2f}), 半径 {rx:.2f}")
                # 圆形暂时仍然使用 G2/G3，不做封口和延时的几何修改
                self._generate_circle_gcode(offset_cx, offset_cy, rx)
            else:
                # 椭圆仍然作为多段线处理，因为标准G代码不支持椭圆指令
                logger.info(f"处理椭圆（转换为多段线）: rx={rx:.2f}, ry={ry:.2f}")
                # 手动生成椭圆点，不再依赖 item.points()
                import math
                steps = 128
                points = []
                for i in range(steps + 1):
                    angle = 2 * math.pi * i / steps
                    # 计算场景坐标（假设无旋转，如果有旋转需要更复杂的处理，这里简化处理）
                    # 注意：get_params 返回的是场景坐标下的 cx, cy 和缩放后的 rx, ry
                    # 但如果 item 有旋转，这里简单的参数化方程是不够的。
                    # 为了安全起见，我们还是尝试调用 item.points() 如果存在，否则使用简单近似
                    x = cx + rx * math.cos(angle)
                    y = cy + ry * math.sin(angle)
                    points.append((x, y))
                
                # 如果 item 确实有 points 方法（我们在 graphics_items.py 中保留了它但加了保护），可以使用
                if hasattr(item, 'points'):
                    try:
                        pts = item.points()
                        if pts: points = pts
                    except Exception:
                        pass

                if points and len(points) >= 2:
                    offset_points = [self._apply_fiducial_offset(pt, fiducial_offset) for pt in points]
                    self._process_polyline(offset_points, color_hex=color_hex)
                    
        except Exception as e:
            logger.error(f"处理椭圆项时出错: {e}")

    def _generate_circle_gcode(self, cx, cy, r):
        """生成圆形的G代码（使用G2/G3）"""
        # 移动到起点（圆的最右侧点）
        start_x = cx + r
        start_y = cy
        
        self.gcode_lines.append(f"G0 X{start_x:.3f} Y{start_y:.3f}")
        self.gcode_lines.append(f"M3 S{self.config.get('max_laser_power', 1000)}") # 激光开启
        
        # 使用G2（顺时针）或G3（逆时针）画圆
        # 这里使用G2画一个整圆，I为圆心相对于起点的X偏移，J为Y偏移
        # 起点是(cx+r, cy)，圆心是(cx, cy)
        # I = cx - start_x = cx - (cx + r) = -r
        # J = cy - start_y = cy - cy = 0
        
        # 注意：某些控制器不支持单条指令画整圆，可能需要分成两段半圆
        # 为了兼容性，我们分成两段半圆处理
        
        # 第一段：从右侧点(0度)到左侧点(180度)
        mid_x = cx - r
        mid_y = cy
        # I = -r, J = 0
        self.gcode_lines.append(f"G3 X{mid_x:.3f} Y{mid_y:.3f} I{-r:.3f} J0.000 F{self.config.get('feed_rate', 1000)}")
        
        # 第二段：从左侧点(180度)回到右侧点(0度)
        # I = r, J = 0
        self.gcode_lines.append(f"G3 X{start_x:.3f} Y{start_y:.3f} I{r:.3f} J0.000")
        
        self.gcode_lines.append("M5") # 激光关闭

    def _process_bitmap_item(self, item, fiducial_offset: Tuple[float, float]):
        """处理位图项（应用定位点偏移）"""
        try:
            if not isinstance(item, QGraphicsPixmapItem):
                return

            pixmap = item.pixmap()
            if pixmap.isNull():
                return

            logger.info("开始处理位图项（应用定位点偏移）")

            # 获取位图在场景中的边界框
            bounding_rect = item.sceneBoundingRect()
            if bounding_rect.isNull():
                logger.warning("无法获取位图边界框")
                return

            # 应用定位点偏移到边界框
            offset_x, offset_y = fiducial_offset
            offset_bounding_rect = bounding_rect.translated(-offset_x, -offset_y)

            # 方法1：首先尝试轮廓检测（生成连续路径）
            if self._try_contour_detection(pixmap, offset_bounding_rect):
                logger.info("轮廓检测成功")
                return

            # 方法2：如果轮廓检测失败，使用光栅扫描
            logger.info("轮廓检测失败，使用光栅扫描")
            self._raster_scan_bitmap(pixmap, offset_bounding_rect, fiducial_offset)

        except Exception as e:
            logger.error(f"位图处理失败: {e}")
            # 最终降级：生成边界框（应用偏移）
            self._process_bounding_box(offset_bounding_rect)

    def _try_contour_detection(self, pixmap: QPixmap, bounding_rect) -> bool:
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

            # 将QImage保存到内存缓冲（PNG），避免直接访问底层指针导致的崩溃
            ba = QByteArray()
            buf = QBuffer(ba)
            if not buf.open(QIODevice.WriteOnly):
                logger.warning("无法打开内存缓冲，跳过轮廓检测")
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
                logger.info("未找到轮廓")
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
                    self._process_polyline(path)
                return True

            return False

        except Exception as e:
            logger.warning(f"轮廓检测失败: {e}")
            return False

    def _raster_scan_bitmap(self, pixmap: QPixmap, bounding_rect, fiducial_offset: Tuple[float, float]):
        """光栅扫描位图（应用定位点偏移）"""
        try:
            # 安全地将QPixmap转换为PIL图像，避免直接访问底层指针
            from PyQt5.QtCore import QBuffer, QIODevice, QByteArray
            from io import BytesIO

            qimage = pixmap.toImage()
            if qimage.isNull():
                logger.warning("位图QImage为空，跳过光栅扫描")
                return

            ba = QByteArray()
            buf = QBuffer(ba)
            if not buf.open(QIODevice.WriteOnly):
                logger.warning("无法打开内存缓冲，跳过光栅扫描")
                return
            qimage.save(buf, 'PNG')
            buf.close()

            pil_image = Image.open(BytesIO(ba.data())).convert('L')

            # 计算缩放比例
            scale_x = bounding_rect.width() / pil_image.width
            scale_y = bounding_rect.height() / pil_image.height
            offset_x = bounding_rect.left()
            offset_y = bounding_rect.top()

            threshold = self.config['grayscale_threshold']
            scan_interval = self.config['scan_interval']
            min_segment_length = self.config['min_segment_length']

            # 计算行数（基于扫描间隔）
            pixel_step = max(1, int(scan_interval / scale_y))

            logger.info(f"开始光栅扫描，行步长: {pixel_step} 像素")

            path_count = 0
            total_points = 0

            for y in range(0, pil_image.height, pixel_step):
                # 收集当前行的有效点
                current_segment = []
                for x in range(pil_image.width):
                    gray = pil_image.getpixel((x, y))
                    if gray < threshold:  # 低于阈值才雕刻
                        real_x = offset_x + x * scale_x
                        real_y = offset_y + y * scale_y
                        current_segment.append((real_x, real_y))

                # 处理当前行的连续段
                if current_segment:
                    # 检查段长度是否足够
                    if self._calculate_segment_length(current_segment) >= min_segment_length:
                        self._process_raster_segment(current_segment)
                        path_count += 1
                        total_points += len(current_segment)

            logger.info(f"光栅扫描完成: {path_count} 条路径, {total_points} 个点")

        except Exception as e:
            logger.error(f"光栅扫描失败: {e}")
            raise

    def _process_raster_segment(self, points: List[Point]):
        """处理光栅扫描段（修复激光控制）"""
        if len(points) < 2:
            return

        # 移动到起点（快速移动，激光关闭）
        start_x, start_y = points[0]
        self._add_rapid_move(start_x, start_y)

        # 开启激光（整条路径保持开启）
        self._add_laser_on()

        # 连续移动到每个点
        for i in range(1, len(points)):
            x, y = points[i]
            self._add_linear_move(x, y)

        # 关闭激光（整条路径结束才关闭）
        self._add_laser_off()

    def _process_bounding_box(self, bounding_rect):
        """处理边界框（降级方案）"""
        points = [
            (bounding_rect.left(), bounding_rect.top()),
            (bounding_rect.right(), bounding_rect.top()),
            (bounding_rect.right(), bounding_rect.bottom()),
            (bounding_rect.left(), bounding_rect.bottom()),
            (bounding_rect.left(), bounding_rect.top())
        ]
        self._process_polyline(points)

    def _calculate_segment_length(self, points: List[Point]) -> float:
        """计算路径段长度"""
        if len(points) < 2:
            return 0.0

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
            "M00 (程序暂停)",
        ]
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


def export_to_nc(canvas,
                 filename: str,
                 config: dict = None,
                 allowed_colors: List[str] = None,
                 layer_params: Dict[str, Dict[str, Any]] = None) -> bool:
    """导出画布为NC文件（支持定位点）"""
    try:
        exporter = GCodeExporter()

        if config:
            exporter.set_config(config)

        if layer_params:
            exporter.set_layer_params(layer_params)

        gcode_lines = exporter.export_canvas(canvas, allowed_colors)

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
        'grayscale_threshold': 128,
        'dpi': 96.0,
        'min_segment_length': 0.5,
    }