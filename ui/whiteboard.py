#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白板部件类（整合 GridCanvas）
实现白板的绘图、缩放、标尺、图形编辑、定位点等功能
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsScene,
                             QGraphicsView, QGraphicsPixmapItem, QGraphicsItem)
from PyQt5.QtCore import Qt, QPoint, QRect, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import (QPainter, QPen, QColor, QPixmap, QBrush, QFont,
                         QPainterPath, QWheelEvent, QTransform, QMouseEvent)
import math
from typing import List, Tuple, Optional

from edit.commands import AddItemCommand
from edit.edit_manager import EditManager
from my_io.gcode.gcode_exporter import Point

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 目标画布相关类定义
Pt = Tuple[float, float]
Path = List[Pt]


class EditablePathItem(QGraphicsPathItem):
    def __init__(self, pts: Path, color: QColor):
        super().__init__()
        self._points = pts[:]
        self._handles: List[QGraphicsEllipseItem] = []
        self._color = color
        self._update_path()
        self.setFlags(QGraphicsPathItem.ItemIsSelectable | QGraphicsPathItem.ItemIsMovable)

    def _update_path(self):
        path = QPainterPath()
        if self._points:
            path.moveTo(self._points[0][0], self._points[0][1])
            for (x, y) in self._points[1:]:
                path.lineTo(x, y)
        self.setPath(path)
        pen = QPen(self._color)
        pen.setCosmetic(True)
        pen.setWidthF(1.2)
        self.setPen(pen)

    def points(self) -> Path:
        return self._points[:]

    def set_points(self, pts: Path):
        self._points = pts[:]
        self._update_path()
        self._rebuild_handles()

    def enable_node_edit(self, on: bool):
        if on:
            self._rebuild_handles()
        else:
            self._clear_handles()

    def _clear_handles(self):
        for h in self._handles:
            s = h.scene()
            if s:
                s.removeItem(h)
        self._handles.clear()

    def _rebuild_handles(self):
        self._clear_handles()
        if not self._points:
            return
        for idx, (x, y) in enumerate(self._points):
            h = _DragHandle(self, idx, x, y)
            self._handles.append(h)

    def update_point(self, idx: int, x: float, y: float):
        if 0 <= idx < len(self._points):
            self._points[idx] = (x, y)
            self._update_path()


class _DragHandle(QGraphicsEllipseItem):
    def __init__(self, owner: EditablePathItem, idx: int, x: float, y: float):
        r = 3.5
        super().__init__(x - r, y - r, 2 * r, 2 * r)
        self._owner = owner
        self._idx = idx
        pen = QPen(QColor(0, 120, 255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(0, 120, 255, 120)))
        self.setZValue(10)
        self.setFlags(QGraphicsEllipseItem.ItemIsMovable | QGraphicsEllipseItem.ItemIsSelectable)
        self.setCursor(Qt.OpenHandCursor)
        owner.scene().addItem(self)

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        pos = self.rect().center() + self.pos()
        self._owner.update_point(self._idx, pos.x(), pos.y())


