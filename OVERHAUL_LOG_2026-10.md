# Overhaul log — October 2026

Branch: `overhaul-2026-10` (from `main` @ `fb03fe0`, the 2026-10-19 auto-update).
Performed by Claude (Opus 5.5) at Anders Eidesvik's request: a full quality
review of data, methodology, site structure, journalism and facts, plus
improvements. This file records every finding, the evidence behind it, and
what was changed. Commits on the branch map to the sections below.

---

## 0. Starting state

- Local clone was 19 commits behind `origin/main` (weekly bot commits). A
  stray local edit to `data/web/geocode_cache.json` was stashed
  (`git stash list` → "pre-overhaul local geocode cache 2026-10-23"); origin's
  cache is a superset.
- GitHub Actions: every weekly "Update Crash Data" + "Deploy" run since June
  succeeded. Latest: 2026-10-19, federal data through Sept 2026, Waymo hub
  through June 2026 (the hub's Sept 24 / Oct 2 2026 release — correct).
- Local re-run of the full pipeline reproduces the bot's output exactly.
  Tests: 62/62 passing.

## 1. Audit findings

Each finding lists the evidence. "Fix" points to the section where it is
addressed.

### Broken on the live site

| # | Finding | Evidence | Fix |
|---|---------|----------|-----|
| F1 | **All maps broken.** CARTO basemap tiles now render "API KEY REQUIRED — carto.com/basemaps/apikey" watermarks. | Headless-Chrome screenshots of the live site, desktop + mobile. | §2.1 |
| F2 | **Fatality prose is wrong.** Dataset has 3 fatal crashes (SF Jan 2025; Tempe Sept 2025; Dallas Aug 2026), FAQ says "In both cases…". The MAINTENANCE.md editorial trigger fired with no alert. | `Highest Injury Severity Alleged == "Fatality"` → 3 rows: 30270-9724, 30270-11713, 30270-16196. | §2.2, §3.4 |
| F3 | **Location-type chart wrong.** Built from regex over narrative text — "parked vehicle" counted as a parking-lot crash, "approaching the intersection" as an intersection crash. Site: Intersection 45%, Parking 26%. NHTSA's structured `Roadway Type`: Intersection 22%, Parking Lot 9%, Street 69%. FAQ "Why are there so many crashes in parking lots?" rests on the wrong number. | Cross-tab of `Roadway Type` (driverless, n=2,131). | §2.3 |
| F4 | **Per-city crash rates mix time windows.** Numerator = crashes through Sept 2026; denominator = miles through June 2026 (CSV1). Inflates every city rate. | `03_compute_statistics.py` city_mileage block. | §2.4 |
| F5 | **Atlanta mileage shown as "not published".** CSV1 publishes `Atlanta Area` = 8.624M mi since the March 2026 release; the pipeline's county map doesn't know that label. | Raw CSV1 202009-202606. | §2.4 |
| F6 | **Incomplete months presented as data.** "Federal data through September 2026" — but September holds 7 driverless crashes vs ~90/month; August (66) is also under-reported. NHTSA's file lags reporting. | Monthly counts from merged data. | §2.5 |
| F7 | Rush-hour label "7–9 AM & 5–7 PM" but code counts 7:00–9:59 and 17:00–19:59; "Late night 11 PM–4 AM" counts 23:00–4:59. | `03_compute_statistics.py` temporal block. | §2.6 |
| F8 | README/methodology say `make data` / `make serve` — there is no Makefile. | `ls` | §2.7 |
| F9 | Favicon 404 on every page load. | Browser console. | §2.7 |

### Methodology and journalism

| # | Finding | Evidence | Fix |
|---|---------|----------|-----|
| M1 | **Waymo-vs-human figures are stale and mislabeled.** Hardcoded 92% / 82% from the 56.7M-mile Kusano et al. (2025) paper, but the page says they cover "271M+ rider-only miles". Waymo publishes current comparisons with confidence intervals in **CSV3** each quarter (through June 2026: serious-injury+ −95% [CI −83 to −99%], any-injury −82%, airbag −82%, police-reported −74%). | Hub CSV3 202009-202606 + release notes 2026-10-02. | §2.8 |
| M2 | **June 2025 reporting-rule break is not shown in trends.** Hub crashes per million RO miles fall from ~10 (Q4'24–Q2'25) to ~5–6 (Q3'25 on) in every metro at once. Over the same break the injury-crash rate is flat (0.5–0.7) and police-reported barely moves; the drop is almost entirely sub-1-mph contacts (≈4.8 → ≈1.7 per M mi). This is NHTSA's Third Amended SGO (effective June 16, 2025) raising the reporting threshold — not a safety change. | Quarterly rates computed from CSV1 history + CSV2 flags. | §2.9, §3 |
| M3 | Mileage chart is hand-maintained and ends at Feb 2026 (200M) while the site's own hero says 271M. Waymo's historical CSV1 files (back to Sept 2024) give a quarterly, per-metro mileage series automatically. | Probed CSV1 URLs 202409…202606 — all HTTP 200. | §2.9 |
| M4 | Hero: "must report **every** crash" and "the **complete** public record" — overclaims (threshold-based reporting since June 2025). | index.html | §3 |
| M5 | "crashes **caused** moderate or worse injuries" — NHTSA field is injury *alleged*, to anyone involved, not causation. | index.html | §3 |
| M6 | FAQ "Why do **most** crashes happen during rush hour?" — share is 28.7%. Temporal sections attribute patterns to traffic without noting they mirror Waymo's own ride demand (exposure). | faq.html, index.html | §3 |
| M7 | FAQ: "rear-end collisions — where another vehicle hits the back of the Waymo". Hub `V2V F2R` is front-to-rear in either direction. | Contact-area fields | §3 |
| M8 | Internal inconsistencies: About says pipeline runs "quarterly" (it's weekly); course called "Building News Apps" (README) vs "Computational Journalism" (FAQ); methodology "three raw CSV files" (four); "see the per-mile rates in the city section below" (it's above). | Page text | §3 |
| M9 | Hero "13 metro areas" next to "11 metros with public service" — 13 includes Denver and D.C. (1 testing crash each). | index.html | §3, §4 |
| M10 | ZIP note says ZIPs "aren't available yet for the most recent crashes" — Waymo stopped publishing ZIPs for events after June 2025 (release notes). | Hub data dictionary | §3 |
| M11 | **Map accuracy overstated.** "89% placed at their real street location" counts 1,280 "road"-tier markers where only one of two street names matched (pin lands somewhere along a possibly miles-long road). Checked against U.S. Census ZIP-area centroids: 25% of road-tier and 6% of street-tier markers sit more than twice the ZIP's radius from the ZIP Waymo reported — i.e. ~330 markers almost certainly in the wrong place. | Census 2024 ZCTA gazetteer vs. marker coordinates | §2.10 |
| M12 | **Two supervised crashes counted as driverless.** NHTSA's operator field is blank, but the narratives say "a test driver was present (in the driver's seating position)", and neither is in Waymo's rider-only hub (30270-14625, Washington D.C.; 30270-4881, San Francisco). Surfaced by the new editorial check ("driverless crash in a metro where driverless operation is illegal"). | Narrative text + hub absence | §2.11 |

### Fact-check (background research agent, spot-checked)

A separate research pass checked every hardcoded claim against current
sources. I re-verified the highest-stakes items myself (Waymo blog Sept 1
2026; News3LV/TechCrunch Las Vegas Sept 14; Axios/Carscoops IIHS Jul 23;
Axios San Antonio Sept 17; NHTSA recall 26E-035; NBC DFW/Fox 4 Dallas).

| # | Claim on site | Verdict | Correct as of 2026-10-23 |
|---|---|---|---|
| X1 | "Public in 11 metros" | Outdated | **15**: + Denver, San Diego, Tampa (Sept 1 2026), Las Vegas (Sept 14 2026) |
| X2 | "Driverless testing in D.C., Denver, Philadelphia" | Wrong | Denver is public; D.C. and Philadelphia are supervised-only (law/permit requires a driver); **Detroit** is in driverless testing (Oct 2026) |
| X3 | San Antonio "paused for roughly two weeks" | Wrong | Paused Apr 20 → mid-Sept 2026 (~5 months) |
| X4 | Recall list complete | Incomplete | Missing: construction-zone recall 26E-035 (3,871 vehicles, June 2026, 13 freeway work-zone entries); NTSB investigations of the Austin school-bus passes and the Santa Monica child strike |
| X5 | Fatalities "in both cases" | Wrong | Three: SF Jan 19 2025 (stopped, Tesla driver charged); Tempe Sept 14 2025 (motorcycle hit Waymo from behind, hit-and-run driver charged); Dallas Aug 7 2026 (pedestrian struck by SUV and thrown into the Waymo; police reportedly found no fault on the Waymo's part) |
| X6 | 92/82% "over 271M miles" (Kusano 2025) | Mislabeled | Those exact values are the Dec 2025 hub release; Kusano 2025 covered 56.7M miles. Now read live from CSV3 |
| X7 | SGO threshold "injury, airbag, or damage > $1,000" | Imprecise | Since June 16 2025: 5-day reports for fatality, hospital transport, airbag, vulnerable road user, (ADS) tow-away; monthly reports for other crashes with damage expected > $1,000 **or** where the ADS vehicle struck something / was the only vehicle. So a Waymo **being hit** with < $1,000 damage is no longer reported (Federal Register 2026-10363) |
| X8 | "Tesla FSD" is in the ADS file | Wrong | FSD (Supervised) is Level 2 → ADAS file; Tesla's robotaxi crashes are in the ADS file |
| X9 | "largest AV deployment in the world" | Contestable | Largest by weekly paid rides (500k+); Baidu Apollo Go reports more cumulative rides. Rephrased |
| X10 | Mileage milestones 7.13M (2023-12-20) and 22M (2024-06-05) | Wrong date/value | 7.14M through Oct 2023; 22M through end of June 2024 |
| X11 | Announced cities include Boston, Sacramento | Unverifiable | No firm Waymo announcement found → removed from the "coming next" map |
| X12 | New independent evidence missing | — | IIHS (Jul 23 2026): 68% fewer police-reportable crashes, 81% fewer injury crashes per mile vs. humans (≈50M miles, 2021–2024); SF only −35%, Austin +4% (small sample) |


### Verified healthy

- Merge direction (NHTSA base, hub enrichment) is sound; dedup keeps the
  latest report version.
- Driverless/supervised split: hub and NHTSA agree on 1,968 of 1,969 matched
  crashes (hub covers rider-only only).
- Multi-vehicle double counting is negligible (2 `Same Incident ID` pairs).
- Weekly CI/CD is reliable.

---

## 2. Changes — data & pipeline

**2.1 Maps (F1)** — see §4.

**2.2 Fatal crashes as data (F2).** `site-data.json → fatal_crashes` lists
every fatal crash (report ID, month, city, Waymo movement/speed, other
party). Prose about fault stays human-written (§3) and is now guarded by
the editorial check (§2.12).

**2.3 Roadway type (F3).** `utils.roadway_type()` maps NHTSA's structured
`Roadway Type`; the narrative-regex classifier (`extract_location_type`,
`LOCATION_PATTERNS`) is deleted. Result: Street 68.5%, Intersection 21.8%,
Parking lot 8.8%, Highway/freeway 0.5%.

**2.4 Per-metro rates (F4, F5).** Rates now count only crashes up to the
month the mileage runs through (CSV1 `data_through_ym`). CSV1 parsing
(`utils.parse_csv1_miles`) understands both formats Waymo has used (depot
names until Sept 2025; counties + aggregate areas since) — Atlanta's
8.624M miles now appear. Rates through June 2026 (crashes per million
miles): SF 9.9 (was 10.6), Phoenix 4.9 (5.1), LA 6.6 (7.0), Austin 7.7
(8.4), Atlanta 7.1 (new).

**2.5 Reporting completeness (F6).** NHTSA's `Report Submission Date`
shows 99.5% of Waymo reports arrive within one month of the crash month,
and the newest submission month is only partly in each file.
`utils.complete_through()` marks the latest two incident months
provisional; `meta.federal_complete_through` (currently July 2026) and
`monthly_trend_meta` drive the chart shading and wording.

**2.6 Time labels (F7)** — label text fixed in §3 (computation unchanged).

**2.7 Makefile, favicon (F8, F9).** Added `Makefile` (`make data`, `make
serve`, `make test`) and a favicon.

**2.8 Benchmarks from CSV3 (M1).** The pipeline downloads hub CSV3 and
`utils.benchmark_summary()` extracts, for the dynamic benchmark Waymo
headlines: serious-injury+, any-injury, airbag, police-reported and fatal
outcomes — overall, per metro, and per crash partner (pedestrian, cyclist,
motorcycle …) — with 95% confidence intervals. Hand-typed percentages are
gone from `config.py`.

**2.9 Mileage history and quarterly rates (M2, M3).** The pipeline
downloads every hosted CSV1 release (Sept 2024 onward, extending itself
each quarter; quarters that later vanish keep their saved values) into
`data/static/miles_quarterly.json`. From it:
- `mileage_series` — hand-sourced milestones (now only non-hub sources,
  two re-dated) merged with every hub total; the chart extends itself.
- `quarterly_rates` — hub crashes per million miles per quarter, overall
  and per metro, for all crashes, injury crashes and police-reported
  crashes, with the June 2025 rule change marked.

**2.10 ZIP-checked geocoding (M11).** New static
`data/static/zip_reference.json` (Census 2024 ZCTA centroids + equivalent
radii; builder: `pipeline/tools/build_zip_reference.py`). For crashes with
a hub ZIP, a geocode is accepted only inside 1.5 ZIP radii; otherwise
Nominatim is re-queried *bounded to the ZIP's box*; failing that, the
marker goes to the ZIP centre under a new honest "zip" precision tier.
Cached under v3 keys. Step 05 now reuses step 04's marker positions (by
report ID) instead of re-deriving them, so the two maps cannot disagree.

**2.11 Supervised misclassification (M12).** `utils.narrative_says_test_driver()`:
blank operator + not in the rider-only hub + narrative states a test
driver was present → supervised. Moves 2 crashes; driverless total 2,133 → 2,131.

**2.12 Editorial alerts (new).** `pipeline/06_editorial_checks.py`
compares the data with `data/static/editorial_baseline.json` (what an
editor has reviewed) and writes alerts for new fatal / serious-injury
crashes, unmapped places, driverless crashes in non-public metros, and
new hub releases. The weekly workflow opens or updates a GitHub issue
labelled `editorial-alert`. Back-tested against the June baseline it
flags the Dallas fatality as HIGH priority. `--accept` records a review.

**2.13 Metro registry.** 15 public metros (+ Denver, San Diego, Tampa,
Las Vegas, with launch months), Detroit (driverless testing), D.C. and
Philadelphia (supervised testing, with reasons). Announced list trimmed to
verified announcements. Carson, Harbor City, Torrance added to LA.

**2.14 Public outputs.**
- `data/web/waymo_crashes.csv` — the cleaned, merged dataset (one row per
  crash, 21 documented columns incl. narrative). Deployed with the site.
- `data/web/update_history.json` — what each automatic update added;
  back-filled from git history to June 2026.
- Map records now carry `report_id` (enables links to a single crash).

**2.15 Tests.** 21 new unit tests (`tests/test_overhaul_2026_10.py`);
83 total, all passing.

## 3. Changes — facts & journalism

Guiding choices: state what the data supports and no more; attribute
Waymo's claims to Waymo; show uncertainty; never let hand-written text
silently go stale.

**Home page**
- Hero: "must report every crash … the complete public record" →
  "must report their crashes … every one Waymo has reported". The "13
  metro areas" stat (incl. testing cities) → "15 cities with public
  service"; driverless miles now carry their as-of date.
- Scrolly: "crashes caused moderate or worse injuries" → "involved a
  moderate or worse injury to someone", plus "an injury on this list
  doesn't mean the Waymo caused the crash". The SF step now gives the per-
  mile comparison with Phoenix instead of only the raw share.
- Where: explains that counts track miles; cards give rates and Waymo's
  per-metro injury comparison with CI; roadway chart retitled and sourced.
- What happens: "Waymo stopped or parked" (60.8%, structured field)
  leads; the rear-end sentence now quantified (97% the Waymo was hit from
  behind); injury levels explained as "alleged, anyone involved".
- **Fatal crashes panel (new):** each death summarized with sources
  (Waymo reports; police via CBS SF, azfamily, NBC DFW, Fox 4). Wording
  on fault is deliberately careful — "no Waymo has been found at fault";
  Dallas: "police had not publicly assigned fault in the latest reports"
  (sources conflict on whether police called it no-fault).
- **"Are Waymos getting safer — and safer than people?" (new):** mileage
  growth; the rule-change finding in plain words with two side-by-side
  rate charts; Waymo's benchmarks with CIs and counts; a caveat box ("this
  is Waymo's analysis of Waymo"; few events behind the rarest outcomes);
  the independent IIHS study (68% / 81%; SF only 35%; Austin +4%).
- When: labels fixed (7–10 a.m. & 5–8 p.m.; 11 p.m.–5 a.m.); exposure
  caveat (patterns follow when Waymo drives; no miles-by-hour data);
  "Day of week" notes it covers exact-dated crashes only.
- Explore: honest precision breakdown; corrected ZIP note; CSV download.

**FAQ** — rewritten throughout. Removed "Why are there so many crashes in
parking lots?" (built on the regex error) and "Why do *most* crashes
happen during rush hour?" (→ "When do most crashes happen?", 28.6%).
New: "Are Waymos getting safer over time?", "Does this mean Waymo wasn't
at fault?". Updated: thresholds (Federal Register 2026-10363), 15 metros
with years, testing cities, recalls/investigations (adds work-zone recall
26E-035, NTSB probes, San Antonio 5-month pause), mileage list now
generated from data, fatal list with automatic fallback.

**Methodology** — rewritten: sources (incl. CSV1/CSV3), base-record
choice, operation type (incl. the new reclassification rule),
completeness (provisional months, rule change, Waymo-filed narratives,
duplicates), rates (window alignment, quarterly method, benchmark method
and limits incl. the unresolved two-Waymo crash 30270-13817 that Waymo
counts as "unknown" severity), map precision tiers with the ZIP audit,
field definitions, the six-step pipeline, a data dictionary for the CSV,
and a public **Corrections** list plus the weekly **update history**.

**About** — "eleven metros / largest AV deployment in the world" →
"largest robotaxi service in the United States … fifteen metro areas";
threshold sentence fixed; "pipeline that runs quarterly" → weekly.
Editorial line "Residents … did not sign up for a safety experiment, but
they are part of one" softened to "People in these cities share their
streets with this technology whether or not they ever ride in it", since
the page's own principles say "We avoid editorializing". *(Author's voice
— flagged for Anders to keep or revert.)*

