"""
metadata.py — Single source of truth for identity and version strings.

Everything user-visible imports from here: the popup, the About dialog, the
PyInstaller spec and the installer script. One edit changes the version
everywhere, which is why v2's "badge says 2.0.0 but the code says 2.1.0"
mismatch cannot happen for values kept in this file.
"""

APP_NAME = "MMMUT WiFi Auto Login"
VERSION = "3.1.0"
AUTHOR = "Nitin Deep"
DESCRIPTION = (
    "Automatic login and live connection\n"
    "monitor for the MMMUT Wi-Fi portal."
)
COPYRIGHT = "© 2026"
LICENSE = "MIT License"
GITHUB_URL = "https://github.com/nitin99-cyber/mmmutwifilogin"
WEBSITE = ""
EMAIL = "nitincsemmmut@gmail.com"
