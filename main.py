#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图形化白板应用程序
主入口文件
"""

import os
import sys

# 在导入 PyQt5 之前尝试设置 QT 插件路径，避免因用户目录含非 ASCII 字符导致
# QLibraryInfo 返回的路径被替换成问号（例如 C:/Users/???/...）而无法找到 plugins。
if 'QT_QPA_PLATFORM_PLUGIN_PATH' not in os.environ:
  candidates = [
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt', 'plugins'),
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
  ]
  for c in candidates:
    if os.path.exists(c):
      os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = c
      try:
        # 在控制台打印，便于诊断（可删除）
        print("QT_QPA_PLATFORM_PLUGIN_PATH set to:", c)
      except Exception:
        pass
      break

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    """主函数"""
    # main.py 开头添加
    import sys
    print("Python 模块搜索路径：")
    for path in sys.path:
      print(f"- {path}")
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion样式，更现代
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

