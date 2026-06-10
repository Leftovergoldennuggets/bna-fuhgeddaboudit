"""
02_merge_and_clean.py — Merge NHTSA crash data with Waymo Safety Hub
==========================================================================
Builds the master crash dataset with the FEDERAL record as the base.

Why NHTSA is the base (not Waymo's hub):
  NHTSA's Standing General Order data is the legally required, complete
  record of every reported Waymo crash, updated roughly monthly. Waymo's
  Safety Hub CSV2 is a curated quarterly release that lags 3-6 months and
  covers only driverless (rider-only) operations. Using the hub as the
  base — as an earlier version of this pipeline did — silently dropped
  months of recent crashes. Instead we keep every NHTSA crash and use the
  hub to ENRICH matched rows with exact dates, street addresses, and
  crash-type classifications.

What it does:
  1. Load both NHTSA files (Amendment 2 + 3), filter to Waymo, harmonize
  2. Deduplicate: keep only the latest version of each crash report
  3. Classify operation type: driverless vs. supervised (test driver)
  4. Left-join the Waymo hub onto the NHTSA record (enrichment)
  5. Append hub-only rows (2 pre-SGO crashes from 2020)
  6. Resolve every crash to a metro area (county first, then city);
     unmapped crashes land in the OTHER bucket with a loud warning
  7. Derive unified date / Year Month columns with a precision flag

Outputs:
  - data/processed/waymo_merged.csv        (every crash, one row each)
  - data/processed/waymo_unmapped_cities.csv  (crashes in the OTHER bucket)

Usage:
  python pipeline/02_merge_and_clean.py
==========================================================================
"""

import os
import sys

import pandas as pd

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    RAW_NHTSA_POST, RAW_NHTSA_PRIOR, RAW_WAYMO_HUB,
    PROCESSED_MERGED, PROCESSED_UNMATCHED, PROCESSED_DIR,
    WAYMO_ENTITY_NAME, COLUMN_RENAMES_PRIOR_TO_POST,
    REQUIRED_NHTSA_COLUMNS, REQUIRED_HUB_COLUMNS,
)
from pipeline.utils import (
    normalize_place, resolve_metro, classify_operation,
    parse_incident_date, to_year_month, validate_columns,
)


