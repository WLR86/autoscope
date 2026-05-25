import time
import math
import logging
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class MountState(Enum):
    IDLE = "idle"
    SLEWING = "slewing"
    TRACKING = "tracking"
    PARKED = "parked"
    ALIGNING = "aligning"
    ERROR = "error"


class TrackingMode(Enum):
    OFF = "off"
    STELLAR = "stellar"
    SOLAR = "solar"
    LUNAR = "lunar"


DIRECTION_MAP = {
    "n": "TELESCOPE_MOTION_NS",
    "s": "TELESCOPE_MOTION_NS",
    "e": "TELESCOPE_MOTION_WE",
    "w": "TELESCOPE_MOTION_WE",
}

DIRECTION_ELEM = {
    "n": "MOTION_NORTH",
    "s": "MOTION_SOUTH",
    "e": "MOTION_WEST",
    "w": "MOTION_EAST",
}

SYNSCAN_SPEEDS = [
    (0.5, "0.5x"),      # 1
    (1.0, "1x Sidereal"), # 2
    (2.0, "2x"),         # 3
    (4.0, "4x"),         # 4
    (8.0, "8x"),         # 5
    (16.0, "16x"),       # 6
    (32.0, "32x"),       # 7
    (64.0, "64x"),       # 8
    (800.0, "800x"),     # 9
]

INDI_RATE_MAP = {1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 3}

TRACKING_SIDEREAL_RATE = 15.041  # arcsec/s
TRACKING_SOLAR_RATE = 15.0
TRACKING_LUNAR_RATE = 14.685


