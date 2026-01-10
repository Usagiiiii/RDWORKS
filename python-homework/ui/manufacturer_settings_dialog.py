from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QTabWidget,
                             QWidget, QFormLayout, QSpinBox, QDoubleSpinBox,
                             QCheckBox, QListWidget, QStackedWidget, QGroupBox,
                             QRadioButton, QComboBox, QGridLayout, QFrame, QSpacerItem, 
                             QSizePolicy)
from PyQt5.QtCore import Qt

# ========================================================
# Password Dialog
# ========================================================
class ManufacturerPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("厂家参数密码")
        # Remove the question mark icon
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setFixedSize(260, 100)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 10)
        layout.setSpacing(10)
        
        # Form layout for label and input
        form_layout = QHBoxLayout()
        form_layout.setSpacing(10)
        form_layout.addWidget(QLabel("厂家参数密码:"))
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        # Use simple stylesheet to force asterisks if platform default is bullets
        # 42 is the ascii code for '*'
        self.password_edit.setStyleSheet("QLineEdit { lineedit-password-character: 42; }")
        self.password_edit.setFixedWidth(120)
        form_layout.addWidget(self.password_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_ok = QPushButton("确定")
        self.btn_ok.setFixedSize(60, 24)
        self.btn_ok.clicked.connect(self.check_password)
        button_layout.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedSize(60, 24)
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        
        # Center the buttons 
        button_layout.setAlignment(Qt.AlignCenter)
        
        layout.addLayout(button_layout)

    def check_password(self):
        if self.password_edit.text() == "rd8888":
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "密码错误！")
            self.password_edit.clear()
            self.password_edit.setFocus()

# ========================================================
# Helper Classes for UI Layouts
# ========================================================

class HLine(QFrame):
    def __init__(self):
        super(HLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

class VLine(QFrame):
    def __init__(self):
        super(VLine, self).__init__()
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)

class MotorSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Initialize data structure for 4 axes
        self.current_axis = 'X'
        self.axis_data = {
            'X': self.get_default_data(),
            'Y': self.get_default_data(),
            'Z': self.get_default_data(),
            'U': self.get_default_data(),
        }
        self.init_ui()

    def get_default_data(self):
        """Return a dict of default values for one axis"""
        return {
            'dir_polarity': 0,      # index of "正" (1) or "负" (0)? "负" is index 0
            'limit_polarity': 0,    # index
            'control_mode': 0,      # index
            'step_dist': 0.35000,
            'breadth': 1000.000,
            'origin_offset': 0.000,
            'check_hard_limit': False,
            'check_pwm_rising': False,
            'check_enable_reset': True,
            'start_speed': 5.000,
            'max_accel': 8000.000,
            'max_speed': 1000.000,
            'estop_accel': 5000.000,
            'key_start_speed': 5.000,
            'key_accel': 3000.000,
            'check_key_reverse': False
        }

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Axis Radio Buttons
        axis_layout = QHBoxLayout()
        axis_layout.setSpacing(15)
        
        # Using QtWidgets.QButtonGroup logically
        from PyQt5.QtWidgets import QButtonGroup
        self.bg = QButtonGroup(self)
        
        self.radio_x = QRadioButton("X")
        self.radio_y = QRadioButton("Y")
        self.radio_z = QRadioButton("Z")
        self.radio_u = QRadioButton("U")
        
        self.bg.addButton(self.radio_x)
        self.bg.addButton(self.radio_y)
        self.bg.addButton(self.radio_z)
        self.bg.addButton(self.radio_u)
        
        # Connect signals
        # We need to save old data BEFORE switching, or just use the toggled(bool) logic
        # Easier: connect to buttonClicked or idClicked of the group
        self.bg.buttonClicked.connect(self.on_axis_button_clicked)
        
        axis_layout.addWidget(self.radio_x)
        axis_layout.addWidget(self.radio_y)
        axis_layout.addWidget(self.radio_z)
        axis_layout.addWidget(self.radio_u)
        axis_layout.addStretch()
        main_layout.addLayout(axis_layout)
        
        main_layout.addWidget(HLine())

        # --- Top Group: Configuration ---
        config_grid = QGridLayout()
        config_grid.setSpacing(8)

        # Row 0
        config_grid.addWidget(QLabel("方向极性:"), 0, 0, alignment=Qt.AlignRight)
        self.dir_polarity = QComboBox()
        self.dir_polarity.addItems(["负", "正"])
        config_grid.addWidget(self.dir_polarity, 0, 1)

        config_grid.addWidget(QLabel("步距(um):"), 0, 2, alignment=Qt.AlignRight)
        step_layout = QHBoxLayout()
        self.step_dist = QDoubleSpinBox()
        self.step_dist.setRange(0, 9999)
        self.step_dist.setDecimals(5)
        step_layout.addWidget(self.step_dist)
        step_layout.addWidget(QPushButton("...")) 
        config_grid.addLayout(step_layout, 0, 3)

        # Row 1
        config_grid.addWidget(QLabel("限位极性:"), 1, 0, alignment=Qt.AlignRight)
        self.limit_polarity = QComboBox()
        self.limit_polarity.addItems(["负", "正"])
        config_grid.addWidget(self.limit_polarity, 1, 1)

        # Row 2
        config_grid.addWidget(QLabel("控制方式:"), 2, 0, alignment=Qt.AlignRight)
        self.control_mode = QComboBox()
        self.control_mode.addItems(["脉冲+方向", "双脉冲"])
        config_grid.addWidget(self.control_mode, 2, 1)

        self.check_hard_limit = QCheckBox("硬限位保护")
        config_grid.addWidget(self.check_hard_limit, 2, 3)

        # Row 3
        config_grid.addWidget(QLabel("幅面:"), 3, 0, alignment=Qt.AlignRight)
        self.breadth = QDoubleSpinBox()
        self.breadth.setRange(0, 99999)
        self.breadth.setDecimals(3)
        self.breadth.setSuffix(" mm")
        config_grid.addWidget(self.breadth, 3, 1)

        self.check_pwm_rising = QCheckBox("PWM上升沿有效")
        config_grid.addWidget(self.check_pwm_rising, 3, 3)

        # Row 4
        config_grid.addWidget(QLabel("原点偏移:"), 4, 0, alignment=Qt.AlignRight)
        self.origin_offset = QDoubleSpinBox()
        self.origin_offset.setRange(-99999, 99999)
        self.origin_offset.setDecimals(3)
        self.origin_offset.setSuffix(" mm")
        config_grid.addWidget(self.origin_offset, 4, 1)

        self.check_enable_reset = QCheckBox("使能复位")
        config_grid.addWidget(self.check_enable_reset, 4, 3)

        main_layout.addLayout(config_grid)
        main_layout.addWidget(HLine())

        # --- Middle Group: Motion Parameters ---
        motion_grid = QGridLayout()
        motion_grid.setSpacing(8)

        # Row 0
        motion_grid.addWidget(QLabel("起跳速度:"), 0, 0, alignment=Qt.AlignRight)
        self.start_speed = QDoubleSpinBox()
        self.start_speed.setRange(0, 9999)
        self.start_speed.setDecimals(3)
        self.start_speed.setSuffix(" mm/s")
        motion_grid.addWidget(self.start_speed, 0, 1)

        motion_grid.addWidget(QLabel("最大加速度:"), 0, 2, alignment=Qt.AlignRight)
        self.max_accel = QDoubleSpinBox()
        self.max_accel.setRange(0, 99999)
        self.max_accel.setDecimals(3)
        self.max_accel.setSuffix(" mm/s2")
        motion_grid.addWidget(self.max_accel, 0, 3)

        # Row 1
        motion_grid.addWidget(QLabel("最大速度:"), 1, 0, alignment=Qt.AlignRight)
        self.max_speed = QDoubleSpinBox()
        self.max_speed.setRange(0, 9999)
        self.max_speed.setDecimals(3)
        self.max_speed.setSuffix(" mm/s")
        motion_grid.addWidget(self.max_speed, 1, 1)

        motion_grid.addWidget(QLabel("急停加速度:"), 1, 2, alignment=Qt.AlignRight)
        self.estop_accel = QDoubleSpinBox()
        self.estop_accel.setRange(0, 99999)
        self.estop_accel.setDecimals(3)
        self.estop_accel.setSuffix(" mm/s2")
        motion_grid.addWidget(self.estop_accel, 1, 3)

        main_layout.addLayout(motion_grid)

        # --- Bottom Group: Key/Button (GroupBox) ---
        key_group = QGroupBox("按键")
        key_layout = QGridLayout()
        key_layout.setSpacing(8)
        
        key_layout.addWidget(QLabel("起跳速度:"), 0, 0, alignment=Qt.AlignRight)
        self.key_start_speed = QDoubleSpinBox()
        self.key_start_speed.setRange(0, 9999)
        self.key_start_speed.setDecimals(3)
        self.key_start_speed.setSuffix(" mm/s")
        key_layout.addWidget(self.key_start_speed, 0, 1)
        
        # Checkbox aligned with right column
        self.check_key_reverse = QCheckBox("按键反向")
        key_layout.addWidget(self.check_key_reverse, 0, 2, 1, 2)

        key_layout.addWidget(QLabel("加速度:"), 1, 0, alignment=Qt.AlignRight)
        self.key_accel = QDoubleSpinBox()
        self.key_accel.setRange(0, 99999)
        self.key_accel.setDecimals(3)
        self.key_accel.setSuffix(" mm/s2")
        key_layout.addWidget(self.key_accel, 1, 1)

        key_group.setLayout(key_layout)
        main_layout.addWidget(key_group)
        main_layout.addStretch()

        # Initialize UI with default 'X' data
        self.radio_x.setChecked(True)
        self.load_data('X')

    def on_axis_button_clicked(self, button):
        # Triggered when button is clicked (and checked)
        new_axis = button.text()
        if new_axis == self.current_axis:
            return
            
        # 1. Save current data
        self.save_data(self.current_axis)
        
        # 2. Update current axis pointer
        self.current_axis = new_axis
        
        # 3. Load new data
        self.load_data(self.current_axis)

    def save_data(self, axis):
        data = {
            'dir_polarity': self.dir_polarity.currentIndex(),
            'limit_polarity': self.limit_polarity.currentIndex(),
            'control_mode': self.control_mode.currentIndex(),
            'step_dist': self.step_dist.value(),
            'breadth': self.breadth.value(),
            'origin_offset': self.origin_offset.value(),
            'check_hard_limit': self.check_hard_limit.isChecked(),
            'check_pwm_rising': self.check_pwm_rising.isChecked(),
            'check_enable_reset': self.check_enable_reset.isChecked(),
            'start_speed': self.start_speed.value(),
            'max_accel': self.max_accel.value(),
            'max_speed': self.max_speed.value(),
            'estop_accel': self.estop_accel.value(),
            'key_start_speed': self.key_start_speed.value(),
            'key_accel': self.key_accel.value(),
            'check_key_reverse': self.check_key_reverse.isChecked()
        }
        self.axis_data[axis] = data

    def load_data(self, axis):
        data = self.axis_data.get(axis, self.get_default_data())
        self.dir_polarity.setCurrentIndex(data['dir_polarity'])
        self.limit_polarity.setCurrentIndex(data['limit_polarity'])
        self.control_mode.setCurrentIndex(data['control_mode'])
        self.step_dist.setValue(data['step_dist'])
        self.breadth.setValue(data['breadth'])
        self.origin_offset.setValue(data['origin_offset'])
        self.check_hard_limit.setChecked(data['check_hard_limit'])
        self.check_pwm_rising.setChecked(data['check_pwm_rising'])
        self.check_enable_reset.setChecked(data['check_enable_reset'])
        self.start_speed.setValue(data['start_speed'])
        self.max_accel.setValue(data['max_accel'])
        self.max_speed.setValue(data['max_speed'])
        self.estop_accel.setValue(data['estop_accel'])
        self.key_start_speed.setValue(data['key_start_speed'])
        self.key_accel.setValue(data['key_accel'])
        self.check_key_reverse.setChecked(data['check_key_reverse'])



class LaserSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Top Box (inside a standard Widget or GroupBox to group them visually) ---
        # The screenshot shows a boxed area (GroupBox style)
        top_group = QGroupBox()
        top_layout = QGridLayout()
        
        # Row 0
        top_layout.addWidget(QLabel("激光管配置:"), 0, 0, alignment=Qt.AlignRight)
        radio_box = QHBoxLayout()
        self.radio_single = QRadioButton("单管")
        self.radio_single.setChecked(True)
        self.radio_multi = QRadioButton("多管")
        radio_box.addWidget(self.radio_single)
        radio_box.addWidget(self.radio_multi)
        radio_box.addStretch()
        top_layout.addLayout(radio_box, 0, 1, 1, 1) # Span 1 col, but use HBox

        # Row 1
        top_layout.addWidget(QLabel("激光器类型:"), 1, 0, alignment=Qt.AlignRight)
        self.laser_type = QComboBox()
        self.laser_type.addItems(["玻璃管", "射频管"])
        top_layout.addWidget(self.laser_type, 1, 1)

        top_layout.addWidget(QLabel("激光衰减:"), 1, 2, alignment=Qt.AlignRight)
        decay_layout = QHBoxLayout()
        self.laser_decay = QDoubleSpinBox()
        self.laser_decay.setRange(0, 100)
        self.laser_decay.setValue(0.0)
        self.laser_decay.setSuffix("") # No suffix in box, label at end
        decay_layout.addWidget(self.laser_decay)
        decay_layout.addWidget(QLabel("%"))
        top_layout.addLayout(decay_layout, 1, 3)

        # Row 2
        top_layout.addWidget(QLabel("激光器寿命:"), 2, 2, alignment=Qt.AlignRight)
        life_layout = QHBoxLayout()
        self.laser_life = QSpinBox()
        self.laser_life.setRange(0, 99999)
        self.laser_life.setValue(1000)
        self.laser_life.setSuffix("")
        life_layout.addWidget(self.laser_life)
        life_layout.addWidget(QLabel("小时"))
        top_layout.addLayout(life_layout, 2, 3)

        # Row 3
        # Checkbox under life
        self.check_show_power = QCheckBox("显示激光电源信息")
        top_layout.addWidget(self.check_show_power, 3, 2, 1, 2)
        
        top_group.setLayout(top_layout)
        main_layout.addWidget(top_group)
        
        # --- Bottom Grid for specific params ---
        # Use a centering layout or margins to make it look like the screenshot (indented)
        param_grid = QGridLayout()
        param_grid.setColumnStretch(2, 1) # Push everything to left but keep centered-ish
        
        # Helper to simplify adding rows
        row = 0
        def add_param(label_text, widget, span=1):
            nonlocal row
            param_grid.addWidget(QLabel(label_text), row, 0, alignment=Qt.AlignRight)
            param_grid.addWidget(widget, row, 1, 1, span)
            row += 1

        self.min_power = QDoubleSpinBox()
        self.min_power.setRange(0, 100)
        self.min_power.setValue(0.0)
        add_param("最小能量(%):", self.min_power)
        
        self.max_power = QDoubleSpinBox()
        self.max_power.setRange(0, 100)
        self.max_power.setValue(100.0)
        add_param("最大能量(%):", self.max_power)
        
        self.laser_freq_khz = QDoubleSpinBox()
        self.laser_freq_khz.setRange(0, 9999)
        self.laser_freq_khz.setValue(100.0)
        add_param("激光频率(KHZ):", self.laser_freq_khz)
        
        self.pre_freq = QDoubleSpinBox()
        self.pre_freq.setRange(0, 99999)
        self.pre_freq.setValue(5000.0)
        add_param("预燃频率(HZ):", self.pre_freq)
        
        self.pre_pulse = QDoubleSpinBox()
        self.pre_pulse.setValue(0.5)
        add_param("预燃脉宽(%):", self.pre_pulse)
        
        self.signal_level = QComboBox()
        self.signal_level.addItems(["低电平", "高电平"])
        add_param("开关信号电平:", self.signal_level)
        
        self.check_water = QCheckBox("水保护")
        # Align checkbox to start of widget column
        param_grid.addWidget(self.check_water, row, 0, 1, 2, alignment=Qt.AlignCenter) 
        
        # Center this grid in the layout
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addLayout(param_grid)
        hbox.addStretch(1)
        
        main_layout.addLayout(hbox)
        main_layout.addStretch()


class OtherSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Horizontal Split
        top_hbox = QHBoxLayout()
        
        # -- Group 1: Machine Config --
        grp_machine = QGroupBox("机器配置")
        form_machine = QFormLayout()
        
        self.trans_mode = QComboBox()
        self.trans_mode.addItems(["皮带步进"])
        form_machine.addRow("传动模式:", self.trans_mode)
        
        self.feed_mode = QComboBox()
        self.feed_mode.addItems(["单向", "双向"])
        form_machine.addRow("上料模式:", self.feed_mode)
        
        self.power_off_delay = QDoubleSpinBox()
        self.power_off_delay.setSuffix(" ms")
        self.power_off_delay.setValue(0.0)
        form_machine.addRow("断电延时:", self.power_off_delay)
        
        self.z_feat = QComboBox()
        self.z_feat.addItems(["平台"])
        self.z_feat.setEnabled(False) # Grayed out in screenshot
        form_machine.addRow("Z轴功能:", self.z_feat)
        
        grp_machine.setLayout(form_machine)
        top_hbox.addWidget(grp_machine)
        
        # -- Group 2: Multi-head Mutual Move --
        grp_multi = QGroupBox("多头互移模式")
        form_multi = QFormLayout()
        
        self.head_count = QComboBox()
        self.head_count.addItems(["1", "2"])
        form_multi.addRow("互移头数:", self.head_count)
        
        self.trans_method = QComboBox()
        self.trans_method.addItems(["单皮带型"])
        form_multi.addRow("传动方式:", self.trans_method)
        
        self.dist_1 = QDoubleSpinBox()
        self.dist_1.setSuffix(" mm")
        self.dist_1.setValue(50.000)
        form_multi.addRow("间距1:", self.dist_1)
        
        grp_multi.setLayout(form_multi)
        top_hbox.addWidget(grp_multi)
        
        main_layout.addLayout(top_hbox)
        
        # -- Encable Params --
        grp_enable = QGroupBox("使能参数")
        vbox_enable = QVBoxLayout()
        self.chk_cover = QCheckBox("使能开盖保护")
        self.chk_fan = QCheckBox("使能开风机")
        vbox_enable.addWidget(self.chk_cover)
        vbox_enable.addWidget(self.chk_fan)
        grp_enable.setLayout(vbox_enable)
        
        main_layout.addWidget(grp_enable)
        
        # Password Modify Button
        hbox_pwd = QHBoxLayout()
        hbox_pwd.addStretch()
        self.btn_modify_pwd = QPushButton("修改参数密码")
        self.btn_modify_pwd.setEnabled(False) # Looks disabled
        hbox_pwd.addWidget(self.btn_modify_pwd)
        
        main_layout.addLayout(hbox_pwd)
        main_layout.addStretch()


class LightSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Outer Frame
        frame = QGroupBox() # Or QFrame with Panel style
        grid = QGridLayout()
        grid.setSpacing(15)
        
        headers = ["空闲", "运行", "暂停", "故障", "使能"]
        # Add Headers
        for i, h in enumerate(headers):
            grid.addWidget(QLabel(h), 0, i+1, alignment=Qt.AlignCenter)
            
        rows = ["绿灯:", "黄灯:", "红灯:"]
        for r, label in enumerate(rows):
            grid.addWidget(QLabel(label), r+1, 0, alignment=Qt.AlignRight)
            for c in range(5):
                # Yellow, Red don't have Enable (column 4) in screenshot
                if c == 4 and r > 0: 
                    continue
                chk = QCheckBox()
                grid.addWidget(chk, r+1, c+1, alignment=Qt.AlignCenter)
                
        # Separator line
        grid.addWidget(HLine(), 4, 0, 1, 6)
        
        # Buzzer
        grid.addWidget(QLabel("蜂鸣器:"), 5, 0, alignment=Qt.AlignRight)
        for c in range(5):
             chk = QCheckBox()
             grid.addWidget(chk, 5, c+1, alignment=Qt.AlignCenter)
             
        frame.setLayout(grid)
        
        # Center the frame in the main layout
        hbox_center = QHBoxLayout()
        hbox_center.addStretch()
        hbox_center.addWidget(frame)
        hbox_center.addStretch()
        
        main_layout.addStretch()
        main_layout.addLayout(hbox_center)
        main_layout.addStretch()


class ClearInfoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        self.chk_clear_all = QCheckBox("清除所有信息")
        self.chk_clear_all.stateChanged.connect(self.on_clear_all)
        main_layout.addWidget(self.chk_clear_all)
        
        # Group Box for items
        group = QGroupBox() # visually distinct area
        group_layout = QVBoxLayout()
        group_layout.setSpacing(8)
        
        self.chk_items = []
        labels = [
            "清除累计开机时间",
            "清除累计加工时间",
            "清除前次加工时间", 
            "清除累计出光时间",
            "清除累计加工次数",
            # X/Y travel have colorful 'X'/'Y' in screenshot, simplified here
            "清除X轴累计行程",
            "清除Y轴累计行程"
        ]
        
        for lbl in labels:
            chk = QCheckBox(lbl)
            chk.setChecked(True)
            self.chk_items.append(chk)
            group_layout.addWidget(chk)
            
        group.setLayout(group_layout)
        main_layout.addWidget(group)
        
        # Execute Button
        hbox_exec = QHBoxLayout()
        hbox_exec.addSpacing(50) # Indent slightly
        self.btn_exec = QPushButton("执行")
        self.btn_exec.setFixedWidth(100)
        hbox_exec.addWidget(self.btn_exec)
        hbox_exec.addStretch()
        
        main_layout.addLayout(hbox_exec)
        main_layout.addStretch()

    def on_clear_all(self, state):
        is_checked = (state == Qt.Checked)
        for chk in self.chk_items:
            chk.setChecked(is_checked)


# ========================================================
# Main Dialog
# ========================================================
class ManufacturerSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("厂家工具")
        self.resize(650, 480)
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # --- Top Tabs ---
        self.tabs = QTabWidget()
        self.tab_params = QWidget() # Placeholder for "厂家参数"
        self.tab_clear_info = ClearInfoWidget() # "信息清零"
        
        self.tabs.addTab(self.tab_params, "厂家参数")
        self.tabs.addTab(self.tab_clear_info, "信息清零")
        
        layout.addWidget(self.tabs)
        
        # Setup "Manufacturer Params" tab content
        self.init_params_tab()
        
        # --- Bottom Area ---
        # "Status bar" text box on left, Buttons on right, Exit on bottom right
        
        bottom_frame = QFrame()
        bottom_frame.setFrameShape(QFrame.StyledPanel)
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(2, 2, 2, 2)
        bottom_layout.setSpacing(5)
        
        # Text/Progress area
        self.status_display = QLabel("  ") # Empty placeholder
        self.status_display.setFrameShape(QFrame.Panel)
        self.status_display.setFrameShadow(QFrame.Sunken)
        self.status_display.setMinimumWidth(200)
        
        bottom_layout.addWidget(self.status_display, 1) # Expandable
        
        # Buttons
        self.btn_read = QPushButton("读参数")
        self.btn_write = QPushButton("写参数")
        self.btn_open = QPushButton("打开")
        self.btn_save = QPushButton("保存")
        
        for btn in [self.btn_read, self.btn_write, self.btn_open, self.btn_save]:
            btn.setFixedWidth(60)
            bottom_layout.addWidget(btn)
            
        layout.addWidget(bottom_frame)
        
        # Exit button row
        exit_layout = QHBoxLayout()
        exit_layout.addStretch()
        self.btn_exit = QPushButton("退出")
        self.btn_exit.setFixedWidth(80)
        self.btn_exit.clicked.connect(self.reject)
        exit_layout.addWidget(self.btn_exit)
        
        layout.addLayout(exit_layout)

    def init_params_tab(self):
        # Layout for the first tab
        tab_layout = QHBoxLayout(self.tab_params)
        tab_layout.setContentsMargins(2, 2, 2, 2)
        
        # Left Sidebar List
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(80)
        self.list_widget.addItems(["电机", "激光", "其他", "三色灯"])
        self.list_widget.setCurrentRow(0)
        self.list_widget.currentRowChanged.connect(self.change_page)
        
        # Highlight selected item blue (basic styling)
        self.list_widget.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)
        
        tab_layout.addWidget(self.list_widget)
        
        # Right Stacked Content
        self.stacked_widget = QStackedWidget()
        # Add pages
        self.stacked_widget.addWidget(MotorSettingsWidget())
        self.stacked_widget.addWidget(LaserSettingsWidget())
        self.stacked_widget.addWidget(OtherSettingsWidget())
        self.stacked_widget.addWidget(LightSettingsWidget())
        
        # Wrap stacked widget in a frame for the border look
        stack_frame = QGroupBox()
        stack_layout = QVBoxLayout(stack_frame)
        stack_layout.setContentsMargins(2, 2, 2, 2)
        stack_layout.addWidget(self.stacked_widget)
        
        tab_layout.addWidget(stack_frame)

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
