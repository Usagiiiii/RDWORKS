#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白板部件类（整合 GridCanvas）
实现白板的绘图、缩放、标尺、图形编辑、定位点等功能
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsScene,
                             QGraphicsView, QGraphicsPixmapItem, QGraphicsItem,
                             QGraphicsTextItem, QInputDialog, QMessageBox)
from PyQt5.QtCore import Qt, QPoint, QRect, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import (QPainter, QPen, QColor, QPixmap, QBrush, QFont,
                         QPainterPath, QWheelEvent, QTransform, QMouseEvent,
                         QFontMetrics, QImage)
import math
from typing import List, Tuple, Optional

from edit.commands import AddItemCommand
from edit.edit_manager import EditManager
from my_io.gcode.gcode_exporter import Point
from ui.graphics_items import EditablePathItem
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 目标画布相关类定义
Pt = Tuple[float, float]
Path = List[Pt]

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

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = self.mapToScene(e.pos())
        x, y = pos.x(), pos.y()

        # 实时预览绘制
        if self._drawing_pts:
            if self._drawing_tmp:
                self.scene.removeItem(self._drawing_tmp)
                self._drawing_tmp = None

            path = QPainterPath()
            if self._tool == self.Tool.DRAW_LINE and len(self._drawing_pts) == 1:
                path.moveTo(self._drawing_pts[0][0], self._drawing_pts[0][1])
                path.lineTo(x, y)

            elif self._tool == self.Tool.DRAW_POLY and self._drawing_pts:
                path.moveTo(self._drawing_pts[0][0], self._drawing_pts[0][1])
                for pt in self._drawing_pts[1:]:
                    path.lineTo(pt[0], pt[1])
                path.lineTo(x, y)

            elif self._tool == self.Tool.DRAW_RECT and self._drawing_pts:
                x0, y0 = self._drawing_pts[0]
                path.addRect(min(x0, x), min(y0, y), abs(x - x0), abs(y - y0))

            elif self._tool == self.Tool.DRAW_ELLIPSE and self._drawing_pts:
                x0, y0 = self._drawing_pts[0]
                rx = abs(x - x0) / 2
                ry = abs(y - y0) / 2
                cx = (x0 + x) / 2
                cy = (y0 + y) / 2
                path.addEllipse(cx - rx, cy - ry, 2 * rx, 2 * ry)

            if not path.isEmpty():
                self._drawing_tmp = QGraphicsPathItem(path)
                pen = QPen(QColor(0, 150, 0))
                pen.setCosmetic(True)
                pen.setStyle(Qt.DashLine)
                self._drawing_tmp.setPen(pen)
                self.scene.addItem(self._drawing_tmp)

        self.headMoved.emit(x, y)
        super().mouseMoveEvent(e)