class MountController:
    def __init__(self, client, device_name: str = "EQMOD Mount"):
        self.client = client
        self.device_name = device_name
        self.state = MountState.IDLE
        self._pulse_running = False
        self._abort = False
        self._on_state_change: Optional[Callable] = None

        self.target_ra = 0.0
        self.target_dec = 0.0
        self.current_ra = 0.0
        self.current_dec = 0.0
        self.current_alt = 0.0
        self.current_az = 0.0
        self.tracking = False
        self.track_mode = TrackingMode.STELLAR
        self.speed_index = 5

    @property
    def dev(self):
        return self.client.get_device(self.device_name)

    def on_state_change(self, callback: Callable):
        self._on_state_change = callback

    def _set_state(self, new_state: MountState):
        old = self.state
        self.state = new_state
        if self._on_state_change and old != new_state:
            self._on_state_change(new_state)

    def connect(self) -> bool:
        if not self.client.wait_for_device(self.device_name, timeout=20):
            logger.error("Mount device not found")
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
                logger.info("Connecting mount...")
                time.sleep(2)

        self.set_slew_rate(self.speed_index)
        self.set_tracking_mode(self.track_mode)

        self._set_state(MountState.IDLE)
        self._update_position()
        return True

    def disconnect(self):
        dev = self.dev
        if dev:
            conn = dev.getSwitch("CONNECTION")
            if conn:
                conn.findWidget("CONNECT").setSel(False)
                conn.findWidget("DISCONNECT").setSel(True)
                self.client.sendNewSwitch(conn)
        self._set_state(MountState.IDLE)

    def _update_position(self):
        ra = self.client.get_number(self.device_name, "EQUATORIAL_EOD_COORD", "RA")
        dec = self.client.get_number(self.device_name, "EQUATORIAL_EOD_COORD", "DEC")
        alt = self.client.get_number(self.device_name, "HORIZONTAL_COORD", "ALT")
        az = self.client.get_number(self.device_name, "HORIZONTAL_COORD", "AZ")
        track = self.client.get_switch_state(self.device_name, "TELESCOPE_TRACK_STATE")

        if ra is not None:
            self.current_ra = ra
        if dec is not None:
            self.current_dec = dec
        if alt is not None:
            self.current_alt = alt
        if az is not None:
            self.current_az = az
        self.tracking = (track == "TRACK_ON")

    def get_position(self) -> tuple[float, float, float, float]:
        self._update_position()
        return (self.current_ra, self.current_dec,
                self.current_alt, self.current_az)

    def get_status(self) -> dict:
        self._update_position()
        return {
            "ra": self.current_ra,
            "dec": self.current_dec,
            "alt": self.current_alt,
            "az": self.current_az,
            "tracking": self.tracking,
            "track_mode": self.track_mode.value,
            "speed": self.speed_index,
            "speed_label": SYNSCAN_SPEEDS[self.speed_index - 1][1],
            "state": self.state.value,
        }

    def set_slew_rate(self, rate: int):
        if rate < 1 or rate > 9:
            return
        self.speed_index = rate
        indi_rate = INDI_RATE_MAP[rate]
        rate_names = ["SLEW_GUIDE", "SLEW_CENTERING", "SLEW_FINDING", "SLEW_MAX"]
        if 0 <= indi_rate < len(rate_names):
            elements = [(rate_names[i], i == indi_rate) for i in range(len(rate_names))]
            self.client._set_switch(self.device_name, "TELESCOPE_SLEW_RATE", elements)
            logger.info(f"Slew speed set to {rate}: {SYNSCAN_SPEEDS[rate - 1][1]}")

    def speed_up(self):
        self.set_slew_rate(min(9, self.speed_index + 1))

    def speed_down(self):
        self.set_slew_rate(max(1, self.speed_index - 1))

    def start_motion(self, direction: str):
        if direction.lower() not in DIRECTION_MAP:
            return
        prop = DIRECTION_MAP[direction.lower()]
        elem = DIRECTION_ELEM[direction.lower()]
        self.client._set_switch(self.device_name, prop, [(elem, True)])
        self._set_state(MountState.SLEWING)

    def stop_motion(self, direction: str):
        if direction.lower() not in DIRECTION_MAP:
            return
        prop = DIRECTION_MAP[direction.lower()]
        elem = DIRECTION_ELEM[direction.lower()]
        self.client._set_switch(self.device_name, prop, [(elem, False)])
        self._check_if_done()

    def stop_all_motion(self):
        for d in ["n", "s", "e", "w"]:
            self.stop_motion(d)

    def _check_if_done(self):
        n_moving = self.client.get_switch_state(self.device_name, "TELESCOPE_MOTION_NS")
        we_moving = self.client.get_switch_state(self.device_name, "TELESCOPE_MOTION_WE")
        if n_moving is None and we_moving is None:
            self._set_state(MountState.TRACKING if self.tracking else MountState.IDLE)

    def slew_to(self, ra: float, dec: float, wait: bool = True,
                progress_cb: Optional[Callable] = None) -> bool:
        self.target_ra = ra
        self.target_dec = dec

        self.client._set_number(self.device_name, "EQUATORIAL_EOD_COORD",
                                [("RA", ra), ("DEC", dec)])

        self.client._set_switch(self.device_name, "ON_COORD_SET",
                                [("SLEW", True), ("TRACK", False), ("SYNC", False)])

        if not wait:
            self._set_state(MountState.SLEWING)
            return True

        self._set_state(MountState.SLEWING)
        self._abort = False

        start_ra = self.current_ra
        start_dec = self.current_dec

        for i in range(300):
            if self._abort:
                self.stop_all_motion()
                self._set_state(MountState.IDLE)
                return False

            self._update_position()
            ra_err = (self.current_ra - ra) * 15 * math.cos(math.radians(dec))
            dec_err = self.current_dec - dec
            err = math.sqrt(ra_err**2 + dec_err**2)
            if progress_cb:
                progress_cb(min(100, int(i * 100 / 300)), err)

            if err < 0.01:
                self._set_state(MountState.TRACKING if self.tracking else MountState.IDLE)
                return True
            time.sleep(0.5)

        self._set_state(MountState.TRACKING if self.tracking else MountState.IDLE)
        return True

    def abort_slew(self):
        self._abort = True
        self.stop_all_motion()

    def sync(self, ra: float, dec: float) -> bool:
        self.client._set_number(self.device_name, "EQUATORIAL_EOD_COORD",
                                [("RA", ra), ("DEC", dec)])
        self.client._set_switch(self.device_name, "ON_COORD_SET",
                                [("SLEW", False), ("TRACK", False), ("SYNC", True)])
        self.current_ra = ra
        self.current_dec = dec
        logger.info(f"Synced to RA={ra:.4f} DEC={dec:.4f}")
        return True

    def set_tracking_mode(self, mode: TrackingMode) -> bool:
        self.track_mode = mode
        if mode == TrackingMode.OFF:
            self.set_tracking(False)
            return True

        self.set_tracking(True)

        track_mode_map = {
            TrackingMode.STELLAR: "TRACK_SIDEREAL",
            TrackingMode.SOLAR: "TRACK_SOLAR",
            TrackingMode.LUNAR: "TRACK_LUNAR",
        }
        mode_name = track_mode_map.get(mode)
        if mode_name:
            ok = self.client._set_switch(
                self.device_name, "TELESCOPE_TRACK_MODE",
                [(m, m == mode_name) for m in
                 ["TRACK_SIDEREAL", "TRACK_SOLAR", "TRACK_LUNAR"]]
            )
            if not ok:
                rate = {
                    TrackingMode.STELLAR: TRACKING_SIDEREAL_RATE,
                    TrackingMode.SOLAR: TRACKING_SOLAR_RATE,
                    TrackingMode.LUNAR: TRACKING_LUNAR_RATE,
                }[mode]
                self.client._set_number(
                    self.device_name, "TELESCOPE_TRACK_RATE",
                    [("TRACK_RATE_RA", rate), ("TRACK_RATE_DEC", 0.0)]
                )

        logger.info(f"Tracking mode set to {mode.value}")
        return True

    def cycle_tracking_mode(self):
        modes = list(TrackingMode)
        idx = modes.index(self.track_mode)
        idx = (idx + 1) % len(modes)
        self.set_tracking_mode(modes[idx])
        return self.track_mode

    def set_tracking(self, enabled: bool) -> bool:
        elem = "TRACK_ON" if enabled else "TRACK_OFF"
        self.client._set_switch(self.device_name, "TELESCOPE_TRACK_STATE", [(elem, True)])
        self.tracking = enabled
        logger.info(f"Tracking {'enabled' if enabled else 'disabled'}")
        return True

    def park(self) -> bool:
        self.client._set_switch(self.device_name, "TELESCOPE_PARK",
                                [("PARK", True)])
        self._set_state(MountState.PARKED)
        logger.info("Mount parked")
        return True

    def unpark(self) -> bool:
        self.client._set_switch(self.device_name, "TELESCOPE_PARK",
                                [("UNPARK", True)])
        self._set_state(MountState.IDLE)
        logger.info("Mount unparked")
        return True

    def is_parked(self) -> bool:
        return self.client.get_switch_state(self.device_name, "TELESCOPE_PARK") == "PARK"

    def home(self) -> bool:
        self.client._set_switch(self.device_name, "TELESCOPE_PARK",
                                [("UNPARK", True)])
        time.sleep(1)
        self.slew_to(0, 90)
        return True

    def pulse_guide(self, direction: str, ms: int) -> bool:
        prop = "TELESCOPE_TIMED_GUIDE_NS" if direction in ("n", "s") else "TELESCOPE_TIMED_GUIDE_WE"
        elem = {"n": "TIMED_GUIDE_NORTH", "s": "TIMED_GUIDE_SOUTH",
                "e": "TIMED_GUIDE_WEST", "w": "TIMED_GUIDE_EAST"}[direction]
        self.client._set_number(self.device_name, prop, [(elem, ms / 1000.0)])
        return True
