from pathlib import Path
from datetime import datetime

LOG_FILE = Path("wifi_login.log")


def log(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n"
        )