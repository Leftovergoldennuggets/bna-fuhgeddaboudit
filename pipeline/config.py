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
# Archived, but NHTSA still revises it occasionally (last modified Mar 2026),
# so it is re-downloaded on every run like the current file.
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
# CSV3 holds Waymo's own comparison of its crash rates against human
# benchmarks (with confidence intervals), overall and per service area.
WAYMO_HUB_CSV3_PREFIX = WAYMO_STORAGE_BASE + "CSV3%20-%20Collision%20Counts%20and%20Comparison%20to%20Benchmarks%20"
# Fallback URLs in case auto-detection fails (update the date if it goes stale):
WAYMO_HUB_CSV2_FALLBACK = WAYMO_HUB_CSV2_PREFIX + "202009-202606-2022benchmark.csv"
WAYMO_HUB_CSV1_FALLBACK = WAYMO_HUB_CSV1_PREFIX + "202009-202606-2022benchmark.csv"
WAYMO_HUB_CSV3_FALLBACK = WAYMO_HUB_CSV3_PREFIX + "202009-202606-2022benchmark.csv"

# Every quarterly CSV1 release stays online, each holding CUMULATIVE
# rider-only miles per service area since Sept 2020. Downloading them all
# gives a quarterly mileage time series (and crash rates over time).
# 202409 is the oldest quarter-end release Waymo still hosts (an off-cycle
# 202407 release also exists; it is cited in mileage_milestones.json).
WAYMO_MILEAGE_HISTORY_START = "202409"


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
RAW_WAYMO_CSV3 = os.path.join(RAW_DIR, "waymo_hub_csv3.csv")

PROCESSED_MERGED = os.path.join(PROCESSED_DIR, "waymo_merged.csv")
PROCESSED_UNMATCHED = os.path.join(PROCESSED_DIR, "waymo_unmapped_cities.csv")

WEB_SITE_DATA = os.path.join(WEB_DIR, "site-data.json")
WEB_CRASH_DATA = os.path.join(WEB_DIR, "crash_data.json")
WEB_SERIOUS_INCIDENTS = os.path.join(WEB_DIR, "serious_incidents.json")
WEB_CRASH_CSV = os.path.join(WEB_DIR, "waymo_crashes.csv")
WEB_UPDATE_HISTORY = os.path.join(WEB_DIR, "update_history.json")

# Geocode cache — stores address → lat/lon lookups so we don't re-geocode
# the same address every time the pipeline runs. Committed to git.
GEOCODE_CACHE = os.path.join(WEB_DIR, "geocode_cache.json")

# Static data files — manually maintained or auto-refreshed reference data
STATIC_MILES_BY_CITY = os.path.join(STATIC_DIR, "miles_by_city.json")
STATIC_MILEAGE_MILESTONES = os.path.join(STATIC_DIR, "mileage_milestones.json")
STATIC_MILES_QUARTERLY = os.path.join(STATIC_DIR, "miles_quarterly.json")
STATIC_ZIP_REFERENCE = os.path.join(STATIC_DIR, "zip_reference.json")

