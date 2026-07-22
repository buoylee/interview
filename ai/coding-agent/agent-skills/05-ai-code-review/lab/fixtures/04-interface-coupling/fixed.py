from typing import Protocol


class OrderRepository(Protocol):
    def total_for_customer(self, customer_id):
        ...


class OrderSummaryService:
    def __init__(self, repository: OrderRepository):
        self.repository = repository

    def summary(self, customer_id):
        return {
            "customer_id": customer_id,
            "total_cents": self.repository.total_for_customer(customer_id),
        }
