import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
import time
from pathlib import Path

from credential_manager import save_account, load_accounts, delete_all_accounts
from config_manager import load_config, save_config
from startup import add_to_startup, remove_from_startup, is_startup_enabled
from internet import is_connected
from network import is_cyberoam_network
from wifi_scanner import connect_to_best_mmmut
from login import login, logout
from logger import log
import metadata

# Retry settings (same as app.py for consistency)
MAX_PORTAL_RETRIES = 15
RETRY_INTERVAL = 1
WIFI_SETTLE_DELAY = 1


# ── Helper functions ──────────────────────────────────────────────────


def center_window(window: tk.Toplevel | tk.Tk, width: int, height: int):
    """Center a Tkinter window on screen."""
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def get_icon_path() -> str:
    """Return the absolute path to the application icon."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = Path(__file__).parent
    return str(Path(base_path) / "assets" / "icon.ico")


def set_icon(window: tk.Toplevel | tk.Tk):
    """Safely set the window icon."""
    try:
        window.iconbitmap(get_icon_path())
    except Exception:
        pass


# ── About Dialog ──────────────────────────────────────────────────────


def open_about(parent: tk.Tk):
    """Open the About modal dialog."""
    about_win = tk.Toplevel(parent)
    about_win.title(f"About - {metadata.APP_NAME}")
    about_win.resizable(False, False)
    center_window(about_win, 460, 920)
    about_win.transient(parent)
    about_win.grab_set()
    set_icon(about_win)

    frame = ttk.Frame(about_win, padding=20)
    frame.pack(fill="both", expand=True)

    # Title
    ttk.Label(frame, text=metadata.APP_NAME,
              font=("Segoe UI", 16, "bold")).pack()
    ttk.Label(frame, text=f"Version {metadata.VERSION}",
              font=("Segoe UI", 10)).pack(pady=(0, 10))
    ttk.Label(frame, text=metadata.DESCRIPTION,
              justify="center").pack()

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Features
    ttk.Label(frame, text="Features",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    for feature in ["• Automatic Login", "• Secure Credential Storage",
                     "• Multiple Account Support", "• Portal Logout",
                     "• Boot Status Popup", "• Windows Startup",
                     "• Lightweight"]:
        ttk.Label(frame, text=feature).pack(anchor="w", padx=10)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Privacy
    ttk.Label(frame, text="Privacy",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    for point in [
        "• No passwords are uploaded.",
        "• No personal data is collected.",
        "• No analytics are used.",
        "• Credentials are stored only on your computer.",
        "• The application only communicates with the official MMMUT login portal."
    ]:
        ttk.Label(frame, text=point).pack(anchor="w", padx=10)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # How Logout Works
    ttk.Label(frame, text="How Logout Works",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    for line in [
        "Logout ends your portal session instantly —",
        "no need to wait for session expiry.",
        "",
        "⚠ Logout disconnects ALL devices using",
        "that username, not just the current one.",
        "",
        "Example: If Account 1 is on Phone & Laptop,",
        "logging out Account 1 disconnects both.",
        "Account 2 on another device stays connected.",
        "",
        "Tip: Use different accounts on different",
        "devices to log out selectively.",
    ]:
        ttk.Label(frame, text=line,
                  font=("Segoe UI", 9)).pack(anchor="w", padx=10)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Developer
    ttk.Label(frame, text="Developer",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(frame, text=f"{metadata.AUTHOR}\nB.Tech CSE'29").pack(
        anchor="w", padx=10)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Links
    def add_link_row(label: str, text: str):
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=10,
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Label(row, text=text).pack(side="left")

    add_link_row("GitHub", metadata.GITHUB_URL)
    add_link_row("Website", metadata.WEBSITE)
    add_link_row("Email", metadata.EMAIL)
    add_link_row("License", metadata.LICENSE)
    add_link_row("Copyright", metadata.COPYRIGHT)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Message
    ttk.Label(
        frame,
        text=("Made for MMMUT students.\n"
              "Please leave a review and stay updated with the\n"
              "developer for the next version with rich feature support."),
        justify="center"
    ).pack(pady=(0, 10))

    ttk.Button(frame, text="Close",
               command=about_win.destroy).pack(pady=(5, 0))


# ── Status update helper ──────────────────────────────────────────────


def update_status(label: tk.Label, text: str, color: str = "#334155"):
    """Thread-safe status label update."""
    label.after(0, lambda: (
        label.config(text=text, foreground=color)
    ))


# ── Connect flow (runs in background thread) ─────────────────────────


def run_connect_flow(status_label: tk.Label, username: str, password: str):
    """Detect portal and login. Runs in a background thread."""

    # Step 1: Quick internet check
    update_status(status_label, "Checking internet...", "#64748b")
    if is_connected():
        update_status(status_label, "✓ Already connected to the internet",
                      "#16a34a")
        return

    # Step 2: Scan & connect to best MMMUT WiFi
    update_status(status_label, "Scanning for MMMUT Wi-Fi...", "#64748b")
    ssid = connect_to_best_mmmut()

    if ssid:
        update_status(status_label,
                      f"● Connected to {ssid}", "#2563eb")
        time.sleep(WIFI_SETTLE_DELAY)
    else:
        update_status(status_label,
                      "No MMMUT Wi-Fi found. Checking portal...", "#64748b")

    # Step 3: Quick portal detection
    update_status(status_label, "Detecting MMMUT portal...", "#64748b")

    portal_found = False
    for attempt in range(1, MAX_PORTAL_RETRIES + 1):
        update_status(
            status_label,
            f"Detecting MMMUT portal... ({attempt}/{MAX_PORTAL_RETRIES})",
            "#64748b"
        )
        if is_cyberoam_network():
            portal_found = True
            break
        time.sleep(RETRY_INTERVAL)

    if not portal_found:
        update_status(status_label,
                      "✗ Not on MMMUT network", "#dc2626")
        return

    update_status(status_label, "● Portal detected", "#2563eb")

    # Step 4: Login
    accounts = load_accounts()
    if not accounts:
        # Fallback if somehow load fails
        accounts = [{"username": username, "password": password}]

    for i, acc in enumerate(accounts):
        user = acc["username"]
        pwd = acc["password"]
        acc_label = "primary" if i == 0 else "backup"

        update_status(status_label,
                      f"● Logging in as {user}...", "#2563eb")

        try:
            status, message = login(user, pwd)
            log(f"GUI login ({acc_label}): {status} - {message}")

            if status == "LIVE":
                update_status(status_label,
                              "✓ Login successful!", "#16a34a")
                return
        except Exception as e:
            log(f"Error during login ({acc_label}): {e}")

    # If we get here, all accounts failed
    update_status(status_label, "✗ Login failed for all accounts", "#dc2626")


# ── Main Setup Window ─────────────────────────────────────────────────


def run():
    """Launch the setup / management window."""
    root = tk.Tk()
    root.title(metadata.APP_NAME)
    root.resizable(False, False)
    set_icon(root)

    # Main scrollable frame
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    # ── Header ──
    ttk.Label(frame, text=metadata.APP_NAME,
              font=("Segoe UI", 16, "bold")).pack()
    ttk.Label(frame, text=f"Version {metadata.VERSION}",
              font=("Segoe UI", 10)).pack(pady=(0, 10))

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 15))

    # ── Credential Form ──
    form_frame = ttk.Frame(frame)
    form_frame.pack(fill="x")

    ttk.Label(form_frame, text="Username 1").pack(anchor="w")
    username1_entry = ttk.Entry(form_frame)
    username1_entry.pack(fill="x", pady=(2, 10))

    ttk.Label(form_frame, text="Password").pack(anchor="w")
    password1_entry = ttk.Entry(form_frame, show="*")
    password1_entry.pack(fill="x", pady=(2, 15))

    ttk.Label(form_frame, text="Username 2 (Optional)").pack(anchor="w")
    username2_entry = ttk.Entry(form_frame)
    username2_entry.pack(fill="x", pady=(2, 10))

    ttk.Label(form_frame, text="Password").pack(anchor="w")
    password2_entry = ttk.Entry(form_frame, show="*")
    password2_entry.pack(fill="x", pady=(2, 15))

    # ── Auto-start checkbox ──
    startup_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        form_frame,
        text="Start automatically with Windows",
        variable=startup_var
    ).pack(anchor="w", pady=(0, 15))

    # ── Status Label ──
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(5, 10))

    status_label = tk.Label(
        frame,
        text="Status: Ready",
        font=("Segoe UI", 10),
        fg="#64748b",
        anchor="w"
    )
    status_label.pack(fill="x", pady=(0, 10))

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 10))

    # ── Pre-fill credentials if returning user ──
    config = load_config()
    existing_accounts = load_accounts()
    is_returning_user = config.get("setup_completed", False)

    if existing_accounts:
        # Fill account 1
        acc1 = existing_accounts[0]
        username1_entry.insert(0, acc1.get("username", ""))
        password1_entry.insert(0, acc1.get("password", ""))

        # Fill account 2 if it exists
        if len(existing_accounts) > 1:
            acc2 = existing_accounts[1]
            username2_entry.insert(0, acc2.get("username", ""))
            password2_entry.insert(0, acc2.get("password", ""))

    # Pre-fill startup checkbox from config
    startup_var.set(config.get("startup_enabled", True))

    # ── Save & Connect ──
    def save_and_connect():
        """Save credentials, update startup, then run the connect flow."""
        username1 = username1_entry.get().strip()
        password1 = password1_entry.get().strip()
        username2 = username2_entry.get().strip()
        password2 = password2_entry.get().strip()

        if not username1 or not password1:
            messagebox.showerror("Error", "Account 1 is required.")
            return

        # Save credentials
        update_status(status_label, "Saving credentials...", "#64748b")
        save_account(1, username1, password1)
        if username2 and password2:
            save_account(2, username2, password2)

        # Update config
        new_config = {
            "setup_completed": True,
            "startup_enabled": startup_var.get()
        }
        save_config(new_config)

        # Update startup
        if startup_var.get():
            add_to_startup()
        else:
            remove_from_startup()

        log("Credentials saved. Starting connect flow.")

        # Show management buttons now that credentials exist
        _show_management_buttons()

        # Run connect flow in background thread
        thread = threading.Thread(
            target=run_connect_flow,
            args=(status_label, username1, password1),
            daemon=True
        )
        thread.start()

    # ── Buttons ──
    buttons_frame = ttk.Frame(frame)
    buttons_frame.pack(fill="x", pady=(0, 5))

    ttk.Button(
        buttons_frame, text="Save & Connect",
        command=save_and_connect
    ).pack(side="left", fill="x", expand=True, padx=(0, 3))

    def do_logout():
        """Log out all saved accounts from the portal."""
        accounts = load_accounts()
        if not accounts:
            update_status(status_label, "No saved credentials", "#dc2626")
            return

        def _logout_thread():
            update_status(status_label, "Logging out...", "#64748b")
            for acc in accounts:
                username = acc["username"]
                try:
                    status, message = logout(username)
                    log(f"Logout {username}: {status} - {message}")
                except Exception as e:
                    log(f"Logout error for {username}: {e}")
            update_status(status_label, "✓ Logged out", "#16a34a")

        thread = threading.Thread(target=_logout_thread, daemon=True)
        thread.start()

    ttk.Button(
        buttons_frame, text="Logout",
        command=do_logout
    ).pack(side="left", fill="x", expand=True, padx=(3, 3))

    ttk.Button(
        buttons_frame, text="About",
        command=lambda: open_about(root)
    ).pack(side="right", fill="x", expand=True, padx=(3, 0))

    # ── Management Buttons (shown only when credentials exist) ──
    mgmt_frame = ttk.Frame(frame)

    def _show_management_buttons():
        """Show the Delete / Auto-Start management buttons."""
        mgmt_frame.pack(fill="x", pady=(5, 5))

    def delete_credentials():
        """Delete all saved credentials after confirmation."""
        confirm = messagebox.askyesno(
            "Delete Credentials",
            "Are you sure?\n\n"
            "This will remove all saved accounts from\n"
            "Windows Credential Manager."
        )
        if not confirm:
            return

        delete_all_accounts()

        # Reset config
        save_config({
            "setup_completed": False,
            "startup_enabled": False
        })
        remove_from_startup()

        # Clear form fields
        username1_entry.delete(0, tk.END)
        password1_entry.delete(0, tk.END)
        username2_entry.delete(0, tk.END)
        password2_entry.delete(0, tk.END)
        startup_var.set(True)

        # Hide management buttons
        mgmt_frame.pack_forget()

        update_status(status_label,
                      "✓ Credentials deleted", "#16a34a")
        log("All credentials deleted by user.")

    def toggle_auto_start():
        """Toggle the auto-start Task Scheduler task."""
        if is_startup_enabled():
            remove_from_startup()
            save_config({
                "setup_completed": True,
                "startup_enabled": False
            })
            startup_var.set(False)
            auto_start_btn.config(text="Enable Auto-Start")
            update_status(status_label,
                          "Auto-start disabled", "#64748b")
            log("Auto-start disabled by user.")
        else:
            add_to_startup()
            save_config({
                "setup_completed": True,
                "startup_enabled": True
            })
            startup_var.set(True)
            auto_start_btn.config(text="Disable Auto-Start")
            update_status(status_label,
                          "Auto-start enabled", "#16a34a")
            log("Auto-start enabled by user.")

    ttk.Button(
        mgmt_frame, text="Delete Credentials",
        command=delete_credentials
    ).pack(side="left", fill="x", expand=True, padx=(0, 5))

    auto_start_text = ("Disable Auto-Start"
                       if is_startup_enabled()
                       else "Enable Auto-Start")
    auto_start_btn = ttk.Button(
        mgmt_frame, text=auto_start_text,
        command=toggle_auto_start
    )
    auto_start_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

    # Show management buttons if returning user
    if is_returning_user and existing_accounts:
        _show_management_buttons()

    # ── Footer ──
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    footer_frame = ttk.Frame(frame)
    footer_frame.pack(fill="x")

    footer_label = tk.Label(
        footer_frame,
        text=f"Developed by {metadata.AUTHOR}\n{metadata.COPYRIGHT}",
        font=("Segoe UI", 9),
        fg="blue",
        cursor="hand2"
    )
    footer_label.pack()
    footer_label.bind("<Button-1>", lambda e: open_about(root))

    # ── Final sizing and display ──
    center_window(root, 380, 680)
    root.mainloop()