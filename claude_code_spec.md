# Claude Code Spec: Editorial Overhaul for "Every Waymo Crash, Mapped"

*Spec document for Claude Code implementation — March 8, 2026*
*Written by Claude Desktop as a knowledge transfer. Read this fully before starting any work.*

---

## Context

This is an evergreen data journalism website at `leftovergoldennuggets.github.io/bna-fuhgeddaboudit/` analyzing every publicly reported Waymo crash. See `BRIEFING_copy.md` for full technical documentation of the codebase, pipeline, and architecture.

We are doing an editorial overhaul to transform the site from a data dashboard into a data story. This spec covers all changes. **Do not change the pipeline architecture, file structure, or deployment system.** Only add to what exists.

**Editorial stance:** Neutral. We present data and let readers draw conclusions. We do not argue Waymo is safe or unsafe.

**Evergreen requirement:** All text that references numbers must use `data-stat` bindings. No hardcoded statistics in HTML. The pipeline auto-updates quarterly.

---

## PART A: Pure HTML/CSS Text Changes (No pipeline work needed)

These changes only require editing HTML files. No JavaScript logic or pipeline changes.

### A1. Rename site identity

**File:** `site/index.html`, `site/about.html`, `site/methodology.html`, `site/faq.html`

In all four files, change the navbar logo text:
- **From:** `Waymo Safety Analysis`
- **To:** `The Waymo Crash Record`

Find: `<a href="index.html" class="nav-logo">Waymo Safety Analysis</a>`
Replace: `<a href="index.html" class="nav-logo">The Waymo Crash Record</a>`

Also update in footer if present.

### A2. Hero card rewrite

**File:** `site/index.html`

Replace the hero card content. The new version should contain:

**Category tag:** Change "DATA JOURNALISM" to "AUTONOMOUS VEHICLES"

**Title:** Keep "Every Waymo Crash, Mapped" (no change)

**Subtitle:** Replace the current subtitle with:
"The federal government requires companies operating self-driving cars to report crashes that result in injury, airbag deployment, or significant property damage. This is every reported Waymo crash on record."

**Byline:** Add below subtitle: "By Anders Eidesvik and Kate Li"

**Date range and update date:** Keep the existing dynamic `data-stat` bindings.

### A3. Scrollytelling step rewrites

**File:** `site/index.html`

Replace the text content inside each `.scrolly-step .step-content` div. The `data-step` attribute values and map views do NOT change — only the text inside the cards.

**Step "intro":**
Title: "Tracking Self-Driving Cars"
Text: "Since 2021, the federal government has required companies operating self-driving cars on American roads to report crashes to the National Highway Traffic Safety Administration. The result is a comprehensive public record of autonomous vehicle incidents. This is Waymo's."

**Step "us-overview":**
Title: "The National Picture"
Text: "Waymo operates autonomous vehicles in <strong><span data-stat="overview.cities_count">--</span> major metropolitan areas</strong> across the United States. Through the NHTSA Standing General Order, <strong><span data-stat="overview.total_crashes" data-animate="true">--</span> crashes</strong> have been reported across these cities — everything from freeway collisions to parking lot fender-benders. Over the same period, Waymo has driven more than <strong><span data-stat="waymo_context.total_rider_only_miles" data-format="millions">--</span></strong> rider-only miles."

**Step "zoom-california":**
Title: "California: The Testing Ground"
Text: "Nearly half of all reported crashes — <strong><span data-stat="city_breakdown.San Francisco.percentage">--</span>%</strong> — have occurred in the San Francisco area. Waymo began commercial operations in San Francisco in 2023, later than Phoenix but in a denser and more complex traffic environment. Within each city, the number of reported crashes reflects how many miles Waymo has driven there. More miles means more incidents reported."

