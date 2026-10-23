"""
03_compute_statistics.py — Compute ALL statistics for the website
==========================================================================
This is the key "evergreen" script. Every number that appears on the
website comes from the JSON file this script produces (site-data.json).

HEADLINE DATASET: crashes during driverless operation (no human driver in
the vehicle). Crashes from supervised testing (a human safety driver
behind the wheel) are counted separately — they reflect a different kind
of operation and Waymo's own published mileage covers driverless
(rider-only) driving, so mixing them would distort comparisons.

What it computes:
  - Total crash counts, date ranges, data-freshness labels
  - Metro breakdowns (count and percentage per metro)
  - Monthly crash trend (for the crashes-over-time chart)
  - Time period analysis (rush hour %, late night %, peak hours)
  - Crash type distribution, severity rates, speed distribution
  - Roadway type analysis (NHTSA's structured field), city peak hours
  - Metro metadata (coordinates, status) the map reads at runtime
  - Reporting completeness (which recent months are still filling in)
  - Per-metro and quarterly crash rates per million rider-only miles
  - Waymo's own comparisons against human benchmarks (hub CSV3)

Inputs:
  - data/processed/waymo_merged.csv (from step 02)

Outputs:
  - data/web/site-data.json (ALL statistics the website displays)

Usage:
  python pipeline/03_compute_statistics.py
==========================================================================
"""

import os
import sys
import json
from datetime import datetime

import pandas as pd

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    PROCESSED_MERGED, WEB_SITE_DATA, WEB_UPDATE_HISTORY, RAW_WAYMO_CSV3,
    TIME_PERIODS, CITIES, OTHER_METRO_CODE, ANNOUNCED_METROS,
    WAYMO_PUBLISHED_STATS, STATIC_MILES_BY_CITY, STATIC_MILES_QUARTERLY,
    STATIC_MILEAGE_MILESTONES,
    BENCHMARK_OUTCOMES, SGO_AMENDMENT_3_DATE,
)
from pipeline.utils import (
    parse_time, categorize_time_period, roadway_type,
    is_moderate_plus, parse_month_label, complete_through,
    quarter_end, benchmark_summary,
)


def year_month_label(year_month):
    """Format integer 202604 as "April 2026" for display."""
    if year_month is None or pd.isna(year_month):
        return None
    year_month = int(year_month)
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    month = year_month % 100
    if not 1 <= month <= 12:
        return None
    return f"{months[month - 1]} {year_month // 100}"


def metro_display_name(code):
    """Display name for a metro code (the OTHER bucket included)."""
    if code == OTHER_METRO_CODE:
        return "Other"
    return CITIES.get(code, {}).get("name", code)


def compute_mileage_series():
    """Cumulative rider-only miles over time, oldest first.

    Merges the hand-sourced milestones (press releases, papers) with the
    cumulative total of every quarterly CSV1 release, so the chart extends
    itself each quarter. Each point keeps its source and URL.
    """
    import calendar
    points = []
    if os.path.exists(STATIC_MILEAGE_MILESTONES):
        with open(STATIC_MILEAGE_MILESTONES) as f:
            for m in json.load(f).get("milestones", []):
                points.append({**m, "kind": "milestone"})
    if os.path.exists(STATIC_MILES_QUARTERLY):
        with open(STATIC_MILES_QUARTERLY) as f:
            for q in json.load(f).get("quarters", []):
                year, month = divmod(int(q["through"]), 100)
                last_day = calendar.monthrange(year, month)[1]
                points.append({
                    "date": f"{year}-{month:02d}-{last_day:02d}",
                    "miles_millions": q["total_miles_millions"],
                    "source": f"Waymo Safety Impact Data Hub CSV1, data through {year_month_label(q['through'])}",
                    "url": q.get("source_url"),
                    "kind": "hub",
                })
    return sorted(points, key=lambda p: p["date"])


