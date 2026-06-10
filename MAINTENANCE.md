# Maintenance Guide

How to keep this website current. (Rewritten June 2026 for the
NHTSA-based pipeline.)

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

## What Requires Manual Updates

### 1. New metro areas (the main one)

**File:** `pipeline/config.py` → `CITIES` dict

When Waymo starts driverless operation in a new metro, add one entry with:
`name`, `state`, `lat`/`lon` (city center), `status` ("public" or
"testing"), `public_since`, `counties` (as they appear in Waymo's CSV2),
and `cities` (suburb names as they appear in NHTSA's City column).

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
announces markets. Current list reflects June 2026.

### 3. Mileage milestones (manual data file)

**File:** `data/static/mileage_milestones.json`

Powers the "Rider-Only Miles Over Time" line chart. Waymo doesn't publish
a historical time series — add new entries when Waymo announces mileage
milestones (press releases, Safety Impact Data Hub).

### 4. Waymo published safety comparisons

**File:** `pipeline/config.py` → `WAYMO_PUBLISHED_STATS`

The "92% fewer serious crashes" figures come from Waymo's peer-reviewed
research. Update if Waymo publishes revised figures.

### 5. Editorial review triggers

- **A new fatality** — `faq.html` ("How serious are these crashes?")
  states that in both fatalities to date the Waymo was stopped/slowing
  and not at fault. A third fatality requires rewriting that sentence.
  There is an HTML comment flagging this.
- **A new recall or federal investigation** — add it to the FAQ item
  "Has Waymo been investigated or recalled?" (currently covers the
  Dec 2025 school-bus recall, the Jan 2026 PE26001 school-zone probe,
  and the May 2026 floodwater recall).
- **The 11-metro list** — hardcoded in prose in `about.html` and the
  FAQ's "In which cities does Waymo operate?" answer (the crash-count
  list below it is dynamic). Update when new markets open.
- **Per-city mileage list** — `faq.html` and `methodology.html` note that
  Waymo publishes mileage for only four markets; update when that changes.

## How to Run the Pipeline Manually

```bash
make data          # full pipeline (download + process)

# Or step by step
python pipeline/01_download_data.py
python pipeline/02_merge_and_clean.py
python pipeline/03_compute_statistics.py
python pipeline/04_generate_map_data.py
python pipeline/05_generate_incidents.py

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
- **Location precision tiers** on every map record: `street` (hub address
  geocoded), `city` (NHTSA-only rows — city centroid + jitter), `metro`
  (fallback). NHTSA-only rows also have month-precision dates
  (`date_precision == "month"`).
- Shared pipeline helpers live in `pipeline/utils.py` (pure functions,
  unit-tested). All configuration lives in `pipeline/config.py`.
- The site is served from the project root; on GitHub Pages,
  `deploy-pages.yml` copies `data/web/` and `data/static/` into `_site/`.
  `data-loader.js` detects the environment and adjusts paths.
- Geocode cache (`data/web/geocode_cache.json`) is committed to git.
  Street addresses cache as `"<address>|<METRO_CODE>"`; city centroids as
  `"__city__<City>|<ST>"`. Delete an entry to force a re-geocode.
