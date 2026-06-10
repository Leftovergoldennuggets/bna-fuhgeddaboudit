"""Unit tests for pipeline/utils.py — the pure helpers every step relies on."""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.utils import (
    normalize_place, normalize_state,
    county_to_metro, city_to_metro, resolve_metro,
    classify_operation, parse_time, parse_incident_date, to_year_month,
    categorize_time_period, severity_level, is_moderate_plus,
    clean_coordinate, validate_columns,
)
from pipeline.config import OTHER_METRO_CODE


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_strips_and_collapses_whitespace(self):
        assert normalize_place("  San   Francisco ") == "San Francisco"

    def test_handles_nan(self):
        assert normalize_place(float("nan")) == ""
        assert normalize_place(None) == ""

    def test_state_full_name_to_code(self):
        assert normalize_state("Arizona") == "AZ"
        assert normalize_state("District of Columbia") == "DC"

    def test_state_code_passthrough(self):
        assert normalize_state("CA") == "CA"
        assert normalize_state(" tx ") == "TX"


# ---------------------------------------------------------------------------
# Metro mapping
# ---------------------------------------------------------------------------

class TestMetroMapping:
    def test_county_lookup_hub_style_state(self):
        # The hub uses full state names
        assert county_to_metro("Arizona", "Maricopa") == "PHOENIX"
        assert county_to_metro("California", "San Mateo") == "SAN_FRANCISCO"

    def test_county_lookup_postal_state(self):
        assert county_to_metro("GA", "DeKalb") == "ATLANTA"

    def test_city_lookup(self):
        assert city_to_metro("AZ", "Tempe") == "PHOENIX"
        assert city_to_metro("CA", "Santa Monica") == "LOS_ANGELES"
        assert city_to_metro("FL", "Miami Beach") == "MIAMI"
        assert city_to_metro("TX", "San Antonio") == "SAN_ANTONIO"

    def test_glendale_disambiguated_by_state(self):
        # Glendale exists in both metros — the state decides
        assert city_to_metro("AZ", "Glendale") == "PHOENIX"
        assert city_to_metro("CA", "Glendale") == "LOS_ANGELES"

    def test_core_city_fallback_on_bad_state(self):
        # NHTSA data-entry error: City="Phoenix", State="CA"
        assert city_to_metro("CA", "Phoenix") == "PHOENIX"

    def test_unmapped_goes_to_other(self):
        metro, mapped = resolve_metro(None, None, "TX", "Huntsville")
        assert metro == OTHER_METRO_CODE
        assert mapped is False

    def test_county_takes_precedence(self):
        metro, mapped = resolve_metro("Arizona", "Maricopa", "AZ", "NowhereVille")
        assert metro == "PHOENIX"
        assert mapped is True

    def test_whitespace_variants(self):
        assert city_to_metro("CA ", " San  Francisco ") == "SAN_FRANCISCO"


# ---------------------------------------------------------------------------
# Operation type
# ---------------------------------------------------------------------------

class TestClassifyOperation:
    def test_blank_is_driverless(self):
        assert classify_operation(None) == "driverless"
        assert classify_operation(float("nan")) == "driverless"
        assert classify_operation("") == "driverless"

    def test_remote_only_is_driverless(self):
        assert classify_operation("Remote (Commercial / Test)") == "driverless"

    def test_in_vehicle_is_supervised(self):
        assert classify_operation("In-Vehicle (Commercial / Test)") == "supervised"
        assert classify_operation("In-Vehicle and Remote (Commercial / Test)") == "supervised"

    def test_unknown_value_is_supervised(self):
        # Conservative: never inflate the headline driverless count
        assert classify_operation("Some Future NHTSA Value") == "supervised"


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------

class TestParseTime:
    def test_colon_format(self):
        assert parse_time("14:30") == (14, 30)

    def test_compact_format(self):
        assert parse_time("1430") == (14, 30)

    def test_midnight(self):
        assert parse_time("00:00") == (0, 0)

    def test_invalid(self):
        assert parse_time("25:00") == (None, None)
        assert parse_time("") == (None, None)
        assert parse_time(None) == (None, None)
        assert parse_time("noon") == (None, None)


