# Maintenance Guide

How to keep this website current. (Rewritten June 2026 for the
NHTSA-based pipeline; updated October 2026 — see OVERHAUL_LOG_2026-10.md.)

## What Updates Automatically

The GitHub Actions pipeline runs **every Monday at 10:00 UTC** and handles:

- **NHTSA crash data** — both pre- and post-June-2025 files re-downloaded;
  new crashes appear on the site within a week of NHTSA publishing them
- **Waymo quarterly releases (CSV1 + CSV2)** — URLs auto-detected by
  probing recent quarter end-dates; when a new release lands (~Mar/Jun/
  Sep/Dec 15), recent crashes automatically gain exact dates, street-level
  geocoded locations, and crash-type classifications
- **Miles by city** — regenerated from Waymo CSV1 into
  `data/static/miles_by_city.json`
- **All statistics, charts, map markers, and `data-stat` bindings** —
  every number on the site regenerates from the data
- **Data-freshness labels** — "federal data through X / hub data through Y"
- **Geocoding** — new addresses geocoded via Nominatim; existing ones cached
- **Quality gates** — unit tests run before the pipeline, and generated
  JSON is validated (counts must not shrink) before anything is committed

If a run commits changes, the deploy workflow publishes the site
automatically.

- **Waymo benchmarks (CSV3)** — the "fewer crashes than human drivers"
  figures and confidence intervals, overall and per metro
- **Mileage history** — every hosted CSV1 release is downloaded into
  `data/static/miles_quarterly.json`; the mileage chart and quarterly
  rate charts extend themselves each quarter
- **Reporting completeness** — the latest two incident months are marked
  provisional using NHTSA's report submission dates
- **Public outputs** — `data/web/waymo_crashes.csv` and
  `data/web/update_history.json`
- **Editorial alerts** — see below

## Editorial review (the GitHub issue)

Some text can't be generated from data. Step 06
(`pipeline/06_editorial_checks.py`) compares each run with
`data/static/editorial_baseline.json` and, when something needs a person,
the workflow opens or updates an issue labelled **editorial-alert**:

- **New fatal crash (HIGH)** — summarize it in two places: the fatal-crash
  list in `site/index.html` (`#fatal-list`) and in `site/faq.html` ("How
  serious are these crashes?"). Each `<li>` carries `data-report-id`.
  Until you do, the pages append a neutral "newly reported, details under
  review" line automatically, so the count is never wrong. Check police
  and news reports before writing anything about fault.
- **New moderate/serious-injury crashes** — skim the narratives.
- **Unmapped places / driverless crashes in a "testing" metro** — update
  `CITIES` (below).
- **New Waymo hub release** — read the release notes PDF linked from
  waymo.com/safety/impact for methodology changes.

When done: `python pipeline/06_editorial_checks.py --accept`, commit
`data/static/editorial_baseline.json`, close the issue.

## What Requires Manual Updates

### 1. New metro areas (the main one)

**File:** `pipeline/config.py` → `CITIES` dict

When Waymo starts driverless operation in a new metro, add one entry with:
`name`, `state`, `lat`/`lon` (city center), `status` ("public" or
"testing"), for testing metros `testing` ("driverless" or "supervised"),
`public_since` (year), `launched` ("YYYY-MM"), `counties` (as they appear
in Waymo's CSV2), and `cities` (suburb names as in NHTSA's City column).
If the metro is in a new state, also add the state's ZIP prefixes to
`pipeline/tools/build_zip_reference.py` and re-run it.

If Waymo's CSV1/CSV3 start naming a new aggregate service area (like
"Atlanta Area"), add it to `CSV1_AGGREGATES` in `config.py` — the
pipeline log warns about unrecognized CSV1 locations.

**Until you do this, nothing breaks**: crashes from unmapped places stay
in the totals and on the map under an "Other" bucket, and the pipeline
log prints a warning listing the unmapped city names (also saved to
`data/processed/waymo_unmapped_cities.csv`). Check the Actions log
occasionally, or after Waymo announces a launch.

Also promote metros from `"testing"` to `"public"` (with `public_since`)
when service opens, and move announced metros from `ANNOUNCED_METROS`
into `CITIES` once they have crashes on record.

