import keyring
import json

SERVICE_NAME = "MMMUT-WIFI-AUTOLOGIN"
MAX_ACCOUNTS = 2


def save_account(index, username, password):
    if not 1 <= index <= MAX_ACCOUNTS:
        raise ValueError(f"Account number must be between 1 and {MAX_ACCOUNTS}.")
    if not username or not password:
        raise ValueError("Username and password are required.")

    data = {
        "username": username,
        "password": password
    }

    keyring.set_password(
        SERVICE_NAME,
        f"account_{index}",
        json.dumps(data)
    )


def load_accounts():
    """Load all saved accounts from Windows Credential Manager."""
    accounts = []

    for i in range(1, MAX_ACCOUNTS + 1):

        data = keyring.get_password(
            SERVICE_NAME,
            f"account_{i}"
        )

        if data:
            account = json.loads(data)
            if account.get("username") and account.get("password"):
                accounts.append(account)

    return accounts


def delete_all_accounts():
    """Remove all saved accounts from Windows Credential Manager."""
    for i in range(1, MAX_ACCOUNTS + 1):
        try:
            keyring.delete_password(SERVICE_NAME, f"account_{i}")
        except keyring.errors.PasswordDeleteError:
            pass  # Account didn't exist, that's fine
