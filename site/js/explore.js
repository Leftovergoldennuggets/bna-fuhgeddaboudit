/**
 * explore.js — Interactive "Explore the Data" section
 * =====================================================
 * Manages the filter sidebar and a separate explore map where users
 * can filter crashes by severity, road user type, city, and time of day.
 *
 * Filter dimensions (designed for regular people, not experts):
 *   - Severity: All / Any injury / Serious only
 *   - Involved: All / Pedestrian / Cyclist / Motorcycle
 *   - City: All / San Francisco / Phoenix / LA / Austin / Atlanta
 *   - Time of day: All / Daytime / Night / Rush hour
 *
 * Dependencies:
 *   - Leaflet + MarkerCluster (from CDN)
 *   - map-controller.js (for formatCityName, formatHour, formatCrashType, CITY_COORDS)
 *   - data-loader.js (for crash data)
 */

// ============================================
// Explore Module
// ============================================

// IIFE module pattern — same as the other modules. See scrollytelling.js for full explanation.
const Explore = (function () {

    // --- Module State ---
    // These variables are private to this module (hidden inside the IIFE)
    let exploreMap = null;          // Separate Leaflet map for the explore section
    let exploreCluster = null;      // MarkerCluster group for filtered crash markers
    let allCrashes = [];            // Full crash dataset (every record from crash_data.json)
    let allMarkers = [];            // Parallel array: allMarkers[i] is the Leaflet marker for allCrashes[i]

    // For this part we consulted Claude who recommended JavaScript Set objects for tracking
    // active filters. A Set is like an array but with two key differences: (1) it
    // automatically prevents duplicates — adding "Phoenix" twice still results in just one
    // "Phoenix", and (2) checking if a value exists with .has() is instant (O(1) time)
    // regardless of how many items are in the Set, while array.includes() gets slower as
    // the array grows. The .add(), .delete(), and .clear() methods make it easy to toggle
    // filters on and off. When we need to convert back to an array (e.g., for filtering),
    // the spread operator [...set] does that.

    // Active filters — tracks what the user has selected
    let filters = {
        cities: new Set(),          // Selected city codes (e.g., "SAN_FRANCISCO", "PHOENIX")
        severity: null,             // null = "All" | "injury" | "serious" | "none" | "fatal"
        roadUser: null,             // null = "All" | "Pedestrian" | "Cyclist" | "Motorcycle"
        timeOfDay: null,            // null = "All" | "daytime" | "night" | "rush"
    };

    // Muted color palette — severity drives the marker color (earth tones)
    const MARKER_GREY = "#b0a696";   // No injury: warm grey
    const MARKER_AMBER = "#c4841d";  // Any injury: amber/orange
    const MARKER_RED = "#8b2020";    // Serious: deep red

    // ============================================
    // Initialize
    // ============================================

    /**
     * Set up the explore section: map, filters, and markers.
     *
     * @param {Array} crashes — crash_data.json (array of crash records)
     * @param {Object} stats  — site-data.json (for filter options)
     */
    function init(crashes, stats) {
        // Store the full crash dataset for filtering later
        allCrashes = crashes;

        // Create the explore map (separate from the scrollytelling map)
        initExploreMap();

        // Build one Leaflet marker per crash (stored in allMarkers array)
        buildMarkers();

        // Create the filter toggle buttons in the sidebar
        buildSeverityFilter();
        buildRoadUserFilter();
        buildCityFilter(stats);
        buildTimeFilter();

        // Set up the "Reset all filters" button
        const resetBtn = document.getElementById("reset-filters");
        if (resetBtn) {
            // When clicked, call the resetFilters function
            resetBtn.addEventListener("click", resetFilters);
        }

        // Show all markers on the map initially (no filters active)
        applyFilters();

        console.log("[Explore] Initialized with", crashes.length, "crashes");
    }

    // ============================================
    // Map Setup
    // ============================================

    function initExploreMap() {
        // L.map() creates a new Leaflet map — similar to MapController but for the explore section
        exploreMap = L.map("explore-map", {
            center: [37.0902, -95.7129],  // US center [latitude, longitude]
            zoom: 4,                       // Zoomed out to show all of the US
            zoomControl: true,             // Show the +/- zoom buttons
            scrollWheelZoom: true,         // Allow scroll wheel to zoom (unlike the scrollytelling map)
            attributionControl: true,      // Show map credits
        });

        // Base tiles: CARTO light without labels — same as the scrollytelling map
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
            {
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
                    '&copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: "abcd",
                maxZoom: 19,
            }
        ).addTo(exploreMap);  // .addTo() adds this tile layer to the explore map

        // Label layer on top — same pattern as MapController
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
            { subdomains: "abcd", maxZoom: 19, pane: "shadowPane" }
        ).addTo(exploreMap);

        // L.markerClusterGroup() groups nearby markers into clusters — same setup as MapController
        exploreCluster = L.markerClusterGroup({
            maxClusterRadius: 50,          // Cluster markers within 50 pixels
            showCoverageOnHover: false,    // Don't show cluster boundary on hover
            // Custom cluster icon styling — same pattern as MapController
            iconCreateFunction: function (cluster) {
                const count = cluster.getChildCount();
                let size = "small";
                if (count > 50) size = "large";
                else if (count > 20) size = "medium";
                // L.divIcon() creates a marker from HTML — see MapController for details
                return L.divIcon({
                    html: "<div><span>" + count + "</span></div>",
                    className: "marker-cluster marker-cluster-" + size,
                    iconSize: L.point(40, 40),
                });
            },
        });

        // .addLayer() puts the cluster group on the map so markers will be visible
        exploreMap.addLayer(exploreCluster);
    }

    // ============================================
    // Popup Content Builder
    // ============================================

    /**
     * Build enriched popup HTML for a crash marker.
     * Shows crash type, date/time, what each party was doing, speed,
     * injury severity, and a truncated narrative with "Read more" toggle.
     *
     * @param {Object} crash — a single crash record from crash_data.json
     * @returns {string} HTML string for the Leaflet popup
     */
    function buildPopupContent(crash) {
        const dateStr = crash.date || "Unknown date";
        const hourStr = crash.hour !== null
            ? MapController.formatHour(crash.hour)
            : "Unknown";

        // Start building the popup HTML
        let html = `<div class="crash-popup crash-popup-enriched">`;

        // Header: crash type + severity badge
        html += `<div class="popup-header">`;
        html += `<strong>${MapController.formatCrashType(crash.crash_type)}</strong>`;
        if (crash.is_serious) {
            html += ` <span class="popup-badge popup-badge-serious">Serious</span>`;
        } else if (crash.has_injury) {
            html += ` <span class="popup-badge popup-badge-injury">Injury</span>`;
        }
        html += `</div>`;

        // City, date, time
        html += `<span class="popup-city">${MapController.formatCityName(crash.city)}</span>`;
        html += ` &mdash; <span class="popup-date">${dateStr} at ${hourStr}</span><br>`;

        // Circumstances table: what each party was doing, speed, other party type
        // Only show if we have at least one enriched field
        if (crash.sv_movement || crash.cp_movement || crash.speed_mph !== null || crash.crash_with) {
            html += `<div class="popup-circumstances">`;

            // Speed at time of crash
            if (crash.speed_mph !== null) {
                html += `<div class="popup-detail"><span class="popup-detail-label">Waymo speed:</span> ${crash.speed_mph} mph</div>`;
            }

            // What Waymo was doing
            if (crash.sv_movement) {
                html += `<div class="popup-detail"><span class="popup-detail-label">Waymo action:</span> ${crash.sv_movement}</div>`;
            }

            // What the other party was doing
            if (crash.cp_movement) {
                html += `<div class="popup-detail"><span class="popup-detail-label">Other party:</span> ${crash.cp_movement}</div>`;
            }

            // What type of vehicle/person Waymo crashed with
            if (crash.crash_with) {
                html += `<div class="popup-detail"><span class="popup-detail-label">Crash with:</span> ${crash.crash_with}</div>`;
            }

            html += `</div>`;
        }

        // Injury severity (if any)
        if (crash.injury_severity && crash.injury_severity !== "No Apparent Injury") {
            const sevColor = crash.is_serious ? "#8b2020" : "#c4841d";
            html += `<div class="popup-severity" style="color:${sevColor}">${crash.injury_severity}</div>`;
        }

        // Location type
        html += `<span class="popup-type">Location: ${crash.location_type}</span>`;

        // Narrative — show first 200 chars with "Read more" toggle
        // For this part we consulted Claude who recommended using a unique ID per popup
        // to toggle the narrative expansion. Each popup gets an ID based on the crash's
        // lat/lon/date combination, which is unique enough to avoid collisions. The onclick
        // handler toggles the display between the truncated preview and the full narrative.
        if (crash.narrative) {
            const truncLen = 200;
            const needsTruncation = crash.narrative.length > truncLen;
            // Create a unique ID using lat + lon (remove dots to make a valid HTML id)
            const uid = "narr-" + String(crash.lat).replace(".", "") + String(crash.lon).replace(".", "");

            if (needsTruncation) {
                const preview = crash.narrative.substring(0, truncLen) + "...";
                html += `<div class="popup-narrative">`;
                html += `<span id="${uid}-short">${preview} <a href="#" onclick="document.getElementById('${uid}-short').style.display='none';document.getElementById('${uid}-full').style.display='inline';return false;" class="popup-readmore">Read more</a></span>`;
                html += `<span id="${uid}-full" style="display:none">${crash.narrative} <a href="#" onclick="document.getElementById('${uid}-full').style.display='none';document.getElementById('${uid}-short').style.display='inline';return false;" class="popup-readmore">Show less</a></span>`;
                html += `</div>`;
            } else {
                html += `<div class="popup-narrative">${crash.narrative}</div>`;
            }
        }

        // Estimated location flag
        if (crash.is_estimated_location) {
            html += `<br><em class="popup-estimated">Approximate location</em>`;
        }

        html += `</div>`;
        return html;
    }

    // ============================================
    // Build Markers
    // ============================================

    function buildMarkers() {
        // Loop through every crash record and create a Leaflet marker for it
        allCrashes.forEach((crash) => {
            // Color by severity — same pattern as MapController.buildCrashMarkers
            let color = MARKER_GREY;
            if (crash.is_serious) color = MARKER_RED;
            else if (crash.has_injury) color = MARKER_AMBER;

            // L.circleMarker() — same as MapController.buildCrashMarkers
            const marker = L.circleMarker([crash.lat, crash.lon], {
                radius: 5,
                fillColor: color,
                color: "#fff",
                weight: 1,
                opacity: 0.8,
                fillOpacity: 0.7,
            });

            // Build the popup content (shown when user clicks a marker)
            // The popup shows enriched crash details including what each party
            // was doing, speed, injury severity, and a truncated NHTSA narrative.
            const popupHTML = buildPopupContent(crash);

            // .bindPopup() attaches a popup — same pattern as MapController.buildCrashMarkers
            marker.bindPopup(popupHTML, { maxWidth: 320 });

            // Store the marker in the allMarkers array (same index as allCrashes)
            allMarkers.push(marker);
        });
    }

    // ============================================
    // Build Filter Controls
    // ============================================

    /**
     * Helper: create underlined text toggle buttons in a container.
     * One option is "All" (value = null), the rest are specific values.
     *
     * @param {HTMLElement} container — DOM element to append toggles to
     * @param {Array} options — [{label: "All", value: null}, {label: "Any injury", value: "injury"}, ...]
     * @param {string} filterKey — key in the `filters` object to update (e.g., "severity", "cities")
     */
    function buildToggleGroup(container, options, filterKey) {
        // Exit early if the container doesn't exist on this page
        if (!container) return;

        // Loop through each option and create a button for it
        // Destructuring: { label, value } pulls those properties out of each option object
        options.forEach(({ label, value }) => {
            // Create a new <button> element
            const btn = document.createElement("button");
            // Set the CSS class for styling
            btn.className = "filter-toggle";
            // Set the button's visible text
            btn.textContent = label;
            // Store the value in a data attribute (data-value="all" or data-value="injury", etc.)
            btn.dataset.value = value === null ? "all" : value;

            // "All" starts as the active (highlighted) option
            if (value === null) btn.classList.add("active");

            // Add a click handler for this button
            btn.addEventListener("click", () => {
                if (filterKey === "cities") {
                    // City filter uses Set-based toggling (can select multiple cities)
                    handleCityToggle(container, btn, value);
                } else {
                    // Single-select: click to select, click same again to deselect (go back to "All")
                    if (filters[filterKey] === value) {
                        // Already selected — deselect it (set back to null = "All")
                        filters[filterKey] = null;
                    } else {
                        // Select this option
                        filters[filterKey] = value;
                    }
                    // Update the UI: remove "active" from all buttons in this group
                    container.querySelectorAll(".filter-toggle").forEach(t => t.classList.remove("active"));
                    if (filters[filterKey] === null) {
                        // No filter active — highlight the "All" button
                        container.querySelector('[data-value="all"]').classList.add("active");
                    } else {
                        // Highlight the clicked button
                        btn.classList.add("active");
                    }
                    // Re-filter and update the map
                    applyFilters();
                }
            });

            // Add the button to the container element in the HTML
            container.appendChild(btn);
        });
    }

    /**
     * Severity filter: All / No injury / Any injury / Serious & moderate / Fatality
     */
    function buildSeverityFilter() {
        // Find the container element by its ID
        const container = document.getElementById("severity-filter");
        // Use the shared buildToggleGroup helper to create toggle buttons
        buildToggleGroup(container, [
            { label: "All", value: null },
            { label: "No injury", value: "none" },
            { label: "Any injury", value: "injury" },
            { label: "Serious", value: "serious" },
            { label: "Fatality", value: "fatal" },
        ], "severity");  // "severity" = which key in the filters object to update
    }

    /**
     * Road user filter: All / Pedestrian / Cyclist / Motorcycle
     */
    function buildRoadUserFilter() {
        // Same pattern as buildSeverityFilter
        const container = document.getElementById("road-user-filter");
        buildToggleGroup(container, [
            { label: "All crashes", value: null },
            { label: "Pedestrian", value: "Pedestrian" },
            { label: "Cyclist", value: "Cyclist" },
            { label: "Motorcycle", value: "Motorcycle" },
        ], "roadUser");
    }

    /**
     * City filter: All + individual cities.
     * Uses the same toggle UI but with Set-based multi-select.
     */
    function buildCityFilter(stats) {
        const container = document.getElementById("city-filter");
        // Exit early if the container or data doesn't exist
        if (!container || !stats.city_breakdown) return;

        // Build the options array: "All cities" first, then one per city from the data
        const options = [{ label: "All cities", value: null }];
        // Object.entries() converts {key: value} into [[key, value], ...] pairs
        Object.entries(stats.city_breakdown).forEach(([cityName, info]) => {
            // Template literal shows the city name with its crash count
            options.push({ label: `${cityName} (${info.count})`, value: info.code });
        });

        // Use the shared toggle builder (it detects "cities" filterKey for multi-select)
        buildToggleGroup(container, options, "cities");
    }

    /**
     * Handle city toggle (multi-select with Set).
     * Unlike severity/roadUser, you can select MULTIPLE cities at once.
     */
    function handleCityToggle(container, btn, value) {
        // Find the "All" button in this container
        const allBtn = container.querySelector('[data-value="all"]');

        if (value === null) {
            // Clicked "All" — clear the Set (deselect all individual cities)
            // .clear() removes everything from the Set
            filters.cities.clear();
            // Remove "active" from all buttons, then highlight just "All"
            container.querySelectorAll(".filter-toggle").forEach(t => t.classList.remove("active"));
            allBtn.classList.add("active");
        } else {
            // Toggle a specific city on/off
            // .has() checks if the Set contains this value
            if (filters.cities.has(value)) {
                // Already selected — .delete() removes it from the Set
                filters.cities.delete(value);
                btn.classList.remove("active");
            } else {
                // Not selected — .add() puts it in the Set
                filters.cities.add(value);
                btn.classList.add("active");
            }
            // .classList.toggle(class, condition) adds the class if condition is true, removes if false
            // If no cities are selected (Set is empty), "All" should be highlighted
            allBtn.classList.toggle("active", filters.cities.size === 0);
        }

        // Re-filter and update the map
        applyFilters();
    }

    /**
     * Time of day filter: All / Daytime / Night / Rush hour
     */
    function buildTimeFilter() {
        // Same pattern as buildSeverityFilter
        const container = document.getElementById("time-filter");
        buildToggleGroup(container, [
            { label: "All", value: null },
            { label: "Daytime (6am–8pm)", value: "daytime" },
            { label: "Night (8pm–6am)", value: "night" },
            { label: "Rush hour", value: "rush" },
        ], "timeOfDay");
    }

    // ============================================
    // Apply Filters
    // ============================================

    /**
     * Filter markers based on current filter state and update the map.
     * This runs every time any filter changes.
     */
    function applyFilters() {
        // .clearLayers() removes ALL markers from the cluster group (start fresh)
        exploreCluster.clearLayers();
        // Counter for how many crashes pass all filters
        let shownCount = 0;

        // Loop through every crash and check if it passes all active filters
        allCrashes.forEach((crash, i) => {
            let show = true;  // Assume it passes until a filter rejects it

            // City filter: if any cities are selected, only show crashes in those cities
            // .size = how many items are in the Set; .has() checks membership
            if (filters.cities.size > 0 && !filters.cities.has(crash.city)) {
                show = false;
            }

            // Severity filter — checks the severity_level field from the pipeline
            // Possible values: "none", "minor", "moderate", "serious", "fatal"
            if (filters.severity === "none" && crash.severity_level !== "none") {
                show = false;
            }
            if (filters.severity === "injury" && crash.severity_level === "none") {
                show = false;
            }
            if (filters.severity === "serious" && !crash.is_serious) {
                show = false;
            }
            if (filters.severity === "fatal" && crash.severity_level !== "fatal") {
                show = false;
            }

            // Road user filter: only show crashes involving the selected road user type
            if (filters.roadUser && crash.crash_type !== filters.roadUser) {
                show = false;
            }

            // Time of day filter (derived from the crash hour)
            if (filters.timeOfDay && crash.hour !== null) {
                const h = crash.hour;  // Hour in 24-hour format (0–23)
                // Daytime = 6am to 8pm
                if (filters.timeOfDay === "daytime" && (h < 6 || h >= 20)) {
                    show = false;
                }
                // Night = 8pm to 6am
                if (filters.timeOfDay === "night" && (h >= 6 && h < 20)) {
                    show = false;
                }
                // Rush hour = 7-10am or 5-8pm (hours 7,8,9,17,18,19 — matches pipeline definition)
                if (filters.timeOfDay === "rush" && !((h >= 7 && h < 10) || (h >= 17 && h < 20))) {
                    show = false;
                }
            }

            // If the crash passed all filters, add its marker to the map
            if (show) {
                // allMarkers[i] is the Leaflet marker for allCrashes[i]
                exploreCluster.addLayer(allMarkers[i]);
                shownCount++;
            }
        });

        // Update the "showing X crashes" count display
        const countEl = document.getElementById("filtered-count");
        if (countEl) {
            // .toLocaleString() adds commas for readability (e.g., 1,123 instead of 1123)
            countEl.textContent = shownCount.toLocaleString("en-US");
        }

        // If exactly one city is selected, zoom the map to that city
        if (filters.cities.size === 1) {
            // [...filters.cities] converts the Set to an array so we can grab the first element
            const cityCode = [...filters.cities][0];
            // Look up the city's coordinates from MapController
            const coords = MapController.CITY_COORDS[cityCode];
            if (coords) {
                // .flyTo() animates the map to the city's location at zoom level 11
                exploreMap.flyTo([coords.lat, coords.lon], 11, { duration: 1 });
            }
        } else if (filters.cities.size === 0) {
            // No city filter — zoom back out to show the full US
            exploreMap.flyTo([37.0902, -95.7129], 4, { duration: 1 });
        }
    }

    /**
     * Reset all filters to their default state (show everything).
     */
    function resetFilters() {
        // .clear() empties the Set of selected cities
        filters.cities.clear();
        // Set all single-select filters back to null (= "All")
        filters.severity = null;
        filters.roadUser = null;
        filters.timeOfDay = null;

        // Reset all toggle button UIs: only "All" buttons should be highlighted
        document.querySelectorAll(".filter-toggle").forEach(btn => {
            // .classList.toggle(class, condition) — adds class if condition is true
            btn.classList.toggle("active", btn.dataset.value === "all");
        });

        // Re-filter the map (will show all crashes since no filters are active)
        applyFilters();
        // Zoom back out to show the full US
        exploreMap.flyTo([37.0902, -95.7129], 4, { duration: 1 });
    }

    // Public API — only init() is exposed; everything else stays private inside the module
    return { init };

// The closing })() immediately runs the function and stores the returned object in Explore
})();
