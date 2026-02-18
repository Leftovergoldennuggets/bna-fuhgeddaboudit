/**
 * Waymo Crash Data Analysis - Scrollytelling Script
 *
 * Features:
 * - Interactive map with scroll-driven zoom
 * - Heatmap visualization showing crash density
 * - Filtered view of moderate/serious/fatal incidents in SF
 * - Clickable markers with detailed crash info panels
 * - Zipcode lookup to find nearest Waymo crash city
 */

// =======================
// Configuration
// =======================
const CONFIG = {
    // Map center points for different views
    views: {
        us: { center: [39.8283, -98.5795], zoom: 4 },
        california: { center: [37.5, -121.5], zoom: 6 },
        sfHeatmap: { center: [37.76, -122.42], zoom: 12 },
        sfHotspots: { center: [37.775, -122.418], zoom: 13 }
    },
    // Animation settings
    animation: {
        zoomDuration: 1.5,
        fadeDuration: 500
    }
};

// City data for zipcode distance calculations
const CITY_DATA = {
    'San Francisco': { lat: 37.7749, lon: -122.4194, state: 'CA' },
    'Phoenix': { lat: 33.4484, lon: -112.0740, state: 'AZ' },
    'Los Angeles': { lat: 34.0522, lon: -118.2437, state: 'CA' },
    'Austin': { lat: 30.2672, lon: -97.7431, state: 'TX' },
    'Atlanta': { lat: 33.7490, lon: -84.3880, state: 'GA' }
};

// =======================
// Global State
// =======================
let map = null;
let heatmapLayer = null;
let crashMarkers = [];
let seriousIncidentMarkers = [];
let allCrashData = [];
let seriousIncidentsData = null;
let currentStep = 'intro';
let isHeatmapVisible = true;
let areMarkersVisible = false;

// =======================
// Initialize Application
// =======================
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadCrashData();
    loadSeriousIncidents();
    initScrollytelling();
    initProgressBar();
    initNavigation();
    initStatCounters();
    initZipcodeSearch();
    initPanelClose();
});

// =======================
// Map Initialization
// =======================
function initMap() {
    // Create map
    map = L.map('main-map', {
        center: CONFIG.views.us.center,
        zoom: CONFIG.views.us.zoom,
        zoomControl: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        dragging: true
    });

    // Add zoom control to bottom right
    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    // Add tile layer (dark style for visual impact)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19
    }).addTo(map);
}

// =======================
// Load Crash Data
// =======================
async function loadCrashData() {
    try {
        const response = await fetch('crash_time_data.json');
        allCrashData = await response.json();
        console.log(`Loaded ${allCrashData.length} crash records`);

        // Create heatmap layer
        createHeatmapLayer();

    } catch (error) {
        console.error('Error loading crash data:', error);
        createSampleHeatmapData();
    }
}

async function loadSeriousIncidents() {
    try {
        const response = await fetch('serious_incidents.json');
        seriousIncidentsData = await response.json();
        console.log(`Loaded ${seriousIncidentsData.sf_incidents.length} SF serious incidents`);
        console.log(`Loaded ${seriousIncidentsData.all_incidents.length} total serious incidents`);

        // Update city data with actual crash counts
        if (seriousIncidentsData.city_data) {
            Object.keys(seriousIncidentsData.city_data).forEach(city => {
                if (CITY_DATA[city]) {
                    CITY_DATA[city].crashCount = seriousIncidentsData.city_data[city].count;
                }
            });
        }
    } catch (error) {
        console.error('Error loading serious incidents:', error);
    }
}

// =======================
// Heatmap Layer
// =======================
function createHeatmapLayer() {
    const heatmapData = allCrashData.map(crash => [
        crash.lat,
        crash.lon,
        0.5
    ]);

    heatmapLayer = L.heatLayer(heatmapData, {
        radius: 25,
        blur: 15,
        maxZoom: 17,
        max: 1.0,
        gradient: {
            0.0: 'blue',
            0.25: 'cyan',
            0.5: 'lime',
            0.75: 'yellow',
            1.0: 'red'
        }
    });
}

function createSampleHeatmapData() {
    const sampleData = [];
    const cities = {
        sf: { lat: 37.76, lon: -122.42, count: 500 },
        phoenix: { lat: 33.45, lon: -112.07, count: 300 },
        la: { lat: 34.05, lon: -118.24, count: 200 }
    };

    Object.values(cities).forEach(city => {
        for (let i = 0; i < city.count; i++) {
            sampleData.push([
                city.lat + (Math.random() - 0.5) * 0.1,
                city.lon + (Math.random() - 0.5) * 0.1,
                0.5
            ]);
        }
    });

    heatmapLayer = L.heatLayer(sampleData, {
        radius: 25,
        blur: 15,
        maxZoom: 17
    });
}

