#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白板部件类（整合 GridCanvas）
实现白板的绘图、缩放、标尺、图形编辑、定位点等功能
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsScene,
                             QGraphicsView, QGraphicsPixmapItem)
from PyQt5.QtCore import Qt, QPoint, QRect, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import (QPainter, QPen, QColor, QPixmap, QBrush, QFont,
                         QPainterPath, QWheelEvent, QTransform, QMouseEvent)
import math
from typing import List, Tuple, Optional

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

        # 定位点相关属性
        self._fiducial: Optional[Tuple[Pt, str]] = None
        self._fiducial_item = None
        self._fiducial_size = 6.0

    # --- 定位点相关方法 ---
    def set_fiducial_size(self, size: float):
        self._fiducial_size = size
        if self._fiducial:
            self._redraw_fiducial()

    def add_fiducial(self, point: Pt, shape: str):
        self.remove_fiducial()
        self._fiducial = (point, shape)
        self._redraw_fiducial()
        logger.info(f"添加定位点: {point}, 形状: {shape}, 尺寸: {self._fiducial_size}")

    def _redraw_fiducial(self):
        if not self._fiducial:
            return
        point, shape = self._fiducial
        x, y = point
        size = self._fiducial_size
        path = QPainterPath()
        if shape == 'cross':
            half = size / 2.0
            path.moveTo(x - half, y)
            path.lineTo(x + half, y)
            path.moveTo(x, y - half)
            path.lineTo(x, y + half)
        else:
            path.addEllipse(QPointF(x, y), size / 2, size / 2)
        self._fiducial_item = QGraphicsPathItem(path)
        pen = QPen(QColor(255, 0, 0), 0.3)
        self._fiducial_item.setPen(pen)
        self.scene.addItem(self._fiducial_item)

    def remove_fiducial(self):
        if self._fiducial_item:
            self.scene.removeItem(self._fiducial_item)
            self._fiducial_item = None
        self._fiducial = None
        logger.info("已删除定位点")

    def get_fiducial(self) -> Optional[Tuple[Pt, str]]:
        return self._fiducial

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

    def add_polyline(self, points, color):
        logger.info(f"画布添加折线：{len(points)}个点，颜色={color.getRgb()}")
        path = QPainterPath()
        if points:
            path.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, y)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(color, 0.5))
            self.scene.addItem(item)
        return item

    def add_rect(self, x: float, y: float, w: float, h: float, color: QColor = QColor(0, 0, 0)):
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        return self.add_polyline(pts, color)

    def add_circle(self, cx: float, cy: float, r: float, steps: int = 64, color: QColor = QColor(0, 0, 0)):
        pts = [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps)) for i in
               range(steps + 1)]
        return self.add_polyline(pts, color)

    def add_image(self, qpixmap: QPixmap, x: float = 0.0, y: float = 0.0):
        item = QGraphicsPixmapItem(qpixmap)
        item.setOffset(x, y)
        item.setTransformationMode(Qt.SmoothTransformation)
        item.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
        item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
        s = 25.4 / 96.0  # 96dpi -> 毫米
        item.setTransform(QTransform().scale(s, -s))
        self.scene.addItem(item)
        self._last_img_item = item
        self._bitmap_count += 1
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
            self.add_fiducial((pos.x(), pos.y()), shape)
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

    def undo(self):
        """GridCanvas暂不支持撤销，保留方法提示"""
        logger.warning("当前画布不支持撤销功能")

    def redo(self):
        """GridCanvas暂不支持重做，保留方法提示"""
        logger.warning("当前画布不支持重做功能")

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