class RotateHandle(QGraphicsEllipseItem):
    """在选中项附近显示的旋转把手，支持鼠标拖拽旋转选中项（带预览与历史记录）。"""
    def __init__(self, canvas, radius=10):
        super().__init__(-radius, -radius, 2*radius, 2*radius)
        self.canvas = canvas
        pen = QPen(QColor(80, 80, 80))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(200, 200, 200)))
        self.setZValue(1000)
        self.setFlags(QGraphicsEllipseItem.ItemIsMovable | QGraphicsEllipseItem.ItemIsSelectable)
        self.setCursor(Qt.OpenHandCursor)
        self._dragging = False
        self._orig_tracking = None
        self._start_angle = None
        self._radius = radius
        # 不直接添加到场景，创建时由 canvas 管理
        # 可选图标显示（尝试从仓库图标目录加载）
        self._pixmap = None
        self._pixmap_item = None
        self._angle_text = None
        self._try_load_icon()

    def mousePressEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        x, y = scene_pos.x(), scene_pos.y()
        # 开始旋转：记录所选项原始状态
        sel = self.canvas.get_selected_items()
        if not sel:
            return
        tracking = []
        from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
        for it in sel:
            try:
                if isinstance(it, EditablePathItem):
                    old = it.points()
                    if old:
                        cx = sum(p[0] for p in old) / len(old)
                        cy = sum(p[1] for p in old) / len(old)
                    else:
                        br = it.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                    tracking.append(('path', it, old, (cx, cy)))
                elif isinstance(it, (QGraphicsPixmapItem, QGraphicsTextItem)):
                    oldt = it.transform()
                    try:
                        br = it.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                    except Exception:
                        cx = it.pos().x(); cy = it.pos().y()
                    tracking.append(('transform', it, oldt, (cx, cy)))
                else:
                    try:
                        oldt = it.transform()
                        br = it.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                        tracking.append(('transform', it, oldt, (cx, cy)))
                    except Exception:
                        continue
            except Exception:
                continue
        if tracking:
            self._orig_tracking = tracking
            px, py = tracking[0][3]
            self._start_angle = math.atan2(y - py, x - px)
            self._dragging = True
            # 改变光标样式表示按下
            try:
                self.setCursor(Qt.ClosedHandCursor)
            except Exception:
                pass
            # 创建/显示角度显示文本
            try:
                if self._angle_text is None:
                    from PyQt5.QtWidgets import QGraphicsTextItem
                    self._angle_text = QGraphicsTextItem('', parent=None)
                    self._angle_text.setZValue(1001)
                    # 文字朝上（画布做了Y翻转，修正文字方向）
                    try:
                        self._angle_text.setTransform(QTransform().scale(1, -1))
                    except Exception:
                        pass
                    self.canvas.scene.addItem(self._angle_text)
            except Exception:
                pass
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._dragging or not self._orig_tracking:
            super().mouseMoveEvent(event)
            return
        scene_pos = self.mapToScene(event.pos())
        x, y = scene_pos.x(), scene_pos.y()
        try:
            px, py = self._orig_tracking[0][3]
            cur_angle = math.atan2(y - py, x - px)
            delta = math.degrees(cur_angle - (self._start_angle or 0.0))
            # 如果按住 Shift 键，执行 15° 步进约束
            try:
                mods = event.modifiers()
                from PyQt5.QtCore import Qt as _QtConst
                if mods & _QtConst.ShiftModifier:
                    delta = round(delta / 15.0) * 15.0
            except Exception:
                pass
            for kind, it, old, pivot in self._orig_tracking:
                cx, cy = pivot
                if kind == 'path':
                    new_pts = []
                    rad = math.radians(delta)
                    cosv = math.cos(rad); sinv = math.sin(rad)
                    for px0, py0 in old:
                        dx = px0 - cx; dy = py0 - cy
                        nx = cx + dx * cosv - dy * sinv
                        ny = cy + dx * sinv + dy * cosv
                        new_pts.append((nx, ny))
                    # 预览：直接设置 Path（不改变内部 _points）
                    try:
                        path = QPainterPath()
                        if new_pts:
                            path.moveTo(new_pts[0][0], new_pts[0][1])
                            for p in new_pts[1:]:
                                path.lineTo(p[0], p[1])
                            it.setPath(path)
                    except Exception:
                        pass
                else:
                    try:
                        t = QTransform()
                        t.translate(cx, cy)
                        t.rotate(delta)
                        t.translate(-cx, -cy)
                        try:
                            it.setTransform(t * old)
                        except Exception:
                            it.setTransform(t)
                    except Exception:
                        pass
        except Exception:
            pass
        # 更新角度显示文本位置与内容
        try:
            if self._angle_text is not None:
                self._angle_text.setPlainText(f"{delta:.1f}°")
                # 放在把手上方
                tx = self.scenePos().x()
                ty = self.scenePos().y() + 12
                self._angle_text.setPos(tx, ty)
        except Exception:
            pass
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not self._dragging or not self._orig_tracking:
            super().mouseReleaseEvent(event)
            return
        scene_pos = self.mapToScene(event.pos())
        x, y = scene_pos.x(), scene_pos.y()
        try:
            px, py = self._orig_tracking[0][3]
            cur_angle = math.atan2(y - py, x - px)
            delta = math.degrees(cur_angle - (self._start_angle or 0.0))
            # Shift 步进约束
            try:
                mods = event.modifiers()
                from PyQt5.QtCore import Qt as _QtConst
                if mods & _QtConst.ShiftModifier:
                    delta = round(delta / 15.0) * 15.0
            except Exception:
                pass
            items_states = []
            for kind, it, old, pivot in self._orig_tracking:
                cx, cy = pivot
                if kind == 'path':
                    new_pts = []
                    rad = math.radians(delta)
                    cosv = math.cos(rad); sinv = math.sin(rad)
                    for px0, py0 in old:
                        dx = px0 - cx; dy = py0 - cy
                        nx = cx + dx * cosv - dy * sinv
                        ny = cy + dx * sinv + dy * cosv
                        new_pts.append((nx, ny))
                    try:
                        it.set_points(new_pts)
                    except Exception:
                        pass
                    items_states.append(('path', it, old, new_pts))
                else:
                    try:
                        m = QTransform()
                        m.translate(cx, cy)
                        m.rotate(delta)
                        m.translate(-cx, -cy)
                        oldt = old
                        try:
                            newt = m * oldt
                        except Exception:
                            newt = m
                        try:
                            it.setTransform(newt)
                        except Exception:
                            pass
                        items_states.append(('transform', it, oldt, newt))
                    except Exception:
                        continue
            if items_states:
                from edit.commands import RotateCommand
                cmd = RotateCommand(self.canvas, items_states)
                # 旋转已应用，直接记录历史
                self.canvas.edit_manager.push_undo(cmd)
        except Exception:
            pass
        finally:
            # 恢复光标
            try:
                self.setCursor(Qt.OpenHandCursor)
            except Exception:
                pass
            # 清理角度文本
            try:
                if self._angle_text is not None:
                    try:
                        self.canvas.scene.removeItem(self._angle_text)
                    except Exception:
                        pass
                    self._angle_text = None
            except Exception:
                pass
            self._dragging = False
            self._orig_tracking = None
            self._start_angle = None
        event.accept()

    def _try_load_icon(self):
        """尝试从仓库图标目录加载旋转图标并作为子项显示。"""
        candidates = [
            'toolbar_row3_icons/rotate_icon.png',
            'toolbar_row3_icons/icon_rotate.png',
            'toolbar_row3_icons/icon3_rotate.png',
            'toolbar_row3_icons/icon3_column4.png'
        ]
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QGraphicsPixmapItem
        for p in candidates:
            try:
                pm = QPixmap(p)
                if not pm.isNull():
                    # 缩放图标以适配把手
                    try:
                        pm = pm.scaled(self._radius*2, self._radius*2)
                    except Exception:
                        pass
                    self._pixmap = pm
                    try:
                        self._pixmap_item = QGraphicsPixmapItem(pm, parent=self)
                        self._pixmap_item.setOffset(-self._radius, -self._radius)
                        self._pixmap_item.setZValue(self.zValue()+1)
                    except Exception:
                        self._pixmap_item = None
                    break
            except Exception:
                continue


