"""
Lure recommender — picks BOTH a topwater option AND a shad-swimbait option
for each scoring window. The "primary" is whichever technique conditions
favor most; the "alternative" is offered as a backup if the primary isn't
producing on the water.

Topwater categories:
  - Walking bait   (Zara Spook / Lonely Angler Doc) — "walk the dog"
                     side-to-side. Calm to lightly choppy water.
  - Popper         (Yo-Zuri 3DB / Storm Chug Bug) — cupped face spits water.
                     Chop and low light.
  - Pencil popper  (Cotton Cordell / Stillwater Smack-It) — long thin bait
                     that fires casts and chugs erratically. Choppy
                     conditions, breaking fish.
  - Wake bait      — runs just under the surface; for fish that won't fully
                     commit (post-frontal, mid-day calm).

Shad / swimbait categories:
  - Soft plastic shad on jighead (Storm WildEye Live Shad / Tsunami
                     Holographic Shad) — classic Chesapeake striper bait.
                     Versatile across depths and conditions.
  - Paddle-tail shad (Z-Man PaddlerZ / Bass Assassin Sea Shad) — more
                     vibration; better in stained water and cold/sluggish
                     fish situations.
  - Hard shad plug   (Lucky Craft LV-300 / Sebile Magic Swimmer) — holds
                     bottom in heavy wind/current better than soft plastic.
"""
from __future__ import annotations

WALKING = "Walking bait (Zara Spook / Lonely Angler Doc)"
POPPER = "Popper (Yo-Zuri 3DB / Storm Chug Bug)"
PENCIL = "Pencil popper (Cotton Cordell / Stillwater Smack-It)"
WAKE = "Wake bait (Sebile Magic Swimmer surface / Spro BBZ-1)"

SHAD_SOFT = "Soft plastic shad on jighead (Storm WildEye Live Shad / Tsunami Holographic Shad)"
SHAD_PADDLE = "Paddle-tail shad on jighead (Z-Man PaddlerZ / Bass Assassin Sea Shad)"
SHAD_HARD = "Hard shad swimming plug (Lucky Craft LV-300 / Sebile Magic Swimmer)"


def recommend(*, wind_mph: int, sky_cover_pct: int, hour: int,
              sunrise_hour: int, sunset_hour: int,
              water_clarity: str = "moderate",
              month: int = 5, temp_f: int = 65) -> dict:
    """
    Return {'primary': {...}, 'alternative': {...}}.

    Each inner dict has keys: type, lure, color, why.
    `type` is "Topwater" or "Swimbait".
    """
    topwater = _topwater_pick(
        wind_mph=wind_mph, sky_cover_pct=sky_cover_pct,
        hour=hour, sunrise_hour=sunrise_hour, sunset_hour=sunset_hour,
        water_clarity=water_clarity, month=month,
    )
    shad = _shad_pick(
        wind_mph=wind_mph, sky_cover_pct=sky_cover_pct,
        hour=hour, sunrise_hour=sunrise_hour, sunset_hour=sunset_hour,
        water_clarity=water_clarity, month=month, temp_f=temp_f,
    )

    low_light = (hour <= sunrise_hour + 1) or (hour >= sunset_hour - 1)

    # When conditions clearly favor shad over topwater:
    #   - heavy wind makes topwater impractical
    #   - cold water (stripers won't chase to surface aggressively)
    #   - bright midday with clear sky
    if wind_mph >= 22 or temp_f < 55:
        return {"primary": shad, "alternative": topwater}
    if not low_light and sky_cover_pct < 50:
        return {"primary": shad, "alternative": topwater}

    # Otherwise topwater is the headline pick (this app's original focus);
    # shad is offered as the switch-to option if fish are short-striking.
    return {"primary": topwater, "alternative": shad}


