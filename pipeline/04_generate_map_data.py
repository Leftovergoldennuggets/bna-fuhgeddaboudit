"""
04_generate_map_data.py — Generate crash_data.json for the interactive map
==========================================================================
Creates a JSON array of individual crash records for the Leaflet map.
Each record has coordinates, time info, crash type, and city — everything
the map needs to display markers and support filtering.

GEOCODING: We use the "Location Address / Description" column from NHTSA
(e.g., "Florida Street near 24th Street") and geocode it via OpenStreetMap's
Nominatim service. Results are cached in geocode_cache.json so we only
need to geocode each unique address once. If geocoding fails for an address,
we fall back to a random offset from the city center.

The first run takes ~15-20 minutes (1 request/second rate limit).
Subsequent runs are near-instant because cached results are reused.

Inputs:
  - data/processed/waymo_merged.csv

Outputs:
  - data/web/crash_data.json
  - data/web/geocode_cache.json (address → lat/lon cache)

Usage:
  python pipeline/04_generate_map_data.py
==========================================================================
"""

import os
import sys
import json
import re
import time

import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    PROCESSED_MERGED, WEB_CRASH_DATA, CITIES, TIME_PERIODS,
    LOCATION_PATTERNS, GEOCODE_CACHE,
)


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def parse_time(time_str):
    """Parse time string into (hour, minute). Returns (None, None) on failure."""
    if pd.isna(time_str) or str(time_str).strip() == "":
        return None, None
    try:
        time_str = str(time_str).strip()
        if ":" in time_str:
            parts = time_str.split(":")
            hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        elif len(time_str) == 4 and time_str.isdigit():
            hour, minute = int(time_str[:2]), int(time_str[2:])
        else:
            return None, None
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (ValueError, IndexError):
        pass
    return None, None


def categorize_time_period(hour):
    """Assign a named time period to an hour (0-23)."""
    if hour is None or pd.isna(hour):
        return "Unknown"
    hour = int(hour)
    for period_name, (start, end) in TIME_PERIODS.items():
        if start < end:
            if start <= hour < end:
                return period_name
        else:
            if hour >= start or hour < end:
                return period_name
    return "Unknown"


def extract_location_type(row):
    """Determine crash location type from narrative text."""
    text = ""
    for col in ["Narrative", "Location Address / Description", "Address"]:
        val = row.get(col)
        if pd.notna(val):
            text += str(val).lower() + " "
    if not text.strip():
        return "Other/Unknown"
    for loc_type, patterns in LOCATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return loc_type
    if re.search(r"\b(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|way|lane|ln)\b", text, re.IGNORECASE):
        return "Street/Road"
    return "Other/Unknown"


def clean_coordinate(val):
    """
    Clean a latitude or longitude value from the NHTSA data.

    Some coordinate fields contain "[PERSONALLY IDENTIFIABLE]" or other
    non-numeric text instead of actual coordinates. We return None for those.
    """
    if pd.isna(val):
        return None
    try:
        val_str = str(val).strip()
        if "PERSONALLY" in val_str.upper() or val_str == "" or "[" in val_str:
            return None
        return float(val_str)
    except (ValueError, TypeError):
        return None


def parse_date(date_str):
    """Parse a date string into a pandas Timestamp."""
    if pd.isna(date_str):
        return None
    try:
        date_str = str(date_str).strip()
        for fmt in ["%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y"]:
            try:
                return pd.to_datetime(date_str, format=fmt)
            except (ValueError, TypeError):
                continue
        return pd.to_datetime(date_str)
    except (ValueError, TypeError):
        return None


# ===========================================================================
# GEOCODING FUNCTIONS
# ===========================================================================

def load_geocode_cache():
    """
    Load the geocode cache from disk.

    The cache maps "address|city" strings to {"lat": ..., "lon": ...} dicts.
    If geocoding previously failed for an address, it's stored as None so we
    don't keep retrying the same bad address.
    """
    if os.path.exists(GEOCODE_CACHE):
        with open(GEOCODE_CACHE, "r") as f:
            return json.load(f)
    return {}


