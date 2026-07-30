# Idempotent Payment Capture

## Requested behavior

Change `PaymentService.charge` to accept an `idempotency_key`.

- The first key/payload pair calls the gateway and returns its receipt.
- Repeating the same key with the same `amount_cents` returns the original receipt without another gateway call.
- Reusing the key with a different amount raises `IdempotencyConflict` and never calls the gateway again.

## Acceptance criteria

- Replay and payload-conflict behavior are tested through the public service method.
- A conflict cannot change the result stored for the original request.

## Out of scope

Cross-process coordination, durable storage, crash recovery and a gateway-side exactly-once guarantee.
