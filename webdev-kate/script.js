/**
 * Waymo Crash Data Analysis - Scrollytelling Interactive Article
 * Features: Map zooming on scroll, interactive crash markers, figure scrollytelling
 */

// ============================================
// Configuration
// ============================================
const CONFIG = {
    // Map view states for scroll progression
    mapViews: {
        'intro': { center: [39.8283, -98.5795], zoom: 4 },           // US center
        'us-overview': { center: [37.0902, -95.7129], zoom: 4 },     // US with markers visible
        'zoom-california': { center: [36.7783, -119.4179], zoom: 6 }, // California
        'sf-focus': { center: [37.7749, -122.4194], zoom: 12 },       // San Francisco
        'sf-hotspots': { center: [37.7749, -122.4194], zoom: 13 },    // SF closer with markers
        'transition': { center: [37.7749, -122.4194], zoom: 11 }      // Zoom out slightly
    },

    // City locations for map markers
    cities: [
        { name: 'San Francisco', coords: [37.7749, -122.4194], crashes: '~600' },
        { name: 'Phoenix', coords: [33.4484, -112.0740], crashes: '~470' },
        { name: 'Los Angeles', coords: [34.0522, -118.2437], crashes: '~160' },
        { name: 'Austin', coords: [30.2672, -97.7431], crashes: '~70' },
        { name: 'Atlanta', coords: [33.7490, -84.3880], crashes: '~40' }
    ],

    // Three featured SF crash incidents (representative examples)
    featuredCrashes: [
        {
            id: 1,
            coords: [37.7815, -122.4096],   // Financial District
            title: 'Financial District Incident',
            date: 'September 15, 2023',
            time: '5:42 PM',
            type: 'V2V Lateral',
            address: 'Market St & 3rd St, San Francisco',
            severity: 'low',
            severityScore: 1,
            description: 'The Waymo vehicle was traveling eastbound on Market Street when a human-driven vehicle changed lanes without signaling, making contact with the right side of the AV. The Waymo vehicle detected the intrusion and initiated braking, minimizing impact force.',
            indicators: {
                policeReported: true,
                injuryReported: false,
                airbagDeployed: false,
                seriousInjury: false
            }
        },
        {
            id: 2,
            coords: [37.7589, -122.4148],   // Mission District
            title: 'Mission District Incident',
            date: 'January 8, 2024',
            time: '2:15 PM',
            type: 'V2V Rear-End',
            address: 'Mission St & 16th St, San Francisco',
            severity: 'low',
            severityScore: 0,
            description: 'While stopped at a red light, the Waymo vehicle was rear-ended by a following human-driven vehicle. The impact was minor with no injuries reported. The AV\'s sensors captured the entire incident, providing clear documentation.',
            indicators: {
                policeReported: false,
                injuryReported: false,
                airbagDeployed: false,
                seriousInjury: false
            }
        },
        {
            id: 3,
            coords: [37.7879, -122.4074],   // Union Square area
            title: 'Union Square Incident',
            date: 'March 22, 2024',
            time: '11:30 AM',
            type: 'Pedestrian Contact',
            address: 'Powell St & Geary St, San Francisco',
            severity: 'medium',
            severityScore: 3,
            description: 'A pedestrian stepped into the crosswalk against the signal while looking at their phone. The Waymo vehicle, which had a green light, detected the pedestrian and initiated emergency braking, reducing speed significantly before minor contact occurred.',
            indicators: {
                policeReported: true,
                injuryReported: true,
                airbagDeployed: false,
                seriousInjury: false
            }
        }
    ]
};

// ============================================
// Global State
// ============================================
let map = null;
let currentStep = 'intro';
let cityMarkers = [];
let crashMarkers = [];
let isMapReady = false;

// ============================================
// Initialize Application
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    initScrollytelling();
    initNavigation();
    initProgressBar();
    initCrashPanel();
    initStatCards();
});

// ============================================
// Map Initialization
// ============================================
function initMap() {
    // Create Leaflet map
    map = L.map('main-map', {
        center: CONFIG.mapViews.intro.center,
        zoom: CONFIG.mapViews.intro.zoom,
        zoomControl: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        dragging: true,
        attributionControl: true
    });

    // Add tile layer (CartoDB Positron for clean look)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    // Add zoom control to bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Add city markers
    addCityMarkers();

    isMapReady = true;
}

