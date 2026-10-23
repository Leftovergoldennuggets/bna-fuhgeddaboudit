"""
01_download_data.py — Download raw crash data from NHTSA and Waymo
==========================================================================
Downloads five CSV files:
  1. NHTSA ADS crashes AFTER June 16, 2025 (Amendment 3 format)
  2. NHTSA ADS crashes BEFORE June 16, 2025 (Amendment 2 format, archived)
  3. Waymo Safety Impact Data Hub CSV2 (Waymo's curated crash list)
  4. Waymo Safety Impact Data Hub CSV1 (rider-only miles by city)
  5. Waymo Safety Impact Data Hub CSV3 (Waymo vs. human benchmarks)

Also regenerates two static files from CSV1:
  - data/static/miles_by_city.json   (latest cumulative miles per metro)
  - data/static/miles_quarterly.json (cumulative miles per metro at every
    quarterly release Waymo still hosts — a mileage time series)

These get saved into data/raw/ and are the starting point for the pipeline.

Usage:
  python pipeline/01_download_data.py
==========================================================================
"""

import csv
import io
import json
import os
import sys
from datetime import date

import requests

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    NHTSA_POST_URL, NHTSA_PRIOR_URL,
    WAYMO_HUB_CSV1_PREFIX, WAYMO_HUB_CSV1_FALLBACK,
    WAYMO_HUB_CSV2_PREFIX, WAYMO_HUB_CSV2_FALLBACK,
    WAYMO_HUB_CSV3_PREFIX, WAYMO_HUB_CSV3_FALLBACK,
    WAYMO_MILEAGE_HISTORY_START, CITIES,
    RAW_NHTSA_POST, RAW_NHTSA_PRIOR, RAW_WAYMO_HUB, RAW_WAYMO_CSV1,
    RAW_WAYMO_CSV3, RAW_DIR,
    STATIC_MILES_BY_CITY, STATIC_MILES_QUARTERLY,
)
from pipeline.utils import parse_csv1_miles, add_months


