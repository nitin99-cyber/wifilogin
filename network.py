import requests


def is_cyberoam_network():
    try:
        requests.get("http://172.16.1.3:8090", timeout=3)
        return True
    except requests.RequestException:
        return False