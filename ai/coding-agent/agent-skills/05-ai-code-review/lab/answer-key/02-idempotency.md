# Idempotency Answer Key

## Defect ID

`IDEM-001`

## Expected lens

`Correctness and Domain Invariants`

## Expected severity

`Critical` — duplicate message delivery repeats an external monetary side effect and can charge a customer more than once.

## Evidence

`buggy.py` accepts the key but discards it. Two calls with `("order-7", 2500)` invoke `gateway.capture` twice and return different receipts. The implementation also has no way to reject the same key paired with a different amount. Expected marker: `IDEM-001`.

## Why project_test misses it

`project_test.py` calls `charge` only once. Passing proves the new signature and initial receipt, not replay or payload-conflict semantics.

## Fixed evidence

`fixed.py` stores `(amount_cents, receipt)` by key, returns the original receipt for an exact replay and raises `IdempotencyConflict` before a second capture when payload differs. Both fixed suites pass.

## Scope boundary

The in-memory map proves repeated delivery only within one live process. It does not survive crashes or coordinate service replicas, and it does not establish gateway-side exactly-once execution.
