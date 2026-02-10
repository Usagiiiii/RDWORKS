from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

def export_to_plt(canvas, filename: str, allowed_colors: List[str] = None):
    """
    导出 PLT (HPGL) 文件
    修正：执行 Y 轴翻转，适应 HPGL 左下角原点坐标系
    """
    # 精度设置：40 units/mm (即 1016 DPI)，这是 PLT 的工业标准
    scale_factor = 40.0
    
    try:
        # 获取画布高度用于坐标翻转
        page_h = 400.0
        if hasattr(canvas, '_work_h'): 
            page_h = float(canvas._work_h)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("IN;PA;\n") # 初始化, 绝对坐标
            f.write("SP1;\n")   # 选择笔号1
            
            count = 0
            items = _get_exportable_items(canvas, allowed_colors)
            
            for item in items:
                points = []
                # 1. 获取顶点数据
                if hasattr(item, 'points') and callable(item.points):
                    points = item.points()
                elif hasattr(item, 'get_params') and callable(item.get_params):
                    # 圆/椭圆 -> 离散化为多边形
                    cx, cy, rx, ry = item.get_params()
                    # 根据圆的大小自动决定分段数，保证平滑度
                    perimeter = 2 * math.pi * max(rx, ry)
                    steps = max(32, int(perimeter * 2)) # 约每0.5mm一段
                    points = []
                    for i in range(steps + 1):
                        angle = 2 * math.pi * i / steps
                        x = cx + rx * math.cos(angle)
                        y = cy + ry * math.sin(angle)
                        points.append((x, y))
                elif hasattr(item, 'rect') and callable(item.rect):
                    # 矩形
                    r = item.rect()
                    t = item.sceneTransform()
                    p1, p2 = r.topLeft(), r.topRight()
                    p3, p4 = r.bottomRight(), r.bottomLeft()
                    points = [
                        (t.map(p1).x(), t.map(p1).y()),
                        (t.map(p2).x(), t.map(p2).y()),
                        (t.map(p3).x(), t.map(p3).y()),
                        (t.map(p4).x(), t.map(p4).y()),
                        (t.map(p1).x(), t.map(p1).y()) # 闭合
                    ]

                if not points or len(points) < 2:
                    continue

                # 2. 坐标转换与写入 (Y轴翻转)
                # PU: Pen Up (抬笔移动到起点)
                p0 = points[0]
                tx0 = int(p0[0] * scale_factor)
                ty0 = int((page_h - p0[1]) * scale_factor) # 翻转Y轴
                f.write(f"PU{tx0},{ty0};\n")
                
                # PD: Pen Down (落笔绘制)
                cmd_parts = ["PD"]
                for p in points[1:]:
                    tx = int(p[0] * scale_factor)
                    ty = int((page_h - p[1]) * scale_factor) # 翻转Y轴
                    cmd_parts.append(f"{tx},{ty}")
                
                f.write(",".join(cmd_parts) + ";\n")
                count += 1
            
            f.write("PU;SP0;IN;\n") # 结束
            
        return True

    except Exception as e:
        logger.error(f"PLT 导出错误: {str(e)}")
        return False

def _get_exportable_items(canvas, allowed_colors):
    # 复用之前 export_dxf 的筛选逻辑，或者简单的重写
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
