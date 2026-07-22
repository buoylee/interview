# Project Overlay

- `gateway.capture` is an external monetary side effect; duplicate calls can charge a customer twice.
- Idempotency identity is the pair of key and request payload. Same key with different amount is a conflict, never a replay.
- The required guarantee is limited to repeated delivery to one live `PaymentService` instance.
- This fixture does not claim crash-safe or distributed exactly-once payment; production storage would need a separate durable design.
