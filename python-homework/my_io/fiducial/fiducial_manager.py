#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定位点管理器
负责定位点的创建、删除、显示和坐标转换
"""

import logging
from typing import Optional, Tuple
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainterPath, QPen, QColor
from PyQt5.QtWidgets import QGraphicsPathItem

logger = logging.getLogger(__name__)

# 类型定义
Point = Tuple[float, float]


class FiducialManager:
    """定位点管理器"""

    def __init__(self, canvas):
        self.canvas = canvas
        self._fiducial = None  # (point, shape)
        self._fiducial_item = None
        self._fiducial_size = 6.0

    def add_fiducial(self, point: Point, shape: str):
        """添加定位点"""
        self.remove_fiducial()
        self._fiducial = (point, shape)
        self._redraw_fiducial()
        logger.info(f"添加定位点: {point}, 形状: {shape}, 尺寸: {self._fiducial_size}")

    def remove_fiducial(self):
        """删除定位点"""
        if self._fiducial_item:
            self.canvas.scene.removeItem(self._fiducial_item)
            self._fiducial_item = None
        self._fiducial = None
        logger.info("已删除定位点")

    def get_fiducial(self) -> Optional[Tuple[Point, str]]:
        """获取当前定位点"""
        return self._fiducial

    def get_fiducial_point(self) -> Optional[Point]:
        """获取定位点坐标（如果没有定位点返回None）"""
        if self._fiducial:
            return self._fiducial[0]
        return None

    def set_fiducial_size(self, size: float):
        """设置定位点尺寸"""
        self._fiducial_size = size
        if self._fiducial:
            self._redraw_fiducial()

    def _redraw_fiducial(self):
        """重新绘制定位点"""
        if not self._fiducial:
            return

        point, shape = self._fiducial
        x, y = point
        size = self._fiducial_size

        path = QPainterPath()
        if shape == 'cross':
            # 绘制十字
            half = size / 2.0
            path.moveTo(x - half, y)
            path.lineTo(x + half, y)
            path.moveTo(x, y - half)
            path.lineTo(x, y + half)
        else:
            # 绘制圆形
            path.addEllipse(QPointF(x, y), size / 2, size / 2)

        self._fiducial_item = QGraphicsPathItem(path)
        pen = QPen(QColor(255, 0, 0), 0.5)  # 红色，线宽0.5
        pen.setCosmetic(True)  # 保持固定大小不受缩放影响
        self._fiducial_item.setPen(pen)

        # 设置高Z值确保定位点始终在最上层
        self._fiducial_item.setZValue(1000)
        self.canvas.scene.addItem(self._fiducial_item)

    def apply_offset_to_point(self, point: Point) -> Point:
        """对点应用定位点偏移"""
        fiducial_point = self.get_fiducial_point()
        if fiducial_point:
            offset_x, offset_y = fiducial_point
            x, y = point
            return (x - offset_x, y - offset_y)
        return point

    def apply_offset_to_path(self, path: list) -> list:
        """对路径应用定位点偏移"""
        fiducial_point = self.get_fiducial_point()
        if fiducial_point:
            offset_x, offset_y = fiducial_point
            return [(x - offset_x, y - offset_y) for x, y in path]
        return path

    def get_fiducial_item(self):
        """获取定位点图形项"""
        return self._fiducial_item