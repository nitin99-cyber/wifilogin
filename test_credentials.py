import unittest
from unittest.mock import patch

from credential_manager import MAX_ACCOUNTS, load_accounts, save_account


class CredentialManagerTests(unittest.TestCase):
    @patch("credential_manager.keyring.set_password")
    def test_save_account_rejects_indices_above_limit(self, set_password):
        with self.assertRaises(ValueError):
            save_account(MAX_ACCOUNTS + 1, "user", "password")
        set_password.assert_not_called()

    @patch("credential_manager.keyring.get_password")
    def test_load_accounts_reads_all_eight_slots(self, get_password):
        get_password.side_effect = [
            '{"username": "user%d", "password": "pass%d"}' % (i, i)
            for i in range(1, MAX_ACCOUNTS + 1)
        ]
        accounts = load_accounts()
        self.assertEqual(len(accounts), MAX_ACCOUNTS)
        self.assertEqual(accounts[-1]["username"], "user8")


if __name__ == "__main__":
    unittest.main()