from typing import List, Tuple, Optional
import logging
import re
import os
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)
Pt = Tuple[float, float]
Path = List[Pt]

def parse_unit(value: str) -> Tuple[float, str]:
    """解析带单位的数值（如 '100px' '20mm'）"""
    m = re.match(r'^([0-9.+-eE]+)\s*(px|mm|cm|in|pt|pc|em|ex)?$', str(value).strip())
    if not m:
        try:
            # 容错：移除末尾非数字字符后尝试转换
            num_str = re.sub(r'[^\d.+-eE]$', '', str(value).strip())
            return float(num_str), "px"
        except:
            raise ValueError(f"无法解析带单位的数值: {value}")
    v = float(m.group(1))
    u = m.group(2) or "px"
    return v, u

def unit_to_mm(v: float, u: str) -> float:
    """单位转换为毫米"""
    conversion = {
        "mm": v,
        "cm": v * 10.0,
        "m": v * 1000.0,
        "in": v * 25.4,
        "ft": v * 304.8,
        "yd": v * 914.4,
        "px": v * 0.2645833333,  # 假设96dpi
        "pt": v * 0.352778,      # 1pt = 1/72in
        "pc": v * 4.233333,      # 1pc = 12pt
        "em": v * 4.233333,      # 假设1em = 12pt
        "ex": v * 2.116666       # 假设1ex = 6pt
    }
    return conversion.get(u, v)

def simplify_polyline(pts: List[Pt], tol: float) -> List[Pt]:
    """使用Ramer-Douglas-Peucker算法简化折线（复用外部rdp实现）"""
    if len(pts) <= 2:
        return pts[:]
    from utils.geom import rdp
    return rdp(pts, tol)

