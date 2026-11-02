"""
popup.py — The compact, non-intrusive network monitor overlay.

DESIGN BRIEF
────────────
The v2 popup was a 380x175 px window with a title, a version number, a
separator and four full-width buttons. It appeared on every boot and sat on
top of whatever the user was doing. It was informative and slightly annoying,
and users close annoying things — after which they get no status at all.

v3 inverts the priority: show the smallest amount of information that is
genuinely useful, and reveal the rest only when the user asks for it by
moving the mouse there.

    idle       ↓ 42.6 Mbps   ↑ 3.2 Mbps   −      (265 x 40 dp, 78% opaque)
    hovered    adds quality · band · latency · signal, fully opaque
    minimised  a 16 dp dot in the corner; monitoring continues

THIS FILE IS PRESENTATION ONLY
──────────────────────────────
It reads state and renders it. It never logs in, never scans Wi-Fi, and never
decides policy. Every action is delegated to a callback supplied by app.py.
That separation is why the popup can be closed, hidden or rebuilt without any
risk of interrupting authentication — in v2 the popup owned the connect flow,
so destroying the window could tear down the login that was in progress.

WHY IT POLLS INSTEAD OF BEING CALLED
────────────────────────────────────
Tk is not thread-safe. The monitor and session threads therefore never touch
these widgets; instead this window polls their published state on a Tk timer
via `after()`, which by definition runs on the Tk main thread. This trades a
negligible amount of idle work for the complete elimination of a class of
intermittent, unreproducible crashes.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import session_manager
import ui_scale
from ui_scale import dp

# ── Geometry, in density-independent units (FR-05) ────────────────────

COMPACT_W = 265
COMPACT_H = 40
EXPANDED_W = 300
EXPANDED_H = 98
DOT_SIZE = 16
EDGE_MARGIN = 12

# ── Appearance (FR-07) ────────────────────────────────────────────────

IDLE_OPACITY = 0.78
HOVER_OPACITY = 1.0

BG = "#111827"          # slate-900: a dark pill reads as an overlay, not a dialog
BG_HOVER = "#1f2937"
FG = "#f8fafc"
FG_MUTED = "#94a3b8"
DOWN_COLOR = "#38bdf8"  # sky-400
UP_COLOR = "#a78bfa"    # violet-400

#: Status colours per state. Anything unlisted falls back to FG_MUTED.
STATE_COLORS = {
    session_manager.CONNECTED: "#4ade80",
    session_manager.AUTHENTICATING: "#60a5fa",
    session_manager.PORTAL_CHECK: "#60a5fa",
    session_manager.CHECKING_INTERNET: "#60a5fa",
    session_manager.RECONNECTING: "#fbbf24",
    session_manager.SESSION_LOST: "#fbbf24",
    session_manager.NETWORK_DETECTING: "#fbbf24",
    session_manager.AUTHENTICATION_FAILED: "#f87171",
    session_manager.UNAVAILABLE: "#f87171",
    session_manager.USER_LOGGED_OUT: "#94a3b8",
}

#: UI refresh period. Faster than the 1 s sampling interval would be wasted
#: work; slower would make the readout feel laggy.
REFRESH_MS = 1000


class MonitorPopup:
    """
    The floating status overlay.

    Args:
        root: An existing Tk root. The popup does not create one, so app.py
            keeps ownership of the Tk lifecycle.
        session: SessionManager to read status from.
        monitor: NetworkMonitor to read throughput from.
        on_connect / on_logout / on_settings / on_exit: user-action callbacks.
            Each is expected to return immediately — anything slow must be
            dispatched to a worker thread by the caller, or the UI will freeze.
    """

    def __init__(self, root: tk.Tk, session, monitor,
                 on_connect: Callable[[], None] | None = None,
                 on_logout: Callable[[], None] | None = None,
                 on_settings: Callable[[], None] | None = None,
                 on_exit: Callable[[], None] | None = None):
        self.root = root
        self.session = session
        self.monitor = monitor
        self.on_connect = on_connect
        self.on_logout = on_logout
        self.on_settings = on_settings
        self.on_exit = on_exit

        self._expanded = False
        self._minimised = False
        self._after_id: str | None = None
        self._drag_origin: tuple[int, int] | None = None

        self._build()
        self._apply_compact_geometry()
        self._schedule_refresh()

    # ── construction ─────────────────────────────────────────────────

    def _build(self):
        root = self.root
        root.title("Wi-Fi Monitor")

        # Borderless: a 40 dp tall pill with a Windows title bar would be
        # mostly title bar. Dragging is re-implemented below instead.
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=BG)
        self._set_opacity(IDLE_OPACITY)

        # -- outer container ------------------------------------------
        self.container = tk.Frame(root, bg=BG, padx=dp(10), pady=dp(6))
        self.container.pack(fill="both", expand=True)

        # -- top row: the always-visible line -------------------------
        self.top_row = tk.Frame(self.container, bg=BG)
        self.top_row.pack(fill="x")

        self.down_label = tk.Label(
            self.top_row, text="↓ —", font=("Segoe UI", 9, "bold"),
            bg=BG, fg=DOWN_COLOR, anchor="w",
        )
        self.down_label.pack(side="left")

        self.up_label = tk.Label(
            self.top_row, text="↑ —", font=("Segoe UI", 9, "bold"),
            bg=BG, fg=UP_COLOR, anchor="w",
        )
        self.up_label.pack(side="left", padx=(dp(12), 0))

        # The minimise affordance (FR-09). A label rather than a Button so it
        # blends into the pill instead of looking like a dialog control.
        self.minimise_btn = tk.Label(
            self.top_row, text="−", font=("Segoe UI", 11, "bold"),
            bg=BG, fg=FG_MUTED, cursor="hand2", padx=dp(4),
        )
        self.minimise_btn.pack(side="right")
        self.minimise_btn.bind("<Button-1>", lambda e: self.minimise())
        self.minimise_btn.bind(
            "<Enter>", lambda e: self.minimise_btn.config(fg=FG))
        self.minimise_btn.bind(
            "<Leave>", lambda e: self.minimise_btn.config(fg=FG_MUTED))

        # Status text shares the top row; it replaces the speeds whenever the
        # connection is not healthy, because "Reconnecting…" matters more than
        # a throughput reading of zero.
        self.status_label = tk.Label(
            self.top_row, text="Starting…", font=("Segoe UI", 9),
            bg=BG, fg=FG_MUTED, anchor="w",
        )

        # -- detail rows: revealed on hover (FR-08) -------------------
        self.detail = tk.Frame(self.container, bg=BG)

        self.quality_label = tk.Label(
            self.detail, text="", font=("Segoe UI", 8),
            bg=BG, fg=FG, anchor="w",
        )
        self.quality_label.pack(fill="x", pady=(dp(6), 0))

        self.link_label = tk.Label(
            self.detail, text="", font=("Segoe UI", 8),
            bg=BG, fg=FG_MUTED, anchor="w",
        )
        self.link_label.pack(fill="x")

        self.hint_label = tk.Label(
            self.detail, text="Right-click for actions",
            font=("Segoe UI", 7), bg=BG, fg=FG_MUTED, anchor="w",
        )
        self.hint_label.pack(fill="x", pady=(dp(4), 0))

        # -- the minimised dot ----------------------------------------
        self.dot = tk.Frame(root, bg=DOWN_COLOR, cursor="hand2")
        self.dot.bind("<Button-1>", lambda e: self.restore())

        # -- interaction ---------------------------------------------
        self._build_context_menu()
        self._bind_hover()
        self._bind_drag()

    def _build_context_menu(self):
        """
        Right-click menu carrying every action the compact bar has no room for.

        This is how FR-18 (manual Connect) survives a UI that is only 40 dp
        tall: the actions still exist, they are just one click deeper.
        """
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Connect now", command=self._fire_connect)
        self.menu.add_command(label="Log out", command=self._fire_logout)
        self.menu.add_separator()
        self.menu.add_command(label="Settings…", command=self._fire_settings)
        self.menu.add_command(label="Hide monitor", command=self.minimise)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self._fire_exit)

        for widget in (self.container, self.top_row, self.down_label,
                       self.up_label, self.status_label, self.detail,
                       self.quality_label, self.link_label, self.hint_label):
            widget.bind("<Button-3>", self._show_menu)

    def _show_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _bind_hover(self):
        """
        Expand on hover, contract on leave.

        Enter/Leave fire for every child widget, so moving between the two
        speed labels would otherwise look like leaving the window. `_on_leave`
        therefore verifies against the real pointer position before contracting.
        """
        targets = (self.container, self.top_row, self.down_label,
                   self.up_label, self.status_label, self.minimise_btn,
                   self.detail, self.quality_label, self.link_label,
                   self.hint_label)
        for widget in targets:
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")

    def _bind_drag(self):
        """Let the user drag the pill, since it has no title bar to grab."""
        for widget in (self.container, self.top_row, self.down_label,
                       self.up_label, self.status_label):
            widget.bind("<Button-1>", self._start_drag, add="+")
            widget.bind("<B1-Motion>", self._do_drag, add="+")
            widget.bind("<ButtonRelease-1>", self._end_drag, add="+")

    # ── geometry ─────────────────────────────────────────────────────

    def _apply_compact_geometry(self):
        """
        Place the pill at the bottom-right of the usable desktop.

        `place_bottom_right` derives the position from the Win32 work area, so
        it clears the taskbar wherever the taskbar happens to be and at
        whatever display scaling is in use. v2 hardcoded a 60 px offset, which
        put the popup partly under the taskbar at 150% scaling.
        """
        ui_scale.place_bottom_right(self.root, COMPACT_W, COMPACT_H,
                                   EDGE_MARGIN)

    def _resize_only(self, w_dp: float, h_dp: float):
        """
        Change size while keeping the bottom-right corner anchored.

        Growing downward would push the expanded panel behind the taskbar, and
        growing rightward would push it off-screen, so the window grows up and
        to the left instead.
        """
        self.root.update_idletasks()
        w, h = ui_scale.fit_size(w_dp, h_dp, EDGE_MARGIN * 2)

        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        current_w = self.root.winfo_width()
        current_h = self.root.winfo_height()

        right = current_x + current_w
        bottom = current_y + current_h

        left, top, wa_right, wa_bottom = ui_scale.work_area()
        x = max(left, min(right - w, wa_right - w))
        y = max(top, min(bottom - h, wa_bottom - h))

        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _set_opacity(self, value: float):
        try:
            self.root.attributes("-alpha", value)
        except tk.TclError:
            pass  # Compositing unavailable; opaque is an acceptable fallback.

    # ── hover behaviour ──────────────────────────────────────────────

    def _pointer_inside(self) -> bool:
        """True when the mouse is genuinely within the window rectangle."""
        try:
            px, py = self.root.winfo_pointerxy()
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            w, h = self.root.winfo_width(), self.root.winfo_height()
        except tk.TclError:
            return False
        return x <= px < x + w and y <= py < y + h

    def _on_enter(self, _event=None):
        if self._minimised:
            return
        self._set_opacity(HOVER_OPACITY)
        self._set_bg(BG_HOVER)
        if not self._expanded:
            self._expanded = True
            self.detail.pack(fill="x")
            self._resize_only(EXPANDED_W, EXPANDED_H)
            self._refresh()

    def _on_leave(self, _event=None):
        if self._minimised:
            return
        # Deferred so the check happens after the pointer has actually settled
        # on its new widget, otherwise crossing a child border looks like exit.
        self.root.after(60, self._maybe_contract)

    def _maybe_contract(self):
        if self._minimised or self._pointer_inside():
            return
        self._set_opacity(IDLE_OPACITY)
        self._set_bg(BG)
        if self._expanded:
            self._expanded = False
            self.detail.pack_forget()
            self._resize_only(COMPACT_W, COMPACT_H)

    def _set_bg(self, color: str):
        """Recolour the pill and every child that shares its background."""
        for widget in (self.root, self.container, self.top_row, self.detail,
                       self.down_label, self.up_label, self.status_label,
                       self.minimise_btn, self.quality_label,
                       self.link_label, self.hint_label):
            try:
                widget.configure(bg=color)
            except tk.TclError:
                pass

    # ── dragging ─────────────────────────────────────────────────────

    def _start_drag(self, event):
        self._drag_origin = (event.x_root - self.root.winfo_x(),
                             event.y_root - self.root.winfo_y())

    def _do_drag(self, event):
        if not self._drag_origin or self._minimised:
            return
        offset_x, offset_y = self._drag_origin
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def _end_drag(self, _event=None):
        self._drag_origin = None

    # ── minimise / restore (FR-09) ───────────────────────────────────

    def minimise(self):
        """
        Shrink to a corner dot.

        Critically this touches nothing but widgets: the network monitor, the
        connection monitor and authentication all keep running. FR-09 treats
        monitoring and UI visibility as independent concerns, because a user
        hiding a status bar is not asking to disable auto-login.
        """
        if self._minimised:
            return
        self._minimised = True
        self._expanded = False
        self.container.pack_forget()
        self.detail.pack_forget()
        self.dot.pack(fill="both", expand=True)
        self._set_opacity(IDLE_OPACITY)
        ui_scale.place_bottom_right(self.root, DOT_SIZE, DOT_SIZE, EDGE_MARGIN)

    def restore(self):
        """Return from the dot to the compact pill."""
        if not self._minimised:
            return
        self._minimised = False
        self.dot.pack_forget()
        self.container.pack(fill="both", expand=True)
        self._set_bg(BG)
        self._apply_compact_geometry()
        self._refresh()

    # ── action callbacks ─────────────────────────────────────────────

    def _fire(self, callback):
        if callback:
            try:
                callback()
            except Exception:
                pass

    def _fire_connect(self):
        self._fire(self.on_connect)

    def _fire_logout(self):
        self._fire(self.on_logout)

    def _fire_settings(self):
        self._fire(self.on_settings)

    def _fire_exit(self):
        self._fire(self.on_exit)

    # ── refresh loop ─────────────────────────────────────────────────

    def _schedule_refresh(self):
        self._refresh()
        self._after_id = self.root.after(REFRESH_MS, self._schedule_refresh)

    def stop_refresh(self):
        """Cancel the timer — call before destroying the window."""
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _refresh(self):
        """
        Pull current state and repaint. Runs on the Tk main thread.

        Wrapped defensively: this fires every second for the entire session,
        so an exception here would otherwise become a repeating error and
        break the timer chain.
        """
        if self._minimised:
            self._refresh_dot()
            return

        try:
            state = self.session.state
            snapshot = self.monitor.snapshot()
        except Exception:
            return

        healthy = state in session_manager.HEALTHY_STATES

        if healthy and snapshot["available"]:
            # Normal case: show the numbers, hide the words.
            self.status_label.pack_forget()
            self.down_label.pack_configure(side="left")
            self.down_label.config(text=f"↓ {snapshot['down_text']}")
            self.up_label.config(text=f"↑ {snapshot['up_text']}")
            self.down_label.pack(side="left")
            self.up_label.pack(side="left", padx=(dp(12), 0))
        else:
            # Something needs saying: replace speeds with the status (FR-19).
            self.down_label.pack_forget()
            self.up_label.pack_forget()
            self.status_label.config(
                text=self.session.status_text(),
                fg=STATE_COLORS.get(state, FG_MUTED),
            )
            self.status_label.pack(side="left")

        if self._expanded:
            self._refresh_detail(snapshot, state)

    def _refresh_detail(self, snapshot: dict, state: str):
        """Populate the hover panel."""
        parts = [snapshot["quality"]]
        if snapshot["band"]:
            parts.append(snapshot["band"])
        parts.append(snapshot["latency_text"])
        self.quality_label.config(text="  ·  ".join(parts))

        bits = []
        if snapshot["signal"]:
            bits.append(f"Signal {snapshot['signal']}%")
        if snapshot["link_mbps"]:
            bits.append(f"Link {snapshot['link_mbps']} Mbps")
        if snapshot["ssid"]:
            bits.append(snapshot["ssid"])
        if not bits:
            bits.append(session_manager.STATE_LABELS.get(state, state))
        self.link_label.config(text="   ".join(bits))

    def _refresh_dot(self):
        """Recolour the minimised dot to reflect health at a glance."""
        try:
            state = self.session.state
        except Exception:
            return
        self.dot.configure(bg=STATE_COLORS.get(state, FG_MUTED))


def create(root: tk.Tk, session, monitor, **callbacks) -> MonitorPopup:
    """Convenience constructor so app.py does not import the class directly."""
    return MonitorPopup(root, session, monitor, **callbacks)
