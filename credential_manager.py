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

    accounts = []

    for i in range(1, 3):

        data = keyring.get_password(
            SERVICE_NAME,
            f"account_{i}"
        )

        if data:
            accounts.append(json.loads(data))

    return accounts