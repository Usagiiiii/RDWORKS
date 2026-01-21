
from PyQt5.QtWidgets import QApplication, QColorDialog, QPushButton, QGridLayout
from PyQt5.QtCore import Qt
import sys
import os

# Setup environment
if 'QT_QPA_PLATFORM_PLUGIN_PATH' not in os.environ:
  candidates = [
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt', 'plugins'),
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
  ]
  for c in candidates:
    if os.path.exists(c):
      os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = c
      break

def inspect(widget, indent=0):
    try:
        txt = getattr(widget, 'text', lambda: '')()
        name = widget.objectName()
        meta = widget.metaObject().className()
        print(" " * indent + f"{type(widget).__name__} ({meta}) name='{name}' text='{txt}' size={widget.size()}")
    except:
         print(" " * indent + f"{type(widget).__name__}")
         
    for child in widget.children():
        inspect(child, indent + 2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = QColorDialog()
    dialog.setOption(QColorDialog.DontUseNativeDialog)
    dialog.show()
    
    # Process events to ensure UI is built
    app.processEvents()
    
    print("--- Hierarchy ---")
    inspect(dialog)
