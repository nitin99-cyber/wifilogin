"""
app.py — Application entry point and lifecycle owner.

WHAT WAS WRONG IN v2
────────────────────
The boot path did this:

    t = threading.Thread(target=_login_thread, daemon=True)
    t.start()
    t.join()          # <-- wait for login to finish
    popup.show_popup(...)

Starting a thread and immediately joining it is the same as calling the
function directly, only with extra steps. The consequence was that nothing
appeared on screen until the entire login sequence had finished — and that
sequence contains a 5 second adapter wait plus up to 15 one-second portal
retries. On a bad boot the user stared at an empty desktop for 20 seconds
with no indication the app was alive, then got a popup announcing failure.

FR-10 forbids that: the UI must appear immediately and report progress while
authentication happens behind it.

WHAT v3 DOES INSTEAD
────────────────────
    declare DPI awareness      (before any window exists)
    create the Tk root
    create SessionManager      (state, no UI)
    start NetworkMonitor       (throughput sampling thread)
    create the popup           (visible now, showing "Starting…")
    start ConnectionMonitor    (wake detection + recovery thread)
    kick off authentication    (worker thread — nothing waits on it)
    mainloop()

Authentication is now one participant in a running system rather than a
prerequisite for the system starting. Everything the user can see is driven by
polled state, so the display is correct at every instant regardless of what
the worker threads are doing.

WHY ONE Tk ROOT
───────────────
Two `tk.Tk()` objects in one process create two independent Tcl interpreters
that cannot share widgets or variables. The root created here is the only one;
the settings window opens as a Toplevel on it.

THREAD OWNERSHIP
────────────────
    main            Tk event loop. The only thread that touches widgets.
    net-monitor     Reads interface counters once a second.
    conn-monitor    Connectivity polling and recovery.
    power-watcher   Win32 message loop for resume events.
    auth-*          Short-lived; one per authentication attempt.

All are daemon threads, so a closed UI cannot leave the process alive.
"""

from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk

import metadata
import popup
import setup
import ui_scale
from config_manager import load_config
from connection_monitor import ConnectionMonitor
from logger import log
from network_monitor import NetworkMonitor
from session_manager import SessionManager

# Win32: returned by GetLastError when a named object already exists.
_ERROR_ALREADY_EXISTS = 183

#: Held for the lifetime of the process. Releasing it would let a second
#: instance start, so it is deliberately a module global rather than a local.
_instance_mutex = None


def _acquire_single_instance() -> bool:
    """
    Ensure only one copy of the app runs at a time.

    Worth having because the two launch paths can collide: the Run-key entry
    fires at logon while the user also double-clicks the shortcut. Two
    processes would both try to authenticate, and the portal would see the
    second login as a duplicate session. SessionManager's single-flight lock
    only guards within one process, so this guards across processes.

    A named mutex is the standard Windows idiom: kernel-managed, released
    automatically if the process crashes, and needs no lock file to clean up.
    """
    global _instance_mutex
    try:
        _instance_mutex = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Global\\MMMUT-WiFi-AutoLogin-SingleInstance"
        )
        if ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            return False
    except (AttributeError, OSError):
        # Non-Windows or a locked-down environment: prefer running to refusing.
        return True
    return True


