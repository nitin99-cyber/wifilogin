"""
setup.py — The setup wizard and management window.

WHAT CHANGED IN v3
──────────────────
1. RESOLUTION SAFETY. v2 hardcoded window sizes in raw pixels:

       center_window(root, 380, 680)
       center_window(about_win, 460, 920)

   920 px does not fit on a 768 px laptop screen, and because the dialog was
   `resizable(False, False)` with no scrolling, the Close button sat below the
   bottom edge where no click could ever reach it. At 150% Windows scaling the
   same dialog wanted 1380 physical pixels of height. Every window here now
   asks for a size in dp, gets clamped to the real work area, and puts its
   content inside a ScrollableFrame so nothing is ever unreachable.

2. ONE SCROLLBAR, NOT TWO. v2 nested a fixed `height=260` account canvas
   inside a non-scrolling window. Two independent scroll regions on one screen
   is confusing, and the wheel target became ambiguous. The inner canvas is
   gone; the whole window scrolls as one surface.

3. NO DUPLICATED LOGIN LOGIC. v2's `run_connect_flow` was a second, slightly
   different copy of the boot login sequence, so a fix in one place did not
   fix the other. Both now call SessionManager, which means the Connect button
   gets single-flight protection and logout suppression for free (FR-18).

4. REUSABLE WINDOW. `build()` populates any Tk or Toplevel, so the monitor
   popup can open Settings as a child window instead of spawning a second Tk
   interpreter in the same process — which does not work.
"""

from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import metadata
import ui_scale
from config_manager import load_config, save_config
from credential_manager import (
    MAX_ACCOUNTS,
    delete_all_accounts,
    load_accounts,
    save_account,
)
from logger import log
from session_manager import SessionManager
from startup import add_to_startup, is_startup_enabled, remove_from_startup
from ui_scale import ScrollableFrame, dp

# Requested window sizes, in density-independent pixels. These are wishes,
# not commands — fit_size() clamps them to whatever the display can show.
MAIN_W_DP = 420
MAIN_H_DP = 680
MAIN_MIN_W_DP = 360
MAIN_MIN_H_DP = 420

ABOUT_W_DP = 480
ABOUT_H_DP = 720
ABOUT_MIN_W_DP = 340
ABOUT_MIN_H_DP = 360

# How long a one-off message (e.g. "Credentials saved") stays on screen before
# the label reverts to reporting live session state.
FLASH_SECONDS = 4.0

# How often the status line re-reads the session state.
STATUS_POLL_MS = 800

COLOR_MUTED = "#64748b"
COLOR_INFO = "#2563eb"
COLOR_OK = "#16a34a"
COLOR_ERROR = "#dc2626"


# ── Window helpers ────────────────────────────────────────────────────


def center_window(window: tk.Toplevel | tk.Tk, width_dp: float,
                  height_dp: float, min_w_dp: float | None = None,
                  min_h_dp: float | None = None):
    """
    Size and centre a window using dp units and the real work area.

    Kept under its original name so the call sites read the same as before,
    but the arguments are now density-independent and the result is clamped
    to the usable desktop rather than trusting the caller's pixel guess.
    """
    ui_scale.place_center(window, width_dp, height_dp,
                          min_w_dp=min_w_dp, min_h_dp=min_h_dp)


