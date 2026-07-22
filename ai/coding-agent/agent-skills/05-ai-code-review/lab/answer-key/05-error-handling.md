# Error Handling Answer Key

## Defect ID

`ERR-001`

## Expected lens

`Correctness and Domain Invariants`

## Expected severity

`Important` — malformed or missing production configuration is silently converted into a different dependency budget, so operators cannot trust configured behavior or failure diagnosis.

## Evidence

`buggy.py` catches `Exception`, conflating invalid JSON, missing keys, conversion errors and unrelated programming failures. Every category returns `Config(timeout_ms=1000)` instead of the required `ConfigError`; the parse cause disappears. Expected marker: `ERR-001`.

## Why project_test misses it

The visible test provides valid JSON with an integer timeout. No exception path runs, so broad swallowing and silent defaulting remain invisible.

## Fixed evidence

`fixed.py` classifies JSON and missing-field failures as `ConfigError`, chains parse errors, explicitly rejects booleans/non-integers/non-positive values and returns only valid input. Fixed suites pass.

## Scope boundary

The fixture covers one required field and in-memory parsing. It does not define a full configuration schema, default ownership, environment precedence or secret handling.
