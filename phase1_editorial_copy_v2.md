# Phase 1: Editorial Copy — REVISED
## "Every Waymo Crash, Mapped"

*Revised draft for Anders & Kate — March 8, 2026*
*All numbers verified against waymo_merged.csv (1,123 rows, Sept 2020–Sept 2025)*
*All Waymo claims verified against Safety Impact Data Hub and peer-reviewed publications*

---

## Site Name

**Change navbar from:** "Waymo Safety Analysis"
**Change navbar to:** "The Waymo Crash Record"

---

## Hero Card

**Proposed:**

> AUTONOMOUS VEHICLES
>
> **Every Waymo Crash, Mapped**
>
> The federal government requires companies operating self-driving cars to report crashes that result in injury, airbag deployment, or significant property damage. This is every reported Waymo crash on record.
>
> By Anders Eidesvik and Kate Li
>
> Covering [dynamic: Sept 2020] through [dynamic: Sept 2025]
> Updated [dynamic date]

**Notes:**
- Accurately reflects post-Amendment 3 reporting requirements (effective June 16, 2025) while remaining true for the pre-June data (which had an even lower threshold). The current phrasing covers both eras.
- Added byline.
- "on record" reinforces that this is official data, not estimates.

---

## Scrollytelling Steps

### Step 1: "intro" — The Mandate

**Map view:** US overview, zoomed out
**Card title:** Tracking Self-Driving Cars

**Card text:**

> **Tracking Self-Driving Cars**
>
> Since 2021, the federal government has required companies operating self-driving cars on American roads to report crashes to the National Highway Traffic Safety Administration.
>
> The result is a comprehensive public record of autonomous vehicle incidents. This is Waymo's.

**Notes:**
- Removed "no matter how minor" per your correction about Amendment 3.
- Kept the language broad enough to be accurate for both pre- and post-June 2025 reporting requirements.
- "Tracking Self-Driving Cars" as the title is clear and journalistic.

---

### Step 2: "us-overview" — The Scale

**Map view:** US with five city markers visible

**Card text:**

> **The National Picture**
>
> Waymo operates autonomous vehicles in **[dynamic: 5] major metropolitan areas** across the United States.
>
> Through the NHTSA Standing General Order, **[dynamic: 1,123] crashes** have been reported across these cities — everything from freeway collisions to parking lot fender-benders.
>
> Over the same period, Waymo has driven more than **[dynamic: 127 million]** rider-only miles.

**Notes:**
- Removed "over five years" — not evergreen.
- Removed "must be understood in the context of" — you were right, it sounds opinionated.
- Instead, the mileage figure is simply stated as a fact in its own sentence. Readers can draw their own conclusions about the ratio.
- All three key numbers use data-stat bindings for evergreen updates.

---

### Step 3: "zoom-california" — California

**Map view:** Zoom to West Coast showing SF, LA cluster sizes

**Card text:**

> **California: The Testing Ground**
>
> Nearly half of all reported crashes — **[dynamic: 46.9]%** — have occurred in the San Francisco area. Waymo began commercial operations in San Francisco in 2023, later than Phoenix but in a denser and more complex traffic environment.
>
> Within each city, the number of reported crashes reflects how many miles Waymo has driven there. More miles means more incidents reported.

**Notes:**
- Fixed: Phoenix (December 2018) was Waymo's first commercial market. SF public launch was 2023.
- Phoenix has 56.5M miles vs SF's 38.8M miles — but SF has more crashes per mile, likely due to traffic complexity. Stated neutrally.
- The last sentence is the key contextual point, stated as a general principle rather than a defense.

---

### Step 4: "sf-heatmap" — Crash Density

**Map view:** Zoomed into San Francisco with cluster markers

**Card text:**

> **Where Crashes Cluster**
>
> **[dynamic: 527] crashes** have been reported in the San Francisco area. The cluster markers show where they concentrate — intersections, busy corridors, and commercial areas.
>
> Click any cluster to zoom in and see individual incidents. Most of these dots represent low-speed events: a tap at a stoplight, a parking lot bump, another vehicle backing into the Waymo.

**Notes:**
- Removed "commercial corridors" standalone phrasing (you asked if this was data-backed). It is: the clusters are densest in areas like SoMa, downtown, and along Mission/Market corridors which are commercial areas with heavy traffic. But to be safe, I've used "intersections, busy corridors, and commercial areas" which matches the location type data (intersections: 39.6%, street: 31.5%, parking: 27.7%).
- The examples in the last sentence are verified: rear-end (26%), lateral (20.9%), backing (15.1%) are the top crash types, and 65.6% involve a stationary Waymo.

