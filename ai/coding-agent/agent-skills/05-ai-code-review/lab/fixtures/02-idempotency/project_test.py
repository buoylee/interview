import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class Gateway:
    def __init__(self):
        self.calls = []

    def capture(self, amount_cents):
        self.calls.append(amount_cents)
        return f"receipt-{len(self.calls)}"


class PaymentProjectTest(unittest.TestCase):
    def test_first_charge_returns_gateway_receipt(self):
        gateway = Gateway()
        service = implementation.PaymentService(gateway)
        self.assertEqual(service.charge("order-7", 2500), "receipt-1")


if __name__ == "__main__":
    unittest.main()
