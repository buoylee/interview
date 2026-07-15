from __future__ import annotations

import argparse
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from order_service.db.engine import build_engine
from order_service.db.schema import metadata, tenants
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)

    with engine.connect() as connection:
        before_execute = connection.in_transaction()
        connection.scalar(text("SELECT 1"))
        after_execute = connection.in_transaction()
        connection.rollback()

    failed_tenant_id = uuid4()
    with engine.connect() as connection:
        connection.execute(
            tenants.insert().values(id=failed_tenant_id, name="Failed Transaction Tenant")
        )
        with suppress(IntegrityError):
            connection.execute(
                tenants.insert().values(id=failed_tenant_id, name="Duplicate Tenant")
            )
        failed_transaction_active = connection.in_transaction()
        failed_transaction_rejected_statement = False
        try:
            connection.scalar(text("SELECT 1"))
        except DBAPIError:
            failed_transaction_rejected_statement = True
        connection.rollback()
        after_failed_rollback = connection.in_transaction()
        connection_reusable_after_rollback = connection.scalar(text("SELECT 1")) == 1
        connection.rollback()

    rollback_tenant_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                tenants.insert().values(id=rollback_tenant_id, name="Rollback Tenant")
            )
            raise RuntimeError("failure injection")
    except RuntimeError:
        pass
    with engine.connect() as connection:
        rolled_back_count = connection.scalar(
            select(func.count())
            .select_from(tenants)
            .where(tenants.c.id == rollback_tenant_id)
        )

    savepoint_tenant_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            tenants.insert().values(id=savepoint_tenant_id, name="Savepoint Tenant")
        )
        try:
            with connection.begin_nested():
                connection.execute(
                    tenants.insert().values(
                        id=savepoint_tenant_id,
                        name="Duplicate Tenant",
                    )
                )
        except IntegrityError:
            pass
    with engine.connect() as connection:
        committed_count = connection.scalar(
            select(func.count())
            .select_from(tenants)
            .where(tenants.c.id == savepoint_tenant_id)
        )

    return Evidence(
        title="Chapter 05 — Connection transaction state",
        hypothesis=(
            "The first execute triggers autobegin on a fresh Connection.",
            "Engine.begin() rolls back on exception, while a savepoint can roll back "
            "one failed unit.",
            "PostgreSQL rejects statements after an error until the failed transaction "
            "is rolled back.",
        ),
        setup=(
            "Fresh PostgreSQL schema",
            "One failed root transaction and one exception block",
            "One nested transaction",
        ),
        command="uv run python -m scenarios.ch05_connection_transactions",
        observation=(
            f"in_transaction_before_execute={before_execute}",
            f"in_transaction_after_execute={after_execute}",
            f"exception_block_rolled_back={rolled_back_count == 0}",
            f"savepoint_preserved_outer={committed_count == 1}",
            f"failed_transaction_active={failed_transaction_active}",
            "failed_transaction_rejected_statement="
            f"{failed_transaction_rejected_statement}",
            "naive_failed_transaction_rejected="
            f"{failed_transaction_rejected_statement}",
            f"in_transaction_after_rollback={after_failed_rollback}",
            "connection_reusable_after_rollback="
            f"{connection_reusable_after_rollback}",
            "corrected_connection_reusable="
            f"{connection_reusable_after_rollback}",
        ),
        explanation=(
            "BEGIN (implicit) is SQLAlchemy/DBAPI transaction state, not necessarily a "
            "literal BEGIN sent at that instant.",
            "A database error leaves PostgreSQL's root transaction failed; rollback ends "
            "it before the same Connection can execute again.",
            "The outer transaction owns atomicity; begin_nested() only scopes a savepoint "
            "within it.",
        ),
        decision=(
            "Place the transaction boundary at the application-service operation and keep "
            "lower layers commit-free.",
        ),
        caveat=(
            "A savepoint does not isolate external side effects and does not shorten the "
            "outer transaction lifetime.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch05-connection-transactions.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
