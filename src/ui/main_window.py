import sys
import math
import time
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QPainter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QGridLayout, QFrame,
    QTabWidget, QListWidget, QListWidgetItem, QMessageBox,
    QLineEdit, QGroupBox, QSlider, QComboBox, QScrollArea,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar, QCheckBox,
    QRadioButton, QButtonGroup, QProgressBar, QTextEdit,
)

logger = logging.getLogger(__name__)


class TelescopeApp(QMainWindow):
    def __init__(self, indi_client, mount, guider, imager,
                 alignment_controller, plate_solver, catalog, config,
                 joystick=None):
        super().__init__()
        self.ic = indi_client
        self.mount = mount
        self.guider = guider
        self.imager = imager
        self.align = alignment_controller
        self.solver = plate_solver
        self.catalog = catalog
        self.config = config
        self.joystick = joystick

        self._init_ui()
        self._setup_timers()
        self._setup_callbacks()
        self._setup_joystick()

    def _init_ui(self):
        self.setWindowTitle("Telescope Controller")
        ui_cfg = self.config.get("ui", {})
        theme = ui_cfg.get("theme", "dark")

        if ui_cfg.get("fullscreen", True):
            self.showFullScreen()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(4, 4, 4, 4)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.tabs)

        self.status = StatusBar(self, config=self.config)
        main_layout.addWidget(self.status)
        main_layout.setStretch(0, 1)

        from .mount_panel import MountPanel
        from .goto_panel import GotoPanel
        from .alignment_panel import AlignmentPanel
        from .camera_panel import CameraPanel

        self.mount_panel = MountPanel(self, self.mount)
        self.goto_panel = GotoPanel(self, self.mount, self.catalog)
        self.align_panel = AlignmentPanel(self, self.mount, self.align,
                                          self.guider, self.imager, self.solver)
        self.camera_panel = CameraPanel(self, self.guider, self.imager)

        self.tabs.addTab(self.mount_panel, "Mount")
        self.tabs.addTab(self.goto_panel, "GOTO")
        self.tabs.addTab(self.align_panel, "Align")
        self.tabs.addTab(self.camera_panel, "Camera")

    def _setup_timers(self):
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        status_ms = self.config.get("ui", {}).get("status_refresh_ms", 500)
        self.status_timer.start(status_ms)

    def _setup_callbacks(self):
        self.mount.on_state_change(lambda s: None)

    def _setup_joystick(self):
        if not self.joystick:
            return
        if not self.joystick.start():
            self.status.joystick_label.setText("No JS")
            return
        self.status.joystick_label.setText("JS: OK")

        def on_joy_action(action, value):
            from src.joystick_controller import JoystickAction
            if action == JoystickAction.MOVE_N:
                self.mount.start_motion("n")
            elif action == JoystickAction.MOVE_S:
                self.mount.start_motion("s")
            elif action == JoystickAction.MOVE_E:
                self.mount.start_motion("e")
            elif action == JoystickAction.MOVE_W:
                self.mount.start_motion("w")
            elif action == JoystickAction.STOP_ALL:
                self.mount.stop_all_motion()
            elif action == JoystickAction.SPEED_UP:
                self.mount.speed_up()
            elif action == JoystickAction.SPEED_DOWN:
                self.mount.speed_down()
            elif action == JoystickAction.TRACK_CYCLE:
                self.mount.cycle_tracking_mode()
            elif action == JoystickAction.HOME:
                self.mount.home()

        self.joystick.on_action(on_joy_action)

    def _update_status(self):
        st = self.mount.get_status()
        self.status.update(
            ra=st["ra"], dec=st["dec"],
            alt=st["alt"], az=st["az"],
            tracking=st["tracking"],
            track_mode=st.get("track_mode", ""),
            speed=st.get("speed", 5),
            speed_label=st.get("speed_label", ""),
            state=st["state"],
        )

    def show_message(self, title: str, msg: str):
        QMessageBox.information(self, title, msg)

    def confirm(self, title: str, msg: str) -> bool:
        r = QMessageBox.question(self, title, msg,
                                 QMessageBox.StandardButton.Yes |
                                 QMessageBox.StandardButton.No)
        return r == QMessageBox.StandardButton.Yes

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        super().keyPressEvent(event)


class StatusBar(QWidget):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self.config = config or {}

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        font = QFont("monospace", 11)
        bold_font = QFont("monospace", 11)
        bold_font.setBold(True)

        self.labels = {}
        fields = [
            ("lst", "LST"),
            ("ra", "RA"),
            ("dec", "DEC"),
            ("alt", "Alt"),
            ("az", "Az"),
        ]
        for key, label in fields:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFont(font)
            val = QLabel("---")
            val.setFont(font)
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            layout.addLayout(row)
            self.labels[key] = val

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #555;")
        layout.addWidget(sep)

        row = QHBoxLayout()
        self.labels["speed"] = QLabel("Spd: 5")
        self.labels["speed"].setFont(bold_font)
        row.addWidget(self.labels["speed"])
        self.labels["track"] = QLabel("Track: Stellar")
        self.labels["track"].setFont(font)
        row.addWidget(self.labels["track"])
        layout.addLayout(row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #555;")
        layout.addWidget(sep2)

        row2 = QHBoxLayout()
        self.labels["state"] = QLabel("IDLE")
        self.labels["state"].setFont(bold_font)
        row2.addWidget(self.labels["state"])
        self.joystick_label = QLabel("")
        self.joystick_label.setFont(QFont("monospace", 9))
        row2.addWidget(self.joystick_label, 1, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row2)

        layout.addStretch()

    def update(self, ra=0, dec=0, alt=0, az=0, tracking=False,
               track_mode="", speed=5, speed_label="", state=""):
        self.labels["lst"].setText(f"{0:.2f}h")
        self.labels["ra"].setText(self._fmt_ra(ra))
        self.labels["dec"].setText(self._fmt_dec(dec))
        self.labels["alt"].setText(f"{alt:.1f}°")
        self.labels["az"].setText(f"{az:.1f}°")
        self.labels["speed"].setText(f"Spd: {speed} ({speed_label})" if speed_label else f"Spd: {speed}")
        self.labels["track"].setText(f"Track: {track_mode.capitalize() if track_mode else 'Off'}")
        self.labels["state"].setText(state.upper() if state else "---")

    def _fmt_ra(self, ra: float) -> str:
        h = int(ra)
        m = int((ra - h) * 60)
        s = ((ra - h) * 60 - m) * 60
        return f"{h:02d}h{m:02d}m{s:04.1f}s"

    def _fmt_dec(self, dec: float) -> str:
        sign = "+" if dec >= 0 else "-"
        d = abs(int(dec))
        m = int((abs(dec) - d) * 60)
        return f"{sign}{d:02d}°{m:02d}'"
