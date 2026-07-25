import json
from pathlib import Path

CONFIG_FILE = Path("config.json")


def load_config():
    if not CONFIG_FILE.exists():
        return {
            "setup_completed": False,
            "startup_enabled": False
        }

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)