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
    TIME_PERIODS, ROADWAY_TYPE_LABELS,
    CSV1_TOTAL_LABEL, CSV1_AGGREGATES, CSV1_DEPOTS,
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


_TEST_DRIVER_PATTERN = re.compile(
    r"(test|safety) driver was present|in the driver'?s seating position",
    re.IGNORECASE,
)


def narrative_says_test_driver(narrative):
    """True when a crash narrative states a human test driver was aboard.

    NHTSA's "Driver / Operator Type" is occasionally left blank even though
    Waymo's own narrative says "a test driver was present (in the driver's
    seating position)". Used as a fallback for rows Waymo's rider-only hub
    does not contain (see add_unified_columns in 02_merge_and_clean.py).
    """
    if narrative is None or (isinstance(narrative, float) and pd.isna(narrative)):
        return False
    return bool(_TEST_DRIVER_PATTERN.search(str(narrative)))


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
# Roadway type
# ---------------------------------------------------------------------------

def roadway_type(value):
    """Map NHTSA's structured "Roadway Type" to a display label.

    Blank, "Unknown" and any value NHTSA adds in future fall back to
    "Other/unknown" so they stay visible in the totals.
    """
    return ROADWAY_TYPE_LABELS.get(normalize_place(value), "Other/unknown")


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


def geocode_cache_key(address, city, state, metro_code, zip_code=None):
    """Cache key for a street-address geocode.

    v3 keys (used when Waymo reported a ZIP code) include that ZIP: those
    results have been checked to land inside the ZIP's area. v2 keys
    include the crash's ACTUAL city and state. (The retired v1 scheme keyed
    by metro code, which made the geocoder search suburb addresses in the
    metro's core city — e.g. a Tempe intersection searched as "Phoenix, AZ".)
    """
    city = normalize_place(city)
    state = normalize_state(state)
    if zip_code:
        return f"v3|{address}|{city}|{state}|{zip_code}"
    if city and state:
        return f"v2|{address}|{city}|{state}"
    return f"v2|{address}|{metro_code}"


def hub_zip(row):
    """The ZIP code Waymo's hub reported for a merged row, or None.

    After the merge the hub's column is "Zip Code_hub" for matched rows
    (NHTSA's own redacted "Zip Code" keeps the plain name) and plain
    "Zip Code" only for the hub-only pre-SGO rows. Waymo stopped
    publishing ZIPs for crashes after June 2025.
    """
    if row.get("record_source") == "hub_only":
        return clean_zip(row.get("Zip Code"))
    return clean_zip(row.get("Zip Code_hub"))


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometres."""
    import math
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def zip_fit(lat, lon, zip_entry):
    """How far a point sits from a ZIP's centre, in ZIP radii.

    zip_entry is [lat, lon, equivalent_radius_km] from zip_reference.json.
    A value <= ~1.5 means the point plausibly lies inside the ZIP area
    (ZIPs are not circles, hence the margin).
    """
    zlat, zlon, radius = zip_entry
    return distance_km(lat, lon, zlat, zlon) / radius


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


# ---------------------------------------------------------------------------
# Year-month arithmetic (YYYYMM integers)
# ---------------------------------------------------------------------------

def add_months(year_month, months):
    """Shift an int YYYYMM by a number of months (202601, -2 → 202511)."""
    index = (year_month // 100) * 12 + (year_month % 100 - 1) + months
    return (index // 12) * 100 + index % 12 + 1


def quarter_end(year_month):
    """The quarter-end month a YYYYMM falls in (202605 → 202606)."""
    year, month = divmod(int(year_month), 100)
    return year * 100 + ((month - 1) // 3 + 1) * 3


def parse_month_label(value):
    """Parse NHTSA's month labels ("SEP-2026") into int YYYYMM, or None."""
    match = re.fullmatch(r"([A-Za-z]{3})-(\d{4})", normalize_place(value))
    if not match:
        return None
    month = _MONTH_ABBREVIATIONS.get(match.group(1).upper())
    return int(match.group(2)) * 100 + month if month else None


