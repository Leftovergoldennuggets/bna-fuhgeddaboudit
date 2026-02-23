"""
run_pipeline.py — Run the complete data pipeline from start to finish
==========================================================================
This is the master script that runs all pipeline steps in order:
  1. Download raw data from NHTSA and Waymo
  2. Merge and clean the datasets
  3. Compute all statistics for the website
  4. Generate map data (crash_data.json)
  5. Extract serious incidents (serious_incidents.json)

Usage:
  python pipeline/run_pipeline.py           # Run all steps
  python pipeline/run_pipeline.py --skip-download   # Skip downloading (use existing raw data)

After running, the website's data files will be in data/web/:
  - site-data.json         (all statistics)
  - crash_data.json        (map markers)
  - serious_incidents.json (serious injury incidents)
==========================================================================
"""

import subprocess
import sys
import os
import time

# List of pipeline steps: (script filename, description)
STEPS = [
    ("01_download_data.py",       "Downloading raw data from NHTSA + Waymo"),
    ("02_merge_and_clean.py",     "Merging and cleaning datasets"),
    ("03_compute_statistics.py",  "Computing all statistics for the website"),
    ("04_generate_map_data.py",   "Generating map data (crash_data.json)"),
    ("05_generate_incidents.py",  "Extracting serious incidents"),
]


def main():
    """Run all pipeline steps in sequence."""
    # Check for --skip-download flag
    skip_download = "--skip-download" in sys.argv

    # Get the directory where this script lives (pipeline/)
    pipeline_dir = os.path.dirname(os.path.abspath(__file__))

    print()
    print("=" * 60)
    print("WAYMO CRASH DATA PIPELINE")
    print("=" * 60)
    print()

    start_time = time.time()
    steps_run = 0

    for script, description in STEPS:
        # Skip download step if requested
        if skip_download and script == "01_download_data.py":
            print(f"SKIPPING: {description} (--skip-download flag)")
            print()
            continue

        script_path = os.path.join(pipeline_dir, script)
        print(f"RUNNING: {description}")
        print(f"  Script: {script}")
        print()

        # Run the script as a subprocess
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=os.path.dirname(pipeline_dir),  # Run from project root
        )

        # Stop if any step fails
        if result.returncode != 0:
            print()
            print(f"PIPELINE FAILED at step: {script}")
            print(f"Exit code: {result.returncode}")
            print("Fix the error above and re-run the pipeline.")
            sys.exit(1)

        steps_run += 1
        print()

    # Done!
    elapsed = time.time() - start_time
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Steps run: {steps_run}")
    print(f"  Time: {elapsed:.1f} seconds")
    print()
    print("Output files in data/web/:")
    web_dir = os.path.join(os.path.dirname(pipeline_dir), "data", "web")
    if os.path.exists(web_dir):
        for f in sorted(os.listdir(web_dir)):
            if f.startswith("."):
                continue
            size = os.path.getsize(os.path.join(web_dir, f))
            print(f"  {f} ({size / 1024:.0f} KB)")
    print()
    print("To view the website locally, run:")
    print("  make serve")
    print("  (then open http://localhost:8000)")


if __name__ == "__main__":
    main()
