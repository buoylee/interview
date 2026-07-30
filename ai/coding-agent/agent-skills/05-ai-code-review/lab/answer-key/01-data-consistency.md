# Data Consistency Answer Key

## Defect ID

`CONS-001`

## Expected lens

`Correctness and Domain Invariants`

## Expected severity

`Critical` — a credible path mutates monetary state without completing the balancing credit, violating conservation and atomic failure.

## Evidence

In `buggy.py`, `transfer` subtracts from `source_id` before validating that `target_id` exists. Calling `transfer("source", "missing", 30)` raises `AccountNotFound` only after the source balance has changed from 100 to 70.

The minimum verification is the public failing-call scenario followed by comparison of all balances to a pre-call snapshot. Expected marker: `CONS-001`.

## Why project_test misses it

`project_test.py` exercises only a valid source/target pair. Both mutations complete, so it proves the happy path but never observes exception atomicity.

## Fixed evidence

`fixed.py` validates both account IDs and sufficient funds before computing and assigning either new balance. Both visible and hidden suites pass for the fixed variant.

## Scope boundary

The key proves only single-process in-memory atomic failure. It does not claim database transactionality, thread safety, crash recovery or multi-currency correctness.
