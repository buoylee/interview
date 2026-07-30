# Timeout, Retry and Fallback Answer Key

## Defect ID

`RES-001`

## Expected lens

`Reliability and Fallback`

## Expected severity

`Important` — the change is untrustworthy under dependency failure: attempts have no deadline, exceed the retry cap and return an ambiguous valid-looking value.

## Evidence

`buggy.py` calls `client.get(user_id)` three times without a timeout. It swallows each `TimeoutError` and returns `{}`, even though an empty profile is a distinct valid business state. The focused timing client records `[None, None, None]`, not two bounded 50 ms attempts. Expected marker: `RES-001`.

## Why project_test misses it

The visible client succeeds immediately and accepts an optional timeout, so the first call returns a profile before retry and fallback behavior is exercised.

## Fixed evidence

`fixed.py` passes `timeout=0.05`, caps attempts at two, propagates non-timeout exceptions and returns an explicit `ProfileResult("degraded", ...)` after timeouts. Both fixed suites pass.

## Scope boundary

The fixture proves arguments, cap and result semantics; it does not measure actual elapsed time, cancellation, backoff, jitter or a circuit breaker.
