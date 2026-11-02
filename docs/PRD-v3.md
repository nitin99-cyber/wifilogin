# Product Requirements Document — WiFi Auto Login v3.0

| | |
|---|---|
| **Product** | MMMUT WiFi Auto Login |
| **Version** | 3.0.0 |
| **Platform** | Windows 10 / 11 (x64) |
| **Status** | Implemented |
| **Author** | Nitin Deep — B.Tech CSE'29, MMMUT Gorakhpur |
| **Supersedes** | v2.1.0 |

---

## 1. Summary

v3.0 changes what the product *is*. Versions 1 and 2 were a **boot-time
script**: run once at logon, log in, show a popup, exit. v3.0 is a **session
companion**: it stays resident, keeps the portal session alive across sleep and
reconnect events, and shows a small live readout of connection health.

The primary goal is stated as one sentence:

> Improve reliability after sleep/reconnect and introduce a lightweight,
> non-intrusive real-time connection monitor.

Everything below exists to serve that sentence, and every non-goal exists to
stop the product growing into something heavier than the problem deserves.

---

## 2. Problem statement

The captive portal used on campus (Cyberoam/Sophos at `172.16.1.3:8090`) issues
a session tied to a username and an IP lease. That session does not survive
everything the operating system does to a laptop. Three failure modes accounted
for essentially every complaint about v2.

**Sleep and wake.** Closing the lid suspends the machine. On resume, Windows
re-associates with the access point within a few seconds, so the Wi-Fi icon
shows connected — but the portal session has been reaped, so nothing routes.
v2 had already exited hours earlier and could not help. The user had to
re-launch the app manually, at which point they might as well have opened the
portal page themselves.

**Roaming and dropout.** Walking between buildings hands the client to a
different access point, and a brief dropout can invalidate the session. Same
outcome: Wi-Fi connected, internet dead, app not running.

**No feedback.** When the connection was bad, the user had no way to tell
whether the problem was signal strength, the portal, or the upstream link. The
absence of information turned every fault into "the app is broken".

A fourth problem was not about the network at all. v2's windows were sized in
hardcoded pixels and the process never declared DPI awareness, so on a
high-DPI display the text was blurry and the About dialog's Close button sat
below the bottom edge of the screen where it could not be clicked.

---

## 3. Goals

**G1 — Automatic recovery.** After sleep, wake, or any loss of connectivity,
the application restores authentication without the user doing anything.

**G2 — Real-time throughput.** Show current download and upload rates,
continuously, at negligible cost.

**G3 — Connection quality.** Report an interpretable quality verdict alongside
the raw numbers, so a user can distinguish "weak signal" from "portal down".

**G4 — Non-annoying UI.** The monitor must be small, semi-transparent, and out
of the way. It must reveal detail on demand rather than occupying space
permanently.

**G5 — No regressions.** Everything v2 did — multi-account failover, Windows
Credential Manager storage, start with Windows, portal logout — keeps working.

---

## 4. Non-goals

The following are explicitly out of scope, and requests for them should be
declined rather than deferred.

Bypassing bandwidth limits or any other portal restriction. This is a
convenience wrapper around a login form; it is not a circumvention tool, and
treating it as one would make it indefensible to run on university
infrastructure.

Continuous speed testing. Downloading test payloads on a loop would consume
shared campus bandwidth to produce a number the user did not ask for. §7
explains the alternative.

Telemetry, analytics, crash reporting, or any outbound connection other than
to the campus portal and one connectivity-check endpoint.

Advertising, upsells, or bundled software.

Linux and macOS support. The implementation is built on Win32 APIs
(`iphlpapi`, `WM_POWERBROADCAST`, Credential Manager) that have no portable
equivalent, and campus users are on Windows.

A full UI redesign. The setup window keeps its structure; it is made
resolution-safe, not reimagined.

---

## 5. Users

