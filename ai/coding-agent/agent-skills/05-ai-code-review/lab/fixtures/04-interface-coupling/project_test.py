import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class Connection:
    orders = [
        {"customer_id": "c-1", "amount_cents": 1200},
        {"customer_id": "c-1", "amount_cents": 300},
        {"customer_id": "c-2", "amount_cents": 900},
    ]


class CompatibleRepository:
    def __init__(self):
        self.connection = Connection()

    def total_for_customer(self, customer_id):
        return sum(
            row["amount_cents"]
            for row in self.connection.orders
            if row["customer_id"] == customer_id
        )


class SummaryProjectTest(unittest.TestCase):
    def test_calculates_customer_total(self):
        service = implementation.OrderSummaryService(CompatibleRepository())
        self.assertEqual(
            service.summary("c-1"),
            {"customer_id": "c-1", "total_cents": 1500},
        )


if __name__ == "__main__":
    unittest.main()
