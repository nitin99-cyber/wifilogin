import keyring
import json

SERVICE_NAME = "MMMUT-WIFI-AUTOLOGIN"


def save_account(index, username, password):
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

    for i in range(1, 3):

        data = keyring.get_password(
            SERVICE_NAME,
            f"account_{i}"
        )

        if data:
            accounts.append(json.loads(data))

    return accounts


def delete_all_accounts():
    """Remove all saved accounts from Windows Credential Manager."""
    for i in range(1, 3):
        try:
            keyring.delete_password(SERVICE_NAME, f"account_{i}")
        except keyring.errors.PasswordDeleteError:
            pass  # Account didn't exist, that's fine