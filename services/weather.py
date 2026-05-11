"""
Weather service — pulls hourly forecast from the NOAA National Weather Service API.

Why weather matters for topwater stripers:
- Cloud cover extends the dawn/dusk topwater bite throughout the day.
- 5–15 mph wind is ideal — it puts a "chop" on the surface that obscures the
  lure's seams and disguises your boat. Glass-calm makes fish spooky;
  20+ mph makes topwater impractical.
- Falling barometric pressure (ahead of a front) often triggers feeding.
- Air temperature is a proxy for water temperature trends.

NOAA Weather API docs: https://www.weather.gov/documentation/services-web-api
Note: this API REQUIRES a User-Agent header identifying your app.
"""
from __future__ import annotations
import requests
from datetime import datetime

UA = {"User-Agent": "striper-fishing-app/1.0 (educational use)"}


def _grid_url(lat: float, lon: float) -> str | None:
    """
    NOAA's API is two-step: first ask which "grid" a lat/lon belongs to,
    then ask that grid for its forecast. This caches one lookup per spot.
    """
    try:
        r = requests.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}",
                         headers=UA, timeout=15)
        r.raise_for_status()
        return r.json()["properties"]["forecastHourly"]
    except Exception as e:
        print(f"[weather] grid lookup failed for {lat},{lon}: {e}")
        return None


def _get_with_retry(url: str, attempts: int = 3, sleep_s: float = 1.5):
    """NOAA hourly forecast endpoints occasionally return a transient 404 right
    after publishing a new forecast cycle. A short retry usually clears it."""
    import time
    last_err = None
    for i in range(attempts):
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(sleep_s)
    raise last_err


def fetch_hourly_forecast(lat: float, lon: float) -> list[dict]:
    """
    Return a list of hourly forecast entries.

    Each entry:
        {
          "time": datetime,
          "temp_f": int,
          "wind_mph": int,
          "wind_dir": "NE" or similar,
          "sky_cover_pct": int,   # 0=clear, 100=overcast
          "short_forecast": str,  # e.g. "Partly Sunny"
        }
    """
    url = _grid_url(lat, lon)
    if not url:
        return []
    try:
        r = _get_with_retry(url)
        periods = r.json()["properties"]["periods"]
    except Exception as e:
        print(f"[weather] hourly fetch failed: {e}")
        return []

    result = []
    for p in periods:
        # wind speed comes as a string like "5 to 10 mph" or "10 mph"
        wind_mph = _parse_wind(p.get("windSpeed", "0 mph"))
        result.append({
            "time": datetime.fromisoformat(p["startTime"]).replace(tzinfo=None),
            "temp_f": p.get("temperature"),
            "wind_mph": wind_mph,
            "wind_dir": p.get("windDirection", ""),
            "sky_cover_pct": _sky_cover_from_forecast(p.get("shortForecast", "")),
            "short_forecast": p.get("shortForecast", ""),
        })
    return result


def _parse_wind(s: str) -> int:
    """Extract the high end of a 'X to Y mph' string, or just the number."""
    import re
    nums = re.findall(r"\d+", s)
    if not nums:
        return 0
    return int(nums[-1])  # last number = high end of the range


def _sky_cover_from_forecast(short: str) -> int:
    """
    NWS hourly forecast doesn't give a numeric cloud %, only words.
    Map common phrases to a rough percentage.
    """
    s = short.lower()
    if "clear" in s or "sunny" in s and "partly" not in s and "mostly" not in s:
        return 10
    if "mostly sunny" in s or "mostly clear" in s:
        return 25
    if "partly sunny" in s or "partly cloudy" in s:
        return 50
    if "mostly cloudy" in s:
        return 75
    if "cloudy" in s or "overcast" in s:
        return 95
    if "fog" in s or "rain" in s or "shower" in s or "storm" in s:
        return 95
    return 50


def find_forecast_for(hourly: list[dict], when: datetime) -> dict | None:
    """Find the hourly forecast entry covering a given time."""
    for h in hourly:
        if h["time"].year == when.year and h["time"].month == when.month \
                and h["time"].day == when.day and h["time"].hour == when.hour:
            return h
    return None
