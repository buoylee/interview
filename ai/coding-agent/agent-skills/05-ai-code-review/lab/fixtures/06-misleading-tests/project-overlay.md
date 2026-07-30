# Project Overlay

- The returned string is used as an identity key; boundary whitespace or malformed structure can create duplicate or unusable identities.
- Normalization and validation are one public contract, not separate optional helpers.
- Test expected values must come from the stated contract, not by repeating the implementation expression.
- This project intentionally uses the bounded rules in the spec rather than claiming RFC-complete validation.
