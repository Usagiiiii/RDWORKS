from pymodbus.pdu import ModbusPDU
import struct
import os

class BaseStringRequest(ModbusPDU):
    """
    Base class for custom string-based requests that follow the structure:
    [AddrHi, AddrLo, QtyHi, QtyLo, ByteCount, Data...]
    Compatible with modbus.c Process_ModbusStringCommand
    """
    _rtu_frame_size = None  # Variable length

    def __init__(self, address=0, data=b'', **kwargs):
        super().__init__(**kwargs)
        self.address = address
        self.data = data
        if isinstance(self.data, str):
            self.data = self.data.encode('utf-8', 'ignore')

    def encode(self):
        # 1. Prepare data
        raw_bytes = self.data
        length = len(raw_bytes)
        
        # 2. Pad to even length (Modbus registers are 16-bit)
        if length % 2 != 0:
            raw_bytes += b'\x00'
            length += 1
            
        # 3. Calculate Quantity (Registers) and ByteCount
        qty = length // 2
        byte_count = length
        
        # 4. pack: Address(2), Quantity(2), ByteCount(1), Data(N)
        header = struct.pack('>HHB', self.address, qty, byte_count)
        return header + raw_bytes

    def decode(self, data):
        # Decode request (for Simulator/Server side)
        try:
            self.address, qty, byte_count = struct.unpack('>HHB', data[:5])
            self.data = data[5:5+byte_count]
        except Exception:
            pass

    # Helper for simulator logic
    def get_text(self):
        try:
            return self.data.decode('utf-8', 'ignore').strip('\x00')
        except:
            return ""

class WriteFileRequest(BaseStringRequest):
    """
    Function Code 33 (0x21): 写入文件到SD卡
    Address 0: Start (Content=Filename)
    Address 0xFFFF: End
    Other: Append Content
    """
    function_code = 33

    async def update_datastore(self, context):
        # For Simulator
        cmd_str = self.get_text()
        if self.address == 0:
            filename = os.path.basename(cmd_str) if cmd_str else "upload.gcode"
            context._upload_filename = filename
            context._upload_data = bytearray()
            print(f"[下位机] <FC33> 收到写文件请求: {filename}", flush=True)
        elif self.address == 65535:
            filename = getattr(context, "_upload_filename", "upload.gcode")
            data = getattr(context, "_upload_data", bytearray())
            target_dir = r"C:\Users\臧雪鹏\Desktop\sim_files"
            os.makedirs(target_dir, exist_ok=True)
            out_path = os.path.join(target_dir, filename)
            try:
                # Strip trailing padding nulls used for Modbus register alignment
                payload = bytes(data).rstrip(b"\x00")
                with open(out_path, "wb") as f:
                    f.write(payload)
                print(f"[下位机] <FC33> 文件写入结束: {out_path}", flush=True)
            except Exception as e:
                print(f"[下位机] <FC33> 写文件失败: {e}", flush=True)
        else:
            if not hasattr(context, "_upload_data"):
                context._upload_data = bytearray()
            context._upload_data.extend(self.data)
            print(f"[下位机] <FC33> 收到数据块 (Length={len(self.data)})", flush=True)
        return WriteFileResponse()

class WriteFileResponse(ModbusPDU):
    function_code = 33
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    def encode(self):
        return b'' # Empty response or success code?
    def decode(self, data):
        pass

class RunGCodeRequest(BaseStringRequest):
    """
    Function Code 35 (0x23): 直接运行 G 代码
    """
    function_code = 35

    async def update_datastore(self, context):
        cmd_str = self.get_text()
        print(f"[下位机] <FC35> 实时指令: {cmd_str}", flush=True)
        return RunGCodeResponse(self.data)

class RunGCodeResponse(ModbusPDU):
    function_code = 35
    def __init__(self, data=b'', **kwargs):
        super().__init__(**kwargs)
        self.data = data
    def encode(self):
        return self.data
    def decode(self, data):
        self.data = data

class SystemCommandRequest(BaseStringRequest):
    """
    Function Code 36 (0x24): 系统指令
    """
    function_code = 36
    
    async def update_datastore(self, context):
        cmd_str = self.get_text()
        print(f"[下位机] <FC36> 系统指令: {cmd_str}", flush=True)
        return SystemCommandResponse(self.data)

class SystemCommandResponse(ModbusPDU):
    function_code = 36
    def __init__(self, data=b'', **kwargs):
        super().__init__(**kwargs)
        self.data = data
    def encode(self):
        return self.data
    def decode(self, data):
        self.data = data

# Aliases for backward compatibility
CustomCommandRequest = RunGCodeRequest
CustomCommandResponse = RunGCodeResponse
SDCardCommandRequest = SystemCommandRequest
SDCardCommandResponse = SystemCommandResponse
