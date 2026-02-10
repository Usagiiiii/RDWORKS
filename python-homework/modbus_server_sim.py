import logging
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusServerContext
try:
    from pymodbus.datastore import ModbusSlaveContext
except ImportError:
    # Pymodbus 3.x+ compability
    from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext

# 导入自定义指令
from my_io.communication.custom_pdus import (
    CustomCommandRequest, SDCardCommandRequest, 
    WriteFileRequest, RunGCodeRequest, SystemCommandRequest
)

# 尝试全局注册自定义 Function Code (兼容 Pymodbus 版本)
try:
    from pymodbus.factory import ServerDecoder
    ServerDecoder.register(WriteFileRequest)
    ServerDecoder.register(RunGCodeRequest)
    ServerDecoder.register(SystemCommandRequest)
except (ImportError, AttributeError):
    pass

# Custom DataBlock to intercept and log G-Code writes
class CallbackDataBlock(ModbusSequentialDataBlock):
    def getValues(self, address, count=1):
        try:
            values = super().getValues(address, count)
        except Exception:
            values = super().getValues(address)

        # Log monitor reads
        try:
            print(f"[下位机 RECV] 监测读寄存器: addr={address}, count={count}", flush=True)
        except Exception:
            pass

        return values

    def setValues(self, address, values):
        super().setValues(address, values)
        # Address 50 is the Execute Flag
        # Note: address passed here is 1-based or 0-based depending on Pymodbus version/context.
        # ModbusSequentialDataBlock usually takes 1-based address from request, converts to 0-based index.
        # But setValues(address, values) -> address is the offset in the block?
        # Let's assume address 51 (reg 50+1) or we check the logic.
        # Actually, ModbusSequentialDataBlock.setValues(address, values) uses value_address = address - self.address.
        # If block starts at 0. Address sent by client is 0-based for pymodbus client? No, Modbus is 0-based on wire, but often 1-based in docs.
        # Pymodbus client: write_register(50, 1) -> sends address 50.
        # Server receives address 50.
        # If block starts at 0, index is 50.
        
        target_index = 50
        if (address <= target_index) and (address + len(values) > target_index):
             # The write covers register 50
             # Find the value for reg 50
             val_index = target_index - address
             if values[val_index] == 1:
                 # Logic to read regs 0-49 and print
                 # We can access internal storage: self.values
                 # Regs 0-49 correspond to indices 0-49
                 try:
                     raw_data = self.values[0:50] 
                     # Decode
                     decoded_str = ""
                     for r in raw_data:
                         hi = (r >> 8) & 0xFF
                         lo = r & 0xFF
                         if hi: decoded_str += chr(hi)
                         if lo: decoded_str += chr(lo)
                     decoded_str = decoded_str.rstrip('\x00')
                     print(f"[下位机 RECV] 收到 G代码指令: {decoded_str}", flush=True)
                 except Exception as e:
                     print(f"[Error] Decoding GCode: {e}", flush=True)

# 配置日志以便看到连接信息
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()
log.setLevel(logging.INFO)
# 显示 Pymodbus 的连接与请求日志，便于确认是否收到数据
logging.getLogger("pymodbus").setLevel(logging.INFO)

def run_server():
    print("="*50)
    print("正在启动本地 Modbus TCP 仿真服务器...")
    print("地址: 127.0.0.1")
    print("端口: 1502")
    print("-" * 50)
    print("请在您的软件配置窗口中输入:")
    print("IP地址: 127.0.0.1")
    print("然后点击“测试”按钮。")
    print("="*50)
    
    # 初始化数据存储 (模拟一些寄存器数据)
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=CallbackDataBlock(0, [0]*100),
        ir=ModbusSequentialDataBlock(0, [0]*100))
    
    try:
        # Pymodbus 3.x
        context = ModbusServerContext(devices=store, single=True)
    except TypeError:
        # Pymodbus 2.x
        context = ModbusServerContext(slaves=store, single=True)
    
    # 启动 TCP 服务器
    try:
        # 支持注册多个自定义PDU
        custom_pdus = [WriteFileRequest, RunGCodeRequest, SystemCommandRequest]
        
        # 绑定到本地回环地址
        StartTcpServer(context=context, address=("127.0.0.1", 1502),
                       ignore_missing_slaves=True, # 宽容模式
                       custom_functions=custom_pdus)
    except TypeError:
        # 旧版本 pymodbus 参数可能是 custom_pdu
        StartTcpServer(context=context, address=("127.0.0.1", 1502),
                       custom_pdu=custom_pdus)
    except PermissionError:
        print("\n[错误] 权限不足：无法绑定端口 502。")
        print("请尝试以【管理员身份】运行终端，或者检查端口是否被占用。")
    except Exception as e:
        print(f"\n[错误] 服务器启动失败: {e}")

if __name__ == "__main__":
    run_server()