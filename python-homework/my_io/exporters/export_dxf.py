
import logging
from typing import List, Tuple
import ezdxf

# 移除显式导入，改为鸭子类型检查，解决循环依赖或导入失败问题
# try:
#     from ui.graphics_items import EditablePathItem, EditableEllipseItem
# except ImportError:
#     EditablePathItem = None
#     EditableEllipseItem = None

logger = logging.getLogger(__name__)

def export_to_dxf(canvas, filename: str, allowed_colors: List[str] = None):
    """
    导出画布内容为 DXF 文件
    :param canvas: 画布对象 (WhiteboardCanvas)
    :param filename: 保存的文件路径
    :param allowed_colors: 允许导出的颜色列表 (Hex字符串)，为None则导出所有
    """
    try:
        # 创建 DXF 文档 (R2010 版本兼容性较好)
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        
        count = 0
        
        # 获取场景中的所有项
        if not hasattr(canvas, 'scene') or not canvas.scene:
            logger.warning("画布没有场景，无法导出")
            return 0
            
        # 收集需要导出的项
        items_to_process = []
        for item in canvas.scene.items():
            try:
                if not item.isVisible():
                    continue
                    
                # 过滤系统辅助项 (网格、原点、激光头等)
                if _is_system_item(item, canvas):
                    continue
                
                # 颜色过滤 (如果实现了颜色属性)
                if allowed_colors is not None:
                     # 尝试获取颜色
                     item_color = None
                     if hasattr(item, 'color'):
                         c = item.color()
                         if c: item_color = c.name().upper() # #RRGGBB
                     elif hasattr(item, 'pen'):
                         c = item.pen().color()
                         if c: item_color = c.name().upper()
                     
                     if item_color and item_color not in allowed_colors:
                         continue

                items_to_process.append(item)
            except Exception as e:
                logger.warning(f"检查导出项时出错: {e}")

        # 遍历处理 - 使用鸭子类型(Duck Typing)而非强类型检查，避免导入依赖问题
        for item in items_to_process:
            # 1. 优先尝试导出为椭圆/圆 (EditableEllipseItem 等)
            # 因为某些圆对象可能同时也具备 points() 方法 (如果在其他地方被扩展了)
            # 但在这里，EditableEllipseItem 没有 points() 方法。
            # 为了安全起见，我们还是先检查 get_params
            
            is_processed = False
            
            if hasattr(item, 'get_params') and callable(getattr(item, 'get_params')):
                try:
                    cx, cy, rx, ry = item.get_params()
                    # 检查是否为圆 (半径差异极小)
                    if abs(rx - ry) < 1e-4:
                        msp.add_circle((cx, cy), rx)
                    else:
                        msp.add_ellipse((cx, cy), major_axis=(rx, 0), ratio=ry/rx)
                    count += 1
                    is_processed = True
                except Exception as e:
                    logger.error(f"导出椭圆项失败: {str(e)}")
            
            # 2. 矢量路径 (EditablePathItem 等)
            if not is_processed and hasattr(item, 'points') and callable(getattr(item, 'points')):
                try:
                    points = item.points()
                    if points and len(points) >= 2:
                        # Ezdxf 接受 [(x, y), ...] 列表
                        msp.add_lwpolyline(points)
                        count += 1
                        is_processed = True
                except Exception as e:
                    logger.error(f"导出路径项失败: {str(e)}")

            # 3. 矩形 (QGraphicsRectItem 等 - 或者是具有 rect() 方法的项)
            if not is_processed and hasattr(item, 'rect') and callable(getattr(item, 'rect')):
                # 注意：很多项都有 rect() (如 boundingRect)，但 QGraphicsRectItem 的 rect() 是定义形状的核心
                # 我们需要区分。通常 QGraphicsRectItem 是标准矩形。
                # 简单检查类名包含 'RectItem' 或者 duck typing 检查无法区分 bounding rect。
                # 最好检查是否是 QGraphicsRectItem 的实例 (但是为了避免导入依赖，我们检查类名)
                class_name = item.__class__.__name__
                if 'RectItem' in class_name:
                    try:
                        r = item.rect()
                        # 获取矩形的四个角 (局部坐标)
                        pts = [
                            (r.left(), r.top()),
                            (r.right(), r.top()),
                            (r.right(), r.bottom()),
                            (r.left(), r.bottom())
                        ]
                        # 转换到场景坐标 (处理矩形本身的移动/旋转)
                        # 注意：如果 item 有变换矩阵，需要应用它
                        scene_pts = []
                        transform = item.sceneTransform()
                        for x, y in pts:
                            from PyQt5.QtCore import QPointF
                            p = transform.map(QPointF(x, y))
                            scene_pts.append((p.x(), p.y()))
                        
                        # 闭合
                        scene_pts.append(scene_pts[0])
                        
                        msp.add_lwpolyline(scene_pts)
                        count += 1
                        is_processed = True
                    except Exception as e:
                        logger.error(f"导出矩形项失败: {str(e)}")

            # 4. 文字 (TextGraphicsItem - 具有 text_data 属性)
            if not is_processed and hasattr(item, 'text_data'):
                try:
                    text_content = item.text_data
                    if text_content:
                        # 获取位置
                        pos = item.scenePos()
                        # 添加文字
                        dxf_text = msp.add_text(text_content, dxfattribs={
                            'height': 10.0 # 默认高度，或者尝试从 item 解析高度
                        })
                        dxf_text.set_pos((pos.x(), pos.y()), align='LEFT')
                        
                        # 尝试获取字体大小/旋转
                        rotation = item.rotation()
                        if abs(rotation) > 1e-4:
                            dxf_text.dxf.rotation = rotation
                            
                        # 如果有 settings 属性，尝试获取高度 (针对 TextGraphicsItem)
                        if hasattr(item, 'settings') and isinstance(item.settings, dict):
                            h = item.settings.get('height', 10.0)
                            if h > 0:
                                dxf_text.dxf.height = h
                                
                        count += 1
                        is_processed = True
                except Exception as e:
                    logger.error(f"导出文字项失败: {str(e)}")

            if not is_processed:
                # 5. 其他类型的 QGraphicsItem (如 QGraphicsPathItem 但没有 points 方法)
                # 或者是 DrawTool 产生的临时 Line/Poly (其实它们就是 EditablePathItem)
                pass
            
        doc.saveas(filename)
        logger.info(f"成功导出 DXF: {filename}, 包含 {count} 个实体")
        return count

    except Exception as e:
        logger.error(f"DXF 导出严重错误: {str(e)}")
        raise e

def _is_system_item(item, canvas) -> bool:
    """判断是否为系统项"""
    try:
        # 1. 检查具名属性
        system_attrs = ['_work_item', '_fiducial_item', '_grid_item', '_laser_head_item', '_origin_item', '_path_preview_item']
        for attr in system_attrs:
            if hasattr(canvas, attr) and getattr(canvas, attr) == item:
                return True
        
        # 2. 检查列表属性 (如工作区元素、缩放手柄等)
        list_attrs = ['_workarea_items', '_scale_handles']
        for attr in list_attrs:
            if hasattr(canvas, attr):
                lst = getattr(canvas, attr)
                if isinstance(lst, list) and item in lst:
                    return True
                    
        # 3. 检查特殊类型 (如 _DragHandle)
        # 防止导出未注册到列表但在场景中的编辑手柄
        class_name = item.__class__.__name__
        if '_DragHandle' in class_name:
            return True
            
    except Exception:
        pass
    return False
