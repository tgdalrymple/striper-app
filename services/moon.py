"""
Moon phase calculator.

Why the moon matters: stripers respond to lunar cycles. The strongest tides
("spring tides") happen around new and full moons because the sun and moon
pull together — more current, more bait movement, more feeding. The days
within ~3 days of new or full moon are often the best of the month.
"""
from __future__ import annotations
from datetime import datetime, timedelta
import math

# A known new moon for reference (Jan 6 2000, 18:14 UTC).
# The synodic month (new moon to new moon) is 29.53059 days on average.
REFERENCE_NEW_MOON = datetime(2000, 1, 6, 18, 14)
SYNODIC_MONTH_DAYS = 29.53058867


def phase_for(date: datetime) -> dict:
    """
    Return the moon phase for a given date.

    {
      "age_days": float,       # days since last new moon (0 = new, ~14.77 = full)
      "phase_name": str,       # human-friendly label
      "illumination_pct": int, # 0=new, 100=full
      "is_spring_tide": bool,  # within 3 days of new or full
    }
    """
    elapsed = (date - REFERENCE_NEW_MOON).total_seconds() / 86400.0
    age = elapsed % SYNODIC_MONTH_DAYS
    if age < 0:
        age += SYNODIC_MONTH_DAYS

    # Illumination follows a cosine curve: 0% at new, 100% at full
    illum = int(round(50 * (1 - math.cos(2 * math.pi * age / SYNODIC_MONTH_DAYS))))

    name = _phase_name(age)
    spring = age < 3 or age > (SYNODIC_MONTH_DAYS - 3) or abs(age - SYNODIC_MONTH_DAYS / 2) < 3

    return {
        "age_days": round(age, 1),
        "phase_name": name,
        "illumination_pct": illum,
        "is_spring_tide": spring,
    }


def _phase_name(age: float) -> str:
    if age < 1.84:    return "New Moon"
    if age < 5.53:    return "Waxing Crescent"
    if age < 9.22:    return "First Quarter"
    if age < 12.91:   return "Waxing Gibbous"
    if age < 16.61:   return "Full Moon"
    if age < 20.30:   return "Waning Gibbous"
    if age < 23.99:   return "Last Quarter"
    if age < 27.68:   return "Waning Crescent"
    return "New Moon"
