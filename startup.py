import os
import sys
from pathlib import Path

from win32com.client import Dispatch


STARTUP_FOLDER = (
    Path(os.getenv("APPDATA"))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)

SHORTCUT_NAME = "MMMUT WiFi Auto Login.lnk"


def add_to_startup():

    startup_file = STARTUP_FOLDER / SHORTCUT_NAME

    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(startup_file))

    if getattr(sys, "frozen", False):
        # Running as packaged EXE
        shortcut.TargetPath = sys.executable
        shortcut.WorkingDirectory = str(Path(sys.executable).parent)

    else:
        # Running from source
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        app = Path(__file__).parent / "app.py"

        shortcut.TargetPath = str(pythonw)
        shortcut.Arguments = f'"{app}"'
        shortcut.WorkingDirectory = str(app.parent)

    shortcut.IconLocation = shortcut.TargetPath
    shortcut.save()

    return True


def remove_from_startup():

    startup_file = STARTUP_FOLDER / SHORTCUT_NAME

    if startup_file.exists():
        startup_file.unlink()

    return True


def is_startup_enabled():

    startup_file = STARTUP_FOLDER / SHORTCUT_NAME

    return startup_file.exists()