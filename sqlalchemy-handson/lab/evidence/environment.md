# M1 environment manifest

## Hypothesis

- The committed evidence identifies every behavior-affecting runtime version.

## Setup

- database_url=postgresql+psycopg://sqlalchemy:***@localhost:55432/sqlalchemy_handson

## Command

- uv run python -m scenarios.environment

## Observation

- python=3.14.3
- implementation=cpython
- sqlalchemy=2.0.51
- psycopg=3.3.4
- postgresql=18.4 (Debian 18.4-1.pgdg13+1)
- platform=arm64-Darwin

## Explanation

- Version and platform context separate reproducible behavior from host-specific timing.

## Decision

- Regenerate this manifest whenever the lockfile or database image changes.

## Caveat

- The rendered database URL hides the password and contains no production secret.
