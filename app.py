"""
Striper Topwater Forecast — main web app.

Run with:
    cd ~/striper-app && ./venv/bin/python app.py

Then open http://localhost:5000 in your browser.

What this file does:
  1. Loads the curated fishing spots from data/spots.json.
  2. For each spot, fetches NOAA tide predictions (cached per station)
     and NOAA hourly weather forecast (cached per ~7-mile grid).
  3. Scores every spot at four time windows per day (dawn, mid-morning,
     mid-afternoon, dusk) across the next 7 days.
  4. Ranks the results and renders an HTML page.

If you change Python code, stop the server (Ctrl+C) and restart it.
"""
from __future__ import annotations
import json
import os
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template

from services import tides, weather, moon, sun, scorer, dnr_report, obstructions, cbibs

app = Flask(__name__)

SPOTS_PATH = Path(__file__).parent / "data" / "spots.json"
FORECAST_DAYS = 7
TOP_PER_DAY = 6

# Server-side cache so that 10 visitors in 10 minutes only trigger ONE round of
# NOAA fetches. The data only meaningfully changes hourly, so a 30-minute TTL
# is plenty fresh and protects us from hammering NOAA.
CACHE_TTL_SECONDS = 30 * 60
_cache = {"data": None, "expires_at": 0.0}


def load_spots() -> list[dict]:
    with open(SPOTS_PATH) as f:
        spots = json.load(f)["spots"]
    # Pre-compute the obstruction list for each spot once at load time —
    # the geometry never changes, only conditions do.
    obs = obstructions.load_all()
    for s in spots:
        s["obstructions"] = obstructions.nearby(s, obs, radius_nm=1.0, limit=8)
    return spots


def build_forecast() -> dict:
    """Fetch all data and score every (spot, day, window) combination."""
    spots = load_spots()

    # --- Cache fetches so we don't repeat API calls ---
    tide_cache: dict[str, list] = {}
    weather_cache: dict[str, list] = {}

    # CBIBS snapshots — fetched once and reused for every spot×window
    water_temp = cbibs.water_temp_snapshot()
    pressure = cbibs.pressure_trend_snapshot()

    def get_tides(station_id):
        if station_id not in tide_cache:
            tide_cache[station_id] = tides.fetch_tide_predictions(station_id, days=FORECAST_DAYS + 1)
        return tide_cache[station_id]

    def get_weather(lat, lon):
        key = f"{round(lat, 1)},{round(lon, 1)}"
        if key not in weather_cache:
            weather_cache[key] = weather.fetch_hourly_forecast(lat, lon)
        if not weather_cache[key]:
            # NOAA grid is unavailable for this exact spot — borrow the
            # nearest neighbor's forecast so we don't fall back to defaults.
            for other_key, other in weather_cache.items():
                if other:
                    return other
        return weather_cache[key]

    # --- Score every spot × day × window ---
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    results_by_day: dict[str, list] = {}

    for day_offset in range(FORECAST_DAYS):
        date = today + timedelta(days=day_offset)
        day_key = date.strftime("%Y-%m-%d")
        results_by_day[day_key] = []

        for spot in spots:
            tide_events = get_tides(spot["tide_station"])
            hourly = get_weather(spot["lat"], spot["lon"])
            if not tide_events:
                continue   # skip if tide fetch failed

            sr, ss = sun.sunrise_sunset(date, spot["lat"], spot["lon"])
            windows = scorer.candidate_windows(date, spot["lat"], spot["lon"])

            for w in windows:
                # Skip windows that have already passed — no point recommending
                # them, and NOAA hourly forecast only covers future hours.
                if w <= datetime.now():
                    continue
                scored = scorer.score_window(
                    spot, w, tide_events, hourly, sr, ss,
                    water_temp=water_temp, pressure=pressure,
                )
                results_by_day[day_key].append(scored)

    # --- Keep top N per day, sorted by score ---
    for day_key in results_by_day:
        results_by_day[day_key].sort(key=lambda x: x["score"], reverse=True)
        results_by_day[day_key] = results_by_day[day_key][:TOP_PER_DAY]

    # --- Day-level summary info (moon, etc.) ---
    day_summaries = []
    for day_offset in range(FORECAST_DAYS):
        date = today + timedelta(days=day_offset)
        # use Cambridge for a representative sunrise/sunset
        sr, ss = sun.sunrise_sunset(date, 38.57, -76.07)
        mp = moon.phase_for(date)
        day_summaries.append({
            "date": date,
            "date_key": date.strftime("%Y-%m-%d"),
            "weekday": date.strftime("%A"),
            "pretty": date.strftime("%a %b %-d"),
            "sunrise": sr.strftime("%-I:%M %p"),
            "sunset": ss.strftime("%-I:%M %p"),
            "moon": mp,
        })

    return {
        "generated_at": datetime.now(),
        "days": day_summaries,
        "results_by_day": results_by_day,
        "dnr": dnr_report.fetch_latest_report(),
        "water_temp": water_temp,
        "pressure": pressure,
    }


def cached_forecast():
    """Return a cached forecast if fresh, otherwise rebuild and cache."""
    now = time.time()
    if _cache["data"] is not None and now < _cache["expires_at"]:
        return _cache["data"]
    try:
        fresh = build_forecast()
    except Exception:
        # On failure, prefer serving stale-but-real data over a 500 page
        traceback.print_exc()
        if _cache["data"] is not None:
            return _cache["data"]
        raise
    _cache["data"] = fresh
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return fresh


@app.route("/")
def index():
    forecast = cached_forecast()
    return render_template("index.html", f=forecast)


@app.route("/healthz")
def health():
    """Render's load balancer pings this to check the app is alive."""
    return "ok", 200


if __name__ == "__main__":
    # Local development entry point. In production, Render runs gunicorn
    # against `app:app` (see Procfile) and never enters this block.
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
