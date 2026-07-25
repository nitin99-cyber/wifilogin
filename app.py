from config_manager import load_config
from credential_manager import load_accounts

from internet import is_connected
from network import is_cyberoam_network
from login import login

import setup
from logger import log


def main():
    log("Application Started")

    config = load_config()

    # First run setup
    if not config["setup_completed"]:
        log("First run detected. Opening setup window.")
        setup.run()
        return

    # Check internet
    log("Checking internet connection...")

    if is_connected():
        log("Internet already available. Exiting.")
        return

    # Check Cyberoam
    log("Internet unavailable. Checking Cyberoam network...")

    if not is_cyberoam_network():
        log("Not connected to Cyberoam network. Exiting.")
        return

    log("Cyberoam network detected.")

    # Load accounts
    accounts = load_accounts()

    if not accounts:
        log("No accounts found in Credential Manager.")
        return

    # Try each account
    for account in accounts:

        username = account["username"]
        password = account["password"]

        log(f"Trying account: {username}")

        try:
            status, message = login(username, password)

            log(f"Server Response: {status} - {message}")

            if status == "LIVE":
                log(f"Login Successful using {username}")
                return

        except Exception as e:
            log(f"Error while logging in with {username}: {e}")

    log("All accounts failed.")


if __name__ == "__main__":
    main()