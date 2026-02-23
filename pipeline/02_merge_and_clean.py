"""
02_merge_and_clean.py — Merge NHTSA crash data with Waymo Safety Hub
==========================================================================
This is a direct port of Anders' notebook (notebook-anders-NEW/merge_nhtsa_waymo.ipynb).

What it does:
  1. Load the three raw CSV files (NHTSA prior, NHTSA post, Waymo Hub)
  2. Filter NHTSA data for Waymo-only crashes
  3. Harmonize column names between Amendment 2 and Amendment 3
  4. Combine the two NHTSA files into one dataset
  5. Deduplicate: keep only the latest version of each crash report
  6. Merge (left join): Waymo Hub + NHTSA data
  7. Save: merged dataset + extras not in hub

Inputs:
  - data/raw/nhtsa_ads_post_june16.csv
  - data/raw/nhtsa_ads_prior_june16.csv
  - data/raw/waymo_hub_csv2.csv

Outputs:
  - data/processed/waymo_merged.csv       (the main merged dataset)
  - data/processed/waymo_extras_not_in_hub.csv  (NHTSA crashes not in Waymo Hub)

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
    PROCESSED_MERGED, PROCESSED_EXTRAS, PROCESSED_DIR,
    WAYMO_ENTITY_NAME, COLUMN_RENAMES_PRIOR_TO_POST,
)


def load_and_filter_nhtsa(filepath, label):
    """
    Load an NHTSA CSV and keep only Waymo crashes.

    The NHTSA data contains crashes from ALL autonomous vehicle companies
    (Waymo, Cruise, Zoox, Tesla, etc.). We filter to keep only Waymo.

    Parameters:
        filepath (str): Path to the NHTSA CSV file
        label (str): Human-readable label for logging (e.g., "Prior to June 16")

    Returns:
        pd.DataFrame: Only the rows where Reporting Entity == "Waymo LLC"
    """
    print(f"  Loading {label}...")
    # NHTSA CSVs sometimes contain non-UTF-8 characters (e.g., smart quotes).
    # Try UTF-8 first, fall back to latin-1 which handles all byte values.
    try:
        df = pd.read_csv(filepath, encoding="utf-8")
    except UnicodeDecodeError:
        print(f"    Note: UTF-8 failed, using latin-1 encoding")
        df = pd.read_csv(filepath, encoding="latin-1")
    print(f"    Total rows (all companies): {len(df)}")

    # Filter for Waymo only
    # .copy() creates an independent copy so edits don't affect the original
    waymo = df[df["Reporting Entity"] == WAYMO_ENTITY_NAME].copy()
    print(f"    Waymo rows: {len(waymo)}")

    return waymo


def harmonize_columns(waymo_prior):
    """
    Rename columns in the Amendment 2 data to match Amendment 3 naming.

    NHTSA changed some column names when they updated the reporting format.
    We rename the older format to match the newer one so the datasets can
    be combined. See config.py for the full mapping.

    Parameters:
        waymo_prior (pd.DataFrame): The pre-June-16 NHTSA data

    Returns:
        pd.DataFrame: Same data with renamed columns
    """
    waymo_prior = waymo_prior.rename(columns=COLUMN_RENAMES_PRIOR_TO_POST)
    print(f"  Renamed {len(COLUMN_RENAMES_PRIOR_TO_POST)} columns to match Amendment 3 format")
    return waymo_prior


def combine_and_deduplicate(waymo_prior, waymo_post):
    """
    Stack the two NHTSA datasets and remove duplicate report versions.

    Some crashes have multiple report versions (updates submitted over time).
    We keep only the most recent version of each crash to avoid double-counting.

    Parameters:
        waymo_prior (pd.DataFrame): Pre-June-16 Waymo crashes (Amendment 2)
        waymo_post (pd.DataFrame): Post-June-16 Waymo crashes (Amendment 3)

    Returns:
        pd.DataFrame: Combined dataset with only the latest version per crash
    """
    # Tag each dataset with which amendment period it came from
    waymo_prior["Data Period"] = "Prior to June 16, 2025 (Amendment 2)"
    waymo_post["Data Period"] = "After June 16, 2025 (Amendment 3)"

    # Stack them vertically (like stacking two Excel sheets on top of each other)
    combined = pd.concat([waymo_prior, waymo_post], ignore_index=True)
    print(f"  Combined: {len(waymo_prior)} + {len(waymo_post)} = {len(combined)} rows")

    # Count duplicates before removing them
    unique_before = combined["Report ID"].nunique()
    dupes = len(combined) - unique_before
    print(f"  Duplicate report versions to remove: {dupes}")

    # Sort by Report ID and version, then keep only the latest version
    combined = combined.sort_values(["Report ID", "Report Version"])
    combined = combined.drop_duplicates(subset="Report ID", keep="last")

    print(f"  After deduplication: {len(combined)} unique crashes")
    return combined


def merge_with_hub(waymo_hub, nhtsa_combined):
    """
    Merge the Waymo Safety Hub data with NHTSA crash details.

    Uses a LEFT JOIN with the Waymo Hub as the base. This means:
    - ALL hub rows are kept (even if no NHTSA match)
    - NHTSA columns are added where there's a matching Report ID
    - Hub rows without a match get NaN in the NHTSA columns

    The merge key:
    - Waymo Hub uses "SGO Report ID"
    - NHTSA uses "Report ID"
    - They contain the same values (e.g., "30270-11853")

    Parameters:
        waymo_hub (pd.DataFrame): Waymo's curated crash data (1,123 rows)
        nhtsa_combined (pd.DataFrame): Combined/deduplicated NHTSA data

    Returns:
        tuple: (merged DataFrame, extras DataFrame)
            - merged: Hub + NHTSA data for matching crashes
            - extras: NHTSA crashes that don't appear in the hub
    """
    # Figure out which NHTSA crashes match the hub
    hub_ids = set(waymo_hub["SGO Report ID"].dropna())
    nhtsa_ids = set(nhtsa_combined["Report ID"].dropna())

    in_both = hub_ids & nhtsa_ids
    nhtsa_only = nhtsa_ids - hub_ids

    print(f"  Crashes in both datasets: {len(in_both)}")
    print(f"  Hub rows with no SGO Report ID: {waymo_hub['SGO Report ID'].isna().sum()}")
    print(f"  NHTSA crashes not in hub: {len(nhtsa_only)} (saved separately)")

    # Separate out the NHTSA crashes that aren't in the hub
    extras = nhtsa_combined[~nhtsa_combined["Report ID"].isin(hub_ids)].copy()

    # Add a reason flag explaining why they're not in the hub
    extras["Reason Not In Hub"] = extras["Data Period"].apply(
        lambda x: "Likely newer than hub update cycle (post-June 2025)"
        if x == "After June 16, 2025 (Amendment 3)"
        else "Likely excluded by Waymo hub methodology (pre-June 2025)"
    )

    # Only merge the NHTSA crashes that exist in the hub
    nhtsa_for_merge = nhtsa_combined[nhtsa_combined["Report ID"].isin(hub_ids)].copy()

    # Perform the left join
    # suffixes=('', '_nhtsa') means: if both datasets have the same column name,
    # the hub version keeps its name and the NHTSA version gets '_nhtsa' appended
    merged = waymo_hub.merge(
        nhtsa_for_merge,
        left_on="SGO Report ID",
        right_on="Report ID",
        how="left",
        suffixes=("", "_nhtsa"),
    )

    # Verify the merge didn't create unexpected duplicates
    if len(merged) == len(waymo_hub):
        print(f"  Merge successful: {len(merged)} rows (matches hub size)")
    else:
        print(f"  WARNING: Row count changed! Hub had {len(waymo_hub)}, merged has {len(merged)}")

    return merged, extras


def main():
    """Run the full merge pipeline."""
    print("=" * 60)
    print("STEP 2: MERGING NHTSA + WAYMO HUB DATA")
    print("=" * 60)

    # --- Load and filter NHTSA data ---
    print()
    print("Loading NHTSA data...")
    waymo_prior = load_and_filter_nhtsa(RAW_NHTSA_PRIOR, "NHTSA Prior (Amendment 2)")
    waymo_post = load_and_filter_nhtsa(RAW_NHTSA_POST, "NHTSA Post (Amendment 3)")

    # --- Harmonize column names ---
    print()
    print("Harmonizing column names...")
    waymo_prior = harmonize_columns(waymo_prior)

    # --- Combine and deduplicate ---
    print()
    print("Combining and deduplicating...")
    nhtsa_combined = combine_and_deduplicate(waymo_prior, waymo_post)

    # --- Load Waymo Hub ---
    print()
    print("Loading Waymo Safety Hub...")
    waymo_hub = pd.read_csv(RAW_WAYMO_HUB)
    print(f"  Waymo Hub rows: {len(waymo_hub)}")
    print(f"  Date range: {waymo_hub['Year Month'].min()} to {waymo_hub['Year Month'].max()}")

    # --- Merge ---
    print()
    print("Merging datasets...")
    merged, extras = merge_with_hub(waymo_hub, nhtsa_combined)

    # --- Save outputs ---
    print()
    print("Saving output files...")
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    merged.to_csv(PROCESSED_MERGED, index=False)
    print(f"  Merged: {PROCESSED_MERGED} ({len(merged)} rows x {len(merged.columns)} cols)")

    extras.to_csv(PROCESSED_EXTRAS, index=False)
    print(f"  Extras: {PROCESSED_EXTRAS} ({len(extras)} rows)")

    # --- Summary ---
    print()
    print("=" * 60)
    print("MERGE COMPLETE")
    print("=" * 60)
    print(f"  Input:  {len(waymo_prior)} prior + {len(waymo_post)} post = {len(waymo_prior) + len(waymo_post)} NHTSA rows")
    print(f"  Hub:    {len(waymo_hub)} rows")
    print(f"  Output: {len(merged)} merged rows, {len(extras)} extras")


if __name__ == "__main__":
    main()
