"""
04_generate_map_data.py — Generate crash_data.json for the interactive map
==========================================================================
Creates a JSON array of individual crash records for the Leaflet map.

LOCATION PRECISION — three tiers, flagged on every record:
  "street"  Hub-enriched crashes have a street-level address
            ("Florida Street near 24th Street") geocoded via OpenStreetMap
            Nominatim. ~92% of enriched crashes geocode successfully.
  "city"    Recent crashes not yet in Waymo's hub: NHTSA redacts the
            street address, so we geocode the city itself and place the
            marker near the city center with a small random offset.
  "metro"   Last resort when even the city can't be geocoded: metro
            center with a random offset.

Results are cached in geocode_cache.json (committed to git) so each
unique address/city is only geocoded once across all pipeline runs.

Inputs:
  - data/processed/waymo_merged.csv

Outputs:
  - data/web/crash_data.json
  - data/web/geocode_cache.json (updated cache)
  - geocoding accuracy stats appended to data/web/site-data.json

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
    PROCESSED_MERGED, WEB_CRASH_DATA, WEB_SITE_DATA, CITIES,
    OTHER_METRO_CODE, GEOCODE_CACHE, WEB_CRASH_CSV, STATIC_ZIP_REFERENCE,
)
from pipeline.utils import (
    parse_time, categorize_time_period, roadway_type,
    clean_coordinate, severity_level, normalize_place, normalize_state,
    clean_zip, geocode_cache_key, reverse_cache_key, hub_zip, zip_fit,
    is_current_cache_key,
)


# ===========================================================================
# GEOCODING
# ===========================================================================

def load_geocode_cache():
    """Load the geocode cache: "address|city" → {"lat","lon"} or None."""
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
    """Clean an NHTSA address string before geocoding."""
    if pd.isna(address) or str(address).strip() == "":
        return ""
    address = str(address).strip()

    # Strip descriptive preambles that confuse geocoders
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
    """Split "Florida Street near 24th Street" into its two streets."""
    for separator in [r"\s+near\s+", r"\s+at\s+", r"\s+and\s+", r"\s*&\s*"]:
        parts = re.split(separator, address, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()

    match = re.match(r"(.+?)\s+between\s+(.+?)(?:\s+and\s+.+)?$", address, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return address, None


def build_geocode_queries(address, city, state, metro_code):
    """Build geocoding query strategies for one address.

    Returns a list of (query, precision) tuples tried in order:
      "street"  — the full intersection or address (best)
      "road"    — a single named street (the point lands somewhere along
                  the right road, but not necessarily at the crash spot)

    Queries use the crash's ACTUAL city from the federal report; the
    metro core city is only a fallback when the city field is missing.
    """
    cleaned = clean_address(address)
    if not cleaned:
        return []

    city = normalize_place(city)
    state = normalize_state(state)
    if city and state:
        suffix = f", {city}, {state}"
    else:
        info = CITIES.get(metro_code, {})
        suffix = f", {info.get('name', '')}, {info.get('state', '')}"

    street_a, street_b = split_intersection(cleaned)
    if street_b:
        return [
            (f"{street_a} & {street_b}{suffix}", "street"),
            (f"{street_a}{suffix}", "road"),
            (f"{street_b}{suffix}", "road"),
        ]
    return [(f"{cleaned}{suffix}", "street")]


def make_geocoder():
    """Nominatim geocoder with the project's user agent."""
    return Nominatim(user_agent="waymo-crash-map (github.com/leftovergoldennuggets/bna-fuhgeddaboudit)", timeout=10)


def try_geocode(geocoder, queries, expected_lat, expected_lon, max_offset):
    """Try queries in order; accept the first result near the expected point.

    Returns {"lat", "lon", "precision"} or None. The sanity radius is
    tight when we know the actual city's centroid (~0.25° ≈ 17 miles)
    so a same-named street in a neighboring city gets rejected.
    """
    for query, precision in queries:
        try:
            result = geocoder.geocode(query)
            time.sleep(1.1)  # Nominatim usage policy: max 1 request/second
            if result:
                lat, lon = result.latitude, result.longitude
                if abs(lat - expected_lat) < max_offset and abs(lon - expected_lon) < max_offset:
                    return {"lat": round(lat, 6), "lon": round(lon, 6), "precision": precision}
        except (GeocoderTimedOut, GeocoderServiceError):
            time.sleep(2.0)
            continue
    return None


