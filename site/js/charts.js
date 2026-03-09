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
const Charts = (function () {

    // Shared color constants (earth tone palette)
    const GREY = "#b8b0a6";
    const ACCENT = "#8b6f47";
    const BORDER_COLOR = "#d4d0cc";
    const TEXT_COLOR = "#6b6b6b";
    const TEXT_DARK = "#333333";

    // Shared font settings for the editorial look
    const MONO_FONT = "'IBM Plex Mono', 'Courier New', monospace";
    const BODY_FONT = "'Inter', sans-serif";

    /**
     * Shared defaults for all charts — minimal, editorial style.
     */
    function getDefaults() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#1a1a1a",
                    titleFont: { family: MONO_FONT, size: 12 },
                    bodyFont: { family: MONO_FONT, size: 12 },
                    padding: 10,
                    cornerRadius: 0,
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
        const canvas = document.getElementById("hourly-chart");
        if (!canvas || !stats.temporal || !stats.temporal.hourly_distribution) return;

        const hourly = stats.temporal.hourly_distribution;

        // Build arrays for hours 0–23
        const labels = [];
        const values = [];
        for (let h = 0; h < 24; h++) {
            // Show labels at every 3 hours for readability
            if (h % 3 === 0) {
                labels.push(formatHourLabel(h));
            } else {
                labels.push("");
            }
            values.push(hourly[String(h)] || 0);
        }

        // Find the peak hour to highlight it
        const maxVal = Math.max(...values);
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

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
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
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
                        },
                        border: { display: false },
                    },
                },
                plugins: {
                    ...getDefaults().plugins,
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            title: function(items) {
                                const hour = items[0].dataIndex;
                                return formatHourLabel(hour);
                            },
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
    // Chart 2: Day of Week (horizontal bar chart)
    // ============================================

    /**
     * Build a horizontal bar chart showing crashes per day of the week.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function buildDayOfWeekChart(stats) {
        const canvas = document.getElementById("day-chart");
        if (!canvas || !stats.day_of_week) return;

        const dayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        const shortLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        const values = dayOrder.map(d => stats.day_of_week[d] || 0);

        // Highlight the peak day
        const maxVal = Math.max(...values);
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

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
                indexAxis: "y",
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
                            title: function(items) {
                                return dayOrder[items[0].dataIndex];
                            },
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

        // Sort by count descending
        const sorted = Object.entries(stats.location_types)
            .sort((a, b) => b[1].count - a[1].count);

        const labels = sorted.map(([name]) => name);
        const values = sorted.map(([, info]) => info.count);
        const pcts = sorted.map(([, info]) => info.percentage);

        // Highlight the top category
        const maxVal = Math.max(...values);
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

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
                indexAxis: "y",
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
        if (!canvas || !stats.crash_circumstances || !stats.crash_circumstances.speed_distribution) return;

        const dist = stats.crash_circumstances.speed_distribution;
        const bucketOrder = ["0_mph", "1_5_mph", "6_15_mph", "16_25_mph", "26_35_mph", "36_plus_mph"];
        const bucketLabels = ["0 mph", "1–5 mph", "6–15 mph", "16–25 mph", "26–35 mph", "36+ mph"];

        const values = bucketOrder.map(k => dist[k] ? dist[k].count : 0);
        const pcts = bucketOrder.map(k => dist[k] ? dist[k].percentage : 0);

        // Highlight the 0 mph bar — the key finding
        const colors = bucketOrder.map(k => k === "0_mph" ? ACCENT : GREY);

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
                indexAxis: "y",
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

        // Sort by count descending
        const sorted = Object.entries(stats.crash_circumstances.crash_type_plain)
            .sort((a, b) => b[1].count - a[1].count);

        const labels = sorted.map(([name]) => name);
        const values = sorted.map(([, info]) => info.count);
        const pcts = sorted.map(([, info]) => info.percentage);

        // Highlight the top category
        const maxVal = Math.max(...values);
        const colors = values.map(v => v === maxVal ? ACCENT : GREY);

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
                indexAxis: "y",
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
    // Utility
    // ============================================

    /** Convert hour number to label: 0 → "12am", 13 → "1pm", etc. */
    function formatHourLabel(hour) {
        if (hour === 0) return "12am";
        if (hour === 12) return "12pm";
        if (hour < 12) return hour + "am";
        return (hour - 12) + "pm";
    }

    // Public API
    return {
        buildHourlyChart,
        buildDayOfWeekChart,
        buildLocationTypeChart,
        buildSpeedChart,
        buildCrashTypeChart,
    };
})();
