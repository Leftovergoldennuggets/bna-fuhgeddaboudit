"""
05_generate_incidents.py — Extract serious crash incidents for the website
==========================================================================
Filters the merged dataset for crashes with moderate, serious, or fatal
injuries and outputs them as a JSON file for the scrollytelling visualization.

"Serious" here means the "Highest Injury Severity Alleged" column contains
"moderate", "serious", or "fatal". We exclude "minor" injuries and
property-damage-only crashes.

Inputs:
  - data/processed/waymo_merged.csv

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
import numpy as np

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import PROCESSED_MERGED, WEB_SERIOUS_INCIDENTS, CITIES, GEOCODE_CACHE


def is_serious_injury(severity_value):
    """
    Check if an injury severity level counts as "serious" for our analysis.

    We include:
      - Moderate injuries
      - Serious injuries
      - Fatalities

    We exclude:
      - Minor injuries (with or without hospitalization)
      - No injuries / property damage only
      - Unknown severity

    Parameters:
        severity_value: The "Highest Injury Severity Alleged" column value

    Returns:
        bool: True if this is a moderate/serious/fatal injury
    """
    if pd.isna(severity_value):
        return False
    val_lower = str(severity_value).lower().strip()
    return "fatal" in val_lower or "serious" in val_lower or "moderate" in val_lower


def clean_narrative(narrative):
    """
    Clean up a crash narrative for display on the website.

    Removes redaction markers and limits length for readability.
    """
    if pd.isna(narrative) or str(narrative) == "nan":
        return "Narrative not available for this incident."
    narrative = str(narrative).strip()
    narrative = re.sub(r"\[XXX\]", "[REDACTED]", narrative)
    narrative = re.sub(r"\[MAY CONTAIN.*?\]", "", narrative)
    narrative = narrative.strip()
    if len(narrative) > 600:
        narrative = narrative[:600] + "..."
    return narrative


def clean_coordinate(val):
    """Clean a coordinate value, returning None if invalid."""
    if pd.isna(val):
        return None
    try:
        val_str = str(val).strip()
        if "PERSONALLY" in val_str.upper() or "[" in val_str or val_str == "":
            return None
        return float(val_str)
    except (ValueError, TypeError):
        return None


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

    # Load merged dataset
    print("Loading merged dataset...")
    df = pd.read_csv(PROCESSED_MERGED)
    print(f"  Total records: {len(df)}")

    # Filter for serious injuries only
    severity_col = "Highest Injury Severity Alleged"
    df["_is_serious"] = df[severity_col].apply(is_serious_injury)
    serious_df = df[df["_is_serious"]].copy()

    print(f"  Moderate/serious/fatal injuries: {len(serious_df)}")
    if severity_col in serious_df.columns:
        print(f"  Severity breakdown:")
        for severity, count in serious_df[severity_col].value_counts().items():
            print(f"    {severity}: {count}")

    # Load the geocode cache (created by step 04_generate_map_data.py)
    geocode_cache = {}
    if os.path.exists(GEOCODE_CACHE):
        with open(GEOCODE_CACHE, "r") as f:
            geocode_cache = json.load(f)
        print(f"  Loaded geocode cache: {len(geocode_cache)} entries")
    else:
        print("  WARNING: No geocode cache found. Run step 04 first for accurate locations.")

    # Use fixed seed for reproducible fallback coordinate approximation
    random.seed(42)

    # Build incident records
    incidents = []
    geocoded_count = 0
    estimated_count = 0

    for _, row in serious_df.iterrows():
        # Get coordinates from NHTSA (almost always redacted)
        lat = clean_coordinate(row.get("Latitude"))
        lon = clean_coordinate(row.get("Longitude"))

        city_code = str(row.get("Location", "")).upper().replace(" ", "_")
        is_estimated = False

        if lat is None or lon is None:
            # Try geocode cache first (address → real coordinates)
            address = str(row.get("Location Address / Description", ""))
            cache_key = f"{address}|{city_code}"
            cached = geocode_cache.get(cache_key)

            if cached is not None:
                lat = cached["lat"]
                lon = cached["lon"]
                geocoded_count += 1
            elif city_code in CITIES:
                # Fall back to city center with random jitter
                city_info = CITIES[city_code]
                lat = city_info["lat"] + (random.random() - 0.5) * 0.04
                lon = city_info["lon"] + (random.random() - 0.5) * 0.04
                is_estimated = True
                estimated_count += 1
            else:
                continue

        # Get crash party (who/what the Waymo vehicle hit)
        crash_with = str(row.get("Crash With", ""))
        if pd.isna(row.get("Crash With")) or crash_with in ("", "nan"):
            crash_party = "Unknown"
        else:
            crash_party = CRASH_PARTY_MAP.get(crash_with, crash_with)

        # Get date and time
        date = str(row.get("Incident Date", ""))
        if pd.isna(row.get("Incident Date")):
            date_nhtsa = row.get("Incident Date_nhtsa")
            date = str(date_nhtsa) if pd.notna(date_nhtsa) else "Date not available"

        time_val = str(row.get("Incident Time (24:00)", ""))
        if pd.isna(row.get("Incident Time (24:00)")):
            time_val = "Time not available"

        # Get address
        address = str(row.get("Location Address / Description", ""))
        if pd.isna(row.get("Location Address / Description")):
            addr_fallback = row.get("Address")
            address = str(addr_fallback) if pd.notna(addr_fallback) else "Location details not available"

        incident = {
            "id": len(incidents) + 1,
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "city": city_code.replace("_", " ").title(),
            "date": date,
            "time": time_val,
            "crash_party": crash_party,
            "severity": str(row.get(severity_col, "")),
            "crash_type": str(row.get("Crash Type", "Unknown")),
            "address": address,
            "narrative": clean_narrative(row.get("Narrative")),
            "is_estimated_location": is_estimated,
        }
        incidents.append(incident)

    print(f"  Total incidents extracted: {len(incidents)}")
    print(f"    Geocoded (accurate): {geocoded_count}")
    print(f"    Estimated (city center): {estimated_count}")

    # Group by city
    sf_incidents = [i for i in incidents if "san francisco" in i["city"].lower()]
    print(f"  San Francisco incidents: {len(sf_incidents)}")

    # City-level counts for the map overview
    city_data = {}
    for city_code, city_info in CITIES.items():
        city_name = city_info["name"]
        count = len([i for i in incidents if city_name.lower() in i["city"].lower()])
        if count > 0:
            city_data[city_name] = {
                "lat": city_info["lat"],
                "lon": city_info["lon"],
                "count": count,
            }

    # Build output JSON
    output = {
        "sf_incidents": sf_incidents,
        "all_incidents": incidents,
        "city_data": city_data,
        "total_serious": len(incidents),
    }

    # Save
    print()
    print("Saving serious_incidents.json...")
    os.makedirs(os.path.dirname(WEB_SERIOUS_INCIDENTS), exist_ok=True)
    with open(WEB_SERIOUS_INCIDENTS, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Saved: {WEB_SERIOUS_INCIDENTS}")


if __name__ == "__main__":
    main()