class Application:
    """Wires the components together and owns their lifetime."""

    def __init__(self, open_settings_on_start: bool = False):
        self.open_settings_on_start = open_settings_on_start

        # DPI awareness must be declared before the first window exists;
        # Windows latches the mode at that point and later calls do nothing.
        awareness = ui_scale.enable_dpi_awareness()

        self.root = tk.Tk()
        scale = ui_scale.init(self.root)
        log(f"{metadata.APP_NAME} {metadata.VERSION} starting "
            f"(DPI awareness: {awareness}, scale {scale:.2f})")

        # The root is only a host for the popup, so keep it out of the way.
        self.root.withdraw()

        self.session = SessionManager()
        self.monitor = NetworkMonitor()
        self.connection = ConnectionMonitor(self.session)

        self.popup_window = tk.Toplevel(self.root)
        self.popup = popup.create(
            self.popup_window, self.session, self.monitor,
            on_connect=self.connect_now,
            on_logout=self.logout,
            on_settings=self.open_settings,
            on_exit=self.shutdown,
        )

        self._settings_window: tk.Toplevel | None = None
        self._shutting_down = False

    # -- lifecycle ----------------------------------------------------

    def start(self):
        """Bring everything up, then hand control to the Tk event loop."""
        self.monitor.start()
        self.connection.start()

        # Authentication is fired and forgotten. Nothing blocks on it, which
        # is the whole point of FR-10 — the popup above is already on screen.
        self._spawn(self._initial_authenticate, "auth-initial")

        if self.open_settings_on_start:
            # Deferred until the loop is running so the Toplevel is mapped
            # against a root that already exists on screen.
            self.root.after(150, self.open_settings)

        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.root.mainloop()

    def shutdown(self):
        """Stop every thread, then tear down the UI. Idempotent."""
        if self._shutting_down:
            return
        self._shutting_down = True
        log("Shutting down.")

        # Stop the timers first so nothing repaints a half-destroyed window.
        try:
            self.popup.stop_refresh()
        except Exception:
            pass

        self.connection.stop()
        self.monitor.stop()

        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    # -- helpers ------------------------------------------------------

    @staticmethod
    def _spawn(target, name: str):
        """
        Run `target` on a short-lived daemon thread.

        Every action the user can trigger from the UI performs network I/O, and
        network I/O on the Tk thread freezes the window — including the status
        text that is supposed to be telling the user what is happening.
        """
        threading.Thread(target=target, name=name, daemon=True).start()

    def _initial_authenticate(self):
        """First authentication attempt after launch."""
        success, message = self.session.authenticate(manual=False)
        log(f"Initial authentication: {success} - {message}")
        if not success:
            # Hand the problem to the monitor, which owns readiness waiting,
            # backoff and retry. Duplicating that logic here is what made v2's
            # boot path and GUI path drift apart.
            self.connection.request_recovery("initial authentication failed")

    # -- user actions -------------------------------------------------

    def connect_now(self):
        """Manual Connect. Clears logout suppression (FR-17, FR-18)."""
        def worker():
            success, message = self.session.authenticate(manual=True)
            log(f"Manual connect: {success} - {message}")
            if not success:
                self.connection.request_recovery("manual connect failed")

        self._spawn(worker, "auth-manual")

    def logout(self):
        """Deliberate logout. Auto-login stays off until Connect is pressed."""
        def worker():
            success, message = self.session.logout_all()
            log(f"Manual logout: {success} - {message}")

        self._spawn(worker, "auth-logout")

    def open_settings(self):
        """Open (or re-focus) the management window."""
        existing = self._settings_window
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        # The same SessionManager instance is passed in, so the settings
        # window's Connect button shares the single-flight lock and the
        # suppression flag with everything else. A fresh instance would give
        # that window its own private idea of the current state.
        self._settings_window = setup.open_window(self.root, self.session)


# ── Entry point ───────────────────────────────────────────────────────


def run_monitor(open_settings: bool = False):
    """Run the full v3 experience: popup, monitors, and auto-login."""
    Application(open_settings_on_start=open_settings).start()


def main():
    """
    Decide which mode to launch.

        --background   started by Windows at logon: monitor only
        --setup        force the setup wizard
        (no flags)     user launched it: monitor plus the settings window

    First run always gets the wizard, because there are no credentials to
    authenticate with and a monitor showing "No saved credentials" forever
    would be useless.
    """
    args = sys.argv[1:]
    background = "--background" in args
    force_setup = "--setup" in args

    if not _acquire_single_instance():
        log("Another instance is already running; exiting.")
        if not background:
            # Launched by hand, so say something rather than vanishing.
            try:
                from tkinter import messagebox
                temp = tk.Tk()
                temp.withdraw()
                messagebox.showinfo(
                    metadata.APP_NAME,
                    f"{metadata.APP_NAME} is already running.\n\n"
                    "Look for the compact monitor near the bottom-right of "
                    "your screen, or click the small coloured dot in the "
                    "corner to bring it back.")
                temp.destroy()
            except Exception:
                pass
        return

    config = load_config()
    if force_setup or not config.get("setup_completed", False):
        log("Opening setup window (first run or --setup).")
        setup.run()
        return

    run_monitor(open_settings=not background)


if __name__ == "__main__":
    main()
