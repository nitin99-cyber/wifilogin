import time
import xml.etree.ElementTree as ET
import requests

from config import USERNAME, PASSWORD, LOGIN_URL, PRODUCT_TYPE

def login ():
    payload ={
        "mode":"191",
        "username": USERNAME,
        "password": PASSWORD,
        "a": str(int(time.time() * 1000)),
        "producttype": PRODUCT_TYPE,
    }
    print("Username:", USERNAME)
    print("Password length:", len(PASSWORD))
    print("Payload:", payload)
    response=requests.post(
        LOGIN_URL,
        data=payload,
        timeout=10
    )
    print("Status Code:", response.status_code)
    print("Response:")
    print(response.text)
    root = ET.fromstring(response.text)
    status = root.findtext("status")
    message = root.findtext("message")
    return status, message