### 2. Announced ("coming soon") metros

**File:** `pipeline/config.py` → `ANNOUNCED_METROS`

Powers the hollow circles on the intro map. Add/remove entries as Waymo
announces markets; only list announcements you can source. Current list
reflects October 2026.

### 3. Mileage milestones (manual data file)

**File:** `data/static/mileage_milestones.json`

Optional. The mileage chart merges these hand-sourced points (press
releases, papers) with every hub release automatically. Add a point only
for a Waymo announcement with a clear as-of date — don't add hub figures
here (they come in automatically).

### 4. Waymo published safety comparisons

Automatic since October 2026 (hub CSV3). If Waymo renames a CSV3
outcome or benchmark label, update `BENCHMARK_OUTCOMES` in `config.py`.
The IIHS study cited on the home page, methodology and FAQ is hand-written
— update it if a newer independent study appears.

### 5. Hand-written facts to re-check periodically

- **Fatal crashes** — handled by the editorial alert (above).
- **Recalls and investigations** — `faq.html` "Has Waymo been investigated
  or recalled?" (as of Oct 2026: school-bus recall + PE25013 + NTSB;
  PE26001 Santa Monica; floodwater recall; work-zone recall 26E-035).
- **City list in prose** — `faq.html` "In which cities does Waymo
  operate?" and `about.html` name the metros and testing cities; the
  counts and per-metro lists are dynamic.
- **Reporting thresholds** — described in `methodology.html`, `faq.html`
  and `index.html` (safety section). Update if NHTSA amends the order again
  (trend charts mark only `SGO_AMENDMENT_3_DATE` in
  `config.py`; a new amendment needs its own marker).

## How to Run the Pipeline Manually

```bash
make data          # full pipeline (download + process)

# Or step by step
python pipeline/01_download_data.py
python pipeline/02_merge_and_clean.py
python pipeline/03_compute_statistics.py
python pipeline/04_generate_map_data.py
python pipeline/05_generate_incidents.py
python pipeline/06_editorial_checks.py

make serve         # http://localhost:8000/site/index.html
```

Run the tests with `python -m pytest tests/ -q`.

## How to Trigger a Manual Update on GitHub

1. Repository **Actions** tab → **"Update Crash Data"** → **Run workflow**
2. The deploy workflow triggers automatically after a successful update

## Architecture Notes

- **Merge direction:** NHTSA is the base record (complete, weekly-fresh);
  Waymo's hub CSV2 is enrichment (exact dates, addresses, crash types).
  Never invert this — the old hub-based merge silently dropped months of
  recent crashes.
- **Operation split:** headline stats = driverless only
  (`operation_type == "driverless"`); supervised-testing crashes are in
  the data with a toggle in Explore.
- **Location precision tiers** on every map record: `street` (hub
  intersection/address geocoded), `road` (one of two streets matched),
  `zip` (placed at the reported ZIP's centre after the address couldn't be
  placed inside it), `city` (NHTSA-only rows — city centroid + jitter),
  `metro` (fallback). Geocodes for crashes with a hub ZIP (through June
  2025) are checked against Census ZIP areas
  (`data/static/zip_reference.json`). NHTSA-only rows also have
  month-precision dates (`date_precision == "month"`).
- **Basemap:** OpenFreeMap (no key) via MapLibre GL, in `site/js/basemap.js`.
  CARTO's free tiles started requiring a key in 2026 and broke every map.
- Shared pipeline helpers live in `pipeline/utils.py` (pure functions,
  unit-tested). All configuration lives in `pipeline/config.py`.
- The site is served from the project root; on GitHub Pages,
  `deploy-pages.yml` copies `data/web/` and `data/static/` into `_site/`.
  `data-loader.js` detects the environment and adjusts paths.
- Geocode cache (`data/web/geocode_cache.json`) is committed to git.
  Street addresses cache as `"v3|<address>|<City>|<ST>|<ZIP>"` (ZIP-checked)
  or `"v2|<address>|<City>|<ST>"`; city centroids as `"__city__<City>|<ST>"`.
  Delete an entry to force a re-geocode.
