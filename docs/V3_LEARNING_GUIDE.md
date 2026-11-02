# WiFi Auto Login v3.0 — Complete Learning & Documentation Guide

This document serves as a complete guide to understanding, building, and explaining **WiFi Auto Login v3.0**. It is designed to help you learn the underlying concepts, understand the architecture, and answer interview questions about the project.

---

## 1. Product Requirements Document (PRD) Summary

**Product:** WiFi Auto Login
**Version:** 3.0.0
**Primary Goal:** Improve reliability after sleep/reconnect and introduce a lightweight, non-intrusive real-time connection monitor.

### Key Objectives
- **Automatic Recovery:** When the laptop wakes from sleep, automatically detect the Wi-Fi reconnection and re-authenticate if the session expired.
- **Live Network Monitor:** Display real-time download and upload throughput without doing external speed tests.
- **Unobtrusive UI:** A compact, transparent popup that sits above the taskbar. It expands on hover to show signal strength, latency, and connection quality.
- **State Management:** Introduce a robust state machine (`IDLE`, `NETWORK_DETECTING`, `AUTHENTICATING`, `CONNECTED`) to handle connection lifecycles elegantly.
- **Preserve Core Logic:** Keep Windows Credential Manager security, multi-account fallback, and the core HTTP POST authentication from v2.0.

---

## 2. Topics & Technologies Used

To build v3.0, the following core topics and technologies are utilized:

1. **Network Interface Monitoring:** Accessing OS-level network statistics (byte counters) to calculate real-time throughput.
2. **OS Event Hooking (Windows API):** Listening for Windows Power Management events (`SYSTEM_RESUME`) to detect laptop sleep/wake cycles.
3. **Multithreading & Concurrency:** Isolating blocking I/O (network requests, ICMP pings) in background threads to keep the Tkinter UI responsive.
4. **Finite State Machines (FSM):** Modeling the Wi-Fi connection session to transition smoothly between different states (e.g., checking internet -> detecting portal -> authenticating).
5. **Desktop UI/UX Design:** Creating frameless (borderless), always-on-top, semi-transparent windows using Tkinter that react to mouse hover events.
6. **Network Reachability & Latency (ICMP/HTTP):** Using lightweight ping checks for latency and HTTP requests to detect captive portals.
7. **Secure Credential Storage:** Utilizing the Windows Credential Manager API to store and retrieve passwords securely.
8. **Modular Software Architecture:** Separating the application into distinct modules (View, Monitors, Session Manager) rather than a monolithic script.

---

## 3. Definitions of Concepts Used

- **Captive Portal:** A web page that a user is forced to interact with before gaining access to the public internet (common in colleges/hotels).
- **Throughput:** The actual rate of successful data delivery over a network channel. Measured here in Kbps/Mbps based on real-time traffic, not maximum potential bandwidth.
- **Latency (Ping):** The time it takes for a small packet of data to travel from your laptop to a server and back. Measured in milliseconds (ms). High latency means a sluggish connection.
- **Main Thread (UI Thread):** The primary thread where Tkinter draws the UI and listens for clicks. If you run a slow network request on this thread, the UI "freezes."
- **Polling:** Repeatedly checking the status of a system at regular intervals (e.g., checking the network byte count every 1 second).
- **Race Condition:** A software bug where the timing of events causes unexpected behavior. For example, trying to login *immediately* upon waking up before the Wi-Fi adapter has actually finished turning on.
- **State Machine:** A design pattern where the system is always in exactly one distinct "state" (e.g., `CONNECTED`), and follows strict rules to transition to another state (e.g., `SESSION_LOST`).

---

## 4. Complete Architecture & Process (How it's made)

### A. Modular Structure
The v3.0 architecture is split into single-responsibility modules:
- `app.py`: Entry point; initializes the UI and starts background threads.
- `session_manager.py`: The "brain" that runs the state machine. It decides *when* to authenticate.
- `connection_monitor.py`: Watches for Wi-Fi drops and system sleep/wake events.
- `network_monitor.py`: Calculates live upload/download speeds.
- `login.py`: The HTTP POST logic to authenticate with the portal.
- `popup.py`: The Tkinter UI logic (transparency, hover expansion, minimization).

### B. The Step-by-Step Process Flow

