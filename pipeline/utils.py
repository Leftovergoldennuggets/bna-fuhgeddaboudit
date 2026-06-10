"""
utils.py — Shared helpers for the Waymo crash data pipeline
==========================================================================
Pure functions used by multiple pipeline steps. Everything here is
unit-tested in tests/ — keep these functions free of file/network I/O.
==========================================================================
"""

import re

import pandas as pd

from pipeline.config import (
    CITIES, OTHER_METRO_CODE, SUPERVISED_OPERATOR_TYPES,
    TIME_PERIODS, LOCATION_PATTERNS,
)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_place(value):
    """Normalize a city/county/state string: trim, collapse whitespace.

    NHTSA data contains stray whitespace variants of the same city name
    (e.g. "San Francisco " vs "San Francisco"), which would otherwise be
    counted as different places.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


# ---------------------------------------------------------------------------
# Metro mapping
# ---------------------------------------------------------------------------

# Waymo's hub uses full state names ("Arizona"); NHTSA uses postal codes
# ("AZ"). Everything is normalized to postal codes before lookups.
_STATE_NAME_TO_CODE = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN",
    "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA",
    "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI",
    "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}


def normalize_state(value):
    """Normalize a state to its 2-letter postal code ("Arizona" → "AZ")."""
    state = normalize_place(value).upper()
    return _STATE_NAME_TO_CODE.get(state, state)


def _build_lookup_tables():
    """Build (state, county) → metro and (state, city) → metro lookups."""
    county_lookup = {}
    city_lookup = {}
    for code, info in CITIES.items():
        state = info["state"].upper()
        for county in info.get("counties", []):
            county_lookup[(state, county.lower())] = code
        for city in info.get("cities", []):
            city_lookup[(state, city.lower())] = code
    return county_lookup, city_lookup


_COUNTY_LOOKUP, _CITY_LOOKUP = _build_lookup_tables()

# Core city name → metro, used as a last resort when the state field is
# wrong or missing but the city name unambiguously identifies a metro
# (NHTSA has occasional data-entry errors like City="Phoenix", State="CA").
_CORE_CITY_LOOKUP = {info["name"].lower(): code for code, info in CITIES.items()}


def county_to_metro(state, county):
    """Map a hub (State, County) pair to a metro code, or None."""
    state = normalize_state(state)
    county = normalize_place(county).lower()
    if not county:
        return None
    return _COUNTY_LOOKUP.get((state, county))


def city_to_metro(state, city):
    """Map an NHTSA (State, City) pair to a metro code.

    Falls back to a core-city-name match when the (state, city) pair is
    unknown but the city name is itself a metro core city (handles NHTSA
    data-entry errors in the State column). Returns None when unmapped.
    """
    state = normalize_state(state)
    city = normalize_place(city).lower()
    if not city:
        return None
    metro = _CITY_LOOKUP.get((state, city))
    if metro:
        return metro
    return _CORE_CITY_LOOKUP.get(city)


def resolve_metro(county_state, county, city_state, city):
    """Resolve a crash to a metro code using county first, then city.

    The county and city can come from different sources with different
    state encodings (hub: "Arizona", NHTSA: "AZ"), so each lookup takes
    its own state. Returns (metro_code, mapped) where mapped is False
    when the crash landed in the OTHER bucket.
    """
    metro = county_to_metro(county_state, county)
    if metro is None:
        metro = city_to_metro(city_state, city)
    if metro is None:
        return OTHER_METRO_CODE, False
    return metro, True


# ---------------------------------------------------------------------------
# Operation type
# ---------------------------------------------------------------------------

def classify_operation(operator_type):
    """Classify a crash as 'driverless' or 'supervised' operation.

    NHTSA's "Driver / Operator Type" is blank for fully driverless trips.
    "Remote" means remote assistance only — the vehicle drives itself —
    so it counts as driverless. Anything with a human in the vehicle
    (or unclear: "Other, see Narrative") counts as supervised.
    """
    value = normalize_place(operator_type)
    if not value:
        return "driverless"
    if value in SUPERVISED_OPERATOR_TYPES:
        return "supervised"
    if value == "Remote (Commercial / Test)":
        return "driverless"
    # Unknown new value: treat as supervised (conservative for the
    # headline driverless count) and let the caller warn about it.
    return "supervised"


# ---------------------------------------------------------------------------
# Date / time parsing
# ---------------------------------------------------------------------------

def parse_time(time_str):
    """Parse "14:30" or "1430" into (hour, minute); (None, None) on failure."""
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


_MONTH_ABBREVIATIONS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_incident_date(date_str):
    """Parse an incident date from either data source.

    Returns (timestamp, precision) where precision is "day" or "month".
    NHTSA's public files redact exact dates to month precision
    ("MAR-2026" → 2026-03-01, precision "month"). The Waymo hub provides
    full dates in several formats (precision "day").
    Returns (None, None) when unparseable.
    """
    if pd.isna(date_str):
        return None, None
    date_str = str(date_str).strip()
    if not date_str:
        return None, None

    # NHTSA month-precision format: "MAR-2026"
    match = re.fullmatch(r"([A-Za-z]{3})-(\d{4})", date_str)
    if match:
        month = _MONTH_ABBREVIATIONS.get(match.group(1).upper())
        if month:
            return pd.Timestamp(int(match.group(2)), month, 1), "month"
        return None, None

    for fmt in ["%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y"]:
        try:
            return pd.to_datetime(date_str, format=fmt), "day"
        except (ValueError, TypeError):
            continue
    try:
        return pd.to_datetime(date_str), "day"
    except (ValueError, TypeError):
        return None, None


def to_year_month(timestamp):
    """Convert a Timestamp to the hub's integer YYYYMM format (or None)."""
    if timestamp is None or pd.isna(timestamp):
        return None
    return timestamp.year * 100 + timestamp.month


