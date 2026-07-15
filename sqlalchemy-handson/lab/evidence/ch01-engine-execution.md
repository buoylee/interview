# Chapter 01 — Engine execution path

## Hypothesis

- create_engine() configures an Engine without checking out a connection.
- The first execute checks out a DBAPI connection before cursor execution.

## Setup

- dialect=postgresql
- driver=psycopg
- pool=QueuePool

## Observation

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
