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

// IIFE module pattern — keeps all variables private, only exposes what we return at the bottom.
// See scrollytelling.js for a full explanation of this pattern.
const MapController = (function () {

    // --- Map View Presets ---
    // These define the center [latitude, longitude] and zoom level for each scrollytelling step
    const VIEWS = {
        "intro":           { center: [39.8283, -98.5795], zoom: 4 },   // Full US view
        "us-overview":     { center: [37.0902, -95.7129], zoom: 4 },   // Full US view (slightly different center)
        "zoom-california": { center: [36.7783, -119.4179], zoom: 6 },  // California zoom
        "sf-heatmap":      { center: [37.7749, -122.4194], zoom: 12 }, // San Francisco street level
        "sf-serious":      { center: [37.7749, -122.4194], zoom: 12 }, // Same SF view, different markers
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

    // --- Plain-English Crash Type Labels ---
    // The data uses Waymo's official codes (e.g., "V2V F2R").
    // We translate them here so regular people can understand.
    const CRASH_TYPE_LABELS = {
        "V2V F2R":          "Rear-end",
        "V2V Lateral":      "Side-impact",
        "V2V Backing":      "Backing up",
        "V2V Head-on":      "Head-on",
        "V2V Intersection": "Intersection",
        "Single Vehicle":   "Single vehicle",
        "All Others":       "Other",
        "Secondary Crash":  "Chain reaction",
        "Motorcycle":       "Motorcycle",
        "Cyclist":          "Cyclist",
        "Pedestrian":       "Pedestrian",
    };

    /** Convert a raw crash type code to a human-readable label */
    function formatCrashType(code) {
        // Look up the code in our labels; if not found, just return the original code
        return CRASH_TYPE_LABELS[code] || code;
    }

    // --- Module State ---
    // These variables are private to this module (hidden inside the IIFE)
    let map = null;                // The Leaflet map instance
    let cityMarkersLayer = null;   // Layer group for city overview circle markers
    let clusterGroup = null;       // MarkerCluster group that groups nearby crash dots
    let seriousMarkersLayer = null; // Layer group for serious incident red dot markers
    let currentView = "intro";     // Track which scrollytelling step we're on
    let crashData = [];            // All crash records from crash_data.json
    let incidentData = null;       // Serious incidents from serious_incidents.json
    let statsData = null;          // Site stats from site-data.json

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
        // Store the data so other functions in this module can use it
        crashData = crashes;
        incidentData = incidents;
        statsData = stats;

        // L.map() creates a new Leaflet map inside the HTML element with id="main-map"
        map = L.map("main-map", {
            center: VIEWS.intro.center,       // Starting center point [lat, lon]
            zoom: VIEWS.intro.zoom,           // Starting zoom level
            zoomControl: false,               // Hide default zoom buttons (we add custom ones below)
            scrollWheelZoom: false,           // Disable scroll zoom (would conflict with scrollytelling)
            doubleClickZoom: false,           // Disable double-click zoom
            dragging: true,                   // Allow click-and-drag to pan
            attributionControl: true,         // Show the map credits in the corner
        });

        // L.tileLayer() adds the map background images (called "tiles")
        // CARTO light without labels gives a clean, quiet backdrop for our data dots
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
            {
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
                    '&copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: "abcd",  // Load tiles from a/b/c/d subdomains for speed
                maxZoom: 19,         // Maximum zoom level allowed
            }
        ).addTo(map);  // .addTo(map) adds this tile layer to the map

        // Second tile layer: just the city/street labels, drawn on top of our markers
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
            { subdomains: "abcd", maxZoom: 19, pane: "shadowPane" }  // "shadowPane" puts labels above markers
        ).addTo(map);

        // Add zoom +/- buttons in the bottom-right corner
        L.control.zoom({ position: "bottomright" }).addTo(map);

        // L.layerGroup() creates an empty container for markers — we add markers to it later
        cityMarkersLayer = L.layerGroup().addTo(map);  // .addTo(map) makes it visible right away

        // For this part we consulted Claude who recommended the Leaflet MarkerCluster plugin
        // for handling 1,000+ crash markers on the map. Without clustering, plotting every
        // marker individually would make the map unreadable (a mess of overlapping dots) and
        // slow to render. MarkerCluster automatically groups nearby markers into numbered
        // circles that show how many crashes are in that area. As you zoom in, clusters
        // split apart into smaller groups and eventually into individual markers. The
        // `maxClusterRadius` controls how close markers need to be to get grouped together.
        clusterGroup = L.markerClusterGroup({
            maxClusterRadius: 50,          // Markers within 50px get clustered together
            spiderfyOnMaxZoom: true,       // At max zoom, spread out overlapping markers
            showCoverageOnHover: false,    // Don't show cluster boundary on hover
            // Custom function to style each cluster bubble
            iconCreateFunction: function (cluster) {
                // cluster.getChildCount() = how many markers are in this cluster
                const count = cluster.getChildCount();
                // Choose a size class based on how many markers
                let size = "small";
                if (count > 50) size = "large";
                else if (count > 20) size = "medium";
                // L.divIcon() creates a marker from an HTML div (instead of an image)
                return L.divIcon({
                    html: "<div><span>" + count + "</span></div>",  // Show the count number
                    className: "marker-cluster marker-cluster-" + size,  // CSS class for styling
                    iconSize: L.point(40, 40),  // Size of the cluster bubble in pixels
                });
            },
        });
        // Note: clusterGroup is NOT added to the map yet — it appears during the "sf-heatmap" step

        // Empty layer group for serious incident markers (added during "sf-serious" step)
        seriousMarkersLayer = L.layerGroup();

        // Build all three types of markers
        buildCityMarkers();      // Big circles showing crash count per city
        buildCrashMarkers();     // Individual crash dot markers (in clusters)
        buildSeriousMarkers();   // Red dots for serious incidents

        // Set up the crash detail side panel (close button, Escape key)
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
        // Exit early if stats data isn't available
        if (!statsData || !statsData.city_breakdown) return;

        // Object.entries() converts the city_breakdown object into [cityName, info] pairs
        Object.entries(statsData.city_breakdown).forEach(([cityName, info]) => {
            // Look up this city's lat/lon coordinates
            const cityCoord = CITY_COORDS[info.code];
            if (!cityCoord) return;  // Skip if we don't have coordinates for this city

            // Size the circle based on crash count (more crashes = bigger circle)
            // Math.sqrt() prevents huge cities from being TOO big
            const radius = Math.max(8, Math.sqrt(info.count) * 1.5);

            // L.circleMarker() creates a circle on the map at the given [lat, lon]
            const marker = L.circleMarker([cityCoord.lat, cityCoord.lon], {
                radius: radius,          // Circle size in pixels
                fillColor: "#8b6f47",    // Earth-tone fill color
                color: "#fff",           // White border
                weight: 2,              // Border thickness
                opacity: 1,             // Border opacity (1 = fully visible)
                fillOpacity: 0.8,       // Fill opacity (slightly transparent)
            });

            // .bindTooltip() attaches a tooltip that appears on hover
            // Template literal: `text ${variable}` inserts the variable's value into the string
            marker.bindTooltip(
                `<strong>${cityName}</strong><br>${info.count} crashes (${info.percentage}%)`,
                { direction: "top", className: "city-tooltip" }  // Tooltip appears above the marker
            );

            // .addLayer() adds this marker to the cityMarkersLayer group
            cityMarkersLayer.addLayer(marker);
        });
    }

    /**
     * Create individual crash dot markers and add them to the cluster group.
     * Each crash gets a small circle marker colored by severity.
     */
    function buildCrashMarkers() {
        // Loop through every crash record
        crashData.forEach((crash) => {
            // Choose color by severity: red for serious, amber for injury, grey for default
            let color = "#b0a696";  // default: warm grey
            if (crash.is_serious) color = "#8b2020";      // deep red for serious
            else if (crash.has_injury) color = "#c4841d";  // amber for any injury

            // L.circleMarker() — similar to buildCityMarkers but smaller dots
            const marker = L.circleMarker([crash.lat, crash.lon], {
                radius: 5,
                fillColor: color,
                color: "#fff",
                weight: 1,
                opacity: 0.8,
                fillOpacity: 0.7,
            });

            // Popup with enriched crash details — shown when the user clicks the marker
            // buildPopupContent() generates the full HTML with speed, movements, narrative, etc.
            marker.bindPopup(buildPopupContent(crash), { maxWidth: 320 });

            // Add this marker to the cluster group (not directly to the map)
            clusterGroup.addLayer(marker);
        });
    }

    /**
     * Create pulsing red markers for serious incidents.
     * These are shown during the "sf-serious" scrollytelling step.
     */
    function buildSeriousMarkers() {
        // Exit early if incident data isn't available
        if (!incidentData || !incidentData.all_incidents) return;

        // Use SF-only incidents for the scrollytelling step (we're zoomed into SF)
        const incidents = incidentData.sf_incidents || incidentData.all_incidents;
        incidents.forEach((incident) => {
            // L.divIcon() creates a custom marker from HTML (instead of an image file)
            const icon = L.divIcon({
                className: "serious-marker",  // CSS class for additional styling
                html: '<div style="width:14px;height:14px;background:#8b2020;border:2px solid white;border-radius:50%;cursor:pointer;"></div>',
                iconSize: [14, 14],     // Total size of the icon in pixels [width, height]
                iconAnchor: [7, 7],     // The point of the icon that sits on the map coordinate (center)
            });

            // L.marker() creates a standard marker (not a circle) at the given [lat, lon]
            const marker = L.marker([incident.lat, incident.lon], { icon: icon });
            // When clicked, show the crash detail panel with this incident's info
            marker.on("click", () => showCrashPanel(incident));
            // Add to the serious markers layer group
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
     * @param {string} stepId — One of the keys in VIEWS (e.g., "sf-heatmap")
     */
    function goToStep(stepId) {
        if (!map) return;           // Safety check: map must exist
        const view = VIEWS[stepId];
        if (!view) return;          // Ignore unknown steps

        // Remember which step we're on
        currentView = stepId;

        // .flyTo() smoothly animates the map to a new center and zoom level
        map.flyTo(view.center, view.zoom, { duration: 1.5, easeLinearity: 0.25 });

        // Show/hide the right marker layers for this step
        updateLayers(stepId);

        // Toggle the dark overlay on the left side of the map (darkens behind text)
        const overlay = document.getElementById("map-overlay");
        if (overlay) {
            if (stepId !== "intro") {
                // .classList.add() adds a CSS class to the element
                overlay.classList.add("active");
            } else {
                // .classList.remove() removes a CSS class from the element
                overlay.classList.remove("active");
            }
        }

        // Hide the "scroll down" hint arrow after the user has scrolled past intro
        const hint = document.getElementById("scroll-hint");
        if (hint && stepId !== "intro") {
            hint.classList.add("hidden");
        }
    }

    /**
     * Show/hide marker layers depending on the scrollytelling step.
     * switch/case checks stepId against multiple options and runs the matching block.
     */
    function updateLayers(stepId) {
        // switch checks the value of stepId against each "case"
        switch (stepId) {
            case "intro":
            case "us-overview":
                // Show city circles, hide crash dots and serious markers
                // map.hasLayer() checks if a layer is currently on the map
                if (!map.hasLayer(cityMarkersLayer)) map.addLayer(cityMarkersLayer);
                // .removeLayer() takes a layer off the map (hides it)
                if (map.hasLayer(clusterGroup)) map.removeLayer(clusterGroup);
                if (map.hasLayer(seriousMarkersLayer)) map.removeLayer(seriousMarkersLayer);
                break;  // "break" exits the switch — without it, the next case would also run

            case "zoom-california":
                // Similar to above — show city markers, hide clusters and serious
                if (!map.hasLayer(cityMarkersLayer)) map.addLayer(cityMarkersLayer);
                if (map.hasLayer(clusterGroup)) map.removeLayer(clusterGroup);
                if (map.hasLayer(seriousMarkersLayer)) map.removeLayer(seriousMarkersLayer);
                break;

            case "sf-heatmap":
                // Show crash clusters, hide city overview markers
                if (map.hasLayer(cityMarkersLayer)) map.removeLayer(cityMarkersLayer);
                // .addLayer() puts a layer on the map (makes it visible)
                if (!map.hasLayer(clusterGroup)) map.addLayer(clusterGroup);
                if (map.hasLayer(seriousMarkersLayer)) map.removeLayer(seriousMarkersLayer);
                break;

            case "sf-serious":
                // Show only serious markers — clean map with just the red dots
                if (map.hasLayer(cityMarkersLayer)) map.removeLayer(cityMarkersLayer);
                if (map.hasLayer(clusterGroup)) map.removeLayer(clusterGroup);
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
        // Find the panel and close button elements
        const panel = document.getElementById("crash-panel");
        const closeBtn = document.getElementById("panel-close");

        if (closeBtn) {
            // When the close button is clicked, hide the panel
            closeBtn.addEventListener("click", () => {
                panel.hidden = true;                    // HTML "hidden" attribute hides the element
                panel.classList.remove("active");       // Also remove the "active" CSS class
            });
        }

        // Close the panel when the Escape key is pressed
        document.addEventListener("keydown", (e) => {
            // e.key tells us which key was pressed
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

        // Determine severity badge color based on the severity text
        let severityClass = "severity-low";
        // .toLowerCase() converts to lowercase so we can compare case-insensitively
        const sev = (incident.severity || "").toLowerCase();
        // .includes() checks if a string contains a substring
        if (sev.includes("fatal")) severityClass = "severity-high";
        else if (sev.includes("serious")) severityClass = "severity-high";
        else if (sev.includes("moderate")) severityClass = "severity-medium";

        // .innerHTML sets the HTML content inside the element
        // Template literal with backticks allows multi-line strings and ${variable} insertions
        content.innerHTML = `
            <div class="panel-header">
                <h3>${formatCrashType(incident.crash_type) || "Incident"}</h3>
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

        // Show the panel
        panel.hidden = false;                // Remove the "hidden" attribute to make it visible
        panel.classList.add("active");       // Add CSS class for slide-in animation

        // .flyTo() animates the map to center on this incident's location
        if (map && incident.lat && incident.lon) {
            map.flyTo([incident.lat, incident.lon], 15, { duration: 0.8 });
        }
    }

    // ============================================
    // Utility Helpers
    // ============================================

    /** Convert 24-hour number to display string (e.g., 17 → "5:00 PM") */
    function formatHour(hour) {
        if (hour === 0) return "12:00 AM";   // Midnight special case
        if (hour === 12) return "12:00 PM";  // Noon special case
        if (hour < 12) return hour + ":00 AM";        // Morning hours
        return (hour - 12) + ":00 PM";                // Afternoon/evening hours
    }

    /** Convert city code to display name (e.g., "SAN_FRANCISCO" → "San Francisco") */
    function formatCityName(code) {
        const city = CITY_COORDS[code];        // Look up the city by its code
        return city ? city.name : code;        // Return the name, or the raw code if not found
    }

    /**
     * Build enriched popup HTML for a crash marker.
     * Shows crash type, date/time, what each party was doing, speed,
     * injury severity, and a truncated narrative with "Read more" toggle.
     * Used by both the scrollytelling map and the explore map.
     *
     * @param {Object} crash — a single crash record from crash_data.json
     * @returns {string} HTML string for the Leaflet popup
     */
    function buildPopupContent(crash) {
        const dateStr = crash.date || "Unknown date";
        const hourStr = crash.hour !== null ? formatHour(crash.hour) : "Unknown";

        // Start building the popup HTML
        let html = `<div class="crash-popup crash-popup-enriched">`;

        // Header: crash type + severity badge
        html += `<div class="popup-header">`;
        html += `<strong>${formatCrashType(crash.crash_type)}</strong>`;
        if (crash.is_serious) {
            html += ` <span class="popup-badge popup-badge-serious">Serious</span>`;
        } else if (crash.has_injury) {
            html += ` <span class="popup-badge popup-badge-injury">Injury</span>`;
        }
        html += `</div>`;

        // City, date, time
        html += `<span class="popup-city">${formatCityName(crash.city)}</span>`;
        html += ` &mdash; <span class="popup-date">${dateStr} at ${hourStr}</span><br>`;

        // Circumstances table: what each party was doing, speed, other party type
        if (crash.sv_movement || crash.cp_movement || crash.speed_mph !== null || crash.crash_with) {
            html += `<div class="popup-circumstances">`;
            if (crash.speed_mph !== null) {
                html += `<div class="popup-detail"><span class="popup-detail-label">Waymo speed:</span> ${crash.speed_mph} mph</div>`;
            }
            if (crash.sv_movement) {
                html += `<div class="popup-detail"><span class="popup-detail-label">Waymo action:</span> ${crash.sv_movement}</div>`;
            }
            if (crash.cp_movement) {
                html += `<div class="popup-detail"><span class="popup-detail-label">Other party:</span> ${crash.cp_movement}</div>`;
            }
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
        // Each popup gets a unique ID based on lat/lon to avoid collisions.
        if (crash.narrative) {
            const truncLen = 200;
            const needsTruncation = crash.narrative.length > truncLen;
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

    /** Get the Leaflet map instance (used by explore.js) */
    function getMap() {
        return map;
    }

    /** Get the cluster group (used by explore.js) */
    function getClusterGroup() {
        return clusterGroup;
    }

    // Public API — these are the only things accessible from outside the module
    return {
        init,
        goToStep,
        showCrashPanel,
        getMap,
        getClusterGroup,
        formatHour,
        formatCityName,
        formatCrashType,
        buildPopupContent,
        CRASH_TYPE_LABELS,
        VIEWS,
        CITY_COORDS,
    };

// The closing })() immediately runs the function and stores the returned object in MapController
})();
