import os
import sys
import subprocess
import winreg
from pathlib import Path

from metadata import APP_NAME

# Registry key for current-user startup programs
# This is what Task Manager → Startup Apps reads from
_REG_KEY_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

# Legacy Task Scheduler task name (for cleanup of old installs)
_LEGACY_TASK_NAME = APP_NAME


def _get_exe_path() -> str:
    """Return the path to the application executable."""
    if getattr(sys, "frozen", False):
        # Running as packaged EXE (PyInstaller)
        return sys.executable
    else:
        # Running from source — use pythonw to avoid console window
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        app = Path(__file__).parent / "app.py"
        return f'"{pythonw}" "{app}"'


def add_to_startup() -> bool:
    """Add app to Windows startup via Registry Run key (HKCU).

    This method:
    - Does NOT require admin privileges
    - Shows up in Task Manager → Startup Apps
    - Runs immediately on user logon (no delay)
    """
    exe_path = _get_exe_path()
    task_command = f'{exe_path} --background'

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, task_command)
        winreg.CloseKey(key)

        # Clean up any legacy scheduled task or shortcut from older versions
        _cleanup_legacy()

        return True
    except OSError:
        # Fallback: try the Startup folder shortcut method
        return _add_startup_shortcut()


def remove_from_startup() -> bool:
    """Remove app from Windows startup (Registry + legacy cleanup)."""
    # Remove registry entry
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except OSError:
        pass  # Entry didn't exist

    # Clean up legacy methods too
    _cleanup_legacy()

    return True


def is_startup_enabled() -> bool:
    """Check if app is registered in Windows startup."""
    # Check Registry Run key (primary method)
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except OSError:
        pass

    # Check legacy Startup folder shortcut as fallback
    return _legacy_shortcut_path().exists()


# ── Legacy cleanup (old schtasks + Startup folder) ────────────────────


def _cleanup_legacy():
    """Remove any leftover scheduled task or Startup shortcut from older versions."""
    # Remove old scheduled task (silently, may fail without admin)
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", _LEGACY_TASK_NAME, "/F"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        pass

    # Remove old Startup folder shortcut
    _remove_startup_shortcut()


# ── Startup folder methods (fallback) ─────────────────────────────────


def _startup_folder() -> Path:
    """Return the Windows Startup folder path."""
    return (
        Path(os.getenv("APPDATA"))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def _legacy_shortcut_path() -> Path:
    """Return the path to the legacy Startup shortcut."""
    return _startup_folder() / f"{APP_NAME}.lnk"


def _add_startup_shortcut() -> bool:
    """Fallback: create a Startup folder shortcut if Registry method fails."""
    try:
        from win32com.client import Dispatch

        startup_file = _legacy_shortcut_path()
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(startup_file))

        if getattr(sys, "frozen", False):
            shortcut.TargetPath = sys.executable
            shortcut.Arguments = "--background"
            shortcut.WorkingDirectory = str(Path(sys.executable).parent)
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            app = Path(__file__).parent / "app.py"
            shortcut.TargetPath = str(pythonw)
            shortcut.Arguments = f'"{app}" --background'
            shortcut.WorkingDirectory = str(app.parent)

        shortcut.IconLocation = shortcut.TargetPath
        shortcut.save()
        return True
    except Exception:
        return False


def _remove_startup_shortcut():
    """Remove the legacy Startup folder shortcut if it exists."""
    shortcut = _legacy_shortcut_path()
    if shortcut.exists():
        shortcut.unlink()