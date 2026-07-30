# Project Overlay

- `timeout_ms` controls a production dependency budget; changing it silently can cause latency amplification or premature failures.
- Defaults must be applied by an explicit configuration layer, never as fallback for malformed input.
- Callers depend on stable `ConfigError` classification; parse failures retain their original cause for diagnosis.
- Boolean values are not accepted as integers despite Python's type relationship.
