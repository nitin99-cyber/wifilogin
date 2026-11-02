"""
connection_monitor.py — Wake detection, network readiness, and recovery.

WHAT PROBLEM THIS SOLVES
────────────────────────
v2 authenticated exactly once, at boot, and then stopped caring. Every
remaining annoyance came from that single design choice: close the laptop lid
at 11am, open it at 2pm, and the Wi-Fi has reconnected but the captive-portal
session has expired — so there is Wi-Fi, no internet, and no app doing
anything about it.

This module watches the connection for the whole session and asks
SessionManager to recover when something breaks.

DETECTING RESUME FROM SLEEP — TWO MECHANISMS
────────────────────────────────────────────
1. PRIMARY: Windows broadcasts WM_POWERBROADCAST / PBT_APMRESUMEAUTOMATIC to
   every top-level window when it resumes. We create a hidden message-only
   window on its own thread to receive it. This is the accurate, event-driven
   route — no polling, immediate notification.

2. FALLBACK: a wall-clock gap check. The poll loop records `time.time()` on
   every tick; if far more wall-clock time has passed than the tick interval
   should allow, the process was suspended.

Both are kept live rather than treating the fallback as dead code, because
the mechanisms fail differently: the message window depends on pywin32 being
importable, while the gap check also catches process suspension that never
produced a power broadcast. A false positive is harmless — the worst outcome
is one extra connectivity check.

WHY NOT JUST "sleep 30 SECONDS AFTER WAKE"
──────────────────────────────────────────
A fixed delay is wrong in both directions: too short on a cold Wi-Fi adapter
and needlessly slow on a fast one. FR-12 requires waiting for actual network
readiness instead, so we poll for the adapter with a backoff and proceed the
moment it is genuinely usable.

ADAPTIVE POLLING
────────────────
Connectivity checks are cheap but not free, so the interval adapts: a healthy
connection is checked infrequently, and a broken one is checked often. This
keeps idle CPU and network cost near zero while still recovering quickly.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from internet import is_connected
from network import is_cyberoam_network
from wifi_scanner import get_current_ssid, connect_to_best_mmmut
from logger import log
import session_manager
from session_manager import SessionManager

# ── Timing configuration ──────────────────────────────────────────────

#: Poll interval while everything is healthy. Long, because nothing is wrong.
POLL_INTERVAL_HEALTHY = 15.0

#: Poll interval while degraded. Short, because we want fast recovery.
POLL_INTERVAL_DEGRADED = 5.0

#: How long after a resume we keep retrying before giving up (seconds).
POST_WAKE_READINESS_TIMEOUT = 60.0

#: Backoff schedule for post-wake readiness polling. Grows so a slow adapter
#: is tolerated without spinning tightly on a fast one.
READINESS_BACKOFF = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0)

#: Wall-clock gap above the expected tick that implies the process was
#: suspended. Generous enough that ordinary scheduling delay never trips it.
WAKE_GAP_THRESHOLD = 25.0

# Win32 message constants (defined here so the fallback path does not need
# pywin32 merely to name them).
_WM_POWERBROADCAST = 0x0218
_WM_CLOSE = 0x0010
_WM_DESTROY = 0x0002
_PBT_APMRESUMEAUTOMATIC = 0x0012
_PBT_APMRESUMESUSPEND = 0x0007
_PBT_APMSUSPEND = 0x0004


class _PowerWatcher:
    """
    Hidden message-only window that reports resume-from-sleep events.

    Runs its own thread because a Win32 message loop is blocking, and the
    window must be created on the same thread that pumps its messages —
    Windows delivers messages to the creating thread's queue.

    Import of pywin32 is deliberately deferred to `start()` so that a machine
    without pywin32 degrades to the wall-clock fallback instead of failing to
    launch the whole app.
    """

    def __init__(self, on_resume: Callable[[], None],
                 on_suspend: Callable[[], None] | None = None):
        self._on_resume = on_resume
        self._on_suspend = on_suspend
        self._thread: threading.Thread | None = None
        self._hwnd = None
        self._class_name = "WifiAutoLoginPowerWatcher"
        self._available = False

    @property
    def available(self) -> bool:
        """True if the message window is actually running."""
        return self._available

    def start(self) -> bool:
        """Start the watcher. Returns False if pywin32 is unavailable."""
        try:
            import win32gui  # noqa: F401
        except ImportError:
            log("Power watcher unavailable (pywin32 missing); "
                "using wall-clock wake detection only.")
            return False

        self._thread = threading.Thread(
            target=self._run, name="power-watcher", daemon=True
        )
        self._thread.start()
        return True

    def _run(self):
        import win32api
        import win32con
        import win32gui

        try:
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = self._class_name
            wc.hInstance = win32api.GetModuleHandle(None)
            # Messages absent from this dict fall through to DefWindowProc.
            wc.lpfnWndProc = {
                _WM_POWERBROADCAST: self._on_power_message,
                _WM_CLOSE: self._on_close,
                _WM_DESTROY: self._on_destroy,
            }
            class_atom = win32gui.RegisterClass(wc)

            self._hwnd = win32gui.CreateWindow(
                class_atom, self._class_name, 0,
                0, 0, 0, 0, 0, 0, wc.hInstance, None,
            )
            self._available = True
            log("Power watcher started (listening for resume events).")

            # Blocking until PostQuitMessage. This thread does nothing else.
            win32gui.PumpMessages()
        except Exception as exc:
            self._available = False
            log(f"Power watcher failed to start: {exc}")

    def _on_power_message(self, hwnd, msg, wparam, lparam):
        """Window procedure for WM_POWERBROADCAST."""
        try:
            if wparam in (_PBT_APMRESUMEAUTOMATIC, _PBT_APMRESUMESUSPEND):
                log("System resume detected (power broadcast).")
                self._on_resume()
            elif wparam == _PBT_APMSUSPEND:
                log("System suspend detected.")
                if self._on_suspend:
                    self._on_suspend()
        except Exception as exc:
            log(f"Power message handler error: {exc}")
        return True

    def _on_close(self, hwnd, msg, wparam, lparam):
        """Destroy the window when asked to close."""
        import win32gui
        win32gui.DestroyWindow(hwnd)
        return 0

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        """
        Post WM_QUIT so PumpMessages() returns and the thread can finish.

        PostQuitMessage must be called from the thread that owns the message
        loop, which is why this happens in the window procedure rather than
        in stop().
        """
        import win32gui
        win32gui.PostQuitMessage(0)
        return 0

    def stop(self):
        """
        Ask the message loop to exit.

        WM_CLOSE is posted rather than WM_QUIT: WM_QUIT targets a thread's
        message queue, not a window, so PostMessage(hwnd, WM_QUIT) is silently
        ignored. WM_CLOSE reaches the window procedure above, which then
        destroys the window and posts the real quit message from the correct
        thread.
        """
        hwnd = self._hwnd
        self._available = False
        if not hwnd:
            return
        try:
            import win32gui
            win32gui.PostMessage(hwnd, _WM_CLOSE, 0, 0)
        except Exception:
            pass
        self._hwnd = None


class ConnectionMonitor:
    """
    Watches the connection lifecycle and triggers recovery.

    Owns two threads: the poll loop, and (indirectly) the power watcher.
    Neither touches Tk. State changes are published through SessionManager,
    which the UI observes.
    """

    def __init__(self, session: SessionManager):
        self._session = session
        self._stop_event = threading.Event()

        # Set by the power watcher or the gap check to request an immediate
        # recovery pass, rather than waiting for the next scheduled poll.
        self._recover_now = threading.Event()

        self._thread: threading.Thread | None = None
        self._power_watcher = _PowerWatcher(on_resume=self._on_resume)

        self._last_tick_wall = 0.0
        self._was_connected = False

    # -- lifecycle ----------------------------------------------------

    def start(self):
        """Start monitoring. Safe to call more than once."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._last_tick_wall = time.time()

        self._power_watcher.start()

        self._thread = threading.Thread(
            target=self._run, name="connection-monitor", daemon=True
        )
        self._thread.start()
        log("Connection monitor started.")

    def stop(self):
        """Stop monitoring."""
        self._stop_event.set()
        self._recover_now.set()
        self._power_watcher.stop()

        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None

    # -- external triggers --------------------------------------------

    def request_recovery(self, reason: str = ""):
        """Ask for an immediate recovery pass instead of waiting for the timer."""
        if reason:
            log(f"Recovery requested: {reason}")
        self._recover_now.set()

    def _on_resume(self):
        """Called from the power watcher thread on resume."""
        self._session.note_reconnecting()
        self.request_recovery("system resume")

    # -- poll loop ----------------------------------------------------

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                # Section 12: a monitoring failure retries; it never
                # terminates the application.
                log(f"Connection monitor tick error: {exc}")

            interval = (POLL_INTERVAL_HEALTHY if self._was_connected
                        else POLL_INTERVAL_DEGRADED)

            # Wait on whichever comes first: the timer, a recovery request,
            # or shutdown. This is why recovery feels instant after a wake.
            triggered = self._recover_now.wait(interval)
            if triggered:
                self._recover_now.clear()

    def _tick(self):
        """One pass of the connection lifecycle check."""
        now = time.time()
        gap = now - self._last_tick_wall
        self._last_tick_wall = now

        # Fallback wake detection: far more wall-clock time elapsed than the
        # longest interval we ever sleep for, so the process was suspended.
        if gap > POLL_INTERVAL_HEALTHY + WAKE_GAP_THRESHOLD:
            log(f"Wake inferred from clock gap ({gap:.0f}s elapsed).")
            if not self._power_watcher.available:
                self._session.note_reconnecting()

        # A deliberate logout outranks everything. Track reality but never act
        # on it — this is the guard that keeps the Logout button meaningful.
        if self._session.auto_login_suppressed:
            self._was_connected = False
            return

        # Never race an authentication attempt that is already running.
        if self._session.is_authenticating:
            return

        if is_connected():
            if not self._was_connected:
                log("Internet available.")
            self._was_connected = True
            self._session.note_connected()
            return

        # Internet is gone. Distinguish "was working, now broken" (a lost
        # session worth recovering) from "never worked" (still starting up).
        if self._was_connected:
            log("Internet lost; beginning recovery.")
            self._session.note_session_lost()
        self._was_connected = False

        self._recover()

    # -- recovery -----------------------------------------------------

    def _recover(self):
        """
        Attempt to restore a working connection.

        Order matters: get a Wi-Fi link first, then confirm the portal is
        reachable, and only then spend a login attempt. Authenticating before
        the link is up is what produced v2's spurious "Not on MMMUT network"
        failures right after a wake.
        """
        if not self._wait_for_network_ready():
            self._session.note_network_detecting()
            return

        if not is_cyberoam_network():
            self._session.note_unavailable("Portal not reachable")
            return

        # Re-check internet before authenticating. On the common wake path the
        # portal session is often still valid, and this turns "log in again"
        # into "nothing to do" — Test Group D scenario 1.
        if is_connected():
            self._was_connected = True
            self._session.note_connected()
            return

        success, message = self._session.authenticate(manual=False)
        if success:
            self._was_connected = True
        else:
            log(f"Automatic recovery did not succeed: {message}")

    def _wait_for_network_ready(self) -> bool:
        """
        Poll until a Wi-Fi link exists, using a backoff (FR-12).

        Returns True as soon as the adapter reports an SSID, False if the
        readiness window expires. One connection attempt to the strongest
        campus AP is made if nothing is associated.
        """
        deadline = time.monotonic() + POST_WAKE_READINESS_TIMEOUT
        attempted_connect = False
        step = 0

        while time.monotonic() < deadline and not self._stop_event.is_set():
            ssid = get_current_ssid()
            if ssid:
                return True

            # Not associated with anything: try to join the best campus AP,
            # but only once per readiness window so we do not thrash the
            # adapter with repeated connect commands.
            if not attempted_connect:
                attempted_connect = True
                self._session.note_network_detecting()
                if connect_to_best_mmmut():
                    return True

            delay = READINESS_BACKOFF[min(step, len(READINESS_BACKOFF) - 1)]
            step += 1
            if self._stop_event.wait(delay):
                return False

        return False


def summarise_state(session: SessionManager) -> str:
    """
    Return the short status string for the compact popup.

    Lives here rather than in the popup so the mapping from state to user-
    visible words has exactly one home, and the popup stays presentation-only.
    """
    return session_manager.STATE_LABELS.get(session.state, session.state)
