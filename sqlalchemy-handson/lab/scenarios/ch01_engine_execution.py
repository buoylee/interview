from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    naive_engines = (create_engine(engine.url), create_engine(engine.url))
    try:
        for naive_engine in naive_engines:
            with naive_engine.connect() as connection:
                assert connection.scalar(text("SELECT 1")) == 1
        naive_distinct_pools = naive_engines[0].pool is not naive_engines[1].pool
    finally:
        for naive_engine in naive_engines:
            naive_engine.dispose()

    corrected_pool_ids: set[int] = set()
    for _ in range(2):
        corrected_pool_ids.add(id(engine.pool))
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    corrected_reused_pool = len(corrected_pool_ids) == 1

    event_order: list[str] = []
    statements: list[str] = []

    def on_checkout(dbapi_connection: Any, connection_record: Any, connection_proxy: Any) -> None:
        del dbapi_connection, connection_record, connection_proxy
        event_order.append("checkout")

    def before_cursor_execute(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        del connection, cursor, parameters, context, executemany
        event_order.append("before_cursor_execute")
        statements.append(statement)

    event.listen(engine.pool, "checkout", on_checkout)
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        with engine.connect() as connection:
            checkout_during_connect = event_order == ["checkout"]
            sql_not_executed_at_checkout = not statements
            result = connection.scalar(text("SELECT :value"), {"value": 42})
    finally:
        event.remove(engine.pool, "checkout", on_checkout)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    return Evidence(
        title="Chapter 01 — Engine execution path",
        hypothesis=(
            "create_engine() configures an Engine without checking out a connection.",
            "Entering engine.connect() checks out a DBAPI connection before SQL execution.",
            "Reusing one process-scoped Engine reuses its Pool across work units.",
        ),
        setup=(
            f"dialect={engine.dialect.name}",
            f"driver={engine.dialect.driver}",
            f"pool={type(engine.pool).__name__}",
        ),
        command="uv run python -m scenarios.ch01_engine_execution",
        observation=(
            f"naive_distinct_pools={naive_distinct_pools}",
            f"corrected_reused_pool={corrected_reused_pool}",
            f"checkout_during_connect={checkout_during_connect}",
            f"sql_not_executed_at_checkout={sql_not_executed_at_checkout}",
            f"event_order={'->'.join(event_order)}",
            f"statement={statements[0]}",
            f"result={result}",
            f"dialect={engine.dialect.name}",
            f"driver={engine.dialect.driver}",
        ),
        explanation=(
            "Engine coordinates a Pool and Dialect; the Dialect adapts "
            "SQLAlchemy constructs to psycopg.",
            "Bound values travel through the DBAPI parameter channel rather than "
            "string concatenation.",
        ),
        decision=(
            "Create one process-scoped Engine per database role, not one Engine per request.",
        ),
        caveat=(
            "Event hooks observe public execution events; they do not expose every "
            "internal call frame.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch01-engine-execution.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
