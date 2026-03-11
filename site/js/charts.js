/**
 * charts.js — Interactive charts using Chart.js
 * ================================================
 * Replaces the static matplotlib PNG images with interactive,
 * responsive charts that read from site-data.json.
 *
 * Charts created:
 *   1. Hourly distribution — bar chart (24 hours)
 *   2. Day of week — horizontal bar chart (Mon–Sun)
 *   3. Location type — horizontal bar chart
 *
 * Style: editorial / minimalist — monospace labels, muted colors,
 * minimal grid, no legends. Matches the Works in Progress aesthetic.
 *
 * Dependencies:
 *   - Chart.js (loaded from CDN in index.html)
 *   - site-data.json (passed in from app.js)
 */

// ============================================
// Charts Module
// ============================================

// IIFE module pattern — keeps all variables private, only exposes what we return at the bottom
const Charts = (function () {

    // Shared color constants (earth tone palette)
    const GREY = "#b8b0a6";        // Default bar color
    const ACCENT = "#8b6f47";      // Highlighted bar color (for peak values)
    const BORDER_COLOR = "#d4d0cc"; // Grid line and axis border color
    const TEXT_COLOR = "#6b6b6b";   // Light text for axis ticks
    const TEXT_DARK = "#333333";    // Darker text for category labels

    // Shared font settings for the editorial look
    const MONO_FONT = "'IBM Plex Mono', 'Courier New', monospace";
    const BODY_FONT = "'Inter', sans-serif";

    /**
     * Shared defaults for all charts — minimal, editorial style.
     * Returns a config object that Chart.js uses for appearance settings.
     */
    function getDefaults() {
        return {
            responsive: true,               // Chart resizes with its container
            maintainAspectRatio: false,      // Let CSS control the height
            plugins: {
                legend: { display: false },  // Hide the legend (not needed for single-dataset charts)
                tooltip: {
                    backgroundColor: "#1a1a1a",                     // Dark tooltip background
                    titleFont: { family: MONO_FONT, size: 12 },     // Monospace font for tooltip title
                    bodyFont: { family: MONO_FONT, size: 12 },      // Monospace font for tooltip body
                    padding: 10,                                     // Space inside the tooltip
                    cornerRadius: 0,                                 // Sharp corners (editorial style)
                },
            },
        };
    }

    // ============================================
    // Chart 1: Hourly Distribution (bar chart)
    // ============================================

    /**
     * Build a vertical bar chart showing crash count per hour of day.
     * The peak hour is highlighted in accent color.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function buildHourlyChart(stats) {
        // Find the <canvas> element where Chart.js will draw
        const canvas = document.getElementById("hourly-chart");
        // If the canvas or data doesn't exist, exit early
        if (!canvas || !stats.temporal || !stats.temporal.hourly_distribution) return;

        // Get the hourly data object (keys are hour numbers "0" through "23")
        const hourly = stats.temporal.hourly_distribution;

        // Build arrays for hours 0–23
        const labels = [];  // X-axis labels
        const values = [];  // Bar heights (crash counts)
        for (let h = 0; h < 24; h++) {
            // Show labels at every 3 hours for readability (skip the rest)
            if (h % 3 === 0) {
                labels.push(formatHourLabel(h));
            } else {
                labels.push("");  // Empty string = no label shown
            }
            // Look up the crash count for this hour; default to 0 if missing
            values.push(hourly[String(h)] || 0);
        }

        // Find the highest value to highlight that bar
        // Math.max(...values) spreads the array into individual arguments
        const maxVal = Math.max(...values);
        // .map() creates a new array: accent color for the peak, grey for the rest
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

        // Create a new Chart.js bar chart on the canvas element
        new Chart(canvas, {
            type: "bar",           // Vertical bar chart
            data: {
                labels: labels,    // X-axis labels (hours)
                datasets: [{
                    data: values,              // The crash count values
                    backgroundColor: colors,   // Bar colors (grey + accent for peak)
                    borderWidth: 0,            // No border on bars
                    borderRadius: 0,           // Sharp corners on bars
                }],
            },
            options: {
                // ...getDefaults() spreads in all the shared defaults (responsive, tooltip style, etc.)
                ...getDefaults(),
                scales: {
                    x: {
                        grid: { display: false },  // Hide vertical grid lines
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },  // Monospace tick labels
                            color: TEXT_COLOR,
                        },
                        border: { color: BORDER_COLOR },  // X-axis line color
                    },
                    y: {
                        grid: {
                            color: BORDER_COLOR,    // Horizontal grid line color
                            drawTicks: false,       // Don't draw small tick marks
                        },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,             // Space between tick label and axis
                        },
                        border: { display: false }, // Hide the Y-axis line
                    },
                },
                plugins: {
                    ...getDefaults().plugins,  // Spread in shared plugin defaults
                    tooltip: {
                        ...getDefaults().plugins.tooltip,  // Spread in shared tooltip defaults
                        callbacks: {
                            // Custom tooltip title: show the formatted hour label
                            title: function(items) {
                                const hour = items[0].dataIndex;  // Which bar was hovered
                                return formatHourLabel(hour);
                            },
                            // Custom tooltip body: show "X crashes"
                            label: function(item) {
                                return item.raw + " crashes";  // item.raw = the actual value
                            },
                        },
                    },
                },
            },
        });
    }

    // ============================================
    // Chart 2: Day of Week (horizontal bar chart)
    // ============================================

    /**
     * Build a horizontal bar chart showing crashes per day of the week.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function buildDayOfWeekChart(stats) {
        // Find the <canvas> element for this chart
        const canvas = document.getElementById("day-chart");
        // Exit early if the canvas or data doesn't exist
        if (!canvas || !stats.day_of_week) return;

        // Define the order we want days displayed (Monday first)
        const dayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        // Short labels for the Y-axis
        const shortLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        // .map() pulls the crash count for each day in order
        const values = dayOrder.map(d => stats.day_of_week[d] || 0);

        // Highlight the peak day — same pattern as buildHourlyChart
        const maxVal = Math.max(...values);
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

        // Create a new Chart.js chart — similar to buildHourlyChart
        new Chart(canvas, {
            type: "bar",
            data: {
                labels: shortLabels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 0,
                    borderRadius: 0,
                }],
            },
            options: {
                ...getDefaults(),
                indexAxis: "y",    // "y" makes it a HORIZONTAL bar chart (bars go left to right)
                scales: {
                    x: {
                        grid: {
                            color: BORDER_COLOR,
                            drawTicks: false,
                        },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,
                        },
                        border: { display: false },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_DARK,  // Darker text for day labels
                        },
                        border: { color: BORDER_COLOR },
                    },
                },
                plugins: {
                    ...getDefaults().plugins,
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            // Show full day name in tooltip (e.g., "Wednesday" instead of "Wed")
                            title: function(items) {
                                return dayOrder[items[0].dataIndex];
                            },
                            // Similar to buildHourlyChart tooltip
                            label: function(item) {
                                return item.raw + " crashes";
                            },
                        },
                    },
                },
            },
        });
    }

    // ============================================
    // Chart 3: Location Type (horizontal bar chart)
    // ============================================

    /**
     * Build a horizontal bar chart showing crashes by location type.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function buildLocationTypeChart(stats) {
        const canvas = document.getElementById("location-chart");
        if (!canvas || !stats.location_types) return;

        // Sort location types by count, highest first
        // Object.entries() converts {key: value} into [[key, value], ...] array
        const sorted = Object.entries(stats.location_types)
            .sort((a, b) => b[1].count - a[1].count);

        // Destructuring: [name] grabs the first element (key), [, info] skips the first and grabs the second
        const labels = sorted.map(([name]) => name);
        const values = sorted.map(([, info]) => info.count);
        const pcts = sorted.map(([, info]) => info.percentage);

        // Highlight the top category — same pattern as above
        const maxVal = Math.max(...values);
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

        // Same pattern as buildDayOfWeekChart (horizontal bar)
        new Chart(canvas, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 0,
                    borderRadius: 0,
                }],
            },
            options: {
                ...getDefaults(),
                indexAxis: "y",  // Horizontal bar chart
                scales: {
                    x: {
                        grid: {
                            color: BORDER_COLOR,
                            drawTicks: false,
                        },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,
                        },
                        border: { display: false },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_DARK,
                        },
                        border: { color: BORDER_COLOR },
                    },
                },
                plugins: {
                    ...getDefaults().plugins,
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            // Show count AND percentage in tooltip
                            label: function(item) {
                                return item.raw + " crashes (" + pcts[item.dataIndex] + "%)";
                            },
                        },
                    },
                },
            },
        });
    }

    // ============================================
    // Chart 4: Speed Distribution (horizontal bar)
    // ============================================

    /**
     * Build a horizontal bar chart showing Waymo vehicle speed
     * at the time of crash. The 0 mph bar is highlighted to
     * emphasize that most crashes happen while stationary.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function buildSpeedChart(stats) {
        const canvas = document.getElementById("speed-chart");
        // Exit early if canvas or nested data path doesn't exist
        if (!canvas || !stats.crash_circumstances || !stats.crash_circumstances.speed_distribution) return;

        // Get the speed distribution data
        const dist = stats.crash_circumstances.speed_distribution;
        // Keys in the JSON data (matching the pipeline output)
        const bucketOrder = ["0_mph", "1_5_mph", "6_15_mph", "16_25_mph", "26_35_mph", "36_plus_mph"];
        // Human-readable labels for the Y-axis
        const bucketLabels = ["0 mph", "1–5 mph", "6–15 mph", "16–25 mph", "26–35 mph", "36+ mph"];

        // Pull count and percentage for each speed bucket
        const values = bucketOrder.map(k => dist[k] ? dist[k].count : 0);
        const pcts = bucketOrder.map(k => dist[k] ? dist[k].percentage : 0);

        // Highlight the 0 mph bar specifically — it's the key finding
        const colors = bucketOrder.map(k => k === "0_mph" ? ACCENT : GREY);

        // Same horizontal bar pattern as buildLocationTypeChart
        new Chart(canvas, {
            type: "bar",
            data: {
                labels: bucketLabels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 0,
                    borderRadius: 0,
                }],
            },
            options: {
                ...getDefaults(),
                indexAxis: "y",  // Horizontal bar chart
                scales: {
                    x: {
                        grid: {
                            color: BORDER_COLOR,
                            drawTicks: false,
                        },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,
                        },
                        border: { display: false },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_DARK,
                        },
                        border: { color: BORDER_COLOR },
                    },
                },
                plugins: {
                    ...getDefaults().plugins,
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            // Similar to buildLocationTypeChart tooltip
                            label: function(item) {
                                return item.raw + " crashes (" + pcts[item.dataIndex] + "%)";
                            },
                        },
                    },
                },
            },
        });
    }

    // ============================================
    // Chart 5: Crash Type (horizontal bar)
    // ============================================

    /**
     * Build a horizontal bar chart showing crash types in plain
     * English, sorted by count descending.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function buildCrashTypeChart(stats) {
        const canvas = document.getElementById("crash-type-chart");
        if (!canvas || !stats.crash_circumstances || !stats.crash_circumstances.crash_type_plain) return;

        // Sort by count descending — same pattern as buildLocationTypeChart
        const sorted = Object.entries(stats.crash_circumstances.crash_type_plain)
            .sort((a, b) => b[1].count - a[1].count);

        const labels = sorted.map(([name]) => name);
        const values = sorted.map(([, info]) => info.count);
        const pcts = sorted.map(([, info]) => info.percentage);

        // Highlight the top category
        const maxVal = Math.max(...values);
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

        // Same horizontal bar pattern as buildLocationTypeChart
        new Chart(canvas, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 0,
                    borderRadius: 0,
                }],
            },
            options: {
                ...getDefaults(),
                indexAxis: "y",  // Horizontal bar chart
                scales: {
                    x: {
                        grid: {
                            color: BORDER_COLOR,
                            drawTicks: false,
                        },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,
                        },
                        border: { display: false },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_DARK,
                        },
                        border: { color: BORDER_COLOR },
                    },
                },
                plugins: {
                    ...getDefaults().plugins,
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            // Similar to buildLocationTypeChart tooltip
                            label: function(item) {
                                return item.raw + " crashes (" + pcts[item.dataIndex] + "%)";
                            },
                        },
                    },
                },
            },
        });
    }

    // ============================================
    // Chart 6: Mileage Growth (line chart)
    // ============================================

    /**
     * Build a line chart showing Waymo's cumulative rider-only miles
     * over time, from the manually compiled mileage milestones data.
     *
     * @param {Object} mileageMilestones — mileage_milestones.json (from data/static/)
     */
    function buildMileageChart(mileageMilestones) {
        const canvas = document.getElementById("mileage-chart");
        // Exit early if canvas or data doesn't exist
        if (!canvas || !mileageMilestones || !mileageMilestones.milestones) return;

        const milestones = mileageMilestones.milestones;

        // Build labels (formatted dates) and values (miles in millions)
        const labels = milestones.map(m => {
            // Parse the date string and format as "Mon YYYY" (e.g., "Jan 2023")
            const d = new Date(m.date);
            return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
        });
        const values = milestones.map(m => m.miles_millions);

        // Create a line chart showing exponential mileage growth
        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    borderColor: ACCENT,           // Line color (earth tone brown)
                    backgroundColor: ACCENT + "20", // Fill under line (same color, very transparent)
                    fill: true,                     // Fill the area under the line
                    borderWidth: 2.5,               // Line thickness
                    pointRadius: 5,                 // Size of the data point dots
                    pointBackgroundColor: ACCENT,   // Fill color of dots
                    pointBorderColor: "#fff",       // White border on dots
                    pointBorderWidth: 2,            // Dot border thickness
                    pointHoverRadius: 7,            // Larger dot on hover
                    tension: 0.3,                   // Slight curve smoothing (0 = straight lines)
                }],
            },
            options: {
                ...getDefaults(),
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            maxRotation: 45,        // Rotate labels if they overlap
                        },
                        border: { color: BORDER_COLOR },
                    },
                    y: {
                        grid: {
                            color: BORDER_COLOR,
                            drawTicks: false,
                        },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,
                            // Format Y-axis as "50M", "100M", etc.
                            callback: function(value) {
                                return value + "M";
                            },
                        },
                        border: { display: false },
                        beginAtZero: true,          // Y-axis starts at 0
                    },
                },
                plugins: {
                    ...getDefaults().plugins,
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            // Show date and miles in tooltip
                            title: function(items) {
                                return labels[items[0].dataIndex];
                            },
                            label: function(item) {
                                return item.raw + " million rider-only miles";
                            },
                            // Show the source for this data point
                            afterLabel: function(item) {
                                const milestone = milestones[item.dataIndex];
                                return "Source: " + (milestone.source || "");
                            },
                        },
                    },
                },
            },
        });
    }

    // ============================================
    // Utility
    // ============================================

    /** Convert hour number to label: 0 → "12am", 13 → "1pm", etc. */
    function formatHourLabel(hour) {
        if (hour === 0) return "12am";   // Midnight special case
        if (hour === 12) return "12pm";  // Noon special case
        if (hour < 12) return hour + "am";       // Morning hours
        return (hour - 12) + "pm";               // Afternoon/evening hours
    }

    // Public API — these 6 functions are the only things accessible from outside the module
    return {
        buildHourlyChart,
        buildDayOfWeekChart,
        buildLocationTypeChart,
        buildSpeedChart,
        buildCrashTypeChart,
        buildMileageChart,
    };

// The closing })() immediately runs the function and stores the returned object in Charts
})();
