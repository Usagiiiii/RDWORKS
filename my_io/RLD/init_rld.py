#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RLD文件格式定义和序列化模块
RLD (Raster Laser Design) - 光栅激光设计文件格式
"""

import json
import base64
import logging
from typing import Dict, List, Any, Optional, Tuple
from PyQt5.QtGui import QColor, QPixmap, QImage, QTransform
from PyQt5.QtCore import QPointF, QBuffer, QIODevice
from PyQt5.QtWidgets import QGraphicsPixmapItem
import os

logger = logging.getLogger(__name__)


class RLDFileFormat:
    """RLD文件格式定义"""

    # 文件魔数和版本
    MAGIC_NUMBER = b'RLDF'
    VERSION = 1

    # 支持的文件扩展名
    EXTENSIONS = ['.rld', '.rldf']

    @staticmethod
    def serialize_scene(canvas) -> Dict[str, Any]:
        """
        序列化画布场景到RLD格式
        """
        try:
            scene_data = {
                'version': RLDFileFormat.VERSION,
                'metadata': {
                    'work_area_width': getattr(canvas, '_work_w', 600.0),
                    'work_area_height': getattr(canvas, '_work_h', 400.0),
                    'total_items': len(canvas.scene.items()) if hasattr(canvas, 'scene') and canvas.scene else 0
                },
                'items': []
            }

            # 序列化所有图形项
            if hasattr(canvas, 'scene'):
                for item in canvas.scene.items():
                    item_data = RLDFileFormat._serialize_item(item)
                    if item_data:
                        scene_data['items'].append(item_data)

            # 序列化定位点
            fiducial_data = RLDFileFormat._serialize_fiducial(canvas)
            if fiducial_data:
                scene_data['fiducial'] = fiducial_data

            return scene_data

        except Exception as e:
            logger.error(f"序列化场景失败: {e}")
            raise

    @staticmethod
    def _serialize_item(item) -> Optional[Dict[str, Any]]:
        """序列化单个图形项"""
        try:
            # 可编辑路径项（矢量图形）
            if hasattr(item, '_points') and hasattr(item, 'points'):
                return RLDFileFormat._serialize_path_item(item)

            # 图片项（修复：统一方法命名为英文）
            elif isinstance(item, QGraphicsPixmapItem):
                if not item.pixmap().isNull():
                    return RLDFileFormat._serialize_image_item(item)  # 修复命名

            # 忽略工作区网格和其他系统项
            elif hasattr(item, '_work_item') and item == getattr(item, '_work_item', None):
                return None

        except Exception as e:
            logger.warning(f"序列化图形项失败: {e}")

        return None

    @staticmethod
    def _serialize_path_item(item) -> Dict[str, Any]:
        """序列化路径项"""
        points = item.points() if hasattr(item, 'points') else getattr(item, '_points', [])

        # 获取颜色
        color = QColor(0, 0, 0)  # 默认黑色
        if hasattr(item, 'pen') and item.pen():
            color = item.pen().color()

        return {
            'type': 'path',
            'points': points,
            'color': {
                'r': color.red(),
                'g': color.green(),
                'b': color.blue(),
                'a': color.alpha()
            },
            'position': {
                'x': item.x() if hasattr(item, 'x') else item.scenePos().x(),
                'y': item.y() if hasattr(item, 'y') else item.scenePos().y()
            },
            'z_value': item.zValue()
        }

    @staticmethod
    def _serialize_image_item(item) -> Optional[Dict[str, Any]]:
        """序列化图片项（修复：统一方法名为英文）"""
        try:
            pixmap = item.pixmap()
            if pixmap.isNull():
                logger.warning("图片项pixmap为空")
                return None

            # 使用QBuffer保存图片数据（优化：确保缓冲区正确处理）
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)

            # 强制使用PNG格式保存，确保兼容性
            success = pixmap.save(buffer, "PNG", 95)  # 添加质量参数（0-100）
            if not success:
                logger.error("保存图片到缓冲区失败")
                return None

            # 获取字节数据并编码为Base64
            image_data = base64.b64encode(buffer.data()).decode('utf-8')
            buffer.close()

            # 获取完整的变换信息（包含缩放、旋转等）
            transform = item.transform()

            return {
                'type': 'image',
                'image_data': image_data,
                'format': 'PNG',
                'position': {
                    'x': item.scenePos().x(),
                    'y': item.scenePos().y()
                },
                'transform': {
                    'm11': transform.m11(),  # 缩放X
                    'm12': transform.m12(),  # 剪切X
                    'm21': transform.m21(),  # 剪切Y
                    'm22': transform.m22(),  # 缩放Y
                    'dx': transform.dx(),  # 平移X
                    'dy': transform.dy()  # 平移Y
                },
                'z_value': item.zValue(),
                'bounding_rect': {
                    'x': item.boundingRect().x(),
                    'y': item.boundingRect().y(),
                    'width': item.boundingRect().width(),
                    'height': item.boundingRect().height()
                }
            }
        except Exception as e:
            logger.error(f"序列化图片项失败: {e}")
            return None

    @staticmethod
    def _serialize_fiducial(canvas) -> Optional[Dict[str, Any]]:
        """序列化定位点"""
        try:
            # 适配whiteboard.py中的定位点存储方式
            if hasattr(canvas, '_fiducial') and canvas._fiducial:
                point, shape = canvas._fiducial
                return {
                    'point': point,
                    'shape': shape,
                    'size': getattr(canvas, '_fiducial_size', 10.0)
                }
            # 兼容fiducial_manager的情况
            fiducial_manager = getattr(canvas, 'fiducial_manager', None)
            if fiducial_manager:
                fiducial = fiducial_manager.get_fiducial()
                if fiducial:
                    point, shape = fiducial
                    return {
                        'point': point,
                        'shape': shape,
                        'size': getattr(fiducial_manager, '_fiducial_size', 10.0)
                    }
        except Exception as e:
            logger.warning(f"序列化定位点失败: {e}")

        return None

    @staticmethod
    def deserialize_to_scene(canvas, data: Dict[str, Any]):
        """
        从RLD格式反序列化到画布场景
        """
        try:
            # 清空画布（保留工作区）
            if hasattr(canvas, 'scene'):
                # 先移除所有用户项，保留系统项（网格等）
                for item in canvas.scene.items():
                    if not (hasattr(item, '_work_item') and item == getattr(item, '_work_item', None)):
                        canvas.scene.removeItem(item)
                # 重新绘制工作区（如果需要）
                if hasattr(canvas, '_draw_workarea'):
                    canvas._draw_workarea()

            # 检查版本兼容性
            version = data.get('version', 0)
            if version > RLDFileFormat.VERSION:
                logger.warning(f"文件版本 {version} 高于当前支持版本 {RLDFileFormat.VERSION}")

            # 恢复工作区尺寸
            metadata = data.get('metadata', {})
            if hasattr(canvas, '_work_w'):
                canvas._work_w = metadata.get('work_area_width', 600.0)
            if hasattr(canvas, '_work_h'):
                canvas._work_h = metadata.get('work_area_height', 400.0)

            # 反序列化图形项
            items_data = data.get('items', [])
            for item_data in items_data:
                RLDFileFormat._deserialize_item(canvas, item_data)

            # 反序列化定位点
            fiducial_data = data.get('fiducial')
            if fiducial_data:
                RLDFileFormat._deserialize_fiducial(canvas, fiducial_data)

            # 刷新视图
            if hasattr(canvas, 'fit_all'):
                canvas.fit_all()
            logger.info(f"成功加载RLD文件，包含 {len(items_data)} 个图形项")

        except Exception as e:
            logger.error(f"反序列化场景失败: {e}")
            raise

    @staticmethod
    def _deserialize_item(canvas, item_data: Dict[str, Any]):
        """反序列化单个图形项"""
        try:
            item_type = item_data.get('type')

            if item_type == 'path':
                RLDFileFormat._deserialize_path_item(canvas, item_data)
            elif item_type == 'image':
                RLDFileFormat._deserialize_image_item(canvas, item_data)

        except Exception as e:
            logger.warning(f"反序列化图形项失败: {e}")

    @staticmethod
    def _deserialize_path_item(canvas, item_data: Dict[str, Any]):
        """反序列化路径项"""
        # 需要从其他模块导入EditablePathItem
        try:
            from ui.whiteboard import EditablePathItem
        except ImportError:
            logger.error("无法导入EditablePathItem，跳过路径反序列化")
            return

        points = item_data.get('points', [])
        color_data = item_data.get('color', {})
        position = item_data.get('position', {})

        # 创建颜色
        color = QColor(
            color_data.get('r', 0),
            color_data.get('g', 0),
            color_data.get('b', 0),
            color_data.get('a', 255)
        )

        # 创建路径项
        item = EditablePathItem(points, color)
        item.setPos(position.get('x', 0), position.get('y', 0))
        item.setZValue(item_data.get('z_value', 0))

        if hasattr(canvas, 'scene'):
            canvas.scene.addItem(item)

    @staticmethod
    def _deserialize_image_item(canvas, item_data: Dict[str, Any]):
        """反序列化图片项（增强兼容性）"""
        try:
            image_data = item_data.get('image_data', '')
            if not image_data:
                logger.warning("图片数据为空")
                return

            position = item_data.get('position', {})
            transform_data = item_data.get('transform', {})

            # 解码Base64图片数据
            try:
                image_bytes = base64.b64decode(image_data)
            except Exception as e:
                logger.error(f"Base64解码失败: {e}")
                return

            # 从数据加载图片（优化：增加格式自动识别）
            pixmap = QPixmap()
            success = pixmap.loadFromData(image_bytes)  # 自动识别格式

            if not success or pixmap.isNull():
                logger.warning("图片数据解码失败，尝试强制PNG格式")
                success = pixmap.loadFromData(image_bytes, "PNG")
                if not success:
                    logger.error("图片加载彻底失败")
                    return

            # 创建图片项并添加到场景
            if hasattr(canvas, 'scene'):
                item = canvas.scene.addPixmap(pixmap)
                item.setPos(position.get('x', 0), position.get('y', 0))
                item.setZValue(item_data.get('z_value', 0))

                # 应用完整变换矩阵（包含缩放、旋转等）
                if transform_data:
                    transform = QTransform(
                        transform_data.get('m11', 1.0),
                        transform_data.get('m12', 0.0),
                        transform_data.get('m21', 0.0),
                        transform_data.get('m22', 1.0),
                        transform_data.get('dx', 0.0),
                        transform_data.get('dy', 0.0)
                    )
                    item.setTransform(transform)

                # 确保图片可交互
                item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
                item.setFlag(QGraphicsPixmapItem.ItemIsFocusable, False)  # 不需要焦点

                logger.info(f"成功反序列化图片项，位置: ({position.get('x', 0)}, {position.get('y', 0)})")

        except Exception as e:
            logger.error(f"反序列化图片项失败: {e}")

    @staticmethod
    def _deserialize_fiducial(canvas, fiducial_data: Dict[str, Any]):
        """反序列化定位点（适配whiteboard.py）"""
        try:
            point = fiducial_data.get('point', (0, 0))
            shape = fiducial_data.get('shape', 'cross')
            size = fiducial_data.get('size', 10.0)

            # 适配whiteboard.py中的定位点方法
            if hasattr(canvas, 'set_fiducial_size'):
                canvas.set_fiducial_size(size)
            if hasattr(canvas, 'add_fiducial'):
                canvas.add_fiducial(point, shape)
            # 兼容fiducial_manager的情况
            else:
                fiducial_manager = getattr(canvas, 'fiducial_manager', None)
                if fiducial_manager:
                    fiducial_manager.set_fiducial_size(size)
                    fiducial_manager.add_fiducial(point, shape)

        except Exception as e:
            logger.warning(f"反序列化定位点失败: {e}")


class RLDFileHandler:
    """RLD文件读写处理器"""

    @staticmethod
    def save_to_file(canvas, filename: str) -> bool:
        """
        保存画布内容到RLD文件
        """
        try:
            # 序列化场景数据
            scene_data = RLDFileFormat.serialize_scene(canvas)

            # 添加文件头信息
            file_data = {
                'file_format': 'RLD',
                'version': RLDFileFormat.VERSION,
                'scene': scene_data
            }

            # 写入文件（优化：确保目录存在）
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2, ensure_ascii=False)

            logger.info(f"成功保存RLD文件: {filename}")
            return True

        except Exception as e:
            logger.error(f"保存RLD文件失败: {e}")
            return False

    @staticmethod
    def load_from_file(canvas, filename: str) -> bool:
        """
        从RLD文件加载画布内容
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(filename):
                logger.error(f"文件不存在: {filename}")
                return False

            # 读取文件
            with open(filename, 'r', encoding='utf-8') as f:
                file_data = json.load(f)

            # 验证文件格式
            if file_data.get('file_format') != 'RLD':
                logger.error("无效的RLD文件格式")
                return False

            # 反序列化场景数据
            scene_data = file_data.get('scene', {})
            RLDFileFormat.deserialize_to_scene(canvas, scene_data)

            logger.info(f"成功加载RLD文件: {filename}")
            return True

        except Exception as e:
            logger.error(f"加载RLD文件失败: {e}")
            return False

    @staticmethod
    def is_rld_file(filename: str) -> bool:
        """检查文件是否为RLD格式"""
        if not filename or not os.path.exists(filename):
            return False

        # 检查扩展名
        if any(filename.lower().endswith(ext) for ext in RLDFileFormat.EXTENSIONS):
            return True

        # 检查文件内容
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('file_format') == 'RLD'
        except:
            return False