def geocode_addresses(df, cache):
    """Geocode street addresses for hub-enriched rows (cached)."""
    geocoder = make_geocoder()

    to_geocode = []
    seen = set()
    for _, row in df.iterrows():
        address = row.get("Location Address / Description")
        if pd.isna(address) or not str(address).strip():
            continue
        city_code = row.get("Location", "")
        city = row.get("City")
        state = row.get("State")
        cache_key = geocode_cache_key(address, city, state, city_code)
        if cache_key in seen or cache_key in cache:
            continue
        seen.add(cache_key)
        queries = build_geocode_queries(address, city, state, city_code)
        if queries and city_code in CITIES:
            to_geocode.append((cache_key, queries, city_code, normalize_place(city), normalize_state(state)))

    if not to_geocode:
        print("  All addresses already geocoded — no new lookups needed!")
        return cache

    print(f"  Need to geocode {len(to_geocode)} NEW addresses "
          f"(~{len(to_geocode) * 2 // 60}-{len(to_geocode) * 3 // 60} min)...")

    success = failed = 0
    for i, (cache_key, queries, city_code, city, state) in enumerate(to_geocode):
        # Sanity-check against the crash's own city when its centroid is
        # cached (geocode_cities runs first); fall back to the metro center.
        city_hit = cache.get(f"__city__{city}|{state}") if city and state else None
        if city_hit:
            expected_lat, expected_lon, max_offset = city_hit["lat"], city_hit["lon"], 0.25
        else:
            info = CITIES[city_code]
            expected_lat, expected_lon, max_offset = info["lat"], info["lon"], 0.5
        result = try_geocode(geocoder, queries, expected_lat, expected_lon, max_offset)
        cache[cache_key] = result
        if result:
            success += 1
        else:
            failed += 1
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(to_geocode)} (success: {success}, failed: {failed})")
        if (i + 1) % 100 == 0:
            save_geocode_cache(cache)

    print(f"  Geocoding complete: {success} succeeded, {failed} failed")
    return cache


ZIP_FIT_MAX = 1.5  # accept a geocode only within 1.5 ZIP radii of the ZIP centre


def load_zip_reference():
    """Census ZCTA centres and radii (see pipeline/tools/build_zip_reference.py)."""
    if not os.path.exists(STATIC_ZIP_REFERENCE):
        print(f"  WARNING: {STATIC_ZIP_REFERENCE} missing — ZIP checks skipped")
        return {}
    with open(STATIC_ZIP_REFERENCE) as f:
        return json.load(f)["zips"]


def geocode_addresses_in_zip(df, cache, zip_ref):
    """Geocode hub addresses that come with a ZIP code, checked against it.

    Waymo reported a ZIP for every hub crash up to June 2025. A geocode is
    accepted only if it lands inside that ZIP's area. Search order:
      1. the existing v2 result, if it is intersection-level and fits
      2. the intersection, searched only inside the ZIP's bounding box
      3. either street alone, inside the ZIP's box  → "road" precision
      4. the ZIP's own centre                       → "zip" precision
    Results are cached under v3 keys (which include the ZIP).
    """
    jobs, seen = [], set()
    for _, row in df.iterrows():
        address = row.get("Location Address / Description")
        zip_code = hub_zip(row)
        if pd.isna(address) or not str(address).strip() or not zip_code or zip_code not in zip_ref:
            continue
        key = geocode_cache_key(address, row.get("City"), row.get("State"), row.get("Location", ""), zip_code)
        if key in cache or key in seen:
            continue
        seen.add(key)
        jobs.append((key, row, zip_code))

    if not jobs:
        print("  ZIP-checked geocodes: all cached")
        return cache

    reused = queried = fallback = 0
    geocoder = None
    print(f"  ZIP-checked geocoding for {len(jobs)} addresses...")
    for i, (key, row, zip_code) in enumerate(jobs):
        address = row.get("Location Address / Description")
        zentry = zip_ref[zip_code]
        city_code = row.get("Location", "")

        old = cache.get(geocode_cache_key(address, row.get("City"), row.get("State"), city_code))
        if old and old.get("precision") == "street" and zip_fit(old["lat"], old["lon"], zentry) <= ZIP_FIT_MAX:
            cache[key] = old
            reused += 1
            continue

        if geocoder is None:
            geocoder = make_geocoder()
        zlat, zlon, radius = zentry
        pad = max(radius * 2, 1.0) / 111.0  # degrees, roughly
        viewbox = [(zlat - pad, zlon - pad * 1.3), (zlat + pad, zlon + pad * 1.3)]
        result, errored = None, False
        for query, precision in build_geocode_queries(address, row.get("City"), row.get("State"), city_code):
            try:
                hit = geocoder.geocode(query, viewbox=viewbox, bounded=True)
                time.sleep(1.1)  # Nominatim usage policy: max 1 request/second
            except (GeocoderTimedOut, GeocoderServiceError):
                errored = True
                time.sleep(2.0)
                continue
            if hit and zip_fit(hit.latitude, hit.longitude, zentry) <= ZIP_FIT_MAX:
                result = {"lat": round(hit.latitude, 6), "lon": round(hit.longitude, 6), "precision": precision}
                break
        if result:
            queried += 1
        elif errored:
            # A timeout or rate limit isn't an answer: leave it uncached so
            # the next run tries again (the row falls back to v2/city for now).
            continue
        else:
            result = {"lat": zlat, "lon": zlon, "precision": "zip"}
            fallback += 1
        cache[key] = result
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(jobs)} (reused {reused}, geocoded {queried}, ZIP centre {fallback})")
            save_geocode_cache(cache)

    print(f"  ZIP-checked geocoding: {reused} reused, {queried} geocoded inside ZIP, "
          f"{fallback} placed at ZIP centre")
    return cache


