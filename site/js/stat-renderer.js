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
const StatRenderer = (function () {

    /**
     * Format a value based on its data-format attribute.
     */
    function formatValue(value, format) {
        if (value === undefined || value === null) return "--";

        switch (format) {
            case "date":
                // Convert ISO timestamp like "2026-02-21T13:04:29" to "Feb 21, 2026"
                try {
                    const date = new Date(value);
                    return date.toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                    });
                } catch {
                    return value;
                }

            case "percent":
                return Number(value).toFixed(1);

            case "millions":
                // Convert 127000000 to "127M+"
                if (typeof value === "number") {
                    return Math.round(value / 1_000_000) + "M+";
                }
                return value;

            default:
                // For numbers, add commas (1123 → "1,123")
                if (typeof value === "number" && Number.isFinite(value)) {
                    // Only add commas to integers; keep decimals as-is
                    if (Number.isInteger(value)) {
                        return value.toLocaleString("en-US");
                    }
                    return value.toString();
                }
                return String(value);
        }
    }

    /**
     * Animate a number counting up from 0 to its target value.
     * Only works with numeric values.
     */
    function animateNumber(element, targetValue, suffix) {
        const duration = 1500; // milliseconds
        const startTime = performance.now();
        const isFloat = !Number.isInteger(targetValue);

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease-out cubic for a nice deceleration effect
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = targetValue * eased;

            if (isFloat) {
                element.textContent = current.toFixed(1) + (suffix || "");
            } else {
                element.textContent = Math.round(current).toLocaleString("en-US") + (suffix || "");
            }

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    /**
     * Render all data-stat placeholders on the page.
     * Call this after loading site-data.json.
     *
     * @param {Object} stats — The parsed site-data.json object
     */
    function renderAll(stats) {
        const elements = document.querySelectorAll("[data-stat]");
        console.log(`[StatRenderer] Rendering ${elements.length} stat placeholders`);

        let filled = 0;
        let missing = 0;

        elements.forEach((el) => {
            const path = el.getAttribute("data-stat");
            const format = el.getAttribute("data-format");
            const suffix = el.getAttribute("data-suffix") || "";
            const shouldAnimate = el.getAttribute("data-animate") === "true";

            // Look up the value using the dot-path resolver
            const rawValue = DataLoader.resolve(stats, path);

            if (rawValue === undefined) {
                console.warn(`[StatRenderer] No value found for path: "${path}"`);
                el.textContent = "N/A";
                missing++;
                return;
            }

            // If animation is requested and the value is a number, animate it
            if (shouldAnimate && typeof rawValue === "number") {
                // Set up IntersectionObserver so animation triggers when visible
                const observer = new IntersectionObserver(
                    (entries) => {
                        entries.forEach((entry) => {
                            if (entry.isIntersecting) {
                                animateNumber(el, rawValue, suffix);
                                observer.unobserve(el);
                            }
                        });
                    },
                    { threshold: 0.5 }
                );
                observer.observe(el);
                // Show a placeholder until it scrolls into view
                el.textContent = "0" + suffix;
            } else {
                // Static render (no animation)
                el.textContent = formatValue(rawValue, format) + suffix;
            }

            filled++;
        });

        console.log(`[StatRenderer] Filled: ${filled}, Missing: ${missing}`);
    }

    // Public API
    return { renderAll, formatValue };
})();