def compute_quarterly_rates(df):
    """Crash rates per million rider-only miles for each quarter.

    Returns {"amendment_3_quarter": YYYYMM, "series": {metro: [rows]}},
    where metro is "All metros" or a metro display name and each row has
    the quarter-end, miles driven that quarter, and counts/rates for all
    hub crashes, injury crashes and police-reported crashes.
    """
    if not os.path.exists(STATIC_MILES_QUARTERLY):
        return {}
    with open(STATIC_MILES_QUARTERLY) as f:
        quarters = json.load(f).get("quarters", [])
    if len(quarters) < 2:
        return {}

    hub = df[df["in_hub"].astype(bool)].copy()
    hub["_quarter"] = hub["Year Month"].astype(int).map(quarter_end)
    flags = {
        "injury": hub.get("Is Any-Injury-Reported", pd.Series(index=hub.index)).astype(str) == "True",
        "police": hub.get("Is Police-Reported", pd.Series(index=hub.index)).astype(str) == "True",
    }

    def row_for(quarter, miles, mask):
        sub = hub[(hub["_quarter"] == quarter) & mask]
        counts = {
            "crashes": int(len(sub)),
            "injury": int(flags["injury"][sub.index].sum()),
            "police": int(flags["police"][sub.index].sum()),
        }
        return {
            "quarter": quarter,
            "miles_millions": round(miles, 3),
            **counts,
            **{f"{k}_per_million": round(v / miles, 2) for k, v in counts.items()},
        }

    series = {"All metros": []}
    for prev, cur in zip(quarters, quarters[1:]):
        q = cur["through"]
        if prev["total_miles_millions"] and cur["total_miles_millions"]:
            miles = cur["total_miles_millions"] - prev["total_miles_millions"]
            if miles > 0:
                series["All metros"].append(row_for(q, miles, pd.Series(True, index=hub.index)))
        for code, cum in cur["metros"].items():
            before = prev["metros"].get(code)
            if before is None or code not in CITIES:
                continue
            miles = cum - before
            # Skip quarters with too few miles for a meaningful rate
            if miles < 1.0:
                continue
            series.setdefault(CITIES[code]["name"], []).append(
                row_for(q, miles, hub["Location"] == code))

    return {
        "amendment_3_quarter": quarter_end(int(SGO_AMENDMENT_3_DATE[:7].replace("-", ""))),
        "series": series,
    }


