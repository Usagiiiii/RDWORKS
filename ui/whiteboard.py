#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白板部件类
实现白板的绘图、缩放、标尺等功能
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea
from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt5.QtGui import (QPainter, QPen, QColor, QPixmap, QBrush, QFont, 
                        QPainterPath, QWheelEvent, QImage)
import math


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
        
        # 计算刻度间隔（画布坐标系）
        base_interval = 50  # 基础间隔（像素）
        
        # 根据缩放调整间隔，保证屏幕上的间隔合理
        screen_interval = base_interval * self.zoom
        
        # 动态调整基础间隔以适应缩放
        if screen_interval < 30:
            # 屏幕间隔太小，增大基础间隔
            multiplier = math.ceil(30 / screen_interval)
            base_interval *= multiplier
            screen_interval = base_interval * self.zoom
        elif screen_interval > 150:
            # 屏幕间隔太大，减小基础间隔
            multiplier = math.ceil(screen_interval / 100)
            base_interval /= multiplier
            screen_interval = base_interval * self.zoom
            
        # 计算第一个刻度在画布坐标系中的位置
        # offset是屏幕偏移，需要转换为画布坐标
        canvas_start = -self.offset / self.zoom if self.zoom > 0 else 0
        
        # 找到第一个刻度对齐的位置（向下取整到base_interval的倍数）
        first_tick = math.floor(canvas_start / base_interval) * base_interval
        
        # 绘制刻度
        tick_value = first_tick
        while True:
            # 计算这个刻度在屏幕上的位置
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
        
        # 计算刻度间隔（画布坐标系）
        base_interval = 50  # 基础间隔（像素）
        
        # 根据缩放调整间隔，保证屏幕上的间隔合理
        screen_interval = base_interval * self.zoom
        
        # 动态调整基础间隔以适应缩放
        if screen_interval < 30:
            multiplier = math.ceil(30 / screen_interval)
            base_interval *= multiplier
            screen_interval = base_interval * self.zoom
        elif screen_interval > 150:
            multiplier = math.ceil(screen_interval / 100)
            base_interval /= multiplier
            screen_interval = base_interval * self.zoom
            
        # 计算第一个刻度在画布坐标系中的位置
        canvas_start = -self.offset / self.zoom if self.zoom > 0 else 0
        
        # 找到第一个刻度对齐的位置
        first_tick = math.floor(canvas_start / base_interval) * base_interval
        
        # 绘制刻度
        tick_value = first_tick
        while True:
            # 计算这个刻度在屏幕上的位置
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