class GridCanvas(QGraphicsView):
    headMoved = pyqtSignal(float, float)
    view_changed = pyqtSignal(float, QPoint)  # 缩放比例、偏移量信号（用于标尺联动）

    class Tool:
        SELECT = 0
        PAN = 1
        DRAW_POLY = 2
        DRAW_RECT = 3
        DRAW_CIRCLE = 4
        EDIT_NODES = 5
        ADD_FID_CROSS = 6
        ADD_FID_CIRCLE = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor(245, 245, 245))
        self.scale(1, -1)  # Y轴翻转（适配图像坐标）
        self.setMouseTracking(True)
        self._last_img_item = None
        self._bitmap_count = 0
        self._work_w = 600.0
        self._work_h = 400.0
        self._draw_workarea()
        self._tool = self.Tool.SELECT
        self._drawing_pts: Path = []
        self._drawing_tmp: Optional[QGraphicsPathItem] = None

        # 定位点相关属性 - 使用新的管理器
        from my_io.fiducial.fiducial_manager import FiducialManager
        self.fiducial_manager = FiducialManager(self)

        # -------------------------- 新增：初始化编辑管理器 --------------------------
        self.edit_manager = EditManager(self)
        # 连接场景的选中状态变化信号 → 通知EditManager更新可用性
        self.scene.selectionChanged.connect(self._on_selection_changed)

    # -------------------------- 新增：选中状态变化处理 --------------------------
    def _on_selection_changed(self):
        """当画布选中项变化时，通知EditManager"""
        has_selection = len(self.get_selected_items()) > 0
        self.edit_manager.set_has_selection(has_selection)

    # -------------------------- 新增：供EditManager调用的接口 --------------------------
    def get_selected_items(self) -> List[QGraphicsItem]:
        """获取所有选中的图形项（排除定位点和工作区网格）"""
        exclude_items = [self._work_item]

        # 使用新的 FiducialManager 获取定位点项
        if hasattr(self, 'fiducial_manager'):
            fiducial_item = self.fiducial_manager.get_fiducial_item()
            if fiducial_item:
                exclude_items.append(fiducial_item)

        return [
            item for item in self.scene.selectedItems()
            if item not in exclude_items  # 不处理网格和定位点
               and isinstance(item, (EditablePathItem, QGraphicsPixmapItem))  # 只处理图形和图片
        ]

    def select_all_items(self):
        """全选所有图形项（排除定位点和工作区网格）"""
        exclude_items = [self._work_item]

        # 使用新的 FiducialManager 获取定位点项
        if hasattr(self, 'fiducial_manager'):
            fiducial_item = self.fiducial_manager.get_fiducial_item()
            if fiducial_item:
                exclude_items.append(fiducial_item)

        for item in self.scene.items():
            if item not in exclude_items and isinstance(item, (EditablePathItem, QGraphicsPixmapItem)):
                item.setSelected(True)

    # --- 定位点相关方法（更新为使用命令模式）---
    def set_fiducial_size(self, size: float):
        self.fiducial_manager.set_fiducial_size(size)

    def add_fiducial(self, point: Point, shape: str):
        """添加定位点（使用命令模式）"""
        from edit.commands import AddFiducialCommand
        cmd = AddFiducialCommand(self, point, shape)
        self.edit_manager.push_undo(cmd)
        cmd.redo()  # 执行添加操作

    def remove_fiducial(self):
        """删除定位点（使用命令模式）"""
        from edit.commands import RemoveFiducialCommand
        if self.fiducial_manager.get_fiducial():
            cmd = RemoveFiducialCommand(self)
            self.edit_manager.push_undo(cmd)
            cmd.redo()  # 执行删除操作

    def get_fiducial(self) -> Optional[Tuple[Point, str]]:
        return self.fiducial_manager.get_fiducial()

    # --- 缩放/平移相关 ---
    def wheelEvent(self, e: QWheelEvent):
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        # 发送视图变化信号（用于标尺联动）
        self._emit_view_changed()

    def _emit_view_changed(self):
        """发送视图变化信号（缩放比例、偏移量）"""
        zoom = self.transform().m11()  # 获取X轴缩放比例（与Y轴一致）
        # 计算场景偏移（视图左上角对应的场景坐标）
        view_rect = self.viewport().rect()
        scene_top_left = self.mapToScene(view_rect.topLeft())
        # 转换为屏幕偏移量（适配标尺坐标）
        offset = QPoint(int(-scene_top_left.x() * zoom), int(-scene_top_left.y() * zoom))
        self.view_changed.emit(zoom, offset)

    def set_tool(self, t: int):
        self._tool = t
        if t == self.Tool.EDIT_NODES:
            for it in self.selected_paths():
                it.enable_node_edit(True)
        else:
            for it in self.all_paths():
                it.enable_node_edit(False)
        self.setDragMode(QGraphicsView.ScrollHandDrag if t == self.Tool.PAN else QGraphicsView.RubberBandDrag)

    def _draw_workarea(self):
        pen = QPen(QColor(200, 200, 200))
        pen.setCosmetic(True)
        rect = QRectF(0, 0, self._work_w, self._work_h)
        self._work_item = self.scene.addRect(rect, pen)
        step = 10.0
        thin = QPen(QColor(220, 220, 220))
        thin.setCosmetic(True)
        thick = QPen(QColor(200, 200, 200))
        thick.setCosmetic(True)
        thick.setWidth(0)
        for x in range(0, int(self._work_w) + 1, int(step)):
            pen = thick if x % 50 == 0 else thin
            self.scene.addLine(x, 0, x, self._work_h, pen)
        for y in range(0, int(self._work_h) + 1, int(step)):
            pen = thick if y % 50 == 0 else thin
            self.scene.addLine(0, y, self._work_w, y, pen)

    # -------------------------- 修改：图形添加方法（使用EditablePathItem + 命令模式） --------------------------
    def add_polyline(self, points, color):
        logger.info(f"画布添加折线：{len(points)}个点，颜色={color.getRgb()}")
        # 替换为可编辑路径项（支持选中、节点编辑）
        item = EditablePathItem(points, color)
        self.scene.addItem(item)

        # 创建"添加图形"命令，压入撤销栈
        cmd = AddItemCommand(self, item)
        self.edit_manager.push_undo(cmd)

        return item

    def add_rect(self, x: float, y: float, w: float, h: float, color: QColor = QColor(0, 0, 0)):
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        return self.add_polyline(pts, color)

    def add_circle(self, cx: float, cy: float, r: float, steps: int = 64, color: QColor = QColor(0, 0, 0)):
        pts = [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps)) for i in
               range(steps + 1)]
        return self.add_polyline(pts, color)

    # -------------------------- 修改：添加图片方法（支持选中 + 命令模式） --------------------------
    def add_image(self, qpixmap: QPixmap, x: float = 0.0, y: float = 0.0):
        # ========== 1. 计算图片尺寸和缩放比例 ==========
        # 获取工作区域尺寸
        work_area_width = self._work_w
        work_area_height = self._work_h

        # 计算图片原始尺寸（毫米）
        pixel_to_mm = 25.4 / 96.0  # 96dpi → 毫米的换算系数
        img_width_mm = qpixmap.width() * pixel_to_mm
        img_height_mm = qpixmap.height() * pixel_to_mm

        # 计算缩放比例，使图片适应工作区域但不超过100%
        # 使用较小的边距，让图片更大
        MARGIN = 5.0  # 减少边距
        max_width = work_area_width - 2 * MARGIN
        max_height = work_area_height - 2 * MARGIN

        # 确保图片不会太小，但也不要超过原始尺寸
        scale_ratio = min(max_width / img_width_mm, max_height / img_height_mm, 1.0)

        # 如果图片很小，可以适当放大
        if img_width_mm * scale_ratio < 50 and img_height_mm * scale_ratio < 50:
            # 小图片适当放大
            scale_ratio = min(100 / img_width_mm, 100 / img_height_mm, 2.0)  # 最大放大2倍

        # 计算缩放后的尺寸
        new_width_mm = img_width_mm * scale_ratio
        new_height_mm = img_height_mm * scale_ratio
        new_width_px = int(qpixmap.width() * scale_ratio)
        new_height_px = int(qpixmap.height() * scale_ratio)

        # 缩放图片
        scaled_pixmap = qpixmap.scaled(new_width_px, new_height_px,
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # ========== 2. 计算精确的居中位置 ==========
        # 使用场景的中心点而不是工作区域的中心点
        scene_center_x = self.scene.sceneRect().center().x()
        scene_center_y = self.scene.sceneRect().center().y()

        # 如果场景矩形无效，使用工作区域中心
        if scene_center_x == 0 and scene_center_y == 0:
            scene_center_x = work_area_width / 2
            scene_center_y = work_area_height / 2

        # 计算图片左上角的位置（使图片在场景中央）
        img_x = scene_center_x - new_width_mm / 2
        img_y = scene_center_y - new_height_mm / 2

        # ========== 3. 添加图片到画布 ==========
        item = QGraphicsPixmapItem(scaled_pixmap)

        # 设置图片位置（精确居中）
        item.setPos(img_x, img_y)
        item.setOffset(0, 0)  # 偏移量为0，位置已通过setPos设置

        item.setTransformationMode(Qt.SmoothTransformation)
        item.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
        item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)

        # 应用缩放转换（像素到毫米）
        s = 25.4 / 96.0  # 96dpi → 毫米的缩放系数
        item.setTransform(QTransform().scale(s, -s))  # Y轴翻转适配Qt坐标系统

        self.scene.addItem(item)

        # ========== 4. 调整视图以确保图片完全居中显示 ==========
        # 计算图片的场景边界框
        img_scene_rect = item.sceneBoundingRect()

        # 扩展场景矩形以包含新图片，但不强制保留边框
        current_scene_rect = self.scene.sceneRect()

        # 计算新的场景矩形（包含所有内容的最小矩形）
        if current_scene_rect.isNull() or current_scene_rect.width() == 0:
            # 如果当前场景矩形无效，使用图片矩形
            new_scene_rect = img_scene_rect
        else:
            # 合并当前场景矩形和图片矩形
            new_scene_rect = current_scene_rect.united(img_scene_rect)

        # 添加很小的边距，避免贴边
        SMALL_MARGIN = 2.0
        new_scene_rect_adjusted = new_scene_rect.adjusted(
            -SMALL_MARGIN, -SMALL_MARGIN, SMALL_MARGIN, SMALL_MARGIN
        )

        # 设置新的场景矩形
        self.scene.setSceneRect(new_scene_rect_adjusted)

        # 适配视图以显示所有内容，但不保留边框
        # 使用图片的边界框来适配视图，确保图片完全可见
        self.fitInView(img_scene_rect, Qt.KeepAspectRatio)

        # 发送视图变化信号更新标尺
        self._emit_view_changed()

        # ========== 5. 添加到撤销栈 ==========
        cmd = AddItemCommand(self, item)
        self.edit_manager.push_undo(cmd)

        self._last_img_item = item
        self._bitmap_count += 1

        logger.info(f"图片已添加并居中，位置: ({img_x:.2f}, {img_y:.2f})，尺寸: {new_width_mm:.2f}×{new_height_mm:.2f}mm")
        logger.info(f"缩放比例: {scale_ratio:.3f}")

        return item

    def all_paths(self) -> List[EditablePathItem]:
        return [it for it in self.scene.items() if isinstance(it, EditablePathItem)]

    def selected_paths(self) -> List[EditablePathItem]:
        return [it for it in self.scene.selectedItems() if isinstance(it, EditablePathItem)]

    def fit_all(self):
        logger.info("执行fit_all：调整视图至所有内容可见")
        items = self.scene.items()
        if not items:
            return
        bounding_rect = self.scene.itemsBoundingRect()
        self.setSceneRect(bounding_rect)
        self.fitInView(bounding_rect, Qt.KeepAspectRatio)
        self._emit_view_changed()  # 同步标尺

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = self.mapToScene(e.pos())
        self.headMoved.emit(pos.x(), pos.y())
        if self._tool in (self.Tool.DRAW_POLY, self.Tool.DRAW_RECT, self.Tool.DRAW_CIRCLE) and self._drawing_pts:
            if self._drawing_tmp:
                self.scene.removeItem(self._drawing_tmp)
                self._drawing_tmp = None
            path = QPainterPath()
            if self._tool == self.Tool.DRAW_POLY:
                path.moveTo(self._drawing_pts[0][0], self._drawing_pts[0][1])
                path.lineTo(pos.x(), pos.y())
            elif self._tool == self.Tool.DRAW_RECT:
                x0, y0 = self._drawing_pts[0]
                path.addRect(min(x0, pos.x()), min(y0, pos.y()), abs(pos.x() - x0), abs(pos.y() - y0))
            elif self._tool == self.Tool.DRAW_CIRCLE:
                x0, y0 = self._drawing_pts[0]
                r = ((pos.x() - x0) ** 2 + (pos.y() - y0) ** 2) ** 0.5
                rect = QRectF(x0 - r, y0 - r, 2 * r, 2 * r)
                path.addEllipse(rect)
            self._drawing_tmp = QGraphicsPathItem(path)
            pen = QPen(QColor(0, 150, 0))
            pen.setCosmetic(True)
            pen.setStyle(Qt.DashLine)
            self._drawing_tmp.setPen(pen)
            self.scene.addItem(self._drawing_tmp)
        # 平移时发送视图变化信号
        if self._tool == self.Tool.PAN and self.dragMode() == QGraphicsView.ScrollHandDrag:
            self._emit_view_changed()
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        pos = self.mapToScene(e.pos())
        if self._tool == self.Tool.DRAW_POLY:
            if not self._drawing_pts:
                self._drawing_pts = [(pos.x(), pos.y())]
            else:
                self._drawing_pts.append((pos.x(), pos.y()))
        elif self._tool in (self.Tool.DRAW_RECT, self.Tool.DRAW_CIRCLE):
            self._drawing_pts = [(pos.x(), pos.y())]
        elif self._tool in (self.Tool.ADD_FID_CROSS, self.Tool.ADD_FID_CIRCLE):
            shape = 'cross' if self._tool == self.Tool.ADD_FID_CROSS else 'circle'

            # +++ 修改：使用命令模式添加定位点 +++
            from edit.commands import AddFiducialCommand
            cmd = AddFiducialCommand(self, (pos.x(), pos.y()), shape)
            self.edit_manager.push_undo(cmd)
            cmd.redo()  # 执行添加操作

            # 自动退出定位点模式，回到选择模式
            self.set_tool(self.Tool.SELECT)
            # 发送状态更新信号（如果主窗口有监听）
            if hasattr(self, 'toolChanged'):
                self.toolChanged.emit(self.Tool.SELECT)
            # +++ 结束新增 +++
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        pos = self.mapToScene(e.pos())
        if self._tool == self.Tool.DRAW_POLY:
            if e.button() == Qt.RightButton and len(self._drawing_pts) >= 2:
                pts = self._drawing_pts[:]
                self._drawing_pts = []
                if self._drawing_tmp:
                    self.scene.removeItem(self._drawing_tmp)
                    self._drawing_tmp = None
                self.add_polyline(pts, QColor(0, 0, 0))
        elif self._tool == self.Tool.DRAW_RECT:
            if self._drawing_pts:
                x0, y0 = self._drawing_pts[0]
                self._drawing_pts = []
                if self._drawing_tmp:
                    self.scene.removeItem(self._drawing_tmp)
                    self._drawing_tmp = None
                w = pos.x() - x0
                h = pos.y() - y0
                self.add_rect(x0, y0, w, h)
        elif self._tool == self.Tool.DRAW_CIRCLE:
            if self._drawing_pts:
                x0, y0 = self._drawing_pts[0]
                self._drawing_pts = []
                if self._drawing_tmp:
                    self.scene.removeItem(self._drawing_tmp)
                    self._drawing_tmp = None
                r = ((pos.x() - x0) ** 2 + (pos.y() - y0) ** 2) ** 0.5
                self.add_circle(x0, y0, r)
        else:
            super().mouseReleaseEvent(e)

    def last_image_item(self):
        return self._last_img_item

    def image_origin_mm(self):
        it = self._last_img_item
        if it is None:
            return 0.0, 0.0
        br = it.boundingRect()
        pt = it.mapToScene(br.bottomLeft())
        return float(pt.x()), float(pt.y())

    # --- 适配原CanvasWidget的方法 ---
    def zoom_in(self):
        """放大（适配原接口）"""
        self.scale(1.15, 1.15)
        self._emit_view_changed()

    def zoom_out(self):
        """缩小（适配原接口）"""
        self.scale(1 / 1.15, 1 / 1.15)
        self._emit_view_changed()

    def zoom_reset(self):
        """重置缩放（适配原接口）"""
        self.resetTransform()
        self.scale(1, -1)  # 恢复Y轴翻转
        self._emit_view_changed()

    def get_zoom_percent(self):
        """获取缩放百分比（适配原接口）"""
        return int(self.transform().m11() * 100)

    def clear(self):
        """清空画布（适配原接口）"""
        self.scene.clear()
        self._draw_workarea()  # 重新绘制工作区网格
        self._last_img_item = None
        self._bitmap_count = 0
        self._drawing_pts = []
        self.remove_fiducial()
        self._emit_view_changed()

    def export_image(self, filename):
        """导出图像（适配原接口）"""
        # 获取场景所有内容的边界框
        items = self.scene.items()
        if not items:
            logger.warning("画布无内容，无法导出")
            return
        bounding_rect = self.scene.itemsBoundingRect()
        # 创建图像（考虑Y轴翻转）
        image = QPixmap(int(bounding_rect.width()), int(bounding_rect.height()))
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        # 平移并翻转Y轴，确保内容正确绘制
        painter.translate(-bounding_rect.x(), bounding_rect.bottom())
        painter.scale(1, -1)
        self.scene.render(painter, source=bounding_rect)
        painter.end()
        image.save(filename)
        logger.info(f"图像已导出至：{filename}")

    # --- 新增：定位点操作扩展 ---
    def set_pen_color(self, color: QColor):
        """设置绘图颜色（适配原接口，用于后续绘图工具）"""
        self._draw_color = color

    def set_pen_width(self, width: float):
        """设置线条宽度（适配原接口）"""
        self._pen_width = width


