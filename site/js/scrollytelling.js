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

// This is the "IIFE module pattern" — a way to create a "module" that keeps its variables private.
// Everything inside the (function() { ... })() is hidden from the rest of the code,
// and only what we return at the bottom (the "Public API") is accessible from outside.
const Scrollytelling = (function () {

    /**
     * Initialize all scroll-related behaviors.
     * Call this after the map is ready.
     */
    function init() {
        // Set up the scroll-triggered step observer
        initStepObserver();
        // Set up the reading progress bar
        initProgressBar();
        // Set up navbar, hamburger menu, and smooth scroll links
        initNavigation();
        // Log to the browser console so we know it worked
        console.log("[Scrollytelling] Initialized");
    }

    // ============================================
    // Step Observer — triggers map transitions
    // ============================================

    function initStepObserver() {
        // Find all HTML elements with the class "scrolly-step"
        const steps = document.querySelectorAll(".scrolly-step");
        // If there are no scrolly steps on this page, exit early
        if (steps.length === 0) return;

        // Create an IntersectionObserver — it watches elements and tells us when they enter/leave the viewport
        // rootMargin: -40% top and -40% bottom means only the middle 20% triggers
        const observer = new IntersectionObserver(
            // Arrow function: shorthand for function(entries) { ... }
            (entries) => {
                // Loop through each observed element that changed visibility
                entries.forEach((entry) => {
                    // entry.isIntersecting is true when the element is in the middle 20% zone
                    if (entry.isIntersecting) {
                        // Read the "data-step" attribute from the HTML element (e.g., "sf-heatmap")
                        const stepId = entry.target.dataset.step;

                        // Remove the "is-active" CSS class from ALL steps (deactivate them all)
                        steps.forEach((s) => s.classList.remove("is-active"));
                        // Add the "is-active" CSS class to THIS step (triggers CSS animation)
                        entry.target.classList.add("is-active");

                        // Tell the map to transition to this step's view
                        MapController.goToStep(stepId);
                    }
                });
            },
            {
                root: null,             // null means observe relative to the browser viewport
                rootMargin: "-40% 0px -40% 0px",  // Shrink the detection zone to the middle 20%
                threshold: 0,           // Trigger as soon as any part of the element enters the zone
            }
        );

        // Start observing each scrolly step element
        steps.forEach((step) => observer.observe(step));
    }

    // ============================================
    // Progress Bar — shows reading progress
    // ============================================

    function initProgressBar() {
        // Find the progress bar fill element by its ID
        const fill = document.getElementById("progress-fill");
        // If there's no progress bar on this page, exit early
        if (!fill) return;

        // Listen for "scroll" events — fires every time the user scrolls
        window.addEventListener("scroll", () => {
            // window.scrollY = how far down the page the user has scrolled (in pixels)
            const scrollTop = window.scrollY;
            // Total scrollable height = full page height minus what's visible
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            // Calculate progress as a percentage (0–100)
            const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
            // Set the CSS width of the progress bar fill
            fill.style.width = progress + "%";
        });
    }

    // ============================================
    // Navigation — sticky header, mobile menu, smooth scroll
    // ============================================

    function initNavigation() {
        // Find the navbar, hamburger toggle button, and nav links container
        const navbar = document.querySelector(".navbar");
        const navToggle = document.querySelector(".nav-toggle");
        const navLinks = document.querySelector(".nav-links");

        // --- Navbar shadow on scroll ---
        if (navbar) {
            // Listen for scroll events on the window
            window.addEventListener("scroll", () => {
                // window.scrollY = how far the user has scrolled down
                if (window.scrollY > 50) {
                    // Add the "scrolled" CSS class (adds a shadow effect)
                    navbar.classList.add("scrolled");
                } else {
                    // Remove the "scrolled" CSS class when near the top
                    navbar.classList.remove("scrolled");
                }
            });
        }

        // --- Mobile hamburger toggle ---
        if (navToggle && navLinks) {
            // When the hamburger button is clicked...
            navToggle.addEventListener("click", () => {
                // .classList.toggle() adds the class if missing, removes it if present
                navToggle.classList.toggle("active");
                navLinks.classList.toggle("active");
            });

            // Close mobile menu when a link is clicked
            navLinks.querySelectorAll("a").forEach((link) => {
                link.addEventListener("click", () => {
                    // Remove "active" from both toggle and links to close the menu
                    navToggle.classList.remove("active");
                    navLinks.classList.remove("active");
                });
            });
        }

        // --- Smooth scroll for anchor links (e.g., #intro, #stats) ---
        // Find all <a> tags whose href starts with "#"
        document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
            // Note: using function(e) instead of arrow function so "this" refers to the clicked link
            anchor.addEventListener("click", function (e) {
                // e.preventDefault() stops the browser from jumping to the anchor instantly
                e.preventDefault();
                // Get the href value (e.g., "#stats") from the clicked link
                const targetId = this.getAttribute("href");
                // Find the element with that ID on the page
                const target = document.querySelector(targetId);
                if (target) {
                    // Get the navbar height so we can offset the scroll position
                    const navHeight = navbar ? navbar.offsetHeight : 0;
                    // getBoundingClientRect().top = distance from the element to the top of the viewport
                    // Add window.scrollY to convert to absolute page position, then subtract navbar height + padding
                    const targetY = target.getBoundingClientRect().top + window.scrollY - navHeight - 20;
                    // Smoothly scroll the page to that position
                    window.scrollTo({ top: targetY, behavior: "smooth" });
                }
            });
        });
    }

    // Public API — only init() is exposed; everything else stays private inside the module
    return { init };

// The closing })() immediately runs the function and stores the returned object in Scrollytelling
})();
