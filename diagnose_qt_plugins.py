# -*- coding: utf-8 -*-
"""
诊断脚本：定位 Qt 插件路径并查找 qwindows.dll
用法：在与你运行程序相同的 Python 环境中运行：
    python diagnose_qt_plugins.py

将输出粘贴到聊天中，我会基于输出给出修复方案。
"""
import sys
import os
import platform
import shutil

print("=== 环境与可执行信息 ===")
print("Python executable:", sys.executable)
print("Python version:", sys.version.replace('\n', ' '))
print("Platform:", platform.platform())
print("Architecture:", platform.architecture())
print()

# Try PyQt5 then PySide2
binding = None
try:
    from PyQt5.QtCore import QLibraryInfo
    import PyQt5
    binding = 'PyQt5'
    binding_file = PyQt5.__file__
except Exception:
    try:
        from PySide2.QtCore import QLibraryInfo
        import PySide2
        binding = 'PySide2'
        binding_file = PySide2.__file__
    except Exception:
        QLibraryInfo = None
        binding_file = None

print('Detected Qt binding:', binding)
print('Binding file:', binding_file)

if QLibraryInfo is not None:
    try:
        plugins_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
        print('\nQLibraryInfo.PluginsPath =', plugins_path)
    except Exception as e:
        print('无法通过 QLibraryInfo 获取 PluginsPath:', e)
        plugins_path = None

    if plugins_path and os.path.exists(plugins_path):
        platforms_dir = os.path.join(plugins_path, 'platforms')
        print('Plugins path exists:', True)
        print('platforms dir:', platforms_dir)
        if os.path.exists(platforms_dir):
            print('platforms contents:')
            try:
                for fn in sorted(os.listdir(platforms_dir)):
                    print(' -', fn)
            except Exception as e:
                print(' 列出 contents 失败:', e)
        else:
            print('platforms 子目录不存在')
    else:
        print('PluginsPath 不存在或未解析')
else:
    print('\n没有检测到可用的 Qt 绑定（PyQt5/PySide2）')

print('\n=== 环境变量相关 ===')
print('QT_QPA_PLATFORM_PLUGIN_PATH =', os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH'))
print('QT_PLUGIN_PATH =', os.environ.get('QT_PLUGIN_PATH'))
print('QT_DEBUG_PLUGINS =', os.environ.get('QT_DEBUG_PLUGINS'))
print()

print('=== 在 site-packages 中搜索 qwindows.dll（这可能要几秒钟） ===')
found = []
# search common site-packages locations
candidates = []
# Add sys.prefix site-packages
candidates.append(os.path.join(sys.prefix, 'Lib', 'site-packages'))
# also try sys.base_prefix for virtualenv edge cases
if sys.base_prefix and sys.base_prefix != sys.prefix:
    candidates.append(os.path.join(sys.base_prefix, 'Lib', 'site-packages'))
# Also check in sys.path entries
for p in sys.path:
    candidates.append(p)

seen = set()
for base in candidates:
    if not base:
        continue
    base = os.path.abspath(base)
    if base in seen:
        continue
    seen.add(base)
    if os.path.exists(base):
        for root, dirs, files in os.walk(base):
            if 'qwindows.dll' in files:
                full = os.path.join(root, 'qwindows.dll')
                found.append(full)

if found:
    print('Found qwindows.dll:')
    for f in found:
        print(' -', f)
else:
    print('No qwindows.dll found in searched site-packages paths.')

print('\n=== 在 PATH 中查找可能的 Qt DLL 目录（列出包含 Qt 或 Inkscape 的 PATH 条目） ===')
for p in os.environ.get('PATH', '').split(os.pathsep):
    if 'Qt' in p or 'Inkscape' in p or 'inkscape' in p:
        print(' -', p)

print('\n=== 小结/下一步建议 ===')
print("1) 如果找到了 qwindows.dll：请确保在运行程序前设置环境变量 'QT_QPA_PLATFORM_PLUGIN_PATH' 指向上面 'plugins' 的父目录（包含 'platforms' 子目录）。")
print("   示例（PowerShell）： $env:QT_QPA_PLATFORM_PLUGIN_PATH = 'C:\\Path\\to\\site-packages\\PyQt5\\Qt\\plugins'; python main.py")
print("2) 如果没有找到 qwindows.dll：建议重新安装 PyQt5： pip uninstall -y PyQt5; pip install PyQt5")
print("3) 如果你使用 PyInstaller 打包：确保在 dist 目录下放置一个 'platforms' 文件夹，里面有 qwindows.dll，或者在打包时使用 --add-data 将插件包含进去。")
print('\n请把这个脚本的完整输出粘贴到聊天中，我会基于输出给出精确修复步骤。')
