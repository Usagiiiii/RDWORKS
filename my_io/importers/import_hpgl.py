from typing import List, Tuple

Pt = Tuple[float, float]
Path = List[Pt]
import os


def import_hpgl(path: str, scale: float = None) -> List[Path]:
    """
    解析 HPGL/PLT（PU/PD/PA/PR/SC）
    scale: 如果为None，使用HPGL默认40单位/mm；否则使用指定的scale（毫米/单位）
    """
    try:
        # 尝试使用latin1编码（兼容性更好）
        txt = open(path, 'r', encoding='latin1', errors='ignore').read()
    except:
        # 如果失败，尝试utf-8编码
        txt = open(path, 'r', encoding='utf-8', errors='ignore').read()

    i = 0
    n = len(txt)

    # 设置缩放比例：如果指定了scale，则使用；否则使用默认40单位/mm
    if scale is not None:
        scale_units_per_mm = 1.0 / scale
    else:
        scale_units_per_mm = 40.0

    x = 0.0
    y = 0.0
    pen_down = False
    cur: Path = []
    out: List[Path] = []

    def flush():
        nonlocal cur
        if len(cur) >= 2:
            out.append(cur)
        cur = []

    def read_nums(j):
        k = txt.find(';', j)
        if k == -1:
            k = n
        raw = txt[j:k].strip()
        nums = []
        if raw:
            for part in raw.replace(' ', '').split(','):
                if part == '':
                    continue
                try:
                    nums.append(float(part))
                except:
                    pass
        return nums, k + 1

    while i < n:
        if i + 1 < n and txt[i].isalpha() and txt[i + 1].isalpha():
            cmd = txt[i:i + 2].upper()
            i += 2
            nums, i = read_nums(i)

            if cmd == 'IN':
                x = y = 0.0
                pen_down = False
                flush()
                scale_units_per_mm = 40.0  # 重置为默认
            elif cmd == 'SC':
                # 处理缩放命令
                if len(nums) >= 2:
                    # 简化处理：如果有SC命令，使用固定比例
                    scale_units_per_mm = 40.0
            elif cmd == 'PU':
                if cur:
                    flush()
                pen_down = False
                if nums:
                    for j in range(0, len(nums), 2):
                        x = nums[j] / scale_units_per_mm
                        if j + 1 < len(nums):
                            y = nums[j + 1] / scale_units_per_mm
            elif cmd == 'PD':
                if not pen_down:
                    pen_down = True
                    if cur:
                        flush()
                    cur = []
                if nums:
                    for j in range(0, len(nums), 2):
                        nx = nums[j] / scale_units_per_mm
                        ny = nums[j + 1] / scale_units_per_mm if j + 1 < len(nums) else y
                        if not cur:
                            cur = [(x, y)]
                        cur.append((nx, ny))
                        x, y = nx, ny
            elif cmd == 'PA':
                if nums:
                    for j in range(0, len(nums), 2):
                        nx = nums[j] / scale_units_per_mm
                        ny = nums[j + 1] / scale_units_per_mm if j + 1 < len(nums) else y
                        if pen_down:
                            if not cur:
                                cur = [(x, y)]
                            cur.append((nx, ny))
                        x, y = nx, ny
            elif cmd == 'PR':
                if nums:
                    for j in range(0, len(nums), 2):
                        dx = nums[j] / scale_units_per_mm
                        dy = nums[j + 1] / scale_units_per_mm if j + 1 < len(nums) else 0.0
                        x += dx
                        y += dy
                        if pen_down:
                            if not cur:
                                cur = [(x - dx, y - dy)]
                            cur.append((x, y))
        else:
            i += 1

    if cur:
        flush()

    return out