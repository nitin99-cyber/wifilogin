"""
ui_scale.py — Resolution and DPI independence for every Tk window.

WHY THIS MODULE EXISTS
──────────────────────
Windows shows a desktop app two different coordinate systems:

  * PHYSICAL pixels — real pixels on the panel        (e.g. 2880 x 1800)
  * LOGICAL  pixels — what a DPI-unaware app is told  (e.g. 1920 x 1200 at 150%)

Tk asks Windows for pixels without saying which kind it wants. That creates
two separate failure modes, and v2 of this app hit both:

  1. The process never declared itself DPI aware, so Windows quietly
     bitmap-stretched the whole window. Result: blurry text on every
     high-DPI laptop.

  2. Window sizes were hardcoded in raw pixels (`center_window(root, 380, 680)`,
     `center_window(about_win, 460, 920)`). A 920 px tall dialog does not fit
     on a 768 px laptop screen, and because nothing scrolled, the Close button
     was physically unreachable.

This module fixes both halves:

  * `enable_dpi_awareness()` is called BEFORE the first `Tk()` exists, so
     Windows hands us real pixels and renders text sharply.
  * `dp()` converts density-independent units into device pixels, so a
     "260 dp wide" popup is the same apparent size at 100% and at 200%.
  * `work_area()` reports the desktop rectangle EXCLUDING the taskbar, so
     windows never hide behind it and we never guess "the taskbar is 60px".
  * `ScrollableFrame` guarantees that content taller than the screen is
     still reachable instead of being clipped off the bottom.

USAGE ORDER MATTERS
───────────────────
    import ui_scale
    ui_scale.enable_dpi_awareness()     # must run before Tk() is created
    root = tk.Tk()
    ui_scale.init(root)                 # must run right after Tk() exists
"""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from tkinter import ttk

# ── Win32 constants ───────────────────────────────────────────────────

_SPI_GETWORKAREA = 0x0030

# DPI_AWARENESS_CONTEXT values are opaque handles expressed as negative ints.
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
_PROCESS_PER_MONITOR_DPI_AWARE = 2

# Baseline DPI. 96 DPI == 100% scaling == 1 dp is 1 device pixel.
BASE_DPI = 96.0

# Smallest screen we promise to support (netbooks / 1024x600 projectors).
MIN_SUPPORTED_W = 1024
MIN_SUPPORTED_H = 600


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


# Cached scale factor, populated by init(). 1.0 == 100% Windows scaling.
_scale: float = 1.0
_initialised: bool = False


# ── Step 1: declare DPI awareness (before Tk exists) ──────────────────


def enable_dpi_awareness() -> str:
    """
    Tell Windows this process handles high-DPI itself.

    Must be called before the first tkinter.Tk() is constructed — Windows
    latches a process's awareness mode when its first window is created,
    so calling this later silently does nothing.

    Tries three APIs newest-first, because each one appeared in a different
    Windows release and older machines will not export the newer symbols:

        SetProcessDpiAwarenessContext  Win10 1703+  (per-monitor, rescales live)
        SetProcessDpiAwareness         Win8.1+      (per-monitor, static)
        SetProcessDPIAware             Vista+       (system-wide only)

    Returns the name of whichever call succeeded, or "none" — the return value
    is only used for logging, never for control flow.
    """
    if not sys.platform.startswith("win"):
        return "none"

    # Newest: per-monitor v2. Handles a laptop docked to a 4K monitor where
    # the two displays have different scale factors.
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        ):
            return "SetProcessDpiAwarenessContext"
    except (AttributeError, OSError):
        pass

    # Win8.1 fallback. Returns an HRESULT: 0 == S_OK.
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(
            _PROCESS_PER_MONITOR_DPI_AWARE
        ) == 0:
            return "SetProcessDpiAwareness"
    except (AttributeError, OSError):
        pass

    # Oldest fallback: system DPI only. Still far better than being unaware.
    try:
        if ctypes.windll.user32.SetProcessDPIAware():
            return "SetProcessDPIAware"
    except (AttributeError, OSError):
        pass

    return "none"


# ── Step 2: work out the scale factor (after Tk exists) ───────────────