def save_geocode_cache(cache):
    """Save the geocode cache to disk."""
    os.makedirs(os.path.dirname(GEOCODE_CACHE), exist_ok=True)
    with open(GEOCODE_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def clean_address(address):
    """
    Clean an NHTSA address string before geocoding.

    Strips noise like "parking lot located near..." and expands abbreviations
    like "N." → "North" so geocoders can parse them better.

    Returns the cleaned address string (without city/state appended).
    """
    if pd.isna(address) or str(address).strip() == "":
        return ""
    address = str(address).strip()

    # Strip descriptive preambles that confuse geocoders
    # e.g., "parking lot located near Main Street" → "Main Street"
    preambles = [
        r"^parking\s+lot\s+(located\s+)?(near|at|on|of|entrance\s+of)\s+",
        r"^parking\s+lot\s+",
        r"^driveway\s+(of|near|at)\s+",
        r"^entrance\s+(of|to|near)\s+",
        r"^exit\s+(of|from|near)\s+",
        r"^alley\s+(near|behind|off)\s+",
    ]
    for pattern in preambles:
        address = re.sub(pattern, "", address, flags=re.IGNORECASE)

    # Expand directional abbreviations — Nominatim handles full words better
    # e.g., "E. Broadway Road" → "East Broadway Road"
    direction_map = {
        r"\bN\.?\s": "North ",
        r"\bS\.?\s": "South ",
        r"\bE\.?\s": "East ",
        r"\bW\.?\s": "West ",
        r"\bNE\.?\s": "Northeast ",
        r"\bNW\.?\s": "Northwest ",
        r"\bSE\.?\s": "Southeast ",
        r"\bSW\.?\s": "Southwest ",
    }
    for abbr, full in direction_map.items():
        address = re.sub(abbr, full, address)

    return address.strip()


def split_intersection(address):
    """
    Split an intersection-style address into its two street parts.

    NHTSA uses formats like:
      "Florida Street near 24th Street"
      "Kansas Street at 23rd Street"
      "Main Street and Broadway"
      "Elm Street between Oak and Pine"

    Returns (street_a, street_b) or (address, None) if not an intersection.
    """
    # Try splitting on "near", "at", "and", "&"
    for separator in [r"\s+near\s+", r"\s+at\s+", r"\s+and\s+", r"\s*&\s*"]:
        parts = re.split(separator, address, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()

    # "X between Y and Z" — extract X and Y
    match = re.match(r"(.+?)\s+between\s+(.+?)(?:\s+and\s+.+)?$", address, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # Not an intersection — return the whole address
    return address, None


def build_geocode_queries(address, city_code):
    """
    Build MULTIPLE geocoding queries to try for a single address.

    Instead of one query that may fail, we generate up to 3 strategies:
      1. Full intersection: "Street A & Street B, City, State"
      2. First street only: "Street A, City, State"
      3. Second street only: "Street B, City, State"

    For non-intersection addresses (like "3939 E Campbell Avenue"), we
    just return the address with city/state appended.

    Returns a list of query strings to try in order.
    """
    cleaned = clean_address(address)
    if not cleaned:
        return []

    city_info = CITIES.get(city_code, {})
    city_name = city_info.get("name", "")
    state = city_info.get("state", "")
    suffix = f", {city_name}, {state}"

    street_a, street_b = split_intersection(cleaned)

    queries = []

    if street_b:
        # Strategy 1: intersection format "Street A & Street B, City, State"
        queries.append(f"{street_a} & {street_b}{suffix}")
        # Strategy 2: just the first street (still gets us to the right block)
        queries.append(f"{street_a}{suffix}")
        # Strategy 3: just the second street (backup)
        queries.append(f"{street_b}{suffix}")
    else:
        # Not an intersection — just one query
        queries.append(f"{cleaned}{suffix}")

    return queries


def try_geocode(geocoder, queries, city_code):
    """
    Try each query in order and return the first valid result.

    "Valid" means Nominatim returned coordinates within 0.5° (~30 miles)
    of the expected city center. This catches cases where Nominatim
    finds a match in the wrong state or country.

    Returns {"lat": ..., "lon": ...} on success, or None on failure.
    Each query attempt takes ~1 second due to rate limiting.
    """
    city_info = CITIES.get(city_code, {})
    expected_lat = city_info.get("lat", 0)
    expected_lon = city_info.get("lon", 0)

    for query in queries:
        try:
            result = geocoder.geocode(query)
            time.sleep(1.0)  # Rate limit: 1 request/second (Nominatim policy)

            if result:
                lat, lon = result.latitude, result.longitude
                # Sanity check: result must be near the expected city
                if abs(lat - expected_lat) < 0.5 and abs(lon - expected_lon) < 0.5:
                    return {"lat": round(lat, 6), "lon": round(lon, 6)}
                # If too far away, try the next query
        except (GeocoderTimedOut, GeocoderServiceError):
            time.sleep(1.0)
            continue

    return None


def geocode_addresses(df, cache):
    """
    Geocode all addresses in the dataframe, using multiple query strategies.

    Uses OpenStreetMap Nominatim (free, no API key needed).
    For each address, tries up to 3 query formats before giving up.
    Results are cached so subsequent runs are instant.

    Returns the updated cache dict.
    """
    # Set up the geocoder with a descriptive user agent (required by Nominatim)
    geocoder = Nominatim(
        user_agent="waymo-crash-analysis-stanford-comm277t",
        timeout=10,
    )

    # Build list of unique addresses that need geocoding
    # (skip addresses that already have a successful cached result)
    to_geocode = []
    seen_keys = set()
    for _, row in df.iterrows():
        address = row.get("Location Address / Description", "")
        city_code = row.get("Location", "")
        cache_key = f"{address}|{city_code}"

        # Skip if already successfully cached (non-null) or already in our list
        if cache_key in seen_keys:
            continue
        seen_keys.add(cache_key)

        # Skip only SUCCESSFUL cache hits — retry previously failed ones (null)
        cached = cache.get(cache_key)
        if cached is not None:
            continue

        queries = build_geocode_queries(address, city_code)
        if queries:
            to_geocode.append((cache_key, queries, city_code))

    if not to_geocode:
        print("  All addresses already geocoded — no new lookups needed!")
        return cache

    # Estimate time: each address tries up to 3 queries (1 sec each)
    # but most will succeed or fail on the first 1-2 tries
    print(f"  Need to geocode {len(to_geocode)} addresses (retrying failures with new strategies)...")
    print(f"  Estimated time: {len(to_geocode) * 2 // 60}-{len(to_geocode) * 3 // 60} min")
    print(f"  (each address tries up to 3 query formats)")
    print()

    success = 0
    failed = 0
    total_queries = 0

    for i, (cache_key, queries, city_code) in enumerate(to_geocode):
        result = try_geocode(geocoder, queries, city_code)
        total_queries += min(len(queries), 3)

        if result:
            cache[cache_key] = result
            success += 1
        else:
            cache[cache_key] = None
            failed += 1

        # Progress update every 50 addresses
        if (i + 1) % 50 == 0:
            pct = round(success / (success + failed) * 100, 1) if (success + failed) > 0 else 0
            print(f"  Progress: {i + 1}/{len(to_geocode)} "
                  f"(success: {success}, failed: {failed}, rate: {pct}%)")

        # Save cache periodically (every 100) in case of interruption
        if (i + 1) % 100 == 0:
            save_geocode_cache(cache)

    pct = round(success / (success + failed) * 100, 1) if (success + failed) > 0 else 0
    print(f"  Geocoding complete: {success} succeeded, {failed} failed ({pct}% success)")
    print(f"  Total API queries made: {total_queries}")
    return cache


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    """Generate crash_data.json for the interactive map."""
    print("=" * 60)
    print("STEP 4: GENERATING MAP DATA")
    print("=" * 60)
    print()

    # Load merged dataset
    print("Loading merged dataset...")
    df = pd.read_csv(PROCESSED_MERGED)
    print(f"  Loaded {len(df)} rows")

    # Parse time data
    print("Parsing time data...")
    df["_hour"], df["_minute"] = zip(*df["Incident Time (24:00)"].apply(parse_time))
    df_time = df[df["_hour"].notna()].copy()
    df_time["_hour"] = df_time["_hour"].astype(int)
    print(f"  Rows with valid time: {len(df_time)}")

    # Parse dates and convert to proper datetime
    df_time["_date"] = pd.to_datetime(df_time["Incident Date"].apply(parse_date))
    has_date = df_time["_date"].notna()
    df_time["_day_of_week"] = df_time["_date"].dt.day_name().where(has_date, "Unknown")
    df_time["_day_num"] = df_time["_date"].dt.dayofweek.where(has_date)
    df_time["_is_weekend"] = df_time["_date"].dt.dayofweek.isin([5, 6]).where(has_date, False)

    # Add time period and location type
    df_time["_time_period"] = df_time["_hour"].apply(categorize_time_period)
    df_time["_location_type"] = df_time.apply(extract_location_type, axis=1)

    # Clean NHTSA coordinates (almost always redacted, but check anyway)
    print("Cleaning coordinates...")
    df_time["_lat"] = df_time["Latitude"].apply(clean_coordinate)
    df_time["_lon"] = df_time["Longitude"].apply(clean_coordinate)

    # -----------------------------------------------------------------------
    # GEOCODE addresses for accurate map markers
    # -----------------------------------------------------------------------
    print()
    print("Geocoding addresses...")
    cache = load_geocode_cache()
    cache_size_before = len(cache)
    cache = geocode_addresses(df_time, cache)

    # Save the updated cache
    save_geocode_cache(cache)
    new_entries = len(cache) - cache_size_before
    if new_entries > 0:
        print(f"  Cache updated: {new_entries} new entries (total: {len(cache)})")
    print()

    # Use a fixed random seed for reproducible fallback jitter
    rng = np.random.default_rng(seed=42)

    # Build the JSON array
    print("Building JSON records...")
    map_data = []
    coords_geocoded = 0
    coords_nhtsa = 0
    coords_estimated = 0

    for _, row in df_time.iterrows():
        lat = row["_lat"]
        lon = row["_lon"]
        is_estimated = False

        # Priority 1: Use NHTSA coordinates if available (rarely are)
        if lat is not None and lon is not None and lat != 0 and lon != 0:
            coords_nhtsa += 1
        else:
            # Priority 2: Use geocoded address
            address = row.get("Location Address / Description", "")
            city_code = row.get("Location", "")
            cache_key = f"{address}|{city_code}"
            cached = cache.get(cache_key)

            if cached is not None:
                lat = cached["lat"]
                lon = cached["lon"]
                coords_geocoded += 1
            else:
                # Priority 3: Fall back to city center with random jitter
                if city_code and city_code in CITIES:
                    city_info = CITIES[city_code]
                    lat = city_info["lat"] + rng.uniform(-0.02, 0.02)
                    lon = city_info["lon"] + rng.uniform(-0.02, 0.02)
                    is_estimated = True
                    coords_estimated += 1
                else:
                    continue  # Skip crashes we can't map at all

        # Format date for display
        date_str = None
        if pd.notna(row["_date"]):
            date_str = row["_date"].strftime("%Y-%m-%d")

        record = {
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "hour": int(row["_hour"]),
            "day_of_week": row["_day_of_week"] if row["_day_of_week"] != "Unknown" else None,
            "day_num": int(row["_day_num"]) if pd.notna(row["_day_num"]) else None,
            "time_period": row["_time_period"],
            "location_type": row["_location_type"],
            "crash_type": row.get("Crash Type", "Unknown"),
            "city": row.get("Location", "Unknown"),
            "date": date_str,
            "is_weekend": bool(row["_is_weekend"]) if pd.notna(row["_is_weekend"]) else False,
            "is_estimated_location": is_estimated,
        }
        map_data.append(record)

    print(f"  Total records: {len(map_data)}")
    print(f"  From NHTSA coordinates: {coords_nhtsa}")
    print(f"  From geocoded addresses: {coords_geocoded}")
    print(f"  Estimated (city center fallback): {coords_estimated}")

    # Save JSON
    print()
    print("Saving crash_data.json...")
    os.makedirs(os.path.dirname(WEB_CRASH_DATA), exist_ok=True)
    with open(WEB_CRASH_DATA, "w") as f:
        json.dump(map_data, f)

    size_kb = os.path.getsize(WEB_CRASH_DATA) / 1024
    print(f"  Saved: {WEB_CRASH_DATA} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
