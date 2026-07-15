from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, event, text

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
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
            result = connection.scalar(text("SELECT :value"), {"value": 42})
    finally:
        event.remove(engine.pool, "checkout", on_checkout)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    return Evidence(
        title="Chapter 01 — Engine execution path",
        hypothesis=(
            "create_engine() configures an Engine without checking out a connection.",
            "The first execute checks out a DBAPI connection before cursor execution.",
        ),
        setup=(
            f"dialect={engine.dialect.name}",
            f"driver={engine.dialect.driver}",
            f"pool={type(engine.pool).__name__}",
        ),
        observation=(
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
