/**
 * explore.js — Interactive "Explore the Data" section
 * =====================================================
 * Manages the filter sidebar and a separate explore map where users
 * can filter crashes by city, crash type, and time period.
 *
 * Features:
 *   - City filter buttons (click to toggle)
 *   - Crash type checkboxes
 *   - Time period checkboxes
 *   - Live-updating marker count
 *   - Reset button to clear all filters
 *   - Separate Leaflet map instance (independent from scrollytelling map)
 *
 * Dependencies:
 *   - Leaflet + MarkerCluster (from CDN)
 *   - map-controller.js (for formatCityName, formatHour, CITY_COORDS)
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

    // Active filters (empty = show all)
    let filters = {
        cities: new Set(),          // Selected city codes (e.g., "SAN_FRANCISCO")
        crashTypes: new Set(),      // Selected crash types (e.g., "V2V Lateral")
        timePeriods: new Set(),     // Selected time periods (e.g., "Morning Rush")
    };

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

        // Populate filter controls from the data
        buildCityFilter(stats);
        buildCrashTypeFilter(stats);
        buildTimePeriodFilter(stats);

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

        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            {
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
                    '&copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: "abcd",
                maxZoom: 19,
            }
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

    /** Color palette for crash types */
    const TYPE_COLORS = {
        "V2V F2R":          "#3182ce",  // Blue
        "V2V Lateral":      "#38a169",  // Green
        "V2V Backing":      "#d69e2e",  // Gold
        "Single Vehicle":   "#805ad5",  // Purple
        "V2V Head-on":      "#e53e3e",  // Red
        "V2V Intersection": "#dd6b20",  // Orange
        "All Others":       "#718096",  // Gray
        "Secondary Crash":  "#2d3748",  // Dark
        "Motorcycle":       "#b83280",  // Pink
        "Cyclist":          "#00b5d8",  // Teal
        "Pedestrian":       "#c53030",  // Dark red
    };

    function buildMarkers() {
        allCrashes.forEach((crash, i) => {
            const color = TYPE_COLORS[crash.crash_type] || "#718096";

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
                `<strong>${crash.crash_type}</strong><br>` +
                `<span class="popup-city">${MapController.formatCityName(crash.city)}</span><br>` +
                `<span class="popup-date">${dateStr} at ${hourStr}</span><br>` +
                `<span class="popup-type">Location: ${crash.location_type}</span>` +
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
     * Create city filter buttons from the data.
     * "All" is selected by default (no filter active).
     */
    function buildCityFilter(stats) {
        const container = document.getElementById("city-filter");
        if (!container || !stats.city_breakdown) return;

        // "All Cities" button
        const allBtn = document.createElement("button");
        allBtn.className = "filter-btn active";
        allBtn.textContent = "All Cities";
        allBtn.dataset.city = "ALL";
        allBtn.addEventListener("click", () => {
            filters.cities.clear();
            container.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
            allBtn.classList.add("active");
            applyFilters();
        });
        container.appendChild(allBtn);

        // One button per city
        Object.entries(stats.city_breakdown).forEach(([cityName, info]) => {
            const btn = document.createElement("button");
            btn.className = "filter-btn";
            btn.textContent = `${cityName} (${info.count})`;
            btn.dataset.city = info.code;
            btn.addEventListener("click", () => {
                // Toggle this city
                if (filters.cities.has(info.code)) {
                    filters.cities.delete(info.code);
                    btn.classList.remove("active");
                } else {
                    filters.cities.add(info.code);
                    btn.classList.add("active");
                }
                // Update "All" button state
                allBtn.classList.toggle("active", filters.cities.size === 0);
                applyFilters();
            });
            container.appendChild(btn);
        });
    }

    /**
     * Create crash type checkboxes.
     */
    function buildCrashTypeFilter(stats) {
        const container = document.getElementById("crash-type-filter");
        if (!container || !stats.crash_types) return;

        Object.entries(stats.crash_types).forEach(([typeName, info]) => {
            const label = document.createElement("label");
            label.className = "filter-checkbox";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = typeName;
            checkbox.checked = true; // All checked by default
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) {
                    filters.crashTypes.delete(typeName);
                } else {
                    filters.crashTypes.add(typeName);
                }
                applyFilters();
            });

            const color = TYPE_COLORS[typeName] || "#718096";
            label.innerHTML = "";
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(
                ` ${typeName} (${info.count})`
            ));

            // Add a small color dot
            const dot = document.createElement("span");
            dot.className = "type-dot";
            dot.style.backgroundColor = color;
            label.insertBefore(dot, label.firstChild.nextSibling);

            container.appendChild(label);
        });
    }

    /**
     * Create time period checkboxes.
     */
    function buildTimePeriodFilter(stats) {
        const container = document.getElementById("time-filter");
        if (!container || !stats.time_periods) return;

        Object.entries(stats.time_periods).forEach(([periodName, info]) => {
            const label = document.createElement("label");
            label.className = "filter-checkbox";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = periodName;
            checkbox.checked = true;
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) {
                    filters.timePeriods.delete(periodName);
                } else {
                    filters.timePeriods.add(periodName);
                }
                applyFilters();
            });

            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(
                ` ${periodName} (${info.count})`
            ));
            container.appendChild(label);
        });
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

            // City filter: if any cities selected, crash must be in one of them
            if (filters.cities.size > 0 && !filters.cities.has(crash.city)) {
                show = false;
            }

            // Crash type filter: if any types UNCHECKED, hide those types
            if (filters.crashTypes.size > 0 && filters.crashTypes.has(crash.crash_type)) {
                show = false;
            }

            // Time period filter: if any periods UNCHECKED, hide those periods
            if (filters.timePeriods.size > 0 && filters.timePeriods.has(crash.time_period)) {
                show = false;
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

        // If a city filter is active, zoom to that city
        if (filters.cities.size === 1) {
            const cityCode = [...filters.cities][0];
            const coords = MapController.CITY_COORDS[cityCode];
            if (coords) {
                exploreMap.flyTo([coords.lat, coords.lon], 11, { duration: 1 });
            }
        } else if (filters.cities.size === 0) {
            // Reset to US overview
            exploreMap.flyTo([37.0902, -95.7129], 4, { duration: 1 });
        }
    }

    /**
     * Reset all filters to their default state (show everything).
     */
    function resetFilters() {
        filters.cities.clear();
        filters.crashTypes.clear();
        filters.timePeriods.clear();

        // Reset UI
        document.querySelectorAll("#city-filter .filter-btn").forEach((btn) => {
            btn.classList.toggle("active", btn.dataset.city === "ALL");
        });
        document.querySelectorAll("#crash-type-filter input").forEach((cb) => {
            cb.checked = true;
        });
        document.querySelectorAll("#time-filter input").forEach((cb) => {
            cb.checked = true;
        });

        applyFilters();
        exploreMap.flyTo([37.0902, -95.7129], 4, { duration: 1 });
    }

    // Public API
    return { init };
})();
