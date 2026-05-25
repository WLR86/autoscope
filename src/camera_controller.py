import time
import threading
import logging
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class CameraState(Enum):
    IDLE = "idle"
    EXPOSING = "exposing"
    DOWNLOADING = "downloading"
    ERROR = "error"


class CameraController:
    def __init__(self, client, device_name: str, name: str = "Camera"):
        self.client = client
        self.device_name = device_name
        self.name = name
        self.state = CameraState.IDLE
        self._on_state_change: Optional[Callable] = None
        self._on_image: Optional[Callable] = None
        self._on_exposure_progress: Optional[Callable] = None

    @property
    def dev(self):
        return self.client.get_device(self.device_name)

    def on_state_change(self, callback: Callable):
        self._on_state_change = callback

    def on_image(self, callback: Callable):
        self._on_image = callback

    def on_exposure_progress(self, callback: Callable):
        self._on_exposure_progress = callback

    def _set_state(self, new_state: CameraState):
        old = self.state
        self.state = new_state
        if self._on_state_change and old != new_state:
            self._on_state_change(new_state)

    def connect(self) -> bool:
        if not self.client.wait_for_device(self.device_name, timeout=20):
            logger.error(f"{self.name} device not found")
            return False
        time.sleep(0.5)

        dev = self.dev
        if dev is None:
            return False

        conn = dev.getSwitch("CONNECTION")
        if conn:
            if not conn.findWidget("CONNECT").getSel():
                conn.findWidget("CONNECT").setSel(True)
                conn.findWidget("DISCONNECT").setSel(False)
                self.client.sendNewSwitch(conn)
                logger.info(f"Connecting {self.name}...")
                time.sleep(2)

        self._set_state(CameraState.IDLE)
        return True

    def disconnect(self):
        dev = self.dev
        if dev:
            conn = dev.getSwitch("CONNECTION")
            if conn:
                conn.findWidget("CONNECT").setSel(False)
                conn.findWidget("DISCONNECT").setSel(True)
                self.client.sendNewSwitch(conn)

    def set_gain(self, gain: int) -> bool:
        return self.client._set_number(self.device_name, "CCD_GAIN", [("GAIN", gain)])

    def set_offset(self, offset: int) -> bool:
        return self.client._set_number(self.device_name, "CCD_OFFSET", [("OFFSET", offset)])

    def set_binning(self, bin_x: int = 1, bin_y: int = 1) -> bool:
        return self.client._set_number(self.device_name, "CCD_BINNING",
                                       [("HOR_BIN", bin_x), ("VER_BIN", bin_y)])

    def set_temperature(self, temp_c: float) -> bool:
        return self.client._set_number(self.device_name, "CCD_TEMPERATURE",
                                       [("CCD_TEMPERATURE_VALUE", temp_c)])

    def get_temperature(self) -> Optional[float]:
        return self.client.get_number(self.device_name, "CCD_TEMPERATURE",
                                      "CCD_TEMPERATURE_VALUE")

    def set_frame(self, x: int = 0, y: int = 0, w: int = -1, h: int = -1):
        if w > 0 and h > 0:
            self.client._set_number(self.device_name, "CCD_FRAME",
                                    [("X", x), ("Y", y), ("WIDTH", w), ("HEIGHT", h)])

    def get_frame_size(self) -> tuple[int, int]:
        w = self.client.get_number(self.device_name, "CCD_FRAME", "WIDTH")
        h = self.client.get_number(self.device_name, "CCD_FRAME", "HEIGHT")
        return (int(w) if w else 0, int(h) if h else 0)

    def expose(self, duration: float, is_guider: bool = False) -> bool:
        ccd_name = "CCD1"
        if is_guider:
            match = self.client.get_switch_state(self.device_name, "ACTIVE_DEVICES")
            if match and "CCD2" in match:
                ccd_name = "CCD2"
            elif match:
                ccd_name = match

        blob_prop = f"CCD{ccd_name[-1] if ccd_name.startswith('CCD') else '1'}"
        blob_prop = f"{ccd_name}_BLOB" if ccd_name != "CCD1" else "CCD_BLOB"

        exposure_prop = f"{ccd_name}_EXPOSURE" if ccd_name != "CCD1" else "CCD_EXPOSURE"

        evt = self.client.start_blob_exposure(
            self.device_name, exposure_prop, f"{ccd_name}_EXPOSURE_VALUE", duration
        )

        self._set_state(CameraState.EXPOSING)

        def monitor():
            remaining = duration
            while remaining > 0 and not evt.is_set():
                if self._on_exposure_progress:
                    self._on_exposure_progress(1.0 - remaining / duration)
                time.sleep(0.1)
                remaining -= 0.1
            if evt.wait(timeout=max(5, duration * 2)):
                self._set_state(CameraState.DOWNLOADING)
                blob_name = f"CCD{ccd_name[-1]}" if ccd_name != "CCD1" else "CCD1"
                data = self.client.get_last_blob(self.device_name, f"{blob_name}_BLOB")
                if data and self._on_image:
                    self._on_image(data)
                self._set_state(CameraState.IDLE)
                if self._on_exposure_progress:
                    self._on_exposure_progress(0)
            else:
                self._set_state(CameraState.ERROR)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        return True

    def abort_exposure(self) -> bool:
        return self.client._set_switch(self.device_name, "CCD_ABORT_EXPOSURE",
                                       [("ABORT", True)])

    def get_status(self) -> dict:
        temp = self.get_temperature()
        w, h = self.get_frame_size()
        gain = self.client.get_number(self.device_name, "CCD_GAIN", "GAIN")
        return {
            "temperature": temp,
            "width": w,
            "height": h,
            "gain": gain,
            "state": self.state.value,
        }

    def set_batch_mode(self, enabled: bool) -> bool:
        return self.client._set_switch(self.device_name, "CCD_BATCH_MODE",
                                       [("ENABLED", enabled)])
