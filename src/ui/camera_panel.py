from PyQt5.QtCore import Qt, QTimer, QByteArray
from PyQt5.QtGui import QPixmap, QFont, QImage
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QGroupBox, QSlider, QDoubleSpinBox, QTabWidget,
    QFrame, QSizePolicy,
)


class CameraPanel(QWidget):
    def __init__(self, app, guider, imager):
        super().__init__()
        self.app = app
        self.guider = guider
        self.imager = imager
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.cam_tabs = QTabWidget()
        self.cam_tabs.addTab(self._build_camera_tab("Guider", self.guider), "Guider")
        self.cam_tabs.addTab(self._build_camera_tab("Imager", self.imager), "Imager")

        layout.addWidget(self.cam_tabs)

    def _build_camera_tab(self, name: str, cam):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)

        controls = QGroupBox("Controls")
        cgrid = QGridLayout(controls)
        cgrid.setSpacing(6)

        cgrid.addWidget(QLabel("Exposure (s):"), 0, 0)
        exp_spin = QDoubleSpinBox()
        exp_spin.setRange(0.001, 3600)
        exp_spin.setValue(3.0)
        exp_spin.setDecimals(3)
        exp_spin.setMinimumHeight(45)
        exp_spin.setStyleSheet("font-size: 14px;")
        cgrid.addWidget(exp_spin, 0, 1)

        cgrid.addWidget(QLabel("Gain:"), 1, 0)
        gain_slider = QSlider(Qt.Orientation.Horizontal)
        gain_slider.setRange(0, 100)
        gain_slider.setValue(50)
        gain_slider.setMinimumHeight(40)
        cgrid.addWidget(gain_slider, 1, 1)
        gain_label = QLabel("50")
        gain_label.setStyleSheet("font-size: 13px;")
        cgrid.addWidget(gain_label, 1, 2)

        gain_slider.valueChanged.connect(
            lambda v: (gain_label.setText(str(v)), cam.set_gain(v))
        )

        btn_expose = QPushButton("📷 Capture")
        btn_expose.setMinimumHeight(55)
        btn_expose.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: bold;
                border-radius: 6px;
                background-color: #8e44ad; color: white;
            }
            QPushButton:pressed { background-color: #9b59b6; }
        """)
        btn_expose.clicked.connect(lambda: cam.expose(exp_spin.value()))

        layout.addWidget(controls)
        layout.addWidget(btn_expose)

        preview_group = QGroupBox("Preview")
        prev_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("No image")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(320, 240)
        self.preview_label.setStyleSheet("background-color: #1a1a2e; font-size: 14px;")
        prev_layout.addWidget(self.preview_label)

        layout.addWidget(preview_group, 1)

        def on_image(data):
            if len(data) < 100:
                return
            try:
                import numpy as np
                if data[:4] == b'\x89HDF':  # rough check, not FITS
                    pass
                from astropy.io import fits
                import io
                hdul = fits.open(io.BytesIO(data))
                img_data = hdul[0].data
                hdul.close()
                if img_data is not None and img_data.size > 0:
                    img = img_data.astype(np.float32)
                    if img.ndim == 2:
                        pmin, pmax = img.min(), img.max()
                        if pmax > pmin:
                            img = (img - pmin) / (pmax - pmin) * 255
                        img = img.astype(np.uint8)
                        h, w = img.shape
                        qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
                        pix = QPixmap.fromImage(qimg)
                        self.preview_label.setPixmap(
                            pix.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                        )
            except Exception as e:
                self.preview_label.setText(f"Preview error: {e}")

        cam.on_image(on_image)

        return widget
