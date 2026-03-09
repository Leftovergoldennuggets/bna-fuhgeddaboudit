"""
03_compute_statistics.py — Compute ALL statistics for the website
==========================================================================
This is the key "evergreen" script. Every number that appears on the website
comes from the JSON file this script produces (site-data.json).

When the data updates, re-running this script regenerates all the statistics
so the website always shows current numbers.

What it computes:
  - Total crash counts and date ranges
  - City breakdowns (count and percentage per city)
  - Time period analysis (rush hour %, late night %, peak hours)
  - Crash type distribution
  - Severity indicators (police-reported, injury, airbag, serious injury rates)
  - Location type analysis (intersection, highway, parking, etc.)
  - City-specific peak hours
  - Waymo published safety context (miles driven, comparison to human drivers)

Also generates matplotlib PNG figures for the scrollytelling sections.

Inputs:
  - data/processed/waymo_merged.csv (from step 02)

Outputs:
  - data/web/site-data.json (ALL statistics the website displays)
  - site/assets/images/*.png (chart images for scrollytelling)

Usage:
  python pipeline/03_compute_statistics.py
==========================================================================
"""

import os
import sys
import json
import re
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend (no display needed)
import matplotlib.pyplot as plt
import seaborn as sns

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    PROCESSED_MERGED, WEB_SITE_DATA, SITE_IMAGES_DIR,
    TIME_PERIODS, CITIES, WAYMO_PUBLISHED_STATS, LOCATION_PATTERNS,
    STATIC_MILES_BY_CITY,
)


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def parse_time(time_str):
    """
    Parse a time string from the NHTSA data into hour and minute.

    The NHTSA "Incident Time (24:00)" column can be in various formats:
    - "14:30" (HH:MM)
    - "1430" (HHMM)
    - Or empty/invalid

    Returns:
        tuple: (hour, minute) or (None, None) if parsing fails
    """
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


def categorize_time_period(hour):
    """
    Assign a named time period to an hour of the day.

    Uses the TIME_PERIODS defined in config.py. "Late Night" wraps around
    midnight (hour 23 through hour 4).

    Parameters:
        hour: Integer 0-23 or None

    Returns:
        str: Time period name (e.g., "Morning Rush") or "Unknown"
    """
    if hour is None or pd.isna(hour):
        return "Unknown"
    hour = int(hour)
    for period_name, (start, end) in TIME_PERIODS.items():
        if start < end:
            # Normal range (e.g., 7-10)
            if start <= hour < end:
                return period_name
        else:
            # Wraps around midnight (e.g., 23-5)
            if hour >= start or hour < end:
                return period_name
    return "Unknown"


def extract_location_type(row):
    """
    Determine where a crash happened based on its narrative text and address.

    Searches the crash narrative and location description for keywords that
    indicate the type of location (intersection, highway, parking lot, etc.).
    Patterns are checked in order — first match wins.

    Parameters:
        row: A DataFrame row with 'Narrative', 'Location Address / Description', 'Address' columns

    Returns:
        str: Location type (e.g., "Intersection", "Highway/Freeway", "Street/Road")
    """
    # Combine all text fields for searching
    text = ""
    for col in ["Narrative", "Location Address / Description", "Address"]:
        val = row.get(col)
        if pd.notna(val):
            text += str(val).lower() + " "

    if not text.strip():
        return "Other/Unknown"

    # Check each location type's regex patterns
    for loc_type, patterns in LOCATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return loc_type

    # Fallback: check if it mentions a street/road
    if re.search(r"\b(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|way|lane|ln)\b", text, re.IGNORECASE):
        return "Street/Road"

    return "Other/Unknown"


def parse_date(date_str):
    """
    Parse a date string from the data into a pandas Timestamp.

    Tries multiple formats since the data has inconsistent date formatting.
    """
    if pd.isna(date_str):
        return None
    try:
        date_str = str(date_str).strip()
        for fmt in ["%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y"]:
            try:
                return pd.to_datetime(date_str, format=fmt)
            except (ValueError, TypeError):
                continue
        return pd.to_datetime(date_str)
    except (ValueError, TypeError):
        return None


