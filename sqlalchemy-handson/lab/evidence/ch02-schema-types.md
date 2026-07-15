# Chapter 02 — Schema and types

## Hypothesis

- MetaData naming conventions produce deterministic PostgreSQL constraint names.
- The PostgreSQL dialect preserves JSONB and partial-index intent.

## Setup

- PostgreSQL 18.4
- SQLAlchemy MetaData.create_all() for the M1 lab

## Observation

- table_count=8
- tables=idempotency_records,inventories,inventory_reservations,order_lines,orders,outbox_events,products,tenants
- product_unique_constraints=uq_products_tenant_id_id,uq_products_tenant_id_sku
- outbox_indexes=ix_outbox_events_claimable

## Explanation

- Named constraints become stable handles for migrations and IntegrityError translation.
- TypeDecorator.cache_ok=True lets the Money type participate in statement caching.

## Decision

- Name every business-relevant constraint and use Decimal-backed numeric storage for money.

## Caveat

- create_all() is a lab bootstrap mechanism; Alembic owns production schema evolution in M3.
