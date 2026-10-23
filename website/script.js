// ==========================================================================
// MMMUT WiFi Auto Login — Core Application Logic & Firebase Integration
// Preserves: Google Analytics, Firestore Analytics, 1-Click Likes, Reviews
// ==========================================================================

import { initializeApp } from "https://www.gstatic.com/firebasejs/12.17.1/firebase-app.js";
import {
  getFirestore,
  collection,
  addDoc,
  doc,
  setDoc,
  increment,
  serverTimestamp,
  getDoc
} from "https://www.gstatic.com/firebasejs/12.17.1/firebase-firestore.js";

// ==========================================
// FIREBASE CONFIGURATION (Verified Live Project)
// Note: Firebase Web API keys are standard client-side project identifiers.
// Access controls and domain restrictions are enforced in Google Cloud Console.
// ==========================================
const firebaseConfig = {
  apiKey: "AIzaSyBwIQBibLm6F65wRaK8u5JhEnMv13YjQ_M",
  authDomain: "wifilogin-b9c52.firebaseapp.com",
  projectId: "wifilogin-b9c52",
  storageBucket: "wifilogin-b9c52.firebasestorage.app",
  messagingSenderId: "870436247754",
  appId: "1:870436247754:web:0522a0f9aa19da9192bc33",
  measurementId: "G-6QYK9390CX"
};

// Initialize Firebase
let app, db;
try {
  app = initializeApp(firebaseConfig);
  db = getFirestore(app);
} catch (error) {
  console.warn("Firebase initialization notice:", error);
}

// ==========================================
// SECURITY & VALIDATION UTILITIES
// ==========================================

/**
 * Escapes HTML characters to prevent XSS.
 */
function sanitize(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/[&<>"'/]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;',
    '"': '&quot;', "'": '&#39;', '/': '&#x2F;'
  }[char]));
}

/**
 * Validates integer rating range (1 to 5).
 */
function safeRating(val) {
  const n = parseInt(val, 10);
  return Number.isInteger(n) && n >= 1 && n <= 5 ? n : null;
}

/**
 * Rate Limiting for Reviews (10 minutes cooldown).
 */
const RATE_LIMIT_KEY = 'review_last_submitted';
const RATE_LIMIT_MS = 10 * 60 * 1000;

function isRateLimited() {
  const last = localStorage.getItem(RATE_LIMIT_KEY);
  if (!last) return false;
  return (Date.now() - parseInt(last, 10)) < RATE_LIMIT_MS;
}

function setRateLimit() {
  localStorage.setItem(RATE_LIMIT_KEY, Date.now().toString());
}

function getRemainingCooldown() {
  const last = parseInt(localStorage.getItem(RATE_LIMIT_KEY) || '0', 10);
  return Math.ceil((RATE_LIMIT_MS - (Date.now() - last)) / 60000);
}

// ==========================================
// SILENT ANALYTICS TRACKING
// ==========================================
async function trackStat(statName) {
  if (!db) return;
  try {
    const statRef = doc(db, 'analytics', statName);
    await setDoc(statRef, { count: increment(1) }, { merge: true });
  } catch (e) {
    // Tracking failures must remain silent to never degrade user experience
  }
}

