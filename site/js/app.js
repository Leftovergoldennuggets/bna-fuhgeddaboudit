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
        Charts.buildMileageChart(data.mileageMilestones);  // Line chart: rider-only miles over time
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
        <circle cx="98" cy="13" r="6"/>
        <path d="M32 40 V13 M32 25 H25 V16 M32 29 H39 V20"/>
        <path d="M56 40 L61 31 H77 L82 40 M64 31 V26 H74 V31"/>`,
    LOS_ANGELES: `
        <path d="M28 40 C26 30 27 23 30 16"/>
        <path d="M30 16 C24 13 18 13 14 17 M30 16 C27 10 22 7 17 8 M30 16 C35 10 40 8 44 10 M30 16 C36 13 42 14 45 18"/>
        <path d="M66 40 V28 H76 V40 M82 40 V20 H92 V40 M98 40 V30 H106 V40"/>`,
    AUSTIN: `
        <path d="M26 40 V31 H52 V40 M30 31 Q39 17 48 31 M39 19 V11"/>
        <path d="M70 40 V18 L77 11 L84 18 V40 M77 11 V6"/>`,
    ATLANTA: `
        <path d="M38 40 V17 L45 10 L52 17 V40 M45 10 V3"/>
        <path d="M62 40 V25 H72 V40 M78 40 V29 H88 V40"/>`,
    MIAMI: `
        <path d="M24 40 C22 31 23 25 26 19"/>
        <path d="M26 19 C21 16 16 16 12 19 M26 19 C23 13 19 11 15 12 M26 19 C31 13 36 12 39 14"/>
        <path d="M56 40 V25 H61 V17 H69 V25 H74 V40 M65 17 V10"/>
        <path d="M84 35 Q90 29 96 35 Q102 41 108 35"/>`,
    DALLAS: `
        <path d="M34 40 V19"/>
        <circle cx="34" cy="13" r="5.5"/>
        <path d="M64 40 V16 L88 24 V40 M72 40 V19 M80 40 V21"/>`,
    HOUSTON: `
        <path d="M28 40 V23 H38 V40 M44 40 V12 H56 V40 M48 12 V7 M62 40 V26 H72 V40 M78 40 V18 H88 V40"/>`,
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
    OTHER: `
        <path d="M28 37 H38 M48 37 H58 M68 37 H78"/>
        <circle cx="96" cy="19" r="5"/>
        <path d="M96 24 V32"/>`,
};

/** Wrap a metro's art paths in a consistently-styled SVG. */
function cityArtSVG(code) {
    const art = CITY_ART[code] || CITY_ART.OTHER;
    return `<svg viewBox="0 0 120 44" fill="none" stroke="currentColor"
        stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
        aria-hidden="true"><path d="M8 40 H112" opacity="0.45"/>${art}</svg>`;
}

// ============================================
// Dynamic City Cards
// ============================================

/**
 * Build city breakdown cards in the #city-cards-container.
 * Each card shows a city name, crash count, percentage, miles driven,
 * crash rate per million miles, and peak hour.
 *
 * @param {Object} stats — site-data.json
 */
function buildCityCards(stats) {
    // Find the HTML element where city cards should go
    const container = document.getElementById("city-cards-container");
    // If the container doesn't exist on this page, or there's no city data, stop here
    if (!container || !stats.city_breakdown) return;

    // Object.entries() converts {SF: {...}, LA: {...}} into [["SF", {...}], ["LA", {...}]]
    // .sort() reorders so the city with the most crashes comes first
    const sorted = Object.entries(stats.city_breakdown).sort(
        // Arrow function comparing two cities' crash counts (b - a = descending order)
        (a, b) => b[1].count - a[1].count
    );

    // .forEach() loops through every [cityName, info] pair in the sorted array
    // For this part we consulted Claude who recommended destructuring assignment — a
    // shorthand that unpacks an array into named variables in one line. Instead of writing
    // `const stats = results[0]; const crashData = results[1]; const incidents = results[2];`
    // we can write it all in one line. The variable names are matched by position: first
    // item goes to the first name, second to the second, and so on.
    sorted.forEach(([cityName, info]) => {

        // Look up peak hour for this city (if available)
        const peak = stats.city_peaks ? stats.city_peaks[cityName] : null;

        // Look up mileage data for this city (if available)
        const mileage = stats.city_mileage ? stats.city_mileage[cityName] : null;

        // Create a new <div> element to hold this city's card
        const card = document.createElement("div");
        // Give it a CSS class so our stylesheet can style it
        card.className = "city-card";

        // Build mileage lines — only show if we have miles data
        let mileageHTML = "";
        if (mileage && mileage.miles_millions !== null && mileage.miles_millions !== undefined) {
            // .toFixed(1) rounds to 1 decimal place: 56.535 → "56.5"
            const milesFormatted = mileage.miles_millions.toFixed(1) + "M";
            // Template literal (backtick string): ${...} inserts a variable's value into the string
            mileageHTML += `<div class="city-card-miles">${milesFormatted} miles driven</div>`;
            if (mileage.crashes_per_million_miles !== null) {
                // Similar to above — insert crash rate into the HTML string
                mileageHTML += `<div class="city-card-rate">${mileage.crashes_per_million_miles} crashes per M miles</div>`;
            }
        }

        // Status note for metros without open public service, and for the
        // catch-all "Other" bucket (supervised testing locations, etc.)
        let statusHTML = "";
        if (info.status === "testing") {
            statusHTML = `<div class="city-card-status">Driverless testing — service not yet open</div>`;
        } else if (info.code === "OTHER") {
            statusHTML = `<div class="city-card-status">Outside mapped metro areas</div>`;
        }

        // Peak hour line — only shown when there's enough data to compute it
        const peakHTML = peak ? `<div class="city-card-peak">Peak: ${peak.peak_label}</div>` : "";

        // Set the card's inner HTML using a template literal with embedded variables
        // .toLocaleString("en-US") formats 1123 as "1,123" with commas
        card.innerHTML = `
            <div class="city-card-art">${cityArtSVG(info.code)}</div>
            <h3 class="city-card-name">${cityName}</h3>
            <div class="city-card-count">${info.count.toLocaleString("en-US")}</div>
            <div class="city-card-label">crashes (${info.percentage}%)</div>
            ${mileageHTML}
            ${peakHTML}
            ${statusHTML}
        `;

        // Add the finished card into the container on the page
        container.appendChild(card);
    });
}

// ============================================
// Severity Waffle — one square per crash
// ============================================

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
