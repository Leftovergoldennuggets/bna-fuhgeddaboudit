/**
 * app.js — Application orchestrator
 * ====================================
 * This is the main entry point. It loads all data, then initializes
 * each module in the correct order:
 *
 *   1. Load all JSON data files (site-data, crash_data, serious_incidents)
 *   2. Render statistics into HTML placeholders
 *   3. Build the city cards in the spatial section
 *   4. Initialize the scrollytelling map
 *   5. Initialize the scrollytelling observer
 *   6. Initialize the explore section (filters + map)
 *
 * If data loading fails, it shows an error message to the user.
 *
 * Dependencies: All other JS modules must be loaded before this one.
 */

// ============================================
// App Init
// ============================================

// Wait until the HTML page is fully loaded before running our code
document.addEventListener("DOMContentLoaded", async function () {
    // Log a message to the browser console so we know the app started
    console.log("[App] Starting Waymo Crash Data Analysis...");

    // try/catch: attempt the code inside "try", and if anything fails, jump to "catch"
    try {
        // Step 1: Load all data files
        // "await" pauses here until the data finishes downloading
        const data = await DataLoader.loadAll();

        // Step 2: Fill in all data-stat placeholders with real numbers
        StatRenderer.renderAll(data.stats);

        // Step 3: Build dynamic city cards and the severity waffle
        buildCityCards(data.stats);
        buildFatalList(data.stats);
        buildBenchmarkRows(data.stats);
        fillSafetyNumbers(data.stats);
        fillFindings(data.stats);
        showLatestUpdate();
        buildSeverityWaffle(data.crashes);

        // Step 4: Initialize the scrollytelling map
        MapController.init(data.crashes, data.incidents, data.stats);

        // Step 5: Initialize scroll-driven transitions
        Scrollytelling.init();

        // Step 6: Build interactive charts (replaces static PNG images)
        Charts.buildSpeedChart(data.stats);
        Charts.buildCrashTypeChart(data.stats);       // Similar to above
        Charts.buildHourlyChart(data.stats);           // Similar to above
        Charts.buildDayOfWeekChart(data.stats);        // Similar to above
        Charts.buildLocationTypeChart(data.stats);     // Similar to above
        Charts.buildMileageChart(data.stats);          // Line chart: rider-only miles over time
        Charts.buildRateCharts(data.stats);            // Quarterly crash rates per million miles
        Charts.buildTrendChart(data.stats);            // Bar chart: crashes per month over time

        // Step 7: Initialize the interactive explore section
        Explore.init(data.crashes, data.stats);

        console.log("[App] All modules initialized successfully");
    } catch (error) {
        // If anything above failed, log the error and show it to the user
        console.error("[App] Failed to initialize:", error);
        showError(error.message);
    }
});

// ============================================
// City Card Artwork — tiny landmark line drawings
// ============================================
// One hand-drawn SVG per metro (120×44 grid, stroke-only, drawn in the
// site's accent color). Each picks one or two landmarks readable at
// small size rather than a literal skyline.