**Step "sf-heatmap":**
Title: "Where Crashes Cluster"
Text: "<strong><span data-stat="city_breakdown.San Francisco.count">--</span> crashes</strong> have been reported in the San Francisco area. The cluster markers show where they concentrate — intersections, busy corridors, and commercial areas. Click any cluster to zoom in and see individual incidents. Most of these dots represent low-speed events: a tap at a stoplight, a parking lot bump, another vehicle backing into the Waymo."

**Step "sf-serious":**
Title: "The Most Serious Incidents"
Text: "Of <span data-stat="overview.total_crashes">--</span> reported crashes, the vast majority resulted in no injuries at all. Only <strong><span data-stat="severity.injury_reported.count">--</span></strong> involved any reported injury, and just <strong><span data-stat="severity.moderate_plus.count">--</span></strong> involved moderate, serious, or fatal injuries. The red markers show where those most serious incidents occurred. Click any one to read the full federal crash narrative."

### A4. Waymo comparison caveat rewrite

**File:** `site/index.html`

In the "How Does This Compare?" box, replace the introductory text:

**From:** "According to Waymo's peer-reviewed research covering 56.7 million rider-only miles:"

**To:** "Waymo publishes crash rate comparisons on its <a href="https://waymo.com/safety/impact/" target="_blank" rel="noopener">Safety Impact Data Hub</a>, applying a methodology peer-reviewed in <em>Traffic Injury Prevention</em> (Kusano et al., 2025) to their latest crash data covering <span data-stat="waymo_context.total_rider_only_miles" data-format="millions">--</span> rider-only miles. These figures come from Waymo's own analysis. While the methodology has been peer-reviewed, the comparison benchmarks may not perfectly match Waymo's specific operating conditions."

### A5. Bridging text additions

**File:** `site/index.html`

Add a bridging paragraph before the "When Do Crashes Happen?" section heading:

"Crash timing reveals a familiar pattern: Waymo incidents peak during the hours and days when roads are busiest. This mirrors what traffic safety researchers see in human-driver crash data nationally — more vehicles on the road means more opportunities for collisions."

Style this as a `<p>` with class `section-intro` or similar, matching existing body text styling.

### A6. Explore section intro rewrite

**File:** `site/index.html`

Replace the explore section subtitle "Filter and explore all 1,123 crashes interactively" with:

"Every reported crash is mapped below. Use the filters to find patterns — or look up what's happened near you."

Add below the filters (or above the map), a "Things to try" prompt box:

```html
<div class="explore-prompts">
  <p class="explore-prompts-title">Things to try:</p>
  <ul>
    <li>Filter by <strong>"Serious"</strong> to see only the <span data-stat="severity.moderate_plus.count">--</span> crashes that resulted in moderate-to-fatal injuries.</li>
    <li>Select <strong>"Pedestrian"</strong> or <strong>"Cyclist"</strong> to find incidents involving vulnerable road users.</li>
    <li>Switch to <strong>"Night"</strong> to see how crash patterns shift after dark.</li>
  </ul>
</div>
```

Style with muted text, slightly smaller font, matching the earth tone palette.

---

## PART B: New "What Happens in These Crashes?" Section

This is the biggest single addition. It adds a new content section with two new Chart.js charts and supporting statistics.

### B1. New statistics to compute

**File:** `pipeline/03_compute_statistics.py`

Add a new top-level key `crash_circumstances` to the `site-data.json` output:

