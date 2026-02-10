
import sys
import os
from PyQt5.QtWidgets import QApplication, QGraphicsScene, QGraphicsPathItem
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QPainterPath, QTransform, QFont, QFontDatabase

# Setup path to import modules
sys.path.append(os.getcwd())

from ui.graphics_items import TextGraphicsItem
from my_io.gcode.gcode_exporter import GCodeExporter

def debug_export():
    app = QApplication(sys.argv)
    
    # 1. Create Text Item
    settings = {
        'font_family': 'Arial',
        'is_bold': False,
        'is_italic': False,
        'height': 50.0, # 50mm height
        'width_percent': 100,
        'char_spacing': 0,
        'line_spacing': 0
    }
    text_item = TextGraphicsItem("摸鱼", settings)
    text_item.setPos(100, 100)
    
    # Check path
    path = text_item.path()
    print(f"Path Element Count: {path.elementCount()}")
    print(f"Path Control Point Rect: {path.controlPointRect()}")
    
    if path.isEmpty():
        print("ERROR: Path is empty!")
        return

    # 2. Simulate Export Logic
    print("\n--- Simulating Export Logic ---")
    
    # Map to scene
    # Since item is not in a scene, mapToScene acts like mapToParent or mapFromItem(self, path) ?
    # mapToScene(path) is equivalent to sceneTransform().map(path)
    # Since no scene, sceneTransform is just item transform?
    # TextGraphicsItem usually has no transform unless rotated/scaled.
    # But it has setPos(100, 100).
    
    # mapToScene works if item is in scene, or using mapToScene(path) uses item's total transformation.
    # Let's add to scene to be sure.
    scene = QGraphicsScene()
    scene.addItem(text_item)
    
    scene_path = text_item.mapToScene(path)
    print(f"Scene Path Rect: {scene_path.controlPointRect()}")
    
    polygons = scene_path.toSubpathPolygons(QTransform()) # Flatten with default transform (identity)
    print(f"Polygons count: {len(polygons)}")
    
    total_points = 0
    for i, poly in enumerate(polygons):
        pts = []
        for pt in poly:
            pts.append((pt.x(), pt.y()))
        total_points += len(pts)
        if i < 2: # Print first few polygons details
            print(f"Poly {i} points: {len(pts)}")
            print(f"  Start: {pts[0]}")
            print(f"  End: {pts[-1]}")
            
    print(f"Total points generated: {total_points}")
    
    if total_points < 10:
        print("ERROR: Too few points for text!")
    else:
        print("SUCCESS: Text seems to generate points.")

if __name__ == "__main__":
    try:
        debug_export()
    except Exception as e:
        import traceback
        traceback.print_exc()
