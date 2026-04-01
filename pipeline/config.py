"""
config.py — Central configuration for the Waymo crash data pipeline
==========================================================================
ALL constants live here: URLs, file paths, time periods, cities, etc.
When something changes (new data URL, new city, etc.), update THIS file only.
==========================================================================
"""

import os

# ---------------------------------------------------------------------------
# Where the project root is (one level up from this pipeline/ directory)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # e.g., /Users/you/bna-fuhgeddaboudit


# ===========================================================================
# DATA SOURCE URLs
# ===========================================================================
# These are the direct download links for the three raw data files.
# NHTSA provides separate files for crashes before and after June 16, 2025
# because the reporting format changed (Amendment 2 → Amendment 3).

# NHTSA: Crashes reported AFTER June 16, 2025 (Amendment 3 format)
# This URL stays the same — NHTSA just adds new rows to the same file.
NHTSA_POST_URL = (
    "https://static.nhtsa.gov/odi/ffdd/sgo-2021-01/"
    "SGO-2021-01_Incident_Reports_ADS.csv"
)
# NOTE: The URL ends in _ADS.csv (Automated Driving Systems), NOT _ADAS.csv
# (Advanced Driver Assistance Systems). ADAS is a different dataset (Tesla, etc.).

# NHTSA: Crashes reported BEFORE June 16, 2025 (Amendment 2 format)
# This is an archived file — it should not change over time.
NHTSA_PRIOR_URL = (
    "https://static.nhtsa.gov/odi/ffdd/sgo-2021-01/"
    "Archive-2021-2025/SGO-2021-01_Incident_Reports_ADS.csv"
)
# NOTE: Same _ADS.csv distinction applies here.

# Waymo Safety Impact Data Hub — CSV2 (crashes with SGO IDs and outcome groups)
# The filename changes every quarter when Waymo updates their data.
# The date range in the filename reflects the data period (e.g., "202009-202512").
# The URL is constructed dynamically based on the current date so the pipeline
# automatically picks up new quarterly releases without manual config changes.
# Pattern: data always starts at 202009 and ends at the most recent quarter.
# Waymo publishes ~Mar 15 (data through Dec), ~Jun 15 (through Mar),
# ~Sep 15 (through Jun), ~Dec 15 (through Sep).
WAYMO_STORAGE_BASE = (
    "https://storage.googleapis.com/waymo-uploads/files/documents/"
    "safety/safety-impact-data/"
)
WAYMO_HUB_CSV2_PREFIX = WAYMO_STORAGE_BASE + "CSV2%20-%20Crashes%20with%20SGO%20ID%20and%20Group%20Membership%20"
WAYMO_HUB_CSV1_PREFIX = WAYMO_STORAGE_BASE + "CSV1%20-%20RO%20Miles%20per%20Location%20"
# The end-date is built dynamically in 01_download_data.py — see build_waymo_url()
# Fallback URLs in case auto-detection fails:
WAYMO_HUB_CSV2_FALLBACK = WAYMO_HUB_CSV2_PREFIX + "202009-202512-2022benchmark.csv"
WAYMO_HUB_CSV1_FALLBACK = WAYMO_HUB_CSV1_PREFIX + "202009-202512-2022benchmark.csv"


# ===========================================================================
# FILE PATHS
# ===========================================================================
# Raw data = downloaded CSVs (gitignored, re-downloadable)
# Processed data = intermediate merged CSV (gitignored)
# Web data = JSON files the website reads (committed to git)

RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")           # Downloaded CSVs land here
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")  # Intermediate merged CSV
WEB_DIR = os.path.join(PROJECT_ROOT, "data", "web")           # JSON files the site reads
STATIC_DIR = os.path.join(PROJECT_ROOT, "data", "static")     # Hand-maintained reference data

# Raw data file paths (where downloads get saved)
RAW_NHTSA_POST = os.path.join(RAW_DIR, "nhtsa_ads_post_june16.csv")
RAW_NHTSA_PRIOR = os.path.join(RAW_DIR, "nhtsa_ads_prior_june16.csv")
RAW_WAYMO_HUB = os.path.join(RAW_DIR, "waymo_hub_csv2.csv")
RAW_WAYMO_CSV1 = os.path.join(RAW_DIR, "waymo_hub_csv1.csv")

# Processed (intermediate) file paths
PROCESSED_MERGED = os.path.join(PROCESSED_DIR, "waymo_merged.csv")
PROCESSED_EXTRAS = os.path.join(PROCESSED_DIR, "waymo_extras_not_in_hub.csv")  # NHTSA crashes Waymo didn't include

# Web-ready JSON file paths (the website reads these)
WEB_SITE_DATA = os.path.join(WEB_DIR, "site-data.json")
WEB_CRASH_DATA = os.path.join(WEB_DIR, "crash_data.json")
WEB_SERIOUS_INCIDENTS = os.path.join(WEB_DIR, "serious_incidents.json")

# Geocode cache — stores address → lat/lon lookups so we don't re-geocode
# the same address every time the pipeline runs. Committed to git.
GEOCODE_CACHE = os.path.join(WEB_DIR, "geocode_cache.json")

# Static data files — manually maintained, not auto-downloaded
# These provide mileage context that Waymo doesn't publish as a time series.
STATIC_MILES_BY_CITY = os.path.join(STATIC_DIR, "miles_by_city.json")
STATIC_MILEAGE_MILESTONES = os.path.join(STATIC_DIR, "mileage_milestones.json")

