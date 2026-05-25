import sys
import time
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import PyIndi
except ImportError:
    logger.error("pyindi-client not installed. Run: pip install pyindi-client")
    sys.exit(1)


class INDIClient(PyIndi.BaseClient):
    def __init__(self, host: str = "localhost", port: int = 7624):
        super().__init__()
        self.host = host
        self.port = port
        self.server_connected = False
        self.devices: dict[str, PyIndi.BaseDevice] = {}
        self._blob_events: dict[str, threading.Event] = {}
        self._last_blob_data: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def connect_server(self) -> bool:
        if not self.setServer(self.host, self.port):
            logger.error(f"Failed to set server {self.host}:{self.port}")
            return False
        if not self.connectServer():
            logger.error(f"Failed to connect to INDI server at {self.host}:{self.port}")
            return False
        logger.info(f"Connected to INDI server at {self.host}:{self.port}")
        self.server_connected = True
        return True

    def disconnect_server(self):
        self.disconnectServer()
        self.server_connected = False
        logger.info("Disconnected from INDI server")

    def newDevice(self, d: PyIndi.BaseDevice):
        with self._lock:
            self.devices[d.getDeviceName()] = d
        logger.info(f"New device: {d.getDeviceName()}")

    def removeDevice(self, d: PyIndi.BaseDevice):
        with self._lock:
            self.devices.pop(d.getDeviceName(), None)
        logger.info(f"Device removed: {d.getDeviceName()}")

    def newProperty(self, p: PyIndi.Property):
        logger.debug(f"New property: {p.getName()} on {p.getDeviceName()}")

    def updateProperty(self, p: PyIndi.Property):
        pass

    def removeProperty(self, p: PyIndi.Property):
        pass

    def newBLOB(self, bp: PyIndi.IBLOB):
        device_name = bp.getDeviceName()
        prop_name = bp.getName()
        key = f"{device_name}.{prop_name}"
        for blob in bp:
            with self._lock:
                self._last_blob_data[key] = bytes(blob.getblob())
            if key in self._blob_events:
                self._blob_events[key].set()

    def get_device(self, name: str) -> Optional[PyIndi.BaseDevice]:
        with self._lock:
            return self.devices.get(name)

    def wait_for_device(self, name: str, timeout: float = 30.0) -> Optional[PyIndi.BaseDevice]:
        start = time.time()
        while time.time() - start < timeout:
            dev = self.get_device(name)
            if dev is not None:
                return dev
            time.sleep(0.1)
        logger.error(f"Timeout waiting for device: {name}")
        return None

    def send_blob(self, device_name: str, prop_name: str, blob_elem: str, data: bytes):
        dev = self.get_device(device_name)
        if not dev:
            return False
        bp = dev.getBLOB(prop_name)
        if not bp:
            return False
        blob = bp.findWidget(blob_elem)
        if not blob:
            return False
        blob.setblob(data, len(data))
        self.sendNewBLOB(bp)
        return True

    def start_blob_exposure(self, device_name: str, exposure_prop: str,
                            exposure_elem: str, duration: float) -> threading.Event:
        key = f"{device_name}.{exposure_prop.split('.')[0] if '.' not in exposure_prop else ''}"
        evt = threading.Event()
        with self._lock:
            self._blob_events[key] = evt
        self._set_number(device_name, exposure_prop, [(exposure_elem, duration)])
        return evt

    def get_last_blob(self, device_name: str, prop_name: str) -> Optional[bytes]:
        key = f"{device_name}.{prop_name}"
        with self._lock:
            return self._last_blob_data.get(key)

    def _set_number(self, device_name: str, prop_name: str,
                    elements: list[tuple[str, float]]) -> bool:
        dev = self.get_device(device_name)
        if not dev:
            return False
        np = dev.getNumber(prop_name)
        if not np:
            return False
        for elem_name, value in elements:
            elem = np.findWidget(elem_name)
            if not elem:
                return False
            elem.setValue(value)
        self.sendNewNumber(np)
        return True

    def _set_switch(self, device_name: str, prop_name: str,
                    elements: list[tuple[str, bool]]) -> bool:
        dev = self.get_device(device_name)
        if not dev:
            return False
        sp = dev.getSwitch(prop_name)
        if not sp:
            return False
        for elem_name, state in elements:
            elem = sp.findWidget(elem_name)
            if not elem:
                return False
            elem.setSel(state)
        self.sendNewSwitch(sp)
        return True

    def _set_text(self, device_name: str, prop_name: str,
                  elements: list[tuple[str, str]]) -> bool:
        dev = self.get_device(device_name)
        if not dev:
            return False
        tp = dev.getText(prop_name)
        if not tp:
            return False
        for elem_name, value in elements:
            elem = tp.findWidget(elem_name)
            if not elem:
                return False
            elem.setText(value)
        self.sendNewText(tp)
        return True

    def get_number(self, device_name: str, prop_name: str,
                   elem_name: str) -> Optional[float]:
        dev = self.get_device(device_name)
        if not dev:
            return None
        np = dev.getNumber(prop_name)
        if not np:
            return None
        elem = np.findWidget(elem_name)
        if not elem:
            return None
        return elem.getValue()

    def get_switch(self, device_name: str, prop_name: str,
                   elem_name: str) -> Optional[bool]:
        dev = self.get_device(device_name)
        if not dev:
            return None
        sp = dev.getSwitch(prop_name)
        if not sp:
            return None
        elem = sp.findWidget(elem_name)
        if not elem:
            return None
        return elem.getSel()

    def get_switch_state(self, device_name: str, prop_name: str) -> Optional[str]:
        dev = self.get_device(device_name)
        if not dev:
            return None
        sp = dev.getSwitch(prop_name)
        if not sp:
            return None
        for i in range(sp.count()):
            elem = sp[i]
            if elem.getSel():
                return elem.getName()
        return None

    def wait_for_property(self, device_name: str, prop_name: str,
                          timeout: float = 10.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            dev = self.get_device(device_name)
            if dev:
                if dev.getNumber(prop_name) or dev.getSwitch(prop_name) or \
                   dev.getText(prop_name) or dev.getBLOB(prop_name):
                    return True
            time.sleep(0.1)
        return False

    def wait_for_number(self, device_name: str, prop_name: str,
                        elem_name: str, target: float,
                        tolerance: float = 0.1, timeout: float = 30.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            val = self.get_number(device_name, prop_name, elem_name)
            if val is not None and abs(val - target) < tolerance:
                return True
            time.sleep(0.2)
        return False
