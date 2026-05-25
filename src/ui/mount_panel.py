from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QGroupBox,
)


class MountPanel(QWidget):
    def __init__(self, app, mount):
        super().__init__()
        self.app = app
        self.mount = mount
        self._build_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(250)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        layout.addWidget(self._build_direction_pad(), stretch=3)
        layout.addWidget(self._build_speed_grid(), stretch=2)
        layout.addWidget(self._build_tracking_controls(), stretch=1)

    def _build_direction_pad(self):
        group = QGroupBox("Direction")
        grid = QGridLayout(group)
        grid.setSpacing(4)

        btn_style = """
            QPushButton {
                font-size: 24px; font-weight: bold;
                min-width: 90px; min-height: 90px;
                border-radius: 8px;
            }
        """

        btn_n = QPushButton("N ▲")
        btn_n.setStyleSheet(btn_style)
        btn_n.pressed.connect(lambda: self.mount.start_motion("n"))
        btn_n.released.connect(lambda: self.mount.stop_motion("n"))

        btn_s = QPushButton("S ▼")
        btn_s.setStyleSheet(btn_style)
        btn_s.pressed.connect(lambda: self.mount.start_motion("s"))
        btn_s.released.connect(lambda: self.mount.stop_motion("s"))

        btn_e = QPushButton("E ▶")
        btn_e.setStyleSheet(btn_style)
        btn_e.pressed.connect(lambda: self.mount.start_motion("e"))
        btn_e.released.connect(lambda: self.mount.stop_motion("e"))

        btn_w = QPushButton("◀ W")
        btn_w.setStyleSheet(btn_style)
        btn_w.pressed.connect(lambda: self.mount.start_motion("w"))
        btn_w.released.connect(lambda: self.mount.stop_motion("w"))

        stop = QPushButton("STOP ■")
        stop.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: bold;
                min-width: 90px; min-height: 90px;
                border-radius: 8px;
                background-color: #c0392b; color: white;
            }
            QPushButton:pressed { background-color: #e74c3c; }
        """)
        stop.clicked.connect(self.mount.stop_all_motion)

        grid.addWidget(btn_n, 0, 1)
        grid.addWidget(btn_w, 1, 0)
        grid.addWidget(stop, 1, 1)
        grid.addWidget(btn_e, 1, 2)
        grid.addWidget(btn_s, 2, 1)

        return group

    def _build_speed_grid(self):
        group = QGroupBox("Slew Speed")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        self.speed_buttons = []
        speed_labels = ["1\n0.5x", "2\n1x", "3\n2x", "4\n4x", "5\n8x",
                        "6\n16x", "7\n32x", "8\n64x", "9\n800x"]

        grid = QGridLayout()
        grid.setSpacing(4)

        for i in range(9):
            btn = QPushButton(speed_labels[i])
            btn.setMinimumHeight(55)
            rate = i + 1
            btn.clicked.connect(lambda checked, r=rate: self.mount.set_slew_rate(r))
            self.speed_buttons.append(btn)
            row, col = i // 5, i % 5
            if col >= 3:
                col = col + 1
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        self.speed_label = QLabel("Speed: 5 (8x)")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_label.setStyleSheet("font-size: 15px; font-weight: bold; padding: 4px;")
        layout.addWidget(self.speed_label)

        return group

    def _build_tracking_controls(self):
        group = QGroupBox("Tracking")
        layout = QHBoxLayout(group)
        layout.setSpacing(8)

        self.track_btn = QPushButton("Stellar")
        self.track_btn.setMinimumHeight(55)
        self.track_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; }
        """)
        self.track_btn.clicked.connect(self._cycle_tracking)

        self.track_status = QLabel("●")
        self.track_status.setStyleSheet("font-size: 22px;")
        self.track_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        park_btn = QPushButton("Park")
        park_btn.setMinimumHeight(55)
        park_btn.setStyleSheet("font-size: 13px;")
        park_btn.clicked.connect(self.mount.park)

        unpark_btn = QPushButton("Unpark")
        unpark_btn.setMinimumHeight(55)
        unpark_btn.setStyleSheet("font-size: 13px;")
        unpark_btn.clicked.connect(self.mount.unpark)

        layout.addWidget(self.track_status)
        layout.addWidget(self.track_btn, 1)
        layout.addWidget(park_btn)
        layout.addWidget(unpark_btn)
        return group

    def _cycle_tracking(self):
        mode = self.mount.cycle_tracking_mode()
        self._update_track_display()

    def _update_track_display(self):
        mode = self.mount.track_mode
        if mode.value == "off":
            self.track_btn.setText("Off")
            self.track_btn.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #e74c3c; }")
            self.track_status.setText("○")
            self.track_status.setStyleSheet("font-size: 22px; color: #e74c3c;")
        elif mode.value == "stellar":
            self.track_btn.setText("Stellar ★")
            self.track_btn.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #f1c40f; }")
            self.track_status.setText("★")
            self.track_status.setStyleSheet("font-size: 22px; color: #f1c40f;")
        elif mode.value == "solar":
            self.track_btn.setText("Solar ☀")
            self.track_btn.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #e67e22; }")
            self.track_status.setText("☀")
            self.track_status.setStyleSheet("font-size: 22px; color: #e67e22;")
        elif mode.value == "lunar":
            self.track_btn.setText("Lunar ☽")
            self.track_btn.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #95a5a6; }")
            self.track_status.setText("☽")
            self.track_status.setStyleSheet("font-size: 22px; color: #95a5a6;")

    def _refresh(self):
        idx = self.mount.speed_index
        for i, btn in enumerate(self.speed_buttons):
            if i + 1 == idx:
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 11px; font-weight: bold;
                        background-color: #2980b9; color: white;
                        border: 2px solid #3498db;
                        border-radius: 6px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 11px;
                        background-color: #3a3a3a; color: #ccc;
                        border: 1px solid #555;
                        border-radius: 6px;
                    }
                """)
        from src.mount_controller import SYNSCAN_SPEEDS
        label = SYNSCAN_SPEEDS[idx - 1][1] if 1 <= idx <= 9 else ""
        self.speed_label.setText(f"Speed {idx}: {label}")
        self._update_track_display()