---

### Step 5: "sf-serious" — Severity

**Map view:** Same SF view with red serious-incident markers added

**Card text:**

> **The Most Serious Incidents**
>
> Of [dynamic: 1,123] reported crashes, the vast majority resulted in no injuries at all. Only **[dynamic: 96]** involved any reported injury, and just **[dynamic: 15]** involved moderate, serious, or fatal injuries.
>
> The red markers show where those most serious incidents occurred. Click any one to read the full federal crash narrative.

**Notes:** No changes from v1. This step is strong.

---

## Bridging Text Between Sections

### Waymo Comparison Caveat (within "How Does This Compare?" box)

**Current text:**
> According to Waymo's peer-reviewed research covering 56.7 million rider-only miles:

**Replace with:**
> Waymo publishes crash rate comparisons on its Safety Impact Data Hub, applying a peer-reviewed methodology (Kusano et al., 2025) to data covering [dynamic: 127 million] rider-only miles. These figures come from Waymo's own analysis. While the methodology has been peer-reviewed and adheres to industry best practices (the RAVE checklist), the comparisons are made against human driver benchmarks that may not perfectly match Waymo's specific operating conditions.

**Notes:**
- Now accurately distinguishes between: (1) the peer-reviewed paper (56.7M miles, methodology), and (2) the Safety Impact Data Hub (127M miles, applying that methodology to latest data).
- Transparent about source without being dismissive.
- References the RAVE checklist which is the industry standard Waymo adheres to.

---

### Before "When Do Crashes Happen?"

> Crash timing reveals a familiar pattern: Waymo incidents peak during the hours and days when roads are busiest. This mirrors what traffic safety researchers see in human-driver crash data nationally — more vehicles on the road means more opportunities for collisions.

**Notes:** Added the human-driver comparison. NHTSA FARS data consistently shows Friday and Saturday as peak crash days for human drivers, matching Waymo's pattern.

---

### Before "Where Do Crashes Happen?"

> The geographic distribution of crashes largely reflects where Waymo drives the most. Phoenix — where Waymo has driven the most miles (56.5 million) — has the second-highest crash count. San Francisco, with 38.8 million miles in a denser urban environment, has the most. Within each city, the crash rate per million miles varies, reflecting differences in traffic density, road design, and driving conditions.

**TODO for pipeline (REMIND ME):**
- Add miles-driven-by-city data to the pipeline (source: Waymo Safety Impact Data Hub CSV)
- Compute crashes per million miles for each city
- Display alongside crash counts in the city cards
- Note that SF has more complex traffic than Phoenix, which Waymo acknowledges in their methodology

---

### NEW SECTION: "What Happens in These Crashes?"

**Place after "By the Numbers," before "When Do Crashes Happen?"**

> ## What Happens in These Crashes?
>
> The word "crash" conjures images of high-speed collisions. The reality in this dataset is very different.
>
> **In nearly two-thirds of reported crashes, the Waymo vehicle was traveling at 0 mph at the time of contact.**
>
> [CHART: Horizontal bar chart — Speed distribution]
> 0 mph: 734 (65.6%)
> 1–5 mph: 146 (13.0%)
> 6–15 mph: 118 (10.5%)
> 16–25 mph: 77 (6.9%)
> 26–35 mph: 32 (2.9%)
> 36+ mph: 12 (1.1%)
>
> *Based on 1,119 crashes with speed data. Median speed: 0 mph. Mean: 4.1 mph.*
>
> The most common scenario: the Waymo vehicle is stopped at a light or waiting in traffic, and another vehicle makes contact — often while backing up, changing lanes, or proceeding through an intersection.
>
> [CHART: Horizontal bar chart — Crash types in plain English]
> Rear-end collision: 292 (26.0%)
> Side-impact collision: 235 (20.9%)
> Backing collision: 170 (15.1%)
> Single vehicle: 106 (9.4%)
> Head-on collision: 102 (9.1%)
> Intersection collision: 89 (7.9%)
> Other: 66 (5.9%)
> Secondary crash: 23 (2.0%)
> Motorcycle: 17 (1.5%)
> Cyclist: 15 (1.3%)
> Pedestrian: 8 (0.7%)
>
> Crashes involving vulnerable road users — pedestrians, cyclists, and motorcyclists — account for 40 of 1,123 total incidents (3.6%).