```json
"crash_circumstances": {
  "speed_distribution": {
    "0_mph": { "count": 734, "percentage": 65.6 },
    "1_5_mph": { "count": 146, "percentage": 13.0 },
    "6_15_mph": { "count": 118, "percentage": 10.5 },
    "16_25_mph": { "count": 77, "percentage": 6.9 },
    "26_35_mph": { "count": 32, "percentage": 2.9 },
    "36_plus_mph": { "count": 12, "percentage": 1.1 }
  },
  "speed_stats": {
    "total_with_speed_data": 1119,
    "median_speed_mph": 0,
    "mean_speed_mph": 4.1
  },
  "waymo_precrash_movement": {
    "Stopped": { "count": 560, "percentage": 49.9 },
    "Proceeding Straight": { "count": 292, "percentage": 26.0 },
    "Parked": { "count": 160, "percentage": 14.2 },
    "Making Left Turn": { "count": 35, "percentage": 3.1 },
    "Making Right Turn": { "count": 23, "percentage": 2.0 },
    "Other": { "count": 51, "percentage": 4.5 }
  },
  "crash_type_distribution": {
    "Rear-end collision": { "code": "V2V F2R", "count": 292, "percentage": 26.0 },
    "Side-impact collision": { "code": "V2V Lateral", "count": 235, "percentage": 20.9 },
    "Backing collision": { "code": "V2V Backing", "count": 170, "percentage": 15.1 },
    "Single vehicle": { "code": "Single Vehicle", "count": 106, "percentage": 9.4 },
    "Head-on collision": { "code": "V2V Head-on", "count": 102, "percentage": 9.1 },
    "Intersection collision": { "code": "V2V Intersection", "count": 89, "percentage": 7.9 },
    "Other": { "code": "All Others", "count": 66, "percentage": 5.9 },
    "Secondary crash": { "code": "Secondary Crash", "count": 23, "percentage": 2.0 },
    "Motorcycle": { "code": "Motorcycle", "count": 17, "percentage": 1.5 },
    "Cyclist": { "code": "Cyclist", "count": 15, "percentage": 1.3 },
    "Pedestrian": { "code": "Pedestrian", "count": 8, "percentage": 0.7 }
  },
  "vulnerable_road_users": {
    "total": 40,
    "percentage": 3.6,
    "pedestrian": 8,
    "cyclist": 15,
    "motorcycle": 17
  }
}
```

**How to compute from waymo_merged.csv:**

Speed distribution: Use column `SV Precrash Speed (MPH)`. Values are floats like "0.0", "22.0". Bucket into the ranges shown. Compute mean and median.

Waymo pre-crash movement: Use column `SV Pre-Crash Movement`. Group less common movements into "Other".

Crash type distribution: Use column `Crash Type` from the Waymo Hub data. Apply the existing `CRASH_TYPE_LABELS` mapping to get plain English names.

Vulnerable road users: Count rows where `Crash Type` is "Pedestrian", "Cyclist", or "Motorcycle".

### B2. New HTML section

**File:** `site/index.html`

Insert this new section AFTER the "By the Numbers" / "How Does This Compare?" section and BEFORE the "When Do Crashes Happen?" section.

```html
<section class="content-section" id="crash-circumstances">
  <div class="section-container">
    <h2>What Happens in These Crashes?</h2>
    <p class="section-subtitle">Understanding the circumstances behind <span data-stat="overview.total_crashes">--</span> reported incidents</p>

    <p>The word "crash" conjures images of high-speed collisions. The reality in this dataset is very different.</p>

    <p><strong>In nearly two-thirds of reported crashes, the Waymo vehicle was traveling at 0 mph at the time of contact.</strong></p>

    <div class="chart-container">
      <h3 class="chart-title">Waymo Vehicle Speed at Time of Crash</h3>
      <canvas id="speed-chart"></canvas>
      <p class="chart-note">Based on <span data-stat="crash_circumstances.speed_stats.total_with_speed_data">--</span> crashes with speed data. Median speed: <span data-stat="crash_circumstances.speed_stats.median_speed_mph">--</span> mph. Mean: <span data-stat="crash_circumstances.speed_stats.mean_speed_mph">--</span> mph.</p>
    </div>

    <p>The most common scenario: the Waymo vehicle is stopped at a light or waiting in traffic, and another vehicle makes contact — often while backing up, changing lanes, or proceeding through an intersection.</p>

    <div class="chart-container">
      <h3 class="chart-title">Crashes by Type</h3>
      <canvas id="crash-type-chart"></canvas>
    </div>

    <p>Crashes involving vulnerable road users — pedestrians, cyclists, and motorcyclists — account for <span data-stat="crash_circumstances.vulnerable_road_users.total">--</span> of <span data-stat="overview.total_crashes">--</span> total incidents (<span data-stat="crash_circumstances.vulnerable_road_users.percentage">--</span>%).</p>
  </div>
</section>
```

