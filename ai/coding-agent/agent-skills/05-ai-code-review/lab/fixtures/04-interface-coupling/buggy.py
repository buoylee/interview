class OrderSummaryService:
    def __init__(self, repository):
        self.repository = repository

    def summary(self, customer_id):
        rows = self.repository.connection.orders
        total = sum(
            row["amount_cents"]
            for row in rows
            if row["customer_id"] == customer_id
        )
        return {"customer_id": customer_id, "total_cents": total}
