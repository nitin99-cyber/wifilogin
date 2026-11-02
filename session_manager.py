"""
session_manager.py — Authentication state, recovery, and the logout guard.

WHY A STATE MACHINE
───────────────────
v2 stored connection status implicitly: it lived in whatever line of a long
function happened to be executing, plus the text currently sitting in a Tk
label. That made three bugs structurally possible:

  1. Two login attempts could overlap (boot auto-login still running while
     the user clicks Connect), doubling requests to the portal and racing to
     write the same status.
  2. Nothing could tell the difference between "session dropped" and "the
     user asked to log out", so a monitor that saw no internet would helpfully
     log the user straight back in — making the Logout button useless.
  3. There was no single place to ask "what is happening right now?", so the
     UI had to infer it from strings.

v3 makes state explicit, guards transitions, and lets both the UI and the
connection monitor read one authoritative value.

THE LOGOUT SUPPRESSION RULE (FR-17)
───────────────────────────────────
This is the requirement most likely to be got wrong, so it is enforced in one
place. After a deliberate logout the manager enters USER_LOGGED_OUT and sets
a suppression flag. While that flag is set, automatic recovery is refused —
only an explicit user action clears it. Without this the app would fight its
own user:

    user logs out -> monitor sees no internet -> auto-login -> logged in again

Suppression is intentionally NOT time-based. An expiring timer would mean the
app silently starts logging you back in a few minutes after you asked it not
to, which is exactly the surprising behaviour we are trying to avoid.

THREADING CONTRACT
──────────────────
Every public method is safe to call from any thread. All state lives behind
`_lock`. Authentication runs under a separate non-blocking `_auth_lock` which
implements single-flight: whoever gets there first authenticates, everyone
else is told "already in progress" rather than queueing up a second attempt.

This module never imports tkinter. Status reaches the UI through a callback
that the UI itself is responsible for marshalling onto the Tk thread.
"""

from __future__ import annotations

import threading
from typing import Callable

from credential_manager import load_accounts
from internet import is_connected
from network import is_cyberoam_network
from login import login, logout
from logger import log

# ── States (FR-15) ────────────────────────────────────────────────────

IDLE = "IDLE"
NETWORK_DETECTING = "NETWORK_DETECTING"
NETWORK_CONNECTED = "NETWORK_CONNECTED"
CHECKING_INTERNET = "CHECKING_INTERNET"
PORTAL_CHECK = "PORTAL_CHECK"
AUTHENTICATING = "AUTHENTICATING"
CONNECTED = "CONNECTED"
SESSION_LOST = "SESSION_LOST"
RECONNECTING = "RECONNECTING"
AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
USER_LOGGED_OUT = "USER_LOGGED_OUT"
UNAVAILABLE = "UNAVAILABLE"

#: Short text shown in the compact popup for each state (FR-19).
STATE_LABELS = {
    IDLE: "Starting…",
    NETWORK_DETECTING: "Waiting for network…",
    NETWORK_CONNECTED: "Connecting…",
    CHECKING_INTERNET: "Checking…",
    PORTAL_CHECK: "Connecting…",
    AUTHENTICATING: "Connecting…",
    CONNECTED: "Connected",
    SESSION_LOST: "Reconnecting…",
    RECONNECTING: "Reconnecting…",
    AUTHENTICATION_FAILED: "Authentication required",
    USER_LOGGED_OUT: "Logged out",
    UNAVAILABLE: "No network",
}

#: States in which throughput numbers are meaningful enough to display.
HEALTHY_STATES = {CONNECTED}

# Portal responses that mean "this account is in use elsewhere" rather than
# "these credentials are wrong". Only the former is worth a failover.
_MAX_LOGIN_KEYWORDS = [
    "maximum login limit",
    "max login limit",
    "maximum simultaneous",
    "login limit reached",
    "already logged in",
]

# Responses that mean the credentials themselves are wrong. Retrying these
# just hammers the portal with a request that can never succeed (section 12).
_BAD_CREDENTIAL_KEYWORDS = [
    "invalid username",
    "invalid password",
    "authentication failed",
    "wrong password",
    "user not found",
]


