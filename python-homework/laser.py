# =========================================================
#  激光雕刻图像处理 + GCode 发送  一体化主程序
# =========================================================
import sys
import os
# -------------------- 图像处理 --------------------
import cv2
import numpy as np
# -------------------- 串口枚举 --------------------
import serial.tools.list_ports
# -------------------- Modbus 双协议 ------------------
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException
# -------------------- GUI ---------------------
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QTimer
# ---------------------------------------------------


class LaserImageGcodeSender(QMainWindow):
    """主窗口：集成图像处理 + GCode 发送（TCP/RTU）"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("激光雕刻图像处理 & GCode发送下位机 系统")
        self.resize(1400, 850)

        # ===== 图像处理相关 =====
        self.original_image = None   # 原图
        self.gray_image = None       # 灰度图
        self.gcode_lines = []        # 生成的 GCode
        self.gray_data_list = []     # 每行灰度 16bit 数据
        self.image_path = None       # 当前图片路径

        # ===== 发送控制相关 =====
        self.current_line = 0        # 当前发送行号
        self.is_sending = False      # 发送进行中标志

        # ===== Modbus 客户端 =====
        self.modbus_client = None    # TCP 时用
        self.serial_client = None    # RTU 时用
        self.conn_mode = "TCP"       # 当前连接模式

        self.init_ui()               # 搭建界面

    # ------------------------------------------------------------------
    #  界面总入口
    # ------------------------------------------------------------------
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)

        # 左侧：图像处理 + 显示
        left = self.create_left_panel()
        main.addWidget(left, 2)

        # 右侧：GCode 显示 + 连接/发送控制
        right = self.create_right_panel()
        main.addWidget(right, 1)

        # 底部状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 —— 请先加载并处理图片，再连接设备")

    # ------------------------------------------------------------------
    #  左侧：图像处理页
    # ------------------------------------------------------------------
    def create_left_panel(self):
        panel = QGroupBox("图像处理")
        v = QVBoxLayout(panel)

        # 图片展示标签
        self.image_label = QLabel("请点击“加载图片”导入图像\n支持 PNG、JPG、JPEG、BMP")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumHeight(300)
        self.image_label.setStyleSheet("""
            QLabel{
                border: 2px dashed #aaa;
                background: #f8f8f8;
                font-size: 15px;
                color: #555;
            }
        """)
        v.addWidget(self.image_label, 1)

        # 图像信息
        self.image_info = QLabel("图像信息：未加载")
        v.addWidget(self.image_info)

        # 参数区
        param_box = QGroupBox("处理参数")
        gp = QVBoxLayout(param_box)

        # DPI
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("DPI（每英寸像素）:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(100, 1200)
        self.dpi_spin.setValue(254)          # 254≈0.1mm/像素
        h1.addWidget(self.dpi_spin)
        h1.addStretch()
        gp.addLayout(h1)

        # 激光功率
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("激光功率 (0-100%):"))
        self.power_spin = QSpinBox()
        self.power_spin.setRange(0, 100)
        self.power_spin.setValue(50)
        h2.addWidget(self.power_spin)
        h2.addStretch()
        gp.addLayout(h2)

        # 雕刻速度
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("雕刻速度 (mm/min):"))
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(100, 5000)
        self.speed_spin.setValue(1000)
        h3.addWidget(self.speed_spin)
        h3.addStretch()
        gp.addLayout(h3)

        # 空走速度
        h4 = QHBoxLayout()
        h4.addWidget(QLabel("空走速度 (mm/min):"))
        self.rapid_spin = QSpinBox()
        self.rapid_spin.setRange(100, 10000)
        self.rapid_spin.setValue(3000)
        h4.addWidget(self.rapid_spin)
        h4.addStretch()
        gp.addLayout(h4)

        v.addWidget(param_box)

        # 功能按钮
        btn_box = QGroupBox("操作")
        bb = QHBoxLayout(btn_box)
        self.load_img_btn = QPushButton("加载图片")
        self.proc_img_btn = QPushButton("处理图片")
        self.save_gcode_btn = QPushButton("保存GCode")
        self.proc_img_btn.setEnabled(False)
        self.save_gcode_btn.setEnabled(False)

        self.load_img_btn.clicked.connect(self.load_image)
        self.proc_img_btn.clicked.connect(self.process_image)
        self.save_gcode_btn.clicked.connect(self.save_gcode)

        bb.addWidget(self.load_img_btn)
        bb.addWidget(self.proc_img_btn)
        bb.addWidget(self.save_gcode_btn)
        v.addWidget(btn_box)
        # v.addStretch()
        return panel

    # ------------------------------------------------------------------
    #  右侧：GCode 显示 + 连接/发送控制（与代码2保持一致）
    # ------------------------------------------------------------------
    def create_right_panel(self):
        panel = QWidget()
        vl = QVBoxLayout(panel)

        # ① GCode 显示
        gcode_group = QGroupBox("GCode 内容（可手动编辑）")
        gl = QVBoxLayout(gcode_group)
        self.gcode_edit = QTextEdit()
        self.gcode_edit.setFont(QFont("Courier New", 10))
        self.gcode_edit.setStyleSheet("background:#1e1e1e;color:#d4d4d4;")
        gl.addWidget(self.gcode_edit)
        self.gcode_info = QLabel("GCode 信息：未加载")
        gl.addWidget(self.gcode_info)
        vl.addWidget(gcode_group, 3)

        # ② 连接方式选择
        mode_group = QGroupBox("连接方式")
        ml = QHBoxLayout(mode_group)
        self.tcp_radio = QRadioButton("TCP")
        self.rtu_radio = QRadioButton("串口 RTU")
        self.tcp_radio.setChecked(True)
        self.tcp_radio.toggled.connect(self.on_mode_change)
        ml.addWidget(self.tcp_radio)
        ml.addWidget(self.rtu_radio)
        vl.addWidget(mode_group)

        # ③ 参数堆叠
        self.stacked = QStackedWidget()
        # TCP 页
        tcp_page = QWidget()
        tvl = QVBoxLayout(tcp_page)
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("IP 地址:"))
        self.ip_edit = QLineEdit("192.168.1.100")
        h1.addWidget(self.ip_edit)
        tvl.addLayout(h1)
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("端口:"))
        self.port_edit = QLineEdit("502")
        h2.addWidget(self.port_edit)
        tvl.addLayout(h2)
        self.stacked.addWidget(tcp_page)

        # 串口页
        rtu_page = QWidget()
        rvl = QVBoxLayout(rtu_page)
        # 串口
        h = QHBoxLayout()
        h.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        h.addWidget(self.port_combo)
        btn_ref = QPushButton("刷新")
        btn_ref.clicked.connect(self.refresh_ports)
        h.addWidget(btn_ref)
        rvl.addLayout(h)
        # 波特率
        h = QHBoxLayout()
        h.addWidget(QLabel("波特率:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("115200")
        h.addWidget(self.baud_combo)
        rvl.addLayout(h)
        self.stacked.addWidget(rtu_page)
        vl.addWidget(self.stacked)

        # ④ 启停
        ctrl_group = QGroupBox("发送控制")
        cl = QVBoxLayout(ctrl_group)
        self.conn_btn = QPushButton("连接设备")
        self.start_btn = QPushButton("开始发送")
        self.stop_btn = QPushButton("停止发送")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.conn_btn.clicked.connect(self.connect_device)
        self.start_btn.clicked.connect(self.start_sending)
        self.stop_btn.clicked.connect(self.stop_sending)
        cl.addWidget(self.conn_btn)
        cl.addWidget(self.start_btn)
        cl.addWidget(self.stop_btn)
        vl.addWidget(ctrl_group)

        # ⑤ 日志
        log_group = QGroupBox("日志")
        ll = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setMaximumHeight(150)
        self.log_edit.setReadOnly(True)
        ll.addWidget(self.log_edit)
        vl.addWidget(log_group)

        vl.addStretch()
        return panel

    # -------------------- 工具函数 --------------------
    def refresh_ports(self):
        """枚举串口"""
        self.port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.addItems(ports if ports else ["无串口"])

    def on_mode_change(self):
        """切换 TCP/RTU 参数页"""
        self.stacked.setCurrentIndex(0 if self.tcp_radio.isChecked() else 1)
        self.conn_mode = "TCP" if self.tcp_radio.isChecked() else "RTU"

    def log(self, msg):
        """在日志区与状态栏同时输出"""
        self.log_edit.append(msg)
        self.status_bar.showMessage(msg)

    # ==================================================================
    #  图像处理：加载 → 处理 → 保存GCode
    # ==================================================================
    def load_image(self):
        """加载图片"""
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp)")
            if not path:
                self.log("用户取消加载图片")
                return
            if not os.path.exists(path):
                raise FileNotFoundError("文件不存在")
            self.image_path = path
            # OpenCV 读取
            self.original_image = cv2.imdecode(
                np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if self.original_image is None:
                raise ValueError("OpenCV 无法解码图片")
            # 统一转 3 通道
            if len(self.original_image.shape) == 2:
                self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_GRAY2BGR)
            elif self.original_image.shape[2] == 4:
                self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGRA2BGR)

            self.show_image(self.original_image)
            h, w = self.original_image.shape[:2]
            size_kb = os.path.getsize(path) // 1024
            self.image_info.setText(f"图像信息：{w}×{h} 像素 | {size_kb} KB")
            self.log("✓ 图片加载成功")
            self.proc_img_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))
            self.log(f"✗ 加载图片失败：{e}")

    def show_image(self, img):
        """将 OpenCV 图像显示到 QLabel"""
        if len(img.shape) == 3:
            h, w, ch = img.shape
            bytes_per_line = ch * w
            qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        else:
            h, w = img.shape
            qimg = QImage(img.data, w, h, w, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(qimg)
        self.image_label.setPixmap(
            pixmap.scaled(self.image_label.width() - 10,
                          self.image_label.height() - 10,
                          Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def process_image(self):
        """处理图片并生成 GCode"""
        if self.original_image is None:
            QMessageBox.warning(self, "提示", "请先加载图片！")
            return
        try:
            self.log("→ 开始处理图片...")
            # 转灰度
            gray = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
            # 按 DPI 缩放
            dpi = self.dpi_spin.value()
            ratio = dpi / 254.0
            oh, ow = gray.shape
            nh = int(oh * ratio)
            nw = int(ow * ratio)
            self.gray_image = cv2.resize(gray, (nw, nh), interpolation=cv2.INTER_AREA)
            self.show_image(self.gray_image)
            self.log(f"→ 尺寸缩放：{ow}×{oh} → {nw}×{nh}")
            # 生成 GCode
            self.generate_gcode()
            self.log(f"✓ 处理完成，共生成 {len(self.gcode_lines)} 行 GCode")
            self.save_gcode_btn.setEnabled(True)
            # 把 GCode 显示到右侧
            self.gcode_edit.setPlainText("\n".join(self.gcode_lines))
            self.update_gcode_info()
            # 若已连接设备，可解锁发送
            if self.client and self.client.is_socket_open():
                self.start_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "处理失败", str(e))
            self.log(f"✗ 处理失败：{e}")

    def generate_gcode(self):
        """生成 GCode + 16bit 灰度数据，写入同一文件"""
        h, w = self.gray_image.shape
        power = self.power_spin.value()
        speed = self.speed_spin.value()
        rapid = self.rapid_spin.value()

        self.gcode_lines.clear()
        self.gray_data_list.clear()

        # ---------- 1. 标准 GCode 头 ----------
        self.gcode_lines.append("; 激光雕刻 GCode + 16bit GrayData")
        self.gcode_lines.append(f"; 图片尺寸: {w}×{h} 像素")
        self.gcode_lines.append(f"; 激光功率: {power}%")
        self.gcode_lines.append(f"; 雕刻速度: {speed} mm/min")
        self.gcode_lines.append("G21 ; 毫米单位")
        self.gcode_lines.append(f"M3 S{power} ; 设激光功率")
        self.gcode_lines.append("")

        # ---------- 2. 逐行扫描（只生成空走+雕刻指令，不内嵌灰度） ----------
        for y in range(h):
            y_pos = round(y * 0.1, 2)
            x_end = round(w * 0.1, 2)
            self.gcode_lines.append(f"G0 X0 Y{y_pos} F{rapid}")
            self.gcode_lines.append(f"G1 X{x_end} Y{y_pos} F{speed} ; row={y}")
            # 同时记录本行 16bit 灰度，后面统一写
            row_16 = [int(self.gray_image[y, x]) * 257 for x in range(w)]
            self.gray_data_list.append(row_16)

        # ---------- 3. 文件尾 ----------
        self.gcode_lines += ["", "M5 ; 关闭激光", "G0 X0 Y0 ; 回原点", ";<<<<GRAY16>>>>"]

        # ---------- 4. 追加灰度数据 ----------
        for idx, row in enumerate(self.gray_data_list):
            hex_line = " ".join(f"{g:04X}" for g in row)
            self.gcode_lines.append(hex_line)
        self.gcode_lines.append(";<<<<END>>>>")

    def save_gcode(self):
        """保存生成的 GCode"""
        if not self.gcode_lines:
            QMessageBox.warning(self, "提示", "没有可保存的 GCode！")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 GCode", "engraving.gcode", "GCode (*.gcode);;Text (*.txt)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(self.gcode_lines))
                self.log(f"✓ GCode 已保存到：{path}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))

    def update_gcode_info(self):
        """更新右侧 GCode 信息"""
        total = len(self.gcode_lines)
        engrave = len([l for l in self.gcode_lines if l.startswith("G1 X")])
        self.gcode_info.setText(f"GCode 信息：总行数 {total} | 雕刻指令 {engrave}")

    # ==================================================================
    #  下方：Modbus 连接 & 发送控制（与代码2 逻辑基本一致）
    # ==================================================================
    @property
    def client(self):
        """统一返回当前有效客户端"""
        return self.modbus_client if self.conn_mode == "TCP" else self.serial_client

    def connect_device(self):
        """连接/断开 设备"""
        # 若已连接 → 断开
        if self.client and self.client.is_socket_open():
            self.client.close()
            if self.conn_mode == "TCP":
                self.modbus_client = None
            else:
                self.serial_client = None
            self.conn_btn.setText("连接设备")
            self.start_btn.setEnabled(False)
            self.log("已断开设备连接")
            return
        # 未连接 → 按模式连接
        if self.conn_mode == "TCP":
            self._connect_tcp()
        else:
            self._connect_rtu()

    def _connect_tcp(self):
        """建立 Modbus-TCP 连接"""
        ip = self.ip_edit.text().strip()
        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            QMessageBox.critical(self, "输入错误", "端口号必须是数字！")
            return
        try:
            self.log(f"→ 正在连接 Modbus-TCP {ip}:{port}")
            self.modbus_client = ModbusTcpClient(ip, port=port)
            if self.modbus_client.connect():
                self.conn_btn.setText("断开连接")
                self.log(f"✓ Modbus-TCP 连接成功")
                if self.gcode_lines:
                    self.start_btn.setEnabled(True)
            else:
                raise ConnectionError("连接失败，请检查 IP 与端口")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            self.log(f"✗ TCP 连接失败：{e}")

    def _connect_rtu(self):
        """建立 Modbus-RTU 串口连接"""
        try:
            port = self.port_combo.currentText()
            baud = int(self.baud_combo.currentText())
            bytesize = int(self.data_spin.value())
            stopbits = float(self.stop_combo.currentText())
            parity_map = {"None": "N", "Even": "E", "Odd": "O"}
            parity = parity_map[self.parity_combo.currentText()]
            self.log(f"→ 正在连接串口 {port} {baud} {bytesize}{parity}{stopbits}")
            self.serial_client = ModbusSerialClient(
                method="rtu",
                port=port,
                baudrate=baud,
                bytesize=bytesize,
                stopbits=stopbits,
                parity=parity,
                timeout=1
            )
            if self.serial_client.connect():
                self.conn_btn.setText("断开连接")
                self.log("✓ 串口 RTU 连接成功")
                if self.gcode_lines:
                    self.start_btn.setEnabled(True)
            else:
                raise ConnectionError("串口打开失败，可能被占用或参数错误")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            self.log(f"✗ 串口连接失败：{e}")

    def start_sending(self):
        """开始发送 GCode"""
        if not self.client or not self.client.is_socket_open():
            QMessageBox.warning(self, "提示", "请先连接设备！")
            return
        if not self.gcode_lines:
            QMessageBox.warning(self, "提示", "没有可发送的 GCode！")
            return
        engrave_lines = [l for l in self.gcode_lines if l.startswith("G1 X")]
        reply = QMessageBox.question(
            self, "确认", f"确定开始发送 GCode 吗？\n共 {len(engrave_lines)} 行雕刻指令")
        if reply != QMessageBox.Yes:
            return
        self.current_line = 0
        self.is_sending = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.conn_btn.setEnabled(False)
        self.load_img_btn.setEnabled(False)
        self.proc_img_btn.setEnabled(False)
        self.save_gcode_btn.setEnabled(False)

        self.log(f"开始发送 GCode（雕刻指令 {len(engrave_lines)} 行）...")
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self.send_next_line)
        self.send_timer.start(10)          # 10 ms/行，可改

    def send_next_line(self):
        """定时发送下一行（仅发送 G1 雕刻行）"""
        if not self.is_sending:
            return
        # 跳过非 G1 行
        while (self.current_line < len(self.gcode_lines) and
               not self.gcode_lines[self.current_line].startswith("G1 X")):
            self.current_line += 1
        if self.current_line >= len(self.gcode_lines):
            self.stop_sending()
            self.log("✓ GCode 发送完成！")
            QMessageBox.information(self, "完成", "所有 GCode 指令已发送完成！")
            return
        try:
            line = self.gcode_lines[self.current_line]
            # 写 GCode 到寄存器 0-49
            self.write_gcode_regs(line)
            # 写执行标志
            self.client.write_register(50, 1)
            # 进度打印
            engrave_num = (self.current_line + 2) // 2
            total_engrave = len([l for l in self.gcode_lines if l.startswith("G1 X")])
            if engrave_num % 5 == 0:
                self.log(f"已发送第 {engrave_num}/{total_engrave} 行")
            self.current_line += 1
        except ModbusException as e:
            self.log(f"✗ Modbus 错误：{e}")
            self.stop_sending()
        except Exception as e:
            self.log(f"✗ 发送错误：{e}")
            self.stop_sending()

    def write_gcode_regs(self, gcode_line):
        """将 GCode 字符串写入寄存器 0-49（每寄存器 2 字节）"""
        ascii_vals = [ord(c) for c in gcode_line[:100]]
        ascii_vals += [0] * (100 - len(ascii_vals))
        for i in range(0, 100, 2):
            val = (ascii_vals[i] << 8) | ascii_vals[i + 1]
            self.client.write_register(i // 2, val)


    def stop_sending(self):
        """停止发送"""
        self.is_sending = False
        if hasattr(self, "send_timer"):
            self.send_timer.stop()
        # 按钮恢复
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.conn_btn.setEnabled(True)
        self.load_img_btn.setEnabled(True)
        self.proc_img_btn.setEnabled(True)
        self.save_gcode_btn.setEnabled(True)
        # 写停止标志
        if self.client and self.client.is_socket_open():
            try:
                self.client.write_register(50, 0)
                self.log("已发送停止信号")
            except:
                pass

    def closeEvent(self, event):
        """窗口关闭时清理连接"""
        if self.modbus_client and self.modbus_client.is_socket_open():
            self.modbus_client.close()
            self.log("Modbus-TCP 连接已关闭")
        if self.serial_client and self.serial_client.is_socket_open():
            self.serial_client.close()
            self.log("Modbus-RTU 串口已关闭")
        event.accept()


# ======================== 入口 ========================
def main():
    app = QApplication(sys.argv)

    # 全局样式
    app.setStyleSheet("""
        QMainWindow{background-color:#f0f0f0;}
        QGroupBox{font-weight:bold;border:2px solid #4CAF50;border-radius:5px;margin-top:10px;padding-top:10px;}
        QPushButton{padding:8px;background-color:#4CAF50;color:white;border:none;border-radius:4px;font-weight:bold;}
        QPushButton:hover{background-color:#45a049;}
        QPushButton:disabled{background-color:#ccc;}
        QTextEdit{background:#1e1e1e;color:#d4d4d4;border:1px solid #333;}
        QLabel{font-size:10pt;}
        QLineEdit{padding:4px;border:1px solid #ccc;border-radius:3px;}
    """)

    win = LaserImageGcodeSender()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()