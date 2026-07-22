# Project Overlay

- `total_for_customer(customer_id)` is the stable application-facing repository seam.
- Connection objects, storage shape and `orders` layout are private adapter details and may change independently.
- `OrderSummaryService` owns response composition; the repository owns querying and aggregation.
- Tests should use an interface-only fake so leaked adapter knowledge cannot pass accidentally.
