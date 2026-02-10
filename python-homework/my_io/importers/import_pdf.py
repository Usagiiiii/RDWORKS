from typing import List, Tuple
import fitz

Pt = Tuple[float, float]
Path = List[Pt]


def import_pdf_or_ai(path: str) -> List[Path]:
    """导入PDF文件（复用原函数名，专注处理PDF）"""
    try:
        import fitz
    except ImportError:
        raise RuntimeError('需要安装 PyMuPDF: pip install pymupdf')

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise RuntimeError(f'无法打开文件: {str(e)}')

def _flatten_bezier(p1, p2, p3, p4, steps=10) -> List[Tuple[float, float]]:
    """Flatten a cubic Bezier curve into points"""
    res = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        # Cubic Bezier formula
        # B(t) = (1-t)^3 P1 + 3(1-t)^2 t P2 + 3(1-t)t^2 P3 + t^3 P4
        bx = (mt**3 * p1.x) + (3 * mt**2 * t * p2.x) + (3 * mt * t**2 * p3.x) + (t**3 * p4.x)
        by = (mt**3 * p1.y) + (3 * mt**2 * t * p2.y) + (3 * mt * t**2 * p3.y) + (t**3 * p4.y)
        res.append((bx, by))
    return res

def import_pdf_or_ai(path: str) -> List[Path]:
    """导入PDF文件（专注处理PDF，支持直线、曲线、矩形）"""
    try:
        import fitz
    except ImportError:
        raise RuntimeError('需要安装 PyMuPDF: pip install pymupdf')

    out = []
    
    # 使用上下文管理器确保文件句柄被正确关闭
    try:
        with fitz.open(path) as doc:
            for page in doc:
                try:
                    drawings = page.get_drawings()
                    for d in drawings:
                        # Each 'drawing' is a path which might contain multiple sub-paths (items)
                        # But typically items are connected or separate.
                        # If items are connected, we should append to current path.
                        # If 'l' starts with p1 != last_point, it is a move.
                        # fitz get_drawings logic: items are segments.
                        # item[1] (start point) usually equals previous item end point if connected.
                        
                        # However, output format allows List[Path], where Path is List[Pt].
                        # We can treat each connected sequence as a path.
                        
                        # Simplified approach: handle each item as segments, join if close?
                        # Or just output segments.
                        # Better: try to form continuous paths.
                        
                        current_pts = []
                        
                        for item in d['items']:
                            cmd = item[0]
                            if cmd == 'l':  # Line: ('l', p1, p2)
                                p1, p2 = item[1], item[2]
                                if not current_pts:
                                    current_pts.append((p1.x, p1.y))
                                    current_pts.append((p2.x, p2.y))
                                else:
                                    # Check continuity
                                    last = current_pts[-1]
                                    if abs(last[0]-p1.x) < 1e-4 and abs(last[1]-p1.y) < 1e-4:
                                        current_pts.append((p2.x, p2.y))
                                    else:
                                        # Break in continuity, save current and start new
                                        if len(current_pts) >= 2:
                                            out.append(current_pts)
                                        current_pts = [(p1.x, p1.y), (p2.x, p2.y)]

                            elif cmd == 'c':  # Curve: ('c', p1, p2, p3, p4)
                                p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                                curve_pts = _flatten_bezier(p1, p2, p3, p4)
                                
                                if not current_pts:
                                    current_pts.extend(curve_pts)
                                else:
                                    last = current_pts[-1]
                                    if abs(last[0]-p1.x) < 1e-4 and abs(last[1]-p1.y) < 1e-4:
                                        # Skip first point of curve if it matches
                                        current_pts.extend(curve_pts[1:])
                                    else:
                                        if len(current_pts) >= 2:
                                            out.append(current_pts)
                                        current_pts = list(curve_pts)

                            elif cmd == 're': # Rect: ('re', rect)
                                rect = item[1]
                                # Rect is closed path: tl -> tr -> br -> bl -> close
                                # fitz.Rect: (x0, y0, x1, y1) -> top-left is (x0, y0) usually? 
                                # fitz coordinate system: y increases downwards usually.
                                # (x0, y0) is top-left, (x1, y1) is bottom-right.
                                # Let's generate points.
                                pts = [
                                    (rect.x0, rect.y0),
                                    (rect.x1, rect.y0),
                                    (rect.x1, rect.y1),
                                    (rect.x0, rect.y1),
                                    (rect.x0, rect.y0) # Close it
                                ]
                                if current_pts:
                                    # Rect implies new isolated path usually
                                    if len(current_pts) >= 2:
                                        out.append(current_pts)
                                    current_pts = []
                                out.append(pts)
                                
                            # Ignore 'qu' (Quad) for now or treat as closed 4-gon?
                            # fitz output for quads?
                            
                        if current_pts and len(current_pts) >= 2:
                            out.append(current_pts)

                except Exception:
                    continue
    except Exception as e:
        raise RuntimeError(f'处理PDF异常: {str(e)}')

    if not out:
        raise RuntimeError("未从PDF文件中提取到矢量路径")

    return out