class CanvasWidget(QWidget):
    """画布部件"""
    
    zoom_changed = pyqtSignal(float)
    offset_changed = pyqtSignal(QPoint)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 画布大小（虚拟画布，可以很大）
        self.canvas_width = 5000
        self.canvas_height = 5000
        
        # 缩放和平移
        self.zoom = 1.0
        # 初始偏移：让画布中心点(0,0)显示在视图左上方附近
        # 这样标尺就会从负数开始，类似原图
        self.offset = QPoint(200, 100)
        self.panning = False
        self.last_pan_point = QPoint()
        
        # 绘图相关
        # 关闭绘制功能（禁用鼠标绘画）
        self.allow_drawing = False
        self.drawing = False
        self.last_point = QPoint()
        self.current_tool = 'pen'
        self.pen_color = QColor(0, 0, 0)
        self.pen_width = 2
        
        # 图形缓存 - 使用虚拟画布
        self.image = QPixmap(self.canvas_width, self.canvas_height)
        self.image.fill(Qt.white)
        
        # 临时图形
        self.temp_image = None
        self.temp_start_point = None
        
        # 历史记录
        self.history = []
        self.history_index = -1
        self.max_history = 50
        
        # 保存初始状态
        self.save_state()
        
        # 设置最小尺寸
        self.setMinimumSize(800, 600)
        
        # 启用鼠标跟踪
        self.setMouseTracking(True)
        
    def set_tool(self, tool):
        """设置当前工具"""
        self.current_tool = tool
        
    def set_pen_color(self, color):
        """设置画笔颜色"""
        self.pen_color = color
        
    def set_pen_width(self, width):
        """设置画笔宽度"""
        self.pen_width = width
        
    def clear(self):
        """清空画布"""
        self.image.fill(Qt.white)
        self.save_state()
        self.update()
        
    def save_state(self):
        """保存当前状态到历史记录"""
        # 删除当前位置之后的历史
        self.history = self.history[:self.history_index + 1]
        
        # 添加新状态
        self.history.append(self.image.copy())
        self.history_index += 1
        
        # 限制历史记录数量
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.history_index -= 1
            
    def undo(self):
        """撤销"""
        if self.history_index > 0:
            self.history_index -= 1
            self.image = self.history[self.history_index].copy()
            self.update()
            
    def redo(self):
        """重做"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.image = self.history[self.history_index].copy()
            self.update()
            
    def zoom_in(self):
        """放大"""
        self.zoom = min(self.zoom * 1.2, 10.0)
        self.zoom_changed.emit(self.zoom)
        self.update()
        
    def zoom_out(self):
        """缩小"""
        self.zoom = max(self.zoom / 1.2, 0.1)
        self.zoom_changed.emit(self.zoom)
        self.update()
        
    def zoom_reset(self):
        """重置缩放"""
        self.zoom = 1.0
        self.zoom_changed.emit(self.zoom)
        self.update()
        
    def get_zoom_percent(self):
        """获取缩放百分比"""
        return int(self.zoom * 100)
        
    def export_image(self, filename):
        """导出图像"""
        self.image.save(filename)
        
    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮事件 - 实现缩放"""
        # 获取鼠标位置
        mouse_pos = event.pos()
        
        # 计算鼠标在画布上的位置（缩放前）
        canvas_pos_before = self.screen_to_canvas(mouse_pos)
        
        # 执行缩放
        if event.angleDelta().y() > 0:
            self.zoom = min(self.zoom * 1.1, 10.0)
        else:
            self.zoom = max(self.zoom / 1.1, 0.1)
            
        # 计算鼠标在画布上的位置（缩放后）
        canvas_pos_after = self.screen_to_canvas(mouse_pos)
        
        # 调整偏移量，使鼠标位置保持不变
        delta = canvas_pos_after - canvas_pos_before
        self.offset -= QPoint(int(delta.x() * self.zoom), int(delta.y() * self.zoom))
        
        self.zoom_changed.emit(self.zoom)
        self.offset_changed.emit(self.offset)
        self.update()
        
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MiddleButton or \
           (event.button() == Qt.LeftButton and event.modifiers() & Qt.ControlModifier):
            # 中键或Ctrl+左键开始平移
            self.panning = True
            self.last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.LeftButton:
            # 左键绘图已禁用
            if self.allow_drawing:
                self.drawing = True
                self.last_point = self.screen_to_canvas(event.pos())
                if self.current_tool in ['line', 'rectangle', 'circle']:
                    self.temp_start_point = self.last_point
                    self.temp_image = self.image.copy()
            else:
                event.ignore()
                
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.panning:
            # 平移画布
            delta = event.pos() - self.last_pan_point
            self.offset += delta
            self.last_pan_point = event.pos()
            self.offset_changed.emit(self.offset)
            self.update()
        elif self.drawing and self.allow_drawing:
            current_point = self.screen_to_canvas(event.pos())
            
            if self.current_tool == 'pen':
                self.draw_line_on_image(self.last_point, current_point)
                self.last_point = current_point
                self.update()
            elif self.current_tool == 'eraser':
                self.erase_line(self.last_point, current_point)
                self.last_point = current_point
                self.update()
            elif self.current_tool in ['line', 'rectangle', 'circle']:
                # 绘制临时图形
                self.update()
                
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.MiddleButton or \
           (event.button() == Qt.LeftButton and self.panning):
            # 结束平移
            self.panning = False
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.LeftButton and self.drawing and self.allow_drawing:
            # 结束绘图
            self.drawing = False
            
            if self.current_tool in ['line', 'rectangle', 'circle']:
                current_point = self.screen_to_canvas(event.pos())
                self.draw_shape(self.temp_start_point, current_point)
                self.temp_image = None
                self.temp_start_point = None
            
            self.save_state()
            self.update()
            
    def screen_to_canvas(self, screen_pos):
        """屏幕坐标转画布坐标"""
        # 屏幕坐标 -> 画布坐标
        # canvas = (screen - offset) / zoom
        x = (screen_pos.x() - self.offset.x()) / self.zoom
        y = (screen_pos.y() - self.offset.y()) / self.zoom
        return QPoint(int(x), int(y))
        
    def canvas_to_screen(self, canvas_pos):
        """画布坐标转屏幕坐标"""
        # 画布坐标 -> 屏幕坐标
        # screen = canvas * zoom + offset
        x = canvas_pos.x() * self.zoom + self.offset.x()
        y = canvas_pos.y() * self.zoom + self.offset.y()
        return QPoint(int(x), int(y))
        
    def draw_line_on_image(self, start, end):
        """在图像上绘制线条"""
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, 
                  Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(start, end)
        
    def erase_line(self, start, end):
        """擦除线条"""
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(Qt.white, self.pen_width * 3, Qt.SolidLine, 
                  Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(start, end)
        
    def draw_shape(self, start, end):
        """绘制图形"""
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine)
        painter.setPen(pen)
        
        if self.current_tool == 'line':
            painter.drawLine(start, end)
        elif self.current_tool == 'rectangle':
            rect = QRect(start, end).normalized()
            painter.drawRect(rect)
        elif self.current_tool == 'circle':
            rect = QRect(start, end).normalized()
            painter.drawEllipse(rect)
            
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制浅灰色背景（画布外区域）
        painter.fillRect(self.rect(), QColor(245, 245, 245))
        
        # 计算画布在屏幕上的可见区域
        canvas_rect_screen = QRect(
            int(self.offset.x()),
            int(self.offset.y()),
            int(self.canvas_width * self.zoom),
            int(self.canvas_height * self.zoom)
        )
        
        # 绘制白色画布背景
        painter.fillRect(canvas_rect_screen, Qt.white)
        
        # 保存变换状态
        painter.save()
        
        # 应用缩放和平移变换
        painter.translate(self.offset)
        painter.scale(self.zoom, self.zoom)
        
        # 绘制画布内容
        painter.drawPixmap(0, 0, self.image)
        
        # 绘制临时图形
        if self.drawing and self.current_tool in ['line', 'rectangle', 'circle'] and \
           self.temp_start_point:
            # 获取当前鼠标位置（相对于widget）
            cursor_pos = self.mapFromGlobal(self.cursor().pos())
            current_point = self.screen_to_canvas(cursor_pos)
            
            pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine)
            painter.setPen(pen)
            
            if self.current_tool == 'line':
                painter.drawLine(self.temp_start_point, current_point)
            elif self.current_tool == 'rectangle':
                rect = QRect(self.temp_start_point, current_point).normalized()
                painter.drawRect(rect)
            elif self.current_tool == 'circle':
                rect = QRect(self.temp_start_point, current_point).normalized()
                painter.drawEllipse(rect)
        
        painter.restore()
        
        # 绘制画布边框
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        painter.drawRect(canvas_rect_screen.adjusted(0, 0, -1, -1))


