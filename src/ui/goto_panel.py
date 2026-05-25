from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QGroupBox, QLineEdit, QListWidget,
    QListWidgetItem, QTabWidget, QProgressBar, QDoubleSpinBox,
)


class GotoPanel(QWidget):
    def __init__(self, app, mount, catalog):
        super().__init__()
        self.app = app
        self.mount = mount
        self.catalog = catalog
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(self._build_manual_entry())
        layout.addWidget(self._build_catalog_browser())
        layout.addWidget(self._build_goto_button())

    def _build_manual_entry(self):
        group = QGroupBox("Manual Coordinates")
        grid = QGridLayout(group)
        grid.setSpacing(6)

        grid.addWidget(QLabel("RA (hours):"), 0, 0)
        self.ra_input = QDoubleSpinBox()
        self.ra_input.setRange(0, 24)
        self.ra_input.setDecimals(4)
        self.ra_input.setSingleStep(0.1)
        self.ra_input.setValue(0)
        self.ra_input.setMinimumHeight(50)
        self.ra_input.setStyleSheet("font-size: 16px;")
        grid.addWidget(self.ra_input, 0, 1)

        grid.addWidget(QLabel("DEC (°):"), 1, 0)
        self.dec_input = QDoubleSpinBox()
        self.dec_input.setRange(-90, 90)
        self.dec_input.setDecimals(3)
        self.dec_input.setSingleStep(1)
        self.dec_input.setValue(0)
        self.dec_input.setMinimumHeight(50)
        self.dec_input.setStyleSheet("font-size: 16px;")
        grid.addWidget(self.dec_input, 1, 1)

        return group

    def _build_catalog_browser(self):
        group = QGroupBox("Object Catalog")
        layout = QVBoxLayout(group)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search object...")
        self.search_input.setMinimumHeight(45)
        self.search_input.setStyleSheet("font-size: 14px;")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        self.object_list = QListWidget()
        self.object_list.setMinimumHeight(200)
        self.object_list.setStyleSheet("font-size: 13px;")
        self._populate_list()

        layout.addLayout(search_layout)
        layout.addWidget(self.object_list)
        return group

    def _build_goto_button(self):
        btn = QPushButton("▶ GOTO")
        btn.setMinimumHeight(70)
        btn.setStyleSheet("""
            QPushButton {
                font-size: 20px; font-weight: bold;
                border-radius: 8px;
                background-color: #2980b9; color: white;
            }
            QPushButton:pressed { background-color: #3498db; }
        """)
        btn.clicked.connect(self._on_goto)
        return btn

    def _populate_list(self, query: str = ""):
        self.object_list.clear()
        if query:
            objects = self.catalog.search(query)
        else:
            objects = self.catalog.get_all()
        for obj in objects[:200]:
            item = QListWidgetItem(
                f"{obj.name}  ({obj.constellation})  mag={obj.magnitude:.1f}"
            )
            item.setData(Qt.ItemDataRole.UserRole, obj)
            self.object_list.addItem(item)

    def _on_search(self, text: str):
        self._populate_list(text)

    def _on_goto(self):
        selected = self.object_list.currentItem()
        if selected:
            obj = selected.data(Qt.ItemDataRole.UserRole)
            ra, dec = obj.ra_hours, obj.dec_deg
        else:
            ra = self.ra_input.value()
            dec = self.dec_input.value()

        if self.app.confirm("GOTO", f"Slew to RA={ra:.4f} DEC={dec:.3f}?"):
            self.app.status_timer.stop()
            try:
                self.mount.slew_to(ra, dec, wait=False)
            finally:
                self.app.status_timer.start()
