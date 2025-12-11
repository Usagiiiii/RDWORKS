from typing import List, Tuple, Optional
import logging
import os
from PIL import Image

logger = logging.getLogger(__name__)
Pt = Tuple[float, float]
Path = List[Pt]


def import_ai(path: str) -> Tuple[Optional[List[Path]], str, Optional[Image.Image]]:
    """导入AI文件（修复文件删除逻辑）"""
    status_msg = f"开始处理AI文件: {os.path.basename(path)}"
    logger.info(status_msg)
    bitmap_image = None

    # 方法1: 尝试作为PDF导入
    try:
        logger.info("方法1: 尝试直接作为PDF导入")
        from .import_pdf import import_pdf_or_ai
        paths = import_pdf_or_ai(path)
        status_msg += "\n✓ 直接作为PDF导入成功"
        logger.info("方法1成功: 提取到矢量路径")
        return paths, status_msg, None
    except Exception as e:
        err_msg = f"方法1失败: {str(e)}"
        status_msg += f"\n✗ {err_msg}"
        logger.error(f"方法1异常: {err_msg}", exc_info=True)

    # 方法2: 尝试转换为SVG
    converted_path_svg = None  # 显式定义变量
    try:
        logger.info("方法2: 尝试转换为SVG")
        from utils.import_utils import auto_convert_file
        converted_path_svg, convert_msg = auto_convert_file(path, 'svg')
        status_msg += "\n" + convert_msg
        if converted_path_svg and os.path.exists(converted_path_svg):
            from .import_svg import import_svg
            paths = import_svg(converted_path_svg)
            if paths and len(paths) > 0:
                logger.info(f"方法2成功: SVG转换后提取到{len(paths)}条路径")
                # 成功时删除临时文件
                if os.path.exists(converted_path_svg):
                    os.unlink(converted_path_svg)
                status_msg += "\n✓ SVG转换导入成功"
                return paths, status_msg, None
            else:
                logger.warning("方法2失败: SVG转换后未提取到有效路径")
        else:
            logger.warning("方法2失败: 未生成有效SVG文件")
    except Exception as e:
        err_msg = f"方法2失败: {str(e)}"
        status_msg += f"\n✗ {err_msg}"
        logger.error(f"方法2异常: {err_msg}", exc_info=True)
    finally:
        # 修复：确保临时文件被清理
        if converted_path_svg and os.path.exists(converted_path_svg):
            try:
                os.unlink(converted_path_svg)
                logger.debug("清理临时SVG文件")
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {cleanup_error}")

    # 方法3: 尝试转换为PDF
    converted_path_pdf = None
    try:
        logger.info("方法3: 尝试转换为PDF")
        from utils.import_utils import auto_convert_file
        converted_path_pdf, convert_msg = auto_convert_file(path, 'pdf')
        status_msg += "\n" + convert_msg
        if converted_path_pdf and os.path.exists(converted_path_pdf):
            from .import_pdf import import_pdf_or_ai
            paths = import_pdf_or_ai(converted_path_pdf)
            # 成功时删除临时文件
            if os.path.exists(converted_path_pdf):
                os.unlink(converted_path_pdf)
            status_msg += "\n✓ PDF转换导入成功"
            logger.info("方法3成功: PDF转换后提取到路径")
            return paths, status_msg, None
        else:
            logger.warning("方法3失败: 未生成有效PDF文件")
    except Exception as e:
        err_msg = f"方法3失败: {str(e)}"
        status_msg += f"\n✗ {err_msg}"
        logger.error(f"方法3异常: {err_msg}", exc_info=True)
    finally:
        if converted_path_pdf and os.path.exists(converted_path_pdf):
            try:
                os.unlink(converted_path_pdf)
            except Exception as cleanup_error:
                logger.warning(f"清理临时PDF文件失败: {cleanup_error}")

    # 方法4: 尝试作为位图导入
    converted_path_png = None
    try:
        logger.info("方法4: 尝试转换为PNG位图")
        from utils.import_utils import auto_convert_file
        converted_path_png, convert_msg = auto_convert_file(path, 'png')
        status_msg += "\n" + convert_msg
        if converted_path_png and os.path.exists(converted_path_png):
            im = Image.open(converted_path_png).convert('RGBA')
            bitmap_image = im
            # 成功时删除临时文件
            if os.path.exists(converted_path_png):
                os.unlink(converted_path_png)
            status_msg += "\n✓ 作为位图导入成功"
            logger.info("方法4成功: 转换为位图")
            return [], status_msg, bitmap_image
        else:
            logger.warning("方法4失败: 未生成有效PNG文件")
    except Exception as e:
        err_msg = f"方法4失败: {str(e)}"
        status_msg += f"\n✗ {err_msg}"
        logger.error(f"方法4异常: {err_msg}", exc_info=True)
    finally:
        if converted_path_png and os.path.exists(converted_path_png):
            try:
                os.unlink(converted_path_png)
            except Exception as cleanup_error:
                logger.warning(f"清理临时PNG文件失败: {cleanup_error}")

    # 所有方法失败
    final_msg = "所有AI导入方法均失败"
    status_msg += "\n" + final_msg
    logger.error(final_msg + f"，文件: {path}")
    return None, status_msg, None