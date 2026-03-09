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
const DataLoader = (function () {

    // Base paths to the JSON data files.
    // Locally: site is served from project root, HTML is in site/, data is in data/
    //   → path from site/ to data/web/ is "../data/web/"
    //   → path from site/ to data/static/ is "../data/static/"
    // GitHub Pages: the deploy workflow copies data into the site folder
    //   → paths are just "data/web/" and "data/static/"
    // We detect which environment we're in by checking the hostname.
    const isGitHubPages = window.location.hostname.includes("github.io");
    const DATA_BASE = isGitHubPages ? "data/web/" : "../data/web/";
    const STATIC_BASE = isGitHubPages ? "data/static/" : "../data/static/";

    /**
     * Fetch a single JSON file and return its parsed contents.
     * Throws a clear error message if the fetch fails.
     *
     * @param {string} filename — The JSON filename to load
     * @param {string} [base] — Base path override (defaults to DATA_BASE)
     */
    async function fetchJSON(filename, base) {
        const url = (base || DATA_BASE) + filename;
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(
                    `Failed to load ${filename}: HTTP ${response.status}. ` +
                    `Make sure you've run the data pipeline (make data).`
                );
            }
            return await response.json();
        } catch (error) {
            console.error(`[DataLoader] Error loading ${filename}:`, error);
            throw error;
        }
    }

    /**
     * Load all data files in parallel.
     * Returns an object with stats, crashes, incidents, and static mileage data.
     */
    async function loadAll() {
        console.log("[DataLoader] Loading data files...");

        // Fetch all files at the same time (faster than one-by-one)
        // Static files (mileage) are optional — site works without them
        const [stats, crashes, incidents, mileageMilestones, milesByCity] = await Promise.all([
            fetchJSON("site-data.json"),
            fetchJSON("crash_data.json"),
            fetchJSON("serious_incidents.json"),
            fetchJSON("mileage_milestones.json", STATIC_BASE).catch(() => null),
            fetchJSON("miles_by_city.json", STATIC_BASE).catch(() => null),
        ]);

        console.log("[DataLoader] All data loaded successfully");
        console.log(`  Stats: ${Object.keys(stats).length} top-level keys`);
        console.log(`  Crashes: ${crashes.length} records`);
        console.log(`  Incidents: ${incidents.total_serious} serious incidents`);
        if (mileageMilestones) console.log(`  Mileage milestones: ${mileageMilestones.milestones.length} entries`);
        if (milesByCity) console.log(`  Miles by city: ${Object.keys(milesByCity.cities).length} cities`);

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
        // Split on dots, but handle keys with spaces (like "San Francisco")
        // by trying progressively longer key segments
        const parts = path.split(".");
        let current = obj;

        let i = 0;
        while (i < parts.length && current !== undefined && current !== null) {
            // Try single part first
            if (current[parts[i]] !== undefined) {
                current = current[parts[i]];
                i++;
            } else {
                // Try combining parts (for keys with dots that aren't separators)
                // e.g., "city_breakdown.San Francisco.count" where "San Francisco" has a space
                let found = false;
                for (let j = i + 1; j <= parts.length; j++) {
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
                        const spaceKey = parts.slice(i, j).join(" ");
                        if (current[spaceKey] !== undefined) {
                            current = current[spaceKey];
                            i = j;
                            spaceFound = true;
                            break;
                        }
                    }
                    if (!spaceFound) {
                        console.warn(`[DataLoader] Could not resolve path: "${path}" (stuck at "${parts[i]}")`);
                        return undefined;
                    }
                }
            }
        }

        return current;
    }

    // Public API
    return { loadAll, resolve, fetchJSON };
})();