def _matches(message: str, keywords: list[str]) -> bool:
    if not message:
        return False
    lowered = message.lower()
    return any(keyword in lowered for keyword in keywords)


def is_max_login_error(message: str) -> bool:
    """True when the portal refused because the account is in use elsewhere."""
    return _matches(message, _MAX_LOGIN_KEYWORDS)


def is_bad_credentials(message: str) -> bool:
    """True when the portal rejected the credentials themselves."""
    return _matches(message, _BAD_CREDENTIAL_KEYWORDS)


class SessionManager:
    """
    Owns authentication state for the whole application.

    Create exactly one and share it. Two instances would each keep their own
    idea of the current state and their own auth lock, which would defeat the
    single-flight guarantee.
    """

    def __init__(self, on_state_change: Callable[[str, str], None] | None = None):
        """
        Args:
            on_state_change: Called as (state, detail) after every transition.
                Invoked on whichever thread caused the change, so a Tk caller
                must marshal it with `widget.after(0, ...)`.
        """
        self._lock = threading.Lock()

        # Non-blocking single-flight guard around authentication.
        self._auth_lock = threading.Lock()

        self._state = IDLE
        self._detail = ""
        self._suppress_auto_login = False
        self._active_username = ""
        self._on_state_change = on_state_change

    # -- state access -------------------------------------------------

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def detail(self) -> str:
        with self._lock:
            return self._detail

    @property
    def auto_login_suppressed(self) -> bool:
        """True while a deliberate logout is blocking automatic recovery."""
        with self._lock:
            return self._suppress_auto_login

    @property
    def is_authenticating(self) -> bool:
        """True while an authentication attempt holds the single-flight lock."""
        return self._auth_lock.locked()

    def status_text(self) -> str:
        """Return the short label the compact popup should show."""
        with self._lock:
            return STATE_LABELS.get(self._state, self._state)

    def _set_state(self, state: str, detail: str = ""):
        """
        Transition to `state` and notify the listener.

        The callback is deliberately invoked OUTSIDE the lock. Calling it while
        holding `_lock` would mean UI code runs with the lock held, and if that
        code called back into the manager it would deadlock.
        """
        with self._lock:
            if self._state == state and self._detail == detail:
                return
            self._state = state
            self._detail = detail
            callback = self._on_state_change

        log(f"State → {state}" + (f" ({detail})" if detail else ""))

        if callback:
            try:
                callback(state, detail)
            except Exception as exc:
                # A broken listener must not break the state machine.
                log(f"State listener error: {exc}")

    # -- suppression (FR-17) ------------------------------------------

    def suppress_auto_login(self):
        """Block automatic recovery until an explicit user action resumes it."""
        with self._lock:
            self._suppress_auto_login = True

    def resume_auto_login(self):
        """Re-enable automatic recovery after a deliberate user action."""
        with self._lock:
            self._suppress_auto_login = False

    # -- the authentication routine -----------------------------------

    def authenticate(self, manual: bool = False) -> tuple[bool, str]:
        """
        Run the full authentication sequence. Blocking; call from a worker.

        Args:
            manual: True when the user clicked Connect. A manual attempt
                clears logout suppression, because clicking Connect is an
                unambiguous statement of intent. An automatic attempt
                respects suppression and declines.

        Returns:
            (success, message)
        """
        # Single-flight: acquire without blocking so a second caller returns
        # immediately instead of piling up behind the first (FR-18).
        if not self._auth_lock.acquire(blocking=False):
            return False, "Authentication already in progress"

        try:
            if manual:
                self.resume_auto_login()
            elif self.auto_login_suppressed:
                log("Automatic login suppressed by user logout; skipping.")
                return False, "Auto-login suppressed after logout"

            return self._authenticate_locked()
        finally:
            self._auth_lock.release()

    def _authenticate_locked(self) -> tuple[bool, str]:
        """Body of authenticate(); runs with the single-flight lock held."""

        # Step 1 — already online? Cheapest possible check, and it makes the
        # common wake-from-sleep case (session still valid) cost one request.
        self._set_state(CHECKING_INTERNET)
        if is_connected():
            self._set_state(CONNECTED, "Already connected")
            return True, "Already connected"

        # Step 2 — is the captive portal reachable? If not, we are simply not
        # on this campus network and there is nothing to authenticate against.
        self._set_state(PORTAL_CHECK)
        if not is_cyberoam_network():
            self._set_state(UNAVAILABLE, "Portal not reachable")
            return False, "Portal not reachable"

        # Step 3 — credentials.
        accounts = load_accounts()
        if not accounts:
            self._set_state(AUTHENTICATION_FAILED, "No saved credentials")
            return False, "No saved credentials"

        # Step 4 — try each account in order.
        self._set_state(AUTHENTICATING)
        last_message = "All accounts failed"

        for index, account in enumerate(accounts, start=1):
            username = account["username"]
            try:
                status, message = login(username, account["password"])
                # Note the password is never included in any log line.
                log(f"Login attempt {index}/{len(accounts)} "
                    f"as {username}: {status} - {message}")
                last_message = message or last_message

                if status == "LIVE":
                    with self._lock:
                        self._active_username = username
                    self._set_state(CONNECTED, "Login successful")
                    return True, "Login successful"

                if is_bad_credentials(message):
                    # Wrong password will never start working on retry, so
                    # stop rather than looping against the portal.
                    log(f"Account {index} has invalid credentials; not retrying.")
                    continue

                if is_max_login_error(message):
                    log(f"Account {index} at max login limit; trying next.")
                    continue

                log(f"Account {index} failed; trying next.")

            except Exception as exc:
                last_message = str(exc)
                log(f"Login error on account {index} ({username}): {exc}")

        self._set_state(AUTHENTICATION_FAILED, last_message)
        return False, last_message

    # -- logout -------------------------------------------------------

    def logout_all(self) -> tuple[bool, str]:
        """
        Log every saved account out of the portal and suppress auto-login.

        Suppression is set BEFORE the network calls, not after. If it were set
        afterwards, the connection monitor could observe "no internet" during
        the logout request itself and immediately re-authenticate — the exact
        race FR-17 exists to prevent.
        """
        self.suppress_auto_login()

        accounts = load_accounts()
        if not accounts:
            self._set_state(USER_LOGGED_OUT, "No saved credentials")
            return False, "No saved credentials"

        all_ok = True
        for account in accounts:
            username = account["username"]
            try:
                status, message = logout(username)
                log(f"Logout {username}: {status} - {message}")
                if status != "LIVE":
                    all_ok = False
            except Exception as exc:
                log(f"Logout error for {username}: {exc}")
                all_ok = False

        with self._lock:
            self._active_username = ""

        self._set_state(USER_LOGGED_OUT,
                        "Logged out" if all_ok else "Logout sent")
        return all_ok, "Logged out" if all_ok else "Logout sent"

    # -- transitions driven by the connection monitor -----------------

    def note_network_detecting(self):
        """The adapter is not ready yet (post-wake, or Wi-Fi off)."""
        if self.state not in (AUTHENTICATING,):
            self._set_state(NETWORK_DETECTING)

    def note_session_lost(self):
        """
        Internet disappeared while we believed we were connected.

        A deliberate logout is not a lost session, so USER_LOGGED_OUT is left
        untouched — otherwise the popup would misreport the user's own action
        as a failure and invite a reconnect.
        """
        with self._lock:
            if self._state == USER_LOGGED_OUT or self._suppress_auto_login:
                return
        self._set_state(SESSION_LOST)

    def note_reconnecting(self):
        """Recovery has begun after a wake or a reconnect."""
        with self._lock:
            if self._suppress_auto_login:
                return
        self._set_state(RECONNECTING)

    def note_connected(self):
        """Internet confirmed working; nothing to do."""
        self._set_state(CONNECTED)

    def note_unavailable(self, detail: str = ""):
        """No usable network at all."""
        with self._lock:
            if self._state == USER_LOGGED_OUT:
                return
        self._set_state(UNAVAILABLE, detail)