1. **Initialization:**
   - The user starts the app. `app.py` loads credentials from Windows Credential Manager.
   - The UI (`popup.py`) renders a small, semi-transparent widget at the bottom right.
2. **Real-time Monitoring (`network_monitor.py`):**
   - A background thread wakes up every 1 second.
   - It reads the total bytes sent/received by the network adapter.
   - It subtracts the previous second's values to get the delta (bytes per second).
   - It sends this delta to the UI thread to update the "↓ 42.6 Mbps ↑ 3.2 Mbps" text safely.
3. **Handling Sleep & Wake:**
   - The user closes their laptop (Sleep).
   - When opened, Windows fires a `SYSTEM_RESUME` event.
   - `connection_monitor.py` catches this event and alerts `session_manager.py`.
4. **Smart Reconnection (The State Machine):**
   - **Wait:** The app knows the Wi-Fi card isn't ready instantly, so it waits and polls for network readiness (avoiding race conditions).
   - **Check:** Once Wi-Fi connects to "MMMUT", the app tries to reach an external site (e.g., 1.1.1.1).
   - **Portal Detection:** If the external site redirects to `172.16.1.3:8090`, the app knows the session expired.
   - **Authentication:** `login.py` runs in the background, submitting the HTTP POST request.
   - **Success:** Once logged in, the UI updates from "Authenticating..." to showing the live network speed.
5. **UI Interaction:**
   - The UI is usually 70% transparent.
   - When the mouse hovers over it, Tkinter detects an `<Enter>` event. Opacity goes to 100%, and the window expands to show Signal and Latency.
   - On mouse `<Leave>`, it shrinks and becomes transparent again.

---

## 5. Interview Questions & Answers

If you put this project on your resume, here is how you can confidently answer technical questions.

**Q1: How did you implement the live network throughput monitor without eating up user bandwidth?**
> **Answer:** "I avoided doing active speed tests (like downloading a file continuously), which would waste bandwidth. Instead, I used OS-level network interface statistics. In Python, I read the system's total bytes sent and received, wait one second, and read them again. The difference between the two readings gives me the exact real-time throughput of the laptop without generating any extra network traffic."

**Q2: Why did you separate the Tkinter UI and the network monitoring into different threads?**
> **Answer:** "Tkinter operates on an event-driven main loop. If I execute a blocking operation—like an HTTP request to the captive portal or an ICMP ping—on the main thread, the entire UI freezes until the network responds. By using Python's `threading` module, I offloaded network polling and authentication to background workers. These workers then safely send updates back to the UI thread using thread-safe mechanisms, ensuring the app remains snappy and responsive."

**Q3: How does your application handle the laptop waking up from sleep?**
> **Answer:** "I hooked into the Windows Power Management API to listen for `SYSTEM_RESUME` events. However, immediately after waking up, the network adapter is usually still initializing. If you try to authenticate immediately, it fails. I handled this race condition by implementing a `NETWORK_DETECTING` state with a controlled backoff/retry loop. The app waits until the Wi-Fi adapter successfully connects to the campus SSID before attempting to check internet reachability and authenticate."

**Q4: Can you explain the State Machine pattern in your application?**
> **Answer:** "In v2.0, connection checks were mostly linear, which caused bugs if the network dropped mid-login. For v3.0, I implemented an explicit finite state machine (FSM). The session manager always knows its state: `IDLE`, `NETWORK_DETECTING`, `PORTAL_CHECK`, `AUTHENTICATING`, or `CONNECTED`. This prevents the application from making contradictory actions—like attempting to authenticate twice simultaneously—and makes the logic highly predictable and easy to debug."

**Q5: How did you design the application to be unobtrusive and user-friendly?**
> **Answer:** "My goal was 'visible when useful, invisible by default.' I created a frameless, compact Tkinter window positioned right above the taskbar. By default, it has a reduced opacity (e.g., 70%), so it doesn't distract the user or completely block content underneath. I used Tkinter hover events so that when the user moves their mouse over the widget, it becomes fully opaque and expands to reveal deeper metrics like latency and connection quality."

**Q6: What happens if a user's primary account reaches its maximum login limit?**
> **Answer:** "The application reads the XML response from the captive portal. If it detects the specific 'Maximum Login Limit Reached' message, it falls back to a secondary account configured in the Windows Credential Manager. This logic runs automatically, ensuring the user gets internet access without needing to intervene manually."
