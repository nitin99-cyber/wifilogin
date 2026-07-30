/**
 * MMMUT WiFi Auto Login — Landing Page Script
 *
 * Features:
 *   - Google Analytics 4 integration (placeholder)
 *   - Download & GitHub click tracking
 *   - Smooth-scroll active link highlighting
 *   - FAQ accordion
 *   - Mobile navigation toggle
 *   - Sticky header shadow on scroll
 */

/* ============================================================
   Google Analytics 4 — Replace with your Measurement ID
   ============================================================ */
const GA_MEASUREMENT_ID = "G-XXXXXXXXXX"; // <-- Replace this

// Dynamically inject GA4 script tag
(function loadGA() {
  if (GA_MEASUREMENT_ID === "G-XXXXXXXXXX") return; // skip if placeholder
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag("js", new Date());
  gtag("config", GA_MEASUREMENT_ID);
})();

/* ============================================================
   Utility: fire a GA4 event (safe even if GA is not loaded)
   ============================================================ */
function trackEvent(eventName, params) {
  if (typeof window.gtag === "function") {
    window.gtag("event", eventName, params);
  }
}

/* ============================================================
   DOM Ready
   ============================================================ */
document.addEventListener("DOMContentLoaded", () => {

  /* ---------- Header scroll shadow ---------- */
  const header = document.querySelector(".header");
  function onScroll() {
    header.classList.toggle("header--scrolled", window.scrollY > 10);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- Mobile nav toggle ---------- */
  const toggle = document.querySelector(".nav__toggle");
  const navLinks = document.querySelector(".nav__links");

  if (toggle) {
    toggle.addEventListener("click", () => {
      const isOpen = navLinks.classList.toggle("nav__links--open");
      toggle.setAttribute("aria-expanded", isOpen);
    });

    // Close nav when a link is clicked
    navLinks.querySelectorAll(".nav__link").forEach((link) => {
      link.addEventListener("click", () => {
        navLinks.classList.remove("nav__links--open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- FAQ Accordion ---------- */
  document.querySelectorAll(".faq__question").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".faq__item");
      const answer = item.querySelector(".faq__answer");
      const isOpen = item.classList.contains("faq__item--open");

      // Close all
      document.querySelectorAll(".faq__item--open").forEach((openItem) => {
        openItem.classList.remove("faq__item--open");
        openItem.querySelector(".faq__answer").style.maxHeight = null;
        openItem.querySelector(".faq__question").setAttribute("aria-expanded", "false");
      });

      // Toggle current
      if (!isOpen) {
        item.classList.add("faq__item--open");
        answer.style.maxHeight = answer.scrollHeight + "px";
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });

  /* ---------- Download click tracking ---------- */
  document.querySelectorAll("[data-track='download']").forEach((el) => {
    el.addEventListener("click", () => {
      trackEvent("download_click", {
        event_category: "engagement",
        event_label: "Download Button",
      });
    });
  });

  /* ---------- GitHub click tracking ---------- */
  document.querySelectorAll("[data-track='github']").forEach((el) => {
    el.addEventListener("click", () => {
      trackEvent("github_click", {
        event_category: "engagement",
        event_label: "View Source Code",
      });
    });
  });

  /* ---------- Active nav link on scroll ---------- */
  const sections = document.querySelectorAll("section[id]");
  const navItems = document.querySelectorAll(".nav__link");

  function highlightNav() {
    const scrollY = window.scrollY + 100;
    sections.forEach((section) => {
      const top = section.offsetTop;
      const height = section.offsetHeight;
      const id = section.getAttribute("id");
      if (scrollY >= top && scrollY < top + height) {
        navItems.forEach((link) => {
          link.classList.remove("nav__link--active");
          if (link.getAttribute("href") === `#${id}`) {
            link.classList.add("nav__link--active");
          }
        });
      }
    });
  }
  window.addEventListener("scroll", highlightNav, { passive: true });
});
