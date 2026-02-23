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

    // Base path to the JSON data files (relative to site/ directory)
    const DATA_BASE = "../data/web/";

    /**
     * Fetch a single JSON file and return its parsed contents.
     * Throws a clear error message if the fetch fails.
     */
    async function fetchJSON(filename) {
        const url = DATA_BASE + filename;
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
     * Load all three data files in parallel.
     * Returns an object with stats, crashes, and incidents.
     */
    async function loadAll() {
        console.log("[DataLoader] Loading data files...");

        // Fetch all three files at the same time (faster than one-by-one)
        const [stats, crashes, incidents] = await Promise.all([
            fetchJSON("site-data.json"),
            fetchJSON("crash_data.json"),
            fetchJSON("serious_incidents.json"),
        ]);

        console.log("[DataLoader] All data loaded successfully");
        console.log(`  Stats: ${Object.keys(stats).length} top-level keys`);
        console.log(`  Crashes: ${crashes.length} records`);
        console.log(`  Incidents: ${incidents.total_serious} serious incidents`);

        return { stats, crashes, incidents };
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