# Editorial review baseline — the crashes a human has already reviewed and
# written prose about (e.g. the fatal-crash summaries in faq.html). The
# editorial check flags anything not in here. See MAINTENANCE.md.
STATIC_EDITORIAL_BASELINE = os.path.join(STATIC_DIR, "editorial_baseline.json")
EDITORIAL_ALERTS = os.path.join(PROCESSED_DIR, "editorial_alerts.md")


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
#   testing:  for "testing" metros, "driverless" (no one in the driver's
#             seat) or "supervised" (safety driver required)
#   public_since: year public rider-only service started (display only)
#   launched: month public rider-only service started, "YYYY-MM" (display)
#
# A crash whose county/city is not listed anywhere lands in the "OTHER"
# bucket — it stays in the totals and on the map, and the pipeline prints a
# loud warning so the mapping can be extended. Nothing is silently dropped.
CITIES = {
    "SAN_FRANCISCO": {
        "name": "San Francisco", "state": "CA", "lat": 37.7749, "lon": -122.4194,
        "status": "public", "public_since": "2023", "launched": "2023-08",
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
        "status": "public", "public_since": "2020", "launched": "2020-10",
        "counties": ["Maricopa", "Pinal"],
        "cities": [
            "Phoenix", "Tempe", "Scottsdale", "Mesa", "Chandler", "Gilbert",
            "Glendale", "Paradise Valley", "Guadalupe", "Sacaton", "Peoria",
            "Avondale", "Goodyear",
        ],
    },
    "LOS_ANGELES": {
        "name": "Los Angeles", "state": "CA", "lat": 34.0522, "lon": -118.2437,
        "status": "public", "public_since": "2024", "launched": "2024-03",
        "counties": ["Los Angeles"],
        "cities": [
            "Los Angeles", "Santa Monica", "Venice", "Inglewood", "Culver City",
            "West Hollywood", "Beverly Hills", "Lennox", "Marina del Rey",
            "Hawthorne", "El Segundo", "Burbank", "Glendale", "Compton",
            "Gardena", "Pasadena", "Westchester", "Playa del Rey", "Carson",
            "Harbor City", "Torrance",
        ],
    },
    "AUSTIN": {
        "name": "Austin", "state": "TX", "lat": 30.2672, "lon": -97.7431,
        "status": "public", "public_since": "2025", "launched": "2025-03",
        "counties": ["Travis", "Williamson"],
        "cities": ["Austin", "Del Valle", "Round Rock", "Pflugerville"],
    },
    "ATLANTA": {
        "name": "Atlanta", "state": "GA", "lat": 33.7490, "lon": -84.3880,
        "status": "public", "public_since": "2025", "launched": "2025-06",
        "counties": ["Fulton", "DeKalb"],
        "cities": [
            "Atlanta", "Decatur", "Sandy Springs", "Brookhaven", "East Point",
            "College Park",
        ],
    },
    "MIAMI": {
        "name": "Miami", "state": "FL", "lat": 25.7617, "lon": -80.1918,
        "status": "public", "public_since": "2026", "launched": "2026-01",
        "counties": ["Miami-Dade"],
        "cities": [
            "Miami", "Miami Beach", "Coral Gables", "Hialeah", "Doral",
            "North Miami", "Miami Gardens", "Key Biscayne",
        ],
    },
    "ORLANDO": {
        "name": "Orlando", "state": "FL", "lat": 28.5383, "lon": -81.3792,
        "status": "public", "public_since": "2026", "launched": "2026-02",
        "counties": ["Orange"],
        "cities": ["Orlando", "Winter Park", "Maitland"],
    },
    "DALLAS": {
        "name": "Dallas", "state": "TX", "lat": 32.7767, "lon": -96.7970,
        "status": "public", "public_since": "2026", "launched": "2026-02",
        "counties": ["Dallas", "Ellis"],
        "cities": [
            "Dallas", "Irving", "Ennis", "Garland", "Richardson", "Plano",
            "Addison", "Mesquite", "Grand Prairie",
        ],
    },
    "HOUSTON": {
        "name": "Houston", "state": "TX", "lat": 29.7604, "lon": -95.3698,
        "status": "public", "public_since": "2026", "launched": "2026-02",
        "counties": ["Harris"],
        "cities": ["Houston", "Bellaire", "Pasadena"],
    },
    "SAN_ANTONIO": {
        "name": "San Antonio", "state": "TX", "lat": 29.4252, "lon": -98.4946,
        # Paused Apr 20 – mid-Sept 2026 after an empty vehicle was swept
        # into Salado Creek (floodwater recall).
        "status": "public", "public_since": "2026", "launched": "2026-02",
        "counties": ["Bexar"],
        "cities": ["San Antonio"],
    },
    "NASHVILLE": {
        "name": "Nashville", "state": "TN", "lat": 36.1627, "lon": -86.7816,
        "status": "public", "public_since": "2026", "launched": "2026-04",
        "counties": ["Davidson"],
        "cities": ["Nashville"],
    },
    "DENVER": {
        "name": "Denver", "state": "CO", "lat": 39.7392, "lon": -104.9903,
        "status": "public", "public_since": "2026", "launched": "2026-09",
        "counties": ["Denver", "Arapahoe", "Jefferson"],
        "cities": ["Denver", "Aurora", "Lakewood", "Englewood", "Glendale"],
    },
    "SAN_DIEGO": {
        "name": "San Diego", "state": "CA", "lat": 32.7157, "lon": -117.1611,
        "status": "public", "public_since": "2026", "launched": "2026-09",
        "counties": ["San Diego"],
        "cities": ["San Diego", "La Jolla", "National City", "Chula Vista",
                   "Coronado", "Del Mar"],
    },
    "TAMPA": {
        "name": "Tampa", "state": "FL", "lat": 27.9506, "lon": -82.4572,
        "status": "public", "public_since": "2026", "launched": "2026-09",
        "counties": ["Hillsborough", "Pinellas"],
        "cities": ["Tampa", "St. Petersburg", "Saint Petersburg", "Clearwater"],
    },
    "LAS_VEGAS": {
        "name": "Las Vegas", "state": "NV", "lat": 36.1699, "lon": -115.1398,
        "status": "public", "public_since": "2026", "launched": "2026-09",
        "counties": ["Clark"],
        "cities": ["Las Vegas", "Paradise", "Spring Valley", "Enterprise",
                   "Winchester", "Henderson", "North Las Vegas"],
    },
    "DETROIT": {
        "name": "Detroit", "state": "MI", "lat": 42.3314, "lon": -83.0458,
        "status": "testing", "testing": "driverless", "public_since": None,
        "counties": ["Wayne"],
        "cities": ["Detroit", "Dearborn", "Hamtramck"],
    },
    "WASHINGTON_DC": {
        # D.C. law requires a human driver; testing is supervised only.
        "name": "Washington, D.C.", "state": "DC", "lat": 38.9072, "lon": -77.0369,
        "status": "testing", "testing": "supervised", "public_since": None,
        "counties": ["District of Columbia"],
        "cities": ["Washington"],
    },
    "PHILADELPHIA": {
        # PennDOT permits operation only with a safety driver.
        "name": "Philadelphia", "state": "PA", "lat": 39.9526, "lon": -75.1652,
        "status": "testing", "testing": "supervised", "public_since": None,
        "counties": ["Philadelphia"],
        "cities": ["Philadelphia"],
    },
}

