# Chapter 06 — Pooling and capacity

## Hypothesis

- pool_size=2 and max_overflow=0 allow exactly two simultaneous checkouts.
- A third checkout waits pool_timeout before SQLAlchemy raises TimeoutError.

## Setup

- pool_size=2
- max_overflow=0
- pool_timeout=0.2 seconds

## Command

- uv run python -m scenarios.ch06_pooling_capacity

## Observation

- configured_hard_limit=2
- checked_out_at_timeout=2
- timeout_class=sqlalchemy.exc.TimeoutError
- naive_checkout_timed_out=True
- corrected_pool_recovered=True
- timeout_within_expected_bound=True
- error_message=QueuePool limit of size 2 overflow 0 reached, connection timed out, timeout 0.20 (Background on this error at: https://sqlalche.me/e/20/3o7r)

## Explanation

- QueuePool limits concurrent checked-out connections, not request concurrency.
- The process-wide ceiling multiplies pool limits by workers and service instances.

## Decision

- Budget database connections across all processes before changing pool_size.

## Caveat

- The timeout duration is an invariant window; scheduler-level milliseconds vary by host.
