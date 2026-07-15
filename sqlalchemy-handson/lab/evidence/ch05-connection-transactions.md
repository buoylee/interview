# Chapter 05 — Connection transaction state

## Hypothesis

- The first execute triggers autobegin on a fresh Connection.
- Engine.begin() rolls back on exception, while a savepoint can roll back one failed unit.
- PostgreSQL rejects statements after an error until the failed transaction is rolled back.

## Setup

- Fresh PostgreSQL schema
- One failed root transaction and one exception block
- One nested transaction

## Command

- uv run python -m scenarios.ch05_connection_transactions

## Observation

- in_transaction_before_execute=False
- in_transaction_after_execute=True
- exception_block_rolled_back=True
- savepoint_preserved_outer=True
- failed_transaction_active=True
- failed_transaction_rejected_statement=True
- naive_failed_transaction_rejected=True
- in_transaction_after_rollback=False
- connection_reusable_after_rollback=True
- corrected_connection_reusable=True

## Explanation

- BEGIN (implicit) is SQLAlchemy/DBAPI transaction state, not necessarily a literal BEGIN sent at that instant.
- A database error leaves PostgreSQL's root transaction failed; rollback ends it before the same Connection can execute again.
- The outer transaction owns atomicity; begin_nested() only scopes a savepoint within it.

## Decision

- Place the transaction boundary at the application-service operation and keep lower layers commit-free.

## Caveat

- A savepoint does not isolate external side effects and does not shorten the outer transaction lifetime.