def complete_through(latest_submission_month):
    """Last incident month whose federal record should be complete.

    Under the amended SGO, routine crashes are reported by the 15th of the
    month after they happen — 99.5% of Waymo's reports arrive within one
    month of the incident month. NHTSA's file only partly covers the newest
    submission month, so that month is treated as partial: incidents in it
    and in the month before it may still be missing reports.
    """
    if latest_submission_month is None:
        return None
    return add_months(int(latest_submission_month), -2)


# ---------------------------------------------------------------------------
# Waymo hub CSV1 — rider-only miles per location
# ---------------------------------------------------------------------------

def _county_to_metro_any_state(name):
    """CSV1 county rows carry no state; match the county name across metros."""
    name = normalize_place(name).lower()
    for code, info in CITIES.items():
        if name in (c.lower() for c in info.get("counties", [])):
            return code
    return None


def parse_csv1_miles(rows):
    """Parse a CSV1 release into (total, {metro_code: miles}, unknown_names).

    `rows` is a list of (location_name, miles_millions) pairs. Handles both
    the depot format (until Sept 2025) and the county + aggregate format
    (since Dec 2025). An aggregate service-area row replaces the sum of its
    component counties; the total falls back to the sum of metros for old
    releases that have no blended-total row.
    """
    total = None
    aggregates, depots, counties, unknown = {}, {}, {}, []
    for name, miles in rows:
        name = normalize_place(name)
        try:
            miles = float(miles)
        except (TypeError, ValueError):
            continue
        if name == CSV1_TOTAL_LABEL:
            total = miles
        elif name in CSV1_AGGREGATES:
            aggregates[CSV1_AGGREGATES[name]] = miles
        elif name in CSV1_DEPOTS:
            code = CSV1_DEPOTS[name]
            depots[code] = depots.get(code, 0.0) + miles
        elif _county_to_metro_any_state(name):
            code = _county_to_metro_any_state(name)
            counties[code] = counties.get(code, 0.0) + miles
        else:
            unknown.append(name)

    metro_miles = {**counties, **depots, **aggregates}
    metro_miles = {code: round(m, 3) for code, m in metro_miles.items()}
    if total is None and metro_miles:
        total = round(sum(metro_miles.values()), 3)
    return total, metro_miles, unknown


# ---------------------------------------------------------------------------
# Waymo hub CSV3 — comparisons against human benchmarks
# ---------------------------------------------------------------------------

def _benchmark_row(row):
    """One CSV3 row → the fields the site shows (percent reductions positive)."""
    def pct(value):
        return None if pd.isna(value) else round(-float(value) * 100, 1)

    return {
        "waymo_count": int(row["Waymo Count"]),
        "predicted_human_count": round(float(row["Predicted Benchmark Count"]), 1),
        "waymo_rate_per_million": round(float(row["Waymo IPMM"]), 3),
        "human_rate_per_million": round(float(row["Benchmark IPMM"]), 3),
        "reduction_pct": pct(row["Waymo Percent Reduction"]),
        # The CI on the reduction runs the opposite way to the CI on the
        # (negative) percent change: CI Upper of the change = low reduction.
        "reduction_ci_low": pct(row["Waymo Percent Reduction CI Upper"]),
        "reduction_ci_high": pct(row["Waymo Percent Reduction CI Lower"]),
    }


def benchmark_summary(csv3, outcomes, metro_names=None):
    """Extract Waymo-vs-human comparisons from a CSV3 DataFrame.

    Returns {"overall": {key: row}, "by_metro": {metro_code: {key: row}},
    "by_partner": {key: {partner: row}}} for the outcomes given as
    (key, outcome, benchmark_comparison) tuples. `metro_names` maps CSV3
    "County Name" values to metro codes (defaults to CSV1_AGGREGATES plus
    single-county metros).
    """
    if metro_names is None:
        metro_names = dict(CSV1_AGGREGATES)
        for name in csv3["County Name"].dropna().unique():
            if name not in metro_names and name != CSV1_TOTAL_LABEL:
                code = _county_to_metro_any_state(name)
                # A county that is part of an aggregate area is a component,
                # not a metro of its own.
                if code and code not in CSV1_AGGREGATES.values():
                    metro_names[name] = code

    all_crashes = csv3[csv3["Grouping Type"] == "All Crashes"]
    result = {"overall": {}, "by_metro": {}, "by_partner": {}}
    for key, outcome, comparison in outcomes:
        rows = all_crashes[
            (all_crashes["Outcome"] == outcome)
            & (all_crashes["Benchmark Comparison"] == comparison)
        ]
        overall = rows[rows["County Name"] == CSV1_TOTAL_LABEL]
        if len(overall):
            result["overall"][key] = _benchmark_row(overall.iloc[0])
        for name, code in metro_names.items():
            metro = rows[rows["County Name"] == name]
            if len(metro):
                result["by_metro"].setdefault(code, {})[key] = _benchmark_row(metro.iloc[0])

        partners = csv3[
            (csv3["Grouping Type"] == "Aggregate Crash Type")
            & (csv3["Outcome"] == outcome)
            & (csv3["Benchmark Comparison"] == comparison)
            & (csv3["County Name"] == CSV1_TOTAL_LABEL)
        ]
        for _, row in partners.iterrows():
            result["by_partner"].setdefault(key, {})[row["Conflict Partner Type Group"]] = _benchmark_row(row)
    return result


