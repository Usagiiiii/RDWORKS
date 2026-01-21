
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'python-homework'))

from PyQt5.QtWidgets import QApplication
from ui.system_settings_dialog import SystemSettingsDialog

if __name__ == "__main__":
    app = QApplication(sys.argv)
    print("Creating SystemSettingsDialog...")
    try:
        dlg = SystemSettingsDialog(None) # Parent is None
        print("Dialog created. Showing...")
        dlg.show()
        # sys.exit(app.exec_()) # Don't need to run event loop for crash check generally, but lets try
        print("Show called.")
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()
