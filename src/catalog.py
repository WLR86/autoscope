import math
import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SkyObject:
    name: str
    ra_hours: float
    dec_deg: float
    magnitude: float
    obj_type: str = ""
    catalog: str = ""
    constellation: str = ""
    description: str = ""

    def altaz(self, lat: float, lon: float, lst: float):
        ha = lst - self.ra_hours
        ha_rad = math.radians(ha * 15)
        dec_rad = math.radians(self.dec_deg)
        lat_rad = math.radians(lat)

        alt = math.asin(
            math.sin(lat_rad) * math.sin(dec_rad) +
            math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
        )

        az = math.atan2(
            -math.sin(ha_rad),
            math.tan(dec_rad) * math.cos(lat_rad) - math.sin(lat_rad) * math.cos(ha_rad)
        )
        return math.degrees(alt), math.degrees(az) % 360

    def is_visible(self, lat: float, lon: float, lst: float,
                   min_alt: float = 15) -> bool:
        alt, _ = self.altaz(lat, lon, lst)
        return alt > min_alt


MESSIER_OBJECTS = [
    SkyObject("M1 - Crab Nebula", 5.578, 22.017, 8.4, "Supernova Remnant", "Messier", "Taurus"),
    SkyObject("M3 - Globular Cluster", 13.702, 28.383, 6.2, "Globular Cluster", "Messier", "Canes Venatici"),
    SkyObject("M13 - Hercules Cluster", 16.700, 36.461, 5.8, "Globular Cluster", "Messier", "Hercules"),
    SkyObject("M15 - Great Pegasus Cluster", 21.500, 12.167, 6.2, "Globular Cluster", "Messier", "Pegasus"),
    SkyObject("M27 - Dumbbell Nebula", 19.983, 22.717, 7.4, "Planetary Nebula", "Messier", "Vulpecula"),
    SkyObject("M31 - Andromeda Galaxy", 0.712, 41.267, 3.4, "Spiral Galaxy", "Messier", "Andromeda"),
    SkyObject("M33 - Triangulum Galaxy", 1.567, 30.660, 5.7, "Spiral Galaxy", "Messier", "Triangulum"),
    SkyObject("M42 - Orion Nebula", 5.583, -5.383, 4.0, "Diffuse Nebula", "Messier", "Orion"),
    SkyObject("M45 - Pleiades", 3.783, 24.117, 1.6, "Open Cluster", "Messier", "Taurus"),
    SkyObject("M51 - Whirlpool Galaxy", 13.500, 47.233, 8.4, "Spiral Galaxy", "Messier", "Canes Venatici"),
    SkyObject("M57 - Ring Nebula", 18.900, 33.033, 8.8, "Planetary Nebula", "Messier", "Lyra"),
    SkyObject("M64 - Black Eye Galaxy", 12.950, 21.683, 8.5, "Spiral Galaxy", "Messier", "Coma Berenices"),
    SkyObject("M65 - Leo Triplet", 11.333, 13.083, 9.3, "Spiral Galaxy", "Messier", "Leo"),
    SkyObject("M81 - Bode's Galaxy", 9.933, 69.067, 6.9, "Spiral Galaxy", "Messier", "Ursa Major"),
    SkyObject("M82 - Cigar Galaxy", 9.933, 69.683, 8.4, "Starburst Galaxy", "Messier", "Ursa Major"),
    SkyObject("M101 - Pinwheel Galaxy", 14.050, 54.350, 7.9, "Spiral Galaxy", "Messier", "Ursa Major"),
    SkyObject("M104 - Sombrero Galaxy", 13.000, -11.617, 8.0, "Spiral Galaxy", "Messier", "Virgo"),
]