# Bucket for crashes in places we haven't mapped to a metro yet.
# They keep showing up in totals and on the map (geocoded by city name).
OTHER_METRO_CODE = "OTHER"

# U.S. metros Waymo has announced for future service (testing, mapping or
# a stated launch plan) that are not in CITIES above. Shown as hollow
# circles on the intro map only — not part of crash stats. Each entry was
# checked against Waymo announcements or major coverage (Oct 2026); see
# OVERHAUL_LOG_2026-10.md. Update as announcements land (MAINTENANCE.md).
ANNOUNCED_METROS = [
    {"name": "New York",    "state": "NY", "lat": 40.7128, "lon": -74.0060},
    {"name": "Minneapolis", "state": "MN", "lat": 44.9778, "lon": -93.2650},
    {"name": "New Orleans", "state": "LA", "lat": 29.9511, "lon": -90.0715},
    {"name": "Baltimore",   "state": "MD", "lat": 39.2904, "lon": -76.6122},
    {"name": "Pittsburgh",  "state": "PA", "lat": 40.4406, "lon": -79.9959},
    {"name": "St. Louis",   "state": "MO", "lat": 38.6270, "lon": -90.1994},
    {"name": "Charlotte",   "state": "NC", "lat": 35.2271, "lon": -80.8431},
    {"name": "Chicago",     "state": "IL", "lat": 41.8781, "lon": -87.6298},
    {"name": "Seattle",     "state": "WA", "lat": 47.6062, "lon": -122.3321},
    {"name": "Portland",    "state": "OR", "lat": 45.5152, "lon": -122.6784},
]


