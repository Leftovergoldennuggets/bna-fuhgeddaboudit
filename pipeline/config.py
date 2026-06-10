"""
config.py — Central configuration for the Waymo crash data pipeline
==========================================================================
ALL constants live here: URLs, file paths, time periods, metros, etc.
When something changes (new data URL, new city, etc.), update THIS file only.
==========================================================================
"""

import os

# ---------------------------------------------------------------------------
# Where the project root is (one level up from this pipeline/ directory)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ===========================================================================
# DATA SOURCE URLs
# ===========================================================================
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

# Waymo Safety Impact Data Hub — quarterly CSV releases.
# The filename changes every quarter (e.g., "202009-202512"). The URL is
# auto-detected in 01_download_data.py by probing recent quarter end dates.
WAYMO_STORAGE_BASE = (
    "https://storage.googleapis.com/waymo-uploads/files/documents/"
    "safety/safety-impact-data/"
)
WAYMO_HUB_CSV2_PREFIX = WAYMO_STORAGE_BASE + "CSV2%20-%20Crashes%20with%20SGO%20ID%20and%20Group%20Membership%20"
WAYMO_HUB_CSV1_PREFIX = WAYMO_STORAGE_BASE + "CSV1%20-%20RO%20Miles%20per%20Location%20"
# Fallback URLs in case auto-detection fails (update the date if it goes stale):
WAYMO_HUB_CSV2_FALLBACK = WAYMO_HUB_CSV2_PREFIX + "202009-202512-2022benchmark.csv"
WAYMO_HUB_CSV1_FALLBACK = WAYMO_HUB_CSV1_PREFIX + "202009-202512-2022benchmark.csv"


# ===========================================================================
# FILE PATHS
# ===========================================================================
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
WEB_DIR = os.path.join(PROJECT_ROOT, "data", "web")
STATIC_DIR = os.path.join(PROJECT_ROOT, "data", "static")

RAW_NHTSA_POST = os.path.join(RAW_DIR, "nhtsa_ads_post_june16.csv")
RAW_NHTSA_PRIOR = os.path.join(RAW_DIR, "nhtsa_ads_prior_june16.csv")
RAW_WAYMO_HUB = os.path.join(RAW_DIR, "waymo_hub_csv2.csv")
RAW_WAYMO_CSV1 = os.path.join(RAW_DIR, "waymo_hub_csv1.csv")

PROCESSED_MERGED = os.path.join(PROCESSED_DIR, "waymo_merged.csv")
PROCESSED_UNMATCHED = os.path.join(PROCESSED_DIR, "waymo_unmapped_cities.csv")

WEB_SITE_DATA = os.path.join(WEB_DIR, "site-data.json")
WEB_CRASH_DATA = os.path.join(WEB_DIR, "crash_data.json")
WEB_SERIOUS_INCIDENTS = os.path.join(WEB_DIR, "serious_incidents.json")

# Geocode cache — stores address → lat/lon lookups so we don't re-geocode
# the same address every time the pipeline runs. Committed to git.
GEOCODE_CACHE = os.path.join(WEB_DIR, "geocode_cache.json")

# Static data files — manually maintained or auto-refreshed reference data
STATIC_MILES_BY_CITY = os.path.join(STATIC_DIR, "miles_by_city.json")
STATIC_MILEAGE_MILESTONES = os.path.join(STATIC_DIR, "mileage_milestones.json")


# ===========================================================================
# FILTER SETTINGS
# ===========================================================================
WAYMO_ENTITY_NAME = "Waymo LLC"  # Exact string in the NHTSA "Reporting Entity" column

# NHTSA "Driver / Operator Type" values that mean a human was supervising the
# drive from inside the vehicle. Blank/NaN means there was no operator — i.e.
# fully driverless operation. "Remote" means remote assistance only (the
# vehicle still drives itself), so we count it as driverless.
SUPERVISED_OPERATOR_TYPES = {
    "In-Vehicle (Commercial / Test)",
    "In-Vehicle and Remote (Commercial / Test)",
    "Other, see Narrative",
}


