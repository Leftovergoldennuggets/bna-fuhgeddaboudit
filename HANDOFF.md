# HANDOFF — Waymo site overhaul (paused 2026-06-09)

Work-in-progress state for the June 2026 overhaul. Everything below is
committed on the branch **`waymo-overhaul-2026-06`**. Delete this file when
the overhaul ships.

## Why this overhaul

1. **The site was silently stale.** The old pipeline used Waymo's quarterly
   hub CSV2 as the merge base, so every NHTSA crash newer than the hub's
   last release (Dec 2025) was dropped. 226 crashes from Jan–Apr 2026 —
   including crashes in 7 brand-new metros — never appeared. The GitHub
   Action was NOT broken; it ran green every 2 weeks but had nothing new to
   say. (Local repo was also 4 commits behind origin — that's why it looked
   broken.)
2. **Waymo grew from 5 to 11 public metros** (added: Miami, Dallas, Houston,
   San Antonio, Orlando, Nashville) plus testing in DC, Denver, Philadelphia,
   and 16 announced markets. None of that was on the site.

## What's DONE (committed on this branch, all tests green)

### Pipeline (complete, verified end-to-end with fresh data)
- `pipeline/config.py` — rewritten. `CITIES` is now a metro registry with
  counties (for hub data), city lists (for NHTSA data), status
  (public/testing), launch year. Added `ANNOUNCED_METROS` (16 coming-soon
  metros), `SUPERVISED_OPERATOR_TYPES`, `REQUIRED_*_COLUMNS` for validation.
- `pipeline/utils.py` — NEW. All shared pure helpers: state normalization
  ("Arizona"→"AZ" — hub uses full names, NHTSA postal codes!), metro
  resolution (county first, then city, then core-city fallback), operation
  classification (blank operator = driverless; "Remote" = driverless;
  in-vehicle/unknown = supervised), date parsing with precision ("MAR-2026"
  → month precision; NHTSA redacts exact dates), severity levels.
- `pipeline/02_merge_and_clean.py` — rewritten. **NHTSA is now the base,
  hub is enrichment** (left join NHTSA←hub + 2 appended hub-only pre-SGO
  rows). Adds unified columns: `operation_type`, `in_hub`, `record_source`,
  `incident_date`, `date_precision`, `Year Month`, `Location` (metro code),
  `metro_mapped`. Unmapped places land in an `OTHER` bucket with loud
  warnings — nothing is silently dropped. Validates columns up front.
- `pipeline/03_compute_statistics.py` — rewritten. Headline = driverless
  only (1,602 as of Jun 9). New outputs: `monthly_trend`, `cities` metadata
  block (coords/status for the map — frontend no longer hardcodes),
  `expansion` list, `meta.federal_data_through(_label)` +
  `meta.hub_data_through(_label)`, `overview.supervised_crashes`,
  `overview.preliminary_count`, `crash_types_meta`, speed
  `stopped_pct`/`under_5mph_pct`. Severity booleans now use known-value
  bases. Matplotlib/seaborn figure generation DELETED (PNGs were never
  referenced by any page; deps removed from requirements).
- `pipeline/04_generate_map_data.py` — rewritten. Maps ALL 1,839 crashes
  (incl. supervised + no-time rows). Three location tiers flagged per
  record: `street` (hub address geocoded), `city` (NHTSA-only rows —
  city centroid + jitter), `metro` (fallback). New record fields:
  `operation_type`, `in_hub`, `location_precision`, `date_precision`,
  `city_name`, month-precision dates as "YYYY-MM".
- `pipeline/05_generate_incidents.py` — rewritten for new schema;
  driverless-only; precision-aware date formatting. 17 serious incidents
  (was 15), still exactly 2 fatalities (Jan 2025 SF Tesla pileup, Sep 2025
  Tempe motorcyclist) — the FAQ fatality language is still valid.
- `requirements.txt` pinned ranges; `requirements-dev.txt` adds pytest.

### Tests + CI (done)
- `tests/test_utils.py` + `tests/test_merge.py` — 53 tests, all passing
  (`.venv/bin/python -m pytest tests/ -q`). Cover state/metro mapping,
  Glendale AZ/CA disambiguation, operation classification, date precision,
  merge keep-everything guarantees, dup-hub-ID abort.
- `.github/workflows/ci.yml` — NEW: pytest on push/PR.
- `.github/workflows/update-data.yml` — weekly (Mon 10:00 UTC), runs tests
  before pipeline, validates output JSON (no shrinking counts), commits
  `data/static/` too (old bug: miles_by_city.json was never committed by
  CI), rebases before push, writes job summary.
- `.github/workflows/deploy-pages.yml` — skips deploy when the data run
  failed; checks out `main` explicitly.

### Frontend JS (done)
- `map-controller.js` — CITY_COORDS now populated from `stats.cities` at
  init (no hardcoding); announced metros drawn as hollow dashed circles;
  scrollytelling map shows driverless only; popups format month-precision
  dates ("March 2026"), show provenance notes (approximate location /
  pending hub enrichment / supervised testing).
- `explore.js` — new `includeSupervised` filter (checkbox id
  `supervised-toggle`, default off); road-user filter falls back to NHTSA
  `crash_with` for unclassified crashes; time filters now exclude
  unknown-time crashes; reset handles the new toggle.
