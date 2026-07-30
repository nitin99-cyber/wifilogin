# MMMUT WiFi Auto Login — Website

Static landing page for the **MMMUT WiFi Auto Login** desktop application.

Built with plain HTML, CSS, and vanilla JavaScript. Designed to be hosted on **GitHub Pages** with zero build steps.

---

## Project Structure

```
website/
├── index.html              # Main landing page
├── style.css               # All styles
├── script.js               # GA4, FAQ accordion, mobile nav, tracking
├── README.md               # This file
└── assets/
    ├── icons/
    │   └── favicon.svg      # SVG favicon
    └── images/
        └── og-image.png     # Open Graph social preview image
```

---

## Deploying to GitHub Pages

1. Push the contents of the `website/` folder to a GitHub repository (e.g., `nitin99-cyber/wifilogin`).
2. Go to **Settings → Pages** in your repository.
3. Under **Source**, select the branch (e.g., `main`) and set the folder to `/ (root)`.
4. Click **Save**. Your site will be live at:
   ```
   https://nitin99-cyber.github.io/wifilogin/
   ```

> **Tip:** If your website files are inside a subfolder (like `website/`), either move them to the repository root or use a separate branch/repo for the site.

---

## How to Update the Download Link

Open `index.html` and search for:

```
https://drive.google.com/YOUR_LINK_HERE
```

Replace **both occurrences** (hero button + download section button) with your actual Google Drive sharing link.

---

## How to Update the Version

1. Search `index.html` for `v1.0.0` and update all occurrences.
2. Update the `<meta>` description if needed.
3. Update the changelog list in the **Download** section.

---

## How to Add Screenshots

1. Take screenshots of the Setup Window, About Dialog, and Installer.
2. Save them as:
   ```
   assets/images/screenshot-setup.png
   assets/images/screenshot-about.png
   assets/images/screenshot-installer.png
   ```
3. In `index.html`, replace each `<div class="screenshot-placeholder">` block with:
   ```html
   <div class="screenshot">
     <img src="assets/images/screenshot-setup.png" alt="Setup Window" loading="lazy" />
   </div>
   ```

---

## How to Configure Google Analytics

1. Create a GA4 property at [analytics.google.com](https://analytics.google.com).
2. Copy your **Measurement ID** (starts with `G-`).
3. Open `script.js` and replace:
   ```js
   const GA_MEASUREMENT_ID = "G-XXXXXXXXXX";
   ```
   with your actual ID:
   ```js
   const GA_MEASUREMENT_ID = "G-YOUR_REAL_ID";
   ```

The script automatically tracks:
- **Page views** (standard GA4)
- **Download button clicks** (`download_click` event)
- **GitHub button clicks** (`github_click` event)

---

## Technologies Used

| Tech | Purpose |
|------|---------|
| HTML5 | Semantic structure |
| CSS3 | Custom properties, Grid, Flexbox, responsive design |
| Vanilla JS | Accordion, mobile nav, scroll effects, analytics |
| Google Fonts | Inter typeface |
| SVG | Icons, illustrations, favicon |

No frameworks. No build tools. No dependencies.

---

## License

MIT License — © 2026 Nitin Deep
