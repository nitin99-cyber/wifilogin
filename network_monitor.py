"""
network_monitor.py — Real-time throughput, link quality and latency.

WHAT THIS MEASURES (AND WHAT IT DOES NOT)
─────────────────────────────────────────
This module reports how much traffic is *currently flowing through your own
network adapter*. That is deliberately NOT the same thing as a speed test:

  * A speed test asks "how fast COULD this link go?" by downloading a large
    payload. It costs bandwidth and money, and on a shared campus network it
    is antisocial to run it on a loop.

  * This module asks "how fast IS data moving right now?" by reading the
    counters Windows already maintains for the adapter. It costs one cheap
    syscall per second and generates zero network traffic.

So an idle machine correctly reads ~0 Mbps. That is not a bug — nothing is
being transferred. Never present these numbers as the campus link capacity.

HOW THE COUNTERS ARE READ
─────────────────────────
Windows exposes per-interface byte counters through the IP Helper API. We
call `GetIfTable` from iphlpapi.dll with ctypes, which avoids adding a
third-party dependency such as psutil to a project whose whole selling point
is that it is a small, fast, single .exe.

Throughput is then a first derivative:

    bytes_per_second = (octets_now - octets_before) / seconds_elapsed
    bits_per_second  = bytes_per_second * 8

THE 32-BIT COUNTER WRAP PROBLEM
───────────────────────────────
`MIB_IFROW.dwInOctets` is a 32-bit DWORD, so it overflows back to zero every
4 GiB. On a 100 Mbit link that is roughly every six minutes, so this is a
routine event, not an edge case. A naive subtraction would produce a large
negative delta and render a nonsense spike.

We detect it by noticing that the counter went *down*, and reconstruct the
real delta as `(2**32 - previous) + current`. This is correct as long as no
more than one wrap happened between two samples, which at a one-second
sampling interval would require sustained throughput above ~34 Gbps.
"""

from __future__ import annotations

import ctypes
import re
import socket
import subprocess
import threading
import time

# ── Win32 / MIB-II constants ──────────────────────────────────────────

_ERROR_INSUFFICIENT_BUFFER = 122
_NO_ERROR = 0

_MAX_INTERFACE_NAME_LEN = 256
_MAXLEN_PHYSADDR = 8
_MAXLEN_IFDESCR = 256

# Interface types from the IANA ifType registry, as used by MIB_IFROW.dwType.
IF_TYPE_ETHERNET = 6
IF_TYPE_SOFTWARE_LOOPBACK = 24
IF_TYPE_IEEE80211 = 71          # Wi-Fi
IF_TYPE_TUNNEL = 131

# Interface types that never represent a real physical uplink.
_EXCLUDED_TYPES = {IF_TYPE_SOFTWARE_LOOPBACK, IF_TYPE_TUNNEL}

_COUNTER_MODULO = 2 ** 32       # dwInOctets / dwOutOctets are DWORDs.

# ── Sampling / smoothing configuration ────────────────────────────────

SAMPLE_INTERVAL = 1.0           # Seconds between counter reads (FR-02).
EMA_ALPHA = 0.4                 # Smoothing weight for the newest sample.
LATENCY_EVERY_N_SAMPLES = 5     # Latency is slower to measure; do it rarely.

# Latency probe target. Defaults to the campus portal because it is on the
# local network: the probe therefore measures Wi-Fi/LAN health and consumes
# no internet bandwidth at all.
LATENCY_HOST = "172.16.1.3"
LATENCY_PORT = 8090
LATENCY_TIMEOUT = 1.0


