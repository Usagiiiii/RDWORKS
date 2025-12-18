import json
import os

CONFIG_FILE = "devices.json"

class DeviceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeviceManager, cls).__new__(cls)
            cls._instance.devices = []
            cls._instance.load_devices()
        return cls._instance

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

    def remove_device(self, index):
        if 0 <= index < len(self.devices):
            self.devices.pop(index)
            self.save_devices()

    def update_device(self, index, name, address):
        if 0 <= index < len(self.devices):
            self.devices[index] = {"name": name, "address": address}
            self.save_devices()
