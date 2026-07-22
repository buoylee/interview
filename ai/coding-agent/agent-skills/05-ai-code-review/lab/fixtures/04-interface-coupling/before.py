class OrderSummaryService:
    def summary(self, customer_id, orders):
        total = sum(
            row["amount_cents"]
            for row in orders
            if row["customer_id"] == customer_id
        )
        return {"customer_id": customer_id, "total_cents": total}
