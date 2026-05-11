"""
Obstruction lookup — given a fishing spot, return the obstructions, wrecks,
rocks, and daymarks within a casting-friendly radius. Sourced from NOAA ENC
data via scripts/fetch_obstructions.py and stored in data/obstructions.json.

Distance is computed with the haversine formula and reported in yards plus a
compass bearing, so you can find each feature visually from your spot.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "obstructions.json"

# 1 nautical mile = 2025.37 yards
NM_TO_YD = 2025.37
# Earth radius in nautical miles (mean)
EARTH_R_NM = 3440.065


def load_all() -> list[dict]:
    """Read the cached obstructions list. Returns [] if the file doesn't exist."""
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH) as f:
        return json.load(f).get("obstructions", [])


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in nautical miles."""
    a1, a2 = math.radians(lat1), math.radians(lat2)
    da = math.radians(lat2 - lat1)
    do = math.radians(lon2 - lon1)
    h = math.sin(da / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(do / 2) ** 2
    return 2 * EARTH_R_NM * math.asin(math.sqrt(h))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 (0 = N, 90 = E)."""
    a1, a2 = math.radians(lat1), math.radians(lat2)
    do = math.radians(lon2 - lon1)
    x = math.sin(do) * math.cos(a2)
    y = math.cos(a1) * math.sin(a2) - math.sin(a1) * math.cos(a2) * math.cos(do)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg: float) -> str:
    """Convert a bearing in degrees to a 16-point compass label."""
    return _COMPASS[int((deg + 11.25) // 22.5) % 16]


def nearby(spot: dict, all_obstructions: list[dict],
           radius_nm: float = 0.5, limit: int = 8) -> list[dict]:
    """
    Return obstructions within `radius_nm` of `spot`, closest first.
    Each item is enriched with distance_yd, bearing_deg, compass.
    Capped at `limit` items per spot to keep the UI readable.
    """
    spot_lat, spot_lon = spot["lat"], spot["lon"]
    found = []
    for o in all_obstructions:
        d = haversine_nm(spot_lat, spot_lon, o["lat"], o["lon"])
        if d > radius_nm:
            continue
        b = bearing_deg(spot_lat, spot_lon, o["lat"], o["lon"])
        found.append({
            **o,
            "distance_nm": round(d, 2),
            "distance_yd": int(round(d * NM_TO_YD)),
            "bearing_deg": int(round(b)),
            "compass": compass(b),
        })
    found.sort(key=lambda x: x["distance_nm"])
    return found[:limit]