def get_icon_path() -> str:
    """Return the absolute path to the application icon."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = Path(__file__).parent
    return str(Path(base_path) / "assets" / "icon.ico")


def set_icon(window: tk.Toplevel | tk.Tk):
    """Set the window icon, ignoring failure (a missing icon is cosmetic)."""
    try:
        window.iconbitmap(get_icon_path())
    except Exception:
        pass


# ── About dialog ──────────────────────────────────────────────────────


def open_about(parent: tk.Misc):
    """
    Open the About dialog.

    This is the window that was broken on every ordinary laptop in v2. Three
    changes fix it: the content lives in a ScrollableFrame, the window is
    resizable, and its height is clamped to the work area. It now asks for
    720 dp and gracefully accepts 620 px on a small screen.
    """
    about_win = tk.Toplevel(parent)
    about_win.title(f"About - {metadata.APP_NAME}")
    about_win.resizable(True, True)
    center_window(about_win, ABOUT_W_DP, ABOUT_H_DP,
                  ABOUT_MIN_W_DP, ABOUT_MIN_H_DP)
    about_win.transient(parent if isinstance(parent, (tk.Tk, tk.Toplevel))
                        else about_win.master)
    about_win.grab_set()
    set_icon(about_win)

    scroller = ScrollableFrame(about_win)
    scroller.pack(fill="both", expand=True)

    frame = ttk.Frame(scroller.body, padding=dp(20))
    frame.pack(fill="both", expand=True)

    def heading(text: str):
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=dp(10))
        ttk.Label(frame, text=text,
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")

    def bullets(items):
        for item in items:
            ttk.Label(frame, text=item, font=("Segoe UI", 9),
                      wraplength=dp(ABOUT_W_DP - 70),
                      justify="left").pack(anchor="w", padx=dp(10))

    ttk.Label(frame, text=metadata.APP_NAME,
              font=("Segoe UI", 16, "bold")).pack()
    ttk.Label(frame, text=f"Version {metadata.VERSION}",
              font=("Segoe UI", 10)).pack(pady=(0, dp(10)))
    ttk.Label(frame, text=metadata.DESCRIPTION, justify="center",
              wraplength=dp(ABOUT_W_DP - 60)).pack()

    heading("What's new in 3.0")
    bullets([
        "• Reconnects automatically after sleep or Wi-Fi loss",
        "• Live download and upload speed monitor",
        "• Connection quality, band, latency and signal on hover",
        "• Compact overlay that stays out of the way",
        "• Correct layout at any screen size or display scaling",
    ])

    heading("Features")
    bullets([
        "• Automatic login",
        "• Secure credential storage (Windows Credential Manager)",
        "• Multiple account support with automatic failover",
        "• Portal logout",
        "• Starts with Windows",
        "• Lightweight — no background service, no installer bloat",
    ])

    heading("Privacy")
    bullets([
        "• No passwords are uploaded.",
        "• No personal data is collected.",
        "• No analytics or telemetry are used.",
        "• Credentials are stored only on your computer.",
        "• Passwords are never written to the log file.",
        "• The app talks only to the official MMMUT login portal.",
    ])

    heading("How logout works")
    bullets([
        "Logout ends your portal session immediately — you do not",
        "have to wait for it to expire.",
        "",
        "⚠ Logout disconnects EVERY device using that username,",
        "not just this one.",
        "",
        "Example: if Account 1 is signed in on your phone and your",
        "laptop, logging out Account 1 disconnects both. Account 2",
        "on another device stays connected.",
        "",
        "After you log out, automatic login stays switched off until",
        "you press Connect again — the app will not quietly sign you",
        "back in.",
        "",
        "Tip: use different accounts on different devices so you can",
        "log out selectively.",
    ])

    heading("Developer")
    ttk.Label(frame, text=f"{metadata.AUTHOR}\nB.Tech CSE'29",
              font=("Segoe UI", 9)).pack(anchor="w", padx=dp(10))

    heading("Links")

    def add_link_row(label: str, text: str):
        # Skip blanks: an empty "Website:" row looks like a bug.
        if not text:
            return
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=dp(2))
        ttk.Label(row, text=label, width=10,
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Label(row, text=text, font=("Segoe UI", 9),
                  wraplength=dp(ABOUT_W_DP - 140),
                  justify="left").pack(side="left")

    add_link_row("GitHub", metadata.GITHUB_URL)
    add_link_row("Website", metadata.WEBSITE)
    add_link_row("Email", metadata.EMAIL)
    add_link_row("License", metadata.LICENSE)
    add_link_row("Copyright", metadata.COPYRIGHT)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=dp(10))
    ttk.Label(
        frame,
        text=("Made for MMMUT students.\n"
              "Feedback and issues are welcome on GitHub."),
        justify="center", font=("Segoe UI", 9),
    ).pack(pady=(0, dp(10)))

    ttk.Button(frame, text="Close",
               command=about_win.destroy).pack(pady=(dp(5), 0))

    scroller.scroll_to_top()


# ── Status line ───────────────────────────────────────────────────────


class _StatusPresenter:
    """
    Drives the status label.

    Two kinds of message compete for one line:

      * SESSION STATE — "Connected", "Reconnecting…". Owned by SessionManager
        and changed by worker threads.
      * LOCAL EVENTS — "Credentials saved", "Auto-start enabled". Owned by
        this window and irrelevant to the session.

    Rather than have threads write to the widget (unsafe) or fight over it,
    the label polls session state on a Tk timer and a local event temporarily
    overrides it for a few seconds. Everything therefore happens on the Tk
    main thread, and `flash()` is safe to call from anywhere.
    """

    def __init__(self, label: tk.Label, session: SessionManager):
        self._label = label
        self._session = session
        self._flash_text = ""
        self._flash_color = COLOR_MUTED
        self._flash_until = 0.0
        self._after_id: str | None = None

    def flash(self, text: str, color: str = COLOR_MUTED,
              seconds: float = FLASH_SECONDS):
        """Show a transient message. Safe to call from any thread."""
        self._flash_text = text
        self._flash_color = color
        self._flash_until = time.monotonic() + seconds

    def start(self):
        self._tick()

    def stop(self):
        if self._after_id is not None:
            try:
                self._label.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _tick(self):
        try:
            if self._flash_text and time.monotonic() < self._flash_until:
                text, color = self._flash_text, self._flash_color
            else:
                self._flash_text = ""
                text = f"Status: {self._session.status_text()}"
                detail = self._session.detail
                if detail and detail not in text:
                    text = f"{text} — {detail}"
                color = COLOR_MUTED
            self._label.config(text=text, fg=color)
        except tk.TclError:
            return  # Window closed mid-tick; stop quietly.

        self._after_id = self._label.after(STATUS_POLL_MS, self._tick)


# ── Window construction ───────────────────────────────────────────────


def build(window: tk.Tk | tk.Toplevel,
          session: SessionManager | None = None) -> _StatusPresenter:
    """
    Populate `window` with the management UI.

    Split out from `run()` so the same UI can be a standalone Tk root at first
    launch or a Toplevel opened from the monitor popup later. Returns the
    status presenter so the caller can stop its timer on close.
    """
    if session is None:
        session = SessionManager()

    window.title(metadata.APP_NAME)
    window.resizable(True, True)
    set_icon(window)

    # One scroll surface for the whole window. On a large monitor the
    # scrollbar hides itself and this looks exactly like a plain frame.
    scroller = ScrollableFrame(window)
    scroller.pack(fill="both", expand=True)

    frame = ttk.Frame(scroller.body, padding=dp(20))
    frame.pack(fill="both", expand=True)

    # -- header ------------------------------------------------------
    ttk.Label(frame, text=metadata.APP_NAME,
              font=("Segoe UI", 16, "bold")).pack()
    ttk.Label(frame, text=f"Version {metadata.VERSION}",
              font=("Segoe UI", 10)).pack(pady=(0, dp(10)))
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, dp(15)))

    # -- accounts ----------------------------------------------------
    form_frame = ttk.Frame(frame)
    form_frame.pack(fill="both", expand=True)

    ttk.Label(form_frame, text=f"Accounts (1-{MAX_ACCOUNTS})",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(form_frame,
              text="Account 1 is required. Later accounts are tried in order.",
              foreground=COLOR_MUTED,
              wraplength=dp(MAIN_W_DP - 60),
              justify="left").pack(anchor="w", pady=(dp(2), dp(6)))

    # A plain frame, not a nested canvas: the outer ScrollableFrame already
    # provides scrolling, and two scroll regions would compete for the wheel.
    accounts_frame = ttk.Frame(form_frame)
    accounts_frame.pack(fill="x")

    account_entries: list[tuple[ttk.LabelFrame, ttk.Entry, ttk.Entry]] = []

    def add_account_row(username: str = "", password: str = ""):
        """Append one editable account row, up to the supported limit."""
        if len(account_entries) >= MAX_ACCOUNTS:
            messagebox.showinfo(
                "Account limit",
                f"You can add up to {MAX_ACCOUNTS} accounts.")
            return

        index = len(account_entries) + 1
        row = ttk.LabelFrame(accounts_frame, text=f"Account {index}",
                             padding=dp(8))
        row.pack(fill="x", pady=(0, dp(6)))

        username_entry = ttk.Entry(row)
        password_entry = ttk.Entry(row, show="*")

        ttk.Label(row, text="Username").grid(
            row=0, column=0, sticky="w", padx=(0, dp(8)))
        username_entry.grid(row=0, column=1, sticky="ew")
        ttk.Label(row, text="Password").grid(
            row=1, column=0, sticky="w", padx=(0, dp(8)), pady=(dp(5), 0))
        password_entry.grid(row=1, column=1, sticky="ew", pady=(dp(5), 0))
        row.columnconfigure(1, weight=1)

        username_entry.insert(0, username)
        password_entry.insert(0, password)
        account_entries.append((row, username_entry, password_entry))

    for account in load_accounts():
        add_account_row(account.get("username", ""),
                        account.get("password", ""))
    if not account_entries:
        add_account_row()

    ttk.Button(form_frame, text="+ Add Account",
               command=add_account_row).pack(anchor="w", pady=(dp(5), dp(10)))

    # -- startup toggle ----------------------------------------------
    startup_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(form_frame, text="Start automatically with Windows",
                    variable=startup_var).pack(anchor="w", pady=(0, dp(15)))

    # -- status line -------------------------------------------------
    ttk.Separator(frame, orient="horizontal").pack(
        fill="x", pady=(dp(5), dp(10)))

    status_label = tk.Label(frame, text="Status: Ready",
                            font=("Segoe UI", 10), fg=COLOR_MUTED,
                            anchor="w", justify="left",
                            wraplength=dp(MAIN_W_DP - 60))
    status_label.pack(fill="x", pady=(0, dp(10)))

    status = _StatusPresenter(status_label, session)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, dp(10)))

    # -- saved configuration -----------------------------------------
    config = load_config()
    is_returning_user = config.get("setup_completed", False)
    startup_var.set(config.get("startup_enabled", True))

    # -- actions -----------------------------------------------------

    def collect_credentials() -> list[tuple[str, str]] | None:
        """Read and validate the form. Returns None if invalid."""
        credentials = [
            (username.get().strip(), password.get().strip())
            for _, username, password in account_entries
        ]
        # Drop trailing rows the user left completely blank.
        while credentials and not credentials[-1][0] and not credentials[-1][1]:
            credentials.pop()

        if not credentials or not credentials[0][0] or not credentials[0][1]:
            messagebox.showerror("Error", "Account 1 is required.")
            return None
        if any(not user or not pwd for user, pwd in credentials):
            messagebox.showerror(
                "Error", "Complete each account or clear its empty row.")
            return None
        return credentials

    def save_and_connect():
        """Save credentials and hand authentication to the session manager."""
        credentials = collect_credentials()
        if credentials is None:
            return

        status.flash("Saving credentials...", COLOR_MUTED)
        delete_all_accounts()
        for index, (username, password) in enumerate(credentials, start=1):
            save_account(index, username, password)

        save_config({"setup_completed": True,
                     "startup_enabled": startup_var.get()})

        if startup_var.get():
            add_to_startup()
        else:
            remove_from_startup()

        log("Credentials saved. Starting connect flow.")
        _show_management_buttons()

        def worker():
            # manual=True: the user pressed a button, so this also clears any
            # logout suppression left over from an earlier Logout (FR-17/18).
            success, message = session.authenticate(manual=True)
            status.flash(
                ("✓ " if success else "✗ ") + message,
                COLOR_OK if success else COLOR_ERROR,
            )

        threading.Thread(target=worker, name="setup-connect",
                         daemon=True).start()

    def do_logout():
        """Log every saved account out and stop auto-login."""
        if not load_accounts():
            status.flash("No saved credentials", COLOR_ERROR)
            return

        def worker():
            status.flash("Logging out...", COLOR_MUTED)
            success, message = session.logout_all()
            status.flash(("✓ " if success else "● ") + message,
                         COLOR_OK if success else COLOR_INFO)

        threading.Thread(target=worker, name="setup-logout",
                         daemon=True).start()

    # -- primary buttons ---------------------------------------------
    buttons_frame = ttk.Frame(frame)
    buttons_frame.pack(fill="x", pady=(0, dp(5)))

    ttk.Button(buttons_frame, text="Save & Connect",
               command=save_and_connect).pack(
        side="left", fill="x", expand=True, padx=(0, dp(3)))
    ttk.Button(buttons_frame, text="Logout", command=do_logout).pack(
        side="left", fill="x", expand=True, padx=(dp(3), dp(3)))
    ttk.Button(buttons_frame, text="About",
               command=lambda: open_about(window)).pack(
        side="right", fill="x", expand=True, padx=(dp(3), 0))

    # -- management buttons ------------------------------------------
    mgmt_frame = ttk.Frame(frame)

    def _show_management_buttons():
        mgmt_frame.pack(fill="x", pady=(dp(5), dp(5)))

    def delete_credentials():
        confirm = messagebox.askyesno(
            "Delete Credentials",
            "Are you sure?\n\n"
            "This removes all saved accounts from\n"
            "Windows Credential Manager.")
        if not confirm:
            return

        delete_all_accounts()
        save_config({"setup_completed": False, "startup_enabled": False})
        remove_from_startup()

        for row, _, _ in account_entries:
            row.destroy()
        account_entries.clear()
        add_account_row()
        startup_var.set(True)
        mgmt_frame.pack_forget()

        status.flash("✓ Credentials deleted", COLOR_OK)
        log("All credentials deleted by user.")

    def toggle_auto_start():
        if is_startup_enabled():
            remove_from_startup()
            save_config({"setup_completed": True, "startup_enabled": False})
            startup_var.set(False)
            auto_start_btn.config(text="Enable Auto-Start")
            status.flash("Auto-start disabled", COLOR_MUTED)
            log("Auto-start disabled by user.")
        else:
            add_to_startup()
            save_config({"setup_completed": True, "startup_enabled": True})
            startup_var.set(True)
            auto_start_btn.config(text="Disable Auto-Start")
            status.flash("Auto-start enabled", COLOR_OK)
            log("Auto-start enabled by user.")

    ttk.Button(mgmt_frame, text="Delete Credentials",
               command=delete_credentials).pack(
        side="left", fill="x", expand=True, padx=(0, dp(5)))

    auto_start_btn = ttk.Button(
        mgmt_frame,
        text="Disable Auto-Start" if is_startup_enabled()
        else "Enable Auto-Start",
        command=toggle_auto_start,
    )
    auto_start_btn.pack(side="right", fill="x", expand=True, padx=(dp(5), 0))

    if is_returning_user and account_entries:
        _show_management_buttons()

    # -- footer ------------------------------------------------------
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=dp(10))

    footer_frame = ttk.Frame(frame)
    footer_frame.pack(fill="x")

    footer_label = tk.Label(
        footer_frame,
        text=f"Developed by {metadata.AUTHOR}\n{metadata.COPYRIGHT}",
        font=("Segoe UI", 9), fg="blue", cursor="hand2",
    )
    footer_label.pack()
    footer_label.bind("<Button-1>", lambda e: open_about(window))

    status.start()
    return status


def open_window(parent: tk.Misc,
                session: SessionManager | None = None) -> tk.Toplevel:
    """
    Open the management UI as a child window of an existing Tk application.

    This is what the popup's "Settings…" uses. Creating a second `tk.Tk()`
    in one process gives you two Tcl interpreters that cannot share widgets,
    so a Toplevel is the only correct option once a root exists.
    """
    window = tk.Toplevel(parent)
    status = build(window, session=session)
    center_window(window, MAIN_W_DP, MAIN_H_DP, MAIN_MIN_W_DP, MAIN_MIN_H_DP)

    def on_close():
        status.stop()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_close)
    window.lift()
    window.focus_force()
    return window


def run(session: SessionManager | None = None):
    """
    Launch the setup / management window standalone.

    DPI awareness is declared before `tk.Tk()` because Windows latches a
    process's awareness mode when its first window appears — calling it
    afterwards silently does nothing and the app renders blurry.
    """
    mode = ui_scale.enable_dpi_awareness()

    root = tk.Tk()
    ui_scale.init(root)
    log(f"Setup window: DPI awareness via {mode}, "
        f"scale {ui_scale.scale_factor():.2f}")

    build(root, session=session)
    center_window(root, MAIN_W_DP, MAIN_H_DP, MAIN_MIN_W_DP, MAIN_MIN_H_DP)
    root.mainloop()
