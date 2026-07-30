import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class LedgerProjectTest(unittest.TestCase):
    def test_successful_transfer_moves_money(self):
        ledger = implementation.Ledger({"source": 100, "target": 20})
        ledger.transfer("source", "target", 30)
        self.assertEqual(ledger.balance("source"), 70)
        self.assertEqual(ledger.balance("target"), 50)


if __name__ == "__main__":
    unittest.main()
