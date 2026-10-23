"""
build_zip_reference.py — One-off builder for data/static/zip_reference.json
==========================================================================
Downloads the U.S. Census Bureau's ZCTA (ZIP Code Tabulation Area)
gazetteer and keeps, for every ZCTA in a state where Waymo has a metro,
its internal point and an "equivalent radius" (the radius of a circle with
the ZCTA's land area). Step 04 uses it to check that a geocoded crash
actually lands inside the ZIP code Waymo reported for it.

Re-run only when a metro in a new state is added to config.CITIES:
  python pipeline/tools/build_zip_reference.py
==========================================================================
"""

import io
import json
import math
import os
import sys
import zipfile

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pipeline.config import CITIES, STATIC_ZIP_REFERENCE

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_Gaz_zcta_national.zip"
)

# ZCTAs carry no state, so keep those whose first three digits fall in the
# ZIP prefix ranges of the states we need (USPS assignment).
STATE_ZIP_PREFIXES = {
    "AZ": [(850, 865)], "CA": [(900, 961)], "CO": [(800, 816)],
    "DC": [(200, 205), (569, 569)], "FL": [(320, 349)], "GA": [(300, 319), (398, 399)],
    "MI": [(480, 499)], "NV": [(889, 898)],
    "PA": [(150, 196)], "TN": [(370, 385)], "TX": [(750, 799), (885, 885)],
}


def main():
    states = {info["state"] for info in CITIES.values()}
    missing = states - set(STATE_ZIP_PREFIXES)
    if missing:
        raise SystemExit(f"Add ZIP prefix ranges for {sorted(missing)} to STATE_ZIP_PREFIXES")
    ranges = [r for s in states for r in STATE_ZIP_PREFIXES[s]]

    print(f"Downloading {GAZETTEER_URL} ...")
    resp = requests.get(GAZETTEER_URL, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        text = zf.read(zf.namelist()[0]).decode("latin-1")

    lines = text.splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    reference = {}
    for line in lines[1:]:
        row = dict(zip(header, (v.strip() for v in line.split("\t"))))
        zcta = row["GEOID"]
        prefix = int(zcta[:3])
        if not any(lo <= prefix <= hi for lo, hi in ranges):
            continue
        land_km2 = float(row["ALAND"]) / 1e6
        reference[zcta] = [
            round(float(row["INTPTLAT"]), 5),
            round(float(row["INTPTLONG"]), 5),
            round(max(math.sqrt(land_km2 / math.pi), 0.3), 2),  # equivalent radius, km
        ]

    output = {
        "description": "ZCTA internal point [lat, lon] and equivalent radius (km) from the U.S. Census Bureau 2024 ZCTA gazetteer, for states with Waymo metros. Built by pipeline/tools/build_zip_reference.py.",
        "source_url": GAZETTEER_URL,
        "zips": reference,
    }
    with open(STATIC_ZIP_REFERENCE, "w") as f:
        json.dump(output, f, separators=(",", ":"))
    print(f"Saved {len(reference)} ZCTAs to {STATIC_ZIP_REFERENCE}")


if __name__ == "__main__":
    main()