### B3. New charts

**File:** `site/js/charts.js`

Add two new chart builder functions following the existing pattern (matching colors, fonts, tooltip style):

**1. Speed Distribution Chart** (`#speed-chart`)
- Type: horizontal bar chart (like the existing location-type chart)
- 6 bars: "0 mph", "1–5 mph", "6–15 mph", "16–25 mph", "26–35 mph", "36+ mph"
- Data source: `stats.crash_circumstances.speed_distribution`
- Color: default grey `#b8b0a6`, highlight the "0 mph" bar with accent `#8b6f47` to emphasize the finding
- No grid lines, Source Serif 4 font for labels

**2. Crash Type Chart** (`#crash-type-chart`)
- Type: horizontal bar chart
- 11 bars using plain English labels
- Data source: `stats.crash_circumstances.crash_type_distribution`
- Same color scheme as other charts
- Sort by count descending (rear-end at top)

### B4. Initialize new charts

**File:** `site/js/app.js`

Add to the initialization sequence after existing chart builds:
```js
Charts.buildSpeedChart(stats);
Charts.buildCrashTypeChart(stats);
```

---

## PART C: Mileage Data Integration

### C1. Static mileage milestones file

**File to create:** `data/static/mileage_milestones.json`

This is a manually maintained file (NOT auto-downloaded) because Waymo doesn't publish a time series. Each entry is sourced from press releases and public statements. The file should be committed to git and loaded by the website.

```json
{
  "description": "Waymo rider-only mileage milestones compiled from press releases, public statements, and archived web pages. Manually updated when new milestones are announced.",
  "last_updated": "2026-03-08",
  "milestones": [
    { "date": "2023-01-31", "miles_millions": 1, "source": "Waymo press release", "url": "https://waymo.com/blog/..." },
    { "date": "2023-12-20", "miles_millions": 7.13, "source": "The Verge", "url": "https://www.theverge.com/..." },
    { "date": "2024-06-05", "miles_millions": 22, "source": "Waymo press release", "url": "https://waymo.com/blog/..." },
    { "date": "2024-09-30", "miles_millions": 33, "source": "Waymo (Wayback Machine)", "url": "https://web.archive.org/..." },
    { "date": "2024-12-31", "miles_millions": 50, "source": "Waymo (Wayback Machine)", "url": "https://web.archive.org/..." },
    { "date": "2025-03-31", "miles_millions": 71.43, "source": "Waymo (Wayback Machine)", "url": "https://web.archive.org/..." },
    { "date": "2025-07-15", "miles_millions": 100, "source": "Waymo (X/Twitter)", "url": "https://x.com/Waymo/status/1945106097741664630" },
    { "date": "2026-02-02", "miles_millions": 127, "source": "Waymo press release", "url": "https://waymo.com/blog/2026/02/waymo-raises-usd16-billion-investment-round/" }
  ]
}
```

**IMPORTANT:** Anders will provide the exact URLs. The ones above are placeholders. Each must link to the original source.

### C2. Miles by city data

**File to create:** `data/static/miles_by_city.json`

This data IS published by Waymo on the Safety Impact Data Hub. It can potentially be auto-downloaded, but for now treat it as manually updated alongside the quarterly pipeline run.

