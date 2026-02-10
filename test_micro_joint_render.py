
import sys
import os

# Add local path for imports
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'python-homework'))

from PyQt5.QtWidgets import QApplication, QGraphicsScene, QGraphicsView
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPainter, QImage, QColor, QPen

# Attempt to import EditablePathItem
# Depending on where the file is located relative to execution
try:
    from ui.graphics_items import EditablePathItem
except ImportError:
    # Try adjusting path
    sys.path.append(os.path.join(os.getcwd(), 'python-homework'))
    from ui.graphics_items import EditablePathItem

def test_render():
    app = QApplication(sys.argv)
    
    # Create a scene
    scene = QGraphicsScene(0, 0, 200, 200)
    
    # Create points for a rect (Open shape for now, 4 points)
    # 100x100 rect
    pts = [(50, 50), (150, 50), (150, 150), (50, 150), (50, 50)] # Closed 5 points
    
    item = EditablePathItem(pts, QColor(0, 0, 0))
    scene.addItem(item)
    
    # Configure micro-joint
    config = {
        'enabled': True,
        'mode': 'qty',
        'qty': 5,
        'dist': 1.0,
        'width': 2.0
    }
    item.micro_joint_config = config
    
    # Render to image
    image = QImage(200, 200, QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    
    scene.render(painter)
    painter.end()
    
    # Check pixels manually or save
    image.save("debug_micro_joint.png")
    print("Saved debug_micro_joint.png")
    
    # We can also check if _draw_micro_joints was actually called if we mock it?
    # Or just inspect the code again.

if __name__ == "__main__":
    test_render()
