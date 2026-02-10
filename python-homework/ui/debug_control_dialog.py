from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QLineEdit, QTextEdit, QGroupBox, QComboBox, QCheckBox,
                             QSplitter, QWidget, QAbstractItemView, QFileDialog, QTabWidget,
                             QFormLayout, QApplication)
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, QThread
import datetime
import os
import tempfile
import re
from utils.device_manager import DeviceManager
from PyQt5.QtWidgets import QMessageBox # Ensure QMessageBox is imported
from pymodbus.client import ModbusTcpClient


class _MonitorWorker(QObject):
    result = pyqtSignal(list)
    error = pyqtSignal(str)

    def do_read(self, client, start_addr: int, reg_count: int):
        try:
            if client is None:
                self.error.emit("Client is not available")
                return

            try:
                rr = client.read_holding_registers(start_addr, count=reg_count, device_id=1)
            except TypeError:
                try:
                    rr = client.read_holding_registers(start_addr, count=reg_count, slave=1)
                except TypeError:
                    rr = client.read_holding_registers(start_addr, count=reg_count, unit=1)

            if rr.isError():
                self.error.emit(f"Modbus Error: {rr}")
                return

            regs = rr.registers if hasattr(rr, "registers") else []
            self.result.emit(regs)
        except Exception as e:
            self.error.emit(f"Exception: {str(e)}")