def geocode_cities(df, cache):
    """Geocode city centroids for every city in the dataset.

    Used two ways: as the placement for crashes whose street address
    NHTSA redacts, and as the sanity anchor when geocoding street
    addresses. One lookup per unique city, cached forever.
    """
    geocoder = make_geocoder()

    needed = set()
    for _, row in df.iterrows():
        city = normalize_place(row.get("City"))
        state = normalize_state(row.get("State"))
        if city and state:
            needed.add((city, state))

    to_geocode = [(c, s) for c, s in sorted(needed) if f"__city__{c}|{s}" not in cache]
    if not to_geocode:
        return cache


    print(f"  Geocoding {len(to_geocode)} city centroid(s)...")
    for city, state in to_geocode:
        cache_key = f"__city__{city}|{state}"
        result = None
        try:
            hit = geocoder.geocode(f"{city}, {state}, USA")
            time.sleep(1.1)
            if hit:
                result = {"lat": round(hit.latitude, 6), "lon": round(hit.longitude, 6)}
        except (GeocoderTimedOut, GeocoderServiceError):
            time.sleep(2.0)
        cache[cache_key] = result
        print(f"    {city}, {state}: {'ok' if result else 'FAILED'}")
    return cache


# ===========================================================================
# MAIN
# ===========================================================================

# Columns of the public CSV download, in order: (csv column, record key).
# Documented for readers in methodology.html ("Download the data").
CSV_EXPORT_COLUMNS = [
    ("report_id", "report_id"),
    ("operation", "operation_type"),
    ("date", "date"),
    ("date_precision", "date_precision"),
    ("hour", "hour"),
    ("metro", "city"),
    ("city", "city_name"),
    ("zip_code", "zip_code"),
    ("latitude", "lat"),
    ("longitude", "lon"),
    ("location_precision", "location_precision"),
    ("roadway_type", "location_type"),
    ("crash_type_waymo", "crash_type"),
    ("crash_with", "crash_with"),
    ("waymo_movement", "sv_movement"),
    ("other_party_movement", "cp_movement"),
    ("waymo_speed_mph", "speed_mph"),
    ("highest_injury_alleged", "injury_severity"),
    ("severity_level", "severity_level"),
    ("in_waymo_hub", "in_hub"),
    ("narrative", "narrative"),
]


def export_crash_csv(map_data):
    """Write the cleaned, merged dataset as a CSV readers can download."""
    rows = []
    for rec in map_data:
        row = {col: rec.get(key) for col, key in CSV_EXPORT_COLUMNS}
        row["metro"] = CITIES.get(row["metro"], {}).get("name", "Other")
        rows.append(row)
    out = pd.DataFrame(rows, columns=[c for c, _ in CSV_EXPORT_COLUMNS])
    out = out.sort_values(["date", "report_id"], na_position="first")
    out.to_csv(WEB_CRASH_CSV, index=False)
    print(f"  Saved: {WEB_CRASH_CSV} ({len(out)} rows, "
          f"{os.path.getsize(WEB_CRASH_CSV) / 1024:.0f} KB)")