// =======================
// Show/Hide Heatmap
// =======================
function showHeatmap() {
    if (heatmapLayer && !map.hasLayer(heatmapLayer)) {
        heatmapLayer.addTo(map);
        isHeatmapVisible = true;
    }
    document.getElementById('heatmap-legend')?.classList.add('visible');
}

function hideHeatmap() {
    if (heatmapLayer && map.hasLayer(heatmapLayer)) {
        map.removeLayer(heatmapLayer);
        isHeatmapVisible = false;
    }
    document.getElementById('heatmap-legend')?.classList.remove('visible');
}

// =======================
// Serious Incident Markers (SF only)
// =======================
function createSeriousIncidentMarkers() {
    // Clear existing markers
    seriousIncidentMarkers.forEach(marker => map.removeLayer(marker));
    seriousIncidentMarkers = [];

    if (!seriousIncidentsData || !seriousIncidentsData.sf_incidents) {
        console.warn('No serious incidents data available');
        return;
    }

    console.log(`Creating ${seriousIncidentsData.sf_incidents.length} markers`);

    // Create markers for each SF serious incident
    seriousIncidentsData.sf_incidents.forEach((incident, index) => {
        // All markers use the same accent color
        const markerHtml = `
            <div class="serious-marker pulse">
                <span class="marker-number">${index + 1}</span>
            </div>
        `;

        const icon = L.divIcon({
            className: 'serious-marker-container',
            html: markerHtml,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        const marker = L.marker([incident.lat, incident.lon], { icon })
            .on('click', () => showSeriousIncidentPanel(incident));

        seriousIncidentMarkers.push(marker);
        console.log(`Created marker ${index + 1} at [${incident.lat}, ${incident.lon}]`);
    });
}

function showSeriousIncidentMarkers() {
    if (seriousIncidentMarkers.length === 0) {
        createSeriousIncidentMarkers();
    }

    console.log(`Showing ${seriousIncidentMarkers.length} markers on map`);

    seriousIncidentMarkers.forEach(marker => {
        if (!map.hasLayer(marker)) {
            marker.addTo(map);
        }
    });
    areMarkersVisible = true;
}

function hideSeriousIncidentMarkers() {
    seriousIncidentMarkers.forEach(marker => map.removeLayer(marker));
    areMarkersVisible = false;
}

// =======================
// Serious Incident Panel
// =======================
function showSeriousIncidentPanel(incident) {
    const panel = document.getElementById('crash-panel');
    const content = document.getElementById('panel-content');

    // Format time nicely
    let timeDisplay = incident.time;
    if (incident.time && incident.time !== 'Time not available') {
        const [hours, minutes] = incident.time.split(':');
        const h = parseInt(hours);
        const ampm = h >= 12 ? 'PM' : 'AM';
        const hour12 = h % 12 || 12;
        timeDisplay = `${hour12}:${minutes} ${ampm}`;
    }

    // Get crash party icon
    const partyIcons = {
        'Vehicle': '🚗',
        'Motorcyclist': '🏍️',
        'Cyclist': '🚴',
        'Pedestrian': '🚶',
        'Animal': '🦌',
        'Fixed Object': '🚧',
        'Scooter': '🛴'
    };

    let partyIcon = '🚗';
    Object.keys(partyIcons).forEach(key => {
        if (incident.crash_party.toLowerCase().includes(key.toLowerCase())) {
            partyIcon = partyIcons[key];
        }
    });

    content.innerHTML = `
        <h3>Incident #${incident.id}</h3>
        <div class="severity-badge severity-${incident.severity.toLowerCase().replace(/\s+/g, '-').replace(/[()]/g, '')}">
            ${incident.severity}
        </div>
        <div class="crash-meta">
            <span>📅 ${incident.date}</span>
            <span>🕐 ${timeDisplay}</span>
        </div>
        <div class="crash-party">
            <span class="party-icon">${partyIcon}</span>
            <span class="party-label">Crash Party: <strong>${incident.crash_party}</strong></span>
        </div>
        <div class="crash-location">
            <span>📍 ${incident.address}</span>
        </div>
        <div class="crash-narrative">
            <h4>Incident Narrative</h4>
            <p>${incident.narrative}</p>
        </div>
        <div class="crash-tags">
            <span class="crash-tag">${incident.crash_type}</span>
            <span class="crash-tag">${incident.city}</span>
        </div>
    `;

    panel.classList.add('visible');
}

function hideCrashPanel() {
    document.getElementById('crash-panel')?.classList.remove('visible');
}

function initPanelClose() {
    document.getElementById('panel-close')?.addEventListener('click', hideCrashPanel);
}

// =======================
// Zipcode Search Feature
// =======================
function initZipcodeSearch() {
    const searchBtn = document.getElementById('zipcode-search-btn');
    const input = document.getElementById('zipcode-input');

    if (searchBtn) {
        searchBtn.addEventListener('click', performZipcodeSearch);
    }

    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performZipcodeSearch();
            }
        });
    }
}