# ---------------------------------------------------------------------------
# Editorial checks
# ---------------------------------------------------------------------------

def editorial_alerts(snapshot, baseline):
    """Compare the current data against the human-reviewed baseline.

    snapshot / baseline: dicts with "fatal" and "moderate_plus" (lists of
    {"report_id", ...} crash summaries), "hub_data_through" (int YYYYMM),
    and — snapshot only — "unmapped" ({place: count}) and
    "testing_metro_crashes" ({metro: count} for driverless crashes in
    metros not yet open to the public). Returns a list of
    (priority, title, detail_lines), most urgent first.
    """
    alerts = []
    reviewed_fatal = set(baseline.get("fatal_report_ids", []))
    new_fatal = [c for c in snapshot["fatal"] if c["report_id"] not in reviewed_fatal]
    if new_fatal:
        alerts.append((
            "HIGH",
            f"{len(new_fatal)} new fatal crash(es) — fatality prose needs review",
            ["faq.html (\"How serious are these crashes?\") summarizes every fatal "
             "crash individually. Read the narrative(s), check news coverage for "
             "fault findings, and update the prose."]
            + [f"{c['report_id']}: {c['month_label']}, {c['city']} — Waymo {c['sv_movement']} "
               f"at {c['speed_mph']} mph, crash with {c['crash_with']}" for c in new_fatal],
        ))

    reviewed_serious = set(baseline.get("moderate_plus_report_ids", []))
    new_serious = [c for c in snapshot["moderate_plus"]
                   if c["report_id"] not in reviewed_serious and c["report_id"] not in reviewed_fatal
                   and c not in new_fatal]
    if new_serious:
        alerts.append((
            "MEDIUM",
            f"{len(new_serious)} new moderate/serious-injury crash(es)",
            ["Skim the narratives for newsworthy circumstances (vulnerable road "
             "users, Waymo at fault, school zones)."]
            + [f"{c['report_id']}: {c['month_label']}, {c['city']} — {c['severity']}" for c in new_serious],
        ))

    if snapshot.get("unmapped"):
        alerts.append((
            "MEDIUM",
            "Crashes in places not mapped to any metro",
            ["Add these places to CITIES in pipeline/config.py (a new metro, or a "
             "suburb of an existing one)."]
            + [f"{place}: {n}" for place, n in snapshot["unmapped"].items()],
        ))

    if snapshot.get("testing_metro_crashes"):
        alerts.append((
            "MEDIUM",
            "Driverless crashes in metros marked as not yet public",
            ["Has Waymo opened public service there? If so, set status to "
             "\"public\" in CITIES and update the metro lists in the prose."]
            + [f"{metro}: {n}" for metro, n in snapshot["testing_metro_crashes"].items()],
        ))

    if snapshot["hub_data_through"] > baseline.get("hub_data_through", 0):
        alerts.append((
            "LOW",
            "New Waymo Safety Impact Data Hub release",
            ["The pipeline already ingested it. Read Waymo's release notes "
             "(linked from waymo.com/safety/impact) for methodology changes and "
             "check that the benchmark section still reads correctly.",
             f"Hub data now through {snapshot['hub_data_through']} "
             f"(reviewed: {baseline.get('hub_data_through')})."],
        ))
    return alerts