def categorize_time_period(hour):
    """Assign a named time period to an hour (0-23); handles midnight wrap."""
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


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

def severity_level(severity_value, has_injury=False):
    """Classify NHTSA "Highest Injury Severity Alleged" into a level.

    Returns one of: "fatal", "serious", "moderate", "minor", "none".
    """
    raw = "" if pd.isna(severity_value) else str(severity_value).lower()
    if "fatal" in raw:
        return "fatal"
    if "serious" in raw:
        return "serious"
    if "moderate" in raw:
        return "moderate"
    if "minor" in raw or has_injury:
        return "minor"
    return "none"


def is_moderate_plus(severity_value):
    """True when severity is moderate, serious, or fatal."""
    return severity_level(severity_value) in ("moderate", "serious", "fatal")


# ---------------------------------------------------------------------------
# Location type extraction
# ---------------------------------------------------------------------------

def extract_location_type(row):
    """Determine crash location type from narrative/address text fields."""
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
    """Clean a lat/lon value; NHTSA redacts these as "[PERSONALLY ...]"."""
    if pd.isna(val):
        return None
    try:
        val_str = str(val).strip()
        if "PERSONALLY" in val_str.upper() or val_str == "" or "[" in val_str:
            return None
        return float(val_str)
    except (ValueError, TypeError):
        return None


def clean_zip(value):
    """Normalize a zip code to 5 digits, or None.

    Handles pandas float artifacts ("94103.0") and NHTSA's redaction
    placeholder ("[MAY CONTAIN PERSONALLY IDENTIFIABLE INFORMATION]").
    """
    if pd.isna(value):
        return None
    z = str(value).strip()
    if len(z) >= 5 and z[:5].isdigit():
        return z[:5]
    return None


def geocode_cache_key(address, city, state, metro_code):
    """Cache key for a street-address geocode.

    v2 keys include the crash's ACTUAL city and state. The v1 scheme keyed
    by metro code, which made the geocoder search suburb addresses in the
    metro's core city (e.g. a Tempe intersection searched as "Phoenix, AZ")
    — sometimes silently matching a same-named street in the wrong city.
    """
    city = normalize_place(city)
    state = normalize_state(state)
    if city and state:
        return f"v2|{address}|{city}|{state}"
    return f"v2|{address}|{metro_code}"


def reverse_cache_key(lat, lon):
    """Cache key for a reverse-geocode (coordinates → zip) lookup."""
    return f"__rev__{lat:.4f},{lon:.4f}"


def validate_columns(df, required, source_name):
    """Fail fast with a clear message when an input file changes format."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(
            f"ERROR: {source_name} is missing expected column(s): {missing}\n"
            f"The upstream data format may have changed. Compare the file's "
            f"header against the required columns in pipeline/config.py and "
            f"update the pipeline accordingly."
        )
