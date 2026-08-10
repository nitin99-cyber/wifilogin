// Import Firebase SDKs (using modular CDN)
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.1/firebase-app.js";
import { 
  getFirestore, 
  collection, 
  addDoc, 
  doc,
  setDoc,
  increment 
} from "https://www.gstatic.com/firebasejs/10.8.1/firebase-firestore.js";

// ==========================================
// 🔴 FIREBASE CONFIGURATION (USER MUST FILL)
// ==========================================
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT_ID.appspot.com",
  messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// Initialize Firebase
let app, db;
try {
  app = initializeApp(firebaseConfig);
  db = getFirestore(app);
} catch (error) {
  console.warn("Firebase not properly configured yet.", error);
}

document.addEventListener('DOMContentLoaded', () => {

  // ==========================================
  // SCROLL REVEAL ANIMATIONS
  // ==========================================
  const revealElements = document.querySelectorAll('.reveal');
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  revealElements.forEach(el => revealObserver.observe(el));


  // ==========================================
  // SILENT ANALYTICS TRACKING
  // ==========================================
  const downloadBtn = document.getElementById('download-btn');

  async function trackStat(statName) {
    if (!db) return;
    try {
      const statRef = doc(db, 'analytics', statName);
      await setDoc(statRef, { count: increment(1) }, { merge: true });
    } catch (e) {
      console.error("Silent tracking failed (likely missing config)", e);
    }
  }

  // Track site load as a visit silently
  trackStat('visits');

  // Track Download clicks silently
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      trackStat('downloads');
    });
  }

  // ==========================================
  // REVIEWS & FEEDBACK SUBMISSION
  // ==========================================
  const feedbackForm = document.getElementById('feedback-form');
  const statusMsg = document.getElementById('review-status-msg');

  if (feedbackForm) {
    feedbackForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      if (!db) {
        statusMsg.style.color = '#ff00cc';
        statusMsg.innerText = "Error: Firebase is not configured. Cannot save review.";
        return;
      }

      const name = document.getElementById('reviewer-name').value;
      const text = document.getElementById('reviewer-text').value;
      
      // Get selected rating (radio buttons)
      let rating = 5; // default
      const ratingInput = document.querySelector('input[name="rating"]:checked');
      if (ratingInput) {
        rating = parseInt(ratingInput.value);
      }

      const submitBtn = feedbackForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.innerText = "Submitting...";

      try {
        await addDoc(collection(db, "reviews"), {
          name: name,
          text: text,
          rating: rating,
          timestamp: new Date()
        });

        statusMsg.style.color = '#00d2ff';
        statusMsg.innerText = "Thank you for your feedback!";
        feedbackForm.reset();
      } catch (e) {
        console.error("Error adding review: ", e);
        statusMsg.style.color = '#ff00cc';
        statusMsg.innerText = "Error submitting review. Please try again later.";
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = "Submit Review";
      }
    });
  }
});
