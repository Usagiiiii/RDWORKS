import logging
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException
from my_io.communication.custom_pdus import (
    RunGCodeRequest, RunGCodeResponse,
    SystemCommandRequest, SystemCommandResponse, 
    WriteFileRequest, WriteFileResponse,
    CustomCommandRequest, SDCardCommandRequest
)

# Register Custom PDUs for Client
try:
    # Attempt Pymodbus 3.x registration (v3.11+)
    from pymodbus.pdu import DecodePDU
    DecodePDU.add_pdu(WriteFileRequest, WriteFileResponse)
    DecodePDU.add_pdu(RunGCodeRequest, RunGCodeResponse)
    DecodePDU.add_pdu(SystemCommandRequest, SystemCommandResponse)
except (ImportError, AttributeError):
    # Fallback for older Pymodbus versions or if DecodePDU structure is different
    try:
        from pymodbus.factory import ClientDecoder
        ClientDecoder.register(RunGCodeResponse)
        ClientDecoder.register(SystemCommandResponse)
        ClientDecoder.register(WriteFileResponse)
    except (ImportError, AttributeError):
        pass

logger = logging.getLogger(__name__)

class LaserCommunicator(QObject):
    """
    激光设备通信模块
    封装了 Modbus TCP/RTU 连接及 GCode 发送逻辑
    """
    log_message = pyqtSignal(str) # Usually for Recv/System logs
    log_send_message = pyqtSignal(str) # New signal for Send logs
    connection_changed = pyqtSignal(bool)
    sending_progress = pyqtSignal(int, int) # current, total
    sending_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    file_upload_progress = pyqtSignal(int, int) # transferred, total

    def __init__(self):
        super().__init__()
        self.client = None
        self.is_connected = False
        self.is_port_open = False
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
            self.client = ModbusTcpClient(ip, port=port, timeout=1)
            if self.client.connect():
                if self._probe_connection(self.client):
                    self.is_connected = True
                    self.connection_changed.emit(True)
                    self.log_message.emit("Modbus-TCP 连接成功")
                    return True

                self.client.close()
                self.client = None
                raise ConnectionError("设备无响应")

            raise ConnectionError("连接失败")
        except Exception as e:
            self.error_occurred.emit(f"TCP 连接失败: {str(e)}")
            return False

    def connect_rtu(self, port, baudrate=115200, bytesize=8, parity='N', stopbits=1, verify=False):
        """连接 Modbus RTU (串口)"""
        self.disconnect_device()
        try:
            self.log_message.emit(f"正在连接串口 {port}...")
            # 尝试适配不同版本的 pymodbus
            try:
                # pymodbus v3.x (无 method 参数)
                self.client = ModbusSerialClient(
                    port=port,
                    baudrate=baudrate,
                    bytesize=bytesize,
                    parity=parity,
                    stopbits=stopbits,
                    timeout=1
                )
            except TypeError:
                # pymodbus v2.x (需要 method 参数)
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
                self.is_port_open = True
                self.log_message.emit("串口已打开")

                if verify:
                    if self._probe_connection(self.client):
                        self.is_connected = True
                        self.connection_changed.emit(True)
                        self.log_message.emit("下位机响应，连接成功")
                        return True

                    raise ConnectionError("设备无响应")

                return True

            raise ConnectionError("串口打开失败")
        except Exception as e:
            self.is_port_open = False
            self.error_occurred.emit(f"串口连接失败: {str(e)}")
            return False

    def _probe_connection(self, client) -> bool:
        """通过读取寄存器确认设备真实响应"""
        try:
            # 兼容不同版本的 pymodbus 调用方式
            try:
                rr = client.read_holding_registers(1, count=1, device_id=1)
            except TypeError:
                try:
                    rr = client.read_holding_registers(1, count=1, slave=1)
                except TypeError:
                    rr = client.read_holding_registers(1, count=1, unit=1)

            return not rr.isError()
        except Exception:
            return False

    def disconnect_device(self):
        """断开连接"""
        if self.is_sending:
            self.stop_sending()
            
        if self.client:
            self.client.close()
            self.client = None

        self.is_port_open = False
            
        if self.is_connected:
            self.is_connected = False
            self.connection_changed.emit(False)
            self.log_message.emit("设备已断开")

    def upload_file_to_sd(self, local_path, remote_filename="job.nc"):
        """上传文件到设备 SD 卡 (FC 0x21)"""
        if not self.is_connected:
            self.error_occurred.emit("未连接设备")
            return False

        try:
            self.log_message.emit(f"开始上传文件: {local_path} -> {remote_filename}")
            
            with open(local_path, 'rb') as f:
                content = f.read()
            
            total_bytes = len(content)
            
            # Helper to log Hex
            tid_counter = 1 # Fake TID for visual consistency if real one unavailable
            
            def calculate_crc16(data: bytes) -> int:
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

            def log_packet(req, step_desc):
                nonlocal tid_counter
                pdu_bytes = req.encode()
                # PDU = Unit(1) + FC(1) + ReqData
                modbus_pdu = b'\x01\x21' + pdu_bytes

                if isinstance(self.client, ModbusTcpClient):
                    # ModbusTCP Header: TID(2) Proto(2) Len(2)
                    header = f"{tid_counter:04X}0000{len(modbus_pdu):04X}"
                    body = "".join([f"{b:02X}" for b in modbus_pdu])
                    self.log_send_message.emit(f"[TCP] {header}{body}")
                else:
                    # RTU: Slave(1) + FC(1) + ReqData + CRC(2)
                    # modbus_pdu is already Slave + FC + ReqData (wait, encode returns ReqData only)
                    # Actually req.encode returns the Data part.
                    # PDU logic in caller: modbus_pdu = b'\x01\x21' + pdu_bytes
                    # So modbus_pdu IS the RTU "ADU" without CRC for RTU.
                    # Let's verify ModbusPDU structure.
                    crc = calculate_crc16(modbus_pdu)
                    # CRC is Low Byte first
                    crc_bytes = crc.to_bytes(2, byteorder='little')
                    full_frame = modbus_pdu + crc_bytes
                    body = "".join([f"{b:02X}" for b in full_frame])
                    self.log_send_message.emit(f"[RTU] {body}")
                
            def log_response(resp):
                nonlocal tid_counter
                
                if isinstance(self.client, ModbusTcpClient):
                    # Header + Unit(1) + FC(1) + Data(0)
                    # Len = 2
                    header = f"{tid_counter:04X}00000002"
                    body = "0121" 
                    # Log Recv (Format: (Len)Hex)
                    total_len = 6 + 2 # Header(6) + Body(2) = 8
                    self.log_message.emit(f"({total_len}){header}{body}")
                    tid_counter = (tid_counter + 1) % 65535
                else:
                    # RTU Response: Slave(1) + FC(1) + Data(0) + CRC(2)
                    frame = b'\x01\x21'
                    crc = calculate_crc16(frame)
                    crc_bytes = crc.to_bytes(2, byteorder='little')
                    full_resp = frame + crc_bytes
                    body = "".join([f"{b:02X}" for b in full_resp])
                    self.log_message.emit(f"[RTU-Resp] {body}")

            # 1. Start (Addr=0, Data=Filename)
            req = WriteFileRequest(address=0, data=remote_filename)
            req.slave_id = 1
            log_packet(req, "Start")
            
            resp = self._execute_request(req)
            if resp.isError():
                 raise Exception(f"Start upload failed: {resp}")
            log_response(resp)

            # 2. Upload chunks (Addr=1, Data=128 bytes)
            # Safe payload size: 256(Frame) - Header ~ 200 bytes. Conservative: 128
            chunk_size = 128
            transferred = 0
            
            for i in range(0, total_bytes, chunk_size):
                chunk = content[i : i+chunk_size]
                
                req = WriteFileRequest(address=1, data=chunk)
                req.slave_id = 1
                
                log_packet(req, f"Chunk {i}")
                
                resp = self._execute_request(req)
                if resp.isError():
                     raise Exception(f"Write chunk failed at offset {i}")
                
                log_response(resp)

                transferred += len(chunk)
                self.file_upload_progress.emit(transferred, total_bytes)
                QApplication.processEvents() # Prevent UI freeze

            # 3. End (Addr=0xFFFF)
            req = WriteFileRequest(address=0xFFFF, data=b'')
            req.slave_id = 1
            
            log_packet(req, "End")
            
            resp = self._execute_request(req)
            if resp.isError():
                 raise Exception(f"End upload failed")
            log_response(resp)

            self.log_message.emit("文件上传成功")
            return True

        except Exception as e:
            self.error_occurred.emit(f"文件上传失败: {str(e)}")
            return False

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

    def send_immediate_gcode(self, gcode_str):
        """发送单条即时指令 (FC 0x23)"""
        if not self.is_connected:
            self.error_occurred.emit("未连接设备")
            return

        try:
            req = RunGCodeRequest(address=0, data=gcode_str)
            req.slave_id = 1
            resp = self._execute_request(req)
            
            if resp.isError():
                self.error_occurred.emit(f"指令发送失败: {resp}")
            else:
                self.log_message.emit(f"发送指令: {gcode_str}")
        except Exception as e:
            self.error_occurred.emit(f"指令发送异常: {str(e)}")

    def send_custom_command(self, fc, data_str):
        """发送自定义指令 (FC35/36/33等)"""
        if not self.is_connected:
            self.error_occurred.emit("未连接设备")
            return

        try:
            req = None
            if fc == 35 or fc == 0x23:
                req = RunGCodeRequest(address=0, data=data_str)
            elif fc == 36 or fc == 0x24:
                req = SystemCommandRequest(address=0, data=data_str)
            else:
                self.error_occurred.emit(f"不支持的功能码: {fc}")
                return

            req.slave_id = 1
            resp = self._execute_request(req)
            
            if resp.isError():
                 self.error_occurred.emit(f"指令(FC{fc})执行错误: {resp}")
            
        except Exception as e:
            self.error_occurred.emit(f"自定义指令发送异常: {e}")

    def _execute_request(self, req):
        """Helper to execute request safely"""
        try:
            resp = self.client.execute(request=req)
        except TypeError:
            # Pymodbus version difference
            resp = self.client.execute(False, req)
        return resp

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
            
            # 使用 FC35 (RunGCodeRequest) 直接发送指令
            req = RunGCodeRequest(address=0, data=line)
            req.slave_id = 1
            resp = self._execute_request(req)
            
            if resp.isError():
                 self.error_occurred.emit(f"Line {self.current_line+1} 发送失败: {resp}")
                 # Option: continue or stop? Stops for safety.
                 self.stop_sending()
            else:
                 self.sending_progress.emit(self.current_line + 1, len(self.gcode_lines))
                 self.current_line += 1
            
        except ModbusException as e:
            self.error_occurred.emit(f"Modbus 错误: {str(e)}")
            self.stop_sending()
        except Exception as e:
            self.error_occurred.emit(f"发送错误: {str(e)}")
            self.stop_sending()