The single user persona is an MMMUT student or staff member on a personal
Windows laptop, with one to eight portal accounts, no administrator rights on
the network, and no interest in networking internals. They judge the product on
one question: *does the internet just work?*

A secondary persona is the maintainer — this project doubles as a portfolio
and interview artefact, which is why the codebase is documented at the level
it is.

---

## 6. Functional requirements

Each requirement lists the module that implements it. §16 has the full
traceability table.

### 6.1 Throughput monitoring

**FR-01 — Live throughput from interface counters.** Download and upload rates
are derived from the operating system's own per-adapter byte counters. Speed
tests are prohibited. → `network_monitor.py`

**FR-02 — Sampling.** Counters are sampled about once per second on a
background thread, never on the UI thread. Values are smoothed so the readout
does not jitter. A sampling failure degrades to "no data" and retries; it never
crashes the application. → `network_monitor.NetworkMonitor`

**FR-03 — Quality states.** The connection is classified as one of Excellent,
Good, Fair, Poor, or Unavailable. → `network_monitor.classify_quality`

**FR-04 — Latency.** Round-trip latency is measured and displayed in
milliseconds, formatted as `18 ms`. → `network_monitor.measure_latency_ms`

### 6.2 Popup UI

**FR-05 — Compact size.** Roughly 250–280 × 35–45 density-independent pixels
when idle. → `popup.COMPACT_W` / `COMPACT_H` (265 × 40 dp)

**FR-06 — Position.** Bottom-right of the usable desktop, above the taskbar,
correct at every display scaling factor. → `ui_scale.place_bottom_right`

**FR-07 — Transparency.** About 70–80% opacity when idle. → `popup.IDLE_OPACITY`
(0.78)

**FR-08 — Hover expansion.** Hovering reveals quality, band, latency, and
signal strength, and raises opacity to full. → `popup.MonitorPopup._on_enter`

**FR-09 — Minimise without stopping work.** Hiding the popup must not stop
network monitoring, sleep/wake detection, authentication monitoring, or
reconnection logic. → `popup.MonitorPopup.minimise`

**FR-10 — UI does not wait for authentication.** The window appears
immediately at launch and reports progress while authentication runs behind it.
→ `app.Application.start`

### 6.3 Sleep, wake, and recovery

**FR-11 — Resume detection.** The application detects that Windows has resumed
from sleep. → `connection_monitor._PowerWatcher`

**FR-12 — Network readiness.** After a resume, the application waits for the
network to actually become usable rather than sleeping for a fixed period.
→ `connection_monitor.ConnectionMonitor._wait_for_network_ready`

**FR-13 — Reauthentication after wake.** If the portal session did not survive
the sleep, the application logs in again automatically.
→ `ConnectionMonitor._recover`

**FR-14 — Reauthentication after loss.** The same applies to any mid-session
connectivity loss, not only to sleep. → `ConnectionMonitor._tick`

### 6.4 State machine

**FR-15 — Explicit states.** The application has exactly one authoritative
notion of what it is currently doing, drawn from this set:

| State | Meaning |
|---|---|
| `IDLE` | Nothing has happened yet |
| `NETWORK_DETECTING` | Waiting for an adapter / association |
| `NETWORK_CONNECTED` | Associated, internet not yet verified |
| `CHECKING_INTERNET` | Probing for connectivity |
| `PORTAL_CHECK` | Testing whether the captive portal is reachable |
| `AUTHENTICATING` | A login request is in flight |
| `CONNECTED` | Internet confirmed working |
| `SESSION_LOST` | Was connected, no longer is |
| `RECONNECTING` | Recovery in progress |
| `AUTHENTICATION_FAILED` | Portal rejected every account |
| `USER_LOGGED_OUT` | Deliberate logout; auto-login suppressed |
| `UNAVAILABLE` | No usable network at all |

→ `session_manager.py`

### 6.5 Authentication behaviour

**FR-16 — Multi-account failover.** Up to eight accounts are tried in order.
A "maximum login limit" response moves on to the next account. Invalid
credentials are not retried. → `SessionManager._authenticate_locked`

