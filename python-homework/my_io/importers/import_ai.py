from typing import List, Tuple, Optional
import logging
import os
from PIL import Image

import tempfile

logger = logging.getLogger(__name__)
Pt = Tuple[float, float]
Path = List[Pt]

def _create_sanitized_ai(path: str) -> Optional[str]:
    """
    Creates a temporary sanitized AI file for PostScript processing.
    Injects standard Illustrator ProcSets definitions to make it compatible with Ghostscript.
    """
    try:
        header_ops = [
             b'/Lb { pop pop pop pop pop pop pop pop pop pop } bind def',
             b'/LB { } bind def',
             b'/Ln { pop } bind def',
             b'/XR { pop } bind def',
             b'/R { pop } bind def',
             
             b'/Adobe_Illustrator_AI5 5 dict def',
             b'Adobe_Illustrator_AI5 /terminate { } put',
             b'/Adobe_ColorImage_AI6 5 dict def',
             b'Adobe_ColorImage_AI6 /terminate { } put',
             b'/Adobe_typography_AI5 5 dict def',
             b'Adobe_typography_AI5 /terminate { } put',
             b'/Adobe_cshow 5 dict def',
             b'Adobe_cshow /terminate { } put',
             b'/Adobe_level2_AI5 5 dict def',
             b'Adobe_level2_AI5 /terminate { } put',
             
             b'/annotatepage { } bind def',

             b'/m { moveto } bind def',
             b'/L { lineto } bind def',
             b'/c { curveto } bind def',
             b'/S { stroke } bind def',
             b'/f { fill } bind def',
             b'/F { fill } bind def',
             b'/s { closepath stroke } bind def',
             b'/b { closepath fill stroke } bind def',
             b'/B { fill stroke } bind def',
             
             b'/K { setcmykcolor } bind def',
             b'/k { setcmykcolor } bind def',
             b'/w { setlinewidth } bind def',
             b'/j { setlinejoin } bind def',
             b'/J { setlinecap } bind def',
             b'/d { setdash } bind def',
             b'/M { setmiterlimit } bind def',
             
             b'/g { setgray } bind def',
             b'/G { setgray } bind def',
             b'/rg { setrgbcolor } bind def',
             b'/RG { setrgbcolor } bind def',
             
             b'/To { pop } bind def', 
             b'/TO { pop } bind def',
             b'/Tp { pop } bind def',
             b'/TP { pop } bind def',
        ]
        
        with open(path, 'rb') as f:
            content = f.read()

        # Safer injection: Do not split main content which might contain binary data
        try:
            first_newline_idx = content.find(b'\n')
            if first_newline_idx != -1:
                # Include the newline in the first line
                line1 = content[:first_newline_idx+1]
                rest = content[first_newline_idx+1:]
                
                if line1.startswith(b'%!PS-Adobe'):
                     # Insert headers after the PS line
                     new_content = line1 + b'\r\n'.join(header_ops) + b'\r\n' + rest
                else:
                     new_content = b'\r\n'.join(header_ops) + b'\r\n' + content
            else:
                new_content = b'\r\n'.join(header_ops) + b'\r\n' + content
        except Exception:
             new_content = b'\r\n'.join(header_ops) + b'\r\n' + content
            
        lines = [] # Clear memory if possible, though python GC handles it

        # Create temp file in a safe location (using standard temp dir)
        # Note: We must ensure the file is closed so subprocess can read it.
        # mkstemp return (fd, path)
        fd, temp_path = tempfile.mkstemp(suffix='.ai')
        with os.fdopen(fd, 'wb') as tmp:
            tmp.write(new_content)
            
        logger.info(f"Created sanitized AI file: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Failed to sanitize AI file: {e}")
        return None

def import_ai(path: str) -> Tuple[Optional[List[Path]], str, Optional[Image.Image]]:
    """导入AI文件（修复文件删除逻辑）"""
    status_msg = f"开始处理AI文件: {os.path.basename(path)}"
    logger.info(status_msg)
    bitmap_image = None
    
    # 预先检测文件类型
    is_ps = False
    try:
        with open(path, 'rb') as f:
            header = f.read(15)
            # Check for standard PS header or common variations like %!PS-Adobe-3.0
            if header.startswith(b'%!PS-Adobe-'):
                is_ps = True
    except Exception as e:
        logger.warning(f"Failed to check file header: {e}")

    # 方法1: 尝试作为PDF导入
    try:
        if is_ps:
            logger.info("检测到旧版 PostScript AI 文件，跳过 PDF 直接解析")
            status_msg += "\n! 检测到 PostScript 格式，跳过 PDF 直接解析"
            raise Exception("PostScript format detected (requires conversion)")

        logger.info("方法1: 尝试直接作为PDF导入")
        from .import_pdf import import_pdf_or_ai
        paths = import_pdf_or_ai(path)
        status_msg += "\n✓ 直接作为PDF导入成功"
        logger.info("方法1成功: 提取到矢量路径")
        return paths, status_msg, None
    except Exception as e:
        err_msg = f"方法1失败: {str(e)}"
        status_msg += f"\n✗ {err_msg}"
        logger.error(f"方法1异常: {err_msg}") # Reduced noise, moved exc_info logic if needed

    # 方法2: 尝试转换为SVG
    # 对于 PostScript AI 文件，SVG 转换（inkscape/magick）通常效果不佳且容易失败，
    # 且我们已经有了专门针对 PS 优化的 PDF 转换路径（方法3），因此跳过此步以减少报错干扰。
    if is_ps:
        logger.info("方法2: 跳过 SVG 转换（针对 PostScript 文件优先使用 PDF 转换）")
    else:
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
    sanitized_file_path = None
    try:
        logger.info("方法3: 尝试转换为PDF")
        
        conversion_input_path = path

        # Make sure is_ps is used here if defined above (it is now scope safe due to move to top of func)
        if is_ps:
             # Create sanitized version for Ghostscript
             sanitized = _create_sanitized_ai(path)
             if sanitized:
                 sanitized_file_path = sanitized
                 conversion_input_path = sanitized_file_path # Use sanitized file for conversion
                 status_msg += "\n! 使用修复后的文件进行转换"

        from utils.import_utils import auto_convert_file
        converted_path_pdf, convert_msg = auto_convert_file(conversion_input_path, 'pdf')
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
        if sanitized_file_path and os.path.exists(sanitized_file_path):
             try:
                 os.unlink(sanitized_file_path)
             except:
                 pass

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