class CommandDebugDialog(QDialog):
    monitor_request = pyqtSignal(object, int, int)
    def on_start_monitor(self):
        # 1. 获取连接参数
        current_tab_idx = self.config_tab.currentIndex()
        is_tcp = (current_tab_idx == 1)
        
        connect_success = False
        address_str = ""
        
        # 2. 尝试连接
        if is_tcp:
            ip = self.edit_ip.text().strip()
            port_str = self.edit_port.text().strip()
            if not ip:
                 QMessageBox.warning(self, "参数错误", "请输入IP地址")
                 return
            try:
                port = int(port_str)
                address_str = f"Web:{ip}" # 预先生成地址字符串
                # 连接 TCP
                if self.communicator.connect_tcp(ip, port):
                    connect_success = True
            except ValueError:
                 QMessageBox.warning(self, "参数错误", "端口号必须是数字")
                 return
        else:
            # 串口连接
            port_name = self.combo_port.currentText()
            try:
                baud = int(self.combo_baud.currentText())
                # 获取其他参数
                parity_map = {"None": "N", "Even": "E", "Odd": "O", "Mark": "M", "Space": "S"}
                parity = parity_map.get(self.combo_parity.currentText(), "N")
                bytesize = int(self.combo_bytesize.currentText())
                stopbits_str = self.combo_stopbits.currentText()
                stopbits = float(stopbits_str) if '.' in stopbits_str else int(stopbits_str)
                
                address_str = f"USB:{port_name}" # 预先生成地址字符串
                if self.communicator.connect_rtu(port_name, baud, bytesize, parity, stopbits):
                    connect_success = True
            except Exception as e:
                self.append_error_log(f"参数解析失败: {e}")
                return

        if not connect_success:
            # 不弹窗阻断，只记录日志
            self.append_error_log("连接尝试失败，进入离线监测模式")
        
        # 3. 连接成功：处理设备保存 (仅成功时保存新设备)
        if connect_success:
            dm = DeviceManager()
            devices = dm.get_devices()
            exists = False
            for d in devices:
                if d.get("address") == address_str:
                    exists = True
                    break
            
            if not exists:
                # 自动添加新设备
                new_name = f"Device_{len(devices)+1}"
                dm.add_device(new_name, address_str)
                self.append_send_log(f"新设备已保存: {new_name} ({address_str})")

        # 4. 启动监测逻辑 (无论连接是否成功都启动)
        self.btn_start_mon.setEnabled(False)
        self.btn_stop_mon.setEnabled(True)
        # 禁用配置面板防止修改
        self.config_tab.setEnabled(False) 
        
        interval = int(self.edit_interval.text()) if self.edit_interval.text().isdigit() else 300
        
        if not is_tcp:
            # 串口监测
            self.monitor_timer = QTimer(self)
            self.monitor_timer.timeout.connect(self._monitor_send_serial)
            self.monitor_timer.start(interval)
            self.append_send_log("串口监测已启动，每{}ms发送一次".format(interval))
        else:
            # TCP/IP 监测
            if not hasattr(self, 'monitor_tcp_seq'):
                self.monitor_tcp_seq = 0
            self.monitor_timer = QTimer(self)
            self.monitor_timer.timeout.connect(self._monitor_tcp_step)
            self.monitor_timer.start(interval)
            self.append_send_log("TCP/IP 监测已启动，每{}ms发送一次".format(interval))


    def _monitor_tcp_step(self):
        # TCP 监测数据包
        tid = self.monitor_tcp_seq
        self.monitor_tcp_seq = (self.monitor_tcp_seq + 1) % 65535

        # 读取监测参数
        try:
            start_addr = int(self.edit_start_addr.text().strip())
        except Exception:
            start_addr = 1
        try:
            reg_count = int(self.edit_len.text().strip())
        except Exception:
            reg_count = 1
        if reg_count <= 0:
            reg_count = 1

        # 构造发送日志 (Hex)
        hex_send = f"{tid:04X}000000060103{start_addr:04X}{reg_count:04X}"
        self.append_send_log(hex_send)

        # 实际发送 Modbus TCP 请求
        if self.communicator.client and self.communicator.is_connected:
            if self._monitor_busy:
                return
            self._monitor_busy = True
            self._pending_monitor_mode = "tcp"
            self._pending_tcp_tid = tid
            self.monitor_request.emit(self.communicator.client, start_addr, reg_count)

    def _calc_crc16(self, data: bytes) -> int:
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for i in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def _monitor_send_serial(self):
        # 串口监测发送一条读保持寄存器指令
        try:
            start_addr = int(self.edit_start_addr.text().strip())
        except Exception:
            start_addr = 1
        try:
            reg_count = int(self.edit_len.text().strip())
        except Exception:
            reg_count = 1
        if reg_count <= 0:
            reg_count = 1

        raw_req = f"0103{start_addr:04X}{reg_count:04X}"
        crc = self._calc_crc16(bytes.fromhex(raw_req))
        crc_lo = crc & 0xFF
        crc_hi = (crc >> 8) & 0xFF
        hex_send = f"{raw_req}{crc_lo:02X}{crc_hi:02X}"
        self.append_send_log(hex_send.upper())

        # 如果串口已打开，尝试读取并显示返回数据
        if self.communicator.client and (self.communicator.is_connected or getattr(self.communicator, "is_port_open", False)):
            if self._monitor_busy:
                return
            self._monitor_busy = True
            self._pending_monitor_mode = "serial"
            self.monitor_request.emit(self.communicator.client, start_addr, reg_count)

    def _handle_monitor_result(self, regs):
        mode = self._pending_monitor_mode
        self._pending_monitor_mode = None

        if mode == "tcp":
            tid = self._pending_tcp_tid if self._pending_tcp_tid is not None else 0
            self._pending_tcp_tid = None
            self._handle_tcp_monitor_result(tid, regs)
            return

        if mode == "serial":
            self._handle_serial_monitor_result(regs)
            return

        # Fallback: treat as serial-style response
        self._handle_serial_monitor_result(regs)

    def _handle_tcp_monitor_result(self, tid, regs):
        try:
            byte_count = len(regs) * 2
            data_hex = "".join([f"{v:04X}" for v in regs])
            # Len = Unit(1) + Func(1) + ByteCount(1) + Data(N)
            length = 3 + byte_count
            total_len = 6 + length
            hex_recv = f"({total_len}){tid:04X}0000{length:04X}0103{byte_count:02X}{data_hex}"
            self.append_recv_log(hex_recv)

            if regs:
                self.reg_table.setItem(0, 1, QTableWidgetItem(str(regs[0])))
        finally:
            self._monitor_busy = False

    def _handle_serial_monitor_result(self, regs):
        try:
            # 串口监测收到响应，标记为真实已连接
            if not self.communicator.is_connected:
                self.communicator.is_connected = True
                self.communicator.connection_changed.emit(True)
                self.append_recv_log("下位机响应，连接成功")

            byte_count = len(regs) * 2
            data_hex = "".join([f"{v:04X}" for v in regs])
            raw_resp_str = f"0103{byte_count:02X}{data_hex}"
            crc = self._calc_crc16(bytes.fromhex(raw_resp_str))
            crc_lo = crc & 0xFF
            crc_hi = (crc >> 8) & 0xFF
            hex_recv = f"{raw_resp_str}{crc_lo:02X}{crc_hi:02X}"
            self.append_recv_log(hex_recv.upper())

            if regs:
                self.reg_table.setItem(0, 1, QTableWidgetItem(str(regs[0])))
        finally:
            self._monitor_busy = False

    def _handle_monitor_error(self, msg):
        self._monitor_busy = False
        self.append_error_log(msg)


    def on_stop_monitor(self):
        self.btn_start_mon.setEnabled(True)
        self.btn_stop_mon.setEnabled(False)
        self.config_tab.setEnabled(True) # 恢复配置启用
        # 停止定时器
        if hasattr(self, 'monitor_timer') and self.monitor_timer.isActive():
            self.monitor_timer.stop()
            self.append_send_log("监测已停止")


    def on_write_value(self):
        # 1. 不再强制检查连接状态 (应用户要求，只记录发送日志，不弹窗)
        # if not self.communicator.is_connected:
        #     QMessageBox.warning(self, "未连接", "设备未连接，无法执行写入操作。")
        #     return
            
        # 2. 获取参数
        try:
            addr = int(self.edit_start_addr.text().strip())
            
            val_item = self.reg_table.item(0, 2)
            if not val_item or not val_item.text().strip():
                # 这个参数检查还是保留警告比较好，否则用户不知道为什么没反应
                QMessageBox.warning(self, "参数错误", "请输入待写入的值")
                return
            val = int(val_item.text().strip())
        except ValueError:
            QMessageBox.warning(self, "参数错误", "地址或写入值必须为数字")
            return
            
        # 3. 构造 "发送日志"
        # 即使未连接，也要构造假的报文显示出来
        is_tcp = True # 默认为 TCP 格式，或者根据当前 Tab 判断
        if self.config_tab.currentIndex() == 0: # 串口 Tab
            is_tcp = False
            
        if is_tcp:
            # 获取一个临时的 transaction id
            tid = self.monitor_tcp_seq if hasattr(self, 'monitor_tcp_seq') else 0
            # Increment for next usage
            self.monitor_tcp_seq = (tid + 1) % 65535 if hasattr(self, 'monitor_tcp_seq') else 1
            
            hex_send = f"{tid:04X}000000060106{addr:04X}{val:04X}"
            self.append_send_log(hex_send)
        else:
            # RTU
            raw_req = f"0106{addr:04X}{val:04X}"
            crc = self._calc_crc16(bytes.fromhex(raw_req))
            crc_lo = crc & 0xFF
            crc_hi = (crc >> 8) & 0xFF
            hex_send = f"{raw_req}{crc_lo:02X}{crc_hi:02X}"
            self.append_send_log(hex_send.upper())
            
        # 4. 执行写入 (如果连接了的话)
        if self.communicator.is_connected and self.communicator.client:
            try:
                # 兼容性尝试
                try:
                    rr = self.communicator.client.write_register(addr, val, slave=1)
                except TypeError:
                    rr = self.communicator.client.write_register(addr, val, unit=1)
                    
                if not rr.isError():
                    # 5. 写入成功，记录接收日志
                    if is_tcp:
                        hex_recv = f"{tid:04X}000000060106{addr:04X}{val:04X}"
                        self.append_recv_log(hex_recv)
                    else:
                        self.append_recv_log(hex_send.upper()) # 回显
                        
                    self.append_recv_log(f"写入成功: 地址{addr} -> {val}")
                else:
                    self.append_error_log(f"写入失败: {rr}")
                    
            except Exception as e:
                self.append_error_log(f"写入异常: {str(e)}")
        else:
             # 未连接时，只在错误日志记录一条，不弹窗
             # 或者按照用户要求：什么也不做，让用户自己看接收日志（由于接收日志没有内容，用户就知道没通）
             # 这里加上一条非弹窗的提示是个好习惯
             self.append_error_log("未连接设备，无接收响应")


    def on_custom_send(self):
        cmd = self.edit_custom_send.text().strip()
        if cmd:
            self.append_send_log(cmd)
            # 这里可以调用 self.communicator.send_immediate_gcode(cmd) 或其他自定义逻辑
        else:
            self.append_error_log("自定义指令为空")
    def __init__(self, communicator, parent=None):
        super().__init__(parent)
        self.setWindowTitle("通讯和G代码调试")
        self.resize(1000, 600)
        self.communicator = communicator

        self._monitor_busy = False
        self._pending_monitor_mode = None
        self._pending_tcp_tid = None

        self._monitor_thread = QThread(self)
        self._monitor_worker = _MonitorWorker()
        self._monitor_worker.moveToThread(self._monitor_thread)
        self.monitor_request.connect(self._monitor_worker.do_read)
        self._monitor_worker.result.connect(self._handle_monitor_result)
        self._monitor_worker.error.connect(self._handle_monitor_error)
        self._monitor_thread.start()

        try:
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self._stop_monitor_thread)
        except Exception:
            pass
        
        # 预定义指令集 (参考截图)
        self.commands = [
            ("17", "!", "停止点动"),
            ("7",  "$J=G91 X10 F9000", "X点动"),
            ("8",  "$J=G91 Y10 F1000", "Y点动"),
            ("9",  "$J=G91 Z5 F1000", "Z点动"),
            ("2",  "$X", "G代码: 解锁"),
            ("21", "$Z", ""),
            ("18", "?", "查询状态"),
            ("3",  "G10L20P0X0.000", "G代码: x清0"),
            ("4",  "G10L20P0Y0.000", "G代码: y清0"),
            ("5",  "G10L20P0Z0.000", "G代码: z清0"),
            ("6",  "G90G10L20P0X0.000Y0.000Z0.000", "G代码: 清0"),
            ("20", "G92 X0 Y0 Z0", ""),
            ("13", "+CREG:11,1", "列出sd卡文件"),
            ("10", "+CREG:12,1,test21.gcode", ""),
            ("14", "+CREG:12,1,tuzi.gcode", ""),
            ("11", "+CREG:12,1,tuzi4.gcode", "系统指令: XXX文件设置为当前文件"),
            ("15", "+CREG:13,0", "暂停执行当前文件"),
            ("12", "+CREG:13,1", "系统指令: 执行或继续当前G文件"),
            ("16", "+CREG:14,0", "打印当前文件的内容"),
            ("19", "+CREG:15,1,tuzi1.gcode", "删除XXX文件"),
        ]

        self.init_ui()
        self.setup_connections()

        # 寄存器刷新定时器
        self.reg_timer = QTimer(self)
        self.reg_timer.timeout.connect(self.refresh_register)

    def closeEvent(self, event):
        # 停止所有定时器
        if hasattr(self, 'monitor_timer') and self.monitor_timer.isActive():
            self.monitor_timer.stop()
        if hasattr(self, 'reg_timer') and self.reg_timer.isActive():
            self.reg_timer.stop()

        self._stop_monitor_thread()
            
        # 安全断开外部信号连接，防止对象销毁后回调导致Crash
        try:
            self.communicator.log_message.disconnect(self.append_recv_log)
        except Exception: pass
        
        try:
            self.communicator.error_occurred.disconnect(self.append_error_log)
        except Exception: pass
        
        try:
            self.communicator.sending_finished.disconnect(self.on_sending_finished)
        except Exception: pass
        
        event.accept()

    def _stop_monitor_thread(self):
        try:
            if hasattr(self, '_monitor_thread') and self._monitor_thread.isRunning():
                self._monitor_thread.quit()
                self._monitor_thread.wait(3000)
        except Exception:
            pass

        # self.reg_timer.start(1000) # 暂时不自动启动


    def init_ui(self):
        # 主水平分割器：左-中-右
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 左侧竖直布局（通讯和代码+监测设置）
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        config_panel = self.create_config_panel()
        left_layout.addWidget(config_panel, stretch=0)
        left_widget.setMinimumWidth(220)
        left_widget.setMaximumWidth(260)

        # 中间 G代码文件处理
        file_widget = self.create_file_tab()
        file_widget.setMinimumWidth(350)
        file_widget.setMaximumWidth(500)

        # 右侧 快捷控制与指令
        shortcut_widget = self.create_shortcut_tab()
        shortcut_widget.setMinimumWidth(350)
        shortcut_widget.setMaximumWidth(700)

        # 主分割器
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(file_widget)
        main_splitter.addWidget(shortcut_widget)
        main_splitter.setSizes([240, 420, 600])  # 初始宽度分配

        layout.addWidget(main_splitter)
        self.setLayout(layout)
        self.resize(1280, 720)



    def format_combobox(self, combo):
        """统一设置下拉框样式"""
        combo.setMaxVisibleItems(10)
        combo.setEditable(True)
        combo.lineEdit().setReadOnly(True) 
        combo.lineEdit().setAlignment(Qt.AlignLeft)

    def create_config_panel(self):
        """创建左侧连接配置面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 5, 0)
        
        # 上半部分：连接设置 Tab
        self.config_tab = QTabWidget()
        
        # 串口页面
        serial_tab = QWidget()
        serial_layout = QVBoxLayout(serial_tab)
        
        # 端口
        h0 = QHBoxLayout()
        h0.addWidget(QLabel("端口"))
        self.combo_port = QComboBox()
        self.combo_port.addItems([f"COM{i}" for i in range(1, 13)]) # 模拟COM口
        self.combo_port.setCurrentText("COM11")
        self.format_combobox(self.combo_port)
        h0.addWidget(self.combo_port)
        serial_layout.addLayout(h0)
        
        # 波特率
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("波特率"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.combo_baud.setCurrentText("9600")
        self.format_combobox(self.combo_baud)
        h1.addWidget(self.combo_baud)
        serial_layout.addLayout(h1)
        
        # 校验位
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("校验位"))
        self.combo_parity = QComboBox()
        self.combo_parity.addItems(["None", "Even", "Odd", "Mark", "Space"])
        self.format_combobox(self.combo_parity)
        h2.addWidget(self.combo_parity)
        serial_layout.addLayout(h2)

        # 数据位
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("数据位"))
        self.combo_bytesize = QComboBox()
        self.combo_bytesize.addItems(["5", "6", "7", "8"])
        self.combo_bytesize.setCurrentText("8")
        self.format_combobox(self.combo_bytesize)
        h3.addWidget(self.combo_bytesize)
        serial_layout.addLayout(h3)
        
         # 停止位
        h4 = QHBoxLayout()
        h4.addWidget(QLabel("停止位"))
        self.combo_stopbits = QComboBox()
        self.combo_stopbits.addItems(["1", "1.5", "2"])
        self.format_combobox(self.combo_stopbits)
        h4.addWidget(self.combo_stopbits)
        serial_layout.addLayout(h4)
        
        # 按钮
        self.btn_open_serial = QPushButton("打开串口")
        self.btn_open_serial.setCheckable(True)
        # self.btn_open_serial.clicked.connect(...) # 预留
        serial_layout.addWidget(self.btn_open_serial)
        
        serial_layout.addStretch()
        
        # TCP页面 (简单占位)
        tcp_tab = QWidget()
        tcp_layout = QFormLayout(tcp_tab)
        self.edit_ip = QLineEdit("127.0.0.1")
        self.edit_port = QLineEdit("502")
        tcp_layout.addRow("IP地址", self.edit_ip)
        tcp_layout.addRow("端口", self.edit_port)
        
        self.config_tab.addTab(serial_tab, "串口")
        self.config_tab.addTab(tcp_tab, "TCP/IP")
        
        layout.addWidget(self.config_tab)
        
        # 下半部分：监测设置 (仿截图)
        group_monitor = QGroupBox("监测设置")
        mon_layout = QVBoxLayout(group_monitor)
        
        h_mon1 = QHBoxLayout()
        h_mon1.addWidget(QLabel("通讯方式"))
        self.edit_method_display = QLineEdit("串口")
        self.edit_method_display.setReadOnly(True)
        self.edit_method_display.setStyleSheet("background-color: #f0f0f0; color: #333;") # 灰色背景表示只读
        h_mon1.addWidget(self.edit_method_display)
        mon_layout.addLayout(h_mon1)
        
        # 联动 Tab 切换
        self.config_tab.currentChanged.connect(self.on_config_tab_changed)

        h_mon2 = QHBoxLayout()
        h_mon2.addWidget(QLabel("监测间隔时间"))
        self.edit_interval = QLineEdit("300")
        self.edit_interval.setMaximumWidth(50)
        h_mon2.addWidget(self.edit_interval)
        h_mon2.addWidget(QLabel("毫秒"))
        mon_layout.addLayout(h_mon2)

        
        h_mon3 = QHBoxLayout()
        h_mon3.addWidget(QLabel("监测起始地址"))
        self.edit_start_addr = QLineEdit("1")
        h_mon3.addWidget(self.edit_start_addr)
        mon_layout.addLayout(h_mon3)
        
        h_mon4 = QHBoxLayout()
        h_mon4.addWidget(QLabel("监测地址长度"))
        self.edit_len = QLineEdit("1")
        h_mon4.addWidget(self.edit_len)
        mon_layout.addLayout(h_mon4)
        
        h_btn = QHBoxLayout()
        self.btn_start_mon = QPushButton("开始监测")
        self.btn_stop_mon = QPushButton("停止监测")
        self.btn_write = QPushButton("执行写入")
        self.btn_stop_mon.setEnabled(False) # 默认禁用
        
        h_btn.addWidget(self.btn_start_mon)
        h_btn.addWidget(self.btn_stop_mon)
        h_btn.addWidget(self.btn_write)
        
        mon_layout.addLayout(h_btn)
        
        # 下方输入框 (自定义发送)
        self.edit_custom_send = QLineEdit("+CREG:35,G10L20P0X0.000")
        self.btn_custom_send = QPushButton("发送自定义")
        
        h_custom = QHBoxLayout()
        h_custom.addWidget(self.edit_custom_send)
        h_custom.addWidget(self.btn_custom_send)
        mon_layout.addLayout(h_custom)
        
        mon_layout.addStretch()
        layout.addWidget(group_monitor)

        return panel



    def create_shortcut_tab(self):
        """创建快捷指令面板"""
        widget = QGroupBox("快捷控制与指令") # 使用 GroupBox 增加视觉区分
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(5, 15, 5, 5) 
         
        # 1. 顶部区域： 连接状态 | 自定义指令框 | 发送按钮
        top_layout = QHBoxLayout()
        
        # 连接状态
        top_layout.addWidget(QLabel("状态:"))
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        top_layout.addWidget(self.status_label)
        
        top_layout.addStretch()
        
        # 自定义指令输入
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("G代码...")
        self.cmd_input.setMaximumWidth(120)  # 减小宽度
        self.cmd_input.returnPressed.connect(self.on_send_custom) # 回车发送
        top_layout.addWidget(self.cmd_input)
        
        # 发送指令 按钮
        btn_send = QPushButton("发送指令")
        btn_send.setMaximumWidth(80) # 减小按钮宽度
        btn_send.clicked.connect(self.on_send_custom) 
        top_layout.addWidget(btn_send)
        
        main_layout.addLayout(top_layout)

        # 2. 表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["序号", "指令", "内容", "备注"])
        
        # 调整列宽以更紧凑
        self.table.setColumnWidth(0, 40) # 序号
        self.table.setColumnWidth(1, 40) # 指令
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch) # 内容列自适应
        self.table.setColumnWidth(3, 100) # 备注
        
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24) # 减小行高
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        self.populate_table()
        
        main_layout.addWidget(self.table)
        
        return widget


    def on_config_tab_changed(self, index):
        """当连接设置 tab 切换时，更新下方显示的通讯方式"""
        if index == 0:
            self.edit_method_display.setText("串口")
        else:
            self.edit_method_display.setText("TCP/IP")

    def create_file_tab(self):
        """创建G代码文件发送面板"""
        widget = QGroupBox("G代码文件处理")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 15, 5, 5)
        
        # 1. 顶部控制栏
        top_layout = QHBoxLayout()
        btn_read = QPushButton("读文件")
        btn_read.clicked.connect(self.on_read_file_clicked)
        
        lbl_file = QLabel("文件名")
        self.edit_file_name = QLineEdit()
        self.edit_file_name.setPlaceholderText("选择文件...")
        self.edit_file_name.setText("test.gcode") # Default filename
        
        btn_send = QPushButton("发送G文件")
        btn_send.clicked.connect(self.on_send_file_clicked)
        
        top_layout.addWidget(btn_read)
        top_layout.addSpacing(10) # 减小间距
        top_layout.addWidget(lbl_file)
        # 限制文件名输入框宽度
        self.edit_file_name.setMaximumWidth(250)
        top_layout.addWidget(self.edit_file_name)
        top_layout.addWidget(btn_send)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # 2. 中间文件内容显示
        middle_splitter = QSplitter(Qt.Horizontal)
        
        # 原文件内容
        self.source_edit = QTextEdit()
        self.source_edit.setPlaceholderText("文件原始内容...")
        self.source_edit.textChanged.connect(self.on_source_text_changed)
        
        # 发送队列/处理后的内容
        self.processed_edit = QTextEdit()
        self.processed_edit.setPlaceholderText("待发送的指令队列...")
        self.processed_edit.setReadOnly(True) # Make read-only as requested (purely removing comments)
        
        middle_splitter.addWidget(self.source_edit)
        middle_splitter.addWidget(self.processed_edit)
        layout.addWidget(middle_splitter, 1)
        
        # 3. 底部日志区域
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # 左下：寄存器监控表（更紧凑，列名与截图2一致，第三列可编辑）
        reg_group = QGroupBox("日志")
        reg_layout = QVBoxLayout(reg_group)
        self.reg_table = QTableWidget(1, 3)
        self.reg_table.setHorizontalHeaderLabels(["地址", "读取值", "待写入值"])
        self.reg_table.verticalHeader().setVisible(False)
        self.reg_table.setEditTriggers(QTableWidget.AllEditTriggers)
        self.reg_table.setItem(0, 0, QTableWidgetItem("1"))
        self.reg_table.setItem(0, 1, QTableWidgetItem("0"))
        self.reg_table.setItem(0, 2, QTableWidgetItem(""))
        self.reg_table.setColumnWidth(0, 50)
        self.reg_table.setColumnWidth(1, 80)
        self.reg_table.setColumnWidth(2, 80)
        reg_layout.addWidget(self.reg_table)
        bottom_splitter.addWidget(reg_group)
        
        # 右下：发送/接收日志 (上下分)
        log_right_splitter = QSplitter(Qt.Vertical)
        
        # 发送日志 (Hex风格)
        send_frame = QGroupBox("发送日志")
        send_layout = QVBoxLayout(send_frame)
        self.send_log_2 = QTextEdit()
        self.send_log_2.setReadOnly(True)
        send_layout.addWidget(self.send_log_2)
        
        # 接收日志 (Hex风格)
        recv_frame = QGroupBox("接收日志")
        recv_layout = QVBoxLayout(recv_frame)
        self.recv_log_2 = QTextEdit()
        self.recv_log_2.setReadOnly(True)
        recv_layout.addWidget(self.recv_log_2)
        
        log_right_splitter.addWidget(send_frame)
        log_right_splitter.addWidget(recv_frame)
        bottom_splitter.addWidget(log_right_splitter)
        
        bottom_splitter.setStretchFactor(1, 2)
        layout.addWidget(bottom_splitter, 1) # Assign less stretch to bottom compared to middle? 
        # Actually usually logs are smaller.
        layout.setStretch(1, 2) # Middle content weight 2
        layout.setStretch(2, 1) # Bottom logs weight 1
        
        return widget

    def populate_table(self):
        # (序号, 指令代码, 指令内容, 备注)
        # 根据截图手动映射指令代码 (大多是 35, 36)
        table_data = [
            ("17", "35", "!", "停止点动"),
            ("7",  "35", "$J=G91 X10 F9000", "X点动"),
            ("8",  "35", "$J=G91 Y10 F1000", "y点动"),
            ("9",  "35", "$J=G91 Z5 F1000", "Z点动"),
            ("2",  "35", "$X", "G代码: 解锁"),
            ("21", "35", "$Z", ""),
            ("18", "35", "?", "查询状态"),
            ("3",  "35", "G10L20P0X0.000", "G代码: x清0"),
            ("4",  "35", "G10L20P0Y0.000", "G代码: y清0"),
            ("5",  "35", "G10L20P0Z0.000", "G代码: z清0"),
            ("6",  "35", "G90G10L20P0X0.000Y0.000Z0.000", "G代码: 清0"),
            ("20", "35", "G92 X0 Y0 Z0", ""),
            ("13", "36", "+CREG:11,1", "列出sd卡文件"),
            ("10", "36", "+CREG:12,1,test21.gcode", ""),
            ("14", "36", "+CREG:12,1,tuzi.gcode", ""),
            ("11", "36", "+CREG:12,1,tuzi4.gcode", "系统指令: XXX文件设置为当前文件"),
            ("15", "36", "+CREG:13,0", "暂停执行当前文件"),
            ("12", "36", "+CREG:13,1", "系统指令: 执行或继续当前G文件"),
            ("16", "36", "+CREG:14,0", "打印当前文件的内容"),
            ("19", "36", "+CREG:15,1,tuzi1.gcode", "删除XXX文件"),
        ]

        self.table.setRowCount(0)
        for seq, code, cmd, note in table_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(seq))
            self.table.setItem(row, 1, QTableWidgetItem(code))
            self.table.setItem(row, 2, QTableWidgetItem(cmd))
            self.table.setItem(row, 3, QTableWidgetItem(note))

    def on_toggle_serial(self, checked):
        if checked:
            # 获取串口参数
            port = self.combo_port.currentText()
            baud = int(self.combo_baud.currentText())
            
            parity_map = {"None": "N", "Even": "E", "Odd": "O", "Mark": "M", "Space": "S"}
            parity_str = self.combo_parity.currentText()
            parity = parity_map.get(parity_str, "N")
            
            bytesize = int(self.combo_bytesize.currentText())
            
            stopbits_str = self.combo_stopbits.currentText()
            stopbits = float(stopbits_str) if '.' in stopbits_str else int(stopbits_str)

            # 仅打开串口，不做探测
            if self.communicator.connect_rtu(port, baud, bytesize, parity, stopbits, verify=False):
                self.btn_open_serial.setText("关闭串口")
                self.set_serial_config_enabled(False)
            else:
                self.btn_open_serial.setChecked(False) # 恢复未按下状态
        else:
            self.communicator.disconnect_device()
            self.btn_open_serial.setText("打开串口")
            self.set_serial_config_enabled(True)

    def set_serial_config_enabled(self, enabled):
        self.combo_port.setEnabled(enabled)
        self.combo_baud.setEnabled(enabled)
        self.combo_parity.setEnabled(enabled)
        self.combo_bytesize.setEnabled(enabled)
        self.combo_stopbits.setEnabled(enabled)

    def setup_connections(self):
        # 串口开关按钮
        self.btn_open_serial.clicked.connect(self.on_toggle_serial)
        
        # 监测按钮
        self.btn_start_mon.clicked.connect(self.on_start_monitor)
        self.btn_stop_mon.clicked.connect(self.on_stop_monitor)
        self.btn_write.clicked.connect(self.on_write_value)
        self.btn_custom_send.clicked.connect(self.on_custom_send)
        
        # 监听连接状态变化
        self.communicator.connection_changed.connect(self.update_connection_status)

        # 表格双击发送 - 修改为默认编辑行为，不再发送
        # self.table.cellDoubleClicked.connect(self.on_table_double_click)
        
        # 监听通讯器信号
        self.communicator.log_message.connect(self.append_recv_log)
        try:
            # Try to connect the new signal if it exists (in case user didn't restart app completely)
            self.communicator.log_send_message.connect(self.append_send_log)
        except AttributeError:
            pass
        self.communicator.error_occurred.connect(self.append_error_log)
        self.communicator.sending_finished.connect(self.on_sending_finished)
        
        # 初始状态更新
        self.update_connection_status(self.communicator.is_connected)

    def on_sending_finished(self):
        self.append_recv_log("GCode 发送完成")

    def update_connection_status(self, is_connected):
        status = "已连接" if is_connected else "未连接"
        style = "color: green; font-weight: bold;" if is_connected else "color: red; font-weight: bold;"
        
        self.status_label.setText(status)
        self.status_label.setStyleSheet(style)

    def append_recv_log(self, msg):
        # 过滤连接状态类系统消息，接收日志只显示真实返回内容
        if isinstance(msg, str):
            sys_prefixes = (
                "正在连接串口",
                "正在连接 Modbus-TCP",
                "串口 RTU 连接成功",
                "串口已打开",
                "Modbus-TCP 连接成功",
                "设备已断开",
            )
            if msg.startswith(sys_prefixes):
                return

        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{time_str}] {msg}"
        # Update both tabs
        if hasattr(self, 'recv_log_1'):
             self.recv_log_1.append(formatted)
        if hasattr(self, 'recv_log_2'):
             self.recv_log_2.append(formatted)

    def append_error_log(self, msg):
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"<span style='color:red'>[{time_str}] Error: {msg}</span>"
        if hasattr(self, 'recv_log_1'):
             self.recv_log_1.append(formatted)
        if hasattr(self, 'recv_log_2'):
             self.recv_log_2.append(formatted)

    def append_send_log(self, msg):
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{time_str}] -> {msg}"
        if hasattr(self, 'send_log_1'):
             self.send_log_1.append(formatted)
        if hasattr(self, 'send_log_2'):
             self.send_log_2.append(formatted)

    def on_table_double_click(self, row, col):
        code_item = self.table.item(row, 1) # 功能码
        cmd_item = self.table.item(row, 2) # 内容
        if cmd_item and code_item:
            cmd = cmd_item.text()
            try:
                fc = int(code_item.text())
            except:
                fc = 35 # 默认
            self.send_command(cmd, fc)

    def on_send_custom(self, checked=False):
        # 兼容 clicked(bool) 信号
        cmd = self.cmd_input.text().strip()
        if cmd:
            self.send_command(cmd, 35) # 自定义指令默认 35
            # self.cmd_input.clear()
        else:
            # 尝试发送选中行
            current_row = self.table.currentRow()
            if current_row >= 0:
                code_item = self.table.item(current_row, 1)
                cmd_item = self.table.item(current_row, 2)
                if cmd_item:
                    try:
                        fc = int(code_item.text()) if code_item else 35
                    except:
                        fc = 35
                    self.send_command(cmd_item.text(), fc)
            else:
                self.append_error_log("请输入指令或选择一行")

    def send_command(self, cmd, fc=35):
        # 构造并记录 Log
        # 注意：这里我们模拟构造成 Modbus 报文样式以便用户观察
        # FC35: TransID(2) Prot(2) Len(2) Unit(1) FC(1) Data...
        # 简单起见，我们只记录 ASCII Hex
        
        data_bytes = cmd.encode('utf-8')
        data_hex = "".join([f"{b:02X}" for b in data_bytes])
        # 假装这是 Modbus TCP 头
        # 本应更严谨，但这里主要是为了 Log 看起来像
        fake_header = f"0000000000{len(data_bytes)+2:02X}01{fc:02X}" # Length=DataLen+Unit(1)+FC(1)? No PDU length usually.
        # Unit(1) + FC(1) + Data
        # Modbus TCP Header: Trans(2) Proto(2) Len(2). Len = Unit(1) + PDU_Len
        
        log_hex = f"{fake_header}{data_hex}".upper()
        self.append_send_log(log_hex)

        if not self.communicator.is_connected:
            # 仅仅记录 Log，不报错 (根据之前的要求)
            self.append_error_log("未连接: 仅生成发送日志")
            return

        # 真正发送
        if fc == 35 or fc == 36:
            self.communicator.send_custom_command(fc, cmd)
        else:
            # Fallback to old behavior for other FCs?
            # 实际上当前只有 35/36 被用作 commands
            self.communicator.send_immediate_gcode(cmd)
        
    def on_source_text_changed(self):
        """Handle source text changes: clean G-code and update preview"""
        content = self.source_edit.toPlainText()
        lines = content.splitlines()
        cleaned_lines = []
        for line in lines:
            # Remove (...) comments
            line = re.sub(r'\(.*?\)', '', line)
            # Remove ; comments
            line = line.split(';')[0]
            
            line = line.strip()
            if line: # Remove empty lines
                cleaned_lines.append(line)
                
        self.processed_edit.setText("\n".join(cleaned_lines))

    def on_read_file_clicked(self):
        fname, _ = QFileDialog.getOpenFileName(self, '打开G代码文件', '.', "GCode Files (*.nc *.gcode *.txt *.tap);;All Files (*)")
        if fname:
            try:
                self.edit_file_name.setText(os.path.basename(fname))
                with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    self.source_edit.setText(content)
                    # Triggering parsing automatically via textChanged signal
            except Exception as e:
                self.append_error_log(f"读取文件失败: {e}")

    def on_send_file_clicked(self):
        # 获取要发送的文件名和内容
        # 修复变量名错误: file_path_edit -> edit_file_name
        file_name = self.edit_file_name.text()
        content = self.processed_edit.toPlainText()
        
        if not file_name:
            self.append_error_log("请先选择文件或输入文件名")
            return

        if not content:
            self.append_error_log("文件内容为空")
            return

        # 创建一个临时文件来保存要发送的内容
        try:
            # 必须使用 delete=False，这样关闭后文件依然存在，可以被 upload_file_to_sd 读取
            # mode='w+' 用于写入文本内容
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix='.gcode') as tmp:
                tmp.write(content)
                temp_path = tmp.name
            
            # 使用 upload_file_to_sd 发送
            # 注意: file_name 只是显示用的文件名，temp_path 是实际内容的文件路径
            local_filename = os.path.basename(file_name)
            self.append_send_log(f"开始发送文件: {local_filename} (FC33)")
            
            # 调用 laser_communicator 的上传方法
            if self.communicator.is_connected:
                self.communicator.upload_file_to_sd(temp_path, local_filename)
            else:
                 self.append_error_log("设备未连接")

            # 清理临时文件 (upload_file_to_sd 是同步还是异步? 
            # 如果是异步，这里删除会导致问题。根据 implementation 它是同步分包发送的)
            # 为了保险，稍后删除或者假定它是同步的。
            # 查看 laser_communicator.py 的 upload_file_to_sd 实现... 它是同步循环发送的。
            try:
                os.unlink(temp_path)
            except:
                pass
                
        except Exception as e:
            self.append_error_log(f"发送文件失败: {e}")
        
    def refresh_register(self):
        # 预留：刷新寄存器值
        pass
