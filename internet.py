import requests


def is_connected():
    """Quick check: is the internet already available?"""
    try:
        response = requests.get(
            "https://www.google.com/generate_204",
            timeout=1
        )
        return response.status_code == 204
    except requests.RequestException:
        return False