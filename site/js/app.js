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

        // Step 3: Build dynamic city cards in the spatial section
        buildCityCards(data.stats);

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
        // If peak data exists use it, otherwise show "N/A"
        const peakLabel = peak ? peak.peak_label : "N/A";

        // Look up mileage data for this city (if available)
        const mileage = stats.city_mileage ? stats.city_mileage[cityName] : null;

        // Create a new <div> element to hold this city's card
        const card = document.createElement("div");
        // Give it a CSS class so our stylesheet can style it
        card.className = "city-card";

        // Build mileage lines — only show if we have miles data
        let mileageHTML = "";
        if (mileage && mileage.miles_millions !== null) {
            // .toFixed(1) rounds to 1 decimal place: 56.535 → "56.5"
            const milesFormatted = mileage.miles_millions.toFixed(1) + "M";
            // Template literal (backtick string): ${...} inserts a variable's value into the string
            mileageHTML += `<div class="city-card-miles">${milesFormatted} miles driven</div>`;
            if (mileage.crashes_per_million_miles !== null) {
                // Similar to above — insert crash rate into the HTML string
                mileageHTML += `<div class="city-card-rate">${mileage.crashes_per_million_miles} crashes per M miles</div>`;
            }
        }

        // Set the card's inner HTML using a template literal with embedded variables
        // .toLocaleString("en-US") formats 1123 as "1,123" with commas
        card.innerHTML = `
            <h3 class="city-card-name">${cityName}</h3>
            <div class="city-card-count">${info.count.toLocaleString("en-US")}</div>
            <div class="city-card-label">crashes (${info.percentage}%)</div>
            ${mileageHTML}
            <div class="city-card-peak">Peak: ${peakLabel}</div>
        `;

        // Add the finished card into the container on the page
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