// ==========================================
// DOM INTERACTION HANDLERS
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
  // 1. Record Page Visit silently
  trackStat('visits');

  // 2. Track all Download CTA clicks
  const downloadBtns = document.querySelectorAll('#download-btn, #nav-download-btn, .track-download');
  downloadBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      trackStat('downloads');
      if (typeof window.gtag === 'function') {
        window.gtag('event', 'download_click', {
          event_category: 'software',
          event_label: 'Windows Setup Installer'
        });
      }
    });
  });

  // 3. Mobile Navigation Menu Toggle
  const navToggle = document.getElementById('mobile-nav-toggle');
  const mobileMenu = document.getElementById('mobile-nav-menu');
  if (navToggle && mobileMenu) {
    navToggle.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', isOpen);
    });
  }

  // 4. Modal Overlay Support (System Docs / Info)
  const modal = document.getElementById('content-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalBody = document.getElementById('modal-body');
  const modalFooter = document.getElementById('modal-footer');
  const modalClose = document.getElementById('modal-close');

  function openModal() {
    if (modal) modal.classList.add('active');
  }

  function closeModal() {
    if (modal) modal.classList.remove('active');
  }

  if (modalClose) modalClose.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  async function fetchAndShowContent(docId, title, extraFooterHtml = '') {
    if (!modal) return;
    openModal();
    if (modalTitle) modalTitle.textContent = title;
    if (modalBody) modalBody.innerHTML = '<p>Loading documentation...</p>';
    if (modalFooter) modalFooter.style.display = 'none';

    try {
      if (!db) {
        if (modalBody) modalBody.innerHTML = '<p>Documentation is available in the <a href="https://github.com/nitin99-cyber/wifilogin" target="_blank" style="color:var(--color-text-primary); text-decoration:underline;">GitHub repository README</a>.</p>';
        return;
      }
      const snap = await getDoc(doc(db, 'content', docId));
      if (snap.exists()) {
        const data = snap.data();
        if (modalBody) modalBody.innerHTML = data.html || data.text || '<p>No content available.</p>';
        if (modalFooter && (extraFooterHtml || data.footerHtml)) {
          modalFooter.innerHTML = extraFooterHtml || data.footerHtml;
          modalFooter.style.display = 'flex';
        }
      } else {
        if (modalBody) modalBody.innerHTML = '<p>Detailed architecture and guide are available in the <a href="https://github.com/nitin99-cyber/wifilogin" target="_blank" style="color:var(--color-text-primary); text-decoration:underline;">GitHub Repository</a>.</p>';
      }
    } catch (e) {
      if (modalBody) modalBody.innerHTML = '<p>Documentation is available in the <a href="https://github.com/nitin99-cyber/wifilogin" target="_blank" style="color:var(--color-text-primary); text-decoration:underline;">GitHub repository README</a>.</p>';
    }
  }

  const docsBtns = document.querySelectorAll('#docs-btn, #hero-docs-btn, .open-docs-btn');
  docsBtns.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      fetchAndShowContent('readme', 'System Documentation');
    });
  });

  // 5. 1-Click Heart Reaction (Rating)
  const heartBtn = document.getElementById('heart-btn');
  const heartStatus = document.getElementById('quick-rating-status');
  const HEART_KEY = 'project_liked';

  if (heartBtn && heartStatus) {
    if (localStorage.getItem(HEART_KEY)) {
      heartBtn.classList.add('liked');
      heartBtn.disabled = true;
      heartStatus.textContent = 'Thanks for your support!';
    } else {
      heartBtn.addEventListener('click', async () => {
        if (!db) return;
        heartBtn.disabled = true;
        heartStatus.textContent = 'Saving...';

        try {
          await addDoc(collection(db, 'ratings'), {
            rating: 1,
            timestamp: serverTimestamp()
          });
          localStorage.setItem(HEART_KEY, 'true');
          heartBtn.classList.add('liked');
          heartStatus.textContent = 'Thanks for your support!';
        } catch (err) {
          heartStatus.textContent = 'Could not record like.';
          heartBtn.disabled = false;
        }
      });
    }
  }

  // 6. Interactive Star Rating Display Logic
  const ratingRadios = document.querySelectorAll('input[name="rating"]');
  const ratingDisplay = document.getElementById('rating-display');
  const ratingLabels = {
    '1': '1 of 5 — Needs Improvement',
    '2': '2 of 5 — Fair',
    '3': '3 of 5 — Good',
    '4': '4 of 5 — Very Good',
    '5': '5 of 5 — Excellent'
  };

  if (ratingRadios.length > 0 && ratingDisplay) {
    ratingRadios.forEach((radio) => {
      radio.addEventListener('change', () => {
        const label = ratingLabels[radio.value] || `${radio.value} of 5`;
        ratingDisplay.textContent = label;
        ratingDisplay.style.color = '#D4AF37'; // Restrained warm gold
      });
    });
  }

  // 7. Feedback & Reviews Form Submission
  const feedbackForm = document.getElementById('feedback-form');
  const statusMsg = document.getElementById('review-status-msg');

  if (feedbackForm) {
    feedbackForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      // Clear any prior status classes
      if (statusMsg) {
        statusMsg.className = 'status-msg';
        statusMsg.textContent = '';
      }

      // Honeypot anti-spam check (bots fill hidden inputs)
      const honeypot = document.getElementById('hp-field');
      if (honeypot && honeypot.value !== '') {
        feedbackForm.reset();
        return;
      }

      // Rate limit check
      if (isRateLimited()) {
        const mins = getRemainingCooldown();
        if (statusMsg) {
          statusMsg.className = 'status-msg status-warning';
          statusMsg.textContent = `Please wait ${mins} minute(s) before submitting another review.`;
        }
        return;
      }

      // Validate Message text
      const reviewerTextEl = document.getElementById('reviewer-text');
      const rawText = reviewerTextEl ? reviewerTextEl.value.trim() : '';
      const text = sanitize(rawText);

      if (!text || text.length < 5 || text.length > 1000) {
        if (statusMsg) {
          statusMsg.className = 'status-msg status-error';
          statusMsg.textContent = 'Feedback message must be between 5 and 1000 characters.';
        }
        reviewerTextEl?.focus();
        return;
      }

      // Validate Star Rating
      const ratingInput = document.querySelector('input[name="rating"]:checked');
      const rating = safeRating(ratingInput?.value);
      if (!rating) {
        if (statusMsg) {
          statusMsg.className = 'status-msg status-error';
          statusMsg.textContent = 'Please select a star rating (1 to 5 stars).';
        }
        return;
      }

      // Optional Name
      const nameInput = document.getElementById('reviewer-name');
      const rawName = nameInput ? nameInput.value.trim() : '';
      const name = rawName ? sanitize(rawName) : 'Anonymous Student';

      // Optional Email
      const emailInput = document.getElementById('reviewer-email');
      const rawEmail = emailInput ? emailInput.value.trim() : '';
      const email = rawEmail ? sanitize(rawEmail) : '';

      // Feedback Category
      const categorySelect = document.getElementById('feedback-category');
      const category = categorySelect ? sanitize(categorySelect.value) : 'General Feedback';

      // Prepend category to message text for administrative clarity
      const formattedText = `[${category}] ${text}`;

      const submitBtn = document.getElementById('feedback-submit-btn') || feedbackForm.querySelector('button[type="submit"]');
      const originalBtnText = submitBtn ? submitBtn.textContent : 'Submit Feedback';

      // Set Loading State
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';
      }
      if (statusMsg) {
        statusMsg.className = 'status-msg status-loading';
        statusMsg.textContent = 'Submitting feedback to Firebase...';
      }

      try {
        if (!db) {
          throw new Error("Firebase database connection is unavailable");
        }

        const docData = {
          name,
          text: formattedText,
          rating,
          category,
          timestamp: serverTimestamp()
        };

        if (email) {
          docData.email = email;
        }

        // Write directly to existing 'reviews' collection
        await addDoc(collection(db, 'reviews'), docData);

        // Track custom feedback submission event in GA4
        if (typeof window.gtag === 'function') {
          window.gtag('event', 'feedback_submit', {
            event_category: 'engagement',
            event_label: category,
            value: rating
          });
        }

        // Set cooldown timer on success
        setRateLimit();

        if (statusMsg) {
          statusMsg.className = 'status-msg status-success';
          statusMsg.textContent = 'Thank you! Your feedback has been submitted successfully.';
        }

        // Reset form ONLY on success
        feedbackForm.reset();
        if (ratingDisplay) {
          ratingDisplay.textContent = 'Select a rating (1 to 5 stars)';
          ratingDisplay.style.color = 'var(--color-text-secondary)';
        }
      } catch (err) {
        console.error('Feedback submit error:', err);
        if (statusMsg) {
          statusMsg.className = 'status-msg status-error';
          statusMsg.textContent = 'Submission failed. Please check your connection and try again.';
        }
        // Do NOT clear form on error — user input is preserved
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalBtnText;
        }
      }
    });
  }
});
