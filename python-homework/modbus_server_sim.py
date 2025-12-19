import logging
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext

# 配置日志以便看到连接信息
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

def run_server():
    print("="*50)
    print("正在启动本地 Modbus TCP 仿真服务器...")
    print("地址: 127.0.0.1")
    print("端口: 502")
    print("-" * 50)
    print("请在您的软件配置窗口中输入:")
    print("IP地址: 127.0.0.1")
    print("然后点击“测试”按钮。")
    print("="*50)
    
    # 初始化数据存储 (模拟一些寄存器数据)
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, [0]*100),
        ir=ModbusSequentialDataBlock(0, [0]*100))
    
    context = ModbusServerContext(slaves=store, single=True)
    
    # 启动 TCP 服务器
    try:
        # 绑定到本地回环地址
        StartTcpServer(context=context, address=("127.0.0.1", 502))
    except PermissionError:
        print("\n[错误] 权限不足：无法绑定端口 502。")
        print("请尝试以【管理员身份】运行终端，或者检查端口是否被占用。")
    except Exception as e:
        print(f"\n[错误] 服务器启动失败: {e}")

if __name__ == "__main__":
    run_server()