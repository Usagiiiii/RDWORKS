# utils/image_utils.py
import logging
import os
import re
import subprocess
import tempfile
from typing import Optional, Tuple

from PIL import Image
from PyQt5 import QtGui
from PyQt5.QtGui import QImage, QPixmap  # 确保导入PyQt的相关类

from utils.tool_utils import _check_conversion_tool
logger = logging.getLogger(__name__)

def pil_to_qpixmap(im: Image.Image) -> QPixmap:
    """将PIL图像转换为QPixmap"""
    im = im.convert("RGBA")
    w, h = im.size
    data = im.tobytes("raw", "RGBA")
    qimg = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)
# ---- 工具函数：QImage -> PIL.Image（用于导出时从画布取图像） -------------------
def qimage_to_pil(qimg: QtGui.QImage) -> Image.Image:
    """
    将 QImage 转为 PIL.Image（RGBA）。不依赖 ImageQt，最大程度保持兼容。
    """
    qimg = qimg.convertToFormat(QtGui.QImage.Format_RGBA8888)
    width = qimg.width()
    height = qimg.height()
    ptr = qimg.bits()
    ptr.setsize(qimg.byteCount())
    arr = bytes(ptr)
    im = Image.frombuffer("RGBA", (width, height), arr, "raw", "RGBA", 0, 1)
    return im


def convert_wbmp_to_png(wbmp_path: str) -> Optional[Image.Image]:
    """转换WBMP到PNG格式"""
    try:
        # 尝试直接用PIL打开
        with Image.open(wbmp_path) as img:
            # 创建一个新的RGBA图像
            png_img = Image.new("RGBA", img.size, (255, 255, 255, 255))
            # 转换WBMP（通常是单色）到RGBA
            png_img.paste(img.convert("L"), mask=img.convert("L"))
            return png_img
    except Exception:
        pass

    # 尝试使用其他方法读取WBMP原始数据
    try:
        with open(wbmp_path, 'rb') as f:
            data = f.read()

        # 简单的WBMP解析（仅支持基本格式）
        if len(data) < 2:
            return None

        # 解析WBMP头部
        type_field = data[0]
        if type_field != 0:  # 仅支持类型0
            return None

        fix_bit = (data[1] >> 7) & 1
        if fix_bit != 0:
            return None

        width = 0
        i = 2
        while i < len(data):
            byte = data[i]
            width = (width << 7) | (byte & 0x7F)
            if not (byte & 0x80):
                i += 1
                break
            i += 1

        height = 0
        while i < len(data):
            byte = data[i]
            height = (height << 7) | (byte & 0x7F)
            if not (byte & 0x80):
                i += 1
                break
            i += 1

        # 创建图像
        img = Image.new('1', (width, height))
        pixels = img.load()
        bit_idx = 0
        for y in range(height):
            for x in range(width):
                if i >= len(data):
                    break
                byte = data[i]
                bit = (byte >> (7 - bit_idx)) & 1
                pixels[x, y] = 0 if bit else 1  # WBMP通常是黑底白图，这里反转一下
                bit_idx += 1
                if bit_idx >= 8:
                    bit_idx = 0
                    i += 1
            if i >= len(data):
                break

        # 转换为RGBA
        return img.convert('RGBA')
    except Exception:
        return None


def auto_convert_file(input_path: str, target_format: str) -> Tuple[Optional[str], str]:
    """自动转换文件格式（添加备选方案）"""
    original_ext = os.path.splitext(input_path)[1].lower()
    status_msg = f"正在将{original_ext}转换为{target_format}..."

    # 根据目标格式选择合适的转换工具
    converters = []

    if target_format == 'svg':
        converters.append(('Inkscape', 'inkscape'))
        # 添加备选：使用ImageMagick（如果可用）
        converters.append(('ImageMagick', 'magick'))
        converters.append(('ImageMagick', 'convert'))

    elif target_format == 'pdf':
        converters.append(('Inkscape', 'inkscape'))
        converters.append(('Ghostscript', 'gswin64c'))
        converters.append(('Ghostscript', 'gswin32c'))
        converters.append(('Ghostscript', 'gs'))

    elif target_format == 'png':
        if original_ext == '.eps':
            # EPS文件优先使用Ghostscript
            converters.append(('Ghostscript', 'gswin64c'))
            converters.append(('Ghostscript', 'gswin32c'))
            converters.append(('Ghostscript', 'gs'))
            converters.append(('Inkscape', 'inkscape'))
        else:
            converters.append(('Inkscape', 'inkscape'))
            converters.append(('ImageMagick', 'magick'))
            converters.append(('ImageMagick', 'convert'))

    # 尝试每种转换器
    for converter_name, tool_name in converters:
        # 检查工具是否可用
        tool_path = _check_conversion_tool(tool_name)
        if not tool_path:
            status_msg += f"\n未找到工具: {tool_name}"
            continue

        converted_path = _convert_with_tool(input_path, target_format, tool_name)
        if converted_path:
            status_msg = f"✓ 成功使用{converter_name}将{original_ext}转换为{target_format}"
            return converted_path, status_msg
        else:
            status_msg += f"\n{converter_name}转换失败"

    status_msg += "\n所有转换方法均失败"
    return None, status_msg


