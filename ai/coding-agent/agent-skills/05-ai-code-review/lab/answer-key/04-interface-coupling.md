# Interface Coupling Answer Key

## Defect ID

`ARCH-001`

## Expected lens

`Architecture and Maintainability`

## Expected severity

`Important` — the service violates the required dependency boundary, so a valid repository implementation cannot substitute without failure.

## Evidence

`buggy.py` never calls the stable `total_for_customer` seam. It reaches through `repository.connection.orders`, leaking connection and storage layout into application logic. An interface-only repository raises `AttributeError`; expected marker: `ARCH-001`.

## Why project_test misses it

`CompatibleRepository` exposes both the intended method and the private `connection.orders` shape. The test double accidentally reproduces the forbidden implementation detail, allowing coupled code to pass.

## Fixed evidence

`fixed.py` types the dependency as an `OrderRepository` protocol and calls only `total_for_customer`. Both the compatible visible fake and interface-only hidden fake pass.

## Scope boundary

The fixture proves dependency direction and the declared seam. It does not prove a real database adapter's query correctness, performance or transaction behavior.
