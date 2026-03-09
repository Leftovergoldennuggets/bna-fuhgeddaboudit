/**
 * stat-renderer.js — Inject statistics from JSON into HTML placeholders
 * ======================================================================
 * Finds all HTML elements with a `data-stat` attribute and replaces
 * their text content with the corresponding value from site-data.json.
 *
 * HTML usage examples:
 *   <span data-stat="overview.total_crashes">--</span>
 *   <span data-stat="temporal.rush_hour_percentage" data-suffix="%">--</span>
 *   <span data-stat="meta.generated_at" data-format="date">--</span>
 *   <div data-stat="overview.total_crashes" data-animate="true">--</div>
 *
 * Supported attributes:
 *   data-stat      — Dot-separated path into site-data.json
 *   data-format    — "date" (format ISO date), "percent", "millions" (127M+)
 *   data-suffix    — Text appended after the number (e.g., "%")
 *   data-animate   — "true" to animate counting up from 0
 */

// ============================================
// StatRenderer Module
// ============================================

// IIFE module pattern: wraps code in (function(){ ... })() so variables stay private
// Only the object returned at the bottom (renderAll, formatValue) is accessible outside
const StatRenderer = (function () {

    /**
     * Format a value based on its data-format attribute.
     */
    function formatValue(value, format) {
        // If no value exists, show a placeholder dash
        if (value === undefined || value === null) return "--";

        // "switch" checks the format string and runs the matching case
        switch (format) {
            case "date":
                // Convert ISO timestamp like "2026-02-21T13:04:29" to "Feb 21, 2026"
                try {
                    // Create a JavaScript Date object from the ISO string
                    const date = new Date(value);
                    // Format it as a human-readable US date string
                    return date.toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                    });
                } catch {
                    // If date parsing fails, just show the raw value
                    return value;
                }

            case "percent":
                // .toFixed(1) rounds to 1 decimal place: 46.929 → "46.9"
                return Number(value).toFixed(1);

            case "millions":
                // Convert 127000000 to "127M+"
                if (typeof value === "number") {
                    // Divide by 1 million, round to nearest whole number, add "M+"
                    return Math.round(value / 1_000_000) + "M+";
                }
                return value;

            case "yearmonth":
                // Convert 202009 to "Sept 2020"
                if (typeof value === "number") {
                    // Extract the year: 202009 / 100 = 2020.09 → floor → 2020
                    const year = Math.floor(value / 100);
                    // Extract the month: 202009 % 100 = 9 (September)
                    const month = value % 100;
                    // Array of month abbreviations (index 0 = Jan, index 11 = Dec)
                    const monthNames = [
                        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"
                    ];
                    // month - 1 because arrays start at 0 but months start at 1
                    return monthNames[month - 1] + " " + year;
                }
                return String(value);

            default:
                // For numbers, add commas (1123 → "1,123")
                if (typeof value === "number" && Number.isFinite(value)) {
                    if (Number.isInteger(value)) {
                        // .toLocaleString("en-US") formats with commas: 1123 → "1,123"
                        return value.toLocaleString("en-US");
                    }
                    // Decimals: just convert to string without commas
                    return value.toString();
                }
                // Non-numbers: convert to string as-is
                return String(value);
        }
    }

    /**
     * Animate a number counting up from 0 to its target value.
     * Only works with numeric values.
     */
    function animateNumber(element, targetValue, suffix) {
        // Animation lasts 1.5 seconds (1500 milliseconds)
        const duration = 1500;
        // performance.now() returns the current time in milliseconds (very precise)
        const startTime = performance.now();
        // Check if the number has decimals (to know how to display it)
        const isFloat = !Number.isInteger(targetValue);

        // For this part we consulted Claude who recommended requestAnimationFrame for smooth
        // number counting animations. This browser API synchronizes our animation with the
        // screen's refresh rate (typically 60 frames per second), so numbers update smoothly
        // without jitter. The easing formula `1 - Math.pow(1 - t, 3)` creates a "fast start,
        // slow finish" curve (called "ease-out cubic"): t goes from 0 to 1 over the animation
        // duration, and the formula makes the first 50% of time cover ~87% of the distance,
        // then the remaining 50% of time covers only ~13%. This makes the counting feel natural
        // — it races up quickly then gently settles on the final number.

        // This function runs on every screen refresh (~60 times per second)
        function update(currentTime) {
            // How many milliseconds have passed since the animation started
            const elapsed = currentTime - startTime;
            // Progress goes from 0.0 (just started) to 1.0 (finished)
            const progress = Math.min(elapsed / duration, 1);

            // Ease-out cubic: starts fast, slows down at the end (looks natural)
            const eased = 1 - Math.pow(1 - progress, 3);
            // Calculate the current number to display based on progress
            const current = targetValue * eased;

            if (isFloat) {
                // For decimals, show 1 decimal place: 46.9%
                element.textContent = current.toFixed(1) + (suffix || "");
            } else {
                // For whole numbers, round and add commas: 1,123
                element.textContent = Math.round(current).toLocaleString("en-US") + (suffix || "");
            }

            // If the animation isn't done yet, schedule another frame
            if (progress < 1) {
                // requestAnimationFrame() runs this function again on the next screen refresh
                requestAnimationFrame(update);
            }
        }

        // Kick off the animation by scheduling the first frame
        requestAnimationFrame(update);
    }

    /**
     * Render all data-stat placeholders on the page.
     * Call this after loading site-data.json.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function renderAll(stats) {
        // querySelectorAll finds every element with a data-stat attribute
        const elements = document.querySelectorAll("[data-stat]");
        console.log(`[StatRenderer] Rendering ${elements.length} stat placeholders`);

        // Counters to track how many placeholders we successfully filled
        let filled = 0;
        let missing = 0;

        // .forEach() loops through every matching element on the page
        elements.forEach((el) => {
            // Read the data-stat attribute to know which value to look up
            const path = el.getAttribute("data-stat");
            // Read optional formatting and display attributes
            const format = el.getAttribute("data-format");
            const suffix = el.getAttribute("data-suffix") || "";
            // Check if this element should animate (count up from 0)
            const shouldAnimate = el.getAttribute("data-animate") === "true";

            // Look up the value using the dot-path resolver (e.g., "overview.total_crashes" → 1123)
            const rawValue = DataLoader.resolve(stats, path);

            if (rawValue === undefined) {
                // Value not found in the data — show "N/A" and log a warning
                console.warn(`[StatRenderer] No value found for path: "${path}"`);
                el.textContent = "N/A";
                missing++;
                // "return" inside forEach acts like "continue" — skip to the next element
                return;
            }

            // If animation is requested and the value is a number, animate it
            if (shouldAnimate && typeof rawValue === "number") {
                // For this part we consulted Claude who recommended IntersectionObserver — a browser
                // API that efficiently watches elements and fires a callback when they scroll into
                // the user's viewport (the visible area of the page). This is much better than
                // listening to every single scroll event (which fires dozens of times per second and
                // slows down the page). The observer only fires once when an element crosses the
                // visibility threshold, making it ideal for triggering animations when a stat
                // scrolls into view. The `threshold: 0.1` means "trigger when 10% of the element
                // is visible." Once triggered, `observer.unobserve(el)` stops watching that element
                // so the animation only plays once.
                const observer = new IntersectionObserver(
                    // This arrow function runs whenever the element's visibility changes
                    (entries) => {
                        // .forEach() loops through each observed element
                        entries.forEach((entry) => {
                            // entry.isIntersecting is true when the element is visible on screen
                            if (entry.isIntersecting) {
                                // Start the counting animation
                                animateNumber(el, rawValue, suffix);
                                // Stop watching — we only want to animate once
                                observer.unobserve(el);
                            }
                        });
                    },
                    // threshold: 0.5 means trigger when 50% of the element is visible
                    { threshold: 0.5 }
                );
                // Start watching this element for visibility changes
                observer.observe(el);
                // Show "0" as a placeholder until the element scrolls into view
                el.textContent = "0" + suffix;
            } else {
                // Static render (no animation) — just set the text immediately
                el.textContent = formatValue(rawValue, format) + suffix;
            }

            filled++;
        });

        // Log summary so we can check everything worked
        console.log(`[StatRenderer] Filled: ${filled}, Missing: ${missing}`);
    }

    // Public API — only these two functions are accessible outside the module
    return { renderAll, formatValue };
})();
