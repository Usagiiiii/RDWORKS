import pymodbus
print(f"Pymodbus Version: {pymodbus.__version__}")
try:
    from pymodbus.factory import ClientDecoder
    print("ClientDecoder found in pymodbus.factory")
except ImportError:
    print("ClientDecoder NOT found in pymodbus.factory")

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    pass
