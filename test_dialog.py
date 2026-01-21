import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python-homework'))

from PyQt5.QtWidgets import QApplication
from ui.text_dialog import TextDialog

def test():
    app = QApplication(sys.argv)
    
    print("Testing TextDialog...")
    try:
        dlg = TextDialog()
        print("Text Dialog Created. Showing...")
        dlg.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error creating/showing dialog: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