def _topwater_pick(*, wind_mph, sky_cover_pct, hour, sunrise_hour,
                   sunset_hour, water_clarity, month) -> dict:
    low_light = (hour <= sunrise_hour + 1) or (hour >= sunset_hour - 1)

    # ---- Type ----
    if wind_mph >= 15:
        lure = PENCIL
        reason_type = "Wind 15+ mph — pencil poppers cast far and call fish through chop."
    elif wind_mph >= 8:
        lure = POPPER if not low_light else WALKING
        reason_type = ("Light chop + low light suits a walking bait’s subtle side-to-side action."
                       if low_light else
                       "Light chop hides line and prop — poppers excel here.")
    elif wind_mph <= 3 and not low_light and sky_cover_pct < 60:
        lure = WAKE
        reason_type = "Slick calm + bright sun = spooky fish. Wake bait sub-surface gets bites a topwater won't."
    else:
        lure = WALKING
        reason_type = "Calm to light wind — the classic walk-the-dog presentation."

    # ---- Color ----
    if water_clarity == "stained":
        color = "Chartreuse / yellow"
        reason_color = "Stained water — high-vis chartreuse cuts through the murk."
    elif sky_cover_pct >= 70:
        color = "Bone / white"
        reason_color = "Overcast sky — bone or white shows up against grey water."
    elif low_light:
        color = "Bone with red head"
        reason_color = "Dawn/dusk silhouette — bone with a contrasting head is a classic."
    elif sky_cover_pct < 40:
        color = "Chrome / bunker"
        reason_color = "Bright sun, clear water — chrome flashes like a real baitfish."
    else:
        color = "Bone / white"
        reason_color = "Mixed conditions — bone is the all-around safe pick."

    # ---- Size by season ----
    if month in (4, 5):
        size_note = " Spring profile: 4–5\" (matching smaller baitfish)."
    elif month in (10, 11):
        size_note = " Fall profile: 6–7\" (chasing bunker/menhaden)."
    else:
        size_note = ""

    return {
        "type": "Topwater",
        "lure": lure,
        "color": color,
        "why": f"{reason_type} {reason_color}{size_note}",
    }


def _shad_pick(*, wind_mph, sky_cover_pct, hour, sunrise_hour,
               sunset_hour, water_clarity, month, temp_f) -> dict:
    low_light = (hour <= sunrise_hour + 1) or (hour >= sunset_hour - 1)

    # ---- Type ----
    if temp_f < 55:
        lure = SHAD_PADDLE
        reason_type = "Cold water — slow-roll a paddletail near bottom for sluggish fish."
    elif wind_mph >= 18:
        lure = SHAD_HARD
        reason_type = "Heavy wind — a hard swimming plug tracks straighter than soft plastic in chop."
    elif water_clarity == "stained":
        lure = SHAD_PADDLE
        reason_type = "Stained water — paddletail's vibration helps fish find it."
    else:
        lure = SHAD_SOFT
        reason_type = "Soft plastic shad — the bread-and-butter Chesapeake striper bait."

    # ---- Color ----
    if water_clarity == "stained":
        color = "Chartreuse / yellow with dark back"
        reason_color = "High-vis pattern in murky water."
    elif temp_f < 55:
        color = "Smoke purple / black"
        reason_color = "Cold-water fish prefer dark silhouettes; subtle profile."
    elif sky_cover_pct >= 70:
        color = "Pearl white"
        reason_color = "Overcast — neutral white stands out against grey backdrop."
    elif sky_cover_pct < 30 and water_clarity == "clear":
        color = "Pearl with silver flash"
        reason_color = "Bright sun + clear water — silver flash mimics a fleeing baitfish."
    elif low_light:
        color = "White with chartreuse tail"
        reason_color = "Dawn/dusk — pale body with high-vis accent."
    else:
        color = "Pearl white with chartreuse tail"
        reason_color = "All-around favorite — pearl body, accent tail color."

    # ---- Jighead weight ----
    if wind_mph >= 15:
        head = "3/4–1 oz jighead"
    elif wind_mph >= 8:
        head = "1/2–3/4 oz jighead"
    else:
        head = "3/8–1/2 oz jighead"

    # ---- Size by season ----
    if month in (4, 5):
        size_note = " Spring: 3–5\" body."
    elif month in (10, 11):
        size_note = " Fall: 5–7\" body (matching bunker)."
    else:
        size_note = " 4–6\" body — most versatile."

    return {
        "type": "Swimbait",
        "lure": lure,
        "color": color,
        "why": f"{reason_type} {reason_color} Rig with {head}.{size_note}",
    }
