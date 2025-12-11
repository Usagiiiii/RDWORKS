from typing import List, Tuple, Optional
import logging
import os

logger = logging.getLogger(__name__)
Pt = Tuple[float, float]
Path = List[Pt]


def import_eps_as_vector(path: str) -> Tuple[Optional[List[Path]], str]:
    """导入EPS为矢量"""
    status_msg = "正在处理EPS矢量文件..."

    # 尝试转换为SVG（使用软件目录下的Inkscape）
    from utils.import_utils import auto_convert_file
    converted_path, convert_msg = auto_convert_file(path, 'svg')
    status_msg += "\n" + convert_msg

    if converted_path:
        try:
            from .import_svg import import_svg
            paths = import_svg(converted_path)
            os.unlink(converted_path)
            status_msg += "\n✓ SVG转换导入成功"
            return paths, status_msg
        except Exception as e:
            if os.path.exists(converted_path):
                os.unlink(converted_path)
            status_msg += f"\n✗ SVG导入失败: {str(e)}"

    # 尝试转换为PDF
    converted_path, convert_msg = auto_convert_file(path, 'pdf')
    status_msg += "\n" + convert_msg

    if converted_path:
        try:
            from .import_pdf import import_pdf_or_ai
            paths = import_pdf_or_ai(converted_path)
            os.unlink(converted_path)
            status_msg += "\n✓ PDF转换导入成功"
            return paths, status_msg
        except Exception as e:
            if os.path.exists(converted_path):
                os.unlink(converted_path)
            status_msg += f"\n✗ PDF导入失败: {str(e)}"

    status_msg += "\n✗ 所有矢量转换方法均失败"
    return None, status_msg