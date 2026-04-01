"""
01_download_data.py — Download raw crash data from NHTSA and Waymo
==========================================================================
Downloads four CSV files:
  1. NHTSA ADS crashes AFTER June 16, 2025 (Amendment 3 format)
  2. NHTSA ADS crashes BEFORE June 16, 2025 (Amendment 2 format, archived)
  3. Waymo Safety Impact Data Hub CSV2 (Waymo's curated crash list)
  4. Waymo Safety Impact Data Hub CSV1 (rider-only miles by city)

Also auto-updates data/static/miles_by_city.json with fresh mileage from CSV1.

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
    RAW_NHTSA_POST, RAW_NHTSA_PRIOR, RAW_WAYMO_HUB, RAW_WAYMO_CSV1, RAW_DIR,
    STATIC_MILES_BY_CITY,
)


# Mapping from CSV1 county/region names to display city names
# CSV1 uses county names (e.g., "Maricopa") while the site uses city names (e.g., "Phoenix")
_CSV1_COUNTY_TO_CITY = {
    "Maricopa": "Phoenix",
    "San Francisco Bay Area": "San Francisco",
    "Los Angeles": "Los Angeles",
    "Travis": "Austin",
    # Atlanta / Fulton not yet in CSV1 as of Dec 2025
}

# City launch notes for the miles_by_city.json file
_CITY_NOTES = {
    "Phoenix": "Waymo's first commercial market. Waymo One launched December 2018.",
    "San Francisco": "Public launch 2023. Denser traffic environment than Phoenix.",
    "Los Angeles": "Public launch 2024.",
    "Austin": "Waymo's newest major market.",
    "Atlanta": "Mileage not yet published by Waymo on the Safety Impact Data Hub.",
}


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


def update_miles_by_city(csv1_path, end_date_str):
    """
    Parse CSV1 (rider-only miles by location) and update miles_by_city.json.

    This replaces the previously hand-maintained static file with fresh data
    from Waymo's CSV1, so mileage stats stay current automatically.
    """
    print("  Updating miles_by_city.json from CSV1...")

    with open(csv1_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Parse mileage per county/region
    miles_col = "Waymo RO Miles (Millions)"
    total_miles = None
    city_miles = {}

    for row in rows:
        name = row["County Name"].strip()
        miles = float(row[miles_col].strip())

        if name == "All Locations (mileage blended)":
            total_miles = miles
        elif name in _CSV1_COUNTY_TO_CITY:
            city_miles[_CSV1_COUNTY_TO_CITY[name]] = miles

    # Build the JSON structure (matches the existing miles_by_city.json format)
    data_through = _end_date_to_human(end_date_str) or "Unknown"

    cities = {}
    for city_name in ["Phoenix", "San Francisco", "Los Angeles", "Austin", "Atlanta"]:
        miles = city_miles.get(city_name)
        cities[city_name] = {
            "miles_millions": miles,
            "note": _CITY_NOTES.get(city_name, ""),
        }

    output = {
        "description": "Rider-only miles by city from the Waymo Safety Impact Data Hub. Updated automatically by the pipeline from CSV1.",
        "source_url": "https://waymo.com/safety/impact/#downloads",
        "data_through": data_through,
        "last_updated": date.today().isoformat(),
        "cities": cities,
        "total_miles_millions": total_miles,
    }

    os.makedirs(os.path.dirname(STATIC_MILES_BY_CITY), exist_ok=True)
    with open(STATIC_MILES_BY_CITY, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    print(f"    Data through: {data_through}")
    print(f"    Total miles: {total_miles}M")
    print(f"    Saved: {STATIC_MILES_BY_CITY}")


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
    print()

    # List of (URL, save path, description) for each file to download
    downloads = [
        (NHTSA_POST_URL,  RAW_NHTSA_POST,  "NHTSA ADS — post June 16, 2025 (Amendment 3)"),
        (NHTSA_PRIOR_URL, RAW_NHTSA_PRIOR, "NHTSA ADS — prior to June 16, 2025 (Amendment 2)"),
        (csv2_url,        RAW_WAYMO_HUB,   "Waymo Safety Impact Data Hub (CSV2 — crashes)"),
        (csv1_url,        RAW_WAYMO_CSV1,   "Waymo Safety Impact Data Hub (CSV1 — miles)"),
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

    print("All downloads complete!")
    print(f"Files saved in: {RAW_DIR}")


if __name__ == "__main__":
    main()