def compute_all_statistics(df_all):
    """Compute every statistic the website needs.

    df_all contains ALL crashes; headline stats use the driverless subset.
    Returns the dictionary that gets saved as site-data.json.
    """
    stats = {}

    df = df_all[df_all["operation_type"] == "driverless"].copy()
    supervised = df_all[df_all["operation_type"] == "supervised"]

    total_crashes = len(df)
    in_hub = df["in_hub"].astype(bool)

    federal_through = df_all["Year Month"].max()
    hub_through = df.loc[in_hub, "Year Month"].max()

    # Reporting completeness: the newest months are still filling in
    # (see complete_through in utils.py for the reasoning).
    submissions = df_all["Report Submission Date"].map(parse_month_label).dropna() \
        if "Report Submission Date" in df_all.columns else pd.Series(dtype=float)
    latest_submission = int(submissions.max()) if len(submissions) else None
    complete = complete_through(latest_submission)
    if complete is None or complete > federal_through:
        complete = int(federal_through)

    # -------------------------------------------------------------------
    # META
    # -------------------------------------------------------------------
    stats["meta"] = {
        "generated_at": datetime.now().isoformat(),
        "pipeline_version": "2.0",
        "total_rows_in_merged": len(df_all),
        "date_range_start": int(df["Year Month"].min()),
        "date_range_end": int(df["Year Month"].max()),
        "federal_data_through": int(federal_through),
        "federal_data_through_label": year_month_label(federal_through),
        "hub_data_through": int(hub_through),
        "hub_data_through_label": year_month_label(hub_through),
        "latest_submission_month": latest_submission,
        "federal_complete_through": int(complete),
        "federal_complete_through_label": year_month_label(complete),
        "sgo_amendment_3_date": SGO_AMENDMENT_3_DATE,
    }

    # -------------------------------------------------------------------
    # OVERVIEW
    # -------------------------------------------------------------------
    metro_codes = [c for c in df["Location"].dropna().unique() if c in CITIES]
    public_metros = [c for c in CITIES if CITIES[c]["status"] == "public"]

    preliminary = int((~in_hub).sum())
    stats["overview"] = {
        "total_crashes": total_crashes,
        "supervised_crashes": int(len(supervised)),
        "total_all_operations": int(len(df_all)),
        "preliminary_count": preliminary,
        "cities_count": len(metro_codes),
        "public_metros_count": len(public_metros),
        "cities_list": sorted(metro_display_name(c) for c in metro_codes),
    }

    # -------------------------------------------------------------------
    # CITY BREAKDOWN — every metro with driverless crashes, plus OTHER
    # -------------------------------------------------------------------
    city_counts = df["Location"].value_counts()
    city_breakdown = {}
    for code, count in city_counts.items():
        if code != OTHER_METRO_CODE and code not in CITIES:
            continue
        city_breakdown[metro_display_name(code)] = {
            "code": code,
            "count": int(count),
            "percentage": round(count / total_crashes * 100, 1),
            "status": CITIES.get(code, {}).get("status", "other"),
        }
    stats["city_breakdown"] = city_breakdown

    # -------------------------------------------------------------------
    # CITIES METADATA — read by the map at runtime (no hardcoded coords)
    # -------------------------------------------------------------------
    stats["cities"] = {
        code: {
            "name": info["name"],
            "state": info["state"],
            "lat": info["lat"],
            "lon": info["lon"],
            "status": info["status"],
            "public_since": info["public_since"],
            "launched": info.get("launched"),
            "testing": info.get("testing"),
            "count": int(city_counts.get(code, 0)),
        }
        for code, info in CITIES.items()
    }
    stats["expansion"] = ANNOUNCED_METROS

    # -------------------------------------------------------------------
    # SEVERITY INDICATORS
    # -------------------------------------------------------------------
    # Hub boolean columns only exist for hub-enriched rows, so their
    # percentages use the rows with known values as the base.
    bool_cols = {
        "Is Police-Reported": "police_reported",
        "Is Any-Injury-Reported": "injury_reported",
        "Is Any Vehicle Airbag Deployment": "airbag_any_vehicle",
        "Is Ego Vehicle Airbag Deployment": "airbag_ego_vehicle",
        "Is Suspected Serious Injury+": "serious_injury",
    }
    severity = {}
    for col, key in bool_cols.items():
        if col not in df.columns:
            continue
        known = df[col].map(
            {"True": True, "False": False, True: True, False: False}
        ).dropna()
        count = int(known.sum())
        severity[key] = {
            "count": count,
            "known_base": int(len(known)),
            "percentage": round(count / len(known) * 100, 1) if len(known) else 0,
        }

    # NHTSA's severity text field covers (nearly) every crash.
    severity_col = "Highest Injury Severity Alleged"
    moderate_plus = df[severity_col].apply(is_moderate_plus)
    severity["moderate_plus"] = {
        "count": int(moderate_plus.sum()),
        "percentage": round(moderate_plus.sum() / total_crashes * 100, 1),
    }
    fatality_mask = df[severity_col].astype(str).str.contains("Fatal", case=False, na=False)
    severity["fatality"] = {
        "count": int(fatality_mask.sum()),
        "percentage": round(fatality_mask.sum() / total_crashes * 100, 1),
    }

    # SF-specific severity (for the scrollytelling step focused on SF)
    sf_mask = df["Location"] == "SAN_FRANCISCO"
    sf_moderate_plus = df.loc[sf_mask, severity_col].apply(is_moderate_plus)
    severity["sf_moderate_plus"] = {
        "count": int(sf_moderate_plus.sum()),
        "percentage": round(sf_moderate_plus.sum() / int(sf_mask.sum()) * 100, 1) if sf_mask.sum() else 0,
    }
    stats["severity"] = severity

    # -------------------------------------------------------------------
    # CRASH TYPES — hub classification (covers hub-enriched rows)
    # -------------------------------------------------------------------
    classified = df[df["Crash Type"].notna()]
    crash_types = classified["Crash Type"].value_counts()
    stats["crash_types"] = {
        ct: {
            "count": int(count),
            "percentage": round(count / len(classified) * 100, 1),
        }
        for ct, count in crash_types.items()
    }
    stats["crash_types_meta"] = {
        "classified_count": int(len(classified)),
        "unclassified_count": int(total_crashes - len(classified)),
    }

    # -------------------------------------------------------------------
    # MONTHLY TREND — crashes per month (for the over-time chart)
    # -------------------------------------------------------------------
    monthly = df["Year Month"].dropna().astype(int).value_counts().sort_index()
    stats["monthly_trend"] = {str(ym): int(n) for ym, n in monthly.items()}
    provisional = monthly[monthly.index > complete]
    stats["monthly_trend_meta"] = {
        "complete_through": int(complete),
        "provisional_months": [str(ym) for ym in provisional.index],
        "provisional_count": int(provisional.sum()),
    }

    # -------------------------------------------------------------------
    # TEMPORAL ANALYSIS
    # -------------------------------------------------------------------
    df["_hour"], df["_minute"] = zip(*df["Incident Time (24:00)"].apply(parse_time))
    df_time = df[df["_hour"].notna()].copy()
    df_time["_hour"] = df_time["_hour"].astype(int)
    total_with_time = len(df_time)
    stats["overview"]["total_with_time_data"] = total_with_time

    df_time["_time_period"] = df_time["_hour"].apply(categorize_time_period)
    tp_counts = df_time["_time_period"].value_counts()
    stats["time_periods"] = {
        period: {
            "count": int(tp_counts.get(period, 0)),
            "percentage": round(tp_counts.get(period, 0) / total_with_time * 100, 1) if total_with_time else 0,
        }
        for period in TIME_PERIODS
    }

    rush_hour = df_time[
        ((df_time["_hour"] >= 7) & (df_time["_hour"] <= 9))
        | ((df_time["_hour"] >= 17) & (df_time["_hour"] <= 19))
    ]
    late_night = df_time[(df_time["_hour"] >= 23) | (df_time["_hour"] <= 4)]
    daytime = df_time[(df_time["_hour"] >= 6) & (df_time["_hour"] < 20)]
    nighttime = df_time[(df_time["_hour"] >= 20) | (df_time["_hour"] < 6)]

    def pct(n):
        return round(n / total_with_time * 100, 1) if total_with_time else 0

    stats["temporal"] = {
        "rush_hour_count": len(rush_hour),
        "rush_hour_percentage": pct(len(rush_hour)),
        "late_night_count": len(late_night),
        "late_night_percentage": pct(len(late_night)),
        "daytime_count": len(daytime),
        "daytime_percentage": pct(len(daytime)),
        "nighttime_count": len(nighttime),
        "nighttime_percentage": pct(len(nighttime)),
        "hourly_distribution": {
            str(h): int((df_time["_hour"] == h).sum()) for h in range(24)
        },
    }

    # -------------------------------------------------------------------
    # DAY OF WEEK — only crashes with an exact (day-precision) date
    # -------------------------------------------------------------------
    df_time["_date"] = pd.to_datetime(df_time["incident_date"], errors="coerce")
    dated = df_time[(df_time["date_precision"] == "day") & df_time["_date"].notna()].copy()
    dated["_day_of_week"] = dated["_date"].dt.day_name()
    dated["_is_weekend"] = dated["_date"].dt.dayofweek.isin([5, 6])

    if len(dated) > 0:
        dow_counts = dated["_day_of_week"].value_counts()
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        stats["day_of_week"] = {day: int(dow_counts.get(day, 0)) for day in day_order}

        weekend_count = int(dated["_is_weekend"].sum())
        stats["temporal"]["weekend_count"] = weekend_count
        stats["temporal"]["weekday_count"] = len(dated) - weekend_count
        stats["temporal"]["weekend_percentage"] = round(weekend_count / len(dated) * 100, 1)

        peak_by_day = {}
        for day in day_order:
            day_df = dated[dated["_day_of_week"] == day]
            if len(day_df) > 0:
                peak = day_df["_hour"].mode()
                if len(peak) > 0:
                    peak_by_day[day] = {"peak_hour": int(peak.iloc[0]), "total": int(len(day_df))}
        stats["temporal"]["peak_by_day"] = peak_by_day

    # -------------------------------------------------------------------
    # CITY PEAKS
    # -------------------------------------------------------------------
    city_peaks = {}
    for code in df_time["Location"].dropna().unique():
        if code not in CITIES:
            continue
        city_df = df_time[df_time["Location"] == code]
        if len(city_df) < 10:
            continue
        peak_hour = city_df["_hour"].mode()
        if len(peak_hour) == 0:
            continue
        peak_h = int(peak_hour.iloc[0])
        if peak_h == 0:
            peak_label = "Midnight"
        elif peak_h == 12:
            peak_label = "12:00 PM"
        elif peak_h < 12:
            peak_label = f"{peak_h}:00 AM"
        else:
            peak_label = f"{peak_h - 12}:00 PM"
        city_peaks[metro_display_name(code)] = {
            "peak_hour": peak_h,
            "peak_label": peak_label,
            "total_crashes": int(len(city_df)),
        }
    stats["city_peaks"] = city_peaks

    # -------------------------------------------------------------------
    # ROADWAY TYPES — NHTSA's structured field, every driverless crash
    # -------------------------------------------------------------------
    road = df["Roadway Type"].apply(roadway_type) if "Roadway Type" in df.columns \
        else pd.Series("Other/unknown", index=df.index)
    loc_counts = road.value_counts()
    stats["location_types"] = {
        lt: {
            "count": int(count),
            "percentage": round(count / total_crashes * 100, 1),
        }
        for lt, count in loc_counts.items()
    }

    # -------------------------------------------------------------------
    # CRASH CIRCUMSTANCES: speed, plain-English crash types, VRU
    # -------------------------------------------------------------------
    crash_circumstances = {}

    speeds = pd.to_numeric(df["SV Precrash Speed (MPH)"], errors="coerce").dropna()
    total_with_speed = len(speeds)
    buckets = [
        ("0_mph", speeds == 0),
        ("1_5_mph", (speeds >= 1) & (speeds <= 5)),
        ("6_15_mph", (speeds >= 6) & (speeds <= 15)),
        ("16_25_mph", (speeds >= 16) & (speeds <= 25)),
        ("26_35_mph", (speeds >= 26) & (speeds <= 35)),
        ("36_plus_mph", speeds >= 36),
    ]
    crash_circumstances["speed_distribution"] = {
        name: {
            "count": int(mask.sum()),
            "percentage": round(mask.sum() / total_with_speed * 100, 1) if total_with_speed else 0,
        }
        for name, mask in buckets
    }
    stopped_or_crawling = int((speeds <= 5).sum())
    # What the Waymo was doing: NHTSA's structured pre-crash movement field.
    movement = df["SV Pre-Crash Movement"].fillna("").astype(str).str.strip()
    known_movement = movement[(movement != "") & ~movement.str.contains("Unknown", case=False)]
    stationary = known_movement.isin(["Stopped", "Parked"])
    crash_circumstances["stationary"] = {
        "count": int(stationary.sum()),
        "known_base": int(len(known_movement)),
        "percentage": round(stationary.sum() / len(known_movement) * 100, 1) if len(known_movement) else 0,
    }

    crash_circumstances["speed_stats"] = {
        "total_with_speed_data": total_with_speed,
        "median_speed_mph": round(float(speeds.median()), 1),
        "mean_speed_mph": round(float(speeds.mean()), 1),
        "stopped_pct": round(int((speeds == 0).sum()) / total_with_speed * 100, 1) if total_with_speed else 0,
        "under_5mph_pct": round(stopped_or_crawling / total_with_speed * 100, 1) if total_with_speed else 0,
    }

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
    # Rear-end ("front-to-rear") crashes can go either way. NHTSA's contact
    # area fields say which end of the Waymo was hit.
    f2r = df[df["Crash Type"] == "V2V F2R"]
    rear_cols = [c for c in df.columns if c.startswith("SV Contact Area - Rear")]
    front_cols = [c for c in df.columns if c.startswith("SV Contact Area - Front")]
    if len(f2r) and rear_cols:
        rear_hit = (f2r[rear_cols] == "Y").any(axis=1)
        front_hit = (f2r[front_cols] == "Y").any(axis=1)
        crash_circumstances["rear_end"] = {
            "count": int(len(f2r)),
            "waymo_struck_from_behind": int((rear_hit & ~front_hit).sum()),
            "waymo_struck_from_behind_pct": round((rear_hit & ~front_hit).sum() / len(f2r) * 100, 1),
            "waymo_front_contact": int(front_hit.sum()),
        }

    crash_circumstances["crash_type_plain"] = {
        crash_type_labels.get(code, code): {
            "count": int(count),
            "percentage": round(count / len(classified) * 100, 1),
        }
        for code, count in crash_types.items()
    }

    # Vulnerable road users: hub Crash Type when classified, otherwise
    # derived from NHTSA's "Crash With" for not-yet-classified rows.
    crash_with = df["Crash With"].fillna("")
    vru_specs = {
        "pedestrian": (df["Crash Type"] == "Pedestrian")
        | (df["Crash Type"].isna() & (crash_with == "Non-Motorist: Pedestrian")),
        "cyclist": (df["Crash Type"] == "Cyclist")
        | (df["Crash Type"].isna() & (crash_with == "Non-Motorist: Cyclist")),
        "motorcycle": (df["Crash Type"] == "Motorcycle")
        | (df["Crash Type"].isna() & (crash_with == "Motorcycle")),
    }
    vru_counts = {key: int(mask.sum()) for key, mask in vru_specs.items()}
    vru_total = sum(vru_counts.values())
    crash_circumstances["vulnerable_road_users"] = {
        "total": vru_total,
        "percentage": round(vru_total / total_crashes * 100, 1),
        **vru_counts,
    }
    stats["crash_circumstances"] = crash_circumstances

    # -------------------------------------------------------------------
    # CITY MILEAGE: crash rates per million miles (where published)
    # -------------------------------------------------------------------
    if os.path.exists(STATIC_MILES_BY_CITY):
        with open(STATIC_MILES_BY_CITY, "r") as f:
            miles_data = json.load(f)

        # Rates compare like with like: only crashes up to the month the
        # mileage figures run through (CSV1 lags the federal record).
        miles_through = miles_data.get("data_through_ym") or int(hub_through)
        in_window = df[df["Year Month"] <= miles_through]
        window_counts = in_window["Location"].value_counts()
        city_mileage = {}
        for code, info in CITIES.items():
            display_name = info["name"]
            crash_count = int(window_counts.get(code, 0))
            miles_entry = miles_data.get("cities", {}).get(display_name, {})
            miles_millions = miles_entry.get("miles_millions")
            rate = round(crash_count / miles_millions, 1) if miles_millions else None
            city_mileage[display_name] = {
                "miles_millions": miles_millions,
                "crashes_in_window": crash_count,
                "crashes_per_million_miles": rate,
            }
        stats["city_mileage"] = city_mileage
        stats["city_mileage_meta"] = {
            "data_through": miles_data.get("data_through"),
            "data_through_ym": miles_through,
            "source_url": miles_data.get("source_url"),
        }
    else:
        print(f"  WARNING: {STATIC_MILES_BY_CITY} not found — skipping city mileage stats")

    # -------------------------------------------------------------------
    # WAYMO PUBLISHED SAFETY CONTEXT
    # -------------------------------------------------------------------
    waymo_context = dict(WAYMO_PUBLISHED_STATS)
    if os.path.exists(STATIC_MILES_BY_CITY):
        with open(STATIC_MILES_BY_CITY, "r") as f:
            miles_for_context = json.load(f)
        total_millions = miles_for_context.get("total_miles_millions")
        if total_millions is not None:
            waymo_context["total_rider_only_miles"] = int(total_millions * 1_000_000)
        waymo_context["data_through"] = miles_for_context.get("data_through")

    # Waymo's comparisons against human drivers, straight from hub CSV3
    if os.path.exists(RAW_WAYMO_CSV3):
        csv3 = pd.read_csv(RAW_WAYMO_CSV3)
        bench = benchmark_summary(csv3, BENCHMARK_OUTCOMES)
        bench["by_metro"] = {
            CITIES[code]["name"]: rows for code, rows in bench["by_metro"].items()
        }
        stats["benchmarks"] = bench
        overall = bench["overall"]
        # Flat keys kept for simple data-stat bindings
        for key, flat in [("serious_injury", "serious_crash_reduction_pct"),
                          ("any_injury", "injury_crash_reduction_pct"),
                          ("airbag", "airbag_crash_reduction_pct")]:
            if key in overall:
                waymo_context[flat] = overall[key]["reduction_pct"]
        print("  Benchmarks (CSV3): " + ", ".join(
            f"{k} −{v['reduction_pct']}% [{v['reduction_ci_low']}–{v['reduction_ci_high']}]"
            for k, v in overall.items()))
    else:
        print(f"  WARNING: {RAW_WAYMO_CSV3} not found — skipping benchmark comparisons")
    stats["waymo_context"] = waymo_context

    # -------------------------------------------------------------------
    # QUARTERLY RATES — hub crashes per million rider-only miles
    # -------------------------------------------------------------------
    # Miles per quarter = difference between consecutive cumulative CSV1
    # releases. Crashes = hub-matched driverless crashes in that quarter
    # (the hub and CSV1 cover the same rider-only operations). Quarters
    # where a metro's mileage is missing from either release are skipped.
    stats["quarterly_rates"] = compute_quarterly_rates(df)

    # -------------------------------------------------------------------
    # MILEAGE SERIES — hand-sourced milestones + every hub CSV1 release
    # -------------------------------------------------------------------
    stats["mileage_series"] = compute_mileage_series()

    # -------------------------------------------------------------------
    # FATAL CRASHES — listed individually (facts only; prose is editorial)
    # -------------------------------------------------------------------
    stats["fatal_crashes"] = [
        {
            "report_id": row["Report ID"],
            "year_month": int(row["Year Month"]),
            "month_label": year_month_label(row["Year Month"]),
            "metro": metro_display_name(row["Location"]),
            "city": row.get("City") or None,
            "sv_movement": row.get("SV Pre-Crash Movement") if pd.notna(row.get("SV Pre-Crash Movement")) else None,
            "speed_mph": float(row["SV Precrash Speed (MPH)"]) if pd.notna(row.get("SV Precrash Speed (MPH)")) else None,
            "crash_with": row.get("Crash With") if pd.notna(row.get("Crash With")) else None,
        }
        for _, row in df[fatality_mask].sort_values("Year Month").iterrows()
    ]

    return stats