const CITY_ART = {
    SAN_FRANCISCO: `
        <path d="M30 40 V14 M38 40 V14 M30 14 H38 M30 21 H38 M30 28 H38"/>
        <path d="M8 26 Q19 14 30 14 M38 14 Q56 24 72 32"/>
        <path d="M88 40 L95 11 L102 40 M95 11 V6 M91 28 H99"/>`,
    PHOENIX: `
        <circle cx="100" cy="12" r="5"/>
        <path d="M24 40 V13 M24 25 H17 V16 M24 29 H31 V20"/>
        <path d="M40 40 Q48 30 54 31 Q58 32 60 27 Q66 15 76 19 Q84 23 90 40"/>`,
    LOS_ANGELES: `
        <path d="M24 40 C22 30 23 23 26 16"/>
        <path d="M26 16 C20 13 14 13 10 17 M26 16 C23 10 18 7 13 8 M26 16 C31 10 36 8 40 10 M26 16 C32 13 38 14 41 18"/>
        <path d="M54 40 V30 H104 V40 M68 30 Q79 14 90 30 M79 22 V18 M56 30 Q60 23 64 30 M94 30 Q98 23 102 30"/>`,
    AUSTIN: `
        <path d="M26 40 V31 H52 V40 M30 31 Q39 17 48 31 M39 19 V11"/>
        <path d="M70 40 V18 L77 11 L84 18 V40 M77 11 V6"/>`,
    ATLANTA: `
        <path d="M38 40 V17 L45 10 L52 17 V40 M45 10 V3"/>
        <path d="M62 40 V25 H72 V40 M78 40 V29 H88 V40"/>`,
    MIAMI: `
        <path d="M22 40 C20 31 21 25 24 19"/>
        <path d="M24 19 C19 16 14 16 10 19 M24 19 C21 13 17 11 13 12 M24 19 C29 13 34 12 37 14"/>
        <path d="M50 40 V24 H82 V40 M60 24 V14 H72 V24 M66 14 V8 M50 30 H82 M50 35 H82"/>
        <path d="M88 35 Q94 29 100 35 Q106 41 112 35"/>`,
    DALLAS: `
        <path d="M34 40 V19"/>
        <circle cx="34" cy="13" r="5.5"/>
        <path d="M64 40 V16 L88 24 V40 M72 40 V19 M80 40 V21"/>`,
    HOUSTON: `
        <path d="M30 38 V16 L34 7 L38 16 V38 M30 38 L26 40 M38 38 L42 40 M30 24 H38 M30 31 H38"/>
        <path d="M60 40 V18 H70 V40 M74 40 V24 L79 19 L84 24 V40 M88 40 V28 H96 V40"/>`,
    SAN_ANTONIO: `
        <path d="M36 40 V26 H45 Q48 26 49 21 Q52 15 60 15 Q68 15 71 21 Q72 26 75 26 H84 V40"/>
        <path d="M55 40 V33 Q60 27 65 33 V40"/>`,
    NASHVILLE: `
        <path d="M50 40 V22 H70 V40 M53 22 V7 M67 22 V7 M53 22 Q60 14 67 22"/>
        <path d="M82 40 V30 H92 V40"/>`,
    WASHINGTON_DC: `
        <path d="M28 40 V13 L31 7 L34 13 V40"/>
        <path d="M56 40 V33 H96 V40 M62 33 Q76 15 90 33 M76 18 V10"/>`,
    DENVER: `
        <path d="M8 40 L26 16 L38 30 L52 12 L66 30 L76 22 L88 34"/>
        <path d="M94 40 V29 H102 V40 M106 40 V25 H112 V40"/>`,
    PHILADELPHIA: `
        <path d="M52 40 V17 H68 V40 M52 17 L60 6 L68 17 M60 6 V2"/>
        <circle cx="60" cy="25" r="3.5"/>
        <path d="M32 40 V28 H42 V40 M78 40 V24 H88 V40"/>`,
    ORLANDO: `
        <circle cx="44" cy="21" r="12"/>
        <path d="M44 9 V33 M32 21 H56 M36 13 L52 29 M52 13 L36 29 M37 40 L44 22 L51 40"/>
        <path d="M86 40 C84 32 85 27 88 22 M88 22 C84 19 80 19 77 21 M88 22 C92 17 96 16 99 18"/>`,
    SAN_DIEGO: `
        <path d="M8 34 Q36 14 64 34 M18 27 V40 M32 21 V40 M46 21 V40 M58 28 V40"/>
        <path d="M88 40 C86 31 87 25 90 19 M90 19 C85 16 80 16 76 19 M90 19 C94 13 99 12 103 14"/>`,
    TAMPA: `
        <path d="M38 40 V28 H82 V40 M44 28 V19 M60 28 V13 M76 28 V19"/>
        <path d="M41 19 Q44 13 47 19 Z M57 13 Q60 6 63 13 Z M73 19 Q76 13 79 19 Z M44 13 V10 M60 6 V2 M76 13 V10"/>
        <path d="M88 35 Q94 29 100 35 Q106 41 112 35"/>`,
    LAS_VEGAS: `
        <path d="M14 26 L32 18 L50 26 L32 34 Z M26 31 V40 M38 31 V40 M32 9 V15 M29 12 H35"/>
        <path d="M82 40 L84 17 M90 40 L88 17 M80 17 H92 V12 H80 Z M86 12 V3"/>`,
    DETROIT: `
        <path d="M54 40 V8 H66 V40 M54 14 H66"/>
        <path d="M42 40 V16 H52 V40 M68 40 V16 H78 V40"/>
        <path d="M32 40 V22 H40 V40 M80 40 V22 H88 V40"/>`,
    OTHER: `
        <path d="M28 37 H38 M48 37 H58 M68 37 H78"/>
        <circle cx="96" cy="19" r="5"/>
        <path d="M96 24 V32"/>`,
};

