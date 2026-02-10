#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图形化白板应用程序
主入口文件
"""

import os
import sys
#cd c:\Users\臧雪鹏\Desktop\RDWORKS-python\python-homework  python modbus_server_sim.py
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
from PyQt5.QtCore import QTranslator, QLibraryInfo
from ui.main_window import MainWindow


def main():
    """主函数"""
    # main.py 开头添加
    import sys
    print("Python 模块搜索路径：")
    for path in sys.path:
      print(f"- {path}")
    app = QApplication(sys.argv)

    # 加载 Qt 中文翻译
    translator = QTranslator()
    
    # 尝试查找翻译文件的路径列表
    translation_paths = [
        QLibraryInfo.location(QLibraryInfo.TranslationsPath),
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'translations'),
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt', 'translations'),
    ]
    
    for path in translation_paths:
        if path and os.path.exists(path):
            # 优先尝试 qt_zh_CN
            if translator.load("qt_zh_CN", path):
                app.installTranslator(translator)
                break
            # 其次尝试 qtbase_zh_CN
            elif translator.load("qtbase_zh_CN", path):
                app.installTranslator(translator)
                break

    app.setStyle('Fusion')  # 使用Fusion样式，更现代
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()





























































