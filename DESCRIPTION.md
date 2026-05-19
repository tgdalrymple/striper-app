# Striper Topwater Forecast — Application Summary

## What it does

A web application ([fishing.tgdalrymple.com](https://fishing.tgdalrymple.com)) that ranks
the best windows for casting **topwater** and **soft-plastic shad** lures to striped
bass over the next 7 days. For each ranked window it tells you the spot, the time,
a primary lure type and color, an alternative lure if the primary isn't producing,
and the rationale behind the pick.

## Geographic coverage

20 curated spots across three regions:

- **Chesapeake Bay** from Poplar Island south to the Little Choptank entrance
- **Choptank River** mainstem and tributaries (incl. Tred Avon)
- **Little Choptank River** and its tributaries

Each spot includes lat/lon, depth range, structure notes (point, rip-rap, shoal,
drop-off, bridge piling, etc.), and the relevant NOAA chart (12266 Choptank,
12270 Eastern Bay/Poplar).

## Data sources

| Source | Used for |
|---|---|
| **NOAA Tides & Currents API** | High/low tide predictions for each spot's nearest station (Cambridge, Oxford, Knapps Narrows, Cook Point) |
| **NOAA National Weather Service API** | Hourly forecast — wind speed, sky cover, air temperature |
| **Astronomical calculation** | Sunrise/sunset (NOAA solar position formula), moon phase (synodic-month math) |
| **MD DNR weekly fishing report** | Most recent report scraped from news.maryland.gov and displayed for ground-truth context |
| **NOAA Charts 12266 & 12270** | Referenced when curating spot bathymetry and structure notes |

## Scoring criteria and weights

Each spot is scored at four candidate windows per day (dawn, mid-morning,
mid-afternoon, dusk). Each criterion produces a 0–100 sub-score, then the
sub-scores are combined as a weighted average:

| Weight | Criterion | What earns a high score |
|---|---|---|
| **25%** | **Tide phase (timing)** | 1–2 hours from a tide change (moving water) = 100. Slack tide (±30 min of high/low) = 15. |
| **20%** | **Cloud cover** | Especially valuable mid-day — overcast extends the low-light bite window. |
| **20%** | **Moon phase** | Spring tides (within 3 days of new or full moon) = 90. Otherwise 60. |
| **15%** | **Structure** | Spots with a defined drop-off = 80. Open-water spots = 60. |
| **10%** | **Current strength (magnitude)** | Sinusoidal model from tide cycle position × tidal range. Slack = 0. Mid-cycle on a 3 ft+ tidal swing = 100. Higher current is better. |
| **5%** | **Light level** | Within 30 min of sunrise/sunset = 100. Drops sharply with distance from dawn/dusk windows. |
| **5%** | **Wind / surface chop** | 5–15 mph = 100 (ideal ripple). Slick calm <3 mph = 50. 21–25 mph = 30. >25 mph = 10. |

**Note on tide vs current.** These are two complementary criteria. *Tide phase* rewards the right TIMING — being 1–2 hours from a high or low (the rule-of-thumb "moving water" window). *Current strength* rewards the right MAGNITUDE — a spring tide pushes more water through the same cycle than a neap tide, even at the same number of minutes from slack. Both contribute to "moving water = feeding fish."

Weights are tunable in `services/scorer.py` (the `WEIGHTS` dictionary) to reflect
what you observe on the water.

## Lure-selection logic

Two recommendations per window — a **Primary** (best fit for conditions) and an
**Alternative** (the other technique, in case the primary isn't producing).

**Technique-choice rules:**

- Wind ≥ 22 mph **or** water temp < 55 °F → **Swimbait primary** (topwater impractical or fish unwilling to chase)
- Bright mid-day with clear sky → **Swimbait primary** (fish are deeper)
- Otherwise → **Topwater primary**, swimbait alternative

**Within topwater:** walking bait (calm, dawn/dusk), popper (chop), pencil popper
(15+ mph wind), wake bait (slick calm mid-day). Color by sky/clarity: chartreuse
(stained), bone/white (overcast), bone with red head (dawn/dusk), chrome/bunker
(bright clear).

**Within swimbait:** soft plastic shad on jighead (default), paddle-tail shad
(stained or cold water), hard swimming plug (heavy wind). Color by conditions:
chartreuse (stained), smoke purple (cold), pearl white (overcast), pearl + silver
flash (bright clear). Jighead weight scales with wind (3/8 oz calm → 1 oz heavy
chop). Size scales with season (3–5" spring, 5–7" fall).

## Honest limitations

- The scoring is a **heuristic** that codifies conventional wisdom — not a trained
  prediction model. It reflects what experienced anglers say works, not measured
  catch outcomes.
- **Spot coordinates are approximate** and intended for general guidance. Always
  verify against NOAA charts before navigating.
- Free-tier hosting means the **first visit each day takes ~30 seconds** to wake
  the server; subsequent visits are fast.
- Maryland fishing regulations apply (seasons, slot limits, license) — check
  [dnr.maryland.gov](https://dnr.maryland.gov) before fishing.
