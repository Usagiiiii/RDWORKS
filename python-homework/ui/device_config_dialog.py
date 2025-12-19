from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QLabel, QLineEdit, QRadioButton, QComboBox, QGroupBox, QMessageBox, QWidget, QApplication)
from PyQt5.QtCore import Qt
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from utils.device_manager import DeviceManager

class PortSettingDialog(QDialog):
    def __init__(self, parent=None, name="", mode="USB", port="自动", ip="192.168.1.100"):
        super().__init__(parent)
        self.setWindowTitle("设置端口")
        self.resize(450, 250)
        
        self.name = name
        self.mode = mode
        self.port = port
        self.ip = ip
        
        self.init_ui()
        self.update_ui_state()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 机器名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("机器名称:"))
        self.name_edit = QLineEdit(self.name)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 端口设置区域
        # 使用 GridLayout 或者 VBox + HBox 模拟
        
        # USB 选项
        usb_layout = QHBoxLayout()
        self.usb_radio = QRadioButton("USB")
        self.usb_radio.setChecked(self.mode == "USB")
        self.usb_radio.toggled.connect(self.update_ui_state)
        usb_layout.addWidget(self.usb_radio)
        
        usb_settings_layout = QHBoxLayout()
        usb_settings_layout.addSpacing(40) # Indent
        usb_settings_layout.addWidget(QLabel("端口号:"))
        self.port_combo = QComboBox()
        self.port_combo.setView(QListView()) # 解决遮挡问题
        self.port_combo.setEditable(True)
        self.port_combo.lineEdit().setReadOnly(True)
        self.port_combo.setStyleSheet("QComboBox { background-color: #ffffff; }")
        self.port_combo.addItems(["自动", "COM1", "COM2", "COM3", "COM4"])
        self.port_combo.setCurrentText(self.port)
        usb_settings_layout.addWidget(self.port_combo, 1)
        self.btn_test_usb = QPushButton("测试")
        self.btn_test_usb.clicked.connect(self.on_btn_test_usb_clicked)
        usb_settings_layout.addWidget(self.btn_test_usb)
        
        layout.addLayout(usb_layout)
        layout.addLayout(usb_settings_layout)

        # 网络 选项
        net_layout = QHBoxLayout()
        self.net_radio = QRadioButton("网络")
        self.net_radio.setChecked(self.mode == "Network")
        self.net_radio.toggled.connect(self.update_ui_state)
        net_layout.addWidget(self.net_radio)
        
        net_settings_layout = QHBoxLayout()
        net_settings_layout.addSpacing(40) # Indent
        net_settings_layout.addWidget(QLabel("IP地址:"))
        self.ip_edit = QLineEdit(self.ip)
        # 简单的 IP 输入掩码，实际项目中可以使用更复杂的验证
        self.ip_edit.setInputMask("000.000.000.000;_") 
        net_settings_layout.addWidget(self.ip_edit, 1)
        self.btn_test_net = QPushButton("测试")
        self.btn_test_net.clicked.connect(self.on_btn_test_net_clicked)
        net_settings_layout.addWidget(self.btn_test_net)

        layout.addLayout(net_layout)
        layout.addLayout(net_settings_layout)

        layout.addStretch(1)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        # 左侧可以是状态栏或者留空
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("border: 1px solid gray; border-radius: 2px;")
        self.status_label.setFixedHeight(20)
        bottom_layout.addWidget(self.status_label, 1)

        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        bottom_layout.addWidget(self.btn_ok)
        bottom_layout.addWidget(self.btn_cancel)

        layout.addLayout(bottom_layout)

    def update_ui_state(self):
        is_usb = self.usb_radio.isChecked()
        
        self.port_combo.setEnabled(is_usb)
        self.btn_test_usb.setEnabled(is_usb)
        
        self.ip_edit.setEnabled(not is_usb)
        self.btn_test_net.setEnabled(not is_usb)

    def on_btn_test_usb_clicked(self):
        port = self.port_combo.currentText()
        if port == "自动" or not port:
             QMessageBox.information(self, "提示", "请选择具体的端口号进行测试")
             return
             
        self.status_label.setText(f"正在测试串口 {port}...")
        QApplication.processEvents()
        
        try:
            # 尝试连接串口，使用默认波特率 115200
            client = ModbusSerialClient(method='rtu', port=port, baudrate=115200, timeout=1)
            if client.connect():
                self.status_label.setText("测试成功")
                QMessageBox.information(self, "成功", f"串口 {port} 连接成功！")
                client.close()
            else:
                self.status_label.setText("测试失败")
                QMessageBox.warning(self, "失败", f"串口 {port} 连接失败！\n请检查端口是否被占用或设备是否连接。")
        except Exception as e:
            self.status_label.setText("测试出错")
            QMessageBox.critical(self, "错误", f"连接出错: {str(e)}")

    def on_btn_test_net_clicked(self):
        ip = self.ip_edit.text()
        port = 502 # 默认 Modbus TCP 端口
        
        self.status_label.setText(f"正在测试 {ip}:{port}...")
        QApplication.processEvents()
        
        try:
            client = ModbusTcpClient(ip, port=port, timeout=2)
            if client.connect():
                self.status_label.setText("测试成功")
                QMessageBox.information(self, "成功", f"Modbus-TCP {ip} 连接成功！")
                client.close()
            else:
                self.status_label.setText("测试失败")
                QMessageBox.warning(self, "失败", f"Modbus-TCP {ip} 连接失败！\n请检查IP地址是否正确或设备是否在线。")
        except Exception as e:
            self.status_label.setText("测试出错")
            QMessageBox.critical(self, "错误", f"连接出错: {str(e)}")

    def get_data(self):
        mode = "USB" if self.usb_radio.isChecked() else "Network"
        return {
            "name": self.name_edit.text(),
            "mode": mode,
            "port": self.port_combo.currentText(),
            "ip": self.ip_edit.text()
        }


