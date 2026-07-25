from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

USERNAME = os.getenv("USERNAME", "").strip()
PASSWORD = os.getenv("PASSWORD", "").strip()
LOGIN_URL = "http://172.16.1.3:8090/login.xml"
PRODUCT_TYPE = "0"

if not USERNAME or not PASSWORD:
    raise RuntimeError("USERNAME and PASSWORD must be set in the .env file or environment.")

