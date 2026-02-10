#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QDoubleSpinBox,
    QHBoxLayout,
    QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings


class FilletDialog(QDialog):
    manualRequested = pyqtSignal()
    autoRequested = pyqtSignal()

    _settings_group = "fillet_dialog"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("倒圆角")
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)

        radius_label = QLabel("圆角半径:")
        self.radius_input = QDoubleSpinBox()
        self.radius_input.setRange(0.0, 9999.0)
        self.radius_input.setDecimals(3)
        self.radius_input.setSingleStep(0.5)
        self.radius_input.setValue(5.0)
        self.radius_input.setFixedWidth(90)
        radius_unit = QLabel("mm")

        min_label = QLabel("最小夹角:")
        self.min_angle_input = QDoubleSpinBox()
        self.min_angle_input.setRange(0.0, 180.0)
        self.min_angle_input.setDecimals(1)
        self.min_angle_input.setSingleStep(1.0)
        self.min_angle_input.setValue(0.0)
        self.min_angle_input.setFixedWidth(90)

        max_label = QLabel("最大夹角:")
        self.max_angle_input = QDoubleSpinBox()
        self.max_angle_input.setRange(0.0, 180.0)
        self.max_angle_input.setDecimals(1)
        self.max_angle_input.setSingleStep(1.0)
        self.max_angle_input.setValue(180.0)
        self.max_angle_input.setFixedWidth(90)

        grid.addWidget(radius_label, 0, 0, 1, 1, Qt.AlignRight)
        grid.addWidget(self.radius_input, 0, 1)
        grid.addWidget(radius_unit, 0, 2)

        grid.addWidget(min_label, 1, 0, 1, 1, Qt.AlignRight)
        grid.addWidget(self.min_angle_input, 1, 1, 1, 2)

        grid.addWidget(max_label, 2, 0, 1, 1, Qt.AlignRight)
        grid.addWidget(self.max_angle_input, 2, 1, 1, 2)

        root.addLayout(grid)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)

        self.manual_btn = QPushButton("手动倒圆角")
        self.auto_btn = QPushButton("自动倒圆角")
        self.manual_btn.clicked.connect(self._on_manual)
        self.auto_btn.clicked.connect(self._on_auto)

        buttons.addWidget(self.manual_btn)
        buttons.addWidget(self.auto_btn)
        root.addLayout(buttons)

        self.setFixedWidth(260)

        self._load_settings()
        self.radius_input.valueChanged.connect(self._save_settings)
        self.min_angle_input.valueChanged.connect(self._save_settings)
        self.max_angle_input.valueChanged.connect(self._save_settings)

    def _settings(self):
        return QSettings("RDWORKS", "RDWORKS-python")

    def _load_settings(self):
        settings = self._settings()
        settings.beginGroup(self._settings_group)
        radius = settings.value("radius", 5.0, type=float)
        min_angle = settings.value("min_angle", 0.0, type=float)
        max_angle = settings.value("max_angle", 180.0, type=float)
        settings.endGroup()
        self.radius_input.setValue(radius)
        self.min_angle_input.setValue(min_angle)
        self.max_angle_input.setValue(max_angle)

    def _save_settings(self, *_args):
        settings = self._settings()
        settings.beginGroup(self._settings_group)
        settings.setValue("radius", self.radius_input.value())
        settings.setValue("min_angle", self.min_angle_input.value())
        settings.setValue("max_angle", self.max_angle_input.value())
        settings.endGroup()

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _on_manual(self):
        self.manualRequested.emit()

    def _on_auto(self):
        self.autoRequested.emit()

    def get_values(self):
        return (
            self.radius_input.value(),
            self.min_angle_input.value(),
            self.max_angle_input.value()
        )

    def get_mode(self):
        return None