Course name standardized to "begun in Stanford's COMM 277T" (README said
"Building News Apps", FAQ "Computational Journalism" — *Anders to
confirm*).

## 4. Changes — design & UX

- **Maps fixed (F1):** `site/js/basemap.js` — OpenFreeMap "positron"
  (free, open source, no key, no limits) through MapLibre GL 4.7.1 and
  maplibre-gl-leaflet 0.0.22; OSM raster fallback without WebGL. Sets max
  zoom (needed by marker clustering) and resizes with its container.
- Overview map also shows public metros without crashes (San Diego,
  Tampa) and testing cities (Detroit, D.C., Philadelphia), each labeled.
- City cards: 2-column grid on phones (was a 14-card single column);
  metros with < 10 crashes collapsed into one "Also:" line; noisy "peak
  hour" removed; drawings added for San Diego, Tampa, Las Vegas, Detroit.
- Benchmark rows: dot + CI bar on a 0–100% scale, counts underneath;
  stacks on mobile.
- Monthly chart: three shades (hub-detailed / federal-only / still
  filling in) with legend; dashed rule-change line. Rate charts share the
  marker. Mileage chart on a true time axis; hub points filled, announced
  milestones hollow; source in tooltip.
- Explore: map fills its column (removed an empty band under the map);
  marker popups show the NHTSA report ID and ZIP-centre placement.
- Favicon on every page; meta descriptions updated.

**New features (added after Anders asked about features/storytelling):**
- **"What We Found"** section under the hero: four findings with live
  numbers, each linking to its evidence — Waymo stopped/parked in 60.8%;
  82% fewer injury crashes than humans (Waymo's analysis; IIHS smaller
  gap); reported-crash rate 10.2 → 5.7 per million miles across the rule
  change; 3 deaths, none found Waymo's fault (falls back to neutral
  wording if an unreviewed fatal crash appears).
- **Narrative search** in Explore (all words must match the narrative,
  city or other party): "school bus" → 4 crashes.
- **Shareable crash links**: `#crash=<NHTSA report ID>` opens that crash
  on the Explore map; opening a popup writes its link to the address bar.
- **Latest update** line in the hero (from `update_history.json`).
- Popup badges distinguish Fatal / Serious injury / Moderate injury (the
  fatal Dallas crash had been badged "Serious").

**Considered and not done:** comparing Waymo with Tesla/Zoox (their
crashes are in the same NHTSA file, but neither publishes miles, so only
misleading raw counts are possible); a full visual redesign (the existing
editorial look works; the problems were broken maps and missing context).

## 5. Verification

_(filled in at the end)_