```json
{
  "description": "Rider-only miles by city from Waymo Safety Impact Data Hub",
  "source_url": "https://waymo.com/safety/impact/",
  "data_through": "September 2025",
  "last_updated": "2026-03-08",
  "cities": {
    "Phoenix": { "miles_millions": 56.535, "note": "Waymo's first commercial market (Dec 2018)" },
    "San Francisco": { "miles_millions": 38.816 },
    "Los Angeles": { "miles_millions": 25.47 },
    "Austin": { "miles_millions": 6.337 },
    "Atlanta": { "miles_millions": null, "note": "Mileage not yet published by Waymo" }
  }
}
```

### C3. Compute crash rates per million miles

**File:** `pipeline/03_compute_statistics.py`

After loading the miles-by-city data, add to `site-data.json`:

```json
"city_mileage": {
  "San Francisco": { "miles_millions": 38.816, "crashes_per_million_miles": 13.6 },
  "Phoenix": { "miles_millions": 56.535, "crashes_per_million_miles": 5.5 },
  "Los Angeles": { "miles_millions": 25.47, "crashes_per_million_miles": 8.2 },
  "Austin": { "miles_millions": 6.337, "crashes_per_million_miles": 9.6 },
  "Atlanta": { "miles_millions": null, "crashes_per_million_miles": null }
}
```

### C4. Update city cards

**File:** `site/index.html` (the city cards section in "Where Do Crashes Happen?")

Add miles driven and crash rate below the existing crash count:

```
San Francisco
527 crashes (46.9%)
38.8M miles driven
13.6 crashes per million miles
Peak: 5:00 PM
```

Use `data-stat` bindings for all numbers. Do NOT display rate for Atlanta if miles are null.

### C5. Mileage growth chart (optional — lower priority)

If time permits, add a line chart showing the mileage growth over time from `mileage_milestones.json`. This would go in the "By the Numbers" section or near the "National Picture" scrollytelling step.

- Type: line chart (Chart.js)
- X axis: dates
- Y axis: millions of miles
- Simple, clean, matching earth tone style
- Source attribution below: "Source: Compiled from Waymo press releases and public data by Anders Eidesvik"

---

## PART D: Data Loader Updates

**File:** `site/js/data-loader.js`

The data loader currently fetches 3 JSON files. It needs to also load:
- `data/static/miles_by_city.json` (for city cards)
- `data/static/mileage_milestones.json` (for growth chart, if built)

These are small static files. Add them to `DataLoader.loadAll()` in parallel with the existing fetches.

Update the path detection for GitHub Pages vs local, same pattern as existing files.

---

## PART E: Map Visual Improvements

### E1. Fix cluster marker colors

**File:** `site/js/map-controller.js` and/or `site/css/styles.css`

**Problem:** Cluster bubbles currently go from brown → amber → deep red as count increases. This makes high-count clusters look like severity indicators (readers think red = dangerous).

**Fix:** Use a single color for ALL cluster bubbles regardless of count. Use the existing brown `#8b6f47`. Size already communicates count. Reserve red exclusively for serious incident markers.

### E2. Coordinate jittering for overlapping crashes

**File:** `site/js/map-controller.js` (or `pipeline/04_generate_map_data.py`)

**Problem:** Multiple crashes at the same address stack on top of each other, appearing as a single dot when zoomed in.

**Fix:** Add a small random offset (±0.0001 degrees, approximately 10 meters) to coordinates that share the same lat/lon. This can be done either:
- In the pipeline (preferred — deterministic, cached) using a seeded random offset
- Or in the JS when creating markers

The jittering should be small enough that markers stay on the correct street but spread enough to be individually clickable.

---

## PART F: Enriched Crash Popups for Explore Section

### F1. Add more fields to crash_data.json

**File:** `pipeline/04_generate_map_data.py`

Currently each crash record in `crash_data.json` has ~12 fields. Add:

```json
{
  "existing fields...",
  "sv_movement": "Stopped",
  "cp_movement": "Backing",
  "crash_with": "SUV",
  "injury_severity": "No Injuries Reported",
  "speed_mph": 0,
  "narrative": "On November 8, 2025 at 12:14 PM PT a Waymo..."
}
```