/** What each drawing shows — captioned on the card for readers who don't know the city. */
const CITY_LANDMARKS = {
    SAN_FRANCISCO: "Golden Gate Bridge · Transamerica Pyramid",
    PHOENIX: "Saguaro cactus · Camelback Mountain",
    LOS_ANGELES: "Palm tree · Griffith Observatory",
    AUSTIN: "Texas State Capitol · Frost Bank Tower",
    ATLANTA: "Bank of America Plaza",
    MIAMI: "Palm tree · Art Deco hotel · the ocean",
    DALLAS: "Reunion Tower · Fountain Place",
    HOUSTON: "Saturn V rocket (\u201cSpace City\u201d) · downtown towers",
    SAN_ANTONIO: "The Alamo",
    NASHVILLE: "AT&T Building (\u201cBatman Building\u201d)",
    WASHINGTON_DC: "Washington Monument · U.S. Capitol",
    DENVER: "Rocky Mountains",
    PHILADELPHIA: "City Hall",
    ORLANDO: "The Wheel at ICON Park · palm tree",
    SAN_DIEGO: "Coronado Bridge · palm tree",
    TAMPA: "Minarets of Plant Hall, University of Tampa",
    LAS_VEGAS: "\u201cWelcome to Fabulous Las Vegas\u201d sign · the STRAT tower",
    DETROIT: "Renaissance Center",
};

/** Wrap a metro's art paths in a consistently-styled SVG. */
function cityArtSVG(code) {
    const art = CITY_ART[code] || CITY_ART.OTHER;
    const label = CITY_LANDMARKS[code];
    return `<svg viewBox="0 0 120 44" fill="none" stroke="currentColor"
        stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
        ${label ? `role="img" aria-label="Line drawing: ${label}"` : 'aria-hidden="true"'}>
        ${label ? `<title>${label}</title>` : ""}<path d="M8 40 H112" opacity="0.45"/>${art}</svg>`;
}

// ============================================
// Dynamic City Cards
// ============================================

/** Cities with fewer driverless crashes than this go in the one-line "also" list. */
const CITY_CARD_MIN_CRASHES = 10;

/**
 * Build the city cards in #city-cards-container, plus the "also" line
 * for smaller metros. Each card shows the crash count and share; where
 * Waymo publishes mileage, the crash rate per million miles and Waymo's
 * own injury-crash comparison with human drivers (with its 95% CI).
 *
 * @param {Object} stats — site-data.json
 */