def main():
    """Generate crash_data.json for the interactive map."""
    print("=" * 60)
    print("STEP 4: GENERATING MAP DATA")
    print("=" * 60)
    print()

    print("Loading merged dataset...")
    df = pd.read_csv(PROCESSED_MERGED, low_memory=False)
    print(f"  Loaded {len(df)} rows (all operation types)")

    # Parse time — kept nullable; crashes without a time stay on the map
    df["_hour"], df["_minute"] = zip(*df["Incident Time (24:00)"].apply(parse_time))
    df["_time_period"] = df["_hour"].apply(categorize_time_period)
    df["_location_type"] = df["Roadway Type"].apply(roadway_type) if "Roadway Type" in df.columns \
        else "Other/unknown"
    df["_date"] = pd.to_datetime(df["incident_date"], errors="coerce")
    has_day = df["date_precision"] == "day"
    df["_day_of_week"] = df["_date"].dt.day_name().where(has_day & df["_date"].notna())
    df["_day_num"] = df["_date"].dt.dayofweek.where(has_day & df["_date"].notna())
    df["_is_weekend"] = df["_date"].dt.dayofweek.isin([5, 6]).where(has_day & df["_date"].notna(), False)

    # NHTSA's own coordinates (almost always redacted, but check anyway)
    df["_lat"] = df["Latitude"].apply(clean_coordinate) if "Latitude" in df.columns else None
    df["_lon"] = df["Longitude"].apply(clean_coordinate) if "Longitude" in df.columns else None

    print()
    print("Geocoding...")
    cache = load_geocode_cache()
    # Retire v1 cache entries (keyed by metro instead of the crash's
    # actual city — see geocode_cache_key). Everything re-geocodes once
    # under the v2 scheme and is cached again.
    legacy = [k for k in cache if not is_current_cache_key(k)]
    if legacy:
        print(f"  Purging {len(legacy)} legacy (v1) cache entries — addresses "
              f"re-geocode once with their actual city")
        for k in legacy:
            del cache[k]
    cache_before = len(cache)
    cache = geocode_cities(df, cache)      # city centroids first: they anchor the sanity checks
    cache = geocode_addresses(df, cache)
    zip_ref = load_zip_reference()
    cache = geocode_addresses_in_zip(df, cache, zip_ref)
    save_geocode_cache(cache)
    if len(cache) > cache_before:
        print(f"  Cache updated: {len(cache) - cache_before} new entries (total: {len(cache)})")
    print()

    # Fixed seed: identical fallback positions on every run
    rng = np.random.default_rng(seed=42)

    print("Building JSON records...")
    map_data = []
    pending_zip = []  # (record, hub_zip) — zips finalized after the reverse pass
    precision_counts = {"exact": 0, "street": 0, "road": 0, "zip": 0, "city": 0, "metro": 0, "skipped": 0}

    for _, row in df.iterrows():
        lat, lon = row["_lat"], row["_lon"]
        city_code = row.get("Location", "")
        location_precision = None

        if lat is not None and lon is not None and lat != 0 and lon != 0:
            location_precision = "exact"
        else:
            # Street-level geocode (hub-enriched rows with an address)
            address = row.get("Location Address / Description")
            if pd.notna(address) and str(address).strip():
                zip_code = hub_zip(row)
                cached = None
                if zip_code and zip_code in zip_ref:
                    cached = cache.get(geocode_cache_key(
                        address, row.get("City"), row.get("State"), city_code, zip_code))
                if cached is None:
                    cached = cache.get(geocode_cache_key(
                        address, row.get("City"), row.get("State"), city_code))
                if cached is not None:
                    lat, lon = cached["lat"], cached["lon"]
                    location_precision = cached.get("precision", "street")

        if location_precision is None:
            # City-level geocode (NHTSA redacts addresses)
            city = normalize_place(row.get("City"))
            state = normalize_state(row.get("State"))
            cached = cache.get(f"__city__{city}|{state}") if city and state else None
            if cached is not None:
                lat = cached["lat"] + rng.uniform(-0.01, 0.01)
                lon = cached["lon"] + rng.uniform(-0.01, 0.01)
                location_precision = "city"
            elif city_code in CITIES:
                info = CITIES[city_code]
                lat = info["lat"] + rng.uniform(-0.02, 0.02)
                lon = info["lon"] + rng.uniform(-0.02, 0.02)
                location_precision = "metro"
            else:
                precision_counts["skipped"] += 1
                continue

        precision_counts[location_precision] += 1

        # Date display: respect precision (month-only for NHTSA-redacted dates)
        date_str = None
        if pd.notna(row["_date"]):
            if row.get("date_precision") == "day":
                date_str = row["_date"].strftime("%Y-%m-%d")
            else:
                date_str = row["_date"].strftime("%Y-%m")

        has_injury = str(row.get("Is Any-Injury-Reported", "")).strip() == "True"
        level = severity_level(row.get("Highest Injury Severity Alleged"), has_injury)

        crash_type = row.get("Crash Type")
        crash_type = str(crash_type) if pd.notna(crash_type) else None
        crash_with = row.get("Crash With")
        crash_with = str(crash_with).strip() if pd.notna(crash_with) else None

        is_vulnerable = (
            crash_type in ("Pedestrian", "Cyclist", "Motorcycle")
            or (crash_type is None and crash_with in (
                "Non-Motorist: Pedestrian", "Non-Motorist: Cyclist", "Motorcycle"))
        )

        def text_or_none(value):
            value = str(value).strip() if pd.notna(value) else None
            return None if value in (None, "", "nan") else value

        speed_mph = None
        speed_raw = row.get("SV Precrash Speed (MPH)")
        if pd.notna(speed_raw):
            try:
                speed_mph = round(float(speed_raw), 1)
            except (ValueError, TypeError):
                pass

        # Zip code: Waymo's hub publishes it; NHTSA redacts its own.
        # After the merge the hub's column is "Zip Code_hub" for matched
        # rows (NHTSA's redacted "Zip Code" keeps the original name) and
        # plain "Zip Code" only for the two hub-only pre-SGO rows.
        row_zip = hub_zip(row)

        report_id = row.get("Report ID")
        if pd.isna(report_id):
            report_id = row.get("SGO Report ID")
        record = {
            "report_id": str(report_id) if pd.notna(report_id) else None,
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "hour": int(row["_hour"]) if pd.notna(row["_hour"]) else None,
            "day_of_week": row["_day_of_week"] if pd.notna(row["_day_of_week"]) else None,
            "day_num": int(row["_day_num"]) if pd.notna(row["_day_num"]) else None,
            "time_period": row["_time_period"],
            "location_type": row["_location_type"],
            "crash_type": crash_type or "Pending classification",
            "city": city_code if city_code else OTHER_METRO_CODE,
            "city_name": normalize_place(row.get("City")) or None,
            "date": date_str,
            "date_precision": row.get("date_precision"),
            "is_weekend": bool(row["_is_weekend"]) if pd.notna(row["_is_weekend"]) else False,
            "is_estimated_location": location_precision in ("zip", "city", "metro"),
            "location_precision": location_precision,
            "operation_type": row.get("operation_type"),
            "in_hub": bool(row.get("in_hub")),
            "has_injury": has_injury,
            "is_serious": level in ("moderate", "serious", "fatal"),
            "severity_level": level,
            "is_vulnerable_road_user": bool(is_vulnerable),
            "sv_movement": text_or_none(row.get("SV Pre-Crash Movement")),
            "cp_movement": text_or_none(row.get("CP Pre-Crash Movement")),
            "crash_with": crash_with,
            "speed_mph": speed_mph,
            "injury_severity": text_or_none(row.get("Highest Injury Severity Alleged")),
            "narrative": text_or_none(row.get("Narrative")),
            "zip_code": row_zip,
        }
        map_data.append(record)
        pending_zip.append((record, row_zip))

    print(f"  Total records: {len(map_data)}")
    for tier, count in precision_counts.items():
        print(f"    {tier}: {count}")

    # -----------------------------------------------------------------------
    # REVERSE PASS: coordinates → zip, for two purposes
    #   1. Fill zips the hub didn't publish (street/road-tier markers)
    #   2. Audit: does each marker actually sit in the zip the federal
    #      record says? Gives a published accuracy number instead of an
    #      assumption. One lookup per unique coordinate, cached forever.
    # -----------------------------------------------------------------------
    print()
    print("Reverse-geocoding zips (fill + placement audit)...")
    precise = [(rec, hz) for rec, hz in pending_zip
               if rec["location_precision"] in ("street", "road", "exact")]
    needed_coords = sorted({(rec["lat"], rec["lon"]) for rec, _ in precise
                            if reverse_cache_key(rec["lat"], rec["lon"]) not in cache})
    if needed_coords:
        print(f"  {len(needed_coords)} new coordinate lookups (~{len(needed_coords) * 12 // 600} min)...")
        geocoder = make_geocoder()
        for i, (lat, lon) in enumerate(needed_coords):
            postcode = None
            try:
                hit = geocoder.reverse((lat, lon), exactly_one=True, zoom=18)
                time.sleep(1.1)
                if hit:
                    postcode = clean_zip((hit.raw.get("address") or {}).get("postcode"))
            except (GeocoderTimedOut, GeocoderServiceError):
                time.sleep(2.0)
            cache[reverse_cache_key(lat, lon)] = postcode
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{len(needed_coords)}")
                save_geocode_cache(cache)
        save_geocode_cache(cache)

    zip_filled = zip_checked = zip_matched = 0
    for rec, reported_zip in precise:
        reverse_zip = cache.get(reverse_cache_key(rec["lat"], rec["lon"]))
        if reported_zip and reverse_zip:
            zip_checked += 1
            if reported_zip == reverse_zip:
                zip_matched += 1
        if not reported_zip and reverse_zip:
            rec["zip_code"] = reverse_zip
            zip_filled += 1

    with_zip = sum(1 for rec in map_data if rec["zip_code"])
    print(f"  Zips: {with_zip}/{len(map_data)} records "
          f"({zip_filled} filled from coordinates)")
    if zip_checked:
        print(f"  Placement audit: {zip_matched}/{zip_checked} street-level markers "
              f"({round(zip_matched / zip_checked * 100, 1)}%) sit in the zip the "
              f"federal record reports")

    print()
    print("Saving waymo_crashes.csv (public download)...")
    export_crash_csv(map_data)

    print()
    print("Saving crash_data.json...")
    os.makedirs(os.path.dirname(WEB_CRASH_DATA), exist_ok=True)
    with open(WEB_CRASH_DATA, "w") as f:
        json.dump(map_data, f)  # No indent — keeps the file ~3x smaller
    print(f"  Saved: {WEB_CRASH_DATA} ({os.path.getsize(WEB_CRASH_DATA) / 1024:.0f} KB)")

    # --- Append geocoding stats to site-data.json (driverless only, to
    # match the headline dataset the site describes) ---
    driverless = [r for r in map_data if r["operation_type"] == "driverless"]
    total_mapped = len(driverless)
    estimated = sum(1 for r in driverless if r["is_estimated_location"])
    accurate = total_mapped - estimated
    dl_with_zip = sum(1 for r in driverless if r["zip_code"])

    city_geo = {}
    for entry in driverless:
        code = entry["city"]
        city_geo.setdefault(code, {"total": 0, "estimated": 0})
        city_geo[code]["total"] += 1
        if entry["is_estimated_location"]:
            city_geo[code]["estimated"] += 1

    city_accuracy = {
        CITIES.get(code, {}).get("name", code): round((c["total"] - c["estimated"]) / c["total"] * 100)
        for code, c in city_geo.items() if c["total"] > 0
    }

    geocoding_stats = {
        "total_mapped": total_mapped,
        "accurate": accurate,
        "estimated": estimated,
        "accuracy_pct": round(accurate / total_mapped * 100, 1) if total_mapped else 0,
        "by_city": city_accuracy,
        "zip_coverage": dl_with_zip,
        "zip_coverage_pct": round(dl_with_zip / total_mapped * 100, 1) if total_mapped else 0,
        "zip_checked": zip_checked,
        "zip_match_pct": round(zip_matched / zip_checked * 100, 1) if zip_checked else 0,
        # Markers per precision tier: street = the intersection/address
        # itself (or NHTSA coordinates); road = on the right street, exact
        # point approximate; zip / city / metro = centre of that area.
        "tiers": {
            tier: sum(1 for r in driverless
                      if r["location_precision"] == tier or (tier == "street" and r["location_precision"] == "exact"))
            for tier in ("street", "road", "zip", "city", "metro")
        },
    }

    print()
    print("Updating site-data.json with geocoding stats...")
    if os.path.exists(WEB_SITE_DATA):
        with open(WEB_SITE_DATA, "r") as f:
            site_data = json.load(f)
        site_data["geocoding"] = geocoding_stats
        with open(WEB_SITE_DATA, "w") as f:
            json.dump(site_data, f, indent=2)
        print(f"  Geocoding: {accurate}/{total_mapped} street-level ({geocoding_stats['accuracy_pct']}%)")
    else:
        print(f"  WARNING: {WEB_SITE_DATA} not found — skipping geocoding stats")


if __name__ == "__main__":
    main()
