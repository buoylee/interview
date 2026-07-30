import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class LedgerVerificationTest(unittest.TestCase):
    def test_failed_transfer_leaves_every_balance_unchanged(self):
        ledger = implementation.Ledger({"source": 100, "target": 20})
        before = dict(ledger.balances)

        with self.assertRaises(implementation.AccountNotFound):
            ledger.transfer("source", "missing", 30)

        self.assertEqual(
            ledger.balances,
            before,
            "CONS-001 failed transfer exposed a partial balance mutation",
        )


if __name__ == "__main__":
    unittest.main()