function buildCityCards(stats) {
    const container = document.getElementById("city-cards-container");
    if (!container || !stats.city_breakdown) return;

    const sorted = Object.entries(stats.city_breakdown).sort(
        (a, b) => b[1].count - a[1].count
    );
    const bench = (stats.benchmarks && stats.benchmarks.by_metro) || {};
    const small = [];

    sorted.forEach(([cityName, info]) => {
        if (info.count < CITY_CARD_MIN_CRASHES || info.code === "OTHER") {
            small.push([cityName, info]);
            return;
        }
        const mileage = stats.city_mileage ? stats.city_mileage[cityName] : null;
        const meta = stats.cities ? stats.cities[info.code] : null;
        const injury = bench[cityName] && bench[cityName].any_injury;

        let detailHTML = "";
        if (mileage && mileage.miles_millions) {
            detailHTML += `<div class="city-card-miles">${mileage.miles_millions.toFixed(1)}M driverless miles</div>`;
            if (mileage.crashes_per_million_miles !== null) {
                detailHTML += `<div class="city-card-rate"><strong>${mileage.crashes_per_million_miles}</strong> crashes per million miles</div>`;
            }
        } else {
            detailHTML += `<div class="city-card-miles city-card-muted">Mileage not yet published</div>`;
        }
        if (injury && injury.reduction_pct !== null) {
            detailHTML += `<div class="city-card-bench" title="Waymo's analysis; 95% confidence interval ${injury.reduction_ci_low}–${injury.reduction_ci_high}%">
                ${Math.round(injury.reduction_pct)}% fewer injury crashes than human drivers
                <span class="city-card-ci">(${Math.round(injury.reduction_ci_low)}–${Math.round(injury.reduction_ci_high)}%)</span></div>`;
        }
        const launched = meta && meta.launched ? formatMonth(meta.launched) : null;

        const card = document.createElement("div");
        card.className = "city-card";
        card.innerHTML = `
            <div class="city-card-art">${cityArtSVG(info.code)}</div>
            ${CITY_LANDMARKS[info.code] ? `<div class="city-card-landmark">${CITY_LANDMARKS[info.code]}</div>` : ""}
            <h3 class="city-card-name">${cityName}</h3>
            ${launched ? `<div class="city-card-since">Public since ${launched}</div>` : ""}
            <div class="city-card-count">${info.count.toLocaleString("en-US")}</div>
            <div class="city-card-label">crashes (${info.percentage}%)</div>
            ${detailHTML}
        `;
        container.appendChild(card);
    });

    const also = document.getElementById("city-also");
    if (also && small.length) {
        const parts = small.map(([cityName, info]) => {
            const note = info.status === "testing" ? " (testing)"
                : info.code === "OTHER" ? " (outside Waymo's metros)" : "";
            return `${cityName} ${info.count.toLocaleString("en-US")}${note}`;
        });
        also.innerHTML = `<span class="city-also-label">Also:</span> ${parts.join(" &middot; ")}`;
    }

    const mileageCount = document.getElementById("mileage-metro-count");
    if (mileageCount && stats.city_mileage) {
        const n = Object.values(stats.city_mileage).filter((m) => m.miles_millions).length;
        mileageCount.textContent = numberWord(n);
    }
}

/** "2024-03" → "March 2024" */
function formatMonth(yearMonth) {
    const [year, month] = yearMonth.split("-");
    const names = ["January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December"];
    return `${names[parseInt(month, 10) - 1]} ${year}`;
}

/** Spell out small numbers, AP style. */
function numberWord(n) {
    const words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
    return n < 10 ? words[n] : String(n);
}

/**
 * The fatal-crash list is written by an editor (it needs judgment about
 * fault), so it can fall behind the data. This compares the list with
 * stats.fatal_crashes and appends any crash the editor hasn't covered yet,
 * using only the facts from the federal report — the page never shows a
 * stale count.
 *
 * @param {Object} stats — site-data.json
 */
function buildFatalList(stats) {
    const list = document.getElementById("fatal-list");
    if (!list || !stats.fatal_crashes) return;
    const documented = new Set(
        [...list.querySelectorAll("li[data-report-id]")].map((li) => li.dataset.reportId)
    );
    stats.fatal_crashes
        .filter((c) => !documented.has(c.report_id))
        .forEach((c) => {
            const li = document.createElement("li");
            li.className = "fatal-pending";
            const speed = c.speed_mph !== null ? ` at ${c.speed_mph} mph` : "";
            li.innerHTML = `<strong>${c.city || c.metro}, ${c.month_label}.</strong>
                Newly reported; details under review. From the federal report: the Waymo was
                ${(c.sv_movement || "in an unknown state").toLowerCase()}${speed}; the other party
                was a ${(c.crash_with || "road user").replace("Non-Motorist: ", "").toLowerCase()}
                (report ${c.report_id}).`;
            list.appendChild(li);
        });
}