def _system_dpi(root: tk.Misc | None = None) -> float:
    """
    Return the effective DPI of the primary display.

    Preferred source is GetDpiForSystem() because it reports the value
    Windows is actually using for scaling. Tk's own winfo_fpixels() is the
    fallback for pre-1607 machines.
    """
    try:
        dpi = float(ctypes.windll.user32.GetDpiForSystem())
        if dpi > 0:
            return dpi
    except (AttributeError, OSError):
        pass

    if root is not None:
        try:
            # "1i" == one inch expressed in pixels.
            dpi = float(root.winfo_fpixels("1i"))
            if dpi > 0:
                return dpi
        except tk.TclError:
            pass

    return BASE_DPI


def init(root: tk.Misc) -> float:
    """
    Calibrate this module against the real display and align Tk's own scaling.

    Two separate things get set, and conflating them is the classic Tkinter
    high-DPI bug:

      * `_scale` scales PIXEL geometry (window sizes, padding) via dp().
      * `tk scaling` scales POINT-sized things (fonts) inside Tk itself.

    Tk defines `tk scaling` as "pixels per point", and there are 72 points
    per inch — hence dpi/72, not dpi/96. Fonts declared as
    ("Segoe UI", 10) are in points, so once this is correct they grow on a
    150% display automatically and we never hardcode font pixel sizes.

    Returns the scale factor (1.0 at 100%, 1.5 at 150%).
    """
    global _scale, _initialised

    dpi = _system_dpi(root)
    _scale = dpi / BASE_DPI

    try:
        root.tk.call("tk", "scaling", dpi / 72.0)
    except tk.TclError:
        pass

    _initialised = True
    return _scale


def scale_factor() -> float:
    """Return the cached scale factor (1.0 == 100% Windows scaling)."""
    return _scale


def dp(value: float) -> int:
    """
    Convert density-independent pixels to device pixels.

    dp(260) is 260 px at 100% scaling and 390 px at 150% scaling, so a
    widget sized in dp keeps the same physical size on screen regardless
    of the user's display settings.
    """
    return int(round(value * _scale))


# ── Step 3: honest screen geometry ────────────────────────────────────


def work_area() -> tuple[int, int, int, int]:
    """
    Return the primary monitor's usable rectangle as (left, top, right, bottom).

    "Usable" means the taskbar is already subtracted. This is what lets the
    popup sit flush above the taskbar without the v2 hack of assuming the
    taskbar is exactly 60 px tall — an assumption that broke at 150% scaling
    and for anyone with a vertical or auto-hiding taskbar.

    Falls back to the full screen if the Win32 call is unavailable.
    """
    rect = _RECT()
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            _SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
        )
        if ok and rect.right > rect.left and rect.bottom > rect.top:
            return rect.left, rect.top, rect.right, rect.bottom
    except (AttributeError, OSError):
        pass

    try:
        w = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
        if w > 0 and h > 0:
            return 0, 0, w, h
    except (AttributeError, OSError):
        pass

    return 0, 0, 1366, 768


def work_area_size() -> tuple[int, int]:
    """Return the usable desktop size as (width, height) in device pixels."""
    left, top, right, bottom = work_area()
    return right - left, bottom - top


# ── Step 4: window sizing and placement ───────────────────────────────


def fit_size(want_w_dp: float, want_h_dp: float,
             margin_dp: float = 24) -> tuple[int, int]:
    """
    Convert a desired dp size into device pixels, clamped to the work area.

    This is the single guard that makes "all screen types" work: a window can
    ASK for 460 x 920 dp, but on a 1366x768 laptop it will be handed back
    something that actually fits. Pair it with ScrollableFrame so the content
    that no longer fits stays scrollable rather than being cut off.
    """
    avail_w, avail_h = work_area_size()
    margin = dp(margin_dp)

    w = min(dp(want_w_dp), max(dp(200), avail_w - margin))
    h = min(dp(want_h_dp), max(dp(200), avail_h - margin))
    return w, h