**FR-17 — Logout must stick (critical).** After a user-initiated logout, the
application must **not** log back in automatically. Only an explicit user
action re-enables automatic login. → `SessionManager.suppress_auto_login`

**FR-18 — Manual connect.** A Connect action always works and never produces
two concurrent login attempts. → `SessionManager.authenticate` single-flight
lock, plus a process-wide named mutex in `app._acquire_single_instance`

**FR-19 — Status display.** The UI shows a short, human-readable status for
every state. → `session_manager.STATE_LABELS`

**FR-20 — Logging.** Events are logged for diagnosis. Passwords, tokens, and
raw request bodies are never written to the log. → `logger.py`, enforced at
every call site

---

## 7. Design decisions

These are the choices where a reasonable engineer could have gone the other
way, recorded with the reason.

**Interface counters, not speed tests.** Windows already counts every byte
that crosses an adapter. Reading those counters costs one syscall and generates
zero traffic, whereas a speed test costs real bandwidth on a shared link. The
consequence is that an idle machine reads ~0 Mbps, which is *correct* — nothing
is being transferred — and the UI must never present the number as link
capacity.

**`ctypes` + `GetIfTable`, not `psutil`.** `psutil` would give the same numbers
in one line. It also adds a compiled dependency that inflates the PyInstaller
bundle for a project whose selling point is a small single `.exe`. The ctypes
struct definition is about sixty lines and is written once.

**TCP handshake, not ICMP ping.** Measuring latency with ICMP requires raw
sockets, which on Windows requires administrator rights. The product promises
it never needs elevation, so latency is measured as the time to complete a TCP
three-way handshake to the portal — one round trip, which is exactly the
quantity of interest, and it stays on the local network so it consumes no
internet bandwidth.

**Two independent wake detectors.** `WM_POWERBROADCAST` is the accurate,
event-driven route, but it depends on `pywin32` being importable. A wall-clock
gap check in the poll loop catches suspension even when no broadcast arrived.
Both are kept live because they fail differently, and a false positive costs
one extra connectivity check.

**Poll, don't push, into the UI.** Tk is not thread-safe. Rather than have
worker threads marshal calls onto the Tk thread for every update, workers
publish state behind a lock and the UI reads it on an `after()` timer. This
eliminates an entire category of intermittent, unreproducible crashes at the
cost of a negligible amount of idle work.

**Suppression never expires.** An auto-login suppression that timed out would
mean the application silently starts signing the user back in a few minutes
after they asked it not to. That is precisely the surprising behaviour FR-17
exists to prevent, so only an explicit user action clears the flag.

---

## 8. Module layout

```
app.py                  Entry point, lifecycle, thread ownership
setup.py                Setup wizard and management window
popup.py                Compact monitor overlay (presentation only)
ui_scale.py             DPI awareness, dp() units, work area, ScrollableFrame

session_manager.py      State machine, authentication policy, logout guard
connection_monitor.py   Wake detection, readiness waiting, recovery
network_monitor.py      Throughput, latency, quality classification

login.py                Portal login/logout HTTP calls
internet.py             Connectivity check
network.py              Captive-portal reachability check
wifi_scanner.py         netsh wrapper: scan, current SSID, connect
credential_manager.py   Windows Credential Manager via keyring
config_manager.py       JSON preferences
startup.py              HKCU Run key registration
logger.py               Append-only log file
metadata.py             Version and identity strings
```

The dependency direction is strictly one way: UI modules import logic modules,
never the reverse. `session_manager.py`, `connection_monitor.py`, and
`network_monitor.py` do not import `tkinter` at all, which is what makes them
testable from a plain Python prompt.

---

## 9. Threading model

