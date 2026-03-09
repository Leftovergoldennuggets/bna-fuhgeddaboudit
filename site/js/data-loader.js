/**
 * data-loader.js — Fetch and parse all JSON data files
 * =====================================================
 * Loads three JSON files that the data pipeline generates:
 *   1. site-data.json   — All computed statistics for the website
 *   2. crash_data.json  — Individual crash records for the Leaflet map
 *   3. serious_incidents.json — Filtered serious/fatal incident details
 *
 * These files live in data/web/ at the project root.
 * The website is served from site/, so paths use "../data/web/".
 *
 * Usage:
 *   const data = await DataLoader.loadAll();
 *   // data.stats   → site-data.json contents
 *   // data.crashes  → crash_data.json contents (array of crash records)
 *   // data.incidents → serious_incidents.json contents
 */

// ============================================
// DataLoader Module
// ============================================

// For this part we consulted Claude who recommended the IIFE (Immediately Invoked Function
// Expression) module pattern. This wraps all the code inside a function that runs once
// immediately. The outer parentheses `(function() { ... })()` create a private scope —
// variables declared inside cannot leak out or conflict with variables in other files.
// Only the object returned at the end (with `return { ... }`) is accessible from outside.
// This is how JavaScript developers organized code into modules before ES6 `import/export`
// became standard. Every JS file in this project except app.js uses this pattern.
const DataLoader = (function () {

    // Base paths to the JSON data files.
    // Locally: site is served from project root, HTML is in site/, data is in data/
    //   → path from site/ to data/web/ is "../data/web/"
    //   → path from site/ to data/static/ is "../data/static/"
    // GitHub Pages: the deploy workflow copies data into the site folder
    //   → paths are just "data/web/" and "data/static/"
    // We detect which environment we're in by checking the hostname.

    // Check if we're running on GitHub Pages (vs. local development)
    const isGitHubPages = window.location.hostname.includes("github.io");
    // Pick the right folder path depending on the environment
    const DATA_BASE = isGitHubPages ? "data/web/" : "../data/web/";
    const STATIC_BASE = isGitHubPages ? "data/static/" : "../data/static/"; // Similar to above

    /**
     * Fetch a single JSON file and return its parsed contents.
     * Throws a clear error message if the fetch fails.
     *
     * @param {string} filename — The JSON filename to load
     * @param {string} [base] — Base path override (defaults to DATA_BASE)
     */
    // "async" means this function can use "await" to pause while waiting for downloads
    async function fetchJSON(filename, base) {
        // Build the full URL by combining the base path with the filename
        const url = (base || DATA_BASE) + filename;
        try {
            // "await fetch(url)" downloads the file and pauses until it arrives
            const response = await fetch(url);
            // Check if the server returned an error (404 not found, 500 server error, etc.)
            if (!response.ok) {
                throw new Error(
                    `Failed to load ${filename}: HTTP ${response.status}. ` +
                    `Make sure you've run the data pipeline (make data).`
                );
            }
            // Parse the downloaded text as JSON and return the resulting object
            return await response.json();
        } catch (error) {
            console.error(`[DataLoader] Error loading ${filename}:`, error);
            // Re-throw so the caller knows something went wrong
            throw error;
        }
    }

    /**
     * Load all data files in parallel.
     * Returns an object with stats, crashes, incidents, and static mileage data.
     */
    async function loadAll() {
        console.log("[DataLoader] Loading data files...");

        // For this part we consulted Claude who recommended using Promise.all to fetch
        // multiple JSON files simultaneously instead of one after another. Without this,
        // loading 3 files would take 3× as long because each would wait for the previous
        // one to finish. Promise.all starts ALL fetches at the same time and waits until
        // every single one has completed. The `await` keyword pauses this function until
        // all results are back. If any fetch fails, the `.catch(() => null)` on each
        // individual fetch prevents the whole group from failing — it just returns null
        // for that file so the site can still work with partial data.
        const [stats, crashes, incidents, mileageMilestones, milesByCity] = await Promise.all([
            fetchJSON("site-data.json"),
            fetchJSON("crash_data.json"),
            fetchJSON("serious_incidents.json"),
            // .catch(() => null) — if this file fails to load, return null instead of crashing
            fetchJSON("mileage_milestones.json", STATIC_BASE).catch(() => null),
            fetchJSON("miles_by_city.json", STATIC_BASE).catch(() => null), // Similar to above
        ]);

        // Log what we loaded so we can verify in the browser console
        console.log("[DataLoader] All data loaded successfully");
        console.log(`  Stats: ${Object.keys(stats).length} top-level keys`);
        console.log(`  Crashes: ${crashes.length} records`);
        console.log(`  Incidents: ${incidents.total_serious} serious incidents`);
        // Only log optional files if they actually loaded
        if (mileageMilestones) console.log(`  Mileage milestones: ${mileageMilestones.milestones.length} entries`);
        if (milesByCity) console.log(`  Miles by city: ${Object.keys(milesByCity.cities).length} cities`);

        // Return all loaded data as a single object with named properties
        return { stats, crashes, incidents, mileageMilestones, milesByCity };
    }

    /**
     * Resolve a dot-separated path like "overview.total_crashes"
     * into the actual value from a nested object.
     *
     * Example:
     *   resolve(stats, "city_breakdown.San Francisco.count")
     *   → 527
     */
    function resolve(obj, path) {
        // Split "overview.total_crashes" into ["overview", "total_crashes"]
        const parts = path.split(".");
        // Start at the top level of the object
        let current = obj;

        // Walk through each part of the path, drilling deeper into the object
        let i = 0;
        while (i < parts.length && current !== undefined && current !== null) {
            // Try single part first (e.g., "overview")
            if (current[parts[i]] !== undefined) {
                // Move one level deeper into the object
                current = current[parts[i]];
                i++;
            } else {
                // Try combining parts (for keys with dots that aren't separators)
                // e.g., "city_breakdown.San Francisco.count" where "San Francisco" has a space
                let found = false;
                for (let j = i + 1; j <= parts.length; j++) {
                    // Join parts with dots to try as a single key
                    const combinedKey = parts.slice(i, j).join(".");
                    if (current[combinedKey] !== undefined) {
                        current = current[combinedKey];
                        i = j;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    // Key with space — try joining with space instead of dot
                    let spaceFound = false;
                    for (let j = i + 1; j <= parts.length; j++) {
                        // Join parts with spaces: ["San", "Francisco"] → "San Francisco"
                        const spaceKey = parts.slice(i, j).join(" ");
                        if (current[spaceKey] !== undefined) {
                            // Similar to above — move deeper and advance the index
                            current = current[spaceKey];
                            i = j;
                            spaceFound = true;
                            break;
                        }
                    }
                    if (!spaceFound) {
                        // Give up — the path doesn't match anything in the data
                        console.warn(`[DataLoader] Could not resolve path: "${path}" (stuck at "${parts[i]}")`);
                        return undefined;
                    }
                }
            }
        }

        // Return whatever value we drilled down to
        return current;
    }

    // Public API — only these three functions are accessible outside the module
    return { loadAll, resolve, fetchJSON };
})();
