
import sys
from PyQt5.QtWidgets import QApplication, QGraphicsScene, QGraphicsView
from PyQt5.QtGui import QFont, QPainterPath, QFontDatabase, QTransform, QFontMetrics

# Mocking the dependencies
class TextGraphicsItem_Mock:
    def __init__(self, text, settings):
        self.text_data = text
        self.settings = settings
        self.path = QPainterPath()
        self.rebuild_path()

    def rebuild_path(self):
        try:
            print("Start rebuild_path")
            txt = self.text_data
            if not txt:
                print("No text")
                return

            font_family = self.settings.get('font_family', 'Arial')
            db = QFontDatabase()
            if font_family not in db.families():
                font_family = 'Arial'
            
            if not db.isSmoothlyScalable(font_family):
                font_family = 'Arial'

            print(f"Using font: {font_family}")

            height_mm = self.settings.get('height', 10.0)
            if height_mm <= 0.001: height_mm = 10.0

            width_percent = self.settings.get('width_percent', 100) / 100.0
            if width_percent <= 0.001: width_percent = 1.0

            char_spacing = self.settings.get('char_spacing', 0.0)
            line_spacing = self.settings.get('line_spacing', 0.0)

            font = QFont(font_family)
            font.setPixelSize(100)
            font.setStyleStrategy(QFont.PreferOutline)
            font.setHintingPreference(QFont.PreferNoHinting)
            
            fm = QFontMetrics(font)
            print(f"Font metrics height: {fm.height()}")

            full_path = QPainterPath()
            
            lines = txt.split('\n')
            current_y = 0.0
            base_size = 100
            scale_factor = height_mm / base_size
            scale_x = scale_factor * width_percent
            scale_y = scale_factor

            for line_str in lines:
                if not line_str:
                    continue
                
                current_x_base = 0.0
                spacing_base = char_spacing / scale_x if scale_x else 0
                
                line_base_path = QPainterPath()
                
                if abs(spacing_base) < 0.001:
                     print(f"Adding text directly: {line_str}")
                     line_base_path.addText(0, 0, font, line_str)
                else:
                    for char in line_str:
                         print(f"Adding char: {char}")
                         line_base_path.addText(current_x_base, 0, font, char)
                         
                         if hasattr(fm, 'horizontalAdvance'):
                            adv = fm.horizontalAdvance(char)
                         else:
                            adv = fm.width(char)
                         current_x_base += adv + spacing_base

                t_line = QTransform()
                t_line.scale(scale_x, scale_y)
                
                line_path_final = t_line.map(line_base_path)
                line_path_final.translate(0, current_y)
                
                full_path.addPath(line_path_final)
                
                current_y += fm.height() * scale_y + line_spacing

            self.path = full_path
            print("Path built successfully")
            print(f"Element count: {full_path.elementCount()}")

        except Exception as e:
            print(f"Exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    settings = {
        'font_family': 'Arial',
        'height': 100,
        'width_percent': 100,
        'char_spacing': 0,
        'line_spacing': 0
    }
    
    print("Test 1: Normal Text")
    item = TextGraphicsItem_Mock("Hello World", settings)
    
    print("\nTest 2: Empty Text")
    item2 = TextGraphicsItem_Mock("", settings)
    
    print("\nTest 3: Chinese Text")
    item3 = TextGraphicsItem_Mock("你好", settings)
    
    print("Done")