# ===========================================================================
# WAYMO PUBLISHED SAFETY CONTEXT
# ===========================================================================
# Waymo's own comparisons against human benchmarks are read from hub CSV3
# every run (see benchmark_summary in utils.py) — nothing here is a
# hand-typed percentage any more. This block only holds the citations.
WAYMO_PUBLISHED_STATS = {
    "source_url": "https://waymo.com/safety/impact/",
    "study_url": "https://doi.org/10.1080/15389588.2025.2499887",
    "study_citation": "Kusano et al. (2025), Traffic Injury Prevention",
}

# CSV3 outcomes shown on the site, in display order. Waymo's hub headline
# uses the "dynamic" human benchmark, which in CSV3 is the row WITHOUT a
# "(non-Dynamic)" suffix (release notes, Dec 2025). "Any Fatal" is the
# exception: its dynamic row is labelled explicitly.
BENCHMARK_OUTCOMES = [
    ("serious_injury", "Suspected Serious Injury+", "Suspected Serious Injury+"),
    ("any_injury",     "Any Injury",                "Any-injury-reported"),
    ("airbag",         "Any Airbag Deployment",     "Any Airbag Deployment"),
    ("police",         "Police Report",             "Police-reported"),
    ("fatal",          "Any Fatal",                 "Any Fatal (Dynamic)"),
]

# The date NHTSA's Third Amended Standing General Order took effect. It
# raised the bar for reporting minor property-damage-only crashes, so crash
# COUNTS (and per-mile rates) before and after are not like-for-like.
SGO_AMENDMENT_3_DATE = "2025-06-16"


# ===========================================================================
# WAYMO CSV1 LOCATION NAMES → METRO CODES
# ===========================================================================
# CSV1 has changed format over time. Until Sept 2025 rows were named after
# Waymo's operations depots ("SAN_FRANCISCO", "MOUNTAIN_VIEW"); since Dec
# 2025 they are counties plus aggregate service areas ("San Francisco Bay
# Area" = San Francisco + San Mateo + Santa Clara counties). Aggregates
# win over their component counties. Counties not listed here are mapped
# through CITIES[...]["counties"]; anything else triggers a warning.
CSV1_TOTAL_LABEL = "All Locations (mileage blended)"
CSV1_AGGREGATES = {
    "San Francisco Bay Area": "SAN_FRANCISCO",
    "Atlanta Area": "ATLANTA",
}
CSV1_DEPOTS = {
    "SAN_FRANCISCO": "SAN_FRANCISCO",
    "MOUNTAIN_VIEW": "SAN_FRANCISCO",
    "PHOENIX": "PHOENIX",
    "LOS_ANGELES": "LOS_ANGELES",
    "AUSTIN": "AUSTIN",
    "ATLANTA": "ATLANTA",
}


# ===========================================================================
# ROADWAY TYPE
# ===========================================================================
# Crash location type comes from NHTSA's structured "Roadway Type" field,
# filled in by the reporting company for every crash. (An earlier version
# guessed it from narrative text with regexes, which counted any mention of
# a "parked vehicle" as a parking-lot crash — see OVERHAUL_LOG_2026-10.md.)
ROADWAY_TYPE_LABELS = {
    "Street": "Street",
    "Intersection": "Intersection",
    "Parking Lot": "Parking lot",
    "Highway / Freeway": "Highway/freeway",
    "Traffic Circle": "Traffic circle",
}
