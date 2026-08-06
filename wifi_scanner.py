"""
WiFi Scanner — Find and connect to the strongest MMMUT Wi-Fi network.

Scans visible SSIDs using `netsh wlan`, filters for MMMUT networks
(case-insensitive partial match), picks the one with the best signal,
and connects to it.
"""

import subprocess
import re
from logger import log

# Any SSID containing one of these tokens (case-insensitive) is an MMMUT network
MMMUT_KEYWORDS = ["mmmut"]


def _run_netsh(*args: str) -> str:
    """Run a netsh command and return its stdout."""
    cmd = ["netsh"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.stdout
    except Exception:
        return ""


def get_current_ssid() -> str | None:
    """Return the SSID the machine is currently connected to, or None."""
    output = _run_netsh("wlan", "show", "interfaces")
    for line in output.splitlines():
        # Match "    SSID                   : MyNetwork"
        # but NOT "    BSSID" lines
        m = re.match(r"^\s+SSID\s+:\s+(.+)$", line)
        if m:
            return m.group(1).strip()
    return None


def _is_mmmut_ssid(ssid: str) -> bool:
    """Check whether an SSID belongs to the MMMUT campus network."""
    lower = ssid.lower()
    return any(kw in lower for kw in MMMUT_KEYWORDS)


def scan_mmmut_networks() -> list[dict]:
    """
    Scan visible Wi-Fi networks and return MMMUT ones sorted by signal
    strength (strongest first).

    Each entry: {"ssid": str, "signal": int, "bssid": str}
    """
    output = _run_netsh("wlan", "show", "networks", "mode=bssid")

    networks: list[dict] = []
    current_ssid = None
    current_bssid = None

    for line in output.splitlines():
        # SSID line
        ssid_match = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line)
        if ssid_match:
            current_ssid = ssid_match.group(1).strip()
            continue

        # BSSID line
        bssid_match = re.match(r"^\s+BSSID\s+\d+\s*:\s*(.+)$", line)
        if bssid_match:
            current_bssid = bssid_match.group(1).strip()
            continue

        # Signal line (e.g. "Signal : 85%")
        signal_match = re.match(r"^\s+Signal\s*:\s*(\d+)%", line)
        if signal_match and current_ssid and current_bssid:
            signal = int(signal_match.group(1))
            if _is_mmmut_ssid(current_ssid):
                networks.append({
                    "ssid": current_ssid,
                    "signal": signal,
                    "bssid": current_bssid,
                })

    # Sort by signal strength descending
    networks.sort(key=lambda n: n["signal"], reverse=True)
    
    # Deduplicate by SSID, keeping the one with the highest signal
    seen_ssids = set()
    deduped_networks = []
    for net in networks:
        if net["ssid"] not in seen_ssids:
            deduped_networks.append(net)
            seen_ssids.add(net["ssid"])
            
    return deduped_networks


def connect_to_best_mmmut() -> str | None:
    """
    Find the strongest MMMUT Wi-Fi and connect to it.

    Returns the SSID connected to, or None if no MMMUT network was found
    or the connection failed.

    If already connected to an MMMUT network, returns that SSID immediately.
    """
    # Already connected to an MMMUT network?
    current = get_current_ssid()
    if current and _is_mmmut_ssid(current):
        log(f"Already connected to MMMUT network: {current}")
        return current

    # Scan
    networks = scan_mmmut_networks()
    if not networks:
        log("No MMMUT Wi-Fi networks found in scan.")
        return None

    best = networks[0]
    log(f"Best MMMUT network: {best['ssid']} "
        f"(signal {best['signal']}%, BSSID {best['bssid']})")

    # Try connecting to the best network, then fall back to others
    for net in networks:
        ssid = net["ssid"]
        log(f"Connecting to {ssid} (signal {net['signal']}%)...")

        output = _run_netsh("wlan", "connect", f'name="{ssid}"')

        if "successfully" in output.lower():
            log(f"Connected to {ssid}")
            return ssid
        else:
            log(f"Failed to connect to {ssid}: {output.strip()}")

    log("Could not connect to any MMMUT network.")
    return None
