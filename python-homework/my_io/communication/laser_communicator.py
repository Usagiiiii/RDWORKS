import logging
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException

logger = logging.getLogger(__name__)

class LaserCommunicator(QObject):
    """
    激光设备通信模块
    封装了 Modbus TCP/RTU 连接及 GCode 发送逻辑
    """
    log_message = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)
    sending_progress = pyqtSignal(int, int) # current, total
    sending_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client = None
        self.is_connected = False
        self.is_sending = False
        self.gcode_lines = []
        self.current_line = 0
        
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self._send_next_line)

    def connect_tcp(self, ip, port):
        """连接 Modbus TCP"""
        self.disconnect_device()
        try:
            self.log_message.emit(f"正在连接 Modbus-TCP {ip}:{port}...")
            self.client = ModbusTcpClient(ip, port=port)
            if self.client.connect():
                self.is_connected = True
                self.connection_changed.emit(True)
                self.log_message.emit("Modbus-TCP 连接成功")
                return True
            else:
                raise ConnectionError("连接失败")
        except Exception as e:
            self.error_occurred.emit(f"TCP 连接失败: {str(e)}")
            return False

    def connect_rtu(self, port, baudrate=115200, bytesize=8, parity='N', stopbits=1):
        """连接 Modbus RTU (串口)"""
        self.disconnect_device()
        try:
            self.log_message.emit(f"正在连接串口 {port}...")
            self.client = ModbusSerialClient(
                method="rtu",
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=1
            )
            if self.client.connect():
                self.is_connected = True
                self.connection_changed.emit(True)
                self.log_message.emit("串口 RTU 连接成功")
                return True
            else:
                raise ConnectionError("串口打开失败")
        except Exception as e:
            self.error_occurred.emit(f"串口连接失败: {str(e)}")
            return False

    def disconnect_device(self):
        """断开连接"""
        if self.is_sending:
            self.stop_sending()
            
        if self.client:
            self.client.close()
            self.client = None
            
        if self.is_connected:
            self.is_connected = False
            self.connection_changed.emit(False)
            self.log_message.emit("设备已断开")

    def start_sending(self, gcode_lines):
        """开始发送 GCode"""
        if not self.is_connected:
            self.error_occurred.emit("未连接设备")
            return

        if not gcode_lines:
            self.error_occurred.emit("没有 GCode 数据")
            return

        self.gcode_lines = gcode_lines
        self.current_line = 0
        self.is_sending = True
        self.send_timer.start(10) # 10ms 发送间隔
        self.log_message.emit(f"开始发送 GCode，共 {len(gcode_lines)} 行")

    def stop_sending(self):
        """停止发送"""
        self.is_sending = False
        self.send_timer.stop()
        
        # 发送停止信号
        if self.is_connected and self.client:
            try:
                self.client.write_register(50, 0)
                self.log_message.emit("已发送停止信号")
            except Exception as e:
                logger.error(f"发送停止信号失败: {e}")
        
        self.sending_finished.emit()

    def _send_next_line(self):
        """发送下一行 GCode"""
        if not self.is_sending:
            return

        # 简单逻辑：只发送 G1 指令，或者全部发送？
        # 参考 laser.py，它似乎跳过了非 G1 行，但又在 generate_gcode 里生成了 G0 等。
        # laser.py 的 send_next_line 里有：
        # while (self.current_line < len(self.gcode_lines) and
        #        not self.gcode_lines[self.current_line].startswith("G1 X")):
        #     self.current_line += 1
        # 这意味着它只发送 G1 指令给下位机执行雕刻？这有点奇怪，G0 移动指令不发吗？
        # 仔细看 laser.py 的 generate_gcode:
        # self.gcode_lines.append(f"G0 X0 Y{y_pos} F{rapid}")
        # self.gcode_lines.append(f"G1 X{x_end} Y{y_pos} F{speed} ; row={y}")
        # 如果只发 G1，那 G0 怎么执行？
        # 也许下位机逻辑是收到 G1 就自动处理移动？或者 laser.py 的逻辑是特定的。
        # 为了保持一致性，我先照搬 laser.py 的逻辑：只发送 G1 行。
        
        while (self.current_line < len(self.gcode_lines) and 
               not self.gcode_lines[self.current_line].startswith("G1 X")):
            self.current_line += 1

        if self.current_line >= len(self.gcode_lines):
            self.stop_sending()
            self.log_message.emit("GCode 发送完成")
            return

        try:
            line = self.gcode_lines[self.current_line]
            self._write_gcode_regs(line)
            self.client.write_register(50, 1) # 执行标志
            
            self.sending_progress.emit(self.current_line + 1, len(self.gcode_lines))
            self.current_line += 1
            
        except ModbusException as e:
            self.error_occurred.emit(f"Modbus 错误: {str(e)}")
            self.stop_sending()
        except Exception as e:
            self.error_occurred.emit(f"发送错误: {str(e)}")
            self.stop_sending()

    def _write_gcode_regs(self, gcode_line):
        """将 GCode 字符串写入寄存器 0-49"""
        # 截断或填充到 100 字符
        ascii_vals = [ord(c) for c in gcode_line[:100]]
        ascii_vals += [0] * (100 - len(ascii_vals))
        
        for i in range(0, 100, 2):
            val = (ascii_vals[i] << 8) | ascii_vals[i + 1]
            self.client.write_register(i // 2, val)
