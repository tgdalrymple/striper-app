"""
CBIBS (Chesapeake Bay Interpretive Buoy System) — provides BOTH water
temperature and air pressure trend for our forecast, sourced from the
Gooses Reef buoy (station GR) at 38.556°N, 76.414°W. That buoy sits
inside our fishing area near James Island, so its readings are
representative of the entire Choptank / mid-Bay region we cover.

Why one station, applied to all spots and all windows:
  - Water temp varies on the order of ~0.5°F per mile in the Bay; our
    spots are within ~15 nm of the buoy, so within ~5°F worst case and
    typically within 1-2°F. Good enough for striper-comfort scoring.
  - Air pressure varies even less spatially — the synoptic pressure
    field is essentially uniform across the operating area.
  - Pressure trend lasts ~12-24 hrs; we use today's observed trend as a
    proxy for the next few days' bite, which is the conventional angler
    wisdom anyway ("a front is coming = good fishing").

CBIBS API docs: https://buoybay.noaa.gov/data/api
The key below is the public testing key documented by NOAA on that page.
"""
from __future__ import annotations
import requests
from datetime import datetime, timedelta

API_BASE = "https://mw.buoybay.noaa.gov/api/v1/json"
STATION = "GR"
KEY = "f159959c117f473477edbdf3245cc2a4831ac61f"


def _fetch(variable: str, hours_back: int) -> list[dict]:
    """Pull a single variable's time series from the last N hours."""
    end = datetime.utcnow()
    start = end - timedelta(hours=hours_back)
    url = f"{API_BASE}/query/{STATION}"
    params = {
        "key": KEY,
        "sd": start.strftime("%Y-%m-%dT%H:%M:%Sz"),
        "ed": end.strftime("%Y-%m-%dT%H:%M:%Sz"),
        "var": variable,
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[cbibs] fetch {variable} failed: {e}")
        return []

    stations = data.get("stations", [])
    if not stations:
        return []
    for v in stations[0].get("variable", []):
        if v.get("actualName") != variable:
            continue
        out = []
        for m in v.get("measurements", []):
            try:
                # CBIBS timestamps look like "2026-05-19T15:48:00+00"
                t = datetime.strptime(m["time"][:19], "%Y-%m-%dT%H:%M:%S")
                out.append({"time": t, "value": float(m["value"])})
            except Exception:
                continue
        return out
    return []


def water_temp_snapshot() -> dict | None:
    """
    Current water temperature plus a 7-day trend label.
    Returns:
        temp_f          — most recent observed water temp, Fahrenheit
        observed_at     — UTC time of that observation
        trend_label     — warming fast / warming / steady / cooling / cooling fast
        change_per_day_f — degrees F change per day across the 7-day window
    """
    obs = _fetch("sea_water_temperature", hours_back=24 * 7)
    if not obs:
        return None

    latest = obs[-1]
    earliest = obs[0]
    temp_f = round(latest["value"] * 9 / 5 + 32, 1)

    days = (latest["time"] - earliest["time"]).total_seconds() / 86400
    if days < 0.5:
        label, rate = "unknown", 0.0
    else:
        delta_f = (latest["value"] - earliest["value"]) * 9 / 5
        rate = delta_f / days
        if   rate >  1.5:  label = "warming fast"
        elif rate >  0.3:  label = "warming"
        elif rate < -1.5:  label = "cooling fast"
        elif rate < -0.3:  label = "cooling"
        else:               label = "steady"

    return {
        "temp_f": temp_f,
        "observed_at": latest["time"],
        "trend_label": label,
        "change_per_day_f": round(rate, 2),
    }


def pressure_trend_snapshot() -> dict | None:
    """
    Current air pressure plus a 12-hour trend label.

    Why 12 hours: long enough to see a real front move through, short
    enough to track today's weather change. Anglers' rule of thumb is
    "falling pressure ahead of a front triggers feeding."

    Returns:
        pressure_mb    — most recent observed pressure, hPa (≈ mb)
        observed_at    — UTC time of that observation
        trend_label    — falling fast / falling / steady / rising / rising fast
        change_12hr_mb — hPa change over the last ~12 hours
    """
    obs = _fetch("air_pressure", hours_back=24)
    if not obs:
        return None

    latest = obs[-1]
    target = latest["time"] - timedelta(hours=12)
    earlier = min(obs, key=lambda x: abs((x["time"] - target).total_seconds()))
    delta = latest["value"] - earlier["value"]

    if   delta < -1.5:  label = "falling fast"
    elif delta < -0.5:  label = "falling"
    elif delta <=  0.5: label = "steady"
    elif delta <=  1.5: label = "rising"
    else:                label = "rising fast"

    return {
        "pressure_mb": round(latest["value"], 1),
        "observed_at": latest["time"],
        "trend_label": label,
        "change_12hr_mb": round(delta, 1),
    }
