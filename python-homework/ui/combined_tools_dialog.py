from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import  QPixmap, QImage, QColor
from .debug_control_dialog import CommandDebugDialog
from PyQt5.QtWidgets import QMessageBox, QGraphicsPixmapItem
import sys
import os

class CombinedToolsDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("综合工具箱")
        self.resize(1000, 650) 
        
        # Add Maximize and Minimize buttons
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab Widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # --- Tab 1: Command & Debug ---
        # We need the communicator from main_window -> right_panel
        communicator = None
        if hasattr(self.main_window, 'right_panel') and hasattr(self.main_window.right_panel, 'communicator'):
            communicator = self.main_window.right_panel.communicator
            
        self.debug_dialog = CommandDebugDialog(communicator, self)
        self.debug_dialog.setWindowFlags(Qt.Widget) # Embed as widget
        # CommandDebugDialog might set its own layout with margins, we might want to check that
        self.tab_widget.addTab(self.debug_dialog, "通讯和G代码(G)")
        
        # --- Tab 2: Laser Image Gcode Sender (Formerly Bitmap Process) ---
        try:
             # Ensure root dir is in path to import laser.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(current_dir)
            if root_dir not in sys.path:
                sys.path.append(root_dir)
                
            from laser import LaserImageGcodeSender
            
            self.laser_sender = LaserImageGcodeSender()
            # LaserImageGcodeSender is a QMainWindow. 
            # We can use it as a widget, but we should make sure it behaves well.
            self.laser_sender.setWindowFlags(Qt.Widget)
            
            # If target item is selected in canvas, maybe we can load it into laser sender?
            # The user just asked to restore the interface, not necessarily preserve the workflow of "edit and apply back".
            # But let's check if we can pre-load the image if one is selected.
            target_item = self._get_target_item()
            if target_item and hasattr(target_item, 'pixmap'):
                 # LaserImageGcodeSender usually loads from file. 
                 # We could save temporary file or see if it has a load_image from pixmap/image method.
                 # For now, just showing the interface is the request.
                 pass
            
            self.tab_widget.addTab(self.laser_sender, "图像灰度处理(Z)")
            
        except Exception as e:
            error_widget = QWidget()
            layout_err = QVBoxLayout(error_widget)
            from PyQt5.QtWidgets import QLabel
            layout_err.addWidget(QLabel(f"无法加载 LaserImageGcodeSender: {e}"))
            self.tab_widget.addTab(error_widget, "图像灰度处理(Z)")

    def _get_target_item(self):
        if not hasattr(self.main_window, 'whiteboard') or not self.main_window.whiteboard:
            return None
        
        selected_items = self.main_window.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            return None
            
        # Find first pixmap item
        for item in selected_items:
            if isinstance(item, QGraphicsPixmapItem):
                return item
        return None

    def _get_target_item(self):
        if not hasattr(self.main_window, 'whiteboard') or not self.main_window.whiteboard:
            return None
        
        selected_items = self.main_window.whiteboard.canvas.scene.selectedItems()
        if not selected_items:
            return None
            
        # Find first pixmap item
        for item in selected_items:
            if isinstance(item, QGraphicsPixmapItem):
                return item
        return None
