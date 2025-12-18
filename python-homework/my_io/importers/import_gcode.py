from typing import List, Tuple
import re

Pt = Tuple[float, float]
Path = List[Pt]

_re_num = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'
rx_x = re.compile(fr'X({_re_num})')
rx_y = re.compile(fr'Y({_re_num})')


def import_gcode(path: str) -> List[Path]:
    """
    简化 G-code 解析：支持 G0/G1/G90/G91/G20/G21/M3/M4/M5 与 XY 直线。
    拉丝（M3/M4）期间的连续 G1 组成多段线。
    """
    mm = True;
    abs_mode = True;
    laser_on = False
    x = y = 0.0
    cur: Path = [];
    out: List[Path] = []

    def flush():
        nonlocal cur
        if len(cur) >= 2: out.append(cur)
        cur = []

    for ln in open(path, 'r', encoding='utf-8', errors='ignore'):
        s = ln.strip()
        s = s.split(';', 1)[0].split('(', 1)[0].strip()
        if not s: continue
        up = s.upper()
        if 'G20' in up: mm = False
        if 'G21' in up: mm = True
        if 'G90' in up: abs_mode = True
        if 'G91' in up: abs_mode = False
        if 'M3' in up or 'M4' in up:
            if not laser_on: laser_on = True; flush()
        if 'M5' in up:
            if laser_on: laser_on = False; flush()
        x_m = rx_x.search(up);
        y_m = rx_y.search(up)
        if x_m or y_m or ('G0' in up) or ('G1' in up):
            nx, ny = x, y
            if x_m: nx = float(x_m.group(1))
            if y_m: ny = float(y_m.group(1))
            if not abs_mode:
                nx = x + (nx if x_m else 0.0)
                ny = y + (ny if y_m else 0.0)
            if not mm: nx *= 25.4; ny *= 25.4
            if 'G0' in up and laser_on:
                laser_on = False;
                flush()
            if laser_on:
                if not cur: cur = [(x, y)]
                cur.append((nx, ny))
            x, y = nx, ny
    if cur: flush()
    return out