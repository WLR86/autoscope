import os
import json
import time
import struct
import logging
import threading
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

JS_EVENT_FORMAT = "IhBB"
JS_EVENT_SIZE = struct.calcsize(JS_EVENT_FORMAT)

JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80


class JoystickAction(Enum):
    MOVE_N = "move_n"
    MOVE_S = "move_s"
    MOVE_E = "move_e"
    MOVE_W = "move_w"
    STOP_ALL = "stop_all"
    SPEED_UP = "speed_up"
    SPEED_DOWN = "speed_down"
    SPEED_SET = "speed_set"
    TRACK_CYCLE = "track_cycle"
    TRACK_MODE = "track_mode"
    HOME = "home"


DEFAULT_JOY_BINDINGS = {
    "axis_ns": 1,
    "axis_ew": 0,
    "axis_deadzone": 8000,
    "btn_speed_up": 5,
    "btn_speed_down": 4,
    "btn_r1": 5,
    "btn_l1": 4,
    "btn_r2": 7,
    "btn_l2": 6,
    "btn_stop": 1,
    "btn_track_mode": 2,
    "btn_home": 0,
    "btn_exit": 3,
}


class JoystickController:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.bindings = {**DEFAULT_JOY_BINDINGS, **self.config.get("bindings", {})}
        self.device_path: Optional[str] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._file: Optional[object] = None

        self._on_action: Optional[Callable[[JoystickAction, float], None]] = None
        self._active_directions: set[str] = set()
        self._current_speed = 5

    def on_action(self, callback: Callable[[JoystickAction, float], None]):
        self._on_action = callback

    def _find_device(self) -> Optional[str]:
        for dev in sorted(Path("/dev/input").glob("js*")):
            return str(dev)
        if Path("/dev/input/by-id").is_dir():
            for dev in sorted(Path("/dev/input/by-id").glob("*joystick*")):
                return str(dev.resolve())
            for dev in sorted(Path("/dev/input/by-id").glob("*gamepad*")):
                return str(dev.resolve())
            for dev in sorted(Path("/dev/input/by-id").glob("*event-joystick*")):
                return str(dev.resolve())
        return None

    def start(self):
        self.device_path = self._find_device()
        if not self.device_path:
            logger.warning("No joystick device found")
            return False

        logger.info(f"Joystick found at {self.device_path}")
        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self.running = False
        if self._file:
            try:
                self._file.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2)

    def _read_loop(self):
        try:
            import fcntl
            self._file = open(self.device_path, "rb")
            fcntl.fcntl(self._file, fcntl.F_SETFL, os.O_NONBLOCK)

            buf = b""
            while self.running:
                try:
                    chunk = self._file.read(1024)
                    if not chunk:
                        time.sleep(0.01)
                        continue
                    buf += chunk
                    while len(buf) >= JS_EVENT_SIZE:
                        event = buf[:JS_EVENT_SIZE]
                        buf = buf[JS_EVENT_SIZE:]
                        self._parse_event(event)
                except BlockingIOError:
                    time.sleep(0.01)
                except OSError as e:
                    logger.error(f"Joystick read error: {e}")
                    time.sleep(0.5)
        except FileNotFoundError:
            logger.error(f"Joystick device {self.device_path} not found")
        except Exception as e:
            logger.error(f"Joystick thread error: {e}")
        finally:
            if self._file:
                try:
                    self._file.close()
                except OSError:
                    pass

    def _parse_event(self, data: bytes):
        try:
            _, value, etype, number = struct.unpack(JS_EVENT_FORMAT, data)
        except struct.error:
            return

        if etype & JS_EVENT_INIT:
            return

        b = self.bindings
        deadzone = b["axis_deadzone"]

        if etype & JS_EVENT_AXIS == JS_EVENT_AXIS:
            if number == b["axis_ns"]:
                old_n = "n" in self._active_directions
                old_s = "s" in self._active_directions
                if value < -deadzone:
                    self._set_direction("n", True)
                    self._set_direction("s", False)
                elif value > deadzone:
                    self._set_direction("s", True)
                    self._set_direction("n", False)
                else:
                    self._set_direction("n", False)
                    self._set_direction("s", False)

            elif number == b["axis_ew"]:
                old_e = "e" in self._active_directions
                old_w = "w" in self._active_directions
                if value < -deadzone:
                    self._set_direction("w", True)
                    self._set_direction("e", False)
                elif value > deadzone:
                    self._set_direction("e", True)
                    self._set_direction("w", False)
                else:
                    self._set_direction("e", False)
                    self._set_direction("w", False)

        elif etype & JS_EVENT_BUTTON == JS_EVENT_BUTTON:
            if not value:
                return
            if number == b["btn_speed_up"] or number == b["btn_r1"] or number == b["btn_r2"]:
                self._emit(JoystickAction.SPEED_UP, 0)
            elif number == b["btn_speed_down"] or number == b["btn_l1"] or number == b["btn_l2"]:
                self._emit(JoystickAction.SPEED_DOWN, 0)
            elif number == b["btn_stop"]:
                self._emit(JoystickAction.STOP_ALL, 0)
            elif number == b["btn_track_mode"]:
                self._emit(JoystickAction.TRACK_CYCLE, 0)
            elif number == b["btn_home"]:
                self._emit(JoystickAction.HOME, 0)

    def _set_direction(self, direction: str, active: bool):
        was_active = direction in self._active_directions
        if active and not was_active:
            self._active_directions.add(direction)
            self._emit(JoystickAction[f"MOVE_{direction.upper()}"], 0)
        elif not active and was_active:
            self._active_directions.discard(direction)
            self._emit(JoystickAction[f"MOVE_{direction.upper()}"], 0)

    def _emit(self, action: JoystickAction, value: float):
        if self._on_action:
            try:
                self._on_action(action, value)
            except Exception as e:
                logger.error(f"Joystick callback error: {e}")

    def get_speed(self) -> int:
        return self._current_speed

    def set_speed(self, speed: int):
        self._current_speed = max(1, min(9, speed))
