# Maintenance Guide

How to keep this website current after the initial launch.

## What Updates Automatically

When the GitHub Actions pipeline runs (quarterly on the 17th of Mar/Jun/Sep/Dec), these update with no manual work:

- **NHTSA crash data** — both pre- and post-June 2025 files are re-downloaded
- **All statistics** — total counts, city breakdowns, severity, timing, speed, crash types
- **All `data-stat` bindings** — every number on the website that uses `data-stat` attributes
- **Charts** — Chart.js reads from `site-data.json` at runtime, no hardcoded limits
- **Map markers** — crash dots, clusters, serious incident markers all regenerate
- **Geocoding** — new addresses are geocoded via Nominatim; existing ones use cache
- **Date range** — "Sept 2020 through Sept 2025" updates from the data automatically

## What Requires Manual Updates

### 1. Waymo Hub CSV2 URL (CRITICAL — most likely failure point)

**File:** `pipeline/config.py` → `WAYMO_HUB_URL`

The Waymo Hub CSV2 filename includes a date range (e.g., `202009-202509`). When Waymo publishes new data, this range changes and the old URL returns a 404.

**How to fix:**
1. Go to https://waymo.com/safety/impact/
2. Find the "Download the data" section
3. Right-click the CSV2 download link → Copy link address
4. Update `WAYMO_HUB_URL` in `pipeline/config.py`

The pipeline has error handling that prints a clear message when this fails, so it will be obvious what happened.

### 2. Mileage milestones (manual data file)

**File:** `data/static/mileage_milestones.json`

This powers the "Rider-Only Miles Over Time" line chart. Waymo doesn't publish a historical time series — each data point was individually sourced from press releases and archived web data.

**How to update:** Add new entries when Waymo announces mileage milestones (check press releases and the Safety Impact Data Hub).

### 3. Miles by city (manual data file)

**File:** `data/static/miles_by_city.json`

Per-city mileage from Waymo's Safety Impact Data Hub. Updated quarterly when Waymo publishes new figures.

**How to update:**
1. Go to https://waymo.com/safety/impact/
2. Check the miles-by-city breakdown
3. Update `data/static/miles_by_city.json` with new values

### 4. Waymo published safety comparisons

**File:** `pipeline/config.py` → `WAYMO_PUBLISHED_STATS`

The "90% fewer serious crashes" and similar comparison stats come from Waymo's peer-reviewed research. If Waymo publishes updated figures (e.g., based on more miles), update the values in `WAYMO_PUBLISHED_STATS`.

### 5. New cities

**File:** `pipeline/config.py` → `CITIES` dict

If Waymo expands to a new city (e.g., Miami, launched Jan 2026), crashes from that city will appear in the total count and on the map, but won't show up in the city breakdown section unless added to the `CITIES` dict.

**How to add a city:**
1. Add the city to `CITIES` in `config.py` with its code, name, state, and center coordinates
2. Add it to `CITY_COORDS` in `site/js/map-controller.js`
3. Add a city mileage entry in `data/static/miles_by_city.json` (if mileage is published)
4. The FAQ city list will need manual updating (it's hardcoded in `faq.html` line 140-148)

### 6. Fatality description in FAQ

**File:** `site/faq.html` — "How serious are these crashes?" section

The fatality description currently says: "In both cases, the Waymo vehicle was stopped or slowing when another party caused the collision." If a future fatality has different circumstances, this sentence needs editorial review. There is an HTML comment flagging this.

## Remaining Hardcoded Text (Acceptable)

These are hardcoded but intentionally so — they are historical facts or editorial statements that don't change with new data:

- **faq.html:** "In the earliest years of the dataset (2020-2022), only 9 crashes were reported" — historical fact
- **faq.html:** "2023 when Waymo launched fully public, rider-only service in San Francisco" — historical fact
- **faq.html:** "San Francisco has the most crashes because Waymo has operated there the longest" — currently true; would need editorial review if LA overtakes SF
- **about.html:** "San Francisco, Phoenix, Los Angeles, Austin, and Atlanta" city list — narrative context, update if new cities are added
- **index.html:** "from 1 million rider-only miles in January 2023" — historical anchor, won't change
- **faq.html:** "Atlanta — mileage not yet published by Waymo" — update when Waymo publishes Atlanta mileage

## How to Run the Pipeline Manually

```bash
# Full pipeline (download + process)
make data

# Or step by step
cd pipeline
python 01_download_data.py
python 02_merge_and_clean.py
python 03_compute_statistics.py
python 04_generate_map_data.py
python 05_generate_incidents.py

# View the site
make serve
# Open http://localhost:8000/site/index.html
```

## How to Trigger a Manual Update on GitHub

1. Go to the repository's **Actions** tab
2. Select **"Update Crash Data"** workflow
3. Click **"Run workflow"** → **"Run workflow"**
4. The deploy workflow will trigger automatically after the data update completes

## Architecture Notes

- The site is served from the **project root** (not `site/`), so `../data/web/` paths resolve correctly in local dev
- On GitHub Pages, `deploy-pages.yml` copies `data/web/` and `data/static/` into `_site/` alongside the site files
- `data-loader.js` detects the environment via `window.location.hostname.includes("github.io")` and adjusts paths
- Geocode cache (`data/web/geocode_cache.json`) is committed to git — reused across runs to avoid re-querying Nominatim
