# Task 8 report

## Status

Implemented real PostgreSQL 16 integration with Alembic migrations, explicit SQLAlchemy Core/domain mapping, async repositories, and an explicitly committed async UoW. No SQLite or database mocks were used.

## Docker prerequisite evidence

- Sandboxed `docker version` reached `/Users/buoy/.orbstack/run/docker.sock` but was denied by the filesystem sandbox.
- The approved retry reported Docker client 29.4.0, server 29.4.0, linux/arm64, OrbStack context.
- Local image: `postgres:16-alpine`, digest `sha256:d394728dee24b7791f1969c683f8b8410fe57450713a1db2aff5a500f0f98ab0`.
- Every behavioral integration run used Testcontainers `PostgresContainer("postgres:16-alpine", driver=None)`.

## Chronological RED / GREEN evidence

1. Surface RED: `uv run pytest tests/integration/test_sqlalchemy_uow.py -q` failed collection with `ModuleNotFoundError: order_service.adapters.sqlalchemy`.
2. Migration behavior RED against Postgres: `1 failed, 1 passed`; `NoSuchTableError: orders` after the intentionally empty migration executed.
3. Migration GREEN: `2 passed in 2.98s` after exact tables, unique constraint, defaults, and dispatch index were added.
4. Order/UoW behavior RED against Postgres: `8 failed`; importable stub lacked async context-manager behavior.
5. Outbox surface RED: collection failed because `SQLAlchemyOutboxRepository` was absent. Importable method stubs were then added.
6. Outbox behavior RED against Postgres: `6 failed`; all reached the unimplemented UoW/repository surface.
7. First order GREEN run: `7 passed, 1 failed`. Root cause was test setup applying two domain version transitions before one save, incompatible with the specified `expected = version - 1`; test was corrected to persist each transition.
8. Focused GREEN: order/UoW `8 passed`; outbox `6 passed`; migrations `2 passed`.
9. Expanded explicit suite GREEN: `16 passed in 3.38s` with schema type/nullability/default assertions.

## Transaction and locking evidence

- Fixture performs Alembic upgrade before yielding the async engine; cleanup executes real `TRUNCATE TABLE outbox_messages, orders CASCADE` after each test. There is no hidden outer transaction.
- Commit visibility is read from a fresh UoW. Normal no-commit exit and exception exit both disappear to a fresh UoW. A duplicate key raises SQLAlchemy `IntegrityError` from the real unique constraint.
- Optimistic save constrains both ID and expected version and raises `ConcurrentOrderUpdate` on rowcount mismatch.
- The lock test opens two independent AsyncSessions. Session one locks message 1 with `FOR UPDATE`; session two calls the production `claim_batch(limit=2)` and returns only message 2, proving `FOR UPDATE SKIP LOCKED` rather than merely inspecting SQL text.
- Lease tests prove an age of 29.999999 seconds remains leased and exactly 30 seconds is claimable, matching the memory adapter's `<=` boundary.

## Final verification

- Explicit Docker integration after Review Fix 2: `uv run pytest tests/integration -m "integration and docker" -q` -> `20 passed in 4.42s` (nonzero collection).
- Default Docker-free after Review Fix 2: `uv run pytest -q` -> `95 passed, 20 deselected in 0.61s`.
- Unit + component regression after Review Fix 2: `uv run pytest tests/unit tests/component -q` -> `95 passed in 0.46s`.
- `uv run alembic upgrade head --sql` generated PostgreSQL DDL successfully.
- `uv run python -m compileall -q src migrations tests/integration` passed.
- `git diff --check` passed.

## Files and interfaces

- Migration/config: `alembic.ini`, `migrations/env.py`, template, and revision `0001`.
- Adapter: `orders`, `outbox_messages`, `SQLAlchemyOrderRepository`, `SQLAlchemyOutboxRepository`, `SQLAlchemyUnitOfWork`, and `ConcurrentOrderUpdate`.
- Tests: shared Testcontainers/engine/session/cleanup fixtures; migration, UoW/order, and outbox integration suites.
- Default selection: pytest addopts now includes `-m not docker`; explicit Docker commands use `-m "integration and docker"`.
- Tutorial/navigation and the authorized Task 8-only implementation-plan correction are included.

## Self-review and concerns

- Explicit row mapping keeps ORM concerns out of domain dataclasses; Decimal, UUID, JSONB, timezone-aware timestamps, enum values, nullable references, versions, attempts, claims, and done state are covered.
- UoW commit remains explicit; exit always rolls back any active/uncommitted work and closes the session.
- No SQL, payment, HTTP, FastAPI, worker, or progress-file scope was changed.
- Concern: integration tests require Docker socket access outside the managed filesystem sandbox; this is environmental and recorded above.

## Review Fix 1

- Added a committed claim test that commits `claimed_at`, opens a fresh UoW to prove the row cannot be reclaimed at 29 seconds, and reads the timestamp through a fresh AsyncSession.
- Expanded migration reflection to exact table/column sets, named primary keys, named uniqueness, named non-unique composite index, absence of checks/foreign keys, UUID/JSONB/numeric/CHAR/text/integer/boolean/timestamptz types, precision/length/timezone flags, complete nullability, and server defaults.
- The downgrade test now restores head in `finally`. Autouse cleanup uses a `to_regclass`-guarded PostgreSQL block and preserves an original test exception if cleanup also fails, so cleanup cannot mask the primary failure.
- Replaced the indirect session-state assertion with an instrumented real `AsyncSession` subclass; normal and exceptional UoW exits each prove exactly one `close()` call.
- Split zero/negative limits and the two missing-ID transitions into independent tests so each branch has direct failure evidence.

### Review mutation RED evidence

- One targeted mutation run deliberately disabled zero-limit return, `mark_done` missing-ID rowcount, claim timestamp update, optimistic conflict rowcount, session close, and changed `CHAR(3)` to text. The selected suite produced seven intended failures: zero returned a claimed row; missing ID did not raise; a committed claim was immediately reclaimable; stale save did not raise; normal and exceptional close counts were zero; reflected currency was TEXT.
- A second targeted mutation independently changed negative-limit rejection and `mark_failed` missing-ID rowcount handling. Both selected tests failed because neither expected exception was raised.
- All mutations were restored. Focused migration/order/outbox GREEN: `20 passed in 3.47s` against Postgres 16.

## Review Fix 2

- Replaced partial column checks with an exact per-column `{type, nullable, default}` contract for both tables. This now explicitly covers `payment_reference` as nullable TEXT and proves every non-defaulted outbox column has no server default.
- Reflected uniqueness and independent indexes for both tables: orders has only the named idempotency uniqueness and no independent indexes; outbox has no uniqueness and exactly the named non-unique dispatch index. PostgreSQL's backing index for a unique constraint is normalized via SQLAlchemy's `duplicates_constraint` marker rather than double-counted.
- Mutation RED 1 added `uq_outbox_aggregate_id`; the schema test failed on the required empty outbox unique-constraint set.
- Mutation RED 2 removed that constraint but added `ix_orders_status`; after normalizing the uniqueness backing index, the schema test failed solely on the required empty orders index set.
- Mutation RED 3 restored indexes but changed `payment_reference` to CHAR(8) and added an unexpected topic default; the complete column-contract equality failed with both reflected differences.
- All migration mutations were restored. Focused migration GREEN: `2 passed in 3.43s` against Postgres 16.
