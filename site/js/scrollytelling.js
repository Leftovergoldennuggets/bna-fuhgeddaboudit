/**
 * scrollytelling.js — Scroll-driven narrative transitions
 * =========================================================
 * Uses IntersectionObserver to detect which scrolly step is visible
 * and triggers the corresponding map transition.
 *
 * How it works:
 *   1. Each `.scrolly-step` element has a `data-step` attribute (e.g., "intro", "sf-heatmap")
 *   2. When a step enters the middle 20% of the viewport, it becomes "active"
 *   3. The active step's `data-step` value is passed to MapController.goToStep()
 *   4. The map smoothly flies to the new location
 *
 * This module also handles:
 *   - The reading progress bar at the top of the page
 *   - The navbar scroll effect (adds shadow when scrolled)
 *   - Smooth scrolling for anchor links
 *   - Mobile hamburger menu toggle
 *
 * Dependencies:
 *   - map-controller.js (for goToStep transitions)
 */

// ============================================
// Scrollytelling Module
// ============================================
const Scrollytelling = (function () {

    /**
     * Initialize all scroll-related behaviors.
     * Call this after the map is ready.
     */
    function init() {
        initStepObserver();
        initProgressBar();
        initNavigation();
        console.log("[Scrollytelling] Initialized");
    }

    // ============================================
    // Step Observer — triggers map transitions
    // ============================================

    function initStepObserver() {
        const steps = document.querySelectorAll(".scrolly-step");
        if (steps.length === 0) return;

        // Observe when a step enters the middle 20% of the viewport
        // rootMargin: -40% top and -40% bottom means only the middle 20% triggers
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const stepId = entry.target.dataset.step;

                        // Mark this step as visually active (triggers CSS animation)
                        steps.forEach((s) => s.classList.remove("is-active"));
                        entry.target.classList.add("is-active");

                        // Tell the map to transition to this step's view
                        MapController.goToStep(stepId);
                    }
                });
            },
            {
                root: null,
                rootMargin: "-40% 0px -40% 0px",
                threshold: 0,
            }
        );

        steps.forEach((step) => observer.observe(step));
    }

    // ============================================
    // Progress Bar — shows reading progress
    // ============================================

    function initProgressBar() {
        const fill = document.getElementById("progress-fill");
        if (!fill) return;

        window.addEventListener("scroll", () => {
            // Calculate how far down the page the user has scrolled
            const scrollTop = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
            fill.style.width = progress + "%";
        });
    }

    // ============================================
    // Navigation — sticky header, mobile menu, smooth scroll
    // ============================================

    function initNavigation() {
        const navbar = document.querySelector(".navbar");
        const navToggle = document.querySelector(".nav-toggle");
        const navLinks = document.querySelector(".nav-links");

        // --- Navbar shadow on scroll ---
        if (navbar) {
            window.addEventListener("scroll", () => {
                if (window.scrollY > 50) {
                    navbar.classList.add("scrolled");
                } else {
                    navbar.classList.remove("scrolled");
                }
            });
        }

        // --- Mobile hamburger toggle ---
        if (navToggle && navLinks) {
            navToggle.addEventListener("click", () => {
                navToggle.classList.toggle("active");
                navLinks.classList.toggle("active");
            });

            // Close mobile menu when a link is clicked
            navLinks.querySelectorAll("a").forEach((link) => {
                link.addEventListener("click", () => {
                    navToggle.classList.remove("active");
                    navLinks.classList.remove("active");
                });
            });
        }

        // --- Smooth scroll for anchor links (e.g., #intro, #stats) ---
        document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
            anchor.addEventListener("click", function (e) {
                e.preventDefault();
                const targetId = this.getAttribute("href");
                const target = document.querySelector(targetId);
                if (target) {
                    const navHeight = navbar ? navbar.offsetHeight : 0;
                    const targetY = target.getBoundingClientRect().top + window.scrollY - navHeight - 20;
                    window.scrollTo({ top: targetY, behavior: "smooth" });
                }
            });
        });
    }

    // Public API
    return { init };
})();