def import_svg(path: str, tol_mm: float = 0.2, close_gap_mm: float = 0.1) -> List[Path]:
    """解析SVG文件提取矢量路径（带详细日志版）"""
    logger.info(f"=== 开始解析SVG文件: {path} ===")
    out: List[Path] = []

    # 1. 检查svgpathtools依赖
    try:
        from svgpathtools import svg2paths2
        logger.debug("成功导入svgpathtools库")
    except ImportError as e:
        logger.error("未安装svgpathtools库，无法解析SVG路径")
        raise RuntimeError("需要安装 svgpathtools：pip install svgpathtools") from e

    # 2. 尝试解析SVG文件（原始文件或转换后文件）
    paths = None
    attrs = None
    svg_attr = None
    converted_path = None  # 临时转换文件路径

    try:
        logger.info("尝试直接解析原始SVG文件")
        paths, attrs, svg_attr = svg2paths2(path)
        logger.info(f"原始SVG解析成功，共包含{len(paths)}条路径元素")
    except Exception as e:
        logger.warning(f"原始SVG解析失败: {str(e)}，尝试自动转换修复")
        # 尝试转换文件
        try:
            from utils.import_utils import auto_convert_file
            converted_path = auto_convert_file(path, 'svg')  # 转换为临时SVG
            if not converted_path or not os.path.exists(converted_path):
                logger.error("自动转换失败，未生成有效临时SVG文件")
                raise RuntimeError("自动转换SVG失败：未生成有效文件") from e

            logger.info(f"使用转换后的临时SVG文件解析: {converted_path}")
            paths, attrs, svg_attr = svg2paths2(converted_path)
            logger.info(f"转换后SVG解析成功，共包含{len(paths)}条路径元素")
        except Exception as e2:
            logger.error(f"转换后SVG仍解析失败: {str(e2)}", exc_info=True)
            if converted_path and os.path.exists(converted_path):
                os.unlink(converted_path)  # 清理临时文件
            raise RuntimeError(f"解析SVG失败，自动修复也失败: {str(e2)}") from e2

    # 3. 解析SVG尺寸和单位，计算px到mm的转换比例
    logger.info("开始解析SVG尺寸和单位信息")
    width_v, width_u = 0.0, "px"
    height_v, height_u = 0.0, "px"

    try:
        if "width" in svg_attr:
            width_v, width_u = parse_unit(svg_attr["width"])
            logger.info(f"SVG宽度: {width_v} {width_u}")
        if "height" in svg_attr:
            height_v, height_u = parse_unit(svg_attr["height"])
            logger.info(f"SVG高度: {height_v} {height_u}")
    except Exception as e:
        logger.warning(f"解析SVG宽高失败: {str(e)}，使用默认值")

    # 计算px到mm的转换比例（默认96dpi: 1px≈0.2645mm）
    px2mm = 0.2645833333
    try:
        if width_u != "px" and width_v > 0:
            mm_width = unit_to_mm(width_v, width_u)
            px2mm = mm_width / width_v
            logger.info(f"根据宽度计算px2mm: {px2mm:.6f} (1px = {px2mm}mm)")
    except Exception as e:
        logger.warning(f"根据宽度计算px2mm失败: {str(e)}，使用默认值")

    # 处理viewBox（可能影响坐标转换）
    viewBox = svg_attr.get("viewBox", "")
    view_x, view_y, view_width, view_height = 0.0, 0.0, 0.0, 0.0
    try:
        if viewBox:
            parts = list(map(float, viewBox.split()))
            if len(parts) == 4:
                view_x, view_y, view_width, view_height = parts
                logger.info(f"SVG viewBox: x={view_x}, y={view_y}, width={view_width}, height={view_height}")
                # 结合viewBox重新计算px2mm
                if view_width > 0 and width_v > 0 and width_u != "px":
                    mm_width = unit_to_mm(width_v, width_u)
                    px2mm = mm_width / view_width
                    logger.info(f"结合viewBox重新计算px2mm: {px2mm:.6f}")
    except Exception as e:
        logger.warning(f"解析viewBox失败: {str(e)}，忽略viewBox")

    # 4. 处理每条路径，转换为毫米坐标并简化
    tol_px = max(0.5, (tol_mm / max(px2mm, 1e-6)))  # 容差转换为像素单位
    logger.info(f"路径处理参数: tol_mm={tol_mm}, close_gap_mm={close_gap_mm}, tol_px={tol_px:.2f}")

    for path_idx, p in enumerate(paths):
        logger.info(f"\n处理第{path_idx+1}/{len(paths)}条路径: 包含{len(p)}个线段")
        pts: List[Pt] = []  # 存储转换后的毫米坐标点

        for seg_idx, seg in enumerate(p):
            try:
                # 计算线段长度并决定采样步数
                seg_length = seg.length()
                logger.debug(f"第{seg_idx+1}/{len(p)}个线段: 长度={seg_length:.2f}px")

                if seg_length < tol_px:
                    # 极短线段只取首尾点
                    start = seg.start
                    end = seg.end
                    pts.append((start.real * px2mm, -start.imag * px2mm))  # Y轴翻转适配Qt
                    pts.append((end.real * px2mm, -end.imag * px2mm))
                    logger.debug(f"极短线段，添加首尾点（共2个点）")
                    continue

                # 较长线段按容差采样
                steps = max(4, int(seg_length / max(1e-6, tol_px)))
                sample = [complex(z) for z in seg.discretize(steps=steps)]
                logger.debug(f"线段采样: 步数={steps}，采样点数量={len(sample)}")
            except Exception as e:
                # 采样失败时降级处理
                logger.warning(f"线段{seg_idx+1}采样失败: {str(e)}，使用默认41点采样")
                sample = [seg.point(t / 40.0) for t in range(41)]  # 强制41点采样

            # 转换采样点为毫米坐标并添加到列表
            for z in sample:
                x_mm = z.real * px2mm
                y_mm = -z.imag * px2mm  # Qt画布Y轴向下为正，SVG向上为正，需翻转
                pts.append((x_mm, y_mm))

        # 处理路径闭合（首尾点距离过小时闭合）
        if len(pts) >= 2:
            dx = pts[0][0] - pts[-1][0]
            dy = pts[0][1] - pts[-1][1]
            gap = (dx**2 + dy**2) ** 0.5
            if gap < close_gap_mm:
                pts[-1] = pts[0]  # 闭合路径
                logger.info(f"路径首尾点距离{gap:.6f}mm < {close_gap_mm}mm，已闭合")

        # 简化路径（去除冗余点）
        simplified = simplify_polyline(pts, tol_mm)
        logger.info(f"路径简化前: {len(pts)}个点，简化后: {len(simplified)}个点")

        # 过滤无效路径（少于2个点）
        if len(simplified) >= 2:
            # 记录路径坐标范围
            xs = [p[0] for p in simplified]
            ys = [p[1] for p in simplified]
            logger.info(
                f"有效路径{path_idx+1}坐标范围: "
                f"X[{min(xs):.2f}mm, {max(xs):.2f}mm], "
                f"Y[{min(ys):.2f}mm, {max(ys):.2f}mm]"
            )
            out.append(simplified)
        else:
            logger.warning(f"路径{path_idx+1}简化后点数量不足（{len(simplified)}个），已过滤")

    # 5. 清理临时转换文件
    if converted_path and os.path.exists(converted_path):
        os.unlink(converted_path)
        logger.debug(f"已清理临时转换文件: {converted_path}")

    # 6. 检查是否有基本形状未被解析为路径
    if not out:
        logger.info("未提取到有效路径，检查是否包含基本形状（rect/circle等）")
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            ns = {"svg": "http://www.w3.org/2000/svg"}  # SVG命名空间
            basic_shapes = root.findall(
                ".//svg:rect | .//svg:circle | .//svg:ellipse | .//svg:line | .//svg:polyline | .//svg:polygon",
                namespaces=ns
            )
            if basic_shapes:
                logger.info(f"检测到{len(basic_shapes)}个基本形状元素，尝试转换为路径")
                from utils.import_utils import auto_convert_file
                converted_path = auto_convert_file(path, 'svg')
                if converted_path and os.path.exists(converted_path):
                    logger.info(f"基本形状转换为路径后，递归解析: {converted_path}")
                    result = import_svg(converted_path, tol_mm, close_gap_mm)
                    os.unlink(converted_path)
                    if result:
                        logger.info(f"基本形状转换后成功提取{len(result)}条路径")
                        return result
                    else:
                        logger.warning("基本形状转换后仍未提取到路径")
                else:
                    logger.error("基本形状转换失败，未生成有效SVG")
                raise RuntimeError("SVG包含基本形状但无法转换为路径，请手动转换为路径后再导入")
            else:
                logger.info("SVG中未检测到基本形状，确认无有效路径")
        except Exception as e:
            logger.error(f"检查基本形状时出错: {str(e)}", exc_info=True)

    # 7. 返回最终提取的路径
    logger.info(f"=== SVG解析完成，共提取到{len(out)}条有效路径 ===")
    return out