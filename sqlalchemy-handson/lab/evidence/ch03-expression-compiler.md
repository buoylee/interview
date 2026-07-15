# Chapter 03 — Expression compiler and cache

## Hypothesis

- Changing bound values does not change the structural SQL shape.
- Two equivalent executions reuse one explicit compiled-cache entry.

## Setup

- PostgreSQL dialect compiler
- Connection-level compiled_cache dictionary

## Command

- uv run python -m scenarios.ch03_expression_compiler

## Observation

- naive_sql=SELECT * FROM products WHERE sku = 'x'; DROP TABLE products; --'
- naive_hostile_value_present_in_sql=True
- compiled_sql=SELECT products.id, products.tenant_id, products.sku, products.name, products.unit_price, products.attributes
FROM products
WHERE products.tenant_id = %(tenant_id)s::UUID AND products.sku = %(sku)s
- hostile_value_present_in_sql=False
- corrected_hostile_value_present_in_sql=False
- bound_sku=x'; DROP TABLE products; --
- compiled_cache_entries=1

## Explanation

- ClauseElement structure and bound values travel separately into compilation and execution.
- Cache keys describe statement structure; uncacheable custom types disable reuse conservatively.

## Decision

- Compose SQL with SQLAlchemy expressions and bind parameters; never concatenate request values.

## Caveat

- The explicit dictionary exposes cache cardinality for the lab; production Engines manage their own cache.
