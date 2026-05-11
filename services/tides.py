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
