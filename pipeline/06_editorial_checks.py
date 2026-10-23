"""
06_editorial_checks.py — Flag data changes that need a human editor
==========================================================================
Some sentences on the site can't be generated from data — e.g. the
FAQ's summary of every fatal crash. This step compares the freshly built
dataset against data/static/editorial_baseline.json (what a person has
already reviewed) and writes data/processed/editorial_alerts.md listing
anything new: fatal or serious-injury crashes, unmapped places, crashes in
metros not yet marked public, and new Waymo hub releases.

The weekly GitHub Action opens (or updates) an issue labelled
"editorial-alert" whenever the alerts file is non-empty. Nothing is
blocked — the data still publishes; the issue makes sure someone looks.

After reviewing (and updating the prose), accept the current state:
  python pipeline/06_editorial_checks.py --accept

Usage:
  python pipeline/06_editorial_checks.py
==========================================================================
"""

import json
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    PROCESSED_MERGED, WEB_SITE_DATA, STATIC_EDITORIAL_BASELINE, EDITORIAL_ALERTS,
    CITIES, OTHER_METRO_CODE,
)
from pipeline.utils import editorial_alerts, is_moderate_plus


def build_snapshot():
    """Summarize the current dataset for the editorial comparison."""
    df = pd.read_csv(PROCESSED_MERGED, low_memory=False)
    with open(WEB_SITE_DATA) as f:
        stats = json.load(f)
    df = df[df["operation_type"] == "driverless"]
    severity = df["Highest Injury Severity Alleged"]

    def summarize(rows):
        return [{
            "report_id": r["Report ID"],
            "month_label": f"{int(r['Year Month']) // 100}-{int(r['Year Month']) % 100:02d}",
            "city": r["City"] if pd.notna(r.get("City")) and r.get("City") else r.get("Location"),
            "severity": r["Highest Injury Severity Alleged"],
        } for _, r in rows.iterrows() if pd.notna(r["Report ID"])]

    unmapped = df[df["Location"] == OTHER_METRO_CODE]
    unmapped = unmapped.apply(lambda r: f"{r.get('City')}, {r.get('State')}", axis=1).value_counts()
    testing = df[df["Location"].map(lambda c: CITIES.get(c, {}).get("status") == "testing")]
    return {
        "fatal": stats.get("fatal_crashes", []),
        "moderate_plus": summarize(df[severity.apply(is_moderate_plus)]),
        "hub_data_through": stats["meta"]["hub_data_through"],
        "unmapped": {k: int(v) for k, v in unmapped.items()},
        "testing_metro_crashes": {CITIES[c]["name"]: int(n) for c, n in testing["Location"].value_counts().items()},
    }


def main():
    print("=" * 60)
    print("STEP 6: EDITORIAL CHECKS")
    print("=" * 60)
    snapshot = build_snapshot()

    if "--accept" in sys.argv:
        baseline = {
            "reviewed_on": date.today().isoformat(),
            "fatal_report_ids": [c["report_id"] for c in snapshot["fatal"]],
            "moderate_plus_report_ids": [c["report_id"] for c in snapshot["moderate_plus"]],
            "hub_data_through": snapshot["hub_data_through"],
        }
        with open(STATIC_EDITORIAL_BASELINE, "w") as f:
            json.dump(baseline, f, indent=2)
            f.write("\n")
        print(f"  Baseline accepted: {len(baseline['fatal_report_ids'])} fatal, "
              f"{len(baseline['moderate_plus_report_ids'])} moderate+ crashes, "
              f"hub through {baseline['hub_data_through']}")
        return

    baseline = {}
    if os.path.exists(STATIC_EDITORIAL_BASELINE):
        with open(STATIC_EDITORIAL_BASELINE) as f:
            baseline = json.load(f)
    alerts = editorial_alerts(snapshot, baseline)

    os.makedirs(os.path.dirname(EDITORIAL_ALERTS), exist_ok=True)
    with open(EDITORIAL_ALERTS, "w") as f:
        if alerts:
            f.write("The weekly data update found changes that need an editor's eye. "
                    "The data itself has already been published.\n\n")
            for priority, title, lines in alerts:
                f.write(f"### [{priority}] {title}\n\n")
                f.writelines(f"- {line}\n" for line in lines)
                f.write("\n")
            f.write("When done, run `python pipeline/06_editorial_checks.py --accept`, "
                    "commit `data/static/editorial_baseline.json`, and close this issue. "
                    "See MAINTENANCE.md → Editorial review.\n")
    if alerts:
        for priority, title, _ in alerts:
            print(f"  ALERT [{priority}] {title}")
        print(f"  Written: {EDITORIAL_ALERTS}")
    else:
        print("  No editorial alerts.")


if __name__ == "__main__":
    main()
