
from typing import List, Tuple
import math

Pt = Tuple[float,float]
Path = List[Pt]

def rdp(points: Path, eps: float) -> Path:
    if len(points) < 3:
        return points[:]
    sx, sy = points[0]
    ex, ey = points[-1]
    dx, dy = ex - sx, ey - sy
    denom = (dx*dx + dy*dy) or 1e-12
    maxd, idx = -1.0, -1
    for i in range(1, len(points)-1):
        x, y = points[i]
        t = ((x - sx)*dx + (y - sy)*dy) / denom
        projx, projy = sx + t*dx, sy + t*dy
        d = math.hypot(x - projx, y - projy)
        if d > maxd:
            maxd, idx = d, i
    if maxd > eps:
        left = rdp(points[:idx+1], eps)
        right = rdp(points[idx:], eps)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]

def bbox_of(paths: List[Path]):
    xs=[]; ys=[]
    for p in paths:
        for (x,y) in p:
            xs.append(x); ys.append(y)
    if not xs: return None
    return (min(xs), min(ys), max(xs), max(ys))

def length_of(path: Path)->float:
    if not path or len(path)<2: return 0.0
    L=0.0
    for i in range(1,len(path)):
        x0,y0=path[i-1]; x1,y1=path[i]
        L += math.hypot(x1-x0, y1-y0)
    return L