def place_center(window: tk.Tk | tk.Toplevel,
                 want_w_dp: float, want_h_dp: float,
                 margin_dp: float = 24,
                 min_w_dp: float | None = None,
                 min_h_dp: float | None = None) -> tuple[int, int]:
    """
    Size a window in dp and centre it inside the usable desktop area.

    Centring uses the work area rather than the raw screen so a window is
    never pushed underneath the taskbar on the bottom edge.
    """
    w, h = fit_size(want_w_dp, want_h_dp, margin_dp)
    left, top, right, bottom = work_area()

    x = left + max(0, ((right - left) - w) // 2)
    y = top + max(0, ((bottom - top) - h) // 2)

    window.geometry(f"{w}x{h}+{x}+{y}")
    if min_w_dp is not None and min_h_dp is not None:
        window.minsize(min(w, dp(min_w_dp)), min(h, dp(min_h_dp)))
    return w, h


def place_bottom_right(window: tk.Tk | tk.Toplevel,
                       want_w_dp: float, want_h_dp: float,
                       margin_dp: float = 12) -> tuple[int, int]:
    """
    Anchor a window to the bottom-right of the usable desktop area.

    Because work_area() already excludes the taskbar, the window lands just
    above it on a bottom taskbar, just left of it on a right-side taskbar,
    and correctly at any scale factor — no magic offsets.
    """
    w, h = fit_size(want_w_dp, want_h_dp, margin_dp * 2)
    left, top, right, bottom = work_area()
    margin = dp(margin_dp)

    x = max(left, right - w - margin)
    y = max(top, bottom - h - margin)

    window.geometry(f"{w}x{h}+{x}+{y}")
    return w, h


def is_small_screen() -> bool:
    """
    True when the usable area is tight enough that layouts should compact.

    Callers use this to drop optional padding and secondary text rather than
    to switch to an entirely different layout.
    """
    w, h = work_area_size()
    return w < MIN_SUPPORTED_W or h < MIN_SUPPORTED_H + 120


# ── Step 5: never let content become unreachable ──────────────────────


class ScrollableFrame(ttk.Frame):
    """
    A frame whose contents scroll vertically when they exceed the space.

    Pack or grid widgets into `.body`, not into the ScrollableFrame itself.

    The scrollbar auto-hides when everything already fits, so on a large
    monitor this is visually identical to a plain Frame — you only pay for
    it on the small screens that need it. This is what turns the v2 About
    dialog from "Close button off-screen" into "scroll down and click Close".

    Mouse wheel binding uses <Enter>/<Leave> rather than a permanent
    bind_all, so a scrollable frame never swallows wheel events meant for
    another widget.
    """

    def __init__(self, parent: tk.Misc, **kwargs):
        super().__init__(parent, **kwargs)

        # Match the ttk theme background so the canvas is invisible.
        try:
            bg = ttk.Style().lookup("TFrame", "background") or None
        except tk.TclError:
            bg = None

        self._canvas = tk.Canvas(
            self, highlightthickness=0, borderwidth=0,
            **({"background": bg} if bg else {}),
        )
        self._vbar = ttk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview
        )
        self._canvas.configure(yscrollcommand=self._on_scroll_set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        #: Put your widgets in here.
        self.body = ttk.Frame(self._canvas)
        self._body_id = self._canvas.create_window(
            (0, 0), window=self.body, anchor="nw"
        )

        self.body.bind("<Configure>", self._on_body_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Only capture the wheel while the pointer is actually over us.
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)
        self.body.bind("<Enter>", self._bind_wheel)
        self.body.bind("<Leave>", self._unbind_wheel)

        self._vbar_visible = True

    # -- internals ----------------------------------------------------

    def _on_body_configure(self, _event=None):
        """Content changed size: refresh the scrollable region."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._sync_scrollbar()

    def _on_canvas_configure(self, event):
        """Viewport changed size: make the content match its width."""
        self._canvas.itemconfigure(self._body_id, width=event.width)
        self._sync_scrollbar()

    def _on_scroll_set(self, first: str, last: str):
        self._vbar.set(first, last)
        self._sync_scrollbar()

    def _sync_scrollbar(self):
        """Hide the scrollbar when the content already fits."""
        try:
            needed = self.body.winfo_reqheight() > self._canvas.winfo_height()
        except tk.TclError:
            return

        if needed and not self._vbar_visible:
            self._vbar.grid(row=0, column=1, sticky="ns")
            self._vbar_visible = True
        elif not needed and self._vbar_visible:
            self._vbar.grid_remove()
            self._vbar_visible = False

    def _bind_wheel(self, _event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event=None):
        self._canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        """Scroll only when there is something hidden to scroll to."""
        if not self._vbar_visible:
            return
        # On Windows event.delta is a multiple of 120 per notch.
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def scroll_to_top(self):
        """Reset the view — useful after repopulating the content."""
        self._canvas.yview_moveto(0.0)
