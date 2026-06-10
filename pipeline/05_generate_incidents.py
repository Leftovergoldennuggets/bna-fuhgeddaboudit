"""
05_generate_incidents.py — Extract serious crash incidents for the website
==========================================================================
Filters the merged dataset for DRIVERLESS crashes with moderate, serious,
or fatal injuries and outputs them as JSON for the scrollytelling map.

"Serious" here means the NHTSA "Highest Injury Severity Alleged" column
contains "moderate", "serious", or "fatal". Minor injuries and
property-damage-only crashes are excluded. Supervised-testing crashes are
excluded from this view (they are visible in the Explore section).

Inputs:
  - data/processed/waymo_merged.csv
  - data/web/geocode_cache.json (from step 04)

Outputs:
  - data/web/serious_incidents.json

Usage:
  python pipeline/05_generate_incidents.py
==========================================================================
"""

import os
import sys
import json
import re
import random

import pandas as pd

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    PROCESSED_MERGED, WEB_SERIOUS_INCIDENTS, CITIES, GEOCODE_CACHE,
)
from pipeline.utils import (
    is_moderate_plus, clean_coordinate, normalize_place, normalize_state,
    geocode_cache_key,
)


def clean_narrative(narrative):
    """Clean up a crash narrative for display on the website."""
    if pd.isna(narrative) or str(narrative) == "nan":
        return "Narrative not available for this incident."
    narrative = str(narrative).strip()
    narrative = re.sub(r"\[XXX\]", "[REDACTED]", narrative)
    narrative = re.sub(r"\[MAY CONTAIN.*?\]", "", narrative)
    return narrative.strip()


def format_incident_date(date_value, precision):
    """Format a date respecting its precision ("March 14, 2025" / "March 2026")."""
    ts = pd.to_datetime(date_value, errors="coerce")
    if pd.isna(ts):
        return "Date not available"
    if precision == "month":
        return ts.strftime("%B %Y")
    return ts.strftime("%B %-d, %Y") if os.name != "nt" else ts.strftime("%B %d, %Y")


# Mapping from NHTSA crash party names to cleaner display names
CRASH_PARTY_MAP = {
    "Passenger Car": "Vehicle (Passenger Car)",
    "SUV": "Vehicle (SUV)",
    "Pickup Truck": "Vehicle (Pickup Truck)",
    "Heavy Truck": "Vehicle (Heavy Truck)",
    "Van": "Vehicle (Van)",
    "Bus": "Vehicle (Bus)",
    "Motorcycle": "Motorcyclist",
    "Non-Motorist: Cyclist": "Cyclist",
    "Non-Motorist: Pedestrian": "Pedestrian",
    "Non-Motorist: Scooter - Skateboard": "Scooter/Skateboard",
    "Non-Motorist: Other": "Other Non-Motorist",
    "Animal": "Animal",
    "Other Fixed Object": "Fixed Object",
    "Pole / Tree": "Pole/Tree",
    "First Responder Vehicle": "First Responder Vehicle",
}