/**
 * Waymo-vs-human comparison rows (#benchmark-rows), one per outcome, from
 * stats.benchmarks.overall (hub CSV3). Each row draws the 95% confidence
 * interval as a bar on a 0–100% "fewer crashes" scale with a dot at the
 * estimate, plus the underlying counts.
 *
 * @param {Object} stats — site-data.json
 */
function buildBenchmarkRows(stats) {
    const container = document.getElementById("benchmark-rows");
    if (!container || !stats.benchmarks || !stats.benchmarks.overall) return;
    const overall = stats.benchmarks.overall;
    const ROWS = [
        { key: "serious_injury", label: "Serious-injury or fatal crashes" },
        { key: "fatal", label: "Fatal crashes" },
        { key: "airbag", label: "Crashes with an airbag deployment" },
        { key: "any_injury", label: "Crashes with any injury" },
        { key: "police", label: "Police-reported crashes" },
    ];
    container.innerHTML = ROWS.filter((r) => overall[r.key]).map((r) => {
        const b = overall[r.key];
        const lo = Math.max(0, b.reduction_ci_low);
        const hi = Math.min(100, b.reduction_ci_high);
        const fmt = (n) => n.toLocaleString("en-US", { maximumFractionDigits: 0 });
        return `
            <div class="bench-row" role="row">
                <div class="bench-label" role="rowheader">${r.label}</div>
                <div class="bench-viz" role="cell" aria-label="${Math.round(b.reduction_pct)}% fewer, 95% confidence interval ${Math.round(b.reduction_ci_low)} to ${Math.round(b.reduction_ci_high)}%">
                    <div class="bench-track">
                        <div class="bench-ci" style="left:${lo}%;width:${Math.max(hi - lo, 0.8)}%"></div>
                        <div class="bench-dot" style="left:${b.reduction_pct}%"></div>
                    </div>
                </div>
                <div class="bench-value" role="cell">
                    <strong>${Math.round(b.reduction_pct)}% fewer</strong>
                    <span class="bench-range">range ${Math.round(b.reduction_ci_low)}–${Math.round(b.reduction_ci_high)}%</span>
                    <span class="bench-counts">${fmt(b.waymo_count)} Waymo crashes vs. ~${fmt(b.predicted_human_count)} expected for human drivers</span>
                </div>
            </div>`;
    }).join("") + `
        <div class="bench-axis" aria-hidden="true"><span>0%</span><span>50%</span><span>100% fewer</span></div>`;
}

/**
 * "What we found": the rule-change finding shows the before/after rates
 * from the data, and the fatal finding falls back to neutral wording if
 * a fatal crash hasn't been reviewed by an editor yet (see buildFatalList).
 */
function fillFindings(stats) {
    const rule = document.getElementById("finding-rule-change");
    const qr = stats.quarterly_rates;
    const rows = qr && qr.series && qr.series["All metros"];
    if (rule && rows && rows.length) {
        const before = rows.filter((r) => r.quarter <= qr.amendment_3_quarter);
        const after = rows.filter((r) => r.quarter > qr.amendment_3_quarter);
        const avg = (list) => list.reduce((sum, r) => sum + r.crashes_per_million, 0) / list.length;
        if (before.length && after.length) {
            rule.textContent = `${avg(before).toFixed(1)} → ${avg(after).toFixed(1)}`;
            rule.title = "Reported crashes per million miles, average per quarter before and after June 16, 2025";
        }
    }
    const fatal = document.getElementById("finding-fatal");
    const list = document.getElementById("fatal-list");
    if (fatal && list && list.querySelector(".fatal-pending")) {
        fatal.innerHTML = "<strong>crashes involved a death. The newest is still under review;</strong> in the earlier ones, another road user hit the Waymo or was thrown into it.";
    }
}

