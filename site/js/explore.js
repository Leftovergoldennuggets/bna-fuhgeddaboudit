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
const Explore = (function () {

    // --- Module State ---
    let exploreMap = null;          // Separate Leaflet map for the explore section
    let exploreCluster = null;      // MarkerCluster for filtered results
    let allCrashes = [];            // Full crash dataset (from crash_data.json)
    let allMarkers = [];            // Parallel array of Leaflet markers

    // Active filters (null = show all for that dimension)
    let filters = {
        cities: new Set(),          // Selected city codes
        severity: null,             // null | "injury" | "serious"
        roadUser: null,             // null | "Pedestrian" | "Cyclist" | "Motorcycle"
        timeOfDay: null,            // null | "daytime" | "night" | "rush"
    };

    // Muted color palette — severity drives the color (earth tones)
    const MARKER_GREY = "#b0a696";
    const MARKER_AMBER = "#c4841d";
    const MARKER_RED = "#8b2020";

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
        allCrashes = crashes;

        // Create the explore map
        initExploreMap();

        // Build all markers (one per crash)
        buildMarkers();

        // Populate filter controls
        buildSeverityFilter();
        buildRoadUserFilter();
        buildCityFilter(stats);
        buildTimeFilter();

        // Set up the reset button
        const resetBtn = document.getElementById("reset-filters");
        if (resetBtn) {
            resetBtn.addEventListener("click", resetFilters);
        }

        // Show all markers initially
        applyFilters();

        console.log("[Explore] Initialized with", crashes.length, "crashes");
    }

    // ============================================
    // Map Setup
    // ============================================

    function initExploreMap() {
        exploreMap = L.map("explore-map", {
            center: [37.0902, -95.7129],  // US center
            zoom: 4,
            zoomControl: true,
            scrollWheelZoom: true,
            attributionControl: true,
        });

        // Base tiles: CARTO light without labels
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
            {
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
                    '&copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: "abcd",
                maxZoom: 19,
            }
        ).addTo(exploreMap);

        // Label layer on top
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
            { subdomains: "abcd", maxZoom: 19, pane: "shadowPane" }
        ).addTo(exploreMap);

        exploreCluster = L.markerClusterGroup({
            maxClusterRadius: 50,
            showCoverageOnHover: false,
            iconCreateFunction: function (cluster) {
                const count = cluster.getChildCount();
                let size = "small";
                if (count > 50) size = "large";
                else if (count > 20) size = "medium";
                return L.divIcon({
                    html: "<div><span>" + count + "</span></div>",
                    className: "marker-cluster marker-cluster-" + size,
                    iconSize: L.point(40, 40),
                });
            },
        });

        exploreMap.addLayer(exploreCluster);
    }

    // ============================================
    // Build Markers
    // ============================================

    function buildMarkers() {
        allCrashes.forEach((crash) => {
            // Color by severity: serious=red, injury=amber, else grey
            let color = MARKER_GREY;
            if (crash.is_serious) color = MARKER_RED;
            else if (crash.has_injury) color = MARKER_AMBER;

            const marker = L.circleMarker([crash.lat, crash.lon], {
                radius: 5,
                fillColor: color,
                color: "#fff",
                weight: 1,
                opacity: 0.8,
                fillOpacity: 0.7,
            });

            const dateStr = crash.date || "Unknown date";
            const hourStr = crash.hour !== null
                ? MapController.formatHour(crash.hour)
                : "Unknown";

            marker.bindPopup(
                `<div class="crash-popup">` +
                `<strong>${MapController.formatCrashType(crash.crash_type)}</strong><br>` +
                `<span class="popup-city">${MapController.formatCityName(crash.city)}</span><br>` +
                `<span class="popup-date">${dateStr} at ${hourStr}</span><br>` +
                `<span class="popup-type">Location: ${crash.location_type}</span>` +
                (crash.has_injury
                    ? `<br><em style="color:#c4841d">Injury reported</em>`
                    : "") +
                (crash.is_estimated_location
                    ? `<br><em class="popup-estimated">Approximate location</em>`
                    : "") +
                `</div>`,
                { maxWidth: 250 }
            );

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
     * @param {string} filterKey — key in the `filters` object to update
     */
    function buildToggleGroup(container, options, filterKey) {
        if (!container) return;

        options.forEach(({ label, value }) => {
            const btn = document.createElement("button");
            btn.className = "filter-toggle";
            btn.textContent = label;
            btn.dataset.value = value === null ? "all" : value;

            // "All" starts active
            if (value === null) btn.classList.add("active");

            btn.addEventListener("click", () => {
                if (filterKey === "cities") {
                    // City uses Set-based toggling (multi-select)
                    handleCityToggle(container, btn, value);
                } else {
                    // Single-select: click to select, click again to deselect
                    if (filters[filterKey] === value) {
                        // Already selected — deselect (go back to "All")
                        filters[filterKey] = null;
                    } else {
                        filters[filterKey] = value;
                    }
                    // Update UI: highlight active toggle
                    container.querySelectorAll(".filter-toggle").forEach(t => t.classList.remove("active"));
                    if (filters[filterKey] === null) {
                        container.querySelector('[data-value="all"]').classList.add("active");
                    } else {
                        btn.classList.add("active");
                    }
                    applyFilters();
                }
            });

            container.appendChild(btn);
        });
    }

    /**
     * Severity filter: All / Any injury / Serious only
     */
    function buildSeverityFilter() {
        const container = document.getElementById("severity-filter");
        buildToggleGroup(container, [
            { label: "All", value: null },
            { label: "Any injury", value: "injury" },
            { label: "Serious", value: "serious" },
        ], "severity");
    }

    /**
     * Road user filter: All / Pedestrian / Cyclist / Motorcycle
     */
    function buildRoadUserFilter() {
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
        if (!container || !stats.city_breakdown) return;

        // Build options array from data
        const options = [{ label: "All cities", value: null }];
        Object.entries(stats.city_breakdown).forEach(([cityName, info]) => {
            options.push({ label: `${cityName} (${info.count})`, value: info.code });
        });

        buildToggleGroup(container, options, "cities");
    }

    /**
     * Handle city toggle (multi-select with Set)
     */
    function handleCityToggle(container, btn, value) {
        const allBtn = container.querySelector('[data-value="all"]');

        if (value === null) {
            // Clicked "All" — clear everything
            filters.cities.clear();
            container.querySelectorAll(".filter-toggle").forEach(t => t.classList.remove("active"));
            allBtn.classList.add("active");
        } else {
            // Toggle specific city
            if (filters.cities.has(value)) {
                filters.cities.delete(value);
                btn.classList.remove("active");
            } else {
                filters.cities.add(value);
                btn.classList.add("active");
            }
            // Update "All" button
            allBtn.classList.toggle("active", filters.cities.size === 0);
        }

        applyFilters();
    }

    /**
     * Time of day filter: All / Daytime / Night / Rush hour
     */
    function buildTimeFilter() {
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
     */
    function applyFilters() {
        exploreCluster.clearLayers();
        let shownCount = 0;

        allCrashes.forEach((crash, i) => {
            let show = true;

            // City filter
            if (filters.cities.size > 0 && !filters.cities.has(crash.city)) {
                show = false;
            }

            // Severity filter
            if (filters.severity === "injury" && !crash.has_injury) {
                show = false;
            }
            if (filters.severity === "serious" && !crash.is_serious) {
                show = false;
            }

            // Road user filter
            if (filters.roadUser && crash.crash_type !== filters.roadUser) {
                show = false;
            }

            // Time of day filter (derived from hour)
            if (filters.timeOfDay && crash.hour !== null) {
                const h = crash.hour;
                if (filters.timeOfDay === "daytime" && (h < 6 || h >= 20)) {
                    show = false;
                }
                if (filters.timeOfDay === "night" && (h >= 6 && h < 20)) {
                    show = false;
                }
                if (filters.timeOfDay === "rush" && !((h >= 7 && h < 10) || (h >= 17 && h < 19))) {
                    show = false;
                }
            }

            if (show) {
                exploreCluster.addLayer(allMarkers[i]);
                shownCount++;
            }
        });

        // Update the count display
        const countEl = document.getElementById("filtered-count");
        if (countEl) {
            countEl.textContent = shownCount.toLocaleString("en-US");
        }

        // Zoom to city if a single city is selected
        if (filters.cities.size === 1) {
            const cityCode = [...filters.cities][0];
            const coords = MapController.CITY_COORDS[cityCode];
            if (coords) {
                exploreMap.flyTo([coords.lat, coords.lon], 11, { duration: 1 });
            }
        } else if (filters.cities.size === 0) {
            exploreMap.flyTo([37.0902, -95.7129], 4, { duration: 1 });
        }
    }

    /**
     * Reset all filters to their default state (show everything).
     */
    function resetFilters() {
        filters.cities.clear();
        filters.severity = null;
        filters.roadUser = null;
        filters.timeOfDay = null;

        // Reset all toggle UIs
        document.querySelectorAll(".filter-toggle").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.value === "all");
        });

        applyFilters();
        exploreMap.flyTo([37.0902, -95.7129], 4, { duration: 1 });
    }

    // Public API
    return { init };
})();
