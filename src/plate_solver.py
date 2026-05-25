import os
import io
import json
import math
import time
import logging
import subprocess
import threading
from typing import Optional
from urllib.request import urlopen, Request
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class PlateSolver:
    def __init__(self, config: dict):
        self.config = config
        self.method = config.get("method", "astap")
        self.astap_bin = config.get("astap_binary", "/usr/bin/astap")
        self.star_db = config.get("astap_star_db", "")
        self.online_url = config.get("online_url", "http://nova.astrometry.net/api/")
        self.online_key = config.get("online_api_key", "")
        self.search_radius = config.get("search_radius_deg", 10)
        self.timeout = config.get("solve_timeout", 30)
        self._solve_in_progress = False
        self._last_result: Optional[dict] = None

    def solve(self, image_data: bytes,
              ra_hint: Optional[float] = None,
              dec_hint: Optional[float] = None,
              scale_hint: Optional[float] = None) -> Optional[dict]:
        if self._solve_in_progress:
            logger.warning("Solve already in progress")
            return None

        self._solve_in_progress = True
        try:
            if self.method == "astap":
                return self._solve_astap(image_data, ra_hint, dec_hint, scale_hint)
            elif self.method == "online":
                return self._solve_online(image_data, ra_hint, dec_hint, scale_hint)
            else:
                logger.error(f"Unknown solver method: {self.method}")
                return None
        finally:
            self._solve_in_progress = False

    def _solve_astap(self, image_data: bytes,
                     ra: Optional[float], dec: Optional[float],
                     scale: Optional[float]) -> Optional[dict]:
        tmp_dir = "/tmp/astap_solve"
        os.makedirs(tmp_dir, exist_ok=True)
        fits_path = os.path.join(tmp_dir, "solve.fits")
        out_path = os.path.join(tmp_dir, "solve.ini")

        try:
            from astropy.io import fits
            import numpy as np

            if image_data[:4] == b'\x89HDF':  # FITS header check - not reliable
                with open(fits_path, "wb") as f:
                    f.write(image_data)
            else:
                img = np.frombuffer(image_data, dtype=np.uint8)
                hdu = fits.PrimaryHDU(img.astype(np.int32))
                hdu.writeto(fits_path, overwrite=True)

            cmd = [self.astap_bin, "-f", fits_path, "-o", out_path]
            if ra is not None:
                cmd.extend(["-ra", f"{ra:.6f}"])
            if dec is not None:
                cmd.extend(["-spd", f"{90 - dec:.6f}"])
            if scale is not None:
                cmd.extend(["-scale", f"{scale:.4f}"])
            if self.star_db:
                cmd.extend(["-d", self.star_db])
            cmd.extend(["-r", str(self.search_radius)])
            cmd.append("-s")  # silent mode

            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=self.timeout)
            logger.debug(f"ASTAP stdout: {result.stdout[:200]}")
            logger.debug(f"ASTAP stderr: {result.stderr[:200]}")

            if os.path.exists(out_path):
                return self._parse_astap_result(out_path)

            if result.returncode != 0:
                logger.warning(f"ASTAP failed: {result.stderr[:200]}")
                return None

            return None

        except subprocess.TimeoutExpired:
            logger.error("ASTAP solve timed out")
            return None
        except FileNotFoundError:
            logger.error(f"ASTAP binary not found at {self.astap_bin}")
            return None
        except ImportError:
            logger.error("astropy not installed, cannot process FITS")
            return None
        except Exception as e:
            logger.error(f"ASTAP solve error: {e}")
            return None
        finally:
            for f in [fits_path, out_path]:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except OSError:
                    pass

    def _parse_astap_result(self, ini_path: str) -> Optional[dict]:
        try:
            import configparser
            cp = configparser.ConfigParser()
            cp.read(ini_path)
            section = cp.get("ASTAP", "DETECTION", fallback=None)
            if not section:
                section = "DETECTION"
            if section not in cp:
                return None

            det = cp[section]
            ra_str = det.get("RA", "")
            dec_str = det.get("DEC", "")
            if not ra_str or not dec_str:
                return None

            ra_hours = sum(float(x) / 60 ** i for i, x in enumerate(ra_str.split(":")))
            dec_dms = dec_str.replace("D", ":").replace("M", ":").replace("S", "")
            dec_parts = dec_dms.split(":")
            dec_deg = abs(float(dec_parts[0])) + float(dec_parts[1]) / 60 + \
                      float(dec_parts[2]) / 3600
            if dec_dms.startswith("-") or dec_str.startswith("-"):
                dec_deg = -dec_deg

            result = {
                "ra": ra_hours,
                "dec": dec_deg,
                "ra_deg": ra_hours * 15,
                "status": "success",
                "solver": "astap",
            }
            self._last_result = result
            return result

        except Exception as e:
            logger.error(f"Parse ASTAP result error: {e}")
            return None

    def _solve_online(self, image_data: bytes,
                      ra: Optional[float], dec: Optional[float],
                      scale: Optional[float]) -> Optional[dict]:
        try:
            import requests as req
        except ImportError:
            logger.error("requests not installed for online solver")
            return None

        try:
            base = self.online_url.rstrip("/")
            key = self.online_key

            if not key:
                r = req.post(f"{base}/login", data={"apikey": ""})
                if r.status_code != 200:
                    logger.error("Online solver: no API key and anonymous login failed")
                    return None
                key_data = r.json()
                key = key_data.get("session")

            sub = req.post(f"{base}/upload",
                           data={"session": key, "publicly_visible": "n"})
            if sub.status_code != 200:
                logger.error("Online solver: upload failed")
                return None

            sub_id = sub.json().get("subid")
            if not sub_id:
                return None

            if ra is not None:
                req.post(f"{base}/url_search", data={
                    "session": key, "subid": sub_id,
                    "ra": ra * 15, "dec": dec,
                    "radius": self.search_radius
                })

            start = time.time()
            while time.time() - start < self.timeout:
                stat = req.get(f"{base}/submissions/{sub_id}")
                if stat.status_code != 200:
                    break
                s = stat.json()
                if s.get("status") == "success":
                    jobs = s.get("jobs", [])
                    if jobs:
                        job_id = jobs[0]
                        cal = req.get(f"{base}/jobs/{job_id}/calibration")
                        if cal.status_code == 200:
                            cal_data = cal.json()
                            result = {
                                "ra": cal_data.get("ra", 0) / 15,
                                "dec": cal_data.get("dec", 0),
                                "ra_deg": cal_data.get("ra", 0),
                                "status": "success",
                                "solver": "online",
                                "orientation": cal_data.get("orientation"),
                                "pixscale": cal_data.get("pixscale"),
                            }
                            self._last_result = result
                            return result
                    break
                elif s.get("status") in ("failed", "error"):
                    break
                time.sleep(2)

        except Exception as e:
            logger.error(f"Online solve error: {e}")

        return None

    def get_last_result(self) -> Optional[dict]:
        return self._last_result

    def set_use_guider(self, use_guider: bool):
        self.config["use_guider"] = use_guider