| Thread | Created by | Lifetime | Responsibility |
|---|---|---|---|
| main | Python | process | Tk event loop; the only thread that touches widgets |
| `network-monitor` | `NetworkMonitor.start` | process | Sample counters once per second |
| `connection-monitor` | `ConnectionMonitor.start` | process | Connectivity polling and recovery |
| `power-watcher` | `_PowerWatcher.start` | process | Win32 message loop for resume events |
| `auth-*` | on demand | seconds | One authentication or logout attempt |

Every non-main thread is a daemon, so closing the UI can never leave an
orphaned process behind. Shared state is protected by `threading.Lock`.
Authentication is additionally guarded by a **non-blocking** lock, which
implements single-flight: the first caller proceeds, any concurrent caller is
told "already in progress" rather than queueing a second login.

---

## 10. Performance targets

| Metric | Target | Approach |
|---|---|---|
| Idle CPU | < 1% | One syscall per second; event-based sleeps, never busy-wait |
| Memory | < 60 MB | No frameworks beyond Tk; snapshots are plain dicts |
| Popup appears | < 1 s from launch | UI construction does no network I/O (FR-10) |
| Recovery after wake | < 10 s typical | Event-driven wake signal, then readiness backoff |
| Network cost of monitoring | 0 bytes | Counters are read locally |
| Latency probe cost | one local TCP handshake / 5 s | Portal is on the LAN |

The connectivity poll interval adapts: 15 s while healthy, 5 s while degraded.
There is no point checking often when nothing is wrong, and no point checking
rarely when something is.

---

## 11. Error handling

The governing rule is that **a monitoring failure is never fatal**. Each
worker loop wraps its body in a broad `except`, logs, and continues to the next
tick. Specific policies:

A counter read that fails three times in a row zeroes the displayed rates
rather than leaving a stale number on screen that the user would read as
current.

An adapter change — docking, VPN coming up, Wi-Fi toggled — resets the
baseline instead of computing a delta between two different adapters' lifetime
totals, which would render as an enormous fake spike.

Invalid credentials are not retried, because a wrong password will not start
working on the second attempt and retrying only hammers the portal.

A missing `pywin32` disables the power watcher and logs the fact; the
wall-clock fallback carries on.

If `pywin32`, `iphlpapi`, or `netsh` are all unavailable, the application still
authenticates. Monitoring is an enhancement, not a prerequisite.

---

## 12. Security requirements

Credentials are stored only in **Windows Credential Manager**, reached through
`keyring`. The application never writes a password to disk itself, and never
implements its own encryption — a hand-rolled scheme would be strictly worse
than the DPAPI-backed store the operating system already provides.

Passwords, session tokens, and raw request bodies are **never** logged. Login
attempts are logged as username plus portal status only.

No telemetry, no analytics, no crash reporting. Outbound connections are
limited to the campus portal (`172.16.1.3:8090`) and one connectivity-check
endpoint (`https://www.google.com/generate_204`).

No administrator rights are required, at install time or at run time. Startup
registration uses the per-user `HKCU\...\CurrentVersion\Run` key rather than
Task Scheduler, specifically to avoid needing elevation.

The application does not attempt to bypass, weaken, or probe portal
restrictions. It automates a form the user is entitled to submit.

---

## 13. Test plan

Grouped as an executable checklist; see `TESTING.md` for the full procedure.

**Group A — Throughput.** Idle reads near zero; a large download moves the
download figure and not the upload figure; the readout survives a counter wrap;
disabling the adapter shows Unavailable rather than a stale value.

**Group B — Quality and latency.** Latency renders as `18 ms`; an unreachable
portal shows `—`; walking away from the access point degrades the quality label
monotonically.

**Group C — Popup behaviour.** Size and position at 100%, 125%, 150%, and 200%
scaling; with the taskbar on each of the four edges; auto-hide taskbar;
1366×768 and 4K; hover expands and contracts; minimise leaves monitoring
running; the dot restores.

**Group D — Sleep and wake.** Sleep 1 minute and 3 hours; lid close and open;
hibernate; wake with Wi-Fi in range and out of range; confirm no login request
is sent when the session survived.

