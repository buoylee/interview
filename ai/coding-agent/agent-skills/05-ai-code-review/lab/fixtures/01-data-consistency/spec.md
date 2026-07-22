# Transfer Funds

## Requested behavior

Add `Ledger.transfer(source_id, target_id, amount)`.

- `amount` must be positive.
- Source and target accounts must both exist.
- The source must have sufficient funds.
- A successful transfer debits source and credits target by the same amount.
- Total balance is conserved.
- Any validation failure is atomic: every observable balance remains exactly as it was before the call.

## Acceptance criteria

- Missing accounts raise `AccountNotFound`.
- Insufficient funds raise `InsufficientFunds`.
- Non-positive amounts raise `ValueError`.
- Success and failure paths are covered at the public `Ledger` interface.

## Out of scope

Persistence, concurrent callers, currency conversion and cross-process transactions.