async function performZipcodeSearch() {
    const input = document.getElementById('zipcode-input');
    const resultsDiv = document.getElementById('zipcode-results');
    const zipcode = input?.value.trim();

    if (!zipcode || zipcode.length !== 5 || !/^\d{5}$/.test(zipcode)) {
        if (resultsDiv) {
            resultsDiv.innerHTML = '<p class="error">Please enter a valid 5-digit zipcode.</p>';
        }
        return;
    }

    // Show loading
    if (resultsDiv) {
        resultsDiv.innerHTML = '<p class="loading">Searching...</p>';
    }

    try {
        // Use a free geocoding API to get zipcode coordinates
        const response = await fetch(`https://api.zippopotam.us/us/${zipcode}`);

        if (!response.ok) {
            throw new Error('Zipcode not found');
        }

        const data = await response.json();
        const userLat = parseFloat(data.places[0].latitude);
        const userLon = parseFloat(data.places[0].longitude);
        const userCity = data.places[0]['place name'];
        const userState = data.places[0]['state abbreviation'];

        // Find nearest city with Waymo crashes
        let nearestCity = null;
        let nearestDistance = Infinity;

        Object.entries(CITY_DATA).forEach(([cityName, cityInfo]) => {
            const distance = calculateDistance(userLat, userLon, cityInfo.lat, cityInfo.lon);
            if (distance < nearestDistance) {
                nearestDistance = distance;
                nearestCity = { name: cityName, ...cityInfo, distance };
            }
        });

        // Get total crashes for nearest city
        let crashCount = 'multiple';
        if (seriousIncidentsData && seriousIncidentsData.city_data && seriousIncidentsData.city_data[nearestCity.name]) {
            crashCount = seriousIncidentsData.city_data[nearestCity.name].count;
        }

        // Display results
        if (resultsDiv) {
            resultsDiv.innerHTML = `
                <div class="zipcode-result">
                    <h4>Your Location</h4>
                    <p>${userCity}, ${userState} (${zipcode})</p>

                    <h4>Nearest City with Waymo Crashes</h4>
                    <div class="nearest-city">
                        <span class="city-name">${nearestCity.name}, ${nearestCity.state}</span>
                        <span class="city-distance">~${Math.round(nearestDistance)} miles away</span>
                    </div>

                    <p class="crash-count">
                        <strong>${crashCount}</strong> serious/moderate injury incidents recorded
                    </p>

                    <button class="view-on-map-btn" onclick="flyToCity('${nearestCity.name}')">
                        View on Map
                    </button>
                </div>
            `;
        }

    } catch (error) {
        console.error('Zipcode lookup error:', error);
        if (resultsDiv) {
            resultsDiv.innerHTML = '<p class="error">Could not find that zipcode. Please try again.</p>';
        }
    }
}

// Calculate distance between two points (Haversine formula)
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 3959; // Earth's radius in miles
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function toRad(deg) {
    return deg * (Math.PI / 180);
}

// Fly to a specific city on the map
function flyToCity(cityName) {
    const city = CITY_DATA[cityName];
    if (city) {
        map.flyTo([city.lat, city.lon], 11, { duration: 2 });
        showHeatmap();
    }
}

// Make flyToCity globally accessible
window.flyToCity = flyToCity;

// =======================
// Scrollytelling
// =======================
function initScrollytelling() {
    const steps = document.querySelectorAll('.scrolly-step');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const step = entry.target.dataset.step;
                if (step !== currentStep) {
                    handleStepChange(step);
                    currentStep = step;
                }
                entry.target.classList.add('active');
            } else {
                entry.target.classList.remove('active');
            }
        });
    }, {
        threshold: 0.5,
        rootMargin: '-10% 0px -10% 0px'
    });

    steps.forEach(step => observer.observe(step));
}

