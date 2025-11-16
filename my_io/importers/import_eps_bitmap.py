from typing import Optional, Tuple
import logging
import os
from PIL import Image, EpsImagePlugin
import glob
import sys

logger = logging.getLogger(__name__)


def _setup_ghostscript_path() -> bool:
    """设置Ghostscript路径，优先使用软件目录下的工具"""

    def _get_tools_directory() -> str:
        """获取软件目录下的tools文件夹路径，增加环境变量支持"""
        current_dir = os.path.dirname(os.path.abspath(__file__))  # importers目录
        parent_dir = os.path.dirname(current_dir)  # io目录
        grandparent_dir = os.path.dirname(parent_dir)  # litegcode目录
        base_dir = os.path.dirname(grandparent_dir)  # 项目根目录
        tools_dir = os.path.join(base_dir, 'tools')

        if not os.path.exists(tools_dir):
            tools_dir = os.path.join(os.getcwd(), 'tools')

        if not os.path.exists(tools_dir) and hasattr(sys, '_MEIPASS'):
            tools_dir = os.path.join(sys._MEIPASS, 'tools')

        env_tools_dir = os.environ.get('LITEGCODE_TOOLS_DIR')
        if env_tools_dir and os.path.exists(env_tools_dir):
            tools_dir = env_tools_dir

        return tools_dir if os.path.exists(tools_dir) else ""

    tools_dir = _get_tools_directory()

    # 优先检查软件目录下的Ghostscript
    if tools_dir:
        if sys.platform.startswith('win'):
            gs_patterns = [
                "gs/*/bin/gswin64c.exe",
                "gs/*/bin/gswin32c.exe",
                "gs/bin/gswin64c.exe",
                "gs/bin/gswin32c.exe",
                "*/gswin64c.exe",
                "*/gswin32c.exe"
            ]
            for pattern in gs_patterns:
                full_pattern = os.path.join(tools_dir, pattern)
                matches = glob.glob(full_pattern, recursive=True)
                for match in matches:
                    if os.path.isfile(match) and os.access(match, os.X_OK):
                        EpsImagePlugin.gs_windows_binary = match
                        logger.info(f"使用软件目录下的Ghostscript: {match}")
                        return True
        else:
            gs_patterns = [
                "gs/bin/gs",
                "gs/*/bin/gs",
                "*/gs"
            ]
            for pattern in gs_patterns:
                full_pattern = os.path.join(tools_dir, pattern)
                matches = glob.glob(full_pattern, recursive=True)
                for match in matches:
                    if os.path.isfile(match) and os.access(match, os.X_OK):
                        EpsImagePlugin.gs_windows_binary = match
                        logger.info(f"使用软件目录下的Ghostscript: {match}")
                        return True

    # 检查系统安装的Ghostscript
    possible_paths = []

    if sys.platform.startswith('win'):
        possible_paths.extend([
            os.path.join(os.environ.get('ProgramFiles', ''), 'gs', '*', 'bin', 'gswin64c.exe'),
            os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'gs', '*', 'bin', 'gswin32c.exe'),
            os.path.join('C:\\', 'Program Files', 'gs', '*', 'bin', 'gswin64c.exe'),
            os.path.join('C:\\', 'Program Files (x86)', 'gs', '*', 'bin', 'gswin32c.exe'),
        ])
    else:
        possible_paths.extend([
            '/usr/bin/gs',
            '/usr/local/bin/gs',
            '/opt/homebrew/bin/gs',
        ])

    for pattern in possible_paths:
        matches = glob.glob(pattern, recursive=True)
        for match in matches:
            if os.path.isfile(match) and os.access(match, os.X_OK):
                EpsImagePlugin.gs_windows_binary = match
                logger.info(f"使用系统Ghostscript: {match}")
                return True

    # 检查环境变量
    if 'GHOSTSCRIPT_PATH' in os.environ:
        gs_path = os.environ['GHOSTSCRIPT_PATH']
        if os.path.isfile(gs_path) and os.access(gs_path, os.X_OK):
            EpsImagePlugin.gs_windows_binary = gs_path
            logger.info(f"使用环境变量Ghostscript: {gs_path}")
            return True

    logger.warning("未找到Ghostscript")
    return False


def import_eps_as_bitmap(path: str) -> Tuple[Optional[Image.Image], Optional[str]]:
    """导入EPS为位图"""
    status_msg = "正在处理EPS文件..."

    # 首先尝试直接打开（使用软件目录下的Ghostscript）
    if _setup_ghostscript_path():
        try:
            im = Image.open(path)
            im.load(scale=4)  # 提高分辨率
            status_msg = "✓ 直接打开EPS文件成功（使用软件自带Ghostscript）"
            return im.convert('RGBA'), None
        except Exception as e:
            status_msg = f"直接打开EPS失败: {str(e)}，尝试转换..."

    # 直接打开失败，尝试转换为PNG
    from utils.import_utils import auto_convert_file
    converted_path, convert_msg = auto_convert_file(path, 'png')
    status_msg += "\n" + convert_msg

    if converted_path:
        try:
            im = Image.open(converted_path).convert('RGBA')
            os.unlink(converted_path)
            status_msg += "\n✓ 转换后的PNG导入成功"
            return im, None
        except Exception as e:
            if os.path.exists(converted_path):
                os.unlink(converted_path)
            error_msg = f"转换后的文件打开失败: {str(e)}"
            status_msg += "\n" + error_msg

    # 所有方法都失败
    final_error = (
        "EPS文件处理失败\n\n"
        "已尝试的解决方案：\n"
        "1. 使用软件自带的Ghostscript直接打开\n"
        "2. 使用软件自带的Inkscape转换为PNG格式\n\n"
        "如果仍然失败，请检查：\n"
        "• EPS文件是否损坏\n"
        "• 软件目录下的tools文件夹是否完整\n"
        "• 或手动将EPS转换为PDF/SVG格式后再导入"
    )
    return None, final_error