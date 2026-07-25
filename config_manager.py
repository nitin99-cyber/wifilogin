from pathlib import Path
import json
import os
from metadata import APP_NAME

APP_DIR = Path(os.getenv("LOCALAPPDATA")) / APP_NAME
APP_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "setup_completed": False,
    "startup_enabled": False
}


def load_config():
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)