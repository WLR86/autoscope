import math
import time
import logging
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class AlignmentStar:
    def __init__(self, name: str, ra_hours: float, dec_deg: float,
                 magnitude: float, constellation: str = "",
                 bayer: str = ""):
        self.name = name
        self.ra_hours = ra_hours
        self.dec_deg = dec_deg
        self.magnitude = magnitude
        self.constellation = constellation
        self.bayer = bayer

    def label(self) -> str:
        if self.bayer:
            return f"{self.bayer} · {self.name}"
        return self.name

    def __repr__(self):
        return f"{self.label()} ({self.ra_hours:.2f}h, {self.dec_deg:.1f}°)"


ALIGNMENT_STARS = [
    AlignmentStar("Polaris", 2.530, 89.264, 1.97, "Ursa Minor", "α Ursae Minoris"),
    AlignmentStar("Sirius", 6.752, -16.716, -1.46, "Canis Major", "α Canis Majoris"),
    AlignmentStar("Canopus", 6.398, -52.695, -0.74, "Carina", "α Carinae"),
    AlignmentStar("Arcturus", 14.262, 19.187, -0.05, "Boötes", "α Boötis"),
    AlignmentStar("Vega", 18.617, 38.784, 0.03, "Lyra", "α Lyrae"),
    AlignmentStar("Capella", 5.278, 45.998, 0.08, "Auriga", "α Aurigae"),
    AlignmentStar("Rigel", 5.242, -8.202, 0.18, "Orion", "β Orionis"),
    AlignmentStar("Procyon", 7.655, 5.224, 0.40, "Canis Minor", "α Canis Minoris"),
    AlignmentStar("Betelgeuse", 5.919, 7.407, 0.42, "Orion", "α Orionis"),
    AlignmentStar("Altair", 19.847, 8.868, 0.76, "Aquila", "α Aquilae"),
    AlignmentStar("Aldebaran", 4.600, 16.509, 0.87, "Taurus", "α Tauri"),
    AlignmentStar("Antares", 16.490, -26.432, 0.96, "Scorpius", "α Scorpii"),
    AlignmentStar("Spica", 13.413, -11.161, 0.98, "Virgo", "α Virginis"),
    AlignmentStar("Pollux", 7.763, 28.026, 1.14, "Gemini", "β Geminorum"),
    AlignmentStar("Fomalhaut", 22.958, -29.622, 1.16, "Piscis Austrinus", "α Piscis Austrini"),
    AlignmentStar("Deneb", 20.692, 45.280, 1.25, "Cygnus", "α Cygni"),
    AlignmentStar("Regulus", 10.139, 11.967, 1.36, "Leo", "α Leonis"),
    AlignmentStar("Castor", 7.592, 31.888, 1.58, "Gemini", "α Geminorum"),
    AlignmentStar("Bellatrix", 5.417, 6.350, 1.64, "Orion", "γ Orionis"),
    AlignmentStar("Elnath", 5.434, 28.610, 1.65, "Taurus", "β Tauri"),
    AlignmentStar("Mirach", 1.155, 35.620, 2.07, "Andromeda", "β Andromedae"),
    AlignmentStar("Hamal", 2.116, 23.462, 2.01, "Aries", "α Arietis"),
    AlignmentStar("Mirfak", 3.361, 49.861, 1.79, "Perseus", "α Persei"),
    AlignmentStar("Alkaid", 13.792, 49.300, 1.86, "Ursa Major", "η Ursae Majoris"),
    AlignmentStar("Dubhe", 11.050, 61.750, 1.79, "Ursa Major", "α Ursae Majoris"),
]


class AlignmentMethod(Enum):
    ONE_STAR = "1-star"
    TWO_STAR = "2-star"
    THREE_STAR = "3-star"
    PLATE_SOLVE = "plate-solve"


class AlignmentPoint:
    def __init__(self, catalog_ra: float, catalog_dec: float,
                 measured_ra: float, measured_dec: float,
                 method: AlignmentMethod):
        self.catalog_ra = catalog_ra
        self.catalog_dec = catalog_dec
        self.measured_ra = measured_ra
        self.measured_dec = measured_dec
        self.method = method
        self.timestamp = time.time()
        self.ra_error = (catalog_ra - measured_ra) * 15 * \
                        math.cos(math.radians(catalog_dec))
        self.dec_error = catalog_dec - measured_dec

    def __repr__(self):
        return (f"AlignPoint(cat={self.catalog_ra:.4f},{self.catalog_dec:.3f} "
                f"got={self.measured_ra:.4f},{self.measured_dec:.3f})")