function addCityMarkers() {
    CONFIG.cities.forEach(city => {
        const marker = L.circleMarker(city.coords, {
            radius: 8,
            fillColor: '#3182ce',
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map);

        // Add tooltip
        marker.bindTooltip(`<strong>${city.name}</strong><br>${city.crashes} crashes`, {
            permanent: false,
            direction: 'top',
            className: 'city-tooltip'
        });

        cityMarkers.push(marker);
    });
}

function addCrashHotspots() {
    // Remove existing crash markers first
    crashMarkers.forEach(m => map.removeLayer(m));
    crashMarkers = [];

    CONFIG.featuredCrashes.forEach(crash => {
        // Create pulsing marker
        const icon = L.divIcon({
            className: 'crash-marker-container',
            html: `<div class="crash-marker-pulse"></div><div class="crash-marker-dot"></div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });

        const marker = L.marker(crash.coords, { icon: icon }).addTo(map);

        // Click handler
        marker.on('click', () => showCrashPanel(crash));

        // Hover effects
        marker.on('mouseover', function() {
            this.getElement().classList.add('hovered');
        });
        marker.on('mouseout', function() {
            this.getElement().classList.remove('hovered');
        });

        crashMarkers.push(marker);
    });

    // Add styles for crash markers dynamically
    if (!document.getElementById('crash-marker-styles')) {
        const style = document.createElement('style');
        style.id = 'crash-marker-styles';
        style.textContent = `
            .crash-marker-container {
                position: relative;
            }
            .crash-marker-dot {
                width: 16px;
                height: 16px;
                background: #e53e3e;
                border: 3px solid white;
                border-radius: 50%;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                cursor: pointer;
                transition: transform 0.2s ease;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            }
            .crash-marker-pulse {
                width: 30px;
                height: 30px;
                background: rgba(229, 62, 62, 0.4);
                border-radius: 50%;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                animation: crash-pulse 2s infinite;
            }
            @keyframes crash-pulse {
                0% { transform: translate(-50%, -50%) scale(0.5); opacity: 1; }
                100% { transform: translate(-50%, -50%) scale(2); opacity: 0; }
            }
            .crash-marker-container.hovered .crash-marker-dot {
                transform: translate(-50%, -50%) scale(1.3);
            }
            .crash-marker-container.hovered .crash-marker-pulse {
                animation: none;
                opacity: 0;
            }
        `;
        document.head.appendChild(style);
    }
}

function removeCrashHotspots() {
    crashMarkers.forEach(m => map.removeLayer(m));
    crashMarkers = [];
}

function updateMapView(stepId, animate = true) {
    if (!isMapReady || !CONFIG.mapViews[stepId]) return;

    const view = CONFIG.mapViews[stepId];
    const options = animate ? { duration: 1.5, easeLinearity: 0.25 } : {};

    map.flyTo(view.center, view.zoom, options);

    // Handle crash hotspots visibility
    if (stepId === 'sf-hotspots') {
        setTimeout(() => addCrashHotspots(), 800);
    } else if (stepId !== 'sf-focus') {
        removeCrashHotspots();
    }

    // Update map overlay
    const overlay = document.getElementById('map-overlay');
    if (stepId !== 'intro' && stepId !== 'us-overview') {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }

    // Hide scroll hint after first step
    const scrollHint = document.getElementById('scroll-hint');
    if (stepId !== 'intro') {
        scrollHint.classList.add('hidden');
    }
}

// ============================================
// Scrollytelling
// ============================================
function initScrollytelling() {
    const steps = document.querySelectorAll('.scrolly-step');

    // Intersection Observer for scroll-triggered steps
    const observerOptions = {
        root: null,
        rootMargin: '-40% 0px -40% 0px', // Trigger when step is in middle 20% of viewport
        threshold: 0
    };

    const stepObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const stepId = entry.target.dataset.step;

                // Update active state
                steps.forEach(s => s.classList.remove('is-active'));
                entry.target.classList.add('is-active');

                // Update map if this is a map step
                if (CONFIG.mapViews[stepId]) {
                    updateMapView(stepId);
                }

                currentStep = stepId;
            }
        });
    }, observerOptions);

    steps.forEach(step => {
        stepObserver.observe(step);
    });
}

// ============================================
// Crash Detail Panel
// ============================================
function initCrashPanel() {
    const panel = document.getElementById('crash-panel');
    const closeBtn = document.getElementById('panel-close');

    closeBtn.addEventListener('click', () => {
        panel.classList.remove('active');
    });

    // Close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            panel.classList.remove('active');
        }
    });

    // Close when clicking outside panel (on map)
    document.getElementById('main-map').addEventListener('click', (e) => {
        // Only close if clicking on map, not on a marker
        if (e.target.classList.contains('leaflet-container') ||
            e.target.classList.contains('leaflet-tile')) {
            panel.classList.remove('active');
        }
    });
}

function showCrashPanel(crash) {
    const panel = document.getElementById('crash-panel');
    const content = document.getElementById('panel-content');

    // Build severity badge class
    const severityClass = crash.severity === 'low' ? 'severity-low' :
                         crash.severity === 'medium' ? 'severity-medium' : 'severity-high';

    // Build indicator HTML
    const indicatorHtml = Object.entries(crash.indicators).map(([key, value]) => {
        const label = key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
        const dotClass = value ? 'yes' : 'no';
        const valueText = value ? 'Yes' : 'No';
        return `
            <div class="indicator-item">
                <span class="indicator-dot ${dotClass}"></span>
                <span>${label}: ${valueText}</span>
            </div>
        `;
    }).join('');

    content.innerHTML = `
        <div class="panel-header">
            <h3>${crash.title}</h3>
            <p class="panel-meta">${crash.date} at ${crash.time}</p>
        </div>

        <div class="panel-section">
            <h4>Crash Type</h4>
            <p>${crash.type}</p>
        </div>

        <div class="panel-section">
            <h4>Location</h4>
            <p>${crash.address}</p>
        </div>

        <div class="panel-section">
            <h4>Severity</h4>
            <span class="severity-badge ${severityClass}">
                Score: ${crash.severityScore}/8
            </span>
        </div>

        <div class="panel-section">
            <h4>Incident Description</h4>
            <p>${crash.description}</p>
        </div>

        <div class="panel-section">
            <h4>Severity Indicators</h4>
            <div class="panel-indicators">
                ${indicatorHtml}
            </div>
        </div>
    `;

    panel.classList.add('active');

    // Center map on crash location
    map.flyTo(crash.coords, 15, { duration: 0.8 });
}

// ============================================
// Navigation
// ============================================
function initNavigation() {
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links');
    const navbar = document.querySelector('.navbar');

    // Mobile toggle
    if (navToggle && navLinks) {
        navToggle.addEventListener('click', function() {
            this.classList.toggle('active');
            navLinks.classList.toggle('active');
        });

        // Close on link click
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navToggle.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });
    }

    // Smooth scroll for nav links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const navHeight = navbar?.offsetHeight || 0;
                const targetPosition = target.getBoundingClientRect().top + window.scrollY - navHeight - 20;
                window.scrollTo({ top: targetPosition, behavior: 'smooth' });
            }
        });
    });

    // Navbar scroll effect
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
}

// ============================================
// Progress Bar
// ============================================
function initProgressBar() {
    const progressFill = document.getElementById('progress-fill');

    window.addEventListener('scroll', () => {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = (scrollTop / docHeight) * 100;
        progressFill.style.width = `${scrollPercent}%`;
    });
}

// ============================================
// Stat Cards Animation
// ============================================
function initStatCards() {
    const statCards = document.querySelectorAll('.stat-card');

    const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                // Stagger animation
                setTimeout(() => {
                    entry.target.classList.add('visible');

                    // Animate counter if present
                    const counter = entry.target.querySelector('.stat-number[data-count]');
                    if (counter) {
                        animateCounter(counter);
                    }
                }, index * 100);

                cardObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    statCards.forEach(card => {
        cardObserver.observe(card);
    });
}

function animateCounter(element) {
    const target = parseFloat(element.dataset.count);
    const decimals = parseInt(element.dataset.decimals) || 0;
    const suffix = element.dataset.suffix || '';
    const duration = 2000;
    const frameDuration = 1000 / 60;
    const totalFrames = Math.round(duration / frameDuration);
    const easeOutQuad = t => t * (2 - t);

    let frame = 0;
    const counter = setInterval(() => {
        frame++;
        const progress = easeOutQuad(frame / totalFrames);
        const currentCount = target * progress;

        if (decimals > 0) {
            element.textContent = currentCount.toFixed(decimals) + suffix;
        } else {
            element.textContent = Math.round(currentCount).toLocaleString() + suffix;
        }

        if (frame === totalFrames) {
            clearInterval(counter);
            if (decimals > 0) {
                element.textContent = target.toFixed(decimals) + suffix;
            } else {
                element.textContent = target.toLocaleString() + suffix;
            }
        }
    }, frameDuration);
}

// ============================================
// Figure Scrollytelling (for non-map sections)
// ============================================
// The CSS handles the sticky figure positioning
// Steps are revealed via Intersection Observer in initScrollytelling()

// ============================================
// Console Welcome
// ============================================
console.log(`
%c Waymo Crash Data Analysis - Scrollytelling Edition
%c Interactive data journalism exploring autonomous vehicle safety patterns.
%c Scroll to explore the data story.
`,
'color: #1a365d; font-size: 16px; font-weight: bold;',
'color: #718096; font-size: 12px;',
'color: #3182ce; font-size: 11px;');
