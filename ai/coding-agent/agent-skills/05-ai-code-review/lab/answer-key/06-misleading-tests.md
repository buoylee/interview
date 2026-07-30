# Misleading Tests Answer Key

## Defect ID

`TEST-001`

## Expected lens

Primary: `Test Quality`. Linked finding: `Spec Compliance`.

## Expected severity

`Important` — the visible suite gives false confidence while the implementation omits identity-key normalization and validation required by the spec.

## Evidence

`buggy.py` only lowercases. It preserves boundary whitespace and accepts values without `@`, with empty parts, multiple separators or embedded whitespace. The visible test asserts only the one transformation the implementation happens to perform. Expected marker: `TEST-001`.

## Why project_test misses it

The only input is already structurally valid and has no boundary whitespace. Its expected value distinguishes lowercase from identity, but does not exercise the rest of the explicit contract or any invalid case.

## Fixed evidence

`fixed.py` strips then lowercases, enforces exactly one separator and non-empty parts, rejects remaining whitespace and returns the valid normalized key. Both fixed suites pass.

## Scope boundary

The fixture evaluates the bounded project spec, not RFC-complete email validity, Unicode equivalence, provider-specific rules or deliverability.