class GridCanvas(QGraphicsView):
    headMoved = pyqtSignal(float, float)
    view_changed = pyqtSignal(float, QPoint)  # 缩放比例、偏移量信号（用于标尺联动）

    class Tool:
        SELECT = 0
        NODE_EDIT = 1
        DRAW_LINE = 2
        DRAW_POLY = 3
        DRAW_CURVE = 4
        DRAW_RECT = 5
        DRAW_ELLIPSE = 6
        DRAW_TEXT = 7
        DRAW_POINT = 8
        DRAW_GRID = 9
        DELETE = 10
        H_MIRROR = 11
        V_MIRROR = 12
        DOCK = 13
        ARRAY = 14
        PAN = 15
        ADD_FID_CROSS = 16
        ADD_FID_CIRCLE = 17
        DRAW_CIRCLE = 18  # 新增圆形绘制工具
        ROTATE = 19  # 旋转工具（鼠标拖拽或角度输入）

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
        # 旋转交互状态
        self._rotate_tracking = None  # list of tuples (typ, item, old_state, pivot)
        self._rotate_start_angle = None
        self._drawing_pts: Path = []
        self._drawing_tmp: Optional[QGraphicsPathItem] = None
        self._current_color = QColor(0, 0, 0)  # 默认黑色

        # 定位点相关属性 - 使用新的管理器
        from my_io.fiducial.fiducial_manager import FiducialManager
        self.fiducial_manager = FiducialManager(self)

        # -------------------------- 新增：初始化编辑管理器 --------------------------
        self.edit_manager = EditManager(self)
        # 连接场景的选中状态变化信号 → 通知EditManager更新可用性
        self.scene.selectionChanged.connect(self._on_selection_changed)
        # 旋转把手（场景中的 QGraphicsItem），根据选中项显示/隐藏
        self._rotate_handle = None

    # -------------------------- 新增：选中状态变化处理 --------------------------
    def _on_selection_changed(self):
        """当画布选中项变化时，通知EditManager"""
        has_selection = len(self.get_selected_items()) > 0
        self.edit_manager.set_has_selection(has_selection)
        # 管理旋转把手的显示
        try:
            sel = self.get_selected_items()
            if sel:
                # 计算包围矩形（场景坐标）
                br = None
                for it in sel:
                    try:
                        r = it.sceneBoundingRect()
                        br = r if br is None else br.united(r)
                    except Exception:
                        continue
                if br is not None:
                    # 创建把手（如果不存在）
                    if self._rotate_handle is None:
                        self._rotate_handle = RotateHandle(self)
                        try:
                            self.scene.addItem(self._rotate_handle)
                        except Exception:
                            self._rotate_handle = None
                    if self._rotate_handle is not None:
                        # 放在包围框右上方，靠近边缘（较小偏移）
                        ox = br.right() + 6
                        oy = br.top() - 6
                        self._rotate_handle.setPos(ox, oy)
                        self._rotate_handle.show()
            else:
                if self._rotate_handle is not None:
                    try:
                        self.scene.removeItem(self._rotate_handle)
                    except Exception:
                        pass
                    self._rotate_handle = None
        except Exception:
            pass

    # -------------------------- 新增：供EditManager调用的接口 --------------------------
    def get_selected_items(self) -> List[QGraphicsItem]:
        """获取所有选中的图形项（排除定位点和工作区网格）"""
        exclude_items = [self._work_item]

        # 使用新的 FiducialManager 获取定位点项
        if hasattr(self, 'fiducial_manager'):
            fiducial_item = self.fiducial_manager.get_fiducial_item()
            if fiducial_item:
                exclude_items.append(fiducial_item)

        # 包含文字项（QGraphicsTextItem）以支持删除/剪切/复制
        return [
            item for item in self.scene.selectedItems()
            if item not in exclude_items  # 不处理网格和定位点
               and isinstance(item, (EditablePathItem, QGraphicsPixmapItem, QGraphicsTextItem))  # 处理路径、图片和文字
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
            # 选中路径、图片和文字项
            if item not in exclude_items and isinstance(item, (EditablePathItem, QGraphicsPixmapItem, QGraphicsTextItem)):
                item.setSelected(True)

    # --- 定位点相关方法（更新为使用命令模式）---
    def set_fiducial_size(self, size: float):
        try:
            from edit.commands import SetFiducialSizeCommand
            cmd = SetFiducialSizeCommand(self, size)
            # 先执行再记录历史
            cmd.redo()
            self.edit_manager.push_undo(cmd)
        except Exception:
            # fallback: 直接设置
            try:
                self.fiducial_manager.set_fiducial_size(size)
            except Exception:
                pass

    def add_fiducial(self, point: Point, shape: str):
        """添加定位点（使用命令模式）"""
        from edit.commands import AddFiducialCommand
        cmd = AddFiducialCommand(self, point, shape)
        # 先执行命令再推入历史（EditManager 假定命令已执行）
        cmd.redo()
        self.edit_manager.push_undo(cmd)

    def remove_fiducial(self):
        """删除定位点（使用命令模式）"""
        from edit.commands import RemoveFiducialCommand
        if self.fiducial_manager.get_fiducial():
            cmd = RemoveFiducialCommand(self)
            cmd.redo()
            self.edit_manager.push_undo(cmd)

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

    # --- 工具设置方法 ---
    def set_tool(self, t: int):
        """设置当前工具"""
        old_tool = self._tool
        self._tool = t

        # 退出节点编辑模式
        if old_tool == self.Tool.NODE_EDIT:
            for it in self.all_paths():
                it.enable_node_edit(False)

        # 进入节点编辑模式
        if t == self.Tool.NODE_EDIT:
            for it in self.selected_paths():
                it.enable_node_edit(True)

        # 设置拖动模式
        if t == self.Tool.PAN:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.RubberBandDrag)

        # 清除临时绘图状态
        self._clear_drawing_state()

    def _clear_drawing_state(self):
        """清除绘图状态"""
        if self._drawing_tmp:
            self.scene.removeItem(self._drawing_tmp)
            self._drawing_tmp = None
        self._drawing_pts = []
        # 清除旋转交互状态
        self._rotate_tracking = None
        self._rotate_start_angle = None

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

    # --- 绘图方法 ---
    def add_polyline(self, points, color=None):
        """添加折线"""
        if color is None:
            color = self._current_color
        logger.info(f"画布添加折线：{len(points)}个点，颜色={color.getRgb()}")
        item = EditablePathItem(points, color)
        self.scene.addItem(item)

        cmd = AddItemCommand(self, item)
        self.edit_manager.push_undo(cmd)
        return item

    def add_line(self, x1: float, y1: float, x2: float, y2: float, color=None):
        """添加直线"""
        return self.add_polyline([(x1, y1), (x2, y2)], color)

    def add_rect(self, x: float, y: float, w: float, h: float, color=None):
        """添加矩形"""
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        return self.add_polyline(pts, color)

    def add_ellipse(self, cx: float, cy: float, rx: float, ry: float, color=None):
        """添加椭圆"""
        steps = 64
        pts = []
        for i in range(steps + 1):
            angle = 2 * math.pi * i / steps
            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)
            pts.append((x, y))
        return self.add_polyline(pts, color)

    def add_circle(self, cx: float, cy: float, r: float, color=None):
        """添加圆形"""
        return self.add_ellipse(cx, cy, r, r, color)

    def add_point(self, x: float, y: float, color=None):
        """添加点（小圆点）"""
        if color is None:
            color = self._current_color
        item = QGraphicsEllipseItem(x - 1, y - 1, 2, 2)
        pen = QPen(color)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setBrush(QBrush(color))
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.scene.addItem(item)

        cmd = AddItemCommand(self, item)
        self.edit_manager.push_undo(cmd)
        return item

    def add_text(self, x: float, y: float, text: str, color=None):
        """添加文字"""
        if color is None:
            color = self._current_color
        item = QGraphicsTextItem(text)
        item.setDefaultTextColor(color)
        item.setPos(x, y)
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.ItemIsMovable, True)

        # 设置字体
        font = QFont("Arial", 10)
        item.setFont(font)

        # 画布在初始化时对视图做了 Y 轴翻转（self.scale(1, -1)），
        # 这会导致文本显示为上下颠倒。对文本项也做一次 Y 轴翻转
        # 可以抵消视图的翻转，使文字正常显示同时仍随缩放变换。
        try:
            item.setTransform(QTransform().scale(1, -1))
        except Exception:
            # 如果 QTransform 不可用或出错，忽略（保留原行为）
            pass

        self.scene.addItem(item)

        cmd = AddItemCommand(self, item)
        self.edit_manager.push_undo(cmd)
        return item

    def add_grid(self, x: float, y: float, cols: int, rows: int, col_spacing: float, row_spacing: float, color=None):
        """添加网格"""
        if color is None:
            color = self._current_color

        items = []
        for i in range(cols + 1):
            x_pos = x + i * col_spacing
            items.append(self.add_line(x_pos, y, x_pos, y + rows * row_spacing, color))

        for j in range(rows + 1):
            y_pos = y + j * row_spacing
            items.append(self.add_line(x, y_pos, x + cols * col_spacing, y_pos, color))

        return items

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

        # ========== 3. 添加图片到画布（以灰度显示） ==========
        # 将缩放后的 QPixmap 转为灰度 QImage，再转回 QPixmap 以显示为灰度图
        try:
            qim = scaled_pixmap.toImage()
            gray = qim.convertToFormat(QImage.Format_Grayscale8)
            # 保留 alpha 通道（如果存在）
            try:
                if qim.hasAlphaChannel():
                    alpha = qim.alphaChannel()
                    gray.setAlphaChannel(alpha)
            except Exception:
                pass
            disp_pix = QPixmap.fromImage(gray)
        except Exception:
            disp_pix = scaled_pixmap

        item = QGraphicsPixmapItem(disp_pix)
        # 设置图片位置（精确居中）
        item.setPos(img_x, img_y)
        item.setOffset(0, 0)  # 偏移量为0，位置已通过setPos设置

        item.setTransformationMode(Qt.SmoothTransformation)
        item.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
        item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)

        # 应用缩放转换（像素到毫米）
        s = 25.4 / 96.0  # 96dpi → 毫米的缩放系数
        item.setTransform(QTransform().scale(s, -s))  # Y轴翻转适配Qt坐标系统

        # 使用命令执行添加并记录历史（先执行 redo，再 push）
        cmd = AddItemCommand(self, item)
        try:
            cmd.redo()
        except Exception:
            # 如果 redo 失败，尝试直接添加以保证显示
            try:
                self.scene.addItem(item)
            except Exception:
                pass
        try:
            self.edit_manager.push_undo(cmd)
        except Exception:
            # push 失败不应影响显示
            pass

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

    def scale_selected_items(self, factor: float):
        """对当前选中的项执行缩放（相对于每个项的包围盒中心）。

        - 矢量路径（EditablePathItem）：直接缩放其内部点坐标（从而导出保持正确）。
        - 图片/文字：对其 transform 进行缩放（保持位置相对包围盒中心）。
        """
        items_states = []
        for item in self.scene.selectedItems():
            try:
                # EditablePathItem 使用点数据，需要直接修改点
                from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
                from PyQt5.QtGui import QTransform

                if isinstance(item, EditablePathItem):
                    pts = item.points()
                    if not pts:
                        continue
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x()
                        cy = br.center().y()
                    except Exception:
                        cx = sum(p[0] for p in pts) / len(pts)
                        cy = sum(p[1] for p in pts) / len(pts)
                    scaled = [((p[0] - cx) * factor + cx, (p[1] - cy) * factor + cy) for p in pts]
                    # 保存状态以便作为命令记录
                    items_states.append(('path', item, pts, scaled))

                elif isinstance(item, QGraphicsPixmapItem) or isinstance(item, QGraphicsTextItem):
                    br = item.sceneBoundingRect()
                    cx = br.center().x()
                    cy = br.center().y()
                    m = QTransform()
                    m.translate(cx, cy)
                    m.scale(factor, factor)
                    m.translate(-cx, -cy)
                    oldt = item.transform()
                    newt = m * oldt
                    items_states.append(('transform', item, oldt, newt))
                else:
                    # 其他项尝试应用 transform 缩放
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x()
                        cy = br.center().y()
                        m = QTransform()
                        m.translate(cx, cy)
                        m.scale(factor, factor)
                        m.translate(-cx, -cy)
                        oldt = item.transform()
                        newt = m * oldt
                        items_states.append(('transform', item, oldt, newt))
                    except Exception:
                        continue
            except Exception:
                continue

        # 应用所有变化并推入历史
        try:
            from edit.commands import ScaleCommand
            # 先应用
            for typ, it, old, new in items_states:
                try:
                    if typ == 'path':
                        it.set_points(new)
                    elif typ == 'transform':
                        it.setTransform(new)
                except Exception:
                    continue
            if items_states:
                cmd = ScaleCommand(self, items_states)
                self.edit_manager.push_undo(cmd)
        except Exception:
            pass

    def rotate_selected(self, angle_deg: float):
        """按指定角度(度)旋转当前选中项并记录历史。"""
        items_states = []
        from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
        for item in self.scene.selectedItems():
            try:
                if isinstance(item, EditablePathItem):
                    pts = item.points()
                    if not pts:
                        continue
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                    except Exception:
                        cx = sum(p[0] for p in pts) / len(pts)
                        cy = sum(p[1] for p in pts) / len(pts)
                    rad = math.radians(angle_deg)
                    cosv = math.cos(rad); sinv = math.sin(rad)
                    new_pts = [
                        (cx + (p[0] - cx) * cosv - (p[1] - cy) * sinv,
                         cy + (p[0] - cx) * sinv + (p[1] - cy) * cosv)
                        for p in pts
                    ]
                    item.set_points(new_pts)
                    items_states.append(('path', item, pts, new_pts))
                elif isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem)):
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                    except Exception:
                        cx = item.pos().x(); cy = item.pos().y()
                    m = QTransform()
                    m.translate(cx, cy)
                    m.rotate(angle_deg)
                    m.translate(-cx, -cy)
                    oldt = item.transform()
                    try:
                        newt = m * oldt
                    except Exception:
                        newt = m
                    item.setTransform(newt)
                    items_states.append(('transform', item, oldt, newt))
                else:
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                        m = QTransform()
                        m.translate(cx, cy)
                        m.rotate(angle_deg)
                        m.translate(-cx, -cy)
                        oldt = item.transform()
                        newt = m * oldt
                        item.setTransform(newt)
                        items_states.append(('transform', item, oldt, newt))
                    except Exception:
                        continue
            except Exception:
                continue

        if items_states:
            try:
                from edit.commands import RotateCommand
                cmd = RotateCommand(self, items_states)
                self.edit_manager.push_undo(cmd)
            except Exception:
                pass

    def _get_item_current_angle(self, item):
        """尝试估算项当前的旋转角度（度）。

        - 对于有 transform 的项（图片/文字/常规项），通过 transform 矩阵提取旋转角。
        - 对于路径项，使用质心到第一点向量角度作为近似当前朝向。
        返回角度（度）。如果无法计算则返回 0.0。
        """
        try:
            from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
            if isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem)):
                t = item.transform()
                # QTransform: m11, m12, m21, m22 对应矩阵
                m11 = t.m11(); m21 = t.m21()
                ang = math.degrees(math.atan2(m21, m11))
                return ang
        except Exception:
            pass
        try:
            if isinstance(item, EditablePathItem):
                pts = item.points()
                if not pts:
                    return 0.0
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                px, py = pts[0]
                return math.degrees(math.atan2(py - cy, px - cx))
        except Exception:
            pass
        try:
            # fallback: use sceneBoundingRect orientation (assume 0)
            return 0.0
        except Exception:
            return 0.0

    def rotate_selected_absolute(self, target_angle_deg: float):
        """将每个选中项旋转到目标绝对角度（度），对每项计算所需增量并应用。

        对于每个被选中项，会计算其当前角度（使用 _get_item_current_angle），并旋转 delta = target - current。
        最后把这些变化打包为一个 RotateCommand 推入历史。
        """
        items_states = []
        from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
        for item in self.scene.selectedItems():
            try:
                cur = self._get_item_current_angle(item)
                delta = target_angle_deg - cur
                # 将 delta 应用于每个项（以项的中心为轴）
                if isinstance(item, EditablePathItem):
                    pts = item.points()
                    if not pts:
                        continue
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                    except Exception:
                        cx = sum(p[0] for p in pts) / len(pts)
                        cy = sum(p[1] for p in pts) / len(pts)
                    rad = math.radians(delta)
                    cosv = math.cos(rad); sinv = math.sin(rad)
                    new_pts = [
                        (cx + (p[0] - cx) * cosv - (p[1] - cy) * sinv,
                         cy + (p[0] - cx) * sinv + (p[1] - cy) * cosv)
                        for p in pts
                    ]
                    item.set_points(new_pts)
                    items_states.append(('path', item, pts, new_pts))
                elif isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem)):
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                    except Exception:
                        cx = item.pos().x(); cy = item.pos().y()
                    m = QTransform()
                    m.translate(cx, cy)
                    m.rotate(delta)
                    m.translate(-cx, -cy)
                    oldt = item.transform()
                    try:
                        newt = m * oldt
                    except Exception:
                        newt = m
                    item.setTransform(newt)
                    items_states.append(('transform', item, oldt, newt))
                else:
                    try:
                        br = item.sceneBoundingRect()
                        cx = br.center().x(); cy = br.center().y()
                        m = QTransform()
                        m.translate(cx, cy)
                        m.rotate(delta)
                        m.translate(-cx, -cy)
                        oldt = item.transform()
                        newt = m * oldt
                        item.setTransform(newt)
                        items_states.append(('transform', item, oldt, newt))
                    except Exception:
                        continue
            except Exception:
                continue

        if items_states:
            try:
                from edit.commands import RotateCommand
                cmd = RotateCommand(self, items_states)
                self.edit_manager.push_undo(cmd)
            except Exception:
                pass

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = self.mapToScene(e.pos())
        self.headMoved.emit(pos.x(), pos.y())
        if self._tool in (self.Tool.DRAW_POLY, self.Tool.DRAW_RECT, self.Tool.DRAW_ELLIPSE, self.Tool.DRAW_CURVE) and self._drawing_pts:
            if self._drawing_tmp:
                self.scene.removeItem(self._drawing_tmp)
                self._drawing_tmp = None
            path = QPainterPath()
            if self._tool == self.Tool.DRAW_POLY:
                path.moveTo(self._drawing_pts[0][0], self._drawing_pts[0][1])
                path.lineTo(pos.x(), pos.y())
            elif self._tool == self.Tool.DRAW_CURVE:
                # 将当前鼠标位置当作最后一个锚点，生成平滑曲线预览
                pts = self._drawing_pts + [(pos.x(), pos.y())]
                path = QPainterPath()
                if len(pts) >= 2:
                    # reuse Catmull-Rom -> Bezier logic
                    if len(pts) == 2:
                        path.moveTo(pts[0][0], pts[0][1])
                        path.lineTo(pts[1][0], pts[1][1])
                    else:
                        ext = [pts[0]] + pts + [pts[-1]]
                        path.moveTo(pts[0][0], pts[0][1])
                        n = len(pts)
                        for i in range(1, n):
                            p0 = ext[i - 1]
                            p1 = ext[i]
                            p2 = ext[i + 1]
                            p3 = ext[i + 2]
                            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
                            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
                            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
                            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
                            path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
            elif self._tool == self.Tool.DRAW_RECT:
                x0, y0 = self._drawing_pts[0]
                path.addRect(min(x0, pos.x()), min(y0, pos.y()), abs(pos.x() - x0), abs(pos.y() - y0))
            elif self._tool == self.Tool.DRAW_ELLIPSE:
                x0, y0 = self._drawing_pts[0]
                # 修改为椭圆绘制逻辑：以两点中心为圆心，x/y差为半径
                rx = abs(pos.x() - x0) / 2
                ry = abs(pos.y() - y0) / 2
                cx = (x0 + pos.x()) / 2
                cy = (y0 + pos.y()) / 2
                path.addEllipse(cx - rx, cy - ry, 2 * rx, 2 * ry)
            self._drawing_tmp = QGraphicsPathItem(path)
            pen = QPen(QColor(0, 150, 0))
            pen.setCosmetic(True)
            pen.setStyle(Qt.DashLine)
            self._drawing_tmp.setPen(pen)
            self.scene.addItem(self._drawing_tmp)
        # 平移时发送视图变化信号
        if self._tool == self.Tool.PAN and self.dragMode() == QGraphicsView.ScrollHandDrag:
            self._emit_view_changed()
        # 旋转工具预览：根据开始角度与当前鼠标位置计算角度增量，实时对选中项做预览变换
        if getattr(self, '_rotate_tracking', None):
            try:
                px, py = self._rotate_tracking[0][3]
                cur_angle = math.atan2(pos.y() - py, pos.x() - px)
                delta = math.degrees(cur_angle - self._rotate_start_angle) if self._rotate_start_angle is not None else 0.0
                for kind, it, old, pivot in self._rotate_tracking:
                    cx, cy = pivot
                    if kind == 'path':
                        new_pts = []
                        rad = math.radians(delta)
                        cosv = math.cos(rad); sinv = math.sin(rad)
                        for px0, py0 in old:
                            dx = px0 - cx; dy = py0 - cy
                            nx = cx + dx * cosv - dy * sinv
                            ny = cy + dx * sinv + dy * cosv
                            new_pts.append((nx, ny))
                        # 仅作为预览，不修改内部 _points（使用 setPath 临时显示）
                        try:
                            path = QPainterPath()
                            if new_pts:
                                path.moveTo(new_pts[0][0], new_pts[0][1])
                                for p in new_pts[1:]:
                                    path.lineTo(p[0], p[1])
                                it.setPath(path)
                        except Exception:
                            pass
                    else:
                        try:
                            t = QTransform()
                            t.translate(cx, cy)
                            t.rotate(delta)
                            t.translate(-cx, -cy)
                            # 将旋转乘在原始 transform 之前，以保持原变换关系
                            try:
                                newt = t * old
                                it.setTransform(newt)
                            except Exception:
                                it.setTransform(t)
                        except Exception:
                            pass
            except Exception:
                pass
        super().mouseMoveEvent(e)

    # --- 鼠标事件处理 ---
    def mousePressEvent(self, e: QMouseEvent):
        """鼠标按下事件处理"""
        pos = self.mapToScene(e.pos())
        x, y = pos.x(), pos.y()

        # 记录按下时选中项的状态，用于在鼠标释放时生成移动命令
        try:
            if e.button() == Qt.LeftButton:
                self._move_tracking = []
                for it in self.scene.selectedItems():
                    try:
                        from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
                        if isinstance(it, EditablePathItem):
                            self._move_tracking.append(('path', it, it.points()))
                        elif isinstance(it, (QGraphicsPixmapItem, QGraphicsTextItem)):
                            # 保存 transform 与 pos
                            self._move_tracking.append(('transform', it, it.transform()))
                        else:
                            # fallback: save transform if possible
                            try:
                                self._move_tracking.append(('transform', it, it.transform()))
                            except Exception:
                                continue
                    except Exception:
                        continue
        except Exception:
            self._move_tracking = []

        if e.button() == Qt.LeftButton:
            # 旋转工具：开始旋转交互（仅当至少选中一项时）
            if self._tool == self.Tool.ROTATE:
                try:
                    # 记录所有选中项的原始状态与轴心
                    sel = self.get_selected_items()
                    if not sel:
                        # 没有选中项则不进入旋转交互
                        self._rotate_tracking = None
                    else:
                        tracking = []
                        for it in sel:
                            try:
                                from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
                                if isinstance(it, EditablePathItem):
                                    old = it.points()
                                    # pivot: use points center (average)
                                    if old:
                                        cx = sum(p[0] for p in old) / len(old)
                                        cy = sum(p[1] for p in old) / len(old)
                                    else:
                                        br = it.sceneBoundingRect()
                                        cx = br.center().x(); cy = br.center().y()
                                    tracking.append(('path', it, old, (cx, cy)))
                                elif isinstance(it, (QGraphicsPixmapItem, QGraphicsTextItem)):
                                    oldt = it.transform()
                                    try:
                                        br = it.sceneBoundingRect()
                                        cx = br.center().x(); cy = br.center().y()
                                    except Exception:
                                        cx = it.pos().x(); cy = it.pos().y()
                                    tracking.append(('transform', it, oldt, (cx, cy)))
                                else:
                                    try:
                                        oldt = it.transform()
                                        br = it.sceneBoundingRect()
                                        cx = br.center().x(); cy = br.center().y()
                                        tracking.append(('transform', it, oldt, (cx, cy)))
                                    except Exception:
                                        continue
                            except Exception:
                                continue
                        if tracking:
                            self._rotate_tracking = tracking
                            # compute start angle from first pivot
                            px, py = self._rotate_tracking[0][3]
                            self._rotate_start_angle = math.atan2(y - py, x - px)
                        else:
                            self._rotate_tracking = None
                except Exception:
                    self._rotate_tracking = None
                # when rotate tool, we don't proceed other tool actions here
                return
            if self._tool == self.Tool.DRAW_LINE:
                if not self._drawing_pts:
                    self._drawing_pts = [(x, y)]
                else:
                    # 完成直线绘制
                    self._drawing_pts.append((x, y))
                    self.add_line(self._drawing_pts[0][0], self._drawing_pts[0][1],
                                  self._drawing_pts[1][0], self._drawing_pts[1][1])
                    self._clear_drawing_state()

            elif self._tool == self.Tool.DRAW_POLY:
                if not self._drawing_pts:
                    self._drawing_pts = [(x, y)]
                    # 开始绘制折线，显示第一个点
                    self._show_drawing_preview()
                else:
                    self._drawing_pts.append((x, y))
                    self._show_drawing_preview()

            elif self._tool == self.Tool.DRAW_CURVE:
                # 曲线绘制：点击添加锚点，右键结束
                if not self._drawing_pts:
                    self._drawing_pts = [(x, y)]
                    # 需要至少两个点才能显示预览
                else:
                    self._drawing_pts.append((x, y))
                # 更新预览（如果已有至少2个点）
                if len(self._drawing_pts) >= 2:
                    if self._drawing_tmp:
                        self.scene.removeItem(self._drawing_tmp)
                        self._drawing_tmp = None
                    # 直接调用 mouseMoveEvent 风格的预览生成，使用当前点作为末点
                    path = QPainterPath()
                    pts = self._drawing_pts[:]
                    if len(pts) == 2:
                        path.moveTo(pts[0][0], pts[0][1])
                        path.lineTo(pts[1][0], pts[1][1])
                    else:
                        ext = [pts[0]] + pts + [pts[-1]]
                        path.moveTo(pts[0][0], pts[0][1])
                        n = len(pts)
                        for i in range(1, n):
                            p0 = ext[i - 1]
                            p1 = ext[i]
                            p2 = ext[i + 1]
                            p3 = ext[i + 2]
                            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
                            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
                            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
                            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
                            path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
                    self._drawing_tmp = QGraphicsPathItem(path)
                    pen = QPen(QColor(0, 150, 0))
                    pen.setCosmetic(True)
                    pen.setStyle(Qt.DashLine)
                    self._drawing_tmp.setPen(pen)
                    self.scene.addItem(self._drawing_tmp)

            elif self._tool == self.Tool.DRAW_RECT:
                self._drawing_pts = [(x, y)]

            elif self._tool == self.Tool.DRAW_ELLIPSE:
                self._drawing_pts = [(x, y)]

            elif self._tool == self.Tool.DRAW_POINT:
                self.add_point(x, y)

            elif self._tool == self.Tool.DRAW_TEXT:
                text, ok = QInputDialog.getText(self, "输入文字", "请输入文字内容:")
                if ok and text:
                    self.add_text(x, y, text)

            elif self._tool == self.Tool.DRAW_GRID:
                # 弹出对话框获取网格参数
                cols, ok1 = QInputDialog.getInt(self, "网格列数", "请输入列数:", 5, 1, 100, 1)
                rows, ok2 = QInputDialog.getInt(self, "网格行数", "请输入行数:", 5, 1, 100, 1)
                spacing, ok3 = QInputDialog.getDouble(self, "网格间距", "请输入间距(mm):", 20.0, 1.0, 1000.0, 1)

                if ok1 and ok2 and ok3:
                    self.add_grid(x, y, cols, rows, spacing, spacing)

            elif self._tool in (self.Tool.H_MIRROR, self.Tool.V_MIRROR):
                # 水平/垂直镜像选中的图形
                selected_items = self.get_selected_items()
                if selected_items:
                    # 使用可撤销命令执行镜像（直接修改原图）
                    from edit.commands import MirrorCommand
                    horizontal = (self._tool == self.Tool.H_MIRROR)
                    cmd = MirrorCommand(self, selected_items, horizontal=horizontal)
                    # 先执行再记录历史
                    cmd.redo()
                    self.edit_manager.push_undo(cmd)
                    # 镜像后回到选择工具
                    self.set_tool(self.Tool.SELECT)
                    if hasattr(self, 'toolChanged'):
                        self.toolChanged.emit(self.Tool.SELECT)

        elif e.button() == Qt.RightButton:
            # 右键结束绘制
            if self._tool == self.Tool.DRAW_POLY and len(self._drawing_pts) >= 2:
                self.add_polyline(self._drawing_pts)
                self._clear_drawing_state()
            elif self._tool == self.Tool.DRAW_CURVE and len(self._drawing_pts) >= 2:
                # 完成曲线绘制，创建平滑路径并加入撤销栈
                try:
                    color = self._current_color
                    item = EditablePathItem(self._drawing_pts, color, smooth=True)
                    self.scene.addItem(item)
                    cmd = AddItemCommand(self, item)
                    # 记录历史（假定 item 已经添加）
                    self.edit_manager.push_undo(cmd)
                except Exception as ex:
                    logger.exception("完成曲线绘制时发生异常")
                    try:
                        QMessageBox.critical(self, '绘图错误', f'完成曲线绘制时发生错误:\n{str(ex)}')
                    except Exception:
                        pass
                finally:
                    self._clear_drawing_state()
            else:
                self._clear_drawing_state()

        super().mousePressEvent(e)

    def _show_drawing_preview(self):
        """显示绘制预览"""
        if self._drawing_tmp:
            self.scene.removeItem(self._drawing_tmp)

        if len(self._drawing_pts) < 2:
            return

        path = QPainterPath()
        path.moveTo(self._drawing_pts[0][0], self._drawing_pts[0][1])
        for pt in self._drawing_pts[1:]:
            path.lineTo(pt[0], pt[1])

        self._drawing_tmp = QGraphicsPathItem(path)
        pen = QPen(QColor(0, 150, 0))
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        self._drawing_tmp.setPen(pen)
        self.scene.addItem(self._drawing_tmp)
        

    def _mirror_item(self, item, horizontal=True):
        """镜像图形项"""
        if isinstance(item, EditablePathItem):
            # 镜像路径点
            points = item.points()
            if horizontal:
                # 水平镜像：x坐标取反
                center_x = sum(p[0] for p in points) / len(points)
                mirrored_points = [(2 * center_x - p[0], p[1]) for p in points]
            else:
                # 垂直镜像：y坐标取反
                center_y = sum(p[1] for p in points) / len(points)
                mirrored_points = [(p[0], 2 * center_y - p[1]) for p in points]

            item.set_points(mirrored_points)

        elif isinstance(item, QGraphicsPixmapItem):
            # 镜像图片
            transform = item.transform()
            if horizontal:
                transform.scale(-1, 1)
            else:
                transform.scale(1, -1)
            item.setTransform(transform)

    def mouseReleaseEvent(self, e: QMouseEvent):
        pos = self.mapToScene(e.pos())
        x, y = pos.x(), pos.y()

        if e.button() == Qt.LeftButton:
            if self._tool == self.Tool.DRAW_RECT and self._drawing_pts:
                x0, y0 = self._drawing_pts[0]
                w, h = x - x0, y - y0
                if abs(w) > 1 and abs(h) > 1:
                    self.add_rect(min(x0, x), min(y0, y), abs(w), abs(h))
                self._clear_drawing_state()

            elif self._tool == self.Tool.DRAW_ELLIPSE and self._drawing_pts:
                x0, y0 = self._drawing_pts[0]
                # 修改为椭圆绘制逻辑：以两点中心为圆心，x/y差为半径
                rx = abs(x - x0) / 2
                ry = abs(y - y0) / 2
                if rx > 1 and ry > 1:  # 避免太小
                    cx = (x0 + x) / 2
                    cy = (y0 + y) / 2
                    self.add_ellipse(cx, cy, rx, ry)
                self._clear_drawing_state()
            # 处理拖动造成的状态变化：比较 press 时记录的 状态 与当前状态，若不同则生成 MoveItemsCommand
            try:
                tracking = getattr(self, '_move_tracking', None)
                if tracking:
                    items_states = []
                    for typ, it, old in tracking:
                        try:
                            
                            from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem
                            if typ == 'path' and isinstance(it, EditablePathItem):
                                new = it.points()
                                if new != old:
                                    items_states.append(('path', it, old, new))
                            else:
                                # transform case
                                try:
                                    newt = it.transform()
                                    if newt != old:
                                        items_states.append(('transform', it, old, newt))
                                except Exception:
                                    # also check pos fallback
                                    try:
                                        newpos = it.pos()
                                        if newpos != old:
                                            items_states.append(('pos', it, old, newpos))
                                    except Exception:
                                        continue
                        except Exception:
                            continue
                    if items_states:
                        from edit.commands import MoveItemsCommand
                        cmd = MoveItemsCommand(self, items_states)
                        self.edit_manager.push_undo(cmd)
            except Exception:
                pass

            # 旋转交互结束：如果处于旋转跟踪状态，则根据最终角度计算新状态并记录为 RotateCommand
            try:
                tracking = getattr(self, '_rotate_tracking', None)
                if tracking:
                    # 计算当前角度
                    px, py = tracking[0][3]
                    cur_angle = math.atan2(y - py, x - px)
                    delta = math.degrees(cur_angle - (self._rotate_start_angle or 0.0))
                    items_states = []
                    for kind, it, old, pivot in tracking:
                        cx, cy = pivot
                        if kind == 'path':
                            new_pts = []
                            rad = math.radians(delta)
                            cosv = math.cos(rad); sinv = math.sin(rad)
                            for px0, py0 in old:
                                dx = px0 - cx; dy = py0 - cy
                                nx = cx + dx * cosv - dy * sinv
                                ny = cy + dx * sinv + dy * cosv
                                new_pts.append((nx, ny))
                            # 应用最终点并记录状态
                            try:
                                it.set_points(new_pts)
                            except Exception:
                                pass
                            items_states.append(('path', it, old, new_pts))
                        else:
                            try:
                                m = QTransform()
                                m.translate(cx, cy)
                                m.rotate(delta)
                                m.translate(-cx, -cy)
                                oldt = old
                                try:
                                    newt = m * oldt
                                except Exception:
                                    newt = m
                                try:
                                    it.setTransform(newt)
                                except Exception:
                                    pass
                                items_states.append(('transform', it, oldt, newt))
                            except Exception:
                                continue
                    if items_states:
                        from edit.commands import RotateCommand
                        cmd = RotateCommand(self, items_states)
                        # 旋转已应用，直接记录到历史
                        self.edit_manager.push_undo(cmd)
                    # 清理旋转状态
                    self._rotate_tracking = None
                    self._rotate_start_angle = None
            except Exception:
                # 清理旋转状态，避免残留
                try:
                    self._rotate_tracking = None
                    self._rotate_start_angle = None
                except Exception:
                    pass

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
