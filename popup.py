"""
Boot Popup — Small always-on-top window shown at Windows startup.

Displays live status during auto-login and provides manual
Connect / Settings buttons if auto-login fails.
"""

import tkinter as tk
from tkinter import ttk
import sys
import threading
import time
from pathlib import Path

from credential_manager import load_accounts
from internet import is_connected
from network import is_cyberoam_network
from wifi_scanner import connect_to_best_mmmut
from login import login, logout
from logger import log
import metadata

# Retry settings for popup connect flow
MAX_PORTAL_RETRIES = 5
RETRY_INTERVAL = 0.3
WIFI_SETTLE_DELAY = 0.5

# Auto-close delay after successful login (seconds)
AUTO_CLOSE_DELAY = 3


# ── Helper ────────────────────────────────────────────────────────────


def _get_icon_path() -> str:
    """Return the absolute path to the application icon."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = Path(__file__).parent
    return str(Path(base_path) / "assets" / "icon.ico")


def _set_icon(window: tk.Tk):
    """Safely set the window icon."""
    try:
        window.iconbitmap(_get_icon_path())
    except Exception:
        pass


def _update_status(label: tk.Label, text: str, color: str = "#64748b"):
    """Thread-safe status label update."""
    label.after(0, lambda: label.config(text=text, foreground=color))


# ── Connect flow (runs in background thread) ─────────────────────────


def _run_popup_connect(status_label: tk.Label, root: tk.Tk,
                       connect_btn: ttk.Button):
    """Load saved credentials and attempt login. Runs in a thread."""

    def _enable_button():
        connect_btn.config(state="normal")

    # Step 1: Check internet
    _update_status(status_label, "⏳ Checking internet...", "#64748b")
    if is_connected():
        _update_status(status_label, "✓ Already connected!", "#16a34a")
        root.after(AUTO_CLOSE_DELAY * 1000, _safe_close, root)
        root.after(0, _enable_button)
        return

    # Step 2: Scan & connect WiFi
    _update_status(status_label, "⏳ Scanning MMMUT Wi-Fi...", "#64748b")
    ssid = connect_to_best_mmmut()

    if ssid:
        _update_status(status_label, f"● Connected to {ssid}", "#2563eb")
        time.sleep(WIFI_SETTLE_DELAY)
    else:
        _update_status(status_label,
                       "⏳ No Wi-Fi found, checking portal...", "#64748b")

    # Step 3: Portal detection
    portal_found = False
    for attempt in range(1, MAX_PORTAL_RETRIES + 1):
        _update_status(
            status_label,
            f"⏳ Detecting portal... ({attempt}/{MAX_PORTAL_RETRIES})",
            "#64748b"
        )
        if is_cyberoam_network():
            portal_found = True
            break
        time.sleep(RETRY_INTERVAL)

    if not portal_found:
        _update_status(status_label, "✗ Not on MMMUT network", "#dc2626")
        root.after(0, _enable_button)
        return

    # Step 4: Load accounts and login
    accounts = load_accounts()
    if not accounts:
        _update_status(status_label, "✗ No saved credentials", "#dc2626")
        root.after(0, _enable_button)
        return

    # Try each account
    for i, acc in enumerate(accounts):
        username = acc["username"]
        password = acc["password"]
        label = "primary" if i == 0 else "backup"

        _update_status(status_label,
                       f"⏳ Logging in as {username}...", "#2563eb")

        try:
            status, message = login(username, password)
            log(f"Popup login ({label}): {status} - {message}")

            if status == "LIVE":
                _update_status(status_label,
                               "✓ Login successful!", "#16a34a")
                root.after(AUTO_CLOSE_DELAY * 1000, _safe_close, root)
                root.after(0, _enable_button)
                return
        except Exception as e:
            log(f"Popup login error ({label}): {e}")

    _update_status(status_label, "✗ Login failed", "#dc2626")
    root.after(0, _enable_button)


def _safe_close(root: tk.Tk):
    """Close the popup window if it still exists."""
    try:
        root.destroy()
    except Exception:
        pass


# ── Popup Window ──────────────────────────────────────────────────────


def show_popup(initial_status: str = "Starting...",
               initial_color: str = "#64748b",
               auto_close: bool = False):
    """
    Show the small boot popup window.

    Args:
        initial_status: Text to display in the status label initially.
        initial_color:  Color for the initial status text.
        auto_close:     If True, auto-close after AUTO_CLOSE_DELAY seconds.
    """
    root = tk.Tk()
    root.title(metadata.APP_NAME)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.overrideredirect(False)
    _set_icon(root)

    # ── Position: bottom-right of screen ──
    popup_w, popup_h = 380, 175
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = screen_w - popup_w - 20
    y = screen_h - popup_h - 60  # above taskbar
    root.geometry(f"{popup_w}x{popup_h}+{x}+{y}")

    # ── Content ──
    frame = ttk.Frame(root, padding=15)
    frame.pack(fill="both", expand=True)

    # Title row
    title_frame = ttk.Frame(frame)
    title_frame.pack(fill="x")

    ttk.Label(
        title_frame,
        text="MMMUT WiFi",
        font=("Segoe UI", 12, "bold")
    ).pack(side="left")

    ttk.Label(
        title_frame,
        text=f"v{metadata.VERSION}",
        font=("Segoe UI", 8),
        foreground="#94a3b8"
    ).pack(side="left", padx=(6, 0), pady=(4, 0))

    # Status label
    status_label = tk.Label(
        frame,
        text=initial_status,
        font=("Segoe UI", 10),
        fg=initial_color,
        anchor="w",
        wraplength=300
    )
    status_label.pack(fill="x", pady=(10, 12))

    # Separator
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 10))

    # Buttons row
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill="x")

    connect_btn = ttk.Button(
        btn_frame,
        text="⟳ Connect",
        command=lambda: _on_connect(status_label, root, connect_btn)
    )
    connect_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))

    logout_btn = ttk.Button(
        btn_frame,
        text="⏻ Logout",
        command=lambda: _on_logout(status_label, root)
    )
    logout_btn.pack(side="left", fill="x", expand=True, padx=(3, 3))

    settings_btn = ttk.Button(
        btn_frame,
        text="⚙ Settings",
        command=lambda: _on_settings(root)
    )
    settings_btn.pack(side="left", fill="x", expand=True, padx=(3, 3))

    close_btn = ttk.Button(
        btn_frame,
        text="✕",
        width=3,
        command=root.destroy
    )
    close_btn.pack(side="right", padx=(3, 0))

    # Auto-close on success
    if auto_close:
        root.after(AUTO_CLOSE_DELAY * 1000, _safe_close, root)

    root.mainloop()


def _on_connect(status_label: tk.Label, root: tk.Tk,
                connect_btn: ttk.Button):
    """Handle Connect button click."""
    connect_btn.config(state="disabled")
    thread = threading.Thread(
        target=_run_popup_connect,
        args=(status_label, root, connect_btn),
        daemon=True
    )
    thread.start()


def _on_settings(root: tk.Tk):
    """Open the full settings window and close popup."""
    root.destroy()
    import setup
    setup.run()


def _on_logout(status_label: tk.Label, root: tk.Tk):
    """Log out all saved accounts from the portal."""

    def _logout_thread():
        _update_status(status_label, "⏳ Logging out...", "#64748b")

        accounts = load_accounts()
        if not accounts:
            _update_status(status_label, "✗ No saved credentials", "#dc2626")
            return

        all_ok = True
        for acc in accounts:
            username = acc["username"]
            try:
                status, message = logout(username)
                log(f"Logout {username}: {status} - {message}")
                if status != "LIVE":
                    all_ok = False
            except Exception as e:
                log(f"Logout error for {username}: {e}")
                all_ok = False

        if all_ok:
            _update_status(status_label, "✓ Logged out", "#16a34a")
        else:
            _update_status(status_label, "✓ Logout sent", "#16a34a")

    thread = threading.Thread(target=_logout_thread, daemon=True)
    thread.start()
