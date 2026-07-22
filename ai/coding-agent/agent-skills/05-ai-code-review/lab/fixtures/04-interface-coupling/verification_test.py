import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class InterfaceOnlyRepository:
    def total_for_customer(self, customer_id):
        return 1500


class SummaryVerificationTest(unittest.TestCase):
    def test_service_depends_only_on_repository_interface(self):
        service = implementation.OrderSummaryService(InterfaceOnlyRepository())
        try:
            result = service.summary("c-1")
        except AttributeError as exc:
            self.fail(f"ARCH-001 service leaked persistence internals: {exc}")

        self.assertEqual(
            result,
            {"customer_id": "c-1", "total_cents": 1500},
        )


if __name__ == "__main__":
    unittest.main()
