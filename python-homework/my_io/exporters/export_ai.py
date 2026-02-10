from typing import List, Tuple
import logging
import math

logger = logging.getLogger(__name__)

def export_to_ai(canvas, filename: str, allowed_colors: List[str] = None):
    """
    导出画布内容为 AI (作为 EPS 格式)
    使用 PostScript Level 3
    """
    scale_factor = 72.0 / 25.4 # 1 mm = ~2.83 pt
    
    try:
        # 获取画布高度用于坐标翻转 (PS原点在左下)
        page_h = 400.0 # 默认
        page_w = 600.0 # 默认
        if hasattr(canvas, '_work_h'): page_h = float(canvas._work_h)
        if hasattr(canvas, '_work_w'): page_w = float(canvas._work_w)
        
        # 计算 BoundingBox (Point units)
        bb_w = int(page_w * scale_factor)
        bb_h = int(page_h * scale_factor)
        
        with open(filename, 'w', encoding='utf-8') as f:
            # EPS Header
            f.write(f"%!PS-Adobe-3.0 EPSF-3.0\n")
            f.write(f"%%BoundingBox: 0 0 {bb_w} {bb_h}\n")
            f.write(f"%%Creator: RDWorks Python Exporter\n")
            f.write(f"%%Title: {filename}\n")
            f.write(f"%%EndComments\n")
            
            # Setup
            f.write("1 setlinecap 1 setlinejoin\n") # 圆角端点和连接
            
            count = 0
            items = _get_exportable_items(canvas, allowed_colors)
            
            for item in items:
                points = []
                # 获取点数据
                if hasattr(item, 'points') and callable(item.points):
                    points = item.points()
                elif hasattr(item, 'get_params') and callable(item.get_params):
                    cx, cy, rx, ry = item.get_params()
                    steps = max(32, int(max(rx, ry) * 2))
                    points = []
                    for i in range(steps + 1):
                        angle = 2 * math.pi * i / steps
                        x = cx + rx * math.cos(angle)
                        y = cy + ry * math.sin(angle)
                        points.append((x, y))
                elif hasattr(item, 'rect') and callable(item.rect):
                    r = item.rect()
                    transform = item.sceneTransform()
                    ps = [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]
                    points = [(transform.map(p).x(), transform.map(p).y()) for p in ps]
                    points.append(points[0]) # Close
                
                if not points or len(points) < 2:
                    continue
                    
                # 写入路径
                f.write("newpath\n")
                
                first = True
                for x, y in points:
                    # 转换坐标: mm -> pt, 且翻转 Y
                    px = x * scale_factor
                    py = (page_h - y) * scale_factor 
                    
                    if first:
                        f.write(f"{px:.3f} {py:.3f} moveto\n")
                        first = False
                    else:
                        f.write(f"{px:.3f} {py:.3f} lineto\n")
                
                # 获取颜色
                color_str = "0 0 0" # Default Black
                if hasattr(item, 'pen'):
                    c = item.pen().color()
                    # RGB to required format (0-1)
                    r = c.redF()
                    g = c.greenF()
                    b = c.blueF()
                    color_str = f"{r:.3f} {g:.3f} {b:.3f}"
                
                f.write(f"{color_str} setrgbcolor\n")
                f.write("stroke\n")
                count += 1
                
            f.write("%%EOF\n")
            
        logger.info(f"成功导出 AI(EPS): {filename}, 包含 {count} 个路径")
        return True
        
    except Exception as e:
        logger.error(f"AI 导出错误: {str(e)}")
        return False

def _get_exportable_items(canvas, allowed_colors):
    # 复用过滤逻辑
    export_list = []
    if not hasattr(canvas, 'scene') or not canvas.scene:
        return []
        
    for item in canvas.scene.items():
        if not item.isVisible(): continue
        
        # 排除系统项
        system_attrs = ['_work_item', '_fiducial_item', '_grid_item', '_laser_head_item', '_origin_item', '_path_preview_item']
        is_sys = False
        for attr in system_attrs:
            if hasattr(canvas, attr) and getattr(canvas, attr) == item:
                is_sys = True
                break
        
        if hasattr(canvas, '_workarea_items') and isinstance(canvas._workarea_items, list):
            if item in canvas._workarea_items: is_sys = True
            
        if hasattr(canvas, '_scale_handles') and isinstance(canvas._scale_handles, list):
            if item in canvas._scale_handles: is_sys = True

        if '_DragHandle' in item.__class__.__name__: is_sys = True
        
        if is_sys: continue
        
        # 颜色检查
        if allowed_colors:
             item_color = None
             if hasattr(item, 'pen'):
                 c = item.pen().color()
                 if c: item_color = c.name().upper()
             if item_color and item_color not in allowed_colors:
                 continue
                 
        export_list.append(item)
    return export_list
