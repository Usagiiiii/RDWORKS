import glob
import os
import sys
import logging
from typing import Optional

from PyQt5.QtWidgets import QMessageBox

# 初始化日志
logger = logging.getLogger(__name__)


def check_required_tools(main_window):
    """检查Inkscape等必要工具是否存在"""
    if not _check_conversion_tool('inkscape'):
        msg = "未找到Inkscape工具，AI/SVG转换功能将不可用。\n请安装Inkscape并确保其在PATH中，或放在软件tools目录下，\n也可通过设置环境变量 LITEGCODE_INKSCAPE_PATH 指定工具路径。"
        main_window.logger.error(msg)
        QMessageBox.warning(main_window, "工具缺失", msg)


def _check_conversion_tool(tool: str) -> Optional[str]:
    """检查转换工具是否存在，优先顺序：环境变量 > 软件tools目录 > 系统PATH"""
    # 新增: 优先检查环境变量指定的工具路径（如LITEGCODE_INKSCAPE_PATH）
    env_tool_path = os.environ.get(f"LITEGCODE_{tool.upper()}_PATH")
    if env_tool_path and os.path.exists(env_tool_path) and os.access(env_tool_path, os.X_OK):
        logger.info(f"从环境变量找到工具: {env_tool_path}")
        return env_tool_path

    tools_dir = _get_tools_directory()

    # 检查软件目录下的tools文件夹
    if tools_dir:
        tool_path = _find_tool_in_directory(tool, tools_dir)
        if tool_path:
            logger.info(f"在软件目录下找到工具: {tool_path}")
            return tool_path

    # 检查系统PATH
    for path in os.environ.get('PATH', '').split(os.pathsep):
        exe_path = os.path.join(path, tool)
        if sys.platform.startswith('win'):
            exe_path += '.exe'
        if os.path.exists(exe_path) and os.access(exe_path, os.X_OK):
            logger.info(f"在系统PATH中找到工具: {exe_path}")
            return exe_path

    logger.warning(f"未找到工具: {tool}")
    return None


def _get_tools_directory() -> str:
    """获取软件目录下的tools文件夹路径，增加环境变量支持"""
    # 方法1: 从当前文件路径向上查找（更可靠的层级计算）
    current_dir = os.path.dirname(os.path.abspath(__file__))  # io目录
    parent_dir = os.path.dirname(current_dir)  # litegcode目录
    base_dir = os.path.dirname(parent_dir)  # 项目根目录
    tools_dir = os.path.join(base_dir, 'tools')

    # 方法2: 从工作目录查找
    if not os.path.exists(tools_dir):
        tools_dir = os.path.join(os.getcwd(), 'tools')

    # 方法3: 从可执行文件所在目录查找（打包后）
    if not os.path.exists(tools_dir) and hasattr(sys, '_MEIPASS'):
        tools_dir = os.path.join(sys._MEIPASS, 'tools')

    # 新增: 检查环境变量指定的工具目录（优先级最高）
    env_tools_dir = os.environ.get('LITEGCODE_TOOLS_DIR')
    if env_tools_dir and os.path.exists(env_tools_dir):
        tools_dir = env_tools_dir

    return tools_dir if os.path.exists(tools_dir) else ""


def _find_tool_in_directory(tool_name: str, tools_dir: str) -> Optional[str]:
    """在指定目录中查找工具，扩展查找模式以覆盖更多路径"""
    if not os.path.exists(tools_dir):
        return None

    # Windows可执行文件模式（增加更多可能路径）
    if sys.platform.startswith('win'):
        patterns = [
            f"{tool_name}.exe",  # 直接在tools目录下
            f"{tool_name}/{tool_name}.exe",  # 工具同名子目录
            f"{tool_name}/bin/{tool_name}.exe",  # 工具子目录的bin文件夹
            f"bin/{tool_name}.exe",  # tools/bin目录
            f"*/{tool_name}.exe",  # 任意一级子目录
            f"*/*/{tool_name}.exe",  # 任意二级子目录
            f"Portable{tool_name}/{tool_name}.exe"  # 便携版目录
        ]
    else:
        # Linux/Mac可执行文件模式
        patterns = [
            f"{tool_name}",  # 直接在tools目录下
            f"{tool_name}/{tool_name}",  # 工具同名子目录
            f"{tool_name}/bin/{tool_name}",  # 工具子目录的bin文件夹
            f"bin/{tool_name}",  # tools/bin目录
            f"*/{tool_name}",  # 任意一级子目录
            f"*/*/{tool_name}",  # 任意二级子目录
            f".local/bin/{tool_name}"  # 用户本地安装目录
        ]

    for pattern in patterns:
        full_pattern = os.path.join(tools_dir, pattern)
        matches = glob.glob(full_pattern, recursive=True)
        for match in matches:
            if os.path.isfile(match) and os.access(match, os.X_OK):
                return match

    return None