# Generated figure PNGs for scrollytelling sections
SITE_IMAGES_DIR = os.path.join(PROJECT_ROOT, "site", "assets", "images")


# ===========================================================================
# FILTER SETTINGS
# ===========================================================================
# We only analyze Waymo crashes from the NHTSA data (which includes all AV companies)
WAYMO_ENTITY_NAME = "Waymo LLC"  # Exact string in the NHTSA "Reporting Entity" column


# ===========================================================================
# COLUMN HARMONIZATION
# ===========================================================================
# NHTSA renamed some columns when they switched from Amendment 2 to Amendment 3.
# We rename the PRIOR (Amendment 2) columns to match the POST (Amendment 3) names
# so both datasets can be combined.
#
# Format: { "old name in Amendment 2": "new name in Amendment 3" }
COLUMN_RENAMES_PRIOR_TO_POST = {
    "Weather - Fog/Smoke":              "Weather - Fog/Smoke/Haze",
    "SV Were All Passengers Belted?":   "Were All Passengers Belted?",
    "SV Was Vehicle Towed?":            "Was Any Vehicle Towed?",
    "SV Any Air Bags Deployed?":        "Any Air Bags Deployed?",
}


# ===========================================================================
# TIME PERIOD DEFINITIONS
# ===========================================================================
# How we categorize hours of the day into named time periods.
# Each tuple is (start_hour, end_hour) where start is inclusive, end is exclusive.
# Special case: "Late Night" wraps around midnight (23 → 5).
TIME_PERIODS = {
    "Early Morning":  (5, 7),     # 5:00 AM – 6:59 AM
    "Morning Rush":   (7, 10),    # 7:00 AM – 9:59 AM
    "Late Morning":   (10, 12),   # 10:00 AM – 11:59 AM
    "Midday":         (12, 14),   # 12:00 PM – 1:59 PM
    "Afternoon":      (14, 17),   # 2:00 PM – 4:59 PM
    "Evening Rush":   (17, 20),   # 5:00 PM – 7:59 PM
    "Night":          (20, 23),   # 8:00 PM – 10:59 PM
    "Late Night":     (23, 5),    # 11:00 PM – 4:59 AM (wraps midnight)
}


# ===========================================================================
# CITY INFORMATION
# ===========================================================================
# The cities where Waymo operates, with their center coordinates for map display.
# The "code" matches the Location column in the Waymo Hub data (e.g., "SAN_FRANCISCO").
# The "name" is the human-readable display name for the website.
CITIES = {
    "SAN_FRANCISCO": {"name": "San Francisco", "state": "CA", "lat": 37.7749, "lon": -122.4194},
    "PHOENIX":       {"name": "Phoenix",       "state": "AZ", "lat": 33.4484, "lon": -112.0740},
    "LOS_ANGELES":   {"name": "Los Angeles",   "state": "CA", "lat": 34.0522, "lon": -118.2437},
    "AUSTIN":        {"name": "Austin",         "state": "TX", "lat": 30.2672, "lon": -97.7431},
    "ATLANTA":       {"name": "Atlanta",        "state": "GA", "lat": 33.7490, "lon": -84.3880},
}


# ===========================================================================
# WAYMO PUBLISHED SAFETY CONTEXT
# ===========================================================================
# Crash reduction percentages come from Waymo's peer-reviewed research.
# Source: https://waymo.com/safety/impact/
# Source: https://doi.org/10.1080/15389588.2025.2499887 (56.7M miles study)
#
# NOTE: total_rider_only_miles and data_through are now computed automatically
# from CSV1 in 01_download_data.py — no manual updates needed for those.
# The reduction percentages below are from Waymo's published comparisons and
# cannot be auto-derived (CSV3 is not publicly downloadable). These may need
# manual updates if Waymo publishes significantly revised figures.
WAYMO_PUBLISHED_STATS = {
    "miles_study_period": "56.7 million",       # From the peer-reviewed study
    "serious_crash_reduction_pct": 92,          # vs human drivers
    "injury_crash_reduction_pct": 82,           # vs human drivers
    "airbag_crash_reduction_pct": 83,           # vs human drivers
    "pedestrian_injury_reduction_pct": 92,      # vs human drivers
    "cyclist_injury_reduction_pct": 85,         # vs human drivers
    "motorcycle_injury_reduction_pct": 81,      # vs human drivers
    "source_url": "https://waymo.com/safety/impact/",
    "study_url": "https://doi.org/10.1080/15389588.2025.2499887",
}


# ===========================================================================
# LOCATION TYPE PATTERNS
# ===========================================================================
# Regex patterns to classify crash locations from narrative text.
# These are checked in order — first match wins.
# Used in 03_compute_statistics.py to categorize where crashes happen.
LOCATION_PATTERNS = {
    "Intersection": [
        r"\bintersection\b",   # \b = word boundary, so "intersection" but not "intersectional"
        r"\bcrossing\b",
        r"\bjunction\b",
    ],
    "Highway/Freeway": [
        r"\bhighway\b",
        r"\bfreeway\b",
        r"\bi-\d+\b",          # Matches interstate numbers like "I-10", "I-280"
        r"\bramp\b",
        r"\bexpressway\b",
    ],
    "Parking": [
        r"\bparking\b",
        r"\bgarage\b",
        r"\bvalet\b",
        r"\bparked\b",
    ],
    "Street/Road": [
        r"\bstreet\b",
        r"\broad\b",
        r"\bavenue\b",
        r"\bblvd\b",
        r"\bboulevard\b",
        r"\blane\b",
        r"\bdrive\b",
    ],
}
