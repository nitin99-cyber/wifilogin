from credential_manager import save_account, load_accounts

save_account(
    1,
    "username1",
    "password1"
)

save_account(
    2,
    "username2",
    "password2"
)

print(load_accounts())