/** Hero line: what the latest weekly update added (from update_history.json). */
async function showLatestUpdate() {
    const el = document.getElementById("hero-latest");
    if (!el) return;
    try {
        const history = await DataLoader.fetchJSON("update_history.json");
        const last = [...history].reverse().find((h) => h.new_crashes > 0);
        if (!last) return;
        const date = new Date(last.date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
        el.textContent = `Latest update (${date}): +${last.new_crashes} crashes`;
    } catch (e) {
        /* optional — the hero works without it */
    }
}

/** Numbers in the safety section that need a little arithmetic. */
function fillSafetyNumbers(stats) {
    const el = document.getElementById("quarterly-latest-miles");
    const series = stats.quarterly_rates && stats.quarterly_rates.series
        && stats.quarterly_rates.series["All metros"];
    if (el && series && series.length) {
        el.textContent = Math.round(series[series.length - 1].miles_millions);
    }
}

/**
 * Render every driverless crash as a single colored square, grouped by
 * the worst injury reported. The point is scale: a bar chart says "1%
 * serious"; the waffle lets you SEE 17 red squares in a field of 1,600.
 *
 * @param {Array} crashes — crash_data.json records
 */
function buildSeverityWaffle(crashes) {
    const grid = document.getElementById("severity-waffle");
    const legend = document.getElementById("severity-waffle-legend");
    if (!grid || !crashes) return;

    // Severity tiers, most severe first so they sit top-left where the
    // eye starts — they'd be invisible buried at the bottom.
    const TIERS = [
        { key: "fatal",    label: "Fatal",            color: "#1a1a1a" },
        { key: "serious",  label: "Serious injury",   color: "#8b2020" },
        { key: "moderate", label: "Moderate injury",  color: "#b5573a" },
        { key: "minor",    label: "Minor injury",     color: "#c4841d" },
        { key: "none",     label: "No injury reported", color: "#ddd6cb" },
    ];

    const counts = {};
    crashes.forEach((crash) => {
        if (crash.operation_type === "supervised") return;  // headline dataset only
        counts[crash.severity_level] = (counts[crash.severity_level] || 0) + 1;
    });

    // One <span> per crash; built as a single string for fast rendering
    let cells = "";
    TIERS.forEach((tier) => {
        const n = counts[tier.key] || 0;
        for (let i = 0; i < n; i++) {
            cells += `<span class="waffle-cell" style="background:${tier.color}"></span>`;
        }
    });
    grid.innerHTML = cells;

    if (legend) {
        legend.innerHTML = TIERS.map((tier) => {
            const n = counts[tier.key] || 0;
            return `<span class="waffle-legend-item"><span class="waffle-swatch" style="background:${tier.color}"></span>${tier.label} &middot; ${n.toLocaleString("en-US")}</span>`;
        }).join("");
    }
}

// ============================================
// Error Display
// ============================================

/**
 * Show an error message overlay if data loading fails.
 * This helps the user understand what went wrong.
 */
function showError(message) {
    // Get a reference to the <body> element
    const body = document.body;
    // Create a new <div> to hold the error message
    const errorDiv = document.createElement("div");
    // Give it a CSS class for styling (red overlay, centered text, etc.)
    errorDiv.className = "error-overlay";
    // Fill in the error message using a template literal
    errorDiv.innerHTML = `
        <div class="error-content">
            <h2>Data Loading Error</h2>
            <p>${message}</p>
            <p>Make sure you've run the data pipeline first:</p>
            <code>make data</code>
            <p>Then start the server:</p>
            <code>make serve</code>
        </div>
    `;
    // Insert the error at the very top of the page (before all other content)
    body.insertBefore(errorDiv, body.firstChild);
}
