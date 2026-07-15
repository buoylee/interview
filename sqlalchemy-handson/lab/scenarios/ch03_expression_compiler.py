from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.dialects import postgresql

from order_service.db.engine import build_engine
from order_service.db.schema import metadata, products, tenants
from order_service.db.settings import DatabaseSettings
from order_service.db.statements import product_by_sku_statement
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    tenant_id = uuid4()
    product_id = uuid4()
    hostile_sku = "x'; DROP TABLE products; --"
    naive_sql = f"SELECT * FROM products WHERE sku = '{hostile_sku}'"
    statement = product_by_sku_statement()
    compiled = statement.params(tenant_id=tenant_id, sku=hostile_sku).compile(
        dialect=postgresql.dialect()  # type: ignore[no-untyped-call]
    )
    compiled_sql = "\n".join(line.rstrip() for line in str(compiled).splitlines())
    cache: dict[Any, Any] = {}
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(tenants.insert().values(id=tenant_id, name="Compiler Tenant"))
        connection.execute(
            products.insert().values(
                id=product_id,
                tenant_id=tenant_id,
                sku="COMPILER-1",
                name="Compiler Product",
                unit_price=Decimal("10.00"),
                attributes={},
            )
        )
        cached_connection = connection.execution_options(compiled_cache=cache)
        for _ in range(2):
            cached_connection.execute(
                statement,
                {"tenant_id": tenant_id, "sku": "COMPILER-1"},
            ).one()

    return Evidence(
        title="Chapter 03 — Expression compiler and cache",
        hypothesis=(
            "Changing bound values does not change the structural SQL shape.",
            "Two equivalent executions reuse one explicit compiled-cache entry.",
        ),
        setup=("PostgreSQL dialect compiler", "Connection-level compiled_cache dictionary"),
        command="uv run python -m scenarios.ch03_expression_compiler",
        observation=(
            f"naive_sql={naive_sql}",
            f"naive_hostile_value_present_in_sql={hostile_sku in naive_sql}",
            f"compiled_sql={compiled_sql}",
            f"hostile_value_present_in_sql={hostile_sku in str(compiled)}",
            f"corrected_hostile_value_present_in_sql={hostile_sku in str(compiled)}",
            f"bound_sku={compiled.params['sku']}",
            f"compiled_cache_entries={len(cache)}",
        ),
        explanation=(
            "ClauseElement structure and bound values travel separately into compilation "
            "and execution.",
            "Cache keys describe statement structure; uncacheable custom types disable reuse "
            "conservatively.",
        ),
        decision=(
            "Compose SQL with SQLAlchemy expressions and bind parameters; never concatenate "
            "request values.",
        ),
        caveat=(
            "The explicit dictionary exposes cache cardinality for the lab; production Engines "
            "manage their own cache.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch03-expression-compiler.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