**Notes on chart type:** Recommend horizontal bar charts matching the existing "Crashes by Location Type" style. The speed distribution chart is the visual centerpiece — the 0 mph bar will dominate and instantly communicate the finding. Use the same earth tone color scheme.

**Code requirements for Claude Code:**
1. Add speed distribution stats to `03_compute_statistics.py`
2. Add crash type distribution (already partially exists but needs to be surfaced)
3. Add new Chart.js charts in `charts.js`
4. Add HTML section in `index.html`
5. Wire up data-stat bindings

---

### Before the Explore Section

> ## Explore the Data
>
> Every reported crash is mapped below. Use the filters to find patterns — or look up what's happened near you.
>
> **Things to try:**
> - Filter by **"Serious"** to see only the 15 crashes that resulted in moderate-to-fatal injuries.
> - Select **"Pedestrian"** or **"Cyclist"** to find incidents involving vulnerable road users.
> - Switch to **"Night"** to see how crash patterns shift after dark.

---

## Additional Items

### Mileage Growth Chart

Your Flourish chart showing Waymo's exponential mileage growth (1M in Jan 2023 → 127M by Sept 2025) should be recreated in Chart.js to match the site's style. Best placement: either within the "National Picture" scrollytelling step (as a small inline graphic) or as part of the "By the Numbers" section.

**TODO for pipeline:**
- Add Waymo's mileage milestone data to the pipeline (source: press releases, Safety Impact Data Hub)
- The data from your screenshot shows: LA 25.47M, SF 38.816M, Phoenix 56.535M, Austin 6.337M
- This should be downloadable from the Hub and updated via GitHub Actions

### City Cards Enhancement

The current city cards show: city name, crash count, percentage, peak hour.

**Proposed addition:** Add miles driven and crash rate per million miles.

Example:
> **San Francisco**
> 527 crashes (46.9%)
> 38.8M miles driven
> 13.6 crashes per million miles
> Peak: 5:00 PM

> **Phoenix**
> 312 crashes (27.8%)
> 56.5M miles driven
> 5.5 crashes per million miles
> Peak: 6:00 PM

**This is a significant finding:** SF's crash rate per million miles is roughly 2.5x Phoenix's, likely reflecting the denser, more complex traffic environment. This is worth noting in the bridging text without making a value judgment.

---

## Implementation Plan

### What can be done as pure HTML text changes (Phase 1a — now):
- [ ] Navbar: "Waymo Safety Analysis" → "The Waymo Crash Record"
- [ ] Hero card: new subtitle, byline, category tag
- [ ] All 5 scrollytelling card rewrites
- [ ] Bridging paragraph before "When Do Crashes Happen?"
- [ ] Explore section intro + "Things to try" prompts
- [ ] Waymo comparison caveat rewrite

### What needs Claude Code (Phase 1b — spec document):
- [ ] New "What Happens in These Crashes?" section (HTML + charts + stats)
- [ ] Speed distribution chart (Chart.js)
- [ ] Crash type chart in new section (Chart.js)
- [ ] Add speed stats to `03_compute_statistics.py` → `site-data.json`
- [ ] Bridging text before "Where" section (needs miles-by-city data first)

### What needs pipeline work (Phase 2):
- [ ] Add Waymo mileage data (by city) to pipeline
- [ ] Compute crashes per million miles by city
- [ ] Update city cards with mileage + rate
- [ ] Add mileage growth chart
- [ ] Enrich crash_data.json with NHTSA fields (narrative, movement, speed) for richer popups
- [ ] Add narratives to explore section popups
- [ ] GitHub Actions: add Waymo mileage CSV download

### What needs visual/design work (Phase 3):
- [ ] Fix cluster marker colors (single brown, no red gradient)
- [ ] Add coordinate jittering for overlapping crashes
- [ ] Add your photos of Waymo vehicles
- [ ] Fill in About page bios
- [ ] Mileage growth chart in site style

---

*All statistics verified against waymo_merged.csv. Waymo operational history verified against Wikipedia, Waymo blog, and press coverage. NHTSA SGO Amendment 3 requirements verified against NHTSA.gov. Waymo Safety Impact Data Hub methodology verified against release notes and peer-reviewed publications.*
