# Striper Topwater Forecast

A local web app that ranks the best windows for **topwater casting for striped bass**
in the Choptank River, Little Choptank River, and Chesapeake Bay between
Poplar Island and the Little Choptank, for the next 7 days.

For each window it tells you **where, when, what lure, what color**, and **why**.

## What it uses

- **NOAA Tides & Currents** — high/low tide predictions per station.
- **NOAA Weather Service** — hourly wind, sky, temperature forecast.
- **Moon phase** — calculated from a reference new moon.
- **Sunrise / sunset** — calculated from lat/lon and date.
- **MD DNR Weekly Fishing Report** — most recent post is shown for context.
- **Curated spot list** (`data/spots.json`) — derived from NOAA charts 12266 & 12270.

## Run it

```bash
cd ~/striper-app
./venv/bin/python app.py
```

Then open <http://localhost:8000> in your browser.

The first page-load takes ~30–60 seconds because it fetches tides and weather
for each unique station/area. Reloading the page re-fetches.

Stop the server with **Ctrl+C** in the Terminal.

## Tuning it

Almost everything is in plain text files you can edit:

- **`data/spots.json`** — add, remove, edit fishing spots.
- **`services/scorer.py`** — weight at top of file (`WEIGHTS = {...}`).
  Increase `tide` if you find tides matter most for you, etc.
- **`services/lure.py`** — rules for picking lure type and color.

Restart the server (Ctrl+C, then run again) after editing Python.
For JSON edits, just refresh the browser.

## What this app is NOT

- Not a substitute for a NOAA chart on the water. Verify coordinates.
- Not a precise prediction — it's a ranked heuristic based on conventional
  wisdom. Always cross-check with the MD DNR weekly report.
- Not a license. Maryland fishing rules and seasons apply — check
  [DNR regulations](https://dnr.maryland.gov/fisheries/Pages/regulations/index.aspx)
  before fishing.
