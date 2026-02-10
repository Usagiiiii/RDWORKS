from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QRadioButton, QComboBox, QCheckBox, 
                             QPlainTextEdit, QGroupBox, QPushButton, QDoubleSpinBox, 
                             QSpinBox, QListWidget, QWidget, QDialogButtonBox, QSpacerItem, 
                             QSizePolicy, QListView, QLineEdit, QStackedWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase
import datetime
from ui.extension_dialog import ExtensionDialog

class TextDialog(QDialog):
    def __init__(self, parent=None, initial_text="", initial_settings=None):
        super().__init__(parent)
        self.setWindowTitle("文字")
        self.resize(600, 400)
        
        self.initial_text = initial_text
        self.initial_settings = initial_settings or {}
        self.extension_data = {}  # Store extension dialog data
        
        self.setup_ui()
        self.load_initial_settings()
        self.update_preview()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Top Area: Font Settings + Parameters
        top_layout = QHBoxLayout()
        
        # Left Side of Top: Font Selection and Text Input
        left_panel = QVBoxLayout()
        
        # Font Selection Group
        font_group = QGroupBox()
        font_layout = QGridLayout()
        
        self.radio_truetype = QRadioButton("TrueType字体:")
        self.radio_truetype.setChecked(True)
        self.combo_font = QComboBox()
        self.combo_font.setView(QListView())
        self.combo_font.setStyleSheet("QComboBox { background-color: #ffffff; }")
        self.combo_font.setMaxVisibleItems(10)
        self.combo_font.setEditable(True)
        self.combo_font.lineEdit().setReadOnly(True)
        # Populate fonts
        font_db = QFontDatabase()
        # Only allow scalable fonts (TrueType/OpenType) to prevent crashes with Raster fonts
        families = [f for f in font_db.families() if font_db.isSmoothlyScalable(f)]
        self.combo_font.addItems(families)
        
        # Default to Arial or first available
        index = self.combo_font.findText("Arial")
        if index >= 0:
            self.combo_font.setCurrentIndex(index)
        elif families:
            self.combo_font.setCurrentIndex(0)
        
        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedWidth(30)
        font = self.btn_bold.font()
        font.setBold(True)
        self.btn_bold.setFont(font)
        
        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedWidth(30)
        font = self.btn_italic.font()
        font.setItalic(True)
        self.btn_italic.setFont(font)

        self.radio_shx = QRadioButton("SHX字体:")
        self.combo_shx = QComboBox()
        self.combo_shx.setView(QListView())
        self.combo_shx.setStyleSheet("QComboBox { background-color: #ffffff; }")
        self.combo_shx.setMaxVisibleItems(10)
        self.combo_shx.setEditable(True)
        self.combo_shx.lineEdit().setReadOnly(True)
        self.combo_shx.addItem("SCRIPTS.SHX") # Placeholder
        self.combo_shx.setEnabled(False)

        font_layout.addWidget(self.radio_truetype, 0, 0)
        font_layout.addWidget(self.combo_font, 0, 1)
        font_layout.addWidget(self.btn_bold, 0, 2)
        font_layout.addWidget(self.btn_italic, 0, 3)
        font_layout.addWidget(self.radio_shx, 1, 0)
        font_layout.addWidget(self.combo_shx, 1, 1)
        
        font_group.setLayout(font_layout)
        left_panel.addWidget(font_group)

        # Text Input
        self.text_edit = QPlainTextEdit()
        if self.initial_text:
            self.text_edit.setPlainText(self.initial_text)
        left_panel.addWidget(self.text_edit)
        
        top_layout.addLayout(left_panel, stretch=2)

        # Right Side of Top: Parameters AND Variable Text
        right_panel = QVBoxLayout()
        
        # Parameters Group
        param_group = QGroupBox()
        param_layout = QGridLayout()
        
        self.spin_width_percent = QSpinBox()
        self.spin_width_percent.setRange(1, 1000)
        self.spin_width_percent.setValue(100)
        self.spin_width_percent.setSuffix(" %")
        
        self.spin_char_spacing = QDoubleSpinBox()
        self.spin_char_spacing.setRange(-100, 100)
        self.spin_char_spacing.setSuffix(" mm")
        
        self.spin_line_spacing = QDoubleSpinBox()
        self.spin_line_spacing.setRange(-100, 100)
        self.spin_line_spacing.setSuffix(" mm")

        param_layout.addWidget(QLabel("字宽:"), 0, 0)
        param_layout.addWidget(self.spin_width_percent, 0, 1)
        param_layout.addWidget(QLabel("字间距:"), 1, 0)
        param_layout.addWidget(self.spin_char_spacing, 1, 1)
        param_layout.addWidget(QLabel("行间距:"), 2, 0)
        param_layout.addWidget(self.spin_line_spacing, 2, 1)
        
        param_group.setLayout(param_layout)
        right_panel.addWidget(param_group)

        # Variable Text Group (Simplified placeholder based on screenshot)
        var_group = QGroupBox()
        var_layout = QVBoxLayout()
        
        self.chk_enable_var = QCheckBox("使能变量文字")
        var_layout.addWidget(self.chk_enable_var)
        
        # Container for variable text options
        self.var_options_widget = QWidget()
        var_options_layout = QVBoxLayout(self.var_options_widget)
        var_options_layout.setContentsMargins(0, 0, 0, 0)
        
        self.combo_var_type = QComboBox()
        self.combo_var_type.setView(QListView())
        self.combo_var_type.setStyleSheet("QComboBox { background-color: #ffffff; }")
        self.combo_var_type.setMaxVisibleItems(10)
        self.combo_var_type.setEditable(True)
        self.combo_var_type.lineEdit().setReadOnly(True)
        self.combo_var_type.addItems(["日期", "序列号"])
        var_options_layout.addWidget(self.combo_var_type)
        
        # Use StackedWidget to switch between variable type interfaces without layout shift
        self.stacked_options = QStackedWidget()
        
        # --- Date Options Area (Index 0) ---
        self.widget_date_options = QWidget()
        date_layout = QVBoxLayout(self.widget_date_options)
        date_layout.setContentsMargins(0, 5, 0, 0)
        
        self.list_var_formats = QListWidget()
        self.list_var_formats.addItems([
            "default[20260113]",
            "12Hour[HH:MM][01:42]",
            "12Hour[HH:MM][01:42:59]",
            "24Hour[HH:MM][13:42]",
            "24Hour[HH:MM][13:42:59]",
            "American Date[01/21/2026]",
            "Chinese Date[2026年01月21日]",
            "Chinese Date Time[2026年01月21日]",
            "Chinese Time[13时42分59秒]",
            "European Date Time[21/01/2026p]",
            "European Date[21.01.2026]",
            "Week Year[21/01/2026 13:42:59]"
        ])
        date_layout.addWidget(self.list_var_formats)

        # Date Offset Area
        hbox_offset = QHBoxLayout()
        hbox_offset.setSpacing(2)
        hbox_offset.addWidget(QLabel("日期偏移:"))
        
        self.combo_offset_unit = QComboBox()
        self.combo_offset_unit.setView(QListView())
        self.combo_offset_unit.setStyleSheet("QComboBox { background-color: #ffffff; }")
        self.combo_offset_unit.setMaxVisibleItems(3)
        self.combo_offset_unit.setEditable(True) 
        self.combo_offset_unit.lineEdit().setReadOnly(True)
        self.combo_offset_unit.addItems(["按日", "按月", "按年"])
        self.combo_offset_unit.setFixedWidth(60)
        hbox_offset.addWidget(self.combo_offset_unit)
        
        self.spin_offset_val = QSpinBox()
        self.spin_offset_val.setRange(-36500, 36500)
        self.spin_offset_val.setFixedWidth(50)
        hbox_offset.addWidget(self.spin_offset_val)
        
        date_layout.addLayout(hbox_offset)

        self.stacked_options.addWidget(self.widget_date_options)

        # --- Serial Number Options Area (Index 1) ---
        self.widget_sn_options = QWidget()
        sn_layout = QGridLayout(self.widget_sn_options)
        sn_layout.setContentsMargins(0, 5, 0, 0)
        sn_layout.setSpacing(5)

        self.edit_sn_prefix = QLineEdit()
        self.edit_sn_suffix = QLineEdit()
        self.edit_sn_start = QLineEdit("0000")
        self.edit_sn_current = QLineEdit("0000")
        self.edit_sn_inc = QLineEdit("1")
        self.btn_sn_extend = QPushButton("扩展")
        self.btn_sn_extend.clicked.connect(self.open_extension_dialog)

        # Labels alignment right
        l1 = QLabel("前导字符串:")
        l1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        l2 = QLabel("后导字符串:")
        l2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        l3 = QLabel("开始序号:")
        l3.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        l4 = QLabel("当前序号:")
        l4.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        l5 = QLabel("序号增量:")
        l5.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        sn_layout.addWidget(l1, 0, 0)
        sn_layout.addWidget(self.edit_sn_prefix, 0, 1)
        
        sn_layout.addWidget(l2, 1, 0)
        sn_layout.addWidget(self.edit_sn_suffix, 1, 1)

        sn_layout.addWidget(l3, 2, 0)
        sn_layout.addWidget(self.edit_sn_start, 2, 1)

        sn_layout.addWidget(l4, 3, 0)
        sn_layout.addWidget(self.edit_sn_current, 3, 1)

        sn_layout.addWidget(l5, 4, 0)
        sn_layout.addWidget(self.edit_sn_inc, 4, 1)
        
        # Add stretch or spacer to keep layout compact similar to form
        sn_layout.addWidget(self.btn_sn_extend, 5, 1)
        
        # Ensure SN widget has enough height so it doesn't jump when switching
        # Or better, let stack take the largest size
        
        self.stacked_options.addWidget(self.widget_sn_options)
        
        var_options_layout.addWidget(self.stacked_options)
        
        self.combo_var_type.currentTextChanged.connect(self.on_var_type_changed)
        
        var_layout.addWidget(self.var_options_widget)
        
        # Set initial visibility state
        sp = self.var_options_widget.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.var_options_widget.setSizePolicy(sp)

        self.var_options_widget.setVisible(self.chk_enable_var.isChecked())
        self.chk_enable_var.toggled.connect(self.var_options_widget.setVisible)

        var_group.setLayout(var_layout)
        right_panel.addWidget(var_group)
        
        top_layout.addLayout(right_panel, stretch=1)
        main_layout.addLayout(top_layout)

        # Bottom Area
        bottom_layout = QHBoxLayout()
        
        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(0.1, 1000)
        self.spin_height.setValue(10.0) # Default height
        
        bottom_layout.addWidget(QLabel("高度:"))
        bottom_layout.addWidget(self.spin_height)
        bottom_layout.addWidget(QLabel("mm"))
        
        bottom_layout.addStretch()
        
        # Apply button (just for show mostly in modal dialogs or update preview)
        self.btn_apply = QPushButton("应用")
        bottom_layout.addWidget(self.btn_apply)

        # OK/Cancel
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(self.button_box)

        main_layout.addLayout(bottom_layout)

        # Connect signals
        self.combo_font.currentTextChanged.connect(self.update_preview)
        self.btn_bold.toggled.connect(self.update_preview)
        self.btn_italic.toggled.connect(self.update_preview)
        self.radio_truetype.toggled.connect(self.toggle_font_mode)
        self.radio_shx.toggled.connect(self.toggle_font_mode)

        self.spin_width_percent.valueChanged.connect(self.update_preview)
        self.spin_char_spacing.valueChanged.connect(self.update_preview)
        
        # Connect variable text signals
        self.list_var_formats.currentRowChanged.connect(self.on_date_format_selected)
        self.list_var_formats.itemClicked.connect(self.on_date_format_selected)
        # Offset changes simply update data, no preview update needed for now
        # self.combo_offset_unit.currentTextChanged.connect(self.update_date_preview) 
        # self.spin_offset_val.valueChanged.connect(self.update_date_preview)

    def on_var_type_changed(self, text):
        if text == "日期":
            self.stacked_options.setCurrentIndex(0)
        elif text == "序列号":
            self.stacked_options.setCurrentIndex(1)
            
    def get_selected_date_format(self):
        item = self.list_var_formats.currentItem()
        if not item: return None
        text = item.text()
        # Extract format based on known prefixes
        if text.startswith("default"): return "%Y%m%d"
        if text.startswith("12Hour"): 
            return "%I:%M:%S" if text.count(":") == 2 else "%I:%M"
        if text.startswith("24Hour"): 
            return "%H:%M:%S" if text.count(":") == 2 else "%H:%M"
        if text.startswith("American Date"): return "%m/%d/%Y"
        if text.startswith("Chinese Date Time"): return "%Y年%m月%d日" 
        if text.startswith("Chinese Date"): return "%Y年%m月%d日"
        if text.startswith("Chinese Time"): return "%H时%M分%S秒"
        if text.startswith("European Date Time"): return "%d/%m/%Y"
        if text.startswith("European Date"): return "%d.%m.%Y"
        if text.startswith("Week Year"): return "%d/%m/%Y %H:%M:%S"
        return "%Y%m%d"

    def calculate_offset_date(self):
        # Calculation logic for backend use if needed
        # ... (Same logic as before, kept for reference or backend)
        now = datetime.datetime.now()
        unit = self.combo_offset_unit.currentText()
        val = self.spin_offset_val.value()
        
        if val == 0: return now
        
        if unit == "按日":
            return now + datetime.timedelta(days=val)
        elif unit == "按月":
            import calendar
            m = now.month + val
            m0 = now.month - 1 + val
            y_diff = m0 // 12
            m0 = m0 % 12
            y = now.year + y_diff
            m = m0 + 1
            last_day = calendar.monthrange(y, m)[1]
            d = min(now.day, last_day)
            return now.replace(year=y, month=m, day=d)
        elif unit == "按年":
            try:
                return now.replace(year=now.year + val)
            except ValueError:
                return now.replace(year=now.year + val, day=28)
        return now

    def on_date_format_selected(self, *args):
        if not self.chk_enable_var.isChecked(): return
        if self.combo_var_type.currentText() != "日期": return
        
        item = self.list_var_formats.currentItem()
        if item:
            # User requirement: "Display the text created at that time rather than displaying the date"
            # Interpreted as displaying the variable text string from the list
            self.text_edit.setPlainText(item.text())

    def toggle_font_mode(self):
        is_tt = self.radio_truetype.isChecked()
        self.combo_font.setEnabled(is_tt)
        self.btn_bold.setEnabled(is_tt)
        self.btn_italic.setEnabled(is_tt)
        self.combo_shx.setEnabled(not is_tt)

    def load_initial_settings(self):
        s = self.initial_settings
        if not s:
            return

        # Font Type
        is_tt = s.get('is_truetype', True)
        self.radio_truetype.setChecked(is_tt)
        self.radio_shx.setChecked(not is_tt)
        
        # Font Family
        font_family = s.get('font_family', 'Arial')
        index = self.combo_font.findText(font_family)
        if index >= 0:
            self.combo_font.setCurrentIndex(index)
        
        # Style
        self.btn_bold.setChecked(s.get('is_bold', False))
        self.btn_italic.setChecked(s.get('is_italic', False))
        
        # Metrics
        self.spin_height.setValue(float(s.get('height', 10.0)))
        self.spin_width_percent.setValue(int(s.get('width_percent', 100)))
        self.spin_char_spacing.setValue(float(s.get('char_spacing', 0.0)))
        self.spin_line_spacing.setValue(float(s.get('line_spacing', 0.0)))
        
        # Variable Text
        enable_var = s.get('enable_var', False)
        self.chk_enable_var.setChecked(enable_var)
        if enable_var:
            var_type = s.get('var_type', '日期')
            idx = self.combo_var_type.findText(var_type)
            if idx >= 0:
                self.combo_var_type.setCurrentIndex(idx)
            
            # Simple restoration for variable fields if needed, 
            # but user focus is on font params.
        
        # Trigger mode update
        self.toggle_font_mode()

    def update_preview(self):
        # Update the font of the input area to match selection
        if self.radio_truetype.isChecked():
            font_family = self.combo_font.currentText()
            font = QFont(font_family)
            font.setBold(self.btn_bold.isChecked())
            font.setItalic(self.btn_italic.isChecked())
            
            # Apply Width (Stretch)
            # The spinbox is percentage (e.g., 100 for normal). 
            # QFont setStretch accepts integer percentage.
            font.setStretch(int(self.spin_width_percent.value()))
            
            # Apply Character Spacing
            # Converting mm to logical pixels for display approximation
            # Assuming standard DPI (~96), 1mm is approx 3.78 pixels
            spacing_mm = self.spin_char_spacing.value()
            if spacing_mm != 0:
                font.setLetterSpacing(QFont.AbsoluteSpacing, spacing_mm * 3.78)

            # Use a reasonable size for UI preview, not the physical height
            font.setPointSize(12) 
            self.text_edit.setFont(font)

    def get_data(self):
        # Base Data
        data = {
            "text": self.text_edit.toPlainText(),
            "font_family": self.combo_font.currentText(),
            "is_bold": self.btn_bold.isChecked(),
            "is_italic": self.btn_italic.isChecked(),
            "height": self.spin_height.value(),
            "width_percent": self.spin_width_percent.value(),
            "char_spacing": self.spin_char_spacing.value(),
            "line_spacing": self.spin_line_spacing.value(),
            "is_truetype": self.radio_truetype.isChecked(),
            "enable_var": self.chk_enable_var.isChecked()
        }
        
        # Extended Variable Data (if needed later)
        if self.chk_enable_var.isChecked():
            var_type = self.combo_var_type.currentText()
            data["var_type"] = var_type
            if var_type == "序列号":
                data.update({
                    "sn_prefix": self.edit_sn_prefix.text(),
                    "sn_suffix": self.edit_sn_suffix.text(),
                    "sn_start": self.edit_sn_start.text(),
                    "sn_current": self.edit_sn_current.text(),
                    "sn_inc": self.edit_sn_inc.text()
                })
            elif var_type == "日期":
                 data.update({
                    "date_format_text": self.list_var_formats.currentItem().text() if self.list_var_formats.currentItem() else "",
                    "offset_unit": self.combo_offset_unit.currentText(),
                    "offset_value": self.spin_offset_val.value()
                })
        
        if self.extension_data:
            data.update(self.extension_data)

        return data

    def open_extension_dialog(self):
        dlg = ExtensionDialog(self, initial_data=self.extension_data)
        if dlg.exec_() == QDialog.Accepted:
            self.extension_data = dlg.get_data()