def main():
    """Extract serious incidents and save as JSON."""
    print("=" * 60)
    print("STEP 5: EXTRACTING SERIOUS INCIDENTS")
    print("=" * 60)
    print()

    print("Loading merged dataset...")
    df = pd.read_csv(PROCESSED_MERGED, low_memory=False)
    print(f"  Total records: {len(df)}")

    df = df[df["operation_type"] == "driverless"]
    severity_col = "Highest Injury Severity Alleged"
    serious_df = df[df[severity_col].apply(is_moderate_plus)].copy()

    print(f"  Moderate/serious/fatal injuries (driverless): {len(serious_df)}")
    for severity, count in serious_df[severity_col].value_counts().items():
        print(f"    {severity}: {count}")

    geocode_cache = {}
    if os.path.exists(GEOCODE_CACHE):
        with open(GEOCODE_CACHE, "r") as f:
            geocode_cache = json.load(f)
        print(f"  Loaded geocode cache: {len(geocode_cache)} entries")
    else:
        print("  WARNING: No geocode cache found. Run step 04 first for accurate locations.")

    random.seed(42)

    incidents = []
    geocoded_count = estimated_count = 0

    for _, row in serious_df.iterrows():
        lat = clean_coordinate(row.get("Latitude"))
        lon = clean_coordinate(row.get("Longitude"))
        city_code = str(row.get("Location", ""))
        is_estimated = False

        if lat is None or lon is None:
            # 1) street-level geocode from cache
            address = row.get("Location Address / Description")
            cached = None
            if pd.notna(address) and str(address).strip():
                cached = geocode_cache.get(geocode_cache_key(
                    address, row.get("City"), row.get("State"), city_code))
            if cached is not None:
                lat, lon = cached["lat"], cached["lon"]
                geocoded_count += 1
            else:
                # 2) city centroid from cache
                city = normalize_place(row.get("City"))
                state = normalize_state(row.get("State"))
                city_hit = geocode_cache.get(f"__city__{city}|{state}") if city and state else None
                if city_hit is not None:
                    lat = city_hit["lat"] + (random.random() - 0.5) * 0.01
                    lon = city_hit["lon"] + (random.random() - 0.5) * 0.01
                    is_estimated = True
                    estimated_count += 1
                elif city_code in CITIES:
                    # 3) metro center fallback
                    info = CITIES[city_code]
                    lat = info["lat"] + (random.random() - 0.5) * 0.04
                    lon = info["lon"] + (random.random() - 0.5) * 0.04
                    is_estimated = True
                    estimated_count += 1
                else:
                    continue

        crash_with_raw = row.get("Crash With")
        if pd.isna(crash_with_raw) or str(crash_with_raw).strip() in ("", "nan"):
            crash_party = "Unknown"
        else:
            crash_party = CRASH_PARTY_MAP.get(str(crash_with_raw).strip(), str(crash_with_raw).strip())

        time_val = row.get("Incident Time (24:00)")
        time_val = str(time_val) if pd.notna(time_val) else "Time not available"

        address = row.get("Location Address / Description")
        if pd.notna(address) and str(address).strip():
            address = str(address).strip()
        else:
            city = normalize_place(row.get("City"))
            address = f"{city} (exact location pending Waymo data)" if city else "Location details not available"

        city_display = CITIES.get(city_code, {}).get("name", "Other")

        incident = {
            "id": len(incidents) + 1,
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "city": city_display,
            "date": format_incident_date(row.get("incident_date"), row.get("date_precision")),
            "time": time_val,
            "crash_party": crash_party,
            "severity": str(row.get(severity_col, "")),
            "crash_type": str(row.get("Crash Type")) if pd.notna(row.get("Crash Type")) else "Pending classification",
            "address": address,
            "narrative": clean_narrative(row.get("Narrative")),
            "is_estimated_location": is_estimated,
            "in_hub": bool(row.get("in_hub")),
        }
        incidents.append(incident)

    print(f"  Total incidents extracted: {len(incidents)}")
    print(f"    Geocoded (street-level): {geocoded_count}")
    print(f"    Estimated (city/metro):  {estimated_count}")

    # Jitter exact-duplicate coordinates so stacked markers stay clickable
    seen_coords = {}
    for inc in incidents:
        key = (inc["lat"], inc["lon"])
        if key in seen_coords:
            offset_idx = seen_coords[key]
            inc["lat"] = round(inc["lat"] + 0.00012 * offset_idx, 6)
            inc["lon"] = round(inc["lon"] + 0.00012 * offset_idx, 6)
            seen_coords[key] += 1
        else:
            seen_coords[key] = 1

    sf_incidents = [i for i in incidents if "san francisco" in i["city"].lower()]
    print(f"  San Francisco incidents: {len(sf_incidents)}")

    city_data = {}
    for code, info in CITIES.items():
        count = len([i for i in incidents if i["city"] == info["name"]])
        if count > 0:
            city_data[info["name"]] = {
                "lat": info["lat"],
                "lon": info["lon"],
                "count": count,
            }

    output = {
        "sf_incidents": sf_incidents,
        "all_incidents": incidents,
        "city_data": city_data,
        "total_serious": len(incidents),
    }

    print()
    print("Saving serious_incidents.json...")
    os.makedirs(os.path.dirname(WEB_SERIOUS_INCIDENTS), exist_ok=True)
    with open(WEB_SERIOUS_INCIDENTS, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Saved: {WEB_SERIOUS_INCIDENTS}")


if __name__ == "__main__":
    main()
