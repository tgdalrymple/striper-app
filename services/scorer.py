"""
Scoring engine — turns raw conditions into a 0-100 score for each
(spot × time window) and produces human-readable rationale.

Weights are tunable. The defaults reflect topwater-striper conventional wisdom:

  Light (40%)      — dawn/dusk dominate; mid-day only with heavy clouds.
  Tide (25%)       — moving water 1-2 hrs from a change; slack tide is dead.
  Wind / chop (15%) — 5-15 mph ideal; calm hurts, 20+ kills topwater.
  Cloud cover (10%) — extends bite window, especially mid-day.
  Moon (5%)        — spring tides (new/full ±3d) intensify current.
  Structure (5%)   — drop-offs and points get a small bonus.

You can adjust these in `WEIGHTS` to match what you observe on the water.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from . import tides, weather, moon, sun, lure

WEIGHTS = {
    "light": 0.40,
    "tide": 0.25,
    "wind": 0.15,
    "cloud": 0.10,
    "moon": 0.05,
    "structure": 0.05,
}


def score_window(spot: dict, window_center: datetime,
                 tide_events: list, hourly: list,
                 sunrise: datetime, sunset: datetime) -> dict:
    """Score a single (spot, time window) combination. Returns full breakdown."""

    # --- Light score ---
    minutes_from_dawn = abs((window_center - sunrise).total_seconds() / 60)
    minutes_from_dusk = abs((window_center - sunset).total_seconds() / 60)
    closest = min(minutes_from_dawn, minutes_from_dusk)
    if closest <= 30:        light = 100
    elif closest <= 60:      light = 85
    elif closest <= 90:      light = 65
    elif closest <= 150:     light = 40
    else:                    light = 15

    # --- Tide score ---
    tide_state = tides.tide_state_at(tide_events, window_center)
    mins_from = tide_state["minutes_from_change"]
    if tide_state["phase"] == "slack":
        tide_score = 15
    elif mins_from < 30:        tide_score = 40
    elif mins_from < 60:        tide_score = 75
    elif mins_from < 120:       tide_score = 100   # the sweet spot
    elif mins_from < 180:       tide_score = 80
    else:                       tide_score = 45

    # --- Weather (wind + clouds + temp) ---
    fc = weather.find_forecast_for(hourly, window_center)
    wind_mph = fc["wind_mph"] if fc else 8
    sky = fc["sky_cover_pct"] if fc else 50
    temp_f = fc["temp_f"] if fc else 65

    # Wind ideal band 5-15
    if 5 <= wind_mph <= 15:     wind_score = 100
    elif wind_mph <= 3:         wind_score = 50  # slick calm
    elif wind_mph <= 4:         wind_score = 65
    elif 16 <= wind_mph <= 20:  wind_score = 60
    elif 21 <= wind_mph <= 25:  wind_score = 30
    else:                       wind_score = 10  # blown out

    # Clouds: clearer doesn't help mid-day; overcast bonus
    if closest > 120:
        # mid-day — heavier overcast helps a lot
        cloud_score = min(100, sky + 15)
    else:
        # dawn/dusk — clouds matter less but still slight bonus
        cloud_score = 60 + (sky * 0.3)

    # --- Moon ---
    mp = moon.phase_for(window_center)
    moon_score = 90 if mp["is_spring_tide"] else 60

    # --- Structure ---
    structure_score = 80 if spot.get("drop_off") else 60

    # --- Weighted sum ---
    total = (
        light * WEIGHTS["light"] +
        tide_score * WEIGHTS["tide"] +
        wind_score * WEIGHTS["wind"] +
        cloud_score * WEIGHTS["cloud"] +
        moon_score * WEIGHTS["moon"] +
        structure_score * WEIGHTS["structure"]
    )

    # --- Lure recommendation tied to this window ---
    sr_h = sunrise.hour + (sunrise.minute / 60)
    ss_h = sunset.hour + (sunset.minute / 60)
    water_clarity = "stained" if (fc and "rain" in fc["short_forecast"].lower()) else "moderate"
    pick = lure.recommend(
        wind_mph=wind_mph,
        sky_cover_pct=sky,
        hour=window_center.hour,
        sunrise_hour=int(sr_h),
        sunset_hour=int(ss_h),
        water_clarity=water_clarity,
        month=window_center.month,
        temp_f=temp_f,
    )

    # --- Rationale text ---
    rationale = _rationale(
        spot, window_center, tide_state, mp, wind_mph, sky, temp_f, closest
    )

    return {
        "spot": spot,
        "time": window_center,
        "score": round(total, 1),
        "components": {
            "light": light, "tide": tide_score, "wind": wind_score,
            "cloud": round(cloud_score, 0), "moon": moon_score,
            "structure": structure_score,
        },
        "conditions": {
            "wind_mph": wind_mph, "sky_cover_pct": sky, "temp_f": temp_f,
            "tide_phase": tide_state["phase"],
            "minutes_from_tide_change": mins_from,
            "moon_phase": mp["phase_name"],
            "moon_illum_pct": mp["illumination_pct"],
            "is_spring_tide": mp["is_spring_tide"],
        },
        "lure": pick,
        "rationale": rationale,
    }


def _rationale(spot, when, tide_state, mp, wind, sky, temp, mins_from_light):
    """Build a plain-English explanation of why this window scored as it did."""
    parts = []

    if mins_from_light <= 60:
        parts.append("Prime low-light window — stripers cruise shallows feeding on bait silhouettes.")
    elif mins_from_light <= 150 and sky >= 70:
        parts.append("Heavy overcast extends the topwater window past first light.")
    elif mins_from_light > 150:
        parts.append("Outside prime light hours — score reflects best of mid-day conditions only.")

    phase = tide_state["phase"]
    mins = tide_state["minutes_from_change"]
    if phase == "slack":
        parts.append("Tide is near slack — water is barely moving; bait isn't being pushed.")
    elif mins <= 120:
        parts.append(f"{phase.capitalize()} tide, {mins} min from the change — water is moving "
                     f"and bait is on the move with it.")
    else:
        parts.append(f"{phase.capitalize()} tide, {mins} min from change — still moving but past the strongest flow.")

    if 5 <= wind <= 15:
        parts.append(f"Wind {wind} mph puts a ripple on the surface that hides your boat and the lure's seams.")
    elif wind <= 3:
        parts.append(f"Wind {wind} mph — slick calm; fish can scrutinize the lure, expect short strikes.")
    else:
        parts.append(f"Wind {wind} mph — challenging conditions for accurate topwater casting.")

    if sky >= 70:
        parts.append(f"Sky {sky}% covered — fish feel safer in low light and roam shallower.")

    if mp["is_spring_tide"]:
        parts.append(f"Spring tide ({mp['phase_name']}) — stronger currents pull more bait through structure.")

    if spot.get("drop_off"):
        parts.append("Structure: drop-off — stripers ambush from deep water into the shallows.")

    parts.append(f"Spot notes: {spot.get('rationale','')}")

    return " ".join(parts)


def candidate_windows(date_obj: datetime, lat: float, lon: float) -> list[datetime]:
    """
    Return the time windows to evaluate for a single date.
    We test dawn, dusk, and a mid-morning + mid-afternoon (in case overcast
    extends the bite). The scorer will heavily penalize mid-day if conditions
    don't justify it.
    """
    sr, ss = sun.sunrise_sunset(date_obj, lat, lon)
    return [
        sr + timedelta(minutes=15),       # dawn
        sr + timedelta(hours=2, minutes=30),   # mid-morning
        ss - timedelta(hours=2, minutes=30),   # mid-afternoon
        ss - timedelta(minutes=15),       # dusk
    ]