def update_history(stats):
    """Append an entry to update_history.json when the data changed.

    A public, machine-readable record of what each automatic update added
    (shown on the methodology page). An entry is only added when the crash
    count or a data-through date differs from the previous entry, so
    re-running the pipeline on unchanged data is a no-op.
    """
    history = []
    if os.path.exists(WEB_UPDATE_HISTORY):
        with open(WEB_UPDATE_HISTORY) as f:
            history = json.load(f)
    entry = {
        "date": datetime.now().date().isoformat(),
        "total_crashes": stats["overview"]["total_crashes"],
        "supervised_crashes": stats["overview"]["supervised_crashes"],
        "federal_data_through": stats["meta"]["federal_data_through"],
        "hub_data_through": stats["meta"]["hub_data_through"],
        "fatal_crashes": len(stats.get("fatal_crashes", [])),
        "moderate_plus": stats["severity"]["moderate_plus"]["count"],
    }
    key = ("total_crashes", "federal_data_through", "hub_data_through")
    if history and all(history[-1].get(k) == entry[k] for k in key):
        print("  No change since last entry")
        return
    if history:
        entry["new_crashes"] = entry["total_crashes"] - history[-1]["total_crashes"]
    history.append(entry)
    with open(WEB_UPDATE_HISTORY, "w") as f:
        json.dump(history[-104:], f, indent=2)  # two years of weekly runs
        f.write("\n")
    print(f"  Added entry: {entry}")


