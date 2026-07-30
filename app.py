"""
   --background   Silent auto-login (used by startup at boot)
   No flags       Opens the Setup / Management GUI window
"""

import sys
import time

from config_manager import load_config
from credential_manager import load_accounts
from internet import is_connected
from network import is_cyberoam_network
from wifi_scanner import connect_to_best_mmmut
from login import login

import setup
from logger import log

# Boot-time retry configuration
MAX_PORTAL_RETRIES = 10       # More retries at boot (WiFi takes time)
RETRY_INTERVAL = 1            # Seconds between portal detection retries
WIFI_SETTLE_DELAY = 1         # Wait after WiFi connect before portal check
BOOT_INITIAL_WAIT = 2         # Initial wait for WiFi adapter to initialize

# Keywords that indicate the login limit has been reached
_MAX_LOGIN_KEYWORDS = [
    "maximum login limit",
    "max login limit",
    "maximum simultaneous",
    "login limit reached",
    "already logged in",
]


def _is_max_login_error(message: str) -> bool:
    """Check if a login response message indicates max login limit reached."""
    if not message:
        return False
    lower = message.lower()
    return any(kw in lower for kw in _MAX_LOGIN_KEYWORDS)


def elapsed(start: float) -> str:
    """Return elapsed time since start as a formatted string."""
    return f"{time.perf_counter() - start:.2f}"


def run_background():
    """Silent auto-login flow — runs instantly at Windows startup."""
    start = time.perf_counter()
    log(f"Background auto-login started (+{elapsed(start)}s)")

    config = load_config()

    # First run → open setup wizard (needs user input)
    if not config["setup_completed"]:
        log("First run detected. Opening setup window.")
        setup.run()
        return

    # Step 1: Quick internet check
    log(f"Checking internet... (+{elapsed(start)}s)")
    if is_connected():
        log(f"Internet already available. Exiting. (+{elapsed(start)}s)")
        return

    # Step 2: Brief wait for WiFi adapter to initialize after boot
    log(f"Waiting for WiFi adapter... (+{elapsed(start)}s)")
    time.sleep(BOOT_INITIAL_WAIT)

    # Step 3: Scan & connect to best MMMUT WiFi
    log(f"Scanning for MMMUT Wi-Fi networks... (+{elapsed(start)}s)")
    ssid = connect_to_best_mmmut()

    if ssid:
        log(f"Connected to {ssid}. Waiting for link... (+{elapsed(start)}s)")
        time.sleep(WIFI_SETTLE_DELAY)
    else:
        log(f"No MMMUT WiFi found. Checking if portal is reachable anyway... "
            f"(+{elapsed(start)}s)")

    # Step 4: Portal detection with retries (network may still be settling)
    log(f"Detecting MMMUT portal... (+{elapsed(start)}s)")
    portal_found = False
    for attempt in range(1, MAX_PORTAL_RETRIES + 1):
        if is_cyberoam_network():
            portal_found = True
            log(f"Portal detected on attempt {attempt} (+{elapsed(start)}s)")
            break
        time.sleep(RETRY_INTERVAL)

    if not portal_found:
        log(f"Portal not reachable after {MAX_PORTAL_RETRIES} attempts. "
            f"Exiting. (+{elapsed(start)}s)")
        return

    # Step 5: Load accounts and login with smart failover
    accounts = load_accounts()
    if not accounts:
        log(f"No accounts found in Credential Manager. (+{elapsed(start)}s)")
        return

    # Try account 1 first
    first = accounts[0]
    username1 = first["username"]
    password1 = first["password"]

    log(f"Logging in as {username1} (primary)... (+{elapsed(start)}s)")

    try:
        status, message = login(username1, password1)
        log(f"Response: {status} - {message} (+{elapsed(start)}s)")

        if status == "LIVE":
            log(f"Login successful using {username1} (+{elapsed(start)}s)")
            return

        # If max login limit reached and we have a second account → try it
        if _is_max_login_error(message) and len(accounts) > 1:
            log(f"Max login limit reached for {username1}. "
                f"Switching to backup account... (+{elapsed(start)}s)")
        elif len(accounts) > 1:
            # Any other failure — still try second account as fallback
            log(f"Login failed for {username1}: {message}. "
                f"Trying backup account... (+{elapsed(start)}s)")
        else:
            log(f"Login failed for {username1}: {message}. "
                f"No backup account available. (+{elapsed(start)}s)")
            return

    except Exception as e:
        log(f"Error with {username1}: {e} (+{elapsed(start)}s)")
        if len(accounts) <= 1:
            return

    # Try account 2 (backup)
    if len(accounts) > 1:
        second = accounts[1]
        username2 = second["username"]
        password2 = second["password"]

        log(f"Logging in as {username2} (backup)... (+{elapsed(start)}s)")

        try:
            status, message = login(username2, password2)
            log(f"Response: {status} - {message} (+{elapsed(start)}s)")

            if status == "LIVE":
                log(f"Login successful using {username2} (+{elapsed(start)}s)")
                return
            else:
                log(f"Backup login also failed: {message} "
                    f"(+{elapsed(start)}s)")
        except Exception as e:
            log(f"Error with {username2}: {e} (+{elapsed(start)}s)")

    log(f"All accounts failed. (+{elapsed(start)}s)")


def main():
    """Entry point — decide between GUI and silent mode."""
    if "--background" in sys.argv:
        run_background()
    else:
        # Always show the setup/management window when launched interactively
        setup.run()


if __name__ == "__main__":
    main()