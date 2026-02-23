"""
01_download_data.py — Download raw crash data from NHTSA and Waymo
==========================================================================
Downloads three CSV files:
  1. NHTSA ADS crashes AFTER June 16, 2025 (Amendment 3 format)
  2. NHTSA ADS crashes BEFORE June 16, 2025 (Amendment 2 format, archived)
  3. Waymo Safety Impact Data Hub CSV2 (Waymo's curated crash list)

These get saved into data/raw/ and are the starting point for the pipeline.

Usage:
  python pipeline/01_download_data.py
==========================================================================
"""

import os
import sys
import requests

# Add the project root to Python's path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    NHTSA_POST_URL, NHTSA_PRIOR_URL, WAYMO_HUB_URL,
    RAW_NHTSA_POST, RAW_NHTSA_PRIOR, RAW_WAYMO_HUB, RAW_DIR,
)


def download_file(url, output_path, description):
    """
    Download a file from a URL and save it locally.

    Parameters:
        url (str): The web address to download from
        output_path (str): Where to save the downloaded file
        description (str): Human-readable name for logging (e.g., "NHTSA Post")
    """
    print(f"  Downloading {description}...")
    print(f"    URL: {url}")

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Download the file (timeout after 120 seconds if the server doesn't respond)
    response = requests.get(url, timeout=120)

    # If the download failed (e.g., 404 Not Found), raise an error
    response.raise_for_status()

    # Save the downloaded content to disk
    with open(output_path, "wb") as f:
        f.write(response.content)

    # Show the file size so we can tell if something looks wrong
    size_mb = len(response.content) / (1024 * 1024)
    print(f"    Saved: {output_path} ({size_mb:.1f} MB)")


def main():
    """Download all three raw data files."""
    print("=" * 60)
    print("STEP 1: DOWNLOADING RAW DATA")
    print("=" * 60)
    print()

    # List of (URL, save path, description) for each file to download
    downloads = [
        (NHTSA_POST_URL,  RAW_NHTSA_POST,  "NHTSA ADS — post June 16, 2025 (Amendment 3)"),
        (NHTSA_PRIOR_URL, RAW_NHTSA_PRIOR, "NHTSA ADS — prior to June 16, 2025 (Amendment 2)"),
        (WAYMO_HUB_URL,   RAW_WAYMO_HUB,   "Waymo Safety Impact Data Hub (CSV2)"),
    ]

    for url, path, desc in downloads:
        try:
            download_file(url, path, desc)
            print()
        except requests.exceptions.HTTPError as e:
            print(f"\n    ERROR: Download failed for {desc}")
            print(f"    HTTP status: {e.response.status_code}")
            print()
            if "waymo" in url.lower():
                print("    The Waymo Hub URL may have changed (it updates quarterly).")
                print("    Go to https://waymo.com/safety/impact/ and find the new CSV2 link.")
                print("    Then update WAYMO_HUB_URL in pipeline/config.py")
            else:
                print("    Check if the NHTSA URL has changed at:")
                print("    https://www.nhtsa.gov/automated-vehicles/automated-driving-systems")
            print()
            raise
        except requests.exceptions.ConnectionError:
            print(f"\n    ERROR: Could not connect to download {desc}")
            print("    Check your internet connection and try again.")
            raise

    print("All downloads complete!")
    print(f"Files saved in: {RAW_DIR}")


if __name__ == "__main__":
    main()
