"""Unit tests for the helpers added in the October 2026 overhaul.

Covers: roadway type, year-month arithmetic and reporting completeness,
CSV1 parsing across both of Waymo's formats, CSV3 benchmark extraction,
ZIP-area checks, the test-driver narrative fallback, and editorial alerts.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.utils import (
    roadway_type, add_months, quarter_end, parse_month_label, complete_through,
    parse_csv1_miles, benchmark_summary, zip_fit, distance_km,
    narrative_says_test_driver, geocode_cache_key, hub_zip, editorial_alerts,
)


# ---------------------------------------------------------------------------
# Roadway type
# ---------------------------------------------------------------------------

class TestRoadwayType:
    def test_known_values(self):
        assert roadway_type("Intersection") == "Intersection"
        assert roadway_type("Parking Lot") == "Parking lot"
        assert roadway_type("Highway / Freeway") == "Highway/freeway"

    def test_unknown_and_blank(self):
        assert roadway_type("Unknown") == "Other/unknown"
        assert roadway_type(None) == "Other/unknown"
        assert roadway_type("Some new NHTSA value") == "Other/unknown"


# ---------------------------------------------------------------------------
# Year-month arithmetic and reporting completeness
# ---------------------------------------------------------------------------

class TestYearMonth:
    def test_add_months_across_years(self):
        assert add_months(202601, -2) == 202511
        assert add_months(202512, 1) == 202601
        assert add_months(202409, 3) == 202412

    def test_quarter_end(self):
        assert quarter_end(202601) == 202603
        assert quarter_end(202606) == 202606
        assert quarter_end(202610) == 202612

    def test_parse_month_label(self):
        assert parse_month_label("SEP-2026") == 202609
        assert parse_month_label("jan-2025") == 202501
        assert parse_month_label("") is None
        assert parse_month_label(float("nan")) is None

    def test_complete_through_is_two_months_before_latest_submission(self):
        # Submissions through Sept 2026 (partial) → Aug and Sept incomplete
        assert complete_through(202609) == 202607
        assert complete_through(None) is None


# ---------------------------------------------------------------------------
# CSV1 mileage parsing
# ---------------------------------------------------------------------------

class TestParseCsv1:
    def test_depot_format_sums_mountain_view_into_bay_area(self):
        rows = [("PHOENIX", "37.492"), ("SAN_FRANCISCO", "22.892"),
                ("MOUNTAIN_VIEW", "0.132"), ("ATLANTA", "0.056")]
        total, metros, unknown = parse_csv1_miles(rows)
        assert metros["SAN_FRANCISCO"] == pytest.approx(23.024)
        assert metros["ATLANTA"] == pytest.approx(0.056)
        # Old releases have no blended-total row: total = sum of metros
        assert total == pytest.approx(37.492 + 23.024 + 0.056)
        assert unknown == []

    def test_county_format_prefers_aggregates_over_components(self):
        rows = [("Maricopa", "92.121"), ("San Francisco", "67.907"),
                ("San Mateo", "7.430"), ("Santa Clara", "7.083"),
                ("San Francisco Bay Area", "82.421"),
                ("Fulton", "7.860"), ("DeKalb", "0.764"), ("Atlanta Area", "8.624"),
                ("All Locations (mileage blended)", "271.329")]
        total, metros, unknown = parse_csv1_miles(rows)
        assert total == 271.329
        assert metros["SAN_FRANCISCO"] == 82.421   # aggregate, not 67.9 + 7.4 + 7.1
        assert metros["ATLANTA"] == 8.624
        assert metros["PHOENIX"] == 92.121
        assert unknown == []

    def test_county_without_aggregate_is_summed(self):
        total, metros, _ = parse_csv1_miles([("Fulton", "4.0"), ("DeKalb", "1.0")])
        assert metros["ATLANTA"] == 5.0

    def test_unknown_location_reported(self):
        _, _, unknown = parse_csv1_miles([("Mars Area", "1.0")])
        assert unknown == ["Mars Area"]


# ---------------------------------------------------------------------------
# CSV3 benchmarks
# ---------------------------------------------------------------------------

def _csv3_row(outcome, comparison, county, reduction, ci_lower, ci_upper,
              grouping="All Crashes", partner="All Crashes", count=3):
    return {
        "Outcome": outcome, "Benchmark Comparison": comparison,
        "County Name": county, "Grouping Type": grouping,
        "Conflict Partner Type Group": partner, "Waymo Count": count,
        "Predicted Benchmark Count": 57.9, "Waymo IPMM": 0.011, "Benchmark IPMM": 0.213,
        "Waymo Percent Reduction": reduction,
        "Waymo Percent Reduction CI Lower": ci_lower,
        "Waymo Percent Reduction CI Upper": ci_upper,
    }


class TestBenchmarkSummary:
    OUTCOMES = [("serious_injury", "Suspected Serious Injury+", "Suspected Serious Injury+")]

    def test_uses_dynamic_row_and_flips_ci(self):
        csv3 = pd.DataFrame([
            _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+",
                      "All Locations (mileage blended)", -0.948, -0.992, -0.832),
            _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+ (non-Dynamic)",
                      "All Locations (mileage blended)", -0.937, -0.990, -0.795),
        ])
        out = benchmark_summary(csv3, self.OUTCOMES)["overall"]["serious_injury"]
        assert out["reduction_pct"] == 94.8
        assert out["reduction_ci_low"] == 83.2   # from CI Upper of the change
        assert out["reduction_ci_high"] == 99.2

    def test_metro_aggregates_and_partners(self):
        csv3 = pd.DataFrame([
            _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+",
                      "San Francisco Bay Area", -0.9, -0.99, -0.5),
            _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+",
                      "San Mateo", -0.9, -0.99, -0.5),   # component county — ignored
            _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+",
                      "Maricopa", -0.8, -0.95, -0.4),
            _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+",
                      "All Locations (mileage blended)", -0.7, -0.9, -0.3,
                      grouping="Aggregate Crash Type", partner="Pedestrian"),
        ])
        out = benchmark_summary(csv3, self.OUTCOMES)
        assert set(out["by_metro"]) == {"SAN_FRANCISCO", "PHOENIX"}
        assert out["by_partner"]["serious_injury"]["Pedestrian"]["reduction_pct"] == 70.0


# ---------------------------------------------------------------------------
# ZIP checks and geocode keys
# ---------------------------------------------------------------------------

class TestZipChecks:
    def test_distance(self):
        # SF City Hall → Ferry Building ≈ 2.7 km
        assert distance_km(37.7793, -122.4193, 37.7955, -122.3937) == pytest.approx(2.8, abs=0.3)

    def test_zip_fit_inside_and_outside(self):
        zip_entry = [37.7793, -122.4193, 1.0]  # 1 km radius
        assert zip_fit(37.7800, -122.4190, zip_entry) < 1.5
        assert zip_fit(37.8100, -122.4193, zip_entry) > 1.5

    def test_cache_key_versions(self):
        assert geocode_cache_key("A St at B St", "Tempe", "AZ", "PHOENIX", "85281") == \
            "v3|A St at B St|Tempe|AZ|85281"
        assert geocode_cache_key("A St at B St", "Tempe", "AZ", "PHOENIX") == \
            "v2|A St at B St|Tempe|AZ"

    def test_hub_zip_columns(self):
        assert hub_zip({"record_source": "nhtsa+hub", "Zip Code_hub": 94103.0,
                        "Zip Code": "[REDACTED]"}) == "94103"
        assert hub_zip({"record_source": "hub_only", "Zip Code": "85202"}) == "85202"
        assert hub_zip({"record_source": "nhtsa_only", "Zip Code": "[REDACTED]"}) is None


# ---------------------------------------------------------------------------
# Test-driver narrative fallback
# ---------------------------------------------------------------------------

class TestNarrativeTestDriver:
    def test_detects_test_driver(self):
        assert narrative_says_test_driver(
            "the Waymo AV's Level 4 ADS was engaged in autonomous mode, and a test "
            "driver was present (in the driver's seating position).")
        assert narrative_says_test_driver("a test driver was present (in the drivers seating position)")

    def test_ignores_manual_mode_after_crash(self):
        assert not narrative_says_test_driver(
            "The Waymo AV was returned to the depot in manual mode.")
        assert not narrative_says_test_driver(float("nan"))


# ---------------------------------------------------------------------------
# Editorial alerts
# ---------------------------------------------------------------------------

class TestEditorialAlerts:
    FATAL = {"report_id": "30270-16196", "month_label": "August 2026", "city": "Dallas",
             "sv_movement": "Proceeding Straight", "speed_mph": 5.0,
             "crash_with": "Non-Motorist: Pedestrian"}

    def _snapshot(self, **kw):
        base = {"fatal": [], "moderate_plus": [], "hub_data_through": 202606,
                "unmapped": {}, "testing_metro_crashes": {}}
        base.update(kw)
        return base

    def test_new_fatality_is_high_priority(self):
        alerts = editorial_alerts(self._snapshot(fatal=[self.FATAL]),
                                  {"fatal_report_ids": [], "hub_data_through": 202606})
        assert alerts[0][0] == "HIGH"
        assert "30270-16196" in " ".join(alerts[0][2])

    def test_reviewed_state_is_quiet(self):
        alerts = editorial_alerts(
            self._snapshot(fatal=[self.FATAL]),
            {"fatal_report_ids": ["30270-16196"], "hub_data_through": 202606})
        assert alerts == []

    def test_new_hub_release_and_unmapped(self):
        alerts = editorial_alerts(
            self._snapshot(unmapped={"Reno, NV": 2}, hub_data_through=202609),
            {"fatal_report_ids": [], "hub_data_through": 202606})
        titles = " ".join(t for _, t, _ in alerts)
        assert "not mapped" in titles and "Hub release" in titles


def test_narrative_negated_test_driver_not_matched():
    assert not narrative_says_test_driver("no safety driver was present in the vehicle")


def test_benchmark_skips_metro_split_across_counties():
    csv3 = pd.DataFrame([
        _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+", "Travis", -0.9, -0.99, -0.5),
        _csv3_row("Suspected Serious Injury+", "Suspected Serious Injury+", "Williamson", -0.2, -0.9, 0.5),
    ])
    out = benchmark_summary(csv3, TestBenchmarkSummary.OUTCOMES)
    assert "AUSTIN" not in out["by_metro"]
