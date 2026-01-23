
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

def cross_product(o: Pt, a: Pt, b: Pt) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

def segments_intersect(p1: Pt, p2: Pt, p3: Pt, p4: Pt) -> bool:
    # Check if line segments (p1, p2) and (p3, p4) intersect
    # Exclude endpoint touching
    cp1 = cross_product(p1, p2, p3)
    cp2 = cross_product(p1, p2, p4)
    cp3 = cross_product(p3, p4, p1)
    cp4 = cross_product(p3, p4, p2)
    
    # Strict intersection (crossing)
    if ((cp1 > 1e-9 and cp2 < -1e-9) or (cp1 < -1e-9 and cp2 > 1e-9)) and \
       ((cp3 > 1e-9 and cp4 < -1e-9) or (cp3 < -1e-9 and cp4 > 1e-9)):
        return True
    return False

def is_path_self_intersecting(path_points: List[Pt]) -> bool:
    # Naive O(N^2) check
    n = len(path_points)
    if n < 4: return False 
    
    for i in range(n - 2): # i goes up to n-3
        p1, p2 = path_points[i], path_points[i+1]
        for j in range(i + 2, n - 1): # j starts at i+2
            p3, p4 = path_points[j], path_points[j+1]
            if segments_intersect(p1, p2, p3, p4):
                return True
    return False