class TestTimePeriods:
    def test_morning_rush(self):
        assert categorize_time_period(8) == "Morning Rush"

    def test_late_night_wraps_midnight(self):
        assert categorize_time_period(23) == "Late Night"
        assert categorize_time_period(2) == "Late Night"
        assert categorize_time_period(4) == "Late Night"

    def test_boundary_five_is_early_morning(self):
        assert categorize_time_period(5) == "Early Morning"

    def test_none_is_unknown(self):
        assert categorize_time_period(None) == "Unknown"


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

class TestParseIncidentDate:
    def test_nhtsa_month_precision(self):
        ts, precision = parse_incident_date("MAR-2026")
        assert ts == pd.Timestamp(2026, 3, 1)
        assert precision == "month"

    def test_hub_day_precision_slash(self):
        ts, precision = parse_incident_date("3/14/25")
        assert ts == pd.Timestamp(2025, 3, 14)
        assert precision == "day"

    def test_iso_format(self):
        ts, precision = parse_incident_date("2025-03-14")
        assert ts == pd.Timestamp(2025, 3, 14)
        assert precision == "day"

    def test_unparseable(self):
        assert parse_incident_date("not a date") == (None, None)
        assert parse_incident_date(None) == (None, None)

    def test_to_year_month(self):
        assert to_year_month(pd.Timestamp(2026, 4, 17)) == 202604
        assert to_year_month(None) is None


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

class TestSeverity:
    @pytest.mark.parametrize("value,expected", [
        ("Fatality", "fatal"),
        ("Serious", "serious"),
        ("Moderate W/ Hospitalization", "moderate"),
        ("Minor W/O Hospitalization", "minor"),
        ("Property Damage. No Injured Reported", "none"),
        (None, "none"),
    ])
    def test_levels(self, value, expected):
        assert severity_level(value) == expected

    def test_has_injury_promotes_to_minor(self):
        assert severity_level("Unknown", has_injury=True) == "minor"

    def test_moderate_plus(self):
        assert is_moderate_plus("Moderate") is True
        assert is_moderate_plus("Fatality") is True
        assert is_moderate_plus("Minor W/ Hospitalization") is False
        assert is_moderate_plus(None) is False


# ---------------------------------------------------------------------------
# Coordinates & validation
# ---------------------------------------------------------------------------

class TestCoordinates:
    def test_redacted_is_none(self):
        assert clean_coordinate("[MAY CONTAIN PERSONALLY IDENTIFIABLE INFORMATION]") is None

    def test_valid_float(self):
        assert clean_coordinate("37.7749") == 37.7749

    def test_nan_is_none(self):
        assert clean_coordinate(float("nan")) is None


class TestValidateColumns:
    def test_passes_when_present(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        validate_columns(df, ["a", "b"], "test")  # should not raise

    def test_exits_with_clear_message_when_missing(self):
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(SystemExit, match="missing expected column"):
            validate_columns(df, ["a", "zap"], "test source")


# ---------------------------------------------------------------------------
# Zip codes & geocode cache keys
# ---------------------------------------------------------------------------

from pipeline.utils import clean_zip, geocode_cache_key, reverse_cache_key


class TestCleanZip:
    def test_plain(self):
        assert clean_zip("94110") == "94110"

    def test_pandas_float_artifact(self):
        assert clean_zip(94103.0) == "94103"
        assert clean_zip("94103.0") == "94103"

    def test_zip_plus_four(self):
        assert clean_zip("94110-1234") == "94110"

    def test_nhtsa_redaction_placeholder(self):
        assert clean_zip("[MAY CONTAIN PERSONALLY IDENTIFIABLE INFORMATION]") is None

    def test_garbage(self):
        assert clean_zip("nan") is None
        assert clean_zip("") is None
        assert clean_zip(None) is None
        assert clean_zip(float("nan")) is None


class TestGeocodeCacheKey:
    def test_uses_actual_city_and_state(self):
        key = geocode_cache_key("Mill Ave & 5th St", "Tempe", "AZ", "PHOENIX")
        assert key == "v2|Mill Ave & 5th St|Tempe|AZ"

    def test_normalizes_state_names(self):
        key = geocode_cache_key("Main St", "Tempe", "Arizona", "PHOENIX")
        assert key == "v2|Main St|Tempe|AZ"

    def test_falls_back_to_metro_when_city_missing(self):
        key = geocode_cache_key("Main St", None, None, "PHOENIX")
        assert key == "v2|Main St|PHOENIX"

    def test_reverse_key_rounding(self):
        assert reverse_cache_key(37.123456, -122.654321) == "__rev__37.1235,-122.6543"
