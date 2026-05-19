"""
Scoring engine — turns raw conditions into a 0-100 score for each
(spot × time window) and produces human-readable rationale.

Weights are tunable. The defaults reflect the user's tuned preferences:

  Tide phase (28%)  — TIMING: near but not at a high/low change.
  Cloud cover (20%) — extends bite window, especially mid-day.
  Moon (20%)        — spring tides (new/full ±3d) intensify current.
  Structure (15%)   — drop-offs and points get a small bonus.
  Current (12%)     — MAGNITUDE: how much water is actually moving (range × cycle position).
  Wind / chop (5%)  — peak at 0-8 mph (≤7 knots); calm is good for this user.

You can adjust these in `WEIGHTS` to match what you observe on the water.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from . import tides, weather, moon, sun, lure

WEIGHTS = {
    "tide": 0.28,
    "current": 0.12,
    "wind": 0.05,
    "cloud": 0.20,
    "moon": 0.20,
    "structure": 0.15,
}


def score_window(spot: dict, window_center: datetime,
                 tide_events: list, hourly: list,
                 sunrise: datetime, sunset: datetime) -> dict:
    """Score a single (spot, time window) combination. Returns full breakdown."""

    # `closest` (minutes from nearest sunrise/sunset) is no longer a scored
    # criterion, but the cloud-scoring branch and rationale text still use it.
    minutes_from_dawn = abs((window_center - sunrise).total_seconds() / 60)
    minutes_from_dusk = abs((window_center - sunset).total_seconds() / 60)
    closest = min(minutes_from_dawn, minutes_from_dusk)

    # --- Tide phase score (TIMING — near but not at a change) ---
    tide_state = tides.tide_state_at(tide_events, window_center)
    mins_from = tide_state["minutes_from_change"]
    if tide_state["phase"] == "slack":
        tide_score = 15
    elif mins_from < 30:        tide_score = 40
    elif mins_from < 60:        tide_score = 75
    elif mins_from < 120:       tide_score = 100   # the sweet spot
    elif mins_from < 180:       tide_score = 80
    else:                       tide_score = 45

    # --- Current strength score (MAGNITUDE — how much water is moving) ---
    current = tides.current_strength_at(tide_events, window_center)
    current_score = current["score_0_100"]

    # --- Weather (wind + clouds + temp) ---
    fc = weather.find_forecast_for(hourly, window_center)
    wind_mph = fc["wind_mph"] if fc else 8
    sky = fc["sky_cover_pct"] if fc else 50
    temp_f = fc["temp_f"] if fc else 65

    # Wind — user prefers calm. Peak at 0-8 mph (≤7 knots), falls off above.
    if wind_mph <= 8:           wind_score = 100  # calm to light breeze
    elif wind_mph <= 12:        wind_score = 70
    elif wind_mph <= 15:        wind_score = 50
    elif wind_mph <= 20:        wind_score = 30
    elif wind_mph <= 25:        wind_score = 15
    else:                       wind_score = 5    # blown out

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
        tide_score * WEIGHTS["tide"] +
        current_score * WEIGHTS["current"] +
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
        spot, window_center, tide_state, current, mp, wind_mph, sky, temp_f, closest
    )

    return {
        "spot": spot,
        "time": window_center,
        "score": round(total, 1),
        "components": {
            "tide": tide_score, "current": current_score,
            "wind": wind_score, "cloud": round(cloud_score, 0),
            "moon": moon_score, "structure": structure_score,
        },
        "conditions": {
            "wind_mph": wind_mph, "sky_cover_pct": sky, "temp_f": temp_f,
            "tide_phase": tide_state["phase"],
            "minutes_from_tide_change": mins_from,
            "current_label": current["label"],
            "current_score": current_score,
            "tidal_range_ft": current.get("range_ft", 0),
            "moon_phase": mp["phase_name"],
            "moon_illum_pct": mp["illumination_pct"],
            "is_spring_tide": mp["is_spring_tide"],
        },
        "lure": pick,
        "rationale": rationale,
    }


def _rationale(spot, when, tide_state, current, mp, wind, sky, temp, mins_from_light):
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

    # Current strength commentary — separate from tide phase
    label = current.get("label", "")
    if label in ("strong", "peak"):
        parts.append(f"Current is {label} ({current['score_0_100']}/100, ~{current['range_ft']} ft cycle range) — moving water concentrates bait through pinch points.")
    elif label == "moderate":
        parts.append(f"Current is moderate ({current['score_0_100']}/100) — workable but not peak.")
    elif label in ("weak", "slack"):
        parts.append(f"Current is {label} ({current['score_0_100']}/100) — bait isn't being pushed; bite typically slower.")

    if wind <= 8:
        parts.append(f"Wind {wind} mph — calm to light breeze; quiet presentation, fish less spooky.")
    elif wind <= 15:
        parts.append(f"Wind {wind} mph — workable but breezier than ideal.")
    else:
        parts.append(f"Wind {wind} mph — challenging conditions for accurate casting and boat handling.")

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
