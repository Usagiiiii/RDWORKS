from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QPushButton, QLineEdit, QGroupBox, 
                             QComboBox, QRadioButton, QButtonGroup, QGridLayout,
                             QWidget, QFrame, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen

class AdvancedImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导入高级参数")
        # Removing fixed size to prevent compression, let the layout decide min size
        # self.setFixedSize(650, 550)
        
        # Main Layout (Vertical: Top Area + Buttons)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Content Layout (Horizontal: Left Col + Right Col)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # --- LEFT COLUMN ---
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        
        # 1. 剪口参数
        gb_cut_param = QGroupBox("剪口参数")
        grid_cut = QGridLayout(gb_cut_param)
        grid_cut.setContentsMargins(10, 15, 10, 10)
        grid_cut.setVerticalSpacing(15)
        grid_cut.setHorizontalSpacing(10)
        
        # Row 0: Line Type
        self.chk_cut_line = QCheckBox()
        self.lbl_icon1 = self.create_icon_placeholder("Line", 60, 50)
        
        grid_cut.addWidget(self.chk_cut_line, 0, 0)
        grid_cut.addWidget(self.lbl_icon1, 0, 1)
        
        # Hmin/Hmax
        # Using GridLayout for inputs inside to ensure alignment
        frame_line = QFrame()
        grid_line_params = QGridLayout(frame_line)
        grid_line_params.setContentsMargins(0, 0, 0, 0)
        grid_line_params.setVerticalSpacing(6)
        
        self.txt_hmin1 = QLineEdit("1.000"); self.txt_hmin1.setFixedWidth(60)
        grid_line_params.addWidget(QLabel("Hmin:"), 0, 0, Qt.AlignRight)
        grid_line_params.addWidget(self.txt_hmin1, 0, 1)
        grid_line_params.addWidget(QLabel("mm"), 0, 2)
        
        self.txt_hmax1 = QLineEdit("5.000"); self.txt_hmax1.setFixedWidth(60)
        grid_line_params.addWidget(QLabel("Hmax:"), 1, 0, Qt.AlignRight)
        grid_line_params.addWidget(self.txt_hmax1, 1, 1)
        grid_line_params.addWidget(QLabel("mm"), 1, 2)
        
        grid_cut.addWidget(frame_line, 0, 2)
        
        # Row 1: T Type
        self.chk_cut_t = QCheckBox()
        self.lbl_icon2 = self.create_icon_placeholder("T", 60, 50)
        
        grid_cut.addWidget(self.chk_cut_t, 1, 0)
        grid_cut.addWidget(self.lbl_icon2, 1, 1)
        
        # L/H
        frame_t = QFrame()
        grid_t_params = QGridLayout(frame_t)
        grid_t_params.setContentsMargins(0, 0, 0, 0)
        grid_t_params.setVerticalSpacing(6)
        
        self.txt_l2 = QLineEdit("3.000"); self.txt_l2.setFixedWidth(60)
        grid_t_params.addWidget(QLabel("L:"), 0, 0, Qt.AlignRight)
        grid_t_params.addWidget(self.txt_l2, 0, 1)
        grid_t_params.addWidget(QLabel("mm"), 0, 2)
        
        self.txt_h2 = QLineEdit("10.000"); self.txt_h2.setFixedWidth(60)
        grid_t_params.addWidget(QLabel("H:"), 1, 0, Qt.AlignRight)
        grid_t_params.addWidget(self.txt_h2, 1, 1)
        grid_t_params.addWidget(QLabel("mm"), 1, 2)

        grid_cut.addWidget(frame_t, 1, 2)
        
        # Row 2: V Type
        self.chk_cut_v = QCheckBox()
        self.lbl_icon3 = self.create_icon_placeholder("V", 60, 50)
        
        grid_cut.addWidget(self.chk_cut_v, 2, 0)
        grid_cut.addWidget(self.lbl_icon3, 2, 1)
        
        # 4 inputs
        frame_v = QFrame()
        grid_v_params = QGridLayout(frame_v)
        grid_v_params.setContentsMargins(0, 0, 0, 0)
        grid_v_params.setVerticalSpacing(6)
        
        self.txt_lmin3 = QLineEdit("2.000"); self.txt_lmin3.setFixedWidth(60)
        grid_v_params.addWidget(QLabel("Lmin:"), 0, 0, Qt.AlignRight)
        grid_v_params.addWidget(self.txt_lmin3, 0, 1)
        grid_v_params.addWidget(QLabel("mm"), 0, 2)
        
        self.txt_lmax3 = QLineEdit("5.000"); self.txt_lmax3.setFixedWidth(60)
        grid_v_params.addWidget(QLabel("Lmax:"), 1, 0, Qt.AlignRight)
        grid_v_params.addWidget(self.txt_lmax3, 1, 1)
        grid_v_params.addWidget(QLabel("mm"), 1, 2)
        
        self.txt_amin3 = QLineEdit("10.000"); self.txt_amin3.setFixedWidth(60)
        grid_v_params.addWidget(QLabel("Amin:"), 2, 0, Qt.AlignRight)
        grid_v_params.addWidget(self.txt_amin3, 2, 1)
        grid_v_params.addWidget(QLabel("mm"), 2, 2)
        
        self.txt_amax3 = QLineEdit("60.000"); self.txt_amax3.setFixedWidth(60)
        grid_v_params.addWidget(QLabel("Amax:"), 3, 0, Qt.AlignRight)
        grid_v_params.addWidget(self.txt_amax3, 3, 1)
        grid_v_params.addWidget(QLabel("mm"), 3, 2)
        
        grid_cut.addWidget(frame_v, 2, 2)
        
        # Add Stretch to push everything up if needed, but in QGridLayout rows take space roughly equally unless stretched.
        # Let's clean up grid distribution
        grid_cut.setColumnStretch(2, 1) 
        
        left_layout.addWidget(gb_cut_param)
        
        # 2. 剪口处理
        gb_cut_proc = QGroupBox("剪口处理")
        v_proc = QVBoxLayout(gb_cut_proc)
        
        h_color = QHBoxLayout()
        self.rb_color_diff = QRadioButton("颜色区分")
        self.rb_color_diff.setChecked(True)
        self.cmb_color_layer = QComboBox()
        # 支持 1..20 的图层选择，默认值保持为 3
        self.cmb_color_layer.addItems([str(i) for i in range(1, 21)])
        self.cmb_color_layer.setCurrentText("3")
        # Combo behavior: match existing app pattern (show many items, not editable text)
        self.cmb_color_layer.setMaxVisibleItems(10)
        self.cmb_color_layer.setEditable(True)
        self.cmb_color_layer.lineEdit().setReadOnly(True)
        h_color.addWidget(self.rb_color_diff)
        h_color.addWidget(self.cmb_color_layer)
        h_color.addStretch()
        v_proc.addLayout(h_color)
        
        self.rb_merge_outline = QRadioButton("并入外轮廓")
        v_proc.addWidget(self.rb_merge_outline)
        
        h_merge = QHBoxLayout()
        h_merge.setContentsMargins(20, 0, 0, 0)
        self.chk_mod_cut_size = QCheckBox("修改剪口尺寸")
        self.txt_mod_cut_size = QLineEdit("5.000")
        self.txt_mod_cut_size.setFixedWidth(50)
        h_merge.addWidget(self.chk_mod_cut_size)
        h_merge.addWidget(self.txt_mod_cut_size)
        h_merge.addWidget(QLabel("mm"))
        h_merge.addStretch()
        v_proc.addLayout(h_merge)
        
        self.bg_cut_proc = QButtonGroup(self)
        self.bg_cut_proc.addButton(self.rb_color_diff)
        self.bg_cut_proc.addButton(self.rb_merge_outline)
        
        left_layout.addWidget(gb_cut_proc)
        
        # 3. 内外轮廓分离
        gb_outline = QGroupBox("内外轮廓分离")
        grid_outline = QGridLayout(gb_outline)
        
        self.txt_out_min = QLineEdit("100.000"); self.txt_out_min.setFixedWidth(50)
        grid_outline.addLayout(self.create_entry("外轮廓最小尺寸:", self.txt_out_min), 0, 0)
        
        self.txt_out_max = QLineEdit("4000.000"); self.txt_out_max.setFixedWidth(50)
        grid_outline.addLayout(self.create_entry("外轮廓最大尺寸:", self.txt_out_max), 1, 0)
        
        self.chk_del_outer = QCheckBox("自动删除最外层方框")
        self.chk_del_outer.setChecked(True)
        grid_outline.addWidget(self.chk_del_outer, 2, 0)
        
        self.chk_unify_color = QCheckBox("外轮廓统一颜色")
        self.chk_unify_color.setChecked(True)
        grid_outline.addWidget(self.chk_unify_color, 3, 0)
        
        self.chk_closed_only = QCheckBox("外轮廓仅限闭合图形")
        self.chk_closed_only.setChecked(True)
        grid_outline.addWidget(self.chk_closed_only, 4, 0)
        
        h_rep = QHBoxLayout()
        h_rep.addWidget(QLabel("内轮廓替换图层:"))
        self.cmb_inner_layer = QComboBox()
        # 支持 1..20 的图层选择，默认值与颜色区分图层一致（3）
        self.cmb_inner_layer.addItems([str(i) for i in range(1, 21)])
        self.cmb_inner_layer.setCurrentText("3")
        self.cmb_inner_layer.setMaxVisibleItems(10)
        self.cmb_inner_layer.setEditable(True)
        self.cmb_inner_layer.lineEdit().setReadOnly(True)
        self.chk_inner_layer_enable = QCheckBox()
        self.chk_inner_layer_enable.setChecked(True)
        h_rep.addWidget(self.cmb_inner_layer)
        h_rep.addWidget(self.chk_inner_layer_enable)
        h_rep.addStretch()
        grid_outline.addLayout(h_rep, 5, 0)
        
        self.chk_intersect_conv = QCheckBox("外轮廓相交线转外轮廓")
        grid_outline.addWidget(self.chk_intersect_conv, 6, 0)
        
        left_layout.addWidget(gb_outline)
        
        
        # --- RIGHT COLUMN ---
        right_layout = QVBoxLayout()
        
        # 4. 标签识别
        gb_label = QGroupBox("标签识别")
        v_label = QVBoxLayout(gb_label)
        
        self.chk_label_enable = QCheckBox("使能标签识别功能")
        v_label.addWidget(self.chk_label_enable)
        
        # Indent content
        self.label_content_widget = QWidget()
        v_label_content = QVBoxLayout(self.label_content_widget)
        v_label_content.setContentsMargins(15, 0, 0, 0)
        v_label_content.setSpacing(8)
        
        self.rb_label_recog = QRadioButton("识别图形中标签并添加文字")
        self.rb_label_recog.setChecked(True)
        v_label_content.addWidget(self.rb_label_recog)
        
        self.rb_label_custom = QRadioButton("自定义添加标签文字")
        v_label_content.addWidget(self.rb_label_custom)
        
        h_pos = QHBoxLayout()
        h_pos.setContentsMargins(20, 0, 0, 0)
        h_pos.addWidget(QLabel("标签添加位置:"))
        self.cmb_label_pos = QComboBox()
        self.cmb_label_pos.addItems(["中间", "左上", "左下", "右上", "右下"])
        self.cmb_label_pos.setFixedWidth(80) 
        self.cmb_label_pos.setEditable(True)
        self.cmb_label_pos.lineEdit().setReadOnly(True)
        h_pos.addWidget(self.cmb_label_pos)
        h_pos.addStretch()
        v_label_content.addLayout(h_pos)
        
        line_label = QFrame(); line_label.setFrameShape(QFrame.HLine)
        line_label.setFrameShadow(QFrame.Sunken)
        v_label_content.addWidget(line_label)
        
        # Label Image and Dimensions
        h_label_geom = QHBoxLayout()
        self.lbl_label_img = self.create_icon_placeholder("Label Vis", 80, 50)
        h_label_geom.addWidget(self.lbl_label_img)
        
        v_label_dim = QVBoxLayout()
        v_label_dim.setSpacing(5)
        
        h_ld1 = QHBoxLayout()
        h_ld1.addWidget(QLabel("L:")); 
        self.txt_label_l = QLineEdit("40.000"); self.txt_label_l.setFixedWidth(60)
        h_ld1.addWidget(self.txt_label_l); h_ld1.addWidget(QLabel("mm")); h_ld1.addStretch()
        
        h_ld2 = QHBoxLayout()
        h_ld2.addWidget(QLabel("H:")); 
        self.txt_label_h = QLineEdit("15.000"); self.txt_label_h.setFixedWidth(60)
        h_ld2.addWidget(self.txt_label_h); h_ld2.addWidget(QLabel("mm")); h_ld2.addStretch()

        v_label_dim.addLayout(h_ld1)
        v_label_dim.addLayout(h_ld2)
        h_label_geom.addLayout(v_label_dim)
        h_label_geom.addStretch()
        v_label_content.addLayout(h_label_geom)
        
        # Label Params Grid
        g_label_p = QGridLayout()
        g_label_p.setVerticalSpacing(8)

        g_label_p.addWidget(QLabel("标签图层:", alignment=Qt.AlignRight), 0, 0)
        self.cmb_label_layer = QComboBox()
        # 标签图层 1..20，默认 4
        self.cmb_label_layer.addItems([str(i) for i in range(1, 21)])
        self.cmb_label_layer.setCurrentText("4")
        self.cmb_label_layer.setFixedWidth(80)
        self.cmb_label_layer.setEditable(True)
        self.cmb_label_layer.lineEdit().setReadOnly(True)
        g_label_p.addWidget(self.cmb_label_layer, 0, 1)
        
        g_label_p.addWidget(QLabel("标签字高:", alignment=Qt.AlignRight), 1, 0)
        self.txt_label_height = QLineEdit("12.000"); self.txt_label_height.setFixedWidth(60)
        h_lh = QHBoxLayout(); h_lh.addWidget(self.txt_label_height); h_lh.addWidget(QLabel("mm")); h_lh.addStretch()
        g_label_p.addLayout(h_lh, 1, 1)
        
        g_label_p.addWidget(QLabel("标签字宽:", alignment=Qt.AlignRight), 2, 0)
        self.txt_label_width = QLineEdit("50.000"); self.txt_label_width.setFixedWidth(60)
        h_lw = QHBoxLayout(); h_lw.addWidget(self.txt_label_width); h_lw.addWidget(QLabel("%")); h_lw.addStretch()
        g_label_p.addLayout(h_lw, 2, 1)
        
        g_label_p.addWidget(QLabel("标签偏移:", alignment=Qt.AlignRight), 3, 0)
        l_off = QHBoxLayout()
        l_off.setSpacing(5)
        self.txt_off_x = QLineEdit("0.0"); self.txt_off_x.setFixedWidth(40)
        l_off.addWidget(self.txt_off_x)
        self.txt_off_y = QLineEdit("0.0"); self.txt_off_y.setFixedWidth(40)
        l_off.addWidget(self.txt_off_y)
        l_off.addStretch()
        g_label_p.addLayout(l_off, 3, 1)
        
        self.chk_label_outwards = QCheckBox("标签文字朝外")
        self.chk_label_outwards.setChecked(True)
        g_label_p.addWidget(self.chk_label_outwards, 4, 1)
        
        v_label_content.addLayout(g_label_p)
        
        line_label2 = QFrame(); line_label2.setFrameShape(QFrame.HLine)
        line_label2.setFrameShadow(QFrame.Sunken)
        v_label_content.addWidget(line_label2)
        
        # Bottom area
        g_bottom = QGridLayout()
        g_bottom.setVerticalSpacing(8)
        
        g_bottom.addWidget(QLabel("标签文字:", alignment=Qt.AlignRight), 0, 0)
        self.cmb_label_text = QComboBox()
        # 标签文字选项：按参考截图提供常用选项
        self.cmb_label_text.addItems([
            "图元全称",
            "SIZE后字段",
            "下划线前字段",
            "下划线后字段",
            "中括号内字段",
        ])
        self.cmb_label_text.setFixedWidth(120)
        self.cmb_label_text.setCurrentText("图元全称")
        self.cmb_label_text.setEditable(True)
        self.cmb_label_text.lineEdit().setReadOnly(True)
        g_bottom.addWidget(self.cmb_label_text, 0, 1)
        
        g_bottom.addWidget(QLabel("有效长度限制:", alignment=Qt.AlignRight), 1, 0)
        self.txt_len_limit = QLineEdit("3"); self.txt_len_limit.setFixedWidth(60)
        g_bottom.addWidget(self.txt_len_limit, 1, 1)
        
        v_label_content.addLayout(g_bottom)
        
        v_label.addWidget(self.label_content_widget)
        right_layout.addWidget(gb_label)
        
        # 5. 分离圆孔
        gb_holes = QGroupBox("分离圆孔")
        gb_holes.setCheckable(True)
        gb_holes.setChecked(False) 
        
        grid_holes = QGridLayout(gb_holes)
        grid_holes.setSpacing(5)
        
        grid_holes.addWidget(QLabel("最小直径"), 0, 1)
        grid_holes.addWidget(QLabel("最大直径"), 0, 2)
        grid_holes.addWidget(QLabel("圆孔图层"), 0, 3)
        
        # Row 1
        self.txt_h1_min = QLineEdit("1.000"); self.txt_h1_min.setFixedWidth(50)
        self.txt_h1_max = QLineEdit("10.000"); self.txt_h1_max.setFixedWidth(50)
        self.cmb_h1_layer = QComboBox()
        # 圆孔图层支持 1..20，默认 5
        self.cmb_h1_layer.addItems([str(i) for i in range(1, 21)])
        self.cmb_h1_layer.setCurrentText("5")
        self.cmb_h1_layer.setMaxVisibleItems(10)
        self.cmb_h1_layer.setEditable(True)
        self.cmb_h1_layer.lineEdit().setReadOnly(True)
        self.btn_h1_color = QPushButton(); self.btn_h1_color.setStyleSheet("background-color: red"); self.btn_h1_color.setFixedWidth(20)
        
        grid_holes.addWidget(self.txt_h1_min, 1, 1)
        grid_holes.addWidget(self.txt_h1_max, 1, 2)
        h_l1 = QHBoxLayout(); h_l1.addWidget(self.cmb_h1_layer); h_l1.addWidget(self.btn_h1_color)
        grid_holes.addLayout(h_l1, 1, 3)
        
        # Row 2
        self.chk_h2 = QCheckBox("孔2")
        self.txt_h2_min = QLineEdit("1.000"); self.txt_h2_min.setFixedWidth(50)
        self.txt_h2_max = QLineEdit("10.000"); self.txt_h2_max.setFixedWidth(50)
        self.cmb_h2_layer = QComboBox()
        self.cmb_h2_layer.addItems([str(i) for i in range(1, 21)])
        self.cmb_h2_layer.setCurrentText("6")
        self.cmb_h2_layer.setMaxVisibleItems(10)
        self.cmb_h2_layer.setEditable(True)
        self.cmb_h2_layer.lineEdit().setReadOnly(True)
        self.btn_h2_color = QPushButton(); self.btn_h2_color.setStyleSheet("background-color: yellow"); self.btn_h2_color.setFixedWidth(20)
        
        grid_holes.addWidget(self.chk_h2, 2, 0)
        grid_holes.addWidget(self.txt_h2_min, 2, 1)
        grid_holes.addWidget(self.txt_h2_max, 2, 2)
        h_l2 = QHBoxLayout(); h_l2.addWidget(self.cmb_h2_layer); h_l2.addWidget(self.btn_h2_color)
        grid_holes.addLayout(h_l2, 2, 3)
        
        # Row 3
        self.chk_h3 = QCheckBox("孔3")
        self.txt_h3_min = QLineEdit("1.000"); self.txt_h3_min.setFixedWidth(50)
        self.txt_h3_max = QLineEdit("10.000"); self.txt_h3_max.setFixedWidth(50)
        self.cmb_h3_layer = QComboBox()
        self.cmb_h3_layer.addItems([str(i) for i in range(1, 21)])
        self.cmb_h3_layer.setCurrentText("7")
        self.cmb_h3_layer.setMaxVisibleItems(10)
        self.cmb_h3_layer.setEditable(True)
        self.cmb_h3_layer.lineEdit().setReadOnly(True)
        self.btn_h3_color = QPushButton(); self.btn_h3_color.setStyleSheet("background-color: blue"); self.btn_h3_color.setFixedWidth(20)
        
        grid_holes.addWidget(self.chk_h3, 3, 0)
        grid_holes.addWidget(self.txt_h3_min, 3, 1)
        grid_holes.addWidget(self.txt_h3_max, 3, 2)
        h_l3 = QHBoxLayout(); h_l3.addWidget(self.cmb_h3_layer); h_l3.addWidget(self.btn_h3_color)
        grid_holes.addLayout(h_l3, 3, 3)
        
        # Bottom check
        self.chk_convert_dots = QCheckBox("转为点图元")
        grid_holes.addWidget(self.chk_convert_dots, 4, 1, 1, 3)

        right_layout.addWidget(gb_holes)
        right_layout.addStretch()
        
        # Add columns to content layout
        content_layout.addLayout(left_layout)
        content_layout.addLayout(right_layout)
        main_layout.addLayout(content_layout)
        
        # Bottom Button Box
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        buttons_layout.addWidget(self.btn_ok)
        buttons_layout.addWidget(self.btn_cancel)
        
        main_layout.addLayout(buttons_layout)
        
        # Initialize Logic
        self.connect_signals()
        # gb_holes is checkable: enable/disable its children when toggled
        def _toggle_holes_children(checked):
            widgets = [
                self.txt_h1_min, self.txt_h1_max, self.cmb_h1_layer, self.btn_h1_color,
                self.chk_h2, self.txt_h2_min, self.txt_h2_max, self.cmb_h2_layer, self.btn_h2_color,
                self.chk_h3, self.txt_h3_min, self.txt_h3_max, self.cmb_h3_layer, self.btn_h3_color,
                self.chk_convert_dots
            ]
            for w in widgets:
                w.setEnabled(checked)

        gb_holes.toggled.connect(_toggle_holes_children)
        _toggle_holes_children(gb_holes.isChecked())
        
    def create_entry(self, label_text, widget, suffix="mm"):
        l = QHBoxLayout()
        if label_text:
            l.addWidget(QLabel(label_text))
        l.addWidget(widget)
        if suffix:
            l.addWidget(QLabel(suffix))
        l.addStretch()
        return l

    def create_icon_placeholder(self, text, w=60, h=40):
        lbl = QLabel(text)
        lbl.setFrameShape(QFrame.Box)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedSize(w, h)
        lbl.setStyleSheet("background-color: #f0f0f0; border: 1px solid #999;")
        return lbl

    def connect_signals(self):
        # 1. Cut params enable/disable
        self._toggle(self.chk_cut_line, [self.txt_hmin1, self.txt_hmax1])
        self._toggle(self.chk_cut_t, [self.txt_l2, self.txt_h2])
        self._toggle(self.chk_cut_v, [self.txt_lmin3, self.txt_lmax3, self.txt_amin3, self.txt_amax3])
        
        # 2. Cut Processing
        self.rb_merge_outline.toggled.connect(self.on_merge_outline_toggled)
        self.chk_mod_cut_size.toggled.connect(self.txt_mod_cut_size.setEnabled)
        self.on_merge_outline_toggled(self.rb_merge_outline.isChecked()) # Init
        
        # 4. Label Recognition
        self.chk_label_enable.toggled.connect(self.label_content_widget.setEnabled)
        self.label_content_widget.setEnabled(self.chk_label_enable.isChecked())
        # label-related combos are enabled only when label recognition is enabled (already handled by widget)
        # allow toggling of color combo by radio selection
        self.rb_color_diff.toggled.connect(self.cmb_color_layer.setEnabled)
        self._toggle(self.chk_inner_layer_enable, [self.cmb_inner_layer])
        
        # 5. Holes
        self._toggle(self.chk_h2, [self.txt_h2_min, self.txt_h2_max, self.cmb_h2_layer, self.btn_h2_color])
        self._toggle(self.chk_h3, [self.txt_h3_min, self.txt_h3_max, self.cmb_h3_layer, self.btn_h3_color])
        
    def _toggle(self, checkbox, widgets):
        def handler(checked):
             for w in widgets:
                 w.setEnabled(checked)
        checkbox.toggled.connect(handler)
        handler(checkbox.isChecked())
        
    def on_merge_outline_toggled(self, checked):
        self.chk_mod_cut_size.setEnabled(checked)
        self.txt_mod_cut_size.setEnabled(checked and self.chk_mod_cut_size.isChecked())

