# Chapter 04 — Core DML and Result

## Hypothesis

- executemany sends one statement shape with multiple parameter sets.
- ON CONFLICT updates the existing tenant/SKU row and RETURNING exposes its identity.

## Setup

- Two tenants
- One product upserted twice plus one companion product
- Inventory replenished to 8 and 6 units

## Observation

- executemany_tenant_rows=2
- upsert_preserved_product_id=True
- returned_product_name=Updated
- inventory_available=8
- inventory_version=2
- tenant_report_rows=2
- tenant_stock_values=130.00,130.00

## Explanation

- PostgreSQL RETURNING removes a follow-up lookup for server-visible results.
- Result.mappings() makes the selected row shape explicit before conversion to a record type.

## Decision

- Use Core for explicit set-oriented DML and reports whose SQL shape is the primary abstraction.

## Caveat

- ON CONFLICT and JSONB are PostgreSQL dialect capabilities; portability requires a deliberate fallback.
