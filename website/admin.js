import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.1/firebase-app.js";
import { 
  getAuth, 
  signInWithEmailAndPassword, 
  onAuthStateChanged,
  signOut
} from "https://www.gstatic.com/firebasejs/10.8.1/firebase-auth.js";
import { 
  getFirestore, 
  collection, 
  getDocs, 
  getDoc,
  doc,
  query, 
  orderBy 
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

let app, auth, db;
try {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  db = getFirestore(app);
} catch (error) {
  console.warn("Firebase not configured properly.", error);
}

const loginContainer = document.getElementById('login-container');
const dashboard = document.getElementById('dashboard');
const errorMsg = document.getElementById('login-error');

// Handle Auth State
onAuthStateChanged(auth, (user) => {
  if (user) {
    loginContainer.style.display = 'none';
    dashboard.style.display = 'block';
    fetchAdminData();
  } else {
    loginContainer.style.display = 'block';
    dashboard.style.display = 'none';
  }
});

// Login
document.getElementById('login-btn').addEventListener('click', async () => {
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;
  try {
    await signInWithEmailAndPassword(auth, email, password);
  } catch (e) {
    errorMsg.innerText = "Login failed: " + e.message;
  }
});

// Logout
document.getElementById('logout-btn').addEventListener('click', () => {
  signOut(auth);
});

// Fetch Data securely
async function fetchAdminData() {
  if (!db) return;

  try {
    // Visits
    const vSnap = await getDoc(doc(db, 'analytics', 'visits'));
    if (vSnap.exists()) document.getElementById('val-visits').innerText = vSnap.data().count;

    // Downloads
    const dSnap = await getDoc(doc(db, 'analytics', 'downloads'));
    if (dSnap.exists()) document.getElementById('val-downloads').innerText = dSnap.data().count;

    // Reviews
    const q = query(collection(db, "reviews"), orderBy("timestamp", "desc"));
    const revSnap = await getDocs(q);
    
    let html = '';
    let totalScore = 0;
    let count = 0;

    revSnap.forEach((doc) => {
      const data = doc.data();
      totalScore += data.rating || 0;
      count++;
      const date = data.timestamp ? new Date(data.timestamp.toDate()).toLocaleString() : '';
      
      html += `
        <div class="review-item">
          <strong>${data.name}</strong> - ${data.rating} Stars <br>
          <small>${date}</small><br>
          ${data.text}
        </div>
      `;
    });

    document.getElementById('reviews-list').innerHTML = html || 'No reviews yet.';
    if(count > 0) {
      document.getElementById('val-rating').innerText = (totalScore / count).toFixed(1);
    }
  } catch(e) {
    console.error("Error fetching admin data", e);
    document.getElementById('reviews-list').innerText = "Permission Denied or Error Fetching.";
  }
}
