"""
Tides service — pulls high/low tide predictions from NOAA's free public API.

Why tides matter for stripers: stripers feed aggressively during MOVING water.
The two hours around a tide change (incoming or outgoing) are prime windows
because current pushes bait through structure, and predators set up to ambush.
Slack tide (the brief period when water stops moving at high or low) is usually
the worst time to fish.

NOAA API docs: https://api.tidesandcurrents.noaa.gov/api/prod/
"""
from __future__ import annotations
import requests
from datetime import datetime, timedelta

API_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


def fetch_tide_predictions(station_id: str, days: int = 7) -> list[dict]:
    """
    Return a list of upcoming high/low tide events for a station.

    Each event looks like:
        {"time": datetime, "type": "H" or "L", "height_ft": float}
    """
    today = datetime.now()
    end = today + timedelta(days=days)

    params = {
        "product": "predictions",
        "application": "striper-fishing-app",
        "begin_date": today.strftime("%Y%m%d"),
        "end_date": end.strftime("%Y%m%d"),
        "datum": "MLLW",         # Mean Lower Low Water — standard tidal reference
        "station": station_id,
        "time_zone": "lst_ldt",  # Local Standard / Local Daylight time
        "units": "english",      # feet, not meters
        "interval": "hilo",      # only the high and low extremes, not every 6 minutes
        "format": "json",
    }

    try:
        r = requests.get(API_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[tides] Error fetching station {station_id}: {e}")
        return []

    events = []
    for p in data.get("predictions", []):
        events.append({
            "time": datetime.strptime(p["t"], "%Y-%m-%d %H:%M"),
            "type": p["type"],            # "H" or "L"
            "height_ft": float(p["v"]),
        })
    return events


def current_strength_at(events: list[dict], when: datetime) -> dict:
    """
    Estimate the relative water current strength at `when`.

    Why this matters: stripers feed in moving water. The tide-phase criterion
    rewards good TIMING (near but not at a tide change). Current strength is
    the complementary MAGNITUDE measure — how much water is actually being
    pushed. A spring tide at mid-cycle moves a LOT more water than a neap
    tide at the same moment relative to slack.

    Model: combines two physical drivers
      1. Position in the tide cycle — current is zero at high/low (slack) and
         peaks at the midpoint. A sin(π·fraction) curve captures this.
      2. Tidal range — bigger swing between high and low means more water has
         to move in the same window, so peak current is higher. Normalized
         against a typical Chesapeake range of ~3 ft.

    Returns a dict with:
        relative:    0.0 → 1.0+, peaks ~1.0 on average mid-tide
        score_0_100: clipped to 100 for use in the weighted score
        label:       "slack" / "weak" / "moderate" / "strong" / "peak"
    """
    import math

    prev_event = None
    next_event = None
    for e in events:
        if e["time"] <= when:
            prev_event = e
        elif next_event is None:
            next_event = e
            break

    if prev_event is None or next_event is None:
        return {"relative": 0.0, "score_0_100": 0, "label": "unknown"}

    cycle_seconds = (next_event["time"] - prev_event["time"]).total_seconds()
    if cycle_seconds <= 0:
        return {"relative": 0.0, "score_0_100": 0, "label": "unknown"}

    fraction = (when - prev_event["time"]).total_seconds() / cycle_seconds
    sinusoid = math.sin(math.pi * fraction)   # 0 → 1 → 0 across the cycle

    range_ft = abs(next_event["height_ft"] - prev_event["height_ft"])
    range_factor = min(1.0, range_ft / 3.0)   # 3ft+ swing = full strength

    relative = sinusoid * range_factor
    score = int(round(min(100, relative * 100)))

    if   score < 20:  label = "slack"
    elif score < 40:  label = "weak"
    elif score < 60:  label = "moderate"
    elif score < 80:  label = "strong"
    else:             label = "peak"

    return {
        "relative": round(relative, 2),
        "score_0_100": score,
        "label": label,
        "range_ft": round(range_ft, 1),
    }


def tide_state_at(events: list[dict], when: datetime) -> dict:
    """
    Given the list of high/low events and a target time, describe the tide state.

    Returns:
        {
          "phase": "incoming" | "outgoing" | "slack",
          "minutes_from_change": int,   # how long since/until the nearest tide change
          "next_event": dict,
          "prev_event": dict,
        }

    The scoring engine uses this to decide if `when` falls in a feeding window.
    """
    prev_event = None
    next_event = None
    for e in events:
        if e["time"] <= when:
            prev_event = e
        elif e["time"] > when and next_event is None:
            next_event = e
            break

    if prev_event is None or next_event is None:
        return {"phase": "unknown", "minutes_from_change": 9999,
                "next_event": next_event, "prev_event": prev_event}

    # If previous was a Low and next is a High → water is currently rising (incoming)
    # If previous was a High and next is a Low → water is falling (outgoing)
    phase = "incoming" if prev_event["type"] == "L" else "outgoing"

    mins_since_prev = int((when - prev_event["time"]).total_seconds() / 60)
    mins_to_next = int((next_event["time"] - when).total_seconds() / 60)
    minutes_from_change = min(mins_since_prev, mins_to_next)

    # Within ~30 min of an extreme high or low we treat as slack (dead water)
    if minutes_from_change < 30:
        phase = "slack"

    return {
        "phase": phase,
        "minutes_from_change": minutes_from_change,
        "next_event": next_event,
        "prev_event": prev_event,
    }
