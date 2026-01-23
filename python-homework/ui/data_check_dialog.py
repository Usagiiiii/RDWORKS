from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QPushButton, QLineEdit, QFrame, 
                             QTextEdit, QWidget, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QTransform
import math
from ui.graphics_items import EditablePathItem
from utils.geom import is_path_self_intersecting, segments_intersect, bbox_of

class DataCheckDialog(QDialog):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowTitle("数据检查")
        self.setFixedSize(600, 320)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # --- Left Side ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        # 1. Closure Check Frame
        self.frame_closure = self.create_frame()
        f_layout = QVBoxLayout(self.frame_closure)
        f_layout.setContentsMargins(5, 5, 5, 5)
        f_layout.setSpacing(5)
        
        self.chk_closure = QCheckBox("封闭性检查")
        self.chk_closure.setChecked(True)
        # Bold font for header checkboxes?
        font = self.chk_closure.font()
        # font.setBold(True)
        # self.chk_closure.setFont(font)
        f_layout.addWidget(self.chk_closure)
        
        self.line_closure = QFrame()
        self.line_closure.setFrameShape(QFrame.HLine)
        self.line_closure.setFrameShadow(QFrame.Sunken)
        f_layout.addWidget(self.line_closure)
        
        h_closure = QHBoxLayout()
        h_closure.setContentsMargins(15, 0, 0, 0) # Indent
        self.chk_auto_close = QCheckBox("自动闭合")
        self.chk_auto_close.setChecked(True)
        h_closure.addWidget(self.chk_auto_close)
        h_closure.addStretch()
        h_closure.addWidget(QLabel("闭合容差(mm):"))
        self.txt_closure_tol = QLineEdit("0.01")
        self.txt_closure_tol.setFixedWidth(50)
        h_closure.addWidget(self.txt_closure_tol)
        f_layout.addLayout(h_closure)
        left_layout.addWidget(self.frame_closure)
        
        # 2. Self Intersection
        self.frame_self_cross = self.create_frame()
        f_layout2 = QVBoxLayout(self.frame_self_cross)
        f_layout2.setContentsMargins(5, 5, 5, 5)
        self.chk_self_cross = QCheckBox("自相交检查")
        self.chk_self_cross.setChecked(True)
        f_layout2.addWidget(self.chk_self_cross)
        left_layout.addWidget(self.frame_self_cross)
        
        # 3. Intersection
        self.frame_cross = self.create_frame()
        f_layout3 = QVBoxLayout(self.frame_cross)
        f_layout3.setContentsMargins(5, 5, 5, 5)
        self.chk_cross = QCheckBox("相交检查")
        self.chk_cross.setChecked(True)
        f_layout3.addWidget(self.chk_cross)
        left_layout.addWidget(self.frame_cross)
        
        # 4. Overlap
        self.frame_overlap = self.create_frame()
        f_layout4 = QVBoxLayout(self.frame_overlap)
        f_layout4.setContentsMargins(5, 5, 5, 5)
        f_layout4.setSpacing(5)
        self.chk_overlap = QCheckBox("数据重叠检查")
        self.chk_overlap.setChecked(True)
        f_layout4.addWidget(self.chk_overlap)
        
        self.line_overlap = QFrame()
        self.line_overlap.setFrameShape(QFrame.HLine)
        self.line_overlap.setFrameShadow(QFrame.Sunken)
        f_layout4.addWidget(self.line_overlap)
        
        h_overlap = QHBoxLayout()
        h_overlap.setContentsMargins(15, 0, 0, 0) # Indent
        self.chk_enable_overlap_tol = QCheckBox("使能重叠容差")
        self.chk_enable_overlap_tol.setChecked(True)
        h_overlap.addWidget(self.chk_enable_overlap_tol)
        h_overlap.addStretch()
        h_overlap.addWidget(QLabel("重叠容差(mm):"))
        self.txt_overlap_tol = QLineEdit("0.01")
        self.txt_overlap_tol.setFixedWidth(50)
        h_overlap.addWidget(self.txt_overlap_tol)
        f_layout4.addLayout(h_overlap)
        left_layout.addWidget(self.frame_overlap)
        
        left_layout.addStretch()
        
        main_layout.addWidget(left_widget, 4) # Ratio 4
        
        # --- Connections for Enabled States ---
        self.chk_auto_close.toggled.connect(self.txt_closure_tol.setEnabled)
        self.chk_enable_overlap_tol.toggled.connect(self.txt_overlap_tol.setEnabled)

        # --- Right Side ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        # Font size looks like 10pt or 9pt
        font = self.txt_result.font()
        font.setPointSize(10)
        self.txt_result.setFont(font)
        right_layout.addWidget(self.txt_result)
        
        self.btn_check = QPushButton("检测")
        self.btn_check.setFixedHeight(30)
        self.btn_check.clicked.connect(self.on_check_clicked)
        right_layout.addWidget(self.btn_check)
        
        main_layout.addWidget(right_widget, 3) # Ratio 3

    def create_frame(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Raised)
        return frame

    def check_closure(self, items):
        tol = 0.01
        try:
            tol = float(self.txt_closure_tol.text())
        except:
            pass
            
        closed_count = 0
        open_count = 0
        
        do_auto_close = self.chk_auto_close.isChecked()
        
        for item in items:
            if isinstance(item, EditablePathItem):
                pts = item.points()
                if len(pts) < 2: continue
                
                start_pt = pts[0]
                end_pt = pts[-1]
                dist = math.hypot(start_pt[0]-end_pt[0], start_pt[1]-end_pt[1])
                
                # 逻辑修改：
                # 1. 只有当距离 > 容差时，才视为“不闭合”问题进行报告。
                # 2. 如果开启了自动闭合：
                #    - 距离 <= 容差：执行闭合（吸附）。
                #    - 距离 > 容差：不闭合（保持缺口）。
                
                if dist > 1e-6: # 存在物理缺口
                    if dist > tol:
                        # 大于容差：报告为不闭合，且不进行自动闭合
                        open_count += 1
                    else:
                        # 小于等于容差
                        if do_auto_close:
                            # 修复：吸附闭合（修改最后一个点坐标）
                            new_pts = list(pts)
                            new_pts[-1] = start_pt
                            item.set_points(new_pts)
                            item._update_path()
                            closed_count += 1
                        
        if open_count > 0:
             self.append_text(f"发现不闭合曲线数:{open_count}", False)
        else:
             self.append_text("未发现不闭合曲线", True)
             
        self.append_text(f"已自动闭合曲线数:{closed_count}", True)

    def on_check_clicked(self):
        selected_items = self.canvas.scene.selectedItems()
        if not selected_items:
            # Error Dialog
            msg = QMessageBox(self)
            msg.setWindowTitle("Laser")
            msg.setIcon(QMessageBox.Warning)
            msg.setText("没有选中的待检查曲线!")
            msg.addButton("确定", QMessageBox.AcceptRole)
            msg.exec_()
            return

        self.txt_result.clear()
        
        if self.chk_closure.isChecked():
            self.append_text("封闭性检查结束", True)
            self.check_closure(selected_items)
            
        if self.chk_self_cross.isChecked():
            self.append_text("自相交检查结束", True)
            self.check_self_cross(selected_items)
            
        if self.chk_cross.isChecked():
            self.append_text("相交检查结束", True)
            self.check_cross(selected_items)
            
        if self.chk_overlap.isChecked():
            self.append_text("重叠检查结束", True)
            self.check_overlap(selected_items)

    def check_self_cross(self, items):
        found = False
        for item in items:
            if isinstance(item, EditablePathItem):
                 # Get QPainterPath
                 path = item.path()
                 polys = path.toSubpathPolygons(QTransform())
                 for poly in polys:
                     pts = [(pt.x(), pt.y()) for pt in poly]
                     if is_path_self_intersecting(pts):
                         found = True
                         break
            if found: break
        
        if found:
            self.append_text("发现自相交曲线", False)
        else:
            self.append_text("未发现自相交曲线", True)

    def check_cross(self, items):
        found = False
        # Check intersection between selected items
        # O(N^2) pairwise interaction check
        
        # Prepare point lists to avoid repeated access
        # items_pts = [item.points() for item in items if isinstance(item, EditablePathItem)]
        path_items = [item for item in items if isinstance(item, EditablePathItem)]
        
        for i in range(len(path_items)):
            pts1 = path_items[i].points()
            if len(pts1) < 2: continue
            
            # Pre-calc bounding box for pts1
            bbox1 = bbox_of([pts1])
            if not bbox1: continue
            
            for j in range(i + 1, len(path_items)):
                pts2 = path_items[j].points()
                if len(pts2) < 2: continue
                
                # BBox check first
                bbox2 = bbox_of([pts2])
                if not bbox2: continue
                
                # Check rect intersection: left1 > right2 or right1 < left2 ...
                if (bbox1[0] > bbox2[2] or bbox1[2] < bbox2[0] or 
                    bbox1[1] > bbox2[3] or bbox1[3] < bbox2[1]):
                    continue
                
                # Segment check
                for idx1 in range(len(pts1) - 1):
                    p1, p2 = pts1[idx1], pts1[idx1+1]
                    for idx2 in range(len(pts2) - 1):
                        p3, p4 = pts2[idx2], pts2[idx2+1]
                        if segments_intersect(p1, p2, p3, p4):
                            found = True
                            break
                    if found: break
                if found: break
            if found: break
            
        if found:
            self.append_text("发现相交曲线", False)
        else:
            self.append_text("未发现相交曲线", True)

    def check_overlap(self, items):
        overlap_found = False
        
        # 逻辑修改：
        # 如果勾选了“使能重叠容差”，使用用户输入的容差值。
        # 如果未勾选，则使用极小值 (1e-7)，意味着必须几乎完全重合才算重叠。
        if self.chk_enable_overlap_tol.isChecked():
            try:
                tol = float(self.txt_overlap_tol.text())
            except:
                tol = 0.01
        else:
            tol = 1e-7
        
        path_items = [item for item in items if isinstance(item, EditablePathItem)]
        
        # Check for duplicates or heavy overlap
        for i in range(len(path_items)):
            pts1 = path_items[i].points()
            for j in range(i + 1, len(path_items)):
                pts2 = path_items[j].points()
                
                if len(pts1) != len(pts2):
                    continue
                    
                # Check if all points are within tolerance
                is_duplicate = True
                for k in range(len(pts1)):
                    dist = math.hypot(pts1[k][0]-pts2[k][0], pts1[k][1]-pts2[k][1])
                    if dist > tol:
                        is_duplicate = False
                        break
                
                # Also check reverse direction? (optional, good for user experience)
                if not is_duplicate:
                    is_duplicate = True
                    for k in range(len(pts1)):
                        # pts1[k] vs pts2[n-1-k]
                        dist = math.hypot(pts1[k][0]-pts2[-(k+1)][0], pts1[k][1]-pts2[-(k+1)][1])
                        if dist > tol:
                            is_duplicate = False
                            break

                if is_duplicate:
                    overlap_found = True
                    break
            if overlap_found: break

        if overlap_found:
             self.append_text("发现重叠线条", False)
        else:
             self.append_text("未发现重叠线条", True)

    def append_text(self, text, is_green=False):
        cursor = self.txt_result.textCursor()
        fmt = QTextCharFormat()
        
        # Special case logic based on screenshot behavior
        if text.startswith("未发现"):
            fmt.setForeground(QColor(0, 128, 0)) # Green
        elif text.startswith("已自动"):
            # If count > 0 ("已自动闭合曲线数:1"), screenshot shows RED.
            # If count == 0 ("已自动闭合曲线数:0"), screenshot shows YELLOW/BROWN? Or Green?
            # User provided screenshot "已自动闭合曲线数:1" is RED.
            # Let's parse the number
            try:
                num = int(text.split(":")[-1])
                if num > 0:
                    fmt.setForeground(QColor("red"))
                else:
                    fmt.setForeground(QColor(128, 128, 0)) # Dark Yellow/Brown for 0 count? Or Green?
                    # Let's use Dark Yellow as neutral info for 0 change
            except:
                fmt.setForeground(QColor("black"))
        elif text.endswith("结束"):
            # Headers are Green in screenshot
            fmt.setForeground(QColor(0, 128, 0))
        elif text.startswith("发现"):
            fmt.setForeground(QColor("red"))
        else:
            if is_green:
                fmt.setForeground(QColor(0, 128, 0))
            else:
                fmt.setForeground(QColor("red"))

        cursor.movePosition(cursor.End)
        cursor.insertText(text + "\n", fmt)
        self.txt_result.setTextCursor(cursor)
