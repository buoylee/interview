# Chapter 01 — Engine execution path

## Hypothesis

- create_engine() configures an Engine without checking out a connection.
- Entering engine.connect() checks out a DBAPI connection before SQL execution.
- Reusing one process-scoped Engine reuses its Pool across work units.

## Setup

- dialect=postgresql
- driver=psycopg
- pool=QueuePool

## Command

- uv run python -m scenarios.ch01_engine_execution

## Observation

- naive_distinct_pools=True
- corrected_reused_pool=True
- checkout_during_connect=True
- sql_not_executed_at_checkout=True
- event_order=checkout->before_cursor_execute
- statement=SELECT %(value)s
- result=42
- dialect=postgresql
- driver=psycopg

## Explanation

- Engine coordinates a Pool and Dialect; the Dialect adapts SQLAlchemy constructs to psycopg.
- Bound values travel through the DBAPI parameter channel rather than string concatenation.

## Decision

- Create one process-scoped Engine per database role, not one Engine per request.

## Caveat

- Event hooks observe public execution events; they do not expose every internal call frame.