def load_and_filter_nhtsa(filepath, label):
    """Load an NHTSA CSV and keep only Waymo crashes."""
    print(f"  Loading {label}...")
    # NHTSA CSVs sometimes contain non-UTF-8 characters (smart quotes etc.)
    try:
        df = pd.read_csv(filepath, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        print("    Note: UTF-8 failed, using latin-1 encoding")
        df = pd.read_csv(filepath, encoding="latin-1", low_memory=False)
    print(f"    Total rows (all companies): {len(df)}")

    validate_columns(df, ["Reporting Entity"], label)
    waymo = df[df["Reporting Entity"] == WAYMO_ENTITY_NAME].copy()
    print(f"    Waymo rows: {len(waymo)}")
    if len(waymo) == 0:
        entities = df["Reporting Entity"].dropna().unique()[:10]
        raise SystemExit(
            f"ERROR: No rows matched Reporting Entity == '{WAYMO_ENTITY_NAME}' "
            f"in {label}. The entity name may have changed. "
            f"Entities present include: {list(entities)}"
        )
    return waymo


def combine_and_deduplicate(waymo_prior, waymo_post):
    """Stack both NHTSA files and keep the latest version of each report."""
    waymo_prior = waymo_prior.rename(columns=COLUMN_RENAMES_PRIOR_TO_POST)
    waymo_prior["Data Period"] = "Prior to June 16, 2025 (Amendment 2)"
    waymo_post["Data Period"] = "After June 16, 2025 (Amendment 3)"

    combined = pd.concat([waymo_prior, waymo_post], ignore_index=True)
    print(f"  Combined: {len(waymo_prior)} + {len(waymo_post)} = {len(combined)} rows")

    dupes = len(combined) - combined["Report ID"].nunique()
    print(f"  Duplicate report versions to remove: {dupes}")

    # Some crashes appear in both files (reports amended across the
    # June 2025 format change) and most have multiple versions. Sorting by
    # version and keeping the last row retains the newest version of each.
    combined = combined.sort_values(["Report ID", "Report Version"])
    combined = combined.drop_duplicates(subset="Report ID", keep="last")
    print(f"  After deduplication: {len(combined)} unique crashes")
    return combined


def load_and_dedupe_hub():
    """Load Waymo hub CSV2 and deduplicate on SGO Report ID."""
    hub = pd.read_csv(RAW_WAYMO_HUB)
    validate_columns(hub, REQUIRED_HUB_COLUMNS, "Waymo hub CSV2")
    print(f"  Waymo Hub rows: {len(hub)}")
    print(f"  Date range: {hub['Year Month'].min()} to {hub['Year Month'].max()}")

    # The hub CSV contains duplicate entries for some SGO Report IDs.
    # Keep the row with the most True boolean flags (most complete version).
    # Rows with blank SGO Report IDs are unique pre-SGO crashes — keep all.
    before = len(hub)
    has_id = hub[hub["SGO Report ID"].notna() & (hub["SGO Report ID"] != "")]
    no_id = hub[~hub.index.isin(has_id.index)]

    bool_cols = ["Is NHTSA Reportable In-Transport", "Is Police-Reported", "Is Any-Injury-Reported"]
    bool_cols = [c for c in bool_cols if c in hub.columns]
    has_id = has_id.sort_values(bool_cols, ascending=False)
    has_id = has_id.drop_duplicates(subset="SGO Report ID", keep="first")

    hub = pd.concat([has_id, no_id], ignore_index=True)
    print(f"  Hub deduplication: {before} → {len(hub)} rows ({before - len(hub)} duplicates removed)")
    return hub


def merge_nhtsa_with_hub(nhtsa, hub):
    """LEFT JOIN: every NHTSA crash, enriched with hub columns where matched.

    Hub-only rows (blank SGO Report ID — pre-SGO crashes from 2020) are
    appended afterwards so they stay in the dataset.
    """
    hub_ids = set(hub["SGO Report ID"].dropna())
    nhtsa_ids = set(nhtsa["Report ID"].dropna())

    print(f"  Crashes in both datasets: {len(hub_ids & nhtsa_ids)}")
    print(f"  NHTSA-only (not yet in hub): {len(nhtsa_ids - hub_ids)}")
    print(f"  Hub-only (no SGO ID, pre-SGO era): {hub['SGO Report ID'].isna().sum()}")

    hub_in_nhtsa = hub_ids - nhtsa_ids
    if hub_in_nhtsa:
        print(f"  WARNING: {len(hub_in_nhtsa)} hub SGO IDs missing from NHTSA data: "
              f"{sorted(hub_in_nhtsa)[:5]}...")

    matchable_hub = hub[hub["SGO Report ID"].notna()]
    merged = nhtsa.merge(
        matchable_hub,
        left_on="Report ID",
        right_on="SGO Report ID",
        how="left",
        suffixes=("", "_hub"),
    )
    if len(merged) != len(nhtsa):
        raise SystemExit(
            f"ERROR: Merge changed the row count ({len(nhtsa)} → {len(merged)}). "
            f"The hub data likely contains duplicate SGO Report IDs that "
            f"deduplication missed."
        )
    merged["in_hub"] = merged["SGO Report ID"].notna()
    merged["record_source"] = merged["in_hub"].map(
        {True: "nhtsa+hub", False: "nhtsa_only"}
    )

    # Append the hub-only rows (no SGO ID → never matched above)
    hub_only = hub[hub["SGO Report ID"].isna()].copy()
    if len(hub_only) > 0:
        hub_only["in_hub"] = True
        hub_only["record_source"] = "hub_only"
        merged = pd.concat([merged, hub_only], ignore_index=True)
        print(f"  Appended {len(hub_only)} hub-only rows")

    return merged


def add_unified_columns(df):
    """Derive the unified columns every downstream step relies on.

    - operation_type:  'driverless' | 'supervised'
    - incident_date:   best available date (hub exact > NHTSA month)
    - date_precision:  'day' | 'month' | None
    - Year Month:      int YYYYMM for every row (hub value or derived)
    - Location:        metro code (e.g. SAN_FRANCISCO), OTHER if unmapped
    - City / State:    normalized place names
    """
    # --- Operation type from NHTSA's operator column -----------------------
    op_col = "Driver / Operator Type"
    df["operation_type"] = df.get(op_col, pd.Series(index=df.index)).apply(classify_operation)
    # Hub-only rows have no NHTSA operator column — the hub covers
    # driverless operations only, so they are driverless by definition.
    df.loc[df["record_source"] == "hub_only", "operation_type"] = "driverless"

    known_types = {"", "In-Vehicle (Commercial / Test)",
                   "In-Vehicle and Remote (Commercial / Test)",
                   "Remote (Commercial / Test)", "Other, see Narrative"}
    if op_col in df.columns:
        unknown = set(df[op_col].dropna().map(normalize_place)) - known_types
        if unknown:
            print(f"  WARNING: Unrecognized operator type(s) classified as "
                  f"'supervised': {sorted(unknown)}")

    # --- Unified incident date ---------------------------------------------
    # Hub "Incident Date" is exact; NHTSA's public "Incident Date" is
    # month-precision ("MAR-2026"). Prefer the hub date when present.
    # After the merge, the hub's date lives in "Incident Date_hub" for
    # nhtsa+hub rows, and in "Incident Date" itself for hub_only rows.
    hub_date_col = "Incident Date_hub" if "Incident Date_hub" in df.columns else None

    dates, precisions = [], []
    for _, row in df.iterrows():
        candidates = []
        if row.get("record_source") == "hub_only":
            candidates = [row.get("Incident Date")]
        else:
            if hub_date_col:
                candidates.append(row.get(hub_date_col))
            candidates.append(row.get("Incident Date"))
        ts, precision = None, None
        for candidate in candidates:
            ts, precision = parse_incident_date(candidate)
            if ts is not None:
                break
        dates.append(ts)
        precisions.append(precision)
    df["incident_date"] = dates
    df["date_precision"] = precisions

    no_date = df["incident_date"].isna().sum()
    if no_date:
        print(f"  WARNING: {no_date} rows have no parseable incident date")

    # --- Year Month (int YYYYMM) -------------------------------------------
    derived_ym = df["incident_date"].apply(to_year_month)
    if "Year Month" in df.columns:
        df["Year Month"] = df["Year Month"].fillna(derived_ym)
    else:
        df["Year Month"] = derived_ym
    df["Year Month"] = pd.to_numeric(df["Year Month"], errors="coerce").astype("Int64")

    # --- Metro resolution ---------------------------------------------------
    # Hub rows carry State+County (precise); NHTSA rows carry State+City.
    # After the merge, hub State lives in "State_hub" for nhtsa+hub rows.
    hub_state_col = "State_hub" if "State_hub" in df.columns else "State"

    df["City"] = df.get("City", pd.Series(index=df.index)).apply(normalize_place)
    df["State"] = df.get("State", pd.Series(index=df.index)).apply(normalize_place)

    metros, mapped_flags = [], []
    for _, row in df.iterrows():
        if row.get("record_source") == "hub_only":
            county_state = row.get("State")
        else:
            county_state = row.get(hub_state_col) if row.get("in_hub") else None
        metro, mapped = resolve_metro(
            county_state, row.get("County"),
            row.get("State"), row.get("City"),
        )
        metros.append(metro)
        mapped_flags.append(mapped)
    df["Location"] = metros
    df["metro_mapped"] = mapped_flags

    unmapped = df[~df["metro_mapped"]]
    if len(unmapped) > 0:
        places = (
            unmapped.apply(lambda r: f"{r.get('City') or r.get('County')}, {r.get('State')}", axis=1)
            .value_counts()
        )
        print(f"  WARNING: {len(unmapped)} crashes in unmapped places (kept in "
              f"'OTHER' bucket — add them to CITIES in config.py):")
        for place, count in places.head(15).items():
            print(f"    {place}: {count}")

    return df


def main():
    """Run the full merge pipeline."""
    print("=" * 60)
    print("STEP 2: MERGING NHTSA + WAYMO HUB DATA")
    print("=" * 60)

    print()
    print("Loading NHTSA data...")
    waymo_prior = load_and_filter_nhtsa(RAW_NHTSA_PRIOR, "NHTSA Prior (Amendment 2)")
    waymo_post = load_and_filter_nhtsa(RAW_NHTSA_POST, "NHTSA Post (Amendment 3)")
    validate_columns(waymo_post, REQUIRED_NHTSA_COLUMNS, "NHTSA Post (Amendment 3)")

    print()
    print("Combining and deduplicating NHTSA files...")
    nhtsa = combine_and_deduplicate(waymo_prior, waymo_post)

    print()
    print("Loading Waymo Safety Hub...")
    hub = load_and_dedupe_hub()

    print()
    print("Merging (NHTSA base + hub enrichment)...")
    merged = merge_nhtsa_with_hub(nhtsa, hub)

    print()
    print("Deriving unified columns...")
    merged = add_unified_columns(merged)

    print()
    print("Saving output files...")
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    merged.to_csv(PROCESSED_MERGED, index=False)
    print(f"  Merged: {PROCESSED_MERGED} ({len(merged)} rows x {len(merged.columns)} cols)")

    unmapped = merged[~merged["metro_mapped"]]
    unmapped.to_csv(PROCESSED_UNMATCHED, index=False)
    print(f"  Unmapped: {PROCESSED_UNMATCHED} ({len(unmapped)} rows)")

    print()
    print("=" * 60)
    print("MERGE COMPLETE")
    print("=" * 60)
    driverless = (merged["operation_type"] == "driverless").sum()
    supervised = (merged["operation_type"] == "supervised").sum()
    in_hub = merged["in_hub"].sum()
    print(f"  Total crashes:     {len(merged)}")
    print(f"  Driverless:        {driverless}")
    print(f"  Supervised (test): {supervised}")
    print(f"  Enriched from hub: {in_hub}")
    print(f"  Awaiting hub data: {len(merged) - in_hub}")


if __name__ == "__main__":
    main()