# ===========================================================================
# MAIN COMPUTATION
# ===========================================================================

def compute_all_statistics(df):
    """
    Compute every statistic the website needs from the merged dataset.

    Returns a dictionary that gets saved as site-data.json.
    """
    stats = {}

    # -------------------------------------------------------------------
    # META: When this was generated, data source info
    # -------------------------------------------------------------------
    stats["meta"] = {
        "generated_at": datetime.now().isoformat(),
        "pipeline_version": "1.0",
        "total_rows_in_merged": len(df),
        "date_range_start": int(df["Year Month"].min()) if "Year Month" in df.columns else None,
        "date_range_end": int(df["Year Month"].max()) if "Year Month" in df.columns else None,
    }

    # -------------------------------------------------------------------
    # OVERVIEW: Top-level numbers
    # All crashes are counted (including small cities like Mountain View),
    # but the city breakdown only lists cities in the CITIES dictionary.
    # -------------------------------------------------------------------
    total_crashes = len(df)

    # Only list recognized operating cities (from config.py) in the display
    recognized_cities = sorted([c for c in df["Location"].dropna().unique() if c in CITIES])
    city_display_names = [CITIES[c]["name"] for c in recognized_cities]

    stats["overview"] = {
        "total_crashes": total_crashes,
        "cities_count": len(recognized_cities),
        "cities_list": city_display_names,
    }

    # -------------------------------------------------------------------
    # CITY BREAKDOWN: How many crashes in each recognized city
    # Crashes from unrecognized cities (e.g. Mountain View with only 2)
    # are still in total_crashes but don't get their own city card.
    # -------------------------------------------------------------------
    city_counts = df["Location"].value_counts()
    city_breakdown = {}
    for city_code, count in city_counts.items():
        if city_code not in CITIES:
            continue  # Skip cities not in our recognized list
        display_name = CITIES[city_code]["name"]
        city_breakdown[display_name] = {
            "code": city_code,
            "count": int(count),
            "percentage": round(count / total_crashes * 100, 1),
        }
    stats["city_breakdown"] = city_breakdown

    # -------------------------------------------------------------------
    # SEVERITY INDICATORS: Simple boolean rates (no arbitrary scoring)
    # -------------------------------------------------------------------
    # Convert string "True"/"False" to actual booleans
    bool_cols = {
        "Is Police-Reported": "police_reported",
        "Is Any-Injury-Reported": "injury_reported",
        "Is Any Vehicle Airbag Deployment": "airbag_any_vehicle",
        "Is Ego Vehicle Airbag Deployment": "airbag_ego_vehicle",
        "Is Suspected Serious Injury+": "serious_injury",
    }

    severity = {}
    for col, key in bool_cols.items():
        if col in df.columns:
            # Convert to boolean (handles string "True"/"False" and actual booleans)
            bool_series = df[col].map({"True": True, "False": False, True: True, False: False})
            count = int(bool_series.sum())
            severity[key] = {
                "count": count,
                "percentage": round(count / total_crashes * 100, 1),
            }

    # Also compute a count from the NHTSA text field "Highest Injury Severity Alleged"
    # which captures moderate, serious, and fatal injuries. This matches the 15 incidents
    # shown on the map (from 05_generate_incidents.py) and is more complete than the
    # Waymo Hub boolean "Is Suspected Serious Injury+" which only flags 3.
    severity_col = "Highest Injury Severity Alleged"
    if severity_col in df.columns:
        def _is_moderate_plus(val):
            if pd.isna(val):
                return False
            v = str(val).lower()
            return "moderate" in v or "serious" in v or "fatal" in v

        moderate_plus = df[severity_col].apply(_is_moderate_plus)
        severity["moderate_plus"] = {
            "count": int(moderate_plus.sum()),
            "percentage": round(moderate_plus.sum() / total_crashes * 100, 1),
        }

    stats["severity"] = severity

    # SF-specific severity (for the scrollytelling step focused on San Francisco)
    if severity_col in df.columns:
        sf_mask = df["Location"] == "SAN_FRANCISCO"
        sf_moderate_plus = df.loc[sf_mask, severity_col].apply(_is_moderate_plus)
        severity["sf_moderate_plus"] = {
            "count": int(sf_moderate_plus.sum()),
            "percentage": round(sf_moderate_plus.sum() / int(sf_mask.sum()) * 100, 1) if sf_mask.sum() > 0 else 0,
        }

    # -------------------------------------------------------------------
    # CRASH TYPES: Distribution of crash classifications
    # -------------------------------------------------------------------
    crash_types = df["Crash Type"].value_counts()
    stats["crash_types"] = {
        ct: {
            "count": int(count),
            "percentage": round(count / total_crashes * 100, 1),
        }
        for ct, count in crash_types.items()
    }

    # -------------------------------------------------------------------
    # TEMPORAL ANALYSIS: Time-of-day patterns
    # -------------------------------------------------------------------
    # Parse time data from the NHTSA "Incident Time (24:00)" column
    df["_hour"], df["_minute"] = zip(*df["Incident Time (24:00)"].apply(parse_time))
    df_time = df[df["_hour"].notna()].copy()
    df_time["_hour"] = df_time["_hour"].astype(int)

    total_with_time = len(df_time)
    stats["overview"]["total_with_time_data"] = total_with_time

    # Categorize each crash into a time period
    df_time["_time_period"] = df_time["_hour"].apply(categorize_time_period)

    # Time period counts and percentages
    tp_counts = df_time["_time_period"].value_counts()
    time_period_order = list(TIME_PERIODS.keys())
    time_period_stats = {}
    for period in time_period_order:
        count = int(tp_counts.get(period, 0))
        time_period_stats[period] = {
            "count": count,
            "percentage": round(count / total_with_time * 100, 1) if total_with_time > 0 else 0,
        }
    stats["time_periods"] = time_period_stats

    # Rush hour stats (Morning Rush 7-9 AM + Evening Rush 5-7 PM)
    # Note: Using explicit parentheses to avoid operator precedence issues
    rush_hour = df_time[
        ((df_time["_hour"] >= 7) & (df_time["_hour"] <= 9))
        | ((df_time["_hour"] >= 17) & (df_time["_hour"] <= 19))
    ]
    rush_hour_pct = round(len(rush_hour) / total_with_time * 100, 1) if total_with_time > 0 else 0

    # Late night stats (11 PM - 4 AM)
    late_night = df_time[(df_time["_hour"] >= 23) | (df_time["_hour"] <= 4)]
    late_night_pct = round(len(late_night) / total_with_time * 100, 1) if total_with_time > 0 else 0

    # Day vs night
    daytime = df_time[(df_time["_hour"] >= 6) & (df_time["_hour"] < 20)]
    nighttime = df_time[(df_time["_hour"] >= 20) | (df_time["_hour"] < 6)]

    stats["temporal"] = {
        "rush_hour_count": len(rush_hour),
        "rush_hour_percentage": rush_hour_pct,
        "late_night_count": len(late_night),
        "late_night_percentage": late_night_pct,
        "daytime_count": len(daytime),
        "daytime_percentage": round(len(daytime) / total_with_time * 100, 1) if total_with_time > 0 else 0,
        "nighttime_count": len(nighttime),
        "nighttime_percentage": round(len(nighttime) / total_with_time * 100, 1) if total_with_time > 0 else 0,
    }

    # Hourly distribution (for charts)
    hourly_counts = df_time["_hour"].value_counts().sort_index()
    stats["temporal"]["hourly_distribution"] = {
        str(h): int(hourly_counts.get(h, 0)) for h in range(24)
    }

    # -------------------------------------------------------------------
    # CITY PEAKS: Peak crash hour for each city
    # -------------------------------------------------------------------
    # Parse dates for day-of-week analysis
    df_time["_date"] = df_time["Incident Date"].apply(parse_date)
    df_time_dated = df_time[df_time["_date"].notna()].copy()
    # Convert to proper datetime (parse_date returns mixed types that need conversion)
    df_time_dated["_date"] = pd.to_datetime(df_time_dated["_date"])
    df_time_dated["_day_of_week"] = df_time_dated["_date"].dt.day_name()
    df_time_dated["_is_weekend"] = df_time_dated["_date"].dt.dayofweek.isin([5, 6])

    city_peaks = {}
    for city_code in df_time["Location"].dropna().unique():
        city_df = df_time[df_time["Location"] == city_code]
        if len(city_df) >= 10:
            peak_hour = city_df["_hour"].mode()
            if len(peak_hour) > 0:
                peak_h = int(peak_hour.iloc[0])
                # Format hour for display (e.g., 17 → "5:00 PM")
                if peak_h == 0:
                    peak_label = "Midnight"
                elif peak_h == 12:
                    peak_label = "12:00 PM"
                elif peak_h < 12:
                    peak_label = f"{peak_h}:00 AM"
                else:
                    peak_label = f"{peak_h - 12}:00 PM"

                display_name = CITIES.get(city_code, {}).get("name", city_code)
                city_peaks[display_name] = {
                    "peak_hour": peak_h,
                    "peak_label": peak_label,
                    "total_crashes": int(len(city_df)),
                }
    stats["city_peaks"] = city_peaks

    # -------------------------------------------------------------------
    # LOCATION TYPES: Where crashes happen
    # -------------------------------------------------------------------
    df_time["_location_type"] = df_time.apply(extract_location_type, axis=1)
    loc_counts = df_time["_location_type"].value_counts()
    stats["location_types"] = {
        lt: {
            "count": int(count),
            "percentage": round(count / total_with_time * 100, 1) if total_with_time > 0 else 0,
        }
        for lt, count in loc_counts.items()
    }

    # -------------------------------------------------------------------
    # DAY OF WEEK ANALYSIS
    # -------------------------------------------------------------------
    if len(df_time_dated) > 0:
        dow_counts = df_time_dated["_day_of_week"].value_counts()
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        stats["day_of_week"] = {
            day: int(dow_counts.get(day, 0)) for day in day_order
        }

        # Weekend vs weekday
        weekend_count = int(df_time_dated["_is_weekend"].sum())
        weekday_count = len(df_time_dated) - weekend_count
        stats["temporal"]["weekend_count"] = weekend_count
        stats["temporal"]["weekday_count"] = weekday_count
        stats["temporal"]["weekend_percentage"] = round(weekend_count / len(df_time_dated) * 100, 1)

        # Peak hours by day of week (for heatmap)
        peak_by_day = {}
        for day in day_order:
            day_df = df_time_dated[df_time_dated["_day_of_week"] == day]
            if len(day_df) > 0:
                peak = day_df["_hour"].mode()
                if len(peak) > 0:
                    peak_by_day[day] = {
                        "peak_hour": int(peak.iloc[0]),
                        "total": int(len(day_df)),
                    }
        stats["temporal"]["peak_by_day"] = peak_by_day

    # -------------------------------------------------------------------
    # CRASH CIRCUMSTANCES: Speed, crash type, vulnerable road users
    # Used by the "What Happens in These Crashes?" section
    # -------------------------------------------------------------------
    crash_circumstances = {}

    # Speed distribution — bucket SV Precrash Speed into ranges
    speed_col = "SV Precrash Speed (MPH)"
    if speed_col in df.columns:
        speeds = pd.to_numeric(df[speed_col], errors="coerce").dropna()
        total_with_speed = len(speeds)

        # Define speed buckets
        buckets = [
            ("0_mph", speeds == 0),
            ("1_5_mph", (speeds >= 1) & (speeds <= 5)),
            ("6_15_mph", (speeds >= 6) & (speeds <= 15)),
            ("16_25_mph", (speeds >= 16) & (speeds <= 25)),
            ("26_35_mph", (speeds >= 26) & (speeds <= 35)),
            ("36_plus_mph", speeds >= 36),
        ]
        speed_dist = {}
        for bucket_name, mask in buckets:
            count = int(mask.sum())
            speed_dist[bucket_name] = {
                "count": count,
                "percentage": round(count / total_with_speed * 100, 1) if total_with_speed > 0 else 0,
            }
        crash_circumstances["speed_distribution"] = speed_dist

        crash_circumstances["speed_stats"] = {
            "total_with_speed_data": total_with_speed,
            "median_speed_mph": round(float(speeds.median()), 1),
            "mean_speed_mph": round(float(speeds.mean()), 1),
        }

    # Crash type with plain English labels
    crash_type_labels = {
        "V2V F2R": "Rear-end collision",
        "V2V Lateral": "Side-impact collision",
        "V2V Backing": "Backing collision",
        "Single Vehicle": "Single vehicle",
        "V2V Head-on": "Head-on collision",
        "V2V Intersection": "Intersection collision",
        "All Others": "Other",
        "Secondary Crash": "Secondary crash",
        "Motorcycle": "Motorcycle",
        "Cyclist": "Cyclist",
        "Pedestrian": "Pedestrian",
    }
    if "Crash Type" in df.columns:
        ct_counts = df["Crash Type"].value_counts()
        crash_type_plain = {}
        for code, count in ct_counts.items():
            label = crash_type_labels.get(code, code)
            crash_type_plain[label] = {
                "count": int(count),
                "percentage": round(count / total_crashes * 100, 1),
            }
        crash_circumstances["crash_type_plain"] = crash_type_plain

    # Vulnerable road users (pedestrians, cyclists, motorcyclists)
    if "Crash Type" in df.columns:
        vru_types = {"Pedestrian": "pedestrian", "Cyclist": "cyclist", "Motorcycle": "motorcycle"}
        vru_counts = {}
        vru_total = 0
        for crash_code, key in vru_types.items():
            count = int((df["Crash Type"] == crash_code).sum())
            vru_counts[key] = count
            vru_total += count
        crash_circumstances["vulnerable_road_users"] = {
            "total": vru_total,
            "percentage": round(vru_total / total_crashes * 100, 1),
            **vru_counts,
        }

    stats["crash_circumstances"] = crash_circumstances

    # -------------------------------------------------------------------
    # CITY MILEAGE: Crash rates per million miles by city
    # Uses manually maintained miles_by_city.json from Waymo's Safety Hub.
    # -------------------------------------------------------------------
    if os.path.exists(STATIC_MILES_BY_CITY):
        with open(STATIC_MILES_BY_CITY, "r") as f:
            miles_data = json.load(f)

        city_mileage = {}
        for city_code, city_info in CITIES.items():
            display_name = city_info["name"]
            city_crash_count = int(city_counts.get(city_code, 0))
            miles_entry = miles_data.get("cities", {}).get(display_name, {})
            miles_millions = miles_entry.get("miles_millions")

            if miles_millions is not None and miles_millions > 0:
                rate = round(city_crash_count / miles_millions, 1)
            else:
                rate = None

            city_mileage[display_name] = {
                "miles_millions": miles_millions,
                "crashes_per_million_miles": rate,
            }

        stats["city_mileage"] = city_mileage
        stats["city_mileage_meta"] = {
            "data_through": miles_data.get("data_through"),
            "source_url": miles_data.get("source_url"),
        }
    else:
        print(f"  WARNING: {STATIC_MILES_BY_CITY} not found — skipping city mileage stats")

    # -------------------------------------------------------------------
    # WAYMO PUBLISHED SAFETY CONTEXT
    # -------------------------------------------------------------------
    # These numbers come from Waymo's research, NOT from our data analysis.
    # They provide important context about overall safety performance.
    stats["waymo_context"] = WAYMO_PUBLISHED_STATS

    return stats, df_time, df_time_dated


