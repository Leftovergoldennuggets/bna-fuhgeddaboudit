/**
 * map-controller.js — Leaflet map initialization and marker management
 * =====================================================================
 * Handles the main scrollytelling map:
 *   - Creates the Leaflet map with CartoDB Positron tiles (clean look)
 *   - Adds city overview markers (circle markers showing crash counts)
 *   - Adds individual crash markers in MarkerCluster groups
 *   - Manages serious incident markers with pulsing red dots
 *   - Controls the crash detail panel (shows incident narratives)
 *   - Provides flyTo transitions for scrollytelling steps
 *
 * Dependencies:
 *   - Leaflet (loaded from CDN in index.html)
 *   - Leaflet.MarkerCluster (loaded from CDN in index.html)
 *   - data-loader.js (for crash data)
 */

// ============================================
// MapController Module
// ============================================
const MapController = (function () {

    // --- Map View Presets ---
    // These define the center and zoom for each scrollytelling step
    const VIEWS = {
        "intro":           { center: [39.8283, -98.5795], zoom: 4 },
        "us-overview":     { center: [37.0902, -95.7129], zoom: 4 },
        "zoom-california": { center: [36.7783, -119.4179], zoom: 6 },
        "sf-heatmap":      { center: [37.7749, -122.4194], zoom: 12 },
        "sf-serious":      { center: [37.7749, -122.4194], zoom: 12 },
    };

    // --- City Coordinates (for overview markers) ---
    const CITY_COORDS = {
        "SAN_FRANCISCO": { lat: 37.7749, lon: -122.4194, name: "San Francisco" },
        "PHOENIX":       { lat: 33.4484, lon: -112.0740, name: "Phoenix" },
        "LOS_ANGELES":   { lat: 34.0522, lon: -118.2437, name: "Los Angeles" },
        "AUSTIN":        { lat: 30.2672, lon: -97.7431,  name: "Austin" },
        "ATLANTA":       { lat: 33.7490, lon: -84.3880,  name: "Atlanta" },
        "MOUNTAIN_VIEW": { lat: 37.3861, lon: -122.0839, name: "Mountain View" },
    };

    // --- Module State ---
    let map = null;                // Leaflet map instance
    let cityMarkersLayer = null;   // Layer group for city overview markers
    let clusterGroup = null;       // MarkerCluster group for all crash dots
    let seriousMarkersLayer = null; // Layer group for serious incident markers
    let currentView = "intro";     // Track current scrollytelling step
    let crashData = [];            // Raw crash data from JSON
    let incidentData = null;       // Serious incidents from JSON
    let statsData = null;          // Site stats from JSON

    // ============================================
    // Initialize the map
    // ============================================

    /**
     * Create the Leaflet map and add the tile layer.
     * Call this once when the page loads.
     *
     * @param {Array} crashes   — crash_data.json (array of crash records)
     * @param {Object} incidents — serious_incidents.json
     * @param {Object} stats    — site-data.json
     */
    function init(crashes, incidents, stats) {
        crashData = crashes;
        incidentData = incidents;
        statsData = stats;

        // Create the map in the #main-map container
        map = L.map("main-map", {
            center: VIEWS.intro.center,
            zoom: VIEWS.intro.zoom,
            zoomControl: false,           // We'll add custom zoom control
            scrollWheelZoom: false,        // Disable scroll zoom (would conflict with scrollytelling)
            doubleClickZoom: false,
            dragging: true,
            attributionControl: true,
        });

        // Add CartoDB Positron tiles (clean, light basemap)
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            {
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
                    '&copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: "abcd",
                maxZoom: 19,
            }
        ).addTo(map);

        // Add zoom control in the bottom-right corner
        L.control.zoom({ position: "bottomright" }).addTo(map);

        // Create layer groups (empty for now — filled as scrollytelling progresses)
        cityMarkersLayer = L.layerGroup().addTo(map);
        clusterGroup = L.markerClusterGroup({
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
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
        seriousMarkersLayer = L.layerGroup();

        // Build city overview markers
        buildCityMarkers();

        // Build crash cluster markers (not added to map yet)
        buildCrashMarkers();

        // Build serious incident markers (not added to map yet)
        buildSeriousMarkers();

        // Set up crash detail panel close button
        initCrashPanel();

        console.log("[MapController] Map initialized");
    }

    // ============================================
    // Build Marker Layers
    // ============================================

    /**
     * Create circle markers for each city showing crash count.
     * These are shown during the US overview step.
     */
    function buildCityMarkers() {
        if (!statsData || !statsData.city_breakdown) return;

        Object.entries(statsData.city_breakdown).forEach(([cityName, info]) => {
            const cityCoord = CITY_COORDS[info.code];
            if (!cityCoord) return;

            // Size the circle based on crash count
            const radius = Math.max(8, Math.sqrt(info.count) * 1.5);

            const marker = L.circleMarker([cityCoord.lat, cityCoord.lon], {
                radius: radius,
                fillColor: "#3182ce",
                color: "#fff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8,
            });

            marker.bindTooltip(
                `<strong>${cityName}</strong><br>${info.count} crashes (${info.percentage}%)`,
                { direction: "top", className: "city-tooltip" }
            );

            cityMarkersLayer.addLayer(marker);
        });
    }

    /**
     * Create individual crash dot markers and add them to the cluster group.
     * Each crash gets a small circle marker colored by time period.
     */
    function buildCrashMarkers() {
        // Color palette for time periods
        const TIME_COLORS = {
            "Early Morning": "#805ad5",  // Purple
            "Morning Rush":  "#d69e2e",  // Gold
            "Late Morning":  "#38a169",  // Green
            "Midday":        "#3182ce",  // Blue
            "Afternoon":     "#dd6b20",  // Orange
            "Evening Rush":  "#e53e3e",  // Red
            "Night":         "#2d3748",  // Dark gray
            "Late Night":    "#553c9a",  // Deep purple
        };

        crashData.forEach((crash) => {
            const color = TIME_COLORS[crash.time_period] || "#718096";

            const marker = L.circleMarker([crash.lat, crash.lon], {
                radius: 5,
                fillColor: color,
                color: "#fff",
                weight: 1,
                opacity: 0.8,
                fillOpacity: 0.7,
            });

            // Popup with crash details
            const dateStr = crash.date || "Unknown date";
            const hourStr = crash.hour !== null ? formatHour(crash.hour) : "Unknown";
            marker.bindPopup(
                `<div class="crash-popup">` +
                `<strong>${crash.crash_type}</strong><br>` +
                `<span class="popup-city">${formatCityName(crash.city)}</span><br>` +
                `<span class="popup-date">${dateStr} at ${hourStr}</span><br>` +
                `<span class="popup-type">Location: ${crash.location_type}</span>` +
                (crash.is_estimated_location
                    ? `<br><em class="popup-estimated">Approximate location</em>`
                    : "") +
                `</div>`,
                { maxWidth: 250 }
            );

            clusterGroup.addLayer(marker);
        });
    }

    /**
     * Create pulsing red markers for serious incidents.
     * These are shown during the "sf-serious" scrollytelling step.
     */
    function buildSeriousMarkers() {
        if (!incidentData || !incidentData.all_incidents) return;

        // Add dynamic styles for pulsing markers (only once)
        if (!document.getElementById("serious-marker-styles")) {
            const style = document.createElement("style");
            style.id = "serious-marker-styles";
            style.textContent = `
                .serious-marker { position: relative; }
                .serious-dot {
                    width: 14px; height: 14px;
                    background: #e53e3e;
                    border: 3px solid white;
                    border-radius: 50%;
                    position: absolute;
                    top: 50%; left: 50%;
                    transform: translate(-50%, -50%);
                    cursor: pointer;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                }
                .serious-pulse {
                    width: 30px; height: 30px;
                    background: rgba(229, 62, 62, 0.4);
                    border-radius: 50%;
                    position: absolute;
                    top: 50%; left: 50%;
                    transform: translate(-50%, -50%);
                    animation: serious-pulse 2s infinite;
                }
                @keyframes serious-pulse {
                    0%   { transform: translate(-50%, -50%) scale(0.5); opacity: 1; }
                    100% { transform: translate(-50%, -50%) scale(2);   opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }

        incidentData.all_incidents.forEach((incident) => {
            const icon = L.divIcon({
                className: "serious-marker",
                html: '<div class="serious-pulse"></div><div class="serious-dot"></div>',
                iconSize: [30, 30],
                iconAnchor: [15, 15],
            });

            const marker = L.marker([incident.lat, incident.lon], { icon: icon });
            marker.on("click", () => showCrashPanel(incident));
            seriousMarkersLayer.addLayer(marker);
        });
    }

    // ============================================
    // Map View Transitions (for scrollytelling)
    // ============================================

    /**
     * Transition the map to a named view.
     * Called by scrollytelling.js when a new step becomes active.
     *
     * @param {string} stepId — One of the keys in VIEWS
     */
    function goToStep(stepId) {
        if (!map) return;
        const view = VIEWS[stepId];
        if (!view) return;

        currentView = stepId;

        // Animate the map to the new position
        map.flyTo(view.center, view.zoom, { duration: 1.5, easeLinearity: 0.25 });

        // Toggle layers based on the current step
        updateLayers(stepId);

        // Toggle the dark overlay on the left side of the map
        const overlay = document.getElementById("map-overlay");
        if (overlay) {
            if (stepId !== "intro") {
                overlay.classList.add("active");
            } else {
                overlay.classList.remove("active");
            }
        }

        // Hide scroll hint after first step
        const hint = document.getElementById("scroll-hint");
        if (hint && stepId !== "intro") {
            hint.classList.add("hidden");
        }
    }

    /**
     * Show/hide marker layers depending on the scrollytelling step.
     */
    function updateLayers(stepId) {
        switch (stepId) {
            case "intro":
            case "us-overview":
                // Show city circles, hide crash dots and serious markers
                if (!map.hasLayer(cityMarkersLayer)) map.addLayer(cityMarkersLayer);
                if (map.hasLayer(clusterGroup)) map.removeLayer(clusterGroup);
                if (map.hasLayer(seriousMarkersLayer)) map.removeLayer(seriousMarkersLayer);
                break;

            case "zoom-california":
                // Transition: show city markers, start removing clusters
                if (!map.hasLayer(cityMarkersLayer)) map.addLayer(cityMarkersLayer);
                if (map.hasLayer(clusterGroup)) map.removeLayer(clusterGroup);
                if (map.hasLayer(seriousMarkersLayer)) map.removeLayer(seriousMarkersLayer);
                break;

            case "sf-heatmap":
                // Show crash clusters, hide city overview markers
                if (map.hasLayer(cityMarkersLayer)) map.removeLayer(cityMarkersLayer);
                if (!map.hasLayer(clusterGroup)) map.addLayer(clusterGroup);
                if (map.hasLayer(seriousMarkersLayer)) map.removeLayer(seriousMarkersLayer);
                break;

            case "sf-serious":
                // Show both clusters and serious markers
                if (map.hasLayer(cityMarkersLayer)) map.removeLayer(cityMarkersLayer);
                if (!map.hasLayer(clusterGroup)) map.addLayer(clusterGroup);
                if (!map.hasLayer(seriousMarkersLayer)) map.addLayer(seriousMarkersLayer);
                break;
        }
    }

    // ============================================
    // Crash Detail Panel
    // ============================================

    /**
     * Set up click handlers for the crash detail panel close button.
     */
    function initCrashPanel() {
        const panel = document.getElementById("crash-panel");
        const closeBtn = document.getElementById("panel-close");

        if (closeBtn) {
            closeBtn.addEventListener("click", () => {
                panel.hidden = true;
                panel.classList.remove("active");
            });
        }

        // Close on Escape key
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && panel) {
                panel.hidden = true;
                panel.classList.remove("active");
            }
        });
    }

    /**
     * Display a serious incident's details in the side panel.
     *
     * @param {Object} incident — One record from serious_incidents.json
     */
    function showCrashPanel(incident) {
        const panel = document.getElementById("crash-panel");
        const content = document.getElementById("panel-content");
        if (!panel || !content) return;

        // Determine severity badge color
        let severityClass = "severity-low";
        const sev = (incident.severity || "").toLowerCase();
        if (sev.includes("fatal")) severityClass = "severity-high";
        else if (sev.includes("serious")) severityClass = "severity-high";
        else if (sev.includes("moderate")) severityClass = "severity-medium";

        content.innerHTML = `
            <div class="panel-header">
                <h3>${incident.crash_type || "Incident"}</h3>
                <p class="panel-meta">${incident.date || "Unknown date"} at ${incident.time || "Unknown time"}</p>
            </div>

            <div class="panel-section">
                <h4>Location</h4>
                <p>${incident.address || incident.city || "Unknown"}</p>
            </div>

            <div class="panel-section">
                <h4>Severity</h4>
                <span class="severity-badge ${severityClass}">${incident.severity || "Unknown"}</span>
            </div>

            <div class="panel-section">
                <h4>Other Party</h4>
                <p>${incident.crash_party || "Unknown"}</p>
            </div>

            ${incident.narrative ? `
            <div class="panel-section">
                <h4>Incident Narrative</h4>
                <p class="panel-narrative">${incident.narrative}</p>
            </div>
            ` : ""}

            ${incident.is_estimated_location ? `
            <p class="panel-note"><em>Note: Location is approximate (city-level estimate).</em></p>
            ` : ""}
        `;

        panel.hidden = false;
        panel.classList.add("active");

        // Center map on the incident
        if (map && incident.lat && incident.lon) {
            map.flyTo([incident.lat, incident.lon], 15, { duration: 0.8 });
        }
    }

    // ============================================
    // Utility Helpers
    // ============================================

    /** Convert 24-hour number to display string (e.g., 17 → "5:00 PM") */
    function formatHour(hour) {
        if (hour === 0) return "12:00 AM";
        if (hour === 12) return "12:00 PM";
        if (hour < 12) return hour + ":00 AM";
        return (hour - 12) + ":00 PM";
    }

    /** Convert city code to display name (e.g., "SAN_FRANCISCO" → "San Francisco") */
    function formatCityName(code) {
        const city = CITY_COORDS[code];
        return city ? city.name : code;
    }

    /** Get the Leaflet map instance (used by explore.js) */
    function getMap() {
        return map;
    }

    /** Get the cluster group (used by explore.js) */
    function getClusterGroup() {
        return clusterGroup;
    }

    // Public API
    return {
        init,
        goToStep,
        showCrashPanel,
        getMap,
        getClusterGroup,
        formatHour,
        formatCityName,
        VIEWS,
        CITY_COORDS,
    };
})();