class AlignmentModel:
    def __init__(self, config: dict):
        self.config = config
        self.points: list[AlignmentPoint] = []
        self.method = AlignmentMethod.ONE_STAR
        self._cone_correction_enabled = config.get("use_cone_correction", True)
        self._refraction_enabled = config.get("use_refraction_correction", True)
        self._additive = config.get("additive_correction", True)
        self.max_points = config.get("max_align_points", 20)

    def set_method(self, method: AlignmentMethod):
        self.method = method

    def reset(self):
        self.points.clear()

    @property
    def is_calibrated(self) -> bool:
        return len(self.points) >= 1

    def add_point(self, catalog_ra: float, catalog_dec: float,
                  measured_ra: float, measured_dec: float,
                  method: Optional[AlignmentMethod] = None) -> AlignmentPoint:
        pt = AlignmentPoint(catalog_ra, catalog_dec,
                            measured_ra, measured_dec,
                            method or self.method)
        self.points.append(pt)
        if len(self.points) > self.max_points:
            self.points.pop(0)
        logger.info(f"Added alignment point: {pt}")
        return pt

    def correct(self, target_ra: float, target_dec: float,
                alt: Optional[float] = None) -> tuple[float, float]:
        if not self.points:
            return target_ra, target_dec

        if self._additive:
            d_ra = 0.0
            d_dec = 0.0
            n = 0
            for pt in self.points:
                d_ra += pt.ra_error
                d_dec += pt.dec_error
                n += 1
            if n > 0:
                d_ra /= n
                d_dec /= n
            ra_corr = target_ra + d_ra / (15 * math.cos(math.radians(target_dec)))
            dec_corr = target_dec + d_dec
            return (ra_corr, dec_corr)

        return target_ra, target_dec

    def get_summary(self) -> dict:
        n = len(self.points)
        if n == 0:
            return {"count": 0, "avg_ra_error": 0, "avg_dec_error": 0}

        ra_errs = [p.ra_error for p in self.points]
        dec_errs = [p.dec_error for p in self.points]
        return {
            "count": n,
            "avg_ra_error": sum(ra_errs) / n,
            "avg_dec_error": sum(dec_errs) / n,
            "max_ra_error": max(max(ra_errs), -min(ra_errs)),
            "max_dec_error": max(max(dec_errs), -min(dec_errs)),
            "method": self.method.value,
        }


class AlignmentController:
    def __init__(self, mount, guider_cam, imager_cam,
                 plate_solver: 'PlateSolver',
                 alignment_model: AlignmentModel):
        self.mount = mount
        self.guider_cam = guider_cam
        self.imager_cam = imager_cam
        self.solver = plate_solver
        self.model = alignment_model
        self._current_step = ""
        self._on_progress: Optional[Callable] = None
        self._use_guider = False

    def on_progress(self, callback: Callable):
        self._on_progress = callback

    def _progress(self, msg: str, pct: float = 0):
        self._current_step = msg
        if self._on_progress:
            self._on_progress(msg, pct)

    def get_visible_stars(self, latitude: float, longitude: float,
                          local_sidereal_time: float,
                          min_alt: float = 20) -> list[AlignmentStar]:
        """Filter alignment stars by current visibility."""
        visible = []
        for star in ALIGNMENT_STARS:
            ha = local_sidereal_time - star.ra_hours
            ha_rad = math.radians(ha * 15)
            dec_rad = math.radians(star.dec_deg)
            lat_rad = math.radians(latitude)

            alt = math.asin(
                math.sin(lat_rad) * math.sin(dec_rad) +
                math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
            )
            alt_deg = math.degrees(alt)
            if alt_deg > min_alt:
                visible.append(star)
        visible.sort(key=lambda s: -s.magnitude)
        return visible

    def plate_solve_align(self) -> Optional[AlignmentPoint]:
        self._progress("Capturing image for plate solve...", 10)
        camera = self.guider_cam if self._use_guider else self.imager_cam
        if not camera:
            logger.error("No camera available for plate solve")
            return None

        self.solver.set_use_guider(self._use_guider)

        result: Optional[AlignmentPoint] = None

        def on_image(data: bytes):
            nonlocal result
            self._progress("Plate solving...", 40)
            solve_result = self.solver.solve(data)
            if solve_result:
                measured_ra = solve_result["ra"]
                measured_dec = solve_result["dec"]
                mount_ra, mount_dec, _, _ = self.mount.get_position()
                pt = self.model.add_point(
                    measured_ra, measured_dec,
                    mount_ra, mount_dec,
                    AlignmentMethod.PLATE_SOLVE
                )
                self.mount.sync(measured_ra, measured_dec)
                result = pt
                self._progress(f"Plate solve OK: RA={measured_ra:.4f} DEC={measured_dec:.3f}", 100)
            else:
                self._progress("Plate solve failed", 0)

        camera.on_image(on_image)
        camera.expose(3.0 if self._use_guider else 5.0, is_guider=self._use_guider)

        timeout = 30
        start = time.time()
        while time.time() - start < timeout:
            if result is not None:
                return result
            time.sleep(0.1)
        return None

    def star_align(self, star: AlignmentStar) -> Optional[AlignmentPoint]:
        self._progress(f"Slewing to {star.name}...", 10)

        if not self.mount.slew_to(star.ra_hours, star.dec_deg, wait=True,
                                  progress_cb=lambda p, e: self._progress(
                                      f"Slewing to {star.name}... {p}%", p
                                  )):
            self._progress(f"Slew to {star.name} failed", 0)
            return None

        self._progress(f"Centering {star.name} (use NSEW buttons)", 70)

        self._progress(f"Syncing on {star.name}...", 90)
        pt = self.model.add_point(
            star.ra_hours, star.dec_deg,
            self.mount.current_ra, self.mount.current_dec
        )
        self.mount.sync(star.ra_hours, star.dec_deg)
        self._progress(f"Aligned on {star.name}", 100)
        return pt

    def run_align_sequence(self, stars: list[AlignmentStar],
                           method: AlignmentMethod) -> bool:
        self.model.set_method(method)
        self.model.reset()

        if method == AlignmentMethod.PLATE_SOLVE:
            for i in range(3):
                result = self.plate_solve_align()
                if result:
                    self._progress(f"Plate solve alignment {i+1}/3 complete", 100)
                else:
                    if i > 0:
                        break
                    return False
            return self.model.is_calibrated

        max_stars = {"1-star": 1, "2-star": 2, "3-star": 3}[method.value]
        for i, star in enumerate(stars[:max_stars]):
            result = self.star_align(star)
            if not result:
                if i == 0:
                    return False
                break
            self._progress(f"Star {i+1}/{max_stars} aligned: {star.name}",
                           (i + 1) * 100 // max_stars)

        if self.model.is_calibrated:
            summary = self.model.get_summary()
            logger.info(f"Alignment complete: {summary}")
            return True
        return False
