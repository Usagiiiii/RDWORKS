import sys
from PyQt5.QtWidgets import QApplication
from ui.manufacturer_settings_dialog import ManufacturerSettingsDialog, ManufacturerPasswordDialog

def test():
    app = QApplication(sys.argv)
    
    print("Testing Password Dialog...")
    pwd = ManufacturerPasswordDialog()
    if pwd.exec_() == 1:
        print("Password Accepted.")
        print("Creating Settings Dialog...")
        try:
            dlg = ManufacturerSettingsDialog()
            print("Settings Dialog Created. Showing...")
            dlg.show()
            sys.exit(app.exec_())
        except Exception as e:
            print(f"Error creating/showing settings dialog: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Password Rejected.")

if __name__ == "__main__":
    test()
