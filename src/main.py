#!/usr/bin/env python3
import sys
import os
import time
import json
import signal
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/telescope_controller.log"),
    ],
)
logger = logging.getLogger("main")


def setup_indiserver(config: dict) -> subprocess.Popen:
    indi_cfg = config.get("indi", {})
    drivers = indi_cfg.get("drivers", {})
    driver_list = []

    mount_driver = drivers.get("mount", "indi_eqmod_telescope")
    camera_driver = drivers.get("camera", "indi_asi_ccd")

    driver_list.extend(["-d", mount_driver, "-d", camera_driver])

    cmd = ["indiserver", "-v"] + driver_list
    logger.info(f"Starting INDI server: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        time.sleep(3)
        return proc
    except FileNotFoundError:
        logger.error("indiserver not found. Install INDI first.")
        return None


def setup_astap(config: dict):
    ps_cfg = config.get("plate_solving", {})
    method = ps_cfg.get("method", "astap")
    if method == "astap":
        binary = ps_cfg.get("astap_binary", "/usr/bin/astap")
        if os.path.exists(binary):
            logger.info(f"ASTAP found at {binary}")
        else:
            logger.warning(f"ASTAP not found at {binary}. "
                           f"Plate solving will be unavailable.")


def main():
    logger.info("=== Telescope Handcontroller Replacement ===")

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "telescope_config.json"
    )
    with open(config_path) as f:
        config = json.load(f)

    site = config.get("site", {})
    logger.info(f"Site: lat={site.get('latitude')}, lon={site.get('longitude')}")

    setup_astap(config)

    indi_proc = None
    if config.get("indi", {}).get("auto_start_server", True):
        indi_proc = setup_indiserver(config)

    from src.indi_client import INDIClient
    from src.mount_controller import MountController
    from src.camera_controller import CameraController
    from src.plate_solver import PlateSolver
    from src.alignment import AlignmentModel, AlignmentController
    from src.catalog import Catalog
    from src.joystick_controller import JoystickController

    ic = INDIClient(
        host=config.get("indi", {}).get("server_host", "localhost"),
        port=config.get("indi", {}).get("server_port", 7624),
    )

    if not ic.connect_server():
        logger.error("Failed to connect to INDI server")
        if indi_proc:
            indi_proc.terminate()
        sys.exit(1)

    mount = MountController(ic, "EQMOD Mount")
    guider = CameraController(ic, "ZWO ASI120MC", "Guider")
    imager = CameraController(ic, "ZWO ASI715MC", "Imager")

    if not mount.connect():
        logger.error("Failed to connect mount")
    else:
        logger.info("Mount connected")

    for cam_name, cam in [("Guider", guider), ("Imager", imager)]:
        if cam.connect():
            logger.info(f"{cam_name} camera connected")
        else:
            logger.warning(f"{cam_name} camera not available (retry later)")

    plate_solver = PlateSolver(config.get("plate_solving", {}))
    alignment_model = AlignmentModel(config.get("alignment", {}))
    catalog = Catalog(config.get("catalogs", {}))
    align_ctrl = AlignmentController(mount, guider, imager, plate_solver, alignment_model)

    joystick = JoystickController(config.get("joystick", {}))

    from src.ui.main_window import TelescopeApp
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    theme = config.get("ui", {}).get("theme", "dark")
    if theme == "dark":
        from PyQt5.QtGui import QPalette, QColor
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(41, 128, 185))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)

    window = TelescopeApp(ic, mount, guider, imager, align_ctrl,
                          plate_solver, catalog, config, joystick=joystick)
    window.show()

    def shutdown():
        logger.info("Shutting down...")
        if joystick:
            joystick.stop()
        mount.stop_all_motion()
        mount.set_tracking(False)
        if indi_proc:
            indi_proc.terminate()
        ic.disconnect_server()

    signal.signal(signal.SIGINT, lambda s, f: (shutdown(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda s, f: (shutdown(), sys.exit(0)))

    try:
        ret = app.exec_()
    finally:
        shutdown()
    sys.exit(ret)


if __name__ == "__main__":
    main()