class _MIB_IFROW(ctypes.Structure):
    """
    Mirror of the Win32 MIB_IFROW struct from ifmib.h.

    Field order and array lengths must match the C definition exactly —
    ctypes lays the struct out by these declarations, and a single wrong
    length would silently misalign every counter that follows it.
    """
    _fields_ = [
        ("wszName", ctypes.c_wchar * _MAX_INTERFACE_NAME_LEN),
        ("dwIndex", ctypes.c_ulong),
        ("dwType", ctypes.c_ulong),
        ("dwMtu", ctypes.c_ulong),
        ("dwSpeed", ctypes.c_ulong),
        ("dwPhysAddrLen", ctypes.c_ulong),
        ("bPhysAddr", ctypes.c_ubyte * _MAXLEN_PHYSADDR),
        ("dwAdminStatus", ctypes.c_ulong),
        ("dwOperStatus", ctypes.c_ulong),
        ("dwLastChange", ctypes.c_ulong),
        ("dwInOctets", ctypes.c_ulong),
        ("dwInUcastPkts", ctypes.c_ulong),
        ("dwInNUcastPkts", ctypes.c_ulong),
        ("dwInDiscards", ctypes.c_ulong),
        ("dwInErrors", ctypes.c_ulong),
        ("dwInUnknownProtos", ctypes.c_ulong),
        ("dwOutOctets", ctypes.c_ulong),
        ("dwOutUcastPkts", ctypes.c_ulong),
        ("dwOutNUcastPkts", ctypes.c_ulong),
        ("dwOutDiscards", ctypes.c_ulong),
        ("dwOutErrors", ctypes.c_ulong),
        ("dwOutQLen", ctypes.c_ulong),
        ("dwDescrLen", ctypes.c_ulong),
        ("bDescr", ctypes.c_ubyte * _MAXLEN_IFDESCR),
    ]


def _read_interface_rows() -> list[dict]:
    """
    Return one dict per network interface, or [] if the API is unavailable.

    GetIfTable uses the standard two-call Win32 pattern: ask with a buffer
    that is too small to learn the required size, then ask again for real.
    The table is variable length, so the buffer is allocated at runtime.
    """
    try:
        iphlpapi = ctypes.windll.iphlpapi
    except (AttributeError, OSError):
        return []

    size = ctypes.c_ulong(0)

    # First call: deliberately undersized so Windows reports the real size.
    ret = iphlpapi.GetIfTable(None, ctypes.byref(size), False)
    if ret != _ERROR_INSUFFICIENT_BUFFER or size.value == 0:
        return []

    buffer = ctypes.create_string_buffer(size.value)
    ret = iphlpapi.GetIfTable(buffer, ctypes.byref(size), False)
    if ret != _NO_ERROR:
        return []

    # Layout is: DWORD dwNumEntries, followed by dwNumEntries MIB_IFROWs.
    num_entries = ctypes.cast(
        buffer, ctypes.POINTER(ctypes.c_ulong)
    ).contents.value

    row_size = ctypes.sizeof(_MIB_IFROW)
    rows: list[dict] = []

    for i in range(num_entries):
        offset = ctypes.sizeof(ctypes.c_ulong) + i * row_size
        if offset + row_size > size.value:
            break  # Defensive: never read past the buffer we own.

        row = _MIB_IFROW.from_buffer_copy(buffer, offset)

        # bDescr is a fixed-size byte array padded with NULs.
        descr_len = min(row.dwDescrLen, _MAXLEN_IFDESCR)
        description = bytes(row.bDescr[:descr_len]).split(b"\x00")[0]

        rows.append({
            "index": int(row.dwIndex),
            "type": int(row.dwType),
            "speed_bps": int(row.dwSpeed),
            "oper_status": int(row.dwOperStatus),
            "in_octets": int(row.dwInOctets),
            "out_octets": int(row.dwOutOctets),
            "description": description.decode("latin-1", errors="replace"),
        })

    return rows


def _pick_active_interface(rows: list[dict]) -> dict | None:
    """
    Choose which adapter to report on.

    Selection deliberately ignores `dwOperStatus`. That field is documented as
    an INTERNAL_IF_OPER_STATUS for GetIfTable but real drivers report it
    inconsistently, so relying on it caused adapters to be wrongly skipped.
    Cumulative traffic is a far more reliable signal of "this is the adapter
    actually carrying the user's data".

    Preference order:
      1. Wi-Fi adapters (type 71), busiest first — this app is about Wi-Fi.
      2. Ethernet adapters (type 6), busiest first — docked users still get
         a working monitor.
    Loopback and tunnel adapters are excluded so VPN and localhost traffic
    never masquerade as campus throughput.
    """
    candidates = [r for r in rows if r["type"] not in _EXCLUDED_TYPES]
    if not candidates:
        return None

    def busiest(subset: list[dict]) -> dict:
        return max(subset, key=lambda r: r["in_octets"] + r["out_octets"])

    wireless = [r for r in candidates if r["type"] == IF_TYPE_IEEE80211]
    if wireless:
        return busiest(wireless)

    wired = [r for r in candidates if r["type"] == IF_TYPE_ETHERNET]
    if wired:
        return busiest(wired)

    return busiest(candidates)


