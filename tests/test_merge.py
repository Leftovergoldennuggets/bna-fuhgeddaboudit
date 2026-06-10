"""Integration-style tests for the merge logic in 02_merge_and_clean.py.

Uses small synthetic CSVs so the tests run fast and don't depend on
downloaded data. The script module is imported dynamically because its
filename starts with a digit.
"""

import importlib.util
import os
import sys

import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _load_merge_module():
    path = os.path.join(PROJECT_ROOT, "pipeline", "02_merge_and_clean.py")
    spec = importlib.util.spec_from_file_location("merge_and_clean", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_mod = _load_merge_module()


def make_nhtsa_df(rows):
    """Build a minimal NHTSA-shaped DataFrame."""
    defaults = {
        "Report ID": "30270-1",
        "Report Version": 1,
        "Reporting Entity": "Waymo LLC",
        "Incident Date": "JAN-2026",
        "Incident Time (24:00)": "12:00",
        "City": "San Francisco",
        "State": "CA",
        "Highest Injury Severity Alleged": "No Injuries Reported",
        "Narrative": "test",
        "Driver / Operator Type": None,
        "Crash With": "Passenger Car",
        "SV Pre-Crash Movement": "Stopped",
        "SV Precrash Speed (MPH)": 0,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def make_hub_df(rows):
    """Build a minimal hub-CSV2-shaped DataFrame."""
    defaults = {
        "SGO Report ID": "30270-1",
        "Year Month": 202601,
        "State": "California",
        "County": "San Francisco",
        "Crash Type": "V2V F2R",
        "Incident Date": "1/15/26",
        "Location Address / Description": "Market St & 5th St",
        "Is NHTSA Reportable In-Transport": True,
        "Is Police-Reported": True,
        "Is Any-Injury-Reported": False,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


class TestCombineAndDeduplicate:
    def test_keeps_latest_version(self):
        prior = make_nhtsa_df([
            {"Report ID": "A", "Report Version": 1, "Narrative": "old"},
        ])
        post = make_nhtsa_df([
            {"Report ID": "A", "Report Version": 3, "Narrative": "new"},
            {"Report ID": "B", "Report Version": 1},
        ])
        combined = merge_mod.combine_and_deduplicate(prior, post)
        assert len(combined) == 2
        assert combined.loc[combined["Report ID"] == "A", "Narrative"].iloc[0] == "new"


class TestMergeNhtsaWithHub:
    def test_every_nhtsa_crash_is_kept(self):
        nhtsa = make_nhtsa_df([
            {"Report ID": "A"},
            {"Report ID": "B"},  # not in hub — must NOT be dropped
        ])
        hub = make_hub_df([{"SGO Report ID": "A"}])
        merged = merge_mod.merge_nhtsa_with_hub(nhtsa, hub)
        assert len(merged) == 2
        assert set(merged["record_source"]) == {"nhtsa+hub", "nhtsa_only"}

    def test_hub_only_rows_appended(self):
        nhtsa = make_nhtsa_df([{"Report ID": "A"}])
        hub = make_hub_df([
            {"SGO Report ID": "A"},
            {"SGO Report ID": None},  # pre-SGO crash
        ])
        merged = merge_mod.merge_nhtsa_with_hub(nhtsa, hub)
        assert len(merged) == 2
        assert (merged["record_source"] == "hub_only").sum() == 1

    def test_hub_enrichment_columns_present(self):
        nhtsa = make_nhtsa_df([{"Report ID": "A"}])
        hub = make_hub_df([{"SGO Report ID": "A", "Crash Type": "V2V Lateral"}])
        merged = merge_mod.merge_nhtsa_with_hub(nhtsa, hub)
        assert merged["Crash Type"].iloc[0] == "V2V Lateral"


class TestAddUnifiedColumns:
    def _merge(self, nhtsa_rows, hub_rows):
        nhtsa = make_nhtsa_df(nhtsa_rows)
        hub = make_hub_df(hub_rows)
        merged = merge_mod.merge_nhtsa_with_hub(nhtsa, hub)
        return merge_mod.add_unified_columns(merged)

    def test_hub_date_preferred_over_nhtsa_month(self):
        df = self._merge(
            [{"Report ID": "A", "Incident Date": "JAN-2026"}],
            [{"SGO Report ID": "A", "Incident Date": "1/15/26"}],
        )
        assert df["incident_date"].iloc[0] == pd.Timestamp(2026, 1, 15)
        assert df["date_precision"].iloc[0] == "day"

    def test_nhtsa_only_row_has_month_precision(self):
        df = self._merge(
            [{"Report ID": "A"}, {"Report ID": "B", "Incident Date": "MAR-2026"}],
            [{"SGO Report ID": "A"}],
        )
        row = df[df["Report ID"] == "B"].iloc[0]
        assert row["date_precision"] == "month"
        assert row["Year Month"] == 202603

    def test_operation_type_classification(self):
        df = self._merge(
            [
                {"Report ID": "A", "Driver / Operator Type": None},
                {"Report ID": "B", "Driver / Operator Type": "In-Vehicle (Commercial / Test)"},
            ],
            [{"SGO Report ID": "A"}],
        )
        by_id = df.set_index("Report ID")
        assert by_id.loc["A", "operation_type"] == "driverless"
        assert by_id.loc["B", "operation_type"] == "supervised"

    def test_metro_from_hub_county(self):
        df = self._merge(
            [{"Report ID": "A", "City": "Tempe", "State": "AZ"}],
            [{"SGO Report ID": "A", "State": "Arizona", "County": "Maricopa"}],
        )
        assert df["Location"].iloc[0] == "PHOENIX"

    def test_metro_from_nhtsa_city_when_not_in_hub(self):
        df = self._merge(
            [{"Report ID": "B", "City": "Miami Beach", "State": "FL"}],
            [{"SGO Report ID": "Z"}],  # no match for B
        )
        row = df[df["Report ID"] == "B"].iloc[0]
        assert row["Location"] == "MIAMI"

    def test_unmapped_city_lands_in_other(self):
        df = self._merge(
            [{"Report ID": "B", "City": "Anchorage", "State": "AK"}],
            [{"SGO Report ID": "Z"}],
        )
        row = df[df["Report ID"] == "B"].iloc[0]
        assert row["Location"] == "OTHER"
        assert row["metro_mapped"] == False  # noqa: E712 (numpy bool)

    def test_duplicate_hub_ids_abort(self):
        nhtsa = make_nhtsa_df([{"Report ID": "A"}])
        hub = make_hub_df([
            {"SGO Report ID": "A"},
            {"SGO Report ID": "A"},  # duplicate that dedup should have removed
        ])
        with pytest.raises(SystemExit, match="row count"):
            merge_mod.merge_nhtsa_with_hub(nhtsa, hub)