**Group E — Authentication policy.** Logout then wait five minutes — must stay
logged out. Logout then Connect — must log in. Two rapid Connect clicks — one
login. Two processes launched — one instance. Account 1 at max login limit —
fails over to account 2. Account 1 with a wrong password — no retry loop.

**Group F — Layout.** Every window fully reachable at every tested resolution;
the About dialog's Close button clickable on a 1366×768 screen; no clipped
controls; scrollbars appear only when needed.

---

## 14. Release criteria

Release requires all of: no unhandled exception in any monitoring thread over
a 24-hour run; recovery after wake succeeding in at least nine of ten trials;
idle CPU under 1% measured over ten minutes; the logout guard holding for the
full duration of Group E; every window usable at all four tested scaling
factors; and a log file containing no password-like string.

---

## 15. Milestones

| # | Milestone | Deliverable |
|---|---|---|
| 1 | Scaling foundation | `ui_scale.py` |
| 2 | Throughput sampler | `network_monitor.py` |
| 3 | State machine | `session_manager.py` |
| 4 | Wake and recovery | `connection_monitor.py` |
| 5 | Compact monitor UI | `popup.py` |
| 6 | Resolution-safe windows | `setup.py` |
| 7 | Lifecycle rewire | `app.py`, version bump |
| 8 | Documentation | `docs/` |

---

## 16. Traceability

| FR | Requirement | Implementation | Status |
|---|---|---|---|
| FR-01 | Throughput from counters | `network_monitor._read_interface_rows` | Done |
| FR-02 | 1 Hz off-thread sampling, smoothed | `NetworkMonitor._run`, `EMA_ALPHA` | Done |
| FR-03 | Five quality states | `classify_quality` | Done |
| FR-04 | Latency in ms | `measure_latency_ms`, `latency_text` | Done |
| FR-05 | 250–280 × 35–45 dp | `popup.COMPACT_W/H` | Done |
| FR-06 | Bottom-right, scaling-aware | `ui_scale.place_bottom_right` | Done |
| FR-07 | 70–80% idle opacity | `popup.IDLE_OPACITY` | Done |
| FR-08 | Hover expansion | `_on_enter` / `_maybe_contract` | Done |
| FR-09 | Minimise keeps monitoring | `minimise()` touches widgets only | Done |
| FR-10 | UI never waits for auth | `Application.start` spawns, never joins | Done |
| FR-11 | Resume detection | `_PowerWatcher` + clock-gap fallback | Done |
| FR-12 | Readiness, not fixed delay | `_wait_for_network_ready` | Done |
| FR-13 | Reauth after wake | `_recover` | Done |
| FR-14 | Reauth after loss | `_tick` | Done |
| FR-15 | Explicit state machine | `session_manager` constants | Done |
| FR-16 | Multi-account failover | `_authenticate_locked` | Done |
| FR-17 | Logout suppression | `_suppress_auto_login` | Done |
| FR-18 | Manual connect, no duplicates | `_auth_lock` + named mutex | Done |
| FR-19 | Status text per state | `STATE_LABELS` | Done |
| FR-20 | No secrets in logs | audited at every `log()` call | Done |

---

## 17. Open questions and future work

A system-tray icon would be a more conventional home for the minimised state
than the corner dot, but it needs either `pystray` or a hand-written
`Shell_NotifyIcon` wrapper. The dot ships first because it adds no dependency.

Per-monitor DPI change handling is declared (`PER_MONITOR_AWARE_V2`) but the
application does not currently listen for `WM_DPICHANGED`, so dragging the
popup between two displays with different scaling will not resize it until
restart.

Bandwidth history — a small sparkline of the last sixty seconds — would fit
the hover panel and needs only a ring buffer of existing samples.

---

*Related reading: [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit
together, [CONCEPTS.md](CONCEPTS.md) for definitions of every term used above,
and [INTERVIEW-QA.md](INTERVIEW-QA.md) for the questions this design invites.*