function handleStepChange(step) {
    console.log('Step change:', step);

    // Hide scroll hint after first step
    if (step !== 'intro') {
        document.getElementById('scroll-hint')?.classList.add('hidden');
    }

    // Show/hide map overlay for text readability
    const overlay = document.getElementById('map-overlay');

    switch(step) {
        case 'intro':
            map.flyTo(CONFIG.views.us.center, CONFIG.views.us.zoom, { duration: CONFIG.animation.zoomDuration });
            hideHeatmap();
            hideSeriousIncidentMarkers();
            hideCrashPanel();
            overlay?.classList.remove('visible');
            break;

        case 'us-overview':
            map.flyTo(CONFIG.views.us.center, CONFIG.views.us.zoom, { duration: CONFIG.animation.zoomDuration });
            showHeatmap();
            hideSeriousIncidentMarkers();
            hideCrashPanel();
            overlay?.classList.add('visible');
            break;

        case 'zoom-california':
            map.flyTo(CONFIG.views.california.center, CONFIG.views.california.zoom, { duration: CONFIG.animation.zoomDuration });
            showHeatmap();
            hideSeriousIncidentMarkers();
            hideCrashPanel();
            overlay?.classList.add('visible');
            break;

        case 'sf-heatmap':
            map.flyTo(CONFIG.views.sfHeatmap.center, CONFIG.views.sfHeatmap.zoom, { duration: CONFIG.animation.zoomDuration });
            showHeatmap();
            hideSeriousIncidentMarkers();
            hideCrashPanel();
            overlay?.classList.add('visible');
            break;

        case 'sf-transition':
            // Keep same view, prepare for transition
            showHeatmap();
            hideSeriousIncidentMarkers();
            hideCrashPanel();
            overlay?.classList.add('visible');
            break;

        case 'sf-hotspots':
            map.flyTo(CONFIG.views.sfHotspots.center, CONFIG.views.sfHotspots.zoom, { duration: CONFIG.animation.zoomDuration });
            // Fade out heatmap and show serious incident markers
            setTimeout(() => {
                hideHeatmap();
                showSeriousIncidentMarkers();
            }, 500);
            overlay?.classList.add('visible');
            break;

        case 'transition':
            // Zoom back out slightly
            map.flyTo([37.76, -122.42], 11, { duration: CONFIG.animation.zoomDuration });
            showHeatmap();
            hideSeriousIncidentMarkers();
            hideCrashPanel();
            overlay?.classList.add('visible');
            break;

        // Handle temporal section steps
        case 'temporal-intro':
        case 'temporal-heatmap':
        case 'temporal-weekly':
        case 'temporal-periods':
            break;

        // Handle spatial section steps
        case 'spatial-intro':
        case 'spatial-locations':
        case 'spatial-weekend':
        case 'spatial-weekday':
            break;
    }
}

// =======================
// Progress Bar
// =======================
function initProgressBar() {
    const progressFill = document.getElementById('progress-fill');

    window.addEventListener('scroll', () => {
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight - windowHeight;
        const scrolled = window.scrollY;
        const progress = (scrolled / documentHeight) * 100;

        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
    });
}

// =======================
// Navigation
// =======================
function initNavigation() {
    const navbar = document.querySelector('.navbar');
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links');

    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            navbar?.classList.add('scrolled');
        } else {
            navbar?.classList.remove('scrolled');
        }
    });

    navToggle?.addEventListener('click', () => {
        navLinks?.classList.toggle('active');
    });

    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href');
            const target = document.querySelector(targetId);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
                navLinks?.classList.remove('active');
            }
        });
    });
}

// =======================
// Stat Counters Animation
// =======================
function initStatCounters() {
    const statCards = document.querySelectorAll('.stat-number[data-count]');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    statCards.forEach(card => observer.observe(card));
}

function animateCounter(element) {
    const target = parseInt(element.dataset.count);
    const suffix = element.dataset.suffix || '';
    const duration = 2000;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(easeOut * target);

        element.textContent = current.toLocaleString() + suffix;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// =======================
// Figure Switching for Scrollytelling
// =======================
const figureMapping = {
    'temporal-intro': 'figures/02_time_of_day_analysis/time_of_day_analysis.png',
    'temporal-heatmap': 'figures/02_time_of_day_analysis/time_of_day_analysis.png',
    'temporal-weekly': 'figures/02_time_of_day_analysis/time_of_day_analysis.png',
    'temporal-periods': 'figures/02_time_of_day_analysis/time_insights_summary.png',
    'spatial-intro': 'figures/02_time_of_day_analysis/location_time_analysis.png',
    'spatial-locations': 'figures/02_time_of_day_analysis/location_time_analysis.png',
    'spatial-weekend': 'figures/02_time_of_day_analysis/location_time_analysis.png',
    'spatial-weekday': 'figures/02_time_of_day_analysis/location_time_analysis.png'
};

// Wrap handleStepChange to also update figures
const originalHandleStepChange = handleStepChange;
handleStepChange = function(step) {
    originalHandleStepChange(step);

    if (figureMapping[step]) {
        const temporalFig = document.getElementById('temporal-figure');
        const spatialFig = document.getElementById('spatial-figure');

        if (step.startsWith('temporal') && temporalFig) {
            temporalFig.src = figureMapping[step];
        } else if (step.startsWith('spatial') && spatialFig) {
            spatialFig.src = figureMapping[step];
        }
    }
};
