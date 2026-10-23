/**
 * basemap.js — Shared background map for both Leaflet maps
 *
 * Uses OpenFreeMap's "positron" style: free, open source, no API key and
 * no usage limits (https://openfreemap.org). It is a vector style, so it is
 * drawn by MapLibre GL through the maplibre-gl-leaflet bridge.
 *
 * History: until October 2026 the site used CARTO raster tiles, which
 * began requiring an API key and rendered "API KEY REQUIRED" watermarks
 * on every map. Browsers without WebGL fall back to standard
 * OpenStreetMap raster tiles.
 */

const Basemap = (function () {
    const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
    const ATTRIBUTION =
        '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> ' +
        '&copy; <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> ' +
        'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

    function webglAvailable() {
        try {
            const canvas = document.createElement("canvas");
            return !!(window.WebGLRenderingContext &&
                (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
        } catch (e) {
            return false;
        }
    }

    /**
     * Add the background map to a Leaflet map.
     * @param {L.Map} map
     */
    function addTo(map) {
        // Marker clustering needs a max zoom; raster tile layers used to set it.
        map.setMaxZoom(19);
        // The map's container can change size after load (filters render,
        // layouts reflow); keep Leaflet and the WebGL canvas in sync.
        if (window.ResizeObserver) {
            new ResizeObserver(() => map.invalidateSize()).observe(map.getContainer());
        }
        if (typeof L.maplibreGL === "function" && webglAvailable()) {
            L.maplibreGL({
                style: STYLE_URL,
                attribution: ATTRIBUTION,
                interactive: false,
            }).addTo(map);
            return;
        }
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
            className: "basemap-fallback",
        }).addTo(map);
    }

    return { addTo };
})();