NGC_OBJECTS = [
    SkyObject("NGC 7000 - North America Nebula", 20.967, 44.533, 4.0, "Diffuse Nebula", "NGC", "Cygnus"),
    SkyObject("NGC 6992 - Veil Nebula", 20.917, 31.700, 7.0, "Supernova Remnant", "NGC", "Cygnus"),
    SkyObject("NGC 1499 - California Nebula", 4.017, 36.367, 5.0, "Diffuse Nebula", "NGC", "Perseus"),
    SkyObject("NGC 1976 - Orion Nebula (M42)", 5.583, -5.383, 4.0, "Diffuse Nebula", "NGC", "Orion"),
    SkyObject("NGC 2244 - Rosette Nebula", 6.517, 4.917, 4.8, "Open Cluster", "NGC", "Monoceros"),
    SkyObject("NGC 457 - Owl Cluster", 1.317, 58.300, 6.4, "Open Cluster", "NGC", "Cassiopeia"),
    SkyObject("NGC 6543 - Cat's Eye Nebula", 17.950, 66.633, 9.8, "Planetary Nebula", "NGC", "Draco"),
    SkyObject("NGC 2392 - Eskimo Nebula", 7.483, 20.917, 9.9, "Planetary Nebula", "NGC", "Gemini"),
    SkyObject("NGC 6826 - Blinking Planetary", 19.750, 50.517, 8.8, "Planetary Nebula", "NGC", "Cygnus"),
    SkyObject("NGC 6888 - Crescent Nebula", 20.217, 38.333, 7.4, "Diffuse Nebula", "NGC", "Cygnus"),
    SkyObject("NGC 6960 - Western Veil", 20.800, 30.683, 7.0, "Supernova Remnant", "NGC", "Cygnus"),
    SkyObject("NGC 7023 - Iris Nebula", 21.017, 68.167, 6.8, "Reflection Nebula", "NGC", "Cepheus"),
    SkyObject("NGC 7293 - Helix Nebula", 22.483, -20.833, 7.3, "Planetary Nebula", "NGC", "Aquarius"),
    SkyObject("NGC 7635 - Bubble Nebula", 23.333, 61.167, 10.0, "Diffuse Nebula", "NGC", "Cassiopeia"),
    SkyObject("NGC 7789 - Caroline's Rose", 23.950, 56.700, 6.7, "Open Cluster", "NGC", "Cassiopeia"),
]

PLANETS = [
    SkyObject("Mercury", 0, 0, -0.5, "Planet", "Solar System"),
    SkyObject("Venus", 0, 0, -4.5, "Planet", "Solar System"),
    SkyObject("Mars", 0, 0, -2.0, "Planet", "Solar System"),
    SkyObject("Jupiter", 0, 0, -2.7, "Planet", "Solar System"),
    SkyObject("Saturn", 0, 0, 0.5, "Planet", "Solar System"),
    SkyObject("Uranus", 0, 0, 5.5, "Planet", "Solar System"),
    SkyObject("Neptune", 0, 0, 7.9, "Planet", "Solar System"),
]


class Catalog:
    def __init__(self, config: dict):
        self.config = config
        self._objects: dict[str, list[SkyObject]] = {
            "messier": [],
            "ngc": [],
            "planets": [],
            "custom": [],
        }
        self._load()

    def _load(self):
        if self.config.get("messier", True):
            self._objects["messier"] = list(MESSIER_OBJECTS)
        if self.config.get("ngc", True):
            self._objects["ngc"] = list(NGC_OBJECTS)
        if self.config.get("planets", True):
            self._objects["planets"] = list(PLANETS)

    def get_by_catalog(self, catalog: str) -> list[SkyObject]:
        return self._objects.get(catalog.lower(), [])

    def get_all(self) -> list[SkyObject]:
        result = []
        for objs in self._objects.values():
            result.extend(objs)
        return result

    def search(self, query: str) -> list[SkyObject]:
        q = query.lower()
        results = []
        for obj in self.get_all():
            if q in obj.name.lower() or q in obj.constellation.lower():
                results.append(obj)
        return results

    def get_visible(self, lat: float, lon: float, lst: float,
                    min_alt: float = 15) -> list[SkyObject]:
        visible = []
        for obj in self.get_all():
            if obj.is_visible(lat, lon, lst, min_alt):
                visible.append(obj)
        return visible