# ===========================================================================
# COLUMN REQUIREMENTS & HARMONIZATION
# ===========================================================================
# Columns each input file must contain. Validated loudly at the start of
# 02_merge_and_clean.py so format changes fail fast with a clear message
# instead of a cryptic KeyError halfway through the pipeline.
REQUIRED_NHTSA_COLUMNS = [
    "Report ID",
    "Report Version",
    "Reporting Entity",
    "Incident Date",
    "Incident Time (24:00)",
    "City",
    "State",
    "Highest Injury Severity Alleged",
    "Narrative",
    "Driver / Operator Type",
    "Crash With",
    "SV Pre-Crash Movement",
    "SV Precrash Speed (MPH)",
]

REQUIRED_HUB_COLUMNS = [
    "SGO Report ID",
    "Year Month",
    "State",
    "County",
    "Crash Type",
    "Incident Date",
    "Location Address / Description",
]

# NHTSA renamed some columns when they switched from Amendment 2 to Amendment 3.
# We rename the PRIOR (Amendment 2) columns to match the POST (Amendment 3) names.
COLUMN_RENAMES_PRIOR_TO_POST = {
    "Weather - Fog/Smoke":              "Weather - Fog/Smoke/Haze",
    "SV Were All Passengers Belted?":   "Were All Passengers Belted?",
    "SV Was Vehicle Towed?":            "Was Any Vehicle Towed?",
    "SV Any Air Bags Deployed?":        "Any Air Bags Deployed?",
}


# ===========================================================================
# TIME PERIOD DEFINITIONS
# ===========================================================================
# Each tuple is (start_hour, end_hour) where start is inclusive, end exclusive.
# Special case: "Late Night" wraps around midnight (23 → 5).
TIME_PERIODS = {
    "Early Morning":  (5, 7),
    "Morning Rush":   (7, 10),
    "Late Morning":   (10, 12),
    "Midday":         (12, 14),
    "Afternoon":      (14, 17),
    "Evening Rush":   (17, 20),
    "Night":          (20, 23),
    "Late Night":     (23, 5),
}


