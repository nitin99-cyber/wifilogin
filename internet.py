import requests

def is_connected():
    try:
        response=requests.get(
            "https://www.google.com/generate_204",
            timeout=5
        )
        return response.status_code == 204
    except requests.RequestException:
        return False