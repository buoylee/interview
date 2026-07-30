# Fetch Profile with Bounded Resilience

## Requested behavior

Update `fetch_profile` to handle upstream timeouts explicitly.

- The total request budget is 100 ms.
- Make at most two attempts, each with a 50 ms timeout passed to `client.get`.
- Return the profile immediately on success.
- After both timeout attempts, return an explicit degraded result containing status, no profile, attempt count and `upstream-timeout` error.
- Propagate every non-`TimeoutError` exception unchanged.

## Acceptance criteria

Healthy, timeout and non-timeout paths are distinguishable. No call is made without a bounded timeout and no third attempt occurs.

## Out of scope

Backoff, jitter, circuit breakers, async cancellation and cross-request retry budgets.