# ===========================================================================
# METRO AREAS
# ===========================================================================
# Every metro where Waymo operates or has driverless crashes on record.
#
#   counties: county names in Waymo's hub CSV2 that belong to this metro
#   cities:   city names in NHTSA's City column that belong to this metro
#             (matched case-insensitively after whitespace normalization,
#             keyed together with the metro's state)
#   status:   "public"   — open rider-only service
#             "testing"  — driverless validation / supervised testing
#   public_since: year-month public rider-only service started (display only)
#
# A crash whose county/city is not listed anywhere lands in the "OTHER"
# bucket — it stays in the totals and on the map, and the pipeline prints a
# loud warning so the mapping can be extended. Nothing is silently dropped.
CITIES = {
    "SAN_FRANCISCO": {
        "name": "San Francisco", "state": "CA", "lat": 37.7749, "lon": -122.4194,
        "status": "public", "public_since": "2023",
        # Covers Waymo's whole Bay Area territory: SF, the Peninsula, and
        # (since Nov 2025) San Jose. Waymo reports these as one region.
        "counties": ["San Francisco", "San Mateo", "Santa Clara"],
        "cities": [
            "San Francisco", "Daly City", "South San Francisco", "Brisbane",
            "San Bruno", "Burlingame", "Millbrae", "San Mateo", "Foster City",
            "Belmont", "San Carlos", "Redwood City", "Menlo Park", "Palo Alto",
            "East Palo Alto", "Mountain View", "Los Altos", "Sunnyvale",
            "Santa Clara", "San Jose", "Cupertino", "Campbell", "Milpitas",
            "Colma", "Pacifica", "Portola Valley", "Atherton", "Hillsborough",
            "Woodside", "Oakland", "Emeryville", "Berkeley",
        ],
    },
    "PHOENIX": {
        "name": "Phoenix", "state": "AZ", "lat": 33.4484, "lon": -112.0740,
        "status": "public", "public_since": "2020",
        "counties": ["Maricopa", "Pinal"],
        "cities": [
            "Phoenix", "Tempe", "Scottsdale", "Mesa", "Chandler", "Gilbert",
            "Glendale", "Paradise Valley", "Guadalupe", "Sacaton", "Peoria",
            "Avondale", "Goodyear",
        ],
    },
    "LOS_ANGELES": {
        "name": "Los Angeles", "state": "CA", "lat": 34.0522, "lon": -118.2437,
        "status": "public", "public_since": "2024",
        "counties": ["Los Angeles"],
        "cities": [
            "Los Angeles", "Santa Monica", "Venice", "Inglewood", "Culver City",
            "West Hollywood", "Beverly Hills", "Lennox", "Marina del Rey",
            "Hawthorne", "El Segundo", "Burbank", "Glendale", "Compton",
            "Gardena", "Pasadena", "Westchester", "Playa del Rey",
        ],
    },
    "AUSTIN": {
        "name": "Austin", "state": "TX", "lat": 30.2672, "lon": -97.7431,
        "status": "public", "public_since": "2025",
        "counties": ["Travis", "Williamson"],
        "cities": ["Austin", "Del Valle", "Round Rock", "Pflugerville"],
    },
    "ATLANTA": {
        "name": "Atlanta", "state": "GA", "lat": 33.7490, "lon": -84.3880,
        "status": "public", "public_since": "2025",
        "counties": ["Fulton", "DeKalb"],
        "cities": [
            "Atlanta", "Decatur", "Sandy Springs", "Brookhaven", "East Point",
            "College Park",
        ],
    },
    "MIAMI": {
        "name": "Miami", "state": "FL", "lat": 25.7617, "lon": -80.1918,
        "status": "public", "public_since": "2026",
        "counties": ["Miami-Dade"],
        "cities": [
            "Miami", "Miami Beach", "Coral Gables", "Hialeah", "Doral",
            "North Miami", "Miami Gardens", "Key Biscayne",
        ],
    },
    "ORLANDO": {
        "name": "Orlando", "state": "FL", "lat": 28.5383, "lon": -81.3792,
        "status": "public", "public_since": "2026",
        "counties": ["Orange"],
        "cities": ["Orlando", "Winter Park", "Maitland"],
    },
    "DALLAS": {
        "name": "Dallas", "state": "TX", "lat": 32.7767, "lon": -96.7970,
        "status": "public", "public_since": "2026",
        "counties": ["Dallas", "Ellis"],
        "cities": [
            "Dallas", "Irving", "Ennis", "Garland", "Richardson", "Plano",
            "Addison", "Mesquite", "Grand Prairie",
        ],
    },
    "HOUSTON": {
        "name": "Houston", "state": "TX", "lat": 29.7604, "lon": -95.3698,
        "status": "public", "public_since": "2026",
        "counties": ["Harris"],
        "cities": ["Houston", "Bellaire", "Pasadena"],
    },
    "SAN_ANTONIO": {
        "name": "San Antonio", "state": "TX", "lat": 29.4252, "lon": -98.4946,
        "status": "public", "public_since": "2026",
        "counties": ["Bexar"],
        "cities": ["San Antonio"],
    },
    "NASHVILLE": {
        "name": "Nashville", "state": "TN", "lat": 36.1627, "lon": -86.7816,
        "status": "public", "public_since": "2026",
        "counties": ["Davidson"],
        "cities": ["Nashville"],
    },
    "WASHINGTON_DC": {
        "name": "Washington, D.C.", "state": "DC", "lat": 38.9072, "lon": -77.0369,
        "status": "testing", "public_since": None,
        "counties": ["District of Columbia"],
        "cities": ["Washington"],
    },
    "DENVER": {
        "name": "Denver", "state": "CO", "lat": 39.7392, "lon": -104.9903,
        "status": "testing", "public_since": None,
        "counties": ["Denver", "Arapahoe", "Jefferson"],
        "cities": ["Denver", "Aurora", "Lakewood", "Englewood"],
    },
    "PHILADELPHIA": {
        "name": "Philadelphia", "state": "PA", "lat": 39.9526, "lon": -75.1652,
        "status": "testing", "public_since": None,
        "counties": ["Philadelphia"],
        "cities": ["Philadelphia"],
    },
}