def _build_waymo_url(prefix, fallback):
    """
    Auto-detect the latest Waymo CSV URL by trying quarterly date ranges.

    Waymo publishes new data quarterly, ~2 weeks into the month after each quarter:
      - ~Mar 15 → data through Dec of prior year
      - ~Jun 15 → data through Mar
      - ~Sep 15 → data through Jun
      - ~Dec 15 → data through Sep

    We try the most recent expected quarter first, then work backwards up to
    4 quarters in case the latest hasn't been published yet.

    Returns (url, end_date_str) where end_date_str is like "202512".
    """
    today = date.today()

    quarter_ends = []
    year, month = today.year, today.month
    for _ in range(5):
        qe_month = (month // 3) * 3  # rounds down to nearest quarter boundary
        if qe_month == 0:
            qe_month = 12
            year -= 1
        quarter_ends.append(f"{year}{qe_month:02d}")
        month = qe_month - 3
        if month <= 0:
            month += 12
            year -= 1

    for end_date in quarter_ends:
        url = prefix + f"202009-{end_date}-2022benchmark.csv"
        print(f"    Trying 202009-{end_date}...")
        try:
            resp = requests.head(url, timeout=30)
            if resp.status_code == 200:
                print(f"    Found: 202009-{end_date}")
                return url, end_date
        except requests.exceptions.RequestException:
            continue

    print("    Could not auto-detect latest URL, using fallback.")
    return fallback, None


def _end_date_to_human(end_date_str):
    """Convert '202512' to 'December 2025'."""
    if not end_date_str or len(end_date_str) != 6:
        return None
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    year = end_date_str[:4]
    month_num = int(end_date_str[4:])
    if 1 <= month_num <= 12:
        return f"{month_names[month_num - 1]} {year}"
    return None


def download_file(url, output_path, description):
    """
    Download a file from a URL and save it locally.

    Parameters:
        url (str): The web address to download from
        output_path (str): Where to save the downloaded file
        description (str): Human-readable name for logging (e.g., "NHTSA Post")
    """
    print(f"  Downloading {description}...")
    print(f"    URL: {url}")

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Download the file (timeout after 120 seconds if the server doesn't respond)
    response = requests.get(url, timeout=120)

    # If the download failed (e.g., 404 Not Found), raise an error
    response.raise_for_status()

    # Save the downloaded content to disk ("wb" = write binary, needed for raw bytes)
    with open(output_path, "wb") as f:
        f.write(response.content)

    # Show the file size so we can tell if something looks wrong
    size_mb = len(response.content) / (1024 * 1024)  # Convert bytes → megabytes
    print(f"    Saved: {output_path} ({size_mb:.1f} MB)")


def _read_csv1_rows(text):
    """CSV1 text → [(location_name, miles)] regardless of header names."""
    reader = csv.reader(io.StringIO(text))
    next(reader, None)  # header: "County Name" (new) or "Ops Depot" (old)
    return [(r[0], r[1]) for r in reader if len(r) >= 2]


def update_miles_by_city(csv1_path, end_date_str):
    """
    Parse CSV1 (rider-only miles by location) and update miles_by_city.json.

    Every metro Waymo publishes mileage for is included automatically —
    location names are resolved by parse_csv1_miles (utils.py), which
    understands both CSV1 formats Waymo has used.
    """
    print("  Updating miles_by_city.json from CSV1...")

    with open(csv1_path, "r") as f:
        total_miles, metro_miles, unknown = parse_csv1_miles(_read_csv1_rows(f.read()))
    if unknown:
        print(f"    WARNING: unrecognized CSV1 location(s) {unknown} — add them to "
              f"CSV1_AGGREGATES or a metro's counties in config.py")

    data_through = _end_date_to_human(end_date_str) or "Unknown"
    cities = {
        info["name"]: {"miles_millions": metro_miles.get(code)}
        for code, info in CITIES.items()
    }

    output = {
        "description": "Cumulative rider-only miles by metro from the Waymo Safety Impact Data Hub (CSV1). Regenerated automatically by the pipeline.",
        "source_url": "https://waymo.com/safety/impact/#downloads",
        "data_through": data_through,
        "data_through_ym": int(end_date_str) if end_date_str else None,
        "last_updated": date.today().isoformat(),
        "cities": cities,
        "total_miles_millions": total_miles,
    }

    os.makedirs(os.path.dirname(STATIC_MILES_BY_CITY), exist_ok=True)
    with open(STATIC_MILES_BY_CITY, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    published = {CITIES[c]["name"]: m for c, m in metro_miles.items()}
    print(f"    Data through: {data_through}")
    print(f"    Total miles: {total_miles}M; by metro: {published}")
    print(f"    Saved: {STATIC_MILES_BY_CITY}")


def update_mileage_history(end_date_str):
    """
    Build data/static/miles_quarterly.json from every hosted CSV1 release.

    Each quarterly release holds cumulative miles since Sept 2020, so the
    releases together form a time series. Quarters that fail to download
    keep their previously saved values — Waymo removing an old file must
    never erase history from the site.
    """
    print("  Updating miles_quarterly.json from all hosted CSV1 releases...")
    existing = {}
    if os.path.exists(STATIC_MILES_QUARTERLY):
        with open(STATIC_MILES_QUARTERLY) as f:
            existing = {q["through"]: q for q in json.load(f).get("quarters", [])}

    quarters = {}
    if end_date_str:
        ym = int(WAYMO_MILEAGE_HISTORY_START)
        while ym <= int(end_date_str):
            url = WAYMO_HUB_CSV1_PREFIX + f"202009-{ym}-2022benchmark.csv"
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                total, metro_miles, unknown = parse_csv1_miles(_read_csv1_rows(resp.text))
                if unknown:
                    print(f"    WARNING ({ym}): unrecognized CSV1 location(s) {unknown}")
                quarters[ym] = {
                    "through": ym,
                    "total_miles_millions": total,
                    "metros": metro_miles,
                    "source_url": url,
                }
            except requests.exceptions.RequestException as e:
                if ym in existing:
                    quarters[ym] = existing[ym]
                    print(f"    {ym}: download failed ({e.__class__.__name__}) — kept saved values")
                else:
                    print(f"    {ym}: not available ({e.__class__.__name__})")
            ym = add_months(ym, 3)
    for ym, q in existing.items():
        quarters.setdefault(ym, q)

    output = {
        "description": "Cumulative rider-only miles per metro at each Waymo Safety Impact Data Hub release (CSV1). Each release covers Sept 2020 through the quarter-end in 'through' (YYYYMM). Regenerated automatically by the pipeline.",
        "quarters": [quarters[k] for k in sorted(quarters)],
    }
    with open(STATIC_MILES_QUARTERLY, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    summary = ", ".join(f"{k}={quarters[k]['total_miles_millions']}M" for k in sorted(quarters))
    print(f"    {len(quarters)} quarterly releases: {summary}")
    print(f"    Saved: {STATIC_MILES_QUARTERLY}")


def main():
    """Download all raw data files and update derived static files."""
    print("=" * 60)
    print("STEP 1: DOWNLOADING RAW DATA")
    print("=" * 60)
    print()

    # Auto-detect the latest Waymo CSV URLs
    print("  Auto-detecting latest Waymo data URLs...")
    csv2_url, end_date = _build_waymo_url(WAYMO_HUB_CSV2_PREFIX, WAYMO_HUB_CSV2_FALLBACK)
    csv1_url, _ = _build_waymo_url(WAYMO_HUB_CSV1_PREFIX, WAYMO_HUB_CSV1_FALLBACK)
    csv3_url, _ = _build_waymo_url(WAYMO_HUB_CSV3_PREFIX, WAYMO_HUB_CSV3_FALLBACK)
    print()

    # List of (URL, save path, description) for each file to download
    downloads = [
        (NHTSA_POST_URL,  RAW_NHTSA_POST,  "NHTSA ADS — post June 16, 2025 (Amendment 3)"),
        (NHTSA_PRIOR_URL, RAW_NHTSA_PRIOR, "NHTSA ADS — prior to June 16, 2025 (Amendment 2)"),
        (csv2_url,        RAW_WAYMO_HUB,   "Waymo Safety Impact Data Hub (CSV2 — crashes)"),
        (csv1_url,        RAW_WAYMO_CSV1,   "Waymo Safety Impact Data Hub (CSV1 — miles)"),
        (csv3_url,        RAW_WAYMO_CSV3,   "Waymo Safety Impact Data Hub (CSV3 — benchmarks)"),
    ]

    for url, path, desc in downloads:
        try:
            download_file(url, path, desc)
            print()
        except requests.exceptions.HTTPError as e:
            print(f"\n    ERROR: Download failed for {desc}")
            print(f"    HTTP status: {e.response.status_code}")
            print()
            if "waymo" in url.lower():
                print("    The Waymo Hub URL may have changed.")
                print("    Go to https://waymo.com/safety/impact/ and find the new CSV link.")
                print("    Then update the URL prefix in pipeline/config.py")
            else:
                print("    Check if the NHTSA URL has changed at:")
                print("    https://www.nhtsa.gov/automated-vehicles/automated-driving-systems")
            print()
            raise
        except requests.exceptions.ConnectionError:
            print(f"\n    ERROR: Could not connect to download {desc}")
            print("    Check your internet connection and try again.")
            raise

    # Update miles_by_city.json from the freshly downloaded CSV1
    update_miles_by_city(RAW_WAYMO_CSV1, end_date)
    print()
    update_mileage_history(end_date)
    print()

    print("All downloads complete!")
    print(f"Files saved in: {RAW_DIR}")


if __name__ == "__main__":
    main()