**File size consideration:** Adding narratives (200-500 words each × 1,119 crashes) will increase crash_data.json significantly. Two options:
1. Include narratives for ALL crashes (simpler, larger file ~2-5MB)
2. Create a separate `crash_narratives.json` that's lazy-loaded on click (smaller initial load, more complex JS)

Recommend option 1 for simplicity. The file is loaded once and cached.

### F2. Update explore map popups

**File:** `site/js/explore.js`

Update the popup content for individual crash markers to show:
- Crash type (plain English — already exists)
- City and date (already exists)
- What Waymo was doing (sv_movement)
- What the other party was doing (cp_movement)
- Other party type (crash_with)
- Injury severity
- Speed at time of crash
- Truncated narrative (first 200 chars) with "Read full report" expansion

### F3. Update explore map serious incident popups

Currently only the 15 serious incidents have detailed panels. In the explore section, ALL crashes should show enriched popups (though the full narrative panel experience can remain exclusive to serious incidents in the scrollytelling section).

---

## Implementation Order

Suggested order for Claude Code:

1. **Part A** — Text changes (fastest, most visible impact)
2. **Part B** — New "What Happens" section (biggest editorial addition)
3. **Part C1-C3** — Mileage data files and pipeline stats
4. **Part C4** — City cards update
5. **Part E1** — Fix cluster colors
6. **Part F** — Enriched popups
7. **Part E2** — Coordinate jittering
8. **Part C5** — Growth chart (if time)
9. **Part D** — Data loader updates (needed for C and F)

Note: Part D (data loader) is a dependency for Parts C and F — do it when needed.

---

## Design Reference

**Colors:**
- Accent: `#8b6f47`
- Background: `#faf8f5`
- Alt background: `#f0ece6`
- Text: `#2c2c2c`
- Light text: `#6b6b6b`
- Chart bars: `#b8b0a6` (default), `#8b6f47` (highlight/hover)
- Danger/serious: `#8b2020`

**Fonts:**
- Headlines: Source Serif 4
- Body: Inter
- Data/numbers: IBM Plex Mono

**Chart style:**
- No grid lines
- Custom tooltip
- Horizontal bars for distributions
- Source Serif 4 for labels

---

## Files That Change

| File | Parts |
|------|-------|
| `site/index.html` | A1-A6, B2, C4 |
| `site/about.html` | A1 |
| `site/methodology.html` | A1, add note about speed/movement analysis |
| `site/faq.html` | A1, add FAQ about crash circumstances |
| `site/js/charts.js` | B3 |
| `site/js/app.js` | B4 |
| `site/js/data-loader.js` | D |
| `site/js/map-controller.js` | E1, E2 |
| `site/js/explore.js` | F2, F3 |
| `site/css/styles.css` | A6 (explore prompts), B2 (new section) |
| `pipeline/03_compute_statistics.py` | B1, C3 |
| `pipeline/04_generate_map_data.py` | F1 |
| `data/static/mileage_milestones.json` | C1 (NEW) |
| `data/static/miles_by_city.json` | C2 (NEW) |

---

## Quality Checks

After implementation:
1. Run `make data` and verify `site-data.json` contains the new `crash_circumstances` key
2. Verify all `data-stat` bindings populate correctly on page load
3. Check that the two new charts render in the correct position
4. Verify city cards show mileage data (except Atlanta)
5. Test cluster markers are uniform brown (no red gradient)
6. Test explore map popups show enriched data
7. Run `make serve` and scroll through the full page to verify narrative flow
8. Check mobile responsiveness of new sections

---

*Spec written by Claude Desktop for Claude Code implementation. All statistics verified against waymo_merged.csv (1,123 rows). All Waymo claims verified against Safety Impact Data Hub and peer-reviewed publications.*