# Bucket for crashes in places we haven't mapped to a metro yet.
# They keep showing up in totals and on the map (geocoded by city name).
OTHER_METRO_CODE = "OTHER"

# Metros Waymo has publicly announced but where no crashes have been
# reported yet. Shown on the expansion map only — not part of crash stats.
# Update this list as announcements land (see MAINTENANCE.md).
# As of June 2026 (source: waymo.com/updates "coming soon" + press coverage).
ANNOUNCED_METROS = [
    {"name": "Las Vegas",   "state": "NV", "lat": 36.1699, "lon": -115.1398},
    {"name": "San Diego",   "state": "CA", "lat": 32.7157, "lon": -117.1611},
    {"name": "Detroit",     "state": "MI", "lat": 42.3314, "lon": -83.0458},
    {"name": "New York",    "state": "NY", "lat": 40.7128, "lon": -74.0060},
    {"name": "Minneapolis", "state": "MN", "lat": 44.9778, "lon": -93.2650},
    {"name": "New Orleans", "state": "LA", "lat": 29.9511, "lon": -90.0715},
    {"name": "Tampa",       "state": "FL", "lat": 27.9506, "lon": -82.4572},
    {"name": "Baltimore",   "state": "MD", "lat": 39.2904, "lon": -76.6122},
    {"name": "Pittsburgh",  "state": "PA", "lat": 40.4406, "lon": -79.9959},
    {"name": "St. Louis",   "state": "MO", "lat": 38.6270, "lon": -90.1994},
    {"name": "Boston",      "state": "MA", "lat": 42.3601, "lon": -71.0589},
    {"name": "Charlotte",   "state": "NC", "lat": 35.2271, "lon": -80.8431},
    {"name": "Chicago",     "state": "IL", "lat": 41.8781, "lon": -87.6298},
    {"name": "Sacramento",  "state": "CA", "lat": 38.5816, "lon": -121.4944},
    {"name": "Seattle",     "state": "WA", "lat": 47.6062, "lon": -122.3321},
    {"name": "Portland",    "state": "OR", "lat": 45.5152, "lon": -122.6784},
]


# ===========================================================================
# WAYMO PUBLISHED SAFETY CONTEXT
# ===========================================================================
# Crash reduction percentages come from Waymo's peer-reviewed research.
# Source: https://waymo.com/safety/impact/
# Source: https://doi.org/10.1080/15389588.2025.2499887 (56.7M miles study)
#
# NOTE: total_rider_only_miles and data_through are computed automatically
# from CSV1 in 01_download_data.py. The reduction percentages below are from
# Waymo's published comparisons and cannot be auto-derived. Update them
# manually if Waymo publishes significantly revised figures.
WAYMO_PUBLISHED_STATS = {
    "miles_study_period": "56.7 million",
    "serious_crash_reduction_pct": 92,
    "injury_crash_reduction_pct": 82,
    "airbag_crash_reduction_pct": 83,
    "pedestrian_injury_reduction_pct": 92,
    "cyclist_injury_reduction_pct": 85,
    "motorcycle_injury_reduction_pct": 81,
    "source_url": "https://waymo.com/safety/impact/",
    "study_url": "https://doi.org/10.1080/15389588.2025.2499887",
}


# ===========================================================================
# LOCATION TYPE PATTERNS
# ===========================================================================
# Regex patterns to classify crash locations from narrative text.
# Checked in order — first match wins.
LOCATION_PATTERNS = {
    "Intersection": [
        r"\bintersection\b",
        r"\bcrossing\b",
        r"\bjunction\b",
    ],
    "Highway/Freeway": [
        r"\bhighway\b",
        r"\bfreeway\b",
        r"\bi-\d+\b",
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