class WhiteboardWidget(QWidget):
    """白板部件（包含标尺和画布）"""
    
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
        
        # 创建画布
        self.canvas = CanvasWidget()
        
        # 连接信号
        self.canvas.zoom_changed.connect(self.on_zoom_changed)
        self.canvas.offset_changed.connect(self.on_offset_changed)
        
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
        
    def on_zoom_changed(self, zoom):
        """缩放改变"""
        self.h_ruler.set_zoom(zoom)
        self.v_ruler.set_zoom(zoom)
        
    def on_offset_changed(self, offset):
        """偏移改变"""
        # 传递屏幕偏移给标尺
        self.h_ruler.set_offset(offset.x())
        self.v_ruler.set_offset(offset.y())
        # 同时更新缩放，确保标尺计算正确
        self.h_ruler.set_zoom(self.canvas.zoom)
        self.v_ruler.set_zoom(self.canvas.zoom)
        
    # 转发画布方法
    def set_tool(self, tool):
        self.canvas.set_tool(tool)
        
    def set_pen_color(self, color):
        self.canvas.set_pen_color(color)
        
    def set_pen_width(self, width):
        self.canvas.set_pen_width(width)
        
    def clear(self):
        self.canvas.clear()
        
    def undo(self):
        self.canvas.undo()
        
    def redo(self):
        self.canvas.redo()
        
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