# 强化转换工具的日志输出
def _convert_with_tool(input_path: str, target_format: str, tool_name: str) -> Optional[str]:
    """使用指定工具转换文件（修复Inkscape 1.0+兼容性）"""
    tool_path = _check_conversion_tool(tool_name)
    if not tool_path:
        return None

    try:
        with tempfile.NamedTemporaryFile(suffix=f'.{target_format}', delete=False) as f:
            output_path = f.name

        # 修复：针对不同版本的Inkscape使用不同的命令行参数
        if tool_name == 'inkscape':
            # 检测Inkscape版本并选择合适的参数
            version_info = _get_inkscape_version(tool_path)
            use_new_syntax = version_info and version_info >= (1, 0, 0)

            if use_new_syntax:
                # Inkscape 1.0+ 新语法
                cmd = [
                    tool_path,
                    input_path,
                    '--export-filename', output_path,
                    '--export-type', target_format
                ]
                if target_format == 'svg':
                    cmd.extend(['--export-plain-svg'])
                elif target_format == 'png':
                    cmd.extend(['--export-dpi=300'])
            else:
                # Inkscape 0.9x 旧语法
                cmd = [
                    tool_path,
                    input_path,
                    f'--export-{target_format}={output_path}',
                    '--without-gui'
                ]
                if target_format == 'png':
                    cmd.extend(['--export-dpi=300'])

        elif tool_name in ['gs', 'gswin64c', 'gswin32c']:
            if target_format == 'png':
                cmd = [
                    tool_path,
                    '-dSAFER', '-dBATCH', '-dNOPAUSE',
                    '-r300',
                    '-sDEVICE=pngalpha',
                    f'-sOutputFile={output_path}',
                    input_path
                ]
            else:
                return None
        else:
            return None

        # 修复：设置正确的编码环境
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        # 运行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=False,  # 使用二进制模式
            timeout=60,
            env=env,
            check=True
        )

        # 手动处理输出，避免编码错误
        stdout = b''
        stderr = b''
        if result.stdout:
            stdout = result.stdout.decode('utf-8', errors='ignore')
        if result.stderr:
            stderr = result.stderr.decode('utf-8', errors='ignore')

        # 检查转换结果
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"工具{tool_name}转换成功")
            return output_path
        else:
            logger.error(f"工具{tool_name}转换失败，返回码: {result.returncode}")
            if os.path.exists(output_path):
                os.unlink(output_path)
            return None

    except subprocess.CalledProcessError as e:
        logger.error(f"工具{tool_name}执行失败: {e.returncode}")
        if 'output_path' in locals() and os.path.exists(output_path):
            os.unlink(output_path)
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"工具{tool_name}执行超时")
        if 'output_path' in locals() and os.path.exists(output_path):
            os.unlink(output_path)
        return None
    except Exception as e:
        logger.error(f"工具{tool_name}执行异常: {str(e)}")
        if 'output_path' in locals() and os.path.exists(output_path):
            os.unlink(output_path)
        return None

def _get_inkscape_version(inkscape_path: str) -> Optional[Tuple[int, int, int]]:
    """获取Inkscape版本号"""
    try:
        result = subprocess.run(
            [inkscape_path, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # 解析版本号，如 "Inkscape 1.2.2 (732a01da63, 2022-12-09)"
            version_match = re.search(r'Inkscape\s+([0-9]+)\.([0-9]+)\.([0-9]+)', result.stdout)
            if version_match:
                major = int(version_match.group(1))
                minor = int(version_match.group(2))
                patch = int(version_match.group(3))
                return (major, minor, patch)
    except Exception as e:
        logger.warning(f"获取Inkscape版本失败: {str(e)}")
    return None