- `charts.js` — new `buildTrendChart(stats)` (canvas id `trend-chart`):
  crashes per month, lighter bars for months after hub coverage.
- `app.js` — calls buildTrendChart; city cards handle missing
  mileage/peak, "testing" status note, OTHER bucket label.

### Data (regenerated locally, committed)
- `data/web/*.json` + `data/static/miles_by_city.json` regenerated from
  fresh downloads (Jun 9). site-data.json: 1,602 driverless crashes,
  federal through April 2026, hub through Dec 2025. geocode_cache grew by
  41 city-centroid entries. crash_data.json now ~3 MB (includes
  supervised + narratives) — fine gzipped, could split later if desired.

## What REMAINS (in order)

1. **index.html** (the big one — none of the new UI elements exist yet;
   the new JS all no-ops gracefully until these are added):
   - `<canvas id="trend-chart">` + section copy for the monthly trend
     (suggest: in Temporal Analysis section).
   - `<input type="checkbox" id="supervised-toggle">` in the Explore
     sidebar ("Include supervised test-driver crashes (237)") + small CSS.
   - `.city-card-status` CSS class for testing-metro cards.
   - Data-freshness note near the hero/map: bind
     `meta.federal_data_through_label` and `meta.hub_data_through_label`
     ("Federal reports through X; Waymo's detailed data through Y. Recent
     crashes shown at city-level accuracy.") `overview.preliminary_count`
     is available.
   - **Fix "Nearly half ... in San Francisco" claim — SF is now 43.8%.**
     Rephrase e.g. "more crashes than any other metro — <span
     data-stat='city_breakdown.San Francisco.percentage'>43.8</span>% of
     the national total" (scrolly step `zoom-california`, ~line 122).
   - "two-thirds of crashes at 0 mph" (~line 226) → bind to
     `crash_circumstances.speed_stats.stopped_pct` /
     `speed_distribution.0_mph.percentage` and soften wording.
   - Hero "X cities" copy: `overview.cities_count` is now 12 (metros with
     driverless crashes); `overview.public_metros_count` = 11. Choose
     phrasing, e.g. "driverless service open to the public in 11 metros".
   - SEO/social: meta description, OG/Twitter cards (og:image — use
     assets/images/waymo-kid-bike.jpg or make a map screenshot), canonical
     URL https://leftovergoldennuggets.github.io/bna-fuhgeddaboudit/.
   - Accessibility: aria-labels on all chart canvases, skip-to-content link.
2. **faq.html** — update hardcoded 5-city list (~line 140) to the 11+
   metros or make dynamic; keep fatality wording (still accurate, verify
   the comment block); ADD new Q&A on 2026 events: NHTSA probe PE26001
   (Santa Monica school-zone child strike, Jan 2026), May 2026 floodwater
   recall (3,791 vehicles, San Antonio pause), Dec 2025 school-bus recall.
   Update "Mountain View 2 crashes" line (Mountain View now maps into the
   SF Bay Area metro). Geocoding accuracy stats keys unchanged.
3. **methodology.html** — rewrite the merge section: federal record is the
   base; Waymo hub enriches with exact dates/addresses/classifications;
   explain the three location-precision tiers, month-precision dates,
   driverless vs supervised split (supervised excluded from headline,
   visible in Explore), OTHER bucket. Explain why totals exceed Waymo's
   own hub count.
4. **about.html** — city list sentence (~line 42) → current markets.
5. **README.md + MAINTENANCE.md** — describe new architecture; "new city"
   procedure is now: add one entry to `CITIES` in config.py (counties +
   cities + coords) — everything else flows; ANNOUNCED_METROS list upkeep.
6. **Verify**: `make serve` → check scrollytelling, explore filters,
   trend chart, popups (esp. a preliminary 2026 crash and a supervised
   one), city cards. Then squash-merge or merge branch → main (deploy
   workflow fires on push to main).
7. Optional ideas (discussed, not started): CSV export of filtered
   crashes in Explore, per-crash permalinks, print stylesheet,
   crash-rate-per-mile trend if Waymo publishes quarterly mileage series.

## Gotchas for the resume session

- Waymo's next quarterly drop (`202009-202603`) lands ~Jun 15, 2026; URL
  probing in 01_download_data.py handles it automatically. After it lands,
  most "preliminary" 2026 crashes get street-level addresses on the next
  weekly run.
- NHTSA public CSVs: month-precision dates ("MAR-2026"), redacted
  addresses/coords — that's why city-level tier exists.
- Hub State column uses FULL state names; NHTSA uses postal codes.
- `severity.police_reported` & friends now report % of known values
  (hub-enriched rows only) — methodology page should mention the base.
- 2 unmapped crashes (San Bernardino CA, Huntsville TX — both supervised)
  intentionally in OTHER.
- Local venv: `.venv/` (python3.14, pandas 3.0.3). Tests:
  `.venv/bin/python -m pytest tests/ -q`.
- Background research findings (city statuses, dates, sources) are
  summarized in the metro registry comments and this file; full sourced
  report was generated 2026-06-09 (Waymo: 11 public metros, 500k
  rides/week, $16B raise, 170.7M RO miles through Dec 2025, 92/83/82%
  reductions unchanged, no new fatalities).
