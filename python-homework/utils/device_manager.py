import json
import os
from PyQt5.QtCore import QObject, pyqtSignal

CONFIG_FILE = "devices.json"

class DeviceManager(QObject):
    _instance = None
    devices_changed = pyqtSignal() # 信号：设备列表发生变化

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeviceManager, cls).__new__(cls)
            # 必须显式调用 QObject 的初始化，否则 C++ 部分未初始化会导致 RuntimeError
            super(DeviceManager, cls._instance).__init__()
        return cls._instance
    
    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return
        # super().__init__() # Removed: already called in __new__
        self.devices = []
        self.load_devices()
        self._initialized = True

    def load_devices(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.devices = json.load(f)
            except:
                self.devices = []
        
        if not self.devices:
            # 默认设备
            self.devices = [{"name": "Device", "address": "USB:自动"}]

    def save_devices(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.devices, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving devices: {e}")

    def get_devices(self):
        return self.devices

    def add_device(self, name, address):
        self.devices.append({"name": name, "address": address})
        self.save_devices()
        self.devices_changed.emit()

    def remove_device(self, index):
        if 0 <= index < len(self.devices):
            self.devices.pop(index)
            self.save_devices()
            self.devices_changed.emit()

    def update_device(self, index, name, address):
        if 0 <= index < len(self.devices):
            self.devices[index] = {"name": name, "address": address}
            self.save_devices()
            self.devices_changed.emit()