class DeviceConfigDialog(QDialog):
    def __init__(self, parent=None, current_index=0):
        super().__init__(parent)
        self.setWindowTitle("设备管理") 
        self.resize(400, 300)
        self.current_index = current_index
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["机器名", "COM口/IP地址"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # 连接点击信号以实现单选
        self.table.itemClicked.connect(self.on_table_item_clicked)
        
        # 样式
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                gridline-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }
        """)

        # 加载数据
        self.device_manager = DeviceManager()
        self.refresh_table()

        layout.addWidget(self.table)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.btn_add = QPushButton("添加")
        self.btn_del = QPushButton("删除")
        self.btn_mod = QPushButton("修改")
        self.btn_exit = QPushButton("退出")
        
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.btn_del.clicked.connect(self.on_del_clicked)
        self.btn_mod.clicked.connect(self.on_mod_clicked)
        self.btn_exit.clicked.connect(self.accept)

        # 按钮样式
        for btn in [self.btn_add, self.btn_del, self.btn_mod, self.btn_exit]:
            btn.setMinimumHeight(28)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

    def refresh_table(self):
        self.table.setRowCount(0)
        devices = self.device_manager.get_devices()
        for i, dev in enumerate(devices):
            # 使用传入的 current_index 来决定默认选中项
            is_checked = (i == self.current_index)
            self.add_device_row(dev['name'], dev['address'], checked=is_checked)

    def add_device_row(self, name, address, checked=False):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 机器名 (带复选框)
        item_name = QTableWidgetItem(name)
        item_name.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item_name.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.setItem(row, 0, item_name)
        
        # 地址
        item_addr = QTableWidgetItem(address)
        item_addr.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.table.setItem(row, 1, item_addr)

    def on_table_item_clicked(self, item):
        """处理表格点击，实现单选互斥"""
        row = item.row()
        self.set_selected_row(row)

    def set_selected_row(self, target_row):
        """设置选中行，并取消其他行的选中状态"""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            state = Qt.Checked if row == target_row else Qt.Unchecked
            it.setCheckState(state)
        self.table.blockSignals(False)
        
        # 更新当前索引
        self.current_index = target_row

    def get_selected_index(self):
        """获取当前选中的设备索引"""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.Checked:
                return row
        return -1

    def on_add_clicked(self):
        dialog = PortSettingDialog(self, name="Device", mode="USB", port="自动")
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            address = f"USB:{data['port']}" if data['mode'] == "USB" else f"Web:{data['ip']}"
            self.device_manager.add_device(data['name'], address)
            self.refresh_table()

    def on_del_clicked(self):
        row = self.table.currentRow()
        if row >= 0:
            self.device_manager.remove_device(row)
            self.refresh_table()
        else:
            QMessageBox.warning(self, "提示", "请先选择要删除的设备")

    def on_mod_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要修改的设备")
            return

        item_name = self.table.item(row, 0)
        item_addr = self.table.item(row, 1)
        
        name = item_name.text()
        address = item_addr.text()
        
        mode = "USB"
        port = "自动"
        ip = "192.168.1.100"
        
        if address.startswith("Web:"):
            mode = "Network"
            ip = address.split(":", 1)[1]
        elif address.startswith("USB:"):
            mode = "USB"
            port = address.split(":", 1)[1]

        dialog = PortSettingDialog(self, name=name, mode=mode, port=port, ip=ip)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            new_address = f"USB:{data['port']}" if data['mode'] == "USB" else f"Web:{data['ip']}"
            
            self.device_manager.update_device(row, data['name'], new_address)
            self.refresh_table()
