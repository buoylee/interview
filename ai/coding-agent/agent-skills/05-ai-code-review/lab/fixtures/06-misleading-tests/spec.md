# Normalize Email Identity

## Requested behavior

`normalize_email(value)` must:

- trim boundary whitespace;
- lowercase the full value;
- require exactly one `@`;
- require non-empty local and domain parts;
- reject any embedded whitespace with `ValueError`;
- return the normalized value when valid.

## Acceptance criteria

Tests cover both transformations and malformed identities through the public function.

## Out of scope

RFC-complete email validation, Unicode/IDNA policy, provider-specific canonicalization and deliverability.
