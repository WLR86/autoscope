from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QGroupBox, QListWidget, QListWidgetItem,
    QProgressBar, QRadioButton, QButtonGroup, QTextEdit,
    QFrame, QSizePolicy,
)


class AlignmentPanel(QWidget):
    def __init__(self, app, mount, align, guider, imager, solver):
        super().__init__()
        self.app = app
        self.mount = mount
        self.align = align
        self.guider = guider
        self.imager = imager
        self.solver = solver
        self._build_ui()
        self._setup_callbacks()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(self._build_method_selector())
        layout.addWidget(self._build_star_list())
        layout.addWidget(self._build_progress())
        layout.addWidget(self._build_control_buttons())

    def _build_method_selector(self):
        group = QGroupBox("Alignment Method")
        layout = QHBoxLayout(group)

        self.method_group = QButtonGroup(self)
        methods = [
            ("1-Star", 0),
            ("2-Star", 1),
            ("3-Star", 2),
            ("Plate Solve", 3),
        ]
        for label, idx in methods:
            rb = QRadioButton(label)
            rb.setMinimumHeight(45)
            rb.setStyleSheet("font-size: 14px;")
            self.method_group.addButton(rb, idx)
            layout.addWidget(rb)
            if idx == 0:
                rb.setChecked(True)

        return group

    def _build_star_list(self):
        group = QGroupBox("Available Alignment Stars")
        layout = QVBoxLayout(group)

        self.star_list = QListWidget()
        self.star_list.setMinimumHeight(180)
        self.star_list.setStyleSheet("font-size: 13px;")

        refresh_btn = QPushButton("Refresh Stars")
        refresh_btn.setMinimumHeight(40)
        refresh_btn.clicked.connect(self._refresh_stars)

        layout.addWidget(self.star_list)
        layout.addWidget(refresh_btn)
        return group

    def _build_progress(self):
        group = QGroupBox("Progress")
        layout = QVBoxLayout(group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setStyleSheet("font-size: 13px;")

        self.status_text = QLabel("Ready")
        self.status_text.setStyleSheet("font-size: 13px;")

        self.align_log = QTextEdit()
        self.align_log.setReadOnly(True)
        self.align_log.setMaximumHeight(100)
        self.align_log.setStyleSheet("font-size: 12px;")

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_text)
        layout.addWidget(self.align_log)
        return group

    def _build_control_buttons(self):
        layout = QHBoxLayout()

        self.btn_start = QPushButton("▶ Start Alignment")
        self.btn_start.setMinimumHeight(60)
        self.btn_start.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: bold;
                border-radius: 8px;
                background-color: #27ae60; color: white;
            }
            QPushButton:pressed { background-color: #2ecc71; }
        """)
        self.btn_start.clicked.connect(self._start_alignment)

        self.btn_sync = QPushButton("Sync")
        self.btn_sync.setMinimumHeight(60)
        self.btn_sync.setStyleSheet("font-size: 14px;")
        self.btn_sync.clicked.connect(self._on_sync)

        self.btn_ps_align = QPushButton("Plate Solve & Align")
        self.btn_ps_align.setMinimumHeight(60)
        self.btn_ps_align.setStyleSheet("font-size: 14px;")
        self.btn_ps_align.clicked.connect(self._plate_solve_align)

        self.btn_reset = QPushButton("Reset Model")
        self.btn_reset.setMinimumHeight(60)
        self.btn_reset.setStyleSheet("font-size: 14px;")
        self.btn_reset.clicked.connect(self._reset_model)

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_sync)
        layout.addWidget(self.btn_ps_align)
        layout.addWidget(self.btn_reset)
        return layout

    def _setup_callbacks(self):
        self.align.on_progress(self._on_progress)

    def _on_progress(self, msg: str, pct: float):
        self.status_text.setText(msg)
        self.progress_bar.setValue(int(pct))
        self.align_log.append(msg)

    def _refresh_stars(self):
        self.star_list.clear()
        cfg = self.app.config.get("site", {})
        lst = self.app.status.labels["lst"]
        lat = cfg.get("latitude", 48.86)
        lon = cfg.get("longitude", 2.35)
        stars = self.align.get_visible_stars(lat, lon, 0)
        for s in stars:
            item = QListWidgetItem(f"{s.name}  ({s.constellation})  mag={s.magnitude:.1f}")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.star_list.addItem(item)

    def _start_alignment(self):
        method_id = self.method_group.checkedId()
        from src.alignment import AlignmentMethod
        methods = [
            AlignmentMethod.ONE_STAR,
            AlignmentMethod.TWO_STAR,
            AlignmentMethod.THREE_STAR,
            AlignmentMethod.PLATE_SOLVE,
        ]
        method = methods[method_id] if method_id < len(methods) else AlignmentMethod.ONE_STAR

        if method == AlignmentMethod.PLATE_SOLVE:
            self.btn_start.setEnabled(False)
            try:
                self.align.run_align_sequence([], method)
            finally:
                self.btn_start.setEnabled(True)
            return

        stars = []
        for i in range(self.star_list.count()):
            item = self.star_list.item(i)
            stars.append(item.data(Qt.ItemDataRole.UserRole))

        selected = []
        for item in self.star_list.selectedItems():
            selected.append(item.data(Qt.ItemDataRole.UserRole))

        if not selected:
            selected = stars[:3]

        if not selected:
            self.status_text.setText("No stars available")
            return

        self.btn_start.setEnabled(False)
        try:
            self.align.run_align_sequence(selected, method)
        finally:
            self.btn_start.setEnabled(True)

    def _on_sync(self):
        ra = self.mount.current_ra
        dec = self.mount.current_dec
        if self.app.confirm("Sync", f"Sync to current RA={ra:.4f} DEC={dec:.3f}?"):
            self.mount.sync(ra, dec)
            self.align_log.append(f"Synced to RA={ra:.4f} DEC={dec:.3f}")

    def _plate_solve_align(self):
        self.btn_ps_align.setEnabled(False)
        try:
            self.align.run_align_sequence([], AlignmentMethod.PLATE_SOLVE)
        finally:
            self.btn_ps_align.setEnabled(True)

    def _reset_model(self):
        if self.app.confirm("Reset", "Reset alignment model?"):
            self.align.model.reset()
            self.align_log.append("Alignment model reset")
            self.status_text.setText("Ready")
            self.progress_bar.setValue(0)