# --- 原有标尺部件保持不变 ---
class RulerWidget(QWidget):
    """标尺部件"""

    def __init__(self, orientation='horizontal', parent=None):
        super().__init__(parent)
        self.orientation = orientation
        self.zoom = 1.0
        self.offset = 0

        if orientation == 'horizontal':
            self.setFixedHeight(30)
            self.setMinimumWidth(100)
        else:
            self.setFixedWidth(30)
            self.setMinimumHeight(100)

        self.setStyleSheet("background-color: #f0f0f0;")

    def set_zoom(self, zoom):
        """设置缩放比例"""
        self.zoom = zoom
        self.update()

    def set_offset(self, offset):
        """设置偏移量"""
        self.offset = offset
        self.update()

    def paintEvent(self, event):
        """绘制标尺"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景
        painter.fillRect(self.rect(), QColor(240, 240, 240))

        # 设置字体
        font = QFont('Arial', 8)
        painter.setFont(font)
        painter.setPen(QColor(80, 80, 80))

        if self.orientation == 'horizontal':
            self._draw_horizontal_ruler(painter)
        else:
            self._draw_vertical_ruler(painter)

    def _draw_horizontal_ruler(self, painter):
        """绘制水平标尺"""
        width = self.width()
        height = self.height()

        base_interval = 50  # 基础间隔（像素）
        screen_interval = base_interval * self.zoom

        # 动态调整基础间隔
        if screen_interval < 30:
            multiplier = math.ceil(30 / screen_interval)
            base_interval *= multiplier
            screen_interval = base_interval * self.zoom
        elif screen_interval > 150:
            multiplier = math.ceil(screen_interval / 100)
            base_interval /= multiplier
            screen_interval = base_interval * self.zoom

        # 计算第一个刻度位置
        canvas_start = -self.offset / self.zoom if self.zoom > 0 else 0
        first_tick = math.floor(canvas_start / base_interval) * base_interval

        # 绘制刻度
        tick_value = first_tick
        while True:
            screen_x = tick_value * self.zoom + self.offset
            if screen_x > width:
                break
            if screen_x >= 0:
                # 主刻度线
                painter.drawLine(int(screen_x), height - 10, int(screen_x), height)
                # 标签
                label = str(int(tick_value))
                painter.drawText(int(screen_x) + 2, height - 15, label)
                # 次刻度
                for i in range(1, 5):
                    sub_tick = tick_value + base_interval * i / 5
                    sub_screen_x = sub_tick * self.zoom + self.offset
                    if 0 <= sub_screen_x <= width:
                        tick_height = 5 if i == 2 else 3
                        painter.drawLine(int(sub_screen_x), height - tick_height,
                                         int(sub_screen_x), height)
            tick_value += base_interval

    def _draw_vertical_ruler(self, painter):
        """绘制垂直标尺"""
        width = self.width()
        height = self.height()

        base_interval = 50  # 基础间隔（像素）
        screen_interval = base_interval * self.zoom

        # 动态调整基础间隔
        if screen_interval < 30:
            multiplier = math.ceil(30 / screen_interval)
            base_interval *= multiplier
            screen_interval = base_interval * self.zoom
        elif screen_interval > 150:
            multiplier = math.ceil(screen_interval / 100)
            base_interval /= multiplier
            screen_interval = base_interval * self.zoom

        # 计算第一个刻度位置（适配GridCanvas的Y轴翻转）
        canvas_start = -self.offset / self.zoom if self.zoom > 0 else 0
        first_tick = math.floor(canvas_start / base_interval) * base_interval

        # 绘制刻度
        tick_value = first_tick
        while True:
            screen_y = tick_value * self.zoom + self.offset
            if screen_y > height:
                break
            if screen_y >= 0:
                # 主刻度线
                painter.drawLine(width - 10, int(screen_y), width, int(screen_y))
                # 标签（旋转90度）
                painter.save()
                painter.translate(width - 15, int(screen_y) - 2)
                painter.rotate(-90)
                label = str(int(tick_value))
                painter.drawText(0, 0, label)
                painter.restore()
                # 次刻度
                for i in range(1, 5):
                    sub_tick = tick_value + base_interval * i / 5
                    sub_screen_y = sub_tick * self.zoom + self.offset
                    if 0 <= sub_screen_y <= height:
                        tick_width = 5 if i == 2 else 3
                        painter.drawLine(width - tick_width, int(sub_screen_y),
                                         width, int(sub_screen_y))
            tick_value += base_interval


# --- 整合GridCanvas的白板主部件 ---
class WhiteboardWidget(QWidget):
    """白板部件（包含标尺和GridCanvas）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        # 创建布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 水平布局（包含垂直标尺和画布）
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # 创建标尺
        self.h_ruler = RulerWidget('horizontal')
        self.v_ruler = RulerWidget('vertical')

        # 创建目标画布（GridCanvas）
        self.canvas = GridCanvas()

        # 连接信号（画布视图变化 -> 标尺更新）
        self.canvas.view_changed.connect(self.on_view_changed)

        # 角落占位符
        corner = QWidget()
        corner.setFixedSize(30, 30)
        corner.setStyleSheet("background-color: #f0f0f0;")

        # 布局组装
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(corner)
        top_layout.addWidget(self.h_ruler)

        h_layout.addWidget(self.v_ruler)
        h_layout.addWidget(self.canvas)

        main_layout.addLayout(top_layout)
        main_layout.addLayout(h_layout)

        # 初始化视图信号
        self.canvas._emit_view_changed()

    def on_view_changed(self, zoom, offset):
        """画布视图变化时更新标尺"""
        self.h_ruler.set_zoom(zoom)
        self.v_ruler.set_zoom(zoom)
        self.h_ruler.set_offset(offset.x())
        self.v_ruler.set_offset(offset.y())

    # --- 转发画布方法（保持原接口兼容） ---
    def set_tool(self, tool):
        """设置工具（传入GridCanvas.Tool常量）"""
        self.canvas.set_tool(tool)

    def set_pen_color(self, color):
        self.canvas.set_pen_color(color)

    def set_pen_width(self, width):
        self.canvas.set_pen_width(width)

    def clear(self):
        self.canvas.clear()

        # -------------------------- 修改：撤销/重做/剪切/复制/粘贴/删除/全选 方法 --------------------------

    def undo(self):
        """撤销（转发给EditManager）"""
        self.canvas.edit_manager.undo()
        logger.info("执行撤销操作")

    def redo(self):
        """重做（转发给EditManager）"""
        self.canvas.edit_manager.redo()
        logger.info("执行重做操作")

    def cut(self):
        """剪切（转发给EditManager）"""
        self.canvas.edit_manager.cut()
        logger.info("执行剪切操作")

    def copy(self):
        """复制（转发给EditManager）"""
        self.canvas.edit_manager.copy()
        logger.info("执行复制操作")

    def paste(self):
        """粘贴（转发给EditManager）"""
        self.canvas.edit_manager.paste()
        logger.info("执行粘贴操作")

    def delete(self):
        """删除（转发给EditManager）"""
        self.canvas.edit_manager.delete()
        logger.info("执行删除操作")

    def select_all(self):
        """全选（转发给EditManager）"""
        self.canvas.edit_manager.select_all()
        logger.info("执行全选操作")

    def zoom_in(self):
        self.canvas.zoom_in()

    def zoom_out(self):
        self.canvas.zoom_out()

    def zoom_reset(self):
        self.canvas.zoom_reset()

    def get_zoom_percent(self):
        return self.canvas.get_zoom_percent()

    def export_image(self, filename):
        self.canvas.export_image(filename)

    # --- GridCanvas扩展功能转发 ---
    def add_fiducial(self, point: Pt, shape: str):
        """添加定位点（shape: 'cross' 或 'circle'）"""
        self.canvas.add_fiducial(point, shape)

    def remove_fiducial(self):
        """删除定位点"""
        self.canvas.remove_fiducial()

    def set_fiducial_size(self, size: float):
        """设置定位点尺寸"""
        self.canvas.set_fiducial_size(size)

    def fit_all(self):
        """适配所有内容到视图"""
        self.canvas.fit_all()