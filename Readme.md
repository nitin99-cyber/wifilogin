<p align="center">
  <img src="assets/icon.ico" alt="MMMUT WiFi Auto Login" width="80"/>
</p>

<h1 align="center">MMMUT WiFi Auto Login</h1>

<p align="center">
  <b>Never manually login to college Wi-Fi again.</b><br/>
  A lightweight Windows utility that automatically connects to the MMMUT campus network<br/>and logs into the Cyberoam captive portal — silently, instantly, every time you boot.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue?style=flat-square" alt="Platform"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-yellow?style=flat-square" alt="Python"/>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"/>
  <img src="https://img.shields.io/badge/version-2.0.0-orange?style=flat-square" alt="Version"/>
</p>

---

## Table of Contents

- [The Story — Why I Built This](#the-story--why-i-built-this)
- [How I Found the Solution](#how-i-found-the-solution)
- [Problems I Faced & How I Solved Them](#problems-i-faced--how-i-solved-them)
- [Features](#features)
- [How It Works](#how-it-works)
- [Architecture & Project Structure](#architecture--project-structure)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Building from Source](#building-from-source)
- [Configuration](#configuration)
- [Privacy & Security](#privacy--security)
- [License](#license)

---

## The Story — Why I Built This

Every student at **MMMUT (Madan Mohan Malaviya University of Technology)** knows the daily frustration:

1. You open your laptop.
2. Windows connects to the campus Wi-Fi (like `MMMUT_LAN` or `MMMUT_HOSTEL`).
3. But there's no internet yet — you're trapped behind a **Cyberoam captive portal**.
4. You have to open a browser, wait for the portal page to load at `172.16.1.3:8090`, type your username and password, and hit Login.
5. You do this **every single time** — after every reboot, every sleep, every time the session expires.
6. Worse, if your phone is already logged in, you hit the **"Maximum Login Limit Reached"** error, and now you have to go logout from your phone first or use a different account.

I got tired of doing this 5-10 times a day. As a Computer Science student, I thought — if I'm going to spend 4 years on this campus, the least I can do is automate the 30 seconds of annoyance that greets me every single morning.

**So I built this app.**

The goal was simple: the moment my laptop boots up, before I even touch the keyboard, the app should silently connect to the strongest MMMUT Wi-Fi, login to the portal, and give me working internet — all in the background, with zero interaction.

---

## How I Found the Solution

The Cyberoam portal at `172.16.1.3:8090` is a standard web form. But to automate it, I needed to understand what happens **under the hood** when you click the "Login" button on that webpage.

### Step 1: Inspecting the Network Request

I opened **Chrome DevTools** (`F12` → **Network** tab), logged in manually on the portal, and watched the HTTP traffic. I discovered:

- The browser sends an **HTTP POST** request to `http://172.16.1.3:8090/login.xml`
- The form data contains:
  ```
  mode: 191
  username: <your_username>
  password: <your_password>
  a: <unix_timestamp_in_milliseconds>
  producttype: 0
  ```
- The server responds with **XML**, not HTML:
  ```xml
  <requestresponse>
    <status>LIVE</status>
    <message>You are signed in as mit2022xxxxxx</message>
  </requestresponse>
  ```
  Or on failure:
  ```xml
  <requestresponse>
    <status>LOGIN</status>
    <message>You've reached the maximum login limit</message>
  </requestresponse>
  ```

### Step 2: Reproducing It in Python

Once I knew the exact URL, payload, and expected response, I wrote a simple Python script using the `requests` library to replicate the browser's POST request. It worked on the first try. That 10-line script became the foundation of this entire application.

### Step 3: Making It a Real Application

A script that runs in the terminal isn't useful for everyday students. I needed:
- A **GUI** so users can enter their credentials without touching code.
- **Secure storage** so passwords aren't saved in plain text files.
- **Auto-startup** so it runs silently every time Windows boots.
- A **standalone .exe** so users don't need to install Python.
- An **installer** so it feels like a real Windows application.

That's how a 10-line script turned into a full desktop application.

---

## Problems I Faced & How I Solved Them

### Problem 1: App Not Starting on Windows Boot

**What happened:** I initially used Windows Task Scheduler (`schtasks /Create /SC ONLOGON`) to register the app for auto-startup. It seemed to work during development, but on real student laptops, the task was never created. The app wasn't showing up in Task Manager's "Startup Apps" tab either.

**Root cause:** Creating an `ONLOGON` scheduled task requires **Administrator privileges**. Students run the app as a standard user, so the `schtasks` command was silently failing (returning a non-zero exit code that I wasn't surfacing).

**Solution:** I switched to the **Windows Registry Run Key** method. By writing to `HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`, the app registers itself for auto-startup without needing admin rights. This is the same mechanism used by apps like Discord, Spotify, and Steam. It also automatically appears in Task Manager → Startup Apps, giving users full control.

---

### Problem 2: "Maximum Login Limit Reached"

**What happened:** Students often have their phone connected to the same portal account. When the app tried to login from the laptop, the portal rejected it with "You've reached the maximum login limit."

**Solution:** I implemented a **smart credential failover** system. The app accepts two sets of credentials (Account 1 and Account 2). It always tries Account 1 first. If the portal response message contains keywords like "maximum login limit" or "already logged in", the app immediately and automatically retries with Account 2 — no user intervention required.

---

### Problem 3: Wi-Fi Not Ready at Boot

**What happened:** When Windows boots, the app would start before the Wi-Fi adapter had fully initialized. The portal check would fail because there was literally no network connection yet.

**Solution:** I added a 2-second initial wait (`BOOT_INITIAL_WAIT`) to let the hardware wake up, followed by aggressive retry logic — 10 attempts with 1-second intervals to detect the Cyberoam portal. This gives the Wi-Fi adapter up to ~12 seconds to become ready, which is more than enough even on slow hardware.

---

### Problem 4: Storing Passwords Securely

**What happened:** Early versions saved credentials in a `config.json` file in plain text. This was a serious security issue — anyone with access to the file could read the passwords.

**Solution:** I switched to the `keyring` library, which interfaces directly with the **Windows Credential Manager** (the same vault that stores your Windows login password, browser saved passwords, etc.). Passwords are encrypted by the operating system using the user's login session key. No plain-text credentials exist anywhere in the app's files.

---

### Problem 5: Finding the Best Wi-Fi Access Point

**What happened:** MMMUT campus has multiple Wi-Fi access points with different SSIDs (like `MMMUT_LAN`, `MMMUT_HOSTEL`, `mmmut_5g`). Sometimes the laptop would connect to a weak access point even when a stronger one was available.

**Solution:** I built a Wi-Fi scanner (`wifi_scanner.py`) that:
1. Runs `netsh wlan show networks mode=bssid` to list all visible networks with their signal strengths.
2. Filters for networks containing "mmmut" in the name (case-insensitive).
3. Sorts them by signal strength (strongest first).
4. Connects to the strongest one using `netsh wlan connect`.

---

### Problem 6: UI Freezing During Network Operations

**What happened:** When the user clicked "Save & Connect" in the GUI, the app would freeze for several seconds while it scanned Wi-Fi networks and attempted login. Windows would show "(Not Responding)" in the title bar.

**Solution:** I moved all network operations to a **background thread** using Python's `threading` module. The GUI runs on the main thread (Tkinter's `mainloop()`), while Wi-Fi scanning and login happen concurrently on a separate thread. Status updates are safely pushed back to the UI using Tkinter's `after()` method.

---

## Features

- **Zero-Touch Auto Login** — Runs silently at Windows startup, connects to the strongest MMMUT Wi-Fi, and logs in automatically.
- **Smart Credential Failover** — If Account 1 hits the max login limit, instantly tries Account 2.
- **Secure Password Storage** — Uses Windows Credential Manager (encrypted, OS-level security).
- **Intelligent Wi-Fi Selection** — Scans all available MMMUT networks and picks the strongest signal.
- **No Admin Required** — Everything works with standard user privileges.
- **Lightweight** — The entire background process completes in ~4 seconds and uses minimal resources.
- **Clean GUI** — Simple setup window for managing credentials and startup preferences.
- **Proper Windows Integration** — Shows in Task Manager Startup Apps, installs to Program Files, has proper uninstaller.

---

## How It Works

```
Windows Boot
    │
    ▼
Registry Run Key launches app.exe --background
    │
    ▼
┌─────────────────────────────┐
│  Is internet already working? │──── Yes ──► Exit (nothing to do)
└─────────────────────────────┘
    │ No
    ▼
┌─────────────────────────────┐
│  Wait for WiFi adapter (2s)  │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Scan & connect to strongest │
│  MMMUT Wi-Fi network         │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Is Cyberoam portal reachable │──── No (retry 10x) ──► Exit
│  at 172.16.1.3:8090?         │
└─────────────────────────────┘
    │ Yes
    ▼
┌─────────────────────────────┐
│  POST login with Account 1   │──── Success (LIVE) ──► Exit ✓
└─────────────────────────────┘
    │ Failed / Max Limit
    ▼
┌─────────────────────────────┐
│  POST login with Account 2   │──── Success (LIVE) ──► Exit ✓
└─────────────────────────────┘
    │ Failed
    ▼
  Log error & exit
```

---

## Architecture & Project Structure

```
wifi_auto-login/
│
├── app.py                  # Entry point — routes to GUI or background mode
├── setup.py                # Tkinter GUI — credential form, status display
├── login.py                # HTTP POST to Cyberoam portal, XML response parsing
├── credential_manager.py   # Read/write credentials via Windows Credential Manager
├── config_manager.py       # JSON config file management (setup state, preferences)
├── startup.py              # Windows Registry auto-startup registration
├── wifi_scanner.py         # Scan Wi-Fi networks, connect to strongest MMMUT AP
├── internet.py             # Quick internet connectivity check (Google 204)
├── network.py              # Cyberoam portal reachability check
├── logger.py               # File-based logging to AppData/Local
├── config.py               # Constants (portal URL, product type)
├── metadata.py             # App name, version, author info
├── main.py                 # Legacy standalone login script
│
├── assets/
│   └── icon.ico            # Application icon
│
├── installer/
│   └── setup.iss           # Inno Setup installer script
│
├── website/                # Static landing page (GitHub Pages)
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── assets/
│
├── MMMUT WiFi Auto Login.spec   # PyInstaller build configuration
├── requirements.txt             # Python dependencies
├── .env                         # Dev-only test credentials (not shipped)
└── .gitignore
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Language | Python 3.10+ | Rapid development, rich ecosystem |
| GUI | Tkinter (ttk) | Built into Python, no extra dependencies |
| HTTP Client | `requests` | Clean API for POST requests to the portal |
| XML Parsing | `xml.etree.ElementTree` | Built into Python, parses Cyberoam responses |
| Credential Storage | `keyring` | Secure OS-level encrypted storage |
| Wi-Fi Control | `netsh` via `subprocess` | Native Windows network commands |
| Auto-Startup | `winreg` | Windows Registry — no admin, shows in Task Manager |
| Packaging | PyInstaller | Bundles Python + dependencies into standalone .exe |
| Installer | Inno Setup | Professional Windows installer with uninstall support |
| Website | HTML/CSS/JS | Static landing page on GitHub Pages |

---

## Installation

### For Users (Recommended)
1. Download the latest `MMMUT-WiFi-Auto-Login-Setup.exe` from the [Releases](https://github.com/nitin99-cyber/mmmutwifilogin/releases) page.
2. Run the installer — it will install the app to Program Files and register it for auto-startup.
3. The setup window will open. Enter your MMMUT portal credentials and click **Save & Connect**.
4. That's it. The app will now auto-login every time you boot your laptop.

### For Developers
```bash
# Clone the repository
git clone https://github.com/nitin99-cyber/mmmutwifilogin.git
cd mmmutwifilogin

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app (GUI mode)
python app.py

# Run the app (background/silent mode)
python app.py --background
```

---

## Building from Source

### Build the Standalone EXE
```bash
# Activate virtual environment
.venv\Scripts\activate

# Build with PyInstaller
pyinstaller "MMMUT WiFi Auto Login.spec"
```
The output `.exe` will be in the `dist/` folder.

### Build the Installer
1. Install [Inno Setup](https://jrsoftware.org/isinfo.php).
2. Open `installer/setup.iss` in Inno Setup Compiler.
3. Click **Build → Compile**.
4. The installer `MMMUT-WiFi-Auto-Login-Setup.exe` will be generated in the project root.

---

## Configuration

The app stores its configuration at:
```
%LOCALAPPDATA%\MMMUT WiFi Auto Login\config.json
```

| Key | Type | Description |
|-----|------|-------------|
| `setup_completed` | `bool` | Whether the user has saved credentials at least once |
| `startup_enabled` | `bool` | Whether auto-startup is enabled |

Credentials are stored in the **Windows Credential Manager** under the service name `MMMUT-WIFI-AUTOLOGIN`.

Logs are written to:
```
%LOCALAPPDATA%\MMMUT WiFi Auto Login\wifi_login.log
```

---

## Privacy & Security

- **No data leaves your computer.** The app only communicates with the MMMUT portal at `172.16.1.3` and a Google connectivity check endpoint.
- **No analytics, no tracking, no telemetry.**
- **Passwords are never stored in plain text.** They are encrypted by Windows Credential Manager using your OS login session key.
- **No admin privileges required.** The app runs entirely within standard user permissions.
- **Open source.** Every line of code is auditable in this repository.

---

## License

MIT License — © 2026 Nitin Deep

Made with ❤️ for MMMUT students.
