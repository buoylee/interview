# Project Overlay

- An empty profile is valid business data and must not represent dependency failure.
- Timeout is the only retryable error in this fixture; non-timeout exceptions retain their original type.
- The end-to-end budget is 100 ms: two sequential attempts of 50 ms maximum each.
- A degraded response must expose status, attempts and stable error classification for callers and telemetry.
- Real wall-clock scheduling and cancellation are out of scope; the test asserts propagated per-attempt budgets and retry cap.
