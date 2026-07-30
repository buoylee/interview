# Project Overlay

- Ledger balances represent monetary value; conservation is a Critical domain invariant.
- `transfer` is one atomic business operation even though the in-memory implementation uses two assignments.
- No caller may observe a partial transfer after an exception.
- Validation must finish before the first mutation, or mutations must be rolled back reliably.
- This fixture evaluates single-process behavior only; persistence and concurrency are out of scope.
