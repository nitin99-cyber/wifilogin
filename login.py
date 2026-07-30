import time
import xml.etree.ElementTree as ET
import requests

from config import LOGIN_URL, PRODUCT_TYPE


def login(username, password):
    payload = {
        "mode": "191",
        "username": username,
        "password": password,
        "a": str(int(time.time() * 1000)),
        "producttype": PRODUCT_TYPE,
    }

    response = requests.post(
        LOGIN_URL,
        data=payload,
        timeout=2,
    )

    root = ET.fromstring(response.text)

    status = root.findtext("status")
    message = root.findtext("message")

    return status, message