#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复版G代码导出模块 - 解决位图导出问题
"""

import logging
import os
from typing import List, Tuple, Optional
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem
from PyQt5.QtGui import QPixmap, QImage
import numpy as np
from PIL import Image
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

    def set_config(self, config: dict):
        """设置导出配置"""
        if config:
            self.config.update(config)

    def export_canvas(self, canvas) -> List[str]:
        """导出整个画布为G代码（支持定位点偏移）"""
        self.gcode_lines = []

        try:
            # 检查是否存在定位点
            fiducial_point = self._get_fiducial_offset(canvas)

            # 添加文件头
            self._add_header(fiducial_point)

            # 获取所有可导出项
            exportable_items = self._get_exportable_items(canvas)
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
        """获取定位点偏移量（如果存在定位点）"""
        try:
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
            logger.warning(f"获取定位点失败: {e}, 使用默认原点")
            return (0.0, 0.0)

    def _apply_fiducial_offset(self, point: Point, fiducial_offset: Tuple[float, float]) -> Point:
        """应用定位点偏移"""
        x, y = point
        offset_x, offset_y = fiducial_offset
        return (x - offset_x, y - offset_y)

    def _get_exportable_items(self, canvas) -> List[tuple]:
        """获取所有可导出项"""
        items = []

        try:
            for item in canvas.scene.items():
                # 排除系统项
                if self._is_system_item(item, canvas):
                    continue

                # 优先检查是否为椭圆/圆 (EditableEllipseItem)
                if EditableEllipseItem and isinstance(item, EditableEllipseItem):
                    items.append(('ellipse', item))
                    continue

                # 矢量路径项 (EditablePathItem 或其他具有 points 方法的项)
                if hasattr(item, 'points') and callable(getattr(item, 'points')):
                    try:
                        points = item.points()
                        if points and len(points) >= 2:
                            items.append(('vector', item))
                    except Exception as e:
                        logger.warning(f"获取矢量路径点时出错: {e}")

                # 位图项
                elif isinstance(item, QGraphicsPixmapItem):
                    if not item.pixmap().isNull():
                        items.append(('bitmap', item))

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
            item_type, item = item_data

            if item_type == 'vector':
                self._process_vector_item(item, fiducial_offset)
            elif item_type == 'ellipse':
                self._process_ellipse_item(item, fiducial_offset)
            elif item_type == 'bitmap':
                self._process_bitmap_item(item, fiducial_offset)

        except Exception as e:
            logger.error(f"处理{item_type}项时出错: {e}")

    def _process_vector_item(self, item, fiducial_offset: Tuple[float, float]):
        """处理矢量路径项（应用定位点偏移）"""
        try:
            points = item.points()
            if points and len(points) >= 2:
                # 应用定位点偏移
                offset_points = [self._apply_fiducial_offset(pt, fiducial_offset) for pt in points]
                logger.info(f"处理矢量路径，包含 {len(points)} 个点，应用定位点偏移")
                self._process_polyline(offset_points)
        except Exception as e:
            logger.error(f"处理矢量项时出错: {e}")

    def _process_ellipse_item(self, item, fiducial_offset: Tuple[float, float]):
        """处理椭圆/圆项（使用G2/G3指令）"""
        try:
            cx, cy, rx, ry = item.get_params()
            
            # 应用定位点偏移
            offset_cx, offset_cy = self._apply_fiducial_offset((cx, cy), fiducial_offset)
            
            # 检查是否为正圆（允许微小误差）
            if abs(rx - ry) < 1e-4:
                logger.info(f"处理圆形: 圆心({offset_cx:.2f}, {offset_cy:.2f}), 半径 {rx:.2f}")
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
                    self._process_polyline(offset_points)
                    
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

    def _process_polyline(self, points: List[Point]):
        """处理折线路径"""
        if len(points) < 2:
            return

        # 移动到起点
        start_x, start_y = points[0]
        self._add_rapid_move(start_x, start_y)

        # 开启激光
        self._add_laser_on()

        # 连续移动
        for i in range(1, len(points)):
            x, y = points[i]
            self._add_linear_move(x, y)

        # 关闭激光
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

    def _add_rapid_move(self, x: float, y: float):
        """快速移动"""
        line = f"G00 X{x:.3f} Y{y:.3f}"
        self.gcode_lines.append(line)
        self.current_x = x
        self.current_y = y

    def _add_linear_move(self, x: float, y: float):
        """线性移动"""
        line = f"G01 X{x:.3f} Y{y:.3f} F{self.config['feed_rate']}"
        self.gcode_lines.append(line)
        self.current_x = x
        self.current_y = y

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


def export_to_nc(canvas, filename: str, config: dict = None) -> bool:
    """导出画布为NC文件（支持定位点）"""
    try:
        exporter = GCodeExporter()

        if config:
            exporter.set_config(config)

        gcode_lines = exporter.export_canvas(canvas)

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