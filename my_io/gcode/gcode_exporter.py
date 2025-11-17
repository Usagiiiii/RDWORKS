#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G代码导出模块
将画布中的图形转换为G代码（NC文件）
"""

import logging
import os
from typing import List, Tuple
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem

logger = logging.getLogger(__name__)

# 类型定义
Point = Tuple[float, float]  # (x, y) 坐标点
Path = List[Point]  # 路径，由多个点组成


class GCodeExporter:
    """G代码导出器"""

    def __init__(self):
        self.gcode_lines = []
        self.current_x = 0.0
        self.current_y = 0.0
        self.laser_on = False

        # G代码配置参数
        self.config = {
            'feed_rate': 1000,  # 进给速度 mm/min
            'laser_power': 255,  # 激光功率 (0-255)
            'rapid_move_rate': 3000,  # 快速移动速度
            'units': 'G21',  # 毫米单位
            'absolute_positioning': 'G90',  # 绝对坐标
        }

    def set_config(self, config: dict):
        """设置导出配置"""
        self.config.update(config)

    def export_canvas(self, canvas) -> List[str]:
        """
        导出整个画布为G代码

        Args:
            canvas: 画布对象，包含图形项

        Returns:
            G代码行列表
        """
        self.gcode_lines = []

        # 添加文件头
        self._add_header()

        # 获取画布中的所有路径项
        path_items = self._get_path_items(canvas)

        if not path_items:
            logger.warning("画布中没有可导出的路径")
            self._add_no_content_warning()
        else:
            # 处理每个路径项
            for item in path_items:
                self._process_path_item(item)

        # 添加文件尾
        self._add_footer()

        return self.gcode_lines

    def _get_path_items(self, canvas) -> List[QGraphicsItem]:
        """获取画布中所有的可导出项（包括矢量和位图）"""
        from PyQt5.QtWidgets import QGraphicsPixmapItem

        path_items = []

        for item in canvas.scene.items():
            # 排除工作区网格等系统项
            if hasattr(canvas, '_work_item') and item == canvas._work_item:
                continue
            if hasattr(canvas, '_fiducial_item') and item == canvas._fiducial_item:
                continue

            # 矢量路径项
            if hasattr(item, '_points') and hasattr(item, 'points'):
                path_items.append(item)

            # 位图项
            elif isinstance(item, QGraphicsPixmapItem):
                path_items.append(item)

        logger.info(f"找到 {len(path_items)} 个可导出的项目")
        return path_items

    def _process_image_item(self, item):
        """处理位图项 - 将图片转换为边界框路径"""
        try:
            if not isinstance(item, QGraphicsPixmapItem):
                return

            # 获取图片的边界框
            bounding_rect = item.sceneBoundingRect()
            if bounding_rect.isNull():
                return

            logger.info(f"处理图片项，边界框: {bounding_rect}")

            # 将图片矩形转换为路径点（毫米单位）
            points = [
                (bounding_rect.left(), bounding_rect.top()),
                (bounding_rect.right(), bounding_rect.top()),
                (bounding_rect.right(), bounding_rect.bottom()),
                (bounding_rect.left(), bounding_rect.bottom()),
                (bounding_rect.left(), bounding_rect.top())  # 闭合
            ]

            # 处理矩形路径
            self._process_polyline(points)

        except Exception as e:
            logger.error(f"处理图片项时出错: {e}")

    def _process_path_item(self, item):
        """处理单个路径项（支持矢量和位图）"""
        try:
            # 处理矢量路径
            if hasattr(item, 'points'):
                points = item.points()
                if len(points) >= 2:
                    self._process_polyline(points)

            # 处理位图
            elif isinstance(item, QGraphicsPixmapItem):
                self._process_image_item(item)

        except Exception as e:
            logger.error(f"处理路径项时出错: {e}")

    def _process_polyline(self, points: List[Point]):
        """处理折线路径"""
        if len(points) < 2:
            return

        # 移动到路径起点（快速移动，激光关闭）
        start_x, start_y = points[0]
        self._add_rapid_move(start_x, start_y)

        # 开启激光
        self._add_laser_on()

        # 按顺序移动到每个点（切削移动）
        for i in range(1, len(points)):
            x, y = points[i]
            self._add_linear_move(x, y)

        # 关闭激光
        self._add_laser_off()

    def _add_header(self):
        """添加G代码文件头"""
        header = [
            "%",  # 文件开始标记
            "O1000",  # 程序号
            f"{self.config['units']}",  # 毫米单位
            f"{self.config['absolute_positioning']}",  # 绝对坐标
            "G17",  # XY平面选择
            "G40",  # 取消刀具半径补偿
            "G49",  # 取消刀具长度补偿
            "G80",  # 取消固定循环
            "G54",  # 工作坐标系
            "",  # 空行
            "M05",  # 确保激光关闭
            "G00 Z10",  # 快速移动到安全高度
            "",  # 空行
        ]
        self.gcode_lines.extend(header)

    def _add_footer(self):
        """添加G代码文件尾"""
        footer = [
            "",  # 空行
            "M05",  # 关闭激光
            "G00 Z10",  # 移动到安全高度
            "G00 X0 Y0",  # 回到原点
            "M30",  # 程序结束
            "%",  # 文件结束标记
        ]
        self.gcode_lines.extend(footer)

    def _add_no_content_warning(self):
        """添加无内容警告"""
        warning = [
            "(警告: 没有找到可导出的图形)",
            "(WARNING: No exportable graphics found)",
            "M00",  # 程序暂停
        ]
        self.gcode_lines.extend(warning)

    def _add_rapid_move(self, x: float, y: float):
        """添加快速移动指令"""
        line = f"G00 X{x:.3f} Y{y:.3f}"
        self.gcode_lines.append(line)
        self.current_x = x
        self.current_y = y

    def _add_linear_move(self, x: float, y: float):
        """添加线性移动指令（切削移动）"""
        line = f"G01 X{x:.3f} Y{y:.3f} F{self.config['feed_rate']}"
        self.gcode_lines.append(line)
        self.current_x = x
        self.current_y = y

    def _add_laser_on(self):
        """开启激光"""
        if not self.laser_on:
            self.gcode_lines.append(f"M03 S{self.config['laser_power']}")  # 开启激光
            self.laser_on = True

    def _add_laser_off(self):
        """关闭激光"""
        if self.laser_on:
            self.gcode_lines.append("M05")  # 关闭激光
            self.laser_on = False


def export_to_nc(canvas, filename: str, config: dict = None) -> bool:
    """
    导出画布为NC文件

    Args:
        canvas: 画布对象
        filename: 输出文件名
        config: 导出配置

    Returns:
        bool: 导出是否成功
    """
    try:
        exporter = GCodeExporter()

        if config:
            exporter.set_config(config)

        # 生成G代码
        gcode_lines = exporter.export_canvas(canvas)

        # 写入文件
        with open(filename, 'w', encoding='utf-8') as f:
            for line in gcode_lines:
                f.write(line + '\n')

        logger.info(f"成功导出G代码到: {filename}")
        logger.info(f"生成 {len(gcode_lines)} 行G代码")

        return True

    except Exception as e:
        logger.error(f"导出G代码失败: {e}")
        return False


def get_default_config() -> dict:
    """获取默认的导出配置"""
    return {
        'feed_rate': 1000,  # 进给速度 mm/min
        'laser_power': 255,  # 激光功率 (0-255)
        'rapid_move_rate': 3000,  # 快速移动速度
        'units': 'G21',  # 毫米单位
        'absolute_positioning': 'G90',  # 绝对坐标
    }