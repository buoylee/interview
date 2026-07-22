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


class PaymentVerificationTest(unittest.TestCase):
    def test_duplicate_delivery_does_not_repeat_capture(self):
        gateway = Gateway()
        service = implementation.PaymentService(gateway)

        first = service.charge("order-7", 2500)
        second = service.charge("order-7", 2500)

        self.assertEqual(
            second,
            first,
            "IDEM-001 duplicate delivery returned a different receipt",
        )
        self.assertEqual(
            gateway.calls,
            [2500],
            "IDEM-001 duplicate delivery repeated the external capture",
        )

    def test_same_key_with_different_amount_is_rejected(self):
        gateway = Gateway()
        service = implementation.PaymentService(gateway)
        service.charge("order-7", 2500)

        conflict_type = getattr(implementation, "IdempotencyConflict", None)
        if conflict_type is None:
            self.fail("IDEM-001 idempotency-key payload conflict is not detected")
        with self.assertRaises(conflict_type):
            service.charge("order-7", 3000)
        self.assertEqual(gateway.calls, [2500])


if __name__ == "__main__":
    unittest.main()
