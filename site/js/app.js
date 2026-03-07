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
document.addEventListener("DOMContentLoaded", async function () {
    console.log("[App] Starting Waymo Crash Data Analysis...");

    try {
        // Step 1: Load all data files
        const data = await DataLoader.loadAll();

        // Step 2: Fill in all data-stat placeholders with real numbers
        StatRenderer.renderAll(data.stats);

        // Step 3: Build dynamic city cards in the spatial section
        buildCityCards(data.stats);

        // Step 4: Initialize the scrollytelling map
        MapController.init(data.crashes, data.incidents, data.stats);

        // Step 5: Initialize scroll-driven transitions
        Scrollytelling.init();

        // Step 6: Build interactive charts (replaces static PNG images)
        Charts.buildHourlyChart(data.stats);
        Charts.buildDayOfWeekChart(data.stats);
        Charts.buildLocationTypeChart(data.stats);

        // Step 7: Initialize the interactive explore section
        Explore.init(data.crashes, data.stats);

        console.log("[App] All modules initialized successfully");
    } catch (error) {
        console.error("[App] Failed to initialize:", error);
        showError(error.message);
    }
});

// ============================================
// Dynamic City Cards
// ============================================

/**
 * Build city breakdown cards in the #city-cards-container.
 * Each card shows a city name, crash count, percentage, and peak hour.
 *
 * @param {Object} stats — site-data.json
 */
function buildCityCards(stats) {
    const container = document.getElementById("city-cards-container");
    if (!container || !stats.city_breakdown) return;

    // Sort cities by crash count (highest first)
    const sorted = Object.entries(stats.city_breakdown).sort(
        (a, b) => b[1].count - a[1].count
    );

    sorted.forEach(([cityName, info]) => {
        // Look up peak hour for this city (if available)
        const peak = stats.city_peaks ? stats.city_peaks[cityName] : null;
        const peakLabel = peak ? peak.peak_label : "N/A";

        const card = document.createElement("div");
        card.className = "city-card";

        card.innerHTML = `
            <h3 class="city-card-name">${cityName}</h3>
            <div class="city-card-count">${info.count.toLocaleString("en-US")}</div>
            <div class="city-card-label">crashes (${info.percentage}%)</div>
            <div class="city-card-peak">Peak: ${peakLabel}</div>
        `;

        container.appendChild(card);
    });
}

// ============================================
// Error Display
// ============================================

/**
 * Show an error message overlay if data loading fails.
 * This helps the user understand what went wrong.
 */
function showError(message) {
    const body = document.body;
    const errorDiv = document.createElement("div");
    errorDiv.className = "error-overlay";
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
    body.insertBefore(errorDiv, body.firstChild);
}