def _counter_delta(previous: int, current: int) -> int:
    """
    Return bytes transferred between two reads of a 32-bit octet counter.

    A counter that appears to have decreased has wrapped past 2**32 rather
    than actually gone backwards, so the delta is reconstructed across the
    boundary. See the module docstring for why this happens every few
    minutes on a fast link.
    """
    if current >= previous:
        return current - previous
    return (_COUNTER_MODULO - previous) + current


# ── Formatting ────────────────────────────────────────────────────────


def format_rate(bits_per_second: float) -> str:
    """
    Render a bit rate with a human-friendly unit.

    Chooses the unit by magnitude and keeps one decimal place below
    1000 Mbps, because "42.6 Mbps" reads better in a 40 px tall popup than
    "44668026 bps".
    """
    bps = max(0.0, float(bits_per_second))

    if bps < 1_000:
        return f"{bps:.0f} bps"
    if bps < 1_000_000:
        return f"{bps / 1_000:.1f} Kbps"
    if bps < 1_000_000_000:
        return f"{bps / 1_000_000:.1f} Mbps"
    return f"{bps / 1_000_000_000:.2f} Gbps"


# ── Wi-Fi link details ────────────────────────────────────────────────


def _netsh(*args: str) -> str:
    """
    Run a netsh command and return stdout, swallowing every failure.

    CREATE_NO_WINDOW matters here: without it, every poll would flash a
    console window on screen, which for a once-per-second monitor would be
    unusable.
    """
    try:
        result = subprocess.run(
            ["netsh", *args],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.stdout or ""
    except Exception:
        return ""


def _band_from_channel(channel: int) -> str:
    """
    Map a Wi-Fi channel number to its frequency band.

    Channel numbering is band-relative, so the number alone identifies the
    band for 2.4 and 5 GHz. 6 GHz reuses low channel numbers, so anything
    outside the known 2.4/5 GHz ranges is reported as 6 GHz.
    """
    if channel <= 0:
        return ""
    if channel <= 14:
        return "2.4 GHz"
    if 32 <= channel <= 177:
        return "5 GHz"
    return "6 GHz"


def read_wifi_link() -> dict:
    """
    Return current Wi-Fi link details parsed from `netsh wlan show interfaces`.

    Keys: ssid, signal (0-100), radio ("802.11ac"), band ("5 GHz"),
    rx_mbps, tx_mbps. Missing values come back as "" or 0 rather than None
    so the UI can format them without special-casing.
    """
    output = _netsh("wlan", "show", "interfaces")
    info = {
        "ssid": "", "signal": 0, "radio": "",
        "band": "", "rx_mbps": 0, "tx_mbps": 0,
    }
    if not output:
        return info

    channel = 0
    for line in output.splitlines():
        # Match "SSID" but not "BSSID": require the key to start the field.
        m = re.match(r"^\s+SSID\s*:\s*(.+)$", line)
        if m:
            info["ssid"] = m.group(1).strip()
            continue

        m = re.match(r"^\s+Signal\s*:\s*(\d+)%", line)
        if m:
            info["signal"] = int(m.group(1))
            continue

        m = re.match(r"^\s+Radio type\s*:\s*(.+)$", line)
        if m:
            info["radio"] = m.group(1).strip()
            continue

        m = re.match(r"^\s+Channel\s*:\s*(\d+)", line)
        if m:
            channel = int(m.group(1))
            continue

        m = re.match(r"^\s+Receive rate \(Mbps\)\s*:\s*([\d.]+)", line)
        if m:
            info["rx_mbps"] = int(float(m.group(1)))
            continue

        m = re.match(r"^\s+Transmit rate \(Mbps\)\s*:\s*([\d.]+)", line)
        if m:
            info["tx_mbps"] = int(float(m.group(1)))
            continue

    info["band"] = _band_from_channel(channel)
    return info


# ── Latency ───────────────────────────────────────────────────────────


def measure_latency_ms(host: str = LATENCY_HOST, port: int = LATENCY_PORT,
                       timeout: float = LATENCY_TIMEOUT) -> float | None:
    """
    Return TCP handshake latency in milliseconds, or None if unreachable.

    A TCP connect is used instead of ICMP ping on purpose: raw sockets for
    ICMP need administrator rights on Windows, and this app's design promise
    is that it never requires elevation. The three-way handshake is one
    round trip, which is exactly the quantity we want to report.
    """
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return (time.perf_counter() - start) * 1000.0
    except OSError:
        return None


# ── Quality classification ────────────────────────────────────────────

QUALITY_EXCELLENT = "Excellent"
QUALITY_GOOD = "Good"
QUALITY_FAIR = "Fair"
QUALITY_POOR = "Poor"
QUALITY_UNAVAILABLE = "Unavailable"


def classify_quality(signal: int, latency_ms: float | None,
                     link_mbps: int) -> str:
    """
    Combine signal strength, latency and negotiated link rate into one label.

    This describes the *health of the wireless link*, not the speed of the
    campus internet connection — a laptop sitting next to the access point
    can score Excellent while the upstream link is congested. The UI must
    never imply otherwise.

    Each input contributes a 0-3 score and the average decides the label, so
    one missing or noisy input cannot single-handedly flip the verdict.
    """
    if signal <= 0 and latency_ms is None and link_mbps <= 0:
        return QUALITY_UNAVAILABLE

    scores: list[int] = []

    if signal > 0:
        if signal >= 75:
            scores.append(3)
        elif signal >= 55:
            scores.append(2)
        elif signal >= 35:
            scores.append(1)
        else:
            scores.append(0)

    if latency_ms is not None:
        if latency_ms <= 20:
            scores.append(3)
        elif latency_ms <= 60:
            scores.append(2)
        elif latency_ms <= 150:
            scores.append(1)
        else:
            scores.append(0)

    if link_mbps > 0:
        if link_mbps >= 200:
            scores.append(3)
        elif link_mbps >= 75:
            scores.append(2)
        elif link_mbps >= 20:
            scores.append(1)
        else:
            scores.append(0)

    if not scores:
        return QUALITY_UNAVAILABLE

    average = sum(scores) / len(scores)
    if average >= 2.5:
        return QUALITY_EXCELLENT
    if average >= 1.75:
        return QUALITY_GOOD
    if average >= 0.9:
        return QUALITY_FAIR
    return QUALITY_POOR


# ── The monitor ───────────────────────────────────────────────────────


class NetworkMonitor:
    """
    Samples throughput on a daemon thread and publishes a snapshot dict.

    THREADING CONTRACT
    ──────────────────
    `start()` spawns one daemon thread. That thread only ever touches this
    object's own state behind `_lock`; it never touches Tk. The UI calls
    `snapshot()` from the Tk main thread on a timer.

    This "worker writes, UI polls" arrangement is used instead of having the
    worker call into the widgets because Tk is not thread-safe: touching a
    widget from a non-Tk thread produces intermittent crashes that are
    almost impossible to reproduce. Polling shared state removes the
    possibility entirely.

    A daemon thread is used so a stuck sample can never prevent the process
    from exiting when the user closes the app.
    """

    def __init__(self, interval: float = SAMPLE_INTERVAL):
        self.interval = interval

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Previous counter read, for the derivative.
        self._prev_in = 0
        self._prev_out = 0
        self._prev_time = 0.0
        self._prev_index: int | None = None

        # Smoothed rates in bits per second.
        self._down_bps = 0.0
        self._up_bps = 0.0

        self._sample_count = 0
        self._latency_ms: float | None = None
        self._link: dict = {
            "ssid": "", "signal": 0, "radio": "",
            "band": "", "rx_mbps": 0, "tx_mbps": 0,
        }
        self._available = False
        self._consecutive_errors = 0

    # -- lifecycle ----------------------------------------------------

    def start(self):
        """Begin sampling. Safe to call more than once."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="network-monitor", daemon=True
        )
        self._thread.start()

    def stop(self):
        """
        Stop sampling and wait briefly for the thread to notice.

        Note this is separate from hiding the popup: minimising the UI must
        NOT call stop(), because FR-09 requires monitoring to continue while
        the window is hidden.
        """
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=self.interval + 0.5)
        self._thread = None

    # -- sampling loop ------------------------------------------------

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._sample_once()
                self._consecutive_errors = 0
            except Exception:
                # A transient measurement failure must never kill the thread
                # or the app (FR-02, section 12). Degrade to "no data" and
                # try again on the next tick.
                self._consecutive_errors += 1
                with self._lock:
                    self._available = False
                    if self._consecutive_errors >= 3:
                        self._down_bps = 0.0
                        self._up_bps = 0.0

            # Event-based sleep so stop() is honoured immediately instead of
            # after a full interval.
            self._stop_event.wait(self.interval)

    def _sample_once(self):
        rows = _read_interface_rows()
        interface = _pick_active_interface(rows)
        now = time.monotonic()

        if interface is None:
            with self._lock:
                self._available = False
                self._down_bps = 0.0
                self._up_bps = 0.0
            return

        in_octets = interface["in_octets"]
        out_octets = interface["out_octets"]
        index = interface["index"]

        # First sample, or the adapter changed (docked, VPN up, Wi-Fi
        # toggled). Establish a baseline instead of reporting a fake spike
        # built from another adapter's lifetime totals.
        if self._prev_index != index or self._prev_time == 0.0:
            self._prev_index = index
            self._prev_in = in_octets
            self._prev_out = out_octets
            self._prev_time = now
            with self._lock:
                self._available = True
                self._down_bps = 0.0
                self._up_bps = 0.0
            return

        elapsed = now - self._prev_time
        if elapsed <= 0:
            return

        down_bytes = _counter_delta(self._prev_in, in_octets)
        up_bytes = _counter_delta(self._prev_out, out_octets)

        self._prev_in = in_octets
        self._prev_out = out_octets
        self._prev_time = now

        raw_down = (down_bytes / elapsed) * 8.0
        raw_up = (up_bytes / elapsed) * 8.0

        # Latency and link details are measured on a slower cadence because
        # both are expensive: a TCP handshake can take up to a second and
        # `netsh` spawns a process. They are computed into locals FIRST and
        # published under the lock afterwards — holding the lock across a
        # blocking call would stall every snapshot() the UI makes.
        self._sample_count += 1
        new_latency = None
        new_link = None
        if self._sample_count % LATENCY_EVERY_N_SAMPLES == 1:
            new_latency = measure_latency_ms()
            new_link = read_wifi_link()

        with self._lock:
            if new_link is not None:
                self._latency_ms = new_latency
                self._link = new_link

            # Exponential moving average: new = a*sample + (1-a)*old.
            # Without this the readout jitters every tick and is unreadable;
            # with alpha too low it lags behind reality. 0.4 keeps it
            # responsive within ~3 samples while removing single-tick noise.
            self._down_bps = EMA_ALPHA * raw_down + (1 - EMA_ALPHA) * self._down_bps
            self._up_bps = EMA_ALPHA * raw_up + (1 - EMA_ALPHA) * self._up_bps
            self._available = True

    # -- readout ------------------------------------------------------

    def snapshot(self) -> dict:
        """
        Return the latest measurements. Safe to call from the Tk main thread.

        Returns a plain dict copy so the caller can never mutate monitor
        state, and never has to hold the lock while it formats widgets.
        """
        with self._lock:
            down = self._down_bps
            up = self._up_bps
            available = self._available
            latency = self._latency_ms
            link = dict(self._link)

        quality = (
            classify_quality(link["signal"], latency,
                             max(link["rx_mbps"], link["tx_mbps"]))
            if available else QUALITY_UNAVAILABLE
        )

        return {
            "available": available,
            "down_bps": down,
            "up_bps": up,
            "down_text": format_rate(down),
            "up_text": format_rate(up),
            "latency_ms": latency,
            "latency_text": f"{latency:.0f} ms" if latency is not None else "—",
            "quality": quality,
            "ssid": link["ssid"],
            "signal": link["signal"],
            "radio": link["radio"],
            "band": link["band"],
            "link_mbps": max(link["rx_mbps"], link["tx_mbps"]),
        }
