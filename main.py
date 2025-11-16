#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图形化白板应用程序
主入口文件
"""

import sys
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

