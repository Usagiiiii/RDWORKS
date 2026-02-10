
import sys
import os
import signal
from PyQt5.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QGraphicsItem, QDialog, QMessageBox
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainterPath, QColor

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

# Import the modules
from ui.whiteboard import WhiteboardWidget
from ui.graphics_items import EditablePathItem

def reproduce():
    app = QApplication(sys.argv)
    
    # Create the widget
    widget = WhiteboardWidget()
    widget.show()
    
    # Add some items to the canvas
    print("Adding items to canvas...")
    canvas = widget.canvas
    
    # Add a path item
    path = [(0,0), (100,0), (100,100), (0,100)]
    item = EditablePathItem(path, QColor(0,0,0))
    canvas.scene.addItem(item)
    
    # Select the item to trigger handle creation (common crash source)
    print("Selecting item...")
    item.setSelected(True)
    # Process events to let selection logic run (handles creation)
    app.processEvents()
    
    # Simulate user clicking "New File" -> "OK"
    print("Executing clear()...")
    try:
        widget.clear()
        print("Clear finished successfully.")
    except Exception as e:
        print(f"Caught exception during clear: {e}")
        # Crash might happen at C++ level, so this might not catch it.
        
    print("Test complete.")
    # Keep window open for a moment or exit
    # sys.exit(0)

if __name__ == "__main__":
    reproduce()
