import sys
import os
import faulthandler

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from my_io.communication.laser_communicator import LaserCommunicator
from ui.debug_control_dialog import CommandDebugDialog


def main():
    if 'QT_QPA_PLATFORM_PLUGIN_PATH' not in os.environ:
        candidates = [
            os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt', 'plugins'),
            os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
        ]
        for path in candidates:
            if os.path.exists(path):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = path
                break
    faulthandler.enable()
    app = QApplication(sys.argv)

    communicator = LaserCommunicator()
    dialog = CommandDebugDialog(communicator)
    dialog.show()

    def start_monitor():
        # Force serial tab
        dialog.config_tab.setCurrentIndex(0)
        dialog.edit_interval.setText("300")
        dialog.edit_start_addr.setText("1")
        dialog.edit_len.setText("1")
        dialog.on_start_monitor()

    # Trigger after UI shows
    QTimer.singleShot(500, start_monitor)

    # Auto-close after a short period to avoid hanging
    QTimer.singleShot(3000, dialog.close)
    QTimer.singleShot(3200, app.quit)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
