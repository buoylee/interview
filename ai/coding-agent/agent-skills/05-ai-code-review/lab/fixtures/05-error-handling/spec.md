# Strict Configuration Loading

## Requested behavior

`load_config(raw)` returns a `Config` with a positive integer `timeout_ms`.

- Invalid JSON raises `ConfigError` and preserves `json.JSONDecodeError` as `__cause__`.
- Missing `timeout_ms` raises `ConfigError`.
- Boolean, non-integer and non-positive timeout values raise `ConfigError`.
- No invalid or missing value is replaced by a default.

## Acceptance criteria

Valid input returns exactly the configured integer. Each invalid category fails explicitly through the public function.

## Out of scope

Additional config fields, environment merging, files, schema libraries and dynamic reload.
