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

    // Tooltip descriptions for each crash type — shown on hover to help
    // readers understand what each category means in practice.
    const CRASH_TYPE_TOOLTIPS = {
        "Rear-end collision": "Another vehicle struck the back of the Waymo, or vice versa. The most common crash type for all drivers.",
        "Side-impact collision": "Contact along the side of one or both vehicles, typically during lane changes or merging.",
        "Backing collision": "One vehicle was reversing when contact occurred — usually another vehicle backing into the Waymo in a parking lot or driveway.",
        "Single vehicle": "The Waymo was the only vehicle involved. Includes hitting fixed objects (poles, curbs, debris), or being struck by objects like shopping carts.",
        "Head-on collision": "Front-to-front contact between the Waymo and another vehicle, often at low speed in tight spaces or when a vehicle crosses the center line.",
        "Intersection collision": "Contact occurring within an intersection, often involving turning movements or signal conflicts.",
        "Other": "Crashes that don't fit standard categories, including unusual circumstances described in the NHTSA narrative.",
        "Secondary crash": "The Waymo was not involved in the initial crash but was struck by a vehicle or debris from a nearby collision.",
        "Motorcycle": "A crash involving a motorcycle and the Waymo vehicle.",
        "Cyclist": "A crash involving a cyclist and the Waymo vehicle.",
        "Pedestrian": "A crash involving a pedestrian and the Waymo vehicle.",
    };

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
                            label: function(item) {
                                return item.raw + " crashes (" + pcts[item.dataIndex] + "%)";
                            },
                            // Show crash type description below the count
                            afterLabel: function(item) {
                                const typeName = labels[item.dataIndex];
                                return CRASH_TYPE_TOOLTIPS[typeName] || "";
                            },
                        },
                        // Wider tooltip to fit the description text
                        maxWidth: 320,
                    },
                },
            },
        });
    }

    // ============================================
    // Chart 6: Mileage Growth (line chart)
    // ============================================

    /**
     * A Chart.js plugin that draws a dashed vertical line with a label —
     * used to mark NHTSA's June 16, 2025 reporting-rule change. Configure
     * with options.plugins.ruleLine = { x: <data index, may be fractional>, label }.
     */
    const ruleLinePlugin = {
        id: "ruleLine",
        afterDatasetsDraw(chart, args, opts) {
            if (!opts || opts.x === undefined || opts.x === null) return;
            const xScale = chart.scales.x;
            const { top, bottom } = chart.chartArea;
            const x = xScale.getPixelForValue(opts.x);
            const ctx = chart.ctx;
            ctx.save();
            ctx.strokeStyle = TEXT_DARK;
            ctx.setLineDash([4, 4]);
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x, top);
            ctx.lineTo(x, bottom);
            ctx.stroke();
            if (opts.label) {
                ctx.setLineDash([]);
                ctx.fillStyle = TEXT_DARK;
                ctx.font = `11px ${MONO_FONT}`;
                ctx.textAlign = opts.align || "left";
                ctx.fillText(opts.label, x + (opts.align === "right" ? -6 : 6), top + 12);
            }
            ctx.restore();
        },
    };

    /**
     * Build the cumulative rider-only miles chart from stats.mileage_series
     * (hand-sourced milestones merged with every quarterly hub release by
     * the pipeline). Plotted on a true time axis (decimal years) so uneven
     * gaps between data points are drawn to scale.
     *
     * @param {Object} stats — site-data.json
     */
    function buildMileageChart(stats) {
        const canvas = document.getElementById("mileage-chart");
        if (!canvas || !stats.mileage_series || !stats.mileage_series.length) return;

        const points = stats.mileage_series.map((p) => {
            const d = new Date(p.date + "T00:00:00");
            const start = new Date(d.getFullYear(), 0, 1);
            const year = d.getFullYear() + (d - start) / (365.25 * 24 * 3600 * 1000);
            return { x: year, y: p.miles_millions, meta: p };
        });

        new Chart(canvas, {
            type: "line",
            data: {
                datasets: [{
                    data: points,
                    borderColor: ACCENT,
                    backgroundColor: "rgba(139, 111, 71, 0.08)",
                    fill: true,
                    tension: 0,
                    borderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: points.map((p) => p.meta.kind === "hub" ? ACCENT : "#faf8f5"),
                    pointBorderColor: ACCENT,
                    pointBorderWidth: 1.5,
                }],
            },
            options: {
                ...getDefaults(),
                scales: {
                    x: {
                        type: "linear",
                        grid: { display: false },
                        border: { color: BORDER_COLOR },
                        ticks: {
                            stepSize: 1,
                            callback: (v) => Number.isInteger(v) ? String(v) : "",
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                        },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: BORDER_COLOR, drawTicks: false },
                        border: { display: false },
                        ticks: {
                            callback: (v) => v + "M",
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,
                        },
                    },
                },
                plugins: {
                    ...getDefaults().plugins,
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            title: (items) => {
                                const d = new Date(items[0].raw.meta.date + "T00:00:00");
                                return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
                            },
                            label: (item) => `${item.raw.y.toLocaleString("en-US")} million miles`,
                            afterLabel: (item) => wrapText(item.raw.meta.source, 48),
                        },
                    },
                },
            },
        });
    }

    /** Break a long string into lines of at most `width` characters. */
    function wrapText(text, width) {
        const words = String(text || "").split(" ");
        const lines = [];
        let line = "";
        words.forEach((w) => {
            if ((line + " " + w).trim().length > width) {
                lines.push(line.trim());
                line = w;
            } else {
                line += " " + w;
            }
        });
        if (line.trim()) lines.push(line.trim());
        return lines;
    }

    /**
     * Two small multiples from stats.quarterly_rates: all reported crashes
     * per million miles, and injury crashes per million miles, by quarter.
     * Side by side they show that the mid-2025 drop in the first is a
     * reporting-rule change (the second barely moves).
     *
     * @param {Object} stats — site-data.json
     */
    function buildRateCharts(stats) {
        const qr = stats.quarterly_rates;
        if (!qr || !qr.series || !qr.series["All metros"]) return;
        const rows = qr.series["All metros"];
        const labels = rows.map((r) => {
            const year = Math.floor(r.quarter / 100);
            return `Q${(r.quarter % 100) / 3} ${year}`;
        });
        // The rule took effect in the quarter ending amendment_3_quarter;
        // draw the line just before the first full quarter under it.
        const firstAfter = rows.findIndex((r) => r.quarter > qr.amendment_3_quarter);
        const ruleX = firstAfter > 0 ? firstAfter - 0.5 : null;

        const make = (canvasId, key, decimals, suggestedMax) => {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            new Chart(canvas, {
                type: "line",
                data: {
                    labels,
                    datasets: [{
                        data: rows.map((r) => r[key]),
                        borderColor: ACCENT,
                        backgroundColor: ACCENT,
                        borderWidth: 2,
                        pointRadius: 4,
                        tension: 0,
                    }],
                },
                options: {
                    ...getDefaults(),
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: BORDER_COLOR },
                            ticks: { font: { family: MONO_FONT, size: 10 }, color: TEXT_COLOR, maxRotation: 0, autoSkip: true },
                        },
                        y: {
                            beginAtZero: true,
                            suggestedMax,
                            grid: { color: BORDER_COLOR, drawTicks: false },
                            border: { display: false },
                            ticks: { font: { family: MONO_FONT, size: 11 }, color: TEXT_COLOR, padding: 8 },
                        },
                    },
                    plugins: {
                        ...getDefaults().plugins,
                        ruleLine: { x: ruleX, label: "New rules", align: "left" },
                        tooltip: {
                            ...getDefaults().plugins.tooltip,
                            callbacks: {
                                label: (item) => {
                                    const r = rows[item.dataIndex];
                                    const count = key === "crashes_per_million" ? r.crashes : r.injury;
                                    return [`${item.raw.toFixed(decimals)} per million miles`,
                                        `${count} crashes over ${r.miles_millions.toFixed(1)}M miles`];
                                },
                            },
                        },
                    },
                },
                plugins: [ruleLinePlugin],
            });
        };
        make("rate-all-chart", "crashes_per_million", 1, 12);
        make("rate-injury-chart", "injury_per_million", 2, 1.5);
    }

    /**
     * Build a bar chart of crashes per month across the whole dataset.
     * The most recent months come from federal reports that Waymo's
     * quarterly release hasn't enriched yet — they're drawn in a lighter
     * shade to signal that those counts can still be amended.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function buildTrendChart(stats) {
        const canvas = document.getElementById("trend-chart");
        if (!canvas || !stats.monthly_trend) return;

        const entries = Object.entries(stats.monthly_trend)
            .sort((a, b) => a[0].localeCompare(b[0]));

        const hubThrough = stats.meta && stats.meta.hub_data_through
            ? String(stats.meta.hub_data_through) : null;

        const MONTHS_SHORT = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const MONTHS_LONG = ["", "January", "February", "March", "April", "May",
            "June", "July", "August", "September", "October", "November", "December"];

        const labels = entries.map(([ym]) => {
            const year = ym.substring(0, 4);
            const month = parseInt(ym.substring(4), 10);
            // Show the year at each January for orientation
            return month === 1 ? MONTHS_SHORT[month] + " " + year : MONTHS_SHORT[month];
        });
        const values = entries.map(([, count]) => count);
        const completeThrough = stats.meta && stats.meta.federal_complete_through
            ? String(stats.meta.federal_complete_through) : null;
        // Three states: detailed by Waymo's hub / federal-only / still filling in
        const stateOf = (ym) => completeThrough && ym > completeThrough ? "provisional"
            : hubThrough && ym > hubThrough ? "federal" : "hub";
        const COLORS = { hub: ACCENT, federal: "#c9b89d", provisional: "#e8e0d4" };
        const colors = entries.map(([ym]) => COLORS[stateOf(ym)]);
        const ruleMonth = stats.meta && stats.meta.sgo_amendment_3_date
            ? stats.meta.sgo_amendment_3_date.slice(0, 7).replace("-", "") : null;
        const ruleIndex = ruleMonth ? entries.findIndex(([ym]) => ym > ruleMonth) : -1;

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 0,
                    barPercentage: 0.9,
                    categoryPercentage: 0.95,
                }],
            },
            options: {
                ...getDefaults(),
                plugins: {
                    ...getDefaults().plugins,
                    ruleLine: ruleIndex > 0
                        ? { x: ruleIndex - 0.5, label: "June 2025: reporting rules change", align: "right" }
                        : {},
                    tooltip: {
                        ...getDefaults().plugins.tooltip,
                        callbacks: {
                            title: function (items) {
                                const ym = entries[items[0].dataIndex][0];
                                return MONTHS_LONG[parseInt(ym.substring(4), 10)] + " " + ym.substring(0, 4);
                            },
                            label: function (item) {
                                const ym = entries[item.dataIndex][0];
                                const note = {
                                    hub: "",
                                    federal: " (federal reports; Waymo detail pending)",
                                    provisional: " (incomplete — reports still arriving)",
                                }[stateOf(ym)];
                                return item.parsed.y + " crashes" + note;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        border: { color: BORDER_COLOR },
                        ticks: {
                            font: { family: MONO_FONT, size: 10 },
                            color: TEXT_COLOR,
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 14,
                        },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: BORDER_COLOR, drawTicks: false },
                        border: { display: false },
                        ticks: {
                            font: { family: MONO_FONT, size: 11 },
                            color: TEXT_COLOR,
                            padding: 8,
                        },
                    },
                },
            },
            plugins: [ruleLinePlugin],
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

    // Public API — these functions are the only things accessible from outside the module
    return {
        buildHourlyChart,
        buildDayOfWeekChart,
        buildLocationTypeChart,
        buildSpeedChart,
        buildCrashTypeChart,
        buildMileageChart,
        buildRateCharts,
        buildTrendChart,
    };

// The closing })() immediately runs the function and stores the returned object in Charts
})();
