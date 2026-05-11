"""
One-time data prep: fetch shallow-water obstructions, wrecks, rocks, and
daymarks from NOAA's Electronic Navigational Chart REST API and save them
to data/obstructions.json.

Run when you want to refresh the data (NOAA updates ENCs weekly on Fridays):
    cd ~/striper-app
    ./venv/bin/python scripts/fetch_obstructions.py

The committed JSON is shipped with the app, so production doesn't have to
hit NOAA on every page load.
"""
from __future__ import annotations
import json
from pathlib import Path
import requests

# Bounding box wrapping all our fishing spots — slightly buffered.
# Order: (xmin/west_lon, ymin/south_lat, xmax/east_lon, ymax/north_lat)
BBOX = (-76.50, 38.45, -75.90, 38.85)

# 15 ft = 4.572 m. NOAA ENC stores depth (VALSOU) in meters.
MAX_DEPTH_M = 4.572

ENC_BASE = "https://gis.charttools.noaa.gov/arcgis/rest/services/encdirect"

# Each tuple = (scale band, layer id, our feature-type label).
# We pull both coastal and approach scales; the union catches anything
# only present at one scale. The script dedupes by lat/lon afterwards.
SOURCES = [
    ("enc_coastal", 30, "obstruction"),
    ("enc_coastal", 31, "rock"),
    ("enc_coastal", 33, "wreck"),
    ("enc_coastal", 8,  "daymark"),
    ("enc_approach", 36, "obstruction"),
    ("enc_approach", 37, "rock"),
    ("enc_approach", 39, "wreck"),
    ("enc_approach", 11, "daymark"),
]


def query_layer(band: str, layer_id: int, where: str) -> list:
    url = f"{ENC_BASE}/{band}/MapServer/{layer_id}/query"
    params = {
        "where": where,
        "geometry": f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("features", [])


def normalize(feature: dict, feature_type: str, band: str) -> dict:
    a = feature.get("attributes", {})
    g = feature.get("geometry", {})
    val = a.get("VALSOU")
    depth_ft = round(val * 3.281, 1) if val is not None else None

    obj = (a.get("OBJNAM") or "").strip()
    info = (a.get("INFORM") or "").strip()
    # CATOBS for obstructions, CATWRK for wrecks, CATLAM/etc. for others
    cat = (a.get("CATOBS") or a.get("CATWRK") or "").strip()
    natsur = (a.get("NATSUR") or "").strip()

    return {
        "lat": round(g.get("y"), 6),
        "lon": round(g.get("x"), 6),
        "depth_ft": depth_ft,
        "type": feature_type,
        "category": cat or None,
        "object_name": obj or None,
        "nature_of_surface": natsur or None,
        "info": info or None,
        "source_scale": band.replace("enc_", ""),
    }


def main():
    print(f"Fetching obstructions in bbox {BBOX} with depth ≤ 15ft (or unknown)…")
    print()

    out, seen = [], set()
    for band, layer_id, ftype in SOURCES:
        # Daymarks: include all (they're markers indicating shallow water)
        # Other types: filter by depth or include if depth is unknown
        if ftype == "daymark":
            where = "1=1"
        else:
            where = f"VALSOU<={MAX_DEPTH_M} OR VALSOU IS NULL"
        try:
            feats = query_layer(band, layer_id, where)
        except Exception as e:
            print(f"  WARN: {band}/{layer_id} ({ftype}) failed: {e}")
            continue

        new = 0
        for f in feats:
            obs = normalize(f, ftype, band)
            # Dedup across scale bands by rounded coordinates + type
            key = (round(obs["lat"], 5), round(obs["lon"], 5), ftype)
            if key in seen:
                continue
            seen.add(key)
            out.append(obs)
            new += 1
        print(f"  {band}/layer{layer_id} ({ftype}): {len(feats)} features  ({new} new after dedup)")

    out.sort(key=lambda x: (x["type"], x["lat"], x["lon"]))

    output_path = Path(__file__).parent.parent / "data" / "obstructions.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "max_depth_ft": 15,
            "source": "NOAA Electronic Navigational Charts (ENC)",
            "fetched_from": ENC_BASE,
            "count": len(out),
            "obstructions": out,
        }, f, indent=2)

    print()
    print(f"Wrote {len(out)} unique features → {output_path}")
    print(f"Breakdown by type:")
    from collections import Counter
    for t, n in Counter(o["type"] for o in out).most_common():
        print(f"  {t}: {n}")


if __name__ == "__main__":
    main()
