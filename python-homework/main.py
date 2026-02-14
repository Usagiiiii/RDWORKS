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
# 仅在未打包时执行此检查
if not getattr(sys, 'frozen', False) and 'QT_QPA_PLATFORM_PLUGIN_PATH' not in os.environ:
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
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from ui.main_window import MainWindow


def main():
    """主函数"""
    # main.py 开头添加
    import sys
    print("Python 模块搜索路径：")
    for path in sys.path:
      print(f"- {path}")
    app = QApplication(sys.argv)

    # -------------------------- 单实例检查逻辑 --------------------------
    server_name = 'RDWorks_Single_Instance_Server'
    socket = QLocalSocket()
    socket.connectToServer(server_name)

    if socket.waitForConnected(500):
        # 如果连接成功，说明已有实例在运行
        # 将命令行参数（文件路径）发送给主实例
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            if os.path.exists(file_path):
                # 发送文件路径，使用 utf-8 编码
                socket.write(file_path.encode('utf-8'))
                socket.waitForBytesWritten(1000)
        
        socket.disconnectFromServer()
        print("已发送参数到主实例，当前进程退出。")
        sys.exit(0)
    else:
        # 如果连接失败，说明这是第一个实例
        # 启动本地服务器监听后续连接
        local_server = QLocalServer()
        # 如果之前非正常退出可能导致 socket 文件残留，尝试移除
        QLocalServer.removeServer(server_name)
        if not local_server.listen(server_name):
            print(f"无法启动单实例监听服务: {local_server.errorString()}")
    # -------------------------------------------------------------------

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

    # -------------------------- 处理新连接请求 --------------------------
    def handle_new_connection():
        """处理来自其他实例的连接请求（即新的文件导入）"""
        new_socket = local_server.nextPendingConnection()
        if new_socket.waitForReadyRead(1000):
            data = new_socket.readAll().data()
            try:
                file_path = data.decode('utf-8')
                if file_path and os.path.exists(file_path):
                    print(f"收到新文件导入请求: {file_path}")
                    # 激活窗口并加载文件
                    window.activateWindow()
                    window.raise_()
                    window.load_image_file(file_path)
            except Exception as e:
                print(f"处理新连接数据出错: {e}")
        new_socket.disconnectFromServer()

    if local_server.isListening():
        local_server.newConnection.connect(handle_new_connection)
    # -------------------------------------------------------------------

    # 检查命令行参数并加载文件（针对首个实例启动时的参数）
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: window.load_image_file(file_path))
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()





























