def main():
    """Compute all statistics and save site-data.json."""
    print("=" * 60)
    print("STEP 3: COMPUTING STATISTICS")
    print("=" * 60)
    print()

    print("Loading merged dataset...")
    df_all = pd.read_csv(PROCESSED_MERGED, low_memory=False)
    print(f"  Loaded {len(df_all)} rows")

    print()
    print("Computing statistics...")
    stats = compute_all_statistics(df_all)

    print()
    print("Updating update_history.json...")
    update_history(stats)

    print()
    print("Saving site-data.json...")
    os.makedirs(os.path.dirname(WEB_SITE_DATA), exist_ok=True)
    with open(WEB_SITE_DATA, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Saved: {WEB_SITE_DATA}")

    print()
    print("Key statistics:")
    overview = stats["overview"]
    print(f"  Driverless crashes:   {overview['total_crashes']}")
    print(f"  Supervised crashes:   {overview['supervised_crashes']}")
    print(f"  Preliminary (no hub): {overview['preliminary_count']}")
    print(f"  Metros with crashes:  {overview['cities_count']}")
    print(f"  Federal data through: {stats['meta']['federal_data_through_label']}")
    print(f"  Hub data through:     {stats['meta']['hub_data_through_label']}")
    for city, data in list(stats["city_breakdown"].items())[:8]:
        print(f"  {city}: {data['count']} crashes ({data['percentage']}%)")


if __name__ == "__main__":
    main()
