import math
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def load_config(path: str = "config/telescope_config.json") -> dict:
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base, path)
    with open(full_path) as f:
        return json.load(f)


def ra_to_hours(ra: float) -> str:
    h = int(ra)
    m = int((ra - h) * 60)
    s = ((ra - h) * 60 - m) * 60
    return f"{h:02d}h{m:02d}m{s:04.1f}s"


def dec_to_dms(dec: float) -> str:
    sign = "+" if dec >= 0 else "-"
    dec = abs(dec)
    d = int(dec)
    m = int((dec - d) * 60)
    s = ((dec - d) * 60 - m) * 60
    return f"{sign}{d:02d}°{m:02d}'{s:04.1f}\""


def hours_to_deg(hours: float) -> float:
    return hours * 15


def deg_to_hours(deg: float) -> float:
    return deg / 15


def local_sidereal_time(longitude: float) -> float:
    now = datetime.now(timezone.utc)
    jd = julian_day(now)
    jd2000 = jd - 2451545.0
    lst = 100.46 + 0.985647 * jd2000 + longitude + 15 * utc_hours(now)
    lst = lst % 360
    return lst / 15


def julian_day(dt: datetime) -> float:
    year = dt.year
    month = dt.month
    day = dt.day + dt.hour / 24 + dt.minute / 1440 + dt.second / 86400
    if month <= 2:
        year -= 1
        month += 12
    a = int(year / 100)
    b = 2 - a + int(a / 4)
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def utc_hours(dt: datetime) -> float:
    return dt.hour + dt.minute / 60 + dt.second / 3600


def ra_dec_separation(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    d1 = math.radians(dec1)
    d2 = math.radians(dec2)
    dra = math.radians((ra1 - ra2) * 15)
    return math.degrees(
        math.acos(
            math.sin(d1) * math.sin(d2) +
            math.cos(d1) * math.cos(d2) * math.cos(dra)
        )
    )


def airmass(altitude_deg: float) -> float:
    alt_rad = math.radians(altitude_deg)
    return 1.0 / math.sin(alt_rad)


def refraction_correction(altitude_deg: float, pressure_hpa: float = 1013,
                          temp_c: float = 15) -> float:
    alt_rad = math.radians(altitude_deg)
    ref = (pressure_hpa / 1013) * (283 / (273 + temp_c)) * \
          (1.02 / math.tan(alt_rad + 10.3 / (alt_rad + 5.11)))
    return ref / 60


def nstar_string(n: int) -> str:
    if n == 1:
        return "1-star"
    elif n == 2:
        return "2-star"
    elif n == 3:
        return "3-star"
    return f"{n}-star"
