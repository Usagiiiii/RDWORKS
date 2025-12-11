from typing import List, Tuple
import math

Pt = Tuple[float, float]
Path = List[Pt]


def simplify_polyline(pts: List[Pt], tol: float) -> List[Pt]:
    """使用Ramer-Douglas-Peucker算法简化折线（复用外部rdp实现）"""
    if len(pts) <= 2:
        return pts[:]
    from utils.geom import rdp # 替换原有手动实现，使用外部工具函数
    return rdp(pts, tol)


def import_dxf(path: str, tol_mm: float = 0.2, close_gap_mm: float = 0.1) -> List[Path]:
    try:
        import ezdxf
    except Exception as e:
        raise RuntimeError('需要安装 ezdxf: pip install ezdxf') from e

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    unit_map = {0: 1.0, 1: 25.4, 2: 304.8, 3: 1609344.0, 4: 1.0, 5: 10.0, 6: 1000.0, 7: 1_000_000.0, 10: 914.4}
    scale = unit_map.get(doc.header.get('$INSUNITS', 4), 1.0)
    out: List[Path] = []

    def add_poly(pts):
        if not pts or len(pts) < 2:
            return
        # 闭合过小的间隙
        if (pts[0][0] - pts[-1][0]) ** 2 + (pts[0][1] - pts[-1][1]) ** 2 < (close_gap_mm / scale) ** 2:
            pts[-1] = pts[0]
        # 简化路径
        simplified = simplify_polyline(pts, tol_mm / scale)
        # 转换为毫米单位
        out.append([(x * scale, y * scale) for x, y in simplified])

    # 处理直线（LINE）
    for e in msp.query('LINE'):
        add_poly([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])

    # 处理轻量多段线（LWPOLYLINE）
    for e in msp.query('LWPOLYLINE'):
        pts = [(p[0], p[1]) for p in e.get_points('xy')]
        if getattr(e, 'closed', False) and pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        add_poly(pts)

    # 处理传统多段线（POLYLINE）
    for e in msp.query('POLYLINE'):
        vertices = []
        for v in e.vertices:
            x = v.dxf.location.x
            y = v.dxf.location.y
            vertices.append((x, y))
        pts = vertices
        if getattr(e, 'closed', False) and pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        add_poly(pts)

    # 处理圆（CIRCLE）和圆弧（ARC）
    def arc_samples(cx, cy, r, sd, ed):
        sd = math.radians(sd)
        ed = math.radians(ed)
        if ed < sd:
            ed += 2 * math.pi
        arc_len = abs(ed - sd) * r
        steps = max(16, int(arc_len / max(1e-6, tol_mm)))
        return [(cx + r * math.cos(sd + i * (ed - sd) / steps),
                 cy + r * math.sin(sd + i * (ed - sd) / steps))
                for i in range(steps + 1)]

    for e in msp.query('CIRCLE'):
        add_poly(arc_samples(e.dxf.center.x, e.dxf.center.y, e.dxf.radius, 0, 360))

    for e in msp.query('ARC'):
        add_poly(arc_samples(e.dxf.center.x, e.dxf.center.y, e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle))

    # 处理样条曲线（SPLINE）
    for e in msp.query('SPLINE'):
        try:
            tool = e.construction_tool()
            L = max(1e-6, getattr(tool, 'approximate_length', lambda: 1000.0)())
            segs = max(64, int(L / max(1e-6, tol_mm)))
            pts = [(p.x, p.y) for p in tool.approximate(segs)]
        except Exception:
            pts = [(p[0], p[1]) for p in e.approximate(segments=128)]
        add_poly(pts)

    # 处理椭圆（ELLIPSE）
    for e in msp.query('ELLIPSE'):
        try:
            tool = e.construction_tool()
            L = max(1e-6, getattr(tool, 'approximate_length', lambda: 1000.0)())
            segs = max(64, int(L / max(1e-6, tol_mm)))
            pts = [(p.x, p.y) for p in tool.approximate(segs)]
        except Exception:
            start = getattr(e.dxf, 'start_param', 0.0) or 0.0
            end = getattr(e.dxf, 'end_param', 2 * math.pi) or (2 * math.pi)
            steps = 192
            pts = []
            for i in range(steps + 1):
                t = start + (end - start) * i / steps
                x, y = e.point_at(t)
                pts.append((x, y))
        add_poly(pts)

    return out