def generate_figures(df_time, df_time_dated):
    """
    Generate matplotlib PNG figures for the scrollytelling sections.

    These are static images displayed during the scroll narrative.
    They get regenerated each time the pipeline runs with fresh data.
    """
    os.makedirs(SITE_IMAGES_DIR, exist_ok=True)

    plt.style.use("seaborn-v0_8-whitegrid")
    sns.set_palette("husl")

    # --- Figure 1: Time-of-day analysis (4-panel) ---
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))

    # Panel 1: Hourly distribution
    ax1 = axes[0, 0]
    hourly_total = df_time["_hour"].value_counts().sort_index()
    colors = ["#ff6b6b" if (7 <= h <= 9 or 17 <= h <= 19) else "#4dabf7" for h in range(24)]
    ax1.bar(range(24), [hourly_total.get(h, 0) for h in range(24)], color=colors, alpha=0.8, edgecolor="black")
    ax1.axvspan(7, 10, alpha=0.15, color="red", label="Morning Rush (7-10)")
    ax1.axvspan(17, 20, alpha=0.15, color="orange", label="Evening Rush (5-8)")
    ax1.set_xlabel("Hour of Day", fontsize=12)
    ax1.set_ylabel("Number of Crashes", fontsize=12)
    ax1.set_title("Overall Hourly Crash Distribution", fontsize=14, fontweight="bold")
    ax1.set_xticks(range(0, 24, 2))
    ax1.legend(loc="upper left")

    # Panel 2: Time period breakdown
    ax2 = axes[0, 1]
    tp_counts = df_time["_time_period"].value_counts()
    time_period_order = list(TIME_PERIODS.keys())
    tp_ordered = tp_counts.reindex([t for t in time_period_order if t in tp_counts.index])
    colors_tp = ["#ffd93d", "#ff6b6b", "#6bcb77", "#4d96ff", "#ff8c42", "#ff6b6b", "#845ec2", "#2c3e50"]
    ax2.barh(range(len(tp_ordered)), tp_ordered.values, color=colors_tp[: len(tp_ordered)], alpha=0.8)
    ax2.set_yticks(range(len(tp_ordered)))
    ax2.set_yticklabels(tp_ordered.index, fontsize=10)
    ax2.set_xlabel("Number of Crashes", fontsize=12)
    ax2.set_title("Crashes by Time Period", fontsize=14, fontweight="bold")
    total_time = len(df_time)
    for i, v in enumerate(tp_ordered.values):
        ax2.text(v + 2, i, f"{v} ({v / total_time * 100:.1f}%)", va="center", fontsize=9)

    # Panel 3: Weekday vs Weekend (if date data available)
    ax3 = axes[1, 0]
    if len(df_time_dated) > 0:
        weekday_hourly = df_time_dated[~df_time_dated["_is_weekend"]].groupby("_hour").size()
        weekend_hourly = df_time_dated[df_time_dated["_is_weekend"]].groupby("_hour").size()
        x = range(24)
        width = 0.35
        ax3.bar([i - width / 2 for i in x], [weekday_hourly.get(h, 0) for h in x], width, label="Weekday", color="steelblue", alpha=0.8)
        ax3.bar([i + width / 2 for i in x], [weekend_hourly.get(h, 0) for h in x], width, label="Weekend", color="coral", alpha=0.8)
        ax3.set_xlabel("Hour of Day", fontsize=12)
        ax3.set_ylabel("Number of Crashes", fontsize=12)
        ax3.set_title("Weekday vs Weekend Hourly Patterns", fontsize=14, fontweight="bold")
        ax3.legend()
        ax3.set_xticks(range(0, 24, 2))
    else:
        ax3.text(0.5, 0.5, "Date data not available", ha="center", va="center", transform=ax3.transAxes)

    # Panel 4: Day vs Night pie chart
    ax4 = axes[1, 1]
    daytime = df_time[(df_time["_hour"] >= 6) & (df_time["_hour"] < 20)]
    nighttime = df_time[(df_time["_hour"] >= 20) | (df_time["_hour"] < 6)]
    labels = [f"Daytime\n(6 AM–8 PM)\n{len(daytime)} crashes", f"Nighttime\n(8 PM–6 AM)\n{len(nighttime)} crashes"]
    ax4.pie([len(daytime), len(nighttime)], labels=labels, autopct="%1.1f%%", colors=["#ffd93d", "#2c3e50"], explode=(0.02, 0.02))
    ax4.set_title("Day vs Night Crashes", fontsize=14, fontweight="bold")

    plt.tight_layout()
    path = os.path.join(SITE_IMAGES_DIR, "time_of_day_analysis.png")
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")

    # --- Figure 2: Location type analysis (2-panel) ---
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Panel 1: Location type distribution
    ax1 = axes[0]
    loc_counts = df_time["_location_type"].value_counts().head(8)
    ax1.barh(range(len(loc_counts)), loc_counts.values, color="steelblue", alpha=0.8)
    ax1.set_yticks(range(len(loc_counts)))
    ax1.set_yticklabels(loc_counts.index, fontsize=10)
    ax1.set_xlabel("Number of Crashes", fontsize=12)
    ax1.set_title("Crashes by Location Type", fontsize=14, fontweight="bold")
    for i, v in enumerate(loc_counts.values):
        ax1.text(v + 2, i, f"{v} ({v / total_time * 100:.1f}%)", va="center", fontsize=9)

    # Panel 2: Hourly pattern for top location types
    ax2 = axes[1]
    top_locs = df_time["_location_type"].value_counts().head(4).index
    for lt in top_locs:
        lt_hourly = df_time[df_time["_location_type"] == lt].groupby("_hour").size()
        ax2.plot(range(24), [lt_hourly.get(h, 0) for h in range(24)], marker="o", label=lt, linewidth=2)
    ax2.set_xlabel("Hour of Day", fontsize=12)
    ax2.set_ylabel("Number of Crashes", fontsize=12)
    ax2.set_title("Hourly Pattern by Location Type", fontsize=14, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.set_xticks(range(0, 24, 2))

    plt.tight_layout()
    path = os.path.join(SITE_IMAGES_DIR, "location_time_analysis.png")
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def main():
    """Compute all statistics and generate figures."""
    print("=" * 60)
    print("STEP 3: COMPUTING STATISTICS")
    print("=" * 60)
    print()

    # Load the merged dataset from step 02
    print("Loading merged dataset...")
    df = pd.read_csv(PROCESSED_MERGED)
    print(f"  Loaded {len(df)} rows")

    # Compute all statistics
    print()
    print("Computing statistics...")
    stats, df_time, df_time_dated = compute_all_statistics(df)

    # Save site-data.json
    print()
    print("Saving site-data.json...")
    os.makedirs(os.path.dirname(WEB_SITE_DATA), exist_ok=True)
    with open(WEB_SITE_DATA, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Saved: {WEB_SITE_DATA}")

    # Print summary of key stats
    print()
    print("Key statistics:")
    print(f"  Total crashes: {stats['overview']['total_crashes']}")
    print(f"  Cities: {stats['overview']['cities_count']}")
    print(f"  With time data: {stats['overview']['total_with_time_data']}")
    print(f"  Rush hour: {stats['temporal']['rush_hour_percentage']}%")
    print(f"  Late night: {stats['temporal']['late_night_percentage']}%")
    for city, data in stats["city_breakdown"].items():
        print(f"  {city}: {data['count']} crashes ({data['percentage']}%)")

    # Generate figures
    print()
    print("Generating figures...")
    generate_figures(df_time, df_time_dated)

    print()
    print("Statistics computation complete!")


if __name__ == "__main__":
    main()
