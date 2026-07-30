import requests


def is_cyberoam_network():
    """Check if the Cyberoam portal at 172.16.1.3 is reachable (local network)."""
    try:
        requests.get("http://172.16.1.3:8090", timeout=0.5)
        return True
    except requests.RequestException:
        return False