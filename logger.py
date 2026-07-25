from pathlib import Path
import os
from datetime import datetime

APP_DIR = Path(os.getenv("LOCALAPPDATA")) / "MMMUT WiFi Auto Login"
APP_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = APP_DIR / "wifi_login.log"


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")