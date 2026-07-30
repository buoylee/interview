# Repository-backed Order Summary

## Requested behavior

Change `OrderSummaryService` to receive a repository and return a customer's total.

- The service depends only on `repository.total_for_customer(customer_id)`.
- It returns `{"customer_id": ..., "total_cents": ...}`.
- Storage connections, table/collection layout and row aggregation stay behind the repository interface.

## Acceptance criteria

Any object implementing the one-method repository seam can be used. The service never inspects repository internals.

## Out of scope

Repository persistence implementation, currency handling, authorization and pagination.
