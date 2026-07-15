from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import Engine, inspect

from order_service.db.engine import build_engine
from order_service.db.schema import metadata
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    unique_names = sorted(
        constraint["name"]
        for constraint in inspector.get_unique_constraints("products")
        if constraint["name"] is not None
    )
    index_names = sorted(
        index["name"]
        for index in inspector.get_indexes("outbox_events")
        if index["name"] is not None
    )
    return Evidence(
        title="Chapter 02 — Schema and types",
        hypothesis=(
            "MetaData naming conventions produce deterministic PostgreSQL constraint names.",
            "The PostgreSQL dialect preserves JSONB and partial-index intent.",
        ),
        setup=("PostgreSQL 18.4", "SQLAlchemy MetaData.create_all() for the M1 lab"),
        observation=(
            f"table_count={len(table_names)}",
            f"tables={','.join(table_names)}",
            f"product_unique_constraints={','.join(unique_names)}",
            f"outbox_indexes={','.join(index_names)}",
        ),
        explanation=(
            "Named constraints become stable handles for migrations and "
            "IntegrityError translation.",
            "TypeDecorator.cache_ok=True lets the Money type participate in statement caching.",
        ),
        decision=(
            "Name every business-relevant constraint and use Decimal-backed "
            "numeric storage for money.",
        ),
        caveat=(
            "create_all() is a lab bootstrap mechanism; Alembic owns production "
            "schema evolution in M3.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("evidence/ch02-schema-types.md"))
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
