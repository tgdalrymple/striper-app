"""
Sunrise / sunset calculator.

Why this matters: the single biggest predictor of topwater striper success is
LIGHT LEVEL. The "magic hour" before sunrise and the hour after, plus the
hour before sunset and after, are the prime topwater windows. We need
sunrise/sunset for each spot's lat/lon to identify those windows.

Algorithm: NOAA's standard solar position formula. Accurate to ~1 minute,
which is plenty for fishing.
"""
from __future__ import annotations
import math
from datetime import datetime, timedelta


def sunrise_sunset(date: datetime, lat: float, lon: float) -> tuple[datetime, datetime]:
    """Return (sunrise, sunset) as local naive datetimes on `date`."""
    # Day of year
    n = date.timetuple().tm_yday

    # Solar mean anomaly and equation of time (simplified)
    lng_hour = lon / 15.0

    def solve(rising: bool) -> datetime:
        t = n + ((6 - lng_hour) / 24.0 if rising else (18 - lng_hour) / 24.0)
        M = (0.9856 * t) - 3.289
        L = M + (1.916 * math.sin(math.radians(M))) + \
            (0.020 * math.sin(math.radians(2 * M))) + 282.634
        L %= 360
        RA = math.degrees(math.atan(0.91764 * math.tan(math.radians(L))))
        RA %= 360
        # Adjust RA to same quadrant as L
        L_q = (math.floor(L / 90)) * 90
        RA_q = (math.floor(RA / 90)) * 90
        RA = RA + (L_q - RA_q)
        RA /= 15.0
        sin_dec = 0.39782 * math.sin(math.radians(L))
        cos_dec = math.cos(math.asin(sin_dec))
        zenith = 90.833  # official sunrise/sunset zenith (incl. refraction)
        cosH = (math.cos(math.radians(zenith)) - (sin_dec * math.sin(math.radians(lat)))) / \
               (cos_dec * math.cos(math.radians(lat)))
        if cosH > 1 or cosH < -1:
            # Sun never rises/sets — won't happen in MD
            return datetime(date.year, date.month, date.day, 6 if rising else 18)
        if rising:
            H = 360 - math.degrees(math.acos(cosH))
        else:
            H = math.degrees(math.acos(cosH))
        H /= 15.0
        T = H + RA - (0.06571 * t) - 6.622
        UT = (T - lng_hour) % 24
        # Convert UT to a local hour-of-day; keep the date the user asked for
        # (UTC sunset can fall after midnight UTC even though it's still
        # "today" locally — we don't want to roll the date forward).
        offset = _eastern_offset(date)
        local_hour = (UT + offset) % 24
        return datetime(date.year, date.month, date.day) + timedelta(hours=local_hour)

    return solve(rising=True), solve(rising=False)


def _eastern_offset(date: datetime) -> int:
    """
    Return the UTC offset for US Eastern time (-5 EST, -4 EDT).
    DST in the US: 2nd Sunday in March → 1st Sunday in November.
    """
    y = date.year
    # second Sunday in March
    march = datetime(y, 3, 1)
    dst_start = march + timedelta(days=(6 - march.weekday()) % 7 + 7)
    # first Sunday in November
    nov = datetime(y, 11, 1)
    dst_end = nov + timedelta(days=(6 - nov.weekday()) % 7)
    if dst_start <= date < dst_end:
        return -4
    return -5
